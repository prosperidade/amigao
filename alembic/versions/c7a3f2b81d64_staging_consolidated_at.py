"""Conferência: "Aceito" deixa de ser igual a "Gravado" — `consolidated_at`.

Origem: validações da Isis de 30/07 e 02/08, auditadas em 06/08 contra o
processo 16 em produção.

O QUE ESTAVA ERRADO
───────────────────
A consolidação do caso 16 gravou **16 campos** em 4 matrículas numa sessão
(cartório, denominação, área, averbações de APP e RL, proprietários, registro
anterior, NIRF, CCIR, INCRA, ônus, livro/folha — audit_logs 1604/1648/1664).
A consultora relatou "gravou apenas NIRF, CCIR, INCRA".

Ela não estava enganada: a Conferência não tinha como dizer o contrário. Uma
linha que pousou na base e uma linha recusada mostravam a mesma palavra —
"Aceito" — e o único sinal de gravação era um toast que morre ao navegar. Num
produto cujo primeiro princípio é "a IA propõe; o humano decide e assina", o
que o humano não vê ele não pode decidir.

POR QUE COLUNA PRÓPRIA E NÃO DERIVAR DE `field_sources`
───────────────────────────────────────────────────────
`field_sources` é por (entidade, COLUNA) e responde "esta coluna já foi
validada por humano?". A pergunta da tela é outra: "ESTA LINHA pousou?".

As duas divergem no caminho da RECONCILIAÇÃO (`_write_entity`): valor novo que
diverge de campo já `human_validated` **não** sobrescreve — por projeto (Ficha
05). Nesse caminho `field_sources` diz "human_validated" e a linha não gravou
nada. Derivar dali carimbaria "Gravado" exatamente sobre o aceite que a base
recusou — o pior erro possível numa tela de conferência.

Não é hipótese: no caso 16, o `audit_log` 1675 registra reconciliações de
`numero_matricula` ("6776" × "6.776") e `codigo_incra_sncr`. Havia ainda dois
caminhos menores com o mesmo defeito (valor incoercível e forma de container
inválida sobre coluna já consolidada).

Some-se o custo: resolver o destino de uma linha de matrícula exige repetir a
cascata de âncora do ITR e o guard fantasma a cada GET da Conferência.

CONTRATO DA COLUNA
──────────────────
* preenchida pela consolidação quando o valor da linha ESTÁ na base (gravou
  agora ou já estava lá e foi reafirmado);
* limpa por qualquer nova decisão do consultor — decidir de novo devolve a
  linha à condição de proposta;
* NULL em tudo que existe hoje. Sem backfill de propósito: carimbar retroativo
  seria afirmar sem medir, e a próxima consolidação (idempotente) preenche
  sozinha o que de fato está na base.

Revision ID: c7a3f2b81d64
Revises: b4e1d70c9a35
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c7a3f2b81d64"
down_revision = "b4e1d70c9a35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extracted_field_staging",
        sa.Column("consolidated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extracted_field_staging", "consolidated_at")
