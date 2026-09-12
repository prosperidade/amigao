"""Frente K — properties.rl_area_ha: a ÁREA de Reserva Legal ganha coluna própria.

O CAR declara `rl_declarada_ha` (um número em hectares) e a extração o
roteava para `properties.rl_status` — coluna de ESTADO, vocabulário
`averbada | proposta | pendente | cancelada`. Medido no gate E2E de 12/09:
o Hub exibia "Reserva Legal: 437,7632" no lugar do estado, e a ponte
matrícula→imóvel (que escreve 'averbada') disputava a mesma coluna com um
número. Área é número, status é estado: dois fatos, duas colunas.

Aditiva e reversível. Nenhum backfill: `rl_status` legado com número dentro
é dado sujo de produção e sai pela reconciliação normal da Conferência —
adivinhar aqui qual string é área e qual é estado seria inventar.

Revision ID: c7e1a94d2f60
Revises: b8d4e1f7a209
Create Date: 2026-09-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e1a94d2f60"
down_revision: str | Sequence[str] | None = "b8d4e1f7a209"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("rl_area_ha", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "rl_area_ha")
