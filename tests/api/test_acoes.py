"""Testes da Ficha 07 — Ações (aba do caso + Quadro de Ações global).

Cobre: geração com fonte a partir do diagnóstico (idempotente), triagem do
consultor, edição de status no kanban, garantia "concluir ação NÃO altera o
passivo" (ADR-016), quadro global com caso de origem e tenant isolation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.regulatory import (
    RegulatoryDiagnosis,
    RegulatoryIssue,
    RegulatoryIssueSeverity,
    StatusAchado,
    StatusSaneamento,
)
from app.models.tenant import Tenant
from app.models.user import User


def _login(http: TestClient, email: str, password: str) -> dict[str, str]:
    response = http.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_internal_user(db_session, *, name: str = "Tenant Acao", email: str = "consultor@example.com"):
    tenant = Tenant(name=name)
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email,
        full_name="Consultor",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.flush()
    return tenant, user


def _seed_case(db_session, *, tenant: Tenant, title: str = "Processo Acao"):
    client = Client(
        tenant_id=tenant.id,
        full_name="Fazenda Boa Vista",
        client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(client)
    db_session.flush()
    prop = Property(
        tenant_id=tenant.id,
        client_id=client.id,
        name="Imóvel São Jorge",
        state="GO",
    )
    db_session.add(prop)
    db_session.flush()
    process = Process(
        tenant_id=tenant.id,
        client_id=client.id,
        property_id=prop.id,
        title=title,
        process_type="car",
        status=ProcessStatus.diagnostico,
        demand_type=DemandType.car,
    )
    db_session.add(process)
    db_session.flush()
    return client, prop, process


def _diagnosis_content() -> dict:
    """Diagnóstico com 2 riscos (proximo_passo + fonte) e 1 afirmação 'acao'."""
    return {
        "content": "Diagnóstico preliminar do imóvel.",
        "sources": [{"type": "document", "ref": "matricula-123"}],
        "riscos": [
            {
                "risco_identificado": "Área da matrícula diverge do CAR",
                "grau": "alto",
                "proximo_passo": "Solicitar retificação de área no CAR",
                "sources": [
                    {"tipo": "documento", "ref": "doc-1", "descricao": "Matrícula 123"}
                ],
            },
            {
                "risco_identificado": "Titularidade em espólio",
                "grau": "critico",
                "proximo_passo": "Providenciar inventário/partilha antes de protocolar",
                "sources": [{"tipo": "matriz", "descricao": "linha titularidade"}],
            },
        ],
        "afirmacoes": [
            {
                "texto": "Protocolar resposta à notificação do órgão",
                "categoria": "acao",
                "fontes": [{"tipo": "rat", "ref": "PROT-9", "descricao": "RAT protocolo 9"}],
            },
            {
                "texto": "Área declarada incompatível",
                "categoria": "passivo",
                "fontes": [{"tipo": "documento", "ref": "car-1"}],
            },
        ],
    }


def _seed_diagnosis(db_session, *, tenant: Tenant, process: Process, version: int = 1):
    diag = RegulatoryDiagnosis(
        tenant_id=tenant.id,
        process_id=process.id,
        content=_diagnosis_content(),
        version=version,
    )
    db_session.add(diag)
    db_session.flush()
    return diag


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_unauthorized_returns_401(client: TestClient):
    assert client.get("/api/v1/processes/1/acoes").status_code == 401
    assert client.get("/api/v1/acoes/kanban").status_code == 401


# ---------------------------------------------------------------------------
# Geração a partir do diagnóstico
# ---------------------------------------------------------------------------


def test_generate_creates_pending_acoes_with_fonte(client: TestClient, db_session):
    tenant, _ = _seed_internal_user(db_session)
    _, _, process = _seed_case(db_session, tenant=tenant)
    _seed_diagnosis(db_session, tenant=tenant, process=process)
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    r = client.post(f"/api/v1/processes/{process.id}/acoes/generate", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # 2 riscos com proximo_passo + 1 afirmação categoria=acao = 3 ações.
    assert body["created"] == 3
    assert body["skipped"] == 0
    assert body["diagnosis_version"] == 1
    for acao in body["acoes"]:
        assert acao["tipo_triagem"] == "pendente"
        assert acao["origem"] == "diagnostico"
        assert acao["status"] == "a_fazer"
        # Toda ação carrega fonte (#70) — nunca vazia.
        assert len(acao["origem_fontes"]) >= 1
        assert acao["vinculo_passivo"] is not None


def test_generate_is_idempotent(client: TestClient, db_session):
    tenant, _ = _seed_internal_user(db_session)
    _, _, process = _seed_case(db_session, tenant=tenant)
    _seed_diagnosis(db_session, tenant=tenant, process=process)
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    first = client.post(f"/api/v1/processes/{process.id}/acoes/generate", headers=headers).json()
    second = client.post(f"/api/v1/processes/{process.id}/acoes/generate", headers=headers).json()
    assert first["created"] == 3
    assert second["created"] == 0
    assert second["skipped"] == 3

    lst = client.get(f"/api/v1/processes/{process.id}/acoes", headers=headers).json()
    assert len(lst) == 3  # não duplicou


def test_generate_without_diagnosis_returns_zero(client: TestClient, db_session):
    tenant, _ = _seed_internal_user(db_session)
    _, _, process = _seed_case(db_session, tenant=tenant)
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    r = client.post(f"/api/v1/processes/{process.id}/acoes/generate", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"created": 0, "skipped": 0, "diagnosis_version": None, "acoes": []}


# ---------------------------------------------------------------------------
# Criação manual
# ---------------------------------------------------------------------------


def test_manual_create(client: TestClient, db_session):
    tenant, _ = _seed_internal_user(db_session)
    _, _, process = _seed_case(db_session, tenant=tenant)
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    r = client.post(
        f"/api/v1/processes/{process.id}/acoes",
        headers=headers,
        json={"titulo": "Ligar para o cartório", "prioridade": "alta"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["origem"] == "manual"
    assert body["tipo_triagem"] == "tarefa"
    assert body["prioridade"] == "alta"


# ---------------------------------------------------------------------------
# Triagem
# ---------------------------------------------------------------------------


def test_triagem_marks_escopo_and_dispensar(client: TestClient, db_session):
    tenant, _ = _seed_internal_user(db_session)
    _, _, process = _seed_case(db_session, tenant=tenant)
    _seed_diagnosis(db_session, tenant=tenant, process=process)
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    client.post(f"/api/v1/processes/{process.id}/acoes/generate", headers=headers)
    acoes = client.get(f"/api/v1/processes/{process.id}/acoes", headers=headers).json()
    a0, a1 = acoes[0]["id"], acoes[1]["id"]

    r = client.post(
        f"/api/v1/processes/{process.id}/acoes/{a0}/triagem",
        headers=headers, json={"decisao": "escopo"},
    )
    assert r.status_code == 200
    assert r.json()["tipo_triagem"] == "escopo"

    r = client.post(
        f"/api/v1/processes/{process.id}/acoes/{a1}/triagem",
        headers=headers, json={"decisao": "dispensar"},
    )
    assert r.json()["tipo_triagem"] == "dispensada"


# ---------------------------------------------------------------------------
# Edição de status + concluir NÃO altera o passivo
# ---------------------------------------------------------------------------


def test_update_status_sets_concluida_at(client: TestClient, db_session):
    tenant, _ = _seed_internal_user(db_session)
    _, _, process = _seed_case(db_session, tenant=tenant)
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    acao = client.post(
        f"/api/v1/processes/{process.id}/acoes",
        headers=headers, json={"titulo": "X"},
    ).json()

    r = client.patch(
        f"/api/v1/processes/{process.id}/acoes/{acao['id']}",
        headers=headers, json={"status": "concluida"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "concluida"
    assert r.json()["concluida_at"] is not None


def test_concluir_acao_nao_altera_passivo(client: TestClient, db_session):
    """Garantia central (ADR-016): concluir a ação não toca o RegulatoryIssue."""
    tenant, _ = _seed_internal_user(db_session)
    _, prop, process = _seed_case(db_session, tenant=tenant)
    issue = RegulatoryIssue(
        tenant_id=tenant.id,
        property_id=prop.id,
        codigo_alerta="AREA_MATRICULA_X_CAR",
        severity=RegulatoryIssueSeverity.alto,
        status_achado=StatusAchado.suspeita,
        status_saneamento=StatusSaneamento.pendente,
        detected_by="auditor",
    )
    db_session.add(issue)
    db_session.flush()
    issue_id = issue.id
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    acao = client.post(
        f"/api/v1/processes/{process.id}/acoes",
        headers=headers,
        json={
            "titulo": "Resolver área",
            "vinculo_passivo": {"tipo": "issue", "ref": str(issue_id), "descricao": "área"},
        },
    ).json()
    client.patch(
        f"/api/v1/processes/{process.id}/acoes/{acao['id']}",
        headers=headers, json={"status": "concluida"},
    )

    db_session.expire_all()
    fresh = db_session.get(RegulatoryIssue, issue_id)
    assert fresh.status_achado == StatusAchado.suspeita
    assert fresh.status_saneamento == StatusSaneamento.pendente
    assert fresh.resolved_at is None


# ---------------------------------------------------------------------------
# Quadro global
# ---------------------------------------------------------------------------


def test_kanban_groups_by_status_with_case_origin(client: TestClient, db_session):
    tenant, _ = _seed_internal_user(db_session)
    _, _, process = _seed_case(db_session, tenant=tenant, title="Caso São Jorge")
    db_session.commit()

    headers = _login(client, "consultor@example.com", "senha123")
    a = client.post(
        f"/api/v1/processes/{process.id}/acoes", headers=headers, json={"titulo": "A1"}
    ).json()
    # Move para em_andamento.
    client.patch(
        f"/api/v1/processes/{process.id}/acoes/{a['id']}",
        headers=headers, json={"status": "em_andamento"},
    )

    r = client.get("/api/v1/acoes/kanban", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    cols = {c["status"]: c for c in data["columns"]}
    assert [c["status"] for c in data["columns"]] == [
        "a_fazer", "em_andamento", "concluida", "bloqueada",
    ]
    assert cols["em_andamento"]["count"] == 1
    card = cols["em_andamento"]["cards"][0]
    assert card["process_title"] == "Caso São Jorge"
    assert card["client_name"] == "Fazenda Boa Vista"
    assert card["property_name"] == "Imóvel São Jorge"


def test_kanban_tenant_isolation(client: TestClient, db_session):
    tenant_a, _ = _seed_internal_user(db_session, name="A", email="a@example.com")
    _, _, proc_a = _seed_case(db_session, tenant=tenant_a)
    tenant_b, _ = _seed_internal_user(db_session, name="B", email="b@example.com")
    _, _, proc_b = _seed_case(db_session, tenant=tenant_b)
    db_session.commit()

    headers_a = _login(client, "a@example.com", "senha123")
    headers_b = _login(client, "b@example.com", "senha123")
    client.post(f"/api/v1/processes/{proc_a.id}/acoes", headers=headers_a, json={"titulo": "de A"})
    client.post(f"/api/v1/processes/{proc_b.id}/acoes", headers=headers_b, json={"titulo": "de B"})

    data_a = client.get("/api/v1/acoes/kanban", headers=headers_a).json()
    assert data_a["total"] == 1
    titulos_a = [c["titulo"] for col in data_a["columns"] for c in col["cards"]]
    assert titulos_a == ["de A"]

    # Tenant A não acessa ação/processo do tenant B.
    assert client.get(f"/api/v1/processes/{proc_b.id}/acoes", headers=headers_a).status_code == 404
