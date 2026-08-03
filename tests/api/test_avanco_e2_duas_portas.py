"""O botão "avançar" precisa dar conta das DUAS saídas da E2 (validação 02/08).

A consultora relatou que o avanço E2→E3 "só funcionou clicando na aba entre
colchetes". O botão era a via natural — e a via natural não levava aonde ela
precisava.

A causa é de desenho, não de clique: a Ficha 07 §6 prevê dois destinos legítimos
saindo do Diagnóstico Preliminar —

    E2 → E3  há documentos essenciais a coletar
    E2 → E4  não há documentos essenciais pendentes (pula a coleta)

— e `MACROETAPA_TRANSITIONS` aceita ambos. Mas `/can-advance` devolvia só o
destino RECOMENDADO (`resolve_next_macroetapa`), e a tela renderizava um botão
só. Quem precisava do outro caminho não tinha maçaneta: clicava na aba, o que
contorna o gate, o guard-rail da confirmação e a linha de auditoria.

Este teste percorre o caminho do BOTÃO, ponta a ponta pela API: ler o gate,
achar as duas portas, e atravessar cada uma delas.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.macroetapa import Macroetapa, MacroetapaChecklist
from app.models.process import Process, ProcessStatus
from app.models.regulatory import RegulatoryDiagnosis
from app.models.tenant import Tenant
from app.models.user import User
from app.services.macroetapa_engine import initialize_macroetapa_checklists


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def caso_na_e2(db_session):
    """Caso parado na E2 com o checklist da etapa inteiro concluído."""
    tenant = Tenant(name="Ramo E2")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="consultor.ramo@example.com", full_name="Consultora",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id, is_active=True,
    )
    cli = Client(
        tenant_id=tenant.id, full_name="Cliente", email="cli.ramo@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add_all([user, cli])
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Caso do ramo",
        process_type="car", status=ProcessStatus.diagnostico,
        macroetapa=Macroetapa.diagnostico_preliminar.value,
    )
    db_session.add(proc)
    db_session.flush()
    initialize_macroetapa_checklists(db_session, proc, tenant.id)

    # O gate da E2 tem três exigências (can_advance_macroetapa): checklist
    # completo, diagnóstico assinado e Consolidação executada. Este teste é sobre
    # o DESTINO do avanço, não sobre o gate — então as três são satisfeitas aqui
    # de propósito, para que um 409 no POST signifique "porta fechada", e não
    # "faltou preparar o caso".
    e2 = (
        db_session.query(MacroetapaChecklist)
        .filter(
            MacroetapaChecklist.process_id == proc.id,
            MacroetapaChecklist.macroetapa == Macroetapa.diagnostico_preliminar.value,
        )
        .first()
    )
    e2.actions = [{**a, "completed": True} for a in e2.actions]
    e2.completion_pct = 100.0
    db_session.add(RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=proc.id,
        validated_at=datetime.now(UTC),
    ))
    db_session.add(AuditLog(
        tenant_id=tenant.id, entity_type="process", entity_id=proc.id,
        # `details` é coluna Text (não JSON) — dict aqui derruba o INSERT.
        action="consolidar", details=f"consolidação do processo {proc.id}",
    ))
    db_session.commit()
    return proc


def _gate(client: TestClient, headers: dict, process_id: int) -> dict:
    r = client.get(f"/api/v1/processes/{process_id}/can-advance", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# As duas portas existem e são nomeadas
# ---------------------------------------------------------------------------

def test_gate_da_e2_oferece_os_dois_destinos(client: TestClient, caso_na_e2) -> None:
    headers = _login(client, "consultor.ramo@example.com", "senha123")

    gate = _gate(client, headers, caso_na_e2.id)

    assert gate["current_macroetapa"] == Macroetapa.diagnostico_preliminar.value
    destinos = {gate["next_macroetapa"], *gate["next_macroetapa_alternativas"]}
    assert destinos == {
        Macroetapa.coleta_documental.value,
        Macroetapa.diagnostico_tecnico.value,
    }, (
        "a E2 tem duas saídas na Ficha 07 §6; oferecer só a recomendada é o que "
        "empurrava a consultora a clicar na aba e contornar o gate"
    )


def test_o_recomendado_nunca_se_repete_nas_alternativas(client: TestClient, caso_na_e2) -> None:
    """Senão a tela renderizaria o mesmo destino duas vezes."""
    headers = _login(client, "consultor.ramo@example.com", "senha123")

    gate = _gate(client, headers, caso_na_e2.id)

    assert gate["next_macroetapa"] not in gate["next_macroetapa_alternativas"]


# ---------------------------------------------------------------------------
# Atravessar cada porta pelo caminho do botão
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "destino",
    [Macroetapa.coleta_documental.value, Macroetapa.diagnostico_tecnico.value],
)
def test_avanco_pelo_botao_leva_a_qualquer_das_duas_portas(
    client: TestClient, db_session, caso_na_e2, destino: str
) -> None:
    """É o POST que o botão dispara — o mesmo para a porta principal e a segunda."""
    headers = _login(client, "consultor.ramo@example.com", "senha123")

    r = client.post(
        f"/api/v1/processes/{caso_na_e2.id}/macroetapa",
        headers=headers,
        json={"macroetapa": destino},
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    atualizado = db_session.query(Process).filter(Process.id == caso_na_e2.id).first()
    assert atualizado.macroetapa == destino


def test_destino_invalido_continua_recusado(client: TestClient, caso_na_e2) -> None:
    """Abrir a segunda porta não pode abrir todas: E2 não salta para a E6."""
    headers = _login(client, "consultor.ramo@example.com", "senha123")

    r = client.post(
        f"/api/v1/processes/{caso_na_e2.id}/macroetapa",
        headers=headers,
        json={"macroetapa": Macroetapa.orcamento_negociacao.value},
    )

    assert r.status_code in (400, 409), r.text


# ---------------------------------------------------------------------------
# Etapa terminal
# ---------------------------------------------------------------------------

def test_etapa_final_nao_oferece_porta_nenhuma(client: TestClient, db_session, caso_na_e2) -> None:
    """No fim do fluxo não há destino — e a tela precisa saber disso para DIZER,
    em vez de deixar o clique cair num `return` mudo."""
    headers = _login(client, "consultor.ramo@example.com", "senha123")
    caso_na_e2.macroetapa = Macroetapa.contrato_formalizacao.value
    db_session.commit()

    gate = _gate(client, headers, caso_na_e2.id)

    assert gate["next_macroetapa"] is None
    assert gate["next_macroetapa_alternativas"] == []
