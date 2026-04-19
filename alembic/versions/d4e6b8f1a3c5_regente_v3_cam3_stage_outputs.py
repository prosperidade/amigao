"""Regente v3 Cam3 — stage_outputs table

Revision ID: d4e6b8f1a3c5
Revises: c8a1e5d7f3b2
Create Date: 2026-04-18 21:30:00.000000

CAM3WS-006 — Saídas/artefatos formais por etapa do workspace.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e6b8f1a3c5"
down_revision: Union[str, Sequence[str], None] = "c8a1e5d7f3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stage_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "process_id",
            sa.Integer(),
            sa.ForeignKey("processes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("macroetapa", sa.String(), nullable=False, index=True),
        sa.Column("output_type", sa.String(), nullable=False, index=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_data", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("produced_by_agent", sa.String(), nullable=True),
        sa.Column(
            "produced_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("needs_human_validation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "validated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index(
        "ix_stage_outputs_process_macroetapa",
        "stage_outputs",
        ["process_id", "macroetapa"],
    )


def downgrade() -> None:
    op.drop_index("ix_stage_outputs_process_macroetapa", table_name="stage_outputs")
    op.drop_table("stage_outputs")
