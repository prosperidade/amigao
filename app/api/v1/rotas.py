"""Endpoints da Rota Regulatória (E5, Sprint 2).

* ``GET   /processes/{process_id}/rota``                 (rota + passos ordenados)
* ``POST  /processes/{process_id}/rota/gerar``           (materializa da IA; reconcilia)
* ``PATCH /rotas/{rota_id}/reordenar``                   (nova ordem dos passos)
* ``PATCH /rotas/{rota_id}/passos/{passo_id}``           (edita título/prazo/órgão/classificação)
* ``POST  /rotas/{rota_id}/passos``                      (adiciona passo manual — Ficha §9)
* ``DELETE /rotas/{rota_id}/passos/{passo_id}``
* ``POST  /rotas/{rota_id}/passos/{passo_id}/validar``   (exige classificação — Princípio 1)
* ``POST  /rotas/{rota_id}/fechar``                      (todos validados; AuditLog hash chain)
* ``GET   /processes/{process_id}/rota/regeneracao-previa`` (o que a atualização vai fazer)
* ``GET   /rotas/{rota_id}/versoes``                     (histórico — nada se perde)

Auth: perfil ``internal``. Tenant isolation em todas as queries.

Princípio 1 (a IA propõe; o consultor decide e assina): a materialização propõe
passos; reordenar/classificar/validar/fechar são decisões humanas. "Fechar rota"
grava um ``AuditLog`` com hash chain SHA-256 (Princípio 2 — auditável).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.process import Process
from app.models.rota import (
    Rota,
    RotaPasso,
    RotaPassoOrigem,
    RotaPassoStatus,
    RotaStatus,
)
from app.models.user import User
from app.schemas.rota import (
    RotaMaterializeOut,
    RotaOut,
    RotaPassoCreate,
    RotaPassoOut,
    RotaPassoUpdate,
    RotaRegeneracaoPrevia,
    RotaReorder,
    RotaVersaoOut,
)
from app.services.audit_hash import stamp_audit_hash
from app.services.rota_materializer import materialize_rota

process_router = APIRouter()
rota_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_process_or_404(db: Session, process_id: int, tenant_id: int) -> Process:
    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if process is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")
    return process


def _get_rota_or_404(db: Session, rota_id: int, tenant_id: int) -> Rota:
    rota = (
        db.query(Rota)
        .filter(Rota.id == rota_id, Rota.tenant_id == tenant_id)
        .first()
    )
    if rota is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota não encontrada")
    return rota


def _get_passo_or_404(db: Session, rota_id: int, passo_id: int, tenant_id: int) -> RotaPasso:
    passo = (
        db.query(RotaPasso)
        .filter(
            RotaPasso.id == passo_id,
            RotaPasso.rota_id == rota_id,
            RotaPasso.tenant_id == tenant_id,
        )
        .first()
    )
    if passo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passo {passo_id} não encontrado nesta rota",
        )
    return passo


def _audit(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    rota_id: int,
    action: str,
    old_value: str | None = None,
    new_value: str | None = None,
    details: str | None = None,
) -> None:
    """AuditLog com hash chain SHA-256 (Princípio 2 — auditável)."""
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="rota",
        entity_id=rota_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        details=details,
    )
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)


# ---------------------------------------------------------------------------
# /processes/{process_id}/rota
# ---------------------------------------------------------------------------


@process_router.get("/{process_id}/rota", response_model=RotaOut | None)
def get_rota(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Rota | None:
    """Rota do processo (com passos ordenados). ``null`` se ainda não materializada."""
    _get_process_or_404(db, process_id, current_user.tenant_id)
    return (
        db.query(Rota)
        .filter(Rota.process_id == process_id, Rota.tenant_id == current_user.tenant_id)
        .order_by(Rota.id.desc())
        .first()
    )


@process_router.post(
    "/{process_id}/rota/gerar",
    response_model=RotaMaterializeOut,
    status_code=status.HTTP_201_CREATED,
)
def gerar_rota(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RotaMaterializeOut:
    """Roda a LegislacaoAgent e materializa/reconcilia a Rota (aditiva, não-destrutiva)."""
    process = _get_process_or_404(db, process_id, current_user.tenant_id)
    try:
        result = materialize_rota(
            db, process=process, tenant_id=current_user.tenant_id, user_id=current_user.id
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao gerar a rota: {exc}",
        ) from exc

    _audit(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        rota_id=result.rota.id,
        action="rota_materializada",
        new_value=result.rota.status.value,
        details=f"created={result.created} matched={result.matched} diff={result.is_diff}",
    )
    db.commit()
    db.refresh(result.rota)
    return RotaMaterializeOut(
        created=result.created,
        matched=result.matched,
        is_diff=result.is_diff,
        rota=RotaOut.model_validate(result.rota),
        orgaos_corrigidos=result.orgaos_corrigidos,
        versao_preservada=result.versao_preservada,
    )


@process_router.get("/{process_id}/rota/regeneracao-previa", response_model=RotaRegeneracaoPrevia)
def previa_regeneracao(
    process_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RotaRegeneracaoPrevia:
    """O que vai acontecer se o consultor mandar a IA atualizar a rota.

    Existe para que o aviso da tela seja VERDADE conferida no servidor, e não uma
    frase otimista escrita no componente: diz quantos passos existem hoje e em
    que versão eles ficarão guardados. "Atualizar da IA apagou toda a rota"
    (30/07) nasceu de uma ação irreversível oferecida sem aviso.
    """
    from app.models.rota import RotaVersao  # noqa: PLC0415

    _get_process_or_404(db, process_id, current_user.tenant_id)
    rota = (
        db.query(Rota)
        .filter(Rota.process_id == process_id, Rota.tenant_id == current_user.tenant_id)
        .order_by(Rota.id.desc())
        .first()
    )
    if rota is None or not rota.passos:
        return RotaRegeneracaoPrevia(
            passos_atuais=0, versao_a_preservar=None,
            aviso="Nenhuma rota ainda — a IA vai propor a primeira.",
        )
    ultima = (
        db.query(func.max(RotaVersao.versao))
        .filter(RotaVersao.rota_id == rota.id)
        .scalar()
    ) or 0
    proxima = ultima + 1
    validados = sum(1 for p in rota.passos if p.status == RotaPassoStatus.validado)
    manuais = sum(1 for p in rota.passos if p.origem == RotaPassoOrigem.manual)
    detalhe = []
    if validados:
        detalhe.append(f"{validados} já validado(s)")
    if manuais:
        detalhe.append(f"{manuais} criado(s) por você")
    sufixo = f" ({', '.join(detalhe)})" if detalhe else ""
    return RotaRegeneracaoPrevia(
        passos_atuais=len(rota.passos),
        versao_a_preservar=proxima,
        aviso=(
            f"A rota atual — {len(rota.passos)} passo(s){sufixo} — será preservada "
            f"como versão {proxima} e continua consultável no histórico. Nada é "
            "apagado: a IA só acrescenta o que for novo."
        ),
    )


@rota_router.get("/{rota_id}/versoes", response_model=list[RotaVersaoOut])
def listar_versoes(
    rota_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> list[Any]:
    """Histórico da rota — cada foto guardada antes de uma regeneração."""
    from app.models.rota import RotaVersao  # noqa: PLC0415

    _get_rota_or_404(db, rota_id, current_user.tenant_id)
    return (
        db.query(RotaVersao)
        .filter(
            RotaVersao.rota_id == rota_id,
            RotaVersao.tenant_id == current_user.tenant_id,
        )
        .order_by(RotaVersao.versao.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# /rotas/{rota_id}
# ---------------------------------------------------------------------------


@rota_router.patch("/{rota_id}/reordenar", response_model=RotaOut)
def reordenar_rota(
    rota_id: int,
    payload: RotaReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Rota:
    """Persiste a ordem do consultor (o "aprendizado" do MVP é capturar este sinal)."""
    rota = _get_rota_or_404(db, rota_id, current_user.tenant_id)
    passos_by_id = {p.id: p for p in rota.passos}
    if set(payload.passo_ids) != set(passos_by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A lista de passos deve conter exatamente os passos desta rota.",
        )
    for ordem, passo_id in enumerate(payload.passo_ids, start=1):
        passos_by_id[passo_id].ordem = ordem
    db.commit()
    db.refresh(rota)
    return rota


@rota_router.post(
    "/{rota_id}/passos", response_model=RotaPassoOut, status_code=status.HTTP_201_CREATED
)
def add_passo_manual(
    rota_id: int,
    payload: RotaPassoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RotaPasso:
    """Adiciona um passo manual (Ficha §9). Nunca tocado por re-run da IA."""
    rota = _get_rota_or_404(db, rota_id, current_user.tenant_id)
    max_ordem = max((p.ordem for p in rota.passos), default=0)

    passo = RotaPasso(
        tenant_id=current_user.tenant_id,
        rota_id=rota.id,
        ordem=max_ordem + 1,
        titulo=payload.titulo,
        descricao=payload.descricao,
        orgao=payload.orgao,
        prazo_estimado_dias=payload.prazo_estimado_dias,
        prazo_fonte=None,
        sources=[],
        norma_ref=payload.norma_ref,
        classificacao=payload.classificacao,
        origem=RotaPassoOrigem.manual,
        origem_manual_nota=payload.origem_manual_nota,
        status=RotaPassoStatus.proposto,
        # Chave própria: passo manual nunca colide com IA nem com outro manual.
        dedupe_key=f"r{rota.id}:manual:tmp:{secrets.token_hex(6)}",
    )
    db.add(passo)
    db.flush()
    passo.dedupe_key = f"r{rota.id}:manual:p{passo.id}"
    db.commit()
    db.refresh(passo)
    return passo


@rota_router.patch("/{rota_id}/passos/{passo_id}", response_model=RotaPassoOut)
def editar_passo(
    rota_id: int,
    passo_id: int,
    payload: RotaPassoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RotaPasso:
    passo = _get_passo_or_404(db, rota_id, passo_id, current_user.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(passo, field, value)
    db.commit()
    db.refresh(passo)
    return passo


@rota_router.delete("/{rota_id}/passos/{passo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_passo(
    rota_id: int,
    passo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> None:
    passo = _get_passo_or_404(db, rota_id, passo_id, current_user.tenant_id)
    # Apagar passo é irreversível e era MUDO — na reconstituição de 30/07 dois
    # passos do caso 15 tinham sumido e não havia como saber quem, quando nem
    # qual era o conteúdo. O que sai da rota fica na trilha.
    _audit(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        rota_id=rota_id,
        action="rota_passo_removido",
        old_value=passo.titulo,
        details=(
            f"passo {passo.id} · ordem {passo.ordem} · origem "
            f"{passo.origem.value if passo.origem else '—'} · status "
            f"{passo.status.value if passo.status else '—'}"
        ),
    )
    db.delete(passo)
    db.commit()


@rota_router.post("/{rota_id}/passos/{passo_id}/validar", response_model=RotaPassoOut)
def validar_passo(
    rota_id: int,
    passo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> RotaPasso:
    """Valida um passo. Exige ``classificacao`` (Ficha §8.1: força faturável vs direção).

    Passo sem fonte normativa entra marcado (radar-não-cancela); o ato de validar
    é o reconhecimento do consultor — não recusamos por falta de norma.
    """
    rota = _get_rota_or_404(db, rota_id, current_user.tenant_id)
    passo = _get_passo_or_404(db, rota_id, passo_id, current_user.tenant_id)
    if passo.classificacao is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Classifique o passo (item de proposta ou direção) antes de validar.",
        )
    passo.status = RotaPassoStatus.validado

    # Transições da rota: primeira validação sai de 'proposta' para 'em_validacao';
    # se estava 'desatualizada' e não há mais passo pendente, o diff foi aceito.
    db.flush()
    pendentes = [p for p in rota.passos if p.status != RotaPassoStatus.validado]
    if not pendentes and rota.status in (RotaStatus.proposta, RotaStatus.desatualizada) or rota.status == RotaStatus.proposta:
        rota.status = RotaStatus.em_validacao

    db.commit()
    db.refresh(passo)
    return passo


@rota_router.post("/{rota_id}/fechar", response_model=RotaOut)
def fechar_rota(
    rota_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_internal_user),
) -> Rota:
    """Fecha (assina) a rota. Só habilita quando TODOS os passos estão validados.

    Rota ``desatualizada`` → 409 até o consultor validar os novos passos (aceitar
    o diff). O fechamento grava um ``AuditLog`` com hash chain (Princípio 2).

    Validação 02/08 — o impasse da E5. ``desatualizada`` também é marcada quando
    a IA REMOVE um passo (``is_diff`` cobre ``removed_by_ia``, ver
    ``rota_materializer._reconcile_passos``). Nesse caso não nasce passo novo:
    não há o que validar, ``validar_passo`` nunca dispara, a rota nunca sai de
    ``desatualizada`` e o 409 abaixo passava a valer para sempre. A consultora
    ficava presa na E5 com a tela dizendo "todos os passos validados" e o botão
    recusando — sem maçaneta nenhuma.

    Por isso o 409 agora exige TER o que validar. Com zero passos pendentes,
    clicar em "Fechar rota" É o aceite do diff — a decisão continua sendo humana
    e explícita, e vai para a auditoria como qualquer fechamento.
    """
    rota = _get_rota_or_404(db, rota_id, current_user.tenant_id)

    if not rota.passos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rota sem passos — nada a fechar.",
        )
    pendentes = [p for p in rota.passos if p.status != RotaPassoStatus.validado]
    if rota.status == RotaStatus.desatualizada and pendentes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rota desatualizada: valide os novos passos antes de fechar.",
        )
    if pendentes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{len(pendentes)} passo(s) ainda não validado(s). Valide todos antes de fechar.",
        )

    rota.status = RotaStatus.validada
    rota.validated_by = current_user.id
    rota.validated_at = datetime.now(UTC)
    db.flush()

    _audit(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        rota_id=rota.id,
        action="rota_fechada",
        new_value="validada",
        details=f"passos={len(rota.passos)}",
    )
    db.commit()
    db.refresh(rota)
    return rota
