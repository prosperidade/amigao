"""Frente G (REC-001 + CONF-001, ADR-067) — decisões, não campos.

A Conferência agrupava por CAMPO: 42 linhas na ELODI (caso #23) para os fatos
que a spec Isis nomeia em §3.4/§6. O sintoma medido (`docs/auditoria/
CONFIRMACAO_ENTRADA_2026-09-09.md`, "Decisão agrupada" — INSUFICIENTE): a
matrícula 3.181 aparecia em DUAS linhas — `matricula_listada` do CAR e
`numero_matricula` da certidão, mesmo hint, duas decisões cobradas por um
fato só.

Os valores usados (492,9252 × 437,7632 de RL; 926,3654 e 3.181; 3.673; R.15)
são os mesmos já medidos e citados nas Frentes E/F/fiação
(`tests/services/test_observacao_registral.py`, `test_fiacao_entrada.py` —
docs 546/547/549 da ELODI, extracted_text real de produção) e no próprio
ADR-066. Pull fresco de produção nesta sessão foi bloqueado pelo classificador
de auto-modo (Supabase MCP `execute_sql` recusado) — não reinventados, mas
não re-verificados nesta rodada (registrado no ADR-067).

ADENDO (`fix/reconciliacao-rl-chave`, Frente I): a fixture original de RL
usava `atributos={"area": "492,9252", ...}` — chave escrita à mão, que por
coincidência era a MESMA chave errada que `reconciliation_decisions.py:296`
buscava (`atributos["area"]`). O teste passava, confirmando o código; a
produção grava `atributos["area_ha"]` (conferido, id 1645/1603 do #23 real),
e o valor real caía no fallback de regex sobre texto narrativo, produzindo
2492.925227012009 a partir de 492,9252 + a data do ato. Fixture escrita a
partir do CÓDIGO confirma o código; fixture escrita a partir do DADO de
produção encontra o bug. A partir daqui, toda fixture de reconciliação nasce
de linha real de staging (valores colados do SELECT em produção), nunca de
dict inventado.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.ficha01_extraction import data_referencia_do_processo
from app.services.reconciliation_decisions import build_decisions
from app.services.staging_consolidation import (
    consolidate_process,
    decide_field,
    decidir_decisao_agrupada,
)

_SEQ = {"n": 0}


def _seed(db_session, *, client_type=ClientType.pj, full_name="ELODI AGROPECUARIA"):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Reconc {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name=full_name, email=f"reconc{n}@example.com",
                 client_type=client_type, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Retiro dos Olhos Dagua")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                    title="Caso", process_type="car", status=ProcessStatus.triagem,
                    demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, prop, cli


def _doc(db_session, tenant, proc, doc_type):
    _SEQ["n"] += 1
    d = Document(tenant_id=tenant.id, process_id=proc.id,
                 original_file_name=f"{doc_type}.pdf", filename=f"{doc_type}.pdf",
                 content_type="application/pdf",
                 storage_key=f"reconc/{tenant.id}/{_SEQ['n']}",
                 document_type=doc_type, ocr_status=OcrStatus.done)
    db_session.add(d)
    db_session.flush()
    return d


def _linha(db_session, tenant, proc, doc, *, field_name, valor, entidade, alvo=None,
           hint=None, tipo_obs=None, atributos=None, unidade=None,
           status=ExtractedFieldStatus.pendente, fonte=None):
    field_value = {"value": valor}
    if unidade:
        field_value["unidade"] = unidade
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=field_name, field_value=field_value,
        status=status, target_entity=entidade, target_field=alvo,
        matricula_hint=hint, source_doc_type=fonte or doc.document_type,
        tipo_observacao=tipo_obs, atributos=atributos,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _elodi(db_session):
    """As 4 matrículas + CAR + representante da ELODI (caso #23), reduzidas
    aos campos que esta frente precisa medir — não o dump completo."""
    tenant, proc, prop, cli = _seed(db_session)
    car = _doc(db_session, tenant, proc, "car")
    mat_3181 = _doc(db_session, tenant, proc, "matricula")
    mat_3673 = _doc(db_session, tenant, proc, "matricula")
    mat_3313 = _doc(db_session, tenant, proc, "matricula")
    mat_4387 = _doc(db_session, tenant, proc, "matricula")
    cnh_joel = _doc(db_session, tenant, proc, "rg_cpf")

    rows: dict[str, ExtractedFieldStaging] = {}

    # ── Composição — REC-001: 3.181 no CAR (matricula_listada) e na certidão
    # (numero_matricula) — o caso que deu nome à frente.
    rows["car_lista_3181"] = _linha(
        db_session, tenant, proc, car, field_name="matricula_listada",
        valor={"numero": "3181"}, entidade="matricula", hint="3181",
    )
    rows["certidao_3181"] = _linha(
        db_session, tenant, proc, mat_3181, field_name="numero_matricula",
        valor="3.181", entidade="matricula", alvo="numero_matricula", hint="3181",
    )
    for hint, doc in (("3673", mat_3673), ("3313", mat_3313), ("4387", mat_4387)):
        rows[f"certidao_{hint}"] = _linha(
            db_session, tenant, proc, doc, field_name="numero_matricula",
            valor=hint, entidade="matricula", alvo="numero_matricula", hint=hint,
        )

    # ── Área da 3.181 — abertura da matrícula, 926,36.54 (notação registral;
    # doc 547 real). "× CAR × SIGEF se houver" (GATE) — não há SIGEF nesta
    # fixture, então a decisão nasce fonte_unica (autoritativa por ADR-062).
    rows["area_3181"] = _linha(
        db_session, tenant, proc, mat_3181, field_name="area_registrada_ha",
        valor="926,36.54", entidade="matricula", alvo="area_ha", hint="3181",
        unidade="ha",
    )

    # ── Reserva Legal — duas averbações REAIS, uma por matrícula (`fix/
    # reconciliacao-rl-chave`, Frente I): AV.03 da 3.181 (185,85.60ha,
    # notação registral, doc 547 real) e AV.02 da 3.673 (492,9252ha, doc 549
    # real) SOMAM — não competem, são atos de matrículas diferentes. A soma
    # (678,7812ha) × RL declarada do CAR (437,7632ha, dívida #218/ADR-066) é
    # a decisão do IMÓVEL (`reserva_legal_total`) — >10%, crítico.
    # `atributos` copiado literal do #23 real (id 1603/1645): a chave é
    # `area_ha`, não `area` — é exatamente a fixture que o bug original
    # escondia (ver ADENDO no topo do arquivo).
    rows["rl_averbacao_3181"] = _linha(
        db_session, tenant, proc, mat_3181, field_name="averbacao_rl",
        valor="AV.03 · Reserva Legal · 185,85.60 ha · 21 de maio de 2004",
        entidade="matricula", alvo="averbacao_rl", hint="3181", tipo_obs="reserva_legal",
        atributos={
            "ato": "AV.03", "area_ha": "185,85.60", "data_ato": "21 de maio de 2004",
            "vigencia": "vigente",
            "descricao": "Procede-se esta averbação para constar a RELOCAÇÃO da área "
                          "de reserva Legal devidamente aprovada pelo Órgão Ambiental competente.",
        },
    )
    rows["rl_averbacao_3673"] = _linha(
        db_session, tenant, proc, mat_3673, field_name="averbacao_rl",
        valor="AV.02 · Reserva Legal · 492,9252 ha · 27/01/2009",
        entidade="matricula", alvo="averbacao_rl", hint="3673", tipo_obs="reserva_legal",
        atributos={
            "ato": "AV.02", "area_ha": "492,9252", "data_ato": "27/01/2009",
            "vigencia": "vigente",
            "descricao": "Procede-se a averbação da Reserva Legal desta Matricula em "
                          "conjunto com as Matriculas nº 1.224 e 1.225.",
        },
    )
    rows["rl_car"] = _linha(
        db_session, tenant, proc, car, field_name="rl_declarada_ha",
        valor="437,7632", entidade="imovel", alvo="rl_status", unidade="ha",
    )

    # ── Titularidade por matrícula — cadeia de compra e venda (Frente F,
    # ADR-066/ADR-067 adendo). 3.313: R-11 real (id 1629) — SONIA INÊS
    # GONDIM é TRANSMITENTE, não deve virar "proprietária" (o achado que
    # motivou esta frente). Pessoa vem como DICT (`{"cpf":..., "nome":...}`).
    rows["cv_3313_r11"] = _linha(
        db_session, tenant, proc, mat_3313, field_name="observacao",
        valor="R-11 · Compra e venda · adquirido por IZAURA DE FATIMA PEGO · de SONIA INÊS GONDIM",
        entidade=None, hint="3313", tipo_obs="compra_venda",
        atributos={
            "ato": "R-11", "data_ato": "27 de janeiro de 2014",
            "adquirentes": [{"cpf": "858.345.059-53", "nome": "IZAURA DE FATIMA PEGO"}],
            "transmitentes": [{"cpf": "283.621.361-20", "nome": "SONIA INÊS GONDIM"}],
        },
    )
    # 3.181: dois atos reais em sequência (id 1602, 1608) — pessoa vem como
    # STRING (forma real diferente da 3.313, medida no mesmo processo #23).
    # O titular atual é ELODI (R-09/2018), o adquirente do ato MAIS RECENTE
    # — não ALEXANDRE (R-02/2012), a primeira evidência da lista.
    rows["cv_3181_r02"] = _linha(
        db_session, tenant, proc, mat_3181, field_name="observacao",
        valor="R-02 · Compra e venda · adquirido por ALEXANDRE AUGUSTO CLEMENTE · de VERA LÚCIA BRAUN GALVÃO",
        entidade=None, hint="3181", tipo_obs="compra_venda",
        atributos={
            "ato": "R-02", "data_ato": "15/10/2012",
            "adquirentes": ["ALEXANDRE AUGUSTO CLEMENTE"],
            "transmitentes": ["VERA LÚCIA BRAUN GALVÃO"],
        },
    )
    rows["cv_3181_r09"] = _linha(
        db_session, tenant, proc, mat_3181, field_name="observacao",
        valor="R-09 · Compra e venda · adquirido por ELODI AGROPECUÁRIA · de ALEXANDRE AUGUSTO CLEMENTE",
        entidade=None, hint="3181", tipo_obs="compra_venda",
        atributos={
            "ato": "R-09", "data_ato": "21 de agosto de 2018",
            "adquirentes": ["ELODI AGROPECUÁRIA"],
            "transmitentes": ["ALEXANDRE AUGUSTO CLEMENTE"],
        },
    )

    # ── Gravames da 3.673 — AV.03 (hipoteca, baixada) e R.15 (alienação
    # fiduciária Itaú, sem baixa) — decisão ÚNICA "gravames vigentes".
    # `entidade=None`/`alvo=None`: medido contra a extração real (Frente I,
    # caso #23) — `observacao_registral.DESTINO_POR_TIPO` não mapeia gravame
    # nenhum, então `_linhas_de_observacoes` NUNCA marca `target_entity` para
    # estas linhas (fica `None`); o vínculo com a matrícula é só o
    # `matricula_hint`. `field_name="observacao"` é o fallback real
    # (`target_field or "observacao"`) para observação sem destino.
    rows["gravame_av03"] = _linha(
        db_session, tenant, proc, mat_3673, field_name="observacao", valor="hipoteca AV.03",
        entidade=None, hint="3673", tipo_obs="hipoteca",
        atributos={"ato": "AV.03", "vigencia": "baixado"},
    )
    rows["gravame_r15"] = _linha(
        db_session, tenant, proc, mat_3673, field_name="observacao", valor="alienação R.15",
        entidade=None, hint="3673", tipo_obs="alienacao_fiduciaria",
        atributos={"ato": "R.15", "vigencia": "vigente"},
    )

    # ── Titularidade (ELODI, PJ) + representante (Joel, CNH — ENT-001: doc
    # pessoal sobre PJ vai para representante, não para o titular).
    rows["cliente_nome"] = _linha(
        db_session, tenant, proc, car, field_name="nome_titular",
        valor="ELODI AGROPECUARIA", entidade="cliente", alvo="full_name",
    )
    rows["cliente_doc"] = _linha(
        db_session, tenant, proc, car, field_name="cnpj",
        valor="29.091.958/0001-17", entidade="cliente", alvo="document",
    )
    rows["repr_nome"] = _linha(
        db_session, tenant, proc, cnh_joel, field_name="nome",
        valor="Joel", entidade="representante", alvo="full_name",
    )
    rows["repr_doc"] = _linha(
        db_session, tenant, proc, cnh_joel, field_name="cpf",
        valor="111.222.333-44", entidade="representante", alvo="document",
    )

    # ── CAR (número/status).
    rows["car_numero"] = _linha(
        db_session, tenant, proc, car, field_name="numero_car",
        valor="GO-1234567-ABCD1234", entidade="imovel", alvo="car_code",
    )
    rows["car_status"] = _linha(
        db_session, tenant, proc, car, field_name="status_car",
        valor="Ativo", entidade="imovel", alvo="car_status",
    )

    return tenant, proc, prop, cli, rows


def test_data_de_abertura_do_caso_alimenta_a_vigencia(db_session):
    tenant, proc, _prop, _cli = _seed(db_session)
    proc.opened_at = datetime(2024, 5, 20, 12, 0, tzinfo=UTC)
    db_session.flush()

    assert data_referencia_do_processo(db_session, tenant.id, proc.id) == date(2024, 5, 20)


def _decisao(resultado, aspecto, identificador=None):
    for d in resultado.decisoes:
        _entidade, ident, asp = d.chave
        if asp == aspecto and (identificador is None or ident == identificador):
            return d
    return None


class TestComposicaoREC001:
    """A matrícula 3.181: uma decisão, não duas linhas."""

    def test_car_e_certidao_viram_uma_decisao_so(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))

        d = _decisao(resultado, "composicao", "3181")
        assert d is not None
        assert len(d.evidencias) == 2
        assert {e.documento_tipo for e in d.evidencias} == {"car", "matricula"}
        assert {e.staging_id for e in d.evidencias} == {
            rows["car_lista_3181"].id, rows["certidao_3181"].id,
        }
        assert d.concordancia == "concordam"

    def test_composicao_produz_uma_decisao_por_matricula(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        composicoes = [d for d in resultado.decisoes if d.chave[2] == "composicao"]
        assert {d.chave[1] for d in composicoes} == {"3181", "3673", "3313", "4387"}


class TestAreaPorMatricula:
    def test_area_da_3181_autoritativa_por_matricula(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "area", "3181")
        assert d is not None
        assert d.valor_proposto == 926.3654
        # única fonte nesta fixture (GATE: "× SIGEF se houver" — não há aqui).
        assert d.concordancia == "fonte_unica"
        assert d.evidencias[0].fonte_autoritativa is True


class TestReservaLegalPorMatricula:
    """`fix/reconciliacao-rl-chave`: RL de matrículas DIFERENTES não compete
    — cada averbação é decisão própria, fonte única (mesmo desenho de
    `area`). AV.03 da 3.181 e AV.02 da 3.673 são dois fatos, não duas
    leituras do mesmo fato."""

    def test_rl_3181_fonte_unica_valor_estruturado(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "reserva_legal", "3181")
        assert d is not None
        assert d.concordancia == "fonte_unica"
        # 185,85.60 é notação registral (hectares,ares.centiares) — não
        # 2492.925227012009 nem qualquer regex sobre texto narrativo.
        assert d.valor_proposto == 185.856
        assert d.evidencias[0].fonte_autoritativa is True

    def test_rl_3673_fonte_unica_valor_estruturado(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "reserva_legal", "3673")
        assert d is not None
        assert d.concordancia == "fonte_unica"
        assert d.valor_proposto == 492.9252
        # regressão do bug original: "492,9252 ha · 27/01/2009" regex'ado
        # inteiro produzia 2492.925227012009.
        assert d.valor_proposto != 2492.925227012009


class TestReservaLegalSemCampoEstruturado:
    """Sem `atributos["area_ha"]`, a evidência fica VISÍVEL mas não é um
    número — nunca mais regex sobre o texto narrativo do ato (produziu
    2492.925227012009 a partir de "492,9252 ha · 27/01/2009", Frente I,
    caso #23)."""

    def test_sem_area_ha_vira_evidencia_visivel_sem_valor_numerico(self, db_session):
        tenant, proc, _prop, _cli = _seed(db_session)
        mat = _doc(db_session, tenant, proc, "matricula")
        row = _linha(
            db_session, tenant, proc, mat, field_name="averbacao_rl",
            valor="AV.02 · Reserva Legal · 492,9252 ha · 27/01/2009",
            entidade="matricula", alvo="averbacao_rl", hint="9001", tipo_obs="reserva_legal",
            # atributos SEM "area_ha" — extração incompleta/malformada.
            atributos={"ato": "AV.02", "data_ato": "27/01/2009", "vigencia": "vigente"},
        )
        resultado = build_decisions([row])
        d = _decisao(resultado, "reserva_legal", "9001")
        assert d is not None
        assert d.evidencias[0].valor_normalizado == "sem área estruturada"
        assert d.evidencias[0].valor_normalizado != 2492.925227012009
        assert d.valor_proposto == "sem área estruturada"


class TestReservaLegalTotalDoImovel:
    """A decisão do IMÓVEL compara a SOMA das matrículas × CAR — mesmo
    desenho de `area_total`/`_injetar_area_total`."""

    def test_soma_das_matriculas_x_car_diverge_critico(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "reserva_legal_total")
        assert d is not None
        soma = next(e for e in d.evidencias if e.campo == "soma_matriculas")
        car = next(e for e in d.evidencias if e.documento_tipo == "car")
        assert soma.valor_normalizado == 678.7812  # 185,856 + 492,9252
        assert car.valor_normalizado == 437.7632
        assert d.concordancia == "divergem"
        assert d.nivel_divergencia == "critico"
        assert round(d.delta, 3) == 241.018
        assert round(d.percentual, 4) == 0.3551

        # a decisão por matrícula não desaparece — ela é a EVIDÊNCIA da soma.
        assert _decisao(resultado, "reserva_legal", "3181") is not None
        assert _decisao(resultado, "reserva_legal", "3673") is not None


class TestGravamesVigentes:
    def test_zero_hipotecas_vigentes_r15_vigente_uma_decisao(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "gravames", "3673")
        assert d is not None
        assert len(d.evidencias) == 2
        vigentes = [e for e in d.evidencias if e.valor_normalizado == "vigente"]
        baixados = [e for e in d.evidencias if e.valor_normalizado == "baixado"]
        assert len(vigentes) == 1 and vigentes[0].campo == "R.15"
        assert len(baixados) == 1 and baixados[0].campo == "AV.03"
        # síntese, não "o valor vencedor" de um confronto entre dois atos
        assert d.valor_proposto == "AV.03: baixado; R.15: vigente"


class TestTitularidadeERepresentante:
    def test_titularidade_elodi_e_representante_joel_sao_decisoes_distintas(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        titularidade = _decisao(resultado, "titularidade")
        representante = _decisao(resultado, "identificacao")
        assert titularidade is not None and representante is not None
        assert titularidade.chave != representante.chave
        nomes = {e.valor_normalizado for e in titularidade.evidencias}
        assert "ELODI AGROPECUARIA" in nomes
        nomes_repr = {e.valor_normalizado for e in representante.evidencias}
        assert "Joel" in nomes_repr


class TestTitularidadeMatricula:
    """`fix/reconciliacao-rl-chave` (Frente F ligada ao build_decisions):
    titular ATUAL da matrícula, pela cadeia de compra e venda — nunca o
    primeiro nome da lista. Achado original: SONIA INÊS GONDIM (transmitente
    do R-11/2014 na 3.313, #23 real) aparecia como "proprietário" porque o
    único lugar com o nome era o campo bruto `proprietarios` da certidão."""

    def test_sonia_e_transmitente_nao_titular(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "titularidade", "3313")
        assert d is not None
        assert d.valor_proposto == "IZAURA DE FATIMA PEGO (ato R-11)"
        nomes_na_evidencia = {e.valor_normalizado for e in d.evidencias}
        assert "SONIA INÊS GONDIM (transmitente)" in nomes_na_evidencia
        assert "SONIA" not in d.valor_proposto
        assert rows["cv_3313_r11"].id in d.staging_ids
        # saiu do sem_agrupamento — Frente G tratava compra_venda como campo
        # sem chave natural.
        assert rows["cv_3313_r11"].id not in {i["staging_id"] for i in resultado.sem_agrupamento}

    def test_titular_e_o_ato_mais_recente_nao_o_primeiro(self, db_session):
        """3.181: R-02/2012 (ALEXANDRE) depois R-09/2018 (ELODI) — pessoa em
        formato STRING (forma real diferente da 3.313, que é DICT — os dois
        formatos coexistem em produção)."""
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "titularidade", "3181")
        assert d is not None
        assert d.valor_proposto == "ELODI AGROPECUÁRIA (ato R-09)"
        assert len(d.evidencias) == 4  # 2 atos × (adquirente + transmitente)


class TestCarNumeroStatus:
    def test_car_numero_status_uma_decisao(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "car")
        assert d is not None
        assert len(d.evidencias) == 2


class TestContagemNadaSePerde:
    """42 linhas (aqui, o subconjunto da fixture) → N decisões; soma das
    evidências + sem_agrupamento cobre TODAS as linhas."""

    def test_soma_das_evidencias_mais_sem_agrupamento_e_o_total(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        todas = list(rows.values())
        resultado = build_decisions(todas)
        total_em_decisoes = sum(len(d.staging_ids) for d in resultado.decisoes)
        total_sem_agrupamento = len(resultado.sem_agrupamento)
        assert total_em_decisoes + total_sem_agrupamento == len(todas)
        # nesta fixture reduzida, toda linha foi desenhada para casar com uma
        # regra — o teste de regressão abaixo cobre o caminho sem_agrupamento.
        assert total_sem_agrupamento == 0

    def test_numero_de_decisoes_diferente_de_8_e_esperado_e_documentado(self, db_session):
        """ADR-067: "composição de matrículas (4)" já são 4 decisões, uma por
        matrícula — o total sobe de 8 para mais, e isso é o desenho certo, não
        um erro de contagem (registrado no ADR, não forçado a 8)."""
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        assert len(resultado.decisoes) > 8


class TestRegressaoFrentesAnteriores:
    """Campos das Frentes C-F que NÃO têm chave natural nesta frente continuam
    visíveis em `sem_agrupamento` — nunca escondidos, nunca quebrados."""

    def test_campos_sem_regra_de_chave_aparecem_visiveis(self, db_session):
        tenant, proc, _prop, _cli, _rows = _elodi(db_session)
        doc = _doc(db_session, tenant, proc, "matricula")
        extras = [
            _linha(db_session, tenant, proc, doc, field_name="cartorio",
                   valor="CRI de São João d'Aliança", entidade="matricula",
                   alvo="cartorio", hint="9999"),
            _linha(db_session, tenant, proc, doc, field_name="modulos_fiscais",
                   valor="31,1547", entidade="imovel", alvo="modulos_fiscais"),
            _linha(db_session, tenant, proc, doc, field_name="numero_ccir",
                   valor="123.456", entidade="matricula", alvo="numero_ccir", hint="9999"),
            _linha(db_session, tenant, proc, doc, field_name="app_declarada_ha",
                   valor="42,80", entidade="imovel", alvo="app_area_ha"),
        ]
        resultado = build_decisions(extras)
        assert len(resultado.decisoes) == 0
        assert len(resultado.sem_agrupamento) == len(extras)
        for item in resultado.sem_agrupamento:
            assert item["motivo"]


class TestValeriaPF:
    """Valéria (#22, PF) — 3 linhas → decisões coerentes com PF."""

    def test_tres_linhas_pf(self, db_session):
        tenant, proc, _prop, _cli = _seed(
            db_session, client_type=ClientType.pf, full_name="Valeria Ruiz",
        )
        cnh = _doc(db_session, tenant, proc, "rg_cpf")
        rows = [
            _linha(db_session, tenant, proc, cnh, field_name="nome",
                   valor="Valeria Ruiz", entidade="cliente", alvo="full_name"),
            _linha(db_session, tenant, proc, cnh, field_name="cpf",
                   valor="123.456.789-00", entidade="cliente", alvo="document"),
            _linha(db_session, tenant, proc, cnh, field_name="data_nascimento",
                   valor="01/01/1980", entidade="cliente", alvo="birth_date"),
        ]
        resultado = build_decisions(rows)
        titularidade = _decisao(resultado, "titularidade")
        assert titularidade is not None
        assert len(titularidade.evidencias) == 2
        # data_nascimento não tem chave natural nesta frente — visível, não some.
        assert len(resultado.sem_agrupamento) == 1
        assert resultado.sem_agrupamento[0]["field_name"] == "data_nascimento"


class TestDecidirDecisaoAgrupada:
    """Decidir a decisão grava as linhas que ela agrupa (consolidated_at
    existente) — "Aceito" e "Gravado" continuam distintos."""

    def test_decidir_composicao_aceita_as_duas_evidencias(self, db_session):
        tenant, proc, _prop, _cli, rows = _elodi(db_session)
        decidir_decisao_agrupada(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            chave=("matricula", "3181", "composicao"), acao="aceitar", user_id=None,
        )
        db_session.refresh(rows["car_lista_3181"])
        db_session.refresh(rows["certidao_3181"])
        assert rows["car_lista_3181"].status == ExtractedFieldStatus.aceito
        assert rows["certidao_3181"].status == ExtractedFieldStatus.aceito
        assert rows["car_lista_3181"].consolidated_at is None  # decidida, ainda não gravada

    def test_estado_evolui_pendente_decidida_gravada(self, db_session):
        tenant, proc, prop, _cli, rows = _elodi(db_session)
        antes = build_decisions(list(rows.values()))
        assert _decisao(antes, "composicao", "3181").estado == "pendente"

        decidir_decisao_agrupada(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            chave=("matricula", "3181", "composicao"), acao="aceitar", user_id=None,
        )
        db_session.expire_all()
        rows_pos = (
            db_session.query(ExtractedFieldStaging)
            .filter(ExtractedFieldStaging.process_id == proc.id)
            .all()
        )
        depois = build_decisions(rows_pos)
        assert _decisao(depois, "composicao", "3181").estado == "decidida"

        # Duas execuções (mesma convenção do GATE): a 1ª cria a matrícula pela
        # certidão; o aceite do CAR (`matricula_listada`) só CONFIRMA um
        # registro que já existe (guard fantasma, ADR-062) — na 1ª passagem a
        # matrícula ainda não existia quando o CAR foi processado, então o
        # carimbo do CAR só acontece na 2ª. Comportamento real da
        # consolidação, não uma folga do teste.
        consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id, user_id=None)
        consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id, user_id=None)
        db_session.expire_all()
        rows_pos2 = (
            db_session.query(ExtractedFieldStaging)
            .filter(ExtractedFieldStaging.process_id == proc.id)
            .all()
        )
        gravado = build_decisions(rows_pos2)
        assert _decisao(gravado, "composicao", "3181").estado == "gravada"

    def test_estado_misto_e_parcialmente_gravada(self, db_session):
        tenant, proc, _prop, _cli, rows = _elodi(db_session)
        decidir_decisao_agrupada(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            chave=("matricula", "3181", "composicao"), acao="aceitar", user_id=None,
        )
        rows["certidao_3181"].consolidated_at = rows["certidao_3181"].decided_at
        rows["car_lista_3181"].consolidated_at = None
        db_session.flush()

        atual = build_decisions(list(rows.values()))
        assert _decisao(atual, "composicao", "3181").estado == "parcialmente_gravada"

    def test_reabrir_devolve_a_decisao_a_pendente(self, db_session):
        tenant, proc, _prop, _cli, rows = _elodi(db_session)
        decidir_decisao_agrupada(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            chave=("matricula", "3181", "composicao"), acao="aceitar", user_id=None,
        )
        decidida = decidir_decisao_agrupada(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            chave=("matricula", "3181", "composicao"), acao="reabrir", user_id=None,
        )
        assert decidida.estado == "pendente"

    def test_editar_tipo_preserva_sugestao_e_reconciliacao_consumo_decidido(self, db_session):
        tenant, proc, _prop, _cli = _seed(db_session)
        doc = _doc(db_session, tenant, proc, "matricula")
        row = _linha(
            db_session, tenant, proc, doc, field_name="averbacao_app",
            valor="AV.03 — garantia hipotecária", entidade="matricula",
            alvo="averbacao_app", hint="3181", tipo_obs="app",
            atributos={"ato": "AV.03", "data_ato": "15/04/2008"},
        )

        decide_field(
            db_session, tenant_id=tenant.id, process_id=proc.id, field_id=row.id,
            acao="reclassificar", tipo_observacao="hipoteca", user_id=None,
        )
        db_session.refresh(row)

        assert row.tipo_observacao == "hipoteca"
        assert row.atributos["tipo_sugerido"] == "app"
        # O texto que a tela MOSTRA acompanha a decisão: sem isto o cartão
        # exibiria "AV.03 · APP · …" ao lado do tipo decidido "Hipoteca".
        assert "Hipoteca" in row.field_value["value"]
        assert row.field_value["value_sugerido"] == "AV.03 — garantia hipotecária"
        assert row.target_entity is None and row.target_field is None
        decisoes = build_decisions([row]).decisoes
        assert len(decisoes) == 1
        # `Decisao.chave` é a tupla (entidade, identificador, aspecto) — só o
        # `to_dict()` da API a nomeia em campos.
        assert decisoes[0].chave == ("matricula", "3181", "gravames")
        assert decisoes[0].evidencias[0].tipo_observacao == "hipoteca"


class TestFrenteJEvidenciaTipada:
    """Frente J — regressão do TypeError medido no #23 real: `Evidencia` ganhou
    `tipo_observacao` e a decisão de TITULARIDADE (construída fora de
    `_evidencia_de`) derrubava `build_decisions` inteiro. Aqui a linha é uma
    `compra_venda` como as do #23 (R-13 da 3.673)."""

    def test_titularidade_nao_quebra_e_carrega_o_tipo(self, db_session):
        tenant, proc, _prop, _cli = _seed(db_session)
        doc = _doc(db_session, tenant, proc, "matricula")
        _linha(
            db_session, tenant, proc, doc, field_name="observacao",
            valor="R-13 · Compra e venda · 10/12/2019", entidade=None, alvo=None,
            hint="3673", tipo_obs="compra_venda",
            atributos={"ato": "R-13", "data_ato": "10/12/2019",
                       "adquirentes": ["ELODI AGROPECUÁRIA"],
                       "transmitentes": ["ALEXANDRE AUGUSTO CLEMENTE"]},
        )
        rows = db_session.query(ExtractedFieldStaging).filter(
            ExtractedFieldStaging.process_id == proc.id
        ).all()
        resultado = build_decisions(rows)
        titularidade = _decisao(resultado, "titularidade", "3673")
        assert titularidade is not None
        assert {e.tipo_observacao for e in titularidade.evidencias} == {"compra_venda"}
        assert all("tipo_observacao" in e.to_dict() for e in titularidade.evidencias)
        assert "ELODI AGROPECUÁRIA" in str(titularidade.valor_proposto)

    def test_evidencia_sintetica_de_soma_tem_tipo_none(self, db_session):
        tenant, proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        for decisao in resultado.decisoes:
            for e in decisao.evidencias:
                if e.staging_id is None:
                    assert e.tipo_observacao is None


class TestFrenteJEscolherFonteSemDestino:
    """Frente J expôs `escolher_fonte` na decisão agrupada (item 5). Uma
    evidência SEM destino (gravame/baixa/aditivo — ADR-065) não disputa coluna
    com ninguém: `_reject_siblings` não pode varrer `target_field IS NULL` e
    derrubar todas as outras observações da mesma matrícula."""

    def test_escolher_fonte_em_gravame_nao_rejeita_as_outras_observacoes(self, db_session):
        tenant, proc, _prop, _cli = _seed(db_session)
        doc = _doc(db_session, tenant, proc, "matricula")
        escolhida = _linha(
            db_session, tenant, proc, doc, field_name="observacao",
            valor="AV.03 · Hipoteca · 15/04/2008", entidade=None, alvo=None,
            hint="3673", tipo_obs="hipoteca", atributos={"ato": "AV.03", "vigencia": "vigente"},
        )
        vizinhas = [
            _linha(db_session, tenant, proc, doc, field_name="observacao",
                   valor="AV.09 · Baixa · 16/03/2017", entidade=None, alvo=None,
                   hint="3673", tipo_obs="baixa", atributos={"ato": "AV.09"}),
            _linha(db_session, tenant, proc, doc, field_name="observacao",
                   valor="AV.10 · Arrendamento · 50 ha", entidade=None, alvo=None,
                   hint="3673", tipo_obs="arrendamento", atributos={"ato": "AV.10"}),
        ]

        decide_field(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            field_id=escolhida.id, acao="escolher_fonte", user_id=None,
        )

        db_session.refresh(escolhida)
        assert escolhida.status == ExtractedFieldStatus.aceito
        for v in vizinhas:
            db_session.refresh(v)
            assert v.status == ExtractedFieldStatus.pendente, f"{v.atributos} foi rejeitada em massa"


class TestFrenteJAceitarCobreTodosOsMembros:
    """Achado do gate E2E (12/09): `aceitar` percorria as EVIDÊNCIAS, e nem
    todo membro da decisão vira evidência. A decisão de titularidade monta a
    lista a partir da CADEIA (`cadeia_titularidade`), então um ato de
    `compra_venda` que não nomeia adquirente/transmitente entra no grupo e não
    aparece na lista — medido no caso real: matrícula 3.181 com 3 membros para
    2 evidências. A linha órfã nunca era aceita e a decisão ficava presa em
    "pendente": a consultora clicava em Aceitar e a tela não mudava."""

    def test_aceitar_decide_membro_que_nao_virou_evidencia(self, db_session):
        tenant, proc, _prop, _cli = _seed(db_session)
        doc = _doc(db_session, tenant, proc, "matricula")
        # Ato COM os dois lados nomeados → vira evidência na cadeia.
        com_partes = _linha(
            db_session, tenant, proc, doc, field_name="observacao",
            valor="R-13 · Compra e venda · 10/12/2019", entidade=None, alvo=None,
            hint="3673", tipo_obs="compra_venda",
            atributos={"ato": "R-13", "data_ato": "10/12/2019",
                       "adquirentes": ["ELODI AGROPECUÁRIA"],
                       "transmitentes": ["ALEXANDRE AUGUSTO CLEMENTE"]},
        )
        # Ato do MESMO fato, sem partes distinguidas → membro sem evidência.
        orfa = _linha(
            db_session, tenant, proc, doc, field_name="observacao",
            valor="R-09 · Compra e venda · 03/05/2016", entidade=None, alvo=None,
            hint="3673", tipo_obs="compra_venda",
            atributos={"ato": "R-09", "data_ato": "03/05/2016"},
        )

        rows = db_session.query(ExtractedFieldStaging).filter(
            ExtractedFieldStaging.process_id == proc.id).all()
        decisao = _decisao(build_decisions(rows), "titularidade", "3673")
        assert decisao is not None
        ids_evidencia = {e.staging_id for e in decisao.evidencias if e.staging_id is not None}
        assert orfa.id in decisao.staging_ids and orfa.id not in ids_evidencia, (
            "a fixture precisa ter um membro fora da lista de evidências"
        )

        decidir_decisao_agrupada(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            chave=("matricula", "3673", "titularidade"), acao="aceitar", user_id=None,
        )
        db_session.expire_all()
        for linha in (com_partes, orfa):
            db_session.refresh(linha)
            assert linha.status == ExtractedFieldStatus.aceito, linha.atributos

        rows_pos = db_session.query(ExtractedFieldStaging).filter(
            ExtractedFieldStaging.process_id == proc.id).all()
        assert _decisao(build_decisions(rows_pos), "titularidade", "3673").estado == "decidida"
