"""Estrutura da norma como dado no knowledge_catalog (#119, ADR-041).

O texto legislativo entrega de graca tres coisas que o corpus jogava fora:

  (a) HIERARQUIA — o chunker usa o padrao mais granular que quebra e descarta
      titulo/capitulo/secao. Medido: so 12 chunks de 3.192 federais tinham
      rotulo hierarquico.
  (b) IDENTIDADE DO DISPOSITIVO — 93,1% dos chunks federais mencionam um
      artigo, e o numero nao estava em campo consultavel. Estava dentro de
      `section`, como texto.
  (c) REFERENCIAS CRUZADAS — 329 chunks federais com "na forma do art.",
      "nos termos do art.", "previsto/disposto no art.": arestas de grafo
      viradas texto corrido.

EXTRACAO SIM, NAVEGACAO NAO: as referencias sao gravadas como dado. Resolver,
seguir ou expandir e decisao futura, nao subproduto desta migration.

`dispositivo_origem` existe porque campo preenchido por heranca precisa ser
DISTINGUIVEL de campo lido do texto. Rotulo inferido apresentado como lido e a
familia da #121 (atribuicao errada) e da #123 (registrar o pedido como se fosse
o realizado).

Colunas nascem NULL: nao ha reindexacao nesta migration. Elas se preenchem na
proxima passada de indice — uma so, no fim da remediacao, junto com a
normalizacao Unicode da #122.

Revision ID: b7e3f1a90c24
Revises: a2f6c8d40b17
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e3f1a90c24"
down_revision: str | Sequence[str] | None = "a2f6c8d40b17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_catalog",
        sa.Column("dispositivo", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "knowledge_catalog",
        sa.Column("dispositivo_origem", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "knowledge_catalog",
        sa.Column("hierarquia", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_catalog",
        sa.Column("referencias", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # O ponto da #119 e o dispositivo virar CONSULTAVEL. Sem indice, "me traga o
    # art. 61-A" continua sendo varredura de tabela.
    op.create_index(
        "ix_knowledge_catalog_dispositivo",
        "knowledge_catalog",
        ["dispositivo"],
        unique=False,
    )
    # Consulta tipica cruza identidade da norma com dispositivo:
    # "art. 18 do Decreto 6.514/2008".
    op.create_index(
        "ix_knowledge_catalog_identifier_dispositivo",
        "knowledge_catalog",
        ["identifier", "dispositivo"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_catalog_identifier_dispositivo", table_name="knowledge_catalog")
    op.drop_index("ix_knowledge_catalog_dispositivo", table_name="knowledge_catalog")
    op.drop_column("knowledge_catalog", "referencias")
    op.drop_column("knowledge_catalog", "hierarquia")
    op.drop_column("knowledge_catalog", "dispositivo_origem")
    op.drop_column("knowledge_catalog", "dispositivo")
