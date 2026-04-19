"""Process repository — queries and mutations for Process entities."""

from __future__ import annotations

from typing import Optional, Sequence

from app.models.audit_log import AuditLog
from app.models.process import Process
from app.models.task import TERMINAL_TASK_STATUSES, Task
from app.repositories.base import BaseRepository


class ProcessRepository(BaseRepository[Process]):
    model = Process

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[list] = None,
        client_id: Optional[int] = None,
    ) -> Sequence[Process]:
        q = self._base_query().filter(Process.deleted_at.is_(None))
        if client_id is not None:
            q = q.filter(Process.client_id == client_id)
        for f in filters or []:
            q = q.filter(f)
        return q.offset(skip).limit(limit).all()

    def get_scoped(
        self, process_id: int, *, client_id: Optional[int] = None
    ) -> Optional[Process]:
        q = self._base_query().filter(Process.id == process_id)
        if client_id is not None:
            q = q.filter(Process.client_id == client_id)
        return q.first()

    def get_scoped_or_404(
        self,
        process_id: int,
        *,
        client_id: Optional[int] = None,
        detail: str = "Processo não encontrado",
    ) -> Process:
        obj = self.get_scoped(process_id, client_id=client_id)
        if obj is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=detail)
        return obj

    def count_incomplete_tasks(self, process_id: int) -> int:
        return (
            self.db.query(Task)
            .filter(
                Task.tenant_id == self.tenant_id,
                Task.process_id == process_id,
                Task.status.notin_(list(TERMINAL_TASK_STATUSES)),
            )
            .count()
        )

    def add_audit(
        self,
        *,
        user_id: int,
        process: Process,
        action: str,
        details: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> AuditLog:
        audit = AuditLog(
            tenant_id=self.tenant_id,
            user_id=user_id,
            entity_type="process",
            entity_id=process.id,
            action=action,
            details=details,
            old_value=old_value,
            new_value=new_value,
        )
        self.db.add(audit)
        self.db.flush()
        from app.services.audit_hash import stamp_audit_hash
        stamp_audit_hash(self.db, audit)
        return audit

    def get_timeline(self, process_id: int) -> Sequence[AuditLog]:
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == self.tenant_id,
                AuditLog.entity_type == "process",
                AuditLog.entity_id == process_id,
            )
            .order_by(AuditLog.created_at.desc())
            .all()
        )
