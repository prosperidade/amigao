"""sprint 2 (E5): remoção lembrada no RotaPasso (tombstone)

Passo removido pelo consultor deixa de ser apagado e passa a ser marcado. Sem
isto, "Atualizar da IA" ressuscitava o que o humano tirou — a linha sumia e a
reconciliação, que casa a proposta da IA contra os passos existentes, não tinha
com o que casar. Ver `app/models/rota.py` (RotaPasso.deleted_at).

Aditiva: nenhuma linha existente muda de comportamento (`deleted_at` nasce NULL
= passo vivo, que é o que todas as linhas de hoje são).

Revision ID: d3b8a1f0c94e
Revises: c7a3f2b81d64
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

revision = "d3b8a1f0c94e"
down_revision = "c7a3f2b81d64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rota_passos",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "rota_passos",
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_rota_passos_deleted_at", "rota_passos", ["deleted_at"], unique=False
    )
    op.create_foreign_key(
        "fk_rota_passos_deleted_by_user",
        "rota_passos",
        "users",
        ["deleted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # As lápides viram apagamento de verdade na volta — é o comportamento que o
    # schema antigo sabia representar. Some a memória de que foram removidas;
    # não some nada que o consultor ainda veja na tela.
    op.execute("DELETE FROM rota_passos WHERE deleted_at IS NOT NULL")
    op.drop_constraint("fk_rota_passos_deleted_by_user", "rota_passos", type_="foreignkey")
    op.drop_index("ix_rota_passos_deleted_at", table_name="rota_passos")
    op.drop_column("rota_passos", "deleted_by_user_id")
    op.drop_column("rota_passos", "deleted_at")
