"""Append-only evidence versions and review history; mutable execution cursors."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.models.base import Base
from app.models.types import PortableJSON


class CaseSnapshot(Base):
    __tablename__ = "case_snapshots"
    id = Column(String(32), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    content = Column(PortableJSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("tenant_id", "process_id", "content_hash"),)


class EvidenceVersion(Base):
    __tablename__ = "evidence_versions"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    object_id = Column(String(120), nullable=False)
    version = Column(Integer, nullable=False)
    kind = Column(String(30), nullable=False)
    content = Column(PortableJSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    agent_name = Column(String(50), nullable=True)
    job_id = Column(Integer, ForeignKey("ai_jobs.id", ondelete="RESTRICT"), nullable=True)
    # Durable copies of source text and storage identity survive soft archival.
    source_record = Column(PortableJSON, nullable=True)
    source_document_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("tenant_id", "process_id", "object_id", "version"),)


class EvidenceReview(Base):
    __tablename__ = "evidence_reviews"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False)
    revision = Column(Integer, nullable=False)
    action = Column(String(30), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    justification = Column(String, nullable=False)
    premises = Column(PortableJSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("evidence_id", "revision"),)


class EvidenceInvalidation(Base):
    __tablename__ = "evidence_invalidations"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    reason = Column(PortableJSON, nullable=False)
    returned_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    returned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id = Column(String(32), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(32), ForeignKey("case_snapshots.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key = Column(String(120), nullable=False)
    chain_name = Column(String(80), nullable=False)
    status = Column(String(40), nullable=False, default="pending")
    steps = Column(PortableJSON, nullable=False)
    cursor = Column(Integer, nullable=False, default=0)
    waiting_reason = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("tenant_id", "process_id", "idempotency_key"),)
