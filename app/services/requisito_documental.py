"""Fonte ÚNICA de verdade sobre requisitos documentais (Ficha 08).

Antes deste módulo, "o requisito documental está satisfeito?" era uma expressão
booleana escrita inline em 8 lugares — cada um com fonte da verdade própria. No
processo 15 (caso real) três deles discordavam sobre a MESMA matrícula, no mesmo
instante: o checklist dizia "recebido", o dossiê dizia "ausente", e a verdade era
"recebido, em processamento". Ver
``docs/auditoria/AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md``.

Este módulo é o único lugar que responde essa pergunta. Regras de domínio vêm da
**Ficha 08** (``docs/fichas/FICHA_08_BASE_DADOS_CONFERENCIA.md``):

* **§2** — a lista canônica dos **6** documentos obrigatórios. A Licença Ambiental
  (candidata a 7º) está EM ABERTO na Ficha §6.4 e **não** entra aqui.
* **§7.1** — presente ≠ completo: sub-campo essencial ausente (ex.: ITR sem a
  parte DIAT) ⇒ ``SATISFEITO_PARCIAL`` com ``gaps`` nos campos dependentes.
* **§7.2** — satisfação por equivalência: georreferenciamento certificado
  EMBUTIDO na Matrícula satisfaz o requisito Planta/Memorial SIGEF.
* **§7.3** — documento vencido gera ``alertas``, **nunca** rebaixa o estado nem
  trava (radar-não-cancela).

Princípio P12 aplicado a requisitos: o consultor **nunca** vê "ausente" com o
documento visível na tela. Se o arquivo chegou, o pior estado possível é
``RECEBIDO_EM_PROCESSAMENTO``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging

# ---------------------------------------------------------------------------
# Estados
# ---------------------------------------------------------------------------

class RequisitoStatus(str, enum.Enum):
    """Estados de um requisito documental.

    A ordem importa: ``_ORDEM`` usa a declaração para agregar o estado de
    vários documentos que servem ao mesmo requisito (o melhor documento define o
    estado do requisito — um ITR completo não é rebaixado por outro incompleto).
    """

    AUSENTE = "ausente"
    RECEBIDO_EM_PROCESSAMENTO = "recebido_em_processamento"
    SATISFEITO_PARCIAL = "satisfeito_parcial"
    SATISFEITO = "satisfeito"


_ORDEM = {
    RequisitoStatus.AUSENTE: 0,
    RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO: 1,
    RequisitoStatus.SATISFEITO_PARCIAL: 2,
    RequisitoStatus.SATISFEITO: 3,
}


# ---------------------------------------------------------------------------
# Ficha 08 §2 — os 6 obrigatórios
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Requisito:
    key: str
    label: str
    papel: str                      # papel na base, conforme a Ficha §2
    doc_types: frozenset[str]       # vocabulário de `Document.document_type`
    subcampos_essenciais: frozenset[str] = frozenset()
    equivalentes: frozenset[str] = frozenset()   # §7.2 — outros requisitos que o satisfazem


# Vocabulário: mapeia os MUITOS nomes que um documento recebe (intake manual,
# classificação por conteúdo, portal do cliente) para UM requisito. Sem este mapa,
# `cpf_cnpj` nunca casa com o requisito `doc_pessoal` — divergência D3 da auditoria,
# que deixava a CNH do proprietário anexada com o requisito pendente.
REQUISITOS_BASE: tuple[Requisito, ...] = (
    Requisito(
        key="matricula",
        label="Matrícula",
        papel="Documento-mãe jurídico — domínio, cadeia dominial, ônus, averbações.",
        doc_types=frozenset({
            "matricula", "certidao_matricula", "certidao_inteiro_teor",
            "inteiro_teor", "matricula_atualizada",
        }),
        # Sem número não há como identificar o registro (Ficha §3.2).
        subcampos_essenciais=frozenset({"numero_matricula"}),
    ),
    Requisito(
        key="car",
        label="CAR",
        papel="Documento-mãe ambiental — RL, APP, área vetorizada, situação do cadastro.",
        # `rat` NÃO entra aqui, e isso é decisão de domínio, não omissão
        # (Isis, 26/07): o RAT é o **parecer do órgão sobre** o CAR, com foto de
        # uma análise passada. O documento oficial do cadastro é o
        # recibo/demonstrativo. RAT é fonte de CONTEXTO e HISTÓRICO — nunca
        # satisfaz o requisito do CAR, por mais completo que pareça. Ver
        # `tests/services/test_rat_nao_satisfaz_car.py` e Ficha 08 §2.
        doc_types=frozenset({"car", "recibo_car", "cadastro_ambiental_rural"}),
        subcampos_essenciais=frozenset({"numero_car"}),
    ),
    Requisito(
        key="ccir",
        label="CCIR",
        papel="Documento-mãe fiscal/cadastral rural — código INCRA, módulos fiscais.",
        doc_types=frozenset({"ccir"}),
        subcampos_essenciais=frozenset({"codigo_sncr_incra"}),
    ),
    Requisito(
        key="itr",
        label="ITR (DIAC + DIAT)",
        papel="Declaração tributária — código INCRA, VTN, distribuição de área.",
        doc_types=frozenset({"itr", "diac", "diat", "ditr"}),
        # Ficha §7.1, caso real nomeado: um ITR só com o DIAC (identificação) não
        # traz VTN/distribuição de área. `vtn` é o marcador do DIAT no extrator.
        subcampos_essenciais=frozenset({"vtn"}),
    ),
    Requisito(
        key="identidade",
        label="Documento de identidade do titular (RG/CNH)",
        papel="Fonte de verdade do titular único do caso (Ficha §3.1).",
        doc_types=frozenset({
            "rg_cpf", "cpf_cnpj", "rg", "cnh", "doc_pessoal", "identidade",
        }),
        subcampos_essenciais=frozenset({"cpf"}),
    ),
    Requisito(
        key="planta_memorial",
        label="Planta / Memorial descritivo (SIGEF)",
        papel="Documento-mãe técnico de perímetro — coordenadas, confrontações.",
        doc_types=frozenset({
            "sigef", "memorial_descritivo", "planta_topografica", "planta",
        }),
        # Ficha §7.2 — georref certificado embutido na Matrícula satisfaz este
        # requisito. "Nem todo imóvel possui" um SIGEF separado (§2); travar o card
        # exigindo um arquivo que oficialmente não existe seria falso.
        equivalentes=frozenset({"matricula"}),
    ),
)

REQUISITOS_POR_KEY: dict[str, Requisito] = {r.key: r for r in REQUISITOS_BASE}

# Campos do staging que provam georreferenciamento certificado dentro da Matrícula
# (Ficha §7.2). São os mesmos que o extrator emite para `matricula` e `sigef`.
_GEORREF_EMBUTIDO_FIELDS = frozenset({"codigo_certificacao", "numero_geo"})


def requisito_de_doc_type(doc_type: Optional[str]) -> Optional[str]:
    """Mapa doc_type → requisito. ``None`` quando o tipo não serve a nenhum dos 6.

    Ponto único de tradução do vocabulário. Antes cada consumidor comparava
    strings por igualdade exata (``item.doc_type == doc_type``), o que fazia
    `certidao_inteiro_teor` nunca casar com o requisito `matricula`.
    """
    if not doc_type:
        return None
    dt = doc_type.strip().lower()
    for req in REQUISITOS_BASE:
        if dt in req.doc_types:
            return req.key
    return None


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class RequisitoResultado:
    requisito: str
    label: str
    status: RequisitoStatus
    document_ids: list[int] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)        # §7.1 campos dependentes ausentes
    alertas: list[str] = field(default_factory=list)     # §7.3 vencimento — nunca trava
    satisfeito_por: Optional[str] = None                 # §7.2 requisito equivalente que supriu
    detalhe: str = ""                                    # frase pronta, honesta, para a tela

    @property
    def tem_documento(self) -> bool:
        """True quando existe arquivo na base servindo a este requisito.

        Enquanto for True, `status` nunca é AUSENTE — é a garantia do P12.
        """
        return bool(self.document_ids)

    @property
    def pendente(self) -> bool:
        """Conta como pendência de coleta? Só quando não há documento nenhum.

        `SATISFEITO_PARCIAL` NÃO é pendência de coleta — o documento chegou; o que
        falta é sub-campo, que vira `gaps` nos campos dependentes (Ficha §7.1).
        """
        return self.status is RequisitoStatus.AUSENTE


# ---------------------------------------------------------------------------
# Núcleo
# ---------------------------------------------------------------------------

def _status_de_documento(
    doc: Document,
    req: Requisito,
    campos_do_doc: set[str],
) -> tuple[RequisitoStatus, list[str]]:
    """Estado que UM documento confere ao requisito, + gaps de sub-campo."""
    # OCR ainda rodando (ou falhou e vai ser reprocessado): o arquivo está lá, mas
    # ainda não há o que afirmar sobre o conteúdo. Honesto: "em processamento".
    if doc.ocr_status in (OcrStatus.pending, OcrStatus.processing):
        return RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO, []

    # Sem nenhum campo extraído ainda — o extrator não passou por aqui.
    if not campos_do_doc:
        return RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO, []

    faltantes = sorted(req.subcampos_essenciais - campos_do_doc)
    if faltantes:
        return RequisitoStatus.SATISFEITO_PARCIAL, faltantes

    return RequisitoStatus.SATISFEITO, []


def _vencimento_alerta(doc: Document, agora: datetime) -> Optional[str]:
    """Ficha §7.3 — vencido gera alerta, nunca trava.

    Só avalia quando `expires_at` está preenchido: "nem todo CCIR tem data de
    vencimento; não assumir prazo fixo genérico".
    """
    exp = doc.expires_at
    if exp is None:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp < agora:
        return f"{doc.filename}: vencido em {exp.date().isoformat()} — solicitar reenvio."
    return None


def _georref_embutido(campos_por_doc: dict[int, set[str]], docs_matricula: list[Document]) -> Optional[int]:
    """Ficha §7.2 — devolve o id da Matrícula que carrega georref certificado."""
    for doc in docs_matricula:
        if campos_por_doc.get(doc.id, set()) & _GEORREF_EMBUTIDO_FIELDS:
            return doc.id
    return None


def _doc_type_por_item_do_checklist(
    db: Session, process_id: int, tenant_id: int
) -> dict[Optional[str], Optional[str]]:
    """Mapa ``checklist_item_id`` → ``doc_type`` do item, para o processo.

    É a intenção declarada pelo consultor no momento do upload ("este arquivo é
    o CAR"), disponível antes de o OCR terminar. Devolve ``{}`` quando o processo
    não tem checklist — o caminho por conteúdo segue valendo sozinho.
    """
    from app.models.checklist_template import ProcessChecklist  # noqa: PLC0415

    checklists = (
        db.query(ProcessChecklist)
        .filter(
            ProcessChecklist.process_id == process_id,
            ProcessChecklist.tenant_id == tenant_id,
        )
        .all()
    )
    mapa: dict[Optional[str], Optional[str]] = {}
    for cl in checklists:
        for item in (cl.items or []):
            if isinstance(item, dict) and item.get("id"):
                mapa[str(item["id"])] = item.get("doc_type")
    return mapa


def documentos_sem_requisito(
    db: Session, process_id: int, tenant_id: int
) -> list[Document]:
    """Documentos do caso que não servem a nenhum dos 6 — nem por tipo, nem por
    vínculo de checklist.

    Existe para que a tela possa DIZER que eles estão lá. Documento que o sistema
    não soube encaixar não pode simplesmente desaparecer da contagem: era assim
    que o painel dava a impressão de base vazia com arquivos anexados (P12).
    """
    intencao = _doc_type_por_item_do_checklist(db, process_id, tenant_id)
    documentos = (
        db.query(Document)
        .filter(
            Document.process_id == process_id,
            Document.tenant_id == tenant_id,
            Document.deleted_at.is_(None),
        )
        .all()
    )
    orfaos: list[Document] = []
    for doc in documentos:
        if requisito_de_doc_type(doc.document_type):
            continue
        if requisito_de_doc_type(intencao.get(doc.checklist_item_id)):
            continue
        orfaos.append(doc)
    return orfaos


def avaliar_requisitos(
    db: Session,
    process_id: int,
    tenant_id: int,
    *,
    agora: Optional[datetime] = None,
) -> dict[str, RequisitoResultado]:
    """Avalia os 6 requisitos da Ficha 08 §2 para um processo. Fonte única.

    Uma única passada no banco (documentos + staging) serve todos os consumidores.
    """
    agora = agora or datetime.now(UTC)

    documentos = (
        db.query(Document)
        .filter(
            Document.process_id == process_id,
            Document.tenant_id == tenant_id,
            Document.deleted_at.is_(None),
        )
        .all()
    )

    # Campos efetivamente extraídos, por documento. É o sinal de "o sistema já leu
    # este arquivo" — independente de a consolidação ter rodado. Requisito
    # DOCUMENTAL trata de presença/completude do documento; consolidação do dado é
    # outro eixo (Ficha 05), e confundir os dois foi exatamente o bug do caso 15.
    campos_por_doc: dict[int, set[str]] = {}
    if documentos:
        linhas = (
            db.query(ExtractedFieldStaging.document_id, ExtractedFieldStaging.field_name)
            .filter(
                ExtractedFieldStaging.process_id == process_id,
                ExtractedFieldStaging.tenant_id == tenant_id,
            )
            .all()
        )
        for doc_id, field_name in linhas:
            if doc_id is not None:
                campos_por_doc.setdefault(doc_id, set()).add(field_name)

    # Agrupa documentos por requisito, traduzindo o vocabulário.
    #
    # Validação 02/08: a consultora subiu o CAR na E3, re-rodou o agente e a
    # Conferência seguiu dizendo que faltava. A causa está nesta linha, não no
    # upload: o agrupamento é feito por `document_type`, e `document_type` só é
    # preenchido DEPOIS que o OCR roda e a classificação por conteúdo acerta.
    # Enquanto isso o documento não caía em requisito nenhum — era descartado em
    # silêncio — e o requisito ficava AUSENTE com o arquivo visível na tela ao
    # lado. Isto quebrava a promessa que este módulo faz no próprio docstring
    # (P12: "o consultor nunca vê 'ausente' com o documento visível na tela").
    #
    # O remédio é usar a INTENÇÃO DECLARADA como segunda via: quando o consultor
    # sobe o arquivo contra um item do checklist, o vínculo (`checklist_item_id`)
    # já diz a que requisito ele serve — sem depender do OCR ter terminado. Isso
    # não inventa classificação: só honra o que a pessoa afirmou ao anexar.
    intencao_por_item = _doc_type_por_item_do_checklist(db, process_id, tenant_id)

    docs_por_requisito: dict[str, list[Document]] = {r.key: [] for r in REQUISITOS_BASE}
    for doc in documentos:
        key = requisito_de_doc_type(doc.document_type)
        if key is None:
            key = requisito_de_doc_type(intencao_por_item.get(doc.checklist_item_id))
        if key:
            docs_por_requisito[key].append(doc)

    resultados: dict[str, RequisitoResultado] = {}

    for req in REQUISITOS_BASE:
        docs = docs_por_requisito[req.key]
        res = RequisitoResultado(
            requisito=req.key,
            label=req.label,
            status=RequisitoStatus.AUSENTE,
        )

        for doc in docs:
            st, faltantes = _status_de_documento(doc, req, campos_por_doc.get(doc.id, set()))
            res.document_ids.append(doc.id)
            # O MELHOR documento define o estado — um ITR completo não é rebaixado
            # por outro incompleto anexado junto.
            if _ORDEM[st] > _ORDEM[res.status]:
                res.status = st
                res.gaps = faltantes
            alerta = _vencimento_alerta(doc, agora)
            if alerta:
                res.alertas.append(alerta)

        resultados[req.key] = res

    # §7.2 — equivalência, aplicada depois que todos os requisitos diretos já foram
    # avaliados (a Matrícula precisa estar resolvida para poder suprir a Planta).
    for req in REQUISITOS_BASE:
        res = resultados[req.key]
        if res.tem_documento or not req.equivalentes:
            continue
        for eq_key in sorted(req.equivalentes):
            if eq_key != "matricula":
                continue
            doc_id = _georref_embutido(campos_por_doc, docs_por_requisito["matricula"])
            if doc_id is not None:
                res.status = RequisitoStatus.SATISFEITO
                res.satisfeito_por = "matricula"
                res.document_ids = [doc_id]
                break

    for res in resultados.values():
        res.detalhe = descrever(res)

    return resultados


# ---------------------------------------------------------------------------
# Semântica honesta na tela (P12)
# ---------------------------------------------------------------------------

def descrever(res: RequisitoResultado) -> str:
    """Frase pronta para o consultor. Nunca diz "ausente" com documento na base."""
    if res.status is RequisitoStatus.AUSENTE:
        return f"{res.label}: não recebido."

    if res.status is RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO:
        return (
            f"{res.label}: recebido, em processamento — o sistema ainda está lendo "
            "o documento."
        )

    if res.status is RequisitoStatus.SATISFEITO_PARCIAL:
        campos = ", ".join(res.gaps)
        return (
            f"{res.label}: recebido, mas incompleto — falta {campos}. "
            "Confirme se o documento enviado atende ao requisito."
        )

    if res.satisfeito_por == "matricula":
        return (
            f"{res.label}: satisfeito pelo georreferenciamento certificado embutido "
            "na Matrícula (Ficha 08 §7.2) — não exige arquivo SIGEF separado."
        )

    return f"{res.label}: recebido."


def contar_pendentes_checklist(
    db: Session,
    process_id: int,
    tenant_id: int,
    items: Optional[list[dict]],
) -> int:
    """Itens obrigatórios do ProcessChecklist que de fato faltam coletar.

    Ponto ÚNICO desta contagem — antes o mesmo laço de 4 linhas estava copiado em
    ``processes.py`` (kanban e detalhe), divergência D6 da auditoria.

    O checklist por demanda tem itens que não estão nos 6 da Ficha 08 (fotos da
    área, laudo anterior, auto de infração): esses continuam contando pelo estado
    gravado no JSON. Para os que ESTÃO nos 6, a fonte única tem a palavra final —
    um item marcado "pending" cujo documento já está na base não é pendência de
    coleta. Era assim que `doc_proprietario` ficava pendente com a CNH anexada.
    """
    if not items:
        return 0

    resultados: Optional[dict[str, RequisitoResultado]] = None
    pendentes = 0

    for item in items:
        if not item.get("required") or item.get("status") != "pending":
            continue
        key = requisito_de_doc_type(item.get("doc_type"))
        if key is None:
            pendentes += 1          # fora dos 6 — só o checklist sabe
            continue
        if resultados is None:      # lazy: só toca o banco se algum item for dos 6
            resultados = avaliar_requisitos(db, process_id, tenant_id)
        if not resultados[key].tem_documento:
            pendentes += 1

    return pendentes


def contar_pendentes(resultados: dict[str, RequisitoResultado]) -> int:
    """Quantos dos 6 realmente faltam coletar.

    Só conta `AUSENTE`. Documento recebido — mesmo em processamento ou incompleto —
    não é pendência de COLETA; é gap de campo (§7.1) ou espera de leitura.
    """
    return sum(1 for r in resultados.values() if r.pendente)
