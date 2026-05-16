"""Sprint B1 — Endpoint público da waitlist do Regente Ambiental.

Captura leads do form em ``/lista-de-espera.html`` (regenteambiental.com.br).

Características:
- **Público** (sem auth, sem ``X-Auth-Profile``, sem tenant_id)
- **Rate limit**: 10 req/min por IP (slowapi)
- **Idempotente por e-mail**: sempre 200, sem distinguir signup novo de existente
  (anti-enumeração). E-mails soft-deletados não reativam — silenciosamente
  recebem a mesma resposta.
- **Async pós-signup**: ``sync_resend_audience`` e ``send_welcome_email``
  enfileirados como tasks Celery; falhas não bloqueiam a resposta.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.rate_limit import limiter
from app.models.pre_cadastro import PreCadastro
from app.schemas.pre_cadastro import PreCadastroIn, PreCadastroOut

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=PreCadastroOut,
    status_code=status.HTTP_200_OK,
    summary="Captura lead da waitlist do Regente",
    description=(
        "Endpoint público para captura de leads via "
        "/lista-de-espera.html.\n\n"
        "**Idempotente**: o mesmo e-mail enviado múltiplas vezes retorna a "
        "mesma resposta (200), sem revelar se o lead já existia "
        "(anti-enumeração).\n\n"
        "**Rate limit**: 10 requests por minuto por IP.\n\n"
        "**LGPD**: requer ``consentimento: true`` no payload."
    ),
)
@limiter.limit("10/minute")
def create_waitlist_lead(
    request: Request,  # required by slowapi  # noqa: ARG001
    payload: PreCadastroIn,
    db: Session = Depends(get_db),
) -> PreCadastroOut:
    existing = (
        db.query(PreCadastro)
        .filter(PreCadastro.email == payload.email)
        .first()
    )
    if existing is not None:
        if existing.deleted_at is not None:
            # Lead exerceu opt-out anteriormente. Não reativa silenciosamente.
            logger.info(
                "waitlist_signup_blocked_soft_deleted email=%s id=%s",
                payload.email, existing.id,
            )
        else:
            logger.info(
                "waitlist_signup_duplicate email=%s id=%s",
                payload.email, existing.id,
            )
        return PreCadastroOut()

    lead = PreCadastro(
        email=payload.email,
        nome=payload.nome,
        telefone=payload.telefone,
        perfil_profissional=payload.perfil_profissional,
        estado=payload.estado,
        tipo_licenciamento=payload.tipo_licenciamento,
        volume_mensal=payload.volume_mensal,
        ferramenta_atual=payload.ferramenta_atual,
        preco_aceito=(
            payload.preco_aceito.model_dump() if payload.preco_aceito else None
        ),
        expectativa=payload.expectativa,
        deal_breaker=payload.deal_breaker,
        interesse_grupo=payload.interesse_grupo,
        source=payload.source,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_term=payload.utm_term,
        utm_content=payload.utm_content,
        consentimento_dado_em=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    logger.info(
        "waitlist_signup_created id=%s email=%s utm_source=%s utm_campaign=%s",
        lead.id, lead.email, lead.utm_source, lead.utm_campaign,
    )

    _enqueue_post_signup_tasks(lead.id)
    return PreCadastroOut()


def _enqueue_post_signup_tasks(lead_id: int) -> None:
    """Fire-and-forget: enfileira sync de contato e welcome email.

    Falha não bloqueia a resposta — lead já está persistido. Em incidente
    operacional (Redis down), os erros aparecem no logger e no Prometheus.
    """
    try:
        from app.workers.waitlist_tasks import (  # noqa: PLC0415 — lazy pra evitar ciclo
            send_welcome_email,
            sync_resend_audience,
        )
        sync_resend_audience.delay(lead_id)
        send_welcome_email.delay(lead_id)
    except Exception as exc:  # noqa: BLE001 — operacional, não funcional
        logger.error("waitlist_enqueue_failed lead_id=%s error=%s", lead_id, exc)
