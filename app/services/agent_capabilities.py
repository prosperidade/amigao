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
# Versão exigida por agente: o diagnóstico passou a 1.4.0 com o formato de afirmação (ADR-080).
REQUIRED_VERSIONS = {"auditor_imovel": "1.3.0", "diagnostico": "1.4.0"}

# ADR-074: pre-contract Redator and Orçamento are deterministic contracts over the validated Rota.
COMMERCIAL_SKILLS = {
    "redator": ("redator/relatorio_preliminar_escopo", "redator.py"),
    "orcamento": ("orcamento/orcamento_da_rota", "orcamento.py"),
}


def _commercial_manifest(manifest, agent_name, metadata):
    name, implementation = COMMERCIAL_SKILLS[agent_name]
    meta = discover_skills().get(name)
    if meta is None:
        manifest["missing"].append({"skill": name, "reason": "ausente_ou_invalida"})
    elif not matches_context(meta, agent=agent_name, ctx_metadata=metadata):
        # The definitive technical piece (post-contract, TR checklist) has no method yet.
        manifest["not_applicable"].append({"skill": name, "reason": "fora da cadeia comercial pré-contratação"})
        manifest["missing"].append({"agent": agent_name,
                                    "reason": "Peça técnica definitiva (pós-contratação) sem método disponível"})
    else:
        skill = load_skill(name)
        if skill is None or "Contrato de evidência — ADR-074" not in skill.body or meta.version != "1.0.0":
            manifest["missing"].append({"skill": name, "reason": "incompativel_com_contrato_074"})
        else:
            manifest["applied"].append({"name": name, "version": meta.version, "hash": canonical_hash(skill.body),
                "source_hash": canonical_hash(Path(meta.path).read_text(encoding="utf-8")),
                "content": skill.body, "attachments": [], "mode": "deterministic_contract"})
            code = (Path(__file__).parent / "comercial" / implementation).read_text(encoding="utf-8")
            manifest["implementation"].append({"method": f"comercial.{implementation[:-3]}",
                "hash": canonical_hash(code), "llm": False})
    manifest["status"] = "capacidade_insuficiente" if manifest["missing"] else "available"
    return manifest


def capability_manifest(agent_name, metadata):
    manifest = {"policy_version": "069.1", "applied": [], "missing": [], "not_applicable": [],
                "rules": [], "templates": [], "implementation": []}
    if agent_name not in ACTIVE_AGENTS:
        return {**manifest, "status": "agente_desativado"}
    if agent_name == "extrator":
        manifest["domain_pending"] = [{"status": "PENDENTE-ISIS",
            "subject": "Suficiência da Receita para o gate de falecimento; eventual certidão de óbito"}]
        ontology = Path(__file__).resolve().parents[2] / "docs/arquitetura/ONTOLOGIA_REGENTE_v1.md"
        if ontology.is_file():
            manifest["implementation"].append({"method": "ontologia_entrada_semantica",
                "status": "proposta_com_adendo", "hash": canonical_hash(ontology.read_text(encoding="utf-8"))})
        else:
            manifest["missing"].append({"method": "ontologia_entrada_semantica", "reason": "vocabulario_obrigatorio_ausente"})
        catalog = discover_skills()
        for family in ("registral", "cadastral", "pessoal", "geoespacial", "contratual", "cartorario"):
            name = f"extrator/{family}"
            meta = catalog.get(name)
            skill = load_skill(name) if meta else None
            expected_version = "1.0.0" if family == "cartorario" else "1.1.0"
            if skill is None or meta.version != expected_version:
                manifest["missing"].append({"skill": name, "reason": "metodo_obrigatorio_ausente"})
                continue
            manifest["applied"].append({"name": name, "version": meta.version,
                "hash": canonical_hash(skill.body),
                "source_hash": canonical_hash(Path(meta.path).read_text(encoding="utf-8")),
                "content": skill.body, "attachments": [],
                "mode": "deterministic_contract" if family == "cartorario" else "system_prompt"})
        manifest["status"] = "capacidade_insuficiente" if manifest["missing"] else "available"
        return manifest
    if agent_name in COMMERCIAL_SKILLS:
        return _commercial_manifest(manifest, agent_name, metadata)
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
            if skill is None or "Contrato de evidência — ADR-069" not in skill.body or meta.version != REQUIRED_VERSIONS[agent_name]:
                manifest["missing"].append({"skill": required, "reason": "incompativel_com_contrato_069"})
            else:
                attachments = []
                for path in sorted(Path(meta.path).parent.glob("*.md")):
                    if path.name != "SKILL.md":
                        content = path.read_text(encoding="utf-8")
                        attachments.append({"name": path.name, "hash": canonical_hash(content), "content": content})
                manifest["applied"].append({"name": required, "version": meta.version,
                    "hash": canonical_hash(skill.body),
                    "source_hash": canonical_hash(Path(meta.path).read_text(encoding="utf-8")), "content": skill.body, "attachments": attachments,
                    "mode": "deterministic_contract" if agent_name == "auditor_imovel" else "system_prompt"})
                if agent_name == "auditor_imovel":
                    code = Path(__file__).with_name("inconsistency_matrix.py").read_text(encoding="utf-8")
                    manifest["implementation"].append({"method": "inconsistency_matrix", "hash": canonical_hash(code),
                        "coverage": "document_comparison_only; no spatial overlay or legal applicability"})
    manifest["status"] = "capacidade_insuficiente" if manifest["missing"] else "available"
    return manifest
