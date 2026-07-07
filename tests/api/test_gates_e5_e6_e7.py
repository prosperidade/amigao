"""Fase 0 (item 9 do adendo — adotado após review) — cobertura de integração
dos gates de saída da E5/E6/E7 contra o BD real (via `/can-advance`), no
mesmo padrão de `tests/api/test_ramo_e2.py`.

Os testes unitários (`tests/models/test_macroetapa_gate.py`) já cobrem
`can_advance_macroetapa`/`compute_macroetapa_state` isoladamente; faltava a
integração ponta a ponta (Rota/Proposal/Contract reais) — completada aqui.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.contract import Contract, ContractStatus
from app.models.macroetapa import Macroetapa, MacroetapaChecklist
from app.models.process import Process, ProcessStatus
from app.models.proposal import Proposal, ProposalStatus
from app.models.rota import Rota, RotaStatus
from app.models.tenant import Tenant
from app.models.user import User


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_process_at(db_session, *, email: str, macroetapa: Macroetapa) -> tuple[Tenant, User, Process]:
    tenant = Tenant(name=f"Gates Tenant {email}")
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    process = Process(tenant_id=tenant.id, client_id=cli.id, title="Caso",
                       process_type="prad", status=ProcessStatus.diagnostico,
                       macroetapa=macroetapa.value)
    db_session.add(process)
    db_session.flush()
    # Checklist da etapa a 100% — isola o teste no sinal do gate novo, não no checklist.
    db_session.add(MacroetapaChecklist(
        tenant_id=tenant.id, process_id=process.id, macroetapa=macroetapa.value,
        actions=[{"id": "x", "label": "x", "completed": True}], completion_pct=100.0,
    ))
    db_session.commit()
    return tenant, user, process


class TestGateE5RotaValidada:
    def test_sem_rota_validada_can_advance_false(self, client: TestClient, db_session):
        tenant, _user, process = _seed_process_at(
            db_session, email="e5semrota@example.com", macroetapa=Macroetapa.caminho_regulatorio,
        )
        headers = _login(client, "e5semrota@example.com")
        ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
        assert ca["can_advance"] is False
        assert any("rota" in b.lower() for b in ca["blockers"])

    def test_com_rota_validada_can_advance_true(self, client: TestClient, db_session):
        tenant, _user, process = _seed_process_at(
            db_session, email="e5comrota@example.com", macroetapa=Macroetapa.caminho_regulatorio,
        )
        db_session.add(Rota(
            tenant_id=tenant.id, process_id=process.id, demand_type="prad",
            status=RotaStatus.validada, validated_at=datetime.now(UTC),
        ))
        db_session.commit()
        headers = _login(client, "e5comrota@example.com")
        ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
        assert ca["can_advance"] is True, ca


class TestGateE6PropostaAceita:
    def test_sem_proposta_aceita_can_advance_false(self, client: TestClient, db_session):
        tenant, _user, process = _seed_process_at(
            db_session, email="e6semproposta@example.com", macroetapa=Macroetapa.orcamento_negociacao,
        )
        headers = _login(client, "e6semproposta@example.com")
        ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
        assert ca["can_advance"] is False
        assert any("proposta" in b.lower() for b in ca["blockers"])

    def test_com_proposta_aceita_can_advance_true(self, client: TestClient, db_session):
        tenant, _user, process = _seed_process_at(
            db_session, email="e6comproposta@example.com", macroetapa=Macroetapa.orcamento_negociacao,
        )
        db_session.add(Proposal(
            tenant_id=tenant.id, process_id=process.id, client_id=process.client_id,
            status=ProposalStatus.accepted, title="Proposta", accepted_at=datetime.now(UTC),
        ))
        db_session.commit()
        headers = _login(client, "e6comproposta@example.com")
        ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
        assert ca["can_advance"] is True, ca


class TestGateE7ContratoAssinado:
    """E7 é terminal (sem próxima macroetapa) — o efeito prático do gate é
    no badge (`current_state`), não em `can_advance`/`next_macroetapa`."""

    def test_sem_assinatura_estado_fica_aguardando_validacao(self, client: TestClient, db_session):
        tenant, _user, process = _seed_process_at(
            db_session, email="e7semassinatura@example.com", macroetapa=Macroetapa.contrato_formalizacao,
        )
        headers = _login(client, "e7semassinatura@example.com")
        ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
        assert ca["current_state"] == "aguardando_validacao"

    def test_com_assinatura_estado_fica_pronta_para_avancar(self, client: TestClient, db_session):
        tenant, _user, process = _seed_process_at(
            db_session, email="e7comassinatura@example.com", macroetapa=Macroetapa.contrato_formalizacao,
        )
        db_session.add(Contract(
            tenant_id=tenant.id, process_id=process.id, client_id=process.client_id,
            status=ContractStatus.signed, title="Contrato",
            signed_at=datetime.now(UTC), signed_by_client=True,
        ))
        db_session.commit()
        headers = _login(client, "e7comassinatura@example.com")
        ca = client.get(f"/api/v1/processes/{process.id}/can-advance", headers=headers).json()
        assert ca["current_state"] == "pronta_para_avancar"
