"""Ficha 01 / FASE 4 — decisão do consultor + consolidação (ciclo completo)."""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.matricula import Matricula
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _st(tenant_id, process_id, source, fname, value, status, *, entity, target, hint=None):
    # Em produção todo campo 'aceito' carrega decided_value (decide_field/
    # bulk_accept o gravam); só o ACHADO (divergente_fundo aceito) fica None. O
    # fixture espelha esse contrato para refletir o staging real.
    decided = {"value": value} if status == ExtractedFieldStatus.aceito else None
    return ExtractedFieldStaging(
        tenant_id=tenant_id, process_id=process_id, source_doc_type=source,
        field_name=fname, field_value={"value": value}, status=status,
        decided_value=decided,
        target_entity=entity, target_field=target, matricula_hint=hint,
        created_by_agent="extrator",
    )


def _setup(db_session, email="f4@example.com"):
    tenant = Tenant(name="Fase4 Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente Antigo", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    C = ExtractedFieldStatus
    rows = [
        # matrícula 4.698 (consistentes)
        _st(tenant.id, proc.id, "matricula", "area_registrada_ha", "660,6561", C.consistente, entity="matricula", target="area_ha", hint="4.698"),
        _st(tenant.id, proc.id, "matricula", "cartorio", "CRI Uirapuru", C.consistente, entity="matricula", target="cartorio", hint="4.698"),
        _st(tenant.id, proc.id, "matricula", "averbacao_rl", "132,00 ha averbada", C.consistente, entity="matricula", target="averbacao_rl", hint="4.698"),
        # matrícula 6.776 (consistente)
        _st(tenant.id, proc.id, "matricula", "area_registrada_ha", "349,9022", C.consistente, entity="matricula", target="area_ha", hint="6.776"),
        # cliente + imóvel (consistentes)
        _st(tenant.id, proc.id, "matricula", "nome", "Luiz Augusto da Silva", C.consistente, entity="cliente", target="full_name"),
        _st(tenant.id, proc.id, "car", "numero_car", "GO-5221080-A1B2C3", C.consistente, entity="imovel", target="car_code"),
        # CAR área total — DIVERGENTE (gate + escolher_fonte); total_area_ha não é gravado
        _st(tenant.id, proc.id, "car", "area_declarada_ha", "1.010,7113", C.divergente_transcricao, entity="imovel", target="total_area_ha"),
    ]
    db_session.add_all(rows)
    db_session.flush()
    return tenant, proc, cli, prop, {r.field_name + ":" + (r.matricula_hint or r.target_field): r.id for r in rows}


def test_ciclo_completo_decisao_e_consolidacao(client: TestClient, db_session):
    tenant, proc, cli, prop, ids = _setup(db_session)
    db_session.commit()
    h = _login(client, "f4@example.com")
    base = f"/api/v1/processes/{proc.id}"

    # 1) aceita consistentes em lote (6 consistentes; o divergente fica de fora)
    r = client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["aceitos"] == 6

    # 2) gate: aceitar um divergente_transcricao → 422
    car_div = ids["area_declarada_ha:total_area_ha"]
    r = client.post(f"{base}/staging-fields/{car_div}/decidir", headers=h, json={"acao": "aceitar"})
    assert r.status_code == 422

    # 3) escolher_fonte no divergente → aceito (total_area_ha não será gravado)
    r = client.post(f"{base}/staging-fields/{car_div}/decidir", headers=h, json={"acao": "escolher_fonte"})
    assert r.status_code == 200
    assert r.json()["status"] == "aceito"

    # 4) consolidar → cria as 2 matrículas + atualiza cliente/imóvel
    r = client.post(f"{base}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["matriculas_criadas"] == 2
    assert res["cliente_atualizado"] is True
    assert res["imovel_atualizado"] is True
    assert res["area_total_matriculas"] == 1010.5583

    # base real gravada
    mats = db_session.query(Matricula).filter(Matricula.property_id == prop.id).order_by(Matricula.numero_matricula).all()
    assert [m.numero_matricula for m in mats] == ["4.698", "6.776"]
    m4698 = next(m for m in mats if m.numero_matricula == "4.698")
    assert m4698.area_ha == 660.6561
    assert m4698.cartorio == "CRI Uirapuru"
    assert "132" in (m4698.averbacao_rl or "")
    db_session.refresh(cli)
    assert cli.full_name == "Luiz Augusto da Silva"
    db_session.refresh(prop)
    assert prop.car_code == "GO-5221080-A1B2C3"
    # total_area_ha NÃO sobrescrito (Ficha: área = derivada)
    assert prop.total_area_ha is None
    assert prop.area_total_matriculas() == 1010.5583

    # 5) idempotência — re-consolidar não duplica
    r2 = client.post(f"{base}/consolidar", headers=h)
    assert r2.status_code == 200
    assert r2.json()["matriculas_criadas"] == 0
    assert db_session.query(Matricula).filter(Matricula.property_id == prop.id).count() == 2


def test_consolidacao_parcial_divergente_vira_acao(client: TestClient, db_session):
    """Consolidação PARCIAL (decisão Isis, opção b): aceita-se só os consistentes
    e consolida-se SEM resolver o divergente_transcricao. Os consistentes gravam
    e o divergente vira UMA Acao (origem=consolidacao). Audit registra. Idempotente."""
    from app.models.acao import Acao, AcaoOrigem
    from app.models.audit_log import AuditLog

    tenant, proc, cli, prop, ids = _setup(db_session, email="f4parcial@example.com")
    db_session.commit()
    h = _login(client, "f4parcial@example.com")
    base = f"/api/v1/processes/{proc.id}"

    # aceita os consistentes; o divergente (area_declarada_ha→total_area_ha) fica pendente
    client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)

    # consolida sem resolver o divergente → não bloqueia
    r = client.post(f"{base}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["campos_gravados"] > 0          # consistentes gravaram
    assert res["matriculas_criadas"] == 2
    assert res["acoes_criadas"] == 1           # divergente virou ação

    acoes = db_session.query(Acao).filter(Acao.process_id == proc.id).all()
    assert len(acoes) == 1
    assert acoes[0].origem == AcaoOrigem.consolidacao
    assert acoes[0].origem_fontes                       # carrega fonte (Princípio 11)
    assert acoes[0].vinculo_passivo["tipo"] == "divergencia"

    # audit action='consolidar' passou a existir (antes: ZERO)
    audits = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == proc.id, AuditLog.action == "consolidar")
        .all()
    )
    assert len(audits) >= 1
    assert audits[0].hash_sha256 is not None            # hash chain (Princípio 2)

    # idempotência: re-consolidar não duplica gravação nem ação
    r2 = client.post(f"{base}/consolidar", headers=h)
    assert r2.json()["acoes_criadas"] == 0
    assert db_session.query(Acao).filter(Acao.process_id == proc.id).count() == 1


def test_criar_acao_explicita_na_divergencia(client: TestClient, db_session):
    """Fase 0 (gap-analysis Ficha 07, item 6) — 3º caminho EXPLÍCITO: o
    consultor clica "criar ação" na divergência ANTES de consolidar. A ação
    nasce na hora (mesmo gerador da consolidação); o campo continua
    divergente_transcricao (decisão foi "virar trabalho", não "resolver
    valor"); consolidar depois não duplica (dedupe_key idempotente)."""
    from app.models.acao import Acao, AcaoOrigem

    tenant, proc, cli, prop, ids = _setup(db_session, email="f4criaracao@example.com")
    db_session.commit()
    h = _login(client, "f4criaracao@example.com")
    base = f"/api/v1/processes/{proc.id}"
    field_id = ids["area_declarada_ha:total_area_ha"]

    r = client.post(
        f"{base}/staging-fields/{field_id}/decidir",
        headers=h, json={"acao": "criar_acao"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "divergente_transcricao"  # não "resolve" o valor

    acoes = db_session.query(Acao).filter(Acao.process_id == proc.id).all()
    assert len(acoes) == 1
    assert acoes[0].origem == AcaoOrigem.consolidacao

    # consolidar depois não duplica (mesma dedupe_key)
    client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)
    r2 = client.post(f"{base}/consolidar", headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["acoes_criadas"] == 0
    assert db_session.query(Acao).filter(Acao.process_id == proc.id).count() == 1


def test_criar_acao_rejeita_fora_de_divergente_transcricao(client: TestClient, db_session):
    """'criar_acao' só se aplica a divergente_transcricao — 422 nos demais status."""
    tenant, proc, cli, prop, ids = _setup(db_session, email="f4criaracaoerr@example.com")
    db_session.commit()
    h = _login(client, "f4criaracaoerr@example.com")
    base = f"/api/v1/processes/{proc.id}"
    consistente_field_id = ids["area_registrada_ha:4.698"]

    r = client.post(
        f"{base}/staging-fields/{consistente_field_id}/decidir",
        headers=h, json={"acao": "criar_acao"},
    )
    assert r.status_code == 422


def test_rl_bridge_matricula_para_imovel(client: TestClient, db_session):
    """Ponte matrícula→imóvel (Princípio 11): RL só chega como averbação na
    matrícula; o Hub lê prop.rl_status. Derivamos 'averbada' marcando a origem
    como derivada (transparente). APP NÃO é derivada de texto livre."""
    tenant, proc, cli, prop, ids = _setup(db_session, email="f4rl@example.com")
    assert prop.rl_status is None
    db_session.commit()
    h = _login(client, "f4rl@example.com")
    base = f"/api/v1/processes/{proc.id}"

    client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)  # inclui averbacao_rl da 4.698
    r = client.post(f"{base}/consolidar", headers=h)
    assert r.status_code == 200, r.text

    db_session.refresh(prop)
    assert prop.rl_status == "averbada"
    assert (prop.field_sources or {}).get("rl_status") == "derived_matricula"
    # APP não é inventada de texto livre — sem dado estruturado, fica vazia.
    assert prop.app_area_ha is None


def test_rl_status_nivel_imovel_grava_via_allowlist(client: TestClient, db_session):
    """rl_status passou a estar na allowlist do imóvel: o RL de nível-imóvel
    (rl_declarada_ha→imovel.rl_status) grava (antes caía em `ignorados`)."""
    tenant, proc, cli, prop = _setup_min(db_session, "f4rlimovel@example.com")
    C = ExtractedFieldStatus
    db_session.add(_st(tenant.id, proc.id, "car", "rl_declarada_ha", "proposta", C.aceito,
                       entity="imovel", target="rl_status"))
    db_session.commit()
    h = _login(client, "f4rlimovel@example.com")
    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    assert "imovel.rl_status" not in r.json().get("ignorados", [])
    db_session.refresh(prop)
    assert prop.rl_status == "proposta"


def test_editar_grava_decided_value_e_consolida(client: TestClient, db_session):
    tenant, proc, cli, prop, ids = _setup(db_session, email="f4b@example.com")
    db_session.commit()
    h = _login(client, "f4b@example.com")
    base = f"/api/v1/processes/{proc.id}"

    # editar a área da matrícula 4.698 (override manual) — exige valor
    fid = ids["area_registrada_ha:4.698"]
    r = client.post(f"{base}/staging-fields/{fid}/decidir", headers=h, json={"acao": "editar"})
    assert r.status_code == 422  # valor obrigatório
    r = client.post(f"{base}/staging-fields/{fid}/decidir", headers=h, json={"acao": "editar", "valor": "661,0000"})
    assert r.status_code == 200
    assert r.json()["decided_value"] == "661,0000"

    client.post(f"{base}/consolidar", headers=h)
    mat = db_session.query(Matricula).filter(Matricula.numero_matricula == "4.698").first()
    assert mat is not None and mat.area_ha == 661.0


def test_rejeitar_nao_grava(client: TestClient, db_session):
    tenant, proc, cli, prop, ids = _setup(db_session, email="f4c@example.com")
    db_session.commit()
    h = _login(client, "f4c@example.com")
    base = f"/api/v1/processes/{proc.id}"

    client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)
    # rejeita o cartório da 4.698
    fid = ids["cartorio:4.698"]
    r = client.post(f"{base}/staging-fields/{fid}/decidir", headers=h, json={"acao": "rejeitar"})
    assert r.status_code == 200 and r.json()["status"] == "rejeitado"

    client.post(f"{base}/consolidar", headers=h)
    mat = db_session.query(Matricula).filter(Matricula.numero_matricula == "4.698").first()
    # matrícula criada (área aceita), mas cartório rejeitado não gravou
    assert mat is not None
    assert mat.cartorio is None


# ── Item 2 (Ficha 05) — âncora SIGEF, reconciliação, achado não grava ──────

def _setup_min(db_session, email):
    """Tenant/user/cliente/imóvel/processo mínimos, sem staging."""
    tenant = Tenant(name=f"T {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="C", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cli", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda X")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, cli, prop


def test_ancora_sigef_define_fonte_multiplas_consistentes(client: TestClient, db_session):
    """Mesmo destino (matrícula 4655 area_ha) por CCIR e SIGEF, mesmo valor: sem
    escolha do consultor, a âncora é o SIGEF (Ficha 05) — vence a proveniência."""
    tenant, proc, cli, prop = _setup_min(db_session, "f4sigef@example.com")
    C = ExtractedFieldStatus
    db_session.add_all([
        _st(tenant.id, proc.id, "ccir", "area_ha", "349,9022", C.aceito,
            entity="matricula", target="area_ha", hint="4655"),
        _st(tenant.id, proc.id, "sigef", "area_georreferenciada_ha", "349,9022", C.aceito,
            entity="matricula", target="area_ha", hint="4655"),
    ])
    db_session.commit()
    h = _login(client, "f4sigef@example.com")
    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["campos_gravados"] == 1  # 1 destino, não 2
    area_writes = [w for w in res["writes"] if w["field"] == "area_ha"]
    assert len(area_writes) == 1
    assert area_writes[0]["fonte"] == "sigef"
    mat = db_session.query(Matricula).filter(Matricula.numero_matricula == "4655").first()
    assert mat is not None and mat.area_ha == 349.9022


def test_reconciliacao_nao_sobrescreve_valor_ja_consolidado(client: TestClient, db_session):
    """Campo já consolidado + doc novo com valor diferente → NÃO sobrescreve,
    volta como reconciliação (alerta) — Ficha 05."""
    tenant, proc, cli, prop = _setup_min(db_session, "f4rec@example.com")
    C = ExtractedFieldStatus
    row1 = _st(tenant.id, proc.id, "matricula", "area_registrada_ha", "349,9022", C.aceito,
               entity="matricula", target="area_ha", hint="4655")
    db_session.add(row1)
    db_session.commit()
    h = _login(client, "f4rec@example.com")
    base = f"/api/v1/processes/{proc.id}"

    r1 = client.post(f"{base}/consolidar", headers=h)
    assert r1.json()["campos_gravados"] == 1
    mat = db_session.query(Matricula).filter(Matricula.numero_matricula == "4655").first()
    assert mat.area_ha == 349.9022

    # doc novo: valor divergente para o MESMO campo já consolidado
    db_session.add(_st(tenant.id, proc.id, "sigef", "area_georreferenciada_ha", "400,0000",
                       C.aceito, entity="matricula", target="area_ha", hint="4655"))
    db_session.commit()
    r2 = client.post(f"{base}/consolidar", headers=h)
    res2 = r2.json()
    assert res2["campos_gravados"] == 0           # não regravou
    assert len(res2["reconciliacoes"]) == 1       # voltou como alerta
    rec = res2["reconciliacoes"][0]
    assert rec["field"] == "area_ha"
    assert rec["anterior"] == 349.9022 and rec["novo"] == 400.0
    db_session.refresh(mat)
    assert mat.area_ha == 349.9022                # NÃO sobrescrito


def test_divergente_fundo_aceito_como_achado_nao_grava(client: TestClient, db_session):
    """divergente_fundo 'aceito' é achado (decided_value None) — NÃO grava valor."""
    tenant, proc, cli, prop = _setup_min(db_session, "f4fundo@example.com")
    C = ExtractedFieldStatus
    db_session.add(_st(tenant.id, proc.id, "matricula", "area_registrada_ha", "349,9022",
                       C.divergente_fundo, entity="matricula", target="area_ha", hint="4655"))
    db_session.commit()
    h = _login(client, "f4fundo@example.com")
    base = f"/api/v1/processes/{proc.id}"

    fid = db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.process_id == proc.id).first().id
    r = client.post(f"{base}/staging-fields/{fid}/decidir", headers=h, json={"acao": "aceitar"})
    assert r.status_code == 200 and r.json()["status"] == "aceito"

    r = client.post(f"{base}/consolidar", headers=h)
    assert r.json()["campos_gravados"] == 0
    mat = db_session.query(Matricula).filter(Matricula.numero_matricula == "4655").first()
    # achado não grava valor; matrícula pode existir sem área
    assert mat is None or mat.area_ha is None
