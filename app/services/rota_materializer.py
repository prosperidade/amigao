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
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func
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

# Proveniência declarada por etapa, indexada por `id()` do objeto — a `Etapa` é
# `extra=forbid` e não aceita campo novo, e criar um schema paralelo só para
# carregar duas strings custaria mais do que este mapa de vida curta (existe
# entre `_etapa_from_raw` e `_reconcile_passos`, na mesma chamada).
_ORIGEM_REFS: dict[int, list[str]] = {}


@dataclass
class RotaMaterializeResult:
    rota: Rota
    created: int
    matched: int
    is_diff: bool  # houve diferença vs. o snapshot anterior?
    # Órgãos que a IA citou fora das esferas do caso e o guard removeu (ADR-034).
    # Sobe até a tela: correção silenciosa esconderia que o agente errou de esfera.
    orgaos_corrigidos: list[dict[str, Any]] = field(default_factory=list)
    # Versão em que a rota anterior ficou guardada antes desta regeneração.
    versao_preservada: int | None = None


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
        etapa = Etapa(
            ordem=max(ordem, 1),
            titulo=titulo,
            descricao=(raw.get("descricao") or None),
            prazo_estimado_dias=prazo_int,
            orgao=(raw.get("orgao") or None),
            sources=sources,
            prazo_fonte=prazo_fonte,
        )
        # ADR-039 — a proveniência declarada pelo modelo viaja ao lado da Etapa
        # tipada (que é `extra=forbid` e não a comportaria). Fica crua aqui; quem
        # valida contra os achados/ações REAIS é `_reconcile_passos`.
        _ORIGEM_REFS[id(etapa)] = [
            str(r) for r in (raw.get("origem_refs") or []) if str(r).strip()
        ]
        return etapa
    except Exception:  # noqa: BLE001 — etapa malformada não derruba a materialização
        logger.warning("rota_materializer: etapa descartada (malformada)", extra={"titulo": titulo})
        return None


def orgao_fora_das_esferas(orgao: str | None, esferas: list[str]) -> bool:
    """O órgão pertence a uma esfera que este caso NÃO tem?

    Conservador de propósito: só acusa quando o órgão é RECONHECÍVEL e sua esfera
    está fora das do caso. Órgão não reconhecido ("Cliente / Advogado", cartório,
    um estado sem sigla catalogada) não é acusado — na dúvida não se apaga o
    trabalho do agente.
    """
    from app.services.esfera import esfera_do_orgao  # noqa: PLC0415

    if not orgao or not esferas:
        return False
    esfera = esfera_do_orgao(orgao)
    return esfera is not None and esfera not in esferas


def aplicar_esfera_do_caso(
    etapas: list[Etapa], caminho: str | None, orgao: str | None, esferas: list[str]
) -> tuple[list[Etapa], str | None, list[dict[str, Any]]]:
    """Guard determinístico da ADR-034 na Rota (validação 30/07).

    O prompt já recebe os órgãos do caso, mas prompt é pedido, não garantia — e o
    custo do erro aqui é prazo perdido, não retrabalho de tela. Em produção a
    Rota do caso 15 nasceu com TODOS os passos em "SEMAD"/"SEMAD-GO" para autos do
    **IBAMA**: "Protocolização da defesa administrativa na SEMAD".

    Quando o órgão de um passo é de esfera que o caso não tem, o órgão é
    **removido** (vira nulo) em vez de mantido: passo sem órgão o consultor
    completa; passo com o órgão ERRADO ele segue. O passo continua na rota —
    radar-não-cancela — e o que foi retirado volta em ``corrigidos`` para virar
    aviso na tela e linha de auditoria.
    """
    corrigidos: list[dict[str, Any]] = []
    if not esferas:
        return etapas, orgao, corrigidos

    saida: list[Etapa] = []
    for etapa in etapas:
        if orgao_fora_das_esferas(etapa.orgao, esferas):
            corrigidos.append({"passo": etapa.titulo, "orgao_removido": etapa.orgao})
            saida.append(etapa.model_copy(update={"orgao": None}))
        else:
            saida.append(etapa)

    orgao_final = orgao
    if orgao_fora_das_esferas(orgao, esferas):
        corrigidos.append({"passo": "(órgão competente da rota)", "orgao_removido": orgao})
        orgao_final = None
    return saida, orgao_final, corrigidos


def _norma_ref(etapa: Etapa) -> str | None:
    """Citação denormalizada — 1ª fonte ``legislacao`` com descrição (p/ display+dedupe)."""
    for src in etapa.sources:
        if src.tipo == "legislacao" and src.descricao:
            return src.descricao.strip()
    return None


def _identidade_passo(orgao: str | None, titulo: str) -> tuple[str, str]:
    """Identidade legível de um passo — o par que a chave nova resume."""
    return ((orgao or "").strip().lower(), (titulo or "").strip().lower())


def _passo_dedupe_key(rota_id: int, norma_ref: str | None, orgao: str | None, titulo: str) -> str:
    """Chave estável por (rota, órgão, título). Espelha ``Acao.dedupe_key`` (ADR-016).

    Exclui ``ordem`` (instável), matrícula (a rota é por imóvel) e — desde a
    validação de 30/07 — a ``norma_ref``.

    Por que a norma saiu: ela vem do ``fonte_trecho`` que o LLM escreve, e o LLM
    não é determinístico. Duas execuções produziam o MESMO passo com chaves
    diferentes, e a reconciliação "aditiva" duplicava a rota inteira em vez de
    casar. Medido em produção no caso 15: os pares 7/12 ("Recebimento e análise
    do auto de infração e notificação") e 8/13 ("Reunião e levantamento
    documental para defesa") — título e órgão idênticos, ``dedupe_key``
    diferentes. Foi essa enxurrada de duplicatas que levou a consultora a limpar
    a rota na mão e a relatar que "atualizar da IA apagou toda a rota".

    ``norma_ref`` continua PERSISTIDA no passo (display e proveniência) — só
    deixou de participar da identidade. O parâmetro fica na assinatura porque
    chamadores antigos o passam posicionalmente.
    """
    _ = norma_ref  # fora da identidade de propósito — ver docstring
    raw = f"{orgao or ''}|{titulo.strip().lower()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"r{rota_id}:{digest}"


# ---------------------------------------------------------------------------
# Materialização
# ---------------------------------------------------------------------------

def _run_legislacao(
    db: Session, *, process: Process, tenant_id: int, user_id: int | None, demand_type: str,
    bloco_fundamento: str = "",
) -> tuple[list[Etapa], str, str | None, int | None]:
    """Roda a ``LegislacaoAgent`` e devolve (etapas típadas, caminho, órgão, ai_job_id)."""
    ctx = AgentContext(
        tenant_id=tenant_id,
        user_id=user_id,
        process_id=process.id,
        session=db,
        # ADR-039: o diagnóstico fundamentado e as ações triadas entram AQUI.
        # Era esta chamada — sem `chain_data`, com metadata só de `demand_type` —
        # que fazia a rota nascer cega ao que o caso apurou.
        metadata={"demand_type": demand_type, "bloco_fundamento": bloco_fundamento},
    )
    result = AgentRegistry.create("legislacao", ctx).run()
    if not result.success:
        raise RuntimeError(result.error or "Falha ao executar a LegislacaoAgent")

    data = result.data if isinstance(result.data, dict) else {}
    etapas = [e for e in (_etapa_from_raw(r) for r in data.get("etapas", []) or []) if e]
    caminho = str(data.get("caminho_regulatorio") or "") or None
    orgao = str(data.get("orgao_competente") or "") or None
    return etapas, caminho, orgao, result.ai_job_id


def _snapshot_rota(rota: Rota) -> dict[str, Any]:
    """Foto serializável da rota + passos, como estão AGORA."""
    return {
        "rota": {
            "id": rota.id,
            "demand_type": rota.demand_type,
            "status": rota.status.value if rota.status else None,
            "caminho_regulatorio": rota.caminho_regulatorio,
            "orgao_competente": rota.orgao_competente,
            "validated_at": rota.validated_at.isoformat() if rota.validated_at else None,
        },
        "passos": [
            {
                "id": p.id,
                "ordem": p.ordem,
                "titulo": p.titulo,
                "descricao": p.descricao,
                "orgao": p.orgao,
                "prazo_estimado_dias": p.prazo_estimado_dias,
                "prazo_fonte": p.prazo_fonte,
                "norma_ref": p.norma_ref,
                "sources": p.sources,
                "classificacao": p.classificacao.value if p.classificacao else None,
                "origem": p.origem.value if p.origem else None,
                "origem_manual_nota": p.origem_manual_nota,
                "status": p.status.value if p.status else None,
                "dedupe_key": p.dedupe_key,
            }
            for p in rota.passos
        ],
    }


def preservar_versao(
    db: Session, *, rota: Rota, tenant_id: int, user_id: int | None,
    motivo: str = "regeneracao",
) -> int | None:
    """Congela o estado atual da rota como uma versão numerada. Devolve o número.

    Chamado ANTES de a IA reconciliar. Rota sem passos não vira versão (não há o
    que preservar, e uma lista de versões vazias só faz ruído).
    """
    from app.models.rota import RotaVersao  # noqa: PLC0415

    if rota is None or rota.id is None or not rota.passos:
        return None
    ultima = (
        db.query(func.max(RotaVersao.versao))
        .filter(RotaVersao.rota_id == rota.id)
        .scalar()
    )
    versao = (ultima or 0) + 1
    db.add(RotaVersao(
        tenant_id=tenant_id, rota_id=rota.id, versao=versao, motivo=motivo,
        snapshot=_snapshot_rota(rota), created_by_user_id=user_id,
    ))
    db.flush()
    return versao


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
    *, rota: Rota, tenant_id: int, etapas: list[Etapa], contexto: Any = None
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
    # Índice de compatibilidade: passos gravados ANTES de a `norma_ref` sair da
    # identidade têm chave legada. Sem isto, a primeira regeneração pós-mudança
    # duplicaria a rota inteira uma última vez — exatamente o que o fix combate.
    por_identidade = {
        _identidade_passo(p.orgao, p.titulo): p for p in rota.passos
        if p.origem == RotaPassoOrigem.ia
    }
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

        match = existing.get(key) or por_identidade.get(
            _identidade_passo(etapa.orgao, etapa.titulo)
        )
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
            # ADR-039 — proveniência: de qual achado e/ou ação este passo nasceu.
            # Só referência que casa com o que EXISTE neste caso é aceita; o
            # resto é descartado com log. Passo sem origem é honesto; passo com
            # origem inventada corromperia a corrente inteira.
            if contexto is not None:
                for ref in _ORIGEM_REFS.get(id(etapa), []):
                    issue_id, acao_id = contexto.resolver_ref(ref)
                    if issue_id is not None and passo.origem_issue_id is None:
                        passo.origem_issue_id = issue_id
                    elif acao_id is not None and passo.origem_acao_id is None:
                        passo.origem_acao_id = acao_id
                    elif issue_id is None and acao_id is None:
                        logger.warning(
                            "rota: origem declarada não existe neste caso — descartada",
                            extra={"rota_id": rota.id, "ref": ref, "passo": etapa.titulo},
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

    # Perda de trabalho do consultor = nunca mais (validação 30/07). A foto é
    # tirada ANTES de a IA rodar: se a regeneração falhar no meio, a versão já
    # está guardada; se der certo, o consultor tem para onde voltar.
    rota_atual = (
        db.query(Rota)
        .filter(
            Rota.tenant_id == tenant_id,
            Rota.process_id == process.id,
            Rota.demand_type == demand_type,
        )
        .first()
    )
    versao_preservada = preservar_versao(
        db, rota=rota_atual, tenant_id=tenant_id, user_id=user_id
    ) if rota_atual is not None else None

    # ── Guard do ADR-039: sem diagnóstico assinado, a rota NÃO é traçada ────
    # Gerar mesmo assim produziria uma peça formal fundamentada no relato do
    # cliente — plausível, assinável e errada. `DiagnosticoNaoFundamentado` sobe
    # até o endpoint e vira a frase que o consultor lê, com o próximo movimento.
    from app.services.rota_contexto import montar_contexto_rota  # noqa: PLC0415

    contexto = montar_contexto_rota(db, process=process, tenant_id=tenant_id)

    etapas, caminho, orgao, ai_job_id = _run_legislacao(
        db, process=process, tenant_id=tenant_id, user_id=user_id,
        demand_type=demand_type, bloco_fundamento=contexto.bloco_prompt(),
    )

    # ADR-034 na Rota (validação 30/07): a esfera vem de QUEM autuou, não da UF.
    esferas: list[str] = []
    try:
        from app.services.passivos_esfera import esferas_do_processo  # noqa: PLC0415

        esferas = list(esferas_do_processo(db, tenant_id, process.id))
    except Exception as exc:  # noqa: BLE001 — sem esfera o guard só não age
        logger.warning("rota_materializer: falha ao derivar esferas do caso: %s", exc)
    etapas, orgao, orgaos_corrigidos = aplicar_esfera_do_caso(
        etapas, caminho, orgao, esferas
    )
    if orgaos_corrigidos:
        logger.warning(
            "rota_orgao_fora_da_esfera",
            extra={
                "process_id": process.id, "tenant_id": tenant_id,
                "esferas_do_caso": esferas, "corrigidos": orgaos_corrigidos,
            },
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
        rota=rota, tenant_id=tenant_id, etapas=etapas, contexto=contexto
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
    return RotaMaterializeResult(
        rota=rota, created=created, matched=matched, is_diff=is_diff,
            orgaos_corrigidos=orgaos_corrigidos,
        versao_preservada=versao_preservada,
    )
