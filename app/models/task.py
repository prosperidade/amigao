import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)
class TaskStatus(str, enum.Enum):
    backlog = "backlog"
    a_fazer = "a_fazer"
    em_progresso = "em_progresso"
    aguardando = "aguardando"
    revisao = "revisao"
    concluida = "concluida"
    cancelada = "cancelada"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


VALID_TASK_TRANSITIONS = {
    TaskStatus.backlog: [TaskStatus.a_fazer, TaskStatus.cancelada],
    TaskStatus.a_fazer: [TaskStatus.em_progresso, TaskStatus.cancelada],
    TaskStatus.em_progresso: [TaskStatus.aguardando, TaskStatus.revisao, TaskStatus.cancelada],
    TaskStatus.aguardando: [TaskStatus.em_progresso, TaskStatus.cancelada],
    TaskStatus.revisao: [TaskStatus.concluida, TaskStatus.cancelada],
    TaskStatus.concluida: [TaskStatus.cancelada],
    TaskStatus.cancelada: [],
}


TERMINAL_TASK_STATUSES = {TaskStatus.concluida, TaskStatus.cancelada}


def is_valid_task_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    if from_status == to_status:
        return True
    return to_status in VALID_TASK_TRANSITIONS.get(from_status, [])


class Task(Base):
    """Modelo de Tarefa vinculada a um Processo, Imóvel ou Documento."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    status = Column(Enum(TaskStatus), default=TaskStatus.a_fazer, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.medium, nullable=False)

    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False)

    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    process = relationship("Process")
    property = relationship("Property")
    document = relationship("Document")
    assignee = relationship("User", foreign_keys=[assigned_to_user_id])
    creator = relationship("User", foreign_keys=[created_by_user_id])
    dependencies = relationship(
        "Task",
        secondary=task_dependencies,
        primaryjoin=id==task_dependencies.c.task_id,
        secondaryjoin=id==task_dependencies.c.depends_on_task_id,
        backref="dependent_tasks",
    )
