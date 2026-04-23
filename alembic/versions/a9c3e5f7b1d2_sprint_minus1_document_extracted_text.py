"""Sprint -1 D — Document.extracted_text + extracted_at

Revision ID: a9c3e5f7b1d2
Revises: f8b2c4d6e0a1
Create Date: 2026-04-23 18:00:00.000000

Corrige dívida documentada na auditoria de 2026-04-23:
ExtratorAgent busca Document.extracted_text mas o campo não existia no model.
Hoje o fluxo só funciona porque o texto é sempre passado em metadata.

Adiciona:
- extracted_text (Text, nullable) — texto OCR/PDF extraído do documento
- extracted_at (DateTime, nullable) — timestamp da extração

Aditiva, sem backfill. Campos ficam NULL para documentos antigos.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c3e5f7b1d2"
down_revision: str | Sequence[str] | None = "f8b2c4d6e0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "extracted_at")
    op.drop_column("documents", "extracted_text")
