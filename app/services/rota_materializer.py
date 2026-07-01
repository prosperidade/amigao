"""Materialização + reconciliação da Rota Regulatória (E5, Sprint 2).

Roda a ``LegislacaoAgent`` e grava suas ``etapas`` como ``RotaPasso`` duráveis,
reconciliando com o que já existe (padrão consolidação parcial, ADR-017). A IA
propõe; o consultor decide — a reconciliação é **aditiva e não-destrutiva**:
re-rodar nunca apaga edição/classificação/ordem do humano nem passo manual.

════════════════════════════════════════════════════════════════════════════
ATENÇÃO — O DUAL-EMIT DA LegislacaoAgent (não erre isto)
════════════════════════════════════════════════════════════════════════════
``EnquadramentoRegulatorioContent`` tem DOIS shapes de ``etapas`` no MESMO dict:

  • TIPADO   — ``Etapa`` com ``sources`` (list[SourceRef]) + ``prazo_fonte``.
              É o que queremos. Vem de ``enq.model_dump()``
              (``app/schemas/stage_output.py:413-440`` e ``:395-410``).
  • BRUTO    — dict do LLM com ``fonte_trecho`` (sem ``sources``/``prazo_fonte``).
              ``legislacao.py:719-723`` faz ``... | {"etapas": list(etapas_raw)}``
              e **sobrescreve** o top-level com o bruto. NÃO usar.

Ou seja: ``result.data["etapas"]`` é o BRUTO (o típado foi sobrescrito no merge).
Validar ``result.data`` inteiro contra o schema QUEBRA (``Etapa`` é ``extra=forbid``
e o bruto traz ``fonte_trecho``). Por isso reconstruímos ``Etapa`` tipada aqui,
preferindo campos típados quando presentes e mapeando ``fonte_trecho`` do jeito
que o agente mapeia (``_etapa_fonte``) quando só o bruto chegou. Assim o que é
PERSISTIDO é sempre o típado (``sources``+``prazo_fonte``), nunca o bruto.

TASK 0b (estabilidade de título): o LLM não é determinístico (sem seed), então os
títulos das etapas PODEM variar entre execuções. Por isso ``dedupe_key`` é
HIGIENE, não oráculo (dívida #48) — evita duplicar o óbvio, mas a reconciliação
real é mediada pelo consultor. Nunca bloqueamos o sprint blindando identidade.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import AgentContext, AgentRegistry
from app.core.logging import get_logger
from app.models.process import Process
from app.models.rota import (
    Rota,
    RotaPasso,
    RotaPassoOrigem,
    RotaPassoStatus,
    RotaStatus,
)
from app.schemas.stage_output import Etapa, SourceRef

logger = get_logger(__name__)


@dataclass
class RotaMaterializeResult:
    rota: Rota
    created: int
    matched: int
    is_diff: bool  # houve diferença vs. o snapshot anterior?


# ---------------------------------------------------------------------------
# Reconstrução TIPADA de Etapa (ver docstring do módulo)
# ---------------------------------------------------------------------------

def _coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return max(int(value), 0)
    except (TypeError, ValueError):
        return None


def _sources_prazo_from_fonte_trecho(
    fonte_trecho: Any, prazo_int: int | None
) -> tuple[list[SourceRef], str | None]:
    """Espelha ``LegislacaoAgent._etapa_fonte`` (legislacao.py:560-575).

    Fonte plausível → ``SourceRef(legislacao)`` + ``'norma'``; sem fonte mas com
    prazo → marcação honesta ``'estimativa_profissional'``; nada → ``([], None)``.
    """
    ref = str(fonte_trecho).strip() if fonte_trecho not in (None, "") else ""
    if ref and "sem fonte" not in ref.lower() and "estimativa" not in ref.lower():
        return [SourceRef(tipo="legislacao", descricao=ref)], "norma"
    if prazo_int is not None:
        return (
            [
                SourceRef(
                    tipo="sem_fonte",
                    sem_fonte=True,
                    descricao="estimativa profissional — sem fonte normativa nos autos",
                )
            ],
            "estimativa_profissional",
        )
    return [], None


def _coerce_sources(raw: Any) -> list[SourceRef]:
    out: list[SourceRef] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, SourceRef):
                out.append(item)
            elif isinstance(item, dict):
                try:
                    out.append(SourceRef(**item))
                except Exception:  # noqa: BLE001 — fonte malformada não derruba a rota
                    continue
    return out


def _etapa_from_raw(raw: Any) -> Etapa | None:
    """Reconstrói uma ``Etapa`` TIPADA de um item de ``etapas`` (típado OU bruto).

    Tolera os dois shapes do dual-emit e sempre devolve o típado
    (``sources``+``prazo_fonte``). Itens sem título são descartados.
    """
    if not isinstance(raw, dict):
        return None
    titulo = (raw.get("titulo") or "").strip()
    if not titulo:
        return None
    prazo_int = _coerce_int(raw.get("prazo_estimado_dias"))

    if "sources" in raw or "prazo_fonte" in raw:
        # Já veio no shape TIPADO (se o dual-emit for corrigido no futuro).
        sources = _coerce_sources(raw.get("sources"))
        prazo_fonte = raw.get("prazo_fonte") or None
    else:
        # Shape BRUTO (top-level atual): mapeia fonte_trecho como o agente.
        sources, prazo_fonte = _sources_prazo_from_fonte_trecho(
            raw.get("fonte_trecho"), prazo_int
        )

    ordem = _coerce_int(raw.get("ordem")) or 1
    try:
        return Etapa(
            ordem=max(ordem, 1),
            titulo=titulo,
            descricao=(raw.get("descricao") or None),
            prazo_estimado_dias=prazo_int,
            orgao=(raw.get("orgao") or None),
            sources=sources,
            prazo_fonte=prazo_fonte,
        )
    except Exception:  # noqa: BLE001 — etapa malformada não derruba a materialização
        logger.warning("rota_materializer: etapa descartada (malformada)", extra={"titulo": titulo})
        return None


def _norma_ref(etapa: Etapa) -> str | None:
    """Citação denormalizada — 1ª fonte ``legislacao`` com descrição (p/ display+dedupe)."""
    for src in etapa.sources:
        if src.tipo == "legislacao" and src.descricao:
            return src.descricao.strip()
    return None


def _passo_dedupe_key(rota_id: int, norma_ref: str | None, orgao: str | None, titulo: str) -> str:
    """Chave estável por (rota, norma, órgão, título). Espelha ``Acao.dedupe_key``
    (ADR-016). Exclui ``ordem`` (instável) e matrícula (a rota é por imóvel)."""
    raw = f"{norma_ref or ''}|{orgao or ''}|{titulo.strip().lower()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"r{rota_id}:{digest}"


# ---------------------------------------------------------------------------
# Materialização
# ---------------------------------------------------------------------------

def _run_legislacao(
    db: Session, *, process: Process, tenant_id: int, user_id: int | None, demand_type: str
) -> tuple[list[Etapa], str, str | None, int | None]:
    """Roda a ``LegislacaoAgent`` e devolve (etapas típadas, caminho, órgão, ai_job_id)."""
    ctx = AgentContext(
        tenant_id=tenant_id,
        user_id=user_id,
        process_id=process.id,
        session=db,
        metadata={"demand_type": demand_type},
    )
    result = AgentRegistry.create("legislacao", ctx).run()
    if not result.success:
        raise RuntimeError(result.error or "Falha ao executar a LegislacaoAgent")

    data = result.data if isinstance(result.data, dict) else {}
    etapas = [e for e in (_etapa_from_raw(r) for r in data.get("etapas", []) or []) if e]
    caminho = str(data.get("caminho_regulatorio") or "") or None
    orgao = str(data.get("orgao_competente") or "") or None
    return etapas, caminho, orgao, result.ai_job_id


def _upsert_rota(
    db: Session,
    *,
    process: Process,
    tenant_id: int,
    demand_type: str,
    caminho: str | None,
    orgao: str | None,
    ai_job_id: int | None,
) -> Rota:
    rota = (
        db.query(Rota)
        .filter(
            Rota.tenant_id == tenant_id,
            Rota.process_id == process.id,
            Rota.demand_type == demand_type,
        )
        .first()
    )
    if rota is None:
        rota = Rota(
            tenant_id=tenant_id,
            process_id=process.id,
            demand_type=demand_type,
            status=RotaStatus.proposta,
            caminho_regulatorio=caminho,
            orgao_competente=orgao,
            source_ai_job_id=ai_job_id,
        )
        db.add(rota)
        db.flush()  # precisa do id para compor dedupe_key dos passos
    else:
        rota.source_ai_job_id = ai_job_id
        # Narrativa da rota é da IA (não é campo editado passo-a-passo pelo
        # consultor) — pode atualizar sem violar "não sobrescrever edição humana".
        if caminho:
            rota.caminho_regulatorio = caminho
        if orgao:
            rota.orgao_competente = orgao
    return rota


def _reconcile_passos(
    *, rota: Rota, tenant_id: int, etapas: list[Etapa]
) -> tuple[int, int, bool]:
    """Reconcilia as ``etapas`` da IA contra os ``RotaPasso`` existentes.

    Regras (aditiva, mediada por humano):
    - passo IA novo (dedupe não casa) → insere ``origem=ia, status=proposto``;
    - passo IA que casa dedupe → PRESERVA ordem/edições/classificação; NÃO
      sobrescreve conteúdo (a 1ª materialização vale) — só sinaliza diff;
    - passo ``origem=manual`` → NUNCA tocado (chave própria, nunca casa aqui);
    - remoção pela IA não apaga passo existente (mediado por humano).

    Retorna ``(created, matched, is_diff)``.
    """
    existing = {p.dedupe_key: p for p in rota.passos}
    max_ordem = max((p.ordem for p in rota.passos), default=0)

    created = 0
    matched = 0
    seen: set[str] = set()

    for etapa in etapas:
        norma = _norma_ref(etapa)
        key = _passo_dedupe_key(rota.id, norma, etapa.orgao, etapa.titulo)
        if key in seen:
            continue
        seen.add(key)

        match = existing.get(key)
        if match is None:
            max_ordem += 1
            passo = RotaPasso(
                tenant_id=tenant_id,
                ordem=max_ordem,
                titulo=etapa.titulo,
                descricao=etapa.descricao,
                orgao=etapa.orgao,
                prazo_estimado_dias=etapa.prazo_estimado_dias,
                prazo_fonte=etapa.prazo_fonte,
                sources=[s.model_dump() for s in etapa.sources],
                norma_ref=norma,
                origem=RotaPassoOrigem.ia,
                status=RotaPassoStatus.proposto,
                dedupe_key=key,
            )
            # Anexa à relação (não db.add + rota_id): mantém rota.passos coerente
            # em memória logo após a materialização, sem exigir refresh.
            rota.passos.append(passo)
            created += 1
        else:
            matched += 1
            # NÃO sobrescreve: preserva ordem/edição/classificação do consultor.

    # Diff = a IA trouxe passo novo, OU sumiu com algum passo IA antes presente.
    ia_keys_antes = {
        k for k, p in existing.items() if p.origem == RotaPassoOrigem.ia
    }
    removed_by_ia = ia_keys_antes - seen
    is_diff = created > 0 or bool(removed_by_ia)
    return created, matched, is_diff


def materialize_rota(
    db: Session, *, process: Process, tenant_id: int, user_id: int | None = None
) -> RotaMaterializeResult:
    """Roda a legislação e materializa/reconcilia a Rota do processo.

    Não comita — o caller decide a transação. A Rota é keyed por
    ``demand_type`` do processo (a IA hoje keia por demanda, não por passivo —
    religar ``auditor→legislacao`` é follow-on, REGISTRO_DIVIDAS).
    """
    demand_type = (
        process.demand_type.value
        if getattr(process, "demand_type", None)
        else "nao_identificado"
    )

    etapas, caminho, orgao, ai_job_id = _run_legislacao(
        db, process=process, tenant_id=tenant_id, user_id=user_id, demand_type=demand_type
    )
    rota = _upsert_rota(
        db,
        process=process,
        tenant_id=tenant_id,
        demand_type=demand_type,
        caminho=caminho,
        orgao=orgao,
        ai_job_id=ai_job_id,
    )
    created, matched, is_diff = _reconcile_passos(
        rota=rota, tenant_id=tenant_id, etapas=etapas
    )

    # Ficha §9: se a rota JÁ estava validada e a IA trouxe diferença, NÃO
    # rebaixa o conteúdo assinado — marca 'desatualizada' e trava "Fechar rota"
    # até o consultor aceitar o diff. IA propõe, humano decide.
    if rota.status == RotaStatus.validada and is_diff:
        rota.status = RotaStatus.desatualizada

    db.flush()
    # Reflete a verdade do banco (passos manuais adicionados por outro caminho,
    # ordenação) no objeto retornado — a relação carrega ordenada por `ordem`.
    db.expire(rota, ["passos"])
    logger.info(
        "rota_materialized",
        extra={
            "process_id": process.id,
            "tenant_id": tenant_id,
            "rota_id": rota.id,
            "demand_type": demand_type,
            "passos_created": created,
            "passos_matched": matched,
            "is_diff": is_diff,
            "status": rota.status.value,
        },
    )
    return RotaMaterializeResult(rota=rota, created=created, matched=matched, is_diff=is_diff)
