"""Frente L — o `except` que grava numa sessão envenenada.

A Frente K mediu a primeira ocorrência (o socorro da consolidação morria de
`PendingRollbackError` antes de socorrer). Esta suíte prova a correção nos
pontos que a varredura da L encontrou: o `try` derruba a transação DE VERDADE
— byte NUL vindo do texto de um PDF, divisão por zero no banco — e o teste
cobra que o desfecho da falha chegue à linha.

Sem a correção cada um destes testes falha no mesmo ponto: o carimbo de falha
nunca é gravado (o documento fica "processing"/"running" para sempre) e o erro
que sobe é o `PendingRollbackError` genérico no lugar da causa.
"""

from __future__ import annotations

import types

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, InternalError, PendingRollbackError
from sqlalchemy.orm import sessionmaker

import app.workers.ai_tasks as ai_tasks
from app.models.ai_job import AIJob, AIJobStatus
from app.models.client import Client, ClientStatus, ClientType
from app.models.legislation import LegislationDocument
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.services.legislation_service import ingest_legislation_document

# Texto com byte NUL — o que um PDF real entrega quando a camada de texto está
# corrompida. Postgres não aceita NUL em coluna text: o flush cai.
TEXTO_COM_NUL = "Art. 1 Fica instituido\x00 o regime de que trata esta Lei."


@pytest.fixture
def db_session(db_engine):
    """Sobrepõe o `db_session` do conftest SÓ neste módulo.

    O fixture compartilhado faz `sessionmaker(bind=connection)`, e o default do
    SQLAlchemy 2 nesse arranjo é `join_transaction_mode="rollback_only"`: um
    `session.rollback()` desfaz a transação EXTERNA do teste inteiro, apagando
    até as linhas já commitadas. Como é exatamente o `rollback()` que está sob
    teste aqui, o fixture compartilhado mediria outra coisa — as linhas somem e
    o socorro acha que a linha "não existe mais", que não é o que acontece em
    produção (lá a sessão do worker é dona da própria transação).

    `create_savepoint` é o modo que a documentação do SQLAlchemy recomenda para
    esse padrão de fixture, e reproduz a semântica real: o rollback desfaz o
    que veio depois do último commit, e só isso.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


class _SessaoSemFechar:
    """`SessionLocal` do worker apontando para a sessão transacional do teste.

    Diferente do wrapper das outras suítes, este NÃO neutraliza `rollback()` —
    é justamente o rollback que está sob teste. Na sessão do pytest o rollback
    volta ao SAVEPOINT aberto no início, então só desfaz o que veio depois do
    último `commit()` — que é a semântica de produção.
    """

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def close(self) -> None:
        pass


@pytest.fixture
def semeado(db_session):
    tenant = Tenant(name="Frente L")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="frente.l@example.com",
        full_name="Frente L",
        hashed_password="x" * 60,
        tenant_id=tenant.id,
        is_active=True,
    )
    cliente = Client(
        tenant_id=tenant.id,
        full_name="Cliente Frente L",
        email="cli.frente.l@example.com",
        client_type=ClientType.pf,
        status=ClientStatus.active,
    )
    db_session.add_all([user, cliente])
    db_session.flush()

    processo = Process(
        tenant_id=tenant.id,
        client_id=cliente.id,
        title="Processo Frente L",
        process_type="car",
        status=ProcessStatus.triagem,
    )
    db_session.add(processo)
    # commit: as linhas precisam sobreviver ao rollback do socorro, como
    # sobrevivem em produção (foram gravadas numa transação anterior).
    db_session.commit()
    return tenant, user, cliente, processo


# ---------------------------------------------------------------------------
# 1) legislation_service.ingest_legislation_document — SAVEPOINT
# ---------------------------------------------------------------------------

def test_legislacao_texto_com_nul_grava_failed_e_preserva_a_causa(db_session):
    doc = LegislationDocument(
        title="Lei de teste", source_type="lei", scope="federal", status="pending",
    )
    db_session.add(doc)
    db_session.commit()

    with pytest.raises(Exception) as excinfo:
        ingest_legislation_document(doc.id, db_session, raw_text=TEXTO_COM_NUL)

    # A causa real sobe — não o PendingRollbackError do socorro atropelado.
    assert not isinstance(excinfo.value, PendingRollbackError)
    assert "NUL" in str(excinfo.value)

    # E a sessão de quem chamou continua utilizável: o carimbo de falha é
    # gravável, que é o ponto do savepoint (rollback aqui apagaria o `doc`).
    db_session.commit()
    relido = db_session.get(LegislationDocument, doc.id)
    assert relido is not None, "o savepoint não podia levar a própria linha junto"
    assert relido.status == "failed"
    assert "NUL" in (relido.error_message or "")


def test_legislacao_caminho_feliz_continua_gravando(db_session):
    """O savepoint não pode engolir o sucesso — controle do teste acima."""
    doc = LegislationDocument(
        title="Lei boa", source_type="lei", scope="federal", status="pending",
    )
    db_session.add(doc)
    db_session.commit()

    ingest_legislation_document(doc.id, db_session, raw_text="Art. 1 Texto limpo.")
    db_session.commit()

    relido = db_session.get(LegislationDocument, doc.id)
    assert relido.status == "indexed"
    assert relido.full_text == "Art. 1 Texto limpo."
    assert relido.content_hash and relido.token_count


# ---------------------------------------------------------------------------
# 2) ai_tasks.run_llm_classification — rollback + AIJob carimbado
# ---------------------------------------------------------------------------

class _SinalDeRetry(Exception):
    """Sentinela no lugar de self.retry (padrão de test_agent_tasks_retry)."""


def _classificador_que_envenena(**_kwargs):
    resultado = types.SimpleNamespace(
        demand_type="licenciamento",
        initial_diagnosis=TEXTO_COM_NUL,   # derruba o commit do `try`
        confidence=0.9,
        urgency_flag=False,
    )
    return resultado, None


def test_classificacao_com_sessao_envenenada_carimba_o_aijob(
    semeado, db_session, monkeypatch
):
    tenant, user, _cliente, processo = semeado

    monkeypatch.setattr(ai_tasks, "SessionLocal", lambda: _SessaoSemFechar(db_session))
    monkeypatch.setattr(
        "app.services.llm_classifier.classify_demand_with_llm",
        _classificador_que_envenena,
    )

    def _retry(*_a, **_k):
        return _SinalDeRetry("retry pedido")

    monkeypatch.setattr(ai_tasks.run_llm_classification, "retry", _retry)

    with pytest.raises(_SinalDeRetry):
        ai_tasks.run_llm_classification(
            process_id=processo.id, tenant_id=tenant.id, user_id=user.id
        )

    jobs = (
        db_session.query(AIJob)
        .filter(AIJob.entity_type == "process", AIJob.entity_id == processo.id)
        .all()
    )
    assert len(jobs) == 1, "o AIJob criado antes da falha tem de sobreviver ao socorro"
    assert jobs[0].status == AIJobStatus.failed, "sem o rollback o job ficava 'running'"
    assert "NUL" in (jobs[0].error or "")
    assert jobs[0].finished_at is not None


# ---------------------------------------------------------------------------
# 3) ai_tasks.run_document_extraction — mesma classe
# ---------------------------------------------------------------------------

def test_extracao_de_documento_com_sessao_envenenada_carimba_o_aijob(
    semeado, db_session, monkeypatch
):
    from app.models.document import Document, OcrStatus

    tenant, user, cliente, processo = semeado
    doc = Document(
        tenant_id=tenant.id,
        process_id=processo.id,
        client_id=cliente.id,
        original_file_name="m.pdf",
        filename="m.pdf",
        content_type="application/pdf",
        storage_key=f"tenant-{tenant.id}/m.pdf",
        document_type="matricula",
        ocr_status=OcrStatus.done,
        extracted_text="matricula 3.181, area 926,3654 ha",
    )
    db_session.add(doc)
    db_session.commit()

    monkeypatch.setattr(ai_tasks, "SessionLocal", lambda: _SessaoSemFechar(db_session))

    def _extrator_que_envenena(**_kwargs):
        # JSONB com byte NUL: o commit do `try` cai no banco.
        return {"denominacao": TEXTO_COM_NUL}, None

    monkeypatch.setattr(
        "app.services.document_extractor.extract_document_fields",
        _extrator_que_envenena,
    )

    def _retry(*_a, **_k):
        return _SinalDeRetry("retry pedido")

    monkeypatch.setattr(ai_tasks.run_document_extraction, "retry", _retry)

    with pytest.raises(_SinalDeRetry):
        ai_tasks.run_document_extraction(
            document_id=doc.id, tenant_id=tenant.id, user_id=user.id
        )

    jobs = (
        db_session.query(AIJob)
        .filter(AIJob.entity_type == "document", AIJob.entity_id == doc.id)
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].status == AIJobStatus.failed, "sem o rollback o job ficava 'running'"
    assert jobs[0].error


# ---------------------------------------------------------------------------
# 4) A porta em si — `gravar_desfecho_de_falha` sobre sessão abortada no BANCO
# ---------------------------------------------------------------------------

def test_porta_do_socorro_grava_sobre_transacao_abortada(semeado, db_session):
    from app.core.db_rescue import gravar_desfecho_de_falha

    tenant, _user, _cliente, processo = semeado
    # Os inteiros saem do ORM ANTES — a mesma regra que o código sob teste
    # passou a seguir. Ler `processo.id` depois do veneno dispara lazy-load e
    # derruba o próprio teste (foi o que aconteceu ao escrever este arquivo).
    processo_id, tenant_id = processo.id, tenant.id

    # Envenena de verdade: erro do Postgres, não exceção sintética.
    with pytest.raises(DataError):
        db_session.execute(text("SELECT 1/0"))
    # Sessão inutilizável: o Postgres recusa qualquer comando até o fim da
    # transação (InternalError/InFailedSqlTransaction); quando o que cai é um
    # flush do ORM, o próprio SQLAlchemy desativa a transação e o sintoma vira
    # PendingRollbackError. As duas portas dão no mesmo lugar.
    # Prova de que a sessao esta mesmo inutilizavel: ate o comando mais simples
    # e recusado ate o fim da transacao. (`db.get` sozinho nao serviria de
    # prova — ele responde pelo mapa de identidade sem ir ao banco.)
    with pytest.raises((InternalError, PendingRollbackError)):
        db_session.execute(text("SELECT 1"))

    assert gravar_desfecho_de_falha(
        db_session, Process, processo_id, title="Processo Frente L (falhou)"
    ) is True

    relido = db_session.get(Process, processo_id)
    assert relido.title == "Processo Frente L (falhou)"
    assert relido.tenant_id == tenant_id


def test_porta_do_socorro_sem_identificador_nao_estoura(db_session):
    from app.core.db_rescue import gravar_desfecho_de_falha

    assert gravar_desfecho_de_falha(db_session, Process, None, title="x") is False


# ---------------------------------------------------------------------------
# 5) e 6) budget guard dos workers de leitura — o guard CONSULTA o banco
# ---------------------------------------------------------------------------

def _fronteiras_do_worker(monkeypatch, modulo, db_session):
    """Storage, realtime e SessionLocal falsos — o banco continua real."""
    eventos: list[dict] = []

    class _Storage:
        def download_bytes(self, _key: str) -> bytes:
            return b"%PDF-1.4 bytes de teste"

    monkeypatch.setattr("app.services.storage.get_storage_service", lambda: _Storage())
    monkeypatch.setattr(
        "app.services.notifications.publish_realtime_event",
        lambda **kw: eventos.append(kw) or True,
    )
    monkeypatch.setattr(modulo, "SessionLocal", lambda: _SessaoSemFechar(db_session))

    def _guard_derruba_o_banco(_tenant_id, db):
        # Erro REAL do Postgres dentro do guard — é o que uma conexão derrubada
        # ou um statement timeout produzem ali.
        db.execute(text("SELECT 1/0"))

    monkeypatch.setattr(
        "app.core.ai_gateway.check_tenant_monthly_budget", _guard_derruba_o_banco
    )
    return eventos


def _documento(db_session, *, tenant_id, client_id, process_id, **extra):
    from app.models.document import Document, OcrStatus

    doc = Document(
        tenant_id=tenant_id,
        process_id=process_id,
        client_id=client_id,
        original_file_name=extra.pop("nome", "doc.pdf"),
        filename=extra.pop("filename", "doc.pdf"),
        content_type=extra.pop("content_type", "application/pdf"),
        storage_key=f"tenant-{tenant_id}/frente-l-{extra.pop('sufixo', 'a')}",
        document_type=extra.pop("document_type", "matricula"),
        ocr_status=OcrStatus.pending,
        **extra,
    )
    db_session.add(doc)
    db_session.commit()
    return doc


def test_ocr_guard_de_orcamento_que_cai_no_banco_nao_deixa_o_doc_em_processing(
    semeado, db_session, monkeypatch
):
    import app.workers.ocr_tasks as ocr_tasks
    from app.models.document import Document, OcrStatus

    tenant, user, cliente, processo = semeado
    doc = _documento(
        db_session, tenant_id=tenant.id, client_id=cliente.id, process_id=processo.id,
    )
    doc_id, tenant_id, user_id = doc.id, tenant.id, user.id
    _fronteiras_do_worker(monkeypatch, ocr_tasks, db_session)

    resultado = ocr_tasks.ocr_then_extract(
        doc_id=doc_id, tenant_id=tenant_id, user_id=user_id
    )

    assert resultado["status"] == "budget_check_failed", (
        "falha ao CONSULTAR o orçamento não é orçamento esgotado"
    )
    relido = db_session.get(Document, doc_id)
    assert relido.ocr_status == OcrStatus.failed, (
        "sem o rollback o carimbo morria e o documento ficava 'processing'"
    )
    assert "orçamento" in (relido.ocr_error or "").lower()


def test_audio_guard_de_orcamento_que_cai_no_banco_carimba_o_documento(
    semeado, db_session, monkeypatch
):
    import app.workers.audio_tasks as audio_tasks
    from app.models.document import Document, OcrStatus

    tenant, user, cliente, processo = semeado
    doc = _documento(
        db_session, tenant_id=tenant.id, client_id=cliente.id, process_id=processo.id,
        nome="reuniao.m4a", filename="reuniao.m4a", content_type="audio/mp4",
        mime_type="audio/mp4", document_type="audio_entrevista",
        document_category="audio", sufixo="b",
    )
    doc_id, tenant_id, user_id = doc.id, tenant.id, user.id
    _fronteiras_do_worker(monkeypatch, audio_tasks, db_session)

    resultado = audio_tasks.transcribe_audio_document(
        doc_id=doc_id, tenant_id=tenant_id, user_id=user_id
    )

    assert resultado["status"] == "budget_check_failed"
    relido = db_session.get(Document, doc_id)
    assert relido.ocr_status == OcrStatus.failed
    assert "orçamento" in (relido.ocr_error or "").lower()
