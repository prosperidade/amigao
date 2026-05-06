"""Sprint V (A4) — adiciona valor `intake` ao enum documentsource.

Revision ID: b3d5c7e9f1a2
Revises: f9d2e8c1a4b3
Create Date: 2026-05-06

Permite distinguir documentos anexados durante o Intake dos uploads feitos
no Workspace depois do caso criado. Habilita o ponto crítico #1 da auditoria
(documentos do Intake aparecem com origem clara no caso e nos Hubs) e a
priorização do auditor_imovel sobre fontes de abertura de caso.

Downgrade é no-op: PostgreSQL não suporta DROP VALUE em enum sem recriar o
tipo, e nenhum dado pré-existente depende da remoção.
"""
from alembic import op


revision = "b3d5c7e9f1a2"
down_revision = "f9d2e8c1a4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE precisa rodar fora da transação implícita do
    # Alembic em algumas versões do PG; autocommit_block isola em transação
    # própria com autocommit.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE documentsource ADD VALUE IF NOT EXISTS 'intake'")


def downgrade() -> None:
    # PostgreSQL não permite remover valor de enum sem recriar o tipo.
    # Como nenhum schema/index depende do valor `intake`, o downgrade é no-op.
    pass
