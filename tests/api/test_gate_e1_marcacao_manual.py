"""Gate E1 destravado pela marcação manual — item 1 da validação 20/07.

Reproduz o caminho do processo 15, que estava parado na `entrada_demanda` com
zero diagnósticos: os checkboxes das ações da etapa eram DECORATIVOS (renderizados
dentro de uma `<div>`, sem `onClick`), o endpoint de toggle existia e ninguém o
chamava, e o gate — que depende dessas ações — nunca liberava.

Cobre as três exigências da decisão do André:
  1. marcar de verdade (e PERSISTIR — `MacroetapaChecklist.actions` é JSON sem
     `MutableList`, a mesma armadilha da dívida #70);
  2. o guard-rail declara em texto claro que os agentes não rodaram, sem travar;
  3. a confirmação registra na auditoria O QUE estava pendente no momento.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.macroetapa import Macroetapa, MacroetapaChecklist
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.services.macroetapa_engine import initialize_macroetapa_checklists

_SEQ = {"n": 0}


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_e1(db_session):
    """Caso na E1, como o processo 15: nenhuma ação marcada, agentes nunca rodaram."""
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Tenant E1 {n}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email=f"consultor.e1.{n}@example.com", full_name="Consultor",
        hashed_password=get_password_hash("senha123"),
        tenant_id=tenant.id, is_active=True,
    )
    cli = Client(
        tenant_id=tenant.id, full_name="Cliente", email=f"cli.e1.{n}@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add_all([user, cli])
    db_session.flush()
    process = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Defesa Administrativa",
        process_type="car", status=ProcessStatus.triagem,
        macroetapa=Macroetapa.entrada_demanda.value,
    )
    db_session.add(process)
    db_session.flush()
    initialize_macroetapa_checklists(db_session, process, tenant.id)
    db_session.commit()
    return tenant, user, process


def _checklist_e1(db_session, process):
    return (
        db_session.query(MacroetapaChecklist)
        .filter(
            MacroetapaChecklist.process_id == process.id,
            MacroetapaChecklist.macroetapa == Macroetapa.entrada_demanda.value,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# 1. Marcar de verdade — e persistir
# ---------------------------------------------------------------------------

def test_marcar_acao_persiste_no_banco(client: TestClient, db_session):
    """A marcação tem de sobreviver ao reload — é o que o consultor vê após F5.

    `MacroetapaChecklist.actions` é `Column(JSON)` sem `MutableList`; o padrão
    antigo (`actions = list(...)` → mutar dicts compartilhados → reatribuir) não
    deixava o objeto dirty e o UPDATE nunca era emitido.
    """
    tenant, user, process = _seed_e1(db_session)
    headers = _login(client, user.email, "senha123")
    cl = _checklist_e1(db_session, process)
    action_id = cl.actions[0]["id"]

    r = client.patch(
        f"/api/v1/processes/{process.id}/macroetapa/{Macroetapa.entrada_demanda.value}/actions",
        json={"action_id": action_id, "completed": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    recarregado = _checklist_e1(db_session, process)
    marcada = next(a for a in recarregado.actions if a["id"] == action_id)
    assert marcada["completed"] is True
    assert marcada["completed_at"] is not None


def test_marcacao_grava_autoria(client: TestClient, db_session):
    """Quem marcou. Antes só o instante era gravado — sem dono, a auditoria da
    etapa não respondia "quem disse que isto foi feito?"."""
    tenant, user, process = _seed_e1(db_session)
    headers = _login(client, user.email, "senha123")
    cl = _checklist_e1(db_session, process)
    action_id = cl.actions[0]["id"]

    client.patch(
        f"/api/v1/processes/{process.id}/macroetapa/{Macroetapa.entrada_demanda.value}/actions",
        json={"action_id": action_id, "completed": True},
        headers=headers,
    )

    db_session.expire_all()
    marcada = next(
        a for a in _checklist_e1(db_session, process).actions if a["id"] == action_id
    )
    assert marcada["completed_by_user_id"] == user.id


def test_desmarcar_limpa_autoria(client: TestClient, db_session):
    tenant, user, process = _seed_e1(db_session)
    headers = _login(client, user.email, "senha123")
    cl = _checklist_e1(db_session, process)
    action_id = cl.actions[0]["id"]
    url = (
        f"/api/v1/processes/{process.id}/macroetapa/"
        f"{Macroetapa.entrada_demanda.value}/actions"
    )

    client.patch(url, json={"action_id": action_id, "completed": True}, headers=headers)
    client.patch(url, json={"action_id": action_id, "completed": False}, headers=headers)

    db_session.expire_all()
    marcada = next(
        a for a in _checklist_e1(db_session, process).actions if a["id"] == action_id
    )
    assert marcada["completed"] is False
    assert marcada["completed_by_user_id"] is None
    assert marcada["completed_at"] is None


# ---------------------------------------------------------------------------
# 2. Guard-rail: declara, nunca trava
# ---------------------------------------------------------------------------

def test_gate_avisa_que_os_agentes_nao_rodaram(client: TestClient, db_session):
    tenant, user, process = _seed_e1(db_session)
    headers = _login(client, user.email, "senha123")

    r = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers)
    assert r.status_code == 200
    gate = r.json()

    assert gate["agentes_executados"] is False
    assert any("agentes desta etapa não foram executados" in a for a in gate["avisos"])


def test_aviso_nao_e_bloqueio(client: TestClient, db_session):
    """Radar-não-cancela: com as ações marcadas, o avanço é permitido mesmo sem
    os agentes. O aviso informa; ele não tranca."""
    tenant, user, process = _seed_e1(db_session)
    headers = _login(client, user.email, "senha123")
    cl = _checklist_e1(db_session, process)
    url = (
        f"/api/v1/processes/{process.id}/macroetapa/"
        f"{Macroetapa.entrada_demanda.value}/actions"
    )
    for action in cl.actions:
        client.patch(url, json={"action_id": action["id"], "completed": True}, headers=headers)

    gate = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()

    assert gate["can_advance"] is True          # não trava
    assert gate["agentes_executados"] is False  # mas avisa
    assert gate["avisos"]


# ---------------------------------------------------------------------------
# 3. O caminho completo do processo 15 + auditoria da confirmação
# ---------------------------------------------------------------------------

def test_caminho_processo_15_marcar_tudo_e_avancar_e1_para_e2(
    client: TestClient, db_session
):
    """Marcar as ações → card libera → confirmar → E1 vira E2.

    É o caminho que estava interrompido: sem UI clicável, o caso ficava na E1
    para sempre, e o diagnóstico (que só roda na E2) nunca acontecia.
    """
    tenant, user, process = _seed_e1(db_session)
    headers = _login(client, user.email, "senha123")
    cl = _checklist_e1(db_session, process)
    url = (
        f"/api/v1/processes/{process.id}/macroetapa/"
        f"{Macroetapa.entrada_demanda.value}/actions"
    )
    for action in cl.actions:
        client.patch(url, json={"action_id": action["id"], "completed": True}, headers=headers)

    gate = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
    assert gate["can_advance"] is True
    destino = gate["next_macroetapa"]
    assert destino == Macroetapa.diagnostico_preliminar.value

    r = client.post(
        f"/api/v1/processes/{process.id}/macroetapa",
        json={"macroetapa": destino},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    atualizado = db_session.query(Process).filter(Process.id == process.id).first()
    assert atualizado.macroetapa == Macroetapa.diagnostico_preliminar.value


def test_auditoria_registra_o_que_estava_pendente_no_avanco(
    client: TestClient, db_session
):
    """Liberdade com consciência ASSINADA: a confirmação vai para a auditoria
    junto com o que estava pendente — daqui a três meses a pergunta "o consultor
    sabia?" tem resposta com a lista exata."""
    tenant, user, process = _seed_e1(db_session)
    headers = _login(client, user.email, "senha123")
    cl = _checklist_e1(db_session, process)
    url = (
        f"/api/v1/processes/{process.id}/macroetapa/"
        f"{Macroetapa.entrada_demanda.value}/actions"
    )
    for action in cl.actions:
        client.patch(url, json={"action_id": action["id"], "completed": True}, headers=headers)

    client.post(
        f"/api/v1/processes/{process.id}/macroetapa",
        json={"macroetapa": Macroetapa.diagnostico_preliminar.value},
        headers=headers,
    )

    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_type == "process",
            AuditLog.entity_id == process.id,
            AuditLog.action == "macroetapa_changed",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert "ressalvas" in (audit.details or "")
    assert "agentes da etapa não executados" in audit.details
