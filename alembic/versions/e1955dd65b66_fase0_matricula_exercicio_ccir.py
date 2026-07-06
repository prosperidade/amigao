"""Fase 0 (gap-analysis Ficha 07, item 8) — campo `exercicio_ccir` na Matricula.

CCIR é documento ANUAL — o exercício (ano) permite o auditor emitir
CCIR_EXERCICIO_ANTERIOR (código já existia no catálogo, `regulatory_catalog_seed.py`,
sem emissor) quando `exercicio_ccir < ano corrente`. Nullable: legado sem
backfill, extração preenche daqui pra frente.

Revision ID: e1955dd65b66
Revises: b7c9d1e3f5a7
Create Date: 2026-07-06

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e1955dd65b66"
down_revision = "b7c9d1e3f5a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matriculas",
        sa.Column("exercicio_ccir", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("matriculas", "exercicio_ccir")
