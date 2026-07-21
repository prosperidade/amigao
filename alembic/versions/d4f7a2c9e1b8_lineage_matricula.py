"""lineage da matricula — de qual staging/decisao ela nasceu

Item 5 da Fase 2 (caso 15). `field_sources` diz o TIPO da fonte
(raw/ai_extracted/human_validated); `lineage` diz QUAL linha de staging e QUAL
decisão materializaram o registro.

Sem ela, "de onde veio esse 2923?" só se responde cruzando timestamps na mão —
foi exatamente o que a investigação do caso 15 teve de fazer para descobrir que
a matrícula nasceu do CCIR aceito (hint 2923) e não da certidão (4698).

Aditiva e nullable: registros antigos ficam sem lineage (não há como inventar
retroativamente), e isso é honesto — ausência de certidão de nascimento é
informação, não erro.

Revision ID: d4f7a2c9e1b8
Revises: c3e9b1d7f4a2
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa

from app.models.types import PortableJSON

revision = "d4f7a2c9e1b8"
down_revision = "c3e9b1d7f4a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matriculas", sa.Column("lineage", PortableJSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("matriculas", "lineage")
