"""Escopo de extração em lote — dívida #78.

A rota `POST /processes/{id}/extract` processa TODOS os documentos do processo.
No caso 15 isso significaria pagar LLM em 42 documentos, sendo que 10 já estão
lidos. Aqui mora a seleção de QUEM entra no lote — a parte que decide gasto, e
por isso testada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.extracted_field_staging import ExtractedFieldStaging


@dataclass
class EscopoLote:
    documentos: list[Document]
    sem_texto: list[int]          # não dá para extrair — precisa de OCR antes
    sem_tipo: list[int]           # extração genérica, sem spec de campos
    total_chars: int

    @property
    def tokens_estimados(self) -> int:
        """~4 chars por token. Estimativa de ENTRADA, não inclui prompt nem saída."""
        return self.total_chars // 4


def coletar_escopo(
    db: Session,
    *,
    document_ids: Optional[list[int]] = None,
    process_ids: Optional[list[int]] = None,
    sem_staging: bool = False,
) -> EscopoLote:
    """Seleciona os documentos do lote. Sem escopo explícito, levanta erro.

    `sem_staging=True` filtra os que ainda não têm NENHUMA linha de staging —
    é o recorte que evita re-pagar por documento já lido.
    """
    if not document_ids and not process_ids:
        raise ValueError("escopo obrigatório: informe document_ids ou process_ids")

    q = db.query(Document).filter(Document.deleted_at.is_(None))
    if document_ids:
        q = q.filter(Document.id.in_(document_ids))
    if process_ids:
        q = q.filter(Document.process_id.in_(process_ids))
    docs = q.order_by(Document.id).all()

    if sem_staging and docs:
        com_staging = {
            row[0]
            for row in db.query(ExtractedFieldStaging.document_id)
            .filter(ExtractedFieldStaging.document_id.in_([d.id for d in docs]))
            .distinct()
            .all()
        }
        docs = [d for d in docs if d.id not in com_staging]

    return EscopoLote(
        documentos=docs,
        sem_texto=[d.id for d in docs if not (d.extracted_text or "").strip()],
        sem_tipo=[d.id for d in docs if not (d.document_type or "").strip()],
        total_chars=sum(len(d.extracted_text or "") for d in docs),
    )
