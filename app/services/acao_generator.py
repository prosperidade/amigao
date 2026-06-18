"""Geração de ``Acao`` a partir do diagnóstico (Ficha 07 §2).

Cada **ação de remediação** do diagnóstico vira uma ``Acao`` com
``tipo_triagem="pendente"`` (aguardando triagem do consultor). A fonte vem do
contrato #70 (``SourceRef``): cada risco carrega ``sources``; cada afirmação
``categoria="acao"`` carrega ``fontes``. Nunca inventar fonte — sem fonte
identificável, injeta uma ``SourceRef`` ``sem_fonte`` (honestidade explícita).

**Idempotência** (Ficha 07 §2): a ``dedupe_key`` é derivada de
``process + passivo + título`` — estável entre versões do diagnóstico. Regerar
não duplica; só cria o que ainda não existe.

**Não altera o passivo**: a ação só REFERENCIA o passivo via ``vinculo_passivo``
(JSON solto, sem FK). Nada aqui escreve em ``RegulatoryIssue``/achado.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.acao import Acao, AcaoOrigem, AcaoStatus, AcaoTipoTriagem
from app.models.process import Process
from app.models.regulatory import RegulatoryDiagnosis

logger = get_logger(__name__)


def _dedupe_key(process_id: int, passivo_desc: str, titulo: str) -> str:
    """Chave estável por (processo, passivo, título). Cabe em String(120)."""
    raw = f"{passivo_desc.strip().lower()}|{titulo.strip().lower()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"p{process_id}:{digest}"


def _normalize_fontes(raw_fontes: Any, *, passivo_desc: str) -> list[dict[str, Any]]:
    """Normaliza a lista de fontes para o shape #70 (``SourceRef``).

    Tolerante: dicts válidos passam; entradas inválidas viram ``sem_fonte``.
    Lista vazia → uma ``SourceRef`` ``sem_fonte`` (nunca silenciar)."""
    # Import local pra evitar acoplar o módulo de schemas no import-time.
    from app.schemas.stage_output import SourceRef

    out: list[dict[str, Any]] = []
    if isinstance(raw_fontes, list):
        for item in raw_fontes:
            if not isinstance(item, dict):
                continue
            try:
                out.append(SourceRef(**item).model_dump())
            except Exception:
                # Fonte malformada — preserva o que dá como descrição, marca honesta.
                out.append(
                    SourceRef(
                        tipo="sem_fonte",
                        sem_fonte=True,
                        descricao=str(item)[:200],
                    ).model_dump()
                )
    if not out:
        out.append(
            SourceRef(
                tipo="sem_fonte",
                sem_fonte=True,
                descricao=f"Ação derivada de: {passivo_desc[:160]}" if passivo_desc else None,
            ).model_dump()
        )
    return out


def _iter_acoes_de_remediacao(content: dict[str, Any], diag_id: int):
    """Extrai (titulo, passivo_desc, fontes, vinculo) das ações do diagnóstico.

    Duas origens, ambas com fonte #70:
    - ``riscos[*].proximo_passo`` (ou ``mitigacao_sugerida`` legado) — o passivo
      é o próprio risco; fonte = ``risco.sources``.
    - ``afirmacoes[*]`` com ``categoria="acao"`` — fonte = ``afirmacao.fontes``.
    """
    riscos = content.get("riscos") if isinstance(content, dict) else None
    if isinstance(riscos, list):
        for idx, risco in enumerate(riscos):
            if not isinstance(risco, dict):
                continue
            titulo = (risco.get("proximo_passo") or risco.get("mitigacao_sugerida") or "").strip()
            if not titulo:
                continue
            passivo_desc = (
                risco.get("risco_identificado") or risco.get("descricao") or ""
            ).strip()
            yield {
                "titulo": titulo,
                "passivo_desc": passivo_desc,
                "fontes": risco.get("sources"),
                "vinculo": {
                    "tipo": "risco",
                    "ref": f"diag{diag_id}:risco:{idx}",
                    "descricao": passivo_desc or None,
                },
            }

    afirmacoes = content.get("afirmacoes") if isinstance(content, dict) else None
    if isinstance(afirmacoes, list):
        for idx, af in enumerate(afirmacoes):
            if not isinstance(af, dict):
                continue
            if af.get("categoria") != "acao":
                continue
            titulo = (af.get("texto") or "").strip()
            if not titulo:
                continue
            yield {
                "titulo": titulo,
                "passivo_desc": titulo,
                "fontes": af.get("fontes"),
                "vinculo": {
                    "tipo": "afirmacao",
                    "ref": f"diag{diag_id}:afirmacao:{idx}",
                    "descricao": titulo[:160],
                },
            }


def latest_diagnosis(db: Session, *, process_id: int, tenant_id: int) -> RegulatoryDiagnosis | None:
    """Versão mais recente do diagnóstico do processo (ou None)."""
    return (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.tenant_id == tenant_id,
        )
        .order_by(RegulatoryDiagnosis.version.desc())
        .first()
    )


def generate_acoes_from_diagnosis(
    db: Session,
    *,
    process: Process,
    tenant_id: int,
) -> tuple[list[Acao], int, int | None]:
    """Gera ações ``pendente`` a partir do diagnóstico mais recente do processo.

    Idempotente: pula o que já existe (por ``dedupe_key``). Não comita — o
    caller decide a transação. Retorna ``(criadas, puladas, versao_diagnostico)``.
    """
    diag = latest_diagnosis(db, process_id=process.id, tenant_id=tenant_id)
    if diag is None:
        return [], 0, None

    content = diag.content if isinstance(diag.content, dict) else {}

    # Chaves já existentes deste processo — evita 1 query por candidato.
    existing_keys = {
        row[0]
        for row in db.query(Acao.dedupe_key)
        .filter(
            Acao.tenant_id == tenant_id,
            Acao.process_id == process.id,
            Acao.dedupe_key.isnot(None),
        )
        .all()
    }

    created: list[Acao] = []
    skipped = 0
    seen_this_run: set[str] = set()

    for item in _iter_acoes_de_remediacao(content, diag.id):
        key = _dedupe_key(process.id, item["passivo_desc"], item["titulo"])
        if key in existing_keys or key in seen_this_run:
            skipped += 1
            continue
        seen_this_run.add(key)

        acao = Acao(
            tenant_id=tenant_id,
            process_id=process.id,
            titulo=item["titulo"],
            origem=AcaoOrigem.diagnostico,
            origem_descricao=item["passivo_desc"] or None,
            origem_fontes=_normalize_fontes(item["fontes"], passivo_desc=item["passivo_desc"]),
            vinculo_passivo=item["vinculo"],
            status=AcaoStatus.a_fazer,
            tipo_triagem=AcaoTipoTriagem.pendente,
            dedupe_key=key,
        )
        db.add(acao)
        created.append(acao)

    if created:
        db.flush()
        logger.info(
            "acoes_generated",
            extra={
                "process_id": process.id,
                "tenant_id": tenant_id,
                "diagnosis_version": diag.version,
                "acoes_created": len(created),
                "acoes_skipped": skipped,
            },
        )

    return created, skipped, diag.version
