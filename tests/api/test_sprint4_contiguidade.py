"""Sprint 4 — granularidade matrícula×imóvel (Ficha 07 §9) + integridade.

Cobre as decisões travadas do sprint:
- `matriculas_contiguas` tri-state: declarar grava selo human_validated + audit;
- soma derivada ANOTADA (nunca suprimida) no Hub quando False/NULL multi-matrícula;
- lacunas: área considera soma derivada (fim do falso positivo) e contiguidade
  não declarada é informativa (NUNCA trava);
- re-home mínimo: PATCH matrícula→outro imóvel do mesmo tenant, auditado;
- coerência matriz×consolidação: conflito de docs distintos volta ao consultor;
- guard fantasma: hint de sigef/outro não CRIA matrícula.
"""

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.matricula import Matricula
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(db_session, email, *, matriculas=2):
    tenant = Tenant(name=f"T-{email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge")
    db_session.add(prop)
    db_session.flush()
    areas = [660.6561, 349.9022, 100.0]
    mats = []
    for i in range(matriculas):
        m = Matricula(tenant_id=tenant.id, property_id=prop.id,
                      numero_matricula=str(4698 + i), area_ha=areas[i % len(areas)])
        db_session.add(m)
        mats.append(m)
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso S4", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, cli, prop, mats


def _st(tenant_id, process_id, source, fname, value, *, entity, target, hint=None,
        document_id=None, status=ExtractedFieldStatus.aceito):
    decided = {"value": value} if status == ExtractedFieldStatus.aceito else None
    return ExtractedFieldStaging(
        tenant_id=tenant_id, process_id=process_id, source_doc_type=source,
        field_name=fname, field_value={"value": value}, status=status,
        decided_value=decided, target_entity=entity, target_field=target,
        matricula_hint=hint, document_id=document_id, created_by_agent="extrator",
    )


class TestDeclararContiguidade:
    def test_patch_grava_selo_e_audita(self, client, db_session):
        tenant, proc, cli, prop, _ = _setup(db_session, "s4a@example.com")
        db_session.commit()
        h = _login(client, "s4a@example.com")

        r = client.patch(f"/api/v1/properties/{prop.id}", headers=h,
                         json={"matriculas_contiguas": False})
        assert r.status_code == 200, r.text
        assert r.json()["matriculas_contiguas"] is False

        db_session.refresh(prop)
        assert prop.matriculas_contiguas is False
        assert prop.field_sources["matriculas_contiguas"] == "human_validated"

        logs = db_session.query(AuditLog).filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.action == "declarar_contiguidade").all()
        assert len(logs) == 1
        assert logs[0].entity_id == prop.id

    def test_patch_sem_o_campo_nao_toca_selo(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4b@example.com")
        db_session.commit()
        h = _login(client, "s4b@example.com")
        r = client.patch(f"/api/v1/properties/{prop.id}", headers=h, json={"biome": "Cerrado"})
        assert r.status_code == 200
        db_session.refresh(prop)
        assert "matriculas_contiguas" not in (prop.field_sources or {})


class TestSomaAnotada:
    def test_hub_header_nota_quando_nao_declarado(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4c@example.com")
        db_session.commit()
        h = _login(client, "s4c@example.com")
        r = client.get(f"/api/v1/properties/{prop.id}/summary", headers=h)
        assert r.status_code == 200, r.text
        header = r.json()["header"]
        assert header["matriculas_count"] == 2
        assert header["matriculas_contiguas"] is None
        assert header["total_area_ha"] == 1010.5583      # soma derivada (fallback)
        assert header["area_total_nota"]                  # anotada, nunca suprimida
        assert "não declaradas contíguas" in header["area_total_nota"]

    def test_hub_header_sem_nota_quando_contiguas(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4d@example.com")
        prop.matriculas_contiguas = True
        db_session.commit()
        h = _login(client, "s4d@example.com")
        header = client.get(f"/api/v1/properties/{prop.id}/summary", headers=h).json()["header"]
        assert header["matriculas_contiguas"] is True
        assert header["area_total_nota"] is None

    def test_dossier_areas_com_nota_quando_negada(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4e@example.com")
        prop.matriculas_contiguas = False
        db_session.commit()
        h = _login(client, "s4e@example.com")
        r = client.get(f"/api/v1/processes/{proc.id}/dossier", headers=h)
        assert r.status_code == 200, r.text
        prop_data = r.json()["property"]
        assert prop_data["matriculas_contiguas"] is False
        assert prop_data["areas"]["area_total_matriculas_ha"] == 1010.5583
        assert "NÃO contíguas" in prop_data["areas"]["area_total_nota"]

    def test_uma_matricula_nunca_tem_nota(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4f@example.com", matriculas=1)
        db_session.commit()
        h = _login(client, "s4f@example.com")
        header = client.get(f"/api/v1/properties/{prop.id}/summary", headers=h).json()["header"]
        assert header["area_total_nota"] is None


class TestLacunas:
    def _codes(self, dossier_json):
        return {i["code"] for i in dossier_json["inconsistencies"]}

    def test_missing_area_considera_soma_derivada(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4g@example.com")
        db_session.commit()
        h = _login(client, "s4g@example.com")
        codes = self._codes(client.get(f"/api/v1/processes/{proc.id}/dossier", headers=h).json())
        assert "MISSING_AREA" not in codes   # antes: falso positivo pós-consolidação

    def test_lacuna_contiguidade_nao_declarada_multi_matricula(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4h@example.com")
        db_session.commit()
        h = _login(client, "s4h@example.com")
        d = client.get(f"/api/v1/processes/{proc.id}/dossier", headers=h).json()
        found = [i for i in d["inconsistencies"] if i["code"] == "CONTIGUIDADE_NAO_DECLARADA"]
        assert len(found) == 1
        assert found[0]["severity"] == "info"   # informativa — NUNCA trava

    def test_aviso_orientando_separacao_quando_negada(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4i@example.com")
        prop.matriculas_contiguas = False
        db_session.commit()
        h = _login(client, "s4i@example.com")
        d = client.get(f"/api/v1/processes/{proc.id}/dossier", headers=h).json()
        found = [i for i in d["inconsistencies"] if i["code"] == "MATRICULAS_NAO_CONTIGUAS"]
        assert len(found) == 1
        assert found[0]["severity"] == "warning"
        assert "mova" in found[0]["description"]

    def test_sem_lacuna_com_uma_matricula(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4j@example.com", matriculas=1)
        db_session.commit()
        h = _login(client, "s4j@example.com")
        codes = self._codes(client.get(f"/api/v1/processes/{proc.id}/dossier", headers=h).json())
        assert "CONTIGUIDADE_NAO_DECLARADA" not in codes
        assert "MATRICULAS_NAO_CONTIGUAS" not in codes

    def test_can_advance_gap_informativo(self, client, db_session):
        _, proc, cli, prop, _ = _setup(db_session, "s4k@example.com")
        db_session.commit()
        h = _login(client, "s4k@example.com")
        r = client.get(f"/api/v1/processes/{proc.id}/can-advance", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        gaps = body["gaps"]
        assert any("Contiguidade" in g for g in gaps)
        # soma derivada conta como área conhecida → gap de área não dispara
        assert not any("Área total" in g for g in gaps)
        # matrículas na base → gap de matrícula não dispara
        assert not any(g.startswith("Matrícula do imóvel") for g in gaps)
        # lacunas NUNCA travam: contiguidade não aparece nos blockers
        assert not any("ontiguidade" in b for b in body["blockers"])


class TestReHome:
    def test_move_matricula_para_outro_imovel(self, client, db_session):
        tenant, proc, cli, prop, mats = _setup(db_session, "s4l@example.com")
        prop2 = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Shangri-lá")
        db_session.add(prop2)
        db_session.commit()
        h = _login(client, "s4l@example.com")

        r = client.patch(f"/api/v1/properties/{prop.id}/matriculas/{mats[0].id}",
                         headers=h, json={"property_id": prop2.id})
        assert r.status_code == 200, r.text
        assert r.json()["property_id"] == prop2.id
        db_session.refresh(mats[0])
        assert mats[0].property_id == prop2.id

        logs = db_session.query(AuditLog).filter(
            AuditLog.tenant_id == tenant.id, AuditLog.action == "matricula_movida").all()
        assert len(logs) == 1

    def test_move_no_op_para_o_mesmo_imovel(self, client, db_session):
        tenant, proc, cli, prop, mats = _setup(db_session, "s4m@example.com")
        db_session.commit()
        h = _login(client, "s4m@example.com")
        r = client.patch(f"/api/v1/properties/{prop.id}/matriculas/{mats[0].id}",
                         headers=h, json={"property_id": prop.id})
        assert r.status_code == 200
        assert db_session.query(AuditLog).filter(
            AuditLog.action == "matricula_movida", AuditLog.tenant_id == tenant.id).count() == 0

    def test_move_matricula_de_outro_imovel_404(self, client, db_session):
        tenant, proc, cli, prop, mats = _setup(db_session, "s4n@example.com")
        prop2 = Property(tenant_id=tenant.id, client_id=cli.id, name="Outra")
        db_session.add(prop2)
        db_session.commit()
        h = _login(client, "s4n@example.com")
        # matrícula não pertence a prop2 (path) → 404
        r = client.patch(f"/api/v1/properties/{prop2.id}/matriculas/{mats[0].id}",
                         headers=h, json={"property_id": prop.id})
        assert r.status_code == 404


class TestIntegridadeConsolidacao:
    def test_conflito_de_docs_distintos_devolvido_ao_consultor(self, client, db_session):
        """ADR-062 (fonte única registral) supera o cenário original deste teste
        (2 CCIRs conflitantes em `denominacao_imovel`, caso 13/ADR-023): CCIR
        não escreve mais esse campo — nenhum dos dois chega a `_group_conflict_
        values` para desempatar. Nada vira `Acao` de consolidação (o achado
        agora nasceria da matriz de inconsistências, canal separado); as duas
        linhas ficam em `ignorados`, nada gravado."""
        tenant, proc, cli, prop, _ = _setup(db_session, "s4o@example.com", matriculas=0)
        db_session.add_all([
            _st(tenant.id, proc.id, "ccir", "denominacao", "Fazenda Shangri-lá ( Parte 2)",
                entity="matricula", target="denominacao_imovel", hint="2923"),
            _st(tenant.id, proc.id, "ccir", "denominacao", "Fazenda Sao Jorge Lote 1 B",
                entity="matricula", target="denominacao_imovel", hint="2923"),
        ])
        db_session.commit()
        h = _login(client, "s4o@example.com")
        r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["divergencias_devolvidas"] == []
        assert res["acoes_criadas"] == 0
        assert len([i for i in res["ignorados"] if "denominacao_imovel" in i]) == 2

        # nada gravado; staging fica como estava (não vira divergente_transcricao —
        # a fonte simplesmente não compete, não há decisão a devolver)
        mat = db_session.query(Matricula).filter(
            Matricula.property_id == prop.id, Matricula.numero_matricula == "2923").first()
        assert mat is None or mat.denominacao_imovel is None

    def test_conflito_entre_duas_certidoes_ainda_e_devolvido_ao_consultor(self, client, db_session):
        """O que sobra para o guard de conflito resolver em `matricula` pós-
        ADR-062: certidão × certidão (re-upload, retificação) — jurídico de
        verdade, não ruído de fonte. `area_ha` não está entre os campos
        redirecionados para a matriz (item 4 do ADR — só denominação e
        INCRA/SNCR têm emissor de achado ligado hoje), então continua virando
        `Acao`, como sempre."""
        tenant, proc, cli, prop, _ = _setup(db_session, "s4o2@example.com", matriculas=0)
        db_session.add_all([
            _st(tenant.id, proc.id, "matricula", "area", "349,9022",
                entity="matricula", target="area_ha", hint="2923"),
            _st(tenant.id, proc.id, "matricula", "area", "352,0000",
                entity="matricula", target="area_ha", hint="2923"),
        ])
        db_session.commit()
        h = _login(client, "s4o2@example.com")
        r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
        assert r.status_code == 200, r.text
        res = r.json()
        assert len(res["divergencias_devolvidas"]) == 1
        assert res["divergencias_devolvidas"][0]["field"] == "area_ha"
        assert res["acoes_criadas"] == 1

    def test_conflito_de_denominacao_entre_certidoes_e_devolvido_mas_nao_vira_acao(self, client, db_session):
        """Mesmo entre DUAS certidões (fonte igual, `_group_conflict_values`
        segue devolvendo normalmente), `denominacao_imovel` é um dos 2 campos
        já redirecionados para a matriz (ADR-062, item 4) — a Ação não nasce
        mais aqui, redundante seria duplicar o achado. O `Acao`-generator não
        distingue fonte, só campo: quem decide se compete é o filtro de
        fonte única na consolidação (que aqui deixou o conflito acontecer,
        por serem duas certidões)."""
        tenant, proc, cli, prop, _ = _setup(db_session, "s4o3@example.com", matriculas=0)
        db_session.add_all([
            _st(tenant.id, proc.id, "matricula", "denominacao", "Fazenda Shangri-lá ( Parte 2)",
                entity="matricula", target="denominacao_imovel", hint="2923"),
            _st(tenant.id, proc.id, "matricula", "denominacao", "Fazenda Sao Jorge Lote 1 B",
                entity="matricula", target="denominacao_imovel", hint="2923"),
        ])
        db_session.commit()
        h = _login(client, "s4o3@example.com")
        r = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h)
        assert r.status_code == 200, r.text
        res = r.json()
        assert len(res["divergencias_devolvidas"]) == 1
        assert res["divergencias_devolvidas"][0]["field"] == "denominacao_imovel"
        assert res["acoes_criadas"] == 0

        mat = db_session.query(Matricula).filter(
            Matricula.property_id == prop.id, Matricula.numero_matricula == "2923").first()
        assert mat is None or mat.denominacao_imovel is None
        rows = db_session.query(ExtractedFieldStaging).filter(
            ExtractedFieldStaging.process_id == proc.id).all()
        assert all(r_.status == ExtractedFieldStatus.divergente_transcricao for r_ in rows)

    def test_edicao_do_consultor_resolve_conflito(self, client, db_session):
        """Edição explícita (decided_value ≠ extraído) é decisão humana — grava."""
        tenant, proc, cli, prop, _ = _setup(db_session, "s4p@example.com", matriculas=0)
        r1 = _st(tenant.id, proc.id, "ccir", "denominacao", "Fazenda Shangri-lá",
                 entity="matricula", target="denominacao_imovel", hint="2923")
        r1.decided_value = {"value": "Fazenda São Jorge Lote 1B"}   # editado
        r2 = _st(tenant.id, proc.id, "ccir", "denominacao", "Fazenda Sao Jorge Lote 1 B",
                 entity="matricula", target="denominacao_imovel", hint="2923")
        db_session.add_all([r1, r2])
        db_session.commit()
        h = _login(client, "s4p@example.com")
        res = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h).json()
        assert res["divergencias_devolvidas"] == []
        mat = db_session.query(Matricula).filter(
            Matricula.property_id == prop.id, Matricula.numero_matricula == "2923").first()
        assert mat is not None
        assert mat.denominacao_imovel == "Fazenda São Jorge Lote 1B"

    def test_guard_fantasma_sigef_nao_cria_matricula(self, client, db_session):
        """ADR-062 endureceu o guard fantasma da Sprint 4 (que já vetava só
        `sigef` para criação): agora SIGEF nem chega a competir pela ESCRITA
        do campo — a recusa é fonte única registral, não mais só "não cria"."""
        tenant, proc, cli, prop, _ = _setup(db_session, "s4q@example.com", matriculas=0)
        db_session.add(_st(tenant.id, proc.id, "sigef", "area_georreferenciada_ha", "3,1256",
                           entity="matricula", target="area_ha", hint="492262"))
        db_session.commit()
        h = _login(client, "s4q@example.com")
        res = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h).json()
        assert res["matriculas_criadas"] == 0
        assert any("certidão de matrícula" in ig for ig in res["ignorados"])
        assert db_session.query(Matricula).filter(
            Matricula.numero_matricula == "492262").count() == 0

    def test_sigef_nao_atualiza_mais_matricula_existente(self, client, db_session):
        """ADR-062 supera o comportamento antigo deste teste ("sigef não CRIA,
        mas atualiza matrícula que já existe"): geo_certificação é campo
        registral (item 1) — SIGEF não escreve nem quando a matrícula já
        existe. Matrícula existir deixou de bastar; só a certidão escreve."""
        tenant, proc, cli, prop, mats = _setup(db_session, "s4r@example.com", matriculas=1)
        valor_original = mats[0].geo_certificacao_codigo
        db_session.add(_st(tenant.id, proc.id, "sigef", "codigo_certificacao", "ABC-123",
                           entity="matricula", target="geo_certificacao_codigo",
                           hint=mats[0].numero_matricula))
        db_session.commit()
        h = _login(client, "s4r@example.com")
        res = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h).json()
        assert res["matriculas_criadas"] == 0
        assert res["campos_gravados"] == 0
        assert any("certidão de matrícula" in ig for ig in res["ignorados"])
        db_session.refresh(mats[0])
        assert mats[0].geo_certificacao_codigo == valor_original

    def test_certidao_atualiza_matricula_existente(self, client, db_session):
        """A própria certidão de matrícula (fonte autorizada, ADR-062) segue
        atualizando um registro que já existe — o guard fantasma nunca vetou
        a fonte que tem permissão de escrever."""
        tenant, proc, cli, prop, mats = _setup(db_session, "s4r2@example.com", matriculas=1)
        db_session.add(_st(tenant.id, proc.id, "matricula", "codigo_certificacao", "ABC-123",
                           entity="matricula", target="geo_certificacao_codigo",
                           hint=mats[0].numero_matricula))
        db_session.commit()
        h = _login(client, "s4r2@example.com")
        res = client.post(f"/api/v1/processes/{proc.id}/consolidar", headers=h).json()
        assert res["matriculas_criadas"] == 0
        assert res["campos_gravados"] == 1
        db_session.refresh(mats[0])
        assert mats[0].geo_certificacao_codigo == "ABC-123"
