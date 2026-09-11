"""STATE-001 — uma função por indicador, nunca recalculado em cada tela.

Frente H (ADR-068). Medido em `docs/auditoria/AUDITORIA_INDEPENDENTE_FASE1_
2026-09.md` bloco E e `AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md` bloco C:
pelo menos seis lugares respondiam "quanto falta neste processo?" com contas
independentes — checklist (`checklist_engine`), barra da macroetapa
(`macroetapa_engine`), staging preparado (frontend, `ConsolidacaoPanel.tsx`),
`consolidated_at` por linha (`processes.py`), resultado da última consolidação
(`campos_gravados`, `staging_consolidation.py`) e o `checklist_summary` do
dossiê (`dossier.py`, que reimplementava a MESMA conta do checklist — bug
incluído).

A conclusão da auditoria Astra (bloco C) é o desenho desta frente: **não são
seis números que devam ser sempre iguais** — são famílias de cálculo que
respondem perguntas DIFERENTES:

- "quantos documentos entraram?" → checklist documental (`checklist_engine`,
  já era a única fonte canônica — só faltava consertar o bug e parar de
  duplicar em `dossier.py`).
- "quantas ações desta etapa estão feitas?" → progresso da macroetapa
  (`macroetapa_engine.calculate_completion_pct`) — mede ATIVIDADE, não
  documento nem decisão. Legitimamente outro número.
- "quanto da Conferência está resolvido?" → **não existia função canônica**.
  É a que este módulo cria: `progresso_conferencia`, sobre a MESMA unidade
  que a Frente G (ADR-067) definiu — a Decisão, não o campo — reaproveitando
  `reconciliation_decisions.build_decisions` (que já expõe `Decisao.estado
  ∈ {pendente, decidida, gravada}`, sem coluna nova).

Toda tela/endpoint que precisa de um destes números chama a função — nunca
recalcula com sua própria lógica. Quando duas telas mostram números
diferentes, o rótulo tem de dizer que perguntas diferentes estão sendo
respondidas (Astra: "a tela tem que nomear cada um, não mostrar dois %").
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.extracted_field_staging import ExtractedFieldStaging
from app.services.reconciliation_decisions import build_decisions

_DECISAO_DECIDIDA = {"decidida", "gravada"}
# Mesmo conjunto que `reconciliation_decisions._DECIDIDOS` — uma linha
# `sem_agrupamento` usa o status bruto do staging, não o `estado` agregado
# de uma `Decisao` (que só existe para linhas agrupadas).
_STAGING_DECIDIDOS = {"aceito", "rejeitado"}


@dataclass
class ProgressoConferencia:
    """A resposta canônica para "quanto da Conferência está resolvido?".

    ``decisoes_total`` inclui tanto as `Decisao` agrupadas (ADR-067) quanto as
    linhas `sem_agrupamento` (Frente G as trata como decisão individual — cada
    uma ainda é algo que o consultor precisa decidir, só não tem par para
    agrupar). Nunca escondidas (Ficha 07: "nada some sem dizer").
    """

    process_id: int
    decisoes_total: int
    decididas: int
    gravadas: int
    pendentes: int

    def to_dict(self) -> dict:
        return {
            "process_id": self.process_id,
            "decisoes_total": self.decisoes_total,
            "decididas": self.decididas,
            "gravadas": self.gravadas,
            "pendentes": self.pendentes,
        }


def progresso_conferencia(db: Session, *, tenant_id: int, process_id: int) -> ProgressoConferencia:
    """Única fonte de "quanto falta decidir/gravar na Conferência" de um processo.

    Recomputa a qualquer leitura — mesma filosofia de `reconciliation_
    decisions.build_decisions`: nenhum estado a sincronizar, nada fica velho.
    """
    rows = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
        )
        .all()
    )
    resultado = build_decisions(rows)
    by_id = {r.id: r for r in rows}

    decididas = 0
    gravadas = 0
    for decisao in resultado.decisoes:
        if decisao.estado in _DECISAO_DECIDIDA:
            decididas += 1
        if decisao.estado == "gravada":
            gravadas += 1

    for item in resultado.sem_agrupamento:
        row = by_id.get(item.get("staging_id"))
        if row is None:
            continue
        status_val = row.status.value if hasattr(row.status, "value") else row.status
        if row.consolidated_at is not None:
            decididas += 1
            gravadas += 1
        elif status_val in _STAGING_DECIDIDOS:
            decididas += 1

    decisoes_total = len(resultado.decisoes) + len(resultado.sem_agrupamento)
    return ProgressoConferencia(
        process_id=process_id,
        decisoes_total=decisoes_total,
        decididas=decididas,
        gravadas=gravadas,
        pendentes=decisoes_total - decididas,
    )
