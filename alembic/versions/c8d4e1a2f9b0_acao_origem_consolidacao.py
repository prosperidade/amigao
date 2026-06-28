"""Adiciona o valor `consolidacao` ao enum `acao_origem`.

Ações nascidas de uma divergência de transcrição NÃO resolvida na consolidação
(decisão Isis, opção b — consolidação parcial). Proveniência limpa: não reusa
`auditor`. Em Postgres é `ALTER TYPE ... ADD VALUE` (fora de transação); em
SQLite (testes) o enum vira VARCHAR e nada precisa mudar no schema.

Revision ID: c8d4e1a2f9b0
Revises: ac7f01b9e3d5
Create Date: 2026-06-28

"""
from __future__ import annotations

from alembic import op

revision = "c8d4e1a2f9b0"
down_revision = "ac7f01b9e3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite: enum é VARCHAR, sem tipo a alterar.
    # ADD VALUE não roda dentro do bloco transacional do Alembic.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE acao_origem ADD VALUE IF NOT EXISTS 'consolidacao'")


def downgrade() -> None:
    # Postgres não remove valor de enum trivialmente (exigiria recriar o tipo e
    # reescrever a coluna). Valor órfão é inofensivo — downgrade é no-op.
    pass
