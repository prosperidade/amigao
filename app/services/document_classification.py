"""Persistência do tipo classificado por conteúdo (dívida #70).

`classify_doc_type` sempre soube dizer o tipo real de um documento a partir do
texto. O que faltava era **guardar a resposta**: em `extrator.py` o
`effective_type` era usado para escolher os campos do staging e morria no escopo
da função. Consequência medida no processo 15: **36 de 42 documentos com
`document_type = NULL`**, invisíveis para o vínculo com o checklist e para a
fonte única de requisitos (ADR-031), que lê o tipo persistido.

Este módulo é o ponto ÚNICO que decide "posso gravar este tipo?" — usado tanto
pelo extrator (ao vivo) quanto pelo backfill (retroativo). Ter duas
implementações da mesma regra é exatamente a classe que o ADR-031 acabou de
matar; não vamos recriá-la aqui.

**Decisão do André (2026-07-20), fechada:** o preenchimento é **só onde é NULL**.
Nunca sobrescreve um `document_type` já gravado — mesmo que o conteúdo discorde.
Um tipo existente pode ser correção manual do consultor, e desfazê-la em massa
seria pior que o problema. Divergência entre conteúdo e tipo gravado é
**achado a reportar**, candidato a alerta futuro, não escrita silenciosa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document


@dataclass
class ResultadoClassificacao:
    """O que aconteceu com um documento. `motivo` é legível para o relatório."""

    document_id: int
    tipo_anterior: Optional[str]
    tipo_proposto: Optional[str]
    gravado: bool
    item_vinculado: Optional[str] = None
    motivo: str = ""

    @property
    def divergente(self) -> bool:
        """Conteúdo discorda do tipo já gravado — achado, nunca escrita.

        É o sinal que a decisão do André manda apenas reportar.
        """
        return (
            self.tipo_anterior is not None
            and self.tipo_proposto is not None
            and self.tipo_anterior != self.tipo_proposto
        )


def _esta_vazio(valor: Optional[str]) -> bool:
    """NULL ou string vazia contam como "sem tipo".

    `"outro"` NÃO conta: é um valor gravado, e a decisão é não sobrescrever
    valor gravado. Documentos em `"outro"` aparecem no relatório como achado.
    """
    return valor is None or not valor.strip()


def aplicar_classificacao(
    db: Session,
    doc: Document,
    tipo_proposto: Optional[str],
    *,
    revincular: bool = True,
) -> ResultadoClassificacao:
    """Grava o tipo classificado quando (e só quando) o campo está vazio.

    Faz `flush`, nunca `commit`: quem chama decide a fronteira da transação — o
    extrator participa da transação do job, o backfill commita em lote.
    """
    res = ResultadoClassificacao(
        document_id=doc.id,
        tipo_anterior=doc.document_type,
        tipo_proposto=tipo_proposto,
        gravado=False,
    )

    if tipo_proposto is None or not tipo_proposto.strip() or tipo_proposto == "outro":
        res.motivo = "classificação não chegou a um tipo específico"
        return res

    if not _esta_vazio(doc.document_type):
        res.motivo = (
            f"tipo já gravado ({doc.document_type}) — preservado por decisão"
            if not res.divergente
            else (
                f"tipo já gravado ({doc.document_type}) diverge do conteúdo "
                f"({tipo_proposto}) — preservado; achado para revisão humana"
            )
        )
        return res

    doc.document_type = tipo_proposto
    res.gravado = True
    res.motivo = f"tipo ausente → gravado como {tipo_proposto}"
    db.flush()

    if revincular:
        res.item_vinculado = revincular_checklist(db, doc)

    return res


@dataclass
class RelatorioBackfill:
    escopo: str
    executado: bool
    candidatos: int = 0                  # NULL com texto salvo
    sem_texto: int = 0                   # NULL mas sem texto → precisa de OCR antes
    resultados: list[ResultadoClassificacao] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.resultados is None:
            self.resultados = []

    @property
    def gravados(self) -> list[ResultadoClassificacao]:
        return [r for r in self.resultados if r.gravado]

    @property
    def a_gravar(self) -> list[ResultadoClassificacao]:
        """Os que TÊM tipo específico — o número que importa no dry-run.

        `gravados` filtra pelo que foi de fato escrito e por isso zera no
        dry-run: o relatório dizia "seriam gravados: 0" quando eram 28.
        """
        return [
            r for r in self.resultados
            if r.tipo_proposto not in (None, "", "outro")
        ]

    @property
    def sem_tipo_definido(self) -> list[ResultadoClassificacao]:
        """Texto lido mas as regras não chegaram a um tipo específico."""
        return [r for r in self.resultados if not r.gravado and r.tipo_proposto in (None, "outro", "")]

    @property
    def vinculados(self) -> list[ResultadoClassificacao]:
        return [r for r in self.resultados if r.item_vinculado]


def planejar_backfill(
    db: Session,
    *,
    process_ids: Optional[list[int]] = None,
    tenant_id: Optional[int] = None,
    executar: bool = False,
) -> RelatorioBackfill:
    """Reclassifica documentos SEM tipo usando o texto que já está no banco.

    Custo zero de IA: `classify_doc_type` é rule-based sobre o texto já salvo —
    nada de re-OCR, nada de chamada a provider. O que custa LLM é a extração de
    campos (`extract_and_stage`), que este backfill **não** dispara.

    `executar=False` (default) é dry-run: classifica e relata sem gravar nada.
    """
    from app.services.ficha01_extraction import classify_doc_type  # noqa: PLC0415

    if not process_ids and tenant_id is None:
        raise ValueError("escopo obrigatório: informe process_ids ou tenant_id")

    q = db.query(Document).filter(
        Document.deleted_at.is_(None),
        (Document.document_type.is_(None)) | (Document.document_type == ""),
    )
    if process_ids:
        q = q.filter(Document.process_id.in_(process_ids))
    if tenant_id is not None:
        q = q.filter(Document.tenant_id == tenant_id)

    docs = q.order_by(Document.id).all()

    escopo = (
        f"processos {process_ids}" if process_ids else f"tenant {tenant_id}"
    )
    rel = RelatorioBackfill(escopo=escopo, executado=executar)

    for doc in docs:
        texto = (doc.extracted_text or "").strip()
        if not texto:
            # Sem texto não há o que classificar — precisa de OCR antes. Contado
            # à parte para não parecer que "o backfill não deu conta".
            rel.sem_texto += 1
            continue

        rel.candidatos += 1
        tipo = classify_doc_type(texto, None)

        if not executar:
            res = ResultadoClassificacao(
                document_id=doc.id,
                tipo_anterior=doc.document_type,
                tipo_proposto=tipo,
                gravado=False,
                motivo=(
                    f"[dry-run] gravaria {tipo}"
                    if tipo and tipo != "outro"
                    else "[dry-run] sem tipo específico — nada a gravar"
                ),
            )
        else:
            res = aplicar_classificacao(db, doc, tipo)

        rel.resultados.append(res)

    return rel


def revincular_checklist(db: Session, doc: Document) -> Optional[str]:
    """Re-dispara o vínculo doc↔item agora que o documento tem tipo.

    O `auto_link_document` original só roda no upload, com o tipo daquele
    instante — se ele era NULL, o vínculo nunca acontecia e nada o reparava
    depois. Aqui fechamos o ciclo: classificou, gravou, vinculou.

    Grava o vínculo **dos dois lados** (`Document.checklist_item_id` além do JSON
    do checklist) — a auditoria mediu `checklist_item_id` NULL em 100% dos
    documentos do processo 15, o que deixava qualquer consumidor que parta do
    documento cego ao requisito atendido (dívida #71).
    """
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415
    from app.services.checklist_engine import auto_link_document  # noqa: PLC0415

    if doc.process_id is None or not doc.document_type:
        return None

    checklist = (
        db.query(ProcessChecklist)
        .filter(ProcessChecklist.process_id == doc.process_id)
        .first()
    )
    if checklist is None:
        return None

    item_id = auto_link_document(db, checklist, doc.id, doc.document_type)
    if item_id and not doc.checklist_item_id:
        doc.checklist_item_id = item_id
    db.flush()
    return item_id
