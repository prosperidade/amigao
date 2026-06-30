"""Dedupe de ``RegulatoryIssue`` — idempotência da geração + saneamento retroativo.

**Origem do bug (medido no caso 13 / property 10):** ``auditor_imovel._persist_issues``
inseria um ``RegulatoryIssue`` por finding a CADA execução da chain, sem checar se
um achado idêntico já existia. Como o auditor roda toda vez que a etapa E2/E4
re-roda os agentes, o mesmo ``VERIFICACAO_ESPACIAL_PENDENTE`` acumulou 11 linhas
idênticas (ids 18..28) ao longo de ~2 semanas — todas com o mesmo
``codigo_alerta`` / ``tema`` / ``descricao``. O problema é de GERAÇÃO (banco com
duplicatas), não de exibição.

**Chave de dedupe (perene no imóvel):** ``(property_id, codigo_alerta|type,
tema, descricao)``. O achado é perene em ``Property`` (ADR-012), por isso a chave
é por imóvel — não por processo. Inclui ``descricao`` para não colapsar achados
distintos que apenas compartilham o ``codigo_alerta`` (ex.: duas divergências de
área em matrículas diferentes têm ``descricao`` distinta e devem coexistir).

Espelha o padrão ``dedupe_key`` do ``acao_generator`` (Ficha 07 §2): regerar não
duplica. NÃO apaga achados com decisão do consultor (``status_achado`` ≠
``suspeita``, ``status_saneamento`` ≠ ``pendente``, ou com ``ProcessIssueDecision``
vinculada): numa duplicata decidida, a linha com decisão é preservada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


def issue_dedupe_key(
    *,
    property_id: int,
    codigo_alerta: Optional[str],
    type_legacy: Optional[str] = None,
    tema: Optional[str],
    descricao: Optional[str],
) -> str:
    """Chave canônica de um achado regulatório para fins de idempotência.

    ``codigo_alerta`` é a identidade preferida (taxonomia rica, PROMPT_5); para
    registros legados sem código usa-se o ``type`` antigo. ``tema`` + ``descricao``
    desempatam achados de mesmo código em alvos diferentes.
    """
    ident = codigo_alerta or (f"type:{type_legacy}" if type_legacy else "?")
    return "|".join(
        [
            str(property_id),
            ident,
            (tema or "").strip(),
            (descricao or "").strip(),
        ]
    )


@dataclass
class SaneamentoAlertasResult:
    """Resultado do saneamento retroativo de alertas duplicados."""

    rows_before: int = 0
    rows_after: int = 0
    duplicates_removed: int = 0
    groups_collapsed: int = 0
    decisions_preserved: int = 0
    conflicts: list[str] = field(default_factory=list)  # grupos com decisões conflitantes
    details: list[str] = field(default_factory=list)

    @property
    def total_removed(self) -> int:
        return self.duplicates_removed


def _is_decided(issue: Any, decided_issue_ids: set[int]) -> bool:
    """Um achado é 'decidido' (preservar sempre) quando carrega sinal humano:
    consultor mexeu no ``status_achado`` (≠ suspeita) ou ``status_saneamento``
    (≠ pendente), ou há uma ``ProcessIssueDecision`` apontando para ele.
    """
    from app.models.regulatory import StatusAchado, StatusSaneamento  # noqa: PLC0415

    if issue.id in decided_issue_ids:
        return True
    if issue.status_achado is not None and issue.status_achado != StatusAchado.suspeita:
        return True
    return (
        issue.status_saneamento is not None
        and issue.status_saneamento != StatusSaneamento.pendente
    )


def sanear_alertas_duplicados(
    session: Session,
    *,
    tenant_id: int,
    property_id: Optional[int] = None,
    dry_run: bool = False,
) -> SaneamentoAlertasResult:
    """Colapsa grupos de ``RegulatoryIssue`` não resolvidos que são duplicatas
    exatas (mesma ``issue_dedupe_key``), preservando o sinal humano.

    Regra por grupo (apenas linhas com ``resolved_at IS NULL``):
      - Linhas DECIDIDAS (sinal do consultor) são SEMPRE preservadas.
      - Se há ≥1 decidida, as NÃO decididas do grupo são removidas (ruído puro).
      - Se NÃO há decidida, mantém-se a MAIS RECENTE (maior ``detected_at``) e
        removem-se as demais.
      - Grupos com ≥2 decididas CONFLITANTES (ex.: uma ``confirmada`` e uma
        ``descartada``) são reportados em ``conflicts`` e NADA é apagado entre
        elas — a resolução é decisão humana (não destruímos julgamento).

    Idempotente: rodar de novo não remove nada na segunda passada.
    """
    from app.models.regulatory import ProcessIssueDecision, RegulatoryIssue  # noqa: PLC0415

    result = SaneamentoAlertasResult()

    q = session.query(RegulatoryIssue).filter(
        RegulatoryIssue.tenant_id == tenant_id,
        RegulatoryIssue.resolved_at.is_(None),
    )
    if property_id is not None:
        q = q.filter(RegulatoryIssue.property_id == property_id)
    issues = q.order_by(RegulatoryIssue.id.asc()).all()
    result.rows_before = len(issues)

    if not issues:
        result.rows_after = 0
        return result

    # Issues referenciadas por uma decisão contextual (FK CASCADE) — nunca apagar.
    decided_ids_rows = (
        session.query(ProcessIssueDecision.issue_id)
        .filter(ProcessIssueDecision.tenant_id == tenant_id)
        .all()
    )
    decided_issue_ids: set[int] = {r[0] for r in decided_ids_rows}

    # Agrupar por chave de dedupe.
    groups: dict[str, list[Any]] = {}
    for iss in issues:
        payload = iss.payload or {}
        key = issue_dedupe_key(
            property_id=iss.property_id,
            codigo_alerta=iss.codigo_alerta,
            type_legacy=iss.type.value if iss.type is not None else None,
            tema=payload.get("tema"),
            descricao=payload.get("descricao"),
        )
        groups.setdefault(key, []).append(iss)

    removed = 0
    for key, group in groups.items():
        if len(group) <= 1:
            continue

        decided = [g for g in group if _is_decided(g, decided_issue_ids)]
        undecided = [g for g in group if g not in decided]

        if len(decided) >= 2:
            # Conflito: ≥2 decididas (possivelmente confirmada × descartada).
            # Preserva todas as decididas; remove só o ruído não decidido.
            result.conflicts.append(
                f"{key} — {len(decided)} linhas decididas (ids="
                f"{[g.id for g in decided]}); resolução é humana"
            )
            result.decisions_preserved += len(decided)
            to_remove = undecided
            keepers = decided
        elif len(decided) == 1:
            keepers = decided
            to_remove = undecided
            result.decisions_preserved += 1
        else:
            # Sem decisão: mantém a mais recente.
            keepers = [max(group, key=lambda g: (g.detected_at, g.id))]
            to_remove = [g for g in group if g not in keepers]

        if not to_remove:
            continue

        result.groups_collapsed += 1
        result.details.append(
            f"grupo '{key}': mantidas ids={[g.id for g in keepers]}, "
            f"removidas ids={[g.id for g in to_remove]}"
        )
        for g in to_remove:
            removed += 1
            if not dry_run:
                session.delete(g)

    if not dry_run:
        session.flush()

    result.duplicates_removed = removed
    result.rows_after = result.rows_before - removed
    return result
