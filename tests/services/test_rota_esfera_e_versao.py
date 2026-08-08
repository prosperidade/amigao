"""Rota: esfera do passivo (#3) e regeneração que não destrói (#4).

Validação Isis 30/07, caso 15 (Fazenda São Jorge, GO, autos do IBAMA):

* **#3** — "a rota da E5 mandou *defender auto na SEMAD* para auto do IBAMA".
  Medido em produção: ``rotas.orgao_competente`` = "Secretaria de Estado de Meio
  Ambiente e Desenvolvimento Sustentável - SEMAD (Goiás)" e TODOS os passos da
  IA com ``orgao`` em "SEMAD"/"SEMAD-GO", num caso cujos passivos são autos
  federais 484341/D e 484343/D. O derive-por-órgão do #125 (ADR-034) valia para
  a busca de corpus e nunca chegava à rota.

* **#4** — "atualizar da IA apagou toda a rota". A reconciliação é aditiva, mas a
  ``dedupe_key`` incluía a ``norma_ref`` que o LLM varia entre execuções: em
  produção os passos 7/12 e 8/13 têm título e órgão IDÊNTICOS e chaves
  diferentes — cada regeneração duplicava a rota.
"""

from __future__ import annotations

from app.models.rota import Rota, RotaPasso, RotaPassoOrigem, RotaPassoStatus, RotaStatus
from app.models.tenant import Tenant
from app.schemas.stage_output import Etapa
from app.services.rota_materializer import (
    _passo_dedupe_key,
    _reconcile_passos,
    aplicar_esfera_do_caso,
    orgao_fora_das_esferas,
    preservar_versao,
)

# ── #3 — esfera ────────────────────────────────────────────────────────────


def test_orgao_estadual_em_caso_federal_e_acusado():
    assert orgao_fora_das_esferas("SEMAD", ["federal"]) is True
    assert orgao_fora_das_esferas("SEMAD-GO", ["federal"]) is True
    assert orgao_fora_das_esferas("IBAMA", ["federal"]) is False


def test_orgao_nao_reconhecido_nunca_e_acusado():
    """Na dúvida não se apaga o trabalho do agente."""
    assert orgao_fora_das_esferas("Cliente / Advogado", ["federal"]) is False
    assert orgao_fora_das_esferas("Cartório de Registro de Imóveis", ["federal"]) is False
    assert orgao_fora_das_esferas(None, ["federal"]) is False


def test_auto_do_ibama_a_rota_nunca_cita_orgao_errado():
    """O caso do relatório: passos "na SEMAD" para auto do IBAMA."""
    etapas = [
        Etapa(ordem=1, titulo="Recebimento e análise do auto de infração", orgao="SEMAD-GO"),
        Etapa(ordem=2, titulo="Protocolização da defesa administrativa na SEMAD", orgao="SEMAD"),
        Etapa(ordem=3, titulo="Reunião e levantamento documental", orgao="Cliente / Advogado"),
        Etapa(ordem=4, titulo="Protocolo da defesa", orgao="IBAMA"),
    ]
    saida, orgao, corrigidos = aplicar_esfera_do_caso(
        etapas, "defesa administrativa",
        "Secretaria de Estado de Meio Ambiente e Desenvolvimento Sustentável - SEMAD (Goiás)",
        ["federal"],
    )
    orgaos = [e.orgao for e in saida]
    assert "SEMAD" not in orgaos and "SEMAD-GO" not in orgaos
    # O órgão certo e o não-reconhecido ficam intactos; só o errado sai.
    assert orgaos == [None, None, "Cliente / Advogado", "IBAMA"]
    # E o órgão competente da rota também é corrigido.
    assert orgao is None
    # Radar-não-cancela: nenhum passo some, e o que foi retirado é reportado.
    assert len(saida) == 4
    assert {c["orgao_removido"] for c in corrigidos} == {
        "SEMAD-GO", "SEMAD",
        "Secretaria de Estado de Meio Ambiente e Desenvolvimento Sustentável - SEMAD (Goiás)",
    }


def test_caso_com_as_duas_esferas_aceita_os_dois_orgaos():
    """Processo 15 real: autos do IBAMA E notificação da SEMAD convivem."""
    etapas = [
        Etapa(ordem=1, titulo="Defesa do auto federal", orgao="IBAMA"),
        Etapa(ordem=2, titulo="Resposta à notificação estadual", orgao="SEMAD"),
    ]
    saida, _orgao, corrigidos = aplicar_esfera_do_caso(
        etapas, None, None, ["federal", "estadual"]
    )
    assert [e.orgao for e in saida] == ["IBAMA", "SEMAD"]
    assert corrigidos == []


def test_sem_esfera_conhecida_o_guard_nao_age():
    """Não inventar esfera quando não se sabe é parte da regra (ADR-034)."""
    etapas = [Etapa(ordem=1, titulo="Passo", orgao="SEMAD")]
    saida, orgao, corrigidos = aplicar_esfera_do_caso(etapas, None, "SEMAD", [])
    assert saida[0].orgao == "SEMAD"
    assert orgao == "SEMAD"
    assert corrigidos == []


# ── #4 — regenerar nunca destrói ───────────────────────────────────────────


def test_dedupe_key_nao_muda_quando_a_norma_muda():
    """A causa medida da duplicação: o LLM varia `fonte_trecho` entre execuções."""
    a = _passo_dedupe_key(1, "Lei 9.605/98, art. 70", "IBAMA", "Protocolar defesa")
    b = _passo_dedupe_key(1, "Decreto 6.514/2008, art. 113", "IBAMA", "Protocolar defesa")
    assert a == b
    # Órgão e título continuam definindo identidade.
    assert a != _passo_dedupe_key(1, None, "SEMAD", "Protocolar defesa")
    assert a != _passo_dedupe_key(1, None, "IBAMA", "Outro passo")


def _rota_com_passos(db_session, passos: list[dict]) -> tuple[Tenant, Rota]:
    tenant = Tenant(name="Rota Versao")
    db_session.add(tenant)
    db_session.flush()
    from app.models.client import Client, ClientStatus, ClientType
    from app.models.process import Process, ProcessStatus

    cli = Client(tenant_id=tenant.id, full_name="T", email=f"rv{tenant.id}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, title="Caso",
                   process_type="car", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    rota = Rota(tenant_id=tenant.id, process_id=proc.id, demand_type="car",
                status=RotaStatus.proposta)
    db_session.add(rota)
    db_session.flush()
    for i, p in enumerate(passos, start=1):
        rota.passos.append(RotaPasso(
            tenant_id=tenant.id, ordem=i, titulo=p["titulo"], orgao=p.get("orgao"),
            sources=[], origem=p.get("origem", RotaPassoOrigem.ia),
            status=p.get("status", RotaPassoStatus.proposto),
            dedupe_key=p["dedupe_key"],
        ))
    db_session.flush()
    return tenant, rota


def test_regeneracao_casa_passo_legado_em_vez_de_duplicar(db_session):
    """Passo gravado com a chave ANTIGA (com norma) não vira duplicata."""
    tenant, rota = _rota_com_passos(db_session, [{
        "titulo": "Recebimento e análise do auto de infração e notificação",
        "orgao": "IBAMA",
        "dedupe_key": f"r{1}:chavelegadaantiga0000",
        "status": RotaPassoStatus.validado,
    }])
    etapas = [Etapa(
        ordem=1, titulo="Recebimento e análise do auto de infração e notificação",
        orgao="IBAMA",
    )]
    created, matched, _is_diff, suprimidos = _reconcile_passos(
        rota=rota, tenant_id=tenant.id, etapas=etapas
    )
    assert created == 0, "mesmo título+órgão não pode virar passo novo"
    assert matched == 1
    # Casou por identidade com um passo VIVO — nada a ver com lápide (ADR-061).
    assert suprimidos == 0
    assert len(rota.passos) == 1
    # E a validação do consultor sobrevive.
    assert rota.passos[0].status == RotaPassoStatus.validado


def test_preservar_versao_congela_a_rota_antes_de_regenerar(db_session):
    tenant, rota = _rota_com_passos(db_session, [
        {"titulo": "Passo do consultor", "orgao": None, "dedupe_key": "r1:manual:p1",
         "origem": RotaPassoOrigem.manual, "status": RotaPassoStatus.validado},
        {"titulo": "Passo da IA", "orgao": "IBAMA", "dedupe_key": "r1:aaa"},
    ])

    v1 = preservar_versao(db_session, rota=rota, tenant_id=tenant.id, user_id=None)
    assert v1 == 1

    from app.models.rota import RotaVersao

    versao = db_session.query(RotaVersao).filter(RotaVersao.rota_id == rota.id).one()
    titulos = [p["titulo"] for p in versao.snapshot["passos"]]
    assert titulos == ["Passo do consultor", "Passo da IA"]
    assert versao.snapshot["rota"]["demand_type"] == "car"
    assert versao.motivo == "regeneracao"

    # Numeração incremental — cada atualização guarda a sua foto.
    assert preservar_versao(db_session, rota=rota, tenant_id=tenant.id, user_id=None) == 2


def test_rota_sem_passos_nao_gera_versao_vazia(db_session):
    tenant, rota = _rota_com_passos(db_session, [])
    assert preservar_versao(db_session, rota=rota, tenant_id=tenant.id, user_id=None) is None
