"""Case-scoped evidence repository. The caller owns commit and rollback."""

from __future__ import annotations

from datetime import date
from time import monotonic, sleep
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.evidence import CaseSnapshot, EvidenceInvalidation, EvidenceReview, EvidenceVersion
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.process import Process
from app.models.property import Property
from app.models.user import User
from app.schemas.evidence import EvidenceObject, ExecutionEnvelope, ReviewRequest, canonical_hash


def authorize(db: Session, tenant_id: int, user_id: int | None, process_id: int):
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True)).first()
    case = db.query(Process).filter(Process.id == process_id, Process.tenant_id == tenant_id,
                                    Process.deleted_at.is_(None)).first()
    if user is None or case is None:
        raise HTTPException(404, "Caso não encontrado")
    return case


def lock_case(db: Session, tenant_id: int, process_id: int, *, wait: bool = True):
    # Transaction-scoped; protects an empty collection too (unlike row-only locks).
    key = int(canonical_hash(["evidence", tenant_id, process_id])[:15], 16)
    function = "pg_advisory_xact_lock" if wait else "pg_try_advisory_xact_lock"
    acquired = db.execute(text(f"SELECT {function}(:key)"), {"key": key}).scalar()
    if not wait:
        # A panel refresh also captures evidence. Brief contention with that read
        # must not reject a legitimate gesture; a running execution still gets 409.
        deadline = monotonic() + 1.0
        while not acquired and monotonic() < deadline:
            sleep(.05)
            acquired = db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}).scalar()
        if not acquired:
            raise HTTPException(409, "Execução ou revisão concorrente; recarregue o estado")


def versions(db, tenant_id, process_id):
    return db.query(EvidenceVersion).filter(EvidenceVersion.tenant_id == tenant_id,
                                           EvidenceVersion.process_id == process_id).order_by(EvidenceVersion.id).all()


def latest_objects(db, tenant_id, process_id):
    latest = {}
    for row in versions(db, tenant_id, process_id):
        if row.object_id not in latest or row.version > latest[row.object_id].version:
            latest[row.object_id] = row
    return latest


def last_review(db, row):
    return db.query(EvidenceReview).filter(EvidenceReview.evidence_id == row.id,
                                           EvidenceReview.tenant_id == row.tenant_id,
                                           EvidenceReview.process_id == row.process_id).order_by(EvidenceReview.revision.desc()).first()


def persist_object(db, tenant_id, process_id, obj: EvidenceObject, *, agent=None, job_id=None, source_record=None):
    if obj.attributes.document_id is not None:
        document = db.query(Document).filter(Document.id == obj.attributes.document_id,
            Document.tenant_id == tenant_id, Document.process_id == process_id).first()
        if document is None:
            raise HTTPException(422, "Documento fora do caso autorizado")
    existing = db.query(EvidenceVersion).filter(
        EvidenceVersion.tenant_id == tenant_id, EvidenceVersion.process_id == process_id,
        EvidenceVersion.object_id == obj.id, EvidenceVersion.version == obj.version,
    ).first()
    payload = obj.model_dump(mode="json")
    digest = canonical_hash(payload)
    if existing:
        if existing.content_hash != digest:
            raise HTTPException(409, "Versão imutável já existe com outro conteúdo")
        return existing
    # Every premise must be recoverable inside this case, never merely a claimed id.
    refs = list(obj.premises) + list(obj.norms) + list(obj.rules)
    verification_refs = []
    if obj.knowledge.verification:
        verification_refs = [obj.knowledge.verification.source, obj.knowledge.verification.preserved_response]
        refs += verification_refs
    if obj.knowledge.examined:
        refs += obj.knowledge.examined.material
    norm_texts = []
    for ref in refs:
        premise = db.query(EvidenceVersion).filter(
            EvidenceVersion.tenant_id == tenant_id, EvidenceVersion.process_id == process_id,
            EvidenceVersion.object_id == ref.id, EvidenceVersion.version == ref.version,
        ).first()
        if premise is None:
            raise HTTPException(422, "Premissa não recuperável neste caso")
        if ref in obj.norms:
            if premise.kind != "fonte_primaria":
                raise HTTPException(422, "Norma exige fonte primária recuperável")
            norm_texts.append(str(premise.content.get("attributes", {}).get("literal") or ""))
        if ref in verification_refs:
            if premise.kind != "fonte_primaria" or premise.content.get("origin") != "consulta":
                raise HTTPException(422, "Verificação exige registro de consulta primária")
            if ref == obj.knowledge.verification.source:
                record = premise.source_record or {}
                verification = obj.knowledge.verification
                if (record.get("status") != "success" or record.get("scope") != verification.scope or record.get("identifiers") != verification.identifiers
                    or record.get("consulted_at") != verification.consulted_at.isoformat()):
                    raise HTTPException(422, "Escopo, identificadores e data não correspondem à consulta preservada")
            if ref == obj.knowledge.verification.preserved_response and (premise.source_record or {}).get("response") is None:
                raise HTTPException(422, "Resposta da consulta não foi preservada")
    if obj.kind == "conclusao":
        from app.services.citation_evaluator import extract_citations, validate_citations
        citations = extract_citations(obj.statement or "")
        if not validate_citations(citations, norm_texts).valid:
            raise HTTPException(422, "Citação normativa sem fonte versionada no contexto")
    row = EvidenceVersion(tenant_id=tenant_id, process_id=process_id, object_id=obj.id,
                          version=obj.version, kind=obj.kind, content=payload, content_hash=digest,
                          agent_name=agent, job_id=job_id, source_record=source_record,
                          source_document_id=obj.attributes.document_id)
    db.add(row)
    db.flush()
    invalidate_dependents(db, tenant_id, process_id)
    return row


def object_dependencies(content):
    refs = content.get("premises", []) + content.get("norms", []) + content.get("rules", [])
    knowledge = content.get("knowledge") or {}
    if verification := knowledge.get("verification"):
        refs += [verification["source"], verification["preserved_response"]]
    if examined := knowledge.get("examined"):
        refs += examined["material"]
    return refs


def invalidate_dependents(db, tenant_id, process_id):
    """Transitive version invalidation; never edits a previous approval or stage."""
    latest = latest_objects(db, tenant_id, process_id)
    invalid = {r.evidence_id for r in db.query(EvidenceInvalidation).filter(
        EvidenceInvalidation.tenant_id == tenant_id, EvidenceInvalidation.process_id == process_id).all()}
    changed = True
    while changed:
        changed = False
        for row in latest.values():
            if row.id in invalid:
                continue
            broken = []
            dependencies = object_dependencies(row.content)
            for ref in dependencies:
                premise = latest.get(ref["id"])
                if premise is None or premise.version != ref["version"] or premise.id in invalid or (decision := last_review(db, premise)) and decision.action in {"rejeitar", "corrigir"}:
                    broken.append(ref)
            if broken:
                db.add(EvidenceInvalidation(tenant_id=tenant_id, process_id=process_id,
                                           evidence_id=row.id, reason={"changed_premises": broken}))
                invalid.add(row.id)
                changed = True
    db.flush()
    return invalid


def _capture(db, tenant_id, process_id, object_id, kind, content, source_record=None):
    latest = db.query(EvidenceVersion).filter(
        EvidenceVersion.tenant_id == tenant_id, EvidenceVersion.process_id == process_id,
        EvidenceVersion.object_id == object_id,
    ).order_by(EvidenceVersion.version.desc()).first()
    fingerprint = canonical_hash({"content": content, "source": source_record})
    if latest and (latest.source_record or {}).get("capture_hash") == fingerprint:
        return latest
    source_record = {**(source_record or {}), "capture_hash": fingerprint}
    version = latest.version if latest else 1
    obj = EvidenceObject(id=object_id, version=version, kind=kind, **content)
    if latest and (latest.content != obj.model_dump(mode="json") or latest.source_record != source_record):
        obj = obj.model_copy(update={"version": version + 1})
    return persist_object(db, tenant_id, process_id, obj, source_record=source_record)


def capture_snapshot(db, tenant_id, user_id, process_id, *, reference_date=None):
    case = authorize(db, tenant_id, user_id, process_id)
    lock_case(db, tenant_id, process_id)
    sources = []
    docs_by_id = {}
    documents = db.query(Document).filter(Document.tenant_id == tenant_id,
                                         Document.process_id == process_id, Document.deleted_at.is_(None)).order_by(Document.id).all()
    for doc in documents:
        origin = getattr(doc.source, "value", doc.source)
        if origin == "generated_ai":
            continue  # Generated reports cannot become a hidden route around review.
        from app.services.entrada_semantica import fonte_documental
        row = fonte_documental(db, doc)
        sources.append({"id": row.object_id, "version": row.version})
        docs_by_id[doc.id] = row
    observations = []
    for staging in db.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.tenant_id == tenant_id, ExtractedFieldStaging.process_id == process_id,
    ).order_by(ExtractedFieldStaging.id).all():
        if staging.observacao_ref is not None:
            row = db.query(EvidenceVersion).filter_by(id=staging.observacao_ref,
                tenant_id=tenant_id, process_id=process_id).one()
            observations.append({"id": row.object_id, "version": row.version})
            continue
        source = docs_by_id.get(staging.document_id)
        if not source:
            continue
        row = _capture(db, tenant_id, process_id, f"staging:{staging.id}", "observacao", {
            "origin": "extrator", "attributes": {
                "document_id": staging.document_id, "predicate": staging.field_name,
                "object": staging.source_doc_type,
                "subject": str(staging.matricula_hint) if staging.matricula_hint else None,
                "literal": staging.field_value, "normalized": staging.decided_value,
                "certainty": staging.confidence, "method": "staging",
            }, "premises": [{"id": source.object_id, "version": source.version}],
            "legacy_unverified": True,
        }, source_record={"staging_status": getattr(staging.status, "value", staging.status),
                          "decided_by": staging.decided_by_user_id,
                          "decided_at": str(staging.decided_at) if staging.decided_at else None})
        observations.append({"id": row.object_id, "version": row.version})
    # Durable observations are not limited to the legacy cadastral projection.
    captured = {ref["id"] for ref in observations}
    for row in latest_objects(db, tenant_id, process_id).values():
        if row.kind == "observacao" and row.object_id not in captured:
            observations.append({"id": row.object_id, "version": row.version})
    prop = db.query(Property).filter(Property.id == case.property_id, Property.tenant_id == tenant_id).first()
    uf = (prop.state or "").strip().upper() if prop else None
    valid_ufs = set(["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"])
    uf = uf if uf in valid_ufs else None
    official = getattr(case.demand_type, "value", case.demand_type)
    objective = official if official and official != "nao_identificado" else case.process_type
    case_data = {
        "id": case.id, "objective": objective,
        "objective_origin": "demanda_classificada" if objective == official else "tipo_sugerido_nao_promovido",
        "declared_description": case.description,
        "uf": uf, "uf_origin": f"property:{prop.id}" if uf else None,
        "property": {"id": prop.id, "name": prop.name, "state": uf, "municipality": prop.municipality,
                     "embargo_knowledge": "nao_determinado"} if prop else {},
    }
    cadastro = _capture(db, tenant_id, process_id, "case:declarations", "fonte_primaria",
                        {"origin": "cadastro_legado", "legacy_unverified": True}, source_record=case_data)
    sources.append({"id": cadastro.object_id, "version": cadastro.version})
    captured_sources = {ref["id"] for ref in sources}
    for row in latest_objects(db, tenant_id, process_id).values():
        if row.kind == "fonte_primaria" and row.object_id not in captured_sources and row.content.get("origin") in {"consulta", "cadastro_humano"}:
            sources.append({"id": row.object_id, "version": row.version})
    _capture(db, tenant_id, process_id, "case:material", "derivacao", {
        "origin": "document_inventory", "premises": sources,
        "attributes": {"method": "authorized_document_inventory", "method_version": "069.1",
                       "normalized": sources},
        "limits": ["Inventário dos documentos disponíveis; não demonstra inexistência de documento externo"],
    })
    content = {"case": case_data, "sources": sources, "observations": observations,
               "reference_date": str(reference_date or date.today())}
    digest = canonical_hash(content)
    snapshot = db.query(CaseSnapshot).filter(CaseSnapshot.tenant_id == tenant_id,
                                             CaseSnapshot.process_id == process_id,
                                             CaseSnapshot.content_hash == digest).first()
    if snapshot is None:
        snapshot = CaseSnapshot(id=uuid4().hex, tenant_id=tenant_id, process_id=process_id,
                                content_hash=digest, content=content)
        db.add(snapshot)
        db.flush()
    return snapshot


def build_envelope(db, tenant_id, user_id, process_id, snapshot_id=None):
    authorize(db, tenant_id, user_id, process_id)
    if snapshot_id:
        snapshot = db.query(CaseSnapshot).filter(CaseSnapshot.id == snapshot_id,
            CaseSnapshot.tenant_id == tenant_id, CaseSnapshot.process_id == process_id).first()
        if snapshot is None:
            raise HTTPException(404, "Snapshot não encontrado")
    else:
        snapshot = capture_snapshot(db, tenant_id, user_id, process_id)
    invalid = invalidate_dependents(db, tenant_id, process_id)
    rows = versions(db, tenant_id, process_id)
    indexed = {(r.object_id, r.version): r for r in rows}
    latest = latest_objects(db, tenant_id, process_id)
    envelope = ExecutionEnvelope(tenant_id=tenant_id, case_id=process_id,
        objective=snapshot.content["case"]["objective"], reference_date=snapshot.content["reference_date"],
        snapshot_id=snapshot.id, snapshot_hash=snapshot.content_hash, case=snapshot.content["case"])
    for name in ("sources", "observations"):
        for ref in snapshot.content[name]:
            row = indexed[(ref["id"], ref["version"])]
            review = last_review(db, row)
            legacy_decision = (row.source_record or {}).get("staging_status")
            envelope.review_states.append({"id": row.object_id, "version": row.version,
                "decision": review.action if review else legacy_decision or "proposta", "stale": row.id in invalid})
            if row.id in invalid or latest[row.object_id].version != row.version or (review and review.action in {"rejeitar", "corrigir"}) or (not review and legacy_decision == "rejeitado"):
                envelope.gaps.append({"id": row.object_id, "version": row.version, "reason": "premissa_indisponivel"})
                continue
            getattr(envelope, name).append(EvidenceObject.model_validate(row.content))
    uf_values = []
    for observation in envelope.observations:
        if observation.attributes.predicate not in {"uf", "state", "estado"}:
            continue
        value = observation.attributes.normalized or observation.attributes.literal
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, str) and value.strip():
            uf_values.append({"uf": value.strip().upper(), "source": observation.id})
    registered = envelope.case.get("uf")
    distinct_ufs = {v["uf"] for v in uf_values}
    if len(distinct_ufs) > 1 or (registered and any(v != registered for v in distinct_ufs)):
        envelope.conflicts.append({"predicate": "uf", "cadastro": registered, "documents": uf_values})
        envelope.case = {**envelope.case, "uf": None, "uf_origin": "conflitante"}
    elif not registered and len(distinct_ufs) == 1:
        # A documentary assertion remains qualified by its origin/review state.
        value = next(iter(distinct_ufs))
        if value in {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}:
            envelope.case = {**envelope.case, "uf": value, "uf_origin": uf_values}
    def allowed(row, seen=None):
        seen = set() if seen is None else seen
        if row.id in seen or row.id in invalid or latest[row.object_id].version != row.version:
            return False
        review = last_review(db, row)
        if review and review.action in {"rejeitar", "corrigir"}:
            return False
        if row.kind == "conclusao":
            if not review or review.action not in {"aprovar", "nao_aplicavel"}:
                return False
        for ref in object_dependencies(row.content):
            parent = indexed.get((ref["id"], ref["version"]))
            if parent is None or not allowed(parent, seen | {row.id}):
                return False
        return True
    for row in latest.values():
        if row.kind not in {"conclusao", "derivacao"}:
            continue
        if allowed(row):
            target = envelope.conclusions if row.kind == "conclusao" else envelope.derivations
            target.append(EvidenceObject.model_validate(row.content))
        else:
            # No rejected text, raw result, or summary in the effective context.
            envelope.gaps.append({"id": row.object_id, "version": row.version,
                                  "reason": "desatualizada" if row.id in invalid else "revisao_pendente_ou_rejeitada"})
    return envelope


def review_object(db, tenant_id, user_id, process_id, object_id, request: ReviewRequest):
    authorize(db, tenant_id, user_id, process_id)
    lock_case(db, tenant_id, process_id, wait=False)
    capture_snapshot(db, tenant_id, user_id, process_id)
    row = latest_objects(db, tenant_id, process_id).get(object_id)
    if row is None:
        raise HTTPException(404, "Conclusão não encontrada")
    previous = last_review(db, row)
    revision = previous.revision if previous else 0
    if row.version != request.expected_version or revision != request.expected_revision:
        raise HTTPException(409, "Versão ou revisão superada; recarregue antes de decidir")
    if row.kind not in {"conclusao", "observacao"}:
        raise HTTPException(422, "Objeto não revisável")
    obj = EvidenceObject.model_validate(row.content)
    if request.action == "corrigir":
        if request.correction is None or request.correction.kind != obj.kind:
            raise HTTPException(422, "Correção exige objeto do mesmo tipo")
        corrected = request.correction.model_copy(update={"id": obj.id, "version": obj.version + 1})
        corrected = EvidenceObject.model_validate(corrected.model_dump())
        new_row = persist_object(db, tenant_id, process_id, corrected, agent=row.agent_name, source_record=row.source_record)
    elif request.action in {"aprovar", "nao_aplicavel"}:
        invalid = invalidate_dependents(db, tenant_id, process_id)
        if row.id in invalid:
            raise HTTPException(409, "Premissas desatualizadas; crie nova versão")
        if obj.kind == "conclusao" and not obj.premises:
            raise HTTPException(422, "Conclusão sem premissas recuperáveis não pode ser aprovada")
        if request.action == "nao_aplicavel" and obj.knowledge.state != "nao_aplicavel":
            # An explicit authorized N/A decision creates a new approved version.
            # The old version and all prior approvals remain recoverable.
            db.add(EvidenceReview(tenant_id=tenant_id, process_id=process_id, evidence_id=row.id,
                revision=revision + 1, action="substituida_por_nao_aplicavel", author_id=user_id,
                justification=request.justification, premises=obj.model_dump(mode="json")["premises"]))
            data = obj.model_dump(mode="json")
            data.update(version=obj.version + 1, applicability="nao_aplicavel",
                        applicability_reason=request.justification,
                        knowledge={"state": "nao_aplicavel", "justification": request.justification})
            obj = EvidenceObject.model_validate(data)
            row = persist_object(db, tenant_id, process_id, obj, agent=row.agent_name, source_record=row.source_record)
            revision = 0
    db.add(EvidenceReview(tenant_id=tenant_id, process_id=process_id, evidence_id=row.id,
        revision=revision + 1, action=request.action, author_id=user_id,
        justification=request.justification, premises=obj.model_dump(mode="json")["premises"]))
    db.flush()
    invalidate_dependents(db, tenant_id, process_id)
    import json

    from app.models.audit_log import AuditLog
    from app.services.audit_hash import stamp_audit_hash
    audit = AuditLog(tenant_id=tenant_id, user_id=user_id, entity_type="evidence_version",
        entity_id=row.id, action="evidence_review", details=json.dumps({
            "object_id": obj.id, "version": obj.version, "action": request.action,
            "revision": revision + 1, "justification": request.justification,
            "premises": obj.model_dump(mode="json")["premises"],
        }, ensure_ascii=False))
    db.add(audit)
    stamp_audit_hash(db, audit)
    return {"id": obj.id, "version": new_row.version if request.action == "corrigir" else obj.version,
            "revision": 0 if request.action == "corrigir" else revision + 1,
            "status": "pendente" if request.action == "corrigir" else request.action}
