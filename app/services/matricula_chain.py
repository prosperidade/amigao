"""
Dívida #60 — CADEIA DE FICHAS e VIGÊNCIA de matrícula.

Critério de domínio da Isis (inegociável): "vigente = matrícula da última
averbação; a ficha anterior vira HISTÓRICO — não soma, não gera lacuna, permanece
visível como linhagem". Caso-referência real: 2609→2923→4698 (lote 1B) e
4655→6776 (Shangri-lá → São Jorge).

Este módulo faz DUAS coisas, ambas DETERMINÍSTICAS (sem LLM):

1. DETECTA cadeias entre matrículas do MESMO imóvel e PROPÕE quais são fichas
   anteriores (``detect_chain_proposals``). Nunca aplica sozinho — a IA/heurística
   propõe, o consultor confirma (Princípio 1).
2. APLICA a decisão do consultor (``apply_chain``: marca a anterior como
   histórica, encadeada à vigente) e a REVERTE (``set_vigencia``). Tudo auditado
   (Princípio 2) e reversível.

Sinais de cadeia, em ordem de força:
  (a) ``registro_anterior`` da vigente == ``numero_matricula`` da anterior — o
      registro cita explicitamente a origem. É o mais forte e dá a DIREÇÃO
      (quem cita é a mais nova).
  (b) ``denominacao_anterior`` da vigente casa (norm_compare) com a
      ``denominacao_imovel`` da anterior E as áreas batem — o nome anterior
      lembrado pela ficha nova aponta a antiga. Direção idem (quem lembra é nova).
  (c) mesmo lote/gleba (token extraído da denominação) E área idêntica — sinal
      fraco; direção pelo maior número de matrícula (cartório emite crescente).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.services.audit_hash import stamp_audit_hash
from app.services.inconsistency_matrix import _clean_matricula_hint, norm_compare

logger = logging.getLogger(__name__)

# Áreas "batem" se a diferença relativa é ≤ 0,5% (tolerância de arredondamento
# cartorial entre fontes; NÃO confundir com divergência de fundo, que é maior).
_AREA_REL_TOL = 0.005

# Token de lote/gleba/quadra para o sinal (c): "lote 1B", "gleba são jorge",
# "quadra 04". Extraído da denominação — sinal fraco, exige área idêntica.
_LOTE_RE = re.compile(r"\b(lote|gleba|quadra|chac(?:ara|ára)|s[ií]tio)\s+([0-9a-z]+)\b")


@dataclass
class ChainProposal:
    """Proposta de que ``anterior`` é ficha anterior de ``vigente`` (Dívida #60).

    Confirmada → ``anterior`` vira histórica, encadeada (``superseded_by``) à
    vigente. É PROPOSTA: nada muda sem o clique do consultor."""

    anterior_id: int
    anterior_numero: Optional[str]
    vigente_id: int
    vigente_numero: Optional[str]
    sinal: str            # registro_anterior | denominacao_area | lote_area
    confianca: str        # alta | media | baixa
    evidencia: str


def _num(value: Any) -> Optional[str]:
    """Número de matrícula normalizado p/ comparação ("MATR. 2.923" → "2923")."""
    return _clean_matricula_hint(value)


def _area_close(a: Optional[float], b: Optional[float]) -> bool:
    """True se duas áreas batem dentro da tolerância cartorial (≤ 0,5%)."""
    if a is None or b is None:
        return False
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base <= _AREA_REL_TOL


def _area_identical(a: Optional[float], b: Optional[float]) -> bool:
    """True se áreas são idênticas a 4 casas (sinal (c), mais exigente)."""
    if a is None or b is None:
        return False
    return round(a, 4) == round(b, 4)


def _lote_token(denominacao: Optional[str]) -> Optional[str]:
    """Token de lote/gleba da denominação, normalizado ("Lote 1B" → "lote 1b")."""
    if not denominacao:
        return None
    m = _LOTE_RE.search(denominacao.lower())
    return f"{m.group(1)} {m.group(2)}" if m else None


def _numeric(numero: Optional[str]) -> Optional[int]:
    """Valor inteiro do número de matrícula (p/ direção do sinal (c))."""
    n = _num(numero)
    try:
        return int(n) if n else None
    except ValueError:
        return None


def detect_chain_proposals(prop: Any) -> list[ChainProposal]:
    """Propõe cadeias entre as matrículas VIGENTES de um imóvel (Dívida #60).

    Só olha vigentes (uma já-histórica não volta a ser proposta). Cada par
    produz no máximo UMA proposta, pelo sinal mais forte que casar. Nunca aplica
    — devolve propostas para a Conferência exibir pré-marcadas."""
    mats = [m for m in prop.matriculas_vigentes()] if prop is not None else []
    proposals: list[ChainProposal] = []
    seen_pairs: set[frozenset] = set()

    for v in mats:
        for a in mats:
            if v.id == a.id:
                continue
            pair = frozenset((v.id, a.id))

            # ── Sinal (a) — registro_anterior explícito (mais forte) ──────────
            reg_ant = _num(getattr(v, "registro_anterior", None))
            if reg_ant and reg_ant == _num(a.numero_matricula):
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                proposals.append(ChainProposal(
                    anterior_id=a.id, anterior_numero=a.numero_matricula,
                    vigente_id=v.id, vigente_numero=v.numero_matricula,
                    sinal="registro_anterior", confianca="alta",
                    evidencia=(f"registro anterior da matrícula {v.numero_matricula} "
                               f"aponta a {a.numero_matricula}"),
                ))
                continue

            # ── Sinal (b) — denominacao_anterior casa + áreas batem ───────────
            den_ant = getattr(v, "denominacao_anterior", None)
            if (den_ant and a.denominacao_imovel
                    and norm_compare(den_ant, field="denominacao_imovel")
                    == norm_compare(a.denominacao_imovel, field="denominacao_imovel")
                    and _area_close(v.area_ha, a.area_ha)):
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                proposals.append(ChainProposal(
                    anterior_id=a.id, anterior_numero=a.numero_matricula,
                    vigente_id=v.id, vigente_numero=v.numero_matricula,
                    sinal="denominacao_area", confianca="media",
                    evidencia=(f"denominação anterior de {v.numero_matricula} "
                               f"('{den_ant}') casa com '{a.denominacao_imovel}' "
                               f"e as áreas batem"),
                ))
                continue

    # ── Sinal (c) — mesmo lote/gleba + área IDÊNTICA (fraco; direção pelo nº) ──
    for i, m1 in enumerate(mats):
        for m2 in mats[i + 1:]:
            pair = frozenset((m1.id, m2.id))
            if pair in seen_pairs:
                continue
            t1, t2 = _lote_token(m1.denominacao_imovel), _lote_token(m2.denominacao_imovel)
            if t1 and t1 == t2 and _area_identical(m1.area_ha, m2.area_ha):
                n1, n2 = _numeric(m1.numero_matricula), _numeric(m2.numero_matricula)
                # Maior número = mais recente = vigente (cartório emite crescente).
                if n1 is not None and n2 is not None and n1 != n2:
                    vig, ant = (m1, m2) if n1 > n2 else (m2, m1)
                else:
                    continue  # sem direção confiável — não propõe (evita falso)
                seen_pairs.add(pair)
                proposals.append(ChainProposal(
                    anterior_id=ant.id, anterior_numero=ant.numero_matricula,
                    vigente_id=vig.id, vigente_numero=vig.numero_matricula,
                    sinal="lote_area", confianca="baixa",
                    evidencia=(f"mesmo lote/gleba ('{t1}') e área idêntica "
                               f"({m1.area_ha} ha); {vig.numero_matricula} é mais recente"),
                ))

    return proposals


def apply_chain(
    db: Session, *, tenant_id: int, property_id: int,
    pairs: list[tuple[int, int]], user_id: Optional[int] = None,
) -> dict[str, Any]:
    """Aplica a decisão do consultor: marca cada ANTERIOR como histórica,
    encadeada à VIGENTE (Dívida #60). 1 clique confirma a cadeia inteira.

    ``pairs``: lista de (anterior_id, vigente_id). Idempotente (reaplicar não
    muda nada). Valida que ambas pertencem ao imóvel/tenant. Auditado."""
    from app.models.matricula import Matricula  # noqa: PLC0415

    mats = {
        m.id: m
        for m in db.query(Matricula).filter(
            Matricula.tenant_id == tenant_id,
            Matricula.property_id == property_id,
        ).all()
    }
    aplicadas: list[dict[str, Any]] = []
    for anterior_id, vigente_id in pairs:
        anterior = mats.get(anterior_id)
        vigente = mats.get(vigente_id)
        if anterior is None or vigente is None or anterior_id == vigente_id:
            continue
        if anterior.vigencia == "historica" and anterior.superseded_by_id == vigente_id:
            continue  # já aplicado (idempotente)
        anterior.vigencia = "historica"
        anterior.superseded_by_id = vigente_id
        aplicadas.append({
            "anterior_id": anterior_id, "anterior_numero": anterior.numero_matricula,
            "vigente_id": vigente_id, "vigente_numero": vigente.numero_matricula,
        })
    if aplicadas:
        db.flush()
        _audit(db, tenant_id, property_id, user_id, "cadeia_aplicada",
               {"property_id": property_id, "aplicadas": aplicadas})
        db.commit()
    return {"aplicadas": aplicadas, "count": len(aplicadas)}


def set_vigencia(
    db: Session, *, tenant_id: int, property_id: int, matricula_id: int,
    vigencia: str, superseded_by_id: Optional[int] = None, user_id: Optional[int] = None,
):
    """Define a vigência de UMA matrícula (reversão em Dados / ajuste manual).

    ``vigencia='vigente'`` limpa o encadeamento (volta a somar); ``'historica'``
    exige uma vigente que a substitui (``superseded_by_id``). Auditado."""
    from fastapi import HTTPException  # noqa: PLC0415

    from app.models.matricula import Matricula  # noqa: PLC0415

    if vigencia not in ("vigente", "historica"):
        raise HTTPException(status_code=422, detail="vigencia deve ser 'vigente' ou 'historica'.")

    mat = (
        db.query(Matricula)
        .filter(
            Matricula.id == matricula_id,
            Matricula.tenant_id == tenant_id,
            Matricula.property_id == property_id,
        )
        .first()
    )
    if mat is None:
        raise HTTPException(status_code=404, detail="Matrícula não encontrada.")

    antes = mat.vigencia
    if vigencia == "vigente":
        mat.vigencia = "vigente"
        mat.superseded_by_id = None
    else:
        if superseded_by_id is None or superseded_by_id == matricula_id:
            raise HTTPException(
                status_code=422,
                detail="Marcar como histórica exige 'superseded_by_id' de outra matrícula vigente.",
            )
        alvo = (
            db.query(Matricula)
            .filter(
                Matricula.id == superseded_by_id,
                Matricula.tenant_id == tenant_id,
                Matricula.property_id == property_id,
            )
            .first()
        )
        if alvo is None:
            raise HTTPException(status_code=404, detail="Matrícula vigente (superseded_by) não encontrada.")
        mat.vigencia = "historica"
        mat.superseded_by_id = superseded_by_id

    db.flush()
    _audit(db, tenant_id, property_id, user_id, "vigencia_alterada", {
        "matricula_id": matricula_id, "numero": mat.numero_matricula,
        "de": antes, "para": mat.vigencia, "superseded_by_id": mat.superseded_by_id,
    })
    db.commit()
    db.refresh(mat)
    return mat


def _audit(db: Session, tenant_id: int, property_id: int, user_id: Optional[int],
           action: str, details: dict[str, Any]) -> None:
    """AuditLog com hash chain SHA-256 (Princípio 2 — tudo auditável)."""
    log = AuditLog(
        tenant_id=tenant_id, user_id=user_id, entity_type="property",
        entity_id=property_id, action=action,
        details=json.dumps(details, ensure_ascii=False, default=str),
    )
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)
