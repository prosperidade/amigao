"""Regente Sprint F Bloco 3 — intake_drafts.expires_at

Revision ID: c9f1a3b5d7e2
Revises: b7d9e1f3a5c8
Create Date: 2026-04-19 16:30:00.000000

Adiciona coluna expires_at na tabela intake_drafts e backfill para rascunhos
existentes (expiração = created_at + 15 dias, se já for passado, = now + 15d).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9f1a3b5d7e2"
down_revision: Union[str, Sequence[str], None] = "b7d9e1f3a5c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "intake_drafts",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_intake_drafts_expires_at",
        "intake_drafts",
        ["expires_at"],
    )

    # Backfill: todo draft em estado 'rascunho' ganha expires_at = now + 15d.
    # Drafts em estado terminal (card_criado, base_complementada) ficam com NULL
    # para não serem varridos pelo cleanup.
    op.execute(
        """
        UPDATE intake_drafts
        SET expires_at = NOW() + INTERVAL '15 days'
        WHERE state IN ('rascunho', 'pronto_para_criar')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_intake_drafts_expires_at", table_name="intake_drafts")
    op.drop_column("intake_drafts", "expires_at")
