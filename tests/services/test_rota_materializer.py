"""Testes do materializador da Rota Regulatória (E5, Sprint 2).

Cobre o essencial pedido no sprint:
- a materialização lê o Etapa TIPADO (sources+prazo_fonte), reconstruindo do
  dual-emit — NUNCA confia no bruto top-level como se fosse típado;
- reconciliação é aditiva e NÃO-destrutiva: re-rodar preserva edição, ordem,
  classificação e passo manual do consultor;
- rota validada + diff da IA → 'desatualizada' (não rebaixa o conteúdo assinado).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.agents.base import AgentResult
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.regulatory import RegulatoryDiagnosis
from app.models.rota import (
    RotaPassoClassificacao,
    RotaPassoOrigem,
    RotaPassoStatus,
    RotaStatus,
)
from app.models.tenant import Tenant
from app.schemas.stage_output import EnquadramentoRegulatorioContent, Etapa
from app.services import rota_materializer as mat
from app.services.rota_materializer import _etapa_from_raw, materialize_rota

# ---------------------------------------------------------------------------
# _etapa_from_raw — típado vs bruto (o coração da decisão "ler o típado")
# ---------------------------------------------------------------------------


def test_etapa_from_raw_bruto_maps_fonte_trecho_to_sources():
    """Shape BRUTO (fonte_trecho) → Etapa típada com SourceRef(legislacao)+'norma'."""
    etapa = _etapa_from_raw(
        {"ordem": 1, "titulo": "Protocolar CAR", "prazo_estimado_dias": 30,
         "orgao": "SEMAD", "fonte_trecho": "Lei 12.651/2012, art. 29"}
    )
    assert isinstance(etapa, Etapa)
    assert etapa.prazo_fonte == "norma"
    assert len(etapa.sources) == 1
    assert etapa.sources[0].tipo == "legislacao"
    assert "12.651" in (etapa.sources[0].descricao or "")


def test_etapa_from_raw_bruto_sem_fonte_marca_estimativa():
    """Bruto sem fonte mas com prazo → marcação honesta 'estimativa_profissional'."""
    etapa = _etapa_from_raw(
        {"titulo": "Retificar área", "prazo_estimado_dias": 60, "fonte_trecho": "sem fonte"}
    )
    assert etapa is not None
    assert etapa.prazo_fonte == "estimativa_profissional"
    assert etapa.sources[0].sem_fonte is True


def test_etapa_from_raw_prefers_typed_shape_when_present():
    """Se o dual-emit entregar o típado (sources/prazo_fonte), usa direto."""
    etapa = _etapa_from_raw(
        {"ordem": 2, "titulo": "Y",
         "sources": [{"tipo": "legislacao", "descricao": "Lei X"}],
         "prazo_fonte": "norma"}
    )
    assert etapa is not None
    assert etapa.prazo_fonte == "norma"
    assert etapa.sources[0].descricao == "Lei X"


def test_bruto_top_level_would_break_strict_schema():
    """Documenta a armadilha: validar o bruto direto contra o schema QUEBRA
    (Etapa é extra=forbid; 'fonte_trecho' é campo estranho). Por isso reconstruímos."""
    with pytest.raises(ValidationError):
        EnquadramentoRegulatorioContent.model_validate(
            {
                "content": "x",
                "caminho_regulatorio": "x",
                "etapas": [{"ordem": 1, "titulo": "X", "fonte_trecho": "Lei Y"}],
            }
        )


# ---------------------------------------------------------------------------
# Fixtures de seed + fake agent
# ---------------------------------------------------------------------------


def _seed_process(db_session) -> tuple[Tenant, Process]:
    tenant = Tenant(name="Rota Svc")
    db_session.add(tenant)
    db_session.flush()
    client = Client(
        tenant_id=tenant.id, full_name="Faz", client_type=ClientType.pj,
        status=ClientStatus.active,
    )
    db_session.add(client)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=client.id, name="Imóvel", state="GO")
    db_session.add(prop)
    db_session.flush()
    process = Process(
        tenant_id=tenant.id, client_id=client.id, property_id=prop.id,
        title="P", process_type="car", status=ProcessStatus.diagnostico,
        demand_type=DemandType.car,
    )
    db_session.add(process)
    db_session.flush()
    # ADR-039: a rota só é traçada sobre diagnóstico ASSINADO. Antes desta ADR o
    # contexto era montado sem nada disso e a rota nascia do relato do intake —
    # é justamente o que o guard passou a impedir. O diagnóstico entra aqui para
    # que estes testes sigam exercitando a MATERIALIZAÇÃO, e não o guard (que
    # tem cobertura própria em tests/services/test_rota_contexto.py).
    db_session.add(RegulatoryDiagnosis(
        tenant_id=tenant.id, process_id=process.id, version=1,
        validated_at=datetime.now(UTC), content={},
    ))
    db_session.flush()
    return tenant, process


def _fake_agent_data(etapas: list[dict]) -> dict:
    """Payload no shape do dual-emit: 'etapas' top-level é o BRUTO (fonte_trecho)."""
    return {
        "caminho_regulatorio": "Protocolar CAR e retificar área",
        "orgao_competente": "SEMAD",
        "etapas": etapas,
    }


def _patch_agent(monkeypatch, data: dict) -> None:
    class _Fake:
        def run(self) -> AgentResult:
            return AgentResult(
                success=True, data=data, confidence="high", ai_job_id=None,
                suggestions=[], requires_review=True, agent_name="legislacao", duration_ms=1,
            )

    monkeypatch.setattr(mat.AgentRegistry, "create", lambda name, ctx: _Fake())


_ETAPAS_V1 = [
    {"ordem": 1, "titulo": "Protocolar CAR", "descricao": "no SICAR",
     "prazo_estimado_dias": 30, "orgao": "SEMAD", "fonte_trecho": "Lei 12.651/2012"},
    {"ordem": 2, "titulo": "Retificar área", "prazo_estimado_dias": 60,
     "orgao": "Cartório", "fonte_trecho": "sem fonte"},
]


# ---------------------------------------------------------------------------
# Materialização + reconciliação
# ---------------------------------------------------------------------------


def test_materialize_creates_typed_passos(db_session, monkeypatch):
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))

    res = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    assert res.created == 2
    assert res.matched == 0
    passos = sorted(res.rota.passos, key=lambda p: p.ordem)
    # Passo 1 tem norma; passo 2 é estimativa honesta.
    assert passos[0].prazo_fonte == "norma"
    assert passos[0].norma_ref and "12.651" in passos[0].norma_ref
    assert passos[1].prazo_fonte == "estimativa_profissional"
    assert all(p.origem == RotaPassoOrigem.ia for p in passos)
    assert res.rota.status == RotaStatus.proposta


def test_rerun_is_idempotent_and_preserves_human_edits(db_session, monkeypatch):
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))
    res = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    rota = res.rota

    # Consultor edita o passo 1 e classifica; adiciona um passo manual.
    p1 = sorted(rota.passos, key=lambda p: p.ordem)[0]
    p1.descricao = "EDITADO PELO CONSULTOR"
    p1.classificacao = RotaPassoClassificacao.item_proposta
    manual = mat.RotaPasso(
        tenant_id=tenant.id, rota_id=rota.id, ordem=99, titulo="Passo manual",
        sources=[], origem=RotaPassoOrigem.manual, status=RotaPassoStatus.proposto,
        dedupe_key=f"r{rota.id}:manual:pX",
    )
    db_session.add(manual)
    db_session.flush()

    # Re-roda com o MESMO conteúdo da IA.
    res2 = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    assert res2.created == 0        # nada novo
    assert res2.matched == 2        # os 2 passos IA casaram por dedupe
    assert res2.is_diff is False

    db_session.expire_all()
    fresh = sorted(res2.rota.passos, key=lambda p: p.ordem)
    edited = [p for p in fresh if p.titulo == "Protocolar CAR"][0]
    assert edited.descricao == "EDITADO PELO CONSULTOR"          # edição preservada
    assert edited.classificacao == RotaPassoClassificacao.item_proposta  # classificação preservada
    assert any(p.origem == RotaPassoOrigem.manual for p in fresh)  # manual intacto


def test_rerun_with_new_step_adds_and_flags_diff(db_session, monkeypatch):
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))
    materialize_rota(db_session, process=process, tenant_id=tenant.id)

    etapas_v2 = _ETAPAS_V1 + [
        {"ordem": 3, "titulo": "Averbar reserva legal", "prazo_estimado_dias": 45,
         "orgao": "Cartório", "fonte_trecho": "Lei 12.651/2012, art. 18"}
    ]
    _patch_agent(monkeypatch, _fake_agent_data(etapas_v2))
    res2 = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    assert res2.created == 1
    assert res2.matched == 2
    assert res2.is_diff is True


def test_validated_rota_becomes_desatualizada_on_diff(db_session, monkeypatch):
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))
    res = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    # Simula rota assinada.
    res.rota.status = RotaStatus.validada
    db_session.flush()

    etapas_v2 = _ETAPAS_V1 + [
        {"ordem": 3, "titulo": "Averbar reserva legal", "orgao": "Cartório",
         "fonte_trecho": "Lei 12.651/2012, art. 18"}
    ]
    _patch_agent(monkeypatch, _fake_agent_data(etapas_v2))
    res2 = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    assert res2.is_diff is True
    assert res2.rota.status == RotaStatus.desatualizada  # não rebaixa: sinaliza


# ---------------------------------------------------------------------------
# Remoção LEMBRADA — o gate deste PR
#
# Queixa literal da consultora (02/08): "gerar rota não deu em nada". A trilha
# do caso 16 mostrou o mecanismo: created=5 às 15:37, e às 15:43 ela removeu 4
# passos em 11 segundos. Como a linha era APAGADA, o passo saía de `rota.passos`
# e a regeneração seguinte não tinha com o que casar — recriava tudo. O trabalho
# dela voltava desfeito, e regerar virava um gesto que "não dava em nada".
# ---------------------------------------------------------------------------


def _remover(db_session, passo, user_id=None) -> None:
    """Remove como o endpoint remove — lápide, não DELETE."""
    passo.deleted_at = datetime.now(UTC)
    passo.deleted_by_user_id = user_id
    db_session.flush()


def test_passo_removido_nao_volta_na_regeneracao(db_session, monkeypatch):
    """GATE: o consultor remove um passo; "Atualizar da IA" NÃO o ressuscita."""
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))
    res = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    assert res.created == 2

    alvo = [p for p in res.rota.passos if p.titulo == "Retificar área"][0]
    _remover(db_session, alvo)
    db_session.expire_all()
    assert [p.titulo for p in res.rota.passos] == ["Protocolar CAR"]

    # A IA repropõe exatamente as mesmas duas etapas.
    res2 = materialize_rota(db_session, process=process, tenant_id=tenant.id)

    db_session.expire_all()
    titulos = [p.titulo for p in res2.rota.passos]
    assert titulos == ["Protocolar CAR"], "o passo removido voltou — regerar desfez o gesto humano"
    assert res2.created == 0
    # A supressão é CONTADA, não silenciosa: sem isto a tela diria "nenhum passo
    # novo" e o consultor concluiria que a atualização não rodou.
    assert res2.suprimidos == 1


def test_supressao_nao_desatualiza_rota_assinada(db_session, monkeypatch):
    """Passo removido reproposto para sempre não pode travar a E5 para sempre.

    Se `suprimidos` contasse como diff, toda regeneração rebaixaria a rota
    assinada para 'desatualizada' e "Fechar rota" nunca mais liberaria — o mesmo
    beco sem saída que a validação de 02/08 já custou uma vez.
    """
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))
    res = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    alvo = [p for p in res.rota.passos if p.titulo == "Retificar área"][0]
    _remover(db_session, alvo)
    res.rota.status = RotaStatus.validada
    db_session.flush()

    res2 = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    assert res2.suprimidos == 1
    assert res2.is_diff is False
    assert res2.rota.status == RotaStatus.validada  # segue assinada


def test_remocao_lembrada_nao_atinge_passo_manual(db_session, monkeypatch):
    """Remover um passo IA não arrasta o manual do consultor para a lápide."""
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))
    res = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    rota = res.rota
    manual = mat.RotaPasso(
        tenant_id=tenant.id, rota_id=rota.id, ordem=99, titulo="Ofício à secretaria",
        sources=[], origem=RotaPassoOrigem.manual, status=RotaPassoStatus.proposto,
        dedupe_key=f"r{rota.id}:manual:pY",
    )
    db_session.add(manual)
    db_session.flush()

    _remover(db_session, [p for p in rota.passos if p.titulo == "Protocolar CAR"][0])
    res2 = materialize_rota(db_session, process=process, tenant_id=tenant.id)

    db_session.expire_all()
    titulos = {p.titulo for p in res2.rota.passos}
    assert "Ofício à secretaria" in titulos
    assert "Protocolar CAR" not in titulos


def test_passo_removido_sai_das_leituras_que_alimentam_o_gate(db_session, monkeypatch):
    """Passo removido não conta como pendente nem entra no snapshot da versão.

    São ~20 consumidores lendo `rota.passos` (gate da macroetapa, proposta,
    "fechar rota"); o filtro mora na relação justamente para que nenhum deles
    precise lembrar da lápide.
    """
    tenant, process = _seed_process(db_session)
    _patch_agent(monkeypatch, _fake_agent_data(_ETAPAS_V1))
    res = materialize_rota(db_session, process=process, tenant_id=tenant.id)
    _remover(db_session, [p for p in res.rota.passos if p.titulo == "Retificar área"][0])

    db_session.expire_all()
    assert len(res.rota.passos) == 1
    assert len(res.rota.passos_removidos) == 1
    assert mat._snapshot_rota(res.rota)["passos"] == [
        s for s in mat._snapshot_rota(res.rota)["passos"] if s["titulo"] == "Protocolar CAR"
    ]
