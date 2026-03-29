from app.services import email


def test_check_connection_requires_configured_smtp(monkeypatch) -> None:
    monkeypatch.setattr(email.settings, "SMTP_HOST", "sandbox.smtp.mailtrap.io")
    monkeypatch.setattr(email.settings, "SMTP_USER", "")
    monkeypatch.setattr(email.settings, "SMTP_PASSWORD", "")

    ok, message = email.EmailService().check_connection()

    assert ok is False
    assert "não configurado" in message.lower()


def test_check_connection_validates_smtp_login(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(f"init:{host}:{port}:{timeout}")

        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")
            return False

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self):
            calls.append("starttls")

        def login(self, user, password):
            calls.append(f"login:{user}:{password}")

    monkeypatch.setattr(email.settings, "SMTP_HOST", "smtp.amigao.com")
    monkeypatch.setattr(email.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email.settings, "SMTP_USER", "mailer")
    monkeypatch.setattr(email.settings, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(email.settings, "SMTP_TLS", True)
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)

    ok, message = email.EmailService().check_connection()

    assert ok is True
    assert "sucesso" in message.lower()
    assert "starttls" in calls
    assert "login:mailer:secret" in calls
