"""Rota Regulatória (E5, Sprint 2) — entidades `rotas` e `rota_passos`.

Materializa o caminho regulatório da ``LegislacaoAgent`` (hoje efêmero no JSON do
``AIJob``) como snapshot editável: o consultor reordena, classifica (faturável vs
direção) e **assina** (Princípio 1). Uma rota por ``(tenant, process, demand_type)``
— re-rodar a legislação reconcilia por ``dedupe_key`` (dívida #48: constraint desde
o commit 1). Ver ``app/models/rota.py`` e ``app/services/rota_materializer.py``.

Revision ID: d1e2f3a4b5c6
Revises: c8d4e1a2f9b0
Create Date: 2026-06-30

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.models.types import PortableJSON

revision = "d1e2f3a4b5c6"
down_revision = "c8d4e1a2f9b0"
branch_labels = None
depends_on = None


_ROTA_STATUS = ("proposta", "em_validacao", "validada", "desatualizada")
_PASSO_CLASSIFICACAO = ("item_proposta", "direcao")
_PASSO_ORIGEM = ("ia", "manual")
_PASSO_STATUS = ("proposto", "validado")


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "rotas" not in existing:
        op.create_table(
            "rotas",
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
            sa.Column("demand_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.Enum(*_ROTA_STATUS, name="rota_status"), nullable=False),
            sa.Column("caminho_regulatorio", sa.Text(), nullable=True),
            sa.Column("orgao_competente", sa.String(), nullable=True),
            sa.Column(
                "source_ai_job_id", sa.Integer(),
                sa.ForeignKey("ai_jobs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "validated_by", sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "process_id", "demand_type",
                name="uq_rotas_tenant_process_demand",
            ),
        )
        op.create_index("ix_rotas_tenant_id", "rotas", ["tenant_id"])
        op.create_index("ix_rotas_process_id", "rotas", ["process_id"])

    if "rota_passos" not in existing:
        op.create_table(
            "rota_passos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id", sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "rota_id", sa.Integer(),
                sa.ForeignKey("rotas.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("ordem", sa.Integer(), nullable=False),
            sa.Column("titulo", sa.String(), nullable=False),
            sa.Column("descricao", sa.Text(), nullable=True),
            sa.Column("orgao", sa.String(), nullable=True),
            sa.Column("prazo_estimado_dias", sa.Integer(), nullable=True),
            sa.Column("prazo_fonte", sa.String(), nullable=True),
            sa.Column("sources", PortableJSON(), nullable=False, server_default="[]"),
            sa.Column("norma_ref", sa.String(), nullable=True),
            sa.Column(
                "classificacao",
                sa.Enum(*_PASSO_CLASSIFICACAO, name="rota_passo_classificacao"),
                nullable=True,
            ),
            sa.Column(
                "origem",
                sa.Enum(*_PASSO_ORIGEM, name="rota_passo_origem"),
                nullable=False,
            ),
            sa.Column("origem_manual_nota", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.Enum(*_PASSO_STATUS, name="rota_passo_status"),
                nullable=False,
            ),
            sa.Column("dedupe_key", sa.String(length=120), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "dedupe_key", name="uq_rota_passos_tenant_dedupe"
            ),
        )
        op.create_index("ix_rota_passos_tenant_id", "rota_passos", ["tenant_id"])
        op.create_index("ix_rota_passos_rota_id", "rota_passos", ["rota_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "rota_passos" in existing:
        op.drop_index("ix_rota_passos_rota_id", table_name="rota_passos")
        op.drop_index("ix_rota_passos_tenant_id", table_name="rota_passos")
        op.drop_table("rota_passos")

    if "rotas" in existing:
        op.drop_index("ix_rotas_process_id", table_name="rotas")
        op.drop_index("ix_rotas_tenant_id", table_name="rotas")
        op.drop_table("rotas")

    # Enums só existem no PostgreSQL — derruba pra downgrade limpo.
    if bind.dialect.name == "postgresql":
        for enum_name in (
            "rota_passo_status",
            "rota_passo_origem",
            "rota_passo_classificacao",
            "rota_status",
        ):
            op.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name}"))
