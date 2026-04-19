"""
Output Validation Pipeline para agentes.

Etapas: JSON parse → JSON Schema → regras de dominio → safety check.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OutputValidationError(Exception):
    """Erro de validacao de output do agente."""

    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(f"[{stage}] {detail}")


class OutputValidationPipeline:
    """Pipeline de validacao multi-estagio para outputs de agente."""

    @staticmethod
    def validate(
        raw: dict[str, Any],
        schema: dict | None = None,
    ) -> dict[str, Any]:
        """Valida output passando por todos os estagios."""
        # Stage 1: Garantir que e dict
        if not isinstance(raw, dict):
            raise OutputValidationError("type_check", f"Esperado dict, recebido {type(raw).__name__}")

        # Stage 2: JSON Schema (se fornecido)
        if schema:
            _validate_schema(raw, schema)

        # Stage 3: Regras de dominio
        _check_domain_rules(raw)

        # Stage 4: Safety
        _check_safety(raw)

        return raw

    @staticmethod
    def parse_llm_json(content: str) -> dict[str, Any]:
        """
        Extrai JSON da resposta do LLM (tolerante a texto ao redor).
        Reutiliza pattern existente do llm_classifier/document_extractor.
        """
        content = content.strip()

        # Tentativa 1: parse direto
        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # Tentativa 2: extrair bloco markdown ```json
        if "```json" in content:
            try:
                block = content.split("```json")[1].split("```")[0].strip()
                result = json.loads(block)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, IndexError):
                pass

        # Tentativa 3: encontrar { ... } no texto
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(content[start:end])
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        raise OutputValidationError(
            "json_parse",
            f"Nao foi possivel extrair JSON da resposta LLM: {content[:200]}",
        )


def _validate_schema(data: dict[str, Any], schema: dict) -> None:
    """Validacao basica de schema sem dependencia externa (jsonschema)."""
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    missing = [f for f in required if f not in data]
    if missing:
        raise OutputValidationError(
            "schema",
            f"Campos obrigatorios ausentes: {missing}",
        )

    for field_name, field_schema in properties.items():
        if field_name not in data:
            continue
        value = data[field_name]
        if value is None:
            continue
        expected_type = field_schema.get("type")
        if expected_type and not _type_matches(value, expected_type):
            raise OutputValidationError(
                "schema",
                f"Campo '{field_name}': esperado tipo '{expected_type}', recebido {type(value).__name__}",
            )


def _type_matches(value: Any, expected: str) -> bool:
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    expected_types = type_map.get(expected)
    if expected_types is None:
        return True
    return isinstance(value, expected_types)


def _check_domain_rules(data: dict[str, Any]) -> None:
    """Regras de dominio ambiental basicas."""
    # Confianca deve ser valor valido se presente
    confidence = data.get("confidence")
    if confidence is not None and confidence not in ("high", "medium", "low"):
        logger.warning("validators: confidence invalido '%s', normalizando para 'medium'", confidence)
        data["confidence"] = "medium"

    # Risco deve ser valor valido se presente
    risco = data.get("risco_estimado")
    if risco is not None and risco not in ("baixo", "medio", "alto", "critico"):
        data["risco_estimado"] = "medio"


_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"you\s+are\s+now\s+a\s+different",
    r"system\s*:\s*you\s+are",
    r"<\s*/?\s*system\s*>",
]


def _check_safety(data: dict[str, Any]) -> None:
    """Detecta possiveis artefatos de prompt injection no output."""
    text_values = _extract_text_values(data)
    full_text = " ".join(text_values).lower()

    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, full_text, re.IGNORECASE):
            logger.warning("validators: possivel prompt injection detectado no output")
            raise OutputValidationError(
                "safety",
                "Output contem possivel artefato de prompt injection",
            )


def _extract_text_values(data: Any, depth: int = 0) -> list[str]:
    """Extrai todos os valores string de um dict/list recursivamente."""
    if depth > 5:
        return []
    values: list[str] = []
    if isinstance(data, str):
        values.append(data)
    elif isinstance(data, dict):
        for v in data.values():
            values.extend(_extract_text_values(v, depth + 1))
    elif isinstance(data, list):
        for item in data:
            values.extend(_extract_text_values(item, depth + 1))
    return values
