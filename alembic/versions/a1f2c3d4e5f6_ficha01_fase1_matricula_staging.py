"""ficha01 fase1: matriculas + extracted_field_staging + enum extractedfieldstatus

Ficha 01 (Dicionário de Extração do Intake) — FASE 1: só schema. Cria a entidade
Matrícula (1 Imóvel : N Matrículas) e a tabela de staging de campos extraídos
(agentes propõem, consultor decide). Comportamento de extrator/auditor inalterado.

Revision ID: a1f2c3d4e5f6
Revises: pr21_wa_provider
Create Date: 2026-06-04

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1f2c3d4e5f6"
down_revision = "pr21_wa_provider"
branch_labels = None
depends_on = None


_STATUS_VALUES = (
    "pendente",
    "consistente",
    "divergente_transcricao",
    "divergente_fundo",
    "aceito",
    "rejeitado",
)


def _json_type(is_postgres: bool):
    return postgresql.JSONB() if is_postgres else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = _json_type(is_postgres)

    # Enum NOVO `extractedfieldstatus`. Criado explicitamente (checkfirst) para
    # sobreviver a upgrade→downgrade→upgrade do zero; a coluna referencia com
    # create_type=False para não tentar recriar dentro do create_table.
    if is_postgres:
        status_enum = postgresql.ENUM(*_STATUS_VALUES, name="extractedfieldstatus")
        status_enum.create(bind, checkfirst=True)
        status_col = postgresql.ENUM(
            *_STATUS_VALUES, name="extractedfieldstatus", create_type=False
        )
    else:
        status_col = sa.Enum(*_STATUS_VALUES, name="extractedfieldstatus")

    # 1) matriculas -------------------------------------------------------
    op.create_table(
        "matriculas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "property_id", sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("numero_matricula", sa.String(), nullable=True),
        sa.Column("cartorio", sa.String(), nullable=True),
        sa.Column("registro_livro_folha_ficha", sa.String(), nullable=True),
        sa.Column("codigo_incra_sncr", sa.String(), nullable=True),
        sa.Column("nirf_cib", sa.String(), nullable=True),
        sa.Column("area_ha", sa.Float(), nullable=True),
        sa.Column("denominacao_imovel", sa.String(), nullable=True),
        sa.Column("geo_certificacao_codigo", sa.String(), nullable=True),
        sa.Column("geo_certificacao_status", sa.String(), nullable=True),
        sa.Column("averbacao_app", sa.Text(), nullable=True),
        sa.Column("averbacao_rl", sa.Text(), nullable=True),
        sa.Column("onus_gravames", sa.Text(), nullable=True),
        sa.Column("proprietarios", json_type, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_matriculas_id", "matriculas", ["id"])
    op.create_index("ix_matriculas_tenant_id", "matriculas", ["tenant_id"])
    op.create_index("ix_matriculas_property_id", "matriculas", ["property_id"])
    op.create_index("ix_matriculas_numero_matricula", "matriculas", ["numero_matricula"])
    op.create_index(
        "ix_matriculas_tenant_property", "matriculas", ["tenant_id", "property_id"]
    )

    # 2) extracted_field_staging -----------------------------------------
    op.create_table(
        "extracted_field_staging",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "process_id", sa.Integer(),
            sa.ForeignKey("processes.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column(
            "document_id", sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("source_doc_type", sa.String(length=50), nullable=True),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("field_value", json_type, nullable=True),
        sa.Column("confidence", sa.String(length=10), nullable=True),
        sa.Column("target_entity", sa.String(length=20), nullable=True),
        sa.Column("target_field", sa.String(), nullable=True),
        sa.Column("matricula_hint", sa.String(), nullable=True),
        sa.Column("status", status_col, nullable=False),
        sa.Column("decided_value", json_type, nullable=True),
        sa.Column(
            "decided_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_agent", sa.String(length=50), nullable=True),
        sa.Column(
            "ai_job_id", sa.Integer(),
            sa.ForeignKey("ai_jobs.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_extracted_field_staging_id", "extracted_field_staging", ["id"])
    op.create_index(
        "ix_extracted_field_staging_tenant_id", "extracted_field_staging", ["tenant_id"]
    )
    op.create_index(
        "ix_extracted_field_staging_process_id", "extracted_field_staging", ["process_id"]
    )
    op.create_index(
        "ix_extracted_field_staging_document_id", "extracted_field_staging", ["document_id"]
    )
    op.create_index(
        "ix_extracted_field_staging_status", "extracted_field_staging", ["status"]
    )
    op.create_index(
        "ix_staging_tenant_process_status",
        "extracted_field_staging",
        ["tenant_id", "process_id", "status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # DROP TABLE remove os índices junto; depois removemos o enum do catálogo.
    op.drop_table("extracted_field_staging")
    op.drop_table("matriculas")

    if is_postgres:
        postgresql.ENUM(name="extractedfieldstatus").drop(bind, checkfirst=True)
