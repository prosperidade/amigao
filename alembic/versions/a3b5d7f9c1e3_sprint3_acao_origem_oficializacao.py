"""Adiciona o valor `oficializacao` ao enum `acao_origem`.

Ações nascidas do selo "Correto, pendente de oficialização" (Ficha 07 §3.4/§9):
ao receber o selo, o sistema cria sozinho a ação "Atualização de arquivos
oficiais — {campo}" (proposta; o consultor edita/remove). Proveniência limpa:
não reusa `consolidacao`. Mesmo padrão da migration c8d4e1a2f9b0.

Revision ID: a3b5d7f9c1e3
Revises: f2a4c6e8b0d2
Create Date: 2026-07-03

"""
from __future__ import annotations

from alembic import op

revision = "a3b5d7f9c1e3"
down_revision = "f2a4c6e8b0d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite: enum é VARCHAR, sem tipo a alterar.
    # ADD VALUE não roda dentro do bloco transacional do Alembic.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE acao_origem ADD VALUE IF NOT EXISTS 'oficializacao'")


def downgrade() -> None:
    # Postgres não remove valor de enum trivialmente (exigiria recriar o tipo e
    # reescrever a coluna). Valor órfão é inofensivo — downgrade é no-op.
    pass
