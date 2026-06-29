"""Reprodução do 500 do /consolidar no caso 13 (dados reais do painel)."""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client, email, password="x12345"):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _st(tenant_id, process_id, source, fname, value, status, *, entity, target, hint=None):
    decided = {"value": value} if status == ExtractedFieldStatus.aceito else None
    return ExtractedFieldStaging(
        tenant_id=tenant_id, process_id=process_id, source_doc_type=source,
        field_name=fname, field_value={"value": value}, status=status,
        decided_value=decided, target_entity=entity, target_field=target,
        matricula_hint=hint, created_by_agent="extrator",
    )


def test_repro_caso13_consolidar(client: TestClient, db_session):
    tenant = Tenant(name="T13")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="r13@example.com", full_name="C", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Leonardo", email="c.r13@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso 13", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    C = ExtractedFieldStatus
    t, p = tenant.id, proc.id

    rows = [
        # imovel — alguns fora da allowlist (módulos/regulatory/rat_data)
        _st(t, p, "rat", "area_grafica_ha", "1010.7113", C.aceito, entity="imovel", target="area_grafica_ha"),
        _st(t, p, "rat", "numero_car", "GO-5220009-3B9F", C.aceito, entity="imovel", target="car_code"),
        _st(t, p, "rat", "situacao_car", "Pendente", C.aceito, entity="imovel", target="car_status"),
        _st(t, p, "rat", "modulos_fiscais", "14,4400 módulos", C.aceito, entity="imovel", target="modulos_fiscais"),
        _st(t, p, "ccir", "municipio", "São João D'Aliança", C.aceito, entity="imovel", target="municipality"),
        _st(t, p, "rat", "data_emissao", "24/11/2024", C.aceito, entity="imovel", target="rat_data_emissao"),
        _st(t, p, "rat", "regulatory_issues", "4 itens", C.aceito, entity="imovel", target="regulatory_issues"),
        # matricula 6776 — área, app, RL averbada, número, proprietário (string)
        _st(t, p, "matricula", "area", "349,9022", C.aceito, entity="matricula", target="area_ha", hint="6776"),
        _st(t, p, "matricula", "averbacao_app", {"area": "186,1647", "referencia": "matrícula n° 4.655"}, C.aceito, entity="matricula", target="averbacao_app", hint="6776"),
        _st(t, p, "matricula", "averbacao_rl", {"area": "186,1647", "referencia": "AV.10/M3.026"}, C.aceito, entity="matricula", target="averbacao_rl", hint="6776"),
        _st(t, p, "matricula", "numero", "6.776", C.aceito, entity="matricula", target="numero_matricula", hint="6776"),
        # proprietarios como STRING (não lista) — destino matricula.proprietarios (PortableJSON)
        _st(t, p, "ccir", "proprietario", "Leonardo Ribeiro", C.aceito, entity="matricula", target="proprietarios", hint="2923"),
        _st(t, p, "ccir", "proprietario", "Gabriela Ribeiro Werner", C.aceito, entity="matricula", target="proprietarios", hint="2923"),
        # matricula 2923 e 492262 com áreas
        _st(t, p, "ccir", "area", "660,6561", C.aceito, entity="matricula", target="area_ha", hint="2923"),
        _st(t, p, "sigef", "area", "3,1256", C.aceito, entity="matricula", target="area_ha", hint="492262"),
        _st(t, p, "ccir", "codigo_incra", "950.084.286.346", C.aceito, entity="matricula", target="codigo_incra_sncr", hint="2923"),
        # 4 divergências de denominação (transcrição) em destinos distintos → geram ações
        _st(t, p, "matricula", "denominacao", "Fazenda SÃO JORGE LOTE 01-C", C.divergente_transcricao, entity="matricula", target="denominacao_imovel", hint="6776"),
        _st(t, p, "ccir", "denominacao", "Fazenda Shangri-la parte 2", C.divergente_transcricao, entity="matricula", target="denominacao_imovel", hint="6776"),
        _st(t, p, "matricula", "denominacao", "FAZENDA SÃO JORGE – GLEBA 01 B", C.divergente_transcricao, entity="matricula", target="denominacao_imovel", hint="4698"),
        _st(t, p, "itr", "denominacao", "FAZENDA SAO JORGE LOTE 01-C", C.divergente_transcricao, entity="matricula", target="denominacao_imovel", hint=None),
        # divergente_fundo (achado) — área gráfica
        _st(t, p, "rat", "area_grafica_ha", "1010.7113", C.divergente_fundo, entity="imovel", target="area_grafica_ha"),
    ]
    db_session.add_all(rows)
    db_session.commit()

    h = _login(client, "r13@example.com")
    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
    # Antes: 500 (psycopg2 can't adapt type 'dict' ao gravar averbacao_app/rl Text).
    assert r.status_code == 200, r.text
    res = r.json()

    # Gravou: matrículas criadas + ações das divergências de denominação.
    assert res["campos_gravados"] > 0
    assert res["matriculas_criadas"] >= 3            # 6776, 2923, 492262
    assert res["acoes_criadas"] == 3                 # denominacao divergente em 3 destinos

    from app.models.acao import Acao, AcaoOrigem
    from app.models.audit_log import AuditLog
    from app.models.matricula import Matricula

    # averbacao_app/rl gravados como TEXTO legível (não dict cru).
    m6776 = db_session.query(Matricula).filter(Matricula.numero_matricula == "6776").first()
    assert m6776 is not None
    assert isinstance(m6776.averbacao_app, str) and "186,1647" in m6776.averbacao_app
    assert isinstance(m6776.averbacao_rl, str)

    # audit 'consolidar' passou a existir (era ZERO).
    assert db_session.query(AuditLog).filter(
        AuditLog.entity_id == proc.id, AuditLog.action == "consolidar").count() >= 1

    # ações nascidas das divergências, com origem própria.
    acoes = db_session.query(Acao).filter(Acao.process_id == proc.id, Acao.origem == AcaoOrigem.consolidacao).all()
    assert len(acoes) == 3
