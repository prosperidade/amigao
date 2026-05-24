"""AuditorImovelAgent — Sprint A2 (Onda 2 da Fase 2).

Agente que orquestra tools determinísticas (`app.services.property_audit`) para
a matriz de cruzamento documental da skill `diagnostico/situacao_ambiental_imovel_rural`.

Princípio (radar, não cancela):
- A matemática é das tools (`property_audit.audit_property`); o LLM **não** faz conta.
- Cada divergência detectada vira um `RegulatoryIssue` persistido + uma
  `Divergencia` no payload (consumível pelo Diagnóstico via chain_data).
- Sem `Property.geom` (gap D1), a parte espacial é marcada como pendente —
  o cruzamento documental segue.

Não toca em `app/agents/diagnostico.py` (escopo do A3). A integração com o
fluxo do consultor é via chain (`chain_data["auditor_imovel"]`) — chains
existentes em `app/agents/orchestrator.py` podem registrar este agente quando
fizer sentido (sprint posterior define a chain).
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType
from app.services.property_audit import (
    AuditFinding,
    audit_property,
    finding_to_issue_type,
)

logger = logging.getLogger(__name__)


@AgentRegistry.register
class AuditorImovelAgent(BaseAgent):
    """Cruza documentos do imóvel e emite divergências tipadas."""

    name = "auditor_imovel"
    description = "Cruza matrícula × CAR × CCIR/ITR/SIGEF; detecta GEO INCRA, RL e área divergente"
    job_type = AIJobType.diagnostico_propriedade  # reusa enum; criar tipo próprio é Sprint posterior
    prompt_slugs: list[str] = []  # MVP sem LLM — só tools determinísticas

    def validate_preconditions(self) -> None:
        if not self.ctx.process_id:
            raise ValueError("process_id obrigatório para auditor_imovel")

    def execute(self) -> dict[str, Any]:
        process_data = self._load_process_data()
        property_data = process_data.get("property") or {}
        documents = process_data.get("documents") or []
        extracted = self.ctx.chain_data.get("extrator", {}) if isinstance(self.ctx.chain_data, dict) else {}

        # Rodar a bateria determinística
        findings: list[AuditFinding] = audit_property(
            property_data=property_data,
            documents=documents,
            extracted_data=extracted,
        )

        # Persistir cada finding como RegulatoryIssue (quando há property_id real)
        issue_ids = self._persist_issues(property_data, findings)

        # Payload (consumível pela chain — vide Divergencia em stage_output.py)
        divergencias = [
            {
                "tema": f.tema,
                "divergencia": f.descricao,
                "impacto": f.impacto,
            }
            for f in findings
        ]
        criticos = [f for f in findings if f.severity == "critical"]
        warnings = [f for f in findings if f.severity == "warning"]

        return {
            "content": (
                f"{len(findings)} divergência(s) detectada(s) "
                f"({len(criticos)} crítica(s), {len(warnings)} alerta(s))."
            ),
            "requires_review": True,  # princípio 1 do manifesto
            "divergencias": divergencias,
            "issue_ids": issue_ids,
            "findings_raw": [
                {
                    "type": f.type,
                    "severity": f.severity,
                    "tema": f.tema,
                    "descricao": f.descricao,
                    "impacto": f.impacto,
                    "evidencia": f.evidencia,
                }
                for f in findings
            ],
            "geom_present": property_data.get("geom") is not None,
            "method": "deterministic_tools",  # sinaliza que não passou por LLM
        }

    # ------------------------------------------------------------------

    def _load_process_data(self) -> dict[str, Any]:
        """Espelha DiagnosticoAgent._load_process_data — extrai Property + Documents
        relevantes para o cruzamento. Mantém pure-dict para o auditor permanecer testável.
        """
        from app.models.document import Document  # noqa: PLC0415
        from app.models.process import Process  # noqa: PLC0415
        from app.models.property import Property  # noqa: PLC0415

        process = (
            self.ctx.session.query(Process)
            .filter(Process.id == self.ctx.process_id, Process.tenant_id == self.ctx.tenant_id)
            .first()
        )
        if not process:
            raise ValueError(f"Processo {self.ctx.process_id} não encontrado")

        data: dict[str, Any] = {"process": {"id": process.id}}

        if process.property_id:
            prop = self.ctx.session.query(Property).filter(Property.id == process.property_id).first()
            if prop:
                data["property"] = {
                    "id": prop.id,
                    "total_area_ha": prop.total_area_ha,
                    "area_documental_ha": prop.area_documental_ha,
                    "area_grafica_ha": prop.area_grafica_ha,
                    "car_code": prop.car_code,
                    "car_status": prop.car_status,
                    "rl_status": prop.rl_status,
                    "geom": prop.geom,
                    # campos opcionais que podem vir do extrator são consultados em chain_data
                }

        docs = (
            self.ctx.session.query(Document)
            .filter(Document.process_id == self.ctx.process_id, Document.tenant_id == self.ctx.tenant_id)
            .filter(Document.deleted_at.is_(None))
            .all()
        )
        data["documents"] = [
            {"id": d.id, "document_type": d.document_type}
            for d in docs
        ]
        return data

    def _fallback_prompts(self) -> dict[str, str]:
        # MVP sem LLM — não há prompts. BaseAgent exige a implementação abstrata.
        return {}

    def _persist_issues(
        self,
        property_data: dict[str, Any],
        findings: list[AuditFinding],
    ) -> list[int]:
        """Cria um RegulatoryIssue por finding. Retorna IDs criados."""
        from app.models.regulatory import (  # noqa: PLC0415
            RegulatoryIssue,
            RegulatoryIssueSeverity,
            RegulatoryIssueType,
        )

        property_id = property_data.get("id")
        if not property_id:
            # Sem property persistida (caso de teste/dry-run), apenas reporta no payload.
            return []

        ids: list[int] = []
        for f in findings:
            issue = RegulatoryIssue(
                tenant_id=self.ctx.tenant_id,
                property_id=property_id,
                document_id=None,
                type=RegulatoryIssueType(finding_to_issue_type(f)),
                severity=RegulatoryIssueSeverity(f.severity),
                payload={
                    "descricao": f.descricao,
                    "impacto": f.impacto,
                    "tema": f.tema,
                    "finding_type": f.type,
                    "evidencia": f.evidencia,
                },
                detected_by=self.name,
            )
            self.ctx.session.add(issue)
            self.ctx.session.flush()
            ids.append(issue.id)
        self.ctx.session.commit()
        return ids
