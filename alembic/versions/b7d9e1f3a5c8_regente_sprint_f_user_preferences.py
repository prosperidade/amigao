"""Regente Sprint F Bloco 2 — user preferences column

Revision ID: b7d9e1f3a5c8
Revises: a3f5c7b9d2e4
Create Date: 2026-04-19 16:00:00.000000

Adiciona coluna JSONB `preferences` à tabela users para a tela de Configurações
(Camada 4). Comporta 4 grupos: profile, notifications, operational, ai.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7d9e1f3a5c8"
down_revision: Union[str, Sequence[str], None] = "a3f5c7b9d2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferences")
