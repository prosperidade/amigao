"""Regente Sprint G — adiciona 'blocked' ao enum ClientStatus

Revision ID: d8b3f7c2e5a9
Revises: c9f1a3b5d7e2
Create Date: 2026-04-20 10:00:00.000000

Cam2 (Cliente Hub) — a sócia decidiu em 2026-04-19 que os status operacionais do
cliente são: ativo / em andamento / sem casos ativos / bloqueado.

Os valores "em andamento" e "sem casos ativos" são DERIVADOS (computados a partir
de `has_active_cases`) — não persistidos. Apenas "bloqueado" é um novo estado
persistido que o consultor seta manualmente, ortogonal a lead/active/inactive.

Mapa visual (no Cliente Hub):
    status=active  & cases_active > 0  → "em andamento"
    status=active  & cases_active == 0 → "sem casos ativos"
    status=blocked                     → "bloqueado"
    status=lead/inactive/delinquent    → mantém label original
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d8b3f7c2e5a9"
down_revision: Union[str, Sequence[str], None] = "c9f1a3b5d7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE clientstatus ADD VALUE IF NOT EXISTS 'blocked'")


def downgrade() -> None:
    # PostgreSQL não suporta remover valores de enum sem recriar o tipo.
    # Deixado como no-op por segurança (mesmo padrão do agent_system migration).
    pass
