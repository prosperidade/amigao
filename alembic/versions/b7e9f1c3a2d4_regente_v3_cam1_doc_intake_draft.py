"""Regente v3 Cam1 — add intake_draft_id to documents

Revision ID: b7e9f1c3a2d4
Revises: a6d8f2c4b1e3
Create Date: 2026-04-18 18:30:00.000000

Permite que documentos sejam anexados a um rascunho antes do processo existir
(CAM1-007 upload durante intake, CAM1-005 importar para análise inicial).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e9f1c3a2d4"
down_revision: Union[str, Sequence[str], None] = "a6d8f2c4b1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "intake_draft_id",
            sa.Integer(),
            sa.ForeignKey("intake_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_documents_intake_draft_id",
        "documents",
        ["intake_draft_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_intake_draft_id", table_name="documents")
    op.drop_column("documents", "intake_draft_id")
