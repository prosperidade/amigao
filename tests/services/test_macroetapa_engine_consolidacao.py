"""Fase 0 (gap-analysis Ficha 07, item 2) — ``has_consolidated`` detecta se a
Consolidação (Ficha 05) já rodou para um processo, via ``AuditLog(action="consolidar")``.
"""

import json

from app.models.audit_log import AuditLog
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.audit_hash import stamp_audit_hash
from app.services.macroetapa_engine import has_consolidated


def _setup(db_session):
    tenant = Tenant(name="Consolidacao Tenant")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email="cons@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                    title="Caso", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc


class TestHasConsolidated:
    def test_sem_audit_log_de_consolidacao_retorna_false(self, db_session) -> None:
        tenant, proc = _setup(db_session)
        db_session.commit()
        assert has_consolidated(db_session, tenant.id, proc.id) is False

    def test_com_audit_log_consolidar_retorna_true(self, db_session) -> None:
        tenant, proc = _setup(db_session)
        log = AuditLog(
            tenant_id=tenant.id, entity_type="process", entity_id=proc.id,
            action="consolidar", details=json.dumps({"campos_gravados": 3}),
        )
        db_session.add(log)
        db_session.flush()
        stamp_audit_hash(db_session, log)
        db_session.commit()
        assert has_consolidated(db_session, tenant.id, proc.id) is True

    def test_audit_log_de_outra_acao_nao_conta(self, db_session) -> None:
        """Só `action == "consolidar"` conta — `staging_decidir` (decisão de
        campo individual) não é a Consolidação em si."""
        tenant, proc = _setup(db_session)
        log = AuditLog(
            tenant_id=tenant.id, entity_type="process", entity_id=proc.id,
            action="staging_decidir", details=json.dumps({}),
        )
        db_session.add(log)
        db_session.flush()
        stamp_audit_hash(db_session, log)
        db_session.commit()
        assert has_consolidated(db_session, tenant.id, proc.id) is False

    def test_audit_log_de_outro_processo_nao_conta(self, db_session) -> None:
        """Isolamento por processo — consolidar o caso 1 não libera o caso 2."""
        tenant, proc = _setup(db_session)
        other_proc = Process(
            tenant_id=tenant.id, client_id=proc.client_id, property_id=proc.property_id,
            title="Outro caso", process_type="prad", status=ProcessStatus.triagem,
        )
        db_session.add(other_proc)
        db_session.flush()
        log = AuditLog(
            tenant_id=tenant.id, entity_type="process", entity_id=other_proc.id,
            action="consolidar", details=json.dumps({}),
        )
        db_session.add(log)
        db_session.flush()
        stamp_audit_hash(db_session, log)
        db_session.commit()
        assert has_consolidated(db_session, tenant.id, proc.id) is False
