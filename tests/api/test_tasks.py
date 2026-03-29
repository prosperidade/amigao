from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _task_fixture(db_session):
    tenant = Tenant(name="Tenant Tarefas")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="consultor.tarefa@example.com",
        full_name="Consultor Tarefa",
        hashed_password=get_password_hash("consultor123"),
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    client_record = Client(
        tenant_id=tenant.id,
        full_name="Cliente Tarefa",
        email="cliente.tarefa@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add(client_record)
    db_session.flush()

    process = Process(
        tenant_id=tenant.id,
        client_id=client_record.id,
        title="Processo Tarefa",
        process_type="licenciamento",
        status=ProcessStatus.triagem,
    )
    db_session.add(process)
    db_session.flush()

    return tenant, user, process


def test_update_task_status_alias_endpoint_enforces_valid_transition(client: TestClient, db_session):
    _, user, process = _task_fixture(db_session)

    task = Task(
        tenant_id=user.tenant_id,
        process_id=process.id,
        title="Checklist de campo",
        status=TaskStatus.a_fazer,
        priority=TaskPriority.medium,
        created_by_user_id=user.id,
    )
    db_session.add(task)
    db_session.commit()

    headers = _login(client, "consultor.tarefa@example.com", "consultor123")
    response = client.patch(
        f"/api/v1/tasks/{task.id}/status",
        json={"status": "concluida"},
        headers=headers,
    )

    assert response.status_code == 400
    assert "Transição de status inválida" in response.json()["detail"]


def test_update_task_status_happy_path_sets_completed_at_and_audits(client: TestClient, db_session):
    _, user, process = _task_fixture(db_session)

    task = Task(
        tenant_id=user.tenant_id,
        process_id=process.id,
        title="Checklist de campo",
        status=TaskStatus.revisao,
        priority=TaskPriority.medium,
        created_by_user_id=user.id,
    )
    db_session.add(task)
    db_session.commit()

    headers = _login(client, "consultor.tarefa@example.com", "consultor123")
    response = client.patch(
        f"/api/v1/tasks/{task.id}/status",
        json={"status": "concluida"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "concluida"
    assert body["completed_at"] is not None
    assert "cancelada" in body["allowed_transitions"]

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == "task", AuditLog.entity_id == task.id, AuditLog.action == "status_changed")
        .first()
    )
    assert audit is not None
    assert audit.old_value == "revisao"
    assert audit.new_value == "concluida"


def test_task_cannot_conclude_with_pending_dependency(client: TestClient, db_session):
    _, user, process = _task_fixture(db_session)

    dependency = Task(
        tenant_id=user.tenant_id,
        process_id=process.id,
        title="Dependência",
        status=TaskStatus.em_progresso,
        priority=TaskPriority.medium,
        created_by_user_id=user.id,
    )
    task = Task(
        tenant_id=user.tenant_id,
        process_id=process.id,
        title="Tarefa Dependente",
        status=TaskStatus.revisao,
        priority=TaskPriority.medium,
        created_by_user_id=user.id,
    )
    db_session.add_all([dependency, task])
    db_session.flush()
    task.dependencies.append(dependency)
    db_session.commit()

    headers = _login(client, "consultor.tarefa@example.com", "consultor123")
    response = client.patch(
        f"/api/v1/tasks/{task.id}/status",
        json={"status": "concluida"},
        headers=headers,
    )

    assert response.status_code == 400
    assert "dependências pendentes" in response.json()["detail"]
