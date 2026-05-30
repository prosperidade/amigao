"""Cofre de credenciais de portal por cliente (PR 2.3) + merge de 2 heads.

Esta migration tem DUPLO papel:
  1. **Merge** das duas heads que divergiam de `d2c3e4f5a6b8`:
     - `e3d4f5g6a7b8` (PROMPT_7 — ProcessIssueDecision)
     - `e6f7a8b9c0d1` (PR 2.2 — workflow por demand_type)
     Estavam ambas como head (mergeadas em main por PRs independentes), quebrando
     `alembic upgrade head` (ambíguo). Esta revisão reunifica o grafo.
  2. Cria a tabela `credentials` — login/senha de portais externos por cliente.
     A coluna `password_encrypted` guarda ciphertext (ADR-014 / `EncryptedString`).

Revision ID: c0d1e2f3a4b5
Revises: e3d4f5g6a7b8, e6f7a8b9c0d1
Create Date: 2026-05-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = ("e3d4f5g6a7b8", "e6f7a8b9c0d1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("portal", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("login", sa.String(), nullable=True),
        sa.Column("password_encrypted", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_credentials_id", "credentials", ["id"])
    op.create_index("ix_credentials_tenant_id", "credentials", ["tenant_id"])
    op.create_index("ix_credentials_client_id", "credentials", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_credentials_client_id", table_name="credentials")
    op.drop_index("ix_credentials_tenant_id", table_name="credentials")
    op.drop_index("ix_credentials_id", table_name="credentials")
    op.drop_table("credentials")
