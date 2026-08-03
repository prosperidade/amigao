"""A rota nasce do diagnóstico fundamentado, não do relato do intake (ADR-038).

A consultora perguntou: *"a rota traçada na E5 se direciona pelas ações definidas
na E4?"* A medição disse não — e nem pelo diagnóstico. `materialize_rota` montava
o contexto sem `chain_data` e a Legislação lia `process.initial_diagnosis`, o
**pré-diagnóstico por regras do intake**. A rota saía do que o CLIENTE CONTOU.

Estes testes trancam as quatro decisões da ADR-038:

* quem entra no contexto (diagnóstico assinado + achados que dirigem + ações
  triadas), e quem fica de fora sem sumir;
* a hierarquia do filtro — decisão humana > override do caso > catálogo;
* o guard: sem diagnóstico assinado não há rota, e os dois "nãos" são distintos;
* a proveniência: só referência que existe de verdade é aceita.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.acao import Acao, AcaoTipoTriagem
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.regulatory import (
    DecisaoConsultor,
    ProcessIssueDecision,
    RegulatoryDiagnosis,
    RegulatoryAlertFactibilidade,
    RegulatoryFamilia,
    RegulatoryIssue,
    RegulatoryIssueCatalog,
    RegulatoryIssueSeverity,
)
from app.models.tenant import Tenant
from app.services.rota_contexto import (
    DiagnosticoNaoFundamentado,
    montar_contexto_rota,
)


@pytest.fixture
def caso(db_session):
    tenant = Tenant(name="Rota fundamentada")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(
        tenant_id=tenant.id, full_name="Titular", email=f"rf{tenant.id}@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
        title="Caso", process_type="car", status=ProcessStatus.diagnostico,
        initial_diagnosis="O cliente disse que quer regularizar tudo rápido.",
    )
    db_session.add(proc)
    db_session.flush()
    return db_session, tenant, proc, prop


def _diagnostico(db, tenant, proc, *, assinado: bool = True, version: int = 1, **kw):
    diag = RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=proc.id, version=version,
        validated_at=datetime.now(UTC) if assinado else None,
        content=kw.pop("content", {}),
    )
    db.add(diag)
    db.flush()
    return diag


def _catalogo(db, codigo: str, *, muda_rota: bool):
    entrada = RegulatoryIssueCatalog(
        codigo_alerta=codigo, familia=RegulatoryFamilia.titularidade,
        descricao_curta=codigo, factibilidade=RegulatoryAlertFactibilidade.documental,
        severity_base=RegulatoryIssueSeverity.atencao,
        muda_rota_regulatoria=muda_rota, muda_escopo_preco_prazo=False,
    )
    db.add(entrada)
    db.flush()
    return entrada


def _achado(db, tenant, prop, codigo: str, *, override=None, descricao="achado"):
    issue = RegulatoryIssue(
        tenant_id=tenant.id, property_id=prop.id, codigo_alerta=codigo,
        familia=RegulatoryFamilia.titularidade, severity=RegulatoryIssueSeverity.atencao,
        muda_rota_regulatoria=override, payload={"descricao": descricao},
    )
    db.add(issue)
    db.flush()
    return issue


# ---------------------------------------------------------------------------
# Guard — sem diagnóstico assinado não há rota
# ---------------------------------------------------------------------------

def test_sem_diagnostico_algum_bloqueia_dizendo_o_proximo_passo(caso) -> None:
    db, tenant, proc, _prop = caso

    with pytest.raises(DiagnosticoNaoFundamentado) as exc:
        montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert "Diagnóstico Técnico" in str(exc.value)


def test_diagnostico_nao_assinado_bloqueia_com_outra_frase(caso) -> None:
    """Os dois "nãos" são distintos — o movimento do consultor é outro."""
    db, tenant, proc, _prop = caso
    _diagnostico(db, tenant, proc, assinado=False)

    with pytest.raises(DiagnosticoNaoFundamentado) as exc:
        montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert "não foi assinado" in str(exc.value)
    assert "Diagnóstico Técnico" not in str(exc.value)


def test_usa_a_versao_assinada_mais_recente(caso) -> None:
    db, tenant, proc, _prop = caso
    _diagnostico(db, tenant, proc, version=1)
    _diagnostico(db, tenant, proc, version=3)
    _diagnostico(db, tenant, proc, version=4, assinado=False)  # rascunho não vale

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert ctx.diagnosis.version == 3


# ---------------------------------------------------------------------------
# O filtro — a hierarquia da ADR-038
# ---------------------------------------------------------------------------

def test_catalogo_decide_quando_nao_ha_override(caso) -> None:
    db, tenant, proc, prop = caso
    _diagnostico(db, tenant, proc)
    _catalogo(db, "DIRIGE", muda_rota=True)
    _catalogo(db, "NAO_DIRIGE", muda_rota=False)
    dirige = _achado(db, tenant, prop, "DIRIGE")
    nao = _achado(db, tenant, prop, "NAO_DIRIGE")

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert [a.issue.id for a in ctx.achados_dirigem] == [dirige.id]
    assert nao.id in [a.issue.id for a in ctx.achados_contexto]


def test_override_do_caso_vence_o_default_do_catalogo(caso) -> None:
    """Área pequena normalmente não muda rota; neste caso muda (exemplo do modelo)."""
    db, tenant, proc, prop = caso
    _diagnostico(db, tenant, proc)
    _catalogo(db, "NORMALMENTE_NAO", muda_rota=False)
    issue = _achado(db, tenant, prop, "NORMALMENTE_NAO", override=True)

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert [a.issue.id for a in ctx.achados_dirigem] == [issue.id]
    assert ctx.achados_dirigem[0].motivo == "override no achado deste imóvel"


@pytest.mark.parametrize(
    "decisao", [DecisaoConsultor.fora_escopo, DecisaoConsultor.ignorar_justificado]
)
def test_decisao_humana_vence_ate_o_override(caso, decisao) -> None:
    """Princípio 1: o consultor disse que não entra — não entra, por mais grave."""
    db, tenant, proc, prop = caso
    _diagnostico(db, tenant, proc)
    _catalogo(db, "GRAVE", muda_rota=True)
    issue = _achado(db, tenant, prop, "GRAVE", override=True)
    db.add(ProcessIssueDecision(
        tenant_id=tenant.id, process_id=proc.id, issue_id=issue.id,
        decisao=decisao, justificativa="fora do contratado",
    ))
    db.flush()

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert ctx.achados_dirigem == []
    assert [a.issue.id for a in ctx.achados_contexto] == [issue.id]


def test_achado_que_nao_dirige_nao_some_da_vista(caso) -> None:
    """Vai como contexto secundário — o agente não pode perder o quadro."""
    db, tenant, proc, prop = caso
    _diagnostico(db, tenant, proc)
    _catalogo(db, "NAO_DIRIGE", muda_rota=False)
    _achado(db, tenant, prop, "NAO_DIRIGE", descricao="CCIR defasado")

    bloco = montar_contexto_rota(db, process=proc, tenant_id=tenant.id).bloco_prompt()

    assert "CONTEXTO SECUNDÁRIO" in bloco
    assert "CCIR defasado" in bloco
    assert "NÃO gere passo" in bloco


def test_achado_legado_sem_codigo_nao_dirige_mas_e_nomeado(caso) -> None:
    """Na dúvida não se afirma que dirige a rota — e não se esconde o achado.

    O caso real é o registro LEGADO: `codigo_alerta` é nullable só por
    retrocompat (pré-PROMPT_5), e o banco tem FK para o catálogo — um código
    inventado é impossível de inserir. Quem cai neste ramo é o achado antigo,
    sem taxonomia, que não dá para classificar nem esconder."""
    db, tenant, proc, prop = caso
    _diagnostico(db, tenant, proc)
    issue = _achado(db, tenant, prop, None)

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert ctx.achados_dirigem == []
    assert ctx.achados_contexto[0].issue.id == issue.id
    assert ctx.achados_contexto[0].motivo == "achado sem código de alerta (registro legado)"


# ---------------------------------------------------------------------------
# Ações triadas
# ---------------------------------------------------------------------------

def test_so_acoes_triadas_entram(caso) -> None:
    db, tenant, proc, _prop = caso
    _diagnostico(db, tenant, proc)
    manter = [
        Acao(tenant_id=tenant.id, process_id=proc.id, titulo="vira trabalho",
             tipo_triagem=AcaoTipoTriagem.tarefa),
        Acao(tenant_id=tenant.id, process_id=proc.id, titulo="vira proposta",
             tipo_triagem=AcaoTipoTriagem.escopo),
    ]
    excluir = [
        Acao(tenant_id=tenant.id, process_id=proc.id, titulo="ninguém olhou",
             tipo_triagem=AcaoTipoTriagem.pendente),
        Acao(tenant_id=tenant.id, process_id=proc.id, titulo="consultor descartou",
             tipo_triagem=AcaoTipoTriagem.dispensada),
    ]
    db.add_all(manter + excluir)
    db.flush()

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert sorted(a.titulo for a in ctx.acoes) == ["vira proposta", "vira trabalho"]


# ---------------------------------------------------------------------------
# O relato do cliente é rebaixado, não removido
# ---------------------------------------------------------------------------

def test_relato_do_cliente_entra_rotulado_como_nao_conferido(caso) -> None:
    db, tenant, proc, _prop = caso
    _diagnostico(db, tenant, proc)

    bloco = montar_contexto_rota(db, process=proc, tenant_id=tenant.id).bloco_prompt()

    assert "RELATO DO CLIENTE — NÃO CONFERIDO" in bloco
    assert "regularizar tudo rápido" in bloco
    assert "NUNCA como fundamento" in bloco


def test_afirmacoes_do_diagnostico_entram_com_fonte(caso) -> None:
    db, tenant, proc, _prop = caso
    _diagnostico(db, tenant, proc, content={"afirmacoes": [
        {"texto": "RL averbada abaixo do mínimo",
         "fontes": [{"tipo": "documento", "descricao": "Matrícula 4698"}]},
        {"texto": "Sem fonte declarada", "fontes": []},
    ]})

    bloco = montar_contexto_rota(db, process=proc, tenant_id=tenant.id).bloco_prompt()

    assert "RL averbada abaixo do mínimo (fonte: Matrícula 4698)" in bloco
    assert "Sem fonte declarada (sem fonte declarada)" in bloco


# ---------------------------------------------------------------------------
# Proveniência — nunca inventada
# ---------------------------------------------------------------------------

def test_resolver_ref_aceita_so_o_que_existe_neste_caso(caso) -> None:
    db, tenant, proc, prop = caso
    _diagnostico(db, tenant, proc)
    _catalogo(db, "DIRIGE", muda_rota=True)
    issue = _achado(db, tenant, prop, "DIRIGE")
    acao = Acao(tenant_id=tenant.id, process_id=proc.id, titulo="a",
                tipo_triagem=AcaoTipoTriagem.escopo)
    db.add(acao)
    db.flush()

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert ctx.resolver_ref(f"ACHADO-{issue.id}") == (issue.id, None)
    assert ctx.resolver_ref(f"ACAO-{acao.id}") == (None, acao.id)
    # Alucinações e lixo caem fora — passo sem origem é melhor que origem falsa.
    assert ctx.resolver_ref("ACHADO-999999") == (None, None)
    assert ctx.resolver_ref("ACAO-999999") == (None, None)
    assert ctx.resolver_ref("o achado da matrícula") == (None, None)
    assert ctx.resolver_ref(None) == (None, None)


def test_achado_de_contexto_nao_pode_ser_citado_como_origem(caso) -> None:
    """Só o que DIRIGE a rota vira passo — o secundário não é referenciável."""
    db, tenant, proc, prop = caso
    _diagnostico(db, tenant, proc)
    _catalogo(db, "NAO_DIRIGE", muda_rota=False)
    issue = _achado(db, tenant, prop, "NAO_DIRIGE")

    ctx = montar_contexto_rota(db, process=proc, tenant_id=tenant.id)

    assert ctx.resolver_ref(f"ACHADO-{issue.id}") == (None, None)


def test_prompt_exige_proveniencia_e_proibe_inventar(caso) -> None:
    db, tenant, proc, _prop = caso
    _diagnostico(db, tenant, proc)

    bloco = montar_contexto_rota(db, process=proc, tenant_id=tenant.id).bloco_prompt()

    assert "PROVENIÊNCIA OBRIGATÓRIA" in bloco
    assert "origem_refs" in bloco
    assert "inventar um rótulo é pior que não ter" in bloco
