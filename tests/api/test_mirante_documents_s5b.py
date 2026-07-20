"""S5-B — proposta e contrato nos moldes Mirante.

Cobre:
- estrutura completa das 6 seções (proposta) e 8 cláusulas (contrato);
- as 3 validações de consistência (soma serviços==total; soma parcelas==bloco;
  matrículas vigentes) — casos que PASSAM e casos que BLOQUEIAM;
- rastreabilidade passo→etapa (o item da proposta carrega o `rota_passo_id`);
- vigência de matrícula respeitada (histórica não fundamenta contrato);
- bloqueio honesto: perfil do tenant incompleto, proposta não-aceita, placeholder;
- endpoints (rascunho + registro em Saídas).
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.proposal import Proposal, ProposalStatus
from app.models.rota import (
    Rota,
    RotaPasso,
    RotaPassoClassificacao,
    RotaPassoStatus,
    RotaStatus,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services import mirante_documents as md
from app.services.mirante_documents import (
    DocumentConsistencyError,
    DocumentGenerationError,
    PlaceholderUnresolvedError,
    build_contrato,
    build_proposta,
    render_contrato_text,
    render_proposta_text,
)
from app.services.proposal_generator import generate_proposal_from_rota

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _issuer_settings() -> dict:
    """Perfil emissor COMPLETO (fictício — zero PII real)."""
    return {
        "issuer": {
            "razao_social": "Mirante Consultoria Ambiental Ltda.",
            "cnpj": "00.000.000/0001-00",
            "endereco": "Rua Exemplo, 000 — Município/UF",
            "responsavel_tecnico": {
                "nome": "Eng. Fictícia de Exemplo",
                "titulo": "Engenheira Agrônoma",
                "crea": "CREA-XX 000000/D",
            },
            "banco": {
                "nome": "Banco Exemplo (000)", "agencia": "0000",
                "conta": "00000-0", "titular": "Mirante Consultoria Ambiental Ltda.",
                "pix": "00.000.000/0001-00",
            },
            "condicoes": {"foro": "Comarca de Exemplo/UF", "multa_percentual": "10%"},
        }
    }


def _login(client: TestClient, email: str, password: str = "x12345") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(db_session, email, *, settings=None, matricula_vigencia="vigente"):
    tenant = Tenant(name=f"T {email}", settings=settings if settings is not None else _issuer_settings())
    db_session.add(tenant)
    db_session.flush()
    user = User(email=email, full_name="Consultor", hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True, is_superuser=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente Exemplo", cpf_cnpj="000.000.000-00",
                 email=f"c.{email}", client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Exemplo",
                    municipality="Município Exemplo", state="UF", total_area_ha=349.9022,
                    tipologia="Pecuária extensiva")
    db_session.add(prop)
    db_session.flush()
    mat = Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="0.000",
                    area_ha=349.9022, vigencia=matricula_vigencia)
    db_session.add(mat)
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso CAR", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, cli, prop, proc, mat


def _rota_validada(db_session, tenant, proc, *, billable=2):
    rota = Rota(tenant_id=tenant.id, process_id=proc.id, demand_type="car", status=RotaStatus.validada)
    db_session.add(rota)
    db_session.flush()
    for i in range(billable):
        db_session.add(RotaPasso(
            tenant_id=tenant.id, rota_id=rota.id, ordem=i, titulo=f"Serviço faturável {i+1}",
            descricao=f"Detalhe do serviço {i+1}", norma_ref=f"Lei {i+1}", prazo_estimado_dias=10,
            classificacao=RotaPassoClassificacao.item_proposta,
            status=RotaPassoStatus.validado, sources=[], dedupe_key=f"{proc.id}-fat-{i}",
        ))
    db_session.flush()
    return rota


def _proposta_da_rota(db_session, tenant, cli, proc, *, status=ProposalStatus.accepted,
                      installments=None, total_override=None):
    """Cria uma Proposal com escopo REAL vindo da Rota (seam S5-A→S5-B)."""
    _rota_validada(db_session, tenant, proc)
    draft = generate_proposal_from_rota(db_session, proc.id, tenant.id)
    total = total_override if total_override is not None else draft.suggested_value
    p = Proposal(
        tenant_id=tenant.id, client_id=cli.id, process_id=proc.id, title=draft.title,
        scope_items=draft.scope_items, total_value=total, validity_days=30,
        payment_terms="50% na assinatura e 50% na entrega.",
        payment_installments=installments or [], status=status, rota_id=draft.rota_id,
    )
    db_session.add(p)
    db_session.flush()
    return p, draft


# ---------------------------------------------------------------------------
# PROPOSTA — estrutura das 6 seções + rastreabilidade
# ---------------------------------------------------------------------------

def test_proposta_estrutura_6_secoes(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "prop.6@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, status=ProposalStatus.draft)
    doc = build_proposta(db_session, p)
    texto = render_proposta_text(doc)
    for marca in [
        "1. CARACTERIZAÇÃO DA PROPRIEDADE", "2. OBJETIVO", "3. O QUE SERÁ FEITO",
        "4. ENTREGÁVEIS", "5. INVESTIMENTO", "6. CONDIÇÕES COMERCIAIS",
    ]:
        assert marca in texto, f"seção ausente: {marca}"
    # seção 1 vem do Property Hub
    assert "Município Exemplo / UF" in texto
    assert "349,9022 ha" in texto
    # assinatura do responsável técnico (tenant)
    assert "CREA-XX 000000/D" in texto
    assert "Mirante Consultoria Ambiental Ltda." in texto


def test_proposta_rastreabilidade_passo_etapa(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "prop.rastro@ex.com")
    p, draft = _proposta_da_rota(db_session, tenant, cli, proc, status=ProposalStatus.draft)
    doc = build_proposta(db_session, p)
    # cada etapa (seção 3) carrega o rota_passo_id de origem
    passo_ids_escopo = {it["rota_passo_id"] for it in draft.scope_items}
    passo_ids_etapas = {e["rota_passo_id"] for e in doc.etapas}
    assert passo_ids_etapas == passo_ids_escopo
    assert all(e["rota_passo_id"] is not None for e in doc.etapas)
    # seção 4 (entregáveis) deriva dos passos
    assert len(doc.entregaveis) == len(doc.etapas)


def test_proposta_perfil_tenant_incompleto_bloqueia(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "prop.noprof@ex.com", settings={})
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, status=ProposalStatus.draft)
    with pytest.raises(PlaceholderUnresolvedError) as exc:
        build_proposta(db_session, p)
    assert "Perfil do tenant incompleto" in str(exc.value)


# ---------------------------------------------------------------------------
# CONTRATO — estrutura das 8 cláusulas + espelhamento do escopo aceito
# ---------------------------------------------------------------------------

def test_contrato_estrutura_8_clausulas(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "ctr.8@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    doc = build_contrato(db_session, p)
    texto = render_contrato_text(doc)
    for n in range(1, 9):
        assert f"CLÁUSULA {n}ª" in texto, f"cláusula {n}ª ausente"
    # cláusula 1ª espelha o escopo aceito; matrícula vigente citada
    assert "Matrícula(s): 0.000" in texto
    # cláusula 2ª — dados bancários do tenant + testemunhas
    assert "Banco: Banco Exemplo" in texto
    assert "Testemunhas:" in texto
    # foro
    assert "Comarca de Exemplo/UF" in texto


def test_contrato_clausula2_espelha_clausula1(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "ctr.espelho@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)  # sem installments → parcela única
    doc = build_contrato(db_session, p)
    soma_servicos = sum(s["valor"] for s in doc.bloco["servicos"])
    soma_parcelas = sum(pc["valor"] for pc in doc.bloco["parcelas"])
    assert md._cents(soma_servicos) == md._cents(doc.bloco["total"])
    assert md._cents(soma_parcelas) == md._cents(doc.bloco["total"])


def test_contrato_bonus_malus_desligado_por_default(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "ctr.bm@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    doc = build_contrato(db_session, p)
    assert doc.condicoes["bonus_malus"]["ativo"] is False
    assert "bônus/malus" not in render_contrato_text(doc)
    # ligado explicitamente aparece
    doc2 = build_contrato(db_session, p, bonus_malus_ativo=True)
    assert "bônus/malus" in render_contrato_text(doc2)


# ---------------------------------------------------------------------------
# Validações de consistência — casos que BLOQUEIAM
# ---------------------------------------------------------------------------

def test_soma_servicos_diverge_total_bloqueia(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "val.scope@ex.com")
    # total declarado errado (999 ≠ 1200 do escopo)
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, total_override=999.0)
    with pytest.raises(DocumentConsistencyError) as exc:
        build_contrato(db_session, p)
    assert "soma dos serviços" in str(exc.value)


def test_soma_parcelas_diverge_bloco_bloqueia(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "val.parc@ex.com")
    # parcelas somam 1000, bloco é 1200 → cláusula 2ª ≠ cláusula 1ª
    installments = [{"numero": 1, "vencimento": "Na assinatura", "valor": 500},
                    {"numero": 2, "vencimento": "Na entrega", "valor": 500}]
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, installments=installments)
    with pytest.raises(DocumentConsistencyError) as exc:
        build_contrato(db_session, p)
    assert "parcelas" in str(exc.value).lower()


def test_parcelas_corretas_passam(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "val.parc.ok@ex.com")
    installments = [{"numero": 1, "vencimento": "Na assinatura", "valor": 600},
                    {"numero": 2, "vencimento": "Na entrega", "valor": 600}]
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, installments=installments)
    doc = build_contrato(db_session, p)  # não levanta
    assert len(doc.bloco["parcelas"]) == 2


def test_matricula_historica_bloqueia_contrato(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "val.mat@ex.com", matricula_vigencia="historica")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc)
    with pytest.raises(DocumentConsistencyError) as exc:
        build_contrato(db_session, p)
    assert "matrícula vigente" in str(exc.value).lower()


def test_contrato_exige_proposta_aceita(db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "val.draft@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, status=ProposalStatus.draft)
    with pytest.raises(DocumentGenerationError) as exc:
        build_contrato(db_session, p)
    assert "ACEITA" in str(exc.value)


# ---------------------------------------------------------------------------
# Guard de placeholder (unidade)
# ---------------------------------------------------------------------------

def test_placeholder_guard_bloqueia_tokens():
    for txt in ["foo {{cliente.nome}} bar", "valor [12] pendente", "x }} y"]:
        with pytest.raises(PlaceholderUnresolvedError):
            md.assert_resolved(txt)
    md.assert_resolved("Texto totalmente resolvido, sem tokens.")  # não levanta


# ---------------------------------------------------------------------------
# Endpoints — rascunho + registro em Saídas
# ---------------------------------------------------------------------------

def test_endpoint_gerar_proposta_rascunho_registra_saida(client: TestClient, db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "ep.prop@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, status=ProposalStatus.draft)
    db_session.commit()
    h = _login(client, "ep.prop@ex.com")

    r = client.post(f"/api/v1/proposals/{p.id}/documento", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "1. CARACTERIZAÇÃO DA PROPRIEDADE" in body["content"]
    assert body["content_data"]["kind"] == "proposta_mirante"
    # registrado em Saídas como RASCUNHO (needs_human_validation)
    arts = client.get(f"/api/v1/processes/{proc.id}/artifacts?macroetapa=orcamento_negociacao", headers=h)
    assert arts.status_code == 200
    proposta_arts = [a for a in arts.json() if a["output_type"] == "proposta"]
    assert proposta_arts and proposta_arts[0]["needs_human_validation"] is True


def test_endpoint_gerar_contrato_bloqueia_sem_aceite(client: TestClient, db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "ep.ctr.block@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, status=ProposalStatus.draft)
    db_session.commit()
    h = _login(client, "ep.ctr.block@ex.com")

    r = client.post("/api/v1/contracts/gerar", headers=h, json={"proposal_id": p.id})
    assert r.status_code == 422
    assert "ACEITA" in r.json()["detail"]


def test_endpoint_gerar_contrato_da_proposta_aceita(client: TestClient, db_session):
    tenant, cli, _prop, proc, _mat = _setup(db_session, "ep.ctr.ok@ex.com")
    p, _ = _proposta_da_rota(db_session, tenant, cli, proc, status=ProposalStatus.accepted)
    db_session.commit()
    h = _login(client, "ep.ctr.ok@ex.com")

    r = client.post("/api/v1/contracts/gerar", headers=h, json={"proposal_id": p.id})
    assert r.status_code == 201, r.text
    body = r.json()
    assert "CLÁUSULA 1ª" in body["content"]
    assert body["contract"]["proposal_id"] == p.id
    # minuta registrada em Saídas (E7)
    arts = client.get(f"/api/v1/processes/{proc.id}/artifacts?macroetapa=contrato_formalizacao", headers=h)
    minutas = [a for a in arts.json() if a["output_type"] == "minuta"]
    assert minutas and minutas[0]["needs_human_validation"] is True
