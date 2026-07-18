"""Dívida #60 — vigência e cadeia de fichas de matrícula

Critério de domínio da Isis: "vigente = matrícula da última averbação; a ficha
anterior vira HISTÓRICO — não soma, não gera lacuna, permanece visível como
linhagem". Adiciona à `matriculas`:

- ``vigencia`` ('vigente'|'historica', default 'vigente' — backfill sem custo):
  só a vigente soma a área e gera lacunas. ORTOGONAL a `deactivated_at`
  (rejeição ≠ histórico: histórica é documento válido, só não vigente).
- ``superseded_by_id`` (FK self, SET NULL): a ficha vigente que substituiu esta
  (cadeia navegável 2609→2923→4698). SET NULL preserva a histórica.
- ``registro_anterior`` / ``denominacao_anterior``: sinais registrais da cadeia
  (registro de origem citado na certidão; nome anterior do imóvel). Evidência da
  detecção de cadeia — nunca decidem sozinhos (proposta + confirmação humana).

Revision ID: c7d3e1a9f0b2
Revises: fa9c1d3b5e70
Create Date: 2026-07-18
"""

import sqlalchemy as sa
from alembic import op


revision = "c7d3e1a9f0b2"
down_revision = "fa9c1d3b5e70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matriculas",
        sa.Column("registro_anterior", sa.String(), nullable=True),
    )
    op.add_column(
        "matriculas",
        sa.Column("denominacao_anterior", sa.String(), nullable=True),
    )
    op.add_column(
        "matriculas",
        sa.Column(
            "vigencia", sa.String(), nullable=False, server_default="vigente"
        ),
    )
    op.add_column(
        "matriculas",
        sa.Column("superseded_by_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_matriculas_superseded_by",
        "matriculas",
        "matriculas",
        ["superseded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_matriculas_superseded_by", "matriculas", type_="foreignkey")
    op.drop_column("matriculas", "superseded_by_id")
    op.drop_column("matriculas", "vigencia")
    op.drop_column("matriculas", "denominacao_anterior")
    op.drop_column("matriculas", "registro_anterior")
