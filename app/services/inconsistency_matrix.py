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

Calibração caso #11 (Fazenda São Jorge — dump real de produção, 2026-06-06):
- ÁREA em DOIS NÍVEIS: por matrícula (certidão×CCIR×ITR×SIGEF, mesmo
  `matricula_hint`) e do imóvel (CAR/RAT × soma das matrículas). Imóvel muito
  maior que a soma conhecida ⇒ ATENÇÃO de vínculo (matrícula faltante), não
  falsa divergência. Inclui a área do RAT (`area_vetorizada_ha`).
- PENDÊNCIAS do RAT: o tema é casado por categoria+detalhamento+recomendação
  (as categorias do órgão são genéricas — "Unidades de Conservação",
  "Inconsistência Adicional"; o conteúdo vive no detalhamento).
- SIGEF: valida presença REAL de código + status (não só área).
- DICIONÁRIO DE SINÔNIMOS por item canônico (constantes abaixo), construído a
  partir da medição do staging real + `_FIELD_SPECS` da Fase 2.
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

# Imóvel (CAR/RAT) ≥ 1,5× a soma das matrículas conhecidas ⇒ provável matrícula
# faltante / vínculo incompleto — vira ATENÇÃO (pedir vínculo), não divergência.
MISSING_MATRICULA_FACTOR = Decimal("1.5")


# ---------------------------------------------------------------------------
# Dicionário de sinônimos por item canônico
# ---------------------------------------------------------------------------
# Origem dos nomes: MEDIÇÃO do staging real (caso #11) + `_FIELD_SPECS` da Fase 2
# (`app/services/ficha01_extraction.py`). NÃO inventar nomes — adicionar aqui
# quando a medição revelar uma variação nova.
#
# Área é resolvida por (doc_type → field_names) porque o MESMO nome muda de nível
# conforme o documento: `area_declarada_ha` é do imóvel no CAR e da matrícula no
# ITR. `_AREA_LEVEL` diz o nível de cada fonte.
_AREA_SYNONYMS: dict[str, tuple[str, ...]] = {
    "matricula": ("area_registrada_ha", "area_ha", "area_total", "area_total_imovel"),
    "sigef": ("area_georreferenciada_ha",),
    "ccir": ("area_ha", "area_declarada_ha"),
    "itr": ("area_declarada_ha", "area_ha"),
    "car": ("area_declarada_ha", "area_total", "area_total_imovel"),
    "rat": ("area_vetorizada_ha", "area_grafica_ha"),
}
_AREA_LEVEL: dict[str, str] = {
    "matricula": "matricula", "sigef": "matricula", "ccir": "matricula",
    "itr": "matricula", "car": "imovel", "rat": "imovel",
}
_DENOM_SYNONYMS: tuple[str, ...] = (
    "denominacao", "denominacao_imovel", "nome_imovel", "nome_imovel_rural",
    "averbacao_denominacao",
)
_INCRA_SYNONYMS: tuple[str, ...] = (
    "codigo_sncr_incra", "codigo_incra", "codigo_incra_sncr",
)

# Pendências do RAT → tema técnico. Prioridade importa (acesso/UC/supressão antes
# de cobertura; documentos por último). Casado contra categoria+detalhamento+
# recomendação normalizados.
_TEMA_LABEL: dict[str, str] = {
    "uc": "Sobreposição com Unidade(s) de Conservação",
    "supressao": "Supressão de vegetação / antropização pós-2008",
    "hidrografia": "Hidrografia / APP / nascentes não declaradas",
    "cobertura": "Cobertura do solo",
}
_TEMA_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("acesso", ("acesso", "via de acesso", "servidao")),
    ("uc", ("unidade de conservacao", "unidades de conservacao", "conservacao",
            "sobreposic", "area de protecao ambiental")),
    ("supressao", ("supress", "antropizada apos", "pos-2008", "apos 22 de julho",
                   "22 de julho de 2008", "desmat")),
    ("hidrografia", ("hidrograf", "nascente", "curso d", "drenagem")),
    ("cobertura", ("cobertura do solo", "vetorizac", "uso do solo", "remanescente", "vegetac")),
    ("documentos", ("apresentar", "documento", "certidao", "cpf", "rg do",
                    "licenca", "georreferenciamento", "inteiro teor")),
)


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
                # acumula: o staging real pode ter N linhas pendencias_rat (3× no
                # caso #11). A dedup por TEMA depois colapsa as repetições.
                src.pendencias.extend(val)
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


def _rat_has(rat: Optional[_Source], termos: tuple[str, ...]) -> bool:
    if rat is None:
        return False
    for pend in rat.pendencias:
        cat = _norm_text(pend.get("categoria") if isinstance(pend, dict) else pend)
        det = _norm_text(pend.get("detalhamento") if isinstance(pend, dict) else "")
        if any(t in cat or t in det for t in termos):
            return True
    return False


def _classificar_pendencia(pend: dict[str, Any]) -> Optional[str]:
    """Tema de uma pendência do RAT, casando categoria+detalhamento+recomendação.

    As categorias reais do órgão são genéricas ("Unidades de Conservação",
    "Inconsistência Adicional", "Documentos") — o conteúdo discriminante mora no
    detalhamento. Por isso o casamento NÃO pode ser só na categoria.

    Casa em categoria+detalhamento, NÃO na recomendação: o texto-padrão do órgão
    repete "área antropizada após 22 de julho de 2008" na recomendação de
    cobertura, o que falsearia o tema como supressão.
    """
    texto = " ".join(
        _norm_text(pend.get(k)) for k in ("categoria", "detalhamento")
    )
    texto = f" {texto} "
    for tema, termos in _TEMA_KEYWORDS:
        if any(t in texto for t in termos):
            return tema
    return None


def _extrai_uc(pend: dict[str, Any]) -> Optional[str]:
    """Tenta nomear a Unidade de Conservação no texto da pendência (best-effort).

    O RAT do caso #11 só diz "uma ou mais Unidades de Conservação" (sem nome) →
    devolve None e a linha fica genérica. Se um parecer nomear ("APA Pouso Alto"),
    o nome é capturado. Degrada com elegância — nunca quebra.
    """
    blob = " ".join(str(pend.get(k) or "") for k in ("detalhamento", "recomendacao", "categoria"))
    m = re.search(
        r"\b(APA|ARIE|FLONA|REBIO|PARNA|Parque|Reserva|Esta[çc][ãa]o Ecol[óo]gica)\s+"
        r"[A-ZÀ-Ý][\wÀ-ÿ'’\- ]{2,40}",
        blob,
    )
    return m.group(0).strip() if m else None


def _collect_areas(
    rows: list[Any],
) -> tuple[dict[str, dict[str, tuple[float, Any]]], dict[str, tuple[float, Any]]]:
    """Observações de área separadas por NÍVEL (caso #11, item 3).

    Retorna ``(por_matricula, por_imovel)``:
    - ``por_matricula[hint][doc_type] = (valor, row)`` — certidão/sigef/ccir/itr.
    - ``por_imovel[doc_type] = (valor, row)`` — car/rat (imóvel inteiro).

    Em duplicatas da MESMA fonte mantém o MAIOR valor: o staging real teve a área
    do RAT às vezes mal-parseada (separador de milhar → '1.0107113' ≈ 1 ha em vez
    de 1010,7113). Como a mesma fonte tem UMA área verdadeira, o maior recupera o
    valor correto. (Qualidade da Fase 2 é achado à parte.)
    """
    por_matricula: dict[str, dict[str, tuple[float, Any]]] = {}
    por_imovel: dict[str, tuple[float, Any]] = {}
    for row in rows:
        dt = (getattr(row, "source_doc_type", None) or "outro").lower()
        fn = getattr(row, "field_name", None)
        syns = _AREA_SYNONYMS.get(dt)
        if not syns or fn not in syns:
            continue
        val = _to_float_br(_row_value(row))
        if not val or val <= 0:
            continue
        if _AREA_LEVEL.get(dt) == "matricula":
            hint = getattr(row, "matricula_hint", None) or "?"
            bucket = por_matricula.setdefault(hint, {})
            prev = bucket.get(dt)
            if prev is None or val > prev[0]:
                bucket[dt] = (val, row)
        else:
            prev = por_imovel.get(dt)
            if prev is None or val > prev[0]:
                por_imovel[dt] = (val, row)
    return por_matricula, por_imovel


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

    # --- área — DOIS NÍVEIS (matrícula × imóvel) — Ficha 02 item 3 -------
    por_matricula, por_imovel = _collect_areas(rows)

    # nível matrícula: confronto entre fontes da MESMA matrícula
    for hint in sorted(por_matricula):
        fontes_mat = {lbl: v for lbl, (v, _) in por_matricula[hint].items()}
        if len(fontes_mat) < 2:
            continue  # 1 fonte só não confronta nada
        vals = list(fontes_mat.values())
        diff = max(vals) - min(vals)
        pct = Decimal(str(diff)) / Decimal(str(max(vals))) if max(vals) else Decimal(0)
        mat_rows = [r for (_v, r) in por_matricula[hint].values() if r is not None]
        if diff == 0:
            linhas.append(MatrixRow(
                f"area_matricula:{hint}", f"Área — matrícula {hint} (ha)", fontes_mat,
                MatrixSituacao.consistente.value,
                "Áreas conferem entre as fontes da matrícula.", _destino("consistente")))
            for r in mat_rows:
                status_updates.append((r, "consistente"))
        else:
            subtipo = "transcricao" if pct <= AREA_TOLERANCE_PCT else "fundo"
            linhas.append(MatrixRow(
                f"area_matricula:{hint}", f"Área — matrícula {hint} (ha)", fontes_mat,
                MatrixSituacao.divergente.value,
                f"conciliar área da matrícula {hint}: diferença de {_fmt_ha(diff)} ha entre as fontes",
                _destino("divergente", subtipo=subtipo), subtipo=subtipo))
            for r in mat_rows:
                status_updates.append((r, f"divergente_{subtipo}"))

    # soma das matrículas conhecidas (preferindo certidão/matrícula → sigef → …)
    area_by_matricula: dict[str, float] = {}
    soma_rows: list[Any] = []
    for hint, bucket in por_matricula.items():
        chosen = None
        for lbl in ("matricula", "sigef", "ccir", "itr"):
            if lbl in bucket:
                chosen = bucket[lbl]
                break
        if chosen is None:
            chosen = next(iter(bucket.values()))
        area_by_matricula[hint] = chosen[0]
        if chosen[1] is not None:
            soma_rows.append(chosen[1])
    soma_matriculas = round(sum(area_by_matricula.values()), 4) if area_by_matricula else None

    # nível imóvel: CAR/RAT × soma das matrículas
    imovel_areas = {lbl: v for lbl, (v, _) in por_imovel.items()}
    if soma_matriculas is not None and imovel_areas:
        fontes_area: dict[str, Any] = dict(area_by_matricula)
        fontes_area["soma_matriculas"] = soma_matriculas
        fontes_area.update(imovel_areas)
        imovel_rows = [r for (_v, r) in por_imovel.values() if r is not None]
        imovel_max = max(imovel_areas.values())
        maxlbl = max(imovel_areas, key=lambda k: imovel_areas[k])
        diff = abs(imovel_max - soma_matriculas)
        base = max(imovel_max, soma_matriculas)
        pct = Decimal(str(diff)) / Decimal(str(base)) if base else Decimal(0)

        if diff == 0:
            linhas.append(MatrixRow(
                "area_total", "Área total (ha)", fontes_area,
                MatrixSituacao.consistente.value, "Áreas conferem entre as fontes.",
                _destino("consistente")))
            for r in soma_rows + imovel_rows:
                status_updates.append((r, "consistente"))
        elif Decimal(str(imovel_max)) >= Decimal(str(soma_matriculas)) * MISSING_MATRICULA_FACTOR:
            # imóvel muito maior que a soma conhecida ⇒ matrícula faltante / vínculo
            # incompleto: ATENÇÃO pedindo vínculo, NÃO falsa divergência de fundo.
            linhas.append(MatrixRow(
                "area_total", "Área total (ha)", fontes_area,
                MatrixSituacao.atencao.value,
                (f"vincular matrículas: soma conhecida {_fmt_ha(soma_matriculas)} ha "
                 f"« {_fmt_ha(imovel_max)} ha do imóvel ({maxlbl.upper()}) — "
                 f"verificar matrícula(s) faltante(s)"),
                _destino("atencao")))
            for r in soma_rows:
                status_updates.append((r, "consistente"))
        else:
            subtipo = "transcricao" if pct <= AREA_TOLERANCE_PCT else "fundo"
            linhas.append(MatrixRow(
                "area_total", "Área total (ha)", fontes_area,
                MatrixSituacao.divergente.value,
                (f"ajustar/justificar diferença de {_fmt_ha(diff)} ha "
                 f"(soma matrículas {_fmt_ha(soma_matriculas)} vs {maxlbl.upper()} "
                 f"{_fmt_ha(imovel_max)})"),
                _destino("divergente", subtipo=subtipo), subtipo=subtipo))
            novo = f"divergente_{subtipo}"
            for r in soma_rows:
                status_updates.append((r, "consistente"))
            for r in imovel_rows:
                status_updates.append((r, novo))

    # --- denominacao_imovel ---------------------------------------------
    denom_rows: list[Any] = []
    denom_fontes: dict[str, Any] = {}
    for key, src in sources.items():
        val = _get(src, *_DENOM_SYNONYMS)
        if val not in (None, ""):
            denom_fontes[key] = val
            r = _row_of(src, *_DENOM_SYNONYMS)
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
        val = _get(src, *_INCRA_SYNONYMS)
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

    # --- sigef_georreferenciamento (valida presença REAL de código+status) ---
    tem_contexto_imovel = bool(matricula_keys or car or ccir or itr or sigef or por_matricula)
    sigef_codigo = _get(sigef, "codigo_certificacao") if sigef else None
    sigef_status = _norm_text(_get(sigef, "status_certificacao")) if sigef else ""
    sigef_area = _to_float_br(_get(sigef, "area_georreferenciada_ha")) if sigef else None
    cert_real = bool(
        sigef and sigef_codigo
        and sigef_status in ("ativo", "ativa", "certificado", "certificada")
    )
    rat_geo_pendencia = _rat_has(rat, ("geo", "georref", "sigef", "vetoriz", "perimetro", "vertice"))
    if not tem_contexto_imovel:
        pass
    elif not cert_real:
        fontes_sig = {"sigef": (sigef_codigo or (sigef_area if sigef_area else "ausente")),
                      "rat": "pendência geo" if rat_geo_pendencia else "—"}
        linhas.append(MatrixRow(
            "sigef_georreferenciamento", "Georreferenciamento (SIGEF)", fontes_sig,
            MatrixSituacao.critico.value, "verificar DCR/SIGEF/SNCR (certificação ausente/pendente)",
            _destino("critico")))
    elif rat_geo_pendencia:
        # certificação existe (código+status reais) mas o órgão pede apresentação
        linhas.append(MatrixRow(
            "sigef_georreferenciamento", "Georreferenciamento (SIGEF)",
            {"sigef": sigef_codigo, "rat": "órgão solicita apresentação do SIGEF"},
            MatrixSituacao.atencao.value,
            "certificação existe (código presente); o órgão solicita sua apresentação no CAR",
            _destino("atencao")))
    else:
        linhas.append(MatrixRow(
            "sigef_georreferenciamento", "Georreferenciamento (SIGEF)",
            {"sigef": sigef_codigo, "status": sigef_status},
            MatrixSituacao.consistente.value, "Certificação presente e ativa.", _destino("consistente")))

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

    # --- pendências do RAT → linhas técnicas + acesso + documentos -------
    # Ficha 02 item 4 (caso #11): TEMA casado por categoria+detalhamento+
    # recomendação; dedup por tema (colapsa as repetições do staging 3×).
    if rat is not None and rat.pendencias:
        temas_vistos: set[str] = set()
        docs_solicitados: list[str] = []
        acesso_visto = False
        for pend in rat.pendencias:
            if not isinstance(pend, dict):
                continue
            tema = _classificar_pendencia(pend)
            if tema is None:
                continue
            if tema == "acesso":
                acesso_visto = True
                continue
            if tema == "documentos":
                det = (pend.get("detalhamento") or pend.get("categoria") or "").strip()
                if det and det not in docs_solicitados:
                    docs_solicitados.append(det)
                continue
            if tema in temas_vistos:
                continue  # 1 linha por tema
            temas_vistos.add(tema)
            label = _TEMA_LABEL[tema]
            if tema == "uc":
                uc_nome = _extrai_uc(pend)
                if uc_nome:
                    label = f"{label}: {uc_nome}"
            acao = pend.get("recomendacao") or "confronto espacial pendente (geo/Etapa 4)"
            linhas.append(MatrixRow(
                item=f"tecnica:{tema}",
                label=f"[técnica] {label}",
                fontes={"rat": pend.get("detalhamento") or pend.get("categoria") or label},
                situacao=MatrixSituacao.critico.value,
                acao_recomendada=str(acao),
                destino=_destino("critico"),
                profundidade="tecnica",
            ))
        if acesso_visto:
            linhas.append(MatrixRow(
                "acesso_imovel", "Acesso ao imóvel", {"rat": "descrição insuficiente"},
                MatrixSituacao.atencao.value, "padronizar acesso com coordenadas",
                _destino("atencao")))
        if docs_solicitados:
            linhas.append(MatrixRow(
                "documentos_solicitados", "Documentos solicitados pelo órgão",
                {"rat": docs_solicitados},
                MatrixSituacao.atencao.value,
                "providenciar os documentos exigidos no parecer (RAT)",
                _destino("atencao")))

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
