"""Schemas Pydantic para os endpoints regulatórios — Sprint A1 Tarefa D2.

Read-only nesta sprint: nenhum POST/PUT exposto. Escrita fica para A2/Y.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.models.regulatory import RegulatoryIssueSeverity, RegulatoryIssueType

IssueStatusFilter = Literal["open", "resolved", "all"]


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
    """Saída de leitura de RegulatoryIssue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    document_id: int | None
    type: RegulatoryIssueType
    severity: RegulatoryIssueSeverity
    payload: dict[str, Any] | None
    detected_by: str | None
    detected_at: datetime
    resolved_at: datetime | None
