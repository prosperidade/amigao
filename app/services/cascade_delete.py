"""
Cascade delete — fix/upload-checklist-binding

Exclusão controlada em cascata para clientes e imóveis. Necessária porque:

- A taxonomia de FKs mistura RESTRICT (process.client_id, property.client_id,
  contract.client_id, proposal.client_id) com CASCADE (document.process_id,
  process_checklist) e SET NULL (document.client_id, document.property_id,
  process.property_id), então um DELETE direto no banco falha por integridade
  em alguns caminhos e produz órfãos em outros.
- A consultora precisa apagar clientes e imóveis pra resubir casos de teste,
  e a UI exige um preview com contagens exatas (X imóveis, Y casos, Z
  documentos) antes de confirmar.
- LGPD/auditoria: a exclusão precisa ser registrada com hash-chain em AuditLog
  e nunca pode tocar dados de outro cliente.

Tudo aqui é hard delete. O `Document.deleted_at` (soft delete) só é usado pelo
endpoint /documents/{id} DELETE, não por esta cascata.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.checklist_template import ProcessChecklist
from app.models.client import Client
from app.models.contract import Contract
from app.models.document import Document
from app.models.process import Process
from app.models.property import Property
from app.models.proposal import Proposal
from app.services.audit_hash import stamp_audit_hash

# ---------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------

@dataclass
class CascadePreview:
    """Contagem de entidades que serão removidas em cascata."""
    properties: int
    processes: int
    documents: int
    checklists: int
    contracts: int
    proposals: int

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------

def _collect_client_scope(
    db: Session,
    tenant_id: int,
    client_id: int,
) -> tuple[list[int], list[int], list[int]]:
    """Devolve (property_ids, process_ids, document_ids) do cliente.

    Documentos só entram se a relação (Document.client_id, process_id ou
    property_id) couber dentro do escopo do cliente — nunca tocamos doc de
    outro cliente.
    """
    prop_ids = [
        pid for (pid,) in db.query(Property.id)
        .filter(Property.client_id == client_id, Property.tenant_id == tenant_id)
        .all()
    ]
    proc_ids = [
        pid for (pid,) in db.query(Process.id)
        .filter(Process.client_id == client_id, Process.tenant_id == tenant_id)
        .all()
    ]
    doc_conds = [Document.client_id == client_id]
    if proc_ids:
        doc_conds.append(Document.process_id.in_(proc_ids))
    if prop_ids:
        doc_conds.append(Document.property_id.in_(prop_ids))
    doc_ids = [
        did for (did,) in db.query(Document.id)
        .filter(Document.tenant_id == tenant_id, or_(*doc_conds))
        .all()
    ]
    return prop_ids, proc_ids, doc_ids


def preview_client_cascade(
    db: Session,
    tenant_id: int,
    client_id: int,
) -> CascadePreview:
    """Conta o que cairia em cascata sem alterar o banco."""
    prop_ids, proc_ids, doc_ids = _collect_client_scope(db, tenant_id, client_id)

    checklists = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id.in_(proc_ids))
        .count()
        if proc_ids else 0
    )
    contracts = (
        db.query(Contract)
        .filter(Contract.client_id == client_id, Contract.tenant_id == tenant_id)
        .count()
    )
    proposals = (
        db.query(Proposal)
        .filter(Proposal.client_id == client_id, Proposal.tenant_id == tenant_id)
        .count()
    )
    return CascadePreview(
        properties=len(prop_ids),
        processes=len(proc_ids),
        documents=len(doc_ids),
        checklists=checklists,
        contracts=contracts,
        proposals=proposals,
    )


def cascade_delete_client(
    db: Session,
    tenant_id: int,
    user_id: int,
    client_id: int,
) -> CascadePreview:
    """Apaga cliente + dependências em ordem segura. Registra audit_log."""
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.tenant_id == tenant_id)
        .first()
    )
    if client is None:
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    prop_ids, proc_ids, doc_ids = _collect_client_scope(db, tenant_id, client_id)
    preview = preview_client_cascade(db, tenant_id, client_id)
    client_name = client.full_name

    # 1. Documentos (hard delete; LGPD obriga registro e este endpoint é o
    # único que apaga o documento de verdade — o DELETE /documents/{id} faz
    # soft delete).
    if doc_ids:
        db.query(Document).filter(Document.id.in_(doc_ids)).delete(
            synchronize_session=False
        )

    # 2. Checklists (CASCADE via process_id, mas removemos explicitamente para
    # não depender da ordem dos triggers).
    if proc_ids:
        db.query(ProcessChecklist).filter(
            ProcessChecklist.process_id.in_(proc_ids)
        ).delete(synchronize_session=False)

    # 3. Processos (libera RESTRICT em Process.client_id).
    if proc_ids:
        db.query(Process).filter(
            Process.id.in_(proc_ids), Process.tenant_id == tenant_id
        ).delete(synchronize_session=False)

    # 4. Imóveis (libera RESTRICT em Property.client_id).
    if prop_ids:
        db.query(Property).filter(
            Property.id.in_(prop_ids), Property.tenant_id == tenant_id
        ).delete(synchronize_session=False)

    # 5. Contratos e propostas (RESTRICT em Contract.client_id / Proposal.client_id).
    db.query(Contract).filter(
        Contract.client_id == client_id, Contract.tenant_id == tenant_id
    ).delete(synchronize_session=False)
    db.query(Proposal).filter(
        Proposal.client_id == client_id, Proposal.tenant_id == tenant_id
    ).delete(synchronize_session=False)

    db.flush()

    # 6. Cliente.
    db.delete(client)
    db.flush()

    # 7. Audit log com hash-chain (LGPD).
    audit = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="client",
        entity_id=client_id,
        action="cascade_deleted",
        details=json.dumps(
            {"client_name": client_name, "cascade": preview.to_dict()},
            ensure_ascii=False,
        ),
    )
    db.add(audit)
    db.flush()
    stamp_audit_hash(db, audit)

    return preview


# ---------------------------------------------------------------------------
# Imóvel
# ---------------------------------------------------------------------------

def _collect_property_scope(
    db: Session,
    tenant_id: int,
    property_id: int,
) -> tuple[list[int], list[int]]:
    """Devolve (process_ids, document_ids) do imóvel."""
    proc_ids = [
        pid for (pid,) in db.query(Process.id)
        .filter(
            Process.property_id == property_id,
            Process.tenant_id == tenant_id,
        )
        .all()
    ]
    doc_conds = [Document.property_id == property_id]
    if proc_ids:
        doc_conds.append(Document.process_id.in_(proc_ids))
    doc_ids = [
        did for (did,) in db.query(Document.id)
        .filter(Document.tenant_id == tenant_id, or_(*doc_conds))
        .all()
    ]
    return proc_ids, doc_ids


def preview_property_cascade(
    db: Session,
    tenant_id: int,
    property_id: int,
) -> CascadePreview:
    proc_ids, doc_ids = _collect_property_scope(db, tenant_id, property_id)
    checklists = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id.in_(proc_ids))
        .count()
        if proc_ids else 0
    )
    return CascadePreview(
        properties=1,
        processes=len(proc_ids),
        documents=len(doc_ids),
        checklists=checklists,
        contracts=0,
        proposals=0,
    )


def cascade_delete_property(
    db: Session,
    tenant_id: int,
    user_id: int,
    property_id: int,
    *,
    client_id: Optional[int] = None,
) -> CascadePreview:
    """Apaga imóvel + processos + documentos vinculados em ordem segura."""
    prop = (
        db.query(Property)
        .filter(Property.id == property_id, Property.tenant_id == tenant_id)
        .first()
    )
    if prop is None:
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(status_code=404, detail="Imóvel não encontrado")
    if client_id is not None and prop.client_id != client_id:
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(status_code=404, detail="Imóvel não encontrado")

    proc_ids, doc_ids = _collect_property_scope(db, tenant_id, property_id)
    preview = preview_property_cascade(db, tenant_id, property_id)
    prop_name = prop.name

    if doc_ids:
        db.query(Document).filter(Document.id.in_(doc_ids)).delete(
            synchronize_session=False
        )
    if proc_ids:
        db.query(ProcessChecklist).filter(
            ProcessChecklist.process_id.in_(proc_ids)
        ).delete(synchronize_session=False)
        db.query(Process).filter(
            Process.id.in_(proc_ids), Process.tenant_id == tenant_id
        ).delete(synchronize_session=False)

    db.flush()
    db.delete(prop)
    db.flush()

    audit = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="property",
        entity_id=property_id,
        action="cascade_deleted",
        details=json.dumps(
            {"property_name": prop_name, "cascade": preview.to_dict()},
            ensure_ascii=False,
        ),
    )
    db.add(audit)
    db.flush()
    stamp_audit_hash(db, audit)

    return preview
