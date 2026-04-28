"""Sprint U — knowledge_catalog (RAG semantico via pgvector).

Revision ID: f9d2e8c1a4b3
Revises: a9c3e5f7b1d2
Create Date: 2026-04-27

Changes:
- Habilita extensao `vector` (pgvector) no Postgres.
- Cria tabela `knowledge_catalog`: chunks de fontes diversas (legislacao,
  oficios, manuais, jurisprudencia) com embeddings em vector(768) gerados
  pelo Gemini text-embedding-004.
- Indices: btree para filtragem (tenant/uf/scope/source_type/identifier),
  GIN para metadata jsonb, IVFFlat com 100 lists para busca por similaridade
  cosseno em embedding.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f9d2e8c1a4b3"
down_revision = "a9c3e5f7b1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extensao pgvector — instalada na imagem custom (docker/db/Dockerfile).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Tabela principal.
    op.create_table(
        "knowledge_catalog",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),

        # Origem do chunk.
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),

        # Conteudo.
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_tokens", sa.Integer(), nullable=False, server_default="0"),

        # Metadados juridicos para filtragem.
        sa.Column("jurisdiction", sa.String(length=20), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("agency", sa.String(length=100), nullable=True),
        sa.Column("identifier", sa.String(length=255), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),

        # Embedding.
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),

        # Idempotencia.
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Coluna `embedding` via SQL puro (vector type nao tem reflexao no SQLAlchemy
    #    sem o pacote pgvector instalado no container alembic).
    op.execute("ALTER TABLE knowledge_catalog ADD COLUMN embedding vector(768)")

    # 4. Indices de filtragem.
    op.create_index(
        "ix_knowledge_catalog_source",
        "knowledge_catalog",
        ["source_type", "source_ref"],
    )
    op.create_index("ix_knowledge_catalog_uf", "knowledge_catalog", ["uf"])
    op.create_index(
        "ix_knowledge_catalog_jurisdiction",
        "knowledge_catalog",
        ["jurisdiction"],
    )
    op.create_index(
        "ix_knowledge_catalog_identifier",
        "knowledge_catalog",
        ["identifier"],
    )
    op.create_index(
        "ix_knowledge_catalog_content_hash",
        "knowledge_catalog",
        ["content_hash"],
        unique=True,
    )
    op.execute(
        "CREATE INDEX ix_knowledge_catalog_metadata "
        "ON knowledge_catalog USING GIN (extra_metadata)"
    )

    # 5. Indice IVFFlat para busca por similaridade (cosine).
    #    100 lists e default razoavel para dezenas a centenas de milhares de linhas.
    #    Ajustar quando crescermos para milhoes (lists ~ sqrt(n_rows)).
    op.execute(
        "CREATE INDEX ix_knowledge_catalog_embedding_cosine "
        "ON knowledge_catalog USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_catalog_embedding_cosine")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_catalog_metadata")
    op.drop_index("ix_knowledge_catalog_content_hash", table_name="knowledge_catalog")
    op.drop_index("ix_knowledge_catalog_identifier", table_name="knowledge_catalog")
    op.drop_index("ix_knowledge_catalog_jurisdiction", table_name="knowledge_catalog")
    op.drop_index("ix_knowledge_catalog_uf", table_name="knowledge_catalog")
    op.drop_index("ix_knowledge_catalog_source", table_name="knowledge_catalog")
    op.drop_table("knowledge_catalog")
    # Extensao mantida — pode ser usada por outras tabelas no futuro.
