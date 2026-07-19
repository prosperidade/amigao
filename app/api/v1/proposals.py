"""
Proposals API — Sprint 4

  GET    /proposals                         — lista por tenant
  POST   /proposals                         — criar proposta
  GET    /proposals/{id}                    — detalhe
  PATCH  /proposals/{id}                    — atualizar
  POST   /proposals/{id}/send               — marcar como enviada
  POST   /proposals/{id}/accept             — marcar como aceita
  POST   /proposals/{id}/reject             — marcar como recusada
  GET    /proposals/generate-draft          — gera rascunho automático
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.process import Process
from app.models.proposal import Proposal, ProposalStatus
from app.models.user import User
from app.services.audit_hash import stamp_audit_hash
from app.services.email import EmailService
from app.services.mirante_documents import (
    DocumentGenerationError,
    build_proposta,
    render_pdf,
    render_proposta_text,
)
from app.services.proposal_generator import (
    ProposalGenerationError,
    generate_proposal_from_rota,
)
from app.services.storage import get_storage_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Garante datetime tz-aware (Postgres devolve aware; SQLite/mocks, naive)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _effective_status(p: Proposal, now: Optional[datetime] = None) -> ProposalStatus:
    """Estado EFETIVO da proposta (S5-A) — 'expirada' é DERIVADO no read (sem cron):
    proposta enviada cuja validade venceu vale como expirada. Os demais estados
    são os persistidos."""
    now = now or datetime.now(UTC)
    exp = _aware(p.expires_at)
    if p.status == ProposalStatus.sent and exp is not None and exp < now:
        return ProposalStatus.expired
    return p.status


def _audit_proposal(db: Session, p: Proposal, user_id: Optional[int], action: str,
                    extra: Optional[dict] = None) -> None:
    """Transição auditada (quem/quando) com hash chain (Princípio 2)."""
    details = {"proposal_id": p.id, "status": p.status.value,
               "version_number": p.version_number}
    if extra:
        details.update(extra)
    log = AuditLog(
        tenant_id=p.tenant_id, user_id=user_id, entity_type="proposal",
        entity_id=p.id, action=action,
        details=json.dumps(details, ensure_ascii=False, default=str),
    )
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------

class ProposalCreate(BaseModel):
    client_id: int
    process_id: Optional[int] = None
    title: str
    scope_items: list[dict] = []
    total_value: Optional[float] = None
    validity_days: int = 30
    payment_terms: Optional[str] = None
    payment_installments: list[dict] = []   # S5-B — [{numero, vencimento, valor}]
    notes: Optional[str] = None
    complexity: Optional[str] = None
    rota_id: Optional[int] = None       # S5-A — Rota validada de origem


class ProposalUpdate(BaseModel):
    title: Optional[str] = None
    scope_items: Optional[list[dict]] = None
    total_value: Optional[float] = None
    validity_days: Optional[int] = None
    payment_terms: Optional[str] = None
    payment_installments: Optional[list[dict]] = None   # S5-B — parcelas estruturadas
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_proposal_or_404(db: Session, proposal_id: int, tenant_id: int) -> Proposal:
    p = db.query(Proposal).filter(
        Proposal.id == proposal_id,
        Proposal.tenant_id == tenant_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")
    return p


def _serialize(p: Proposal) -> dict:
    return {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "process_id": p.process_id,
        "client_id": p.client_id,
        "status": p.status.value,
        # S5-A: 'expirada' é derivada no read (validade vencida numa enviada).
        "effective_status": _effective_status(p).value,
        "version_number": p.version_number,
        "rota_id": p.rota_id,
        "previous_version_id": p.previous_version_id,
        "title": p.title,
        "scope_items": p.scope_items,
        "total_value": p.total_value,
        "validity_days": p.validity_days,
        "payment_terms": p.payment_terms,
        "payment_installments": p.payment_installments or [],
        "notes": p.notes,
        "complexity": p.complexity,
        "sent_at": p.sent_at,
        "accepted_at": p.accepted_at,
        "rejected_at": p.rejected_at,
        "expires_at": p.expires_at,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


# ---------------------------------------------------------------------------
# GET /proposals/generate-draft  (antes do {id} para não colidir)
# ---------------------------------------------------------------------------

@router.get("/generate-draft")
def generate_draft(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Gera rascunho de proposta A PARTIR da Rota validada (S5-A).

    Sem Rota validada (ou sem passo faturável) → 422 com mensagem honesta,
    coerente com o gate E5→E6. O escopo nasce dos passos ``item_proposta`` da
    Rota (rastreável); a PRICE_TABLE só precifica."""
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == current_user.tenant_id,
    ).first()
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    try:
        draft = generate_proposal_from_rota(db, process_id, current_user.tenant_id)
    except ProposalGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "title": draft.title,
        "demand_type": draft.demand_type,
        "complexity": draft.complexity,
        "scope_items": draft.scope_items,
        "suggested_value_min": draft.suggested_value_min,
        "suggested_value_max": draft.suggested_value_max,
        "suggested_value": draft.suggested_value,
        "estimated_days": draft.estimated_days,
        "payment_terms": draft.payment_terms,
        "notes": draft.notes,
        "rota_id": draft.rota_id,
    }


# ---------------------------------------------------------------------------
# GET /proposals
# ---------------------------------------------------------------------------

@router.get("/")
def list_proposals(
    process_id: Optional[int] = None,
    client_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    q = db.query(Proposal).filter(Proposal.tenant_id == current_user.tenant_id)
    if process_id:
        q = q.filter(Proposal.process_id == process_id)
    if client_id:
        q = q.filter(Proposal.client_id == client_id)
    proposals = q.order_by(Proposal.created_at.desc()).offset(skip).limit(limit).all()
    return [_serialize(p) for p in proposals]


# ---------------------------------------------------------------------------
# POST /proposals
# ---------------------------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_proposal(
    body: ProposalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    expires = datetime.now(UTC) + timedelta(days=body.validity_days)
    proposal = Proposal(
        tenant_id=current_user.tenant_id,
        client_id=body.client_id,
        process_id=body.process_id,
        title=body.title,
        scope_items=body.scope_items,
        total_value=body.total_value,
        validity_days=body.validity_days,
        payment_terms=body.payment_terms,
        payment_installments=body.payment_installments,
        notes=body.notes,
        complexity=body.complexity,
        rota_id=body.rota_id,
        created_by_user_id=current_user.id,
        expires_at=expires,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    logger.info("Proposta criada: id=%s client=%s", proposal.id, body.client_id)
    return _serialize(proposal)


# ---------------------------------------------------------------------------
# GET /proposals/{id}
# ---------------------------------------------------------------------------

@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    return _serialize(_get_proposal_or_404(db, proposal_id, current_user.tenant_id))


# ---------------------------------------------------------------------------
# POST /proposals/{id}/documento — gera a peça (PDF + Saída) nos moldes Mirante
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/documento")
def gerar_documento_proposta(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Gera a PROPOSTA formal (6 seções Mirante) a partir do escopo da Rota +
    precificação (S5-B). Determinístico. RASCUNHO — o consultor revisa/edita e
    assina (IA propõe, humano decide).

    Bloqueia (422) com mensagem honesta se: perfil do tenant incompleto,
    inconsistência de valores, ou placeholder não resolvido. Registra a peça em
    Saídas (StageOutput, output_type='proposta') e devolve URL de download."""
    from app.models.stage_output import StageOutput  # noqa: PLC0415

    proposal = _get_proposal_or_404(db, proposal_id, current_user.tenant_id)
    try:
        doc = build_proposta(db, proposal)
        corpo = render_proposta_text(doc)
    except DocumentGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    pdf_key: Optional[str] = None
    storage_warning: Optional[str] = None
    try:
        pdf_bytes = render_pdf(f"Proposta {doc.numero}", corpo)
        filename = f"proposta_{proposal_id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
        storage = get_storage_service()
        result = storage.upload_bytes(
            content=pdf_bytes, filename=filename, content_type="application/pdf",
            tenant_id=current_user.tenant_id, process_id=proposal.process_id or 0,
        )
        pdf_key = result["storage_key"]
    except Exception as exc:  # storage/PDF não-fatal: a Saída textual é registrada
        logger.warning("PDF da proposta %s não armazenado: %s", proposal_id, exc)
        storage_warning = f"Peça gerada; PDF não armazenado ({exc})."

    content_data = doc.to_content_data()
    content_data["pdf_storage_key"] = pdf_key
    artifact = None
    if proposal.process_id:
        artifact = StageOutput(
            tenant_id=current_user.tenant_id,
            process_id=proposal.process_id,
            macroetapa="orcamento_negociacao",
            output_type="proposta",
            title=f"Proposta {doc.numero}",
            content=corpo,
            content_data=content_data,
            produced_by_user_id=current_user.id,
            needs_human_validation=True,  # RASCUNHO — humano decide
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)

    download_url = None
    if pdf_key:
        try:
            download_url = get_storage_service().generate_presigned_get_url(pdf_key, expires_in=3600)
        except Exception as exc:  # noqa: BLE001
            logger.warning("URL de download da proposta %s indisponível: %s", proposal_id, exc)

    return {
        "message": "Proposta gerada como rascunho." if not storage_warning else "Proposta gerada.",
        "warning": storage_warning,
        "artifact_id": artifact.id if artifact else None,
        "numero": doc.numero,
        "content": corpo,
        "content_data": content_data,
        "download_url": download_url,
    }


# ---------------------------------------------------------------------------
# PATCH /proposals/{id}
# ---------------------------------------------------------------------------

@router.patch("/{proposal_id}")
def update_proposal(
    proposal_id: int,
    body: ProposalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    proposal = _get_proposal_or_404(db, proposal_id, current_user.tenant_id)
    if proposal.status not in (ProposalStatus.draft,):
        raise HTTPException(status_code=422, detail="Apenas propostas em rascunho podem ser editadas.")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(proposal, field, value)

    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return _serialize(proposal)


# ---------------------------------------------------------------------------
# POST /proposals/{id}/send
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/send")
def send_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Marca proposta como enviada e dispara e-mail ao cliente."""
    proposal = _get_proposal_or_404(db, proposal_id, current_user.tenant_id)
    if proposal.status != ProposalStatus.draft:
        raise HTTPException(status_code=422, detail="Proposta já foi enviada ou finalizada.")

    proposal.status = ProposalStatus.sent
    proposal.sent_at = datetime.now(UTC)
    # Validade conta a partir do ENVIO (renova o relógio da expiração derivada).
    proposal.expires_at = datetime.now(UTC) + timedelta(days=proposal.validity_days or 30)
    db.add(proposal)
    _audit_proposal(db, proposal, current_user.id, "proposal_enviada")
    db.commit()
    db.refresh(proposal)

    # Notificação por e-mail (best-effort)
    if proposal.client and proposal.client.email:
        try:
            svc = EmailService()
            svc.send_email(
                email_to=proposal.client.email,
                subject=f"Proposta Comercial — {proposal.title}",
                html_content=_proposal_email_html(proposal),
            )
        except Exception as exc:
            logger.warning("Falha ao enviar e-mail da proposta %s: %s", proposal_id, exc)

    logger.info("Proposta enviada: id=%s", proposal_id)
    return _serialize(proposal)


# ---------------------------------------------------------------------------
# POST /proposals/{id}/accept
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/accept")
def accept_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    proposal = _get_proposal_or_404(db, proposal_id, current_user.tenant_id)
    eff = _effective_status(proposal)
    # S5-A — máquina estrita: só aceita uma proposta ENVIADA e não expirada.
    if eff == ProposalStatus.expired:
        raise HTTPException(
            status_code=422,
            detail="Proposta expirada — gere uma nova versão para renegociar.",
        )
    if eff != ProposalStatus.sent:
        raise HTTPException(
            status_code=422,
            detail="Só é possível aceitar uma proposta enviada (estado atual: "
            f"{eff.value}).",
        )
    proposal.status = ProposalStatus.accepted
    proposal.accepted_at = datetime.now(UTC)
    db.add(proposal)
    _audit_proposal(db, proposal, current_user.id, "proposal_aceita")
    db.commit()
    db.refresh(proposal)
    return _serialize(proposal)


# ---------------------------------------------------------------------------
# POST /proposals/{id}/reject
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/reject")
def reject_proposal(
    proposal_id: int,
    reason: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    proposal = _get_proposal_or_404(db, proposal_id, current_user.tenant_id)
    eff = _effective_status(proposal)
    # Recusa vale para enviada OU expirada (o cliente pode recusar após vencer).
    if eff not in (ProposalStatus.sent, ProposalStatus.expired):
        raise HTTPException(
            status_code=422,
            detail=f"Só é possível recusar uma proposta enviada (estado atual: {eff.value}).",
        )
    proposal.status = ProposalStatus.rejected
    proposal.rejected_at = datetime.now(UTC)
    if reason:
        proposal.notes = f"{proposal.notes or ''}\n\nMotivo da recusa: {reason}".strip()
    db.add(proposal)
    _audit_proposal(db, proposal, current_user.id, "proposal_recusada",
                    {"reason": reason} if reason else None)
    db.commit()
    db.refresh(proposal)
    return _serialize(proposal)


# ---------------------------------------------------------------------------
# POST /proposals/{id}/nova-versao  — renegociação (S5-A)
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/nova-versao", status_code=status.HTTP_201_CREATED)
def new_version(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Any:
    """Renegociação (S5-A): gera a versão N+1 a partir de uma proposta recusada
    ou expirada. A anterior é PRESERVADA (histórico); a nova nasce em rascunho,
    linkada à anterior (``previous_version_id``), com a validade renovada."""
    prev = _get_proposal_or_404(db, proposal_id, current_user.tenant_id)
    eff = _effective_status(prev)
    if eff not in (ProposalStatus.rejected, ProposalStatus.expired):
        raise HTTPException(
            status_code=422,
            detail="Nova versão só a partir de proposta recusada ou expirada "
            f"(estado atual: {eff.value}).",
        )
    nova = Proposal(
        tenant_id=prev.tenant_id,
        client_id=prev.client_id,
        process_id=prev.process_id,
        rota_id=prev.rota_id,
        previous_version_id=prev.id,
        version_number=(prev.version_number or 1) + 1,
        status=ProposalStatus.draft,
        title=prev.title,
        scope_items=prev.scope_items,
        total_value=prev.total_value,
        validity_days=prev.validity_days,
        payment_terms=prev.payment_terms,
        notes=prev.notes,
        complexity=prev.complexity,
        created_by_user_id=current_user.id,
        expires_at=datetime.now(UTC) + timedelta(days=prev.validity_days or 30),
    )
    db.add(nova)
    db.flush()
    _audit_proposal(db, nova, current_user.id, "proposal_nova_versao",
                    {"previous_version_id": prev.id, "version_number": nova.version_number})
    db.commit()
    db.refresh(nova)
    logger.info("Nova versão de proposta: %s → %s (v%s)", prev.id, nova.id, nova.version_number)
    return _serialize(nova)


# ---------------------------------------------------------------------------
# Helper e-mail
# ---------------------------------------------------------------------------

def _proposal_email_html(proposal: Proposal) -> str:
    client_name = proposal.client.full_name if proposal.client else "Cliente"
    value_str = f"R$ {proposal.total_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if proposal.total_value else "A combinar"
    return f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto;">
  <div style="background:#1a7a3c;padding:20px;border-radius:8px 8px 0 0;">
    <h2 style="color:white;margin:0">Regente Ambiental</h2>
    <p style="color:#a7f3d0;margin:4px 0 0">Consultoria e Regularização Ambiental</p>
  </div>
  <div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;">
    <p>Olá, <strong>{client_name}</strong>!</p>
    <p>Segue nossa proposta comercial para os serviços solicitados.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr><td style="padding:8px;background:#f9fafb;font-weight:bold">Título</td>
          <td style="padding:8px">{proposal.title}</td></tr>
      <tr><td style="padding:8px;background:#f9fafb;font-weight:bold">Valor Total</td>
          <td style="padding:8px;color:#1a7a3c;font-size:18px"><strong>{value_str}</strong></td></tr>
      <tr><td style="padding:8px;background:#f9fafb;font-weight:bold">Condições</td>
          <td style="padding:8px">{proposal.payment_terms or 'A combinar'}</td></tr>
      <tr><td style="padding:8px;background:#f9fafb;font-weight:bold">Validade</td>
          <td style="padding:8px">{proposal.validity_days} dias</td></tr>
    </table>
    <p>Entre em contato conosco para esclarecer dúvidas ou aprovar a proposta.</p>
    <p style="color:#6b7280;font-size:12px;margin-top:24px">
      Esta proposta é válida por {proposal.validity_days} dias a partir do envio.
    </p>
  </div>
</body></html>
"""
