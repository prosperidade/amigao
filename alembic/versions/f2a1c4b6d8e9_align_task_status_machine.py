"""Align task statuses with business rules

Revision ID: f2a1c4b6d8e9
Revises: e91d20acba9c
Create Date: 2026-04-01 03:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f2a1c4b6d8e9"
down_revision: Union[str, Sequence[str], None] = "e91d20acba9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_VALUES = ("todo", "in_progress", "review", "done")
NEW_VALUES = ("backlog", "a_fazer", "em_progresso", "aguardando", "revisao", "concluida", "cancelada")


def upgrade() -> None:
    new_enum = postgresql.ENUM(*NEW_VALUES, name="taskstatus")
    old_enum = postgresql.ENUM(*OLD_VALUES, name="taskstatus_old")

    op.execute("ALTER TYPE taskstatus RENAME TO taskstatus_old")
    new_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        """
        ALTER TABLE tasks
        ALTER COLUMN status TYPE taskstatus
        USING (
            CASE status::text
                WHEN 'todo' THEN 'a_fazer'
                WHEN 'in_progress' THEN 'em_progresso'
                WHEN 'review' THEN 'revisao'
                WHEN 'done' THEN 'concluida'
            END
        )::taskstatus
        """
    )
    old_enum.drop(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    restored_enum = postgresql.ENUM(*OLD_VALUES, name="taskstatus")
    current_enum = postgresql.ENUM(*NEW_VALUES, name="taskstatus_old")

    op.execute("ALTER TYPE taskstatus RENAME TO taskstatus_old")
    restored_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        """
        ALTER TABLE tasks
        ALTER COLUMN status TYPE taskstatus
        USING (
            CASE status::text
                WHEN 'backlog' THEN 'todo'
                WHEN 'a_fazer' THEN 'todo'
                WHEN 'em_progresso' THEN 'in_progress'
                WHEN 'aguardando' THEN 'in_progress'
                WHEN 'revisao' THEN 'review'
                WHEN 'concluida' THEN 'done'
                WHEN 'cancelada' THEN 'review'
            END
        )::taskstatus
        """
    )
    current_enum.drop(op.get_bind(), checkfirst=False)
