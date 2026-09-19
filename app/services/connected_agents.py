"""Persisted execution of the existing six responsibilities through ADR-069."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from pydantic import TypeAdapter

from app.models.ai_job import AIJob, AIJobStatus
from app.models.evidence import AgentExecution, CaseSnapshot, ExecucaoSnapshot, Manifesto
from app.schemas.evidence import EvidenceObject, canonical_hash
from app.services.agent_capabilities import ACTIVE_AGENTS, capability_manifest
from app.services.evidence import (
    authorize,
    build_envelope,
    capture_snapshot,
    invalidate_dependents,
    last_review,
    latest_objects,
    lock_case,
    persist_object,
)

CHAINS = {
    "diagnostico_completo": ["extrator", "auditor_imovel", "legislacao", "diagnostico"],
    "gerar_proposta": ["diagnostico", "redator", "orcamento"],
    "gerar_documento": ["redator"],
    "analise_regulatoria": ["legislacao"],
    "enquadramento_regulatorio": ["extrator", "legislacao"],
}
# Reading, comparison and legal retrieval do not depend on an unreviewed conclusion.
# Synthesis/commercial steps wait only for the conclusions they require.
DEPENDENCIES = {"diagnostico": ["auditor_imovel", "legislacao"],
                "redator": ["diagnostico"], "orcamento": ["diagnostico", "redator"]}


def start_execution(db, tenant_id, user_id, process_id, name, key=None):
    authorize(db, tenant_id, user_id, process_id)
    lock_case(db, tenant_id, process_id, wait=False)
    names = CHAINS.get(name, [name])
    if any(n not in ACTIVE_AGENTS for n in names):
        raise HTTPException(409, "agente_desativado")
    if key:
        existing = db.query(AgentExecution).filter(AgentExecution.tenant_id == tenant_id,
            AgentExecution.process_id == process_id, AgentExecution.idempotency_key == key).first()
        if existing:
            if existing.chain_name != name:
                raise HTTPException(409, "Chave idempotente já usada para outra execução")
            return existing
    snapshot = capture_snapshot(db, tenant_id, user_id, process_id)
    execution = AgentExecution(id=uuid4().hex, tenant_id=tenant_id, process_id=process_id,
        created_by_user_id=user_id, snapshot_id=snapshot.id, idempotency_key=key or uuid4().hex,
        chain_name=name, steps=[{"agent": n, "status": "pending", "depends_on": DEPENDENCIES.get(n, [])} for n in names])
    db.add(execution)
    db.flush()
    registrar_snapshot(db, execution, snapshot.id)
    return execution


def registrar_snapshot(db, execution, snapshot_id):
    existing = db.query(ExecucaoSnapshot).filter_by(execucao_id=execution.id,
        snapshot_id=snapshot_id, a_partir_passo=execution.cursor).first()
    if existing is None:
        db.add(ExecucaoSnapshot(tenant_id=execution.tenant_id, process_id=execution.process_id,
            execucao_id=execution.id, snapshot_id=snapshot_id, a_partir_passo=execution.cursor))
        db.flush()


def get_execution(db, tenant_id, user_id, execution_id):
    execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id,
                                                AgentExecution.tenant_id == tenant_id).first()
    if execution is None:
        raise HTTPException(404, "Execução não encontrada")
    authorize(db, tenant_id, user_id, execution.process_id)
    return execution


def execution_data(execution):
    return {"id": execution.id, "process_id": execution.process_id, "snapshot_id": execution.snapshot_id,
            "status": execution.status, "steps": execution.steps, "cursor": execution.cursor,
            "revision": execution.revision, "waiting_reason": execution.waiting_reason,
            "completed": execution.status == "completed"}


def legacy_step_result(db, execution, step):
    """Read-only UI/AgentResult projection; never an input to another agent."""
    job = db.query(AIJob).filter(AIJob.id == step.get("job_id"), AIJob.tenant_id == execution.tenant_id).first()
    return {"success": step["status"] == "completed", "data": job.result if job else {},
            "confidence": "medium", "ai_job_id": step.get("job_id"), "suggestions": [],
            "requires_review": bool(step.get("outputs")), "agent_name": step["agent"], "duration_ms": 0,
            "error": step.get("error") or (None if step["status"] == "completed" else step["status"])}


def _outputs_resolved(db, execution, step):
    latest = latest_objects(db, execution.tenant_id, execution.process_id)
    invalid = invalidate_dependents(db, execution.tenant_id, execution.process_id)
    for ref in step.get("outputs", []):
        row = latest.get(ref["id"])
        if row is None or row.id in invalid:
            return False
        review = last_review(db, row)
        if not review or review.action not in {"aprovar", "rejeitar", "nao_aplicavel"}:
            return False
    return True


def _audit_objects(agent, envelope):
    """Use the existing deterministic matrix, preserving all input identities."""
    from types import SimpleNamespace

    from app.services.inconsistency_matrix import build_matrix

    rows = []
    for observation in envelope.observations:
        attrs = observation.attributes
        rows.append(SimpleNamespace(id=observation.id, source_doc_type=attrs.object,
            field_name=attrs.predicate, field_value=attrs.normalized if attrs.normalized is not None else attrs.literal,
            document_id=attrs.document_id, matricula_hint=attrs.subject,
            status="pendente", tipo_observacao=None, atributos=None))
    matrix = build_matrix(rows).matriz
    objects = []
    for line in matrix.get("linhas", []):
        if not line.get("fontes") or line.get("situacao") == "consistente":
            continue
        # References to the participating documents limit invalidation to this comparison.
        document_ids = {s.get("document_id") for s in line.get("fontes_detalhe", []) if s.get("document_id")}
        observations = [o for o in envelope.observations if o.attributes.document_id in document_ids]
        premises = [{"id": o.id, "version": o.version} for o in observations]
        # Presence/coverage checks depend on the inventory, including later new documents.
        if not premises or line["item"] in {"sigef_georreferenciamento", "documentos_solicitados"}:
            premises += [{"id": o.id, "version": o.version} for o in envelope.derivations if o.id == "case:material"]
        if not premises:
            continue
        # Recommendations/classifications are reviewable conclusions, not raw
        # comparison inputs. Copying the full matrix row here leaked rejected
        # recommendation text back into the next diagnostic through derivations.
        comparison = {key: line[key] for key in ("item", "label", "fontes", "fontes_detalhe") if key in line}
        assessment = {key: line[key] for key in ("situacao", "acao_recomendada", "destino", "profundidade", "subtipo") if key in line}
        derivation = EvidenceObject(id=f"comparison:{uuid4().hex}", version=1, kind="derivacao",
            origin="auditor_imovel", premises=premises,
            attributes={"method": "inconsistency_matrix", "method_version": "069.2", "normalized": comparison},
            limits=["Classificação documental do comparador legado; não é avaliação jurídica ou espacial"])
        objects.append(derivation)
        objects.append(EvidenceObject(id=f"assessment:{uuid4().hex}", version=1, kind="conclusao",
            origin="auditor_imovel", statement=line.get("acao_recomendada") or line.get("label"),
            conclusion_class="lacuna" if line.get("situacao") == "atencao" else "divergencia",
            premises=[{"id": derivation.id, "version": 1}],
            limits=["Comparação documental; não comprova irregularidade, obrigação ou serviço"],
            attributes={"method": "inconsistency_matrix", "method_version": "069.2", "normalized": assessment}))
    return objects


def run_step(db, execution, step, user_id):
    from app.agents import AgentContext, AgentRegistry
    from app.core.ai_gateway import check_tenant_cost_limit, check_tenant_monthly_budget

    envelope = build_envelope(db, execution.tenant_id, user_id, execution.process_id, execution.snapshot_id)
    metadata = {"uf": envelope.case.get("uf"), "demand_type": envelope.objective}
    manifest = capability_manifest(step["agent"], metadata)
    manifest_hash = canonical_hash(manifest)
    from sqlalchemy.dialects.postgresql import insert
    db.execute(insert(Manifesto).values(id=manifest_hash, content=manifest).on_conflict_do_nothing(index_elements=["id"]))
    envelope.manifest = manifest
    ctx = AgentContext(tenant_id=execution.tenant_id, user_id=user_id,
        process_id=execution.process_id, session=db, metadata=metadata)
    agent = AgentRegistry.create(step["agent"], ctx)
    job = AIJob(tenant_id=execution.tenant_id, created_by_user_id=user_id,
        entity_type="process", entity_id=execution.process_id, agent_name=step["agent"],
        job_type=agent.job_type, status=AIJobStatus.running, chain_trace_id=execution.id,
        started_at=datetime.now(UTC), input_payload={"contract_version": "069.1",
            "context": envelope.model_dump(mode="json"), "context_hash": envelope.semantic_hash,
            "manifest": manifest, "manifesto_hash": manifest_hash, "attempts": []})
    db.add(job)
    db.flush()
    step["job_id"] = job.id
    if manifest["status"] != "available":
        job.status = AIJobStatus.failed
        job.error = "CAPACIDADE INSUFICIENTE" if manifest["status"] == "capacidade_insuficiente" else "AGENTE DESATIVADO"
        job.result = {"status": manifest["status"], "manifest": manifest}
        job.finished_at = datetime.now(UTC)
        step["status"] = manifest["status"]
        return
    if step["agent"] == "extrator":
        from app.services.entrada_semantica import executar_extracao
        check_tenant_cost_limit(execution.tenant_id, db)
        check_tenant_monthly_budget(execution.tenant_id, db)
        attempts = []
        def record(response, label):
            attempts.append({"label": label, "model": response.model_used, "provider": response.provider,
                "tokens_in": response.tokens_in, "tokens_out": response.tokens_out, "cost_usd": response.cost_usd})
        result = executar_extracao(ctx, on_response=record)
        job.tokens_in = sum(a["tokens_in"] for a in attempts)
        job.tokens_out = sum(a["tokens_out"] for a in attempts)
        job.cost_usd = sum(a["cost_usd"] for a in attempts)
        job.model_used = ",".join(sorted({a["model"] for a in attempts}))
        job.input_payload = {**job.input_payload, "attempts": attempts}
        job.result = result
        job.status = AIJobStatus.completed
        job.finished_at = datetime.now(UTC)
        step.update(status="completed", outputs=[])
        db.flush()
        return
    if step["agent"] == "auditor_imovel":
        objects = _audit_objects(agent, envelope)
    else:
        # Preserve the existing responsibility's base prompt; the envelope is the sole case input.
        base_slug = agent.prompt_slugs[0] if agent.prompt_slugs else None
        from app.services.prompt_service import get_active_prompt
        template = get_active_prompt(base_slug, db, tenant_id=execution.tenant_id) if base_slug else None
        base_prompt = template.content if template else agent._fallback_prompts().get(base_slug, "")
        skills = "\n\n".join(s["content"] + "\n" + "\n".join(a["content"] for a in s["attachments"])
                              for s in manifest["applied"])
        system = base_prompt + "\n\n" + skills + (
            "\nCONTRATO 069: produza somente JSON com a chave objects (lista). "
            "Cada item segue o schema a seguir. Cite premissas somente pelos ids/versões fornecidos. "
            "Não infira ausência de uma lacuna. Não crie fontes primárias, ids de documentos, revisores ou datas. "
            "Regras/normas mencionadas na skill são orientação histórica, não prova de aplicabilidade. "
            "Use apenas conclusões autorizadas do envelope. O sistema atribui identidade às novas conclusões.\n"
        ) + json.dumps(EvidenceObject.model_json_schema(), ensure_ascii=False)
        prompt = envelope.model_dump_json()
        parameters = {"agent_name": step["agent"]}
        record = {"base_prompt": {"slug": base_slug, "hash": canonical_hash(base_prompt), "content": base_prompt,
                                  "version": template.version if template else canonical_hash(base_prompt),
                                  "origin": "database" if template else "code_fallback"},
                  "system": system, "user": prompt, "system_hash": canonical_hash(system),
                  "user_hash": canonical_hash(prompt), "parameters": parameters}
        job.input_payload = {**job.input_payload, **record}
        # The existing gateway preserves cost limits and provider fallback.
        from app.core.ai_gateway import complete
        check_tenant_cost_limit(execution.tenant_id, db)
        check_tenant_monthly_budget(execution.tenant_id, db)
        from app.core.ai_trace import attempt_sink
        attempts = []
        token = attempt_sink.set(attempts)
        try:
            response = complete(prompt, system=system, user_preferences=agent._resolve_user_ai_preferences(), **parameters)
        finally:
            attempt_sink.reset(token)
            job.input_payload = {**job.input_payload, "attempts": attempts}
        job.model_used, job.provider = response.model_used, response.provider
        job.tokens_in, job.tokens_out, job.cost_usd = response.tokens_in, response.tokens_out, response.cost_usd
        job.raw_output = response.content
        # Tests may control the gateway response; retain an explicit record of that boundary.
        if not attempts:
            job.input_payload = {**job.input_payload, "attempts": [{"model": response.model_used,
                "provider": response.provider, "cost": response.cost_usd, "scope": "gateway_response_only"}]}
        parsed = json.loads(response.content)
        objects = TypeAdapter(list[EvidenceObject]).validate_python(parsed["objects"])
        if any(obj.kind != "conclusao" for obj in objects):
            raise ValueError("Síntese de agente só pode propor conclusões; não criar fontes primárias")
        objects = [obj.model_copy(update={"id": f"conclusion:{uuid4().hex}", "version": 1,
                                           "origin": step["agent"]}) for obj in objects]
    refs = []
    permitted = {(o.id, o.version) for group in [envelope.sources, envelope.observations,
                                                envelope.derivations, envelope.conclusions] for o in group}
    with db.begin_nested():
        for obj in objects:
            references = obj.premises + obj.norms + obj.rules
            if obj.knowledge.verification:
                references += [obj.knowledge.verification.source, obj.knowledge.verification.preserved_response]
            if obj.knowledge.examined:
                references += obj.knowledge.examined.material
            if any((p.id, p.version) not in permitted for p in references):
                raise ValueError("Premissa fora do contexto autorizado")
            persist_object(db, execution.tenant_id, execution.process_id, obj, agent=step["agent"], job_id=job.id)
            permitted.add((obj.id, obj.version))
            if obj.kind == "conclusao":
                refs.append({"id": obj.id, "version": obj.version})
    job.result = {"objects": [obj.model_dump(mode="json") for obj in objects],
                  "afirmacoes": [obj.as_assertion().model_dump(mode="json") for obj in objects if obj.kind == "conclusao"],
                  "requires_review": bool(objects), "status": "awaiting_review" if objects else "completed"}
    job.status = AIJobStatus.completed
    job.finished_at = datetime.now(UTC)
    step.update(status="completed", outputs=refs)
    db.flush()


def resume_execution(db, tenant_id, user_id, execution_id, expected_revision=None, *, recompute_stale=False):
    from app.core.ai_gateway import AIGatewayError
    execution = get_execution(db, tenant_id, user_id, execution_id)
    lock_case(db, tenant_id, execution.process_id, wait=False)
    db.refresh(execution)
    if expected_revision is not None and execution.revision != expected_revision:
        raise HTTPException(409, "Execução atualizada por outra sessão")
    # Refresh live evidence versions before applying the gate to the persisted snapshot.
    previous_snapshot = db.query(CaseSnapshot).filter(CaseSnapshot.id == execution.snapshot_id,
        CaseSnapshot.tenant_id == tenant_id, CaseSnapshot.process_id == execution.process_id).one()
    current_snapshot = capture_snapshot(db, tenant_id, user_id, execution.process_id,
                                        reference_date=previous_snapshot.content["reference_date"])
    # Jobs retain their immutable original snapshot. Only unexecuted steps use the
    # next snapshot, so a corrected observation cannot be reintroduced on resume.
    execution.snapshot_id = current_snapshot.id
    registrar_snapshot(db, execution, current_snapshot.id)
    if execution.status == "completed" and all(_outputs_resolved(db, execution, s) for s in execution.steps):
        return execution
    steps = [dict(s) for s in execution.steps]
    if recompute_stale:
        latest = latest_objects(db, tenant_id, execution.process_id)
        invalid = invalidate_dependents(db, tenant_id, execution.process_id)
        for step in steps:
            if any(latest.get(ref["id"]) and latest[ref["id"]].id in invalid for ref in step.get("outputs", [])):
                previous = {k: v for k, v in step.items() if k != "history"}
                step["history"] = [*step.get("history", []), previous]
                step.update(status="pending", outputs=[], job_id=None)
    for step in steps:
        if step["status"] == "completed":
            continue
        if step["agent"] not in ACTIVE_AGENTS:
            step["status"] = "agente_desativado"
            continue
        waiting = []
        for parent in steps:
            if parent["agent"] not in step["depends_on"]:
                continue
            if parent["status"] != "completed" or not _outputs_resolved(db, execution, parent):
                waiting.append(parent["agent"])
        if waiting:
            step.update(status="awaiting_review", waiting_for=waiting)
            continue
        try:
            run_step(db, execution, step, user_id)
        except (ValueError, TypeError, KeyError, HTTPException, AIGatewayError) as exc:
            message = getattr(exc, "detail", None) or getattr(exc, "message", None) or str(exc)
            step.update(status="failed", error=message)
            if step.get("job_id"):
                job = db.query(AIJob).filter(AIJob.id == step["job_id"], AIJob.tenant_id == tenant_id).one()
                job.status = AIJobStatus.failed
                job.error = message
                job.result = {"status": "falha_de_verificacao", "parse_error": message}
                job.finished_at = datetime.now(UTC)
    execution.steps = steps
    execution.cursor = next((i for i, s in enumerate(steps) if s["status"] != "completed"), len(steps))
    execution.status = "completed" if all(s["status"] == "completed" and _outputs_resolved(db, execution, s) for s in steps) else (
        "capacidade_insuficiente" if any(s["status"] == "capacidade_insuficiente" for s in steps) else
        "failed" if any(s["status"] == "failed" for s in steps) else "awaiting_review")
    execution.waiting_reason = None if execution.status == "completed" else "Passos obrigatórios pendentes; consulte dependências"
    execution.revision += 1
    db.flush()
    return execution
