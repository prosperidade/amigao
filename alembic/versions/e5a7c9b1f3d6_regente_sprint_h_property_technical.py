"""Regente Sprint H — campos técnicos do Imóvel Hub (CAM2IH-003)

Revision ID: e5a7c9b1f3d6
Revises: d8b3f7c2e5a9
Create Date: 2026-04-20 15:00:00.000000

Adiciona 7 campos técnicos ao modelo Property para viabilizar o Dashboard
técnico do Imóvel Hub (CAM2IH-003) e a Aba Informações expandida
(CAM2IH-004):

  - rl_status            (averbada / proposta / pendente / cancelada)
  - app_area_ha          (área de APP em hectares)
  - regulatory_issues    (JSONB — lista de pendências ambientais)
  - area_documental_ha   (área conforme documentação)
  - area_grafica_ha      (área conforme shape/CAR)
  - tipologia            (agricultura / pecuaria / misto / outro)
  - strategic_notes      (observações estratégicas livres)

Aditiva, nullable, sem backfill necessário. Campos menos críticos
(SNCR/CIB/access_description/operation_start_date) ficam fora do MVP.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.types import PortableJSON

revision: str = "e5a7c9b1f3d6"
down_revision: Union[str, Sequence[str], None] = "d8b3f7c2e5a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("rl_status", sa.String(), nullable=True))
    op.add_column("properties", sa.Column("app_area_ha", sa.Float(), nullable=True))
    op.add_column("properties", sa.Column("regulatory_issues", PortableJSON(), nullable=True))
    op.add_column("properties", sa.Column("area_documental_ha", sa.Float(), nullable=True))
    op.add_column("properties", sa.Column("area_grafica_ha", sa.Float(), nullable=True))
    op.add_column("properties", sa.Column("tipologia", sa.String(), nullable=True))
    op.add_column("properties", sa.Column("strategic_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "strategic_notes")
    op.drop_column("properties", "tipologia")
    op.drop_column("properties", "area_grafica_ha")
    op.drop_column("properties", "area_documental_ha")
    op.drop_column("properties", "regulatory_issues")
    op.drop_column("properties", "app_area_ha")
    op.drop_column("properties", "rl_status")
