"""Ficha 07 — entidade `acoes` (Aba Ações + Quadro de Ações global).

Cria a tabela ``acoes``: ações de remediação triáveis nascidas do diagnóstico
(com fonte — contrato #70) ou criadas manualmente. Triagem do consultor
(tarefa/escopo/dispensada/pendente), status de kanban (a_fazer/em_andamento/
concluida/bloqueada), vínculo de rastreabilidade ao passivo de origem (sem FK —
concluir a ação NUNCA altera o passivo; ver ADR-016).

``responsavel_id`` é nullable (MVP sem Bloco 0). ``dedupe_key`` garante
idempotência da geração (NULL para criação manual).

Revision ID: ac7f01b9e3d5
Revises: b2c3d4e5f6a7
Create Date: 2026-06-18

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.models.types import PortableJSON

revision = "ac7f01b9e3d5"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


_PRIORIDADE = ("alta", "media", "baixa")
_STATUS = ("a_fazer", "em_andamento", "concluida", "bloqueada")
_TRIAGEM = ("pendente", "tarefa", "escopo", "dispensada")
_ORIGEM = ("diagnostico", "auditor", "manual")


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "acoes" in existing:
        return

    op.create_table(
        "acoes",
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
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("origem", sa.Enum(*_ORIGEM, name="acao_origem"), nullable=False),
        sa.Column("origem_descricao", sa.String(), nullable=True),
        sa.Column("origem_fontes", PortableJSON(), nullable=False, server_default="[]"),
        sa.Column("vinculo_passivo", PortableJSON(), nullable=True),
        sa.Column(
            "responsavel_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prazo", sa.Date(), nullable=True),
        sa.Column("prioridade", sa.Enum(*_PRIORIDADE, name="acao_prioridade"), nullable=False),
        sa.Column("status", sa.Enum(*_STATUS, name="acao_status"), nullable=False),
        sa.Column("tipo_triagem", sa.Enum(*_TRIAGEM, name="acao_tipo_triagem"), nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column(
            "created_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("concluida_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_acoes_tenant_dedupe"),
    )
    op.create_index("ix_acoes_tenant_id", "acoes", ["tenant_id"])
    op.create_index("ix_acoes_process_id", "acoes", ["process_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "acoes" not in existing:
        return

    op.drop_index("ix_acoes_process_id", table_name="acoes")
    op.drop_index("ix_acoes_tenant_id", table_name="acoes")
    op.drop_table("acoes")

    # Enums só existem no PostgreSQL — derruba pra downgrade limpo.
    if bind.dialect.name == "postgresql":
        for enum_name in ("acao_origem", "acao_prioridade", "acao_status", "acao_tipo_triagem"):
            op.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name}"))
