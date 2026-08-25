"""ADR-062 — catálogo: código INCRA/SNCR divergente entre fontes.

Revision ID: e4f6a8c2b1d9
Revises: d3b8a1f0c94e
Create Date: 2026-08-25

Fonte única registral na consolidação (E2): CCIR/SIGEF/ITR/CAR deixam de
escrever campo de `target_entity=matricula` (área, denominação, titular,
INCRA/SNCR, NIRF, RL averbada, geo_certificação) — só a certidão de matrícula
escreve. A divergência delas em relação à matrícula deixa de virar `Acao`
pela consolidação (`generate_acoes_from_divergencias`) e passa a nascer da
matriz de inconsistências (`auditor_imovel` → Diagnóstico), redirecionada
para `RegulatoryIssue` (fato perene do imóvel, ADR-012).

A matriz já comparava código INCRA/SNCR entre fontes (`inconsistency_matrix.
build_matrix`, item `codigo_incra_sncr`) — só informativo até aqui. Faltava o
`codigo_alerta` no catálogo evolutivo (`regulatory_issue_catalog`) para o
achado poder ser persistido. `IDENT_NOME_IMOVEL_DIVERGENTE` (denominação) já
existia no seed original (PROMPT_5 Onda A) sem emissor — este PR liga os dois
códigos (`app/agents/auditor_imovel.py`); só o de INCRA/SNCR é novo aqui.

**INSERT idempotente** — catálogo evolutivo, sem mexer em schema nem nas
linhas existentes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.models.types import PortableJSON

revision = "e4f6a8c2b1d9"
down_revision = "d3b8a1f0c94e"
branch_labels = None
depends_on = None

_CODIGO_ALERTA = "IDENT_CODIGO_INCRA_SNCR_DIVERGENTE"


def upgrade() -> None:
    bind = op.get_bind()
    ja_existe = bind.execute(
        sa.text("SELECT 1 FROM regulatory_issue_catalog WHERE codigo_alerta = :c"),
        {"c": _CODIGO_ALERTA},
    ).first()
    if ja_existe:
        return

    catalog_table = sa.table(
        "regulatory_issue_catalog",
        sa.column("codigo_alerta", sa.String),
        sa.column("familia", sa.String),
        sa.column("descricao_curta", sa.String),
        sa.column("factibilidade", sa.String),
        sa.column("severity_base", sa.String),
        sa.column("muda_rota_regulatoria", sa.Boolean),
        sa.column("muda_escopo_preco_prazo", sa.Boolean),
        sa.column("documentos_cruzados_default", PortableJSON),
    )
    op.bulk_insert(catalog_table, [{
        "codigo_alerta": _CODIGO_ALERTA,
        "familia": "identificacao",
        "descricao_curta": "Código INCRA/SNCR diverge entre fontes",
        "factibilidade": "documental",
        "severity_base": "atencao",
        "muda_rota_regulatoria": False,
        "muda_escopo_preco_prazo": True,
        "documentos_cruzados_default": ["Matricula", "CCIR"],
    }])


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM regulatory_issue_catalog WHERE codigo_alerta = :c")
        .bindparams(c=_CODIGO_ALERTA)
    )
