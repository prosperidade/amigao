"""Módulos fiscais ganha destino no imóvel (dívida #200).

O RAT declara o número de módulos fiscais, a extração o produzia desde sempre
(`ficha01_extraction._FieldSpec("modulos_fiscais", ... "imovel", "modulos_fiscais")`)
e a consolidação o descartava a cada rodada — não havia coluna. Na leitura de
produção de 03/08 (processo 16) ele aparecia em `ignorados` como o identificador
nu `imovel.modulos_fiscais`, sem que nada na tela dissesse que a informação
estava sendo jogada fora.

Por que DESTINO e não recusa declarada: módulos fiscais é atributo do IMÓVEL
(área ÷ módulo fiscal do município), não do documento que o declara — diferente
de `rat_protocolo`/`rat_data_emissao`, que identificam o relatório. E tem
consumidor real: porte decide as exceções do Código Florestal que a skill de
diagnóstico aplica ("Exceção por porte — pequeno produtor, agricultura familiar,
Módulo Fiscal") e a H19 do auditor ("exige saber bioma e módulos fiscais").

`Float` e não `Integer`: o quociente é fracionário (uma fazenda de 148 ha num
município de 40 ha/MF tem 3,7 módulos, e o limiar de 4 MF do Código Florestal
depende justamente da fração).

Sem backfill. O número está nos RATs já anexados, mas recalculá-lo aqui seria
inventar: a extração é quem lê o documento, e ela roda de novo quando a
consultora reconsolidar. Ficam NULL, honestamente.

Revision ID: b4e1d70c9a35
Revises: b7e3f1a90c24

REPARENTADA em 06/08: nasceu revisando `a2f6c8d40b17`, mas a frente do corpus
mergeou primeiro (PR #138, `dd65344`) e trouxe `b7e3f1a90c24` para a main a
partir do MESMO pai. Duas revisoes com o mesmo `down_revision` sao dois heads, e
dois heads quebram o `alembic upgrade head`. Regra da casa: o segundo a mergear
se ajusta.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4e1d70c9a35"
down_revision = "b7e3f1a90c24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("modulos_fiscais", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "modulos_fiscais")
