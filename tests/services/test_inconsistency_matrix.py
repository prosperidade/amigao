"""Ficha 02 / FASE 3 — matriz de inconsistências (determinística).

Reproduz a matriz da Isis (Ficha 02 §7) com os dados do caso São Jorge a partir
de linhas de staging simuladas (objetos simples — o builder só lê atributos).
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


def _sao_jorge_rows():
    return [
        # 2 matrículas: áreas que somam 1.010,5583 + denominações distintas
        _row("matricula", "area_registrada_ha", "660,6561", matricula_hint="4.698", unidade="ha"),
        _row("matricula", "denominacao", "Fazenda São Jorge", matricula_hint="4.698"),
        _row("matricula", "area_registrada_ha", "349,9022", matricula_hint="6.776", unidade="ha"),
        _row("matricula", "denominacao", "Shangri-lá Parte 2", matricula_hint="6.776"),
        # CAR: área 1.010,7113 + lista as 2 matrículas
        _row("car", "area_declarada_ha", "1.010,7113", unidade="ha"),
        _row("car", "numero_car", "GO-5221080-A1B2C3"),
        _row("car", "matricula_listada", {"numero": "4.698"}, matricula_hint="4.698"),
        _row("car", "matricula_listada", {"numero": "6.776"}, matricula_hint="6.776"),
        # CCIR e ITR com códigos INCRA distintos; ITR sem CAR declarado
        _row("ccir", "codigo_sncr_incra", "111.111.111.111-1"),
        _row("ccir", "denominacao", "Fazenda São Jorge"),
        _row("itr", "codigo_incra", "222.222.222.222-2"),
        _row("itr", "nome_imovel", "São Jorge"),
        # RAT: pendências técnicas + acesso
        _row("rat", "situacao", "Pendente"),
        _row("rat", "pendencias_rat", [
            {"categoria": "Sobreposição com APA estadual", "detalhamento": "...", "recomendacao": "verificar APA"},
            {"categoria": "Supressões de vegetação pós-2008", "detalhamento": "...", "recomendacao": "comprovar"},
            {"categoria": "Conflito em hidrografia/APP", "detalhamento": "...", "recomendacao": "ajustar"},
            {"categoria": "Via de acesso não declarada", "detalhamento": "acesso insuficiente"},
        ]),
        # SIGEF: ausente (nenhuma linha)
    ]


def _by_item(matriz):
    return {ln["item"]: ln for ln in matriz["linhas"]}


def test_area_total_divergente_transcricao():
    res = build_matrix(_sao_jorge_rows())
    lin = _by_item(res.matriz)["area_total"]
    assert lin["situacao"] == "divergente"
    assert lin["subtipo"] == "transcricao"
    assert lin["fontes"]["soma_matriculas"] == 1010.5583
    assert lin["fontes"]["car"] == 1010.7113
    assert "0,153" in lin["acao_recomendada"]
    assert lin["destino"] == ["alertas"]


def test_denominacao_divergente():
    lin = _by_item(build_matrix(_sao_jorge_rows()).matriz)["denominacao_imovel"]
    assert lin["situacao"] == "divergente"
    assert "padronizar" in lin["acao_recomendada"].lower()


def test_codigo_incra_atencao():
    lin = _by_item(build_matrix(_sao_jorge_rows()).matriz)["codigo_incra_sncr"]
    assert lin["situacao"] == "atencao"
    assert "correspond" in lin["acao_recomendada"].lower()


def test_sigef_critico_quando_ausente():
    lin = _by_item(build_matrix(_sao_jorge_rows()).matriz)["sigef_georreferenciamento"]
    assert lin["situacao"] == "critico"
    assert lin["destino"] == ["diagnostico", "orcamento"]


def test_car_presenca_inconsistente_itr_sem_car():
    lin = _by_item(build_matrix(_sao_jorge_rows()).matriz)["car_presenca_consistencia"]
    assert lin["situacao"] == "inconsistente"
    assert "ITR" in lin["acao_recomendada"]
    # inconsistente exigindo plataforma oficial → também diagnostico + orcamento
    assert "diagnostico" in lin["destino"] and "orcamento" in lin["destino"]


def test_acesso_atencao():
    lin = _by_item(build_matrix(_sao_jorge_rows()).matriz)["acesso_imovel"]
    assert lin["situacao"] == "atencao"
    assert "coordenadas" in lin["acao_recomendada"].lower()


def test_linhas_tecnicas_critico_profundidade_tecnica():
    linhas = build_matrix(_sao_jorge_rows()).matriz["linhas"]
    tecnicas = [ln for ln in linhas if ln.get("profundidade") == "tecnica"]
    # APA + supressões + hidrografia (acesso NÃO entra como técnica)
    assert len(tecnicas) == 3
    assert all(ln["situacao"] == "critico" for ln in tecnicas)
    assert not any("acesso" in ln["label"].lower() for ln in tecnicas)


def test_staging_marcado_area_e_denominacao():
    res = build_matrix(_sao_jorge_rows())
    updates = {id(row): status for row, status in res.status_updates}
    statuses = list(updates.values())
    # matrículas (área) consistentes; CAR (área) divergente_transcricao
    assert "consistente" in statuses
    assert "divergente_transcricao" in statuses
    # nenhuma marcação de aceito/rejeitado (decisão do consultor, Fase 4)
    assert all(s in ("consistente", "divergente_transcricao", "divergente_fundo") for s in statuses)


def test_matriz_vazia_sem_staging():
    res = build_matrix([])
    assert res.matriz["linhas"] == []
    assert res.status_updates == []


# ---------------------------------------------------------------------------
# Sprint 4 — fix do bucket: N documentos do MESMO tipo são fontes distintas
# (shape do caso 13: 2 "CCIRs" completos e conflitantes na matrícula 2923).
# ---------------------------------------------------------------------------

def _row_doc(source_doc_type, field_name, value, *, document_id, matricula_hint=None, unidade=None):
    r = _row(source_doc_type, field_name, value, matricula_hint=matricula_hint, unidade=unidade)
    r.document_id = document_id
    return r


def _caso13_dois_ccirs():
    """Doc 228 (planta lida como ccir) × doc 231 (CCIR real) — ambos hint 2923."""
    return [
        _row_doc("ccir", "denominacao", "Fazenda Shangri-lá ( Parte 2)", document_id=228, matricula_hint="2923"),
        _row_doc("ccir", "area_ha", "349,9022", document_id=228, matricula_hint="2923", unidade="ha"),
        _row_doc("ccir", "codigo_sncr_incra", "950.068.390.895-4", document_id=228, matricula_hint="2923"),
        _row_doc("ccir", "denominacao", "Fazenda Sao Jorge Lote 1 B", document_id=231, matricula_hint="2923"),
        _row_doc("ccir", "area_ha", "660,6561", document_id=231, matricula_hint="2923", unidade="ha"),
        _row_doc("ccir", "codigo_sncr_incra", "000.051.123.390-9", document_id=231, matricula_hint="2923"),
    ]


def test_dois_ccirs_area_divergente_na_mesma_matricula():
    """Antes do fix: bucket único 'ccir' colapsava os 2 docs (keep-max silencioso)
    e a linha area_matricula:2923 nem existia. Agora: divergência REAL."""
    res = build_matrix(_caso13_dois_ccirs())
    lin = _by_item(res.matriz)["area_matricula:2923"]
    assert lin["situacao"] == "divergente"
    assert set(lin["fontes"].keys()) == {"ccir#228", "ccir#231"}
    assert lin["fontes"]["ccir#228"] == 349.9022
    assert lin["fontes"]["ccir#231"] == 660.6561


def test_dois_ccirs_denominacao_divergente():
    res = build_matrix(_caso13_dois_ccirs())
    lin = _by_item(res.matriz)["denominacao_imovel"]
    assert lin["situacao"] == "divergente"
    assert lin["fontes"]["ccir#228"] == "Fazenda Shangri-lá ( Parte 2)"
    assert lin["fontes"]["ccir#231"] == "Fazenda Sao Jorge Lote 1 B"
    # staging das duas denominações marcado divergente (gate do aceitar)
    updates = [(row.field_name, st) for row, st in res.status_updates]
    denom = [st for fn, st in updates if fn == "denominacao"]
    assert denom and all(s == "divergente_transcricao" for s in denom)


def test_dois_ccirs_incra_distintos_atencao():
    lin = _by_item(build_matrix(_caso13_dois_ccirs()).matriz)["codigo_incra_sncr"]
    assert lin["situacao"] == "atencao"
    assert set(lin["fontes"].keys()) == {"ccir#228", "ccir#231"}


def test_tipo_com_um_doc_mantem_chave_simples():
    """Back-compat: 1 doc por tipo → chaves/labels antigas ('ccir', não 'ccir#N')."""
    rows = [
        _row_doc("ccir", "denominacao", "Fazenda São Jorge", document_id=231),
        _row_doc("ccir", "codigo_sncr_incra", "111.111.111.111-1", document_id=231),
        _row_doc("itr", "nome_imovel", "São Jorge", document_id=234),
    ]
    res = build_matrix(rows)
    lin = _by_item(res.matriz)["denominacao_imovel"]
    assert "ccir" in lin["fontes"] and "ccir#231" not in lin["fontes"]
