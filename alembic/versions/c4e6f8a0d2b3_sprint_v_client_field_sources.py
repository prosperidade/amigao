"""Sprint V (F2) — adiciona Client.field_sources (JSONB).

Revision ID: c4e6f8a0d2b3
Revises: b3d5c7e9f1a2
Create Date: 2026-05-06

Espelha Property.field_sources para o Client. Necessário pra UI exibir badge
"extraído pela IA" também no Cliente Hub e pra registrar validação humana de
campos do cadastro (cpf_cnpj, full_name, legal_name, email, phone).
"""
from alembic import op
import sqlalchemy as sa

from app.models.types import PortableJSON


revision = "c4e6f8a0d2b3"
down_revision = "b3d5c7e9f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("field_sources", PortableJSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clients", "field_sources")
