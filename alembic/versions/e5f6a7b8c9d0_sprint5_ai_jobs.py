"""sprint5_ai_jobs

Revision ID: e5f6a7b8c9d0
Revises: d5e6f7a8b9c0
Create Date: 2026-04-02 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e5f6a7b8c9d0'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE aijobstatus AS ENUM ('pending', 'running', 'completed', 'failed')")
    op.execute("CREATE TYPE aijobtype AS ENUM ('classify_demand', 'extract_document', 'generate_proposal', 'generate_dossier_summary')")

    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("job_type", postgresql.ENUM("classify_demand", "extract_document", "generate_proposal", "generate_dossier_summary", name="aijobtype", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "running", "completed", "failed", name="aijobstatus", create_type=False), nullable=False, server_default="pending"),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_jobs_id", "ai_jobs", ["id"])
    op.create_index("ix_ai_jobs_tenant_id", "ai_jobs", ["tenant_id"])
    op.create_index("ix_ai_jobs_job_type", "ai_jobs", ["job_type"])
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_jobs_status", "ai_jobs")
    op.drop_index("ix_ai_jobs_job_type", "ai_jobs")
    op.drop_index("ix_ai_jobs_tenant_id", "ai_jobs")
    op.drop_index("ix_ai_jobs_id", "ai_jobs")
    op.drop_table("ai_jobs")
    op.execute("DROP TYPE IF EXISTS aijobtype")
    op.execute("DROP TYPE IF EXISTS aijobstatus")
