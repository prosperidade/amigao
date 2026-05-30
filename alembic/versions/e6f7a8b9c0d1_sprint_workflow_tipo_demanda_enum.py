"""Sprint workflow tipo demanda — expand DemandType enum

Revision ID: e6f7a8b9c0d1
Revises: d2c3e4f5a6b8
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d2c3e4f5a6b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_VALUES = (
    "car",
    "retificacao_car",
    "licenciamento",
    "regularizacao_fundiaria",
    "outorga",
    "defesa",
    "compensacao",
    "exigencia_bancaria",
    "prad",
    "misto",
    "nao_identificado",
)

NEW_VALUES = (
    "sobreposicao",
    "supressao",
    "due_diligence",
    "arrendamento",
    "condicionantes_antigas",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for value in NEW_VALUES:
                op.execute(f"ALTER TYPE demandtype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        UPDATE processes
        SET demand_type = 'nao_identificado'
        WHERE demand_type::text IN (
            'sobreposicao',
            'supressao',
            'due_diligence',
            'arrendamento',
            'condicionantes_antigas'
        )
        """
    )
    op.execute("ALTER TYPE demandtype RENAME TO demandtype_old")
    restored = postgresql.ENUM(*OLD_VALUES, name="demandtype")
    restored.create(op.get_bind(), checkfirst=False)
    op.execute(
        """
        ALTER TABLE processes
        ALTER COLUMN demand_type TYPE demandtype
        USING demand_type::text::demandtype
        """
    )
    op.execute("DROP TYPE demandtype_old")
