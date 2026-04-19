"""Regente v3 Cam1 — add entry_type and initial_summary to processes

Revision ID: f5b7c9a1d3e2
Revises: e4f5a6b7c8d9
Create Date: 2026-04-18 00:00:00.000000

Adiciona ao Process:
  - entry_type (EntryType enum): 5 cenários da Camada 1 do Regente
  - initial_summary (Text): resumo curto da demanda na voz do cliente (separado
    da description técnica)

Referência: docs/MUDANCAS_REGENTE.md (CAM1-001, CAM1-012)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f5b7c9a1d3e2"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENTRY_TYPE_VALUES = (
    "novo_cliente_novo_imovel",
    "cliente_existente_novo_imovel",
    "cliente_existente_imovel_existente",
    "complementar_base_existente",
    "importar_documentos",
)


def upgrade() -> None:
    entry_type_enum = postgresql.ENUM(*ENTRY_TYPE_VALUES, name="entrytype")
    entry_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "processes",
        sa.Column(
            "entry_type",
            sa.Enum(*ENTRY_TYPE_VALUES, name="entrytype"),
            nullable=True,
        ),
    )
    op.add_column("processes", sa.Column("initial_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("processes", "initial_summary")
    op.drop_column("processes", "entry_type")
    op.execute("DROP TYPE IF EXISTS entrytype")
