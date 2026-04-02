"""sprint2_checklist_document_fields

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Novos campos em documents para vínculo com checklist e validade
    op.add_column("documents", sa.Column("checklist_item_id", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

    # Índice para facilitar busca de documentos vencendo
    op.create_index("ix_documents_expires_at", "documents", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_expires_at", table_name="documents")
    op.drop_column("documents", "expires_at")
    op.drop_column("documents", "checklist_item_id")
