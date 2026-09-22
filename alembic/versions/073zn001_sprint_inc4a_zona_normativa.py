"""ADR-075 + A1–A5: zona normativa — fonte, versão, proveniência, dispositivo, trecho.

Só tabelas NOVAS. O corpus legado (`legislation_documents`, `knowledge_catalog`)
não é alterado: nenhuma coluna nova, nenhum UPDATE, nenhum reindex do ivfflat
(MIGRACAO §7). O catálogo é povoado depois, por `scripts/zona_normativa_construir.py`
(dry-run por padrão), e a Legislação continua desligada até as sondas verdes.

`validacao_norma` é append-only (gatilho), com hash chain própria do catálogo
global — o catálogo não tem tenant.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

revision = "073zn001"
down_revision = "072ge001"
branch_labels = None
depends_on = None

NIVEIS = ("norma", "interpretacao", "exigencia", "procedimento", "precedente", "radar", "nao_determinado")
STATUS = ("bruto", "proposto", "validado")


def _in(col, valores):
    return f"{col} IN ({', '.join(repr(v) for v in valores)})"


def _created(name="created_at"):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")

    op.create_table(
        "fonte_normativa",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("identidade", sa.String(220), nullable=False, unique=True),
        sa.Column("identidade_determinada", sa.Boolean, nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("ente", sa.String(2), nullable=False),
        sa.Column("orgao", sa.String(40), nullable=False, server_default=""),
        sa.Column("numero", sa.String(200), nullable=False, server_default=""),
        sa.Column("ano", sa.Integer),
        sa.Column("esfera", sa.String(12), nullable=False),
        sa.Column("uf", sa.String(2)),
        sa.Column("rotulo", sa.String(220), nullable=False),
        sa.Column("titulo", sa.Text),
        sa.Column("nivel_autoridade", sa.String(20), nullable=False, server_default="nao_determinado"),
        sa.Column("nivel_origem", sa.String(80), nullable=False),
        sa.Column("objetivos", ARRAY(sa.String(40))),
        sa.Column("objetivos_origem", sa.String(80)),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT")),
        _created(),
        sa.CheckConstraint(_in("nivel_autoridade", NIVEIS), name="ck_fonte_nivel"),
        sa.CheckConstraint("esfera IN ('federal','estadual','municipal')", name="ck_fonte_esfera"),
        sa.CheckConstraint("tenant_id IS NULL OR nivel_autoridade = 'precedente'",
                           name="ck_fonte_so_precedente_privado"),
        sa.CheckConstraint("nivel_autoridade <> 'precedente' OR tenant_id IS NOT NULL",
                           name="ck_fonte_precedente_privado_por_padrao"),
    )
    op.create_index("ix_fonte_normativa_nivel", "fonte_normativa", ["nivel_autoridade"])
    op.create_index("ix_fonte_normativa_uf", "fonte_normativa", ["uf"])

    op.create_table(
        "fonte_normativa_versao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fonte_id", sa.Integer, sa.ForeignKey("fonte_normativa.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("status_validacao", sa.String(12), nullable=False, server_default="bruto"),
        sa.Column("vigencia_estado", sa.String(16), nullable=False, server_default="nao_determinada"),
        sa.Column("vigencia_inicio", sa.Date),
        sa.Column("vigencia_fim", sa.Date),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("hash_texto", sa.String(64), nullable=False),
        sa.Column("hash_original", sa.String(64)),
        sa.Column("original_storage_key", sa.String(500)),
        sa.Column("original_conferido_em", sa.DateTime(timezone=True)),
        sa.Column("bloqueio_citacao", sa.String(40)),
        sa.Column("substitui_versao_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT")),
        sa.Column("origem_ingestao", sa.String(40), nullable=False),
        _created(),
        sa.UniqueConstraint("fonte_id", "hash_texto", name="uq_versao_fonte_hash"),
        sa.CheckConstraint(_in("status_validacao", STATUS), name="ck_versao_status"),
        sa.CheckConstraint("vigencia_estado IN ('determinada','nao_determinada')",
                           name="ck_versao_vigencia_estado"),
        sa.CheckConstraint("hash_texto ~ '^[0-9a-f]{64}$' AND "
                           "(hash_original IS NULL OR hash_original ~ '^[0-9a-f]{64}$')",
                           name="ck_versao_hashes"),
    )
    op.create_index("ix_fonte_normativa_versao_fonte", "fonte_normativa_versao", ["fonte_id"])

    op.create_table(
        "fonte_normativa_proveniencia",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fonte_versao_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("legislation_document_id", sa.Integer,
                  sa.ForeignKey("legislation_documents.id", ondelete="RESTRICT")),
        sa.Column("source_ref", sa.String(255)),
        sa.Column("documento_origem_rotulo", sa.String(255), nullable=False),
        sa.Column("offset_inicio", sa.Integer),
        sa.Column("offset_fim", sa.Integer),
        sa.Column("pagina_inicio", sa.Integer),
        sa.Column("pagina_fim", sa.Integer),
        sa.Column("url_impressa", sa.Text),
        sa.Column("impresso_em", sa.String(20)),
        sa.Column("sinal_fronteira", sa.String(30), nullable=False),
        sa.Column("motivos_revisao", ARRAY(sa.String(60))),
        sa.Column("trecho_hash", sa.String(64), nullable=False),
        _created(),
        sa.CheckConstraint("legislation_document_id IS NOT NULL OR source_ref IS NOT NULL",
                           name="ck_proveniencia_tem_origem"),
        sa.CheckConstraint("sinal_fronteira IN ('impressao','cabecalho_formal','sem_sinal','documento_inteiro')",
                           name="ck_proveniencia_sinal"),
    )
    op.create_index("ix_proveniencia_versao", "fonte_normativa_proveniencia", ["fonte_versao_id"])
    op.create_index("ix_proveniencia_doc", "fonte_normativa_proveniencia", ["legislation_document_id"])

    op.create_table(
        "dispositivo",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fonte_versao_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("caminho", sa.String(300), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("artigo", sa.String(20)),
        sa.Column("paragrafo", sa.String(20)),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("dispositivo.id", ondelete="RESTRICT")),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("fonte_versao_id", "caminho", name="uq_dispositivo_caminho"),
        sa.CheckConstraint("tipo IN ('preambulo','artigo','paragrafo','anexo')", name="ck_dispositivo_tipo"),
    )
    op.create_index("ix_dispositivo_versao_artigo", "dispositivo", ["fonte_versao_id", "artigo"])

    op.create_table(
        "trecho_normativo",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("fonte_versao_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dispositivo_id", sa.Integer, sa.ForeignKey("dispositivo.id", ondelete="RESTRICT")),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("cabecalho", sa.String(300), nullable=False),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tsv", TSVECTOR,
                  sa.Computed("to_tsvector('portuguese'::regconfig, cabecalho || ' ' || texto)",
                              persisted=True)),
        sa.Column("embedding_model", sa.String(100)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("fonte_versao_id", "ordem", name="uq_trecho_versao_ordem"),
    )
    # Coluna vetorial por SQL: o tipo `vector` não tem reflexo no SQLAlchemy sem o
    # pacote pgvector (mesma escolha do knowledge_catalog). SEM índice ANN: a busca é
    # exata sobre o elegível enquanto ele couber (ADR-075 §7, #247).
    op.execute("ALTER TABLE trecho_normativo ADD COLUMN embedding vector(768)")
    op.create_index("ix_trecho_normativo_versao", "trecho_normativo", ["fonte_versao_id"])
    op.execute("CREATE INDEX ix_trecho_normativo_tsv ON trecho_normativo USING gin (tsv)")

    op.create_table(
        "interpretacao_norma",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("interpretacao_fonte_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("norma_fonte_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("artigo", sa.String(20)),
        sa.Column("citacao_literal", sa.Text),
        sa.Column("origem", sa.String(30), nullable=False),
        sa.Column("status_validacao", sa.String(12), nullable=False, server_default="bruto"),
        sa.UniqueConstraint("interpretacao_fonte_id", "norma_fonte_id", "artigo",
                            name="uq_interpretacao_norma"),
        sa.CheckConstraint(_in("status_validacao", STATUS), name="ck_interp_status"),
    )
    op.create_index("ix_interpretacao_norma_alvo", "interpretacao_norma", ["norma_fonte_id", "artigo"])

    op.create_table(
        "validacao_norma",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fonte_versao_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("acao", sa.String(30), nullable=False),
        sa.Column("status_de", sa.String(12), nullable=False),
        sa.Column("status_para", sa.String(12), nullable=False),
        sa.Column("validador_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("papel_na_curadoria", sa.String(60), nullable=False),
        sa.Column("area", sa.String(20), nullable=False),
        sa.Column("decisao", sa.String(20), nullable=False),
        sa.Column("nota", sa.Text, nullable=False),
        sa.Column("hash_texto", sa.String(64), nullable=False),
        sa.Column("evidencias", JSONB),
        _created("registrado_em"),
        sa.Column("hash_anterior", sa.String(64)),
        sa.Column("hash_evento", sa.String(64), nullable=False, unique=True),
        sa.CheckConstraint(_in("status_de", STATUS), name="ck_validacao_de"),
        sa.CheckConstraint(_in("status_para", STATUS), name="ck_validacao_para"),
        sa.CheckConstraint("decisao IN ('aprovado','devolvido')", name="ck_validacao_decisao"),
        sa.CheckConstraint("length(trim(nota)) > 0", name="ck_validacao_nota"),
    )
    op.create_index("ix_validacao_norma_versao", "validacao_norma", ["fonte_versao_id"])
    op.execute("CREATE TRIGGER validacao_norma_imutavel BEFORE UPDATE OR DELETE ON validacao_norma "
               "FOR EACH ROW EXECUTE FUNCTION public.rejeitar_mutacao_evidencia()")

    op.create_table(
        "papel_curadoria",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("papel", sa.String(60), nullable=False),
        sa.Column("area", sa.String(20), nullable=False),
        sa.Column("concedido_por_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        _created("concedido_em"),
        sa.Column("revogado_em", sa.DateTime(timezone=True)),
        sa.Column("revogado_por_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("motivo", sa.Text),
        sa.CheckConstraint("papel IN ('validar_fonte_normativa','curar_corpus')",
                           name="ck_papel_curadoria_papel"),
    )
    op.create_index("ix_papel_curadoria_user", "papel_curadoria", ["user_id"])

    op.create_table(
        "tarefa_revisao_normativa",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fonte_versao_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT")),
        sa.Column("legislation_document_id", sa.Integer,
                  sa.ForeignKey("legislation_documents.id", ondelete="RESTRICT")),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("detalhe", JSONB, nullable=False),
        _created("aberta_em"),
        sa.Column("resolvida_em", sa.DateTime(timezone=True)),
        sa.Column("resolvida_por_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("resolucao", sa.Text),
        sa.CheckConstraint(
            "tipo IN ('fronteira_ambigua','identidade_nao_determinada','original_divergente',"
            "'original_ausente','conflito_material','nivel_nao_determinado')",
            name="ck_tarefa_revisao_tipo"),
    )
    op.create_index("ix_tarefa_revisao_aberta", "tarefa_revisao_normativa", ["tipo", "resolvida_em"])


def downgrade():
    op.drop_table("tarefa_revisao_normativa")
    op.drop_table("papel_curadoria")
    op.drop_table("validacao_norma")
    op.drop_table("interpretacao_norma")
    op.drop_table("trecho_normativo")
    op.drop_table("dispositivo")
    op.drop_table("fonte_normativa_proveniencia")
    op.drop_table("fonte_normativa_versao")
    op.drop_table("fonte_normativa")
