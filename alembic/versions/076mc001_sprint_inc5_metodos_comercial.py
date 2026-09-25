"""Métodos e fechamento comercial (Incremento 5, ADR-074).

- `rota_passos.remocao_motivo` — o motivo da remoção lembrada deixa de viver só na
  trilha de auditoria: o orçamento precisa dizer por que um item saiu.
- `orcamento_metodo` — métodos e preços do tenant, versionados: mudar preço é versão nova.
- `redacao_comercial` — relatório preliminar e especificação de escopo (Redator
  pré-contratação), versionados, com a base de que dependem e a revisão humana.
- `orcamento` / `orcamento_item` — orçamento derivado da Rota: um item por passo, com o
  método e o cálculo como foto.
- `orcamento_escolha` — a escolha do consultor (método, quantidade) por passo, que
  sobrevive à próxima versão do orçamento.
- `proposals.orcamento_id` — a proposta aponta o orçamento de onde nasceu.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "076mc001"
down_revision = "075mj001"
branch_labels = None
depends_on = None


def _created():
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _revisao():
    """Revisão humana do artefato e o eixo de versão (superada)."""
    return [
        sa.Column("estado_revisao", sa.String(20), nullable=False, server_default="proposta"),
        sa.Column("revisado_por_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("revisado_em", sa.DateTime(timezone=True)),
        sa.Column("justificativa", sa.Text),
        sa.Column("superada_em", sa.DateTime(timezone=True)),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _created(),
    ]


def _indices(tabela, colunas):
    for c in colunas:
        op.create_index(f"ix_{tabela}_{c}", tabela, [c])


def upgrade():
    op.add_column("rota_passos", sa.Column("remocao_motivo", sa.Text))

    op.create_table(
        "orcamento_metodo",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("codigo", sa.String(60), nullable=False),
        sa.Column("versao", sa.Integer, nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("unidade", sa.String(20), nullable=False),
        sa.Column("valor_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantidade_padrao", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("rule_ids", ARRAY(sa.String(60)), nullable=False, server_default="{}"),
        sa.Column("padrao", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _created(),
        sa.UniqueConstraint("tenant_id", "codigo", "versao", name="uq_orcamento_metodo_versao"),
        sa.CheckConstraint("unidade IN ('hora','fixo','unidade')", name="ck_orcamento_metodo_unidade"),
        sa.CheckConstraint("valor_unitario >= 0", name="ck_orcamento_metodo_valor"),
        sa.CheckConstraint("quantidade_padrao > 0", name="ck_orcamento_metodo_quantidade"),
    )
    _indices("orcamento_metodo", ["tenant_id", "criado_por_id"])

    op.create_table(
        "redacao_comercial",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("process_id", sa.Integer, sa.ForeignKey("processes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("versao", sa.Integer, nullable=False),
        sa.Column("rota_id", sa.Integer, sa.ForeignKey("rotas.id", ondelete="SET NULL")),
        sa.Column("execucao_motor_id", sa.Integer, sa.ForeignKey("execucao_motor.id", ondelete="RESTRICT")),
        sa.Column("conteudo", JSONB, nullable=False),
        sa.Column("base", JSONB, nullable=False),
        sa.Column("base_hash", sa.String(64), nullable=False),
        *_revisao(),
        sa.UniqueConstraint("tenant_id", "process_id", "tipo", "versao", name="uq_redacao_comercial_versao"),
        sa.CheckConstraint("tipo IN ('relatorio_preliminar','especificacao_escopo')", name="ck_redacao_comercial_tipo"),
        sa.CheckConstraint("estado_revisao IN ('proposta','aprovada','rejeitada')",
                           name="ck_redacao_comercial_revisao"),
    )
    _indices("redacao_comercial", ["tenant_id", "process_id", "rota_id", "execucao_motor_id",
                                   "revisado_por_id", "criado_por_id"])

    op.create_table(
        "orcamento",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("process_id", sa.Integer, sa.ForeignKey("processes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("versao", sa.Integer, nullable=False),
        sa.Column("rota_id", sa.Integer, sa.ForeignKey("rotas.id", ondelete="SET NULL")),
        sa.Column("escopo_id", sa.Integer, sa.ForeignKey("redacao_comercial.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("fora", JSONB, nullable=False, server_default="[]"),
        sa.Column("ressalvas", JSONB, nullable=False, server_default="[]"),
        sa.Column("base", JSONB, nullable=False),
        sa.Column("base_hash", sa.String(64), nullable=False),
        *_revisao(),
        sa.UniqueConstraint("tenant_id", "process_id", "versao", name="uq_orcamento_versao"),
        sa.CheckConstraint("estado_revisao IN ('proposta','aprovada','rejeitada')", name="ck_orcamento_revisao"),
        sa.CheckConstraint("total >= 0", name="ck_orcamento_total"),
    )
    _indices("orcamento", ["tenant_id", "process_id", "rota_id", "escopo_id", "revisado_por_id", "criado_por_id"])

    op.create_table(
        "orcamento_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("orcamento_id", sa.Integer, sa.ForeignKey("orcamento.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rota_passo_id", sa.Integer, sa.ForeignKey("rota_passos.id", ondelete="SET NULL")),
        sa.Column("metodo_id", sa.Integer, sa.ForeignKey("orcamento_metodo.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("escolha", sa.String(20), nullable=False),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("descricao", sa.String, nullable=False),
        sa.Column("fundamento", JSONB, nullable=False, server_default="{}"),
        sa.Column("unidade", sa.String(20), nullable=False),
        sa.Column("quantidade", sa.Numeric(10, 2), nullable=False),
        sa.Column("valor_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("calculo", sa.String(200), nullable=False),
        sa.CheckConstraint("escolha IN ('consultor','regra','padrao')", name="ck_orcamento_item_escolha"),
        sa.CheckConstraint("quantidade > 0 AND total >= 0", name="ck_orcamento_item_valores"),
    )
    _indices("orcamento_item", ["tenant_id", "orcamento_id", "rota_passo_id", "metodo_id"])

    op.create_table(
        "orcamento_escolha",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("process_id", sa.Integer, sa.ForeignKey("processes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rota_passo_id", sa.Integer, sa.ForeignKey("rota_passos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metodo_codigo", sa.String(60)),
        sa.Column("quantidade", sa.Numeric(10, 2)),
        sa.Column("autor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "rota_passo_id", name="uq_orcamento_escolha_passo"),
        sa.CheckConstraint("quantidade IS NULL OR quantidade > 0", name="ck_orcamento_escolha_quantidade"),
    )
    _indices("orcamento_escolha", ["tenant_id", "process_id", "rota_passo_id", "autor_id"])

    op.add_column("proposals", sa.Column("orcamento_id", sa.Integer,
                                         sa.ForeignKey("orcamento.id", ondelete="SET NULL")))
    op.create_index("ix_proposals_orcamento_id", "proposals", ["orcamento_id"])


def downgrade():
    op.drop_index("ix_proposals_orcamento_id", table_name="proposals")
    op.drop_column("proposals", "orcamento_id")
    for tabela in ("orcamento_escolha", "orcamento_item", "orcamento", "redacao_comercial", "orcamento_metodo"):
        op.drop_table(tabela)
    op.drop_column("rota_passos", "remocao_motivo")
