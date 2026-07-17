"""forense (caso Isis) — desativação de matrícula rejeitada na Conferência

Contrato da Conferência (forense do teste da Isis): REJEITAR a staging que
materializou uma matrícula deve DESFAZER o efeito — a matrícula sai da soma da
área. `matriculas` não tinha soft-delete: uma matrícula criada a partir de
staging depois rejeitado ficava órfã e continuava somando. Adiciona
`deactivated_at` (+ `deactivation_reason`) para desativação REVERSÍVEL e
auditável (nunca hard-delete): `Property.area_total_matriculas()` passa a somar
só matrículas ativas; reaceitar a staging reativa (idempotente na consolidação).

Revision ID: fa9c1d3b5e70
Revises: b094ae9bee3d
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "fa9c1d3b5e70"
down_revision = "b094ae9bee3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matriculas",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "matriculas",
        sa.Column("deactivation_reason", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("matriculas", "deactivation_reason")
    op.drop_column("matriculas", "deactivated_at")
