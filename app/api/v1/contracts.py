"""
Contracts API — Sprint 4

  GET  /contracts                            — lista por tenant
  POST /contracts                            — criar contrato (a partir de proposta ou avulso)
  GET  /contracts/{id}                       — detalhe
  POST /contracts/{id}/generate-pdf          — gera/regenera PDF
  GET  /contracts/{id}/download              — URL de download do PDF
"""

import json
import logging
from datetime import UTC, date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.contract import Contract, ContractStatus
from app.models.contract_template import ContractTemplate
from app.models.process import Process
from app.models.proposal import Proposal
from app.models.stage_output import StageOutput
from app.models.user import User
from app.services.audit_hash import stamp_audit_hash
from app.services.contract_generator import (
    fill_contract_template,
    find_template_for_demand,
    render_pdf,
)
from app.services.mirante_documents import (
    DocumentGenerationError,
    build_contrato,
    render_contrato_text,
)
from app.services.mirante_documents import render_pdf as render_mirante_pdf
from app.services.storage import get_storage_service
from app.services.tenant_guard import (
    exigir_do_tenant,
    exigir_do_tenant_ou_global,
    exigir_relacoes_do_tenant,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ContractCreate(BaseModel):
    client_id: int
    proposal_id: Optional[int] = None
    process_id: Optional[int] = None
    template_id: Optional[int] = None
    title: str


class ContractFromProposal(BaseModel):
    """S5-B — contrato nasce da proposta ACEITA (moldes Mirante)."""

    proposal_id: int
    bonus_malus_ativo: Optional[bool] = None   # OPCIONAL; None = default do tenant (desligado)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_contract_or_404(db: Session, contract_id: int, tenant_id: int) -> Contract:
    c = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.tenant_id == tenant_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    return c


def _serialize(c: Contract) -> dict:
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "proposal_id": c.proposal_id,
        "process_id": c.process_id,
        "client_id": c.client_id,
        "template_id": c.template_id,
        "status": c.status.value,
        "title": c.title,
        "has_pdf": bool(c.pdf_storage_key),
        "pdf_storage_key": c.pdf_storage_key,
        "signed_at": c.signed_at,
        "signed_by_client": c.signed_by_client,
        "signed_registered_by_user_id": c.signed_registered_by_user_id,
        "has_signed_pdf": bool(c.signed_pdf_storage_key),
        "sent_at": c.sent_at,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _audit_contract(db: Session, c: Contract, user_id: Optional[int], action: str,
                    extra: Optional[dict] = None) -> None:
    """Transição auditada (quem/quando) com hash chain (Princípio 2) — espelha o
    padrão do S5-A para propostas."""
    details = {"contract_id": c.id, "status": c.status.value}
    if extra:
        details.update(extra)
    log = AuditLog(
        tenant_id=c.tenant_id, user_id=user_id, entity_type="contract",
        entity_id=c.id, action=action,
        details=json.dumps(details, ensure_ascii=False, default=str),
    )
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)


def _resolve_demand_type(db: Session, contract: Contract) -> Optional[str]:
    """Deduz o `demand_type` a partir do processo (direto ou via proposta).

    As três resoluções abaixo eram `filter(X.id == …)` puro. Um contrato que
    tivesse nascido apontando para processo/proposta de outro tenant (o que o
    `POST /contracts` permitia até esta frente) fazia o template ser escolhido
    pelo `demand_type` alheio. Agora tudo passa pelo tenant do próprio contrato.
    """
    tenant_id = contract.tenant_id
    if contract.process_id:
        proc = (
            db.query(Process)
            .filter(Process.id == contract.process_id, Process.tenant_id == tenant_id)
            .first()
        )
        if proc and proc.demand_type:
            return proc.demand_type.value
    if contract.proposal_id:
        prop = (
            db.query(Proposal)
            .filter(Proposal.id == contract.proposal_id, Proposal.tenant_id == tenant_id)
            .first()
        )
        if prop and prop.process_id:
            proc = (
                db.query(Process)
                .filter(Process.id == prop.process_id, Process.tenant_id == tenant_id)
                .first()
            )
            if proc and proc.demand_type:
                return proc.demand_type.value
    return None


# ---------------------------------------------------------------------------
# GET /contracts
# ---------------------------------------------------------------------------

@router.get("/")
def list_contracts(
    process_id: Optional[int] = None,
    client_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    q = db.query(Contract).filter(Contract.tenant_id == current_user.tenant_id)
    if process_id:
        q = q.filter(Contract.process_id == process_id)
    if client_id:
        q = q.filter(Contract.client_id == client_id)
    contracts = q.order_by(Contract.created_at.desc()).offset(skip).limit(limit).all()
    return [_serialize(c) for c in contracts]


# ---------------------------------------------------------------------------
# POST /contracts
# ---------------------------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_contract(
    body: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    # `client_id`, `proposal_id` e `process_id` chegam do corpo e eram gravados
    # sem conferência: o contrato nascia no tenant A com o cliente e o processo
    # de B, e a geração de conteúdo/PDF incorporava dados de B numa peça de A.
    exigir_relacoes_do_tenant(db, current_user.tenant_id, body.model_dump())

    # `template_id` tem tenancy DUAL (`ContractTemplate.tenant_id` nullable:
    # None = template global do produto). Nullable não quer dizer "qualquer um
    # serve": o template PRIVADO de outro tenant vira o texto de uma peça
    # assinada. Global passa; do vizinho, não.
    exigir_do_tenant_ou_global(
        db, ContractTemplate, body.template_id, current_user.tenant_id, rotulo="Modelo de contrato"
    )

    # Resolver template se não informado
    template_id = body.template_id
    if not template_id:
        demand_type: Optional[str] = None
        if body.process_id:
            proc = exigir_do_tenant(
                db, Process, body.process_id, current_user.tenant_id, rotulo="Caso"
            )
            if proc and proc.demand_type:
                demand_type = proc.demand_type.value
        tmpl = find_template_for_demand(db, current_user.tenant_id, demand_type)
        template_id = tmpl.id if tmpl else None

    contract = Contract(
        tenant_id=current_user.tenant_id,
        client_id=body.client_id,
        proposal_id=body.proposal_id,
        process_id=body.process_id,
        template_id=template_id,
        title=body.title,
        created_by_user_id=current_user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    logger.info("Contrato criado: id=%s proposal=%s", contract.id, body.proposal_id)
    return _serialize(contract)


# ---------------------------------------------------------------------------
# POST /contracts/gerar — contrato nasce da proposta ACEITA (moldes Mirante, S5-B)
# ---------------------------------------------------------------------------

@router.post("/gerar", status_code=status.HTTP_201_CREATED)
def gerar_contrato_de_proposta(
    body: ContractFromProposal,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Gera a MINUTA de contrato (8 cláusulas Mirante) a partir de uma proposta
    ACEITA (S5-B). Bloco único do processo corrente (multi-bloco = dívida #67).

    Validações de consistência ANTES de emitir (422 com mensagem clara):
      1. soma dos serviços == total declarado da proposta;
      2. soma das parcelas == total do bloco (cláusula 2ª == cláusula 1ª);
      3. matrículas citadas existem e são VIGENTES.
    Também bloqueia se a proposta não estiver ACEITA, se o perfil do tenant
    estiver incompleto, ou se sobrar placeholder não resolvido.

    RASCUNHO (minuta) — o consultor revisa/edita e assina (IA propõe, humano
    decide); a assinatura em si segue o fluxo do S5-C."""
    proposal = db.query(Proposal).filter(
        Proposal.id == body.proposal_id,
        Proposal.tenant_id == current_user.tenant_id,
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")

    try:
        doc = build_contrato(db, proposal, bonus_malus_ativo=body.bonus_malus_ativo)
        corpo = render_contrato_text(doc)
    except DocumentGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    title = f"Contrato — {doc.bloco['imovel']}"
    contract = Contract(
        tenant_id=current_user.tenant_id,
        client_id=proposal.client_id,
        proposal_id=proposal.id,
        process_id=proposal.process_id,
        title=title,
        content=corpo,
        created_by_user_id=current_user.id,
    )
    db.add(contract)
    db.flush()  # id p/ nome do arquivo

    pdf_key: Optional[str] = None
    storage_warning: Optional[str] = None
    try:
        pdf_bytes = render_mirante_pdf(title, corpo)
        filename = f"contrato_{contract.id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
        result = get_storage_service().upload_bytes(
            content=pdf_bytes, filename=filename, content_type="application/pdf",
            tenant_id=current_user.tenant_id, process_id=proposal.process_id or 0,
        )
        pdf_key = result["storage_key"]
        contract.pdf_storage_key = pdf_key
    except Exception as exc:  # não-fatal: minuta textual persiste
        logger.warning("PDF do contrato %s não armazenado: %s", contract.id, exc)
        storage_warning = f"Minuta gerada; PDF não armazenado ({exc})."

    # Registra a minuta em Saídas (E7)
    artifact = None
    if proposal.process_id:
        content_data = doc.to_content_data()
        content_data["pdf_storage_key"] = pdf_key
        content_data["contract_id"] = contract.id
        artifact = StageOutput(
            tenant_id=current_user.tenant_id,
            process_id=proposal.process_id,
            macroetapa="contrato_formalizacao",
            output_type="minuta",
            title=title,
            content=corpo,
            content_data=content_data,
            produced_by_user_id=current_user.id,
            needs_human_validation=True,  # RASCUNHO — humano decide
        )
        db.add(artifact)

    db.commit()
    db.refresh(contract)

    logger.info("Contrato %s gerado da proposta %s (aceita). pdf=%s", contract.id, proposal.id, pdf_key)
    return {
        "message": "Minuta de contrato gerada como rascunho." if not storage_warning else "Minuta gerada.",
        "warning": storage_warning,
        "contract": _serialize(contract),
        "artifact_id": artifact.id if artifact else None,
        "content": corpo,
    }


# ---------------------------------------------------------------------------
# GET /contracts/{id}
# ---------------------------------------------------------------------------

@router.get("/{contract_id}")
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    c = _get_contract_or_404(db, contract_id, current_user.tenant_id)
    data = _serialize(c)
    # Incluir conteúdo preenchido se disponível
    if c.content:
        data["content"] = c.content
    return data


# ---------------------------------------------------------------------------
# POST /contracts/{id}/generate-pdf
# ---------------------------------------------------------------------------

@router.post("/{contract_id}/generate-pdf")
def generate_pdf(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """
    Preenche o template com dados reais, gera PDF e armazena no MinIO.
    """
    contract = _get_contract_or_404(db, contract_id, current_user.tenant_id)

    if not contract.template_id:
        # Tentar resolver template automaticamente
        demand_type = _resolve_demand_type(db, contract)
        tmpl = find_template_for_demand(db, current_user.tenant_id, demand_type)
        if not tmpl:
            raise HTTPException(
                status_code=422,
                detail="Nenhum template de contrato disponível. Selecione um template manualmente.",
            )
        contract.template_id = tmpl.id
        db.add(contract)
        db.flush()

    # Preencher template e salvar conteúdo no banco
    try:
        filled_content = fill_contract_template(db, contract)
    except Exception as exc:
        logger.error("Erro ao preencher template do contrato %s: %s", contract_id, exc)
        raise HTTPException(status_code=500, detail=f"Erro ao processar template: {exc}")

    contract.content = filled_content
    db.add(contract)

    # Gerar bytes do PDF
    pdf_bytes: Optional[bytes] = None
    try:
        pdf_bytes = render_pdf(contract, filled_content)
    except Exception as exc:
        logger.error("Erro ao renderizar PDF do contrato %s: %s", contract_id, exc)
        # Salva o conteúdo mesmo sem PDF e retorna aviso ao invés de 500
        db.commit()
        db.refresh(contract)
        return {
            "message": "Conteúdo gerado, mas o PDF não pôde ser renderizado.",
            "warning": str(exc),
            "pdf_storage_key": None,
            "contract": _serialize(contract),
        }

    # Upload no MinIO (não-fatal: salva o conteúdo mesmo se o storage estiver indisponível)
    storage_warning: Optional[str] = None
    if pdf_bytes:
        filename = f"contrato_{contract_id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
        try:
            storage = get_storage_service()
            result = storage.upload_bytes(
                content=pdf_bytes,
                filename=filename,
                content_type="application/pdf",
                tenant_id=current_user.tenant_id,
                process_id=contract.process_id or 0,
            )
            contract.pdf_storage_key = result["storage_key"]
            db.add(contract)
        except Exception as exc:
            logger.warning("Falha ao armazenar PDF do contrato %s no storage: %s", contract_id, exc)
            storage_warning = f"PDF gerado mas não armazenado (storage indisponível): {exc}"

    db.commit()
    db.refresh(contract)

    logger.info("Contrato %s processado. storage_key=%s warning=%s", contract_id, contract.pdf_storage_key, storage_warning)
    return {
        "message": "PDF gerado com sucesso." if not storage_warning else "Conteúdo salvo. PDF gerado mas não armazenado.",
        "warning": storage_warning,
        "pdf_storage_key": contract.pdf_storage_key,
        "contract": _serialize(contract),
    }


# ---------------------------------------------------------------------------
# GET /contracts/{id}/download
# ---------------------------------------------------------------------------

@router.get("/{contract_id}/download")
def download_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Retorna URL pré-assinada para download do PDF."""
    contract = _get_contract_or_404(db, contract_id, current_user.tenant_id)
    if not contract.pdf_storage_key:
        raise HTTPException(status_code=404, detail="PDF ainda não gerado. Use POST /generate-pdf primeiro.")

    try:
        storage = get_storage_service()
        url = storage.generate_presigned_get_url(contract.pdf_storage_key, expires_in=3600)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL: {exc}")

    return {"download_url": url, "expires_in": 3600}


# ---------------------------------------------------------------------------
# Ciclo de assinatura MANUAL (S5-C) — rascunho → ENVIADO → ASSINADO
# ---------------------------------------------------------------------------

@router.post("/{contract_id}/aprovar-enviar")
def aprovar_enviar_contrato(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Consultor aprova a minuta (rascunho) e a marca como ENVIADA ao cliente.
    Transição auditada. Só um rascunho pode ser aprovado/enviado."""
    contract = _get_contract_or_404(db, contract_id, current_user.tenant_id)
    if contract.status != ContractStatus.draft:
        raise HTTPException(
            status_code=422,
            detail=f"Só um contrato em rascunho pode ser aprovado/enviado (estado atual: '{contract.status.value}').",
        )
    contract.status = ContractStatus.sent
    contract.sent_at = datetime.now(UTC)
    db.add(contract)
    _audit_contract(db, contract, current_user.id, "contract_sent")
    db.commit()
    db.refresh(contract)
    logger.info("Contrato %s aprovado e enviado por user=%s", contract_id, current_user.id)
    return _serialize(contract)


def _parse_signed_at(raw: str) -> datetime:
    """Aceita 'YYYY-MM-DD' ou ISO completo; devolve datetime tz-aware (UTC)."""
    raw = (raw or "").strip()
    try:
        if len(raw) == 10:  # data pura
            d = date.fromisoformat(raw)
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Data de assinatura inválida — use o formato AAAA-MM-DD.",
        ) from exc


@router.post("/{contract_id}/assinar")
async def assinar_contrato(
    contract_id: int,
    signed_at: str = Form(...),
    signed_pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Registra a assinatura MANUAL do contrato (MVP, sem integração externa).

    Exige contrato ENVIADO (aprove/envie antes). Grava `signed_at` (data
    informada), quem registrou e — se enviado — o PDF assinado (upload OPCIONAL).
    Preencher `signed_at` satisfaz o gate E7 (`has_contract_signed`) e, sendo a
    E7 a etapa terminal, CONCLUI o caso (marca `Process.closed_at`). Transição
    auditada. Assinatura eletrônica externa (gov.br/Clicksign) = dívida pós-MVP."""
    contract = _get_contract_or_404(db, contract_id, current_user.tenant_id)
    if contract.status != ContractStatus.sent:
        raise HTTPException(
            status_code=422,
            detail=(
                "Só um contrato ENVIADO pode ser assinado — aprove e envie a minuta "
                f"antes (estado atual: '{contract.status.value}')."
            ),
        )
    dt = _parse_signed_at(signed_at)

    # Upload OPCIONAL do PDF assinado (não-fatal: registra a assinatura mesmo se o
    # storage falhar — degrada com elegância).
    storage_warning: Optional[str] = None
    if signed_pdf is not None:
        try:
            data = await signed_pdf.read()
            filename = f"contrato_{contract_id}_assinado_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
            result = get_storage_service().upload_bytes(
                content=data, filename=filename,
                content_type=signed_pdf.content_type or "application/pdf",
                tenant_id=current_user.tenant_id, process_id=contract.process_id or 0,
            )
            contract.signed_pdf_storage_key = result["storage_key"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF assinado do contrato %s não armazenado: %s", contract_id, exc)
            storage_warning = f"Assinatura registrada; PDF assinado não armazenado ({exc})."

    contract.status = ContractStatus.signed
    contract.signed_at = dt
    contract.signed_registered_by_user_id = current_user.id
    db.add(contract)

    # Caso CONCLUI: a E7 é terminal; contrato assinado marca o fecho do caso.
    #
    # Este era o ponto mais grave da Frente 1: a resolução do processo era
    # `filter(Process.id == …)` puro e o `closed_at` logo abaixo é ESCRITA. Um
    # contrato do tenant A apontando para processo de B (o que o POST legado
    # permitia) fechava o caso de B — dado alheio alterado, não apenas lido.
    # Se a relação for inconsistente, o caso simplesmente não existe para quem
    # assina: 404, e o contrato não é assinado.
    concluido_em = None
    if contract.process_id:
        proc = exigir_do_tenant(
            db, Process, contract.process_id, contract.tenant_id, rotulo="Caso"
        )
        if proc and proc.closed_at is None:
            proc.closed_at = datetime.now(UTC)
            db.add(proc)
            concluido_em = proc.closed_at

    _audit_contract(db, contract, current_user.id, "contract_signed",
                    extra={"signed_at": dt.isoformat(), "has_signed_pdf": bool(contract.signed_pdf_storage_key)})
    db.commit()
    db.refresh(contract)
    logger.info("Contrato %s ASSINADO (signed_at=%s) por user=%s", contract_id, dt.date(), current_user.id)
    return {
        "message": "Contrato assinado — caso concluído." if not storage_warning else "Contrato assinado.",
        "warning": storage_warning,
        "concluido_em": concluido_em,
        "contract": _serialize(contract),
    }


@router.get("/{contract_id}/download-assinado")
def download_contrato_assinado(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """URL pré-assinada do PDF ASSINADO (quando houve upload na assinatura)."""
    contract = _get_contract_or_404(db, contract_id, current_user.tenant_id)
    if not contract.signed_pdf_storage_key:
        raise HTTPException(status_code=404, detail="Nenhum PDF assinado foi anexado a este contrato.")
    try:
        url = get_storage_service().generate_presigned_get_url(contract.signed_pdf_storage_key, expires_in=3600)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL: {exc}")
    return {"download_url": url, "expires_in": 3600}
