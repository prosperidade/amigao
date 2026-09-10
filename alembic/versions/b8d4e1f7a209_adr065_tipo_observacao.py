"""ADR-065 — observação registral tipada: `tipo_observacao` e `atributos`.

Duas colunas aditivas em ``extracted_field_staging``:

  1. ``tipo_observacao`` (String(40), indexada) — O QUE o valor é. Até aqui o
     staging só sabia dizer ONDE o valor pousa (`target_entity`/`target_field`):
     um arrendamento de 50 ha para terceiro (doc 548, AV.10) e uma averbação de
     APP eram indistinguíveis depois de gravados, porque os dois viravam a
     mesma linha `averbacao_app`.
  2. ``atributos`` (JSONB) — o que o TIPO pede: ato ("AV.02"), data, área,
     valor, partes, prazo, ato referenciado, descrição, mais `baixado_por`
     quando outra averbação declara a baixa deste ato.

String e não Enum de propósito: o vocabulário é fechado no código
(`app/services/observacao_registral.py`), e tipo novo não deve custar migration
— a mesma decisão de `source_doc_type`.

Nada é reescrito para trás: linhas antigas ficam com as duas colunas NULL, o que
é a resposta correta para elas (não nasceram de ato tipado). Reversível.

Revision ID: b8d4e1f7a209
Revises: 99fb989b546c
"""

import sqlalchemy as sa
from alembic import op

from app.models.types import PortableJSON

revision = "b8d4e1f7a209"
down_revision = "99fb989b546c"
branch_labels = None
depends_on = None

TABELA = "extracted_field_staging"
IX_TIPO = "ix_extracted_field_staging_tipo_observacao"


def upgrade() -> None:
    op.add_column(TABELA, sa.Column("tipo_observacao", sa.String(length=40), nullable=True))
    op.add_column(TABELA, sa.Column("atributos", PortableJSON(), nullable=True))
    op.create_index(IX_TIPO, TABELA, ["tipo_observacao"])


def downgrade() -> None:
    op.drop_index(IX_TIPO, table_name=TABELA)
    op.drop_column(TABELA, "atributos")
    op.drop_column(TABELA, "tipo_observacao")
