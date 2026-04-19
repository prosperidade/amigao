"""Regente v3 Cam2 — add field_sources JSONB to properties

Revision ID: e7c9b2a4f8d1
Revises: d4e6b8f1a3c5
Create Date: 2026-04-19 00:00:00.000000

CAM2IH-007 — Distingue origem dos dados estruturados do imóvel:
raw / ai_extracted / human_validated por campo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7c9b2a4f8d1"
down_revision: Union[str, Sequence[str], None] = "d4e6b8f1a3c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column(
            "field_sources",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("properties", "field_sources")
