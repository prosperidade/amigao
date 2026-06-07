"""Rastreabilidade "nenhuma afirmação sem fonte" (validação 06/06) — contrato.

Garante que os campos de fonte são ADITIVOS (payloads antigos seguem válidos) e
que a matriz expõe, por linha, as fontes que participaram (doc + valor).
"""

from types import SimpleNamespace

from app.schemas.stage_output import (
    Afirmacao,
    DiagnosticoPreliminarContent,
    Divergencia,
    Etapa,
    Source,
    SourceRef,
)
from app.services.inconsistency_matrix import build_matrix

# --- contrato do SourceRef / Afirmacao -------------------------------------

def test_sourceref_e_afirmacao():
    sr = SourceRef(tipo="documento", ref="165", descricao="Certidão 6776", valor="349,9022")
    assert sr.tipo == "documento" and sr.sem_fonte is False
    sem = SourceRef(tipo="sem_fonte", sem_fonte=True, descricao="sem fonte identificada")
    assert sem.sem_fonte is True
    af = Afirmacao(texto="houve supressão", categoria="passivo", fontes=[sr])
    assert af.fontes[0].ref == "165"


# --- aditividade: payloads ANTIGOS continuam válidos -----------------------

def test_divergencia_aceita_sem_sources():
    d = Divergencia(tema="área", divergencia="x", impacto="y")
    assert d.sources == []  # default, não quebra payload antigo


def test_etapa_aceita_sem_sources_e_com_prazo_fonte():
    e = Etapa(ordem=1, titulo="Protocolar", prazo_estimado_dias=30)
    assert e.sources == [] and e.prazo_fonte is None
    e2 = Etapa(ordem=2, titulo="x", prazo_estimado_dias=10, prazo_fonte="estimativa_profissional",
               sources=[SourceRef(tipo="sem_fonte", sem_fonte=True)])
    assert e2.prazo_fonte == "estimativa_profissional"


def test_diagnostico_content_aditivo():
    # payload "antigo" (sem afirmacoes) valida; afirmacoes default vazio
    base = DiagnosticoPreliminarContent(
        content="diag", sources=[Source(type="document", ref="d1")],
        hipoteses=["passivo X"], checklist_documental=["ação Y"],
    )
    assert base.afirmacoes == []
    # payload novo com afirmacoes + sources em divergencia/risco
    rich = DiagnosticoPreliminarContent(
        content="diag", sources=[Source(type="document", ref="d1")],
        afirmacoes=[Afirmacao(texto="houve supressão",
                              fontes=[SourceRef(tipo="rat", ref="GO-RAT-2024-002207")])],
        divergencias=[Divergencia(tema="área", divergencia="x", impacto="y",
                                  sources=[SourceRef(tipo="documento", ref="165")])],
    )
    assert rich.afirmacoes[0].fontes[0].tipo == "rat"
    assert rich.divergencias[0].sources[0].ref == "165"


# --- matriz: fontes_detalhe por linha (doc + valor) ------------------------

def _row(source_doc_type, field_name, value, *, matricula_hint=None, document_id=None):
    return SimpleNamespace(
        source_doc_type=source_doc_type, field_name=field_name,
        field_value={"value": value}, matricula_hint=matricula_hint,
        status="pendente", document_id=document_id,
    )


def test_matriz_expoe_fontes_detalhe_com_documento():
    rows = [
        _row("matricula", "denominacao", "Gleba 01 B", matricula_hint="4698", document_id=141),
        _row("matricula", "denominacao", "Shangri-lá", matricula_hint="6776", document_id=165),
    ]
    matriz = build_matrix(rows).matriz
    denom = [ln for ln in matriz["linhas"] if ln["item"] == "denominacao_imovel"][0]
    # toda linha tem fontes_detalhe (lista de {fonte, tipo, ...})
    assert denom["fontes_detalhe"], "linha sem fontes_detalhe"
    docs = {f.get("document_id") for f in denom["fontes_detalhe"]}
    assert 141 in docs and 165 in docs  # cita os documentos específicos
    assert all(f["tipo"] in ("documento", "matriz", "rat") for f in denom["fontes_detalhe"])
    # `fontes` (dict antigo) permanece intacto
    assert isinstance(denom["fontes"], dict)


def test_matriz_linha_tecnica_referencia_rat():
    rows = [
        _row("rat", "protocolo", "GO-RAT-2024-002207", document_id=164),
        _row("rat", "pendencias_rat", [
            {"categoria": "Unidades de Conservação",
             "detalhamento": "sobreposição com UC", "recomendacao": "esclarecer"},
        ], document_id=164),
    ]
    matriz = build_matrix(rows).matriz
    tec = [ln for ln in matriz["linhas"] if ln["item"].startswith("tecnica:")][0]
    fd = tec["fontes_detalhe"]
    assert any(f.get("tipo") == "rat" and f.get("protocolo") == "GO-RAT-2024-002207" for f in fd)
