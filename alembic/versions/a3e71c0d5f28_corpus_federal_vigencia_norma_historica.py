"""corpus federal — vigência da norma e norma histórica recuperável (ADR-037)

O caso 15 é um auto de infração de 2007 cujo enquadramento cita o Decreto
3.179/1999 e a Lei 4.771/1965 — normas REVOGADAS hoje, mas que valiam no fato.
A defesa precisa citá-las (tempus regit actum) e o sistema jamais pode
apresentá-las como vigentes.

`legislation_documents` só tinha `effective_date` (início) e `revoked_at`
(carimbo de quando NÓS marcamos o registro como superado — a coluna é usada
pelo próprio ingestor ao substituir uma versão do documento, ver
`scripts/ingest_federais_canonicos.py`). Nenhuma das duas responde "esta norma
valia na data do fato?", e `revoked_at` já tem outro dono semântico — sobrescrevê-la
misturaria "versão do arquivo superada" com "norma revogada pelo legislador".

Três colunas novas, todas nuláveis (aditivo; documento existente segue válido
com tudo NULL e é tratado como vigente):

- `vigencia_inicio`  — quando a norma passou a valer
- `vigencia_fim`     — quando deixou de valer (NULL = vigente)
- `sucessora_id`     — FK para a norma que a substituiu, quando ela está no corpus
- `sucessora_ref`    — nome da sucessora quando ela NÃO está no corpus.
                       A IN IBAMA 10/2012 foi revogada pela IN Conjunta
                       MMA/IBAMA/ICMBio 02/2020, que não é do pacote A: sem este
                       campo, o único jeito de registrar o fato seria apontar a
                       FK para nada e perder a informação.

Revision ID: a3e71c0d5f28
Revises: d7f1a3c9e2b4
Create Date: 2026-07-31

Encadeada APÓS `d7f1a3c9e2b4` (rota_versoes, do PR #126) e não após o pai comum
`c4464efa9ad4`: as duas nasceram do mesmo ancestral em paralelo e deixariam o
Alembic com DUAS heads, o que quebra `alembic upgrade head` no deploy.
"""

from alembic import op
import sqlalchemy as sa


revision = "a3e71c0d5f28"
down_revision = "d7f1a3c9e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "legislation_documents",
        sa.Column("vigencia_inicio", sa.Date(), nullable=True),
    )
    op.add_column(
        "legislation_documents",
        sa.Column("vigencia_fim", sa.Date(), nullable=True),
    )
    op.add_column(
        "legislation_documents",
        sa.Column("sucessora_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "legislation_documents",
        sa.Column("sucessora_ref", sa.String(length=255), nullable=True),
    )
    op.create_foreign_key(
        "fk_legislation_documents_sucessora",
        "legislation_documents",
        "legislation_documents",
        ["sucessora_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # A busca por "norma vigente na data X" filtra por vigencia_fim; sem índice
    # ela varre a tabela inteira a cada consulta do agente.
    op.create_index(
        "ix_legislation_documents_vigencia_fim",
        "legislation_documents",
        ["vigencia_fim"],
    )

    # Backfill conservador: documento já existente que não declara início de
    # vigência herda `effective_date`. NÃO inferimos fim de vigência de nada —
    # marcar norma como revogada sem curadoria humana é exatamente o erro que
    # esta ADR existe para impedir.
    op.execute(
        """
        UPDATE legislation_documents
           SET vigencia_inicio = effective_date::date
         WHERE vigencia_inicio IS NULL
           AND effective_date IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legislation_documents_vigencia_fim",
        table_name="legislation_documents",
    )
    op.drop_constraint(
        "fk_legislation_documents_sucessora",
        "legislation_documents",
        type_="foreignkey",
    )
    op.drop_column("legislation_documents", "sucessora_ref")
    op.drop_column("legislation_documents", "sucessora_id")
    op.drop_column("legislation_documents", "vigencia_fim")
    op.drop_column("legislation_documents", "vigencia_inicio")
