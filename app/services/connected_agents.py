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
    # ADR-074 §1 (ruptura 4): a cadeia comercial parte da Rota validada. O diagnóstico
    # é entrada da Rota, não do orçamento; rodá-lo de novo aqui prendia o orçamento
    # atrás de uma revisão que nada tem a ver com o preço.
    "gerar_proposta": ["redator", "orcamento"],
    "gerar_documento": ["redator"],
    "analise_regulatoria": ["legislacao"],
    "enquadramento_regulatorio": ["extrator", "legislacao"],
}
# Reading, comparison and legal retrieval do not depend on an unreviewed conclusion.
# Synthesis/commercial steps wait only for the conclusions they require.
DEPENDENCIES = {"diagnostico": ["auditor_imovel", "legislacao"], "orcamento": ["redator"]}


def start_execution(db, tenant_id, user_id, process_id, name, key=None, documento_id=None):
    """``documento_id`` (dívida #279) restringe o passo do extrator a um documento do caso.

    Fica gravado no passo da execução persistida, então sobrevive a uma retomada.
    Sem ele, o extrator lê o caso inteiro, como sempre.
    """
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
        chain_name=name, steps=[{"agent": n, "status": "pending", "depends_on": DEPENDENCIES.get(n, []),
                                 **({"document_id": documento_id} if documento_id and n == "extrator" else {})}
                                for n in names])
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
        if "artefato" in ref:
            # ADR-074: redação e orçamento são artefatos versionados, não conclusões.
            from app.services.comercial.cadeia import artefato_resolvido
            if not artefato_resolvido(db, tenant_id=execution.tenant_id,
                                      process_id=execution.process_id, ref=ref):
                return False
            continue
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
    metadata = {"uf": envelope.case.get("uf"), "demand_type": envelope.objective, "chain": execution.chain_name}
    if step.get("document_id"):
        metadata["document_id"] = step["document_id"]  # dívida #279: leitura de um documento só
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
    from app.services.comercial.cadeia import AGENTES_COMERCIAIS
    if step["agent"] in AGENTES_COMERCIAIS:
        from app.services.comercial.cadeia import executar_passo
        outputs, result = executar_passo(db, agent=step["agent"], tenant_id=execution.tenant_id,
                                         process_id=execution.process_id, user_id=user_id)
        job.result = result
        job.status = AIJobStatus.completed
        job.finished_at = datetime.now(UTC)
        step.update(status="completed", outputs=outputs)
        db.flush()
        return
    if step["agent"] == "extrator":
        from app.core.ai_trace import attempt_sink
        from app.services.entrada_semantica import executar_extracao
        check_tenant_cost_limit(execution.tenant_id, db)
        check_tenant_monthly_budget(execution.tenant_id, db)
        attempts = []
        provider_attempts = []
        def record(response, label):
            attempts.append({"label": label, "model": response.model_used, "provider": response.provider,
                "tokens_in": response.tokens_in, "tokens_out": response.tokens_out, "cost_usd": response.cost_usd,
                "raw": response.content, "finish_reason": response.finish_reason})
        token = attempt_sink.set(provider_attempts)
        from app.core.ai_trace import orcamento_do_job
        from app.core.config import settings
        try:
            with orcamento_do_job(settings.teto_de_custo_por_job("extrator"), job_id=job.id,
                                  agente="extrator") as orcamento:
                result = executar_extracao(ctx, on_response=record, ai_job_id=job.id)
        finally:
            # Validation failure must retain the paid response and actual provider attempts.
            attempt_sink.reset(token)
            job.tokens_in = sum(a["tokens_in"] for a in attempts)
            job.tokens_out = sum(a["tokens_out"] for a in attempts)
            # #272: o custo do job é o que foi PAGO — soma de cada chamada ao provedor,
            # inclusive a truncada que foi refeita e não aparece na resposta final.
            job.cost_usd = (orcamento["gasto_usd"] if orcamento["chamadas_pagas"]
                            else sum(a["cost_usd"] for a in attempts))
            job.model_used = ",".join(sorted({a["model"] for a in attempts})) or None
            job.provider = ",".join(sorted({a["provider"] for a in attempts})) or None
            job.raw_output = json.dumps(attempts, ensure_ascii=False) if attempts else None
            job.input_payload = {**job.input_payload, "attempts": provider_attempts,
                "extractions": [{k: v for k, v in a.items() if k != "raw"} for a in attempts],
                "orcamento": {k: orcamento[k] for k in ("limite_usd", "gasto_usd", "chamadas_pagas", "sem_custo")}}
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
        # ADR-080: the diagnosis has a contract base prompt — the legacy one asked for another
        # format and won over the contract (job 201, #25 in dev).
        from app.services import diagnostico_contrato
        base_slug = agent.prompt_slugs[0] if agent.prompt_slugs else None
        template = None
        if step["agent"] == "diagnostico":
            base_record = diagnostico_contrato.prompt_base_registro()
            base_prompt = base_record["content"]
        else:
            from app.services.prompt_service import get_active_prompt
            template = get_active_prompt(base_slug, db, tenant_id=execution.tenant_id) if base_slug else None
            base_prompt = template.content if template else agent._fallback_prompts().get(base_slug, "")
            base_record = {"slug": base_slug, "hash": canonical_hash(base_prompt), "content": base_prompt,
                           "version": template.version if template else canonical_hash(base_prompt),
                           "origin": "database" if template else "code_fallback"}
        skills = "\n\n".join(s["content"] + "\n" + "\n".join(a["content"] for a in s["attachments"])
                              for s in manifest["applied"])
        system = base_prompt + "\n\n" + skills + (
            "\nCONTRATO 069: produza somente JSON com a chave objects (lista). "
            "Cada item segue o schema a seguir. Cite premissas somente pelos ids/versões fornecidos. "
            "Não infira ausência de uma lacuna. Não crie fontes primárias, ids de documentos, revisores ou datas. "
            "Regras/normas mencionadas na skill são orientação histórica, não prova de aplicabilidade. "
            "Use apenas conclusões autorizadas do envelope. O sistema atribui identidade às novas conclusões.\n"
        ) + json.dumps(diagnostico_contrato.SCHEMA_AFIRMACAO if step["agent"] == "diagnostico"
                       else EvidenceObject.model_json_schema(), ensure_ascii=False)
        prompt = envelope.model_dump_json()
        from app.core.config import settings as _settings
        # Each agent's own cap per call (the legacy agents passed it; this path had dropped it and
        # the #23 diagnosis was stopped at the global 0.10 cap). The job-wide cap stays below.
        parameters = {"agent_name": step["agent"],
                      "max_cost_override_usd": _settings.teto_de_custo_por_job(step["agent"])}
        if step["agent"] == "diagnostico":
            parameters["max_tokens"] = _settings.AI_DIAGNOSTICO_MAX_TOKENS
        record = {"base_prompt": base_record,
                  "system": system, "user": prompt, "system_hash": canonical_hash(system),
                  "user_hash": canonical_hash(prompt), "parameters": parameters}
        job.input_payload = {**job.input_payload, **record}
        # The existing gateway preserves cost limits and provider fallback.
        from app.core.ai_gateway import complete
        check_tenant_cost_limit(execution.tenant_id, db)
        check_tenant_monthly_budget(execution.tenant_id, db)
        from app.core.ai_trace import attempt_sink, orcamento_do_job
        from app.core.config import settings
        attempts = []
        pagas = []  # replies that came back (paid), in order
        orcamento = None
        token = attempt_sink.set(attempts)
        try:
            with orcamento_do_job(settings.teto_de_custo_por_job(step["agent"]), job_id=job.id,
                                  agente=step["agent"]) as orcamento:
                response = complete(prompt, system=system, user_preferences=agent._resolve_user_ai_preferences(),
                                    **parameters)
                pagas.append(response)
                sintaxe = diagnostico_contrato.erro_de_sintaxe(response.content) \
                    if step["agent"] == "diagnostico" else None
                if sintaxe:
                    # ADR-080: a reply that is not JSON gets ONE new call (transport, not content;
                    # admission rules never retry). Both replies stay on the job; the job-wide
                    # cap covers both calls. Measured: #23 in dev, a missing "]" in limits.
                    invalida = {"raw": response.content, "erro": sintaxe, "model": response.model_used,
                                "tokens_in": response.tokens_in, "tokens_out": response.tokens_out,
                                "cost_usd": response.cost_usd}
                    job.input_payload = {**job.input_payload, "resposta_sem_sintaxe": invalida}
                    response = complete(prompt, system=system,
                                        user_preferences=agent._resolve_user_ai_preferences(), **parameters)
                    pagas.append(response)
        finally:
            attempt_sink.reset(token)
            if orcamento is not None:
                job.input_payload = {**job.input_payload, "attempts": attempts,
                    "orcamento": {k: orcamento[k] for k in ("limite_usd", "gasto_usd", "chamadas_pagas", "sem_custo")}}
            # #272: what was PAID stays on the job even when a later call raises (budget, cap,
            # truncation) — a discarded or barred reply is still tenant spend.
            if pagas:
                job.model_used, job.provider = pagas[-1].model_used, pagas[-1].provider
                job.tokens_in = sum(r.tokens_in or 0 for r in pagas)
                job.tokens_out = sum(r.tokens_out or 0 for r in pagas)
            if orcamento is not None and orcamento["chamadas_pagas"]:
                job.cost_usd = orcamento["gasto_usd"]
            elif pagas:
                job.cost_usd = sum(r.cost_usd or 0 for r in pagas)
        job.raw_output = response.content
        # Tests may control the gateway response; retain an explicit record of that boundary.
        if not attempts:
            job.input_payload = {**job.input_payload, "attempts": [{"model": response.model_used,
                "provider": response.provider, "cost": response.cost_usd, "scope": "gateway_response_only"}]}
        conteudo = diagnostico_contrato.sem_cerca(response.content) if step["agent"] == "diagnostico" \
            else response.content
        parsed = json.loads(conteudo)
        fora_do_contrato = diagnostico_contrato.faltou_objects(parsed)
        if fora_do_contrato:
            raise ValueError(fora_do_contrato)
        objects = (diagnostico_contrato.para_objetos(parsed["objects"]) if step["agent"] == "diagnostico"
                   else TypeAdapter(list[EvidenceObject]).validate_python(parsed["objects"]))
        if any(obj.kind != "conclusao" for obj in objects):
            raise ValueError("Síntese de agente só pode propor conclusões; não criar fontes primárias")
        if step["agent"] == "diagnostico":
            recusadas = diagnostico_contrato.recusas(objects, envelope)
            if recusadas:
                raise ValueError("Afirmação do diagnóstico recusada (ADR-080): " + "; ".join(recusadas))
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
        from app.services.comercial.cadeia import artefato_desatualizado
        for step in steps:
            if any(artefato_desatualizado(db, tenant_id=tenant_id, process_id=execution.process_id, ref=ref)
                   if "artefato" in ref else (latest.get(ref["id"]) and latest[ref["id"]].id in invalid)
                   for ref in step.get("outputs", [])):
                previous = {k: v for k, v in step.items() if k != "history"}
                step["history"] = [*step.get("history", []), previous]
                step.update(status="pending", outputs=[], job_id=None)
        # A step rerun invalidates what was built on it (ADR-074: new escopo => new orçamento).
        reset = {s["agent"] for s in steps if s["status"] == "pending"}
        for step in steps:
            if step["status"] == "completed" and reset & set(step.get("depends_on", [])):
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
