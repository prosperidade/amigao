"""
Contracts API — Sprint 4

  GET  /contracts                            — lista por tenant
  POST /contracts                            — criar contrato (a partir de proposta ou avulso)
  GET  /contracts/{id}                       — detalhe
  POST /contracts/{id}/generate-pdf          — gera/regenera PDF
  GET  /contracts/{id}/download              — URL de download do PDF
"""

from datetime import datetime, timezone
from typing import Any, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.models.proposal import Proposal
from app.models.process import Process
from app.services.contract_generator import (
    fill_contract_template,
    render_pdf,
    find_template_for_demand,
)
from app.services.storage import get_storage_service

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
        "sent_at": c.sent_at,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _resolve_demand_type(db: Session, contract: Contract) -> Optional[str]:
    if contract.process_id:
        proc = db.query(Process).filter(Process.id == contract.process_id).first()
        if proc and proc.demand_type:
            return proc.demand_type.value
    if contract.proposal_id:
        prop = db.query(Proposal).filter(Proposal.id == contract.proposal_id).first()
        if prop and prop.process_id:
            proc = db.query(Process).filter(Process.id == prop.process_id).first()
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
    # Resolver template se não informado
    template_id = body.template_id
    if not template_id:
        demand_type: Optional[str] = None
        if body.process_id:
            proc = db.query(Process).filter(Process.id == body.process_id).first()
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
        filename = f"contrato_{contract_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
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
