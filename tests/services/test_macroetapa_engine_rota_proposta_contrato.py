"""Fase 0 (item 9 do adendo) — ``has_rota_validada``/``has_proposal_accepted``/
``has_contract_signed`` detectam se Rota/Proposal/Contract já chegaram ao
estado que a Ficha 07 exige pra sair de E5/E6/E7, respectivamente. Espelham
``has_consolidated`` (mesmo arquivo, item 2).
"""

from app.models.client import Client, ClientStatus, ClientType
from app.models.contract import Contract, ContractStatus
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.proposal import Proposal, ProposalStatus
from app.models.rota import Rota, RotaStatus
from app.models.tenant import Tenant
from app.services.macroetapa_engine import (
    has_contract_signed,
    has_proposal_accepted,
    has_rota_validada,
)


def _setup(db_session):
    tenant = Tenant(name="Rota/Proposta/Contrato Tenant")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email="rpc@example.com",
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
    return tenant, cli, proc


class TestHasRotaValidada:
    def test_sem_rota_retorna_false(self, db_session) -> None:
        tenant, _cli, proc = _setup(db_session)
        db_session.commit()
        assert has_rota_validada(db_session, tenant.id, proc.id) is False

    def test_rota_proposta_nao_conta(self, db_session) -> None:
        """Status `proposta` (recém-materializada) não satisfaz o gate."""
        tenant, _cli, proc = _setup(db_session)
        db_session.add(Rota(
            tenant_id=tenant.id, process_id=proc.id, demand_type="car",
            status=RotaStatus.proposta,
        ))
        db_session.commit()
        assert has_rota_validada(db_session, tenant.id, proc.id) is False

    def test_rota_validada_conta(self, db_session) -> None:
        tenant, _cli, proc = _setup(db_session)
        db_session.add(Rota(
            tenant_id=tenant.id, process_id=proc.id, demand_type="car",
            status=RotaStatus.validada,
        ))
        db_session.commit()
        assert has_rota_validada(db_session, tenant.id, proc.id) is True

    def test_rota_de_outro_processo_nao_conta(self, db_session) -> None:
        tenant, cli, proc = _setup(db_session)
        other_proc = Process(
            tenant_id=tenant.id, client_id=cli.id, property_id=proc.property_id,
            title="Outro caso", process_type="prad", status=ProcessStatus.triagem,
        )
        db_session.add(other_proc)
        db_session.flush()
        db_session.add(Rota(
            tenant_id=tenant.id, process_id=other_proc.id, demand_type="car",
            status=RotaStatus.validada,
        ))
        db_session.commit()
        assert has_rota_validada(db_session, tenant.id, proc.id) is False


class TestHasProposalAccepted:
    def test_sem_proposta_retorna_false(self, db_session) -> None:
        tenant, _cli, proc = _setup(db_session)
        db_session.commit()
        assert has_proposal_accepted(db_session, tenant.id, proc.id) is False

    def test_proposta_draft_nao_conta(self, db_session) -> None:
        tenant, cli, proc = _setup(db_session)
        db_session.add(Proposal(
            tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
            status=ProposalStatus.draft, title="Proposta", scope_items=[],
        ))
        db_session.commit()
        assert has_proposal_accepted(db_session, tenant.id, proc.id) is False

    def test_proposta_aceita_conta(self, db_session) -> None:
        tenant, cli, proc = _setup(db_session)
        db_session.add(Proposal(
            tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
            status=ProposalStatus.accepted, title="Proposta", scope_items=[],
        ))
        db_session.commit()
        assert has_proposal_accepted(db_session, tenant.id, proc.id) is True


class TestHasContractSigned:
    def test_sem_contrato_retorna_false(self, db_session) -> None:
        tenant, _cli, proc = _setup(db_session)
        db_session.commit()
        assert has_contract_signed(db_session, tenant.id, proc.id) is False

    def test_contrato_sem_signed_at_nao_conta(self, db_session) -> None:
        """Mesmo com `status=signed`, o gate lê `signed_at` — hoje nenhum
        fluxo escreve nenhum dos dois (item 9: lacuna aceita, Sprint 5)."""
        tenant, cli, proc = _setup(db_session)
        db_session.add(Contract(
            tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
            status=ContractStatus.signed, title="Contrato", signed_at=None,
        ))
        db_session.commit()
        assert has_contract_signed(db_session, tenant.id, proc.id) is False

    def test_contrato_com_signed_at_conta(self, db_session) -> None:
        from datetime import UTC, datetime

        tenant, cli, proc = _setup(db_session)
        db_session.add(Contract(
            tenant_id=tenant.id, process_id=proc.id, client_id=cli.id,
            status=ContractStatus.signed, title="Contrato",
            signed_at=datetime.now(UTC),
        ))
        db_session.commit()
        assert has_contract_signed(db_session, tenant.id, proc.id) is True
