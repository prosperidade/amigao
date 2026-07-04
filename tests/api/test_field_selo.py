"""Sprint 3 — Selo de 3 estados + automatismo de ação (Ficha 07 §3.4/§9).

Cobre as decisões travadas do sprint:
- oscilação pendente→validado→pendente NÃO duplica (dedupe por destino);
- ação dispensada NÃO recria (sistema não desfaz triagem humana);
- Hub grava selo mas NÃO dispara; endpoint de processo dispara;
- IDOR: entidade de outro tenant/processo → 404;
- selo perene no field_sources da entidade.
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.acao import Acao, AcaoOrigem, AcaoTipoTriagem
from app.models.client import Client, ClientStatus, ClientType
from app.models.matricula import Matricula
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(db_session, email="selo@example.com"):
    tenant = Tenant(name="Selo Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente Selo", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Selo",
                    car_code="GO-123-ABC")
    db_session.add(prop)
    db_session.flush()
    mat = Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="4.698",
                    geo_certificacao_codigo="SIGEF-XYZ", nirf_cib="1234567-8")
    db_session.add(mat)
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso Selo", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, cli, prop, mat


def _acoes_oficializacao(db_session, tenant_id, process_id):
    return (
        db_session.query(Acao)
        .filter(
            Acao.tenant_id == tenant_id,
            Acao.process_id == process_id,
            Acao.origem == AcaoOrigem.oficializacao,
        )
        .all()
    )


class TestFieldSeloEndpoint:
    def test_pendente_oficializacao_cria_acao_por_campo(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo1@example.com")
        db_session.commit()
        h = _login(client, "selo1@example.com")

        r = client.post(f"/api/v1/processes/{proc.id}/field-selo", headers=h, json={
            "entity": "matricula", "entity_id": mat.id,
            "field": "geo_certificacao_codigo", "selo": "pendente_oficializacao",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["acao_criada"] is True
        assert body["field_sources"]["geo_certificacao_codigo"] == "pendente_oficializacao"

        acoes = _acoes_oficializacao(db_session, tenant.id, proc.id)
        assert len(acoes) == 1
        assert acoes[0].titulo == "Atualização de arquivos oficiais — Nº SIGEF (certificação)"
        assert acoes[0].tipo_triagem == AcaoTipoTriagem.pendente

        # selo perene: gravado na ENTIDADE
        db_session.refresh(mat)
        assert mat.field_sources["geo_certificacao_codigo"] == "pendente_oficializacao"

        # 1 ação POR CAMPO: outro campo da mesma matrícula → segunda ação
        r = client.post(f"/api/v1/processes/{proc.id}/field-selo", headers=h, json={
            "entity": "matricula", "entity_id": mat.id,
            "field": "nirf_cib", "selo": "pendente_oficializacao",
        })
        assert r.status_code == 200
        assert r.json()["acao_criada"] is True
        assert len(_acoes_oficializacao(db_session, tenant.id, proc.id)) == 2

    def test_oscilacao_nao_duplica(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo2@example.com")
        db_session.commit()
        h = _login(client, "selo2@example.com")
        url = f"/api/v1/processes/{proc.id}/field-selo"
        payload = {"entity": "imovel", "entity_id": prop.id, "field": "car_code"}

        r = client.post(url, headers=h, json={**payload, "selo": "pendente_oficializacao"})
        assert r.status_code == 200 and r.json()["acao_criada"] is True

        # volta a VALIDADO: a ação FICA (consultor dispensa/conclui)
        r = client.post(url, headers=h, json={**payload, "selo": "human_validated"})
        assert r.status_code == 200 and r.json()["acao_criada"] is False
        db_session.refresh(prop)
        assert prop.field_sources["car_code"] == "human_validated"
        assert len(_acoes_oficializacao(db_session, tenant.id, proc.id)) == 1

        # pendente de novo: dedupe por DESTINO bloqueia — não duplica
        r = client.post(url, headers=h, json={**payload, "selo": "pendente_oficializacao"})
        assert r.status_code == 200 and r.json()["acao_criada"] is False
        assert len(_acoes_oficializacao(db_session, tenant.id, proc.id)) == 1

    def test_dispensada_nao_recria(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo3@example.com")
        db_session.commit()
        h = _login(client, "selo3@example.com")
        url = f"/api/v1/processes/{proc.id}/field-selo"
        payload = {"entity": "matricula", "entity_id": mat.id, "field": "nirf_cib"}

        r = client.post(url, headers=h, json={**payload, "selo": "pendente_oficializacao"})
        assert r.status_code == 200 and r.json()["acao_criada"] is True
        acao = _acoes_oficializacao(db_session, tenant.id, proc.id)[0]

        # consultor dispensa (triagem humana)
        acao.tipo_triagem = AcaoTipoTriagem.dispensada
        db_session.commit()

        # re-selar não recria: a linha dispensada segura a dedupe_key
        r = client.post(url, headers=h, json={**payload, "selo": "human_validated"})
        assert r.status_code == 200
        r = client.post(url, headers=h, json={**payload, "selo": "pendente_oficializacao"})
        assert r.status_code == 200 and r.json()["acao_criada"] is False
        acoes = _acoes_oficializacao(db_session, tenant.id, proc.id)
        assert len(acoes) == 1
        assert acoes[0].tipo_triagem == AcaoTipoTriagem.dispensada

    def test_nao_validado_remove_marca(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo4@example.com")
        db_session.commit()
        h = _login(client, "selo4@example.com")
        url = f"/api/v1/processes/{proc.id}/field-selo"
        payload = {"entity": "imovel", "entity_id": prop.id, "field": "car_code"}

        client.post(url, headers=h, json={**payload, "selo": "human_validated"})
        r = client.post(url, headers=h, json={**payload, "selo": "nao_validado"})
        assert r.status_code == 200
        assert "car_code" not in r.json()["field_sources"]
        # não-validado não gera ação
        assert len(_acoes_oficializacao(db_session, tenant.id, proc.id)) == 0

    def test_selo_em_campo_do_cliente(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo11@example.com")
        db_session.commit()
        h = _login(client, "selo11@example.com")

        r = client.post(f"/api/v1/processes/{proc.id}/field-selo", headers=h, json={
            "entity": "cliente", "entity_id": cli.id,
            "field": "cpf_cnpj", "selo": "pendente_oficializacao",
        })
        assert r.status_code == 200, r.text
        assert r.json()["acao_criada"] is True
        db_session.refresh(cli)
        assert cli.field_sources["cpf_cnpj"] == "pendente_oficializacao"
        acoes = _acoes_oficializacao(db_session, tenant.id, proc.id)
        assert acoes[0].titulo == "Atualização de arquivos oficiais — CPF/CNPJ"

    def test_processo_inexistente_404(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo12@example.com")
        db_session.commit()
        h = _login(client, "selo12@example.com")
        r = client.post("/api/v1/processes/999999/field-selo", headers=h, json={
            "entity": "imovel", "entity_id": prop.id,
            "field": "car_code", "selo": "human_validated",
        })
        assert r.status_code == 404

    def test_matricula_em_processo_sem_imovel_404(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo13@example.com")
        proc2 = Process(tenant_id=tenant.id, client_id=cli.id, property_id=None,
                        title="Sem imóvel", process_type="prad", status=ProcessStatus.triagem)
        db_session.add(proc2)
        db_session.commit()
        h = _login(client, "selo13@example.com")
        r = client.post(f"/api/v1/processes/{proc2.id}/field-selo", headers=h, json={
            "entity": "matricula", "entity_id": mat.id,
            "field": "nirf_cib", "selo": "human_validated",
        })
        assert r.status_code == 404

    def test_campo_fora_da_allowlist_422(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo5@example.com")
        db_session.commit()
        h = _login(client, "selo5@example.com")
        r = client.post(f"/api/v1/processes/{proc.id}/field-selo", headers=h, json={
            "entity": "imovel", "entity_id": prop.id,
            "field": "hashed_password", "selo": "human_validated",
        })
        assert r.status_code == 422


class TestFieldSeloIDOR:
    def test_matricula_de_outro_imovel_404(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo6@example.com")
        # outro imóvel do MESMO tenant, não ligado ao processo
        prop2 = Property(tenant_id=tenant.id, client_id=cli.id, name="Outra Fazenda")
        db_session.add(prop2)
        db_session.flush()
        mat2 = Matricula(tenant_id=tenant.id, property_id=prop2.id, numero_matricula="9.999")
        db_session.add(mat2)
        db_session.commit()
        h = _login(client, "selo6@example.com")

        r = client.post(f"/api/v1/processes/{proc.id}/field-selo", headers=h, json={
            "entity": "matricula", "entity_id": mat2.id,
            "field": "nirf_cib", "selo": "pendente_oficializacao",
        })
        assert r.status_code == 404
        assert len(_acoes_oficializacao(db_session, tenant.id, proc.id)) == 0

    def test_entidade_de_outro_tenant_404(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo7@example.com")
        outro = Tenant(name="Outro Tenant")
        db_session.add(outro)
        db_session.flush()
        cli2 = Client(tenant_id=outro.id, full_name="Alheio", email="alheio@example.com",
                      client_type=ClientType.pf, status=ClientStatus.active)
        db_session.add(cli2)
        db_session.flush()
        prop2 = Property(tenant_id=outro.id, client_id=cli2.id, name="Fazenda Alheia")
        db_session.add(prop2)
        db_session.flush()
        mat2 = Matricula(tenant_id=outro.id, property_id=prop2.id, numero_matricula="777")
        db_session.add(mat2)
        db_session.commit()
        h = _login(client, "selo7@example.com")

        r = client.post(f"/api/v1/processes/{proc.id}/field-selo", headers=h, json={
            "entity": "matricula", "entity_id": mat2.id,
            "field": "nirf_cib", "selo": "pendente_oficializacao",
        })
        assert r.status_code == 404

    def test_imovel_nao_ligado_ao_processo_404(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo8@example.com")
        prop2 = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Solta")
        db_session.add(prop2)
        db_session.commit()
        h = _login(client, "selo8@example.com")

        r = client.post(f"/api/v1/processes/{proc.id}/field-selo", headers=h, json={
            "entity": "imovel", "entity_id": prop2.id,
            "field": "car_code", "selo": "human_validated",
        })
        assert r.status_code == 404


class TestHubNaoDispara:
    def test_hub_grava_selo_sem_automatismo(self, client, db_session):
        """Decisão 3: o validate-fields do Hub grava o selo mas NUNCA cria ação."""
        tenant, proc, cli, prop, mat = _setup(db_session, "selo9@example.com")
        db_session.commit()
        h = _login(client, "selo9@example.com")

        r = client.post(f"/api/v1/properties/{prop.id}/validate-fields", headers=h, json={
            "fields": ["car_code"], "source": "pendente_oficializacao",
        })
        assert r.status_code == 200, r.text
        assert r.json()["field_sources"]["car_code"] == "pendente_oficializacao"

        # nenhuma ação nasceu — disparo é exclusivo do endpoint de processo
        total = db_session.query(Acao).filter(Acao.tenant_id == tenant.id).count()
        assert total == 0


class TestDossierExtensao:
    def test_dossier_expoe_selos_campos_chave_e_areas(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo10@example.com")
        prop.area_grafica_ha = 1010.71
        mat.area_ha = 660.6561
        db_session.commit()
        h = _login(client, "selo10@example.com")

        r = client.get(f"/api/v1/processes/{proc.id}/dossier", headers=h)
        assert r.status_code == 200, r.text
        p = r.json()["property"]
        assert p["field_sources"] == (prop.field_sources or {})
        mats = p["matriculas"]
        assert len(mats) == 1
        assert mats[0]["geo_certificacao_codigo"] == "SIGEF-XYZ"
        assert mats[0]["nirf_cib"] == "1234567-8"
        assert "codigo_incra_sncr" in mats[0]
        assert "field_sources" in mats[0]
        areas = p["areas"]
        # documental sem fonte → None honesto (a UI mostra "—" com nota)
        assert areas["area_documental_ha"] is None
        assert areas["area_grafica_ha"] == 1010.71
        assert areas["area_total_matriculas_ha"] == 660.6561

    def test_inconsistencies_endpoint(self, client, db_session):
        tenant, proc, cli, prop, mat = _setup(db_session, "selo14@example.com")
        db_session.commit()
        h = _login(client, "selo14@example.com")

        r = client.get(f"/api/v1/processes/{proc.id}/inconsistencies", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["process_id"] == proc.id
        assert body["total"] == len(body["inconsistencies"])
        assert body["total"] == body["errors"] + body["warnings"] + sum(
            1 for i in body["inconsistencies"] if i["severity"] not in ("error", "warning")
        )
