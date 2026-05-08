"""Sprint A1 (Tarefa D1) — RegulatoryDiagnosis + RegulatoryIssue.

Revision ID: a8e1d4c7f3b6
Revises: c4e6f8a0d2b3
Create Date: 2026-05-08

Cria as duas entidades regulatórias de 1ª classe (audit gap B3):

* ``regulatory_diagnoses`` (versionado por processo)
* ``regulatory_issues`` (vinculado a property + opcional document)

Sem tabela associativa N–N (decisão Q4 da Fase 0): quando um diagnóstico
quiser referenciar issues, lista IDs no próprio ``content`` JSONB.

VALIDAÇÃO MANUAL (Q6 da Fase 0 — testes não usam Alembic, valem
``Base.metadata.create_all``)::

    docker compose exec api alembic upgrade head
    # confere via psql que as 2 tabelas existem
    docker compose exec api alembic downgrade -1
    # confere via psql que as 2 tabelas sumiram + ENUMs também

ENUMs criados manualmente no upgrade e dropados no downgrade — Postgres
não dropa o tipo automaticamente quando a tabela referenciadora é dropada.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models.types import PortableJSON

revision = "a8e1d4c7f3b6"
down_revision = "c4e6f8a0d2b3"
branch_labels = None
depends_on = None


_ISSUE_TYPE_VALUES = (
    "area_divergente",
    "sobreposicao_app",
    "sobreposicao_reserva",
    "poligono_fora_matricula",
    "outro",
)
_ISSUE_SEVERITY_VALUES = ("info", "warning", "critical")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ENUMs (Postgres) — criados explicitamente para permitir drop limpo no downgrade
    if is_postgres:
        issue_type_enum = postgresql.ENUM(
            *_ISSUE_TYPE_VALUES, name="regulatory_issue_type", create_type=False,
        )
        issue_severity_enum = postgresql.ENUM(
            *_ISSUE_SEVERITY_VALUES, name="regulatory_issue_severity", create_type=False,
        )
        issue_type_enum.create(bind, checkfirst=True)
        issue_severity_enum.create(bind, checkfirst=True)
        issue_type_col = issue_type_enum
        issue_severity_col = issue_severity_enum
    else:
        issue_type_col = sa.Enum(*_ISSUE_TYPE_VALUES, name="regulatory_issue_type")
        issue_severity_col = sa.Enum(*_ISSUE_SEVERITY_VALUES, name="regulatory_issue_severity")

    # regulatory_diagnoses
    op.create_table(
        "regulatory_diagnoses",
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
        sa.Column("content", PortableJSON, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "validated_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "process_id", "version",
            name="uq_regulatory_diagnoses_process_version",
        ),
    )
    op.create_index(
        "ix_regulatory_diagnoses_tenant_id",
        "regulatory_diagnoses", ["tenant_id"],
    )
    op.create_index(
        "ix_regulatory_diagnoses_process_id",
        "regulatory_diagnoses", ["process_id"],
    )

    # regulatory_issues
    op.create_table(
        "regulatory_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "property_id", sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id", sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", issue_type_col, nullable=False),
        sa.Column("severity", issue_severity_col, nullable=False, server_default="warning"),
        sa.Column("payload", PortableJSON, nullable=True),
        sa.Column("detected_by", sa.String(), nullable=True),
        sa.Column(
            "detected_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_regulatory_issues_tenant_id",
        "regulatory_issues", ["tenant_id"],
    )
    op.create_index(
        "ix_regulatory_issues_property_id",
        "regulatory_issues", ["property_id"],
    )
    op.create_index(
        "ix_regulatory_issues_document_id",
        "regulatory_issues", ["document_id"],
    )
    op.create_index(
        "ix_regulatory_issues_type",
        "regulatory_issues", ["type"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_index("ix_regulatory_issues_type", table_name="regulatory_issues")
    op.drop_index("ix_regulatory_issues_document_id", table_name="regulatory_issues")
    op.drop_index("ix_regulatory_issues_property_id", table_name="regulatory_issues")
    op.drop_index("ix_regulatory_issues_tenant_id", table_name="regulatory_issues")
    op.drop_table("regulatory_issues")

    op.drop_index("ix_regulatory_diagnoses_process_id", table_name="regulatory_diagnoses")
    op.drop_index("ix_regulatory_diagnoses_tenant_id", table_name="regulatory_diagnoses")
    op.drop_table("regulatory_diagnoses")

    if is_postgres:
        postgresql.ENUM(name="regulatory_issue_severity").drop(bind, checkfirst=True)
        postgresql.ENUM(name="regulatory_issue_type").drop(bind, checkfirst=True)
