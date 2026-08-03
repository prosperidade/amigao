"""Visibilidade do documento — "material interno" do escritório (ADR-060).

Nasceu com a transcrição de áudio de reunião (dívida #103): a gravação registra o
que o cliente contou numa conversa, e nem toda conversa deve voltar para ele pelo
portal. A coluna dá ao consultor o interruptor, sem inventar uma segunda entidade
"documento interno" paralela ao ``Document``.

``server_default="false"`` e ``nullable=False``: todo documento que já existe é,
por definição, material do caso — nenhum deles foi marcado como interno por
ninguém, e ficar NULL abriria um terceiro estado ("não se sabe") que não tem
significado aqui. Default conservador, alinhado à decisão 3b: o áudio entra como
documento normal, com origem marcada no próprio texto da transcrição; esconder é
ato explícito do consultor.

Revision ID: a2f6c8d40b17
Revises: d1a4b7e93c60
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a2f6c8d40b17"
down_revision = "d1a4b7e93c60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "is_internal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "is_internal")
