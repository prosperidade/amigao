"""S5-B — perfil emissor do tenant + parcelas estruturadas da proposta

Suporte à geração de proposta/contrato nos moldes Mirante (S5-B):

- ``tenants.settings`` (PortableJSON, default ``{}``): guarda o **perfil emissor**
  do tenant (razão social, CNPJ, endereço, responsável técnico nome/título/CREA,
  dados bancários, foro e condições comerciais padrão). Sem esses dados a geração
  do documento é BLOQUEADA com mensagem honesta (placeholder não resolvido =
  bloqueio). Ver ADR-029.

- ``proposals.payment_installments`` (PortableJSON, default ``[]``): parcelas
  ESTRUTURADAS ``[{numero, vencimento, valor}]``. Necessárias para a validação de
  consistência do contrato "soma das parcelas == total do bloco" (a classe de
  erro real dos contratos manuais da Mirante). Vazio = uma parcela única à vista
  sintetizada no build (soma trivialmente confere).

Revision ID: f1a7c2d9e4b6
Revises: d4b8e2f1a6c9
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

from app.models.types import PortableJSON

revision = "f1a7c2d9e4b6"
down_revision = "d4b8e2f1a6c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("settings", PortableJSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "proposals",
        sa.Column(
            "payment_installments", PortableJSON(), nullable=False, server_default="[]"
        ),
    )


def downgrade() -> None:
    op.drop_column("proposals", "payment_installments")
    op.drop_column("tenants", "settings")
