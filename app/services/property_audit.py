"""Cálculos determinísticos do auditor_imovel — Sprint A2 (Onda 2 da Fase 2)
+ PROMPT_5 Onda A.

A matemática do cruzamento documental NÃO passa pelo LLM. O auditor_imovel usa
estas funções puras como tools; o LLM pode opcionalmente explicar e priorizar
as divergências detectadas, mas a conta é destas funções.

Cobre os cruzamentos mínimos da skill `auditor_imovel/
analise_divergencias_documentais` (v1.1.0, validada pela sócia):
- Matrícula × CAR / CCIR / ITR / GEO (área)
- Detecção de GEO INCRA ausente na matrícula (H1)
- Detecção de RL averbada × declarada (H12)
- Verificação espacial pendente (sinal quando Property.geom ausente)

Saída: lista de ``AuditFinding`` com **taxonomia rica** (PROMPT_5 Onda A) —
``codigo_alerta`` (catálogo evolutivo `regulatory_issue_catalog`), ``familia``
(enum estável 11), ``grade`` (4 níveis), e overrides do default do catálogo
(``muda_rota_regulatoria`` / ``muda_escopo_preco_prazo`` /
``documentos_cruzados``). Sai o ``severity`` de 3 níveis — agora ``grade``
de 4 é o único eixo (persistido como ``RegulatoryIssue.severity``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# Tolerância default — 1% é o limite do grau "informativo" (a régua da Onda C).
# Tolerância configurável: o caller pode passar outro valor para apertar/relaxar
# qual diferença ainda é "informativa". Acima dela, a régua categoriza em
# atencao/alto/critico — divergência NUNCA é suprimida, só muda o grau.
DEFAULT_AREA_TOLERANCE_PCT: Decimal = Decimal("0.01")

# Régua de graus para divergência de área entre documentos (Onda C, validada
# pela sócia). PROMPT_5 Onda A: agora ``grade`` é o **único** eixo —
# persistido como ``RegulatoryIssue.severity`` (4 níveis). O antigo
# ``_GRADE_TO_SEVERITY`` que colapsava 4→3 SAIU.
#
# Princípio: SEMPRE emitir o finding. A régua só decide o grau — divergência
# pequena (≤ tolerância) vira "informativo", não silêncio. Auditor é radar,
# não cancela: sinaliza todas as inconsistências, deixa o consultor decidir.
GRADE_INFORMATIVO = "informativo"
GRADE_ATENCAO = "atencao"
GRADE_ALTO = "alto"
GRADE_CRITICO = "critico"


def grade_area_divergence(
    diff_pct: Decimal | None,
    tolerance_pct: Decimal = DEFAULT_AREA_TOLERANCE_PCT,
) -> str:
    """Classifica diferença percentual em grau (régua de 4 faixas).

    - `diff_pct is None` (dado ausente) → `atencao` (não dá pra cruzar; sinaliza
      mas não é crítico — o consultor precisa obter o dado faltante).
    - `≤ tolerance_pct` (default 1%) → `informativo` (arredondamento cartorial
      normal entre matrícula × CAR × CCIR).
    - `tolerance_pct < diff ≤ 5%` → `atencao`.
    - `5% < diff ≤ 10%` → `alto`.
    - `> 10%` → `critico` (impacto direto em compensação/recuperação por hectare).
    """
    if diff_pct is None:
        return GRADE_ATENCAO
    if diff_pct <= tolerance_pct:
        return GRADE_INFORMATIVO
    if diff_pct <= Decimal("0.05"):
        return GRADE_ATENCAO
    if diff_pct <= Decimal("0.10"):
        return GRADE_ALTO
    return GRADE_CRITICO


def grade_overlap_severity() -> str:
    """Sobreposição (terceiro / UC / assentamento / terra pública / matrícula
    vizinha) é SEMPRE `critico`, independente do percentual ou da área. É
    finding próprio — não dilui na conta de hectares de divergência documental.

    Helper preparado para quando a detecção espacial real estiver disponível
    (depende de D1, parser shapefile + `Property.geom`). Hoje não há chamador
    em audit_property — fica para sprint posterior.
    """
    return GRADE_CRITICO

# Padrões reconhecidos como menção a GEO INCRA na matrícula.
# Fonte: H1 da skill — "número de GEO certificado pelo INCRA" pode aparecer
# como "código SIGEF", "georreferenciado conforme Lei 10.267/2001", etc.
_GEO_INCRA_HINTS = (
    re.compile(r"\bGEO\b.*\bINCRA\b", re.IGNORECASE),
    re.compile(r"\bSIGEF\b", re.IGNORECASE),
    re.compile(r"\bgeorreferenc[ií]ad[oa]\b", re.IGNORECASE),
    re.compile(r"Lei\s*(?:n[ºo°]?\s*)?10\.?267", re.IGNORECASE),
    re.compile(r"\bCNIR\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class AreaComparison:
    """Resultado de comparar áreas entre dois documentos."""

    area_a_ha: Decimal | None
    area_b_ha: Decimal | None
    diff_ha: Decimal | None
    diff_pct: Decimal | None
    divergent: bool  # True quando diff_pct > tolerance ou um dos lados é None


@dataclass(frozen=True)
class AuditFinding:
    """Achado bruto do auditor — fonte de ``RegulatoryIssue`` + ``Divergencia``.

    PROMPT_5 Onda A: taxonomia rica. Cada finding carrega:

    - ``codigo_alerta`` — código curto, estável, MAIÚSCULAS (catálogo evolutivo
      em `regulatory_issue_catalog`; ex.: ``AREA_MATRICULA_X_CAR``,
      ``GEO_AUSENTE``).
    - ``familia`` — uma das 11 do enum estável (``area``, ``geo_incra``,
      ``ambiental``, ``car``, ``geoespacial``, ``identificacao``,
      ``titularidade``, ``fiscal``, ``restricao_risco``, ``licenciamento``,
      ``validade_documental``).
    - ``grade`` — 4 níveis (``informativo``/``atencao``/``alto``/``critico``).
      É o **único** eixo de severidade — persistido em
      ``RegulatoryIssue.severity`` (que também é 4 níveis). Saiu o ``severity``
      de 3 níveis e o mapeamento ``_GRADE_TO_SEVERITY``.
    - ``muda_rota_regulatoria`` / ``muda_escopo_preco_prazo`` — overrides do
      default do catálogo. ``None`` significa "usar default do catálogo".
    - ``documentos_cruzados`` — lista dos documentos que foram comparados
      neste finding específico. ``None`` = usa default do catálogo.
    """

    codigo_alerta: str           # AREA_MATRICULA_X_CAR, GEO_AUSENTE, ...
    familia: str                 # area, geo_incra, ambiental, car, ...
    grade: str                   # informativo / atencao / alto / critico
    tema: str                    # rótulo legível: "área (matrícula × CAR)", ...
    descricao: str
    impacto: str
    evidencia: dict[str, Any]    # campos crus para auditoria/debug
    muda_rota_regulatoria: bool | None = None   # None = usa default do catálogo
    muda_escopo_preco_prazo: bool | None = None
    documentos_cruzados: list[str] | None = None


# ---------------------------------------------------------------------------
# Comparações de área
# ---------------------------------------------------------------------------

def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def compare_areas(
    area_a_ha: Any,
    area_b_ha: Any,
    tolerance_pct: Decimal = DEFAULT_AREA_TOLERANCE_PCT,
) -> AreaComparison:
    """Compara duas áreas em hectares.

    Retorna ``AreaComparison.divergent=True`` quando:
    - um dos dois é None (não tem como cruzar)
    - ou o diff relativo é maior que ``tolerance_pct`` (default 1%)

    Áreas iguais a zero são tratadas como "não informadas".
    """
    a = _to_decimal(area_a_ha)
    b = _to_decimal(area_b_ha)

    if a is None or b is None or a == 0 or b == 0:
        return AreaComparison(
            area_a_ha=a, area_b_ha=b,
            diff_ha=None, diff_pct=None,
            divergent=True,  # falta de dado é divergência sinalizável
        )

    diff = abs(a - b)
    base = max(a, b)
    pct = diff / base
    return AreaComparison(
        area_a_ha=a, area_b_ha=b,
        diff_ha=diff, diff_pct=pct,
        divergent=pct > tolerance_pct,
    )


# ---------------------------------------------------------------------------
# Detecção GEO INCRA (H1 da skill)
# ---------------------------------------------------------------------------

def has_geo_incra(matricula_text: str | None) -> bool:
    """Retorna True quando o texto da matrícula contém menção a georreferenciamento
    certificado (SIGEF, CNIR, "Lei 10.267", etc.). Heurística textual; falso
    negativo é mais comum que falso positivo — o agente pode marcar como
    "verificar manualmente" quando retorna False.
    """
    if not matricula_text:
        return False
    return any(p.search(matricula_text) for p in _GEO_INCRA_HINTS)


# ---------------------------------------------------------------------------
# Orquestrador determinístico
# ---------------------------------------------------------------------------

def audit_property(
    *,
    property_data: dict[str, Any],
    documents: list[dict[str, Any]] | None = None,
    extracted_data: dict[str, Any] | None = None,
    tolerance_pct: Decimal = DEFAULT_AREA_TOLERANCE_PCT,
) -> list[AuditFinding]:
    """Roda a bateria de cruzamentos sobre ``property_data`` + dados extraídos.

    A entrada não é o ORM (mantém pura); pode ser construída a partir do
    ``DiagnosticoAgent._load_process_data()`` ou de qualquer dict equivalente.

    ``property_data`` esperado (todos opcionais):
    - ``total_area_ha``     — área "oficial" do imóvel (Property.total_area_ha)
    - ``area_documental_ha`` — área da matrícula
    - ``area_grafica_ha``    — área do polígono CAR / SIGEF
    - ``car_area_ha``        — área declarada no CAR (se vier do extrator)
    - ``ccir_area_ha``       — área do CCIR
    - ``itr_area_ha``        — área declarada no ITR
    - ``matricula_text``     — texto bruto da matrícula (para has_geo_incra)
    - ``geom``               — geometria PostGIS (presença/ausência só)
    - ``rl_status``          — averbada/proposta/pendente/cancelada
    - ``rl_declared_ha``     — RL declarada no CAR
    - ``rl_averbada_ha``     — RL averbada na matrícula

    Retorna lista de ``AuditFinding`` (zero ou mais).
    """
    findings: list[AuditFinding] = []
    extracted = extracted_data or {}

    # --- 1. Cruzamento de áreas (Matrícula × CAR × CCIR/ITR / CAR × CCIR) --
    # Cada par tem código próprio no catálogo (PROMPT_5 Onda A).
    area_doc = property_data.get("area_documental_ha")
    area_car = property_data.get("car_area_ha") or property_data.get("area_grafica_ha") or extracted.get("car_area_ha")
    area_ccir = property_data.get("ccir_area_ha") or extracted.get("ccir_area_ha")
    area_itr = property_data.get("itr_area_ha") or extracted.get("itr_area_ha")

    # (rótulo_tema, codigo_alerta, documentos_cruzados, área_a, área_b)
    cmp_pairs = [
        ("matrícula × CAR", "AREA_MATRICULA_X_CAR", ["Matricula", "CAR"], area_doc, area_car),
        ("matrícula × CCIR", "AREA_MATRICULA_X_CCIR", ["Matricula", "CCIR"], area_doc, area_ccir),
        ("matrícula × ITR", "AREA_MATRICULA_X_ITR", ["Matricula", "ITR"], area_doc, area_itr),
        ("CAR × CCIR", "AREA_CAR_X_CCIR", ["CAR", "CCIR"], area_car, area_ccir),
    ]
    for tema, codigo, docs, a, b in cmp_pairs:
        # Pares incompletos (um ou ambos None) NÃO viram finding de área. Não
        # há cruzamento real — é dado faltante, domínio próprio (a detecção
        # de "documento esperado ausente" fica como dívida para uma função
        # separada quando a sócia validar o conjunto canônico de documentos
        # esperados por demand_type).
        if a is None or b is None:
            continue
        cmp = compare_areas(a, b, tolerance_pct=tolerance_pct)
        # Onda C: SEMPRE emite finding quando há cruzamento real (ambos lados
        # presentes). A régua decide o grau (informativo/atencao/alto/critico);
        # divergência nunca é suprimida. Áreas iguais (≤ 1%) viram "informativo"
        # — auditoria sabe que o cruzamento foi feito.
        grade = grade_area_divergence(cmp.diff_pct, tolerance_pct=tolerance_pct)
        descricao = (
            f"Áreas {tema}: {cmp.area_a_ha} ha vs {cmp.area_b_ha} ha "
            f"(Δ={cmp.diff_ha} ha, {(cmp.diff_pct * 100):.2f}%)"
        )
        findings.append(AuditFinding(
            codigo_alerta=codigo,
            familia="area",
            grade=grade,
            tema=f"área ({tema})",
            descricao=descricao,
            impacto=(
                "Passivo, compensação e recuperação são calculados em hectares — "
                "padronizar antes do protocolo."
            ),
            evidencia={
                "area_a_ha": str(cmp.area_a_ha),
                "area_b_ha": str(cmp.area_b_ha),
                "diff_pct": str(cmp.diff_pct),
                "tolerance_pct_used": str(tolerance_pct),
            },
            documentos_cruzados=docs,
        ))

    # --- 2. GEO INCRA na matrícula (H1) ------------------------------------
    matricula_text = property_data.get("matricula_text") or extracted.get("matricula_text")
    if matricula_text is not None and not has_geo_incra(matricula_text):
        findings.append(AuditFinding(
            codigo_alerta="GEO_AUSENTE",
            familia="geo_incra",
            grade=GRADE_CRITICO,
            tema="GEO INCRA",
            descricao="Matrícula não menciona georreferenciamento certificado pelo INCRA.",
            impacto=(
                "CAR sem GEO certificado tende a ser desperdício de recurso; GEO costuma "
                "ser exigido por banco/cartório em retificação, garantia, desmembramento "
                "ou conflito de limites (H1 da skill)."
            ),
            evidencia={"has_geo_incra_match": False},
            documentos_cruzados=["Matricula"],
        ))

    # --- 3. RL averbada × declarada (H12) ----------------------------------
    rl_decl = property_data.get("rl_declared_ha")
    rl_averb = property_data.get("rl_averbada_ha")
    if rl_decl is not None and rl_averb is not None:
        cmp = compare_areas(rl_decl, rl_averb, tolerance_pct=tolerance_pct)
        if cmp.divergent and cmp.diff_pct is not None:
            # Mesma régua de 4 faixas usada nos pares de área. grade preserva
            # os 4 níveis sem colapso (PROMPT_5 — saiu o severity 3-níveis).
            rl_grade = grade_area_divergence(cmp.diff_pct, tolerance_pct=tolerance_pct)
            findings.append(AuditFinding(
                codigo_alerta="RL_MATRICULA_DIVERGENTE_RL_CAR",
                familia="ambiental",
                grade=rl_grade,
                tema="Reserva Legal",
                descricao=(
                    f"RL declarada {rl_decl} ha ≠ averbada {rl_averb} ha "
                    f"({(cmp.diff_pct * 100):.2f}%)"
                ),
                impacto=(
                    "Banco/órgão pode exigir conciliação entre RL averbada na matrícula "
                    "e RL declarada no CAR antes de qualquer protocolização (H12)."
                ),
                evidencia={
                    "rl_declarada_ha": str(rl_decl),
                    "rl_averbada_ha": str(rl_averb),
                    "diff_pct": str(cmp.diff_pct),
                },
                documentos_cruzados=["Matricula", "CAR"],
            ))

    # --- 4. Sobreposição espacial — depende de geom (D1, ausente hoje) -----
    # Verificação espacial: DERIVADA na leitura quando geom IS NULL (ADR-020) —
    # NÃO emitida como RegulatoryIssue armazenado. Estado derivado se calcula na
    # leitura, nunca vira linha (Princípio 11; mesmo padrão de RL "averbada"
    # derivada e APP "—"). O endpoint GET /properties/{id}/diagnosis-notes
    # devolve a nota não-acionável "Verificação espacial pendente — geom
    # indisponível (D1)". Quando D1 (parser shapefile/KML) popular geom, ESTA
    # seção passa a emitir achados ESPACIAIS REAIS (overlay PostGIS: CAR × APP,
    # sobreposição com UC/terceiros) — aí sim findings persistidos.

    return findings


# ---------------------------------------------------------------------------
# Mapeamento Finding → RegulatoryIssue
# ---------------------------------------------------------------------------
#
# PROMPT_5 Onda A removeu `_FINDING_TO_ISSUE_TYPE` / `finding_to_issue_type`.
# Cada `AuditFinding.codigo_alerta` agora vai DIRETO para
# `RegulatoryIssue.codigo_alerta` (FK no catálogo `regulatory_issue_catalog`).
# Não há mais mapeamento intermediário "para outro" — a taxonomia é rica e
# 1:1 com o catálogo evolutivo.
