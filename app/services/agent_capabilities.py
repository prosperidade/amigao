"""Execution policy, including queued messages and procedural capabilities."""

from pathlib import Path

from app.schemas.evidence import canonical_hash
from app.skills import discover_skills, load_skill
from app.skills._registry import matches_context

ACTIVE_AGENTS = frozenset({"extrator", "auditor_imovel", "legislacao", "diagnostico", "redator", "orcamento"})
REQUIRED_SKILLS = {
    "auditor_imovel": "auditor_imovel/analise_divergencias_documentais",
    "diagnostico": "diagnostico/situacao_ambiental_imovel_rural",
}


def capability_manifest(agent_name, metadata):
    manifest = {"policy_version": "069.1", "applied": [], "missing": [], "not_applicable": [],
                "rules": [], "templates": [], "implementation": []}
    if agent_name not in ACTIVE_AGENTS:
        return {**manifest, "status": "agente_desativado"}
    required = REQUIRED_SKILLS.get(agent_name)
    if not required:
        manifest["missing"].append({"agent": agent_name, "reason": "Método-base ainda não disponível; placeholder não é capacidade"})
    else:
        catalog = discover_skills()
        meta = catalog.get(required)
        if meta is None:
            manifest["missing"].append({"skill": required, "reason": "ausente_ou_invalida"})
        elif not matches_context(meta, agent=agent_name, ctx_metadata=metadata):
            manifest["not_applicable"].append({"skill": required, "reason": "UF desconhecida ou fora da cobertura"})
            manifest["missing"].append({"agent": agent_name, "reason": "Método geral de coleta não disponível para esta jurisdição"})
        else:
            skill = load_skill(required)
            if skill is None or "Contrato de evidência — ADR-069" not in skill.body or meta.version != "1.3.0":
                manifest["missing"].append({"skill": required, "reason": "incompativel_com_contrato_069"})
            else:
                attachments = []
                for path in sorted(Path(meta.path).parent.glob("*.md")):
                    if path.name != "SKILL.md":
                        content = path.read_text(encoding="utf-8")
                        attachments.append({"name": path.name, "hash": canonical_hash(content), "content": content})
                manifest["applied"].append({"name": required, "version": meta.version,
                    "hash": canonical_hash(skill.body), "content": skill.body, "attachments": attachments,
                    "mode": "deterministic_contract" if agent_name == "auditor_imovel" else "system_prompt"})
                if agent_name == "auditor_imovel":
                    code = Path(__file__).with_name("inconsistency_matrix.py").read_text(encoding="utf-8")
                    manifest["implementation"].append({"method": "inconsistency_matrix", "hash": canonical_hash(code),
                        "coverage": "document_comparison_only; no spatial overlay or legal applicability"})
    manifest["status"] = "capacidade_insuficiente" if manifest["missing"] else "available"
    return manifest
