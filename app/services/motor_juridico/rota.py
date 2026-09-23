"""Rota gerada pelo motor jurídico (ADR-073 §7 e §8).

Avalia o conjunto ativo e converte ``passo_rota`` e ``coleta`` em `Etapa`. Depois
REUSA a maquinaria da Rota — versão preservada antes, `_upsert_rota`,
`_reconcile_passos` (aditiva, lápides, `desatualizada`), guarda de esfera. Nada disso
muda; muda a origem do passo (``motor``) e a proveniência: avaliação + fundamento por ID.

Guarda da Rota (§8, decisão do André): a Rota do motor dispensa o diagnóstico assinado
do ADR-039 — cada passo já carrega regra homologada, fatos com origem e norma por ID, e
o consultor valida passo a passo. O caminho da `LegislacaoAgent` mantém o guarda.

``alerta_critico`` não vira passo: fica na avaliação e exige ciência antes de fechar.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.process import Process
from app.models.rota import Rota, RotaPassoOrigem, RotaStatus
from app.schemas.stage_output import Etapa, SourceRef
from app.services.motor_juridico.avaliador import Execucao, executar
from app.services.rota_materializer import (
    RotaMaterializeResult,
    _reconcile_passos,
    _upsert_rota,
    aplicar_esfera_do_caso,
    preservar_versao,
)

logger = get_logger(__name__)

EFEITOS_DE_PASSO = ("passo_rota", "coleta")


def _fonte_do_passo(av) -> list[SourceRef]:
    if av.fundamento_caminho and av.fundamento_fonte_versao_id:
        return [SourceRef(
            tipo="legislacao", ref=f"fonte_normativa_versao:{av.fundamento_fonte_versao_id}",
            descricao=av.fundamento_caminho, confianca="alta", fonte_origem="catalogo_normativo",
        )]
    # Fundamento não resolvido: honestidade explícita, nunca substituta por semelhança.
    return [SourceRef(tipo="sem_fonte", sem_fonte=True,
                      descricao=f"fundamento não resolvido: {av.fundamento_razao}")]


def etapas_da_execucao(execucao: Execucao) -> tuple[list[Etapa], dict[int, dict[str, Any]]]:
    """Etapas na ordem das regras, e a proveniência de cada uma (por ``id(etapa)``)."""
    etapas: list[Etapa] = []
    proveniencia: dict[int, dict[str, Any]] = {}
    for av in execucao.avaliacoes:
        if av.estado not in ("aplicavel_disparou", "indeterminado"):
            continue
        rule_id = execucao.rule_ids[av.regra_versao_id]
        for efeito in (av.consequencia or {}).get("efeitos", []):
            if efeito.get("tipo") not in EFEITOS_DE_PASSO:
                continue
            fundamento = av.fundamento_caminho or f"não resolvido ({av.fundamento_razao})"
            descricao = f"{(efeito.get('descricao') or '').strip()}\n\nRegra {rule_id} · Fundamento: {fundamento}"
            sources = _fonte_do_passo(av)
            etapa = Etapa(
                ordem=len(etapas) + 1, titulo=efeito["titulo"], descricao=descricao.strip(),
                orgao=efeito.get("orgao"), sources=sources,
            )
            etapas.append(etapa)
            proveniencia[id(etapa)] = {
                "origem_avaliacao_id": av.id,
                "fundamento_fonte_versao_id": av.fundamento_fonte_versao_id,
                "fundamento_dispositivo_id": av.fundamento_dispositivo_id,
                "sources": [s.model_dump() for s in sources],
                "norma_ref": av.fundamento_caminho,
            }
    return etapas, proveniencia


def gerar_rota_pelo_motor(
    session: Session, *, process: Process, tenant_id: int, user_id: int | None,
    data_referencia: date | None = None,
) -> tuple[RotaMaterializeResult, Execucao]:
    demand_type = process.demand_type.value if getattr(process, "demand_type", None) else "nao_identificado"
    rota_atual = (
        session.query(Rota)
        .filter(Rota.tenant_id == tenant_id, Rota.process_id == process.id, Rota.demand_type == demand_type)
        .first()
    )
    versao_preservada = (
        preservar_versao(session, rota=rota_atual, tenant_id=tenant_id, user_id=user_id, motivo="motor_juridico")
        if rota_atual is not None else None
    )

    execucao = executar(session, process=process, tenant_id=tenant_id, user_id=user_id,
                        data_referencia=data_referencia)
    etapas, proveniencia = etapas_da_execucao(execucao)

    esferas: list[str] = []
    try:
        from app.services.passivos_esfera import esferas_do_processo  # noqa: PLC0415

        esferas = list(esferas_do_processo(session, tenant_id, process.id))
    except Exception as exc:  # noqa: BLE001 — sem esfera o guard só não age (mesmo contrato do materializer)
        logger.warning("motor_juridico: falha ao derivar esferas do caso: %s", exc)
    corrigidas, _, orgaos_corrigidos = aplicar_esfera_do_caso(etapas, None, None, esferas)
    # `model_copy` cria objeto novo: a proveniência segue a etapa pela posição.
    proveniencia = {id(n): proveniencia[id(v)] for v, n in zip(etapas, corrigidas, strict=True)}

    rota = _upsert_rota(
        session, process=process, tenant_id=tenant_id, demand_type=demand_type,
        caminho=f"Rota do motor jurídico — execução {execucao.execucao.id}", orgao=None, ai_job_id=None,
    )
    created, matched, is_diff, suprimidos = _reconcile_passos(
        rota=rota, tenant_id=tenant_id, etapas=corrigidas,
        origem=RotaPassoOrigem.motor, proveniencia_motor=proveniencia,
    )
    if rota.status == RotaStatus.validada and is_diff:
        rota.status = RotaStatus.desatualizada
    session.flush()
    session.expire(rota, ["passos"])
    logger.info(
        "rota_motor_materializada",
        extra={"process_id": process.id, "tenant_id": tenant_id, "rota_id": rota.id,
               "execucao_id": execucao.execucao.id, "passos_created": created, "passos_matched": matched,
               "passos_suprimidos": suprimidos, "is_diff": is_diff},
    )
    return RotaMaterializeResult(
        rota=rota, created=created, matched=matched, is_diff=is_diff,
        orgaos_corrigidos=orgaos_corrigidos, versao_preservada=versao_preservada, suprimidos=suprimidos,
    ), execucao
