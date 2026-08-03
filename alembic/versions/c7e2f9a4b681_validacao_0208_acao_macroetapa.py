"""Validação 02/08 (item 8) — a Ação carimba a etapa em que nasceu.

As Fichas descrevem as ações de cada etapa ficando registradas e visíveis
conforme o caso avança. A aba Ações era uma lista plana: dava para filtrar por
status e triagem, mas não para ler o caso como uma sequência de trabalho — o que
foi feito na Entrada, no Diagnóstico Preliminar, na Coleta.

Faltava o dado, não a tela: ``Acao`` não guardava a macroetapa.

NULL de propósito nas linhas existentes: a etapa em que uma ação antiga nasceu
não é recuperável (o processo só guarda a etapa ATUAL, e usá-la carimbaria toda
ação antiga com a etapa de hoje). Preencher seria inventar histórico. A tela
agrupa essas sob "etapa não registrada" e diz o que são.

Revision ID: c7e2f9a4b681
Revises: b4c8d1e6a293
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c7e2f9a4b681"
down_revision = "b4c8d1e6a293"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("acoes", sa.Column("macroetapa", sa.String(), nullable=True))
    op.create_index("ix_acoes_macroetapa", "acoes", ["macroetapa"])


def downgrade() -> None:
    op.drop_index("ix_acoes_macroetapa", table_name="acoes")
    op.drop_column("acoes", "macroetapa")
