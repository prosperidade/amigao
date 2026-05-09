"""Smoke E2E real do DiagnosticoAgent — Sprint A2-diagnostico-C2.

Roda 2 cenários (AI on rich context + AI off rules-based) com mock pesado
de ``_load_process_data`` (Q5 da Fase 0 — preserva isolamento de DB) e gera
relatório markdown em ``docs/sprints/sprint_a2_diagnostico_smoke.md``.

Pré-requisitos:
- ``OPENAI_API_KEY`` populada em settings.
- Rodar dentro do api container::

    docker compose exec api python scripts/smoke_a2_diagnostico.py

Para mudar o modelo, edite ``MODEL_OVERRIDE`` abaixo.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s: %(message)s")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.base import AgentContext  # noqa: E402
from app.agents.diagnostico import DiagnosticoAgent  # noqa: E402

MODEL_OVERRIDE = "gpt-4o-mini"  # Q6 da Fase 0 — comparabilidade cross-sprint
COST_BUDGET_USD = 0.10

REPORT_PATH = ROOT / "docs" / "sprints" / "sprint_a2_diagnostico_smoke.md"


# ---------------------------------------------------------------------------
# Cenários — mock pesado de _load_process_data + chain_data realista
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "ai_on_rich_context": {
        "ai_on": True,
        "process_data": {
            "process": {
                "id": 42,
                "title": "Regularização ambiental Fazenda Boa Vista",
                "process_type": "regularizacao_fundiaria",
                "status": "diagnostico",
                "demand_type": "regularizacao_fundiaria",
                "initial_diagnosis": "Imóvel com pendências múltiplas",
                "destination_agency": "SEMAD-GO",
                "risk_score": None,
            },
            "property": {
                "name": "Fazenda Boa Vista",
                "municipality": "Niquelândia",
                "state": "GO",
                "total_area_ha": 482.3,
                "biome": "Cerrado",
                "car_code": "GO-1234567",
                "car_status": "pendente",
                "has_embargo": True,
            },
            "documents": [
                {"id": 1, "document_type": "matricula", "ocr_status": "done", "review_required": False},
                {"id": 2, "document_type": "car", "ocr_status": "done", "review_required": False},
                {"id": 3, "document_type": "ccir", "ocr_status": "done", "review_required": False},
                {"id": 4, "document_type": "auto_infracao", "ocr_status": "done", "review_required": True},
            ],
        },
        "chain_data": {
            "extrator": {
                "extracted_fields": {
                    "area_hectares": "482,3",
                    "matricula_numero": "12345",
                    "auto_infracao_numero": "IBAMA-2025-0123",
                },
            },
            "legislacao": {
                "legislacao_aplicavel": [
                    "Lei 12.651/2012",
                    "Lei 9.605/1998",
                    "Decreto 7.830/2012",
                ],
            },
        },
    },
    "ai_off_rules_based": {
        "ai_on": False,
        "process_data": {
            "process": {"id": 43, "title": "Caso fallback", "demand_type": "car"},
            "property": {
                "name": "Sítio Esperança",
                "state": "GO",
                "biome": "Cerrado",
                "car_code": None,  # disparar passivo "CAR não cadastrado"
                "has_embargo": False,
            },
            "documents": [],
        },
        "chain_data": {},
    },
}


def _ctx(*, chain_data: dict[str, Any]) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=1,
        process_id=42,
        session=MagicMock(),
        metadata={},
        chain_data=chain_data,
    )


def _enter_smoke_patches(stack: ExitStack, *, process_data: dict[str, Any], ai_on: bool):
    """Mesma família de patches do A2-redator-C2 + adições para diagnostico:
    - _load_process_data (Q5: mock pesado, preserva isolamento de DB).
    - recall_memory retorna {} (MagicMock truthy bug).
    - settings.ai_configured = False quando ai_on=False (path A.2).
    """
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch.object(DiagnosticoAgent, "_create_running_job", return_value=None))
    stack.enter_context(patch.object(DiagnosticoAgent, "_mempalace_log"))
    stack.enter_context(patch.object(DiagnosticoAgent, "_mempalace_log_failure"))
    stack.enter_context(patch("app.agents.events.emit_agent_event"))
    stack.enter_context(patch("app.core.metrics.record_agent_execution"))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))
    stack.enter_context(patch.object(
        DiagnosticoAgent, "_load_process_data", return_value=process_data,
    ))
    stack.enter_context(patch.object(DiagnosticoAgent, "recall_memory", return_value={}))
    if not ai_on:
        mock_settings = MagicMock()
        mock_settings.ai_configured = False
        stack.enter_context(patch("app.core.config.settings", mock_settings))


def _git_short_sha() -> str:
    env_sha = os.environ.get("SMOKE_COMMIT_SHA", "").strip()
    if env_sha:
        return env_sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True,
        ).strip()
    except Exception:
        return "unknown"


def _run_scenario(name: str, scenario: dict[str, Any]) -> dict[str, Any]:
    agent = DiagnosticoAgent(_ctx(chain_data=scenario["chain_data"]))
    ai_on = scenario["ai_on"]

    with ExitStack() as stack:
        _enter_smoke_patches(stack, process_data=scenario["process_data"], ai_on=ai_on)

        if ai_on:
            # Forçar gpt-4o-mini explicitamente
            original_call = DiagnosticoAgent.call_llm

            def _call_with_model(self, prompt: str, *, system: str = "", **kw: Any):
                kw.setdefault("model", MODEL_OVERRIDE)
                return original_call(self, prompt, system=system, **kw)

            stack.enter_context(patch.object(DiagnosticoAgent, "call_llm", _call_with_model))

        result = agent.run()

    llm_response = agent._llm_response  # None no path rules-based
    payload = result.data if result.success else {}

    return {
        "scenario": name,
        "ai_on": ai_on,
        "success": result.success,
        "error": result.error,
        "requires_review": result.requires_review,
        "model_used": llm_response.model_used if llm_response else None,
        "tokens_in": llm_response.tokens_in if llm_response else 0,
        "tokens_out": llm_response.tokens_out if llm_response else 0,
        "cost_usd": llm_response.cost_usd if llm_response else 0.0,
        "duration_ms": llm_response.duration_ms if llm_response else 0,
        # Campos do schema novo
        "content_preview": (payload.get("content") or "")[:200].replace("\n", " ⏎ "),
        "hipoteses": payload.get("hipoteses", []),
        "lacunas": payload.get("lacunas", []),
        "checklist_documental": payload.get("checklist_documental", []),
        "riscos": payload.get("riscos", []),
        "sources_count": len(payload.get("sources", []) or []),
        "sources_summary": [
            {"type": s.get("type"), "ref": s.get("ref")} for s in payload.get("sources", []) or []
        ],
        "metadata": payload.get("metadata", {}),
        # Dual-emit (chaves antigas)
        "dual_emit_present": all(
            k in payload for k in [
                "situacao_geral", "passivos_identificados", "acoes_remediacao",
                "prioridade_acoes", "risco_estimado", "observacoes",
            ]
        ),
        "risco_estimado_dual": payload.get("risco_estimado"),
    }


def _format_report(rows: list[dict[str, Any]], total_cost: float) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    sha = _git_short_sha()
    lines: list[str] = []

    lines.append("# Sprint A2-diagnostico C2 — Smoke E2E real")
    lines.append("")
    lines.append(f"**Timestamp:** {timestamp}")
    lines.append(f"**Commit:** `{sha}`")
    lines.append(f"**Provider/modelo:** `{MODEL_OVERRIDE}` (gpt-4o-mini via litellm/OpenAI)")
    lines.append(f"**Cenários executados:** {len(rows)}")
    lines.append(f"**Custo total:** **${total_cost:.4f}**")
    lines.append("")
    lines.append(
        "**Estratégia:** mock pesado de `DiagnosticoAgent._load_process_data` "
        "(Q5 da Fase 0) — preserva isolamento de DB. Cenários cobrem path A.1 "
        "(IA com gpt-4o-mini real) e A.2 (rules-based sem IA — custo zero)."
    )
    lines.append("")

    lines.append("## Tabela consolidada")
    lines.append("")
    lines.append("| Cenário | AI on | OK? | review | model | tokens (in/out) | cost USD | sources | hipóteses | risco | dual-emit |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        ok = "✅" if r["success"] else "❌"
        review = "True" if r["requires_review"] else "False"
        lines.append(
            f"| `{r['scenario']}` | {r['ai_on']} | {ok} | {review} | "
            f"`{r['model_used'] or '—'}` | {r['tokens_in']}/{r['tokens_out']} | "
            f"${r['cost_usd']:.4f} | {r['sources_count']} | "
            f"{len(r['hipoteses'])} | {r['risco_estimado_dual'] or '—'} | "
            f"{'✅' if r['dual_emit_present'] else '❌'} |"
        )
    lines.append("")

    lines.append("## Observações por cenário")
    lines.append("")
    for r in rows:
        lines.append(f"### `{r['scenario']}`")
        lines.append("")
        if not r["success"]:
            lines.append(f"❌ **Falhou:** {r['error']}")
            lines.append("")
            continue
        lines.append(f"- **AI on:** {r['ai_on']}")
        lines.append(f"- **`requires_review`:** {r['requires_review']}")
        lines.append(f"- **Sources** ({r['sources_count']}): " + ", ".join(
            f"`{s['type']}/{s['ref']}`" for s in r["sources_summary"]
        ))
        lines.append(f"- **Hipóteses** ({len(r['hipoteses'])}):")
        for h in r["hipoteses"]:
            lines.append(f"    - {h}")
        lines.append(f"- **Lacunas** ({len(r['lacunas'])}): "
                     + (", ".join(r["lacunas"]) if r["lacunas"] else "_(vazio em V1, schema-only)_"))
        lines.append(f"- **Checklist** ({len(r['checklist_documental'])}):")
        for c in r["checklist_documental"]:
            lines.append(f"    - {c}")
        lines.append(f"- **Riscos** ({len(r['riscos'])}):")
        for risco in r["riscos"]:
            sev = risco.get("severidade")
            desc = (risco.get("descricao") or "")[:120]
            lines.append(f"    - severidade=`{sev}` — {desc}")
        if r["metadata"]:
            lines.append(f"- **Metadata:** {json.dumps(r['metadata'], ensure_ascii=False)}")
        lines.append(f"- **Latência:** {r['duration_ms']}ms")
        lines.append(f"- **Custo:** ${r['cost_usd']:.4f}")
        lines.append("")
        if r["content_preview"]:
            lines.append("**Preview do `content`** (primeiros 200 chars):")
            lines.append("")
            lines.append(f"> {r['content_preview']}")
            lines.append("")

    review_true = sum(1 for r in rows if r["requires_review"])
    lines.append("## Calibração `requires_review`")
    lines.append("")
    lines.append(f"**{review_true}/{len(rows)} cenários** retornaram `requires_review=True`.")
    lines.append("")
    if review_true == len(rows):
        lines.append(
            "**Por design.** O `DiagnosticoAgent` retorna `requires_review=True` "
            "**hardcoded** em ambos os paths (linha equivalente do `_build_payload`) — "
            "diagnóstico ambiental sempre precisa de validação humana antes de "
            "alimentar peças do redator. Mesma decisão arquitetural do redator (A2-redator-C2)."
        )
    lines.append("")

    dual_ok = sum(1 for r in rows if r["dual_emit_present"])
    lines.append("## Dual-emit (γ)")
    lines.append("")
    lines.append(
        f"**{dual_ok}/{len(rows)} cenários** preservam todas as 6 chaves antigas "
        f"no payload (`situacao_geral`, `passivos_identificados`, "
        f"`acoes_remediacao`, `prioridade_acoes`, `risco_estimado`, "
        f"`observacoes`). Confirma que a estratégia γ está em pé — frontend "
        f"`DiagnósticoResult` não quebra com AIJobs novos, e AIJobs históricos "
        f"continuam renderizando."
    )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**Nota:** smoke produzido via `scripts/smoke_a2_diagnostico.py` (Sprint A2-diagnostico-C2).")
    return "\n".join(lines)


def main() -> int:
    print(f"Smoke A2-diagnostico-C2 — modelo: {MODEL_OVERRIDE}")
    print(f"Budget: ${COST_BUDGET_USD:.2f}")
    print(f"Cenários: {', '.join(SCENARIOS.keys())}")
    print()

    rows: list[dict[str, Any]] = []
    total_cost = 0.0

    for name, scenario in SCENARIOS.items():
        print(f"→ {name} (ai_on={scenario['ai_on']}) ...", end="", flush=True)
        try:
            row = _run_scenario(name, scenario)
        except Exception as exc:
            print(f" 💥 {exc}")
            row = {
                "scenario": name, "ai_on": scenario["ai_on"], "success": False,
                "error": str(exc), "requires_review": False, "model_used": None,
                "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "duration_ms": 0,
                "content_preview": "", "hipoteses": [], "lacunas": [],
                "checklist_documental": [], "riscos": [], "sources_count": 0,
                "sources_summary": [], "metadata": {}, "dual_emit_present": False,
                "risco_estimado_dual": None,
            }
        rows.append(row)
        total_cost += row["cost_usd"]
        cost_str = f"${row['cost_usd']:.4f}" if row["cost_usd"] else "—"
        ok_str = "✅" if row["success"] else "❌"
        print(f" {ok_str} cost={cost_str} review={row['requires_review']} (acum=${total_cost:.4f})")

        if total_cost > COST_BUDGET_USD:
            print(f"⚠ budget de ${COST_BUDGET_USD:.2f} estourado. Abortando.")
            break

    report = _format_report(rows, total_cost)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print()
    print(f"✓ Relatório salvo em {REPORT_PATH.relative_to(ROOT)}")
    print(f"✓ Custo total: ${total_cost:.4f}")
    return 0 if all(r["success"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
