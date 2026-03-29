import pytest

from app.core.config import Settings


def build_settings(**overrides) -> Settings:
    values = {
        "SECRET_KEY": "amigao-production-like-secret-key-1234",
        "CLIENT_PORTAL_URL": "https://portal.amigao.com/dashboard",
        "BACKEND_CORS_ORIGINS": "https://portal.amigao.com,https://app.amigao.com",
        "MINIO_PUBLIC_URL": "https://storage.amigao.com",
        "MINIO_ACCESS_KEY": "tenant-storage-access-key",
        "MINIO_SECRET_KEY": "tenant-storage-secret-key",
        "SMTP_HOST": "smtp.amigao.com",
        "SMTP_USER": "mailer",
        "SMTP_PASSWORD": "mailer-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_rejects_short_secret_key() -> None:
    with pytest.raises(ValueError, match="pelo menos 32 caracteres"):
        build_settings(SECRET_KEY="curta")


def test_rejects_local_urls_in_production() -> None:
    with pytest.raises(ValueError, match="CLIENT_PORTAL_URL"):
        build_settings(ENVIRONMENT="production", CLIENT_PORTAL_URL="http://localhost:3000/dashboard")


def test_rejects_local_cors_in_production() -> None:
    with pytest.raises(ValueError, match="BACKEND_CORS_ORIGINS"):
        build_settings(
            ENVIRONMENT="production",
            BACKEND_CORS_ORIGINS="https://portal.amigao.com,http://127.0.0.1:3000",
        )


def test_requires_smtp_in_production() -> None:
    with pytest.raises(ValueError, match="SMTP"):
        build_settings(
            ENVIRONMENT="production",
            SMTP_USER="",
            SMTP_PASSWORD="",
        )


def test_requires_non_default_minio_credentials_in_production() -> None:
    with pytest.raises(ValueError, match="MinIO"):
        build_settings(
            ENVIRONMENT="production",
            MINIO_ACCESS_KEY="minioadmin",
            MINIO_SECRET_KEY="minioadmin",
        )


def test_rejects_local_minio_public_url_in_production() -> None:
    with pytest.raises(ValueError, match="MINIO_PUBLIC_URL"):
        build_settings(
            ENVIRONMENT="production",
            MINIO_PUBLIC_URL="http://localhost:9000",
        )


def test_accepts_hardened_production_settings() -> None:
    settings = build_settings(ENVIRONMENT="production")

    assert settings.is_production is True
    assert settings.smtp_configured is True


def test_requires_sender_name_in_production() -> None:
    with pytest.raises(ValueError, match="EMAILS_FROM_NAME"):
        build_settings(
            ENVIRONMENT="production",
            EMAILS_FROM_NAME="   ",
        )


def test_applies_slow_request_threshold_overrides() -> None:
    settings = build_settings(
        SLOW_REQUEST_THRESHOLD_MS=500,
        SLOW_REQUEST_THRESHOLD_OVERRIDES="/api/v1/auth/login=1500,/api/v1/documents/upload-url=800",
    )

    assert settings.slow_request_threshold_for("/api/v1/auth/login") == 1500
    assert settings.slow_request_threshold_for("/api/v1/auth/login/") == 1500
    assert settings.slow_request_threshold_for("/api/v1/processes/") == 500
