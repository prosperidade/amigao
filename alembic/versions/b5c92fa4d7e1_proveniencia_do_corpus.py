"""proveniência do corpus — de onde veio o texto de cada norma (dívida #97)

O sistema cita norma em peça que a consultora assina. "De onde veio esse texto"
precisa ter resposta, e até aqui não tinha: havia `url` (nula em 54 dos 64
documentos) e `file_path` (um caminho de disco), e nenhum campo dizia se a fonte
é oficial. A auditoria de 31/07 mediu que **97,3% do texto do corpus** não tinha
origem rastreável declarada.

Três colunas:

- `fonte_origem`      — de onde veio, em texto legível para o consultor
- `fonte_oficial`     — NOT NULL DEFAULT false. O default é o conservador: o que
                        não foi conferido não se apresenta como oficial.
- `fonte_conferida_em`— quando alguém confirmou. NULL = ninguém confirmou ainda.

O backfill é conservador e NÃO inventa origem:

1. Documento com URL de domínio oficial (planalto, in.gov.br, gov.br) →
   `fonte_oficial = true`, origem nomeando o domínio.
2. Documento vindo de disco (as pastas GO/MT/MS/AC) → **oficial = true**, por
   confirmação do André em 01/08/2026: todas as pastas vieram da Isis, de fontes
   oficiais estaduais. `fonte_conferida_em` recebe a data dessa confirmação —
   é ela que distingue "conferido por uma pessoa" de "deduzido pela URL".
3. Qualquer outra URL (agregador) → `fonte_oficial = false`. Hoje é só o
   LegisWeb da IN IBAMA 10/2012, que aguarda o PDF oficial (dívida #98).
4. O pacote A já gravou proveniência em `extra_metadata` — quando houver, ela
   vence, porque foi declarada na curadoria e não deduzida aqui.

Revision ID: b5c92fa4d7e1
Revises: a3e71c0d5f28
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "b5c92fa4d7e1"
down_revision = "a3e71c0d5f28"
branch_labels = None
depends_on = None


# Data em que o André confirmou a origem das pastas estaduais.
CONFERIDA_EM = "2026-08-01"

CURADORIA_ISIS = (
    "curadoria Isis Terra — fontes oficiais estaduais (SEMAD/Casa Civil/DOE)"
)


def upgrade() -> None:
    op.add_column(
        "legislation_documents",
        sa.Column("fonte_origem", sa.Text(), nullable=True),
    )
    op.add_column(
        "legislation_documents",
        sa.Column(
            "fonte_oficial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "legislation_documents",
        sa.Column("fonte_conferida_em", sa.Date(), nullable=True),
    )

    # 4. A curadoria explícita vence a dedução (pacote A, PR #127).
    #
    # `jsonb_exists(...)` e não o operador `?`: a coluna é `json` (não `jsonb`,
    # via PortableJSON) e o `?` nem existe nesse tipo — além de ser lido como
    # placeholder de parâmetro pelo driver, que é uma segunda armadilha.
    op.execute(
        """
        UPDATE legislation_documents
           SET fonte_origem = extra_metadata->>'fonte_origem',
               fonte_oficial = coalesce(
                   (extra_metadata->>'fonte_oficial')::boolean, false)
         WHERE extra_metadata IS NOT NULL
           AND jsonb_exists(extra_metadata::jsonb, 'fonte_origem')
        """
    )

    # 1. URL de domínio oficial.
    op.execute(
        """
        UPDATE legislation_documents
           SET fonte_origem = CASE
                 WHEN url ILIKE '%planalto.gov.br%'
                   THEN 'Planalto — Presidência da República (oficial)'
                 WHEN url ILIKE '%in.gov.br%'
                   THEN 'DOU — Imprensa Nacional (oficial)'
                 WHEN url ILIKE '%conama.mma.gov.br%' THEN 'CONAMA/MMA (oficial)'
                 ELSE 'portal .gov.br (oficial)'
               END,
               fonte_oficial = true
         WHERE fonte_origem IS NULL
           AND url ILIKE '%.gov.br%'
        """
    )

    # 3. Outra URL = agregador; não é oficial enquanto ninguém conferir.
    op.execute(
        """
        UPDATE legislation_documents
           SET fonte_origem = 'fonte não-oficial (agregador) — ' || url,
               fonte_oficial = false
         WHERE fonte_origem IS NULL AND url IS NOT NULL
        """
    )

    # 2. Disco: as pastas da Isis. Oficial POR CONFIRMAÇÃO HUMANA, com data.
    op.execute(
        f"""
        UPDATE legislation_documents
           SET fonte_origem = '{CURADORIA_ISIS}'
                              || ' [arquivo: ' || coalesce(file_path, '?') || ']',
               fonte_oficial = true,
               fonte_conferida_em = DATE '{CONFERIDA_EM}'
         WHERE fonte_origem IS NULL AND file_path IS NOT NULL
        """
    )

    # Sobra: sem url e sem file_path. Não se inventa origem — fica declarado.
    op.execute(
        """
        UPDATE legislation_documents
           SET fonte_origem = 'origem não identificada — conferir antes de citar',
               fonte_oficial = false
         WHERE fonte_origem IS NULL
        """
    )

    op.create_index(
        "ix_legislation_documents_fonte_oficial",
        "legislation_documents",
        ["fonte_oficial"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legislation_documents_fonte_oficial",
        table_name="legislation_documents",
    )
    op.drop_column("legislation_documents", "fonte_conferida_em")
    op.drop_column("legislation_documents", "fonte_oficial")
    op.drop_column("legislation_documents", "fonte_origem")
