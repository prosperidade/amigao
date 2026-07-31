"""Documento novo entra no diagnóstico (validação Isis 30/07 — item incremental).

O gargalo do fluxo real: ela subiu **dois relatórios analíticos** na E4
(``relatorio_tecnico_juridico_fazenda_sao_jorge.pdf`` e
``relatorio_ampliado_defesa_car_fazenda_sao_jorge.docx``), re-rodou o
diagnóstico, e nada foi incorporado.

Medição — não era filtro, cache nem ordem de execução: ``_load_process_data``
levava ao prompt apenas ``{id, document_type, ocr_status, review_required}``.
**Nem uma linha do conteúdo.** Os canais existentes eram estruturados (campos
cadastrais via staging; fatos de auto de infração) e texto corrido de
parecer/relatório não se encaixa em nenhum — documento de tipo livre não tinha
por onde chegar.

Segundo achado, do mesmo caso: o ``.docx`` ficou em ``ocr_status='pending'`` com
``extracted_text`` nulo desde o upload. Ele precisa aparecer MARCADO, não sumir.
"""

from __future__ import annotations

import pytest

from app.agents.base import AgentContext
from app.agents.diagnostico import DiagnosticoAgent
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant


@pytest.fixture
def agente(db_session):
    tenant = Tenant(name="Doc Novo")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="T", email=f"dn{tenant.id}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, title="Caso 15",
                   process_type="car", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()

    def _doc(nome, texto, *, ocr=OcrStatus.done, tipo=None):
        d = Document(
            tenant_id=tenant.id, process_id=proc.id, original_file_name=nome,
            filename=nome, content_type="application/pdf",
            storage_key=f"dn/{tenant.id}/{nome}", document_type=tipo,
            ocr_status=ocr, extracted_text=texto,
        )
        db_session.add(d)
        db_session.flush()
        return d

    ctx = AgentContext(tenant_id=tenant.id, user_id=None, process_id=proc.id,
                       session=db_session, metadata={})
    return DiagnosticoAgent(ctx), _doc, db_session


def test_relatorio_analitico_novo_chega_ao_contexto_com_conteudo(agente):
    ag, _doc, _db = agente
    antigo = _doc("matricula_6776.pdf", "Certidão de matrícula nº 6.776…", tipo="matricula")
    novo = _doc(
        "relatorio_tecnico_juridico_fazenda_sao_jorge.pdf",
        "RELATÓRIO TÉCNICO-JURÍDICO. Conclusão: a retificação do CAR das "
        "matrículas 4698 e 6776 foi feita de forma incorreta e precisa ser "
        "refeita antes da defesa administrativa.",
        tipo="rat",
    )

    documentos = ag._load_process_data()["documents"]
    por_id = {d["id"]: d for d in documentos}

    # O que faltava: o CONTEÚDO do documento novo no contexto.
    assert "RELATÓRIO TÉCNICO-JURÍDICO" in por_id[novo.id]["trecho"]
    assert "retificação do CAR" in por_id[novo.id]["trecho"]
    # E o nome do arquivo, para o LLM poder nomear a fonte.
    assert por_id[novo.id]["nome_arquivo"] == "relatorio_tecnico_juridico_fazenda_sao_jorge.pdf"
    # O documento antigo continua presente — nada é substituído.
    assert "Certidão de matrícula" in por_id[antigo.id]["trecho"]
    # Mais recente primeiro: o doc que motivou re-rodar não pode ficar no fim.
    assert documentos[0]["id"] == novo.id


def test_documento_sem_ocr_aparece_marcado_e_nao_some(agente):
    """O `.docx` do caso 15 estava em `pending` desde o upload."""
    ag, _doc, _db = agente
    docx = _doc(
        "relatorio_ampliado_defesa_car_fazenda_sao_jorge.docx", None,
        ocr=OcrStatus.pending,
    )
    documentos = ag._load_process_data()["documents"]
    item = next(d for d in documentos if d["id"] == docx.id)

    assert item["sem_leitura"] is True
    assert "SEM texto extraído" in item["nota"]
    assert "trecho" not in item
    # Silenciar faria o diagnóstico parecer completo estando cego (P12).
    assert item["nome_arquivo"].endswith(".docx")


def test_teto_de_contexto_e_respeitado_e_a_omissao_e_declarada(agente, monkeypatch):
    ag, _doc, _db = agente
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "DIAGNOSTICO_DOC_TRECHO_CHARS", 500)
    monkeypatch.setattr(config_mod.settings, "DIAGNOSTICO_DOCS_TRECHO_TOTAL_CHARS", 500)

    velho = _doc("antigo.pdf", "A" * 5_000)
    recente = _doc("recente.pdf", "B" * 5_000)

    documentos = ag._load_process_data()["documents"]
    por_id = {d["id"]: d for d in documentos}

    # O mais recente é servido; o teto global corta o antigo — e diz que cortou.
    assert por_id[recente.id]["trecho"] == "B" * 500
    assert por_id[recente.id]["trecho_truncado"] is True
    assert por_id[velho.id]["trecho_omitido"] is True
    assert "limite de contexto" in por_id[velho.id]["nota"]
    # Nenhum documento desaparece da lista.
    assert len(documentos) == 2
