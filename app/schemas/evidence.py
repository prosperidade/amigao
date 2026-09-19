"""Versioned evidence contract (ADR-069). Unknown values are never invented."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

KnowledgeState = Literal[
    "nao_determinado", "nao_localizado_no_material", "ausencia_verificada_no_escopo",
    "nao_aplicavel", "conflitante", "falha_de_verificacao",
]


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), default=str).encode()).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceRef(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)


class Verification(Contract):
    source: EvidenceRef
    scope: str = Field(min_length=1)
    identifiers: list[str] = Field(min_length=1)
    consulted_at: datetime
    preserved_response: EvidenceRef


class Coverage(Contract):
    material: list[EvidenceRef] = Field(min_length=1)
    scope: str = Field(min_length=1)
    coverage: str = Field(min_length=1)


class EvidenceAttributes(Contract):
    """Applicable fields are explicit; null means unknown, not not-applicable."""

    document_id: int | None = None
    documento_versao_id: int | None = Field(default=None, ge=1)
    fragmento_id: int | None = Field(default=None, ge=1)
    document_version: int | None = Field(default=None, ge=1)
    original_hash: str | None = None
    text_hash: str | None = None
    page: int | None = Field(default=None, ge=1)
    position: str | None = None
    feature: str | None = None
    predicate: str | None = None
    literal: Any = None
    normalized: Any = None
    unit: str | None = None
    subject: str | None = None
    object: str | None = None
    person: str | None = None
    role: str | None = None
    document_date: date | None = None
    act_date: date | None = None
    effective_date: date | None = None
    reference_date: date | None = None
    method: str | None = None
    method_version: str | None = None
    anchor: str | None = None
    certainty: str | None = None
    coverage: Coverage | None = None
    not_applicable_fields: dict[str, str] = Field(default_factory=dict)


class Knowledge(Contract):
    state: KnowledgeState = "nao_determinado"
    verification: Verification | None = None
    examined: Coverage | None = None
    justification: str | None = None

    @model_validator(mode="after")
    def validate_knowledge(self):
        if self.state == "ausencia_verificada_no_escopo" and self.verification is None:
            raise ValueError("Ausência verificada exige consulta e resposta preservadas")
        if self.state == "nao_localizado_no_material" and self.examined is None:
            raise ValueError("Não localizado exige material examinado e cobertura")
        if self.state == "nao_aplicavel" and not self.justification:
            raise ValueError("Não aplicável exige justificativa")
        return self


class EvidenceObject(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    kind: Literal["fonte_primaria", "observacao", "derivacao", "conclusao"]
    attributes: EvidenceAttributes = Field(default_factory=EvidenceAttributes)
    knowledge: Knowledge = Field(default_factory=Knowledge)
    premises: list[EvidenceRef] = Field(default_factory=list)
    statement: str | None = None
    conclusion_class: Literal[
        "fato_documental", "divergencia", "lacuna", "hipotese", "risco", "orientacao", "escopo_proposto",
    ] | None = None
    applicability: str | None = None
    applicability_reason: str | None = None
    norms: list[EvidenceRef] = Field(default_factory=list)
    rules: list[EvidenceRef] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    origin: str = Field(min_length=1)
    legacy_unverified: bool = False

    @model_validator(mode="after")
    def validate_object(self):
        if self.kind == "fonte_primaria" and self.origin not in {"documento", "consulta", "cadastro_humano", "cadastro_legado"}:
            raise ValueError("Saída de agente não é fonte primária")
        if self.kind == "derivacao" and (not self.premises or not self.attributes.method_version):
            raise ValueError("Derivação exige entradas e versão do método")
        if self.kind == "conclusao" and (not self.statement or not self.conclusion_class):
            raise ValueError("Conclusão exige texto e classe")
        if self.conclusion_class == "risco" and (
            not self.premises or self.applicability != "aplicavel" or not self.applicability_reason
        ):
            raise ValueError("Risco exige premissas e teste de aplicabilidade")
        if self.knowledge.state == "nao_aplicavel" and not self.premises:
            raise ValueError("Não aplicável exige premissas")
        return self

    def as_assertion(self):
        """Afirmacao remains the legacy projection, linked to this durable version."""
        from app.schemas.stage_output import Afirmacao, SourceRef
        if self.kind != "conclusao":
            raise ValueError("Somente conclusão tem projeção Afirmacao")
        return Afirmacao(texto=self.statement, categoria=self.conclusion_class,
                         evidence_id=self.id, evidence_version=self.version,
                         fontes=[SourceRef(tipo="auditor", evidence_id=p.id, evidence_version=p.version,
                                          ref=p.id, descricao="Premissa versionada; consulte sua linhagem")
                                 for p in self.premises])


class ExecutionEnvelope(Contract):
    contract_version: str = "1.0"
    tenant_id: int
    case_id: int
    objective: str | None = None
    reference_date: date
    snapshot_id: str
    snapshot_hash: str
    case: dict[str, Any] = Field(default_factory=dict)
    sources: list[EvidenceObject] = Field(default_factory=list)
    observations: list[EvidenceObject] = Field(default_factory=list)
    derivations: list[EvidenceObject] = Field(default_factory=list)
    conclusions: list[EvidenceObject] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[dict[str, Any]] = Field(default_factory=list)
    review_states: list[dict[str, Any]] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)

    @property
    def semantic_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json", exclude={"snapshot_id"}))


class ReviewRequest(Contract):
    expected_version: int = Field(ge=1)
    expected_revision: int = Field(ge=0)
    action: Literal["aprovar", "corrigir", "rejeitar", "nao_aplicavel"]
    justification: str = Field(min_length=1)
    correction: EvidenceObject | None = None
