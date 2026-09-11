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

Os 5 estados (recebido/lido/classificado/extraído/conferido) formam uma escada:
cada um implica o anterior. `derive_document_status` devolve o degrau mais alto
alcançado; nunca um estado "pulado por engano" — se a extração rodou sem OCR
concluído (não deveria acontecer, mas o sinal não mente), o documento aparece
como "extraído" mesmo assim, porque de fato tem staging.
"""

from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document, OcrStatus
from app.services.audit_hash import stamp_audit_hash

AUDIT_ACTION = "document_status_changed"


class DocumentLifecycleStatus(str, enum.Enum):
    """Escada DOC-001 — cada degrau implica os anteriores."""

    recebido = "recebido"
    lido = "lido"
    classificado = "classificado"
    extraido = "extraido"
    conferido = "conferido"


# Mesmo conjunto que `reconciliation_decisions._DECIDIDOS` (ADR-067) — uma
# linha de staging só sai de circulação quando o consultor aceita ou rejeita.
# Import local (não do módulo privado) para não acoplar aos internos dele;
# os dois precisam continuar em sincronia se a Ficha 01 ganhar status novo.
_STAGING_DECIDIDOS = {"aceito", "rejeitado"}


def _tem_leitura(doc: Document) -> bool:
    if (doc.extracted_text or "").strip():
        return True
    return doc.ocr_status in (OcrStatus.done, OcrStatus.not_required)


def _tem_classificacao(doc: Document) -> bool:
    tipo = (doc.document_type or "").strip()
    return bool(tipo) and tipo.lower() != "outro"


def derive_document_status(
    db: Session, document: Document
) -> DocumentLifecycleStatus:
    """Deriva o estado atual — leitura pura, nunca escreve.

    Não recebe `tenant_id` à parte: o `document` já carrega o seu, e ler o
    staging por `document_id` (com filtro de tenant) evita depender de o
    caller ter passado o tenant certo.
    """
    from app.models.extracted_field_staging import ExtractedFieldStaging  # noqa: PLC0415

    if not _tem_leitura(document):
        return DocumentLifecycleStatus.recebido

    if not _tem_classificacao(document):
        return DocumentLifecycleStatus.lido

    staging = (
        db.query(ExtractedFieldStaging.status)
        .filter(
            ExtractedFieldStaging.tenant_id == document.tenant_id,
            ExtractedFieldStaging.document_id == document.id,
        )
        .all()
    )
    if not staging:
        return DocumentLifecycleStatus.classificado

    if all((s.value if hasattr(s, "value") else s) in _STAGING_DECIDIDOS for (s,) in staging):
        return DocumentLifecycleStatus.conferido

    return DocumentLifecycleStatus.extraido


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
