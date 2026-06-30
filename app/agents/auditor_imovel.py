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

        # Ficha 02 / FASE 3 — Matriz de Inconsistências (saída canônica do auditor).
        # Determinística: lê o staging da Fase 2, confronta as fontes e marca o
        # status das linhas confrontadas. Campo NOVO no resultado (não quebra shape).
        matriz = self._build_matriz_inconsistencias()

        # Payload (consumível pela chain — vide Divergencia em stage_output.py)
        divergencias = [
            {
                "tema": f.tema,
                "divergencia": f.descricao,
                "impacto": f.impacto,
            }
            for f in findings
        ]
        # PROMPT_5 Onda A: contagem por grade (4 níveis), não mais severity (3).
        criticos = [f for f in findings if f.grade == "critico"]
        altos = [f for f in findings if f.grade == "alto"]
        atencoes = [f for f in findings if f.grade == "atencao"]

        return {
            "content": (
                f"{len(findings)} divergência(s) detectada(s) "
                f"({len(criticos)} crítica(s), {len(altos)} alto(s), "
                f"{len(atencoes)} atenção)."
            ),
            "requires_review": True,  # princípio 1 do manifesto
            "divergencias": divergencias,
            "issue_ids": issue_ids,
            "findings_raw": [
                {
                    # PROMPT_5 Onda A: taxonomia rica no payload.
                    # `codigo_alerta` + `familia` substituem o `type` legado.
                    # `grade` continua como eixo único de severidade (4 níveis).
                    "codigo_alerta": f.codigo_alerta,
                    "familia": f.familia,
                    "grade": f.grade,
                    "tema": f.tema,
                    "descricao": f.descricao,
                    "impacto": f.impacto,
                    "evidencia": f.evidencia,
                    "muda_rota_regulatoria": f.muda_rota_regulatoria,
                    "muda_escopo_preco_prazo": f.muda_escopo_preco_prazo,
                    "documentos_cruzados": f.documentos_cruzados,
                }
                for f in findings
            ],
            "geom_present": property_data.get("geom") is not None,
            "method": "deterministic_tools",  # sinaliza que não passou por LLM
            # Ficha 02 / FASE 3 — matriz de inconsistências (campo novo).
            "matriz_inconsistencias": matriz,
        }

    def _build_matriz_inconsistencias(self) -> dict[str, Any]:
        """Ficha 02 / FASE 3 — monta a matriz a partir do staging do processo e
        marca o status das linhas confrontadas (consistente / divergente_*).

        Determinístico, best-effort: falha não derruba o auditor (devolve matriz
        vazia). A decisão aceito/rejeitado é do consultor (Fase 4) — não aqui.
        """
        from app.models.extracted_field_staging import (  # noqa: PLC0415
            ExtractedFieldStaging,
            ExtractedFieldStatus,
        )
        from app.services.inconsistency_matrix import build_matrix  # noqa: PLC0415

        try:
            rows = (
                self.ctx.session.query(ExtractedFieldStaging)
                .filter(
                    ExtractedFieldStaging.tenant_id == self.ctx.tenant_id,
                    ExtractedFieldStaging.process_id == self.ctx.process_id,
                )
                .order_by(ExtractedFieldStaging.id.asc())
                .all()
            )
            result = build_matrix(rows)
            for staging_row, novo_status in result.status_updates:
                try:
                    staging_row.status = ExtractedFieldStatus(novo_status)
                except ValueError:
                    continue
            if result.status_updates:
                self.ctx.session.flush()
            return result.matriz
        except Exception as exc:  # pragma: no cover - blindagem
            logger.warning("auditor_imovel: matriz de inconsistências falhou (ignorada): %s", exc)
            return {"fontes": [], "linhas": [], "resumo": {}}

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
        """Cria um ``RegulatoryIssue`` por finding com **taxonomia rica**
        (PROMPT_5 Onda A): ``codigo_alerta`` (FK no catálogo), ``familia``,
        ``severity`` 4 níveis (= ``finding.grade``), e overrides
        ``muda_rota_regulatoria`` / ``muda_escopo_preco_prazo`` /
        ``documentos_cruzados``. O ``type`` legado (3 níveis) fica como
        ``None`` em registros novos.
        """
        from app.models.regulatory import (  # noqa: PLC0415
            RegulatoryFamilia,
            RegulatoryIssue,
            RegulatoryIssueSeverity,
        )
        from app.services.regulatory_dedupe import issue_dedupe_key  # noqa: PLC0415

        property_id = property_data.get("id")
        if not property_id:
            # Sem property persistida (caso de teste/dry-run), apenas reporta no payload.
            return []

        # Idempotência (Ficha 07 §2): um achado por (property, codigo_alerta, tema,
        # descricao) enquanto NÃO resolvido. O auditor roda toda vez que a etapa
        # E2/E4 re-roda os agentes; sem este guard, cada execução inseria uma
        # duplicata (medido no caso 13: 11 linhas idênticas). Re-rodar agora reusa
        # a issue existente — preservando a decisão do consultor em status_achado.
        existing = (
            self.ctx.session.query(RegulatoryIssue)
            .filter(
                RegulatoryIssue.tenant_id == self.ctx.tenant_id,
                RegulatoryIssue.property_id == property_id,
                RegulatoryIssue.resolved_at.is_(None),
            )
            .all()
        )
        by_key: dict[str, RegulatoryIssue] = {}
        for iss in existing:
            payload: dict[str, Any] = iss.payload or {}
            key = issue_dedupe_key(
                property_id=property_id,
                codigo_alerta=iss.codigo_alerta,
                type_legacy=iss.type.value if iss.type is not None else None,
                tema=payload.get("tema"),
                descricao=payload.get("descricao"),
            )
            by_key.setdefault(key, iss)

        ids: list[int] = []
        for f in findings:
            key = issue_dedupe_key(
                property_id=property_id,
                codigo_alerta=f.codigo_alerta,
                type_legacy=None,
                tema=f.tema,
                descricao=f.descricao,
            )
            hit = by_key.get(key)
            if hit is not None:
                # Achado idêntico já existe e não está resolvido — não duplica.
                ids.append(hit.id)
                continue
            issue = RegulatoryIssue(
                tenant_id=self.ctx.tenant_id,
                property_id=property_id,
                document_id=None,
                # Taxonomia rica (PROMPT_5 Onda A) — codigo_alerta é FK no
                # `regulatory_issue_catalog`; familia é o enum estável de 11.
                codigo_alerta=f.codigo_alerta,
                familia=RegulatoryFamilia(f.familia),
                # severity de 4 níveis (PROMPT_5) — grade é o eixo único.
                severity=RegulatoryIssueSeverity(f.grade),
                muda_rota_regulatoria=f.muda_rota_regulatoria,
                muda_escopo_preco_prazo=f.muda_escopo_preco_prazo,
                documentos_cruzados=f.documentos_cruzados,
                # type legado fica nullable em registros novos (deprecated).
                type=None,
                payload={
                    "descricao": f.descricao,
                    "impacto": f.impacto,
                    "tema": f.tema,
                    "evidencia": f.evidencia,
                },
                detected_by=self.name,
            )
            self.ctx.session.add(issue)
            self.ctx.session.flush()
            by_key[key] = issue  # evita duplicar dentro da mesma execução
            ids.append(issue.id)
        self.ctx.session.commit()
        return ids
