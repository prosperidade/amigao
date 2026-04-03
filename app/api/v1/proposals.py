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

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.process import Process
from app.models.proposal import Proposal, ProposalStatus
from app.models.user import User
from app.services.email import EmailService
from app.services.proposal_generator import generate_proposal_draft

router = APIRouter()
logger = logging.getLogger(__name__)


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
    notes: Optional[str] = None
    complexity: Optional[str] = None


class ProposalUpdate(BaseModel):
    title: Optional[str] = None
    scope_items: Optional[list[dict]] = None
    total_value: Optional[float] = None
    validity_days: Optional[int] = None
    payment_terms: Optional[str] = None
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
        "version_number": p.version_number,
        "title": p.title,
        "scope_items": p.scope_items,
        "total_value": p.total_value,
        "validity_days": p.validity_days,
        "payment_terms": p.payment_terms,
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
    """Gera rascunho automático de proposta baseado no processo."""
    process = db.query(Process).filter(
        Process.id == process_id,
        Process.tenant_id == current_user.tenant_id,
    ).first()
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    draft = generate_proposal_draft(db, process_id, current_user.tenant_id)
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
        notes=body.notes,
        complexity=body.complexity,
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
    db.add(proposal)
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
    if proposal.status not in (ProposalStatus.sent, ProposalStatus.draft):
        raise HTTPException(status_code=422, detail="Proposta não pode ser aceita neste estado.")
    proposal.status = ProposalStatus.accepted
    proposal.accepted_at = datetime.now(UTC)
    db.add(proposal)
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
    if proposal.status not in (ProposalStatus.sent, ProposalStatus.draft):
        raise HTTPException(status_code=422, detail="Proposta não pode ser recusada neste estado.")
    proposal.status = ProposalStatus.rejected
    proposal.rejected_at = datetime.now(UTC)
    if reason:
        proposal.notes = f"{proposal.notes or ''}\n\nMotivo da recusa: {reason}".strip()
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return _serialize(proposal)


# ---------------------------------------------------------------------------
# Helper e-mail
# ---------------------------------------------------------------------------

def _proposal_email_html(proposal: Proposal) -> str:
    client_name = proposal.client.full_name if proposal.client else "Cliente"
    value_str = f"R$ {proposal.total_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if proposal.total_value else "A combinar"
    return f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto;">
  <div style="background:#1a7a3c;padding:20px;border-radius:8px 8px 0 0;">
    <h2 style="color:white;margin:0">Amigão do Meio Ambiente</h2>
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
