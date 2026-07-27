"""Materializa o `RegulatoryDiagnosis` a partir da saída do agente de diagnóstico.

**Por que existe** (caso 15, 26/07): o gate E2→E3 exige
`RegulatoryDiagnosis.validated_at` (Princípio 1 — "a IA propõe; o humano decide e
assina"). Mas nada no fluxo criava esse registro: a saída do agente vivia só em
`AIJob.result`, e o bloco de assinatura da UI (`DiagnosisAssinatura`) renderiza
`null` quando não há diagnóstico. Resultado medido no processo 15: gate cobrando
uma assinatura que **não tinha onde ser dada** — 0 linhas em `regulatory_diagnoses`
com 2 jobs de diagnóstico concluídos.

Este módulo é a ponte: pega o `AIJob.result` do agente `diagnostico` e monta um
`content` que passa no gate Pydantic (`DiagnosticoPreliminarContent`) do
`POST /diagnoses`. Não inventa nada — só mapeia o que o agente já emitiu, nas duas
formas que circulam (dual-emit):

* chaves NOVAS: ``content``, ``hipoteses``, ``lacunas``, ``riscos``,
  ``checklist_documental``, ``divergencias``, ``afirmacoes``, ``sources``;
* chaves ANTIGAS: ``situacao_geral``, ``passivos_identificados``,
  ``acoes_remediacao`` — jobs anteriores à Sprint A2.

O schema é ``extra="forbid"``: copiar o result inteiro estouraria. Por isso o
mapeamento é uma ALLOWLIST explícita — campo novo no agente exige entrada aqui,
de propósito (o gate é a barreira contra drift silencioso).
"""

from __future__ import annotations

from typing import Any

__all__ = ["build_content_from_job_result", "DiagnosisMaterializationError"]


class DiagnosisMaterializationError(ValueError):
    """A saída do agente não tem o mínimo para virar um diagnóstico assinável."""


# Campos escalares/listas copiados como vêm quando presentes e não-vazios.
_PASSTHROUGH_LIST_FIELDS = (
    "hipoteses",
    "lacunas",
    "checklist_documental",
    "recomendacoes_externas",
)
_PASSTHROUGH_OBJ_LIST_FIELDS = ("riscos", "divergencias", "afirmacoes")
_PASSTHROUGH_SCALAR_FIELDS = (
    "nivel_risco_geral",
    "nivel_confianca_diagnostico",
    "etapa_funil_sugerida",
)


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _first_text(result: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def build_content_from_job_result(
    result: dict[str, Any], *, ai_job_id: int | None = None
) -> dict[str, Any]:
    """Converte ``AIJob.result`` do agente ``diagnostico`` em ``content`` válido.

    Levanta ``DiagnosisMaterializationError`` quando não há texto de situação —
    sem isso o `content` do `StageOutputContent` seria vazio e o gate Pydantic
    rejeitaria com uma mensagem que não ajuda a consultora. Falhar aqui, com
    causa nomeada, é melhor que devolver 422 genérico.
    """
    if not isinstance(result, dict) or not result:
        raise DiagnosisMaterializationError(
            "A análise do diagnóstico não produziu resultado — rode o agente novamente."
        )

    texto = _first_text(result, "content", "situacao_geral")
    if not texto:
        raise DiagnosisMaterializationError(
            "A análise do diagnóstico não tem texto de situação geral — "
            "rode o agente novamente antes de validar."
        )

    content: dict[str, Any] = {"content": texto}

    # `sources` é obrigatório e não pode ser vazio (StageOutputContent). Quando o
    # job não trouxe fonte estruturada, a fonte HONESTA é o próprio job — não
    # inventamos documento nem norma.
    sources = [s for s in _as_list(result.get("sources")) if isinstance(s, dict)]
    if not sources:
        sources = [
            {
                "type": "manual",
                "ref": f"ai_job:{ai_job_id}" if ai_job_id else "ai_job",
                "excerpt": "diagnóstico produzido pelo agente; fontes por afirmação",
            }
        ]
    content["sources"] = sources

    confidence = result.get("confidence")
    if isinstance(confidence, (int, float)) and 0.0 <= float(confidence) <= 1.0:
        content["confidence"] = float(confidence)

    metadata = result.get("metadata")
    content["metadata"] = dict(metadata) if isinstance(metadata, dict) else {}
    if ai_job_id is not None:
        # Rastreabilidade: de qual execução do agente esta versão nasceu.
        content["metadata"]["ai_job_id"] = ai_job_id

    for field in _PASSTHROUGH_LIST_FIELDS:
        valores = [v for v in _as_list(result.get(field)) if isinstance(v, str) and v.strip()]
        if valores:
            content[field] = valores

    for field in _PASSTHROUGH_OBJ_LIST_FIELDS:
        valores = [v for v in _as_list(result.get(field)) if isinstance(v, dict)]
        if valores:
            content[field] = valores

    for field in _PASSTHROUGH_SCALAR_FIELDS:
        value = result.get(field)
        if isinstance(value, str) and value.strip():
            content[field] = value.strip()

    # Dual-emit legado: jobs antigos só têm `passivos_identificados` /
    # `acoes_remediacao` (list[str]). Viram `hipoteses` / `checklist_documental`
    # apenas quando as chaves novas não vieram — nunca sobrescrevem.
    if "hipoteses" not in content:
        legado = [v for v in _as_list(result.get("passivos_identificados")) if isinstance(v, str)]
        if legado:
            content["hipoteses"] = legado
    if "checklist_documental" not in content:
        legado = [v for v in _as_list(result.get("acoes_remediacao")) if isinstance(v, str)]
        if legado:
            content["checklist_documental"] = legado

    return content
