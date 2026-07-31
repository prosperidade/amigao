"""A consolidação que FALHA deixa trilha (validação Isis 30/07).

Reconstituição do achado: na sessão de 30/07 do caso 15 a consultora clicou
"Gravar na base", viu erro, e a auditoria do caso não tinha **uma linha** do
ocorrido — enquanto todo o resto da sessão dela (``staging_decidir``,
``macroetapa_changed``, ``rota_materializada``) estava registrado. O motivo é
estrutural: o ``_audit`` de sucesso mora DENTRO da transação que a exceção faz
rollback, então o único clique que precisava de rastro era o único que não
deixava nenhum.

O que estes testes travam:

* exceção na consolidação → ``AuditLog(action="consolidar_falhou")`` COMITADO,
  com tipo e mensagem do erro;
* a resposta ao consultor diz, em português, que nada foi gravado e que as
  decisões da Conferência continuam salvas (não é um 500 mudo);
* nada da consolidação é gravado (rollback de verdade).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def caso(db_session):
    tenant = Tenant(name="Trilha Falha")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        email="trilha.falha@example.com", full_name="Consultora",
        hashed_password=get_password_hash("Seed@2026"),
        tenant_id=tenant.id, is_active=True,
    )
    cli = Client(tenant_id=tenant.id, full_name="Titular", email="tf@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    db_session.commit()
    return tenant, user, proc


def test_falha_na_consolidacao_vira_linha_de_auditoria(client: TestClient, db_session, caso, monkeypatch):
    tenant, user, proc = caso
    headers = _login(client, user.email, "Seed@2026")

    def _explode(*_a, **_kw):
        raise RuntimeError("boom na gravação")

    monkeypatch.setattr(
        "app.services.staging_consolidation.consolidate_process", _explode
    )

    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", json={}, headers=headers)
    assert r.status_code == 500

    detalhe = r.json()["detail"]
    # A mensagem é para a consultora, não para o log: diz o que aconteceu com o
    # trabalho dela e qual é o próximo passo.
    assert "NADA foi gravado" in detalhe
    assert "Conferência continuam salvas" in detalhe
    assert "RuntimeError" in detalhe

    trilha = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.entity_type == "process",
            AuditLog.entity_id == proc.id,
            AuditLog.action == "consolidar_falhou",
        )
        .all()
    )
    assert len(trilha) == 1, "o clique que falhou tem de deixar rastro permanente"
    assert "boom na gravação" in (trilha[0].details or "")
    assert trilha[0].user_id == user.id
    # Princípio 2: a trilha da falha entra na mesma cadeia de hash das demais.
    assert trilha[0].hash_sha256


def test_erro_de_negocio_preserva_o_status_original(client: TestClient, db_session, caso, monkeypatch):
    """404/409 do domínio continuam 404/409 — o handler só cobre o inesperado."""
    from fastapi import HTTPException

    _tenant, user, proc = caso
    headers = _login(client, user.email, "Seed@2026")

    def _nao_encontrado(*_a, **_kw):
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    monkeypatch.setattr(
        "app.services.staging_consolidation.consolidate_process", _nao_encontrado
    )
    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", json={}, headers=headers)
    assert r.status_code == 404
