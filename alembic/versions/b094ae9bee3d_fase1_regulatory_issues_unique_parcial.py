"""Fase 1 (N1 item 6) — dívida #48: UNIQUE parcial em regulatory_issues.

Colunas novas `tema`/`subject_ref` (nullable — legado fica NULL, Postgres
trata NULL como distinto em UNIQUE, então registros antigos nunca colidem
entre si). Índice único parcial sobre
`(tenant_id, property_id, codigo_alerta, tema, subject_ref)` para
`resolved_at IS NULL` — cinto de segurança no banco (dedupe hoje é só
app-level, `_persist_issues`). Sweep table-wide em prod (06/07) confirmou
ZERO duplicatas em `(tenant_id, property_id, codigo_alerta)` entre linhas
não resolvidas — migration segura de aplicar sem dado a limpar antes.

Revision ID: b094ae9bee3d
Revises: e1955dd65b66
Create Date: 2026-07-07

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b094ae9bee3d"
down_revision = "e1955dd65b66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regulatory_issues", sa.Column("tema", sa.String(), nullable=True))
    op.add_column("regulatory_issues", sa.Column("subject_ref", sa.String(), nullable=True))
    op.create_index(
        "uq_regulatory_issues_chave_estavel_aberta",
        "regulatory_issues",
        ["tenant_id", "property_id", "codigo_alerta", "tema", "subject_ref"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_regulatory_issues_chave_estavel_aberta", table_name="regulatory_issues")
    op.drop_column("regulatory_issues", "subject_ref")
    op.drop_column("regulatory_issues", "tema")
