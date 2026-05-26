"""PROMPT_6 — camada 2 do Princípio 1 (reconciliação dos 3 status).

Revision ID: d2c3e4f5a6b8
Revises: c1b2d3e4f5a7
Create Date: 2026-05-26

Implementa a **Opção A** do `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md`:
três campos ortogonais que medem dimensões diferentes do mesmo alerta:

1. ``status_achado`` (Enum NOT NULL default ``suspeita``) — natureza do indício.
2. ``decisao_consultor`` (Enum nullable) — ação escolhida sobre alerta crítico.
   Os 5 botões da P4 (camada 2 do Princípio 1). Obrigatório só para
   ``severity=critico`` (gate no PATCH /validate).
3. ``status_saneamento`` (Enum NOT NULL default ``pendente``) — progresso
   prático da resolução.

Adiciona também ``decisao_consultor_justificativa`` (texto livre) e
``decisao_consultor_at`` (timestamp da decisão).

Migration aditiva pura — não migra dados, não dropa nada. Registros
existentes ganham os defaults explícitos (suspeita, pendente). ``decisao_consultor``
fica NULL em registros antigos — consultor preenche conforme revisa.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d2c3e4f5a6b8"
down_revision = "c1b2d3e4f5a7"
branch_labels = None
depends_on = None


_STATUS_ACHADO_VALUES = ("suspeita", "confirmada", "descartada", "resolvida", "ignorada")
_DECISAO_CONSULTOR_VALUES = (
    "corrigir_antes",
    "seguir_com_ressalva",
    "solicitar_doc",
    "fora_escopo",
    "ignorar_justificado",
)
_STATUS_SANEAMENTO_VALUES = (
    "pendente",
    "em_validacao",
    "saneado",
    "descartado",
    "nao_aplicavel",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ── Enums novos ──────────────────────────────────────────────────────
    if is_postgres:
        status_achado_enum = postgresql.ENUM(
            *_STATUS_ACHADO_VALUES, name="regulatory_status_achado", create_type=False,
        )
        decisao_consultor_enum = postgresql.ENUM(
            *_DECISAO_CONSULTOR_VALUES, name="regulatory_decisao_consultor", create_type=False,
        )
        status_saneamento_enum = postgresql.ENUM(
            *_STATUS_SANEAMENTO_VALUES, name="regulatory_status_saneamento", create_type=False,
        )
        status_achado_enum.create(bind, checkfirst=True)
        decisao_consultor_enum.create(bind, checkfirst=True)
        status_saneamento_enum.create(bind, checkfirst=True)
        status_achado_col = status_achado_enum
        decisao_consultor_col = decisao_consultor_enum
        status_saneamento_col = status_saneamento_enum
    else:
        status_achado_col = sa.Enum(*_STATUS_ACHADO_VALUES, name="regulatory_status_achado")
        decisao_consultor_col = sa.Enum(*_DECISAO_CONSULTOR_VALUES, name="regulatory_decisao_consultor")
        status_saneamento_col = sa.Enum(*_STATUS_SANEAMENTO_VALUES, name="regulatory_status_saneamento")

    # ── Colunas em regulatory_issues ─────────────────────────────────────
    op.add_column(
        "regulatory_issues",
        sa.Column(
            "status_achado",
            status_achado_col,
            nullable=False,
            server_default="suspeita",
        ),
    )
    op.add_column(
        "regulatory_issues",
        sa.Column("decisao_consultor", decisao_consultor_col, nullable=True),
    )
    op.add_column(
        "regulatory_issues",
        sa.Column("decisao_consultor_justificativa", sa.String(), nullable=True),
    )
    op.add_column(
        "regulatory_issues",
        sa.Column("decisao_consultor_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "regulatory_issues",
        sa.Column(
            "status_saneamento",
            status_saneamento_col,
            nullable=False,
            server_default="pendente",
        ),
    )

    # Index para o gate do PATCH /validate (filtra por severity=critico
    # + decisao_consultor IS NULL). Mais eficiente que scan completo.
    op.create_index(
        "ix_regulatory_issues_decisao_consultor",
        "regulatory_issues",
        ["decisao_consultor"],
    )
    op.create_index(
        "ix_regulatory_issues_status_achado",
        "regulatory_issues",
        ["status_achado"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_index("ix_regulatory_issues_status_achado", table_name="regulatory_issues")
    op.drop_index("ix_regulatory_issues_decisao_consultor", table_name="regulatory_issues")
    op.drop_column("regulatory_issues", "status_saneamento")
    op.drop_column("regulatory_issues", "decisao_consultor_at")
    op.drop_column("regulatory_issues", "decisao_consultor_justificativa")
    op.drop_column("regulatory_issues", "decisao_consultor")
    op.drop_column("regulatory_issues", "status_achado")

    if is_postgres:
        op.execute("DROP TYPE regulatory_status_saneamento")
        op.execute("DROP TYPE regulatory_decisao_consultor")
        op.execute("DROP TYPE regulatory_status_achado")
