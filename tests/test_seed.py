import seed


def test_seed_password_uses_explicit_env(monkeypatch) -> None:
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "Seed@2026")

    password, explicit = seed._seed_password("SEED_ADMIN_PASSWORD", "admin123")

    assert password == "Seed@2026"
    assert explicit is True


def test_seed_password_derives_from_secret_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr(seed.settings, "SECRET_KEY", "amigao-local-dev-secret-key-2026-32chars")

    password, explicit = seed._seed_password("SEED_ADMIN_PASSWORD", "admin123")

    assert password == "admi!adce9967b3"
    assert explicit is False
