"""Append-only contra TRUNCATE + índice na FK do trecho (achados do Incremento 4a).

Os gatilhos `<tabela>_imutavel` são `BEFORE UPDATE OR DELETE ... FOR EACH ROW`. `TRUNCATE`
não dispara gatilho de linha: com uma linha de SQL, toda a trilha append-only ia embora —
`validacao_norma` (hash chain do catálogo normativo), evidência, geometria e entrada
semântica. Aqui entra o gatilho de statement que faltava, nas 20 tabelas que já se
declaram imutáveis.

Junto vão os índices que faltavam nas FKs da zona normativa. FK sem índice faz cada
remoção do lado referido varrer a tabela referente inteira: a reconstrução do catálogo em
dev estourou o `statement_timeout` duas vezes (`trecho_normativo.dispositivo_id` e
`dispositivo.parent_id`). A varredura cobre a classe inteira, não só os dois casos.

Não muda dado: só acrescenta gatilho e índice.
"""
import sqlalchemy as sa
from alembic import op

revision = "074zn001"
down_revision = "073zn001"
branch_labels = None
depends_on = None


# Varredura da CLASSE do defeito, não do caso: toda FK das tabelas da zona normativa
# que estava sem índice. A primeira (dispositivo_id) apareceu ao apagar dispositivo;
# a segunda (parent_id), ao apagar o pai. Removê-las uma a uma seria esperar a terceira.
FK_SEM_INDICE = [
    ("trecho_normativo", "dispositivo_id"),
    ("trecho_normativo", "tenant_id"),
    ("dispositivo", "parent_id"),
    ("fonte_normativa", "tenant_id"),
    ("fonte_normativa_versao", "substitui_versao_id"),
    ("interpretacao_norma", "interpretacao_fonte_id"),
    ("papel_curadoria", "concedido_por_id"),
    ("papel_curadoria", "revogado_por_id"),
    ("tarefa_revisao_normativa", "fonte_versao_id"),
    ("tarefa_revisao_normativa", "legislation_document_id"),
    ("tarefa_revisao_normativa", "resolvida_por_id"),
    ("validacao_norma", "validador_id"),
]


def _imutaveis(conn) -> list[str]:
    """As tabelas que já têm gatilho de linha de imutabilidade — a lista vem do banco,
    não de uma cópia que envelhece."""
    return [
        r[0] for r in conn.execute(sa.text(
            "SELECT DISTINCT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE t.tgname LIKE '%_imutavel' AND NOT t.tgisinternal ORDER BY 1"
        ))
    ]


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        """CREATE OR REPLACE FUNCTION public.rejeitar_truncate_evidencia() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN RAISE EXCEPTION 'registro append-only: TRUNCATE recusado em %', TG_TABLE_NAME;
        END $$"""
    ))
    for tabela in _imutaveis(conn):
        conn.execute(sa.text(
            f'CREATE TRIGGER {tabela}_sem_truncate BEFORE TRUNCATE ON {tabela} '  # noqa: S608
            "FOR EACH STATEMENT EXECUTE FUNCTION public.rejeitar_truncate_evidencia()"
        ))
    for tabela, coluna in FK_SEM_INDICE:
        op.create_index(f"ix_{tabela}_{coluna}", tabela, [coluna])


def downgrade():
    conn = op.get_bind()
    for tabela, coluna in FK_SEM_INDICE:
        op.drop_index(f"ix_{tabela}_{coluna}", table_name=tabela)
    for tabela in _imutaveis(conn):
        conn.execute(sa.text(f"DROP TRIGGER IF EXISTS {tabela}_sem_truncate ON {tabela}"))  # noqa: S608
    conn.execute(sa.text("DROP FUNCTION IF EXISTS public.rejeitar_truncate_evidencia()"))
