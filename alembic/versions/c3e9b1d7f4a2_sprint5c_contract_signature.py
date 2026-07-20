"""S5-C — assinatura manual do contrato

Adiciona à `contracts` os campos do registro de assinatura MANUAL (MVP, sem
integração externa — assinatura eletrônica gov.br/Clicksign é dívida pós-MVP):

- ``signed_registered_by_user_id`` (FK users, SET NULL): quem REGISTROU a
  assinatura (consultor) — auditoria de quem/quando (o quando já vive em
  ``signed_at``, campo reservado desde o Sprint 4).
- ``signed_pdf_storage_key`` (String): upload OPCIONAL do PDF já assinado (MinIO).

Preencher ``signed_at`` (já existente) satisfaz o gate E7
(``has_contract_signed``). Ver ADR-030.

Revision ID: c3e9b1d7f4a2
Revises: f1a7c2d9e4b6
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

revision = "c3e9b1d7f4a2"
down_revision = "f1a7c2d9e4b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("signed_registered_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("signed_pdf_storage_key", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_contracts_signed_registered_by",
        "contracts", "users",
        ["signed_registered_by_user_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_contracts_signed_registered_by", "contracts", type_="foreignkey")
    op.drop_column("contracts", "signed_pdf_storage_key")
    op.drop_column("contracts", "signed_registered_by_user_id")
