import smtplib
from email.message import EmailMessage
import logging
from typing import Dict, Any

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

def format_notification_template(process_name: str, new_status: str) -> str:
    """Helper prático de Formatação HTML Base de Notificação"""
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 8px;">
        <h2 style="color: #059669;">Amigão do Meio Ambiente</h2>
        <p>Olá,</p>
        <p>Gostaríamos de informar que o status do seu processo foi atualizado.</p>
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 6px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Processo:</strong> {process_name}</p>
            <p style="margin: 5px 0 0 0;"><strong>Novo Status:</strong> <span style="background-color: #ecfdf5; color: #059669; padding: 3px 6px; border-radius: 4px; font-weight: bold;">{new_status.upper()}</span></p>
        </div>
        <p>Você pode acessar mais detalhes diretamente pelo seu Portal do Cliente.</p>
        <hr style="border: 0; border-top: 1px solid #eaeaea; margin: 20px 0;">
        <p style="font-size: 12px; color: #888;">Este é um e-mail automático. Por favor, não responda.</p>
      </body>
    </html>
    """
