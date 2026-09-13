"""Frente L — o que a auditoria de 12/09 reprovou, com teste.

Três achados confirmados por terceiro, cada um com o seu caminho executável:

1. o `begin_nested()` abria DEPOIS da query e do primeiro flush, e o
   `legislation_monitor` atribui `existing.full_text` ANTES de chamar o
   serviço — o autoflush da query derrubava a transação antes de existir
   savepoint, e o monitor seguia o lote numa sessão abortada;
2. `gravar_desfecho_de_falha` podia devolver `False` e nenhum dos quatro
   chamadores lia o retorno — o desfecho não gravado virava "tratado";
3. o socorro recarrega a linha depois do rollback e podia carimbar `failed`
   por cima de um `done` gravado por outra execução nesse intervalo.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

import app.workers.ai_tasks as ai_tasks
import app.workers.ocr_tasks as ocr_tasks
from app.core.db_rescue import gravar_desfecho_de_falha
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.legislation import LegislationDocument
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User

TEXTO_COM_NUL = "Art. 1 Fica instituido\x00 o regime de que trata esta Lei."


@pytest.fixture
def db_session(db_engine):
    """`create_savepoint` — ver a justificativa em test_frente_l_sessao_envenenada."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


class _SessaoSemFechar:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 1) O caminho CONFIRMADO pela auditoria: legislação que já existe
# ---------------------------------------------------------------------------

def test_ingest_de_legislacao_existente_com_nul_deixa_subir_a_causa_real(db_session):
    """O serviço não esconde a causa atrás de PendingRollbackError.

    O caminho: o monitor escreve `existing.full_text = <texto novo>` e só então
    chama o serviço; dentro dele o AUTOFLUSH da primeira query leva a pendência
    junto. Medido em 12/09: depois desse flush falho a sessão exige `rollback`,
    e NENHUM savepoint dentro do serviço recupera. Então o contrato do serviço é
    só este — e este ele cumpre sempre.
    """
    from app.services.legislation_service import ingest_legislation_document

    doc = LegislationDocument(
        title="Lei já ingerida", source_type="lei", scope="federal",
        status="indexed", full_text="texto antigo, limpo",
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    doc.full_text = TEXTO_COM_NUL  # exatamente o gesto do monitor

    with pytest.raises(Exception) as excinfo:
        ingest_legislation_document(doc_id, db_session, raw_text=TEXTO_COM_NUL)

    texto = str(excinfo.value)
    assert "NUL" in texto
    assert "PendingRollbackError" not in type(excinfo.value).__name__, (
        "a causa real tem de subir; o erro genérico do SQLAlchemy esconderia o "
        "que houve — foi assim que o documento ficava 'processing' sem motivo"
    )


def test_monitor_carimba_o_falho_e_segue_o_lote(db_session, monkeypatch):
    """O laço REAL do monitor, com crawler falso: um ruim custa um.

    Antes: tudo numa transação só, `except` sem rollback. Um documento com NUL
    derrubava a sessão, TODA iteração seguinte morria de PendingRollbackError e
    o `db.commit()` do fim levava o crawler inteiro. Agora o dono da sessão
    desfaz, carimba `failed` pela porta de `db_rescue` e segue.
    """
    import app.services.legislation_monitor as monitor
    from app.services.crawlers.base_crawler import CrawledDocument

    docs = [
        CrawledDocument(title="Lei boa A", identifier="LEI-A/2026",
                        content="Art. 1 Texto limpo A.", source_url="http://x/a"),
        CrawledDocument(title="Lei ruim", identifier="LEI-RUIM/2026",
                        content=TEXTO_COM_NUL, source_url="http://x/ruim"),
        CrawledDocument(title="Lei boa B", identifier="LEI-B/2026",
                        content="Art. 1 Texto limpo B.", source_url="http://x/b"),
    ]

    class _CrawlerFalso:
        name = "falso"

        def safe_crawl(self):
            return docs

    monkeypatch.setattr(monitor, "get_crawler", lambda _n: _CrawlerFalso())
    monkeypatch.setattr(monitor, "_create_alerts_for_document", lambda *a, **k: 0)

    # O caminho CONFIRMADO pela auditoria é o de ATUALIZAÇÃO: a linha já existe,
    # commitada numa transação anterior, e o monitor escreve o texto novo nela
    # antes de chamar o serviço. (Documento NOVO que falha é outro caso e está
    # no teste seguinte.)
    ja_existe = LegislationDocument(
        title="Lei ruim", identifier="LEI-RUIM/2026", source_type="lei",
        scope="federal", status="indexed", full_text="conteúdo antigo, limpo",
    )
    db_session.add(ja_existe)
    db_session.commit()
    ruim_id = ja_existe.id

    resultado = monitor._run_single_crawler(db_session, "falso")

    assert resultado.documents_new == 2, "os dois bons tinham de entrar"
    assert len(resultado.errors) == 1, "só o do NUL podia falhar"
    assert "LEI-RUIM/2026" in resultado.errors[0]

    # Os bons estão gravados de verdade...
    titulos = {
        d.title: d.status
        for d in db_session.query(LegislationDocument).all()
    }
    assert titulos.get("Lei boa A") == "indexed"
    assert titulos.get("Lei boa B") == "indexed"
    # ...e o que falhou NÃO ficou preso em "processing": levou o carimbo, com a
    # causa. Antes, a sessão morta fazia os DOIS bons seguintes falharem junto.
    relido = db_session.get(LegislationDocument, ruim_id)
    assert relido.status == "failed", (
        "o dono da sessão carimba depois do rollback — é ele que pode"
    )
    assert "NUL" in (relido.error_message or "")


def test_documento_novo_que_falha_nao_deixa_linha_presa(db_session, monkeypatch):
    """Contraexemplo do teste acima — e uma distinção que o teste revelou.

    Documento NOVO entra com `db.add` + `flush` na MESMA transação que o
    rollback desfaz: a linha nunca chegou a existir. Não há o que carimbar, e
    isso não é falha do socorro — é a resposta certa. O que não pode acontecer
    é sobrar linha em "processing", e não sobra.
    """
    import app.services.legislation_monitor as monitor
    from app.services.crawlers.base_crawler import CrawledDocument

    class _CrawlerFalso:
        name = "falso"

        def safe_crawl(self):
            return [CrawledDocument(
                title="Lei nova ruim", identifier="LEI-NOVA-RUIM/2026",
                content=TEXTO_COM_NUL, source_url="http://x/nova",
            )]

    monkeypatch.setattr(monitor, "get_crawler", lambda _n: _CrawlerFalso())
    monkeypatch.setattr(monitor, "_create_alerts_for_document", lambda *a, **k: 0)

    resultado = monitor._run_single_crawler(db_session, "falso")

    assert resultado.documents_new == 0
    assert len(resultado.errors) == 1
    presas = db_session.query(LegislationDocument).filter(
        LegislationDocument.status == "processing"
    ).all()
    assert presas == [], "nenhuma linha pode ficar em 'processing'"
    assert db_session.query(LegislationDocument).filter(
        LegislationDocument.identifier == "LEI-NOVA-RUIM/2026"
    ).first() is None, "a linha nunca foi commitada — não existe, e está certo"


# ---------------------------------------------------------------------------
# 2) O retorno de `gravar_desfecho_de_falha` não é decorativo
# ---------------------------------------------------------------------------

@pytest.fixture
def semeado(db_session):
    tenant = Tenant(name="Frente L auditoria")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="aud@example.com", full_name="Aud", hashed_password="x" * 60,
                tenant_id=tenant.id, is_active=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente Aud", email="cli.aud@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, title="Proc Aud",
                   process_type="car", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.commit()
    return tenant, user, cli, proc


def test_socorro_que_falha_faz_o_ocr_levantar_em_vez_de_dizer_que_tratou(
    semeado, db_session, monkeypatch
):
    """`False` = documento continua em `processing`. Devolver status seria mentira."""
    from sqlalchemy import text as sql_text

    tenant, user, cli, proc = semeado
    doc = Document(
        tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
        original_file_name="d.pdf", filename="d.pdf", content_type="application/pdf",
        storage_key=f"tenant-{tenant.id}/aud-a", document_type="matricula",
        ocr_status=OcrStatus.pending,
    )
    db_session.add(doc)
    db_session.commit()
    doc_id, tenant_id, user_id = doc.id, tenant.id, user.id

    class _Storage:
        def download_bytes(self, _k):
            return b"%PDF-1.4 bytes"

    monkeypatch.setattr("app.services.storage.get_storage_service", lambda: _Storage())
    monkeypatch.setattr("app.services.notifications.publish_realtime_event", lambda **kw: True)
    monkeypatch.setattr(ocr_tasks, "SessionLocal", lambda: _SessaoSemFechar(db_session))
    monkeypatch.setattr(
        "app.core.ai_gateway.check_tenant_monthly_budget",
        lambda _t, db: db.execute(sql_text("SELECT 1/0")),
    )
    # O socorro não consegue gravar (banco fora).
    monkeypatch.setattr(ocr_tasks, "gravar_desfecho_de_falha", lambda *a, **k: False)

    with pytest.raises(Exception) as excinfo:
        ocr_tasks.ocr_then_extract(doc_id=doc_id, tenant_id=tenant_id, user_id=user_id)
    assert "budget_check_failed" not in str(excinfo.value), (
        "a task não pode terminar com status quando o desfecho não foi gravado"
    )


def test_socorro_que_falha_faz_a_classificacao_nao_pedir_retry(
    semeado, db_session, monkeypatch
):
    """Retry com banco fora cria um AIJob órfão NOVO a cada tentativa."""
    tentou_retry = {"n": 0}

    def _retry(*_a, **_k):
        tentou_retry["n"] += 1
        return RuntimeError("retry")

    monkeypatch.setattr(ai_tasks.run_llm_classification, "retry", _retry)
    monkeypatch.setattr(ai_tasks, "SessionLocal", lambda: _SessaoSemFechar(db_session))
    monkeypatch.setattr(ai_tasks, "gravar_desfecho_de_falha", lambda *a, **k: False)

    def _classificador_que_quebra(**_kw):
        raise RuntimeError("provedor fora do ar")

    monkeypatch.setattr(
        "app.services.llm_classifier.classify_demand_with_llm", _classificador_que_quebra
    )

    _tenant, user, _cli, proc = semeado
    with pytest.raises(RuntimeError) as excinfo:
        ai_tasks.run_llm_classification(
            process_id=proc.id, tenant_id=proc.tenant_id, user_id=user.id
        )
    assert "provedor fora do ar" in str(excinfo.value), "a causa original tem de subir crua"
    assert tentou_retry["n"] == 0, "com o socorro falhado, retry só multiplica órfão"


# ---------------------------------------------------------------------------
# 3) A trava de concorrência
# ---------------------------------------------------------------------------

def test_socorro_nao_carimba_failed_por_cima_de_done_alheio(semeado, db_session):
    """Outra execução concluiu o documento entre o rollback e a recarga."""
    tenant, _user, cli, proc = semeado
    doc = Document(
        tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
        original_file_name="c.pdf", filename="c.pdf", content_type="application/pdf",
        storage_key=f"tenant-{tenant.id}/aud-b", document_type="matricula",
        ocr_status=OcrStatus.done, extracted_text="texto que a outra execução leu",
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    gravou = gravar_desfecho_de_falha(
        db_session, Document, doc_id,
        nao_sobrescrever={"ocr_status": OcrStatus.done},
        ocr_status=OcrStatus.failed,
        ocr_error="orçamento esgotado",
    )

    # True porque o desfecho EXISTE — só não é este. Quem chama não precisa
    # distinguir "gravei failed" de "alguém já gravou done": os dois dizem
    # "a linha não ficou presa".
    assert gravou is True
    relido = db_session.get(Document, doc_id)
    assert relido.ocr_status == OcrStatus.done, "trabalho bom não pode virar failed"
    assert relido.ocr_error is None
    assert relido.extracted_text == "texto que a outra execução leu"


def test_socorro_carimba_quando_o_documento_ainda_esta_processando(semeado, db_session):
    """Contraexemplo do teste acima — a trava não pode virar mordaça."""
    tenant, _user, cli, proc = semeado
    doc = Document(
        tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
        original_file_name="p.pdf", filename="p.pdf", content_type="application/pdf",
        storage_key=f"tenant-{tenant.id}/aud-c", document_type="matricula",
        ocr_status=OcrStatus.processing,
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    assert gravar_desfecho_de_falha(
        db_session, Document, doc_id,
        nao_sobrescrever={"ocr_status": OcrStatus.done},
        ocr_status=OcrStatus.failed,
        ocr_error="orçamento esgotado",
    ) is True
    relido = db_session.get(Document, doc_id)
    assert relido.ocr_status == OcrStatus.failed
    assert relido.ocr_error == "orçamento esgotado"
