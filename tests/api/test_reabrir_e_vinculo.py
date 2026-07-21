"""Reabrir decisão + vínculo manual (degrau 4) — pré-requisitos da re-decisão.

No caso 15 o consultor decidiu com a tela cega: aceitou o CCIR (que declara o
número de matrícula defasado, 2923) e rejeitou a certidão (4698). Para corrigir
isso pela tela consertada — e não por UPDATE manual em produção — ele precisa
poder REABRIR o que decidiu. É o que estes testes travam.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User

_SEQ = {"n": 0}


def _login(client: TestClient, email: str, senha: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Reabrir {n}")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=f"c.reabrir{n}@example.com", full_name="Consultor",
                hashed_password=get_password_hash("senha123"),
                tenant_id=tenant.id, is_active=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"cli.re{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    doc = Document(tenant_id=tenant.id, process_id=proc.id,
                   original_file_name="d.pdf", filename="d.pdf",
                   content_type="application/pdf", storage_key=f"re/{tenant.id}/{n}",
                   document_type="itr", ocr_status=OcrStatus.done)
    db_session.add(doc)
    db_session.flush()
    db_session.commit()
    return tenant, user, proc, prop, doc


def _linha(db_session, tenant, proc, doc, **kw):
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=kw.get("field_name", "nirf_cib"),
        field_value=kw.get("field_value", {"value": "6.442.022-1"}),
        status=kw.get("status", ExtractedFieldStatus.pendente),
        target_entity="matricula",
        target_field=kw.get("target_field", "nirf_cib"),
        matricula_hint=kw.get("matricula_hint"),
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()
    return row


# ---------------------------------------------------------------------------
# Reabrir decisão
# ---------------------------------------------------------------------------

def test_reabrir_devolve_para_pendente(client: TestClient, db_session):
    tenant, user, proc, prop, doc = _seed(db_session)
    linha = _linha(db_session, tenant, proc, doc)
    headers = _login(client, user.email, "senha123")
    url = f"/api/v1/processes/{proc.id}/staging-fields/{linha.id}/decidir"

    client.post(url, json={"acao": "aceitar"}, headers=headers)
    r = client.post(url, json={"acao": "reabrir"}, headers=headers)

    assert r.status_code == 200, r.text
    db_session.expire_all()
    recarregada = db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.id == linha.id).first()
    assert recarregada.status == ExtractedFieldStatus.pendente
    assert recarregada.decided_at is None
    assert recarregada.decided_by_user_id is None
    assert recarregada.decided_value is None


def test_reabrir_registra_a_decisao_anterior(client: TestClient, db_session):
    """Reabrir não apaga história — acrescenta."""
    tenant, user, proc, prop, doc = _seed(db_session)
    linha = _linha(db_session, tenant, proc, doc)
    headers = _login(client, user.email, "senha123")
    url = f"/api/v1/processes/{proc.id}/staging-fields/{linha.id}/decidir"

    client.post(url, json={"acao": "rejeitar"}, headers=headers)
    client.post(url, json={"acao": "reabrir"}, headers=headers)

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == proc.id, AuditLog.action == "staging_reabrir")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert "rejeitado" in (audit.details or "")


def test_reabrir_permite_decidir_de_novo(client: TestClient, db_session):
    """O caminho da Fase 3: rejeitado por engano → reaberto → aceito."""
    tenant, user, proc, prop, doc = _seed(db_session)
    linha = _linha(db_session, tenant, proc, doc)
    headers = _login(client, user.email, "senha123")
    url = f"/api/v1/processes/{proc.id}/staging-fields/{linha.id}/decidir"

    client.post(url, json={"acao": "rejeitar"}, headers=headers)
    client.post(url, json={"acao": "reabrir"}, headers=headers)
    r = client.post(url, json={"acao": "aceitar"}, headers=headers)

    assert r.status_code == 200, r.text
    db_session.expire_all()
    recarregada = db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.id == linha.id).first()
    assert recarregada.status == ExtractedFieldStatus.aceito


# ---------------------------------------------------------------------------
# Degrau 4 — candidatos e vínculo manual
# ---------------------------------------------------------------------------

def test_candidatos_autolink_por_nirf(client: TestClient, db_session):
    tenant, user, proc, prop, doc = _seed(db_session)
    mat = Matricula(tenant_id=tenant.id, property_id=prop.id,
                    numero_matricula="6776", nirf_cib="6.442.022-1")
    db_session.add(mat)
    db_session.flush()
    _linha(db_session, tenant, proc, doc)
    headers = _login(client, user.email, "senha123")

    r = client.get(f"/api/v1/processes/{proc.id}/vinculo-candidatos/{doc.id}",
                   headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["autolink"] is True
    assert body["nivel"] == 1
    assert body["matricula_id"] == mat.id


def test_candidatos_sem_sinal_lista_para_escolha(client: TestClient, db_session):
    tenant, user, proc, prop, doc = _seed(db_session)
    for numero in ("6776", "2923"):
        db_session.add(Matricula(tenant_id=tenant.id, property_id=prop.id,
                                 numero_matricula=numero))
    db_session.flush()
    _linha(db_session, tenant, proc, doc, field_value={"value": "9.999.999-9"})
    headers = _login(client, user.email, "senha123")

    body = client.get(f"/api/v1/processes/{proc.id}/vinculo-candidatos/{doc.id}",
                      headers=headers).json()

    assert body["autolink"] is False
    assert len(body["candidatas"]) == 2


def test_vinculo_manual_ancora_e_grava_proveniencia(client: TestClient, db_session):
    """A escolha do consultor é dado de proveniência — útil se a divergência de
    INCRA virar retificação formal depois (observação da Isis)."""
    tenant, user, proc, prop, doc = _seed(db_session)
    mat = Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="6776")
    db_session.add(mat)
    db_session.flush()
    linha = _linha(db_session, tenant, proc, doc)
    headers = _login(client, user.email, "senha123")

    r = client.post(f"/api/v1/processes/{proc.id}/vinculo-manual/{doc.id}",
                    json={"matricula_id": mat.id}, headers=headers)

    assert r.status_code == 200, r.text
    assert r.json()["linhas_ancoradas"] == 1

    db_session.expire_all()
    assert db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.id == linha.id).first().matricula_hint == "6776"
    recarregada = db_session.query(Matricula).filter(Matricula.id == mat.id).first()
    vinculos = recarregada.lineage["vinculos_manuais"]
    assert vinculos[0]["document_id"] == doc.id
    assert vinculos[0]["user_id"] == user.id
    assert vinculos[0]["sinal"] == "manual"


def test_vinculo_manual_matricula_inexistente(client: TestClient, db_session):
    tenant, user, proc, prop, doc = _seed(db_session)
    headers = _login(client, user.email, "senha123")

    r = client.post(f"/api/v1/processes/{proc.id}/vinculo-manual/{doc.id}",
                    json={"matricula_id": 999999}, headers=headers)

    assert r.status_code == 404
