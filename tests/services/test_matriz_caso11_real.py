"""Ficha 02 / FASE 3 — calibração da matriz contra o STAGING REAL do caso #11.

Fonte: dump de produção do processo 11 (Fazenda São Jorge — Leonardo Ribeiro),
extraído do Supabase em 2026-06-06. O staging real só tinha `rat` + `sigef`
(certidões/CCIR/ITR/CAR nunca chegaram à Fase 2), as linhas vinham TRIPLICADAS
(3 extrações sem dedup) e a área do RAT às vezes vinha mal-parseada
(`1.0107113` ≈ 1 ha em vez de `1010,7113`). Estes shapes estão reproduzidos fiel-
mente abaixo — é o gate de validação do PR de calibração.

Falhas de produção que este teste trava como regressão:
- área NÃO virava linha (RAT ignorado + uma só fonte de área);
- pendências: só "Cobertura" e "Acesso" viravam linha (casamento só na categoria);
- SIGEF "consistente" sem validar código/status reais.
"""

from types import SimpleNamespace

from app.services.inconsistency_matrix import build_matrix


def _row(source_doc_type, field_name, value, *, matricula_hint=None, unidade=None):
    fv = {"value": value}
    if unidade:
        fv["unidade"] = unidade
    return SimpleNamespace(
        source_doc_type=source_doc_type,
        field_name=field_name,
        field_value=fv,
        matricula_hint=matricula_hint,
        status="pendente",
    )


# pendências reais do RAT GO-RAT-2024-002207 (versão 1 — categorias genéricas)
_PEND_V1 = [
    {"categoria": "Documentos", "detalhamento": "Dados da descrição de acesso são insuficientes para a localização do imóvel rural.",
     "recomendacao": "Retifique o CAR detalhando a descrição de acesso ao imóvel."},
    {"categoria": "Unidades de Conservação", "detalhamento": "Foi identificada sobreposição do imóvel em análise com uma ou mais Unidades de Conservação.",
     "recomendacao": "Forneça esclarecimentos e apresente a documentação de comprovação de propriedade/posse."},
    {"categoria": "Cobertura do solo", "detalhamento": "Foram identificados indícios de inconsistências na cobertura do solo declarada no CAR.",
     "recomendacao": "Retifique o CAR indicando remanescentes de vegetação nativa, área consolidada, área antropizada após 22 de julho de 2008 e pousio."},
    {"categoria": "Inconsistência Adicional", "detalhamento": "Existem nascentes e hidrografias não declaradas no imóvel.",
     "recomendacao": "Retifique o CAR declarando todas as drenagens existentes no imóvel."},
]
# versão 2 — inclui pedidos de documentos + SIGEF solicitado pelo órgão
_PEND_V2 = [
    {"categoria": "Documentos", "detalhamento": "Certidão de Inteiro Teor do imóvel rural atualizada",
     "recomendacao": "Apresentar a certidão de inteiro teor."},
    {"categoria": "Documentos", "detalhamento": "Georreferenciamento (SIGEF)",
     "recomendacao": "Apresentar o georreferenciamento do imóvel."},
    {"categoria": "Inconsistências em UC", "detalhamento": "Sobreposição com Unidade de Conservação de Uso Sustentável",
     "recomendacao": "Forneça esclarecimentos."},
    {"categoria": "Inconsistências em Cobertura do solo", "detalhamento": "Inconsistência na vetorização do cadastrante",
     "recomendacao": "Retifique o CAR."},
]


def _caso11_real_rows():
    """Reproduz o staging real do #11 (rat + sigef, triplicado, área mal-parseada)."""
    return [
        # RAT — área vetorizada do IMÓVEL, com a mal-parseada (1.01) e a correta (1010,7)
        _row("rat", "area_vetorizada_ha", 1.0107113, unidade="ha"),
        _row("rat", "area_vetorizada_ha", 1010.7113, unidade="ha"),
        _row("rat", "area_vetorizada_ha", 1.0107113, unidade="ha"),
        _row("rat", "numero_car", "GO-5220009-3B9F4F19156B455D9EE371CAEF57623C"),
        _row("rat", "situacao", "Pendente"),
        _row("rat", "pendencias_rat", _PEND_V1),
        _row("rat", "pendencias_rat", _PEND_V2),
        _row("rat", "pendencias_rat", _PEND_V1),  # triplicação
        # SIGEF — só do Lote 01-C (matrícula 6776); certificação REAL (código+status)
        _row("sigef", "area_georreferenciada_ha", 349.9022, matricula_hint="6776", unidade="ha"),
        _row("sigef", "codigo_certificacao", "029231.2.0006776-55", matricula_hint="6776"),
        _row("sigef", "status_certificacao", "ativo", matricula_hint="6776"),
        _row("sigef", "denominacao", "Fazenda São Jorge Lote 01-C", matricula_hint="6776"),
        # triplicação do sigef
        _row("sigef", "area_georreferenciada_ha", 349.9022, matricula_hint="6776", unidade="ha"),
        _row("sigef", "codigo_certificacao", "029231.2.0006776-55", matricula_hint="6776"),
    ]


def _by_item(matriz):
    return {ln["item"]: ln for ln in matriz["linhas"]}


def test_area_total_atencao_vinculo_incompleto():
    """RAT (imóvel 1010,7) >> soma das matrículas conhecidas (6776 = 349,9) ⇒
    ATENÇÃO de vínculo (matrícula 1B faltante), NÃO falsa divergência."""
    matriz = build_matrix(_caso11_real_rows()).matriz
    lin = _by_item(matriz)["area_total"]
    assert lin["situacao"] == "atencao"
    # área do RAT entrou (antes era ignorada → linha não existia)
    assert lin["fontes"]["rat"] == 1010.7113  # max recupera a mal-parseada
    assert lin["fontes"]["soma_matriculas"] == 349.9022
    assert "faltante" in lin["acao_recomendada"].lower()
    assert lin["destino"] == ["alertas"]


def test_pendencias_todas_categorias_viram_linha():
    """Antes só "Cobertura" e "Acesso" saíam (casamento só na categoria).
    Agora UC + hidrografia + cobertura viram linha técnica (categorias genéricas
    casadas pelo detalhamento)."""
    matriz = build_matrix(_caso11_real_rows()).matriz
    itens = _by_item(matriz)
    tecnicas = {it for it in itens if it.startswith("tecnica:")}
    assert "tecnica:uc" in tecnicas
    assert "tecnica:hidrografia" in tecnicas
    assert "tecnica:cobertura" in tecnicas
    assert all(itens[t]["situacao"] == "critico" for t in tecnicas)
    assert all(itens[t]["profundidade"] == "tecnica" for t in tecnicas)


def test_acesso_e_documentos_separados():
    matriz = build_matrix(_caso11_real_rows()).matriz
    itens = _by_item(matriz)
    assert itens["acesso_imovel"]["situacao"] == "atencao"
    # pedidos de documentos do órgão agregados numa linha própria
    assert "documentos_solicitados" in itens
    docs = itens["documentos_solicitados"]["fontes"]["rat"]
    assert any("inteiro teor" in d.lower() for d in docs)


def test_dedup_pendencias_triplicadas():
    """3 linhas pendencias_rat (2× V1 + 1× V2) ⇒ 1 linha por tema, sem duplicar."""
    linhas = build_matrix(_caso11_real_rows()).matriz["linhas"]
    itens = [ln["item"] for ln in linhas]
    assert len(itens) == len(set(itens)), f"itens duplicados: {itens}"


def test_sigef_valida_codigo_e_status_reais():
    """SIGEF tem código (029231...) + status ativo reais → não é 'critico ausente'.
    Como o RAT pede apresentação do SIGEF, vira ATENÇÃO (não falso consistente)."""
    lin = _by_item(build_matrix(_caso11_real_rows()).matriz)["sigef_georreferenciamento"]
    assert lin["situacao"] == "atencao"
    assert "029231" in str(lin["fontes"].get("sigef", ""))


def test_denominacao_consistente_por_fonte_unica():
    """Só o SIGEF trouxe denominação (certidão/CCIR/CAR não foram extraídos):
    a matriz reporta consistente com UMA fonte — gap honesto de fonte ausente,
    não invenção de divergência."""
    matriz = build_matrix(_caso11_real_rows()).matriz
    lin = _by_item(matriz)["denominacao_imovel"]
    assert lin["situacao"] == "consistente"
    assert set(lin["fontes"].keys()) == {"sigef"}
