"""S5-C — assinatura manual do contrato + Saídas converge + E1→E7 (a Ficha inteira).

Cobre:
- ciclo de assinatura MANUAL: rascunho → aprovar/enviar → assinar (com e sem upload);
- bloqueios honestos (assinar exige ENVIADO; aprovar exige RASCUNHO);
- gate E7 satisfazível (has_contract_signed) + card E7 CONCLUÍDA após assinatura;
- Saídas converge: proposta + minuta aparecem em /artifacts; download de artefato;
- teste de integração E1→E7 completo dirigido pela API (o que nunca existiu).
"""

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

# Reaproveita os helpers de setup do S5-B (mesmo pacote tests/api).
from tests.api.test_mirante_documents_s5b import (
    _login,
    _proposta_da_rota,
    _setup,
)

from app.models.audit_log import AuditLog
from app.models.macroetapa import (
    Macroetapa,
    MacroetapaChecklist,
    MacroetapaState,
    compute_macroetapa_state,
)
from app.models.regulatory import RegulatoryDiagnosis
from app.models.stage_output import StageOutput
from app.services.macroetapa_engine import (
    ensure_macroetapa_checklists,
    has_contract_signed,
)

# ---------------------------------------------------------------------------
# Helpers de fluxo
# ---------------------------------------------------------------------------

def _gerar_contrato(client: TestClient, h: dict, proposal_id: int) -> dict:
    r = client.post("/api/v1/contracts/gerar", headers=h, json={"proposal_id": proposal_id})
    assert r.status_code == 201, r.text
    return r.json()["contract"]


def _sign_diagnosis(db, tenant, proc) -> None:
    """Sinal `diagnosis_validated` (gate E2/E4) — diagnóstico assinado."""
    db.add(RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=proc.id, content={}, version=1,
        validated_at=datetime.now(UTC),
    ))
    db.flush()


def _audit_consolidar(db, tenant, proc) -> None:
    """Sinal `has_consolidated` (gate E2) — AuditLog action='consolidar'."""
    db.add(AuditLog(
        tenant_id=tenant.id, user_id=None, entity_type="process",
        entity_id=proc.id, action="consolidar", details=json.dumps({"writes": 1}),
    ))
    db.flush()


def _complete_stage(db, proc) -> None:
    """Marca o checklist da etapa CORRENTE do processo como 100% (todas as ações)."""
    ensure_macroetapa_checklists(db, proc, proc.tenant_id)
    etapa = Macroetapa(proc.macroetapa)
    cl = (
        db.query(MacroetapaChecklist)
        .filter(MacroetapaChecklist.process_id == proc.id, MacroetapaChecklist.macroetapa == etapa)
        .first()
    )
    assert cl is not None
    cl.actions = [
        {**a, "completed": True, "completed_at": "2026-07-19", "needs_human_validation": False}
        for a in (cl.actions or [])
    ]
    cl.completion_pct = 100.0
    db.flush()


# ---------------------------------------------------------------------------
# Ciclo de assinatura MANUAL
# ---------------------------------------------------------------------------

def test_aprovar_enviar_e_assinar_sem_upload(client: TestClient, db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "sig.ok@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)  # accepted
    db_session.commit()
    h = _login(client, "sig.ok@ex.com")

    contract = _gerar_contrato(client, h, p.id)
    assert contract["status"] == "draft"

    env = client.post(f"/api/v1/contracts/{contract['id']}/aprovar-enviar", headers=h)
    assert env.status_code == 200, env.text
    assert env.json()["status"] == "sent"

    ass = client.post(f"/api/v1/contracts/{contract['id']}/assinar", headers=h,
                      data={"signed_at": "2026-07-19"})
    assert ass.status_code == 200, ass.text
    body = ass.json()
    assert body["contract"]["status"] == "signed"
    assert body["contract"]["signed_at"] is not None
    assert body["contract"]["has_signed_pdf"] is False
    assert body["concluido_em"] is not None  # caso concluído

    # Gate E7 agora satisfazível
    db_session.expire_all()
    assert has_contract_signed(db_session, tenant.id, proc.id) is True


def test_assinar_com_upload_pdf(client: TestClient, db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "sig.up@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    db_session.commit()
    h = _login(client, "sig.up@ex.com")
    contract = _gerar_contrato(client, h, p.id)
    client.post(f"/api/v1/contracts/{contract['id']}/aprovar-enviar", headers=h)

    ass = client.post(
        f"/api/v1/contracts/{contract['id']}/assinar", headers=h,
        data={"signed_at": "2026-07-19"},
        files={"signed_pdf": ("assinado.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert ass.status_code == 200, ass.text
    body = ass.json()
    assert body["contract"]["status"] == "signed"
    # Ou armazenou o PDF assinado, ou degradou com elegância (warning) — nunca 500.
    assert body["contract"]["has_signed_pdf"] or body.get("warning")


def test_assinar_bloqueado_sem_enviar(client: TestClient, db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "sig.block@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    db_session.commit()
    h = _login(client, "sig.block@ex.com")
    contract = _gerar_contrato(client, h, p.id)  # draft

    r = client.post(f"/api/v1/contracts/{contract['id']}/assinar", headers=h,
                    data={"signed_at": "2026-07-19"})
    assert r.status_code == 422
    assert "ENVIADO" in r.json()["detail"]


def test_aprovar_enviar_so_de_rascunho(client: TestClient, db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "sig.appr@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    db_session.commit()
    h = _login(client, "sig.appr@ex.com")
    contract = _gerar_contrato(client, h, p.id)
    client.post(f"/api/v1/contracts/{contract['id']}/aprovar-enviar", headers=h)  # → sent
    r = client.post(f"/api/v1/contracts/{contract['id']}/aprovar-enviar", headers=h)  # de novo
    assert r.status_code == 422


def test_data_assinatura_invalida_bloqueia(client: TestClient, db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "sig.date@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    db_session.commit()
    h = _login(client, "sig.date@ex.com")
    contract = _gerar_contrato(client, h, p.id)
    client.post(f"/api/v1/contracts/{contract['id']}/aprovar-enviar", headers=h)
    r = client.post(f"/api/v1/contracts/{contract['id']}/assinar", headers=h,
                    data={"signed_at": "19/07/2026"})
    assert r.status_code == 422
    assert "AAAA-MM-DD" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Card E7 — contrato assinado CONCLUI (compute_macroetapa_state)
# ---------------------------------------------------------------------------

def _e7_checklist(db, tenant, proc) -> MacroetapaChecklist:
    proc.macroetapa = Macroetapa.contrato_formalizacao.value
    db.flush()
    _complete_stage(db, proc)
    return (
        db.query(MacroetapaChecklist)
        .filter(MacroetapaChecklist.process_id == proc.id,
                MacroetapaChecklist.macroetapa == Macroetapa.contrato_formalizacao)
        .first()
    )


def test_e7_aguardando_sem_assinatura_e_concluida_com(db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "e7.card@ex.com")
    cl = _e7_checklist(db_session, tenant, proc)
    # 100% mas sem contrato assinado → aguardando (o caso não está concluído)
    st_sem = compute_macroetapa_state(
        cl, is_current=True, current_macroetapa=Macroetapa.contrato_formalizacao,
        contract_signed=False,
    )
    assert st_sem == MacroetapaState.aguardando_validacao
    # com contrato assinado → CONCLUÍDA (terminal, sem "avançar")
    st_com = compute_macroetapa_state(
        cl, is_current=True, current_macroetapa=Macroetapa.contrato_formalizacao,
        contract_signed=True,
    )
    assert st_com == MacroetapaState.concluida


# ---------------------------------------------------------------------------
# Saídas converge
# ---------------------------------------------------------------------------

def test_saidas_lista_proposta_e_minuta(client: TestClient, db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "saidas@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    db_session.commit()
    h = _login(client, "saidas@ex.com")

    client.post(f"/api/v1/proposals/{p.id}/documento", headers=h)  # proposta (E6)
    _gerar_contrato(client, h, p.id)                               # minuta (E7)

    arts = client.get(f"/api/v1/processes/{proc.id}/artifacts", headers=h)
    assert arts.status_code == 200
    tipos = {a["output_type"] for a in arts.json()}
    assert "proposta" in tipos
    assert "minuta" in tipos
    # a minuta carrega content_data com o vínculo ao contrato (converge no front)
    minuta = next(a for a in arts.json() if a["output_type"] == "minuta")
    assert minuta["content_data"].get("contract_id")


def test_download_artefato(client: TestClient, db_session):
    tenant, cli, _p, proc, _m = _setup(db_session, "dl@ex.com")
    db_session.commit()
    h = _login(client, "dl@ex.com")
    # artefato COM pdf_storage_key → URL pré-assinada (presign é offline: 200 sem MinIO)
    art = StageOutput(
        tenant_id=tenant.id, process_id=proc.id, macroetapa="orcamento_negociacao",
        output_type="proposta", title="Proposta X", content="…",
        content_data={"pdf_storage_key": "tenant/proc/proposta.pdf"},
        needs_human_validation=True,
    )
    db_session.add(art)
    db_session.commit()
    ok = client.get(f"/api/v1/processes/{proc.id}/artifacts/{art.id}/download", headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["download_url"]

    # artefato SEM pdf → 404 honesto
    art2 = StageOutput(
        tenant_id=tenant.id, process_id=proc.id, macroetapa="orcamento_negociacao",
        output_type="proposta", title="Sem PDF", content="…", content_data={},
    )
    db_session.add(art2)
    db_session.commit()
    nf = client.get(f"/api/v1/processes/{proc.id}/artifacts/{art2.id}/download", headers=h)
    assert nf.status_code == 404


# ---------------------------------------------------------------------------
# E1 → E7 — a Ficha inteira num teste de integração (dirigido pela API)
# ---------------------------------------------------------------------------

def test_e1_a_e7_ficha_inteira(client: TestClient, db_session):
    tenant, cli, prop, proc, mat = _setup(db_session, "ficha.e2e@ex.com")
    proc.macroetapa = Macroetapa.entrada_demanda.value
    db_session.flush()
    # Sinais do percurso: diagnóstico assinado (E2/E4), consolidação (E2),
    # Rota validada (E5) + proposta ACEITA (E6) — a proposta nasce da Rota (S5-A/B).
    _sign_diagnosis(db_session, tenant, proc)
    _audit_consolidar(db_session, tenant, proc)
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)  # cria Rota validada + Proposal accepted
    db_session.commit()
    h = _login(client, "ficha.e2e@ex.com")

    # Gate é real: avançar E1 sem completar o checklist é bloqueado (409).
    proc.macroetapa = Macroetapa.entrada_demanda.value
    db_session.commit()
    blocked = client.post(f"/api/v1/processes/{proc.id}/macroetapa", headers=h,
                          json={"macroetapa": "diagnostico_preliminar"})
    assert blocked.status_code == 409

    # Percurso E1 → E2 → (pula E3) → E4 → E5 → E6 → E7.
    percurso = [
        "diagnostico_preliminar",
        "diagnostico_tecnico",   # E2 pula E3 (sem doc essencial pendente)
        "caminho_regulatorio",
        "orcamento_negociacao",
        "contrato_formalizacao",
    ]
    for target in percurso:
        db_session.refresh(proc)
        _complete_stage(db_session, proc)   # completa a etapa CORRENTE
        db_session.commit()
        r = client.post(f"/api/v1/processes/{proc.id}/macroetapa", headers=h,
                        json={"macroetapa": target})
        assert r.status_code == 200, f"avanço para {target} falhou: {r.text}"

    db_session.refresh(proc)
    assert proc.macroetapa == "contrato_formalizacao"  # chegou na E7 terminal

    # E7: contrato nasce da proposta aceita → aprovar/enviar → assinar → CONCLUI.
    _complete_stage(db_session, proc)
    db_session.commit()
    contract = _gerar_contrato(client, h, p.id)
    client.post(f"/api/v1/contracts/{contract['id']}/aprovar-enviar", headers=h)
    ass = client.post(f"/api/v1/contracts/{contract['id']}/assinar", headers=h,
                      data={"signed_at": "2026-07-19"})
    assert ass.status_code == 200, ass.text

    # A Ficha concluiu: gate E7 satisfazível + caso com closed_at + card CONCLUÍDA.
    db_session.expire_all()
    assert has_contract_signed(db_session, tenant.id, proc.id) is True
    db_session.refresh(proc)
    assert proc.closed_at is not None
    cl_e7 = (
        db_session.query(MacroetapaChecklist)
        .filter(MacroetapaChecklist.process_id == proc.id,
                MacroetapaChecklist.macroetapa == Macroetapa.contrato_formalizacao)
        .first()
    )
    assert compute_macroetapa_state(
        cl_e7, is_current=True, current_macroetapa=Macroetapa.contrato_formalizacao,
        contract_signed=True,
    ) == MacroetapaState.concluida
