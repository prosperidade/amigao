"""ADR-069 additive evidence, review and persisted execution contract.

Revision ID: 069ce001
Revises: c7e1a94d2f60
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "069ce001"
down_revision = "c7e1a94d2f60"
branch_labels = None
depends_on = None


def _scope():
    return [
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table("case_snapshots", sa.Column("id", sa.String(32), primary_key=True), *_scope(),
        sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("content", JSONB(), nullable=False),
        sa.UniqueConstraint("tenant_id", "process_id", "content_hash"))
    op.create_table("evidence_versions", sa.Column("id", sa.Integer(), primary_key=True), *_scope(),
        sa.Column("object_id", sa.String(120), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False), sa.Column("content", JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("agent_name", sa.String(50)),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("ai_jobs.id", ondelete="RESTRICT")),
        sa.Column("source_record", JSONB()),
        sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("tenant_id", "process_id", "object_id", "version"))
    op.create_table("evidence_reviews", sa.Column("id", sa.Integer(), primary_key=True), *_scope(),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("action", sa.String(30), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("justification", sa.String(), nullable=False), sa.Column("premises", JSONB(), nullable=False),
        sa.UniqueConstraint("evidence_id", "revision"))
    op.create_table("evidence_invalidations", sa.Column("id", sa.Integer(), primary_key=True), *_scope(),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("reason", JSONB(), nullable=False),
        sa.Column("returned_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("returned_at", sa.DateTime(timezone=True)))
    op.create_table("agent_executions", sa.Column("id", sa.String(32), primary_key=True), *_scope(),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("snapshot_id", sa.String(32), sa.ForeignKey("case_snapshots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("chain_name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False), sa.Column("steps", JSONB(), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=False), sa.Column("waiting_reason", sa.String()),
        sa.Column("revision", sa.Integer(), nullable=False), sa.UniqueConstraint("tenant_id", "process_id", "idempotency_key"))
    for table in ("case_snapshots", "evidence_versions", "evidence_reviews", "evidence_invalidations", "agent_executions"):
        for column in ("tenant_id", "process_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    # RESTRICT also prevents accidentally deleting source/job history while references exist.
    for table in ("agent_executions", "evidence_invalidations", "evidence_reviews", "evidence_versions", "case_snapshots"):
        op.drop_table(table)
