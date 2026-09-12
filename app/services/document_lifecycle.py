"""DOC-001 — estado do documento como campo único, com transição auditada.

Frente H (ADR-068). A spec Isis (DOC-001/CONF-002) pedia estados distintos e
rastro de autor por alteração. O código já tinha três sinais parciais e sem
relação entre si: `ocr_status` (pipeline de leitura), `extraction_status`
(string livre, hoje só usada para o motivo de "não processado, revisar" —
`app/agents/extrator.py:382`) e `review_required` (flag solta). Nenhum dos
três responde "em que pé está este documento" de ponta a ponta.

Medido antes de decidir (design decision #2 da Frente H): **não criar coluna
nova nem tabela nova**. O estado do documento é uma FUNÇÃO PURA dos sinais que
já existem — mesma filosofia do STATE-001 (`process_indicators.py`): projeção,
não campo mantido à parte para divergir depois. A transição em si (quem, quando,
de→para) é gravada no `AuditLog` já existente (`entity_type="document"`,
mesma tabela que `DocumentRepository.add_audit` já usa para "uploaded") — nunca
uma tabela de histórico própria.

Os 5 estados positivos (recebido/lido/classificado/extraído/conferido) formam
uma escada: cada um implica o anterior. `derive_document_status` devolve o
degrau mais alto alcançado; nunca um estado "pulado por engano" — se a extração
rodou sem OCR concluído (não deveria acontecer, mas o sinal não mente), o
documento aparece como "extraído" mesmo assim, porque de fato tem staging.

Frente J (item 6, reauditoria Codex 11/09) acrescentou os estados NEGATIVOS da
spec (DOC-001) ao mesmo vocabulário — `processando`, `erro_leitura`,
`desatualizado`, `substituido` (deriváveis de uma linha de `Document`) e
`nao_apresentado`/`dispensado` (estados do requisito no checklist, nunca
derivados aqui) — e trocou a régua de "lido": texto LEGÍVEL
(`ficha01_extraction.texto_sem_conteudo_legivel`), não `ocr_status=done`.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document, OcrStatus
from app.services.audit_hash import stamp_audit_hash

AUDIT_ACTION = "document_status_changed"


class DocumentLifecycleStatus(str, enum.Enum):
    """Vocabulário único de DOC-001, incluindo os estados negativos da spec."""

    nao_apresentado = "nao_apresentado"
    recebido = "recebido"
    processando = "processando"
    lido = "lido"
    classificado = "classificado"
    extraido = "extraido"
    conferido = "conferido"
    erro_leitura = "erro_leitura"
    dispensado = "dispensado"
    substituido = "substituido"
    desatualizado = "desatualizado"


# Mesmo conjunto que `reconciliation_decisions._DECIDIDOS` (ADR-067) — uma
# linha de staging só sai de circulação quando o consultor aceita ou rejeita.
# Import local (não do módulo privado) para não acoplar aos internos dele;
# os dois precisam continuar em sincronia se a Ficha 01 ganhar status novo.
_STAGING_DECIDIDOS = {"aceito", "rejeitado"}


def _tem_leitura(doc: Document) -> bool:
    # Mesma fronteira que gera `MOTIVO_OCR_ILEGIVEL` no pipeline. `done` é
    # conclusão técnica do job, não prova de que há conteúdo utilizável.
    from app.services.ficha01_extraction import texto_sem_conteudo_legivel  # noqa: PLC0415

    return not texto_sem_conteudo_legivel(doc.extracted_text)


def _tem_classificacao(doc: Document) -> bool:
    tipo = (doc.document_type or "").strip()
    return bool(tipo) and tipo.lower() != "outro"


def _status_sem_staging(document: Document) -> Optional[DocumentLifecycleStatus]:
    """Os degraus que se decidem só com o próprio documento (sem consultar o
    staging). ``None`` quando é preciso olhar o staging para decidir entre
    classificado / extraído / conferido.

    Frente J (item 6): `lido` exige TEXTO LEGÍVEL — a mesma régua
    (`texto_sem_conteudo_legivel`) que faz o pipeline escrever
    `MOTIVO_OCR_ILEGIVEL` em `extraction_status`. `ocr_status=done` é conclusão
    técnica do job, não prova de conteúdo: o doc 551 do #23 (CNH-e, 444 chars
    de boilerplate de assinatura digital) estava `done` e aparecia "lido".
    Estados negativos da spec (DOC-001): `erro_leitura` (job terminou sem
    texto utilizável), `processando` (job em curso), `desatualizado`
    (validade vencida), `substituido` (removido/trocado por versão nova).
    `nao_apresentado`/`dispensado` são estados do REQUISITO (checklist), não
    de uma linha de `Document` — estão no vocabulário para a tela do
    checklist falar a mesma língua, nunca derivados aqui.
    """
    if document.deleted_at is not None:
        return DocumentLifecycleStatus.substituido

    if document.expires_at is not None:
        agora = datetime.now(UTC)
        validade = document.expires_at
        if validade.tzinfo is None:
            validade = validade.replace(tzinfo=UTC)
        if validade < agora:
            return DocumentLifecycleStatus.desatualizado

    if not _tem_leitura(document):
        if document.ocr_status == OcrStatus.processing:
            return DocumentLifecycleStatus.processando
        if document.ocr_status in (OcrStatus.done, OcrStatus.not_required, OcrStatus.failed):
            return DocumentLifecycleStatus.erro_leitura
        return DocumentLifecycleStatus.recebido

    if not _tem_classificacao(document):
        return DocumentLifecycleStatus.lido
    return None


def _status_pelo_staging(statuses: list) -> DocumentLifecycleStatus:
    if not statuses:
        return DocumentLifecycleStatus.classificado
    if all((s.value if hasattr(s, "value") else s) in _STAGING_DECIDIDOS for s in statuses):
        return DocumentLifecycleStatus.conferido
    return DocumentLifecycleStatus.extraido


def derive_document_status(
    db: Session, document: Document
) -> DocumentLifecycleStatus:
    """Deriva o estado atual — leitura pura, nunca escreve.

    Não recebe `tenant_id` à parte: o `document` já carrega o seu, e ler o
    staging por `document_id` (com filtro de tenant) evita depender de o
    caller ter passado o tenant certo.
    """
    from app.models.extracted_field_staging import ExtractedFieldStaging  # noqa: PLC0415

    direto = _status_sem_staging(document)
    if direto is not None:
        return direto

    staging = (
        db.query(ExtractedFieldStaging.status)
        .filter(
            ExtractedFieldStaging.tenant_id == document.tenant_id,
            ExtractedFieldStaging.document_id == document.id,
        )
        .all()
    )
    return _status_pelo_staging([s for (s,) in staging])


def derive_document_statuses(
    db: Session, documents: list[Document]
) -> dict[int, DocumentLifecycleStatus]:
    """Mesma projeção de `derive_document_status`, para uma LISTA — uma query
    de staging para todos os documentos, não uma por documento (a listagem
    `GET /documents` sem filtro de processo devolve o tenant inteiro; N
    queries ali é o N+1 clássico). Resultado idêntico ao caminho unitário:
    o teste de equivalência está em `tests/services/test_document_lifecycle.py`.
    """
    from app.models.extracted_field_staging import ExtractedFieldStaging  # noqa: PLC0415

    resultado: dict[int, DocumentLifecycleStatus] = {}
    pendentes: list[Document] = []
    for doc in documents:
        direto = _status_sem_staging(doc)
        if direto is not None:
            resultado[doc.id] = direto
        else:
            pendentes.append(doc)
    if not pendentes:
        return resultado

    por_tenant: dict[int, list[int]] = {}
    for doc in pendentes:
        por_tenant.setdefault(doc.tenant_id, []).append(doc.id)
    statuses_por_doc: dict[int, list] = {doc.id: [] for doc in pendentes}
    for tenant_id, ids in por_tenant.items():
        linhas = (
            db.query(ExtractedFieldStaging.document_id, ExtractedFieldStaging.status)
            .filter(
                ExtractedFieldStaging.tenant_id == tenant_id,
                ExtractedFieldStaging.document_id.in_(ids),
            )
            .all()
        )
        for document_id, status in linhas:
            statuses_por_doc.setdefault(document_id, []).append(status)
    for doc in pendentes:
        resultado[doc.id] = _status_pelo_staging(statuses_por_doc.get(doc.id, []))
    return resultado


def _ultimo_status_conhecido(db: Session, document: Document) -> Optional[str]:
    """Último `new_value` gravado para este documento, ou `None` se nunca
    transicionou — nesse caso o baseline é implícito ("recebido": o
    documento existe, é o que basta). Onde o caminho de criação já audita
    (`documents.py`, `action="uploaded"`), esse registro cobre o autor da
    entrada; não duplicamos com um segundo `document_status_changed`."""
    ultimo = (
        db.query(AuditLog.new_value)
        .filter(
            AuditLog.tenant_id == document.tenant_id,
            AuditLog.entity_type == "document",
            AuditLog.entity_id == document.id,
            AuditLog.action == AUDIT_ACTION,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    return ultimo[0] if ultimo else None


def registrar_transicao_se_mudou(
    db: Session,
    document: Document,
    *,
    user_id: Optional[int] = None,
) -> Optional[DocumentLifecycleStatus]:
    """Recalcula o estado; se mudou desde a última leitura conhecida, grava
    a transição no `audit_log` (quem — `user_id`, `None` quando o gatilho é
    automático/pipeline —, quando, de→para) com a hash chain do tenant.

    Devolve o novo estado quando gravou; `None` quando não houve mudança (a
    maioria das chamadas — este helper é seguro para chamar "só para
    garantir" em qualquer ponto de mutação, sem medo de poluir o audit_log).
    """
    atual = derive_document_status(db, document)
    anterior = _ultimo_status_conhecido(db, document) or DocumentLifecycleStatus.recebido.value

    if atual.value == anterior:
        return None

    audit = AuditLog(
        tenant_id=document.tenant_id,
        user_id=user_id,
        entity_type="document",
        entity_id=document.id,
        action=AUDIT_ACTION,
        old_value=anterior,
        new_value=atual.value,
        details=f"documento {document.id}: {anterior} → {atual.value}",
    )
    db.add(audit)
    db.flush()
    stamp_audit_hash(db, audit)
    return atual


def historico_transicoes(db: Session, document: Document) -> list[AuditLog]:
    """Sequência completa de transições registradas, mais antiga primeiro —
    usada pelo gate (colar a sequência de um documento) e por qualquer tela
    que queira mostrar o histórico de leitura/classificação/conferência."""
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.tenant_id == document.tenant_id,
            AuditLog.entity_type == "document",
            AuditLog.entity_id == document.id,
            AuditLog.action == AUDIT_ACTION,
        )
        .order_by(AuditLog.id.asc())
        .all()
    )
