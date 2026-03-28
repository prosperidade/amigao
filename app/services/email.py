import smtplib
from email.message import EmailMessage
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.sender_email = settings.EMAILS_FROM_EMAIL
        self.sender_name = settings.EMAILS_FROM_NAME
        self.use_tls = settings.SMTP_TLS

    def send_email(self, email_to: str, subject: str, html_content: str) -> bool:
        if not self.user or not self.password:
            logger.warning("SMTP Config invalida ou vazia. Simulando envio de E-mail (Console):")
            logger.warning(f"  Para: {email_to}")
            logger.warning(f"  Assunto: {subject}")
            logger.warning(f"  Mensagem (HTML): {html_content[:200]}...")
            return True

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = f"{self.sender_name} <{self.sender_email}>"
        msg['To'] = email_to
        msg.set_content(html_content, subtype='html')

        try:
            server = smtplib.SMTP(self.host, self.port)
            if self.use_tls:
                server.starttls()
            
            server.login(self.user, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email enviado com sucesso para {email_to}")
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar e-mail para {email_to}: {str(e)}")
            return False


def _base_template(title: str, intro: str, body_html: str, footer: str) -> str:
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; max-width: 640px; margin: auto; padding: 24px; border: 1px solid #eaeaea; border-radius: 12px; background-color: #ffffff;">
        <h2 style="color: #059669; margin-top: 0;">Amigão do Meio Ambiente</h2>
        <h3 style="color: #111827;">{title}</h3>
        <p>{intro}</p>
        <div style="background-color: #f9fafb; padding: 16px; border-radius: 10px; margin: 20px 0; border: 1px solid #e5e7eb;">
          {body_html}
        </div>
        <p>{footer}</p>
        <p style="margin-top: 24px;">
          <a href="{settings.CLIENT_PORTAL_URL}" style="display: inline-block; background-color: #059669; color: #ffffff; text-decoration: none; padding: 12px 18px; border-radius: 8px; font-weight: bold;">
            Abrir Portal do Cliente
          </a>
        </p>
        <hr style="border: 0; border-top: 1px solid #eaeaea; margin: 24px 0;">
        <p style="font-size: 12px; color: #888;">Este é um e-mail automático. Por favor, não responda.</p>
      </body>
    </html>
    """


def format_process_status_email(process_name: str, new_status: str) -> str:
    return _base_template(
        title="Atualização de status do processo",
        intro="O status do seu processo foi atualizado no sistema.",
        body_html=(
            f"<p style='margin: 0 0 8px 0;'><strong>Processo:</strong> {process_name}</p>"
            f"<p style='margin: 0;'><strong>Novo status:</strong> "
            f"<span style='background-color: #ecfdf5; color: #059669; padding: 4px 8px; border-radius: 6px; font-weight: bold;'>{new_status.upper()}</span></p>"
        ),
        footer="Você pode acompanhar os detalhes e os próximos passos diretamente pelo portal.",
    )


def format_internal_document_uploaded_email(
    process_name: str,
    client_name: str,
    filename: str,
) -> str:
    return _base_template(
        title="Novo documento enviado pelo portal",
        intro="Um novo arquivo foi anexado pelo cliente e já está disponível para conferência.",
        body_html=(
            f"<p style='margin: 0 0 8px 0;'><strong>Cliente:</strong> {client_name}</p>"
            f"<p style='margin: 0 0 8px 0;'><strong>Processo:</strong> {process_name}</p>"
            f"<p style='margin: 0;'><strong>Arquivo:</strong> {filename}</p>"
        ),
        footer="Revise o documento no painel interno e prossiga com o atendimento conforme o fluxo do processo.",
    )


def format_notification_template(process_name: str, new_status: str) -> str:
    """Compatibilidade com o helper antigo de atualização de status."""
    return format_process_status_email(process_name=process_name, new_status=new_status)
