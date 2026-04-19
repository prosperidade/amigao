"""Regente v3 Cam3 — add state column to macroetapa_checklists

Revision ID: c8a1e5d7f3b2
Revises: b7e9f1c3a2d4
Create Date: 2026-04-18 21:00:00.000000

CAM3FT-004 — Estado formal por etapa (cache; valor canônico vem de
compute_macroetapa_state em runtime).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8a1e5d7f3b2"
down_revision: Union[str, Sequence[str], None] = "b7e9f1c3a2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "macroetapa_checklists",
        sa.Column("state", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_macroetapa_checklists_state",
        "macroetapa_checklists",
        ["state"],
    )


def downgrade() -> None:
    op.drop_index("ix_macroetapa_checklists_state", table_name="macroetapa_checklists")
    op.drop_column("macroetapa_checklists", "state")
