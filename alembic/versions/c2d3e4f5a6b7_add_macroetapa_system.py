"""Add macroetapa system: column on processes + macroetapa_checklists table.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-08

Changes:
- Add macroetapa column to processes table
- Create macroetapa_checklists table
- Data migration: set macroetapa for existing processes based on status
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None

# Macroetapa enum values
MACROETAPA_VALUES = [
    "entrada_demanda",
    "diagnostico_preliminar",
    "coleta_documental",
    "diagnostico_tecnico",
    "caminho_regulatorio",
    "orcamento_negociacao",
    "contrato_formalizacao",
]

# Mapping old status -> macroetapa for data migration
STATUS_TO_MACROETAPA = {
    "lead": "entrada_demanda",
    "triagem": "entrada_demanda",
    "diagnostico": "diagnostico_preliminar",
    "planejamento": "caminho_regulatorio",
}


def upgrade() -> None:
    # 1. Add macroetapa column to processes (nullable, no enum constraint — uses String)
    op.add_column(
        "processes",
        sa.Column("macroetapa", sa.String(), nullable=True, index=True),
    )

    # 2. Create macroetapa_checklists table
    op.create_table(
        "macroetapa_checklists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "process_id",
            sa.Integer(),
            sa.ForeignKey("processes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("macroetapa", sa.String(), nullable=False, index=True),
        sa.Column("actions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("completion_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("process_id", "macroetapa", name="uq_macroetapa_process"),
    )

    # 3. Data migration: set macroetapa for existing pre-contract processes
    for old_status, new_macroetapa in STATUS_TO_MACROETAPA.items():
        op.execute(
            sa.text(
                "UPDATE processes SET macroetapa = :macroetapa "
                "WHERE status = :status AND macroetapa IS NULL AND deleted_at IS NULL"
            ).bindparams(macroetapa=new_macroetapa, status=old_status)
        )


def downgrade() -> None:
    op.drop_table("macroetapa_checklists")
    op.drop_column("processes", "macroetapa")
