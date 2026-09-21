"""ADR-070 roteiro passo 2: versões e fragmentos, sem backfill inferido."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "071es002"
down_revision = "071es001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_unique_constraint("uq_documents_tenant_id", "documents", ["tenant_id", "id"])
    op.create_table("documento_versao", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("documento_id", sa.Integer, nullable=False),
        sa.Column("numero", sa.Integer, nullable=False), sa.Column("sha256_original", sa.String(64), nullable=False),
        sa.Column("texto", sa.Text, nullable=False), sa.Column("sha256_texto", sa.String(64), nullable=False),
        sa.Column("metodo", sa.String, nullable=False), sa.Column("modelo", sa.String),
        sa.Column("parametros", JSONB, nullable=False), sa.Column("origem", sa.String, nullable=False),
        sa.Column("documento_origem_id", sa.Integer), sa.Column("paginas_lidas", sa.Integer),
        sa.Column("paginas_total", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("documento_id", "numero"), sa.UniqueConstraint("tenant_id", "id"),
        sa.CheckConstraint("numero > 0 AND sha256_original ~ '^[0-9a-f]{64}$' AND sha256_texto ~ '^[0-9a-f]{64}$'"),
        sa.ForeignKeyConstraint(["tenant_id", "documento_id"], ["documents.tenant_id", "documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "documento_origem_id"], ["documents.tenant_id", "documents.id"], ondelete="RESTRICT"))
    op.create_table("fragmento", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("documento_versao_id", sa.Integer, nullable=False),
        sa.Column("pagina", sa.Integer), sa.Column("inicio", sa.Integer, nullable=False),
        sa.Column("fim", sa.Integer, nullable=False), sa.Column("trecho", sa.Text, nullable=False),
        sa.Column("sha256_texto", sa.String(64), nullable=False),
        sa.UniqueConstraint("documento_versao_id", "inicio", "fim"), sa.UniqueConstraint("tenant_id", "id"),
        sa.CheckConstraint("inicio >= 0 AND fim > inicio AND (pagina IS NULL OR pagina > 0)"),
        sa.ForeignKeyConstraint(["tenant_id", "documento_versao_id"], ["documento_versao.tenant_id", "documento_versao.id"], ondelete="RESTRICT"))
    for table in ("documento_versao", "fragmento"):
        op.execute(f"CREATE TRIGGER {table}_imutavel BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rejeitar_mutacao_evidencia()")


def downgrade():
    op.drop_table("fragmento")
    op.drop_table("documento_versao")
    op.drop_constraint("uq_documents_tenant_id", "documents")
