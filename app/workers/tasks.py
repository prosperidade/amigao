import logging

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.process import Process
from app.models.user import User
from app.services.email import (
    EmailService,
    format_internal_document_uploaded_email,
    format_process_status_email,
)
from app.services.notifications import publish_realtime_event, register_notification_audit

logger = logging.getLogger(__name__)


def _list_internal_recipients(
    *,
    tenant_id: int,
    actor_user_id: int | None = None,
    excluded_email: str | None = None,
) -> list[str]:
    db = SessionLocal()
    try:
        query = db.query(User).filter(User.tenant_id == tenant_id, User.is_active.is_(True))
        if actor_user_id is not None:
            query = query.filter(User.id != actor_user_id)

        recipients: list[str] = []
        excluded_normalized = excluded_email.strip().lower() if excluded_email else None
        for user in query.all():
            normalized = user.email.strip().lower()
            if excluded_normalized and normalized == excluded_normalized:
                continue
            if normalized not in recipients:
                recipients.append(normalized)
        return recipients
    finally:
        db.close()


@celery_app.task(name="workers.test_job", bind=True)
def test_job(self):
    """Tarefa base de validação do worker - Sprint 1."""
    logger.info("✅ worker funcionando")
    return {"status": "ok", "message": "worker funcionando"}


@celery_app.task(name="workers.log_document_uploaded", bind=True)
def log_document_uploaded(self, document_id: int, tenant_id: int, filename: str):
    """Loga assincronamente o upload de documentos para auditoria."""
    logger.info(
        f"📄 Documento #{document_id} enviado | tenant={tenant_id} | arquivo='{filename}'"
    )
    return {"document_id": document_id, "status": "logged"}


@celery_app.task(name="workers.generate_pdf_report", bind=True)
def generate_pdf_report(self, tenant_id: int, process_id: int):
    """Gera um relatório de visita em PDF para o processo."""
    from app.workers.pdf_generator import generate_process_visit_report
    logger.info(f"⚙️ Iniciando geração de PDF de visita para Processo #{process_id} (Tenant {tenant_id})")

    result = generate_process_visit_report(tenant_id=tenant_id, process_id=process_id)
    return result


@celery_app.task(name="workers.generate_ai_weekly_summary", bind=True)
def generate_ai_weekly_summary(self, tenant_id: int, process_id: int):
    """Gera um resumo semanal executivo utilizando IA (LiteLLM/OpenAI)."""
    from app.workers.ai_summarizer import generate_weekly_summary
    logger.info(f"🤖 Iniciando geração de Resumo IA para Processo #{process_id} (Tenant {tenant_id})")
    result = generate_weekly_summary(tenant_id=tenant_id, process_id=process_id)
    return result


@celery_app.task(name="workers.notify_process_status_changed", bind=True, max_retries=3, default_retry_delay=30)
def notify_process_status_changed(
    self,
    tenant_id: int,
    process_id: int,
    old_status: str,
    new_status: str,
    actor_user_id: int | None = None,
):
    """Envia notificações assíncronas quando o processo muda de status."""
    db = SessionLocal()
    try:
        process = (
            db.query(Process)
            .filter(Process.id == process_id, Process.tenant_id == tenant_id)
            .first()
        )
        if not process:
            logger.warning("Processo %s não encontrado para notificação de status", process_id)
            return {"status": "not_found", "process_id": process_id}

        channels: list[str] = []
        email_sent = False
        if process.client and process.client.email:
            email_html = format_process_status_email(
                process_name=process.title,
                new_status=new_status,
            )
            email_sent = EmailService().send_email(
                email_to=process.client.email,
                subject=f"Atualização do Processo: {process.title}",
                html_content=email_html,
            )
            if email_sent:
                channels.append("email")
            elif settings.is_production or settings.smtp_configured:
                raise RuntimeError(f"Falha ao enviar notificação de status para {process.client.email}")
            else:
                logger.warning(
                    "Notificação por e-mail ignorada para %s em ambiente %s por SMTP não configurado",
                    process.client.email,
                    settings.ENVIRONMENT,
                )

        tenant_payload = {
            "process_id": process.id,
            "client_id": process.client_id,
            "title": process.title,
            "old_status": old_status,
            "new_status": new_status,
        }
        if publish_realtime_event(
            tenant_id=tenant_id,
            event_type="process.status.changed",
            payload=tenant_payload,
        ):
            channels.append("realtime_tenant")

        if publish_realtime_event(
            tenant_id=tenant_id,
            client_id=process.client_id,
            event_type="process.status.changed",
            payload=tenant_payload,
        ):
            channels.append("realtime_client")

        register_notification_audit(
            db=db,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            entity_type="process",
            entity_id=process.id,
            action="notification_process_status_changed",
            details={
                "old_status": old_status,
                "new_status": new_status,
                "channels": channels,
                "email_sent": email_sent,
            },
        )
        db.commit()
        return {"status": "success", "process_id": process.id, "channels": channels}
    except Exception as exc:
        db.rollback()
        retries = getattr(self.request, "retries", 0)
        if retries < 3:
            raise self.retry(exc=exc)
        logger.error("Falha definitiva ao notificar mudança de status do processo %s: %s", process_id, exc)
        return {"status": "failed", "process_id": process_id, "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="workers.notify_document_uploaded", bind=True, max_retries=3, default_retry_delay=30)
def notify_document_uploaded(
    self,
    tenant_id: int,
    process_id: int,
    document_id: int,
    actor_user_id: int | None = None,
    source: str = "internal",
):
    """Publica evento de documento enviado e alerta o time interno quando o upload vem do portal."""
    db = SessionLocal()
    try:
        document = (
            db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        process = (
            db.query(Process)
            .filter(Process.id == process_id, Process.tenant_id == tenant_id)
            .first()
        )
        if not document or not process:
            logger.warning(
                "Documento %s ou processo %s não encontrado para notificação de upload",
                document_id,
                process_id,
            )
            return {"status": "not_found", "document_id": document_id}

        channels: list[str] = []
        payload = {
            "document_id": document.id,
            "process_id": process.id,
            "client_id": process.client_id,
            "filename": document.filename,
            "source": source,
        }
        if publish_realtime_event(
            tenant_id=tenant_id,
            event_type="document.uploaded",
            payload=payload,
        ):
            channels.append("realtime_tenant")

        recipients: list[str] = []
        if source == "client_portal":
            client_email = process.client.email if process.client and process.client.email else None
            recipients = _list_internal_recipients(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                excluded_email=client_email,
            )
            if recipients:
                html = format_internal_document_uploaded_email(
                    process_name=process.title,
                    client_name=process.client.full_name if process.client else "Cliente",
                    filename=document.filename,
                )
                delivered = EmailService().send_email(
                    email_to=", ".join(recipients),
                    subject=f"Novo documento no processo {process.title}",
                    html_content=html,
                )
                if delivered:
                    channels.append("email_internal")
                elif settings.is_production or settings.smtp_configured:
                    raise RuntimeError("Falha ao enviar alerta interno de documento enviado")
                else:
                    logger.warning(
                        "Alerta interno de documento ignorado em ambiente %s por SMTP não configurado",
                        settings.ENVIRONMENT,
                    )

        register_notification_audit(
            db=db,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            entity_type="document",
            entity_id=document.id,
            action="notification_document_uploaded",
            details={
                "process_id": process.id,
                "source": source,
                "channels": channels,
                "recipients": recipients,
            },
        )
        db.commit()
        return {"status": "success", "document_id": document.id, "channels": channels}
    except Exception as exc:
        db.rollback()
        retries = getattr(self.request, "retries", 0)
        if retries < 3:
            raise self.retry(exc=exc)
        logger.error("Falha definitiva ao notificar upload do documento %s: %s", document_id, exc)
        return {"status": "failed", "document_id": document_id, "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="workers.send_email_notification", bind=True)
def send_email_notification(self, email_to: str, subject: str, html_content: str):
    """Envia um email assincronamente pelo serviço SMTP."""
    logger.info(f"✉️ Iniciando disparo de email para {email_to}")

    service = EmailService()
    try:
        success = service.send_email(email_to=email_to, subject=subject, html_content=html_content)
        if not success:
            if not settings.is_production and not settings.smtp_configured:
                logger.warning(
                    "Envio de e-mail ignorado para %s em ambiente %s por SMTP não configurado",
                    email_to,
                    settings.ENVIRONMENT,
                )
                return {"status": "skipped", "to": email_to, "reason": "smtp_not_configured"}
            raise RuntimeError(f"Falha ao enviar e-mail para {email_to}")
        return {"status": "success", "to": email_to}
    except Exception as exc:
        retries = getattr(self.request, "retries", 0)
        if retries < 3:
            raise self.retry(exc=exc, countdown=30)
        logger.error("Falha definitiva no envio de e-mail para %s: %s", email_to, exc)
        return {"status": "failed", "to": email_to, "error": str(exc)}
