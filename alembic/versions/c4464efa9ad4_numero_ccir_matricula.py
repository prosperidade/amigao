"""numero_ccir na matrícula — o número que localiza o CCIR

Item 7 (pós-teste Isis, 21/07). A consultora LOCALIZA o documento CCIR pelo seu
número (ex.: 65077819246). Antes não tinha coluna: caía no `imovel.ccir`
depreciado (ambíguo entre 3 números, N1 item 5) ou se perdia. Agora tem casa
própria, per-lote (uma fazenda tem um CCIR por lote), distinta do
`codigo_incra_sncr` (Código do Imóvel no SNCR).

Aditiva e nullable: matrículas antigas ficam sem — ausência é informação, não
erro (só reextração do CCIR preenche daqui pra frente).

Revision ID: c4464efa9ad4
Revises: d4f7a2c9e1b8
Create Date: 2026-07-22
"""

from alembic import op
import sqlalchemy as sa

revision = "c4464efa9ad4"
down_revision = "d4f7a2c9e1b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matriculas", sa.Column("numero_ccir", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("matriculas", "numero_ccir")
