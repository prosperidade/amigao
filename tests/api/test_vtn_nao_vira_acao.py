"""A Ação 49 do caso 16, reproduzida e fechada — pelas duas portas.

Em produção (processo 16, 02/08 15:19) a consolidação criou a Ação id 49,
"Resolver divergência de vtn", para um campo que não está em
``_MATRICULA_FIELDS`` nem existe como coluna em ``matriculas``. Nenhuma escolha
de fonte, nenhuma edição manual, nenhuma leitura de documento faria aquele valor
entrar na base — e mesmo assim ele entrou na lista de trabalho da consultora.

A divergência chega por DUAS portas, e as duas precisam fechar:

* pelo **guard de conflito** da consolidação, que rodava ANTES da allowlist e
  por isso devolvia como divergência um campo que ele já poderia saber que não
  tem destino (foi este o caminho do caso 16: duas linhas de `vtn` de dois ITRs
  com valores diferentes);
* pela **matriz/extrator**, que grava a linha já com status
  ``divergente_transcricao`` sem nunca passar pela consolidação.
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


def _st(tenant_id, process_id, source, fname, value, status, *, entity, target, hint=None):
    decided = {"value": value} if status == ExtractedFieldStatus.aceito else None
    return ExtractedFieldStaging(
        tenant_id=tenant_id, process_id=process_id, source_doc_type=source,
        field_name=fname, field_value={"value": value}, status=status,
        decided_value=decided, target_entity=entity, target_field=target,
        matricula_hint=hint, created_by_agent="extrator",
    )


def _setup(db_session, email):
    tenant = Tenant(name="VTN Tenant")
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
    return tenant, proc, prop


def test_vtn_conflitante_nao_vira_acao_nem_divergencia(client: TestClient, db_session):
    """Porta 1 — o guard de conflito, agora depois da allowlist.

    Dois ITRs trazem VTNs diferentes para a mesma matrícula. Antes: o guard
    rodava primeiro, devolvia as duas linhas a `divergente_transcricao` e a
    consolidação fechava criando "Resolver divergência de vtn". Agora o campo
    sai por `ignorados`, dizendo o motivo — e a lista de trabalho fica limpa.
    """
    from app.models.acao import Acao

    tenant, proc, _prop = _setup(db_session, "vtn@example.com")
    C = ExtractedFieldStatus
    db_session.add_all([
        # Campo real, para a consolidação ter o que gravar (e o teste não passar
        # por vacuidade).
        _st(tenant.id, proc.id, "matricula", "numero_matricula", "2.923", C.aceito, entity="matricula", target="numero_matricula", hint="2.923"),
        _st(tenant.id, proc.id, "matricula", "cartorio", "CRI de Jataí", C.aceito, entity="matricula", target="cartorio", hint="2.923"),
        # O exemplar: dois valores conflitantes num campo sem coluna.
        _st(tenant.id, proc.id, "itr", "vtn", "4.199.942,38", C.aceito, entity="matricula", target="vtn", hint="2.923"),
        _st(tenant.id, proc.id, "itr", "vtn", "3.073.027,19", C.aceito, entity="matricula", target="vtn", hint="2.923"),
    ])
    db_session.commit()
    h = _login(client, "vtn@example.com")
    base = f"/api/v1/processes/{proc.id}"

    r = client.post(f"{base}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    res = r.json()

    # O campo real gravou — o fix não é "parar de consolidar".
    assert res["campos_gravados"] >= 1

    # Nenhuma ação de trabalho impossível.
    titulos = [a.titulo for a in db_session.query(Acao).filter(Acao.process_id == proc.id).all()]
    assert not any("vtn" in t.lower() for t in titulos), titulos

    # E o campo não voltou como divergência: ele não tem onde pousar, ponto.
    devolvidas = [d["field"] for d in res["divergencias_devolvidas"]]
    assert "vtn" not in devolvidas

    # Some visível, não calado: o motivo aparece em `ignorados` (P12).
    assert any("vtn" in i for i in res["ignorados"]), res["ignorados"]


def test_vtn_ja_divergente_do_extrator_tambem_nao_vira_acao(client: TestClient, db_session):
    """Porta 2 — a linha nasce `divergente_transcricao` na matriz.

    Fechar só o guard da consolidação deixaria esta aberta: a matriz grava o
    status direto, e `generate_acoes_from_divergencias` lê por status.
    """
    from app.models.acao import Acao

    tenant, proc, _prop = _setup(db_session, "vtn2@example.com")
    C = ExtractedFieldStatus
    db_session.add_all([
        _st(tenant.id, proc.id, "itr", "vtn", "4.199.942,38", C.divergente_transcricao, entity="matricula", target="vtn", hint="2.923"),
        _st(tenant.id, proc.id, "itr", "vtn", "3.073.027,19", C.divergente_transcricao, entity="matricula", target="vtn", hint="2.923"),
    ])
    db_session.commit()
    h = _login(client, "vtn2@example.com")

    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["acoes_criadas"] == 0
    assert db_session.query(Acao).filter(Acao.process_id == proc.id).count() == 0


def test_divergencia_de_campo_recusado_por_decisao_continua_virando_acao(
    client: TestClient, db_session
):
    """O contraexemplo que impede a correção de virar um novo sumiço.

    `total_area_ha` também não é gravado pela consolidação — mas por DECISÃO
    (a área do imóvel é derivada da soma das matrículas). Divergir entre o que
    o CAR declara e o que as matrículas somam é achado clássico e continua
    sendo trabalho real. Se este teste ficar vermelho, a correção do `vtn`
    passou do ponto e começou a apagar serviço de verdade.
    """
    from app.models.acao import Acao

    tenant, proc, _prop = _setup(db_session, "recusado@example.com")
    C = ExtractedFieldStatus
    db_session.add_all([
        _st(tenant.id, proc.id, "car", "area_declarada_ha", "1.010,7113", C.divergente_transcricao, entity="imovel", target="total_area_ha"),
        _st(tenant.id, proc.id, "matricula", "area_registrada_ha", "660,6561", C.divergente_transcricao, entity="imovel", target="total_area_ha"),
    ])
    db_session.commit()
    h = _login(client, "recusado@example.com")

    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["acoes_criadas"] == 1
    acao = db_session.query(Acao).filter(Acao.process_id == proc.id).one()
    assert "total_area_ha" in acao.titulo
