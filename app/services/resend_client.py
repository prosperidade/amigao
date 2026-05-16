"""Cliente HTTP para a API do Resend (send-only).

Sprint B1 — waitlist do Regente Ambiental. Coexistência com o EmailService
SMTP existente em ``app/services/email.py``: este cliente cobre apenas
emails da waitlist; transacional do portal interno continua via SMTP.

Cobertura:
- ``send_email`` — envio transacional
- ``upsert_audience_contact`` — cria/atualiza contato no Audience configurado

Convenções alinhadas com EmailService SMTP:
- Erros HTTP do Resend → ``ResendAPIError`` (autoretry em Celery)
- Logs estruturados via logger do módulo
- Métricas ``record_email_delivery("success"|"failed"|"skipped")``
- Alertas via ``emit_operational_alert`` em falhas críticas

Fora de escopo desta sprint:
- Inbound webhooks (bounce/open/click)
- Suppression list management
- Render de templates (templates Jinja vivem em ``app/templates/emails/`` — PR 3)
"""

import logging
from typing import Any, Optional

import httpx

from app.core.alerts import emit_operational_alert
from app.core.config import settings
from app.core.metrics import record_email_delivery

logger = logging.getLogger(__name__)

_RESEND_BASE_URL = "https://api.resend.com"
_DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class ResendAPIError(Exception):
    """Falha na comunicação com a API do Resend (capturável pelo autoretry)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        body: Optional[dict] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


class ResendClient:
    """Wrapper síncrono em torno do endpoint REST do Resend.

    Síncrono porque é chamado de tasks Celery (que rodam em thread). Para
    chamada inline em request FastAPI, prefira enfileirar a chamada como
    task ao invés de bloquear o handler.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        audience_id: Optional[str] = None,
        timeout: httpx.Timeout = _DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.RESEND_API_KEY).strip()
        self.audience_id = (
            audience_id if audience_id is not None else settings.RESEND_AUDIENCE_ID
        ).strip()
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict] = None,
    ) -> dict[str, Any]:
        url = f"{_RESEND_BASE_URL}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, headers=self._headers(), json=payload)
        except httpx.RequestError as exc:
            raise ResendAPIError(f"Resend network error em {method} {path}: {exc}") from exc

        if response.status_code >= 400:
            body = _safe_json(response)
            raise ResendAPIError(
                f"Resend API {response.status_code} em {method} {path}",
                status_code=response.status_code,
                body=body,
            )
        return _safe_json(response)

    def send_email(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
        from_: Optional[str] = None,
        reply_to: Optional[str] = None,
        tags: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """Envia um email transacional.

        Retorna ``{"id": "<message_id>"}`` em sucesso.
        Em failure: levanta ``ResendAPIError``; já registra métrica e alerta.
        """
        if not self.is_configured:
            msg = "Resend não configurado. E-mail não será enviado."
            if settings.is_production:
                logger.error("%s to=%s subject=%s", msg, to, subject)
                record_email_delivery("failed")
                emit_operational_alert(
                    category="email_delivery",
                    severity="error",
                    message="Resend não configurado em produção",
                    metadata={"to": to, "subject": subject},
                )
            else:
                logger.warning("%s to=%s subject=%s", msg, to, subject)
                record_email_delivery("skipped")
            return {}

        payload: dict[str, Any] = {
            "from": from_ or _default_from(),
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text is not None:
            payload["text"] = text
        if reply_to is not None:
            payload["reply_to"] = reply_to
        if tags is not None:
            payload["tags"] = tags

        try:
            result = self._request("POST", "/emails", payload)
            logger.info("resend_email_sent to=%s id=%s", to, result.get("id"))
            record_email_delivery("success")
            return result
        except ResendAPIError as exc:
            logger.error(
                "resend_email_failed to=%s status=%s body=%s",
                to, exc.status_code, exc.body,
            )
            record_email_delivery("failed")
            emit_operational_alert(
                category="email_delivery",
                severity="error",
                message="Falha ao enviar e-mail via Resend",
                metadata={
                    "to": to,
                    "subject": subject,
                    "status": exc.status_code,
                    "error": str(exc),
                },
            )
            raise

    def upsert_audience_contact(
        self,
        *,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        unsubscribed: bool = False,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Cria ou atualiza contato no Audience configurado.

        Tenta POST primeiro; em 409/422 (já existe) faz fallback pra PATCH
        identificado pelo email. Idempotente — rerun seguro.

        Retorna ``{"id": "<contact_id>"}`` em sucesso ou ``{}`` se Resend
        Audience não está configurado (skip silencioso).
        """
        if not self.is_configured or not self.audience_id:
            logger.warning(
                "resend_audience_skip api_key_set=%s audience_id_set=%s email=%s",
                bool(self.api_key), bool(self.audience_id), email,
            )
            return {}

        payload: dict[str, Any] = {"email": email, "unsubscribed": unsubscribed}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if data:
            payload["data"] = data

        path = f"/audiences/{self.audience_id}/contacts"
        try:
            result = self._request("POST", path, payload)
            logger.info("resend_audience_upsert_created email=%s id=%s", email, result.get("id"))
            return result
        except ResendAPIError as exc:
            if exc.status_code in (409, 422):
                logger.info("resend_audience_upsert_patching email=%s (existed)", email)
                return self._request("PATCH", f"{path}/{email}", payload)
            raise


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except Exception:  # noqa: BLE001 — qualquer falha de parse vira opaque body
        return {"_raw": response.text}


def _default_from() -> str:
    name = (settings.RESEND_FROM_NAME or settings.EMAILS_FROM_NAME).strip()
    email = (settings.RESEND_FROM_EMAIL or settings.EMAILS_FROM_EMAIL).strip()
    return f"{name} <{email}>"


_default_client: Optional[ResendClient] = None


def get_resend_client() -> ResendClient:
    """Singleton lazy do cliente. Reaproveita conexão e config entre tasks."""
    global _default_client
    if _default_client is None:
        _default_client = ResendClient()
    return _default_client
