"""S5-A — proposta nasce da Rota + cadeia de versões

Adiciona à `proposals`:
- ``rota_id`` (FK rotas, SET NULL): a Rota validada que originou o escopo da
  proposta (proveniência no nível da proposta; a rastreabilidade fina de cada
  item vive em ``scope_items[].rota_passo_id``, JSON, sem coluna nova).
- ``previous_version_id`` (FK self, SET NULL): renegociação — a versão N+1
  gerada a partir de uma recusada/expirada aponta a anterior (histórico
  preservado).

Revision ID: d4b8e2f1a6c9
Revises: c7d3e1a9f0b2
Create Date: 2026-07-18
"""

import sqlalchemy as sa
from alembic import op

revision = "d4b8e2f1a6c9"
down_revision = "c7d3e1a9f0b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("rota_id", sa.Integer(), nullable=True))
    op.add_column("proposals", sa.Column("previous_version_id", sa.Integer(), nullable=True))
    op.create_index("ix_proposals_rota_id", "proposals", ["rota_id"])
    op.create_foreign_key(
        "fk_proposals_rota", "proposals", "rotas", ["rota_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_proposals_previous_version", "proposals", "proposals",
        ["previous_version_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_proposals_previous_version", "proposals", type_="foreignkey")
    op.drop_constraint("fk_proposals_rota", "proposals", type_="foreignkey")
    op.drop_index("ix_proposals_rota_id", table_name="proposals")
    op.drop_column("proposals", "previous_version_id")
    op.drop_column("proposals", "rota_id")
