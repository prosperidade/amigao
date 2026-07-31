"""O gate E5→E6 diz o que falta, em português (validação Isis 30/07).

O caso 15 ficou preso na E5 e a tela dizia apenas "feche a rota antes de
avançar" — verdadeiro e inútil. Fechar a rota tem duas portas em série
(classificar cada passo; depois validar cada passo) e o consultor não tinha como
saber em qual estava preso. Medido em produção: rota ``em_validacao`` com 8
passos ainda ``proposto``.
"""

from __future__ import annotations

import pytest

from app.models.client import Client, ClientStatus, ClientType
from app.models.macroetapa import Macroetapa, can_advance_macroetapa
from app.models.process import Process, ProcessStatus
from app.models.rota import (
    Rota,
    RotaPasso,
    RotaPassoClassificacao,
    RotaPassoOrigem,
    RotaPassoStatus,
    RotaStatus,
)
from app.models.tenant import Tenant
from app.services.macroetapa_engine import descrever_pendencia_rota


@pytest.fixture
def caso(db_session):
    tenant = Tenant(name="Gate E5")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="T", email=f"g{tenant.id}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, title="Caso",
                   process_type="car", status=ProcessStatus.triagem,
                   macroetapa=Macroetapa.caminho_regulatorio.value)
    db_session.add(proc)
    db_session.flush()
    return db_session, tenant, proc


def _rota(db, tenant, proc, status: RotaStatus, passos: list[tuple]) -> Rota:
    rota = Rota(tenant_id=tenant.id, process_id=proc.id, demand_type="car", status=status)
    db.add(rota)
    db.flush()
    for i, (classificacao, st) in enumerate(passos, start=1):
        rota.passos.append(RotaPasso(
            tenant_id=tenant.id, ordem=i, titulo=f"Passo {i}", sources=[],
            classificacao=classificacao, status=st,
            origem=RotaPassoOrigem.ia, dedupe_key=f"r{rota.id}:p{i}",
        ))
    db.flush()
    return rota


def test_sem_rota_a_frase_manda_gerar(caso):
    db, tenant, proc = caso
    msg = descrever_pendencia_rota(db, tenant.id, proc.id)
    assert "ainda não foi gerada" in msg
    assert "aba Rota" in msg


def test_passos_sem_classificacao_sao_contados(caso):
    db, tenant, proc = caso
    _rota(db, tenant, proc, RotaStatus.em_validacao, [
        (None, RotaPassoStatus.proposto),
        (None, RotaPassoStatus.proposto),
        (RotaPassoClassificacao.item_proposta, RotaPassoStatus.proposto),
        (RotaPassoClassificacao.direcao, RotaPassoStatus.validado),
    ])
    msg = descrever_pendencia_rota(db, tenant.id, proc.id)
    assert "2 passo(s) sem classificação" in msg
    assert "1 passo(s) classificados mas ainda não validados" in msg
    assert "Fechar rota" in msg


def test_todos_validados_aponta_a_macaneta(caso):
    """O caso em que só falta o clique — a tela precisa dizer QUAL clique."""
    db, tenant, proc = caso
    _rota(db, tenant, proc, RotaStatus.em_validacao, [
        (RotaPassoClassificacao.item_proposta, RotaPassoStatus.validado),
        (RotaPassoClassificacao.direcao, RotaPassoStatus.validado),
    ])
    msg = descrever_pendencia_rota(db, tenant.id, proc.id)
    assert "Todos os passos estão validados" in msg
    assert '"Fechar rota"' in msg


def test_rota_desatualizada_explica_o_diff(caso):
    db, tenant, proc = caso
    _rota(db, tenant, proc, RotaStatus.desatualizada, [
        (RotaPassoClassificacao.item_proposta, RotaPassoStatus.validado),
        (None, RotaPassoStatus.proposto),
    ])
    msg = descrever_pendencia_rota(db, tenant.id, proc.id)
    assert "A IA trouxe passos novos" in msg
    assert "1 passo(s)" in msg


def test_rota_validada_nao_tem_pendencia(caso):
    db, tenant, proc = caso
    _rota(db, tenant, proc, RotaStatus.validada, [
        (RotaPassoClassificacao.item_proposta, RotaPassoStatus.validado),
    ])
    assert descrever_pendencia_rota(db, tenant.id, proc.id) == ""


def test_o_gate_usa_a_frase_especifica():
    """A frase do servidor substitui o texto genérico — a tela não reimplementa."""
    from app.models.macroetapa import MacroetapaChecklist

    cl = MacroetapaChecklist(
        process_id=1, macroetapa=Macroetapa.caminho_regulatorio.value,
        completion_pct=100.0, actions=[],
    )
    detalhe = "Falta fechar a rota regulatória: 8 passo(s) sem classificação."
    _can, blockers = can_advance_macroetapa(
        cl, current_macroetapa=Macroetapa.caminho_regulatorio,
        rota_validada=False, rota_pendencia_detalhe=detalhe,
    )
    assert detalhe in blockers

    # Sem detalhe, o piso genérico continua valendo (nunca fica mudo).
    _can2, blockers2 = can_advance_macroetapa(
        cl, current_macroetapa=Macroetapa.caminho_regulatorio, rota_validada=False,
    )
    assert any("feche a rota antes de avançar" in b for b in blockers2)
