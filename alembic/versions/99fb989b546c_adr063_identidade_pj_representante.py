"""ADR-063 — identidade PF/PJ e representante (ENT-001, ENT-002).

Duas mudanças:
  1. Tabela ``client_representatives`` — representante subordinado ao Client PJ.
  2. Índice único FUNCIONAL em ``clients`` por (tenant_id, dígitos do cpf_cnpj),
     parcial (ignora nulos, vazios e excluídos).

O índice é sobre a EXPRESSÃO e não sobre a coluna crua de propósito: a coluna
guarda o documento como o consultor digitou ("29.091.958/0001-17") e a unicidade
é sobre a identidade ("29091958000117"). Índice na coluna crua não impediria o
duplicado da ELODI — mesma pessoa com pontuação diferente passaria.

GUARD DE MIGRAÇÃO: se já existir duplicado no banco, esta migration PARA e lista
os conflitos em vez de aplicar. A spec (ENT-002, observação) veta fusão
automática de registros históricos: "Não executar fusão automática dos registros
históricos sem plano de migração e auditoria". Resolver à mão (ou por plano de
migração próprio) e rodar de novo. Relatório sem aplicar nada:
``python scripts/relatorio_duplicados_documento.py``.

Revision ID: 99fb989b546c
Revises: e4f6a8c2b1d9
"""

import sqlalchemy as sa
from alembic import op

from app.models.types import PortableJSON

revision = "99fb989b546c"
down_revision = "e4f6a8c2b1d9"
branch_labels = None
depends_on = None

IX_NOME = "uq_clients_tenant_documento_normalizado"

# Expressão da identidade: só os dígitos do documento.
_DIGITOS = r"regexp_replace(cpf_cnpj, '[^0-9]', '', 'g')"

SQL_DUPLICADOS = f"""
SELECT tenant_id,
       {_DIGITOS} AS documento,
       count(*)   AS quantos,
       array_agg(id ORDER BY id)        AS ids,
       array_agg(full_name ORDER BY id) AS nomes
  FROM clients
 WHERE cpf_cnpj IS NOT NULL
   AND deleted_at IS NULL
   AND {_DIGITOS} <> ''
 GROUP BY tenant_id, {_DIGITOS}
HAVING count(*) > 1
 ORDER BY tenant_id, documento
"""


def upgrade() -> None:
    op.create_table(
        "client_representatives",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("cpf", sa.String(), nullable=True),
        sa.Column("rg", sa.String(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("papel", sa.String(length=50), nullable=False,
                  server_default="representante_legal"),
        sa.Column("source_document_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("field_sources", PortableJSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_representatives_id", "client_representatives", ["id"])
    op.create_index("ix_client_representatives_tenant_id", "client_representatives", ["tenant_id"])
    op.create_index("ix_client_representatives_client_id", "client_representatives", ["client_id"])
    op.create_index("ix_client_representatives_cpf", "client_representatives", ["cpf"])
    op.create_index("ix_client_representatives_source_document_id",
                    "client_representatives", ["source_document_id"])
    op.create_index("ix_client_repr_tenant_client", "client_representatives",
                    ["tenant_id", "client_id"])

    # ── ENT-002: só depois do relatório de duplicados ───────────────────────
    conn = op.get_bind()
    dups = list(conn.execute(sa.text(SQL_DUPLICADOS)))
    if dups:
        linhas = "\n".join(
            f"  tenant {r.tenant_id} · documento {r.documento} · {r.quantos} cadastros "
            f"· ids {list(r.ids)} · nomes {list(r.nomes)}"
            for r in dups
        )
        raise RuntimeError(
            "ENT-002 NÃO aplicado: já existem cadastros duplicados por CPF/CNPJ "
            f"normalizado neste banco ({len(dups)} grupo(s)).\n{linhas}\n\n"
            "A spec veta fusão automática de registros históricos. Resolva os "
            "conflitos (escolher o cadastro canônico, migrar vínculos, apagar "
            "logicamente o resto) e rode a migration de novo. Para inspecionar "
            "sem aplicar nada: python scripts/relatorio_duplicados_documento.py"
        )

    op.create_index(
        IX_NOME, "clients",
        [sa.text("tenant_id"), sa.text(_DIGITOS)],
        unique=True,
        postgresql_where=sa.text(
            f"cpf_cnpj IS NOT NULL AND deleted_at IS NULL AND {_DIGITOS} <> ''"
        ),
    )


def downgrade() -> None:
    op.drop_index(IX_NOME, table_name="clients")
    op.drop_index("ix_client_repr_tenant_client", table_name="client_representatives")
    op.drop_index("ix_client_representatives_source_document_id",
                  table_name="client_representatives")
    op.drop_index("ix_client_representatives_cpf", table_name="client_representatives")
    op.drop_index("ix_client_representatives_client_id", table_name="client_representatives")
    op.drop_index("ix_client_representatives_tenant_id", table_name="client_representatives")
    op.drop_index("ix_client_representatives_id", table_name="client_representatives")
    op.drop_table("client_representatives")
