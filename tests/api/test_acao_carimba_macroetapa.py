"""A Ação guarda a etapa em que nasceu (validação 02/08, item 8).

As Fichas descrevem as ações de cada etapa ficando registradas e visíveis
conforme o caso avança. A aba Ações era uma lista plana — filtrável por status e
triagem, mas impossível de ler como sequência de trabalho: não dava para ver o
que foi feito na Entrada, no Diagnóstico Preliminar, na Coleta.

Faltava o DADO, não a tela: ``Acao`` não guardava a macroetapa. Sem o carimbo no
nascimento, agrupar depois seria adivinhação (o processo só guarda a etapa
ATUAL — usá-la carimbaria toda ação antiga com a etapa de hoje).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.acao import Acao
from app.models.client import Client, ClientStatus, ClientType
from app.models.macroetapa import Macroetapa
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def caso(db_session):
    tenant = Tenant(name="Ações por etapa")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="consultor.acao@example.com", full_name="Consultora",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id, is_active=True,
    )
    cli = Client(
        tenant_id=tenant.id, full_name="Cliente", email="cli.acao@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add_all([user, cli])
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Caso das ações",
        process_type="car", status=ProcessStatus.diagnostico,
        macroetapa=Macroetapa.coleta_documental.value,
    )
    db_session.add(proc)
    db_session.commit()
    return db_session, tenant, proc


def test_acao_manual_nasce_carimbada_com_a_etapa_atual(client: TestClient, caso) -> None:
    db, _tenant, proc = caso
    headers = _login(client, "consultor.acao@example.com", "senha123")

    r = client.post(
        f"/api/v1/processes/{proc.id}/acoes",
        headers=headers,
        json={"titulo": "Solicitar CCIR ao cliente"},
    )

    assert r.status_code == 201, r.text
    assert r.json()["macroetapa"] == Macroetapa.coleta_documental.value


def test_o_carimbo_e_do_nascimento_e_nao_acompanha_o_caso(client: TestClient, caso) -> None:
    """Avançar a etapa não pode reescrever o histórico das ações antigas.

    É o ponto todo do item: a ação criada na Coleta continua sendo da Coleta
    depois que o caso chega ao Diagnóstico Técnico. Do contrário a aba mostraria
    tudo empilhado na etapa corrente — que é a lista plana de antes, com outro
    rótulo.
    """
    db, _tenant, proc = caso
    headers = _login(client, "consultor.acao@example.com", "senha123")
    client.post(
        f"/api/v1/processes/{proc.id}/acoes", headers=headers,
        json={"titulo": "Ação da coleta"},
    )

    proc.macroetapa = Macroetapa.diagnostico_tecnico.value
    db.commit()

    r = client.get(f"/api/v1/processes/{proc.id}/acoes", headers=headers)
    assert r.status_code == 200, r.text
    acoes = r.json()
    assert [a["macroetapa"] for a in acoes] == [Macroetapa.coleta_documental.value]


def test_acao_antiga_sem_carimbo_continua_legivel(client: TestClient, caso) -> None:
    """NULL é resposta honesta — a etapa de origem não é recuperável.

    A tela agrupa essas sob "Etapa não registrada" em vez de inventar uma.
    """
    db, tenant, proc = caso
    db.add(Acao(
        tenant_id=tenant.id, process_id=proc.id,
        titulo="Ação anterior ao carimbo", macroetapa=None,
    ))
    db.commit()
    headers = _login(client, "consultor.acao@example.com", "senha123")

    r = client.get(f"/api/v1/processes/{proc.id}/acoes", headers=headers)

    assert r.status_code == 200, r.text
    assert r.json()[0]["macroetapa"] is None
