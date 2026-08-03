"""A reunião chega ao diagnóstico (dívida #103 · ADR-060).

Este é o teste que justifica a modelagem inteira. A escolha de ADR-060 — "o áudio
é um documento cujo texto é a transcrição" — só vale a pena se o texto herdar de
graça o que documento já tem: entrar no contexto do diagnóstico, com o `id` que
transforma a citação em fonte clicável.

Se um dia alguém trocar a transcrição por uma entidade paralela (`AudioTranscript`
com tabela própria), este teste quebra — e é para quebrar mesmo.
"""

from __future__ import annotations

import pytest

from app.agents.base import AgentContext
from app.agents.diagnostico import DiagnosticoAgent
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.services.audio_files import TRANSCRICAO_ORIGEM_LABEL, marcar_origem

TRANSCRICAO = marcar_origem(
    "Consultor: e o CAR do lote 1-C, foi retificado? "
    "Cliente: foi, mas o técnico anterior fez errado. Ele mandou o "
    "shapefile da fazenda inteira. Vou te mandar o recibo do CAR e o ITR "
    "até sexta-feira.",
    nome_arquivo="reuniao-2026-08-03.m4a",
)


@pytest.fixture
def cenario(db_session):
    tenant = Tenant(name="Transcrição no diagnóstico")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(
        tenant_id=tenant.id, full_name="Cliente", email=f"tr{tenant.id}@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add(cli)
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Caso com reunião",
        process_type="car", status=ProcessStatus.triagem,
    )
    db_session.add(proc)
    db_session.flush()

    def _doc(nome, texto, *, content_type="application/pdf", tipo=None,
             ocr=OcrStatus.done):
        d = Document(
            tenant_id=tenant.id, process_id=proc.id, original_file_name=nome,
            filename=nome, content_type=content_type,
            storage_key=f"tr/{tenant.id}/{nome}", document_type=tipo,
            ocr_status=ocr, extracted_text=texto,
        )
        db_session.add(d)
        db_session.flush()
        return d

    ctx = AgentContext(
        tenant_id=tenant.id, user_id=None, process_id=proc.id,
        session=db_session, metadata={},
    )
    return DiagnosticoAgent(ctx), _doc


def test_transcricao_entra_no_contexto_do_diagnostico_com_conteudo(cenario):
    """O que o cliente contou na reunião passa a existir para a análise.

    Antes desta frente, o áudio ficava anexado ao caso e o diagnóstico rodava sem
    saber que o cliente já tinha dito que o CAR foi retificado errado.
    """
    ag, _doc = cenario
    audio = _doc(
        "reuniao-2026-08-03.m4a", TRANSCRICAO,
        content_type="audio/mp4", tipo="audio_entrevista",
    )

    documentos = ag._load_process_data()["documents"]
    por_id = {d["id"]: d for d in documentos}

    assert audio.id in por_id, "a transcrição não chegou ao contexto do diagnóstico"
    trecho = por_id[audio.id]["trecho"]
    assert "o técnico anterior fez errado" in trecho
    assert "recibo do CAR e o ITR" in trecho
    # A ORIGEM viaja no próprio texto: o LLM sabe que isso foi DITO, não escrito
    # num documento oficial. Peso probatório diferente.
    assert TRANSCRICAO_ORIGEM_LABEL in trecho


def test_transcricao_carrega_o_id_que_vira_fonte_clicavel(cenario):
    """Princípio 11 (ADR-035): nenhuma afirmação sem fonte.

    O `id` no contexto é o que permite ao LLM citar "doc. N" e a UI transformar
    isso em link — inclusive quando a fonte é uma reunião.
    """
    ag, _doc = cenario
    audio = _doc(
        "reuniao-2026-08-03.m4a", TRANSCRICAO,
        content_type="audio/mp4", tipo="audio_entrevista",
    )

    documentos = ag._load_process_data()["documents"]
    item = next(d for d in documentos if d["id"] == audio.id)

    assert item["nome_arquivo"] == "reuniao-2026-08-03.m4a"
    assert item["document_type"] == "audio_entrevista"
    assert item.get("sem_leitura") is None


def test_audio_ainda_sem_transcricao_aparece_marcado_nao_some(cenario):
    """P12: nenhum documento mudo.

    Áudio em transcrição não pode desaparecer do contexto — o diagnóstico ficaria
    parecendo completo estando cego para a reunião.
    """
    ag, _doc = cenario
    audio = _doc(
        "reuniao-em-processamento.m4a", None,
        content_type="audio/mp4", tipo="audio_entrevista", ocr=OcrStatus.processing,
    )

    documentos = ag._load_process_data()["documents"]
    item = next(d for d in documentos if d["id"] == audio.id)

    assert item["sem_leitura"] is True
    assert "SEM texto extraído" in item["nota"]
