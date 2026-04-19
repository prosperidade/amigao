from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator, Literal
from urllib.parse import urlparse

from pydantic import EmailStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "172.31.32.1"}


def _extract_hostname(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""

    parsed = urlparse(candidate if "://" in candidate else f"http://{candidate}")
    return (parsed.hostname or candidate).strip("[]").lower()


def _is_local_address(value: str) -> bool:
    hostname = _extract_hostname(value)
    if not hostname:
        return False
    return hostname in _LOCAL_HOSTS or hostname.endswith(".local")


def _normalize_path(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    normalized = candidate.rstrip("/")
    return normalized or "/"

class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    SERVICE_NAME: str = "api"
    LOG_LEVEL: str = "INFO"
    SLOW_REQUEST_THRESHOLD_MS: int = 500
    SLOW_REQUEST_THRESHOLD_OVERRIDES: str = (
        "/api/v1/auth/login=2000,"
        "/api/v1/documents/upload-url=800,"
        "/api/v1/documents/confirm-upload=900"
    )
    ALERT_WEBHOOK_URL: str = ""
    ALERT_WEBHOOK_TIMEOUT_SECONDS: float = 2.0
    ALERT_WEBHOOK_AUTH_HEADER: str = "Authorization"
    ALERT_WEBHOOK_AUTH_TOKEN: str = ""
    ALERT_WEBHOOK_SIGNING_SECRET: str = ""
    ALERT_WEBHOOK_MIN_SEVERITY: Literal["info", "warning", "error", "critical"] = "error"
    PROMETHEUS_QUEUE_NAMES: str = "celery"
    PROJECT_NAME: str = "Amigão do Meio Ambiente"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # DATABASE
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "amigao_db"
    POSTGRES_PORT: str = "5432"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # REDIS
    REDIS_URL: str = "redis://localhost:6379/0"
    REALTIME_EVENTS_CHANNEL: str = "amigao_events"

    # STORAGE (MinIO)
    MINIO_SERVER: str = "localhost:9000"
    MINIO_PUBLIC_URL: str = ""
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # EMAIL / SMTP (Mailtrap defaults for dev)
    SMTP_TLS: bool = True
    SMTP_PORT: int = 587
    SMTP_HOST: str = "sandbox.smtp.mailtrap.io"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: EmailStr = "noreply@amigao.com"
    EMAILS_FROM_NAME: str = "Amigão do Meio Ambiente"
    CLIENT_PORTAL_URL: str = "http://localhost:3000/dashboard"
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://172.31.32.1:3000"

    # IA / LLM (Wave 2 — Sprint 5)
    AI_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    AI_DEFAULT_MODEL: str = "gpt-4o-mini"
    AI_FALLBACK_MODEL: str = "gemini/gemini-1.5-flash"
    AI_MAX_TOKENS: int = 2048
    AI_TEMPERATURE: float = 0.2
    AI_TIMEOUT_SECONDS: float = 30.0
    # Custo máximo por job (USD) — proteção contra prompt injection gigante
    AI_MAX_COST_PER_JOB_USD: float = 0.10

    # Legislação — Gemini context loading (sem chunking)
    LEGISLATION_MAX_CONTEXT_TOKENS: int = 500_000
    LEGISLATION_MAX_RESULTS: int = 20

    # Claude API (agente regulatório)
    CLAUDE_LEGAL_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_LEGAL_MAX_TOKENS: int = 4096
    CLAUDE_LEGAL_TEMPERATURE: float = 0.1

    # Gemini (context loading de legislação)
    GEMINI_LEGAL_MODEL: str = "gemini/gemini-2.0-flash"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def slow_request_threshold_overrides(self) -> dict[str, int]:
        overrides: dict[str, int] = {}
        for raw_item in self.SLOW_REQUEST_THRESHOLD_OVERRIDES.split(","):
            item = raw_item.strip()
            if not item or "=" not in item:
                continue
            path, threshold = item.split("=", 1)
            normalized_path = _normalize_path(path)
            if not normalized_path:
                continue
            try:
                overrides[normalized_path] = int(threshold.strip())
            except ValueError:
                continue
        return overrides

    def slow_request_threshold_for(self, path: str) -> int:
        return self.slow_request_threshold_overrides.get(
            _normalize_path(path),
            self.SLOW_REQUEST_THRESHOLD_MS,
        )

    @property
    def minio_internal_endpoint(self) -> str:
        return self.MINIO_SERVER if self.MINIO_SERVER.startswith(("http://", "https://")) else f"http://{self.MINIO_SERVER}"

    @property
    def minio_public_endpoint(self) -> str:
        public_url = self.MINIO_PUBLIC_URL.strip() or self.MINIO_SERVER
        return public_url if public_url.startswith(("http://", "https://")) else f"http://{public_url}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def ai_configured(self) -> bool:
        placeholders = {"", "changeme", "sk-...", "your-key-here", "test", "none"}

        def _is_real_key(key: str | None) -> bool:
            return bool(key and key.strip().lower() not in placeholders and len(key) > 10)

        return self.AI_ENABLED and (
            _is_real_key(self.OPENAI_API_KEY)
            or _is_real_key(self.GEMINI_API_KEY)
            or _is_real_key(self.ANTHROPIC_API_KEY)
        )

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)

    @property
    def alert_webhook_auth_header(self) -> str:
        return self.ALERT_WEBHOOK_AUTH_HEADER.strip()

    @property
    def alert_webhook_auth_token(self) -> str:
        return self.ALERT_WEBHOOK_AUTH_TOKEN.strip()

    @property
    def alert_webhook_signing_secret(self) -> str:
        return self.ALERT_WEBHOOK_SIGNING_SECRET.strip()

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        secret_key = self.SECRET_KEY.strip()
        if not secret_key:
            raise ValueError("SECRET_KEY não pode ser vazia.")
        if len(secret_key) < 32:
            raise ValueError("SECRET_KEY deve ter pelo menos 32 caracteres.")

        insecure_production_keys = {
            "change-this-in-production",
            "mude-esta-chave-em-producao-use-openssl-rand-hex-32",
        }
        if self.is_production and secret_key in insecure_production_keys:
            raise ValueError("SECRET_KEY insegura para produção.")

        if self.is_production and (
            self.MINIO_ACCESS_KEY == "minioadmin" or self.MINIO_SECRET_KEY == "minioadmin"
        ):
            raise ValueError("Credenciais MinIO inseguras para produção.")

        if self.is_production and _is_local_address(self.minio_public_endpoint):
            raise ValueError("MINIO_PUBLIC_URL não pode apontar para endereço local em produção.")

        if self.is_production and _is_local_address(self.CLIENT_PORTAL_URL):
            raise ValueError("CLIENT_PORTAL_URL não pode apontar para localhost em produção.")

        local_origins = [origin for origin in self.cors_origins_list if _is_local_address(origin)]
        if self.is_production and local_origins:
            raise ValueError("BACKEND_CORS_ORIGINS não pode conter endereços locais em produção.")

        if self.is_production and self.ALERT_WEBHOOK_URL and _is_local_address(self.ALERT_WEBHOOK_URL):
            raise ValueError("ALERT_WEBHOOK_URL não pode apontar para endereço local em produção.")

        if self.is_production and not self.smtp_configured:
            raise ValueError("SMTP deve estar configurado em produção.")

        if self.is_production and not self.EMAILS_FROM_NAME.strip():
            raise ValueError("EMAILS_FROM_NAME não pode ser vazio em produção.")

        if self.alert_webhook_auth_token and not self.alert_webhook_auth_header:
            raise ValueError(
                "ALERT_WEBHOOK_AUTH_HEADER deve ser informado quando ALERT_WEBHOOK_AUTH_TOKEN estiver configurado."
            )

        return self

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cached settings factory.  Call ``get_settings.cache_clear()`` to reload."""
    return Settings()


@contextmanager
def override_settings(**kwargs: object) -> Iterator[Settings]:
    """Temporarily replace settings with overridden values.

    Usage::

        with override_settings(ENVIRONMENT="test", AI_ENABLED=True) as s:
            assert s.ENVIRONMENT == "test"
    """
    get_settings.cache_clear()
    try:
        overridden = Settings(**kwargs)  # type: ignore[arg-type]
        get_settings.cache_clear()
        # Patch the cache so get_settings() returns the overridden instance
        get_settings()  # prime the cache with default first
        get_settings.cache_clear()

        # Temporarily replace the cached value
        _original = get_settings
        @lru_cache
        def _patched() -> Settings:
            return overridden

        import app.core.config as _self
        _self.get_settings = _patched  # type: ignore[assignment]
        _self.settings = overridden
        yield overridden
    finally:
        import app.core.config as _self
        _self.get_settings = _original
        _self.get_settings.cache_clear()
        _self.settings = _self.get_settings()


# Backward-compatible module-level singleton.
# Code that does ``from app.core.config import settings`` keeps working.
# For testability, prefer ``get_settings()`` in new code.
settings = get_settings()
