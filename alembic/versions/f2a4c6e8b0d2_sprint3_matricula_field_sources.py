"""Sprint 3 (Selo de oficialização) — adiciona Matricula.field_sources (JSONB).

Fecha o ponto cego de proveniência: Client e Property já tinham `field_sources`;
a Matrícula dependia do fallback `old is not None` na consolidação (qualquer
valor não-nulo = "consolidado"). Com a coluna, a consolidação grava proveniência
explícita e o fallback é aposentado.

BACKFILL (Postgres-only): linhas existentes com valor não-nulo nas colunas da
allowlist da consolidação recebem `human_validated` — todo valor de matrícula
hoje só chega por consolidação de staging ACEITO ou por cadastro manual do
consultor, então a marca é fiel. Sem o backfill, a troca do fallback faria um
doc novo divergente SOBRESCREVER valor legado em silêncio (em vez de virar
reconciliação, Ficha 05).

Revision ID: f2a4c6e8b0d2
Revises: d1e2f3a4b5c6
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa

from app.models.types import PortableJSON

revision = "f2a4c6e8b0d2"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

# Espelho de _MATRICULA_FIELDS (staging_consolidation) no momento desta migration.
# Snapshot deliberado (migrations são imutáveis): mudanças futuras na allowlist
# não retroagem sobre este backfill.
_BACKFILL_COLUMNS = (
    "numero_matricula", "cartorio", "registro_livro_folha_ficha",
    "codigo_incra_sncr", "nirf_cib", "area_ha", "denominacao_imovel",
    "geo_certificacao_codigo", "geo_certificacao_status",
    "averbacao_app", "averbacao_rl", "onus_gravames", "proprietarios",
)


def upgrade() -> None:
    op.add_column(
        "matriculas",
        sa.Column("field_sources", PortableJSON, nullable=True),
    )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite (testes): schema vem do metadata; sem dado legado a backfillar.

    pairs = ", ".join(
        f"'{col}', CASE WHEN {col} IS NOT NULL THEN 'human_validated' END"
        for col in _BACKFILL_COLUMNS
    )
    op.execute(
        f"UPDATE matriculas SET field_sources = jsonb_strip_nulls(jsonb_build_object({pairs}))"
    )


def downgrade() -> None:
    op.drop_column("matriculas", "field_sources")
