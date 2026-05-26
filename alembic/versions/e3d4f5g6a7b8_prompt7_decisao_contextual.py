"""PROMPT_7 — decisão do consultor contextual ao processo (ADR-012).

Revision ID: e3d4f5g6a7b8
Revises: d2c3e4f5a6b8
Create Date: 2026-05-26

Move os 3 campos de decisão (`decisao_consultor`, `decisao_consultor_justificativa`,
`decisao_consultor_at`) de `regulatory_issues` para a nova tabela
`process_issue_decisions` — uma decisão por par `(processo × issue)`.

Razão: ADR-012 da Isis (validado 26/05). A decisão do consultor é **contextual
ao processo**, não perene no imóvel — titularidade torta pesa diferente para
vender e para dar como garantia ao banco. Cada processo recomeça do zero.

**Decisões aplicadas (confirmadas pelo Andre):**
- Nomes **encurtados** na tabela nova: `decisao_consultor` → `decisao`,
  `decisao_consultor_at` → `decided_at`, `decisao_consultor_justificativa`
  → `justificativa`. O contexto da tabela já indica; redundância sai.
- **Drop sem backfill** — não há dados em prod ainda (dev/staging). Migration
  destrutiva pra colunas antigas; downgrade recria as colunas vazias.
- `decided_by_user_id` (FK users) é **novo** vs PROMPT_6 — captura quem
  decidiu além do timestamp.

Estrutura:
- `process_issue_decisions(id, tenant_id, process_id, issue_id, decisao,
  justificativa, decided_by_user_id, decided_at, created_at, updated_at)`
- `UNIQUE(process_id, issue_id)` — uma decisão por par.
- Enum `regulatory_decisao_consultor` **mantido** (PROMPT_6); só muda onde a
  coluna mora.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3d4f5g6a7b8"
down_revision = "d2c3e4f5a6b8"
branch_labels = None
depends_on = None


_DECISAO_VALUES = (
    "corrigir_antes",
    "seguir_com_ressalva",
    "solicitar_doc",
    "fora_escopo",
    "ignorar_justificado",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Enum `regulatory_decisao_consultor` já existe (criado no PROMPT_6).
    # Só referenciamos com `create_type=False` para a nova tabela.
    if is_postgres:
        decisao_enum = postgresql.ENUM(*_DECISAO_VALUES, name="regulatory_decisao_consultor", create_type=False)
        decisao_col = decisao_enum
    else:
        decisao_col = sa.Enum(*_DECISAO_VALUES, name="regulatory_decisao_consultor")

    # 1) Cria tabela `process_issue_decisions` ----------------------------
    op.create_table(
        "process_issue_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "process_id", sa.Integer(),
            sa.ForeignKey("processes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "issue_id", sa.Integer(),
            sa.ForeignKey("regulatory_issues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decisao", decisao_col, nullable=False),
        sa.Column("justificativa", sa.String(), nullable=True),
        sa.Column(
            "decided_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "process_id", "issue_id",
            name="uq_process_issue_decisions_pid_iid",
        ),
    )
    op.create_index(
        "ix_process_issue_decisions_tenant_id",
        "process_issue_decisions", ["tenant_id"],
    )
    op.create_index(
        "ix_process_issue_decisions_process_id",
        "process_issue_decisions", ["process_id"],
    )
    op.create_index(
        "ix_process_issue_decisions_issue_id",
        "process_issue_decisions", ["issue_id"],
    )

    # 2) Drop 3 colunas do `regulatory_issues` ---------------------------
    # Drop sem backfill (decisão do Andre — dev/staging, sem dados em prod).
    op.drop_index("ix_regulatory_issues_decisao_consultor", table_name="regulatory_issues")
    op.drop_column("regulatory_issues", "decisao_consultor_at")
    op.drop_column("regulatory_issues", "decisao_consultor_justificativa")
    op.drop_column("regulatory_issues", "decisao_consultor")


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        decisao_enum = postgresql.ENUM(*_DECISAO_VALUES, name="regulatory_decisao_consultor", create_type=False)
        decisao_col = decisao_enum
    else:
        decisao_col = sa.Enum(*_DECISAO_VALUES, name="regulatory_decisao_consultor")

    # Recria as 3 colunas no regulatory_issues (todas nullable como no PROMPT_6).
    op.add_column("regulatory_issues", sa.Column("decisao_consultor", decisao_col, nullable=True))
    op.add_column(
        "regulatory_issues",
        sa.Column("decisao_consultor_justificativa", sa.String(), nullable=True),
    )
    op.add_column(
        "regulatory_issues",
        sa.Column("decisao_consultor_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_regulatory_issues_decisao_consultor",
        "regulatory_issues", ["decisao_consultor"],
    )

    # Drop tabela nova.
    op.drop_index("ix_process_issue_decisions_issue_id", table_name="process_issue_decisions")
    op.drop_index("ix_process_issue_decisions_process_id", table_name="process_issue_decisions")
    op.drop_index("ix_process_issue_decisions_tenant_id", table_name="process_issue_decisions")
    op.drop_table("process_issue_decisions")
