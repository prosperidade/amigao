"""PR 2.1 — provider e provider_account_id em communication_threads

Adiciona rastreio do provider concreto do canal (evolution/zapi/resend_inbound/
internal) e da conta/instância de origem. Reversível.

Revision ID: pr21_wa_provider
Revises: c0d1e2f3a4b5
Create Date: 2026-05-31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "pr21_wa_provider"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "communication_threads",
        sa.Column("provider", sa.String(), nullable=False, server_default="internal"),
    )
    op.add_column(
        "communication_threads",
        sa.Column("provider_account_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("communication_threads", "provider_account_id")
    op.drop_column("communication_threads", "provider")
