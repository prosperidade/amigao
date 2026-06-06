"""Fase 2 robusta (2026-06-06): classificação por conteúdo com TEXTOS REAIS do
caso São Jorge (proc. 11 prod). Fixtures = trechos verbatim do OCR real.

Bug que estes testes travam: a "Certidão de Inteiro Teor da Matrícula 6776"
(doc 165) caía em `sigef` porque continha "memorial descritivo" (seção de
georref embutida) e `sigef` era checado antes de `matricula`. Agora `matricula`
tem precedência via marcadores fortes de identidade registral.
"""

from app.services.ficha01_extraction import classify_doc_type

# --- trechos VERBATIM do OCR real (Supabase prod) --------------------------

# doc 165 — Certidão de Inteiro Teor da Matrícula 6776 (caía em sigef)
CERTIDAO_6776 = (
    "REPÚBLICA FEDERATIVA DO BRASIL Comarca de Alto Paraíso de Goiás, Distrito "
    "Judiciário de São João d'Aliança - Estado de Goiás Serviço de Registros "
    "Públicos e Tabelionatos Agda Ferreira Rodrigues da Cunha Reis - Oficial "
    "Registrador Certidão Eletrônica de Inteiro Teor da Matrícula. Oficial "
    "Registrador do Registro de Imóveis de São João d'Aliança, Estado de Goiás. "
    "CERTIFICA, que a presente é reprodução autêntica da Matrícula n° 6776, "
    "Código Nacional de Matrícula 029231.2.0006776-55. Imóvel: Fazenda "
    "Shangri-lá (Parte 2), com área de 349,9022 ha. A propriedade compreendida "
    "nos limites no memorial descritivo e mapa anexos a este termo, fica "
    "gravada como de utilização limitada."
)

# doc 141 — Certidão de Inteiro Teor da Matrícula 4698
CERTIDAO_4698 = (
    "REPÚBLICA FEDERATIVA DO BRASIL Comarca de Alto Paraíso de Goiás. Agda "
    "Ferreira Rodrigues da Cunha Reis - Oficial Registrador. Certidão Eletrônica "
    "de Inteiro Teor da Matrícula. Oficial Registrador do Registro de Imóveis de "
    "São João d'Aliança. Matrícula n° 4698, Código Nacional de Matrícula "
    "029231.2.0004698-81. Imóvel: uma parte de terras denominada \"Fazenda São "
    "Jorge – Gleba 01 B\", com a área total de 660,6561 ha."
)

# doc 164 — RAT (parecer do órgão); protocolo GO-RAT-2024-002207
RAT_REAL = (
    "Nome do Imóvel Rural: FAZENDA SÃO JORGE - GLEBA 01 B. Nome: LEONARDO "
    "RIBEIRO. CPF: 15075614825. Município: São João d'Aliança UF: GO. "
    "RELATÓRIO DE ANÁLISE TÉCNICA do CAR. Protocolo GO-RAT-2024-002207. "
    "Situação: Pendente."
)

# Recibo CAR real falhou OCR em prod (txt_len=0) — representativo do cabeçalho SICAR.
RECIBO_CAR_REPRESENTATIVO = (
    "RECIBO DE INSCRIÇÃO no Cadastro Ambiental Rural - CAR. SICAR. "
    "Número do recibo: GO-5220009-3B9F... Área do imóvel: 1.010,7113 ha."
)


def test_certidao_6776_classifica_matricula_nao_sigef():
    """O bug central: certidão com 'memorial descritivo' → matricula, não sigef."""
    assert "memorial descritivo" in CERTIDAO_6776.lower()  # o gatilho do bug existe
    assert classify_doc_type(CERTIDAO_6776) == "matricula"


def test_certidao_4698_classifica_matricula():
    assert classify_doc_type(CERTIDAO_4698) == "matricula"


def test_rat_classifica_rat():
    assert classify_doc_type(RAT_REAL) == "rat"


def test_recibo_car_classifica_car():
    assert classify_doc_type(RECIBO_CAR_REPRESENTATIVO) == "car"


def test_sigef_puro_continua_sigef():
    """Memorial SIGEF avulso (sem identidade registral) continua sigef."""
    sigef_puro = (
        "MEMORIAL DESCRITIVO. Imóvel certificado pelo SIGEF/INCRA. "
        "Georreferenciamento. Vértices: inicia-se no vértice ZNXA-V-203. "
        "Certificação do imóvel."
    )
    assert classify_doc_type(sigef_puro) == "sigef"


def test_respeita_doc_type_humano_ja_setado():
    """Se o consultor/intake já marcou um tipo específico, não sobrescreve."""
    assert classify_doc_type("texto qualquer", current="ccir") == "ccir"
    assert classify_doc_type(CERTIDAO_4698, current="itr") == "itr"
