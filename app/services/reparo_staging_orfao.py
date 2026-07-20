"""Reparo do staging órfão (`process_id` NULL) — caso 15 e afins.

Extração disparada enquanto o documento ainda estava no rascunho do intake
gravava staging sem `process_id`. O dado ficava no banco e invisível para a
Conferência, a matriz e a fonte única, que filtram por processo.

As duas camadas do fix (`extrator.py` e a migração draft→processo em
`intake.py`) impedem novos órfãos. Este módulo repara os que já existem.

**Decisão do André (2026-07-20), com a evidência do caso 15:** híbrido.

* Campo órfão que **também existe** na leva vinculada → **apagar** a órfã. Adotar
  criaria pares duplicados na Conferência da Isis e empurraria a sujeira para um
  dedup futuro.
* Campo órfão que é a **única leitura** daquele campo naquele documento →
  **adotar** (preencher `process_id`). Apagar perderia informação — no caso 15
  seria a `averbacao_rl` da matrícula 6.776, justamente um campo da cadeia
  jurídica onde a Matrícula é a fonte que vence (Ficha 08 §4).

**`field_value` NUNCA é tocado.** A adoção altera só o dono da linha. O bug
dict→text que derrubou a consolidação (#81) nasceu de reserializar valor de
`averbacao_app`/`averbacao_rl`; o reparo não chega perto disso — nem lê o valor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.extracted_field_staging import ExtractedFieldStaging


@dataclass
class LinhaOrfa:
    staging_id: int
    document_id: int
    process_id_alvo: Optional[int]
    field_name: str
    acao: str            # "adotar" | "apagar"
    motivo: str


@dataclass
class RelatorioReparo:
    executado: bool
    linhas: list[LinhaOrfa] = field(default_factory=list)
    sem_dono: int = 0        # órfã cujo documento também não tem processo

    @property
    def adotar(self) -> list[LinhaOrfa]:
        return [linha for linha in self.linhas if linha.acao == "adotar"]

    @property
    def apagar(self) -> list[LinhaOrfa]:
        return [linha for linha in self.linhas if linha.acao == "apagar"]


def planejar_reparo(
    db: Session,
    *,
    process_ids: Optional[list[int]] = None,
    executar: bool = False,
) -> RelatorioReparo:
    """Decide, linha a linha, entre adotar e apagar. Dry-run por default."""
    rel = RelatorioReparo(executado=executar)

    q = (
        db.query(ExtractedFieldStaging, Document.process_id)
        .join(Document, Document.id == ExtractedFieldStaging.document_id)
        .filter(
            ExtractedFieldStaging.process_id.is_(None),
            Document.deleted_at.is_(None),
        )
    )
    if process_ids:
        q = q.filter(Document.process_id.in_(process_ids))

    orfas = q.order_by(ExtractedFieldStaging.document_id, ExtractedFieldStaging.field_name).all()

    for linha, doc_process_id in orfas:
        if doc_process_id is None:
            # O documento também não tem processo: ainda é rascunho de verdade.
            # Não há dono para adotar — deixar quieto é o certo; a migração
            # draft→processo adota quando o caso for criado.
            rel.sem_dono += 1
            continue

        # Existe a MESMA leitura já vinculada ao processo?
        redundante = (
            db.query(ExtractedFieldStaging.id)
            .filter(
                ExtractedFieldStaging.document_id == linha.document_id,
                ExtractedFieldStaging.field_name == linha.field_name,
                ExtractedFieldStaging.process_id == doc_process_id,
            )
            .first()
            is not None
        )

        if redundante:
            acao, motivo = "apagar", "já existe a mesma leitura vinculada ao processo"
        else:
            acao, motivo = "adotar", "ÚNICA leitura deste campo — apagar perderia o dado"

        rel.linhas.append(LinhaOrfa(
            staging_id=linha.id,
            document_id=linha.document_id,
            process_id_alvo=doc_process_id,
            field_name=linha.field_name,
            acao=acao,
            motivo=motivo,
        ))

    if executar:
        for item in rel.adotar:
            # SÓ o dono muda. `field_value` intocado — ver nota do módulo (#81).
            db.query(ExtractedFieldStaging).filter(
                ExtractedFieldStaging.id == item.staging_id
            ).update(
                {ExtractedFieldStaging.process_id: item.process_id_alvo},
                synchronize_session=False,
            )
        ids_apagar = [item.staging_id for item in rel.apagar]
        if ids_apagar:
            db.query(ExtractedFieldStaging).filter(
                ExtractedFieldStaging.id.in_(ids_apagar)
            ).delete(synchronize_session=False)
        db.flush()

    return rel
