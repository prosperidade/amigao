"""Sprint R — teto mensal de IA por tenant

Revision ID: f8b2c4d6e0a1
Revises: e5a7c9b1f3d6
Create Date: 2026-04-23 10:00:00.000000

Adiciona Tenant.ai_monthly_budget_usd (nullable).

- NULL  ⇒ usa AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT do settings.
- 0     ⇒ ilimitado (tanto aqui quanto no default global).
- > 0   ⇒ teto mensal em USD; 429 quando `sum(AIJob.cost_usd)` do mês corrente ≥ teto.

Aditiva, sem backfill.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8b2c4d6e0a1"
down_revision: Union[str, Sequence[str], None] = "e5a7c9b1f3d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("ai_monthly_budget_usd", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "ai_monthly_budget_usd")
