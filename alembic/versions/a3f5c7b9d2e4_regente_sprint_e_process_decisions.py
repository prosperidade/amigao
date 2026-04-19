"""Regente Sprint E — process_decisions table

Revision ID: a3f5c7b9d2e4
Revises: e7c9b2a4f8d1
Create Date: 2026-04-19 14:30:00.000000

Sprint E — Aba Decisões (Camada 3 / governança do raciocínio).
Registra decisões críticas tomadas ao longo do caso com rastreabilidade
completa: o quê, por quê, com base em quê, por quem, impacto, próximo passo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f5c7b9d2e4"
down_revision: Union[str, Sequence[str], None] = "e7c9b2a4f8d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "process_decisions",
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
        sa.Column("decision_type", sa.String(), nullable=False, index=True),
        sa.Column("decision_text", sa.Text(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column(
            "basis",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "decided_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("impact", sa.Text(), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'proposta'"),
            index=True,
        ),
        sa.Column(
            "supersedes_decision_id",
            sa.Integer(),
            sa.ForeignKey("process_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, index=True),
    )

    op.create_index(
        "ix_process_decisions_process_macroetapa",
        "process_decisions",
        ["process_id", "macroetapa"],
    )
    op.create_index(
        "ix_process_decisions_tenant_created",
        "process_decisions",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_process_decisions_tenant_created", table_name="process_decisions")
    op.drop_index("ix_process_decisions_process_macroetapa", table_name="process_decisions")
    op.drop_table("process_decisions")
