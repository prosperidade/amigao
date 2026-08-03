"""A E5 não pode virar beco sem saída quando a IA REMOVE um passo.

Validação 02/08: "não consigo validar a rota para avançar".

`RotaStatus.desatualizada` é marcada sempre que a IA traz diferença depois de a
rota ter sido assinada — e `is_diff` cobre dois casos bem distintos
(`rota_materializer._reconcile_passos`):

* a IA ACRESCENTOU passo  → nasce passo `proposto`, há o que validar;
* a IA REMOVEU passo      → não nasce nada, e não há o que validar.

No segundo caso o sistema se fechava sozinho: `validar_passo` — o único ponto
que devolvia a rota para `em_validacao` — nunca disparava, então a rota ficava
`desatualizada` para sempre; `fechar_rota` respondia 409 para sempre; e a tela
mostrava o botão desabilitado com o rodapé dizendo "Todos os passos validados".
Tudo verdadeiro, nada acionável.

A correção não afrouxa o gate: o que trava é ter passo PENDENTE, não o rótulo do
estado. Sem pendência, clicar em "Fechar rota" É o aceite do diff — decisão
humana, explícita e auditada.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.macroetapa import Macroetapa
from app.models.process import Process, ProcessStatus
from app.models.rota import (
    Rota,
    RotaPasso,
    RotaPassoClassificacao,
    RotaPassoOrigem,
    RotaPassoStatus,
    RotaStatus,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.macroetapa_engine import descrever_pendencia_rota


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def caso(db_session):
    tenant = Tenant(name="Rota E5")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="consultor.rota@example.com", full_name="Consultora",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id, is_active=True,
    )
    cli = Client(
        tenant_id=tenant.id, full_name="Cliente", email="cli.rota@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add_all([user, cli])
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Caso da rota",
        process_type="car", status=ProcessStatus.diagnostico,
        macroetapa=Macroetapa.caminho_regulatorio.value,
    )
    db_session.add(proc)
    db_session.flush()
    return db_session, tenant, proc


def _rota(db, tenant, proc, *, status: RotaStatus, passos_validados: int,
          passos_pendentes: int = 0) -> Rota:
    rota = Rota(tenant_id=tenant.id, process_id=proc.id, demand_type="car", status=status)
    db.add(rota)
    db.flush()
    ordem = 0
    for _ in range(passos_validados):
        ordem += 1
        db.add(RotaPasso(
            tenant_id=tenant.id, rota_id=rota.id, ordem=ordem,
            titulo=f"Passo {ordem}", origem=RotaPassoOrigem.ia,
            classificacao=RotaPassoClassificacao.item_proposta,
            status=RotaPassoStatus.validado, dedupe_key=f"r{rota.id}:v{ordem}",
        ))
    for _ in range(passos_pendentes):
        ordem += 1
        db.add(RotaPasso(
            tenant_id=tenant.id, rota_id=rota.id, ordem=ordem,
            titulo=f"Passo {ordem}", origem=RotaPassoOrigem.ia,
            status=RotaPassoStatus.proposto, dedupe_key=f"r{rota.id}:p{ordem}",
        ))
    db.commit()
    return rota


# ---------------------------------------------------------------------------
# O beco sem saída
# ---------------------------------------------------------------------------

def test_rota_desatualizada_sem_pendente_pode_fechar(client: TestClient, caso) -> None:
    """Diff por REMOÇÃO: nada a validar, então fechar é o aceite."""
    db, tenant, proc = caso
    rota = _rota(db, tenant, proc, status=RotaStatus.desatualizada, passos_validados=3)
    headers = _login(client, "consultor.rota@example.com", "senha123")

    r = client.post(f"/api/v1/rotas/{rota.id}/fechar", headers=headers)

    assert r.status_code == 200, (
        "sem passo pendente não há o que validar — manter o 409 aqui prende a "
        "consultora na E5 sem próximo movimento (validação 02/08)"
    )
    assert r.json()["status"] == RotaStatus.validada.value


def test_blocker_do_gate_para_de_mandar_validar_o_que_nao_existe(caso) -> None:
    """A frase precisa apontar a maçaneta certa: fechar, não validar."""
    db, tenant, proc = caso
    _rota(db, tenant, proc, status=RotaStatus.desatualizada, passos_validados=2)

    frase = descrever_pendencia_rota(db, tenant.id, proc.id)

    assert "Fechar rota" in frase
    assert "esperam sua conferência" not in frase


# ---------------------------------------------------------------------------
# O gate continua fechado onde tem de estar
# ---------------------------------------------------------------------------

def test_desatualizada_com_passo_novo_continua_bloqueando(client: TestClient, caso) -> None:
    """Diff por ACRÉSCIMO: aí sim há o que validar antes de reassinar."""
    db, tenant, proc = caso
    rota = _rota(db, tenant, proc, status=RotaStatus.desatualizada,
                 passos_validados=2, passos_pendentes=1)
    headers = _login(client, "consultor.rota@example.com", "senha123")

    r = client.post(f"/api/v1/rotas/{rota.id}/fechar", headers=headers)

    assert r.status_code == 409, r.text


def test_rota_em_validacao_com_pendente_continua_bloqueando(client: TestClient, caso) -> None:
    """Controle: o caminho normal não foi afrouxado junto."""
    db, tenant, proc = caso
    rota = _rota(db, tenant, proc, status=RotaStatus.em_validacao,
                 passos_validados=1, passos_pendentes=2)
    headers = _login(client, "consultor.rota@example.com", "senha123")

    r = client.post(f"/api/v1/rotas/{rota.id}/fechar", headers=headers)

    assert r.status_code == 400, r.text
    assert "não validado" in r.json()["detail"]


def test_rota_sem_passo_nenhum_continua_recusada(client: TestClient, caso) -> None:
    db, tenant, proc = caso
    rota = _rota(db, tenant, proc, status=RotaStatus.desatualizada, passos_validados=0)
    headers = _login(client, "consultor.rota@example.com", "senha123")

    r = client.post(f"/api/v1/rotas/{rota.id}/fechar", headers=headers)

    assert r.status_code == 400, r.text
