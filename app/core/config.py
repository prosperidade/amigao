import ssl
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator, Literal
from urllib.parse import urlencode, urlparse, urlsplit, urlunsplit

from pydantic import EmailStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "172.31.32.1"}

# redis-py espera os tokens 'none'/'optional'/'required' em ssl_cert_reqs.
# Uma env (Upstash em prod) com a constante Python 'CERT_REQUIRED' quebra a
# criação do cliente: "Invalid SSL Certificate Requirements Flag: CERT_REQUIRED".
# Mapeia qualquer forma comum para o token correto.
_SSL_CERT_REQS_TOKENS = {
    "none": "none", "cert_none": "none", "ssl.cert_none": "none",
    "optional": "optional", "cert_optional": "optional", "ssl.cert_optional": "optional",
    "required": "required", "cert_required": "required", "ssl.cert_required": "required",
}
_SSL_CERT_REQS_CONST = {
    "none": ssl.CERT_NONE,
    "optional": ssl.CERT_OPTIONAL,
    "required": ssl.CERT_REQUIRED,
}


def _redis_cert_reqs_token(raw: str | None) -> str:
    """Normaliza um valor de ssl_cert_reqs para 'none'/'optional'/'required'.
    Default 'required' (Upstash usa cert público válido → verificação segura)."""
    if not raw:
        return "required"
    return _SSL_CERT_REQS_TOKENS.get(raw.strip().lower(), "required")


def _normalize_redis_ssl_cert_reqs(url: str) -> str:
    """Reescreve o param ssl_cert_reqs do URL para o token aceito pelo redis-py.
    Não-SSL ou sem o param → retorna o URL intacto."""
    if "ssl_cert_reqs" not in url:
        return url
    parts = urlsplit(url)
    pairs = []
    changed = False
    for key, value in _parse_query_pairs(parts.query):
        if key == "ssl_cert_reqs":
            token = _redis_cert_reqs_token(value)
            if token != value:
                changed = True
            pairs.append((key, token))
        else:
            pairs.append((key, value))
    if not changed:
        return url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))


def _redis_ssl_cert_reqs_const(url: str) -> int:
    """Constante ssl.CERT_* para o ssl_cert_reqs do URL (default CERT_REQUIRED)."""
    raw = None
    for key, value in _parse_query_pairs(urlsplit(url).query):
        if key == "ssl_cert_reqs":
            raw = value
    return _SSL_CERT_REQS_CONST[_redis_cert_reqs_token(raw)]


def _parse_query_pairs(query: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for chunk in query.split("&"):
        if not chunk:
            continue
        key, sep, value = chunk.partition("=")
        pairs.append((key, value if sep else ""))
    return pairs


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
    PROJECT_NAME: str = "Regente Ambiental"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # DATABASE
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "amigao_db"
    POSTGRES_PORT: str = "5432"
    # Single-string override usado em deploy (Render + Supabase pooler 6543).
    # Tem precedência sobre POSTGRES_* quando setado.
    DATABASE_URL: str = ""

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # REDIS
    REDIS_URL: str = "redis://localhost:6379/0"
    REALTIME_EVENTS_CHANNEL: str = "amigao_events"

    # STORAGE (MinIO / Cloudflare R2)
    MINIO_SERVER: str = "localhost:9000"
    MINIO_PUBLIC_URL: str = ""
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    # Region do cliente S3. Cloudflare R2 EXIGE "auto" — com "us-east-1" o
    # scope da assinatura SigV4 (.../us-east-1/s3/aws4_request) não bate no GET
    # server-side (header-auth) e o R2 responde SignatureDoesNotMatch. O MinIO
    # ignora a region, então "auto" é seguro como default para os dois.
    S3_REGION: str = "auto"

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CRIPTO DE SEGREDOS (ADR-014 — Frente D)
    # Chave-mestra Fernet, OBRIGATÓRIA, separada do SECRET_KEY do JWT.
    # Gerar com `python tools/gen_encryption_key.py`. Sem fallback inseguro:
    # se não estiver setada, a app falha no startup (ver validate_security).
    CREDENTIAL_ENCRYPTION_KEY: str
    # Chave antiga durante rotação (MultiFernet). Opcional.
    CREDENTIAL_ENCRYPTION_KEY_OLD: str | None = None

    # EMAIL / SMTP (Mailtrap defaults for dev)
    SMTP_TLS: bool = True
    SMTP_PORT: int = 587
    SMTP_HOST: str = "sandbox.smtp.mailtrap.io"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: EmailStr = "noreply@regenteambiental.com.br"
    EMAILS_FROM_NAME: str = "Regente Ambiental"

    # RESEND (Sprint B1 — waitlist do Regente)
    # Coexiste com SMTP: SMTP segue cobrindo emails do portal interno;
    # Resend cobre exclusivamente o fluxo da waitlist (send + Audience).
    # Migração completa do EmailService para Resend fica para sprint dedicada.
    RESEND_API_KEY: str = ""
    RESEND_AUDIENCE_ID: str = ""
    RESEND_FROM_EMAIL: EmailStr = "contato@regenteambiental.com.br"
    RESEND_FROM_NAME: str = "Regente Ambiental"

    # ── PR 2.1 — Canal de mensagens (WhatsApp inbound/outbound) ──────────────
    # Integração de canal a CASO JÁ ABERTO (mensagens inbound NÃO criam caso).
    # Tudo DORMENTE por default (None): a feature só ativa quando as credenciais
    # forem preenchidas. Provider plugável — Evolution agora, Z-API em stub.
    WHATSAPP_PROVIDER: str = "evolution"
    EVOLUTION_API_URL: str | None = None
    EVOLUTION_API_KEY: str | None = None
    EVOLUTION_WEBHOOK_SECRET: str | None = None  # HMAC do webhook inbound
    # Z-API — placeholders (provider em STUB, não implementado nesta PR).
    ZAPI_API_URL: str | None = None
    ZAPI_API_KEY: str | None = None
    ZAPI_WEBHOOK_SECRET: str | None = None
    # E-mail inbound — NÃO implementado nesta PR (Resend Inbound não habilitado).
    # Placeholders documentados para quando o domínio/plano habilitar.
    EMAIL_INBOUND_PROVIDER: str | None = None  # "resend" quando habilitado
    RESEND_INBOUND_WEBHOOK_SECRET: str | None = None

    CLIENT_PORTAL_URL: str = "http://localhost:3000/dashboard"
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://172.31.32.1:3000"

    # IA / LLM (Wave 2 — Sprint 5)
    AI_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    # Sprint W (2026-05-14) — provedor de embeddings: "openai" | "gemini".
    # Vazio = auto-detecta (OpenAI se key, senão Gemini). Trocar exige
    # re-embedar TODOS os chunks (vetores entre provedores são incompatíveis).
    EMBEDDING_PROVIDER: str = ""
    AI_DEFAULT_MODEL: str = "gpt-4o-mini"
    AI_FALLBACK_MODEL: str = "gemini/gemini-2.5-flash"
    # White label (André 2026-05-28): provider chinês selecionável pelo consultor.
    # DeepSeek é o mais maduro para LiteLLM; trocar aqui se mudar.
    LLM_CHINESE_PROVIDER: str = "deepseek"
    AI_MAX_TOKENS: int = 2048
    AI_TEMPERATURE: float = 0.2
    AI_TIMEOUT_SECONDS: float = 30.0
    # Custo máximo por job (USD) — proteção contra prompt injection gigante
    AI_MAX_COST_PER_JOB_USD: float = 0.10
    # Sprint R — teto mensal padrão por tenant (USD). 0 = ilimitado.
    # Override por tenant em Tenant.ai_monthly_budget_usd.
    AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT: float = 0.0

    # Legislação — Gemini context loading (sem chunking)
    # Sprint 0 (2026-04-23): Gemini 2.0 Flash tem janela de 1M tokens.
    # Deixamos 900K como budget de contexto (10% de margem pra system prompt + memória).
    LEGISLATION_MAX_CONTEXT_TOKENS: int = 900_000
    # Sprint 0 — budget expandido quando o roteador escolhe Pro (janela 2M).
    # Usado só em consultas com corpus muito grande (coletâneas completas).
    LEGISLATION_MAX_CONTEXT_TOKENS_LONG: int = 1_900_000
    LEGISLATION_MAX_RESULTS: int = 20

    # Sprint V (2026-04-29) — top-k chunks RAG (knowledge_catalog) injetados no
    # prompt do agente legislação como "trechos hiper-relevantes". Complementa o
    # dump completo (que entra como contexto amplo). 8 = ~6k tokens extras, custo
    # marginal em Flash, ROI alto na precisão das citações.
    LEGISLATION_RAG_TOP_K: int = 8

    # Claude API (agente regulatório)
    CLAUDE_LEGAL_MODEL: str = "claude-sonnet-4-20250514"
    # Sprint W (2026-05-14): subido de 4096 para 8192. Gemini 2.5 Flash é
    # verboso e estava truncando o JSON antes do fechamento, quebrando o parser.
    CLAUDE_LEGAL_MAX_TOKENS: int = 8192
    CLAUDE_LEGAL_TEMPERATURE: float = 0.1

    # Gemini (context loading de legislação)
    # Default: Flash (1M tokens) — caso comum.
    # Sprint W (2026-05-14): migrado de gemini-2.0-flash (descontinuado para
    # contas com billing novo) para gemini-2.5-flash.
    GEMINI_LEGAL_MODEL: str = "gemini/gemini-2.5-flash"
    # Modelo para consultas com contexto >800K tokens (janela 2M).
    # Sprint W: migrado de gemini-1.5-pro para gemini-2.5-pro.
    GEMINI_LEGAL_LONG_MODEL: str = "gemini/gemini-2.5-pro"
    # Threshold de contexto acima do qual o roteador troca Flash → Pro.
    GEMINI_LEGAL_LONG_CONTEXT_THRESHOLD_CHARS: int = 3_200_000  # ~800K tokens

    # Modelo Gemini Vision do pipeline de OCR (app/services/ocr_pdf.py).
    # 2026-06-02: migrado de gemini-2.0-flash (descontinuado pelo Google — o
    # worker em prod quebrou com 404 "models/gemini-2.0-flash is no longer
    # available") para gemini-2.5-flash, alinhado ao GEMINI_LEGAL_MODEL.
    # Configurável por env para que o próximo deprecation seja só troca de
    # variável, sem mexer no código.
    GEMINI_OCR_MODEL: str = "gemini/gemini-2.5-flash"

    # Sprint O — Gemini como provider default do agente legislação (decisão da sócia 2026-04-21).
    # Claude continua como fallback quando Gemini não estiver configurado.
    LEGISLATION_USE_GEMINI_DEFAULT: bool = True

    # Sprint 0 — cost guard específico do agente legislação (docs grandes no Gemini).
    # Flash default: $0.30. Override pra Pro quando contexto >800K: $5.00.
    AI_MAX_COST_PER_JOB_USD_LEGISLACAO: float = 0.30
    AI_MAX_COST_PER_JOB_USD_LEGISLACAO_LONG: float = 5.00

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

    def _with_scheme(self, value: str) -> str:
        """Prefixa o scheme quando a env vem sem ele. Respeita MINIO_SECURE —
        em produção (R2) a env chega como `<acct>.r2.cloudflarestorage.com`
        (sem scheme) e PRECISA ir por https; forçar http aqui quebrava o GET."""
        if value.startswith(("http://", "https://")):
            return value
        scheme = "https" if self.MINIO_SECURE else "http"
        return f"{scheme}://{value}"

    @property
    def minio_internal_endpoint(self) -> str:
        return self._with_scheme(self.MINIO_SERVER)

    @property
    def minio_public_endpoint(self) -> str:
        public_url = self.MINIO_PUBLIC_URL.strip() or self.MINIO_SERVER
        return self._with_scheme(public_url)

    @property
    def redis_is_ssl(self) -> bool:
        return self.REDIS_URL.strip().lower().startswith("rediss://")

    @property
    def redis_url_safe(self) -> str:
        """REDIS_URL com o param `ssl_cert_reqs` normalizado para o token que o
        redis-py aceita (`none`/`optional`/`required`). Upstash usa `rediss://`;
        uma env com `?ssl_cert_reqs=CERT_REQUIRED` (nome da constante Python)
        quebra o redis-py: 'Invalid SSL Certificate Requirements Flag'. Normaliza
        defensivamente, independentemente de como a env foi escrita."""
        return _normalize_redis_ssl_cert_reqs(self.REDIS_URL)

    @property
    def celery_redis_use_ssl(self) -> dict | None:
        """Opções SSL para o broker/backend Celery quando o REDIS_URL é
        `rediss://`. Retorna None em `redis://` (setar `broker_use_ssl` num URL
        não-SSL faz o Celery abortar). Ver `app/core/celery_app.py`."""
        if not self.redis_is_ssl:
            return None
        return {"ssl_cert_reqs": _redis_ssl_cert_reqs_const(self.REDIS_URL)}

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

        # Cripto de segredos (ADR-014). Chave OBRIGATÓRIA e em formato Fernet
        # (urlsafe-base64 de 32 bytes → 44 chars). Sem fallback inseguro.
        from cryptography.fernet import Fernet  # local: evita custo no import de config

        encryption_key = self.CREDENTIAL_ENCRYPTION_KEY.strip()
        if not encryption_key:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY é obrigatória (ADR-014). "
                "Gere com `python tools/gen_encryption_key.py`."
            )
        try:
            Fernet(encryption_key.encode())
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY inválida — esperado uma chave Fernet "
                "(urlsafe-base64 de 44 chars). Gere com `python tools/gen_encryption_key.py`."
            ) from exc

        old_encryption_key = (self.CREDENTIAL_ENCRYPTION_KEY_OLD or "").strip()
        if old_encryption_key:
            try:
                Fernet(old_encryption_key.encode())
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "CREDENTIAL_ENCRYPTION_KEY_OLD inválida — esperado uma chave "
                    "Fernet (urlsafe-base64 de 44 chars)."
                ) from exc

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

        # Sprint B1 — Resend é obrigatório em produção para o fluxo de waitlist.
        # API key fica vazia em dev (skip silencioso no client); valida só em prod.
        if self.is_production and not self.RESEND_API_KEY.strip():
            raise ValueError(
                "RESEND_API_KEY deve estar configurado em produção (sprint B1 — waitlist)."
            )

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
