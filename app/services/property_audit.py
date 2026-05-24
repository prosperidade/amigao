"""Cálculos determinísticos do auditor_imovel — Sprint A2 (Onda 2 da Fase 2).

A matemática do cruzamento documental NÃO passa pelo LLM. O auditor_imovel usa
estas funções puras como tools; o LLM pode opcionalmente explicar e priorizar
as divergências detectadas, mas a conta é destas funções.

Cobre os cruzamentos mínimos da skill `diagnostico/situacao_ambiental_imovel_rural`:
- Matrícula × CAR (área, GEO INCRA)
- Matrícula × CCIR/ITR/SIGEF (área)
- Detecção de GEO INCRA ausente na matrícula (H1 da skill)
- Detecção de RL averbada × declarada (H12)

Saída: lista de divergências tipadas para alimentar `RegulatoryIssue`
(`app/models/regulatory.py:RegulatoryIssue`) e `Divergencia`
(`app/schemas/stage_output.py:Divergencia`).
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
# pela sócia). Alinhada com `RiscoGrau` da taxonomia oficial (Mapa de Riscos
# da skill diagnostico) — 4 níveis, NÃO os 3 do RegulatoryIssueSeverity.
# A persistência mapeia 4→3 via _GRADE_TO_SEVERITY abaixo.
#
# Princípio: SEMPRE emitir o finding. A régua só decide o grau — divergência
# pequena (≤ tolerância) vira "informativo", não silêncio. Auditor é radar,
# não cancela: sinaliza todas as inconsistências, deixa o consultor decidir.
GRADE_INFORMATIVO = "informativo"
GRADE_ATENCAO = "atencao"
GRADE_ALTO = "alto"
GRADE_CRITICO = "critico"

_GRADE_TO_SEVERITY: dict[str, str] = {
    GRADE_INFORMATIVO: "info",
    GRADE_ATENCAO: "warning",
    GRADE_ALTO: "critical",
    GRADE_CRITICO: "critical",
}


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
    """Achado bruto do auditor — fonte de RegulatoryIssue + Divergencia.

    Dois eixos de severidade convivem:
    - `severity` (3 níveis: info/warning/critical) — alinha com `RegulatoryIssueSeverity`
      do model; usado na persistência.
    - `grade` (4 níveis: informativo/atencao/alto/critico) — alinha com `RiscoGrau`
      da skill (taxonomia oficial); usado para sinalização no payload e UI.

    Mapeamento 4→3 fica em `_GRADE_TO_SEVERITY`; `grade=""` (vazio) significa
    "não classificado" (callers legados) e o caller derivava manualmente.
    """

    type: str            # area_divergente, sobreposicao_app, geo_incra_ausente, ...
    severity: str        # info, warning, critical
    tema: str            # área, titularidade, GEO INCRA, ...
    descricao: str
    impacto: str
    evidencia: dict[str, Any]  # campos crus para auditoria/debug
    grade: str = ""      # informativo, atencao, alto, critico (Onda C)


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

    # --- 1. Cruzamento de áreas (Matrícula × CAR × CCIR/ITR) ---------------
    area_doc = property_data.get("area_documental_ha")
    area_car = property_data.get("car_area_ha") or property_data.get("area_grafica_ha") or extracted.get("car_area_ha")
    area_ccir = property_data.get("ccir_area_ha") or extracted.get("ccir_area_ha")
    area_itr = property_data.get("itr_area_ha") or extracted.get("itr_area_ha")

    cmp_pairs = [
        ("matrícula × CAR", area_doc, area_car),
        ("matrícula × CCIR", area_doc, area_ccir),
        ("matrícula × ITR", area_doc, area_itr),
        ("CAR × CCIR", area_car, area_ccir),
    ]
    for tema, a, b in cmp_pairs:
        # Pares incompletos (um ou ambos None) NÃO viram finding de
        # `area_divergente`. Não há cruzamento real — é dado faltante, domínio
        # próprio (a detecção de "documento esperado ausente" fica como dívida
        # para uma função separada quando a sócia validar o conjunto canônico
        # de documentos esperados por demand_type).
        if a is None or b is None:
            continue
        cmp = compare_areas(a, b, tolerance_pct=tolerance_pct)
        # Onda C: SEMPRE emite finding quando há cruzamento real (ambos lados
        # presentes). A régua decide o grau (informativo/atencao/alto/critico);
        # divergência nunca é suprimida. Áreas iguais (≤ 1%) viram "informativo"
        # — auditoria sabe que o cruzamento foi feito.
        grade = grade_area_divergence(cmp.diff_pct, tolerance_pct=tolerance_pct)
        severity = _GRADE_TO_SEVERITY[grade]
        descricao = (
            f"Áreas {tema}: {cmp.area_a_ha} ha vs {cmp.area_b_ha} ha "
            f"(Δ={cmp.diff_ha} ha, {(cmp.diff_pct * 100):.2f}%)"
        )
        findings.append(AuditFinding(
            type="area_divergente",
            severity=severity,
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
        ))

    # --- 2. GEO INCRA na matrícula (H1) ------------------------------------
    matricula_text = property_data.get("matricula_text") or extracted.get("matricula_text")
    if matricula_text is not None and not has_geo_incra(matricula_text):
        findings.append(AuditFinding(
            type="geo_incra_ausente",
            severity="critical",
            tema="GEO INCRA",
            descricao="Matrícula não menciona georreferenciamento certificado pelo INCRA.",
            impacto=(
                "CAR sem GEO certificado tende a ser desperdício de recurso; GEO costuma "
                "ser exigido por banco/cartório em retificação, garantia, desmembramento "
                "ou conflito de limites (H1 da skill)."
            ),
            evidencia={"has_geo_incra_match": False},
        ))

    # --- 3. RL averbada × declarada (H12) ----------------------------------
    rl_decl = property_data.get("rl_declared_ha")
    rl_averb = property_data.get("rl_averbada_ha")
    if rl_decl is not None and rl_averb is not None:
        cmp = compare_areas(rl_decl, rl_averb, tolerance_pct=tolerance_pct)
        if cmp.divergent and cmp.diff_pct is not None:
            findings.append(AuditFinding(
                type="rl_divergente",
                severity="warning",
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
                },
            ))

    # --- 4. Sobreposição espacial — depende de geom (D1, ausente hoje) -----
    # MVP: se geom é None, marcamos "verificação espacial pendente" como FYI.
    # Quando D1 (parser shapefile) chegar, esta seção faz overlay PostGIS real
    # (área CAR × APP, sobreposição com UC, etc.).
    if property_data.get("geom") is None:
        findings.append(AuditFinding(
            type="verificacao_espacial_pendente",
            severity="info",
            tema="geometria",
            descricao=(
                "Property.geom não populado — verificação espacial (APP, RL, UC, "
                "sobreposição com terceiros) não pôde ser executada."
            ),
            impacto=(
                "Cruzamento documental concluído sem overlay PostGIS. Quando o "
                "parser de shapefile/KML for habilitado (gap D1), esta análise "
                "complementa o auditor."
            ),
            evidencia={"geom_present": False},
        ))

    return findings


# ---------------------------------------------------------------------------
# Mapeamento Finding → RegulatoryIssueType / Divergencia
# ---------------------------------------------------------------------------

_FINDING_TO_ISSUE_TYPE: dict[str, str] = {
    "area_divergente": "area_divergente",
    "rl_divergente": "outro",  # RegulatoryIssueType não tem "rl_divergente" hoje; vira "outro"
    "geo_incra_ausente": "outro",
    "verificacao_espacial_pendente": "outro",
}


def finding_to_issue_type(finding: AuditFinding) -> str:
    """Mapeia AuditFinding.type → RegulatoryIssueType.value (string).

    Usado pelo agente para criar RegulatoryIssue tipados a partir dos achados
    do auditor. Tipos não previstos no enum viram "outro".
    """
    return _FINDING_TO_ISSUE_TYPE.get(finding.type, "outro")
