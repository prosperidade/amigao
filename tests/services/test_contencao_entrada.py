"""Contenção da entrada (ADR-064) — âncora, janela, número registral, auditoria.

Os casos vêm da confirmação da entrada de 09/09
(`docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md`): valores literais medidos
nos documentos da ELODI, não exemplos inventados.
"""

from __future__ import annotations

import pytest

from app.services.area_registral import (
    normalizar_area_registral,
    parece_notacao_registral,
    parse_extenso_area,
)
from app.services.extraction_window import Fatia, fatiar, mesclar
from app.services.ficha01_extraction import (
    MOTIVO_OCR_ILEGIVEL,
    MOTIVO_SEM_ANCORA,
    build_staging_fields,
    texto_sem_conteudo_legivel,
)
from app.services.field_validators import check_format
from app.services.inconsistency_matrix import parse_area_ha
from app.services.text_anchor import TextoIndexado, ancorar_composto

# Trecho VERBATIM do doc 549 (matrícula 3.673), AV.01, char 10.760 do original.
TEXTO_549 = (
    "AV.01 MAT. 3.673 - Dito imóvel encontra-se cadastrado no CAR-GO sob o nº "
    "5200605-90AD5334772C4ADBB0BAB91AAD96DC4D, com sua área de reserva legal de "
    "42,8070ha, cadastrado em conjunto com outras áres na Receita Federal sob o nº "
    "6.816.752-0, e no INCRA sob o nº 950.041.396-737-1, conforme CCIR de nº "
    '02031617154. IMÓVEL: UMA GLEBA DE TERRAS, situada na Fazenda "POSSE OU '
    'PORCOS- GLEBA 4", com área de 212,3553ha.'
)

# Trecho VERBATIM do doc 547 (matrícula 3.181), abertura.
TEXTO_547_ABERTURA = (
    "MATRICULA Nº 3.181- Data - 01 de Outubro de 2013 - IMÓVEL: UMA GLEBA DE TERRAS, "
    'situada na "FAZENDA RETIRO DOS OLHOS D\'AGUA- QUINHÃO 1, município de Alto '
    "Paraíso de Goiás, com área de 926,36.54ha(novecentos e vinte e seis hectares, "
    "trinta e seis ares e cinquenta e quatro centiares)"
)


# ---------------------------------------------------------------------------
# Contenção 1 — âncora no texto
# ---------------------------------------------------------------------------

class TestAncora:
    def test_valor_do_documento_ancora_com_posicao(self):
        idx = TextoIndexado(TEXTO_549)
        ancora = idx.buscar("6.816.752-0")
        assert ancora is not None
        assert TEXTO_549[ancora.pos:ancora.pos + 11] == "6.816.752-0"
        assert ancora.metodo == "digitos"
        assert "6.816.752-0" in ancora.trecho

    def test_exemplo_do_prompt_nao_ancora(self):
        """N1: `6.442.022-1` é o exemplo escrito no prompt, não está no doc 549."""
        assert "6.442.022" not in TEXTO_549
        assert TextoIndexado(TEXTO_549).buscar("6.442.022-1") is None

    def test_busca_por_digitos_tolera_pontuacao_diferente(self):
        idx = TextoIndexado(TEXTO_549)
        assert idx.buscar("6816752-0") is not None
        assert idx.buscar("6.816.752 - 0") is not None

    def test_busca_por_texto_tolera_acento_e_pontuacao(self):
        idx = TextoIndexado(TEXTO_549)
        # O documento escreve `PORCOS- GLEBA`; o modelo devolve `PORCOS - Gleba`.
        assert idx.buscar('Fazenda "Posse ou Porcos - Gleba 4"') is not None

    def test_valor_curto_e_nao_verificavel_nao_ausente(self):
        """`GO` não prova nada em nenhum dos eixos — a busca não se aplica."""
        idx = TextoIndexado(TEXTO_549)
        assert idx.valor_e_verificavel("GO") is False
        assert idx.valor_e_verificavel("Goiás") is True

    def test_valor_sem_ancora_vira_linha_visivel_sem_destino(self):
        parsed = {
            "numero_matricula": "3.673",
            "nirf_cib": "6.442.022-1",        # o exemplo do prompt
            "denominacao": "Fazenda Inventada",
            "confidence": {"nirf_cib": "high", "denominacao": "high"},
        }
        linhas = build_staging_fields("matricula", parsed, texto=TEXTO_549)
        por_campo = {f.field_name: f for f in linhas}

        barrada = por_campo["nirf_cib"]
        assert barrada.field_value["sem_ancora"] is True
        assert barrada.field_value["motivo"] == MOTIVO_SEM_ANCORA
        assert barrada.field_value["value"] == "6.442.022-1"  # bruto preservado
        assert barrada.confidence == "low"
        # Sem destino: não pousa na base nem que o consultor aceite.
        assert barrada.target_entity is None
        assert barrada.target_field is None

        assert por_campo["denominacao"].field_value["sem_ancora"] is True
        # O que ESTÁ no texto segue normal, com a posição.
        ok = por_campo["numero_matricula"]
        assert not ok.field_value.get("sem_ancora")
        assert ok.target_entity == "matricula"
        assert ok.field_value["ancora"]["pos"] >= 0

    def test_nirf_verdadeiro_entra_com_destino(self):
        parsed = {"nirf_cib": "6.816.752-0", "confidence": {"nirf_cib": "high"}}
        linha = build_staging_fields("matricula", parsed, texto=TEXTO_549)[0]
        assert not linha.field_value.get("sem_ancora")
        assert linha.target_entity == "matricula"
        assert linha.target_field == "nirf_cib"
        assert linha.field_value["ancora"]["metodo"] == "digitos"

    def test_sem_texto_o_gate_nao_julga(self):
        """Mesma regra do guard de identidade: sem o documento, não bloqueia."""
        parsed = {"nirf_cib": "6.442.022-1", "confidence": {}}
        linha = build_staging_fields("matricula", parsed, texto=None)[0]
        assert not linha.field_value.get("sem_ancora")
        assert linha.target_entity == "matricula"

    def test_composto_informa_cobertura_e_nao_barra(self):
        """Fronteira declarada: ônus/averbação são redigidos, não literais."""
        onus = [{"tipo": "Hipoteca", "credor": "ITAÚ UNIBANCO S.A.",
                 "valor": "R$ 9.798.869,87"}]
        cobertura = ancorar_composto(onus, TextoIndexado(TEXTO_549))
        assert cobertura["escopo"] == "composto"
        assert cobertura["ancoradas"] == 0
        assert "[0].credor" in cobertura["sem_ancora"]

        linhas = build_staging_fields(
            "matricula", {"onus": onus, "confidence": {}}, texto=TEXTO_549
        )
        assert linhas[0].target_entity == "matricula"       # não é barrado
        assert linhas[0].field_value["ancora"]["escopo"] == "composto"


# ---------------------------------------------------------------------------
# Contenção 2 — janela completa
# ---------------------------------------------------------------------------

class TestJanela:
    def test_documento_curto_continua_uma_chamada(self):
        assert len(fatiar("x" * 29_854, chunk_chars=45_000,
                          overlap_chars=2_000, max_chunks=8)) == 1

    def test_documento_de_82k_alcanca_o_char_53775(self):
        """Doc 547: o NIRF real está no char 53.775, fora da janela de 30.000."""
        fatias = fatiar("x" * 82_117, chunk_chars=45_000,
                        overlap_chars=2_000, max_chunks=8)
        assert len(fatias) == 2
        assert any(f.inicio <= 53_775 < f.fim for f in fatias)
        assert fatias[-1].fim == 82_117

    def test_sobreposicao_cobre_a_emenda(self):
        fatias = fatiar("x" * 90_000, chunk_chars=45_000,
                        overlap_chars=2_000, max_chunks=8)
        assert fatias[1].inicio < fatias[0].fim

    def test_teto_de_fatias_nao_estoura_e_reporta(self):
        fatias = fatiar("x" * 500_000, chunk_chars=45_000,
                        overlap_chars=2_000, max_chunks=3)
        assert len(fatias) == 3
        assert fatias[-1].fim < 500_000  # cobertura parcial, quem chama sinaliza

    def test_mesclagem_prefere_quem_passa_no_formato(self):
        """Doc 547: código INCRA do confrontante (fatia 0) × NIRF real (fatia 1)."""
        def validar(campo, valor):
            return check_format(campo, valor)

        r = mesclar(
            [
                (Fatia(0, 0, 45_000),
                 {"nirf_cib": "050.041.396.737-1", "confidence": {"nirf_cib": "high"}}),
                (Fatia(1, 43_000, 82_117),
                 {"nirf_cib": "2.974.457-1", "confidence": {"nirf_cib": "medium"}}),
            ],
            validar=validar,
        )
        assert r.parsed["nirf_cib"] == "2.974.457-1"
        assert r.origem["nirf_cib"] == 1
        assert r.preteridos["nirf_cib"] == ["050.041.396.737-1"]

    def test_mesclagem_desempata_por_confianca_depois_por_ordem(self):
        r = mesclar([
            (Fatia(0, 0, 10), {"cartorio": "CRI A", "confidence": {"cartorio": "low"}}),
            (Fatia(1, 8, 20), {"cartorio": "CRI B", "confidence": {"cartorio": "high"}}),
        ])
        assert r.parsed["cartorio"] == "CRI B"

    def test_mesclagem_de_listas_concatena_sem_repetir(self):
        r = mesclar([
            (Fatia(0, 0, 10), {"matriculas": [{"numero": "3181"}]}),
            (Fatia(1, 8, 20), {"matriculas": [{"numero": "3181"}, {"numero": "3313"}]}),
        ])
        assert r.parsed["matriculas"] == [{"numero": "3181"}, {"numero": "3313"}]


# ---------------------------------------------------------------------------
# Contenção 3 — número registral por regra
# ---------------------------------------------------------------------------

class TestNumeroRegistral:
    @pytest.mark.parametrize("literal,esperado", [
        ("926,36.54", 926.3654),      # doc 547 — era 92.636,54
        ("725,46.63", 725.4663),      # doc 548 — era 72.546,63
        ("1.234,05.09", 1234.0509),   # com ponto de milhar nos hectares
    ])
    def test_notacao_registral_decodificada(self, literal, esperado):
        assert parse_area_ha(literal) == pytest.approx(esperado)

    @pytest.mark.parametrize("literal,esperado", [
        ("212,3553", 212.3553),       # doc 549 — NÃO é a notação antiga
        ("2.180,8267", 2180.8267),    # doc 546 (CAR, área gráfica)
        ("2180.3923", 2180.3923),     # doc 546 (CAR, área documental)
        ("316,2053", 316.2053),       # doc 550
        ("1.010,7113", 1010.7113),
    ])
    def test_numeros_normais_ficam_intactos(self, literal, esperado):
        assert parse_area_ha(literal) == pytest.approx(esperado)
        assert parece_notacao_registral(literal) is False

    def test_m2_continua_convertendo(self):
        assert parse_area_ha("3.502.445,851", "m²") == pytest.approx(350.2445851)

    def test_extenso_do_documento_confirma_a_regra(self):
        assert parse_extenso_area(TEXTO_547_ABERTURA) == pytest.approx(926.3654)
        area = normalizar_area_registral("926,36.54", TEXTO_547_ABERTURA)
        assert area.metodo == "notacao_ha_a_ca+extenso"
        assert area.extenso_confere is True
        assert area.hectares, area.ares == (926, 36)

    def test_extenso_divergente_e_sinalizado_nao_escolhido(self):
        area = normalizar_area_registral("926,36.54", "926,36.54ha(novecentos hectares)")
        assert area.valor_ha == pytest.approx(926.3654)   # a REGRA decide
        assert area.extenso_confere is False              # e o desacordo aparece

    def test_extenso_exige_o_rotulo_hectares(self):
        assert parse_extenso_area("pelo prazo de quinze anos") is None

    def test_check_format_reprova_area_fora_da_ordem_de_grandeza(self):
        """`92636.54` era aprovado como área — 100× o real, com status aceito."""
        assert check_format("area_registrada_ha", "150000") is False
        assert check_format("area_registrada_ha", "349,9022") is True

    def test_staging_guarda_bruto_e_normalizado_com_metodo(self):
        parsed = {"area_registrada_ha": "926,36.54",
                  "confidence": {"area_registrada_ha": "high"}}
        linha = build_staging_fields(
            "matricula", parsed, texto=TEXTO_547_ABERTURA)[0]
        fv = linha.field_value
        assert fv["value"] == "926,36.54"                  # bruto NUNCA reescrito
        assert fv["normalizado_ha"] == pytest.approx(926.3654)
        assert fv["metodo_normalizacao"] == "notacao_ha_a_ca+extenso"
        assert fv["extenso_confere"] is True


# ---------------------------------------------------------------------------
# N4 — a nota de status pela causa certa
# ---------------------------------------------------------------------------

class TestTextoIlegivel:
    def test_cnh_e_do_representante_e_ilegivel(self):
        """Doc 551: 444 chars de boilerplate de assinatura, nenhum dado."""
        cnh_e = (
            "QR-CODE Documento assinado com certificado digital em conformidade com "
            "a Medida Provisória nº 2200-2/2001 REPÚBLICA FEDERATIVA DO BRASIL "
            "MINISTÉRIO DOS TRANSPORTES SECRETARIA NACIONAL DE TRÂNSITO - SENATRAN"
        )
        assert texto_sem_conteudo_legivel(cnh_e) is True
        assert "OCR" in MOTIVO_OCR_ILEGIVEL

    def test_rg_da_valeria_e_legivel(self):
        """Doc 545: 849 chars, com número de registro e CPF — foi extraído."""
        rg = (
            "PROIBIDO PLASTIFICAR 2715425388 CARTEIRA NACIONAL DE HABILITAÇÃO "
            "NOME E SOBRENOME VALERIA RUIZ CPF 587.049.731-00"
        )
        assert texto_sem_conteudo_legivel(rg) is False

    def test_documento_curto_so_com_cpf_formatado_e_legivel(self):
        assert texto_sem_conteudo_legivel("Ficha. CPF 587.049.731-00.") is False

    def test_texto_vazio_e_ilegivel(self):
        assert texto_sem_conteudo_legivel("") is True
        assert texto_sem_conteudo_legivel(None) is True
