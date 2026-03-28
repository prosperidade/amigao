import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    
@celery_app.task(name="workers.send_email_notification", bind=True)
def send_email_notification(self, email_to: str, subject: str, html_content: str):
    """Envia um email assincronamente pelo serviço SMTP."""
    from app.services.email import EmailService
    logger.info(f"✉️ Iniciando disparo de email para {email_to}")
    
    service = EmailService()
    success = service.send_email(email_to=email_to, subject=subject, html_content=html_content)
    
    if not success:
        # Tentar novamente caso falhe usando self.retry configurado por Celery
        logger.warning(f"⚠️ Email para {email_to} falhou e será reenviado futuramente.")
    return {"status": "success" if success else "failed", "to": email_to}
