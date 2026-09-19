"""ADR-070, roteiro passo 1: imutabilidade, projeções e histórico.

Não faz backfill, expurgo ou contração. Aplicar antes do passo 2.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "071es001"
down_revision = "069ce001"
branch_labels = None
depends_on = None

IMMUTABLE = ("evidence_versions", "evidence_reviews", "evidence_invalidations",
             "case_snapshots", "manifesto", "execucao_snapshot", "retorno_coleta")


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    for name, expression in {
        "knowledge_state": "content->'knowledge'->>'state'",
        "conclusion_class": "content->>'conclusion_class'",
        "predicate": "content->'attributes'->>'predicate'",
    }.items():
        op.add_column("evidence_versions", sa.Column(name, sa.Text(), sa.Computed(expression, persisted=True)))
    op.execute("""ALTER TABLE evidence_versions ADD CONSTRAINT ck_evidence_kind
        CHECK (content->>'kind' IS NOT NULL AND kind = content->>'kind') NOT VALID""")
    op.execute("""ALTER TABLE evidence_reviews ADD CONSTRAINT ck_evidence_action CHECK
        (action IN ('aprovar','corrigir','rejeitar','nao_aplicavel','substituida_por_nao_aplicavel')) NOT VALID""")
    for table in ("evidence_versions", "evidence_invalidations", "agent_executions", "case_snapshots"):
        op.create_unique_constraint(f"uq_{table}_scope_id", table, ["tenant_id", "process_id", "id"])
    op.create_table("manifesto", sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("execucao_snapshot", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("process_id", sa.Integer, nullable=False),
        sa.Column("execucao_id", sa.String(32), nullable=False), sa.Column("snapshot_id", sa.String(32), nullable=False),
        sa.Column("a_partir_passo", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("execucao_id", "snapshot_id", "a_partir_passo"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id", "execucao_id"],
            ["agent_executions.tenant_id", "agent_executions.process_id", "agent_executions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id", "snapshot_id"],
            ["case_snapshots.tenant_id", "case_snapshots.process_id", "case_snapshots.id"], ondelete="RESTRICT"))
    op.create_table("retorno_coleta", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("process_id", sa.Integer, nullable=False),
        sa.Column("invalidacao_id", sa.Integer, nullable=False, unique=True),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_stage", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "process_id", "invalidacao_id"],
            ["evidence_invalidations.tenant_id", "evidence_invalidations.process_id", "evidence_invalidations.id"], ondelete="RESTRICT"))
    op.execute("""CREATE FUNCTION public.rejeitar_mutacao_evidencia() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN RAISE EXCEPTION 'registro de evidencia imutavel: %', TG_TABLE_NAME;
        END $$""")
    for table in IMMUTABLE:
        op.execute(f"CREATE TRIGGER {table}_imutavel BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rejeitar_mutacao_evidencia()")
    op.execute("ALTER TABLE evidence_versions VALIDATE CONSTRAINT ck_evidence_kind")
    op.execute("ALTER TABLE evidence_reviews VALIDATE CONSTRAINT ck_evidence_action")


def downgrade():
    for table in reversed(IMMUTABLE):
        op.execute(f"DROP TRIGGER {table}_imutavel ON {table}")
    op.execute("DROP FUNCTION public.rejeitar_mutacao_evidencia()")
    for table in ("retorno_coleta", "execucao_snapshot", "manifesto"):
        op.drop_table(table)
    for table in ("evidence_versions", "evidence_invalidations", "agent_executions", "case_snapshots"):
        op.drop_constraint(f"uq_{table}_scope_id", table)
    op.drop_constraint("ck_evidence_action", "evidence_reviews")
    op.drop_constraint("ck_evidence_kind", "evidence_versions")
    for name in ("predicate", "conclusion_class", "knowledge_state"):
        op.drop_column("evidence_versions", name)
