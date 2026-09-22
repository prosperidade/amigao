"""Serviço geoespacial (ADR-072) — leitura, medição, projeção e confronto.

O retângulo `KMZ_JOBSON` é calibrado no PostGIS para medir ≈2,7250 ha
(ST_Area geodésica), o valor do KMZ real de Jobson (Plano §4.5). Os bytes de
produção (doc 560, processo #25) não foram trazidos para dev — só há acesso
SQL somente-leitura à produção (`supabase-prod-ro`), sem canal de storage; o
polígono aqui é uma construção própria, não o arquivo original. Confrontado
contra a área documental 2,6893 ha reproduz a divergência documentada
(~357 m², ~1,33%).
"""
from __future__ import annotations

import io
import zipfile
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.evidence import EvidenceInvalidation, EvidenceReview, EvidenceVersion
from app.models.geometria import ArquivoGeo, ConfrontoArea, Feicao, Medicao, ProjecaoGeometria
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services import geometria
from app.services.property_audit import DENOMINADOR_REFERENCIA_DOCUMENTAL, GRADE_ATENCAO, RESULTADO_DIVERGENTE

_SEQ = {"n": 0}


def _next():
    _SEQ["n"] += 1
    return _SEQ["n"]


def _kml(body: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        + body + "\n</kml>"
    ).encode("utf-8")


def _kmz(kml_bytes: bytes, member: str = "doc.kml") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member, kml_bytes)
    return buf.getvalue()


# Calibrado (ver PostGIS ST_Area geodésica) para medir 2,72502 ha — a área do
# KMZ de Jobson documentada no Plano §4.5 (2,7250 ha).
KMZ_JOBSON_KML = _kml("""<Document><Placemark><name>Perimetro</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
-49.45,-16.35,0 -49.4515447,-16.35,0 -49.4515447,-16.3514920,0 -49.45,-16.3514920,0 -49.45,-16.35,0
</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Document>""")
KMZ_JOBSON = _kmz(KMZ_JOBSON_KML)

# Bowtie autointersectante — inválido por construção (ST_IsValid = false).
KML_BOWTIE = _kml("""<Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
0,0 10,10 10,0 0,10 0,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document>""")


def _seed(db_session, *, com_property=True):
    n = _next()
    tenant = Tenant(name=f"Geometria {n}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, email=f"geo{n}@example.com", full_name="Consultor",
                hashed_password="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name=f"Cliente {n}", email=f"cli{n}@example.com",
                client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = None
    if com_property:
        prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Jobson")
        db_session.add(prop)
        db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id if prop else None,
                   title="Caso", process_type="car", status=ProcessStatus.triagem, demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, user, prop, proc


def _doc(db_session, tenant, proc, *, filename="poligono.kmz", content_type="application/vnd.google-earth.kmz",
        document_type=None, checksum=None):
    n = _next()
    d = Document(tenant_id=tenant.id, process_id=proc.id, original_file_name=filename, filename=filename,
                content_type=content_type, extension=filename.rsplit(".", 1)[-1],
                storage_key=f"geo-test/{tenant.id}/{n}", ocr_status=OcrStatus.not_required,
                document_type=document_type, checksum_sha256=checksum)
    db_session.add(d)
    db_session.flush()
    return d


def _observacao_area(db_session, tenant, proc, doc, *, predicate, literal, unit="ha", normalized=None, object_id=None):
    """Grava uma EvidenceVersion crua (não via persist_object — sem exigir a
    cadeia de fonte_primaria/premissas; aqui só o consumo por geometria.py
    está em teste)."""
    n = _next()
    content = {
        "id": object_id or f"obs:{doc.id}:1:1:{n:024x}", "kind": "observacao", "version": 1,
        "origin": "extrator", "premises": [{"id": f"document:{doc.id}", "version": 1}],
        "knowledge": {"state": "nao_determinado"}, "limits": [],
        "attributes": {"predicate": predicate, "literal": literal, "unit": unit, "document_id": doc.id,
                       "normalized": normalized},
    }
    row = EvidenceVersion(tenant_id=tenant.id, process_id=proc.id, object_id=content["id"], version=1,
                          kind="observacao", content=content, content_hash=f"hash{n}", source_document_id=doc.id)
    db_session.add(row)
    db_session.flush()
    return row


# ---------------------------------------------------------------------------
# Leitura: sucesso, idempotência, falhas visíveis
# ---------------------------------------------------------------------------

class TestProcessarDocumentoSucesso:
    def test_le_kmz_calcula_area_geodesica_e_projeta_property(self, db_session):
        tenant, _user, prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc)
        arquivo = geometria.processar_documento(db_session, doc, dados=KMZ_JOBSON)
        assert arquivo.estado == "lido"
        assert arquivo.membro_lido == "doc.kml"
        import hashlib
        assert arquivo.sha256_original == hashlib.sha256(KMZ_JOBSON).hexdigest()

        feicoes = db_session.query(Feicao).filter_by(tenant_id=tenant.id, arquivo_geo_id=arquivo.id).all()
        assert len(feicoes) == 1
        assert feicoes[0].valida is True
        assert feicoes[0].tipo == "poligono"

        medicoes = db_session.query(Medicao).filter_by(tenant_id=tenant.id, feicao_id=feicoes[0].id).all()
        assert len(medicoes) == 1
        m = medicoes[0]
        assert m.estado == "determinado"
        assert m.origem_tipo == "feicao_calculada"
        # Geodésica no elipsoide GRS80, não graus² — calibrado para ≈2,7250 ha.
        assert abs(float(m.valor_ha) - 2.7250) < 0.001
        assert m.crs_calculo.startswith("EPSG:4674")

        # Única feição poligonal válida ⇒ projeção automática em Property.geom.
        projecao = db_session.query(ProjecaoGeometria).filter_by(tenant_id=tenant.id, property_id=prop.id).one()
        assert projecao.regra == "feicao_poligonal_unica"
        assert projecao.feicao_id == feicoes[0].id
        tem_geom = db_session.execute(text("SELECT geom IS NOT NULL FROM properties WHERE id = :id"),
                                      {"id": prop.id}).scalar()
        assert tem_geom is True

    def test_reler_mesmo_arquivo_nao_duplica(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc)
        geometria.processar_documento(db_session, doc, dados=KMZ_JOBSON)
        geometria.processar_documento(db_session, doc, dados=KMZ_JOBSON)
        assert db_session.query(ArquivoGeo).filter_by(tenant_id=tenant.id, documento_id=doc.id).count() == 1
        assert db_session.query(Feicao).filter_by(tenant_id=tenant.id).count() == 1
        assert db_session.query(Medicao).filter_by(tenant_id=tenant.id).count() == 1

    def test_kml_puro_tambem_e_lido(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc, filename="poligono.kml", content_type="application/vnd.google-earth.kml+xml")
        arquivo = geometria.processar_documento(db_session, doc, dados=KMZ_JOBSON_KML)
        assert arquivo.estado == "lido"
        assert arquivo.membro_lido is None

    def test_hash_bate_com_checksum_do_upload(self, db_session):
        import hashlib
        tenant, _user, _prop, proc = _seed(db_session)
        sha = hashlib.sha256(KMZ_JOBSON).hexdigest()
        doc = _doc(db_session, tenant, proc, checksum=sha)
        arquivo = geometria.processar_documento(db_session, doc, dados=KMZ_JOBSON)
        assert arquivo.estado == "lido"


class TestProcessarDocumentoFalhas:
    def test_geometria_invalida_fica_marcada_sem_medicao_determinada(self, db_session):
        tenant, _user, prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc, filename="bowtie.kml", content_type="application/vnd.google-earth.kml+xml")
        arquivo = geometria.processar_documento(db_session, doc, dados=KML_BOWTIE)
        assert arquivo.estado == "lido"
        feicao = db_session.query(Feicao).filter_by(tenant_id=tenant.id, arquivo_geo_id=arquivo.id).one()
        assert feicao.valida is False
        assert feicao.motivo_invalidade
        medicao = db_session.query(Medicao).filter_by(tenant_id=tenant.id, feicao_id=feicao.id).one()
        assert medicao.estado == "nao_determinado"
        assert "inválida" in medicao.motivo
        # Geometria inválida não vira a geometria do imóvel.
        assert db_session.query(ProjecaoGeometria).filter_by(tenant_id=tenant.id, property_id=prop.id).count() == 0

    def test_formato_nao_suportado_fica_visivel_nunca_em_breve(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc, filename="poligono.shp", content_type="application/x-shapefile")
        arquivo = geometria.processar_documento(db_session, doc, dados=b"qualquer coisa")
        assert arquivo.estado == "falha"
        assert arquivo.falha_codigo == "formato_nao_suportado"

    def test_kmz_ambiguo_vira_falha_com_codigo(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc)
        dados = io.BytesIO()
        with zipfile.ZipFile(dados, "w") as zf:
            zf.writestr("a.kml", KMZ_JOBSON_KML)
            zf.writestr("b.kml", KMZ_JOBSON_KML)
        arquivo = geometria.processar_documento(db_session, doc, dados=dados.getvalue())
        assert arquivo.falha_codigo == "kml_ambiguo"

    def test_hash_divergente_do_checksum_do_upload(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc, checksum="0" * 64)
        arquivo = geometria.processar_documento(db_session, doc, dados=KMZ_JOBSON)
        assert arquivo.falha_codigo == "hash_divergente"

    def test_storage_indisponivel_nao_vira_arquivo_ausente(self, db_session, monkeypatch):
        """#228: bucket/rede indisponível é uma FALHA visível, distinta de
        'arquivo não existe'."""
        from app.services import storage as storage_module

        class _FakeStorage:
            def download_bytes(self, _key):
                raise storage_module.StorageDownloadError("k", "NoSuchBucket", "bucket sumiu")

        monkeypatch.setattr(storage_module, "get_storage_service", lambda: _FakeStorage())
        tenant, _user, _prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc)
        arquivo = geometria.processar_documento(db_session, doc)  # sem `dados=` ⇒ baixa do storage
        assert arquivo.falha_codigo == "storage_indisponivel"

    def test_objeto_realmente_ausente_vira_arquivo_ausente(self, db_session, monkeypatch):
        from app.services import storage as storage_module

        class _FakeStorage:
            def download_bytes(self, _key):
                return b""  # NoSuchKey real — StorageService devolve b""

        monkeypatch.setattr(storage_module, "get_storage_service", lambda: _FakeStorage())
        tenant, _user, _prop, proc = _seed(db_session)
        doc = _doc(db_session, tenant, proc)
        arquivo = geometria.processar_documento(db_session, doc)
        assert arquivo.falha_codigo == "arquivo_ausente"


# O trigger `rejeitar_mutacao_evidencia` (append-only) só existe via Alembic —
# `Base.metadata.create_all()` (a fixture `db_session` deste arquivo) não cria
# triggers de DDL crua, igual ao resto da suíte (nenhum teste de
# `evidence_versions`/`documento_versao` testa o trigger por pytest). A prova
# de que `arquivo_geo`, `feicao`, `medicao`, `projecao_geometria` e
# `confronto_area` são append-only roda contra o banco de dev migrado de
# verdade (smoke pós-`alembic upgrade head`), não aqui.


# ---------------------------------------------------------------------------
# Medições declaradas: literal ancorado → número, sem LLM
# ---------------------------------------------------------------------------

class TestValorDeclarado:
    def test_literal_simples_em_hectares(self):
        valor, motivo = geometria.valor_declarado("Área total: 2,6893.", "ha")
        assert motivo is None
        assert valor == Decimal("2.6893")

    def test_literal_em_m2_converte(self):
        valor, motivo = geometria.valor_declarado("3.502.445,851 m²", "m2")
        assert motivo is None
        assert abs(float(valor) - 350.2445851) < 1e-6

    def test_literal_sem_numero(self):
        valor, motivo = geometria.valor_declarado("Sem menção a área.", "ha")
        assert valor is None and "sem número" in motivo

    def test_literal_vazio(self):
        valor, motivo = geometria.valor_declarado("", "ha")
        assert valor is None and motivo

    def test_unidade_desconhecida_nao_converte_as_cegas(self):
        valor, motivo = geometria.valor_declarado("Área de 10 alqueires.", "alqueire")
        assert valor is None and "unidade" in motivo

    def test_ambiguo_sem_desempate_fica_nao_determinado(self):
        valor, motivo = geometria.valor_declarado(
            "Área Total (ha) do Imóvel Rural: 2.180,8267 Módulos Fiscais: 31,1547", "ha")
        assert valor is None and "números" in motivo

    def test_ambiguo_desempatado_pelo_normalized_do_llm(self):
        valor, motivo = geometria.valor_declarado(
            "Área Total (ha) do Imóvel Rural: 2.180,8267 Módulos Fiscais: 31,1547", "ha",
            normalized={"valor": {"area": 2180.8267}})
        assert motivo is None
        assert valor == Decimal("2180.8267")

    def test_area_implausivel_fica_nao_determinada(self):
        valor, motivo = geometria.valor_declarado("Área de 0,001 ha.", "ha")
        assert valor is None and "plausível" in motivo


class TestPredicadoDeAreaTotal:
    @pytest.mark.parametrize("predicado,esperado", [
        ("area_total", True), ("area_do_imovel", True), ("car_area_ha", True),
        ("area_total_ccir", True), ("area_arrendada", False), ("rl_declarada_ha", False),
        ("app_area_ha", False), ("area_consolidada", False), ("area_de_preservacao", False),
    ])
    def test_marca_subarea_fora_do_confronto(self, predicado, esperado):
        assert geometria.predicado_de_area_total(predicado) is esperado


class TestMedirDeclaracoes:
    def test_gera_medicao_por_observacao_de_area_viva(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        matricula = _doc(db_session, tenant, proc, filename="matricula.pdf", content_type="application/pdf",
                         document_type="matricula")
        _observacao_area(db_session, tenant, proc, matricula, predicate="area_total", literal="Área total: 2,6893.")
        # Subárea: não é "imóvel_total" — não vira medição de área do imóvel.
        _observacao_area(db_session, tenant, proc, matricula, predicate="area_arrendada", literal="Arrenda-se 5 ha.")

        novas = geometria.medir_declaracoes(db_session, tenant.id, proc.id)
        assert len(novas) == 1
        assert novas[0].origem_tipo == "registro"  # matrícula é registro
        assert novas[0].valor_ha == Decimal("2.6893")

    def test_observacao_invalidada_nao_vira_medicao(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        car = _doc(db_session, tenant, proc, filename="car.pdf", content_type="application/pdf", document_type="car")
        obs = _observacao_area(db_session, tenant, proc, car, predicate="area_total", literal="Área total: 10,0000 ha.")
        db_session.add(EvidenceInvalidation(tenant_id=tenant.id, process_id=proc.id, evidence_id=obs.id,
                                            reason={"motivo": "reextraído"}))
        db_session.flush()
        assert geometria.medir_declaracoes(db_session, tenant.id, proc.id) == []

    def test_observacao_rejeitada_pela_revisao_nao_vira_medicao(self, db_session):
        tenant, user, _prop, proc = _seed(db_session)
        car = _doc(db_session, tenant, proc, filename="car.pdf", content_type="application/pdf", document_type="car")
        obs = _observacao_area(db_session, tenant, proc, car, predicate="area_total", literal="Área total: 10,0000 ha.")
        db_session.add(EvidenceReview(tenant_id=tenant.id, process_id=proc.id, evidence_id=obs.id, revision=1,
                                      action="rejeitar", author_id=user.id, justification="duplicada", premises=[]))
        db_session.flush()
        assert geometria.medir_declaracoes(db_session, tenant.id, proc.id) == []

    def test_reler_nao_duplica_medicao_declarada(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        matricula = _doc(db_session, tenant, proc, filename="matricula.pdf", content_type="application/pdf",
                         document_type="matricula")
        _observacao_area(db_session, tenant, proc, matricula, predicate="area_total", literal="Área total: 2,6893.")
        geometria.medir_declaracoes(db_session, tenant.id, proc.id)
        geometria.medir_declaracoes(db_session, tenant.id, proc.id)
        assert db_session.query(Medicao).filter_by(tenant_id=tenant.id, process_id=proc.id).count() == 1


# ---------------------------------------------------------------------------
# Confronto: caso de prova (Jobson) — denominador e tolerância declarados
# ---------------------------------------------------------------------------

class TestExecutarConfronto:
    def test_reproduz_a_divergencia_documentada_do_kmz_de_jobson(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        kmz_doc = _doc(db_session, tenant, proc)
        geometria.processar_documento(db_session, kmz_doc, dados=KMZ_JOBSON)
        matricula = _doc(db_session, tenant, proc, filename="matricula.pdf", content_type="application/pdf",
                         document_type="matricula")
        _observacao_area(db_session, tenant, proc, matricula, predicate="area_total", literal="Área total: 2,6893.")

        execucao = geometria.executar_confronto(db_session, tenant.id, proc.id)
        assert execucao is not None
        linhas = db_session.query(ConfrontoArea).filter_by(tenant_id=tenant.id, execucao=execucao).all()
        assert len(linhas) == 1
        linha = linhas[0]
        assert linha.denominador_regra == DENOMINADOR_REFERENCIA_DOCUMENTAL
        assert round(float(linha.percentual), 2) == 1.33
        assert linha.resultado == RESULTADO_DIVERGENTE
        assert linha.grau == GRADE_ATENCAO
        assert linha.tolerancia_origem == "provisoria_regua_onda_c_pendente_q_isis_04"

    def test_sem_medicao_calculada_devolve_none(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        assert geometria.executar_confronto(db_session, tenant.id, proc.id) is None

    def test_reexecutar_cria_nova_avaliacao_sem_apagar_a_anterior(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        kmz_doc = _doc(db_session, tenant, proc)
        geometria.processar_documento(db_session, kmz_doc, dados=KMZ_JOBSON)
        matricula = _doc(db_session, tenant, proc, filename="matricula.pdf", content_type="application/pdf",
                         document_type="matricula")
        _observacao_area(db_session, tenant, proc, matricula, predicate="area_total", literal="Área total: 2,6893.")

        exec1 = geometria.executar_confronto(db_session, tenant.id, proc.id)
        exec2 = geometria.executar_confronto(db_session, tenant.id, proc.id)
        assert exec1 != exec2
        assert db_session.query(ConfrontoArea).filter_by(tenant_id=tenant.id, execucao=exec1).count() == 1
        assert db_session.query(ConfrontoArea).filter_by(tenant_id=tenant.id, execucao=exec2).count() == 1


# ---------------------------------------------------------------------------
# Projeção manual (feição ambígua) e painel
# ---------------------------------------------------------------------------

class TestProjecaoManual:
    def _duas_feicoes(self, db_session, tenant, proc):
        doc = _doc(db_session, tenant, proc)
        duas = _kml("""<Document>
        <Placemark><name>A</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
        -49.45,-16.35,0 -49.4515,-16.35,0 -49.4515,-16.3515,0 -49.45,-16.3515,0 -49.45,-16.35,0
        </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
        <Placemark><name>B</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
        -49.50,-16.40,0 -49.5015,-16.40,0 -49.5015,-16.4015,0 -49.50,-16.4015,0 -49.50,-16.40,0
        </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
        </Document>""")
        arquivo = geometria.processar_documento(db_session, doc, dados=_kmz(duas))
        return arquivo

    def test_duas_feicoes_poligonais_nao_projeta_sozinho(self, db_session):
        tenant, _user, prop, proc = _seed(db_session)
        self._duas_feicoes(db_session, tenant, proc)
        assert db_session.query(ProjecaoGeometria).filter_by(tenant_id=tenant.id, property_id=prop.id).count() == 0

    def test_consultor_escolhe_com_motivo_obrigatorio(self, db_session):
        tenant, user, prop, proc = _seed(db_session)
        arquivo = self._duas_feicoes(db_session, tenant, proc)
        feicoes = db_session.query(Feicao).filter_by(tenant_id=tenant.id, arquivo_geo_id=arquivo.id).order_by(Feicao.ordem).all()

        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            geometria.escolher_projecao(db_session, tenant.id, user.id, proc.id, feicoes[1].id, "")

        geometria.escolher_projecao(db_session, tenant.id, user.id, proc.id, feicoes[1].id, "Feição B é o perímetro do CAR.")
        projecao = db_session.query(ProjecaoGeometria).filter_by(tenant_id=tenant.id, property_id=prop.id).one()
        assert projecao.feicao_id == feicoes[1].id
        assert projecao.autor_id == user.id
        assert projecao.regra is None

    def test_feicao_de_outro_caso_e_recusada(self, db_session):
        tenant, user, _prop, proc1 = _seed(db_session)
        _tenant2, _user2, _prop2, proc2 = _seed(db_session)
        arquivo = self._duas_feicoes(db_session, tenant, proc1)
        feicao = db_session.query(Feicao).filter_by(tenant_id=tenant.id, arquivo_geo_id=arquivo.id).first()

        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            geometria.escolher_projecao(db_session, tenant.id, user.id, proc2.id, feicao.id, "motivo qualquer")


class TestPainel:
    def test_estrutura_com_confronto_e_sobreposicao_nao_verificada(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        kmz_doc = _doc(db_session, tenant, proc)
        geometria.processar_documento(db_session, kmz_doc, dados=KMZ_JOBSON)
        matricula = _doc(db_session, tenant, proc, filename="matricula.pdf", content_type="application/pdf",
                         document_type="matricula")
        _observacao_area(db_session, tenant, proc, matricula, predicate="area_total", literal="Área total: 2,6893.")
        geometria.executar_confronto(db_session, tenant.id, proc.id)

        painel = geometria.painel(db_session, tenant.id, proc.id)
        assert painel["arquivos"][0]["estado"] == "lido"
        assert painel["arquivos"][0]["feicoes"][0]["area_ha"] is not None
        assert painel["confronto"]["estado"] == "avaliado"
        assert painel["confronto"]["linhas"][0]["resultado"] == RESULTADO_DIVERGENTE
        assert painel["sobreposicao"]["estado"] == "nao_verificado"
        assert painel["projecao"]["property_geom_gravada"] is True
        assert painel["parametros"]["denominador"] == DENOMINADOR_REFERENCIA_DOCUMENTAL

    def test_caso_sem_arquivo_geo_tem_lista_vazia(self, db_session):
        tenant, _user, _prop, proc = _seed(db_session)
        painel = geometria.painel(db_session, tenant.id, proc.id)
        assert painel["arquivos"] == []
        assert painel["confronto"]["estado"] == "nao_verificado"
