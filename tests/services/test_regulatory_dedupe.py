"""Dedupe de RegulatoryIssue — fix dos alertas regulatórios duplicados 11×.

Cobre os dois lados medidos no caso 13 / property 10:
  - GERAÇÃO: ``auditor_imovel._persist_issues`` não duplica em re-execução;
  - SANEAMENTO: ``sanear_alertas_duplicados`` colapsa duplicatas preservando
    o sinal humano e reportando conflitos.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.client import Client, ClientStatus, ClientType
from app.models.property import Property
from app.models.regulatory import (
    RegulatoryIssue,
    RegulatoryIssueSeverity,
    StatusAchado,
)
from app.models.tenant import Tenant
from app.services.regulatory_dedupe import (
    issue_dedupe_key,
    sanear_alertas_duplicados,
)

DESC = "Property.geom não populado — verificação espacial não pôde ser executada."


@pytest.fixture
def tenant(db_session) -> Tenant:
    t = Tenant(name="Tenant Dedupe")
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def property_record(db_session, tenant) -> Property:
    c = Client(
        tenant_id=tenant.id,
        full_name="Fazenda Dedupe",
        client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(c)
    db_session.flush()
    p = Property(tenant_id=tenant.id, client_id=c.id, name="Imóvel Dedupe", state="GO")
    db_session.add(p)
    db_session.flush()
    return p


def _mk_issue(
    db_session,
    *,
    tenant_id: int,
    property_id: int,
    status_achado: StatusAchado = StatusAchado.suspeita,
    tema: str = "geometria",
    descricao: str = DESC,
    detected_at: datetime | None = None,
) -> RegulatoryIssue:
    iss = RegulatoryIssue(
        tenant_id=tenant_id,
        property_id=property_id,
        codigo_alerta=None,  # None evita FK no catálogo; dedupe usa tema/descricao
        severity=RegulatoryIssueSeverity.informativo,
        status_achado=status_achado,
        payload={"tema": tema, "descricao": descricao},
        detected_by="auditor_imovel",
    )
    if detected_at is not None:
        iss.detected_at = detected_at
    db_session.add(iss)
    db_session.flush()
    return iss


# ---------------------------------------------------------------------------
# Chave de dedupe
# ---------------------------------------------------------------------------

class TestDedupeKey:
    def test_chave_estavel_para_inputs_iguais(self):
        k1 = issue_dedupe_key(property_id=10, codigo_alerta="X", tema="geometria", descricao=DESC)
        k2 = issue_dedupe_key(property_id=10, codigo_alerta="X", tema="geometria", descricao=DESC)
        assert k1 == k2

    def test_descricao_distingue_achados_de_mesmo_codigo(self):
        k1 = issue_dedupe_key(property_id=10, codigo_alerta="AREA", tema="area", descricao="100 vs 80")
        k2 = issue_dedupe_key(property_id=10, codigo_alerta="AREA", tema="area", descricao="100 vs 50")
        assert k1 != k2

    def test_property_distingue(self):
        k1 = issue_dedupe_key(property_id=10, codigo_alerta="X", tema="t", descricao="d")
        k2 = issue_dedupe_key(property_id=11, codigo_alerta="X", tema="t", descricao="d")
        assert k1 != k2


# ---------------------------------------------------------------------------
# Saneamento retroativo
# ---------------------------------------------------------------------------

class TestSaneamento:
    def test_colapsa_duplicatas_sem_decisao_mantendo_a_mais_recente(self, db_session, tenant, property_record):
        base = datetime(2026, 6, 13, tzinfo=UTC)
        a = _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id, detected_at=base)
        b = _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id, detected_at=base + timedelta(days=1))
        c = _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id, detected_at=base + timedelta(days=2))

        result = sanear_alertas_duplicados(db_session, tenant_id=tenant.id, property_id=property_record.id)

        assert result.rows_before == 3
        assert result.duplicates_removed == 2
        assert result.rows_after == 1
        remaining = db_session.query(RegulatoryIssue).filter_by(property_id=property_record.id).all()
        assert [r.id for r in remaining] == [c.id]  # a mais recente sobrevive
        assert a.id not in {r.id for r in remaining}
        assert b.id not in {r.id for r in remaining}

    def test_preserva_decisao_do_consultor_e_remove_ruido(self, db_session, tenant, property_record):
        confirmada = _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id,
                               status_achado=StatusAchado.confirmada)
        _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id)
        _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id)

        result = sanear_alertas_duplicados(db_session, tenant_id=tenant.id, property_id=property_record.id)

        assert result.duplicates_removed == 2  # as 2 suspeitas saem
        assert result.decisions_preserved == 1
        remaining = db_session.query(RegulatoryIssue).filter_by(property_id=property_record.id).all()
        assert [r.id for r in remaining] == [confirmada.id]

    def test_decisoes_conflitantes_sao_preservadas_e_reportadas(self, db_session, tenant, property_record):
        """O caso 13 real: confirmada (22) × descartada (23) + ruído. As 2 decididas
        ficam (resolução é humana); só o ruído sai; o conflito é reportado."""
        confirmada = _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id,
                               status_achado=StatusAchado.confirmada)
        descartada = _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id,
                               status_achado=StatusAchado.descartada)
        _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id)  # ruído

        result = sanear_alertas_duplicados(db_session, tenant_id=tenant.id, property_id=property_record.id)

        assert result.duplicates_removed == 1  # só o suspeita
        assert len(result.conflicts) == 1
        remaining_ids = {r.id for r in db_session.query(RegulatoryIssue).filter_by(property_id=property_record.id).all()}
        assert confirmada.id in remaining_ids
        assert descartada.id in remaining_ids

    def test_idempotente(self, db_session, tenant, property_record):
        for _ in range(4):
            _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id)

        first = sanear_alertas_duplicados(db_session, tenant_id=tenant.id, property_id=property_record.id)
        assert first.duplicates_removed == 3
        second = sanear_alertas_duplicados(db_session, tenant_id=tenant.id, property_id=property_record.id)
        assert second.duplicates_removed == 0  # 2ª passada não remove nada

    def test_nao_toca_resolvidas(self, db_session, tenant, property_record):
        resolved = _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id)
        resolved.resolved_at = datetime(2026, 6, 1, tzinfo=UTC)
        _mk_issue(db_session, tenant_id=tenant.id, property_id=property_record.id)
        db_session.flush()

        result = sanear_alertas_duplicados(db_session, tenant_id=tenant.id, property_id=property_record.id)

        # resolvida fica fora do grupo de não resolvidas → nada a colapsar
        assert result.duplicates_removed == 0


# ---------------------------------------------------------------------------
# Geração idempotente (auditor não duplica em re-execução)
# ---------------------------------------------------------------------------

class TestGeracaoIdempotente:
    def test_persist_issues_nao_duplica_em_reexecucao(self, db_session, tenant, property_record, monkeypatch):
        from app.agents.auditor_imovel import AuditorImovelAgent
        from app.agents.base import AgentContext

        ctx = AgentContext(
            tenant_id=tenant.id, user_id=1, process_id=1,
            session=db_session, metadata={}, chain_data={},
        )
        # db_session faz rollback no teardown; _persist_issues chama commit() —
        # neutraliza para flush para não vazar/quebrar a transação do teste.
        monkeypatch.setattr(db_session, "commit", db_session.flush)

        agent = AuditorImovelAgent(ctx)
        finding = SimpleNamespace(
            codigo_alerta=None, familia="geoespacial", grade="informativo",
            tema="geometria", descricao=DESC, impacto="", evidencia=None,
            muda_rota_regulatoria=None, muda_escopo_preco_prazo=None,
            documentos_cruzados=None,
        )
        prop = {"id": property_record.id}

        ids1 = agent._persist_issues(prop, [finding])
        ids2 = agent._persist_issues(prop, [finding])

        assert ids1 == ids2  # reusa a issue existente
        total = db_session.query(RegulatoryIssue).filter_by(property_id=property_record.id).count()
        assert total == 1  # uma única linha após duas execuções
