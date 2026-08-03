"""Testes de API da Rota Regulatória (E5, Sprint 2).

Cobre o fluxo do consultor: materializar (IA propõe) → reordenar/editar/adicionar
manual → classificar+validar passo a passo → fechar (assinar). E as travas:
- validar exige classificação (Ficha §8.1);
- fechar exige TODOS os passos validados;
- rota 'desatualizada' trava o fechamento (409) até aceitar o diff (Ficha §9);
- tenant isolation.

A ``LegislacaoAgent`` é substituída por um fake (não hitamos LLM em teste).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.agents.base import AgentResult
from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.regulatory import RegulatoryDiagnosis
from app.models.tenant import Tenant
from app.models.user import User
from app.services import rota_materializer as mat

# ---------------------------------------------------------------------------
# Helpers de seed / auth / fake agent
# ---------------------------------------------------------------------------


def _login(http: TestClient, email: str, password: str) -> dict[str, str]:
    r = http.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_user(db_session, *, name="Rota API", email="consultor@example.com"):
    tenant = Tenant(name=name)
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=email, full_name="Consultor",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id, is_active=True, is_superuser=True,
    )
    db_session.add(user)
    db_session.flush()
    return tenant, user


def _seed_case(db_session, *, tenant: Tenant):
    client = Client(
        tenant_id=tenant.id, full_name="Faz", client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(client)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=client.id, name="Imóvel", state="GO")
    db_session.add(prop)
    db_session.flush()
    process = Process(
        tenant_id=tenant.id, client_id=client.id, property_id=prop.id,
        title="P", process_type="car", status=ProcessStatus.diagnostico,
        demand_type=DemandType.car,
    )
    db_session.add(process)
    db_session.flush()
    # ADR-038: sem diagnóstico ASSINADO a rota não é traçada (409). Estes testes
    # exercitam o ciclo de vida da rota — gerar, reordenar, validar, fechar —,
    # não o guard, que tem cobertura própria em tests/services/test_rota_contexto.py.
    db_session.add(RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=process.id, version=1,
        validated_at=datetime.now(UTC), content={},
    ))
    db_session.flush()
    return process


_ETAPAS = [
    {"ordem": 1, "titulo": "Protocolar CAR", "prazo_estimado_dias": 30,
     "orgao": "SEMAD", "fonte_trecho": "Lei 12.651/2012"},
    {"ordem": 2, "titulo": "Retificar área", "prazo_estimado_dias": 60,
     "orgao": "Cartório", "fonte_trecho": "sem fonte"},
]


def _patch_agent(monkeypatch, etapas: list[dict]) -> None:
    data = {"caminho_regulatorio": "Caminho", "orgao_competente": "SEMAD", "etapas": etapas}

    class _Fake:
        def run(self) -> AgentResult:
            return AgentResult(
                success=True, data=data, confidence="high", ai_job_id=None,
                suggestions=[], requires_review=True, agent_name="legislacao", duration_ms=1,
            )

    monkeypatch.setattr(mat.AgentRegistry, "create", lambda name, ctx: _Fake())


def _classify_and_validate_all(client: TestClient, headers, rota: dict) -> None:
    for passo in rota["passos"]:
        client.patch(
            f"/api/v1/rotas/{rota['id']}/passos/{passo['id']}",
            headers=headers, json={"classificacao": "item_proposta"},
        )
        r = client.post(
            f"/api/v1/rotas/{rota['id']}/passos/{passo['id']}/validar", headers=headers
        )
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Auth / GET vazio / gerar
# ---------------------------------------------------------------------------


def test_unauthorized_returns_401(client: TestClient):
    assert client.get("/api/v1/processes/1/rota").status_code == 401


def test_get_rota_empty_returns_null(client: TestClient, db_session):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    headers = _login(client, "consultor@example.com", "senha123")
    r = client.get(f"/api/v1/processes/{process.id}/rota", headers=headers)
    assert r.status_code == 200
    assert r.json() is None


def test_gerar_materializes_and_get_returns_passos(client: TestClient, db_session, monkeypatch):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)

    headers = _login(client, "consultor@example.com", "senha123")
    r = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] == 2
    assert body["rota"]["status"] == "proposta"

    got = client.get(f"/api/v1/processes/{process.id}/rota", headers=headers).json()
    assert len(got["passos"]) == 2
    assert got["passos"][0]["prazo_fonte"] == "norma"
    assert got["passos"][1]["prazo_fonte"] == "estimativa_profissional"


# ---------------------------------------------------------------------------
# Reordenar / manual / editar
# ---------------------------------------------------------------------------


def test_reorder_persists_new_order(client: TestClient, db_session, monkeypatch):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)
    headers = _login(client, "consultor@example.com", "senha123")
    rota = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers).json()["rota"]
    ids = [p["id"] for p in rota["passos"]]

    r = client.patch(
        f"/api/v1/rotas/{rota['id']}/reordenar", headers=headers,
        json={"passo_ids": list(reversed(ids))},
    )
    assert r.status_code == 200, r.text
    got = client.get(f"/api/v1/processes/{process.id}/rota", headers=headers).json()
    assert [p["id"] for p in got["passos"]] == list(reversed(ids))


def test_reorder_rejects_mismatched_ids(client: TestClient, db_session, monkeypatch):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)
    headers = _login(client, "consultor@example.com", "senha123")
    rota = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers).json()["rota"]
    r = client.patch(
        f"/api/v1/rotas/{rota['id']}/reordenar", headers=headers,
        json={"passo_ids": [rota["passos"][0]["id"]]},  # incompleto
    )
    assert r.status_code == 400


def test_add_manual_passo(client: TestClient, db_session, monkeypatch):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)
    headers = _login(client, "consultor@example.com", "senha123")
    rota = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers).json()["rota"]

    r = client.post(
        f"/api/v1/rotas/{rota['id']}/passos", headers=headers,
        json={"titulo": "Ligar na secretaria", "origem_manual_nota": "orientação verbal"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["origem"] == "manual"
    assert body["origem_manual_nota"] == "orientação verbal"


# ---------------------------------------------------------------------------
# Validação exige classificação; fechar exige todos validados
# ---------------------------------------------------------------------------


def test_validar_requires_classificacao(client: TestClient, db_session, monkeypatch):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)
    headers = _login(client, "consultor@example.com", "senha123")
    rota = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers).json()["rota"]
    passo_id = rota["passos"][0]["id"]

    # Sem classificação → 400.
    r = client.post(f"/api/v1/rotas/{rota['id']}/passos/{passo_id}/validar", headers=headers)
    assert r.status_code == 400

    # Classifica → valida.
    client.patch(
        f"/api/v1/rotas/{rota['id']}/passos/{passo_id}", headers=headers,
        json={"classificacao": "direcao"},
    )
    r = client.post(f"/api/v1/rotas/{rota['id']}/passos/{passo_id}/validar", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "validado"


def test_fechar_requires_all_validated(client: TestClient, db_session, monkeypatch):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)
    headers = _login(client, "consultor@example.com", "senha123")
    rota = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers).json()["rota"]

    # Valida só um passo → fechar bloqueia (400).
    p0 = rota["passos"][0]["id"]
    client.patch(f"/api/v1/rotas/{rota['id']}/passos/{p0}", headers=headers,
                 json={"classificacao": "item_proposta"})
    client.post(f"/api/v1/rotas/{rota['id']}/passos/{p0}/validar", headers=headers)
    r = client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=headers)
    assert r.status_code == 400

    # Valida todos → fechar assina.
    _classify_and_validate_all(client, headers, rota)
    r = client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "validada"
    assert r.json()["validated_at"] is not None


def test_desatualizada_blocks_fechar(client: TestClient, db_session, monkeypatch):
    tenant, _ = _seed_user(db_session)
    process = _seed_case(db_session, tenant=tenant)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)
    headers = _login(client, "consultor@example.com", "senha123")
    rota = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers).json()["rota"]
    _classify_and_validate_all(client, headers, rota)
    assert client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=headers).status_code == 200

    # IA re-roda com um passo novo → rota vira 'desatualizada'.
    _patch_agent(monkeypatch, _ETAPAS + [
        {"ordem": 3, "titulo": "Averbar reserva legal", "orgao": "Cartório",
         "fonte_trecho": "Lei 12.651/2012, art. 18"}
    ])
    gen = client.post(f"/api/v1/processes/{process.id}/rota/gerar", headers=headers).json()
    assert gen["is_diff"] is True
    assert gen["rota"]["status"] == "desatualizada"

    # Fechar trava até aceitar o diff.
    r = client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=headers)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_tenant_isolation(client: TestClient, db_session, monkeypatch):
    tenant_a, _ = _seed_user(db_session, name="A", email="a@example.com")
    proc_a = _seed_case(db_session, tenant=tenant_a)
    tenant_b, _ = _seed_user(db_session, name="B", email="b@example.com")
    proc_b = _seed_case(db_session, tenant=tenant_b)
    db_session.commit()
    _patch_agent(monkeypatch, _ETAPAS)

    headers_a = _login(client, "a@example.com", "senha123")
    headers_b = _login(client, "b@example.com", "senha123")
    rota_b = client.post(f"/api/v1/processes/{proc_b.id}/rota/gerar", headers=headers_b).json()["rota"]

    # A não vê o processo de B, nem a rota de B.
    assert client.get(f"/api/v1/processes/{proc_b.id}/rota", headers=headers_a).status_code == 404
    assert client.patch(
        f"/api/v1/rotas/{rota_b['id']}/reordenar", headers=headers_a,
        json={"passo_ids": [p["id"] for p in rota_b["passos"]]},
    ).status_code == 404
