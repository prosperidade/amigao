"""Sprint 4 — campo `matriculas_contiguas` (tri-state) no Property.

Ficha 07 §9: grupo de matrículas contíguas do mesmo titular = um imóvel rural,
um CAR (Lei 8.629/93 art. 4º I). O campo registra a DECLARAÇÃO do consultor:
NULL = não informado (estado de todo o legado — sem backfill), True/False =
declarado. A declaração grava selo `human_validated` em `field_sources`
(padrão Sprint 3). Ver ADR-023.

Revision ID: b7c9d1e3f5a7
Revises: a3b5d7f9c1e3
Create Date: 2026-07-04

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c9d1e3f5a7"
down_revision = "a3b5d7f9c1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column("matriculas_contiguas", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("properties", "matriculas_contiguas")
