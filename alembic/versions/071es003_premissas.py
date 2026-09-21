"""ADR-070 roteiro passo 3: referências e invariantes 1 e 2."""
import sqlalchemy as sa
from alembic import op

revision = "071es003"
down_revision = "071es002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    expressions = {
        "documento_versao_id": "(content->'attributes'->>'documento_versao_id')::integer",
        "fragmento_id": "(content->'attributes'->>'fragmento_id')::integer",
        "consulta_object_id": "content->'knowledge'->'verification'->'source'->>'id'",
        "consulta_version": "(content->'knowledge'->'verification'->'source'->>'version')::integer",
    }
    for name, expression in expressions.items():
        op.add_column("evidence_versions", sa.Column(name, sa.Text() if name == "consulta_object_id" else sa.Integer(),
            sa.Computed(expression, persisted=True)))
    for name, table in (("documento_versao_id", "documento_versao"), ("fragmento_id", "fragmento")):
        op.create_foreign_key(f"fk_ev_{name}", "evidence_versions", table,
            ["tenant_id", name], ["tenant_id", "id"], ondelete="RESTRICT")
    op.execute("""ALTER TABLE evidence_versions ADD CONSTRAINT fk_ev_consulta
        FOREIGN KEY (tenant_id,process_id,consulta_object_id,consulta_version)
        REFERENCES evidence_versions(tenant_id,process_id,object_id,version)
        DEFERRABLE INITIALLY DEFERRED NOT VALID""")
    op.execute("""ALTER TABLE evidence_versions ADD CONSTRAINT ck_ev_consulta
        CHECK (knowledge_state IS DISTINCT FROM 'ausencia_verificada_no_escopo'
          OR (consulta_object_id IS NOT NULL AND consulta_version IS NOT NULL)) NOT VALID""")
    op.execute("""ALTER TABLE evidence_versions ADD CONSTRAINT ck_ev_risco
        CHECK (conclusion_class IS DISTINCT FROM 'risco' OR
          (nullif(btrim(content->>'applicability_reason'),'') IS NOT NULL
           AND content->>'applicability' IS NOT DISTINCT FROM 'aplicavel')) NOT VALID""")
    op.create_table("evidence_premissa", sa.Column("tenant_id", sa.Integer, primary_key=True),
        sa.Column("process_id", sa.Integer, primary_key=True), sa.Column("dependente_id", sa.Integer, primary_key=True),
        sa.Column("premissa_object_id", sa.String(120), primary_key=True),
        sa.Column("premissa_version", sa.Integer, primary_key=True),
        sa.Column("papel", sa.String(30), nullable=False, server_default="premissa"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id", "dependente_id"],
            ["evidence_versions.tenant_id", "evidence_versions.process_id", "evidence_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id", "premissa_object_id", "premissa_version"],
            ["evidence_versions.tenant_id", "evidence_versions.process_id", "evidence_versions.object_id", "evidence_versions.version"],
            deferrable=True, initially="DEFERRED"))
    op.execute("""CREATE FUNCTION public.materializar_premissas() RETURNS trigger
      LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
      BEGIN
        INSERT INTO public.evidence_premissa(tenant_id,process_id,dependente_id,premissa_object_id,premissa_version)
        SELECT NEW.tenant_id,NEW.process_id,NEW.id,p->>'id',(p->>'version')::integer
        FROM jsonb_array_elements(COALESCE(NEW.content->'premises','[]'::jsonb)) p
        ON CONFLICT DO NOTHING;
        RETURN NEW;
      END $$""")
    op.execute("CREATE TRIGGER materializar_premissas AFTER INSERT ON evidence_versions FOR EACH ROW EXECUTE FUNCTION public.materializar_premissas()")
    op.execute("""CREATE FUNCTION public.validar_fundamento_evidencia() RETURNS trigger
      LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
      BEGIN
        IF NEW.knowledge_state = 'ausencia_verificada_no_escopo' AND NOT EXISTS (
          SELECT 1 FROM public.evidence_versions e WHERE e.tenant_id=NEW.tenant_id
          AND e.process_id=NEW.process_id AND e.object_id=NEW.consulta_object_id
          AND e.version=NEW.consulta_version AND e.kind='fonte_primaria' AND e.content->>'origin'='consulta')
        THEN RAISE EXCEPTION 'ausencia exige consulta primaria no caso' USING ERRCODE='23514'; END IF;
        IF NEW.conclusion_class = 'risco' AND NOT EXISTS (
          SELECT 1 FROM public.evidence_premissa p JOIN public.evidence_versions e
          ON (e.tenant_id,e.process_id,e.object_id,e.version)=
             (p.tenant_id,p.process_id,p.premissa_object_id,p.premissa_version)
          WHERE p.dependente_id=NEW.id AND p.tenant_id=NEW.tenant_id AND p.process_id=NEW.process_id
            AND (e.kind='observacao' OR (e.kind='conclusao' AND e.conclusion_class='fato_documental')))
        THEN RAISE EXCEPTION 'risco exige observacao ou fato documental' USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE CONSTRAINT TRIGGER validar_fundamento_evidencia AFTER INSERT ON evidence_versions
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.validar_fundamento_evidencia()""")
    op.execute("""CREATE TRIGGER evidence_premissa_imutavel BEFORE UPDATE OR DELETE ON evidence_premissa
      FOR EACH ROW EXECUTE FUNCTION public.rejeitar_mutacao_evidencia()""")
    # Copy only already-recorded edges; no inferred legacy support.
    op.execute("""INSERT INTO evidence_premissa(tenant_id,process_id,dependente_id,premissa_object_id,premissa_version)
      SELECT e.tenant_id,e.process_id,e.id,p->>'id',(p->>'version')::integer
      FROM evidence_versions e CROSS JOIN LATERAL jsonb_array_elements(COALESCE(e.content->'premises','[]'::jsonb)) p
      ON CONFLICT DO NOTHING""")
    for name in ("fk_ev_consulta", "ck_ev_consulta", "ck_ev_risco"):
        op.execute(f"ALTER TABLE evidence_versions VALIDATE CONSTRAINT {name}")


def downgrade():
    op.execute("DROP TRIGGER validar_fundamento_evidencia ON evidence_versions")
    op.execute("DROP TRIGGER materializar_premissas ON evidence_versions")
    op.execute("DROP FUNCTION public.validar_fundamento_evidencia()")
    op.execute("DROP FUNCTION public.materializar_premissas()")
    op.drop_table("evidence_premissa")
    for name in ("fk_ev_consulta", "ck_ev_consulta", "ck_ev_risco", "fk_ev_documento_versao_id", "fk_ev_fragmento_id"):
        op.drop_constraint(name, "evidence_versions")
    for name in ("consulta_version", "consulta_object_id", "fragmento_id", "documento_versao_id"):
        op.drop_column("evidence_versions", name)
