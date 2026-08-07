"""O consultor vê o que foi gravado — round-trip real (auditoria 06/08).

Contraparte de backend do E2E de UI (`ConsolidacaoPanel.test.tsx`): lá se prova
que a TELA muda de estado; aqui se prova que o servidor tem o que dizer.

O caso 16 em produção gravou 16 campos numa sessão e a consultora leu "gravou
apenas NIRF, CCIR e INCRA". Os dois furos que produziram essa leitura:

1. a Conferência não distinguia "aceito" de "gravado" — nenhuma linha admitia
   ter pousado, e nenhuma admitia não ter;
2. o dossiê do caso lia as colunas cruas de `Property` (que a consolidação
   nunca grava) e expunha só quatro campos da matrícula.

Os testes abaixo fixam os dois — e, principalmente, fixam a ASSIMETRIA: o que
pousou diz que pousou, o que não pousou continua dizendo que não.
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _st(tenant_id, process_id, fname, value, *, entity, target, hint=None, source="matricula"):
    return ExtractedFieldStaging(
        tenant_id=tenant_id, process_id=process_id, source_doc_type=source,
        field_name=fname, field_value={"value": value},
        status=ExtractedFieldStatus.consistente,
        target_entity=entity, target_field=target, matricula_hint=hint,
        created_by_agent="extrator",
    )


def _setup(db_session, email):
    tenant = Tenant(name="Gravado Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultora", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Leonardo", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Lote 1BC", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()

    rows = [
        # Campos que PODEM pousar — os mesmos do caso real.
        _st(tenant.id, proc.id, "numero_matricula", "6.776", entity="matricula", target="numero_matricula", hint="6.776"),
        _st(tenant.id, proc.id, "cartorio", "CRI de São João d'Aliança", entity="matricula", target="cartorio", hint="6.776"),
        _st(tenant.id, proc.id, "area_registrada_ha", "349,9022", entity="matricula", target="area_ha", hint="6.776"),
        _st(tenant.id, proc.id, "denominacao", "Fazenda São Jorge Lote 01-C", entity="matricula", target="denominacao_imovel", hint="6.776"),
        _st(tenant.id, proc.id, "nirf", "6.907.469-0", entity="matricula", target="nirf_cib", hint="6.776"),
        _st(tenant.id, proc.id, "ccir", "65077345244", entity="matricula", target="numero_ccir", hint="6.776", source="ccir"),
        _st(tenant.id, proc.id, "codigo_incra", "951.048.549.371-0", entity="matricula", target="codigo_incra_sncr", hint="6.776", source="ccir"),
        # Campo aceito que NÃO tem destino — o contraexemplo que mantém o selo
        # honesto (recusa declarada: o protocolo identifica o RAT, não o imóvel).
        _st(tenant.id, proc.id, "rat_protocolo", "GO-2024-99887", entity="imovel", target="rat_protocolo", source="rat"),
    ]
    db_session.add_all(rows)
    db_session.flush()
    return tenant, proc, prop, {r.target_field: r.id for r in rows}


def test_gesto_completo_consolidar_marca_o_que_pousou_e_so_o_que_pousou(
    client: TestClient, db_session
):
    """Aceitar → gravar → a linha que pousou diz `gravado`; a recusada não."""
    _tenant, proc, _prop, ids = _setup(db_session, "gravado@example.com")
    db_session.commit()
    h = _login(client, "gravado@example.com")
    base = f"/api/v1/processes/{proc.id}"

    # 1) aceitar NÃO é gravar — nenhuma linha pousou ainda.
    assert client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h).status_code == 200
    antes = client.get(f"{base}/staging-fields", headers=h).json()
    assert antes, "staging vazio — fixture não subiu"
    assert all(f["gravado"] is False for f in antes)
    assert all(f["status"] == "aceito" for f in antes)

    # 2) o gesto.
    r = client.post(f"{base}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["campos_gravados"] > 0

    # 3) a assimetria: o que pousou admite, o que não pousou continua negando.
    depois = {f["target_field"]: f for f in client.get(f"{base}/staging-fields", headers=h).json()}
    pousaram = ["cartorio", "area_ha", "denominacao_imovel", "nirf_cib",
                "numero_ccir", "codigo_incra_sncr", "numero_matricula"]
    for campo in pousaram:
        assert depois[campo]["gravado"] is True, f"{campo} gravou na base e a tela não diz"
        assert depois[campo]["gravado_em"] is not None
    # Recusa declarada: aceito, sem destino — e a linha NÃO pode dizer "gravado".
    assert depois["rat_protocolo"]["gravado"] is False
    assert depois["rat_protocolo"]["sem_casa"] is True

    # 4) idempotência: consolidar de novo não desmarca o que já está na base.
    # (`_write_entity` devolve "reafirmado", não "recusado" — era esse colapso
    # que faria o selo piscar a cada clique repetido.)
    assert client.post(f"{base}/consolidar", headers=h).status_code == 200
    de_novo = {f["target_field"]: f for f in client.get(f"{base}/staging-fields", headers=h).json()}
    for campo in pousaram:
        assert de_novo[campo]["gravado"] is True, f"{campo} perdeu o selo ao reconsolidar"


def test_reabrir_a_decisao_apaga_o_selo_de_gravado(client: TestClient, db_session):
    """Carimbo não sobrevive à decisão que o invalidou."""
    _tenant, proc, _prop, ids = _setup(db_session, "reabrir@example.com")
    db_session.commit()
    h = _login(client, "reabrir@example.com")
    base = f"/api/v1/processes/{proc.id}"

    client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)
    client.post(f"{base}/consolidar", headers=h)
    campo_id = ids["cartorio"]

    atual = {f["id"]: f for f in client.get(f"{base}/staging-fields", headers=h).json()}
    assert atual[campo_id]["gravado"] is True

    r = client.post(f"{base}/staging-fields/{campo_id}/decidir", headers=h, json={"acao": "reabrir"})
    assert r.status_code == 200, r.text

    depois = {f["id"]: f for f in client.get(f"{base}/staging-fields", headers=h).json()}
    assert depois[campo_id]["status"] == "pendente"
    assert depois[campo_id]["gravado"] is False


def test_dossie_do_caso_mostra_o_que_a_consolidacao_gravou(client: TestClient, db_session):
    """A outra metade do 290cf3c: o CASO também herda das matrículas.

    Antes deste PR, com quatro matrículas consolidadas, a aba Dados exibia
    "Matrícula —, CCIR —, NIRF —, Área —" porque lia `Property.registry_number`
    /`.ccir`/`.nirf`/`.total_area_ha`, colunas que a consolidação nunca grava.
    """
    _tenant, proc, _prop, _ids = _setup(db_session, "dossie@example.com")
    db_session.commit()
    h = _login(client, "dossie@example.com")
    base = f"/api/v1/processes/{proc.id}"

    client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)
    client.post(f"{base}/consolidar", headers=h)

    r = client.get(f"{base}/dossier", headers=h)
    assert r.status_code == 200, r.text
    prop_data = r.json()["property"]

    # Derivado das matrículas — a coluna crua continua vazia, e deve continuar.
    assert prop_data["registry_number"] == "6.776"
    assert prop_data["ccir"] == "65077345244"
    assert prop_data["nirf"] == "6.907.469-0"
    assert prop_data["codigo_incra_sncr"] == "951.048.549.371-0"
    assert prop_data["cartorio"] == "CRI de São João d'Aliança"
    assert prop_data["total_area_ha"] == 349.9022

    # E a matrícula expõe o que estava gravado e não tinha por onde chegar à
    # tela — a correção literal do "gravou apenas três".
    mat = prop_data["matriculas"][0]
    assert mat["cartorio"] == "CRI de São João d'Aliança"
    assert mat["denominacao_imovel"] == "Fazenda São Jorge Lote 01-C"
    assert mat["codigo_incra_sncr"] == "951.048.549.371-0"
    assert mat["nirf_cib"] == "6.907.469-0"
    assert mat["numero_ccir"] == "65077345244"


def test_imovel_com_duas_matriculas_mostra_as_duas_nunca_escolhe(client: TestClient, db_session):
    """Regra de domínio da Isis (02/08): o imóvel é a JUNÇÃO das matrículas.

    Com duas matrículas discordando, o cabeçalho do caso mostra os dois valores
    lado a lado — nunca escolhe uma nem soma num número que não é de ninguém.
    """
    tenant, proc, _prop, _ids = _setup(db_session, "duas@example.com")
    db_session.add_all([
        _st(tenant.id, proc.id, "numero_matricula", "2.923", entity="matricula", target="numero_matricula", hint="2.923"),
        _st(tenant.id, proc.id, "nirf", "6.442.022-1", entity="matricula", target="nirf_cib", hint="2.923"),
        _st(tenant.id, proc.id, "area_registrada_ha", "660,6561", entity="matricula", target="area_ha", hint="2.923"),
    ])
    db_session.commit()
    h = _login(client, "duas@example.com")
    base = f"/api/v1/processes/{proc.id}"

    client.post(f"{base}/staging-fields/aceitar-consistentes", headers=h)
    client.post(f"{base}/consolidar", headers=h)

    prop_data = client.get(f"{base}/dossier", headers=h).json()["property"]

    # A ORDEM entre as matrículas não é contrato (a agregação percorre a relação,
    # que não declara `order_by`); o que é contrato é aparecerem as DUAS, lado a
    # lado, sem que nenhuma suma. Fixar a ordem aqui seria testar um acidente.
    def partes(valor: str) -> set[str]:
        return {p.strip() for p in valor.split("|")}

    assert partes(prop_data["registry_number"]) == {"2.923", "6.776"}
    assert partes(prop_data["nirf"]) == {"6.442.022-1", "6.907.469-0"}
    assert partes(prop_data["area_ha_por_matricula"]) == {"660,6561", "349,9022"}
    # A soma continua existindo (dimensiona porte/exigência) e continua sendo
    # derivada — o que muda é que agora se sabe de quem é cada parcela.
    assert prop_data["total_area_ha"] == 1010.5583
