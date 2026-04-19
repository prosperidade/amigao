"""Task repository."""

from __future__ import annotations

from typing import Optional, Sequence

from app.models.audit_log import AuditLog
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    def list_by_process(
        self, process_id: int, *, skip: int = 0, limit: int = 100
    ) -> Sequence[Task]:
        return (
            self._base_query()
            .filter(Task.process_id == process_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def add_audit(
        self,
        *,
        user_id: int,
        task: Task,
        action: str,
        details: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> AuditLog:
        audit = AuditLog(
            tenant_id=self.tenant_id,
            user_id=user_id,
            entity_type="task",
            entity_id=task.id,
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
