"""Reconciliação por decisões — Frente G (REC-001 + CONF-001, ADR-067).

A Conferência agrupava por CAMPO: 42 linhas na ELODI para 8 fatos do domínio
(spec Isis §3.3, §5). O sintoma medido (`docs/auditoria/CONFIRMACAO_ENTRADA_
2026-09-09.md`, "Decisão agrupada" — INSUFICIENTE): a matrícula 3.181 aparecia
em DUAS linhas de staging — uma do CAR (`matricula_listada`, hint 3181) e uma
da certidão (`numero_matricula`, hint 3181) — mesmo fato, dois campos, duas
decisões cobradas da consultora por um fato só.

Este módulo NÃO grava nada e não chama LLM — só agrupa `ExtractedFieldStaging`
já existente por CHAVE NATURAL do fato que ele descreve: ``(entidade,
identificador, aspecto)``. Ex.: ``("matricula", "3181", "composicao")``,
``("imovel", "23", "reserva_legal")``. Cada grupo vira uma :class:`Decisao`:
evidências por fonte, concordância/divergência calculada por REGRA (a régua de
4 níveis da skill do auditor, `grade_area_divergence` — nunca LLM), fonte
autoritativa pela ADR-062 (matrícula manda no registral, CAR no ambiental,
CCIR/ITR no cadastral) e estado (pendente/decidida/gravada, reaproveitando
`ExtractedFieldStaging.status`/`consolidated_at` — nenhuma coluna nova).

A decisão em si não é uma entidade persistida (ADR-067 mediu `ProcessDecision`
e `ProcessIssueDecision` antes de escrever este módulo — nenhuma das duas serve:
a primeira é log de governança por macroetapa, sem chave natural; a segunda é
decisão do consultor sobre ACHADO regulatório, não sobre dado cadastral). A
chave natural é recomputável a qualquer momento a partir do staging — não há
estado a sincronizar, e uma decisão "gravada" continua sendo só a leitura atual
de `consolidated_at` nas linhas do grupo.

Linha que não casa com nenhuma regra de chave vai para ``sem_agrupamento`` —
visível, nunca escondida (Ficha 07 princípio "nada some sem dizer").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.services.inconsistency_matrix import _clean_matricula_hint, norm_compare, parse_area_ha
from app.services.observacao_registral import TIPO_RESERVA_LEGAL, TIPOS_GRAVAME
from app.services.property_audit import GRADE_INFORMATIVO, grade_area_divergence

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

# (entidade, identificador, aspecto) — ex.: ("matricula", "3181", "composicao").
ChaveNatural = tuple[str, str, str]

_DECIDIDOS = {ExtractedFieldStatus.aceito, ExtractedFieldStatus.rejeitado}

# Aspectos cujo valor é NUMÉRICO (área/ha) — só estes passam pela régua de 4
# níveis. Os demais (identificador, nome, status) comparam por texto
# normalizado: aplicar `parse_area_ha` num número de matrícula ("3.181") o
# leria como área e produziria uma divergência percentual sem sentido.
_ASPECTOS_NUMERICOS = frozenset({"area", "area_total", "reserva_legal"})

# ADR-062: cada dado tem a fonte autoritativa da sua NATUREZA — registral
# (matrícula), ambiental (CAR), cadastral (CCIR/INCRA). `area_total` não tem
# fonte única (é a SOMA das matrículas, calculada — ver `_injetar_area_total`).
# `identificacao` (representante) não compete: é a própria CNH da pessoa.
_FONTE_AUTORITATIVA_POR_ASPECTO: dict[str, Optional[str]] = {
    "composicao": "matricula",
    "area": "matricula",
    "reserva_legal": "matricula",
    "gravames": "matricula",
    "titularidade": "matricula",
    "car": "car",
    "identificacao": None,
    "area_total": None,
}

_LABEL_ASPECTO: dict[str, str] = {
    "composicao": "Matrícula {id} integra o imóvel",
    "area": "Área — matrícula {id}",
    "reserva_legal": "Reserva Legal",
    "gravames": "Gravames vigentes — matrícula {id}",
    "titularidade": "Titularidade",
    "car": "CAR (número/status)",
    "identificacao": "Representante",
    "area_total": "Área total do imóvel",
}


@dataclass
class Evidencia:
    """Uma observação (linha de staging) que sustenta ou contesta a decisão."""

    staging_id: Optional[int]  # None só na evidência SINTÉTICA (soma calculada)
    documento_id: Optional[int]
    documento_tipo: Optional[str]
    campo: Optional[str]
    valor_bruto: Any
    valor_normalizado: Any
    unidade: Optional[str]
    vigencia: Optional[str]
    status: str
    fonte_autoritativa: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "staging_id": self.staging_id,
            "documento_id": self.documento_id,
            "documento_tipo": self.documento_tipo,
            "campo": self.campo,
            "valor_bruto": self.valor_bruto,
            "valor_normalizado": self.valor_normalizado,
            "unidade": self.unidade,
            "vigencia": self.vigencia,
            "status": self.status,
            "fonte_autoritativa": self.fonte_autoritativa,
        }


@dataclass
class Decisao:
    """A unidade da Conferência (CONF-001): um fato, não um campo."""

    chave: ChaveNatural
    label: str
    evidencias: list[Evidencia]
    concordancia: str  # concordam | divergem | fonte_unica
    nivel_divergencia: Optional[str] = None  # informativo|atencao|alto|critico
    delta: Optional[float] = None
    percentual: Optional[float] = None
    valor_proposto: Any = None
    fonte_autoritativa_doc: Optional[str] = None
    estado: str = "pendente"  # pendente | decidida | gravada
    staging_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        entidade, identificador, aspecto = self.chave
        return {
            "chave": {"entidade": entidade, "identificador": identificador, "aspecto": aspecto},
            "chave_str": f"{entidade}:{identificador}:{aspecto}",
            "label": self.label,
            "evidencias": [e.to_dict() for e in self.evidencias],
            "concordancia": self.concordancia,
            "nivel_divergencia": self.nivel_divergencia,
            "delta": self.delta,
            "percentual": self.percentual,
            "valor_proposto": self.valor_proposto,
            "fonte_autoritativa_doc": self.fonte_autoritativa_doc,
            "estado": self.estado,
            "staging_ids": self.staging_ids,
        }


@dataclass
class ReconciliationResult:
    decisoes: list[Decisao]
    # Linha sem regra de chave — nunca escondida (visível na Conferência num
    # bloco à parte, com o motivo de não ter entrado em nenhuma decisão).
    sem_agrupamento: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisoes": [d.to_dict() for d in self.decisoes],
            "sem_agrupamento": self.sem_agrupamento,
            "total_staging": sum(len(d.staging_ids) for d in self.decisoes)
            + len(self.sem_agrupamento),
        }


# ---------------------------------------------------------------------------
# Chave natural — regras por tipo de fato (escopo item 1 da Frente G)
# ---------------------------------------------------------------------------


def _chave_de(row: ExtractedFieldStaging) -> tuple[Optional[ChaveNatural], Optional[str]]:
    """Chave natural do fato que esta linha descreve, ou (None, motivo).

    Ordem importa: uma linha casa com a PRIMEIRA regra aplicável. As regras são
    as mesmas que a consolidação já usa para saber "de que fato isto fala"
    (`target_entity`/`target_field`/`tipo_observacao`/`matricula_hint`) — este
    módulo só lê, nunca decide destino de escrita (isso continua em
    `staging_consolidation`).
    """
    entity = (row.target_entity or "").lower()
    field_name = row.field_name or ""
    target_field = row.target_field or ""
    pid = str(row.process_id) if row.process_id is not None else "-"

    # 1) Composição: "esta matrícula integra o imóvel" — a mesma matrícula
    # citada pelo CAR (`matricula_listada`) e pela própria certidão (ou por
    # CCIR/ITR/SIGEF, que também declaram `numero_matricula`) é UM fato só
    # (REC-001 — caso da 3.181: CAR + certidão, não duas linhas).
    if entity == "matricula" and field_name in ("numero_matricula", "matricula_listada"):
        hint = _clean_matricula_hint(row.matricula_hint) or _clean_matricula_hint(_valor_bruto(row))
        if hint:
            return ("matricula", hint, "composicao"), None
        return None, "matrícula sem número identificável (hint ausente)"

    # 2) Reserva Legal — COLUNA da matrícula (ADR-062: fonte única registral),
    # confrontada com o que o CAR declara (`rl_declarada_ha`, dívida #218).
    # Uma decisão só por processo: a RL do imóvel é a soma do que está
    # averbado nas matrículas, não um fato por matrícula.
    if entity == "matricula" and row.tipo_observacao == TIPO_RESERVA_LEGAL:
        return ("imovel", pid, "reserva_legal"), None
    if field_name == "rl_declarada_ha":
        return ("imovel", pid, "reserva_legal"), None

    # 3) Gravames vigentes — lista agregada por matrícula (ADR-066): a
    # consultora decide "o que está gravado hoje nesta matrícula", não ato a
    # ato (`onus_gravames` já é coluna única na base pela mesma razão).
    if entity == "matricula" and row.tipo_observacao in TIPOS_GRAVAME:
        hint = _clean_matricula_hint(row.matricula_hint)
        if hint:
            return ("matricula", hint, "gravames"), None
        return None, "gravame sem matrícula identificável"

    # 4) Área total do imóvel — CAR gráfica × CAR documental × soma das
    # matrículas (a soma é injetada depois, `_injetar_area_total`).
    if entity == "imovel" and field_name in ("area_declarada_ha", "area_documental_ha"):
        return ("imovel", pid, "area_total"), None

    # 5) Área por matrícula × fonte — certidão/SIGEF/CCIR/ITR declarando a
    # área da MESMA matrícula (mesmo sinônimo que `inconsistency_matrix.
    # _AREA_SYNONYMS` já usa para o nível "matricula").
    if entity == "matricula" and _eh_area_de_matricula(row):
        hint = _clean_matricula_hint(row.matricula_hint)
        if hint:
            return ("matricula", hint, "area"), None
        return None, "área sem matrícula identificável (mesmo caso do #12 item B)"

    # 6) Titularidade — quem é o titular (PF ou PJ). `target_field` já vem
    # aliasado para "document" (cliente) tanto no CPF quanto no CNPJ.
    if entity == "cliente" and target_field in ("full_name", "document"):
        return ("cliente", pid, "titularidade"), None

    # 7) Representante da PJ — pessoa distinta do titular (ENT-001); a chave é
    # o DOCUMENTO de origem (cada CNH é uma pessoa, não um campo a mais).
    if entity == "representante" and target_field in ("full_name", "document", "birth_date"):
        rid = str(row.document_id) if row.document_id is not None else pid
        return ("representante", rid, "identificacao"), None

    # 8) CAR — número e status do cadastro (ADR-062: CAR manda no ambiental).
    if entity == "imovel" and field_name in ("numero_car", "status_car"):
        return ("imovel", pid, "car"), None

    return None, "tipo sem chave natural mapeada nesta frente — decide-se campo a campo"


# Mesmos sinônimos que `inconsistency_matrix` usa para reconhecer área de
# NÍVEL matrícula (certidão/sigef/ccir/itr) — reaproveitado, não duplicado.
_AREA_MATRICULA_FIELD_NAMES = frozenset(
    {"area_registrada_ha", "area_ha", "area_total", "area_total_imovel", "area_georreferenciada_ha"}
)


def _eh_area_de_matricula(row: ExtractedFieldStaging) -> bool:
    doc_type = (row.source_doc_type or "").lower()
    field_name = row.field_name or ""
    if doc_type == "car":
        return False  # área do CAR é de IMÓVEL, não de matrícula (regra 4 acima)
    return field_name in _AREA_MATRICULA_FIELD_NAMES


def _valor_bruto(row: ExtractedFieldStaging) -> Any:
    src = row.decided_value if row.decided_value is not None else row.field_value
    if isinstance(src, dict) and "value" in src:
        return src["value"]
    return src


# ---------------------------------------------------------------------------
# Evidência + comparação (concordância/divergência POR REGRA — sem LLM)
# ---------------------------------------------------------------------------


def _evidencia_de(row: ExtractedFieldStaging, aspecto: str) -> Evidencia:
    raw = _valor_bruto(row)
    unidade = row.field_value.get("unidade") if isinstance(row.field_value, dict) else None
    if aspecto in _ASPECTOS_NUMERICOS:
        # Observação tipada (ADR-065): a área vive em `atributos["area"]`, não
        # em `field_value["value"]` — que aqui carrega o dict bruto do ato
        # (`{"area": "492,9252", "referencia": "AV.02"}`, mesmo shape medido
        # em `test_fiacao_entrada.py`). Campo de cabeçalho comum (área do
        # imóvel/CAR) não tem `atributos` — cai no `raw` normal.
        area_atributo = (row.atributos or {}).get("area") if isinstance(row.atributos, dict) else None
        numero = parse_area_ha(area_atributo, unidade) if area_atributo is not None else None
        if numero is None:
            numero = parse_area_ha(raw, unidade)
        valor_normalizado: Any = numero if numero is not None else raw
    else:
        valor_normalizado = raw
    vigencia = (row.atributos or {}).get("vigencia") if isinstance(row.atributos, dict) else None
    campo = row.target_field or row.field_name
    if aspecto == "gravames":
        # A pergunta de gravame não é "qual valor", é "este ato está vigente"
        # — o rótulo é o próprio ato (AV.03, R.15), não a coluna de destino.
        campo = (row.atributos or {}).get("ato") or campo
        valor_normalizado = vigencia or "indeterminado"
    return Evidencia(
        staging_id=row.id,
        documento_id=row.document_id,
        documento_tipo=(row.source_doc_type or None),
        campo=campo,
        valor_bruto=raw,
        valor_normalizado=valor_normalizado,
        unidade=unidade,
        vigencia=vigencia,
        status=row.status.value if row.status else "pendente",
    )


def _comparar(aspecto: str, evidencias: list[Evidencia]) -> tuple[str, Optional[str], Optional[float], Optional[float]]:
    """Concordância/divergência POR REGRA — régua de 4 níveis (skill do
    auditor: ≤1% informativo, 1-5% atenção, 5-10% alto, >10% crítico) para
    aspectos numéricos; texto normalizado para os demais. `composicao` e
    `gravames` não comparam VALOR (a chave já garante que é o mesmo fato ou a
    evidência é uma síntese de atos) — múltiplas fontes corroborando é
    "concordam" por definição.
    """
    if aspecto in ("composicao", "gravames"):
        return ("concordam" if len(evidencias) > 1 else "fonte_unica"), None, None, None

    if aspecto in _ASPECTOS_NUMERICOS:
        vals = [e.valor_normalizado for e in evidencias if isinstance(e.valor_normalizado, (int, float))]
        if len(vals) <= 1:
            return "fonte_unica", None, None, None
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return "concordam", GRADE_INFORMATIVO, 0.0, 0.0
        delta = hi - lo
        pct = Decimal(str(delta)) / Decimal(str(hi))
        nivel = grade_area_divergence(pct)
        concordancia = "concordam" if nivel == GRADE_INFORMATIVO else "divergem"
        return concordancia, nivel, float(delta), float(pct)

    # Texto (titularidade, car, identificacao): estes aspectos podem reunir
    # CAMPOS diferentes na mesma decisão (nome + documento, número + status do
    # CAR) — comparar "ELODI AGROPECUARIA" com "29.091.958/0001-17" como se
    # fossem duas respostas para a mesma pergunta produziria uma divergência
    # sem sentido. Só evidências do MESMO campo competem entre si.
    por_campo: dict[str, list[str]] = {}
    for e in evidencias:
        if e.valor_normalizado in (None, ""):
            continue
        por_campo.setdefault(e.campo or "-", []).append(norm_compare(e.valor_normalizado))
    grupos_com_mais_de_uma_fonte = [v for v in por_campo.values() if len(v) > 1]
    if not grupos_com_mais_de_uma_fonte:
        return "fonte_unica", None, None, None
    concordam = all(len(set(v)) == 1 for v in grupos_com_mais_de_uma_fonte)
    return ("concordam" if concordam else "divergem"), None, None, None


def _estado_de(membros: list[ExtractedFieldStaging]) -> str:
    """pendente | decidida | gravada — reaproveita status/consolidated_at, sem
    coluna nova (mesma lógica de "Aceito" ≠ "Gravado" já validada na tela)."""
    if any(r.consolidated_at is not None for r in membros):
        return "gravada"
    if all(r.status in _DECIDIDOS for r in membros):
        return "decidida"
    return "pendente"


def _label_de(chave: ChaveNatural) -> str:
    _entidade, identificador, aspecto = chave
    template = _LABEL_ASPECTO.get(aspecto, "{id}")
    return template.format(id=identificador)


def _montar_decisao(chave: ChaveNatural, membros: list[ExtractedFieldStaging]) -> Decisao:
    _entidade, _identificador, aspecto = chave
    evidencias = [_evidencia_de(r, aspecto) for r in membros]
    concordancia, nivel, delta, pct = _comparar(aspecto, evidencias)

    fonte_doc = _FONTE_AUTORITATIVA_POR_ASPECTO.get(aspecto)
    if fonte_doc:
        for e in evidencias:
            if (e.documento_tipo or "").lower() == fonte_doc:
                e.fonte_autoritativa = True

    if aspecto == "gravames":
        # Síntese dos atos, não "o valor vencedor" — não faz sentido escolher
        # UM gravame como proposta e descartar os outros.
        proposto: Any = "; ".join(f"{e.campo}: {e.valor_normalizado}" for e in evidencias) or None
    else:
        proposto = next((e.valor_normalizado for e in evidencias if e.fonte_autoritativa), None)
        if proposto is None and evidencias:
            proposto = evidencias[0].valor_normalizado

    return Decisao(
        chave=chave,
        label=_label_de(chave),
        evidencias=evidencias,
        concordancia=concordancia,
        nivel_divergencia=nivel,
        delta=delta,
        percentual=pct,
        valor_proposto=proposto,
        fonte_autoritativa_doc=fonte_doc,
        estado=_estado_de(membros),
        staging_ids=[r.id for r in membros],
    )


def _injetar_area_total(decisoes: list[Decisao]) -> None:
    """Acrescenta a evidência CALCULADA "soma das matrículas" à decisão
    `area_total`, quando existir. Não é um valor de linha nenhuma — é a soma
    das decisões `area` já montadas (fonte autoritativa de cada uma, ou a
    única disponível). Sem fonte única (item 2 do escopo): a soma é proposta,
    nunca "vencedora" de uma disputa entre CAR e matrícula.
    """
    por_aspecto: dict[str, list[Decisao]] = {}
    for d in decisoes:
        por_aspecto.setdefault(d.chave[2], []).append(d)
    totais = por_aspecto.get("area_total")
    areas = por_aspecto.get("area")
    if not totais or not areas:
        return
    soma = 0.0
    contribuiu = False
    for d in areas:
        valor = d.valor_proposto if isinstance(d.valor_proposto, (int, float)) else None
        if valor is None:
            for e in d.evidencias:
                if isinstance(e.valor_normalizado, (int, float)):
                    valor = e.valor_normalizado
                    break
        if valor is not None:
            soma += valor
            contribuiu = True
    if not contribuiu:
        return
    for total in totais:
        total.evidencias.append(
            Evidencia(
                staging_id=None,
                documento_id=None,
                documento_tipo="calculado",
                campo="soma_matriculas",
                valor_bruto=None,
                valor_normalizado=round(soma, 4),
                unidade="ha",
                vigencia=None,
                status="calculado",
            )
        )
        # recalcula concordância/valor proposto agora COM a soma
        concordancia, nivel, delta, pct = _comparar("area_total", total.evidencias)
        total.concordancia, total.nivel_divergencia = concordancia, nivel
        total.delta, total.percentual = delta, pct
        if total.valor_proposto is None:
            total.valor_proposto = round(soma, 4)


# ---------------------------------------------------------------------------
# Builder principal
# ---------------------------------------------------------------------------


def build_decisions(rows: list[ExtractedFieldStaging]) -> ReconciliationResult:
    """Agrupa o staging (qualquer status) em decisões — puro, sem I/O.

    Não filtra por status: a Conferência precisa mostrar a decisão PENDENTE
    tanto quanto a já decidida/gravada (é o estado dela, não um filtro de
    entrada). O chamador (endpoint) decide se passa só as linhas do processo.
    """
    grupos: dict[ChaveNatural, list[ExtractedFieldStaging]] = {}
    sem_agrupamento: list[dict[str, Any]] = []

    for row in rows:
        chave, motivo = _chave_de(row)
        if chave is None:
            sem_agrupamento.append({
                "staging_id": row.id,
                "motivo": motivo,
                "target_entity": row.target_entity,
                "target_field": row.target_field,
                "field_name": row.field_name,
            })
            continue
        grupos.setdefault(chave, []).append(row)

    decisoes = [_montar_decisao(chave, membros) for chave, membros in grupos.items()]
    _injetar_area_total(decisoes)
    decisoes.sort(key=lambda d: d.chave)
    return ReconciliationResult(decisoes=decisoes, sem_agrupamento=sem_agrupamento)


def localizar_decisao(rows: list[ExtractedFieldStaging], chave: ChaveNatural) -> Optional[Decisao]:
    """Recomputa as decisões e devolve a que casa com `chave` — usada por
    `decidir_decisao` para nunca decidir sobre um agrupamento desatualizado
    (nova linha pode ter chegado desde a última leitura da tela)."""
    resultado = build_decisions(rows)
    for d in resultado.decisoes:
        if d.chave == chave:
            return d
    return None
