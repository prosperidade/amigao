"""Schemas Pydantic para os endpoints regulatórios.

Histórico:
- **Onda B Fase 2** — POST de `RegulatoryDiagnosis` versionado com gate A4.
- **PROMPT_4 Onda B** — `PATCH /validate` (camada 1 do Princípio 1).
- **PROMPT_5 Onda A** — `RegulatoryIssueOut` ganha `codigo_alerta` + `familia`
  + campos `muda_*` + `documentos_cruzados`; `severity` passa a ter 4 níveis.
- **PROMPT_6** — `RegulatoryIssueOut` ganha os 3 status reconciliados
  (`status_achado`, `decisao_consultor`, `status_saneamento`). Novo
  `RegulatoryIssueUpdate` para o `PATCH /properties/{prop}/issues/{id}`.
- **PROMPT_7** (ADR-012) — `decisao_consultor` sai de `RegulatoryIssue` e
  vira `ProcessIssueDecision` (entidade própria por `(processo × issue)`).
  `RegulatoryIssueOut/Update` perdem os 3 campos de decisão; novos schemas
  `ProcessIssueDecisionCreate/Out` modelam a decisão contextual.
- **PROMPT_8** (#17) — `RegulatoryIssueUpdate` ganha `@model_validator` que
  delega para `regulatory_coherence.assert_status_coerente` (fast-fail
  quando os 2 status vêm juntos no body).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.regulatory import (
    DecisaoConsultor,
    RegulatoryFamilia,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
    StatusAchado,
    StatusSaneamento,
)
from app.services.regulatory_coherence import assert_status_coerente

IssueStatusFilter = Literal["open", "resolved", "all"]


def _coerce_documentos_cruzados(v: Any) -> Any:
    """Normaliza ``documentos_cruzados`` para ``list[str]`` na leitura.

    ``documentos_cruzados`` é JSONB alimentado pelo auditor — cujo conteúdo, em
    paths guiados por LLM, pode chegar como lista de **objetos**
    (ex.: ``[{"doc": "matricula"}]``) em vez de lista de **strings**. O schema
    exige ``list[str]``; sem esta coerção o Pydantic levanta
    ``ResponseValidationError`` e o endpoint de listagem retorna **500 para a
    lista inteira** por causa de uma única linha malformada (causa raiz do 500
    em ``GET /properties/{id}/issues``). Aqui cada item vira string legível,
    preservando a informação em vez de derrubar a resposta (degradar com
    elegância — o radar não cancela). Linhas já corretas passam intactas.
    """
    if not isinstance(v, list):
        return v
    out: list[str] = []
    for item in v:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            parts = [str(x) for x in item.values() if x not in (None, "")]
            out.append(" — ".join(parts) if parts else str(item))
        elif item is not None:
            out.append(str(item))
    return out


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
    PROMPT_6: 3 status reconciliados (Opção A).
    PROMPT_7 (ADR-012): `decisao_consultor` saiu — vive agora em
    `ProcessIssueDecision`. Restam aqui só os 2 perenes
    (`status_achado` e `status_saneamento`).
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
    # 2 status perenes (PROMPT_6 + ADR-012)
    status_achado: StatusAchado
    status_saneamento: StatusSaneamento
    # type legado (nullable, deprecated)
    type: RegulatoryIssueType | None
    payload: dict[str, Any] | None
    detected_by: str | None
    detected_at: datetime
    resolved_at: datetime | None

    @field_validator("documentos_cruzados", mode="before")
    @classmethod
    def _normalize_documentos_cruzados(cls, v: Any) -> Any:
        return _coerce_documentos_cruzados(v)


class RegulatoryIssueUpdate(BaseModel):
    """Input do PATCH /api/v1/properties/{prop_id}/issues/{issue_id}.

    PROMPT_7 (ADR-012): perdeu os 3 campos de decisão — eles agora vivem em
    ``ProcessIssueDecisionCreate`` (PUT `/processes/{pid}/issues/{iid}/decision`).
    Aqui ficam só os 2 status perenes (``status_achado`` e ``status_saneamento``)
    do fato do imóvel.

    Body parcial — campos ausentes não são tocados. Cada campo alterado gera
    AuditLog próprio (Princípio 2).

    PROMPT_8 (#17): `@model_validator` fast-fail para combinações incoerentes
    quando os 2 status vêm juntos no body. PATCH parcial (só 1 campo) é
    validado no endpoint contra o estado resultante.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status_achado: StatusAchado | None = None
    status_saneamento: StatusSaneamento | None = None

    @model_validator(mode="after")
    def _coerencia_quando_body_completo(self) -> RegulatoryIssueUpdate:
        """PROMPT_8 (#17) — fast-fail no body quando os 2 status vêm juntos.

        A fonte da verdade fica no endpoint (que conhece o estado resultante
        após aplicar o body sobre a issue carregada). Aqui só dispara quando
        ambos campos estão presentes — PATCH parcial é validado lá.
        Reaproveita o mesmo helper para não duplicar regra.
        """
        if self.status_achado is not None and self.status_saneamento is not None:
            assert_status_coerente(self.status_achado, self.status_saneamento)
        return self


class DiagnosisNoteOut(BaseModel):
    """Nota DERIVADA na leitura — não-acionável, nunca armazenada (ADR-020).

    Estado derivado se calcula na leitura, não vira linha em `regulatory_issues`
    (Princípio 11; mesmo padrão de RL "averbada" derivada). Hoje cobre só a
    "verificação espacial pendente" quando `Property.geom IS NULL`. `source` é
    sempre 'derived' (rastreabilidade); `acionavel` é sempre False (a UI a
    renderiza como nota discreta, sem botões de decisão)."""

    model_config = ConfigDict(from_attributes=True)

    codigo: str
    titulo: str
    texto: str
    severity: RegulatoryIssueSeverity = RegulatoryIssueSeverity.informativo
    source: Literal["derived"] = "derived"
    acionavel: Literal[False] = False


# ---------------------------------------------------------------------------
# PROMPT_7 (ADR-012) — Schemas de ProcessIssueDecision
# ---------------------------------------------------------------------------

class ProcessIssueDecisionCreate(BaseModel):
    """Input do PUT /api/v1/processes/{process_id}/issues/{issue_id}/decision.

    PUT é **upsert** — cria a primeira decisão ou atualiza a existente. Cada
    processo×issue tem no máximo uma decisão (unique constraint no model).

    **Princípio 2 — justificativa obrigatória para descarte/exclusão:** quando
    ``decisao in {ignorar_justificado, fora_escopo}``, ``justificativa``
    precisa estar preenchida e não-vazia. O nome do valor promete o registro
    — sem justificativa, o "li e aceito técnico" vira só "li e aceito", e a
    camada 2 do Princípio 1 fica incompleta no caso que mais importa
    (descartar uma crítica). Validator retorna 422.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decisao: DecisaoConsultor = Field(
        ...,
        description=(
            "Decisão do consultor sobre o alerta, no contexto deste processo. "
            "5 valores (botões P4): corrigir_antes / seguir_com_ressalva / "
            "solicitar_doc / fora_escopo / ignorar_justificado."
        ),
    )
    justificativa: str | None = Field(
        default=None,
        description=(
            "Texto livre. **Obrigatório** quando decisao in "
            "{ignorar_justificado, fora_escopo} — sem isso o nome do valor "
            "mente e o Princípio 2 (auditável) falha no caso que mais importa "
            "(descartar uma crítica)."
        ),
    )

    @model_validator(mode="after")
    def _justificativa_obrigatoria_em_descarte(self) -> ProcessIssueDecisionCreate:
        """Fecha o buraco que vinha do #19 do REGISTRO_DIVIDAS (PROMPT_6
        revisão): `ignorar_justificado` e `fora_escopo` exigem justificativa
        não-vazia. Aplicado em criação E atualização (PUT é upsert), porque
        em ambos a `decisao` está sempre presente no body."""
        exige_justificativa = {
            DecisaoConsultor.ignorar_justificado,
            DecisaoConsultor.fora_escopo,
        }
        if self.decisao in exige_justificativa:
            j = self.justificativa
            if j is None or not j.strip():
                raise ValueError(
                    f"decisao='{self.decisao.value}' exige justificativa "
                    "não-vazia (Princípio 2 — o nome do valor promete o registro)"
                )
        return self


class ProcessIssueDecisionOut(BaseModel):
    """Saída do GET/PUT /processes/{pid}/issues/{iid}/decision."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    process_id: int
    issue_id: int
    decisao: DecisaoConsultor
    justificativa: str | None
    decided_by_user_id: int | None
    decided_at: datetime
    created_at: datetime | None
    updated_at: datetime | None
