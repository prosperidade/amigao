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
"""

from __future__ import annotations

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.reconciliation_decisions import build_decisions
from app.services.staging_consolidation import consolidate_process, decidir_decisao_agrupada

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
    mat_3009 = _doc(db_session, tenant, proc, "matricula")
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
    for hint, doc in (("3673", mat_3673), ("3313", mat_3313), ("3009", mat_3009)):
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

    # ── Reserva Legal — AV.02 da 3.673 (vigente, 492,9252ha, doc 549 real) ×
    # RL declarada do CAR (437,7632ha, dívida #218/ADR-066) — >10%, crítico.
    rows["rl_matricula"] = _linha(
        db_session, tenant, proc, mat_3673, field_name="averbacao_rl",
        valor={"area": "492,9252", "referencia": "AV.02"}, entidade="matricula",
        alvo="averbacao_rl", hint="3673", tipo_obs="reserva_legal",
        atributos={"ato": "AV.02", "area": "492,9252", "vigencia": "vigente"},
    )
    rows["rl_car"] = _linha(
        db_session, tenant, proc, car, field_name="rl_declarada_ha",
        valor="437,7632", entidade="imovel", alvo="rl_status", unidade="ha",
    )

    # ── Gravames da 3.673 — AV.03 (hipoteca, baixada) e R.15 (alienação
    # fiduciária Itaú, sem baixa) — decisão ÚNICA "gravames vigentes".
    rows["gravame_av03"] = _linha(
        db_session, tenant, proc, mat_3673, field_name="onus", valor="hipoteca AV.03",
        entidade="matricula", hint="3673", tipo_obs="hipoteca",
        atributos={"ato": "AV.03", "vigencia": "baixado"},
    )
    rows["gravame_r15"] = _linha(
        db_session, tenant, proc, mat_3673, field_name="onus", valor="alienação R.15",
        entidade="matricula", hint="3673", tipo_obs="alienacao_fiduciaria",
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
        assert {d.chave[1] for d in composicoes} == {"3181", "3673", "3313", "3009"}


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


class TestReservaLegalDivergenciaCritica:
    def test_rl_matricula_x_car_diverge_critico(self, db_session):
        _tenant, _proc, _prop, _cli, rows = _elodi(db_session)
        resultado = build_decisions(list(rows.values()))
        d = _decisao(resultado, "reserva_legal")
        assert d is not None
        valores = {round(e.valor_normalizado, 4) for e in d.evidencias}
        assert valores == {492.9252, 437.7632}
        assert d.concordancia == "divergem"
        assert d.nivel_divergencia == "critico"
        # fonte autoritativa é a matrícula (ADR-062), não o CAR.
        autoritativa = next(e for e in d.evidencias if e.fonte_autoritativa)
        assert autoritativa.valor_normalizado == 492.9252
        assert d.valor_proposto == 492.9252


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
