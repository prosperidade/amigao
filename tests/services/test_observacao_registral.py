"""Frente E — a extração diz O QUE cada valor é antes de dizer ONDE ele pousa.
Frente F (ADR-066) acrescenta QUANDO e SE ainda vale: `data_ato`/`altera_ato`
estruturados e `vigencia` DERIVADA por regra (nunca pelo LLM).

Todos os trechos abaixo são VERBATIM dos quatro documentos de matrícula da ELODI
(docs 547–550), lidos do `extracted_text` real de produção (Supabase, projeto
"Regente Ambiental", tabela `documents`, ids 547-550 — mesmo texto medido nas
frentes C/D/E). Nenhum exemplo inventado: cada asserção corresponde a um erro
medido em `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md`, à dívida #221 ou
ao HIST-001.
"""

from __future__ import annotations

from datetime import date

from app.services.ficha01_extraction import build_staging_fields
from app.services.observacao_registral import (
    TIPO_ALIENACAO_FIDUCIARIA,
    TIPO_ARRENDAMENTO,
    TIPO_BAIXA,
    TIPO_COMPRA_VENDA,
    TIPO_HIPOTECA,
    TIPO_NAO_CLASSIFICADO,
    TIPO_RESERVA_LEGAL,
    VIGENCIA_BAIXADO,
    VIGENCIA_EXPIRADO,
    VIGENCIA_INDETERMINADO,
    VIGENCIA_RETIFICADO,
    VIGENCIA_VIGENTE,
    aplicar_alteracoes,
    area_de_outro_objeto,
    cadeia_titularidade,
    chave_ato,
    derivar_vigencia,
    destino_de,
    normalizar_tipo,
    observacoes_de,
    onus_vigentes,
    rl_vigente,
    titular_atual,
    ultimo_por_destino,
)

# ── Trechos reais ──────────────────────────────────────────────────────────

# doc 548, char 27.072 — o arrendamento que virou `averbacao_app` (OCR-002).
TEXTO_548_AV10 = (
    "AV.10 MAT. 3.313:(Averbação Referente a Av.15 Mat. 1908): Averba-se para "
    "constar o arrendamento de uma área de 50 hectares para Patrícia Akemi Miaki "
    "Botega pelo período de 15 anos com inicio no dia 01/01/2013 a 01/01/2028, "
    "conforme contrato registrado no Lv. 3-F as fls. 115/116 sob o nº 1702."
)

# doc 549 — a AV.02 (RL de verdade), a AV.03 (hipoteca) e a AV.09 que a baixa;
# o R-11 (preço da compra e venda que virou "hipoteca") e o R.15 (alienação
# fiduciária do Itaú que virou "hipoteca do Banco do Brasil").
TEXTO_549 = (
    "AV.02 MAT. 3.673 -(Averbação referente a Av.09 Mat. 2007 e Av. 04 Mat. 3.669)- "
    "Procede-se a averbação da Reserva Legal desta Matricula em conjunto com as "
    "Matriculas nº 1.224 e 1.225, com a área total de 492,9252ha, não inferior a "
    "20% do total da propriedade. "
    "AV.03 MAT. 3.673 - DATA: 15 DE ABRIL DE 2008 – REGISTRO DE HIPOTECA. Nos "
    "Termos da CRH nº 40/00690-5 com vencimento em 01/12/2016, em favor do Banco "
    "do Brasil S/A Ag. Planaltina – GO, no valor de R$ 657.000,00. "
    "AV.09 MAT. 3.673- DATA: 16 DE MARÇO DE 2017- BAIXA DE HIPOTECA- Averba-se "
    "para constar a baixa da cédula Rural Pignoratícia e Hipotecaria nº 40/00690-5, "
    "constante da AV.03, acima oriunda do R-06 da Matrícula anterior 2007. "
    "R-11 MAT. 3.673- DATA: 18 DE MARÇO DE 2019 - DA COMPRA E VENDA- pelo preço "
    "certo e ajustado de R$ 657.000,00 (seiscentos e cinquenta e sete mil reais). "
    "R.15 MAT. 3.673- DATA: 04 DE JUNHO DE 2.025 – DA ALIENAÇÃO FIDUCIÁRIA- "
    "tornando o Devedor possuidor direto e o Itaú Unibanco S.A possuidor indireto "
    "do imóvel. O valor da garantia fiduciária e do imóvel para fins de venda em "
    "leilão é de R$ 9.798.869,87. "
    "AV.12 MAT. 3.673- DATA: 21 DE AGOSTO DE 2019- BAIXA DE HIPOTECA- ficando "
    "assim, o imóvel livre de hipoteca."
)

# doc 547 — a abertura (área do imóvel) e a Av.03 (relocação da RL), que é a
# dívida #221: mesma forma, significado diferente.
TEXTO_547 = (
    "MATRICULA Nº 3.181- Data - 01 de Outubro de 2013 - IMÓVEL: UMA GLEBA DE "
    "TERRAS, situada na FAZENDA RETIRO DOS OLHOS D'AGUA- QUINHÃO 1, município de "
    "Alto Paraíso de Goiás, com área de 926,36.54ha (novecentos e vinte e seis "
    "hectares, trinta e seis ares e cinquenta e quatro centiares). "
    "Av.03 Mat. 3181: (Averbação Referente a Av.05 M 1039). Procede-se esta "
    "averbação para constar a RELOCAÇÃO da área de reserva Legal de 185,85.60ha, "
    "devidamente aprovada pelo Órgão Ambiental competente."
)


class TestVocabulario:
    """Rótulo do modelo → tipo do vocabulário, com escape visível."""

    def test_rotulos_do_documento_caem_no_tipo_certo(self):
        assert normalizar_tipo("Reserva Legal") == TIPO_RESERVA_LEGAL
        assert normalizar_tipo("REGISTRO DE HIPOTECA") == TIPO_HIPOTECA
        assert normalizar_tipo("DA ALIENAÇÃO FIDUCIÁRIA") == TIPO_ALIENACAO_FIDUCIARIA
        assert normalizar_tipo("BAIXA DE HIPOTECA") == TIPO_BAIXA
        assert normalizar_tipo("RESCISÃO DE ARRENDAMENTO") == TIPO_BAIXA
        assert normalizar_tipo("DA QUITAÇÃO DA DÍVIDA") == TIPO_BAIXA

    def test_compromisso_nao_e_lido_como_compra_e_venda(self):
        """O sinônimo mais longo vence: 'compromisso de compra e venda' contém
        'compra e venda' e não pode ser colapsado nele."""
        assert normalizar_tipo("Compromisso de Venda e Compra") == "compromisso_compra_venda"
        assert normalizar_tipo("DA COMPRA E VENDA") == TIPO_COMPRA_VENDA

    def test_fora_do_vocabulario_vira_escape_visivel_nao_gaveta_alheia(self):
        """O ponto da frente: o que não se sabe classificar aparece como não
        classificado — nunca é espremido em `averbacao_app`."""
        assert normalizar_tipo("Ofício INCRA nº 1032/2016") == TIPO_NAO_CLASSIFICADO
        assert normalizar_tipo(None) == TIPO_NAO_CLASSIFICADO
        assert normalizar_tipo("") == TIPO_NAO_CLASSIFICADO

    def test_chave_do_ato_normaliza_as_formas_do_mesmo_documento(self):
        """"AV.03", "Av.03", "AV-3" e "R.15" convivem no MESMO documento."""
        assert chave_ato("AV.03") == chave_ato("Av.03") == chave_ato("AV-3") == "AV-3"
        assert chave_ato("R.15") == chave_ato("R-15") == "R-15"
        assert chave_ato("sem rótulo") is None


class TestBaixaPorReferencia:
    """AV.09 diz, por escrito, que baixa a AV.03. É referência, não inferência."""

    ATOS = [
        {"ato": "AV.03", "tipo": "hipoteca", "valor": "R$ 657.000,00",
         "partes": ["Banco do Brasil S/A Ag. Planaltina – GO"], "data_ato": "15/04/2008"},
        {"ato": "AV.09", "tipo": "baixa", "altera_ato": "AV.03",
         "descricao": "baixa da cédula nº 40/00690-5, constante da AV.03"},
        {"ato": "R.15", "tipo": "alienacao_fiduciaria", "valor": "R$ 9.798.869,87",
         "partes": ["Itaú Unibanco S.A"], "data_ato": "04/06/2025"},
    ]

    def test_a_hipoteca_baixada_e_marcada(self):
        obs = observacoes_de(self.ATOS)
        aplicar_alteracoes(obs)
        hipoteca = next(o for o in obs if o.ato == "AV.03")
        assert hipoteca.baixado_por == "AV.09"

    def test_hipoteca_baixada_nao_e_afirmada_como_onus_vigente(self):
        """As três hipotecas do doc 549 foram baixadas por AV.09/AV.10/AV.12 — a
        AV.12 diz textualmente "ficando assim, o imóvel livre de hipoteca". O
        staging afirmava duas hipotecas do Banco do Brasil que não existiam."""
        obs = observacoes_de(self.ATOS)
        aplicar_alteracoes(obs)
        vigentes = onus_vigentes(obs)
        assert [o["tipo"] for o in vigentes] == ["Alienação fiduciária"]
        assert vigentes[0]["partes"] == ["Itaú Unibanco S.A"]
        assert vigentes[0]["valor"] == "R$ 9.798.869,87"

    def test_referencia_lida_da_descricao_quando_o_campo_vem_vazio(self):
        atos = [
            {"ato": "AV.03", "tipo": "hipoteca", "partes": ["Banco do Brasil"]},
            {"ato": "AV.09", "tipo": "baixa",
             "descricao": "baixa da cédula nº 40/00690-5, constante da AV.03, acima"},
        ]
        obs = observacoes_de(atos)
        aplicar_alteracoes(obs)
        assert next(o for o in obs if o.ato == "AV.03").baixado_por == "AV.09"

    def test_baixa_e_observacao_de_primeira_classe(self):
        """"AV.12 — imóvel livre de hipoteca" é informação, não ausência."""
        rows = build_staging_fields(
            "matricula",
            {"atos": [{"ato": "AV.12", "tipo": "BAIXA DE HIPOTECA",
                       "descricao": "ficando assim, o imóvel livre de hipoteca"}]},
            texto=TEXTO_549,
        )
        baixa = next(r for r in rows if r.tipo_observacao == TIPO_BAIXA)
        assert baixa.field_name == "observacao"
        assert "AV.12" in baixa.field_value["value"]


class TestDestinoPorTipo:
    """O mapeamento acontece DEPOIS do tipo, e ausência de casa não é erro."""

    def test_reserva_legal_tem_casa_arrendamento_nao(self):
        obs = observacoes_de([
            {"ato": "AV.02", "tipo": "reserva_legal", "area_ha": "492,9252"},
            {"ato": "AV.10", "tipo": "arrendamento", "area_ha": "50"},
        ])
        assert destino_de(obs[0]) == ("matricula", "averbacao_rl")
        assert destino_de(obs[1]) is None

    def test_dois_atos_do_mesmo_destino_o_ultimo_do_documento_leva(self):
        """A coluna é uma só. Vence o ato mais adiante no documento — ordem no
        papel, não vigência inferida (temporalidade é a frente seguinte)."""
        obs = observacoes_de([
            {"ato": "AV.02", "tipo": "reserva_legal", "area_ha": "492,9252"},
            {"ato": "AV.07", "tipo": "reserva_legal", "area_ha": "500,0000"},
        ])
        escolhido = ultimo_por_destino(obs)[("matricula", "averbacao_rl")]
        assert escolhido.ato == "AV.07"


class TestArrendamentoNaoEApp:
    """OCR-002: o documento nunca diz APP, e a AV.10 caía em `averbacao_app`."""

    JSON = {
        "numero_matricula": "3.313",
        "atos": [{
            "ato": "AV.10", "tipo": "arrendamento", "area_ha": "50",
            "partes": ["Patrícia Akemi Miaki Botega"],
            "prazo": "15 anos com inicio no dia 01/01/2013 a 01/01/2028",
            "descricao": "Averba-se para constar o arrendamento de uma área de 50 hectares",
        }],
        "confidence": {"atos": "high"},
    }

    def _linhas(self):
        return build_staging_fields("matricula", self.JSON, texto=TEXTO_548_AV10)

    def test_o_arrendamento_nao_vai_para_averbacao_app(self):
        rows = self._linhas()
        assert not any(r.target_field == "averbacao_app" for r in rows)

    def test_sai_tipado_como_arrendamento_com_prazo_e_parte(self):
        linha = next(r for r in self._linhas() if r.tipo_observacao == TIPO_ARRENDAMENTO)
        assert linha.atributos["prazo"].startswith("15 anos")
        assert linha.atributos["partes"] == ["Patrícia Akemi Miaki Botega"]
        assert linha.atributos["area_ha"] == "50"

    def test_sem_casa_a_linha_aparece_com_o_motivo_e_sem_destino(self):
        """Nunca forçada numa gaveta: sem destino, com o porquê escrito."""
        linha = next(r for r in self._linhas() if r.tipo_observacao == TIPO_ARRENDAMENTO)
        assert (linha.target_entity, linha.target_field) == (None, None)
        assert linha.field_value["sem_destino"] is True
        assert "sem coluna correspondente" in linha.field_value["sem_destino_motivo"]


class TestAreaDeOutroObjeto:
    """Dívida #221 — forma certa, significado errado."""

    OBS_RL = observacoes_de([
        {"ato": "Av.03", "tipo": "reserva_legal", "area_ha": "185,85.60",
         "descricao": "RELOCAÇÃO da área de reserva Legal de 185,85.60ha"},
    ])

    def test_a_area_da_reserva_legal_e_reconhecida_como_de_outro_objeto(self):
        dona = area_de_outro_objeto(self.OBS_RL, "185,85.60")
        assert dona is not None and dona.ato == "Av.03"

    def test_compara_pela_area_normalizada_nao_pela_string(self):
        """`185,85.60` (notação registral) e `185,856` são o MESMO número — a
        comparação passa pela mesma porta única do resto do sistema."""
        assert area_de_outro_objeto(self.OBS_RL, "185,856") is not None

    def test_a_area_do_imovel_nao_e_confundida_com_a_da_reserva(self):
        assert area_de_outro_objeto(self.OBS_RL, "926,36.54") is None

    def test_area_de_rl_nao_grava_como_area_da_matricula(self):
        """O caso do doc 547 na execução DEPOIS-2: âncora válida, formato válido,
        normalização correta — e campo errado. Nenhuma das quatro contenções do
        ADR-064 barrava; o tipo barra."""
        rows = build_staging_fields(
            "matricula",
            {"numero_matricula": "3.181", "area_registrada_ha": "185,85.60",
             "atos": [{"ato": "Av.03", "tipo": "reserva_legal", "area_ha": "185,85.60"}]},
            texto=TEXTO_547,
        )
        area = next(r for r in rows if r.field_name == "area_registrada_ha")
        assert (area.target_entity, area.target_field) == (None, None)
        assert area.confidence == "low"
        assert "Reserva Legal" in area.field_value["sem_destino_motivo"]

    def test_a_area_do_imovel_de_verdade_continua_pousando(self):
        """Controle: com o mesmo JSON e a área da abertura, nada é barrado."""
        rows = build_staging_fields(
            "matricula",
            {"numero_matricula": "3.181", "area_registrada_ha": "926,36.54",
             "atos": [{"ato": "Av.03", "tipo": "reserva_legal", "area_ha": "185,85.60"}]},
            texto=TEXTO_547,
        )
        area = next(r for r in rows if r.field_name == "area_registrada_ha")
        assert (area.target_entity, area.target_field) == ("matricula", "area_ha")
        assert area.field_value["normalizado_ha"] == 926.3654


class TestOnusDerivadoDosAtos:
    """R-11 é preço de compra e venda; R.15 é alienação do Itaú. Nem um nem
    outro é "hipoteca do Banco do Brasil" — que foi o que o staging afirmou."""

    JSON = {
        "numero_matricula": "3.673",
        "atos": [
            {"ato": "AV.03", "tipo": "REGISTRO DE HIPOTECA", "valor": "R$ 657.000,00",
             "partes": ["Banco do Brasil S/A Ag. Planaltina – GO"]},
            {"ato": "AV.09", "tipo": "BAIXA DE HIPOTECA", "altera_ato": "AV.03"},
            {"ato": "R-11", "tipo": "DA COMPRA E VENDA", "valor": "R$ 657.000,00"},
            {"ato": "R.15", "tipo": "DA ALIENAÇÃO FIDUCIÁRIA",
             "valor": "R$ 9.798.869,87", "partes": ["Itaú Unibanco S.A"]},
        ],
        "confidence": {"atos": "high"},
    }

    def _rows(self):
        return build_staging_fields("matricula", self.JSON, texto=TEXTO_549)

    def test_o_preco_da_compra_e_venda_nao_e_gravame(self):
        linha = next(r for r in self._rows() if r.atributos and r.atributos.get("ato") == "R-11")
        assert linha.tipo_observacao == TIPO_COMPRA_VENDA
        onus = next(r for r in self._rows() if r.field_name == "onus")
        assert all(o.get("valor") != "657.000,00" for o in onus.field_value["value"])

    def test_a_alienacao_fiduciaria_guarda_as_partes_daquele_ato(self):
        """`partes` (lista), não `credor` (singular) — gate mediu que o modelo
        não ordena as partes de forma estável entre execuções (doc 550);
        escolher partes[0] como "o credor" inventaria um papel."""
        onus = next(r for r in self._rows() if r.field_name == "onus")
        [item] = onus.field_value["value"]
        assert item["tipo"] == "Alienação fiduciária"
        assert item["partes"] == ["Itaú Unibanco S.A"]

    def test_a_linha_de_onus_e_uma_so_com_destino(self):
        """Uma linha, não N: `onus_gravames` é UMA coluna — N linhas fariam a
        primeira gravar e as outras virarem reconciliação falsa (lição do #155)."""
        rows = self._rows()
        onus = [r for r in rows if r.field_name == "onus"]
        assert len(onus) == 1
        assert (onus[0].target_entity, onus[0].target_field) == ("matricula", "onus_gravames")

    def test_gravame_individual_nao_disputa_a_coluna(self):
        linha = next(r for r in self._rows() if r.atributos and r.atributos.get("ato") == "R.15")
        assert (linha.target_entity, linha.target_field) == (None, None)
        assert "linha de ônus" in linha.field_value["sem_destino_motivo"]


class TestReservaLegalPousaPeloAto:
    """A AV.02 (492,9252 ha em conjunto com 1.224 e 1.225) é a RL registral."""

    def test_a_averbacao_de_rl_leva_o_destino_e_carrega_o_ato(self):
        rows = build_staging_fields(
            "matricula",
            {"atos": [{"ato": "AV.02", "tipo": "reserva_legal", "area_ha": "492,9252",
                       "descricao": "Reserva Legal em conjunto com as Matriculas nº 1.224 e 1.225"}]},
            texto=TEXTO_549,
        )
        linha = next(r for r in rows if r.target_field == "averbacao_rl")
        assert linha.tipo_observacao == TIPO_RESERVA_LEGAL
        assert linha.atributos["ato"] == "AV.02"
        assert "492,9252" in linha.field_value["value"]

    def test_a_gaveta_antiga_nao_duplica_a_linha_tipada(self):
        """JSON legado com `averbacao_rl` E atos tipados: o ato vence, e o
        destino não recebe duas linhas (que seriam decisão em duplicidade)."""
        rows = build_staging_fields(
            "matricula",
            {"averbacao_rl": {"area": "42,8070", "referencia": "Reserva Legal"},
             "atos": [{"ato": "AV.02", "tipo": "reserva_legal", "area_ha": "492,9252"}]},
            texto=TEXTO_549,
        )
        assert sum(1 for r in rows if r.target_field == "averbacao_rl") == 1


class TestNaoRegressao:
    """Documento sem atos e documento de outro tipo seguem exatamente iguais."""

    def test_matricula_sem_atos_produz_os_campos_de_sempre(self):
        rows = build_staging_fields(
            "matricula",
            {"numero_matricula": "3.181", "cartorio": "Registro de Imóveis de Alto Paraíso de Goiás"},
            texto=TEXTO_547 + " Registro de Imóveis de Alto Paraíso de Goiás",
        )
        nomes = {r.field_name for r in rows}
        assert {"numero_matricula", "cartorio"} <= nomes
        assert all(r.tipo_observacao is None for r in rows)

    def test_documento_que_nao_e_matricula_nao_ganha_observacao(self):
        """Controle negativo: `atos` num RG não vira observação de matrícula."""
        rows = build_staging_fields(
            "rg_cpf",
            {"nome": "VALERIA RUIZ", "atos": [{"ato": "AV.01", "tipo": "hipoteca"}]},
            texto="NOME E SOBRENOME VALERIA RUIZ",
            titular_tipo="pf",
        )
        assert all(r.tipo_observacao is None for r in rows)
        assert not any(r.field_name == "observacao" for r in rows)


# ═══════════════════════════════════════════════════════════════════════════
# Frente F (ADR-066) — temporalidade de ato: data_ato/altera_ato estruturados
# e vigencia DERIVADA por regra. Trechos abaixo, de novo, VERBATIM do doc 549
# (Supabase, tabela `documents`, id 549 — mesmo texto das frentes anteriores).
# ═══════════════════════════════════════════════════════════════════════════

class TestVigenciaGravames:
    """doc 549 — as três hipotecas reais (AV.03/04/05) foram baixadas por
    AV.09/AV.10/AV.12; a alienação fiduciária (R.15) não tem baixa no texto."""

    ATOS = [
        {"ato": "AV.03", "tipo": "hipoteca", "data_ato": "15 DE ABRIL DE 2008",
         "valor": "R$ 657.000,00", "partes": ["Banco do Brasil S/A Ag. Planaltina – GO"],
         "descricao": "Nos Termos da CRH nº 40/00690-5 com vencimento em "
                       "01/12/2016, protocolada sob o nº 4993."},
        {"ato": "AV.04", "tipo": "hipoteca", "data_ato": "03 DE ABRIL DE 2009",
         "partes": ["Banco do Brasil S/A Ag. de Planaltina – GO"],
         "descricao": "Nos Termos da CRPH nº 40/00956-4, com vencimento em "
                       "01/02/2017, protocolada sob o nº 5257."},
        {"ato": "AV.05", "tipo": "hipoteca", "data_ato": "15 DE SETEMBRO DE 2011",
         "partes": ["Banco do Brasil S/A Ag. de Planaltina – GO"],
         "descricao": "Nos Termos da CRPH nº 40/01511-4, com vencimento em "
                       "01/09/2019, protocolada sob o nº 6157."},
        {"ato": "AV.09", "tipo": "baixa", "data_ato": "16 DE MARÇO DE 2017",
         "altera_ato": "AV.03",
         "descricao": "Averba-se para constar a baixa da cédula Rural Pignoratícia "
                       "e Hipotecaria nº 40/00690-5, constante da AV.03, acima"},
        {"ato": "AV.10", "tipo": "baixa", "data_ato": "16 DE MARÇO DE 2017",
         "altera_ato": "AV.04",
         "descricao": "Averba-se para constar a baixa da cédula Rural Pignoratícia "
                       "e Hipotecaria nº 40/00956-4, constante da AV.04, acima"},
        {"ato": "AV.12", "tipo": "baixa", "data_ato": "21 DE AGOSTO DE 2019",
         "altera_ato": "AV.05",
         "descricao": "Averba-se para constar a baixa da cédula Rural Pignoratícia "
                       "e Hipotecaria nº 40/01511-4, constante da AV.05 acima, "
                       "ficando assim, o imóvel livre de hipoteca"},
        {"ato": "R.15", "tipo": "alienacao_fiduciaria", "data_ato": "04 DE JUNHO DE 2.025",
         "valor": "R$ 9.798.869,87", "partes": ["ITAÚ UNIBANCO S.A."]},
    ]

    def _obs(self):
        obs = observacoes_de(self.ATOS)
        aplicar_alteracoes(obs)
        derivar_vigencia(obs)
        return obs

    def test_as_tres_hipotecas_ficam_baixadas(self):
        hipotecas = [o for o in self._obs() if o.tipo == TIPO_HIPOTECA]
        assert len(hipotecas) == 3
        assert all(h.vigencia == VIGENCIA_BAIXADO for h in hipotecas)

    def test_zero_hipotecas_vigentes(self):
        """A pergunta consultável: quantos gravames deste tipo ainda valem?"""
        vigentes = [o for o in self._obs() if o.tipo == TIPO_HIPOTECA and o.vigencia == VIGENCIA_VIGENTE]
        assert vigentes == []

    def test_a_alienacao_fiduciaria_sem_baixa_fica_vigente(self):
        alienacao = next(o for o in self._obs() if o.tipo == TIPO_ALIENACAO_FIDUCIARIA)
        assert alienacao.vigencia == VIGENCIA_VIGENTE


class TestVigenciaArrendamento:
    """doc 548, AV.10 — prazo com termo final; expiração compara com a data de
    REFERÊNCIA passada por quem chama, não com `date.today()`."""

    def _obs(self):
        atos = [{
            "ato": "AV.10", "tipo": "arrendamento", "area_ha": "50",
            "partes": ["Patrícia Akemi Miaki Botega"],
            "prazo": "15 anos com inicio no dia 01/01/2013 a 01/01/2028",
        }]
        obs = observacoes_de(atos)
        aplicar_alteracoes(obs)
        return obs

    def test_vigente_para_data_de_referencia_dentro_do_prazo(self):
        obs = self._obs()
        derivar_vigencia(obs, data_referencia=date(2026, 1, 1))
        assert obs[0].vigencia == VIGENCIA_VIGENTE

    def test_expirado_para_data_de_referencia_apos_o_termo(self):
        """Mesmo prazo, data de referência diferente — é teste de REGRA, não
        de LLM: a extração roda uma vez, a pergunta "vale hoje" muda com o
        tempo sem reextrair nada."""
        obs = self._obs()
        derivar_vigencia(obs, data_referencia=date(2029, 1, 1))
        assert obs[0].vigencia == VIGENCIA_EXPIRADO


class TestVigenciaIndeterminado:
    """Silêncio nunca vira `vigente` (ADR-066) — sem data de origem e sem
    alteração encontrada, o estado é `indeterminado`."""

    def test_sem_data_e_sem_baixa_fica_indeterminado_nao_vigente(self):
        obs = observacoes_de([
            {"ato": "AV.07", "tipo": "servidao", "descricao": "servidão de passagem"},
        ])
        aplicar_alteracoes(obs)
        derivar_vigencia(obs)
        assert obs[0].vigencia == VIGENCIA_INDETERMINADO

    def test_tipo_sem_conceito_de_vigencia_fica_sem_o_campo(self):
        """`compra_venda` é evento, não estado — `vigencia` continua None, não
        um valor arbitrário."""
        obs = observacoes_de([
            {"ato": "R-11", "tipo": "compra_venda", "valor": "R$ 657.000,00"},
        ])
        aplicar_alteracoes(obs)
        derivar_vigencia(obs)
        assert obs[0].vigencia is None


class TestAditivoRetifica:
    """`aditivo` já tinha casa no vocabulário desde a Frente E ("aditivo de
    cédula/hipoteca", doc 547 AV.11/13/14) — o achado da Frente F é que o
    código nunca lia a referência dele. Retificação AMENDA, não cancela: o
    gravame retificado segue como ônus vigente."""

    ATOS = [
        {"ato": "AV.03", "tipo": "hipoteca", "data_ato": "15/04/2008",
         "valor": "R$ 657.000,00", "partes": ["Banco do Brasil"]},
        {"ato": "AV.11", "tipo": "aditivo", "altera_ato": "AV.03",
         "descricao": "aditivo à cédula da AV.03, alterando o valor da dívida"},
    ]

    def test_aditivo_marca_retificado_por_nao_baixado_por(self):
        obs = observacoes_de(self.ATOS)
        aplicar_alteracoes(obs)
        derivar_vigencia(obs)
        hipoteca = next(o for o in obs if o.ato == "AV.03")
        assert hipoteca.retificado_por == "AV.11"
        assert hipoteca.baixado_por is None
        assert hipoteca.vigencia == VIGENCIA_RETIFICADO

    def test_gravame_retificado_continua_como_onus_vigente(self):
        obs = observacoes_de(self.ATOS)
        aplicar_alteracoes(obs)
        vigentes = onus_vigentes(obs)
        assert len(vigentes) == 1
        assert vigentes[0]["ato"] == "AV.03"


class TestQuitacaoDeDividaNaoBaixaACompraEVenda:
    """Achado do GATE (LLM real, doc 549 completo): AV.14 — "para constar a
    QUITAÇÃO da dívida mencionada no R-13 acima" — é tipada `baixa` (sinônimo
    "quitação") e cita R-13 (`compra_venda`) em `altera_ato`. O texto está
    certo: o PREÇO foi pago, a venda não foi desfeita. `compra_venda` não tem
    estado de vigência (evento, não em `TIPOS_COM_VIGENCIA`) — sem a trava,
    `resumo()` mostraria "R-13 baixado por AV.14", sugerindo a venda anulada."""

    def test_quitacao_nao_marca_baixado_por_na_compra_e_venda(self):
        atos = [
            {"ato": "R-13", "tipo": "compra_venda", "data_ato": "10 DE DEZEMBRO DE 2019",
             "valor": "R$ 900.000,00", "adquirentes": ["ELODI AGROPECUÁRIA"]},
            {"ato": "AV.14", "tipo": "baixa", "altera_ato": "R-13",
             "descricao": "para constar a QUITAÇÃO da dívida mencionada no R-13 acima"},
        ]
        obs = observacoes_de(atos)
        aplicar_alteracoes(obs)
        r13 = next(o for o in obs if o.ato == "R-13")
        assert r13.baixado_por is None
        assert "baixado por" not in r13.resumo()


class TestReferenciaDeArquivamentoNaoEAlteracao:
    """doc 549 — quase toda averbação abre com "(Averbação referente a Av.XX
    Mat. YYYY)", a matrícula ANTERIOR do mesmo ato numa certidão diferente,
    não uma alteração. `aplicar_alteracoes` só lê essa referência em atos
    BAIXA/ADITIVO — uma hipoteca nunca é FONTE de alteração, então o cabeçalho
    de arquivamento do próprio ato nunca é interpretado como tal."""

    def test_hipoteca_com_cabecalho_de_arquivamento_nao_fica_baixada(self):
        atos = [
            {"ato": "AV.02", "tipo": "reserva_legal", "area_ha": "492,9252",
             "descricao": "Averbação referente a Av.09 Mat. 2007 e Av. 04 Mat. 3.669"},
            {"ato": "AV.03", "tipo": "hipoteca", "valor": "R$ 657.000,00",
             "descricao": "Averbação referente ao R-06 Mat. 2007 e Av. 05 Mat. 3.669"},
        ]
        obs = observacoes_de(atos)
        aplicar_alteracoes(obs)
        assert all(o.baixado_por is None and o.retificado_por is None for o in obs)


class TestRlVigente:
    """doc 549 — AV.02 é a averbação de Reserva Legal (492,9252ha); a RL do
    CAR citada DENTRO do georreferenciamento (AV.01, 42,8070ha) não é RL
    vigente da matrícula — é tipo errado, não coluna errada (mesma classe do
    #221, agora em outro tipo)."""

    def test_rl_vigente_e_a_reserva_legal_nao_o_georreferenciamento(self):
        atos = [
            {"ato": "AV.01", "tipo": "georreferenciamento", "area_ha": "42,8070",
             "descricao": "Dito imóvel encontra-se cadastrado no CAR-GO sob o nº "
                           "5200605-90AD5334772C4ADBB0BAB91AAD96DC4D, com sua área "
                           "de reserva legal de 42,8070ha, cadastrado em conjunto "
                           "com outras áres na Receita Federal sob o nº 6.816.752-0"},
            {"ato": "AV.02", "tipo": "reserva_legal", "area_ha": "492,9252",
             "descricao": "Procede-se a averbação da Reserva Legal desta Matricula "
                           "em conjunto com as Matriculas nº 1.224 e 1.225, com a "
                           "área total de 492,9252ha"},
        ]
        obs = observacoes_de(atos)
        rl = rl_vigente(obs)
        assert rl is not None
        assert rl.ato == "AV.02"
        assert rl.atributos["area_ha"] == "492,9252"

    def test_matricula_sem_averbacao_de_rl_nao_tem_rl_vigente(self):
        obs = observacoes_de([
            {"ato": "AV.01", "tipo": "georreferenciamento",
             "descricao": "georreferenciamento sem menção a reserva legal"},
        ])
        assert rl_vigente(obs) is None


class TestTitularidade:
    """doc 549 — cadeia real: Nascente Agro-industrial → Alexandre Augusto
    Clemente + Karina Santarosa Clemente (R-11, 2019) → ELODI AGROPECUÁRIA
    (R-13, 2019). `papel_no_ato` só quando o próprio ato distingue os dois
    lados — nunca por posição (a lição do achado `partes[0]`, ADR-065)."""

    ATOS = [
        {"ato": "R-11", "tipo": "compra_venda", "data_ato": "18 DE MARÇO DE 2019",
         "valor": "R$ 657.000,00",
         "adquirentes": ["ALEXANDRE AUGUSTO CLEMENTE", "KARINA SANTAROSA CLEMENTE"],
         "transmitentes": ["Nascente Agro-industrial Ltda"]},
        {"ato": "R-13", "tipo": "compra_venda", "data_ato": "10 DE DEZEMBRO DE 2019",
         "valor": "R$ 900.000,00",
         "adquirentes": ["ELODI AGROPECUÁRIA"],
         "transmitentes": ["ALEXANDRE AUGUSTO CLEMENTE", "KARINA SANTAROSA CLEMENTE"]},
    ]

    def test_titular_atual_e_o_adquirente_do_ato_mais_recente(self):
        atual = titular_atual(observacoes_de(self.ATOS))
        assert atual is not None
        assert atual["titulares"] == ["ELODI AGROPECUÁRIA"]
        assert atual["ato"] == "R-13"

    def test_cadeia_lista_os_quatro_titulares_com_o_ato_que_os_inscreveu(self):
        cadeia = cadeia_titularidade(observacoes_de(self.ATOS))
        nomes = {linha["nome"] for linha in cadeia}
        assert nomes == {
            "Nascente Agro-industrial Ltda", "ALEXANDRE AUGUSTO CLEMENTE",
            "KARINA SANTAROSA CLEMENTE", "ELODI AGROPECUÁRIA",
        }
        nascente = next(linha for linha in cadeia if linha["nome"] == "Nascente Agro-industrial Ltda")
        assert nascente["papel_no_ato"] == "transmitente"
        assert nascente["ato"] == "R-11"
        elodi = next(linha for linha in cadeia if linha["nome"] == "ELODI AGROPECUÁRIA")
        assert elodi["papel_no_ato"] == "adquirente"
        assert elodi["ato"] == "R-13"

    def test_sem_compra_e_venda_com_adquirente_titular_atual_e_none(self):
        obs = observacoes_de([{"ato": "AV.02", "tipo": "reserva_legal", "area_ha": "492,9252"}])
        assert titular_atual(obs) is None


class TestAtributosTemporaisNaLinhaDeStaging:
    """`data_ato`, `altera_ato` e `vigencia` sobrevivem inteiros até a linha
    de staging — o mesmo caminho que `tipo_observacao`/`atributos` já
    percorriam desde a Frente E."""

    def test_data_ato_e_altera_ato_chegam_na_linha(self):
        rows = build_staging_fields(
            "matricula",
            {"atos": [
                {"ato": "AV.09", "tipo": "baixa", "data_ato": "16 DE MARÇO DE 2017",
                 "altera_ato": "AV.03",
                 "descricao": "baixa da cédula nº 40/00690-5, constante da AV.03, acima"},
            ]},
            texto=TEXTO_549,
        )
        linha = next(r for r in rows if r.tipo_observacao == TIPO_BAIXA)
        assert linha.atributos["data_ato"] == "16 DE MARÇO DE 2017"
        assert linha.atributos["altera_ato"] == "AV.03"

    def test_vigencia_derivada_chega_na_linha(self):
        rows = build_staging_fields(
            "matricula",
            {"atos": [
                {"ato": "AV.03", "tipo": "hipoteca", "data_ato": "15 DE ABRIL DE 2008",
                 "valor": "R$ 657.000,00"},
                {"ato": "AV.09", "tipo": "baixa", "altera_ato": "AV.03",
                 "descricao": "baixa da cédula nº 40/00690-5, constante da AV.03, acima"},
            ]},
            texto=TEXTO_549,
        )
        hipoteca = next(r for r in rows if r.atributos and r.atributos.get("ato") == "AV.03")
        assert hipoteca.atributos["vigencia"] == VIGENCIA_BAIXADO
