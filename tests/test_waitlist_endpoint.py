"""Sprint B1 — Tests do endpoint público POST /api/v1/waitlist.

Cobertura:
- happy path (signup novo retorna 200)
- idempotência (mesmo email retorna 200 sem distinguir signup novo de existente)
- bloqueio do soft-deleted (mesmo email após opt-out NÃO reativa)
- validações: consentimento obrigatório, UF, Van Westendorp, telefone, email lowercase
- payload completo com todos os campos opcionais

Tasks Celery (sync_resend_audience, send_welcome_email) são stubadas via fixture
``_stub_celery_enqueue`` — testes de tasks vivem em PR 3.

Rate limit é resetado entre testes via ``_reset_rate_limit`` (autouse).
"""

import pytest

from app.models.pre_cadastro import PreCadastro


WAITLIST_URL = "/api/v1/waitlist"


def _valid_payload(**overrides):
    payload = {
        "email": "lead@example.com",
        "nome": "Fulano Teste",
        "consentimento": True,
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def _stub_celery_enqueue(monkeypatch):
    """Stub do enqueue Celery — tasks reais são testadas em PR 3."""
    import app.api.v1.waitlist as waitlist_mod
    monkeypatch.setattr(
        waitlist_mod,
        "_enqueue_post_signup_tasks",
        lambda lead_id: None,
    )


# Rate-limit reset agora vive em conftest.py:_reset_slowapi_limiter (autouse global).


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_signup_happy_path(client, db_session):
    response = client.post(WAITLIST_URL, json=_valid_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "Regente" in body["mensagem"]

    # Verifica persistência
    lead = db_session.query(PreCadastro).filter(PreCadastro.email == "lead@example.com").one()
    assert lead.nome == "Fulano Teste"
    assert lead.consentimento_dado_em is not None
    assert lead.deleted_at is None


def test_signup_with_full_payload(client, db_session):
    payload = _valid_payload(
        telefone="(11) 98765-4321",
        perfil_profissional="Consultor ambiental",
        estado="sp",
        tipo_licenciamento="LO + LP",
        volume_mensal=10,
        ferramenta_atual="Trello",
        preco_aceito={
            "barato_demais": 49,
            "barato": 99,
            "caro": 299,
            "caro_demais": 499,
        },
        expectativa="Economizar tempo no diagnóstico",
        deal_breaker="Preço acima de R$500",
        interesse_grupo=True,
        source="landing_v1",
        utm_source="instagram",
        utm_campaign="lancamento_beta",
        utm_medium="organic",
    )
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 200

    lead = db_session.query(PreCadastro).filter(PreCadastro.email == "lead@example.com").one()
    assert lead.telefone == "11987654321"  # normalizado para apenas dígitos
    assert lead.estado == "SP"  # uppercase normalizado
    assert lead.preco_aceito == {
        "barato_demais": 49,
        "barato": 99,
        "caro": 299,
        "caro_demais": 499,
    }
    assert lead.interesse_grupo is True
    assert lead.utm_campaign == "lancamento_beta"


# ---------------------------------------------------------------------------
# Idempotência (mesma resposta para signup novo e existente)
# ---------------------------------------------------------------------------

def test_signup_idempotent_same_email(client, db_session):
    first = client.post(WAITLIST_URL, json=_valid_payload())
    assert first.status_code == 200

    second = client.post(WAITLIST_URL, json=_valid_payload(nome="Outro Nome"))
    assert second.status_code == 200
    assert second.json() == first.json()

    # Garante que só foi criada uma linha
    count = db_session.query(PreCadastro).filter(PreCadastro.email == "lead@example.com").count()
    assert count == 1


def test_signup_idempotent_email_case_insensitive(client, db_session):
    first = client.post(WAITLIST_URL, json=_valid_payload(email="Lead@Example.com"))
    assert first.status_code == 200

    second = client.post(WAITLIST_URL, json=_valid_payload(email="LEAD@example.com"))
    assert second.status_code == 200

    count = db_session.query(PreCadastro).filter(PreCadastro.email == "lead@example.com").count()
    assert count == 1


def test_signup_blocked_when_soft_deleted(client, db_session):
    """Lead que exerceu opt-out (deleted_at != NULL) não reativa com novo signup."""
    from datetime import datetime, timezone

    deleted_lead = PreCadastro(
        email="optedout@example.com",
        nome="Saiu da lista",
        consentimento_dado_em=datetime.now(timezone.utc),
        deleted_at=datetime.now(timezone.utc),
    )
    db_session.add(deleted_lead)
    db_session.flush()

    response = client.post(WAITLIST_URL, json=_valid_payload(email="optedout@example.com"))
    assert response.status_code == 200  # resposta uniforme — não vaza que está bloqueado

    # Confirma que não criou nova linha nem ressuscitou
    leads = db_session.query(PreCadastro).filter(PreCadastro.email == "optedout@example.com").all()
    assert len(leads) == 1
    assert leads[0].deleted_at is not None


# ---------------------------------------------------------------------------
# Validações
# ---------------------------------------------------------------------------

def test_signup_rejects_missing_consentimento(client):
    payload = _valid_payload(consentimento=False)
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 422


def test_signup_rejects_invalid_email(client):
    payload = _valid_payload(email="nao-eh-email")
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 422


def test_signup_rejects_invalid_uf(client):
    payload = _valid_payload(estado="XX")
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 422


def test_signup_rejects_invalid_van_westendorp(client):
    """barato_demais > barato deveria falhar (ordem incoerente)."""
    payload = _valid_payload(
        preco_aceito={
            "barato_demais": 200,
            "barato": 100,
            "caro": 300,
            "caro_demais": 400,
        },
    )
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 422


def test_signup_rejects_telefone_too_short(client):
    payload = _valid_payload(telefone="123")
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 422


def test_signup_rejects_nome_too_short(client):
    payload = _valid_payload(nome="A")
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 422


def test_signup_rejects_extra_fields(client):
    """``extra="forbid"`` no PreCadastroIn rejeita campos desconhecidos."""
    payload = _valid_payload(campo_inexistente="hack")
    response = client.post(WAITLIST_URL, json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------

def test_signup_rate_limit_blocks_after_10(client):
    """slowapi @limiter.limit("10/minute") deve responder 429 no 11º request."""
    # Envia 10 requests válidos (cada um com email distinto pra todos serem signup novo)
    for i in range(10):
        payload = _valid_payload(email=f"user{i}@example.com")
        response = client.post(WAITLIST_URL, json=payload)
        assert response.status_code == 200, f"Request {i} falhou inesperadamente"

    # 11º deve ser bloqueado
    response = client.post(WAITLIST_URL, json=_valid_payload(email="user11@example.com"))
    assert response.status_code == 429
