"""Sprint B1 — Tasks Celery do fluxo de waitlist.

Tasks deste módulo:
- ``sync_resend_audience(lead_id)`` — cria/atualiza contato no Resend Audience
- ``send_welcome_email(lead_id)`` — envia welcome email (D+0) via Resend

Drip (D+7, D+14, D+21) entra em PR 3 (beat-scan da tabela ``pre_cadastros_drip_log``).

Autoretry: ``autoretry_for=(ResendAPIError,)`` + ``retry_backoff=True``,
até 3 tentativas, com backoff exponencial capado em 10min.
"""

import logging
from typing import Any

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.pre_cadastro import PreCadastro
from app.services.resend_client import ResendAPIError, get_resend_client

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.sync_resend_audience",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    autoretry_for=(ResendAPIError,),
)
def sync_resend_audience(self, lead_id: int) -> None:
    """Cria ou atualiza o contato no Resend Audience configurado.

    Idempotente: o client tenta POST e cai para PATCH em 409/422.
    Atualiza ``PreCadastro.resend_contact_id`` quando o Audience devolve o id.
    """
    db = SessionLocal()
    try:
        lead = db.query(PreCadastro).filter(PreCadastro.id == lead_id).first()
        if lead is None:
            logger.warning("sync_resend_audience lead_not_found id=%s", lead_id)
            return
        if lead.deleted_at is not None:
            logger.info("sync_resend_audience skipped (soft_deleted) id=%s", lead_id)
            return

        client = get_resend_client()
        result = client.upsert_audience_contact(
            email=lead.email,
            first_name=lead.nome,
            data=_lead_to_resend_data(lead),
        )
        contact_id = result.get("id")
        if contact_id and lead.resend_contact_id != contact_id:
            lead.resend_contact_id = contact_id
            db.commit()
        logger.info(
            "sync_resend_audience ok id=%s contact_id=%s",
            lead_id, contact_id,
        )
    finally:
        db.close()


@celery_app.task(
    name="workers.send_welcome_email",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    autoretry_for=(ResendAPIError,),
)
def send_welcome_email(self, lead_id: int) -> None:
    """Envia welcome email (D+0).

    Template inline mínimo nesta sprint; será trocado pelo template Jinja
    em PR 3 quando a infra de templates estiver pronta.
    """
    db = SessionLocal()
    try:
        lead = db.query(PreCadastro).filter(PreCadastro.id == lead_id).first()
        if lead is None or lead.deleted_at is not None:
            return

        client = get_resend_client()
        html = _welcome_html_inline(lead.nome)
        text = (
            f"Olá {lead.nome},\n\n"
            "Você está na lista de espera do Regente. "
            "Em breve enviaremos atualizações sobre o lançamento do beta.\n\n"
            "— Equipe Regente"
        )
        client.send_email(
            to=lead.email,
            subject="Você está na lista do Regente",
            html=html,
            text=text,
            tags=[
                {"name": "stage", "value": "welcome"},
                {"name": "lead_id", "value": str(lead.id)},
            ],
        )
        logger.info("send_welcome_email ok id=%s", lead_id)
    finally:
        db.close()


def _lead_to_resend_data(lead: PreCadastro) -> dict[str, Any]:
    """Reflete o lead para custom data do Resend Audience.

    Única fonte de verdade — quando uma coluna nova for adicionada em
    ``pre_cadastros``, atualizar aqui também (Risco R10 do RELATORIO).
    """
    return {
        "perfil_profissional": lead.perfil_profissional or "",
        "estado": lead.estado or "",
        "tipo_licenciamento": lead.tipo_licenciamento or "",
        "volume_mensal": str(lead.volume_mensal or 0),
        "ferramenta_atual": lead.ferramenta_atual or "",
        "interesse_grupo": str(bool(lead.interesse_grupo)),
        "utm_source": lead.utm_source or "",
        "utm_campaign": lead.utm_campaign or "",
    }


def _welcome_html_inline(nome: str) -> str:
    """Welcome email mínimo. Template Jinja completo entra em PR 3."""
    return f"""<html><body style="font-family: Arial, sans-serif; color: #333; max-width: 640px; margin: auto; padding: 24px;">
  <h2 style="color: #1E7F55; margin-top: 0;">Você está na lista do Regente.</h2>
  <p>Olá <strong>{nome}</strong>,</p>
  <p>Confirmamos seu cadastro na lista de espera do <strong>Regente Ambiental</strong>.</p>
  <p>Em breve enviaremos atualizações sobre o lançamento do beta e as condições para consultores fundadores.</p>
  <p style="margin-top: 32px;">— Equipe Regente</p>
  <hr style="border: 0; border-top: 1px solid #eaeaea; margin: 24px 0;">
  <p style="font-size: 12px; color: #888;">Do caos ao compasso. · regenteambiental.com.br</p>
</body></html>"""
