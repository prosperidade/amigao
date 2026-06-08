"""Ficha 02 / FASE 3 — calibração v2 da matriz contra o STAGING REAL do caso #12.

Fonte: dump de produção do processo 12 (Fazenda São Jorge — Leonardo Ribeiro,
São João d'Aliança/GO), medido no Supabase em 2026-06-07. Este caso expôs 4
defeitos que a v1 (caso #11) não cobria — todos reproduzidos FIELMENTE abaixo a
partir dos valores reais do `extracted_field_staging`:

A. Parse decimal: a área da matrícula 4655 vinha como dict serializado
   `{"value": 349.9022, "confidence": "high"}`; a vírgula do repr do dict
   disparava o ramo PT-BR do parser → 3499022, e a soma das matrículas dava
   3.502.448 ha (metade de Goiás).
B. matricula_hint poluído: `{'value': '4655', ...}`, `MATR. 2.923 R-01`,
   `4655 (2 de 3)`, `6.776` viravam matrículas distintas / colunas-lixo.
C. Denominação com lixo: `Certidão de Embargo` (título de doc) virava denominação.
D. Recomendação cruzada: o detalhamento "Documentos" com
   "Autorização de Desmatamento" casava `supressao` (termo "desmat") e criava
   uma linha "Supressão pós-2008" com a recomendação de ACESSO.

Estes shapes são o gate de não-regressão do PR fix/matriz-v2-rag-recuperacao.
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


# Pendências reais do RAT GO-RAT-2024-002207 (doc 174/191). A 1ª é o pedido de
# documentos cujo detalhamento lista "Autorização de Desmatamento" (defeito D) e
# cuja recomendação fala de ACESSO — o cruzamento que criava a falsa "Supressão".
_PEND_REAL = [
    {"categoria": "Documentos", "atendimento": "Retificação",
     "detalhamento": ("Certidão de Inteiro Teor do imóvel rural atualizada, CPF do(s) "
                      "Proprietário(s) / Possuidor(es), Georreferenciamento (SIGEF), RG do "
                      "proprietário/posseiro, Licença Ambiental e Autorização de Desmatamento, "
                      "Identificação do proprietário / possuidor e comprovação da propriedade / posse."),
     "recomendacao": ("Retifique o CAR detalhando a descrição de acesso ao imóvel com "
                      "informações que permitam sua localização a partir de um ponto de referência conhecido.")},
    {"categoria": "Inconsistências em Ficha do imóvel", "atendimento": "Retificação",
     "detalhamento": "Dados da descrição de acesso são insuficientes para a localização do imóvel rural.",
     "recomendacao": "Retifique o CAR detalhando a descrição de acesso ao imóvel."},
    {"categoria": "Inconsistências em UC", "atendimento": "Retificação",
     "detalhamento": "Foi identificada sobreposição do imóvel em análise com uma ou mais Unidades de Conservação.",
     "recomendacao": "Forneça esclarecimentos sobre sua declaração e apresente a documentação de comprovação de propriedade/posse."},
    {"categoria": "Inconsistências em Cobertura do solo", "atendimento": "Retificação",
     "detalhamento": "Foram identificados indícios de inconsistências na cobertura do solo declarada no CAR.",
     "recomendacao": "Retifique o CAR indicando a localização dos remanescentes de vegetação nativa, área consolidada, área antropizada após 22 de julho de 2008 e pousio."},
    {"categoria": "Inconsistência Adicional", "atendimento": "Retificação",
     "detalhamento": "Existem nascentes e hidrografias não declaradas no imóvel.",
     "recomendacao": "Retifique o CAR declarando todas as drenagens existentes no imóvel ou forneça esclarecimentos."},
]


def _caso12_real_rows():
    """Reproduz o staging real do #12 (os offenders dos defeitos A–D)."""
    return [
        # --- ÁREA (defeito A + B) -----------------------------------------
        # ccir 4655 com o DICT serializado em hint E em value (o gatilho do 3,5M)
        _row("ccir", "area_ha", {"value": 349.9022, "confidence": "high"},
             matricula_hint="{'value': '4655', 'confidence': 'high'}"),
        _row("ccir", "area_ha", 349.9022, matricula_hint="4655"),
        _row("ccir", "area_ha", 349.9022, matricula_hint="MATR. 2.923"),
        _row("ccir", "area_ha", 349.9022, matricula_hint="MATR. 2.923 R-01"),
        _row("ccir", "area_ha", 660.6561, matricula_hint="2923"),
        _row("ccir", "area_ha", 349.9022, matricula_hint="6776"),
        _row("matricula", "area_registrada_ha", 660.6561, matricula_hint="4698", unidade="ha"),
        _row("matricula", "area_registrada_ha", 349.9022, matricula_hint="6.776", unidade="ha"),
        _row("matricula", "area_registrada_ha", 349.9022, matricula_hint="6776", unidade="ha"),
        _row("matricula", "numero_matricula", "6776", matricula_hint="6776"),
        _row("matricula", "numero_matricula", "4698", matricula_hint="4698"),
        _row("matricula", "numero_matricula", "6.776", matricula_hint="6.776"),
        # ITR sem matricula_hint → áreas órfãs (sem vínculo), NÃO confrontam
        _row("itr", "area_declarada_ha", 818.4),
        _row("itr", "area_declarada_ha", 477.1),
        _row("itr", "area_declarada_ha", 349.9),
        _row("itr", "area_declarada_ha", 23.1),
        _row("itr", "area_declarada_ha", 660.6),
        # SIGEF: TAD 492262 e área hint=None (sem vínculo); 4655 com fatia "(2 de 3)"
        _row("sigef", "area_georreferenciada_ha", 3.1256),
        _row("sigef", "area_georreferenciada_ha", 349.9022, matricula_hint="4655"),
        _row("sigef", "area_georreferenciada_ha", 349.9022, matricula_hint="4655 (2 de 3)"),
        _row("sigef", "area_georreferenciada_ha", 3.1256, matricula_hint="492262"),
        # CAR + RAT: área do imóvel (~1010,7 ha)
        _row("car", "area_declarada_ha", 1010.7113, unidade="ha"),
        _row("car", "area_declarada_ha", 660.1145, unidade="ha"),
        _row("car", "numero_car", "GO-5220009-3B9F4F19156B455D9EE371CAEF57623C"),
        _row("rat", "area_vetorizada_ha", 1010.7113, unidade="ha"),
        _row("rat", "area_vetorizada_ha", 1.0107113, unidade="ha"),
        # --- DENOMINAÇÃO (defeito C) --------------------------------------
        _row("sigef", "denominacao", "Certidão de Embargo", matricula_hint="492262"),
        _row("sigef", "denominacao", "Fazenda Shangri-lá", matricula_hint="4655"),
        _row("matricula", "denominacao", "Fazenda São Jorge Lote 01-C", matricula_hint="6776"),
        _row("matricula", "denominacao", "Fazenda São Jorge – Gleba 01 B", matricula_hint="4698"),
        # --- RAT pendências (defeito D) -----------------------------------
        _row("rat", "protocolo", "GO-RAT-2024-002207"),
        _row("rat", "situacao", "Pendente"),
        _row("rat", "pendencias_rat", _PEND_REAL),
        _row("rat", "pendencias_rat", _PEND_REAL),  # repetição real (dedup por tema)
    ]


def _by_item(matriz):
    return {ln["item"]: ln for ln in matriz["linhas"]}


def _all_area_values(matriz):
    """Todos os valores numéricos que aparecem nas colunas de fonte das linhas."""
    vals: list[float] = []
    for ln in matriz["linhas"]:
        for v in (ln.get("fontes") or {}).values():
            if isinstance(v, (int, float)):
                vals.append(float(v))
            elif isinstance(v, list):
                vals.extend(x for x in v if isinstance(x, (int, float)))
    return vals


# === A. Parse decimal: a "fazenda de 3,5 milhões de ha" não pode renascer ====

def test_A_nenhuma_area_implausivel():
    """Defeito A: o dict serializado não vira mais 3499022. NENHUM valor de área
    em qualquer linha passa de 100.000 ha — e como o parse foi corrigido na
    origem, nem sequer há linha de revisão por implausibilidade."""
    matriz = build_matrix(_caso12_real_rows()).matriz
    vals = _all_area_values(matriz)
    assert vals, "esperava valores de área na matriz"
    assert max(vals) < 100_000, f"área implausível sobrevivente: {max(vals)}"
    assert "area_revisao" not in _by_item(matriz), "parse corrigido → sem implausível"


def test_A_area_total_plausivel_imovel_mil():
    """A área do imóvel (CAR/RAT) entra em ~1.010,7 ha — escala plausível."""
    lin = _by_item(build_matrix(_caso12_real_rows()).matriz).get("area_total")
    assert lin is not None
    assert lin["fontes"]["soma_matriculas"] < 100_000
    assert any(abs(v - 1010.7113) < 0.01 for v in lin["fontes"].values()
               if isinstance(v, (int, float)))


# === B. matricula_hint: sem colunas-lixo =====================================

def test_B_hints_limpos_sem_dict_nem_anotacao():
    """Defeito B: as matrículas viram chaves numéricas limpas — nada de dict
    serializado, "MATR.", "R-01" ou "(2 de 3)" como coluna."""
    matriz = build_matrix(_caso12_real_rows()).matriz
    keys = matriz["fontes"] + [ln["item"] for ln in matriz["linhas"]]
    blob = " ".join(keys)
    for proibido in ("{", "'value'", "MATR", "R-01", "(2 de", "6.776"):
        assert proibido not in blob, f"hint sujo vazou na matriz: {proibido}"
    # 4655 / 2923 / 6776 / 4698 viram matrículas; suas variações poluídas COLAPSAM
    mat_keys = {k.split(":", 1)[1] for k in matriz["fontes"] if k.startswith("matricula:")}
    assert mat_keys, "esperava matrículas agrupadas"
    assert all(k.isdigit() for k in mat_keys), f"hint não-numérico: {mat_keys}"


def test_B_area_sem_vinculo_nao_confronta():
    """ITR/SIGEF sem matricula_hint → linha de atenção "sem vínculo", sem
    confrontar valores de escalas diferentes entre si."""
    lin = _by_item(build_matrix(_caso12_real_rows()).matriz).get("area_sem_vinculo")
    assert lin is not None
    assert lin["situacao"] == "atencao"


# === C. Denominação sem lixo =================================================

def test_C_denominacao_sem_titulo_de_documento():
    """Defeito C: "Certidão de Embargo" (título de doc) não aparece como
    denominação — só nomes de imóvel reais."""
    matriz = build_matrix(_caso12_real_rows()).matriz
    lin = _by_item(matriz).get("denominacao_imovel")
    assert lin is not None
    valores = " ".join(str(v) for v in lin["fontes"].values()).lower()
    assert "embargo" not in valores
    assert "certidao" not in valores and "certidão" not in valores
    assert "fazenda" in valores  # denominação real sobreviveu


# === D. Recomendação não cruza ===============================================

def test_D_sem_falsa_supressao():
    """Defeito D: o detalhamento "Documentos" com "Autorização de Desmatamento"
    NÃO vira linha técnica de supressão."""
    itens = _by_item(build_matrix(_caso12_real_rows()).matriz)
    assert "tecnica:supressao" not in itens
    # o pedido de documentos vai pra sua própria linha
    assert "documentos_solicitados" in itens


def test_D_linhas_tecnicas_recomendacao_da_propria_pendencia():
    """Cada linha técnica leva a recomendação DA SUA pendência de origem:
    cobertura→cobertura, UC→UC, hidrografia→drenagens. Nenhuma carrega a
    recomendação de acesso (o cruzamento original)."""
    itens = _by_item(build_matrix(_caso12_real_rows()).matriz)
    cob = itens.get("tecnica:cobertura")
    assert cob is not None
    assert "remanescentes" in cob["acao_recomendada"].lower()
    assert "acesso" not in cob["acao_recomendada"].lower()
    hid = itens.get("tecnica:hidrografia")
    assert hid is not None
    assert "drenagens" in hid["acao_recomendada"].lower()
    # acesso é detectado e vira a SUA linha (não some)
    assert "acesso_imovel" in itens
