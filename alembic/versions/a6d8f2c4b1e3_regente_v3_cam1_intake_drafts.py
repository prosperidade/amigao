"""Regente v3 Cam1 — intake_drafts table

Revision ID: a6d8f2c4b1e3
Revises: f5b7c9a1d3e2
Create Date: 2026-04-18 00:05:00.000000

Cria tabela intake_drafts para "salvar e continuar depois" (CAM1-008/009).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a6d8f2c4b1e3"
down_revision: Union[str, Sequence[str], None] = "f5b7c9a1d3e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DRAFT_STATE_VALUES = (
    "rascunho",
    "pronto_para_criar",
    "card_criado",
    "base_complementada",
)


def upgrade() -> None:
    state_enum = postgresql.ENUM(*DRAFT_STATE_VALUES, name="intakedraftstate")
    state_enum.create(op.get_bind(), checkfirst=True)

    # create_type=False: tipo já criado acima, não tentar criar novamente
    state_enum_col = postgresql.ENUM(
        *DRAFT_STATE_VALUES, name="intakedraftstate", create_type=False
    )

    op.create_table(
        "intake_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "state",
            state_enum_col,
            nullable=False,
            server_default="rascunho",
        ),
        sa.Column("entry_type", sa.String(), nullable=True),
        sa.Column("form_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "linked_process_id",
            sa.Integer(),
            sa.ForeignKey("processes.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index(
        "ix_intake_drafts_state",
        "intake_drafts",
        ["state"],
    )


def downgrade() -> None:
    op.drop_index("ix_intake_drafts_state", table_name="intake_drafts")
    op.drop_table("intake_drafts")
    op.execute("DROP TYPE IF EXISTS intakedraftstate")
