"""Proveniência do passo da rota — de qual achado e/ou ação ele nasceu (ADR-039).

Fecha a corrente inteira, com FK em cada elo:

    RegulatoryIssue → Acao → RotaPasso → ProposalScopeItem

O último elo já existia (``ProposalScopeItem.rota_passo_id``, S5-A); os dois
primeiros faltavam. Sem eles a rota era uma segunda opinião independente do
diagnóstico — não dava para responder "de onde veio este passo?".

``SET NULL`` pelo mesmo motivo do S5-A: a rota é peça assinada e sobrevive ao
desaparecimento da origem. Perder o ponteiro é aceitável; perder o passo que o
consultor validou, não.

Sem backfill de propósito. Passos gerados antes deste commit nasceram de um
contexto que não continha achados nem ações (a rota lia
``process.initial_diagnosis``, o pré-diagnóstico do intake) — atribuir origem a
eles agora seria inventar proveniência, exatamente o que esta coluna existe para
impedir. Ficam NULL, honestamente.

Revision ID: d1a4b7e93c60
Revises: c7e2f9a4b681
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d1a4b7e93c60"
down_revision = "c7e2f9a4b681"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rota_passos", sa.Column("origem_issue_id", sa.Integer(), nullable=True))
    op.add_column("rota_passos", sa.Column("origem_acao_id", sa.Integer(), nullable=True))
    op.create_index("ix_rota_passos_origem_issue_id", "rota_passos", ["origem_issue_id"])
    op.create_index("ix_rota_passos_origem_acao_id", "rota_passos", ["origem_acao_id"])
    op.create_foreign_key(
        "fk_rota_passos_origem_issue", "rota_passos", "regulatory_issues",
        ["origem_issue_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_rota_passos_origem_acao", "rota_passos", "acoes",
        ["origem_acao_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_rota_passos_origem_acao", "rota_passos", type_="foreignkey")
    op.drop_constraint("fk_rota_passos_origem_issue", "rota_passos", type_="foreignkey")
    op.drop_index("ix_rota_passos_origem_acao_id", table_name="rota_passos")
    op.drop_index("ix_rota_passos_origem_issue_id", table_name="rota_passos")
    op.drop_column("rota_passos", "origem_acao_id")
    op.drop_column("rota_passos", "origem_issue_id")
