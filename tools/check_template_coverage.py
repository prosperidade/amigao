"""Verifica cobertura de WorkflowTemplate e LegislationDocument por DemandType.

Gera markdown em docs/arquivo/auditorias/2026-05-28_cobertura_templates.md.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import JSONB

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.models.legislation import LegislationDocument
from app.models.process import DemandType
from app.models.workflow_template import WorkflowTemplate


DEFAULT_OUTPUT = Path("docs/arquivo/auditorias/2026-05-28_cobertura_templates.md")


def _collect_rows() -> list[dict[str, object]]:
    with SessionLocal() as db:
        rows: list[dict[str, object]] = []
        for demand_type in DemandType:
            value = demand_type.value
            has_template = (
                db.query(WorkflowTemplate.id)
                .filter(
                    WorkflowTemplate.demand_type == value,
                    WorkflowTemplate.is_active.is_(True),
                )
                .first()
                is not None
            )
            legislation_count = (
                db.query(func.count(LegislationDocument.id))
                .filter(
                    cast(LegislationDocument.demand_types, JSONB).contains([value])
                )
                .scalar()
                or 0
            )
            rows.append(
                {
                    "demand_type": value,
                    "has_template": has_template,
                    "legislation_count": int(legislation_count),
                }
            )
        return rows


def _render_markdown(rows: list[dict[str, object]]) -> str:
    gaps_template = [str(r["demand_type"]) for r in rows if not r["has_template"]]
    gaps_legislation = [
        str(r["demand_type"]) for r in rows if int(r["legislation_count"]) == 0
    ]
    lines = [
        "# Cobertura de templates e base regulatória por DemandType",
        "",
        f"Gerado em: {datetime.now(UTC).isoformat(timespec='seconds')}",
        "",
        "Fonte: `tools/check_template_coverage.py`.",
        "",
        "| demand_type | WorkflowTemplate ativo? | LegislationDocument com demand_type? |",
        "|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {demand_type} | {template} | {docs} |".format(
                demand_type=row["demand_type"],
                template="sim" if row["has_template"] else "não",
                docs=row["legislation_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Gaps",
            "",
            "- Sem WorkflowTemplate ativo: "
            + (", ".join(gaps_template) if gaps_template else "nenhum"),
            "- Sem LegislationDocument especializado: "
            + (", ".join(gaps_legislation) if gaps_legislation else "nenhum"),
            "",
            "Observação: este relatório não cria templates; apenas evidencia cobertura.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = _collect_rows()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_render_markdown(rows), encoding="utf-8")
    print(f"Relatório gerado em {args.output}")


if __name__ == "__main__":
    main()
