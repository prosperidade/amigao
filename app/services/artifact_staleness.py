"""REV-001 — invalidação transitiva por AVISO, nunca por regeneração.

Frente H (ADR-068). Precedente: ADR-039 item 6 (`rota_contexto.
fundamento_mudou_desde_a_rota`) — "sinaliza, nunca regenera sozinha". A Isis já
reclamou do oposto duas vezes: "atualizar da IA apagou toda a rota" (validação
30/07) e o diagnóstico re-rodado em 09/2026 que não enxergou um documento
subido na E5 (validação de 02/08, medida em `AUDITORIA_INDEPENDENTE_FASE1_
2026-09.md`). Regenerar sozinho destruiria classificação, ordem e decisões
humanas por causa de um evento que o consultor talvez nem tenha visto — o
mesmo raciocínio do ADR-039 se generaliza aqui para diagnóstico e proposta.

Desenho medido antes de escrever (design decision #3 da Frente H): a proposta
original pedia um "snapshot de dependências" gravado em cada artefato (lista
de `document_id`/decisão considerados na geração). Descartado depois de medir
que **os carimbos que já existem bastam**: todo artefato versionado desta
frente (`RegulatoryDiagnosis`, `Rota`, `Proposal`) já tem `created_at` e um
carimbo de validação humana (`validated_at`/`accepted_at`). Comparar
`Document.created_at`/`extracted_at` e `ExtractedFieldStaging.created_at`/
`updated_at` do MESMO processo contra esse carimbo produz o aviso "documento
novo" / "nova evidência" / "decisão alterada" sem tabela nova, sem coluna
nova, sem lista de IDs para manter
sincronizada — a mesma filosofia de projeção pura do STATE-001 (`process_
indicators.py`) e do DOC-001 (`document_lifecycle.py`).

Revisão pós-review (mesma rodada): a primeira versão comparava só
`created_at`/`decided_at` e tinha três falsos negativos medidos — documento
que chega antes do corte mas só fica LEGÍVEL depois (`extracted_at` do OCR/
transcrição, que roda depois do upload); "reabrir" uma decisão zera
`decided_at` e apaga o próprio sinal de que algo mudou; e a consolidação
carimba `consolidated_at` sem nunca tocar `decided_at`. As três são cobertas
agora por `extracted_at` (documento) e `updated_at` (staging — toca em
qualquer UPDATE da linha, decisão nova, mudada, reaberta ou gravada).

Fronteira declarada: o corte é POR PROCESSO, não por quais documentos/decisões
especificamente alimentaram aquela geração — um processo com duas frentes de
trabalho independentes pode gerar aviso "de mais" (falso positivo
informativo). Preferimos o alarme ao silêncio (mesmo princípio do "radar não
cancela"); refinar o escopo por proveniência fina é follow-on nomeado no ADR.
Falso NEGATIVO residual conhecido: dois gravadores concorrentes (worker de
OCR + request da API) tocando `audit_log`/staging ao mesmo tempo não é
garantia deste módulo — é leitura de timestamp, não lock; concorrência real
seria coberta por outro mecanismo, não por este aviso.

Este módulo só LÊ. Não muda status, não enfileira nada, não decide nada — a
mesma garantia que `fundamento_mudou_desde_a_rota` já dava.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session


@dataclass
class AvisoDesatualizado:
    tipo: str  # "documento_novo" | "decisao_alterada"
    motivo: str
    desde: datetime

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "motivo": self.motivo, "desde": self.desde}


def _documento_novo_apos(
    db: Session, *, tenant_id: int, process_id: int, cutoff: datetime
) -> Optional[AvisoDesatualizado]:
    """Documento novo OU leitura tardia de documento existente.

    Achado do code review desta frente: olhar só `created_at` deixa passar a
    "leitura tardia" — upload antes do corte, OCR/transcrição terminando
    DEPOIS (`extracted_at`, gravado em `ocr_tasks.py`/`audio_tasks.py`/
    `extrator.py` na conclusão da leitura, não no upload). É exatamente o
    incidente que motivou esta frente: documento já estava no processo, o
    diagnóstico foi gerado antes de ele ficar legível.
    """
    from sqlalchemy import or_  # noqa: PLC0415

    from app.models.document import Document  # noqa: PLC0415

    candidatos_docs = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.process_id == process_id,
            Document.deleted_at.is_(None),
            or_(
                Document.created_at > cutoff,
                Document.extracted_at > cutoff,
            ),
        )
        .all()
    )
    if not candidatos_docs:
        return None
    # Por documento, o marco relevante é o MAIS ANTIGO dos dois que passou do
    # corte (o primeiro evento que já invalidava); entre documentos, o
    # primeiro aviso é o de marco mais antigo (mesma regra do resto do módulo).
    candidatos = []
    for d in candidatos_docs:
        marcos = [m for m in (d.created_at, d.extracted_at) if m is not None and m > cutoff]
        if marcos:
            candidatos.append((min(marcos), d))
    if not candidatos:
        return None
    desde, d = min(candidatos, key=lambda par: par[0])
    nome = d.original_file_name or d.filename or f"documento #{d.id}"
    lido_depois = d.extracted_at is not None and d.extracted_at > cutoff and (
        d.created_at is None or d.created_at <= cutoff
    )
    motivo = (
        f'documento "{nome}" só ficou legível (leitura concluída) depois desta versão'
        if lido_depois
        else f'documento "{nome}" entrou no processo depois desta versão'
    )
    return AvisoDesatualizado(tipo="documento_novo", motivo=motivo, desde=desde)


def _decisao_alterada_apos(
    db: Session, *, tenant_id: int, process_id: int, cutoff: datetime
) -> Optional[AvisoDesatualizado]:
    """Linha nova OU decisão alterada depois do corte.

    Frente J (item 1, reauditoria Codex 11/09): a versão da Frente H olhava
    só ``updated_at`` e deixava passar o caminho literal do #23 — reextração
    com texto CACHEADO. O documento já existia, ``Document.extracted_at`` não
    muda (o OCR não roda de novo), mas novas linhas de staging NASCEM depois
    do artefato, com ``updated_at IS NULL`` (linha nunca atualizada). Só
    ``created_at`` enxerga isso. ``updated_at`` continua cobrindo decisão,
    reabertura e consolidação posteriores.

    O marco é o MAIS ANTIGO entre todas as linhas candidatas (mesma regra de
    `_documento_novo_apos`) — calculado em Python, não por ``ORDER BY``: uma
    linha antiga com ``updated_at`` recente ordenaria antes de uma linha nova
    com ``created_at`` mais cedo, e o "desde" apontaria o evento errado.
    """
    from sqlalchemy import or_  # noqa: PLC0415

    from app.models.extracted_field_staging import ExtractedFieldStaging  # noqa: PLC0415

    candidatas = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            or_(
                ExtractedFieldStaging.created_at > cutoff,
                ExtractedFieldStaging.updated_at > cutoff,
            ),
        )
        .all()
    )
    if not candidatas:
        return None
    marcados = []
    for r in candidatas:
        marcos = [m for m in (r.created_at, r.updated_at) if m is not None and m > cutoff]
        if marcos:
            marcados.append((min(marcos), r))
    if not marcados:
        return None
    desde, row = min(marcados, key=lambda par: par[0])
    campo = row.target_field or row.field_name or "campo"
    nova = row.created_at is not None and row.created_at > cutoff
    return AvisoDesatualizado(
        tipo="decisao_alterada",
        motivo=(
            f'nova evidência da Conferência sobre "{campo}" entrou depois desta versão'
            if nova
            else f'uma decisão da Conferência sobre "{campo}" mudou depois desta versão'
        ),
        desde=desde,
    )


def checar_desatualizacao(
    db: Session, *, tenant_id: int, process_id: int, cutoff: Optional[datetime]
) -> Optional[AvisoDesatualizado]:
    """O aviso mais antigo (documento novo OU decisão alterada) depois de
    ``cutoff`` — o momento em que o artefato foi gerado/validado. ``None``
    quando não há nada mais novo (nada a avisar) ou quando ``cutoff`` é
    ``None`` (artefato sem data — nunca deveria acontecer, mas não é este
    módulo que vai inventar um carimbo)."""
    if cutoff is None:
        return None
    candidatos = [
        a
        for a in (
            _documento_novo_apos(db, tenant_id=tenant_id, process_id=process_id, cutoff=cutoff),
            _decisao_alterada_apos(db, tenant_id=tenant_id, process_id=process_id, cutoff=cutoff),
        )
        if a is not None
    ]
    if not candidatos:
        return None
    candidatos.sort(key=lambda a: a.desde)
    return candidatos[0]


def desatualizacao_diagnostico(db: Session, diagnosis) -> Optional[AvisoDesatualizado]:
    """``cutoff`` é a validação humana quando existe (o caso literal do
    critério de aceite: "após diagnóstico VALIDADO"); antes disso, a própria
    geração — não faz sentido avisar de algo mais novo que um rascunho."""
    cutoff = diagnosis.validated_at or diagnosis.created_at
    return checar_desatualizacao(
        db, tenant_id=diagnosis.tenant_id, process_id=diagnosis.process_id, cutoff=cutoff
    )


def desatualizacao_rota(db: Session, rota) -> Optional[AvisoDesatualizado]:
    """Complementar a `fundamento_mudou_desde_a_rota` (ADR-039), que olha
    proveniência achado→passo. Esta função olha documento/decisão — os dois
    avisos podem coexistir e respondem perguntas diferentes."""
    cutoff = rota.validated_at or rota.created_at
    return checar_desatualizacao(
        db, tenant_id=rota.tenant_id, process_id=rota.process_id, cutoff=cutoff
    )


def desatualizacao_proposta(db: Session, proposal) -> Optional[AvisoDesatualizado]:
    if proposal.process_id is None:
        return None
    cutoff = proposal.accepted_at or proposal.created_at
    return checar_desatualizacao(
        db, tenant_id=proposal.tenant_id, process_id=proposal.process_id, cutoff=cutoff
    )
