"""Document repository."""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import and_, or_

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.process import Process
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    def _scoped_query(
        self,
        *,
        client_id: Optional[int] = None,
        property_id: Optional[int] = None,
    ):
        q = (
            self.db.query(Document)
            .outerjoin(Process, Document.process_id == Process.id)
            .filter(
                Document.tenant_id == self.tenant_id,
                Document.deleted_at.is_(None),
            )
        )
        if client_id is not None:
            q = q.filter(
                or_(
                    Document.client_id == client_id,
                    and_(
                        Document.client_id.is_(None),
                        Process.client_id == client_id,
                    ),
                )
            )
        if property_id is not None:
            # CAM2IH-004 (Sprint H) — docs do imóvel incluem docs vinculados
            # diretamente ou via processo do imóvel.
            q = q.filter(
                or_(
                    Document.property_id == property_id,
                    and_(
                        Document.property_id.is_(None),
                        Process.property_id == property_id,
                    ),
                )
            )
        return q

    def list_scoped(
        self,
        *,
        client_id: Optional[int] = None,
        process_id: Optional[int] = None,
        property_id: Optional[int] = None,
    ) -> Sequence[Document]:
        q = self._scoped_query(client_id=client_id, property_id=property_id)
        if process_id is not None:
            q = q.filter(Document.process_id == process_id)
        return q.all()

    def get_scoped(
        self, document_id: int, *, client_id: Optional[int] = None
    ) -> Optional[Document]:
        return (
            self._scoped_query(client_id=client_id)
            .filter(Document.id == document_id)
            .first()
        )

    def add_audit(
        self,
        *,
        user_id: int,
        document: Document,
        action: str,
        details: str,
    ) -> AuditLog:
        audit = AuditLog(
            tenant_id=self.tenant_id,
            user_id=user_id,
            entity_type="document",
            entity_id=document.id,
            action=action,
            details=details,
        )
        self.db.add(audit)
        self.db.flush()
        from app.services.audit_hash import stamp_audit_hash
        stamp_audit_hash(self.db, audit)
        return audit
