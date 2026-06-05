"""
Ficha 02 / FASE 3 — Matriz de Inconsistências (saída canônica do auditor_imovel).

DETERMINÍSTICO (sem LLM). Lê o staging da Fase 2 (`ExtractedFieldStaging`),
monta colunas dinâmicas por FONTE (cada matrícula via `matricula_hint`, +
ccir/itr/car/rat/sigef) e linhas canônicas, confronta (âncora = SIGEF quando
presente), classifica pela taxonomia da Ficha 02 §4 e propõe ação + destino.

Não grava na base real; devolve a matriz (JSON) + as marcações de status do
staging (consistente / divergente_transcricao / divergente_fundo). A decisão
aceito/rejeitado é do consultor (Fase 4) — não é marcada aqui.

Gap D1 (sem `Property.geom`): linhas técnicas (APP/hidrografia/supressões/
cobertura, vindas das `pendencias_rat`) são REGISTRADAS como `critico` com
`profundidade="tecnica"` — sem confronto espacial real.
"""

from __future__ import annotations

import enum
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

# Tolerância de área: ≤ 0,5% entre fontes ⇒ divergência de transcrição (pequena,
# justificável); acima ⇒ de fundo. Diferença exatamente 0 ⇒ consistente.
AREA_TOLERANCE_PCT = Decimal("0.005")


class MatrixSituacao(str, enum.Enum):
    """Taxonomia da Ficha 02 §4 (eixo da linha da matriz)."""

    consistente = "consistente"
    atencao = "atencao"
    divergente = "divergente"
    inconsistente = "inconsistente"
    critico = "critico"


@dataclass
class MatrixRow:
    item: str
    label: str
    fontes: dict[str, Any]
    situacao: str
    acao_recomendada: str
    destino: list[str]
    profundidade: str = "intake"  # "intake" | "tecnica"
    subtipo: Optional[str] = None  # divergente → "transcricao" | "fundo"

    def to_dict(self) -> dict[str, Any]:
        d = {
            "item": self.item,
            "label": self.label,
            "fontes": self.fontes,
            "situacao": self.situacao,
            "acao_recomendada": self.acao_recomendada,
            "destino": self.destino,
            "profundidade": self.profundidade,
        }
        if self.subtipo:
            d["subtipo"] = self.subtipo
        return d


def _destino(situacao: str, *, subtipo: Optional[str] = None, requires_official: bool = False) -> list[str]:
    """Destino por taxonomia (Ficha 02 §4)."""
    if situacao == MatrixSituacao.critico.value:
        return ["diagnostico", "orcamento"]
    if situacao == MatrixSituacao.inconsistente.value:
        base = ["correcao_documental"]
        if requires_official:
            base += ["diagnostico", "orcamento"]
        return base
    if situacao == MatrixSituacao.divergente.value:
        return ["diagnostico"] if subtipo == "fundo" else ["alertas"]
    if situacao == MatrixSituacao.atencao.value:
        return ["alertas"]
    return []  # consistente


# ---------------------------------------------------------------------------
# Parsing de valores do staging
# ---------------------------------------------------------------------------

def _row_value(row: Any) -> Any:
    fv = getattr(row, "field_value", None)
    if isinstance(fv, dict):
        return fv.get("value")
    return fv


def _to_float_br(value: Any) -> Optional[float]:
    """Converte número PT-BR ('1.010,7113', '660,6561') ou float para float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower().replace("ha", "").replace("hectares", "").strip()
    s = re.sub(r"[^0-9.,-]", "", s)
    if not s:
        return None
    if "," in s:  # vírgula = decimal; ponto = milhar
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def _fmt_ha(value: float) -> str:
    """Formata em PT-BR com até 4 casas, sem zeros à direita ('0,153')."""
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


# ---------------------------------------------------------------------------
# Agrupamento das fontes
# ---------------------------------------------------------------------------

@dataclass
class _Source:
    key: str
    doc_type: str
    # field_name -> (value, row)
    fields: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    matricula_listadas: list[Any] = field(default_factory=list)  # itens car
    pendencias: list[dict[str, Any]] = field(default_factory=list)  # rat


def _group_sources(rows: list[Any]) -> dict[str, _Source]:
    sources: dict[str, _Source] = {}
    for row in rows:
        dt = (getattr(row, "source_doc_type", None) or "outro").lower()
        hint = getattr(row, "matricula_hint", None)
        fname = getattr(row, "field_name", None)
        val = _row_value(row)

        key = (f"matricula:{hint}" if hint else "matricula") if dt == "matricula" else dt
        src = sources.setdefault(key, _Source(key=key, doc_type=dt))

        if dt == "car" and fname == "matricula_listada":
            src.matricula_listadas.append(val)
            continue
        if dt == "rat" and fname == "pendencias_rat":
            if isinstance(val, list):
                src.pendencias = val
            continue
        if fname:
            src.fields[fname] = (val, row)
    return sources


def _get(src: Optional[_Source], *fnames: str) -> Any:
    if src is None:
        return None
    for fn in fnames:
        if fn in src.fields:
            return src.fields[fn][0]
    return None


def _row_of(src: Optional[_Source], *fnames: str) -> Any:
    if src is None:
        return None
    for fn in fnames:
        if fn in src.fields:
            return src.fields[fn][1]
    return None


# ---------------------------------------------------------------------------
# Builder principal
# ---------------------------------------------------------------------------

@dataclass
class MatrixResult:
    matriz: dict[str, Any]
    status_updates: list[tuple[Any, str]]  # (staging_row, novo_status)


def build_matrix(rows: list[Any]) -> MatrixResult:
    """Constrói a matriz a partir das linhas de staging do processo."""
    sources = _group_sources(rows)
    matricula_keys = sorted(k for k in sources if k.startswith("matricula"))
    car = sources.get("car")
    ccir = sources.get("ccir")
    itr = sources.get("itr")
    sigef = sources.get("sigef")
    rat = sources.get("rat")

    fontes_presentes = list(sources.keys())
    linhas: list[MatrixRow] = []
    status_updates: list[tuple[Any, str]] = []

    # --- area_total ------------------------------------------------------
    area_by_matricula: dict[str, float] = {}
    area_rows: list[Any] = []
    for mk in matricula_keys:
        a = _to_float_br(_get(sources[mk], "area_registrada_ha", "area_ha"))
        if a:
            area_by_matricula[mk] = a
            r = _row_of(sources[mk], "area_registrada_ha", "area_ha")
            if r is not None:
                area_rows.append(r)
    soma_matriculas = round(sum(area_by_matricula.values()), 4) if area_by_matricula else None

    other_areas: dict[str, tuple[float, Any]] = {}
    for key, fnames in (("car", ("area_declarada_ha",)), ("ccir", ("area_ha",)),
                        ("itr", ("area_declarada_ha",)), ("sigef", ("area_georreferenciada_ha",))):
        src = sources.get(key)
        a = _to_float_br(_get(src, *fnames))
        if a:
            other_areas[key] = (a, _row_of(src, *fnames))

    fontes_area: dict[str, Any] = dict(area_by_matricula)
    if soma_matriculas is not None:
        fontes_area["soma_matriculas"] = soma_matriculas
    for k, (a, _) in other_areas.items():
        fontes_area[k] = a

    if soma_matriculas or other_areas:
        anchor = None
        if sigef and other_areas.get("sigef"):
            anchor = other_areas["sigef"][0]
        elif soma_matriculas:
            anchor = soma_matriculas
        elif other_areas:
            anchor = next(iter(other_areas.values()))[0]

        compare_vals = ([soma_matriculas] if soma_matriculas else []) + [a for a, _ in other_areas.values()]
        present = [v for v in compare_vals if v and v > 0]
        if anchor and len(present) >= 2:
            max_v, min_v = max(present), min(present)
            diff = max_v - min_v
            pct = Decimal(str(diff)) / Decimal(str(max_v)) if max_v else Decimal(0)
            if diff == 0:
                row = MatrixRow("area_total", "Área total (ha)", fontes_area,
                                MatrixSituacao.consistente.value,
                                "Áreas conferem entre as fontes.", _destino("consistente"))
                for r in area_rows + [v[1] for v in other_areas.values() if v[1] is not None]:
                    status_updates.append((r, "consistente"))
            else:
                has_zero = any((_to_float_br(_get(sources.get(k), "area_declarada_ha", "area_ha",
                                                  "area_georreferenciada_ha")) == 0)
                               for k in ("sigef",) if sources.get(k))
                subtipo = "fundo" if (has_zero or pct > AREA_TOLERANCE_PCT) else "transcricao"
                maxsrc = max(other_areas, key=lambda k: other_areas[k][0]) if other_areas else "—"
                acao = (
                    f"ajustar/justificar diferença de {_fmt_ha(diff)} ha "
                    f"(soma matrículas {_fmt_ha(soma_matriculas)} vs {maxsrc.upper()} "
                    f"{_fmt_ha(other_areas[maxsrc][0])})"
                ) if soma_matriculas and other_areas else f"ajustar/justificar diferença de {_fmt_ha(diff)} ha"
                row = MatrixRow("area_total", "Área total (ha)", fontes_area,
                                MatrixSituacao.divergente.value, acao,
                                _destino("divergente", subtipo=subtipo), subtipo=subtipo)
                novo = f"divergente_{subtipo}"
                # matrículas formam a âncora → consistentes; fontes que divergem → divergentes.
                for r in area_rows:
                    status_updates.append((r, "consistente"))
                for _k, (a, r) in other_areas.items():
                    if r is not None:
                        status_updates.append((r, "consistente" if anchor and a == anchor else novo))
            linhas.append(row)

    # --- denominacao_imovel ---------------------------------------------
    denom_rows: list[Any] = []
    denom_fontes: dict[str, Any] = {}
    for key, src in sources.items():
        val = _get(src, "denominacao", "nome_imovel")
        if val not in (None, ""):
            denom_fontes[key] = val
            r = _row_of(src, "denominacao", "nome_imovel")
            if r is not None:
                denom_rows.append(r)
    if denom_fontes:
        distintas = {_norm_text(v) for v in denom_fontes.values()}
        if len(distintas) > 1:
            linhas.append(MatrixRow(
                "denominacao_imovel", "Denominação do imóvel", denom_fontes,
                MatrixSituacao.divergente.value, "padronizar denominação entre as fontes",
                _destino("divergente", subtipo="transcricao"), subtipo="transcricao"))
            for r in denom_rows:
                status_updates.append((r, "divergente_transcricao"))
        else:
            linhas.append(MatrixRow(
                "denominacao_imovel", "Denominação do imóvel", denom_fontes,
                MatrixSituacao.consistente.value, "Denominação confere.", _destino("consistente")))
            for r in denom_rows:
                status_updates.append((r, "consistente"))

    # --- codigo_incra_sncr ----------------------------------------------
    incra_fontes: dict[str, Any] = {}
    for key, src in sources.items():
        val = _get(src, "codigo_sncr_incra", "codigo_incra")
        if val not in (None, ""):
            incra_fontes[key] = val
    if incra_fontes:
        distintos = {_norm_text(v) for v in incra_fontes.values()}
        if len(distintos) > 1:
            linhas.append(MatrixRow(
                "codigo_incra_sncr", "Código INCRA/SNCR", incra_fontes,
                MatrixSituacao.atencao.value, "montar tabela de correspondência cadastral",
                _destino("atencao")))
        else:
            linhas.append(MatrixRow(
                "codigo_incra_sncr", "Código INCRA/SNCR", incra_fontes,
                MatrixSituacao.consistente.value, "Código confere.", _destino("consistente")))

    # --- sigef_georreferenciamento --------------------------------------
    # Só faz sentido cobrar SIGEF quando há algum contexto fundiário do imóvel.
    tem_contexto_imovel = bool(matricula_keys or car or ccir or itr or sigef)
    sigef_area = _to_float_br(_get(sigef, "area_georreferenciada_ha")) if sigef else None
    rat_geo_pendencia = _rat_has(rat, ("geo", "georref", "sigef", "vetoriz", "perimetro", "vertice"))
    if not tem_contexto_imovel:
        pass
    elif sigef is None or not sigef_area or rat_geo_pendencia:
        fontes_sig = {"sigef": (sigef_area if sigef_area else "ausente"),
                      "rat": "pendência geo" if rat_geo_pendencia else "—"}
        linhas.append(MatrixRow(
            "sigef_georreferenciamento", "Georreferenciamento (SIGEF)", fontes_sig,
            MatrixSituacao.critico.value, "verificar DCR/SIGEF/SNCR (certificação ausente/pendente)",
            _destino("critico")))
    else:
        linhas.append(MatrixRow(
            "sigef_georreferenciamento", "Georreferenciamento (SIGEF)", {"sigef": sigef_area},
            MatrixSituacao.consistente.value, "Certificação presente.", _destino("consistente")))

    # --- car_presenca_consistencia --------------------------------------
    if car is not None:
        car_code = _get(car, "numero_car")
        itr_car = _get(itr, "numero_car") if itr else None
        car_mats = {_norm_text(m.get("numero") if isinstance(m, dict) else m) for m in car.matricula_listadas}
        car_mats = {m for m in car_mats if m}
        staging_mats = {_norm_text(k.split(":", 1)[1]) for k in matricula_keys if ":" in k}

        if itr is not None and not itr_car:
            linhas.append(MatrixRow(
                "car_presenca_consistencia", "CAR — presença/consistência",
                {"car": car_code or "presente", "itr": "sem CAR declarado"},
                MatrixSituacao.inconsistente.value,
                "atualizar ITR/DIAC com o número do CAR",
                _destino("inconsistente", requires_official=True)))
        elif car_mats and staging_mats and car_mats != staging_mats:
            linhas.append(MatrixRow(
                "car_presenca_consistencia", "CAR — presença/consistência",
                {"car": sorted(car_mats), "matriculas": sorted(staging_mats)},
                MatrixSituacao.inconsistente.value,
                "conciliar matrículas listadas no CAR × matrículas do imóvel",
                _destino("inconsistente", requires_official=True)))
        else:
            linhas.append(MatrixRow(
                "car_presenca_consistencia", "CAR — presença/consistência",
                {"car": car_code or "presente"},
                MatrixSituacao.consistente.value, "CAR presente e coerente.", _destino("consistente")))

    # --- acesso_imovel ---------------------------------------------------
    if _rat_has(rat, ("acesso", "via de acesso", "servidao")):
        linhas.append(MatrixRow(
            "acesso_imovel", "Acesso ao imóvel", {"rat": "descrição insuficiente"},
            MatrixSituacao.atencao.value, "padronizar acesso com coordenadas",
            _destino("atencao")))

    # --- linhas técnicas (pendências do RAT — aguardam geo/Etapa 4) ------
    if rat is not None:
        for pend in rat.pendencias:
            if not isinstance(pend, dict):
                continue
            cat = pend.get("categoria") or ""
            ncat = _norm_text(cat)
            if any(t in ncat for t in ("acesso", "via de acesso", "servidao")):
                continue  # já tratado em acesso_imovel
            if not any(t in ncat for t in (
                "app", "preservacao", "hidrograf", "curso d", "supress", "vegetac",
                "cobertura", "uso do solo", "reserva legal", "sobreposic", "apa",
            )):
                continue
            acao = pend.get("recomendacao") or "confronto espacial pendente (geo/Etapa 4)"
            linhas.append(MatrixRow(
                item=f"tecnica:{ncat[:40]}",
                label=f"[técnica] {cat}",
                fontes={"rat": pend.get("detalhamento") or cat},
                situacao=MatrixSituacao.critico.value,
                acao_recomendada=str(acao),
                destino=_destino("critico"),
                profundidade="tecnica",
            ))

    resumo: dict[str, int] = {}
    for r in linhas:
        resumo[r.situacao] = resumo.get(r.situacao, 0) + 1

    matriz = {
        "fontes": fontes_presentes,
        "linhas": [r.to_dict() for r in linhas],
        "resumo": resumo,
        "gap_d1": "linhas técnicas registradas sem confronto espacial (sem Property.geom)",
    }
    return MatrixResult(matriz=matriz, status_updates=status_updates)


def _rat_has(rat: Optional[_Source], termos: tuple[str, ...]) -> bool:
    if rat is None:
        return False
    for pend in rat.pendencias:
        cat = _norm_text(pend.get("categoria") if isinstance(pend, dict) else pend)
        det = _norm_text(pend.get("detalhamento") if isinstance(pend, dict) else "")
        if any(t in cat or t in det for t in termos):
            return True
    return False
