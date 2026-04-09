"""Add legislation_documents table for knowledge base.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-04-08

Changes:
- Create legislation_documents table (full text storage, no chunking)
- Add new AIJobType enum values for RAG/regulatory
"""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None

NEW_JOB_TYPES = [
    "embedding_generation",
    "enquadramento_regulatorio",
    "monitoramento_legislacao",
]


def upgrade() -> None:
    op.create_table(
        "legislation_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("identifier", sa.String(), nullable=True, index=True),
        sa.Column("uf", sa.String(2), nullable=True, index=True),
        sa.Column("scope", sa.String(), nullable=False, server_default="federal"),
        sa.Column("municipality", sa.String(), nullable=True),
        sa.Column("agency", sa.String(), nullable=True, index=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("demand_types", sa.JSON(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add new AIJobType enum values
    for val in NEW_JOB_TYPES:
        op.execute(
            sa.text(
                "ALTER TYPE aijobtype ADD VALUE IF NOT EXISTS :val"
            ).bindparams(val=val)
        )


def downgrade() -> None:
    op.drop_table("legislation_documents")
