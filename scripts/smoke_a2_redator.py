"""Smoke E2E real do RedatorAgent — Sprint A2-redator-C2.

Roda 1× cada um dos 7 templates servidos pelo RedatorAgent contra o LLM
real (gpt-4o-mini via litellm/OpenAI), com contexto fake mas realista,
e gera relatório markdown em ``docs/sprints/sprint_a2_redator_smoke.md``.

Pré-requisitos:
- ``OPENAI_API_KEY`` populada em settings.
- Rodar dentro do api container::

    docker compose exec api python scripts/smoke_a2_redator.py

Para mudar o modelo, edite ``MODEL_OVERRIDE`` abaixo.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# logging.basicConfig precisa rodar antes de instanciar loggers do app
logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s: %(message)s")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.base import AgentContext  # noqa: E402
from app.agents.redator import RedatorAgent  # noqa: E402

MODEL_OVERRIDE = "gpt-4o-mini"  # provider explícito — facilita comparação cross-sprint
COST_BUDGET_USD = 0.50          # corta o smoke se acumular acima disso

REPORT_PATH = ROOT / "docs" / "sprints" / "sprint_a2_redator_smoke.md"


# ---------------------------------------------------------------------------
# Cenários — texto realista por template + legal_data quando aplicável
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "prad": {
        "metadata": {"document_template": "prad", "instructions": "Imóvel rural com 12 ha de supressão irregular."},
        "chain_data": {
            "legislacao": {
                "legislacao_aplicavel": ["Lei 12.651/2012", "Decreto 7.830/2012", "Lei 9.605/1998"],
            },
            "diagnostico": {"property": {"state": "GO", "biome": "Cerrado"}},
        },
    },
    "memorial": {
        "metadata": {
            "document_template": "memorial",
            "instructions": "Memorial descritivo do imóvel para SICAR.",
            "property_data": {"name": "Fazenda Boa Vista", "total_area_ha": 482.3, "state": "GO"},
        },
        "chain_data": {
            "legislacao": {"legislacao_aplicavel": ["Lei 12.651/2012"]},
        },
    },
    "oficio": {
        "metadata": {
            "document_template": "oficio",
            "addressee": "SEMAD-GO",
            "instructions": "Resposta a notificação sobre regularidade do CAR.",
            "client_data": {"full_name": "Fazenda Teste LTDA"},
        },
        "chain_data": {
            "legislacao": {
                "legislacao_aplicavel": ["Lei 12.651/2012"],
                "normas_estaduais": ["Lei Estadual 18.102/2013"],
            },
        },
    },
    "proposta": {
        "metadata": {
            "document_template": "proposta",
            "instructions": "Consultoria para regularização ambiental completa, valor R$ 18.500.",
            "client_data": {"full_name": "Fazenda Sol Nascente LTDA"},
            "property_data": {"name": "Sol Nascente", "total_area_ha": 200.0},
        },
        "chain_data": {},
    },
    "resposta_notificacao": {
        "metadata": {
            "document_template": "resposta_notificacao",
            "addressee": "SEMAD-GO",
            "prazo_dias": 30,
            "ato_regulatorio": "Notificação SEMAD nº 0123/2026",
            "instructions": "Resposta argumentando regularidade junto ao SICAR.",
        },
        "chain_data": {
            "legislacao": {
                "legislacao_aplicavel": ["Lei 12.651/2012", "Decreto 7.830/2012", "Lei 9.605/1998"],
            },
        },
    },
    "contrato": {
        "metadata": {
            "document_template": "contrato",
            "instructions": "Contrato de prestação de serviços de consultoria ambiental.",
            "client_data": {"full_name": "Fazenda Águas Claras LTDA", "cpf_cnpj": "12.345.678/0001-90"},
        },
        "chain_data": {},
    },
    "comunicacao": {
        "metadata": {
            "document_template": "comunicacao",
            "addressee": "Cliente Final",
            "instructions": "Comunicar ao cliente que o protocolo do CAR foi efetuado.",
        },
        "chain_data": {},
    },
}


def _ctx(**kwargs: Any) -> AgentContext:
    return AgentContext(
        tenant_id=1,
        user_id=None,
        process_id=None,
        session=MagicMock(),
        metadata=kwargs.get("metadata", {}),
        chain_data=kwargs.get("chain_data", {}),
    )


def _enter_smoke_patches(stack: ExitStack):
    """Patches para bypassar cost checks e persistência de DB durante o smoke.

    NB1: ``emit_agent_event`` e ``record_agent_execution`` são imports tardios
    em ``BaseAgent.run()`` — patcheamos no módulo de origem para o lazy import
    pegar o mock.

    NB2: ``get_active_prompt`` precisa retornar ``None`` para forçar o agente
    a usar ``_fallback_prompts`` (hardcoded). Caso contrário o ``MagicMock(session)``
    faz ``get_active_prompt`` retornar um MagicMock truthy e o prompt vira
    placeholder sem sentido — diagnosticado durante o smoke C2 inicial
    (commit dessa sprint).
    """
    stack.enter_context(patch("app.agents.base.check_tenant_cost_limit"))
    stack.enter_context(patch("app.agents.base.check_tenant_monthly_budget"))
    stack.enter_context(patch.object(RedatorAgent, "_create_running_job", return_value=None))
    stack.enter_context(patch("app.agents.events.emit_agent_event"))
    stack.enter_context(patch("app.core.metrics.record_agent_execution"))
    stack.enter_context(patch("app.agents.base.get_active_prompt", return_value=None))


def _git_short_sha() -> str:
    """SHA curto. Aceita SMOKE_COMMIT_SHA via env (caller no host pode passar
    quando o container não tem ``.git`` montado)."""
    import os
    env_sha = os.environ.get("SMOKE_COMMIT_SHA", "").strip()
    if env_sha:
        return env_sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _run_template(template: str, scenario: dict[str, Any]) -> dict[str, Any]:
    """Executa 1 template com LLM real e retorna sumário."""
    agent = RedatorAgent(_ctx(**scenario))

    with ExitStack() as stack:
        _enter_smoke_patches(stack)
        # NÃO mockamos complete — esse é o ponto do smoke real.
        # Para forçar gpt-4o-mini explicitamente, patcheamos call_llm passando model.
        original_call = RedatorAgent.call_llm

        def _call_with_model(self, prompt: str, *, system: str = "", **kw: Any):
            kw.setdefault("model", MODEL_OVERRIDE)
            return original_call(self, prompt, system=system, **kw)

        stack.enter_context(patch.object(RedatorAgent, "call_llm", _call_with_model))

        result = agent.run()

    llm_response = agent._llm_response
    payload = result.data if result.success else {}

    summary = {
        "template": template,
        "success": result.success,
        "error": result.error,
        "requires_review": result.requires_review,
        "model_used": llm_response.model_used if llm_response else None,
        "provider": llm_response.provider if llm_response else None,
        "tokens_in": llm_response.tokens_in if llm_response else 0,
        "tokens_out": llm_response.tokens_out if llm_response else 0,
        "cost_usd": llm_response.cost_usd if llm_response else 0.0,
        "duration_ms": llm_response.duration_ms if llm_response else 0,
        "schema_template": payload.get("template"),
        "document_type_alias": payload.get("document_type"),
        "addressee": payload.get("addressee"),
        "sources_count": len(payload.get("sources", []) or []),
        "legal_citations_count": len(payload.get("legal_citations", []) or []),
        "citation_total": payload.get("citation_total"),
        "citation_valid": payload.get("citation_valid"),
        "citation_coverage_ratio": payload.get("citation_coverage_ratio"),
        "has_prazo_dias": "prazo_dias" in payload,
        "has_ato_regulatorio": "ato_regulatorio" in payload,
        "content_preview": (payload.get("content") or "")[:200].replace("\n", " ⏎ "),
    }
    return summary


def _format_report(rows: list[dict[str, Any]], total_cost: float) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    sha = _git_short_sha()
    lines: list[str] = []

    lines.append("# Sprint A2-redator C2 — Smoke E2E real")
    lines.append("")
    lines.append(f"**Timestamp:** {timestamp}")
    lines.append(f"**Commit:** `{sha}`")
    lines.append(f"**Provider/modelo:** `{MODEL_OVERRIDE}` (gpt-4o-mini via litellm/OpenAI)")
    lines.append(f"**Templates executados:** {len(rows)}")
    lines.append(f"**Custo total:** **${total_cost:.4f}**")
    lines.append("")

    lines.append("## Tabela consolidada")
    lines.append("")
    lines.append("| Template | OK? | review | model_used | tokens (in/out) | cost USD | citations (total/valid) | sources | addressee | prazo+ato? |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        ok = "✅" if r["success"] else "❌"
        review = "True" if r["requires_review"] else "False"
        cit = (
            f"{r['citation_total']}/{r['citation_valid']}"
            if r["citation_total"] is not None
            else "—"
        )
        prazo_ato = (
            "✅"
            if r["has_prazo_dias"] and r["has_ato_regulatorio"]
            else ("⚠️ fallback" if r["template"] == "resposta_notificacao" else "n/a")
        )
        lines.append(
            f"| `{r['template']}` | {ok} | {review} | `{r['model_used'] or '—'}` | "
            f"{r['tokens_in']}/{r['tokens_out']} | ${r['cost_usd']:.4f} | "
            f"{cit} | {r['sources_count']} | {r['addressee'] or '—'} | {prazo_ato} |"
        )
    lines.append("")

    lines.append("## Observações por template")
    lines.append("")
    for r in rows:
        lines.append(f"### `{r['template']}`")
        lines.append("")
        if not r["success"]:
            lines.append(f"❌ **Falhou:** {r['error']}")
            lines.append("")
            continue
        lines.append(f"- **`requires_review`:** {r['requires_review']}")
        lines.append(f"- **Schema:** `template={r['schema_template']}`, `document_type={r['document_type_alias']}` (alias preservado).")
        lines.append(f"- **Sources:** {r['sources_count']}")
        lines.append(f"- **Legal citations:** {r['legal_citations_count']}")
        if r["citation_total"] is not None:
            cov = r["citation_coverage_ratio"]
            lines.append(
                f"- **Citations evaluator:** total={r['citation_total']}, "
                f"valid={r['citation_valid']}, coverage={cov:.0%}" if cov is not None
                else f"- **Citations evaluator:** total={r['citation_total']}, valid={r['citation_valid']}"
            )
        else:
            lines.append("- **Citations evaluator:** skip (sem legal_data ou sem citação no texto).")
        if r["template"] == "resposta_notificacao":
            if r["has_prazo_dias"] and r["has_ato_regulatorio"]:
                lines.append("- **Subclass enriched:** ✅ `RespostaNotificacaoContent` (prazo_dias + ato_regulatorio populados).")
            else:
                lines.append("- **Subclass enriched:** ⚠️ fallback para `PecaJuridicaContent` puro (Q3 da Fase 0).")
        lines.append(f"- **Latência:** {r['duration_ms']}ms")
        lines.append(f"- **Custo:** ${r['cost_usd']:.4f}")
        lines.append("")
        lines.append("**Preview do `content`** (primeiros 200 chars):")
        lines.append("")
        lines.append(f"> {r['content_preview']}")
        lines.append("")

    # Análise calibração requires_review
    review_true = sum(1 for r in rows if r["requires_review"])
    lines.append("## Calibração `requires_review`")
    lines.append("")
    lines.append(f"**{review_true}/{len(rows)} templates** retornaram `requires_review=True`.")
    lines.append("")
    if review_true == len(rows):
        lines.append(
            "**Por design.** O `RedatorAgent` retorna `requires_review=True` "
            "**hardcoded** em todos os templates (`app/agents/redator.py` no "
            "merge final do `execute()`) — peças formais sempre precisam de "
            "revisão humana antes de virar peça oficial. Não é o "
            "`citation_evaluator` forçando: tendo ou não citação inválida, "
            "o flag é `True`. O evaluator só acrescenta `citation_issues` + "
            "`citation_valid=False` no payload quando aplicável (e o frontend "
            "renderiza badge adicional 'Citações suspeitas')."
        )
    else:
        lines.append(
            "Atenção: nem todos os templates marcaram review obrigatória. "
            "Esperado em peças formais. Investigar."
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**Nota:** smoke produzido via `scripts/smoke_a2_redator.py` (Sprint A2-redator-C2).")
    return "\n".join(lines)


def main() -> int:
    print(f"Smoke A2-redator-C2 — modelo: {MODEL_OVERRIDE}")
    print(f"Budget: ${COST_BUDGET_USD:.2f}")
    print(f"Templates: {', '.join(SCENARIOS.keys())}")
    print()

    rows: list[dict[str, Any]] = []
    total_cost = 0.0

    for template, scenario in SCENARIOS.items():
        print(f"→ {template} ...", end="", flush=True)
        try:
            summary = _run_template(template, scenario)
        except Exception as exc:
            print(f" 💥 {exc}")
            summary = {
                "template": template, "success": False, "error": str(exc),
                "requires_review": False, "model_used": None, "provider": None,
                "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "duration_ms": 0,
                "schema_template": None, "document_type_alias": None, "addressee": None,
                "sources_count": 0, "legal_citations_count": 0,
                "citation_total": None, "citation_valid": None, "citation_coverage_ratio": None,
                "has_prazo_dias": False, "has_ato_regulatorio": False, "content_preview": "",
            }
        rows.append(summary)
        total_cost += summary["cost_usd"]
        cost_str = f"${summary['cost_usd']:.4f}" if summary["cost_usd"] else "—"
        ok_str = "✅" if summary["success"] else "❌"
        print(f" {ok_str} cost={cost_str} review={summary['requires_review']} (acumulado=${total_cost:.4f})")

        if total_cost > COST_BUDGET_USD:
            print(f"⚠ budget de ${COST_BUDGET_USD:.2f} estourado. Abortando.")
            break

    report = _format_report(rows, total_cost)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print()
    print(f"✓ Relatório salvo em {REPORT_PATH.relative_to(ROOT)}")
    print(f"✓ Custo total: ${total_cost:.4f}")

    # JSON inline (útil pra inspeção rápida)
    print()
    print("Resumo JSON (preview):")
    print(json.dumps([{k: v for k, v in r.items() if k != "content_preview"} for r in rows], indent=2))

    return 0 if all(r["success"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
