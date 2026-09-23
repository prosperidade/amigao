"""Motor jurídico determinístico (Incremento 4b, ADR-073).

Regra como dado versionado (tabelas do ADR-070 §10):

- `regra` / `regra_versao` — a tradução formal de cada regra da planilha da Ísis.
  O CONTEÚDO de uma versão é imutável (gatilho): mudar a condição é versão nova.
  Só o estado de homologação muda, e só de `rascunho` para frente.
- `conjunto_regras` / `conjunto_regras_item` — o que está publicado; um ativo por escopo.
- `execucao_motor` — retrato dos fatos de um caso + conjunto + data de referência.
- `avaliacao_regra` — append-only, uma linha por regra avaliada (seis estados).
- `ciencia_alerta` — append-only; o alerta crítico não bloqueia, mas não passa sem ciência.

Também: papel `homologar_regra` na curadoria, origem `motor` no passo da Rota e o
ponteiro do passo para a avaliação e o fundamento resolvido por ID.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "075mj001"
down_revision = "074zn001"
branch_labels = None
depends_on = None

APPEND_ONLY = ("execucao_motor", "avaliacao_regra", "ciencia_alerta")


def _created(nome="created_at"):
    return sa.Column(nome, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _fk_user(nome, nullable=True):
    return sa.Column(nome, sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=nullable)


def upgrade():
    # Fora da transação implícita não é necessário (PG ≥ 12); o valor só não pode ser
    # usado na mesma transação — e esta migration não o usa.
    op.execute("ALTER TYPE rota_passo_origem ADD VALUE IF NOT EXISTS 'motor'")

    op.drop_constraint("ck_papel_curadoria_papel", "papel_curadoria", type_="check")
    op.create_check_constraint(
        "ck_papel_curadoria_papel", "papel_curadoria",
        "papel IN ('validar_fonte_normativa','curar_corpus','homologar_regra')",
    )

    op.create_table(
        "regra",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("chave_origem", sa.String(120), nullable=False),
        sa.Column("rule_id", sa.String(60), nullable=False),
        sa.Column("matriz", sa.String(20), nullable=False),
        sa.Column("eixo", sa.String(80)),
        sa.Column("familia", sa.String(80)),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT")),
        _created(),
        sa.UniqueConstraint("chave_origem", "tenant_id", name="uq_regra_chave_tenant"),
    )
    op.create_index("ix_regra_tenant_id", "regra", ["tenant_id"])
    # UNIQUE com tenant NULL não barra duplicata na base global: índice parcial.
    op.create_index("uq_regra_chave_base", "regra", ["chave_origem"], unique=True,
                    postgresql_where=sa.text("tenant_id IS NULL"))

    op.create_table(
        "regra_versao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("regra_id", sa.Integer, sa.ForeignKey("regra.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("versao", sa.Integer, nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("motivo_nao_formalizavel", sa.Text),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("mensagem", sa.Text),
        sa.Column("aplicabilidade", JSONB, nullable=False),
        sa.Column("condicao", JSONB),
        sa.Column("consequencia", JSONB, nullable=False),
        sa.Column("fundamento", JSONB),
        sa.Column("severidade", sa.String(20)),
        sa.Column("decisao_profissional", JSONB),
        sa.Column("origem", JSONB, nullable=False),
        sa.Column("hash_conteudo", sa.String(64), nullable=False),
        _fk_user("homologada_por_id"),
        sa.Column("homologada_em", sa.DateTime(timezone=True)),
        sa.Column("nota_homologacao", sa.Text),
        _created(),
        sa.UniqueConstraint("regra_id", "versao", name="uq_regra_versao_numero"),
        sa.UniqueConstraint("regra_id", "hash_conteudo", name="uq_regra_versao_hash"),
        sa.CheckConstraint("estado IN ('rascunho', 'homologada', 'nao_formalizavel')",
                           name="ck_regra_versao_estado"),
        sa.CheckConstraint(
            "estado <> 'nao_formalizavel' OR (motivo_nao_formalizavel IS NOT NULL AND condicao IS NULL)",
            name="ck_regra_versao_nao_formalizavel_tem_motivo",
        ),
        sa.CheckConstraint(
            "estado <> 'homologada' OR (homologada_por_id IS NOT NULL AND homologada_em IS NOT NULL "
            "AND condicao IS NOT NULL)",
            name="ck_regra_versao_homologada_tem_autor",
        ),
    )
    op.create_index("ix_regra_versao_regra_id", "regra_versao", ["regra_id"])
    op.create_index("ix_regra_versao_homologada_por_id", "regra_versao", ["homologada_por_id"])
    # Conteúdo imutável; estado só sai de `rascunho` (homologar ou declarar não
    # formalizável), nunca volta. Apagar, nunca.
    op.execute(
        """CREATE FUNCTION public.regra_versao_conteudo_imutavel() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'regra_versao é registro permanente: DELETE recusado';
          END IF;
          IF (NEW.regra_id, NEW.versao, NEW.descricao, NEW.mensagem, NEW.aplicabilidade, NEW.condicao,
              NEW.consequencia, NEW.fundamento, NEW.severidade, NEW.decisao_profissional, NEW.origem,
              NEW.hash_conteudo)
             IS DISTINCT FROM
             (OLD.regra_id, OLD.versao, OLD.descricao, OLD.mensagem, OLD.aplicabilidade, OLD.condicao,
              OLD.consequencia, OLD.fundamento, OLD.severidade, OLD.decisao_profissional, OLD.origem,
              OLD.hash_conteudo) THEN
            RAISE EXCEPTION 'conteúdo de regra_versao é imutável: crie uma versão nova';
          END IF;
          IF OLD.estado <> 'rascunho' THEN
            RAISE EXCEPTION 'regra_versao % já saiu de rascunho (%)', OLD.id, OLD.estado;
          END IF;
          RETURN NEW;
        END $$"""
    )
    op.execute("CREATE TRIGGER regra_versao_imutavel BEFORE UPDATE OR DELETE ON regra_versao "
               "FOR EACH ROW EXECUTE FUNCTION public.regra_versao_conteudo_imutavel()")
    op.execute("CREATE TRIGGER regra_versao_sem_truncate BEFORE TRUNCATE ON regra_versao "
               "FOR EACH STATEMENT EXECUTE FUNCTION public.rejeitar_truncate_evidencia()")

    op.create_table(
        "conjunto_regras",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT")),
        sa.Column("estado", sa.String(20), nullable=False, server_default="rascunho"),
        _fk_user("publicado_por_id"),
        sa.Column("publicado_em", sa.DateTime(timezone=True)),
        sa.Column("ativado_em", sa.DateTime(timezone=True)),
        _created(),
        sa.CheckConstraint("estado IN ('rascunho', 'publicado', 'ativo', 'inativo')",
                           name="ck_conjunto_regras_estado"),
        sa.CheckConstraint(
            "estado = 'rascunho' OR (publicado_por_id IS NOT NULL AND publicado_em IS NOT NULL)",
            name="ck_conjunto_regras_publicado_tem_autor",
        ),
    )
    op.create_index("uq_conjunto_regras_ativo_base", "conjunto_regras", ["estado"], unique=True,
                    postgresql_where=sa.text("estado = 'ativo' AND tenant_id IS NULL"))
    op.create_index("uq_conjunto_regras_ativo_tenant", "conjunto_regras", ["tenant_id"], unique=True,
                    postgresql_where=sa.text("estado = 'ativo' AND tenant_id IS NOT NULL"))
    op.create_index("ix_conjunto_regras_tenant_id", "conjunto_regras", ["tenant_id"])
    op.create_index("ix_conjunto_regras_publicado_por_id", "conjunto_regras", ["publicado_por_id"])

    op.create_table(
        "conjunto_regras_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("conjunto_id", sa.Integer, sa.ForeignKey("conjunto_regras.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("regra_versao_id", sa.Integer, sa.ForeignKey("regra_versao.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.UniqueConstraint("conjunto_id", "regra_versao_id", name="uq_conjunto_regras_item"),
    )
    op.create_index("ix_conjunto_regras_item_regra_versao_id", "conjunto_regras_item", ["regra_versao_id"])

    op.create_table(
        "execucao_motor",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("process_id", sa.Integer, sa.ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("conjunto_id", sa.Integer, sa.ForeignKey("conjunto_regras.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("conjunto_tenant_id", sa.Integer, sa.ForeignKey("conjunto_regras.id", ondelete="RESTRICT")),
        sa.Column("data_referencia", sa.Date, nullable=False),
        sa.Column("fatos", JSONB, nullable=False),
        sa.Column("fatos_hash", sa.String(64), nullable=False),
        _fk_user("iniciado_por_id"),
        _created("criado_em"),
    )
    op.create_index("ix_execucao_motor_caso", "execucao_motor", ["tenant_id", "process_id"])
    op.create_index("ix_execucao_motor_process_id", "execucao_motor", ["process_id"])
    op.create_index("ix_execucao_motor_conjunto_id", "execucao_motor", ["conjunto_id"])
    op.create_index("ix_execucao_motor_conjunto_tenant_id", "execucao_motor", ["conjunto_tenant_id"])
    op.create_index("ix_execucao_motor_iniciado_por_id", "execucao_motor", ["iniciado_por_id"])

    op.create_table(
        "avaliacao_regra",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("execucao_id", sa.Integer, sa.ForeignKey("execucao_motor.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("regra_versao_id", sa.Integer, sa.ForeignKey("regra_versao.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("estado", sa.String(30), nullable=False),
        sa.Column("faltantes", ARRAY(sa.String(80))),
        sa.Column("entradas", JSONB),
        sa.Column("consequencia", JSONB),
        sa.Column("fundamento_fonte_versao_id", sa.Integer,
                  sa.ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT")),
        sa.Column("fundamento_dispositivo_id", sa.Integer, sa.ForeignKey("dispositivo.id", ondelete="RESTRICT")),
        sa.Column("fundamento_caminho", sa.String(300)),
        sa.Column("fundamento_razao", sa.String(40)),
        sa.Column("detalhe_erro", sa.Text),
        _created("criado_em"),
        sa.UniqueConstraint("execucao_id", "regra_versao_id", name="uq_avaliacao_regra_execucao"),
        sa.CheckConstraint(
            "estado IN ('nao_aplicavel', 'aplicavel_disparou', 'aplicavel_nao_disparou', 'indeterminado', "
            "'conflito', 'erro_execucao')",
            name="ck_avaliacao_regra_estado",
        ),
        sa.CheckConstraint("(fundamento_dispositivo_id IS NULL) = (fundamento_fonte_versao_id IS NULL)",
                           name="ck_avaliacao_regra_fundamento_par"),
        sa.CheckConstraint("estado <> 'erro_execucao' OR detalhe_erro IS NOT NULL",
                           name="ck_avaliacao_regra_erro_tem_detalhe"),
    )
    op.create_index("ix_avaliacao_regra_execucao", "avaliacao_regra", ["tenant_id", "execucao_id"])
    op.create_index("ix_avaliacao_regra_execucao_id", "avaliacao_regra", ["execucao_id"])
    op.create_index("ix_avaliacao_regra_regra_versao_id", "avaliacao_regra", ["regra_versao_id"])
    op.create_index("ix_avaliacao_regra_fonte_versao_id", "avaliacao_regra", ["fundamento_fonte_versao_id"])
    op.create_index("ix_avaliacao_regra_dispositivo_id", "avaliacao_regra", ["fundamento_dispositivo_id"])

    op.create_table(
        "ciencia_alerta",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("avaliacao_id", sa.Integer, sa.ForeignKey("avaliacao_regra.id", ondelete="RESTRICT"),
                  nullable=False),
        _fk_user("user_id", nullable=False),
        sa.Column("justificativa", sa.Text, nullable=False),
        _created("registrada_em"),
        sa.UniqueConstraint("avaliacao_id", name="uq_ciencia_alerta_avaliacao"),
        sa.CheckConstraint("length(trim(justificativa)) > 0", name="ck_ciencia_alerta_justificativa"),
    )
    op.create_index("ix_ciencia_alerta_user_id", "ciencia_alerta", ["user_id"])
    op.create_index("ix_ciencia_alerta_tenant_id", "ciencia_alerta", ["tenant_id"])

    for tabela in APPEND_ONLY:
        op.execute(f"CREATE TRIGGER {tabela}_imutavel BEFORE UPDATE OR DELETE ON {tabela} "  # noqa: S608
                   "FOR EACH ROW EXECUTE FUNCTION public.rejeitar_mutacao_evidencia()")
        op.execute(f"CREATE TRIGGER {tabela}_sem_truncate BEFORE TRUNCATE ON {tabela} "  # noqa: S608
                   "FOR EACH STATEMENT EXECUTE FUNCTION public.rejeitar_truncate_evidencia()")

    op.add_column("rota_passos", sa.Column(
        "origem_avaliacao_id", sa.Integer, sa.ForeignKey("avaliacao_regra.id", ondelete="SET NULL")))
    op.add_column("rota_passos", sa.Column(
        "fundamento_fonte_versao_id", sa.Integer, sa.ForeignKey("fonte_normativa_versao.id", ondelete="SET NULL")))
    op.add_column("rota_passos", sa.Column(
        "fundamento_dispositivo_id", sa.Integer, sa.ForeignKey("dispositivo.id", ondelete="SET NULL")))
    for coluna in ("origem_avaliacao_id", "fundamento_fonte_versao_id", "fundamento_dispositivo_id"):
        op.create_index(f"ix_rota_passos_{coluna}", "rota_passos", [coluna])


def downgrade():
    for coluna in ("origem_avaliacao_id", "fundamento_fonte_versao_id", "fundamento_dispositivo_id"):
        op.drop_index(f"ix_rota_passos_{coluna}", table_name="rota_passos")
        op.drop_column("rota_passos", coluna)
    # DROP TABLE não dispara gatilho de linha nem de TRUNCATE: a trilha só some aqui,
    # por decisão explícita de desfazer a migration.
    for tabela in ("ciencia_alerta", "avaliacao_regra", "execucao_motor", "conjunto_regras_item",
                   "conjunto_regras", "regra_versao", "regra"):
        op.drop_table(tabela)
    op.execute("DROP FUNCTION IF EXISTS public.regra_versao_conteudo_imutavel()")
    # Papel concedido em `homologar_regra` impede voltar: o CHECK antigo falha alto.
    op.drop_constraint("ck_papel_curadoria_papel", "papel_curadoria", type_="check")
    op.create_check_constraint(
        "ck_papel_curadoria_papel", "papel_curadoria",
        "papel IN ('validar_fonte_normativa','curar_corpus')",
    )
    # Valor de ENUM não se remove no PostgreSQL sem recriar o tipo. Passo com
    # origem `motor` impede o downgrade de fazer sentido; o valor fica, inerte.
