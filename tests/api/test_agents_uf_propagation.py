"""Fase 0 (gap-analysis Ficha 07, item 7) — dívida 44b: a chain de agentes
não propagava `uf` a `ctx.metadata`, então a skill jurídica de UF
(`applies_to: {uf: [...]}`) nunca era injetada quando o caller não setava o
metadado explicitamente. `_build_context` agora deriva `uf` do
`Property.state` do processo quando o caller não o fornece.

Teste com UF≠GO (Acre, corpus já ingerido — Sprint corpus Acre 2026-07-04).
"""

import pytest
from fastapi import HTTPException

from app.api.v1.agents import _build_context
from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.evidence import build_envelope


def _setup(db_session, *, state: str | None):
    tenant = Tenant(name="UF Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="uf@example.com", full_name="Consultor",
                hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email="uf.c@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda", state=state)
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                    title="Caso", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, user, proc


class TestDerivaUf:
    def test_deriva_uf_ac_do_imovel_do_processo(self, db_session) -> None:
        tenant, user, proc = _setup(db_session, state="AC")
        db_session.commit()
        assert build_envelope(db_session, tenant.id, user.id, proc.id).case["uf"] == "AC"

    def test_sem_process_id_nao_constroi_contexto_autorizado(self, db_session) -> None:
        tenant, user, _proc = _setup(db_session, state="AC")
        db_session.commit()
        with pytest.raises(HTTPException) as error:
            build_envelope(db_session, tenant.id, user.id, None)
        assert error.value.status_code == 404

    def test_property_sem_state_retorna_none(self, db_session) -> None:
        tenant, user, proc = _setup(db_session, state=None)
        db_session.commit()
        assert build_envelope(db_session, tenant.id, user.id, proc.id).case["uf"] is None

    def test_isolamento_por_tenant(self, db_session) -> None:
        """Um processo de outro tenant não vaza o UF."""
        tenant, user, proc = _setup(db_session, state="AC")
        db_session.commit()
        outro_tenant = Tenant(name="Outro Tenant")
        db_session.add(outro_tenant)
        db_session.commit()
        with pytest.raises(HTTPException) as error:
            build_envelope(db_session, outro_tenant.id, user.id, proc.id)
        assert error.value.status_code == 404


class TestBuildContextPropagaUf:
    def test_metadata_sem_uf_recebe_uf_derivado(self, db_session) -> None:
        tenant, user, proc = _setup(db_session, state="AC")
        db_session.commit()
        ctx = _build_context(db_session, user, proc.id, {})
        assert ctx.metadata["uf"] == "AC"

    def test_metadata_nao_sobrescreve_uf_autorizada_do_caso(self, db_session) -> None:
        """ADR-069: payload não é autoridade sobre cadastro/documentos do caso."""
        tenant, user, proc = _setup(db_session, state="AC")
        db_session.commit()
        ctx = _build_context(db_session, user, proc.id, {"uf": "GO"})
        assert ctx.metadata["uf"] == "AC"

    def test_sem_property_state_metadata_fica_sem_uf(self, db_session) -> None:
        tenant, user, proc = _setup(db_session, state=None)
        db_session.commit()
        ctx = _build_context(db_session, user, proc.id, {})
        assert ctx.metadata["uf"] is None
