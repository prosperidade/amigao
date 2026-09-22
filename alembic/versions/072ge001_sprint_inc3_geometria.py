"""ADR-072: leitura geoespacial, feição, medição, projeção e confronto (append-only).

Sem backfill: nenhuma área de coluna legada vira medição, e o único KMZ guardado
em produção só é lido por ação explícita ("Ler geometria").
"""
import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision = "072ge001"
down_revision = "071es004"
branch_labels = None
depends_on = None

IMUTAVEIS = ("arquivo_geo", "feicao", "medicao", "projecao_geometria", "confronto_area")


def _created(name="created_at"):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_unique_constraint("uq_processes_tenant_id", "processes", ["tenant_id", "id"])
    op.create_unique_constraint("uq_properties_tenant_id", "properties", ["tenant_id", "id"])

    op.create_table("arquivo_geo", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("process_id", sa.Integer),
        sa.Column("documento_id", sa.Integer, nullable=False), sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("sha256_original", sa.String(64)), sa.Column("formato", sa.String(20), nullable=False),
        sa.Column("membro_lido", sa.String), sa.Column("inventario", JSONB, nullable=False),
        sa.Column("crs_origem", sa.String), sa.Column("estado", sa.String(10), nullable=False),
        sa.Column("falha_codigo", sa.String(40)), sa.Column("falha_detalhe", sa.Text),
        sa.Column("metodo_versao", sa.String(20), nullable=False),
        sa.Column("lido_por_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _created("lido_em"),
        sa.UniqueConstraint("documento_id", "numero"), sa.UniqueConstraint("tenant_id", "id"),
        sa.CheckConstraint("numero > 0 AND (sha256_original IS NULL OR sha256_original ~ '^[0-9a-f]{64}$')"),
        sa.CheckConstraint("(estado = 'lido' AND falha_codigo IS NULL AND sha256_original IS NOT NULL)"
                           " OR (estado = 'falha' AND falha_codigo IS NOT NULL)", name="ck_arquivo_geo_estado"),
        sa.ForeignKeyConstraint(["tenant_id", "documento_id"], ["documents.tenant_id", "documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id"], ["processes.tenant_id", "processes.id"], ondelete="RESTRICT"))
    op.create_index("ix_arquivo_geo_tenant_id", "arquivo_geo", ["tenant_id"])

    op.create_table("feicao", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("arquivo_geo_id", sa.Integer, nullable=False),
        sa.Column("ordem", sa.Integer, nullable=False), sa.Column("identificador_interno", sa.String, nullable=False),
        sa.Column("nome", sa.String), sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("srid_origem", sa.Integer, nullable=False),
        sa.Column("geom_original", Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False),
        sa.Column("geom", Geometry("GEOMETRY", srid=4674, spatial_index=False), nullable=False),
        sa.Column("valida", sa.Boolean, nullable=False), sa.Column("motivo_invalidade", sa.String),
        sa.Column("aneis_internos", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("arquivo_geo_id", "ordem"), sa.UniqueConstraint("tenant_id", "id"),
        sa.CheckConstraint("tipo IN ('poligono','multipoligono','linha','ponto')"),
        sa.CheckConstraint("valida OR motivo_invalidade IS NOT NULL", name="ck_feicao_invalida_tem_motivo"),
        sa.ForeignKeyConstraint(["tenant_id", "arquivo_geo_id"], ["arquivo_geo.tenant_id", "arquivo_geo.id"], ondelete="RESTRICT"))
    op.create_index("ix_feicao_tenant_id", "feicao", ["tenant_id"])
    op.execute("CREATE INDEX ix_feicao_geom ON feicao USING gist (geom)")

    op.create_table("medicao", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("process_id", sa.Integer, nullable=False),
        sa.Column("grandeza", sa.String(20), nullable=False), sa.Column("objeto", sa.String(40), nullable=False),
        sa.Column("origem_tipo", sa.String(30), nullable=False), sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("valor_ha", sa.Numeric(20, 8)), sa.Column("motivo", sa.String),
        sa.Column("metodo", sa.String, nullable=False), sa.Column("metodo_versao", sa.String(20), nullable=False),
        sa.Column("crs_calculo", sa.String), sa.Column("motor_versao", sa.String),
        sa.Column("documento_id", sa.Integer, nullable=False), sa.Column("feicao_id", sa.Integer),
        sa.Column("evidence_version_id", sa.Integer), sa.Column("predicado", sa.String),
        sa.Column("literal", sa.Text), _created(),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.CheckConstraint("grandeza = 'area' AND objeto = 'imovel_total'"),
        sa.CheckConstraint("origem_tipo IN ('feicao_calculada','registro','declaracao_textual')"),
        sa.CheckConstraint("(estado = 'determinado' AND valor_ha IS NOT NULL AND valor_ha > 0)"
                           " OR (estado = 'nao_determinado' AND valor_ha IS NULL AND motivo IS NOT NULL)",
                           name="ck_medicao_estado"),
        # Arco exclusivo: calculada aponta feição; declarada aponta a observação que a sustenta.
        sa.CheckConstraint("(origem_tipo = 'feicao_calculada' AND feicao_id IS NOT NULL AND evidence_version_id IS NULL)"
                           " OR (origem_tipo <> 'feicao_calculada' AND evidence_version_id IS NOT NULL AND feicao_id IS NULL)",
                           name="ck_medicao_arco_fonte"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id"], ["processes.tenant_id", "processes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "documento_id"], ["documents.tenant_id", "documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "feicao_id"], ["feicao.tenant_id", "feicao.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "evidence_version_id"], ["evidence_versions.tenant_id", "evidence_versions.id"], ondelete="RESTRICT"))
    op.create_index("ix_medicao_tenant_process", "medicao", ["tenant_id", "process_id"])
    # Uma medição por fonte e método: reler não duplica, método novo gera linha nova.
    op.execute("CREATE UNIQUE INDEX uq_medicao_feicao_metodo ON medicao (feicao_id, metodo_versao) WHERE feicao_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX uq_medicao_obs_metodo ON medicao (evidence_version_id, metodo_versao) WHERE evidence_version_id IS NOT NULL")

    op.create_table("projecao_geometria", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("property_id", sa.Integer, nullable=False),
        sa.Column("process_id", sa.Integer, nullable=False), sa.Column("feicao_id", sa.Integer, nullable=False),
        sa.Column("regra", sa.String(40)),
        sa.Column("autor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("motivo", sa.String, nullable=False), _created(),
        sa.CheckConstraint("(regra IS NOT NULL) <> (autor_id IS NOT NULL)", name="ck_projecao_regra_ou_autor"),
        sa.CheckConstraint("length(btrim(motivo)) > 0"),
        sa.ForeignKeyConstraint(["tenant_id", "property_id"], ["properties.tenant_id", "properties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id"], ["processes.tenant_id", "processes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "feicao_id"], ["feicao.tenant_id", "feicao.id"], ondelete="RESTRICT"))
    op.create_index("ix_projecao_geometria_property", "projecao_geometria", ["tenant_id", "property_id"])

    op.create_table("confronto_area", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False), sa.Column("process_id", sa.Integer, nullable=False),
        sa.Column("execucao", sa.String(32), nullable=False),
        sa.Column("medicao_calculada_id", sa.Integer, nullable=False),
        sa.Column("medicao_referencia_id", sa.Integer, nullable=False),
        sa.Column("delta_ha", sa.Numeric(20, 8)), sa.Column("denominador_regra", sa.String(40), nullable=False),
        sa.Column("denominador_ha", sa.Numeric(20, 8)), sa.Column("percentual", sa.Numeric(20, 10)),
        sa.Column("percentual_sobre_maior", sa.Numeric(20, 10)),
        sa.Column("tolerancia_pct", sa.Float, nullable=False), sa.Column("tolerancia_origem", sa.String(80), nullable=False),
        sa.Column("resultado", sa.String(30), nullable=False), sa.Column("grau", sa.String(20), nullable=False),
        sa.Column("metodo_versao", sa.String(20), nullable=False),
        sa.Column("executado_por_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _created(),
        sa.UniqueConstraint("execucao", "medicao_calculada_id", "medicao_referencia_id"),
        sa.CheckConstraint("resultado IN ('dentro_da_tolerancia','divergente','nao_calculavel')"),
        sa.CheckConstraint("tolerancia_pct >= 0 AND length(btrim(tolerancia_origem)) > 0"),
        sa.CheckConstraint("resultado = 'nao_calculavel' OR (percentual IS NOT NULL AND denominador_ha IS NOT NULL)",
                           name="ck_confronto_denominador_declarado"),
        sa.ForeignKeyConstraint(["tenant_id", "process_id"], ["processes.tenant_id", "processes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "medicao_calculada_id"], ["medicao.tenant_id", "medicao.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "medicao_referencia_id"], ["medicao.tenant_id", "medicao.id"], ondelete="RESTRICT"))
    op.create_index("ix_confronto_area_tenant_process", "confronto_area", ["tenant_id", "process_id"])
    op.create_index("ix_confronto_area_execucao", "confronto_area", ["execucao"])

    for table in IMUTAVEIS:
        op.execute(f"CREATE TRIGGER {table}_imutavel BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rejeitar_mutacao_evidencia()")


def downgrade():
    for table in reversed(IMUTAVEIS):
        op.drop_table(table)
    op.drop_constraint("uq_properties_tenant_id", "properties")
    op.drop_constraint("uq_processes_tenant_id", "processes")
