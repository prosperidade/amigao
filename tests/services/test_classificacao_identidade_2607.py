"""Classificação por identidade — o contrato que virou certificação (caso 15).

Medido em prod no processo 15:

* doc 329 ``2010 Contrato BIOTA PRAD.pdf`` → classificado ``sigef`` porque o
  texto continha "georreferenc". A ficha do SIGEF então rodou por cima de um
  CONTRATO e leu "Plano de Recuperação de Área Degradada (PRAD)" como
  **denominação do imóvel**.
* doc 322 ``Memorial descritivo certificado.pdf`` (cabeçalho INCRA/Sigef, um
  memorial de verdade) → classificado ``ccir``, porque continha "CCIR" no corpo.

A lição: marcador isolado diz que o documento FALA de algo; identidade é o que
diz que ele É algo.
"""

from app.services.ficha01_extraction import build_staging_fields, classify_doc_type

# Trechos REAIS (início do texto extraído em prod), encurtados.
CONTRATO_PRAD = """
Biota Projetos e Consultoria Ambiental Ltda.
CNPJ: 005.761.748/0001-20

IV. OBRIGAÇÕES DAS PARTES:
3.1 Constituem obrigações da CONTRATADA:
a) Cumprir com o objeto deste contrato de forma plena;
b) Taxa de ART;
Elaboração de projeto com georreferenciamento da área objeto do PRAD.
"""

MEMORIAL_SIGEF = """
Este Memorial Descritivo foi gerado automaticamente pelo Sigef com base nas
informações transmitidas e assinadas digitalmente pelo Responsável Técnico.
MINISTÉRIO DO DESENVOLVIMENTO AGRÁRIO
INSTITUTO NACIONAL DE COLONIZAÇÃO E REFORMA AGRÁRIA
MEMORIAL DESCRITIVO
Denominação: Fazenda Shangri-lá
Proprietário: Simone Geiss de Carvalho-ME
CCIR nº 65077819246
"""

CCIR_REAL = """
CERTIFICADO DE CADASTRO DE IMÓVEL RURAL - CCIR
INCRA — Exercício 2024
Código do Imóvel Rural: 951.048.549.371-0
Denominação do Imóvel: Fazenda São Jorge Lote 1 B
"""


class TestClassificacaoPorIdentidade:
    def test_contrato_de_prad_nao_vira_sigef(self):
        """A regressão exata do caso 15 — antes disto o retorno era 'sigef'."""
        assert classify_doc_type(CONTRATO_PRAD) == "contrato"

    def test_memorial_do_sigef_nao_vira_ccir(self):
        """Menção a CCIR no corpo não sequestra a identidade do memorial."""
        assert classify_doc_type(MEMORIAL_SIGEF) == "sigef"

    def test_ccir_de_verdade_continua_ccir(self):
        """Controle negativo: apertar o SIGEF não pode quebrar o CCIR."""
        assert classify_doc_type(CCIR_REAL) == "ccir"

    def test_georreferenciamento_sozinho_nao_classifica_sigef(self):
        """Marcador fraco isolado não decide mais nada."""
        texto = "Relatório qualquer que menciona georreferenciamento uma vez."
        assert classify_doc_type(texto) != "sigef"

    def test_classificacao_humana_existente_e_respeitada(self):
        """Regra antiga preservada: tipo específico já atribuído não é sobrescrito."""
        assert classify_doc_type(CONTRATO_PRAD, current="matricula") == "matricula"


class TestGuardDeIdentidade:
    """Rede de segurança: mesmo com o tipo errado, identidade não vaza."""

    def test_denominacao_nao_sai_de_doc_sem_marca_do_tipo(self):
        parsed = {
            "denominacao": "Plano de Recuperação de Área Degradada (PRAD)",
            "proprietario": "LEONARDO RIBEIRO",
            "area_georreferenciada_ha": "349,9022",
        }
        rows = build_staging_fields("sigef", parsed, texto=CONTRATO_PRAD)
        nomes = {r.field_name for r in rows}
        assert "denominacao" not in nomes, "denominação saiu de um contrato"
        assert "proprietario" not in nomes
        # O que não é identidade continua passando — o guard é cirúrgico.
        assert "area_georreferenciada_ha" in nomes

    def test_denominacao_sai_normalmente_de_sigef_legitimo(self):
        parsed = {"denominacao": "Fazenda Shangri-lá", "proprietario": "Simone Geiss"}
        rows = build_staging_fields("sigef", parsed, texto=MEMORIAL_SIGEF)
        nomes = {r.field_name for r in rows}
        assert "denominacao" in nomes
        assert "proprietario" in nomes

    def test_sem_texto_o_guard_nao_bloqueia(self):
        """Sem o documento em mãos não é papel do guard adivinhar."""
        parsed = {"denominacao": "Fazenda X"}
        rows = build_staging_fields("sigef", parsed)
        assert any(r.field_name == "denominacao" for r in rows)
