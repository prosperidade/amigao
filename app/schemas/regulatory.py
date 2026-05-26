"""Schemas Pydantic para os endpoints regulatórios.

Histórico:
- **Onda B Fase 2** — POST de `RegulatoryDiagnosis` versionado com gate A4.
- **PROMPT_4 Onda B** — `PATCH /validate` (camada 1 do Princípio 1).
- **PROMPT_5 Onda A** — `RegulatoryIssueOut` ganha `codigo_alerta` + `familia`
  + campos `muda_*` + `documentos_cruzados`; `severity` passa a ter 4 níveis.
  `type` continua como nullable (deprecated) para retrocompat com registros
  antigos.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.regulatory import (
    RegulatoryFamilia,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
)

IssueStatusFilter = Literal["open", "resolved", "all"]


class RegulatoryDiagnosisCreate(BaseModel):
    """Input do POST /processes/{process_id}/diagnoses (Onda B Fase 2).

    O `content` é validado contra `DiagnosticoPreliminarContent` antes da
    persistência via `validate_diagnostic_content` — payloads que não
    respeitam o shape do schema retornam HTTP 422 com detalhes do Pydantic.
    A versão é calculada pelo servidor (`max(version) + 1`).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: dict[str, Any] = Field(
        ...,
        description=(
            "Conteúdo do diagnóstico. Deve respeitar `DiagnosticoPreliminarContent` "
            "(stage_output.py): pelo menos `content` (str) e `sources` (não vazio). "
            "Campos opcionais: hipoteses, lacunas, riscos, checklist_documental, "
            "divergencias, nivel_risco_geral, etc."
        ),
    )


class RegulatoryDiagnosisOut(BaseModel):
    """Saída de leitura de RegulatoryDiagnosis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    process_id: int
    version: int
    content: dict[str, Any]
    validated_by_user_id: int | None
    validated_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class RegulatoryIssueOut(BaseModel):
    """Saída de leitura de RegulatoryIssue.

    PROMPT_5 Onda A: ganha a taxonomia rica. ``type`` continua exposto mas
    é nullable (deprecated; registros novos preenchem `codigo_alerta` +
    `familia`).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    document_id: int | None
    # Taxonomia rica (PROMPT_5)
    codigo_alerta: str | None
    familia: RegulatoryFamilia | None
    muda_rota_regulatoria: bool | None
    muda_escopo_preco_prazo: bool | None
    documentos_cruzados: list[str] | None
    # severity 4 níveis
    severity: RegulatoryIssueSeverity
    # type legado (nullable, deprecated)
    type: RegulatoryIssueType | None
    payload: dict[str, Any] | None
    detected_by: str | None
    detected_at: datetime
    resolved_at: datetime | None
