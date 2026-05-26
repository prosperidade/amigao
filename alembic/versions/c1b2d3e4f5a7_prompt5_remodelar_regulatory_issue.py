"""PROMPT_5 Onda A — remodelar RegulatoryIssue.

Revision ID: c1b2d3e4f5a7
Revises: b1a2c3d4e5f6
Create Date: 2026-05-25

Substitui o ``type`` enum curto (5 valores, maioria caía em "outro") por:
- ``familia`` (enum estável ~11) + ``codigo_alerta`` (catálogo evolutivo).
- ``severity`` 4 níveis (informativo/atencao/alto/critico) — antes 3.
- Campos ``muda_rota_regulatoria`` / ``muda_escopo_preco_prazo`` /
  ``documentos_cruzados``.

Origem da taxonomia: skill `auditor_imovel/analise_divergencias_documentais`
v1.1.0 (validada pela sócia).

**Passos do upgrade:**

1. Cria enums novos: ``regulatory_familia``, ``regulatory_factibilidade``,
   ``regulatory_severity_v2``.
2. Cria tabela ``regulatory_issue_catalog`` (PK = ``codigo_alerta``).
3. Seed inicial de ~45 entradas (40 da skill + extensões + OUTRO_GENERICO +
   VERIFICACAO_ESPACIAL_PENDENTE).
4. Adiciona colunas em ``regulatory_issues``: ``codigo_alerta`` (FK),
   ``familia``, ``muda_rota_regulatoria``, ``muda_escopo_preco_prazo``,
   ``documentos_cruzados``, ``severity_new`` (enum v2).
5. Migra dados: severity 3→4 (info→informativo / warning→atencao /
   critical→alto). ``type`` antigo → ``codigo_alerta`` + ``familia``
   best-effort (vide _TYPE_TO_CATALOG abaixo).
6. Drop coluna ``severity`` antiga; rename ``severity_new`` → ``severity``.
7. Drop enum antigo ``regulatory_issue_severity`` (3 níveis).
8. Torna ``type`` nullable (deprecated, mantido para retrocompat de leitura).

**Downgrade:** best-effort. Mapeia severity 4→3 com **perda** (`critico`→
`critical`; já bate, e os 3 antigos preservam-se). Drop das colunas novas,
restore do severity 3 e enums. Catálogo é dropado.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models.regulatory_catalog_seed import seed_rows_as_dicts
from app.models.types import PortableJSON

revision = "c1b2d3e4f5a7"
down_revision = "b1a2c3d4e5f6"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Enums (string values)
# ---------------------------------------------------------------------------

_FAMILIA_VALUES = (
    "identificacao",
    "titularidade",
    "area",
    "geoespacial",
    "geo_incra",
    "car",
    "ambiental",
    "fiscal",
    "restricao_risco",
    "licenciamento",
    "validade_documental",
)
_FACTIBILIDADE_VALUES = ("documental", "geoespacial", "consulta_externa")
_SEVERITY_V2_VALUES = ("informativo", "atencao", "alto", "critico")


# Mapeamento type antigo → (codigo_alerta, familia) para a migração de dados.
# Best-effort: registros antigos têm contexto pobre; mapeamos para os códigos
# mais próximos da semântica original.
_TYPE_TO_CATALOG: dict[str, tuple[str, str]] = {
    "area_divergente": ("AREA_MATRICULA_X_CAR", "area"),
    "sobreposicao_app": ("APP_OCUPADA", "ambiental"),
    "sobreposicao_reserva": ("RL_CAR_X_REALIDADE", "ambiental"),
    "poligono_fora_matricula": ("CAR_LOCALIZACAO_DIVERGENTE_REALIDADE", "car"),
    "outro": ("OUTRO_GENERICO", "validade_documental"),
}


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1) Enums novos -------------------------------------------------------
    if is_postgres:
        familia_enum = postgresql.ENUM(*_FAMILIA_VALUES, name="regulatory_familia", create_type=False)
        factibilidade_enum = postgresql.ENUM(*_FACTIBILIDADE_VALUES, name="regulatory_factibilidade", create_type=False)
        severity_v2_enum = postgresql.ENUM(*_SEVERITY_V2_VALUES, name="regulatory_severity_v2", create_type=False)
        familia_enum.create(bind, checkfirst=True)
        factibilidade_enum.create(bind, checkfirst=True)
        severity_v2_enum.create(bind, checkfirst=True)
        familia_col = familia_enum
        factibilidade_col = factibilidade_enum
        severity_v2_col = severity_v2_enum
    else:
        familia_col = sa.Enum(*_FAMILIA_VALUES, name="regulatory_familia")
        factibilidade_col = sa.Enum(*_FACTIBILIDADE_VALUES, name="regulatory_factibilidade")
        severity_v2_col = sa.Enum(*_SEVERITY_V2_VALUES, name="regulatory_severity_v2")

    # 2) Tabela catálogo ---------------------------------------------------
    op.create_table(
        "regulatory_issue_catalog",
        sa.Column("codigo_alerta", sa.String(80), primary_key=True),
        sa.Column("familia", familia_col, nullable=False),
        sa.Column("descricao_curta", sa.String(), nullable=False),
        sa.Column("factibilidade", factibilidade_col, nullable=False),
        sa.Column("severity_base", severity_v2_col, nullable=False),
        sa.Column("muda_rota_regulatoria", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("muda_escopo_preco_prazo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("documentos_cruzados_default", PortableJSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_regulatory_issue_catalog_familia", "regulatory_issue_catalog", ["familia"])
    op.create_index("ix_regulatory_issue_catalog_factibilidade", "regulatory_issue_catalog", ["factibilidade"])

    # 3) Seed inicial — fonte única em ``app/models/regulatory_catalog_seed.py``
    catalog_table = sa.table(
        "regulatory_issue_catalog",
        sa.column("codigo_alerta", sa.String),
        sa.column("familia", sa.String),
        sa.column("descricao_curta", sa.String),
        sa.column("factibilidade", sa.String),
        sa.column("severity_base", sa.String),
        sa.column("muda_rota_regulatoria", sa.Boolean),
        sa.column("muda_escopo_preco_prazo", sa.Boolean),
        sa.column("documentos_cruzados_default", PortableJSON),
    )
    op.bulk_insert(catalog_table, seed_rows_as_dicts())

    # 4) Adicionar colunas em regulatory_issues ---------------------------
    op.add_column("regulatory_issues", sa.Column("codigo_alerta", sa.String(80), nullable=True))
    op.add_column("regulatory_issues", sa.Column("familia", familia_col, nullable=True))
    op.add_column("regulatory_issues", sa.Column("muda_rota_regulatoria", sa.Boolean(), nullable=True))
    op.add_column("regulatory_issues", sa.Column("muda_escopo_preco_prazo", sa.Boolean(), nullable=True))
    op.add_column("regulatory_issues", sa.Column("documentos_cruzados", PortableJSON, nullable=True))
    op.add_column("regulatory_issues", sa.Column("severity_new", severity_v2_col, nullable=True))

    op.create_foreign_key(
        "fk_regulatory_issues_codigo_alerta",
        "regulatory_issues",
        "regulatory_issue_catalog",
        ["codigo_alerta"],
        ["codigo_alerta"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_regulatory_issues_codigo_alerta", "regulatory_issues", ["codigo_alerta"])
    op.create_index("ix_regulatory_issues_familia", "regulatory_issues", ["familia"])

    # 5) Migrar dados existentes ------------------------------------------
    # severity 3→4 níveis: info→informativo, warning→atencao, critical→alto.
    op.execute("""
        UPDATE regulatory_issues
        SET severity_new = CASE severity::text
            WHEN 'info' THEN 'informativo'::regulatory_severity_v2
            WHEN 'warning' THEN 'atencao'::regulatory_severity_v2
            WHEN 'critical' THEN 'alto'::regulatory_severity_v2
            ELSE 'atencao'::regulatory_severity_v2
        END
    """) if is_postgres else op.execute("""
        UPDATE regulatory_issues
        SET severity_new = CASE severity
            WHEN 'info' THEN 'informativo'
            WHEN 'warning' THEN 'atencao'
            WHEN 'critical' THEN 'alto'
            ELSE 'atencao'
        END
    """)

    # type → codigo_alerta + familia (best-effort).
    for old_type, (codigo, fam) in _TYPE_TO_CATALOG.items():
        if is_postgres:
            op.execute(f"""
                UPDATE regulatory_issues
                SET codigo_alerta = '{codigo}',
                    familia = '{fam}'::regulatory_familia
                WHERE type::text = '{old_type}'
            """)
        else:
            op.execute(f"""
                UPDATE regulatory_issues
                SET codigo_alerta = '{codigo}',
                    familia = '{fam}'
                WHERE type = '{old_type}'
            """)

    # 6) Drop severity antiga, rename severity_new ------------------------
    op.alter_column("regulatory_issues", "severity_new", nullable=False)
    op.drop_column("regulatory_issues", "severity")
    op.alter_column("regulatory_issues", "severity_new", new_column_name="severity")

    # 7) Drop enum antigo (só Postgres) -----------------------------------
    if is_postgres:
        # Indices que referenciam o enum antigo precisam ser recriados após
        # rename, mas alembic já manteve o index no rename. Drop enum.
        op.execute("DROP TYPE regulatory_issue_severity")

    # 8) type vira nullable (deprecated) ----------------------------------
    op.alter_column("regulatory_issues", "type", nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Recria severity 3 níveis
    if is_postgres:
        severity_old = postgresql.ENUM("info", "warning", "critical", name="regulatory_issue_severity", create_type=False)
        severity_old.create(bind, checkfirst=True)
        severity_old_col = severity_old
    else:
        severity_old_col = sa.Enum("info", "warning", "critical", name="regulatory_issue_severity")

    op.add_column("regulatory_issues", sa.Column("severity_old", severity_old_col, nullable=True))
    if is_postgres:
        op.execute("""
            UPDATE regulatory_issues
            SET severity_old = CASE severity::text
                WHEN 'informativo' THEN 'info'::regulatory_issue_severity
                WHEN 'atencao' THEN 'warning'::regulatory_issue_severity
                WHEN 'alto' THEN 'critical'::regulatory_issue_severity
                WHEN 'critico' THEN 'critical'::regulatory_issue_severity
                ELSE 'warning'::regulatory_issue_severity
            END
        """)
    else:
        op.execute("""
            UPDATE regulatory_issues
            SET severity_old = CASE severity
                WHEN 'informativo' THEN 'info'
                WHEN 'atencao' THEN 'warning'
                WHEN 'alto' THEN 'critical'
                WHEN 'critico' THEN 'critical'
                ELSE 'warning'
            END
        """)
    op.alter_column("regulatory_issues", "severity_old", nullable=False)
    op.drop_column("regulatory_issues", "severity")
    op.alter_column("regulatory_issues", "severity_old", new_column_name="severity")

    # type volta a NOT NULL — best-effort
    op.execute("UPDATE regulatory_issues SET type = 'outro' WHERE type IS NULL")
    op.alter_column("regulatory_issues", "type", nullable=False)

    op.drop_index("ix_regulatory_issues_familia", table_name="regulatory_issues")
    op.drop_index("ix_regulatory_issues_codigo_alerta", table_name="regulatory_issues")
    op.drop_constraint("fk_regulatory_issues_codigo_alerta", "regulatory_issues", type_="foreignkey")
    op.drop_column("regulatory_issues", "documentos_cruzados")
    op.drop_column("regulatory_issues", "muda_escopo_preco_prazo")
    op.drop_column("regulatory_issues", "muda_rota_regulatoria")
    op.drop_column("regulatory_issues", "familia")
    op.drop_column("regulatory_issues", "codigo_alerta")

    op.drop_index("ix_regulatory_issue_catalog_factibilidade", table_name="regulatory_issue_catalog")
    op.drop_index("ix_regulatory_issue_catalog_familia", table_name="regulatory_issue_catalog")
    op.drop_table("regulatory_issue_catalog")

    if is_postgres:
        op.execute("DROP TYPE regulatory_severity_v2")
        op.execute("DROP TYPE regulatory_factibilidade")
        op.execute("DROP TYPE regulatory_familia")
