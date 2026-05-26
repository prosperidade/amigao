"""Schemas Pydantic para os endpoints regulatórios.

Histórico:
- **Onda B Fase 2** — POST de `RegulatoryDiagnosis` versionado com gate A4.
- **PROMPT_4 Onda B** — `PATCH /validate` (camada 1 do Princípio 1).
- **PROMPT_5 Onda A** — `RegulatoryIssueOut` ganha `codigo_alerta` + `familia`
  + campos `muda_*` + `documentos_cruzados`; `severity` passa a ter 4 níveis.
- **PROMPT_6** — `RegulatoryIssueOut` ganha os 3 status reconciliados
  (`status_achado`, `decisao_consultor`, `status_saneamento`). Novo
  `RegulatoryIssueUpdate` para o `PATCH /properties/{prop}/issues/{id}`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.regulatory import (
    DecisaoConsultor,
    RegulatoryFamilia,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
    StatusAchado,
    StatusSaneamento,
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

    PROMPT_5 Onda A: taxonomia rica.
    PROMPT_6: 3 status reconciliados (Opção A do RECONCILIACAO_STATUS_ALERTAS).
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
    # Reconciliação dos 3 status (PROMPT_6 — camada 2 do Princípio 1)
    status_achado: StatusAchado
    decisao_consultor: DecisaoConsultor | None
    decisao_consultor_justificativa: str | None
    decisao_consultor_at: datetime | None
    status_saneamento: StatusSaneamento
    # type legado (nullable, deprecated)
    type: RegulatoryIssueType | None
    payload: dict[str, Any] | None
    detected_by: str | None
    detected_at: datetime
    resolved_at: datetime | None


class RegulatoryIssueUpdate(BaseModel):
    """Input do PATCH /api/v1/properties/{prop_id}/issues/{issue_id} (PROMPT_6).

    Todos os campos são opcionais — o consultor pode editar parcialmente.
    Cada campo alterado gera um AuditLog separado (Princípio 2).

    Quando ``decisao_consultor`` é setado pela primeira vez,
    ``decisao_consultor_at`` é gravado automaticamente pelo servidor (não
    aceita override).

    **Princípio 2 — justificativa obrigatória para descarte/exclusão:** quando
    ``decisao_consultor`` é setado para ``ignorar_justificado`` ou
    ``fora_escopo`` no mesmo body, ``decisao_consultor_justificativa`` precisa
    estar preenchida e não-vazia. O nome do valor promete o registro — sem
    justificativa, o "li e aceito técnico" vira só "li e aceito", e a camada
    2 do Princípio 1 fica incompleta no caso que mais importa (descartar uma
    crítica). Validator retorna 422 quando essas condições não são atendidas.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status_achado: StatusAchado | None = None
    decisao_consultor: DecisaoConsultor | None = None
    decisao_consultor_justificativa: str | None = Field(
        default=None,
        description=(
            "Texto livre. **Obrigatório** quando decisao_consultor in "
            "{ignorar_justificado, fora_escopo} no mesmo body — sem isso o "
            "nome do valor mente e o Princípio 2 (auditável) falha no caso "
            "que mais importa (descartar uma crítica)."
        ),
    )
    status_saneamento: StatusSaneamento | None = None

    @model_validator(mode="after")
    def _justificativa_obrigatoria_em_descarte(self) -> "RegulatoryIssueUpdate":
        """Fecha o buraco #19 do REGISTRO_DIVIDAS: o nome `ignorar_justificado`
        promete a justificativa. `fora_escopo` idem — quem decide tirar do
        contrato precisa registrar por quê. Sem registro, vira cancela
        disfarçada (e Princípio 2 não se sustenta no ponto crítico).

        Aplicado APENAS quando ``decisao_consultor`` está sendo SETADO no body
        — PATCH parcial que só toca outros campos (sem `decisao_consultor`)
        não dispara (a justificativa antiga continua valendo). Isso evita
        forçar re-confirmação a cada mudança de `status_saneamento`.
        """
        exige_justificativa = {
            DecisaoConsultor.ignorar_justificado,
            DecisaoConsultor.fora_escopo,
        }
        if self.decisao_consultor in exige_justificativa:
            j = self.decisao_consultor_justificativa
            if j is None or not j.strip():
                raise ValueError(
                    f"decisao_consultor='{self.decisao_consultor.value}' exige "
                    "decisao_consultor_justificativa não-vazia no mesmo body "
                    "(Princípio 2 — o nome do valor promete o registro)"
                )
        return self
