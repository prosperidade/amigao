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

# Sanidade de área (caso #12, item A): nenhuma fazenda do domínio passa de 100k ha.
# Área de matrícula acima disso é quase certamente erro de parse (vírgula decimal
# perdida → 349,9022 vira 3499022) — não entra no confronto/soma; vira linha de
# revisão. Metade de Goiás (~3,5M ha) era o sintoma.
AREA_SANITY_MAX_HA = Decimal("100000")

# Artefato de parse por separador de MILHAR perdido (validação Isis 16/06): o RAT
# "1.010,7113 ha" foi emitido pelo extrator (LLM) como o float 1.0107113 — ~1000×
# menor (o ponto de milhar virou decimal). Quando a área do IMÓVEL (CAR/RAT) é
# ordens de grandeza MENOR que a soma das matrículas conhecidas, é quase certo
# erro de parse, não divergência real: a área do imóvel jamais seria 1000× menor
# que a soma das suas próprias matrículas. Vai para revisão, NÃO vira passivo.
# Fator conservador (≥100×) para não pegar sobreposição/duplicação legítima.
AREA_PARSE_ARTIFACT_RATIO = Decimal("100")


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
    # Rastreabilidade (validação 06/06): por linha, QUAIS fontes participaram —
    # {fonte, tipo (documento/rat), source_doc_type, document_id, campo, valor}.
    # ADITIVO: `fontes` (dict fonte→valor) permanece para os renderers/testes
    # antigos; a UI nova lê `fontes_detalhe`.
    fontes_detalhe: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "item": self.item,
            "label": self.label,
            "fontes": self.fontes,
            "fontes_detalhe": self.fontes_detalhe,
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


def _normalize_number_str(s: str) -> str:
    """Resolve separadores decimal/milhar pelo ÚLTIMO separador presente.

    Regra robusta (caso #12, item A): quando '.' e ',' coexistem, o separador
    mais à direita é o decimal e o outro é milhar:
      '1.010,7113' → '1010.7113'   (vírgula decimal, ponto milhar)
      '3.502.445,851' → '3502445.851'
      '1,234.56' → '1234.56'       (ponto decimal, vírgula milhar)
    Só vírgula → decimal ('349,9022' → '349.9022'). Só ponto (ou nenhum) →
    mantém ('660.6561' fica 660.6561; NÃO inventamos milhar onde não há vírgula).
    """
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")
    if last_comma != -1 and last_dot != -1:
        if last_comma > last_dot:  # vírgula decimal, ponto milhar
            return s.replace(".", "").replace(",", ".")
        return s.replace(",", "")  # ponto decimal, vírgula milhar
    if last_comma != -1:  # só vírgula = decimal
        return s.replace(",", ".")
    return s  # só ponto, ou inteiro puro


def _to_float_br(value: Any) -> Optional[float]:
    """Converte número PT-BR ('1.010,7113', '660,6561') ou float para float.

    Defesa do caso #12 (item A): NUNCA aceitar dict/lista cru. Um dict de extração
    `{'value': 349.9022, 'confidence': 'high'}` que vazasse como string viraria
    '349.9022,' após limpeza, e a vírgula (separador do dict!) disparava o ramo
    PT-BR → '3499022' (a "fazenda de 3,5 milhões de ha"). Aqui desembrulhamos o
    dict para o escalar e rejeitamos coleções.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        return _to_float_br(value.get("value")) if "value" in value else None
    if isinstance(value, (list, tuple, set)):
        return None
    s = str(value).strip().lower().replace("hectares", "").replace("ha", "").strip()
    s = re.sub(r"[^0-9.,-]", "", s)
    if not s or s in ("-", ".", ","):
        return None
    s = _normalize_number_str(s)
    try:
        return float(s)
    except ValueError:
        return None


def _is_m2(value: Any, unidade: Any) -> bool:
    """True se a área está em m² (unidade marcada ou sufixo no valor cru)."""
    u = _norm_text(unidade)
    if u in ("m2", "m²", "metros quadrados", "metro quadrado"):
        return True
    raw = _norm_text(value)
    return bool(re.search(r"\bm2\b|m²", raw))


def parse_area_ha(value: Any, unidade: Any = None) -> Optional[float]:
    """Função ÚNICA de parse de área → float em hectares (caso #12, item A).

    Aceita as variações REAIS do staging: vírgula decimal ('349,9022'), ponto de
    milhar ('1.010,7113'), ponto decimal ('660.6561') e sufixo de unidade
    ('3.502.445,851 m²' → 350,2445851 ha quando m² está marcado). Não-numérico,
    dict ou lista → None (não polui confronto/soma).
    """
    val = _to_float_br(value)
    if val is None:
        return None
    if _is_m2(value, unidade):
        val = val / 10000.0
    return val


# Faixa de ordem de grandeza plausível para área de imóvel/matrícula do domínio
# (validação Isis 16/06): de 0,1 ha (sítio pequeno) a 100.000 ha. Fora disso é
# quase certo erro de parse — o chamador deve REBAIXAR confiança e NÃO gravar
# como fato (vai pra revisão). O confronto relativo (área « soma das matrículas)
# pega o caso do separador de milhar perdido que cai DENTRO desta faixa.
AREA_PLAUSIBLE_MIN_HA = 0.1
AREA_PLAUSIBLE_MAX_HA = float(AREA_SANITY_MAX_HA)


def is_area_plausible(ha: Optional[float]) -> bool:
    """True se a área (ha) está na ordem de grandeza plausível do domínio."""
    return ha is not None and AREA_PLAUSIBLE_MIN_HA <= ha <= AREA_PLAUSIBLE_MAX_HA


# Anotações que grudam no número da matrícula e NÃO fazem parte dele.
#   '4655 (2 de 3)'  '(parte 2 de 3)'  → fatia de georreferenciamento
#   'R-01' 'AV-3' 'R.05'              → ato registral (registro/averbação)
_HINT_ANNOT_RE = re.compile(
    r"\(\s*\d+\s*de\s*\d+\s*\)|\bav[-.\s]?\d+\b|\br[-.\s]?\d+\b",
    re.IGNORECASE,
)
# Hints que não identificam matrícula nenhuma — não viram coluna de confronto.
_HINT_JUNK = {"", "?", "-", "--", "none", "null", "n/a", "na", "s/n", "sn"}


def _clean_matricula_hint(raw: Any) -> Optional[str]:
    """Extrai o número da matrícula de um `matricula_hint` sujo (caso #12, item B).

    Trata os shapes REAIS do staging do #12:
      "4.655" → "4655"            (ponto de milhar)
      "MATR. 2.923 R-01" → "2923" (prefixo + ato registral)
      "4655 (2 de 3)" → "4655"    (fatia de georref)
      "{'value': '4655', ...}" → "4655"  (dict serializado que vazou)
      "?" / "" / None → None      (sem vínculo — NÃO cria confronto)
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return _clean_matricula_hint(raw.get("value"))
    if isinstance(raw, (list, tuple, set)):
        return None
    s = str(raw).strip()
    if s.lower() in _HINT_JUNK:
        return None
    s = _HINT_ANNOT_RE.sub(" ", s)
    # número com pontos de milhar OU sequência de ≥2 dígitos (matrículas não têm 1 dígito)
    m = re.search(r"\d{1,3}(?:\.\d{3})+|\d{2,}", s)
    if not m:
        return None
    num = m.group(0).replace(".", "")
    return num or None


# Prefixos de TÍTULO DE DOCUMENTO que vazam como "denominação" (caso #12, item C).
# Ex.: a "Certidão de Embargo" (um doc, não o nome do imóvel) caía na denominação
# do SIGEF. Denominação real começa com "Fazenda/Sítio/Gleba/Lote/Chácara…".
_DOC_TITLE_PREFIXES: tuple[str, ...] = (
    "certidao", "recibo", "relatorio", "parecer", "laudo", "requerimento",
    "auto de", "notificacao", "embargo", "protocolo", "memorial", "anexo",
    "declaracao", "comprovante",
)


def _is_doc_title(value: Any) -> bool:
    """True se o valor parece um título de documento, não uma denominação."""
    s = _norm_text(value)
    return any(s.startswith(p) for p in _DOC_TITLE_PREFIXES)


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
    document_id: Optional[int] = None  # 1º document_id visto (rastreabilidade)


def _group_sources(rows: list[Any]) -> dict[str, _Source]:
    sources: dict[str, _Source] = {}
    for row in rows:
        dt = (getattr(row, "source_doc_type", None) or "outro").lower()
        hint = _clean_matricula_hint(getattr(row, "matricula_hint", None))
        fname = getattr(row, "field_name", None)
        val = _row_value(row)

        key = (f"matricula:{hint}" if hint else "matricula") if dt == "matricula" else dt
        src = sources.setdefault(key, _Source(key=key, doc_type=dt))
        if src.document_id is None:
            src.document_id = getattr(row, "document_id", None)

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

    Caso #12 item D: a CATEGORIA "Documentos" tem precedência. O detalhamento de
    um pedido de documentos lista "Licença Ambiental e Autorização de Desmatamento"
    — o termo "desmat" casava `supressao` (que vem antes na ordem), criando uma
    falsa linha "Supressão pós-2008" com a recomendação de acesso da própria
    pendência. Respeitar a categoria impede o cruzamento de conteúdos.
    """
    categoria = _norm_text(pend.get("categoria"))
    if categoria.startswith("documento"):
        # Acesso pode vir rotulado como "Documentos" (caso #11): se o DETALHAMENTO
        # fala de acesso, é acesso. Caso contrário é pedido de documentos — e o
        # detalhamento (lista com "Autorização de Desmatamento") NÃO pode virar
        # `supressao` (caso #12 item D).
        det = _norm_text(pend.get("detalhamento"))
        if any(t in det for t in ("acesso", "via de acesso", "servidao")):
            return "acesso"
        return "documentos"
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


@dataclass
class _AreaObservations:
    por_matricula: dict[str, dict[str, tuple[float, Any]]]  # [hint][doc_type]=(val,row)
    por_imovel: dict[str, tuple[float, Any]]                # [doc_type]=(val,row)
    sem_vinculo: list[tuple[str, float, Any]]              # (doc_type, val, row) sem hint
    implausiveis: list[tuple[str, str, float, Any]]        # (hint|'-', doc_type, val, row)


def _row_unidade(row: Any) -> Any:
    fv = getattr(row, "field_value", None)
    return fv.get("unidade") if isinstance(fv, dict) else None


def _collect_areas(rows: list[Any]) -> _AreaObservations:
    """Observações de área separadas por NÍVEL (caso #11/#12, item 3 + A/B).

    - ``por_matricula[hint][doc_type] = (valor, row)`` — certidão/sigef/ccir/itr
      COM `matricula_hint` limpo (vínculo conhecido).
    - ``por_imovel[doc_type] = (valor, row)`` — car/rat (imóvel inteiro).
    - ``sem_vinculo`` — área de nível matrícula SEM hint utilizável (caso #12 item
      B: ITR vinha sem `numero_matricula`). NÃO confronta — vira linha de atenção.
    - ``implausiveis`` — área > 100.000 ha (caso #12 item A): erro de parse provável,
      fora do confronto/soma, marcada para revisão.

    Em duplicatas da MESMA fonte/hint mantém o MAIOR valor: o staging real teve a
    área do RAT às vezes mal-parseada (separador de milhar → '1.0107113' ≈ 1 ha em
    vez de 1010,7113). Como a mesma fonte tem UMA área verdadeira, o maior recupera
    o valor correto. (Qualidade da Fase 2 é achado à parte.)
    """
    por_matricula: dict[str, dict[str, tuple[float, Any]]] = {}
    por_imovel: dict[str, tuple[float, Any]] = {}
    sem_vinculo: list[tuple[str, float, Any]] = []
    implausiveis: list[tuple[str, str, float, Any]] = []
    sanity_max = float(AREA_SANITY_MAX_HA)
    for row in rows:
        dt = (getattr(row, "source_doc_type", None) or "outro").lower()
        fn = getattr(row, "field_name", None)
        syns = _AREA_SYNONYMS.get(dt)
        if not syns or fn not in syns:
            continue
        val = parse_area_ha(_row_value(row), _row_unidade(row))
        if not val or val <= 0:
            continue
        if val > sanity_max:
            hint = _clean_matricula_hint(getattr(row, "matricula_hint", None)) or "-"
            implausiveis.append((hint, dt, val, row))
            continue
        if _AREA_LEVEL.get(dt) == "matricula":
            hint = _clean_matricula_hint(getattr(row, "matricula_hint", None))
            if hint is None:
                sem_vinculo.append((dt, val, row))
                continue
            bucket = por_matricula.setdefault(hint, {})
            prev = bucket.get(dt)
            if prev is None or val > prev[0]:
                bucket[dt] = (val, row)
        else:
            prev = por_imovel.get(dt)
            if prev is None or val > prev[0]:
                por_imovel[dt] = (val, row)
    return _AreaObservations(por_matricula, por_imovel, sem_vinculo, implausiveis)


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
    areas = _collect_areas(rows)
    por_matricula, por_imovel = areas.por_matricula, areas.por_imovel

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
    # Artefato de parse (Isis 16/06): área de imóvel ordens de grandeza MENOR que a
    # soma das matrículas = separador de milhar perdido no extrator (1.010,7113 →
    # 1.0107113). Tira do confronto e manda pra revisão — não vira falso passivo.
    artefato_parse_imovel: dict[str, float] = {}
    if soma_matriculas and soma_matriculas > 0:
        for lbl, v in list(imovel_areas.items()):
            if v > 0 and Decimal(str(soma_matriculas)) / Decimal(str(v)) >= AREA_PARSE_ARTIFACT_RATIO:
                artefato_parse_imovel[lbl] = v
                del imovel_areas[lbl]
    if soma_matriculas is not None and imovel_areas:
        fontes_area: dict[str, Any] = dict(area_by_matricula)
        fontes_area["soma_matriculas"] = soma_matriculas
        fontes_area.update(imovel_areas)
        imovel_rows = [r for lbl, (_v, r) in por_imovel.items()
                       if r is not None and lbl in imovel_areas]
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

    # --- área SEM vínculo de matrícula (caso #12 item B) ----------------
    # Campos de nível matrícula sem `matricula_hint` (ITR vinha sem nº): NÃO
    # confrontar entre si (escalas diferentes não são divergência). Uma linha de
    # atenção lista os valores órfãos pedindo o vínculo — sem comparar valores.
    if areas.sem_vinculo:
        fontes_orf: dict[str, Any] = {}
        for dt, val, _r in areas.sem_vinculo:
            fontes_orf.setdefault(dt, []).append(val)
        linhas.append(MatrixRow(
            "area_sem_vinculo", "Áreas sem vínculo de matrícula (ha)", fontes_orf,
            MatrixSituacao.atencao.value,
            "vincular cada área à sua matrícula (campos sem nº de matrícula — "
            "não confrontados entre si)",
            _destino("atencao")))

    # --- área IMPLAUSÍVEL — revisar extração (caso #12 item A + Isis 16/06) ----
    # Dois sintomas do MESMO problema (separador mal lido na origem):
    #  - > 100.000 ha: vírgula decimal perdida (349,9022 → 3499022).
    #  - imóvel « soma das matrículas (≥100×): ponto de milhar virou decimal
    #    (1.010,7113 → 1.0107113). Fora do confronto/soma; vira revisão, não passivo.
    if areas.implausiveis or artefato_parse_imovel:
        fontes_imp = {
            f"{dt}{(':' + hint) if hint != '-' else ''}": val
            for (hint, dt, val, _r) in areas.implausiveis
        }
        for lbl, val in artefato_parse_imovel.items():
            fontes_imp[lbl] = val
        linhas.append(MatrixRow(
            "area_revisao", "Área implausível — revisar extração (ha)", fontes_imp,
            MatrixSituacao.atencao.value,
            "revisar área extraída (fora de escala — provável erro de separador "
            "decimal/milhar na origem; ex.: '1.010,7113' lido como 1,0107113)",
            _destino("atencao")))

    # --- denominacao_imovel ---------------------------------------------
    denom_rows: list[Any] = []
    denom_fontes: dict[str, Any] = {}
    for key, src in sources.items():
        val = _get(src, *_DENOM_SYNONYMS)
        # Caso #12 item C: descartar título de documento ("Certidão de Embargo")
        # que vazou como denominação — não é o nome do imóvel.
        if val in (None, "") or _is_doc_title(val):
            continue
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
        # Caso #12 item B: normalizar o nº da matrícula nos DOIS lados ("4.698" ↔
        # "4698") para o confronto CAR×staging não acusar falsa divergência.
        car_mats = {_clean_matricula_hint(m.get("numero") if isinstance(m, dict) else m)
                    for m in car.matricula_listadas}
        car_mats = {m for m in car_mats if m}
        staging_mats = {k.split(":", 1)[1] for k in matricula_keys if ":" in k}

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

    # Rastreabilidade (06/06): por linha, QUAIS fontes participaram (doc + valor).
    rat_protocolo = _get(rat, "protocolo") if rat else None
    for r in linhas:
        r.fontes_detalhe = _fontes_detalhe(r, sources, rat_protocolo)

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


def _fontes_detalhe(
    row: MatrixRow, sources: dict[str, _Source], rat_protocolo: Any,
) -> list[dict[str, Any]]:
    """Expõe, por linha, as fontes que participaram do confronto (determinístico).

    Para cada chave em ``row.fontes`` que é uma fonte real (matricula:xxxx, car,
    ccir, itr, sigef, rat), devolve {fonte, tipo, source_doc_type, document_id,
    valor}. Chaves derivadas (soma_matriculas) saem como tipo 'matriz'. Linhas
    técnicas (item 'tecnica:') referenciam o protocolo do RAT.
    """
    out: list[dict[str, Any]] = []
    for fonte_key, valor in (row.fontes or {}).items():
        src = sources.get(fonte_key)
        if src is not None:
            entry: dict[str, Any] = {
                "fonte": fonte_key,
                "tipo": "rat" if src.doc_type == "rat" else "documento",
                "source_doc_type": src.doc_type,
                "valor": valor,
            }
            if src.document_id is not None:
                entry["document_id"] = src.document_id
            if src.doc_type == "rat" and rat_protocolo:
                entry["protocolo"] = rat_protocolo
            out.append(entry)
        else:
            # chave derivada (soma_matriculas) ou rótulo — sem doc específico
            out.append({"fonte": fonte_key, "tipo": "matriz", "valor": valor})
    # Linha técnica sem fontes-doc explícitas → referencia o RAT de origem.
    if row.item.startswith("tecnica:") and not any(e.get("source_doc_type") == "rat" for e in out):
        rat_entry: dict[str, Any] = {"fonte": "rat", "tipo": "rat", "source_doc_type": "rat"}
        if rat_protocolo:
            rat_entry["protocolo"] = rat_protocolo
        rat_src = sources.get("rat")
        if rat_src is not None and rat_src.document_id is not None:
            rat_entry["document_id"] = rat_src.document_id
        out.append(rat_entry)
    return out
