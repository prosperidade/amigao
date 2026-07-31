"""rota_versoes — regenerar nunca destrói (validação Isis 30/07)

Aditiva: cria a tabela de fotos da Rota. Nenhuma coluna existente é tocada.

Revision ID: d7f1a3c9e2b4
Revises: c4464efa9ad4
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d7f1a3c9e2b4"
down_revision = "c4464efa9ad4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rota_versoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("rota_id", sa.Integer(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(length=50), nullable=False,
                  server_default="regeneracao"),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rota_id"], ["rotas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rota_id", "versao", name="uq_rota_versoes_rota_versao"),
    )
    op.create_index(op.f("ix_rota_versoes_id"), "rota_versoes", ["id"])
    op.create_index(op.f("ix_rota_versoes_tenant_id"), "rota_versoes", ["tenant_id"])
    op.create_index(op.f("ix_rota_versoes_rota_id"), "rota_versoes", ["rota_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_rota_versoes_rota_id"), table_name="rota_versoes")
    op.drop_index(op.f("ix_rota_versoes_tenant_id"), table_name="rota_versoes")
    op.drop_index(op.f("ix_rota_versoes_id"), table_name="rota_versoes")
    op.drop_table("rota_versoes")
