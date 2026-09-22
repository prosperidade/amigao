"""Identidade canônica de fonte normativa — função ÚNICA (ADR-075 §5).

"Tipo + órgão + número + ano — nunca string crua." O corpus grafa a mesma
norma de vários jeitos ("Res. CONAMA 369/2006", "Resolução CONAMA 369/2006",
"RESOLUÇÃO CONAMA Nº 369, DE 28 DE MARÇO DE 2006", título de aba "L6938").
Comparar string deixa passar duplicata; esta função reduz a norma ao que ela é.

A chave tem cinco partes: ``tipo|ente|orgao|numero|ano``.

- ``ente`` é ``br`` (União) ou a UF em minúsculas. Lei e decreto são numerados
  por ente — Decreto 9.710/2020 de Goiás não é decreto federal (Parecer 84).
- ``orgao`` só entra para as espécies numeradas por órgão (IN, resolução,
  portaria, parecer…). Para lei e decreto fica vazio: quem numera é o ente.

Identidade que não fecha (sem ano, sem número, órgão que o texto não diz) sai
``determinada=False``. Não se adivinha: fica ``nao_determinado`` até a revisão
humana (ADR-075 §5).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Espécie canônica ← grafias. Ordem importa: a composta antes da simples.
_TIPOS: tuple[tuple[str, str], ...] = (
    (r"lei\s+complementar|lcp?", "lei_complementar"),
    (r"lei\s+delegada", "lei_delegada"),
    (r"decreto[\s-]+lei|del", "decreto_lei"),
    (r"decreto\s+legislativo", "decreto_legislativo"),
    (r"emenda\s+constitucional", "emenda_constitucional"),
    (r"medida\s+provis[oó]ria|mpv?", "medida_provisoria"),
    (r"orienta[cç][aã]o\s+jur[ií]dica\s+normativa|ojn", "ojn"),
    (r"orienta[cç][aã]o\s+normativa", "orientacao_normativa"),
    (r"instru[cç][aã]o\s+normativa(?:\s+conjunta)?|in", "in"),
    (r"resolu[cç][aã]o(?:\s+conjunta)?|res\.?", "resolucao"),
    (r"portaria(?:\s+conjunta)?", "portaria"),
    (r"delibera[cç][aã]o", "deliberacao"),
    (r"nota\s+t[eé]cnica", "nota_tecnica"),
    (r"parecer", "parecer"),
    (r"decreto", "decreto"),
    (r"lei", "lei"),
)

# Espécies numeradas pelo ÓRGÃO — sem órgão a identidade não fecha.
TIPOS_POR_ORGAO = frozenset({
    "in", "resolucao", "portaria", "deliberacao", "nota_tecnica", "parecer",
    "ojn", "orientacao_normativa",
})

ROTULO_TIPO = {
    "lei": "Lei", "lei_complementar": "LC", "lei_delegada": "Lei Delegada",
    "decreto_lei": "Decreto-Lei", "decreto_legislativo": "Decreto Legislativo",
    "emenda_constitucional": "EC", "medida_provisoria": "MPV", "ojn": "OJN",
    "orientacao_normativa": "Orientação Normativa", "in": "IN",
    "resolucao": "Resolução", "portaria": "Portaria", "deliberacao": "Deliberação",
    "nota_tecnica": "Nota Técnica", "parecer": "Parecer", "decreto": "Decreto",
    "constituicao": "Constituição",
}

UFS = frozenset(
    ["ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms", "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc", "se", "sp", "to"]
)

# Palavras que aparecem entre a espécie e o "Nº" e não são órgão.
_NAO_ORGAO = frozenset({
    "estadual", "federal", "municipal", "conjunta", "normativa", "do", "da", "de",
    "dos", "das", "e", "n", "no", "nº", "numero", "ato", "rpr", "r",
})

# Grafias de órgão que são o mesmo órgão. Chave: sigla reduzida (só [a-z0-9]).
_SINONIMOS_ORGAO = {
    "semadgo": "semad",
    "cmnbacen": "cmn",
    "pfeibama": "pfe-ibama",
    "ibamapfe": "pfe-ibama",
    "semamt": "sema",
    "semaac": "sema",
}


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _tipo_canonico(bruto: str) -> str | None:
    t = re.sub(r"[\s\-]+", " ", _sem_acento(bruto).lower().replace(".", "")).strip()
    for padrao, nome in _TIPOS:
        if re.fullmatch(_sem_acento(padrao).replace("[\\s-]+", "[\\s]+"), t, flags=re.I):
            return nome
    return None


def normalizar_numero(bruto: str | None) -> str:
    """'2.203' e '2203' são a mesma norma; '02' e '2' também. Sufixo '-A' fica."""
    if not bruto:
        return ""
    s = bruto.strip().upper().replace(".", "").replace(" ", "")
    m = re.fullmatch(r"0*(\d+)(-?[A-Z])?", s)
    if not m:
        return s
    return (m.group(1) or "0") + (("-" + m.group(2).lstrip("-")) if m.group(2) else "")


def normalizar_orgao(bruto: str | None, ente: str = "") -> str:
    if not bruto:
        return ""
    s = re.sub(r"[^a-z0-9]", "", _sem_acento(bruto).lower())
    if ente and ente != "br" and s.endswith(ente) and len(s) > len(ente) + 1:
        s = s[: -len(ente)]
    return _SINONIMOS_ORGAO.get(s, s)


def _ano(bruto: str | None) -> int | None:
    if not bruto:
        return None
    b = bruto.strip()
    if len(b) == 2:
        n = int(b)
        return (1900 if n > 30 else 2000) + n
    if len(b) == 4 and b[:2] in ("19", "20"):
        return int(b)
    return None


@dataclass(frozen=True)
class IdentidadeNorma:
    tipo: str
    ente: str                   # "br" ou UF minúscula
    orgao: str = ""
    numero: str = ""
    ano: int | None = None

    @property
    def esfera(self) -> str:
        return "federal" if self.ente == "br" else "estadual"

    @property
    def uf(self) -> str | None:
        return None if self.ente == "br" else self.ente.upper()

    @property
    def determinada(self) -> bool:
        if self.tipo == "constituicao":
            return self.ano is not None
        if self.tipo not in ROTULO_TIPO:
            return bool(self.numero)  # documento não normativo: slug estável
        if not self.numero or self.ano is None:
            return False
        return not (self.tipo in TIPOS_POR_ORGAO and not self.orgao)

    @property
    def chave(self) -> str:
        return f"{self.tipo}|{self.ente}|{self.orgao}|{self.numero}|{self.ano or ''}"

    @property
    def rotulo(self) -> str:
        """Nome legível: 'Decreto 6.514/2008', 'Lei GO 18.104/2013', 'IN SEMAD/GO 3/2025'."""
        if self.tipo == "constituicao":
            return "Constituição Federal" if self.ente == "br" else f"Constituição {self.ente.upper()}"
        if self.tipo not in ROTULO_TIPO:
            return self.numero
        num = self.numero
        base = re.match(r"(\d+)(.*)", num)
        if base and len(base.group(1)) > 3:
            num = f"{int(base.group(1)):,}".replace(",", ".") + base.group(2)
        partes = [ROTULO_TIPO[self.tipo]]
        if self.orgao:
            org = self.orgao.upper()
            partes.append(org if self.ente == "br" else f"{org}/{self.ente.upper()}")
        elif self.ente != "br":
            partes.append(self.ente.upper())
        ano = f"/{self.ano}" if self.ano else "/????"
        return " ".join(partes) + f" {num or '?'}{ano}"


# ---------------------------------------------------------------------------
# Leitura de cabeçalho formal ("DECRETO Nº 1.473, DE 12 DE MARÇO DE 2025")
# ---------------------------------------------------------------------------

_ESPECIES = (
    r"LEI\s+COMPLEMENTAR|LEI\s+DELEGADA|LEI|DECRETO[-\s]+LEI|DECRETO\s+LEGISLATIVO|DECRETO|"
    r"INSTRU[CÇ][AÃ]O\s+NORMATIVA(?:\s+CONJUNTA)?|RESOLU[CÇ][AÃ]O(?:\s+CONJUNTA)?|"
    r"PORTARIA(?:\s+CONJUNTA)?|DELIBERA[CÇ][AÃ]O|NOTA\s+T[EÉ]CNICA|PARECER|"
    r"EMENDA\s+CONSTITUCIONAL|ORIENTA[CÇ][AÃ]O\s+JUR[IÍ]DICA\s+NORMATIVA|"
    r"ORIENTA[CÇ][AÃ]O\s+NORMATIVA|MEDIDA\s+PROVIS[OÓ]RIA"
)

RE_CABECALHO = re.compile(
    rf"(?P<tipo>{_ESPECIES})"
    r"(?P<meio>(?:\s+[A-Za-zÀ-ú][\wÀ-ú/\.\-]*){0,5}?)"
    r"\s+N\s*[º°oO\.]*\s*[:\.]?\s*(?P<num>\d[\d\.]*(?:\s*-\s*[A-Z](?![a-z]))?)"
    r"(?:\s*[/\-]\s*(?P<ano1>(?:19|20)\d{2}|\d{2})(?!\d))?"
    r"(?:[^\n]{0,45}?(?:\bDE\s+(?:\d{1,2}[/\.]\d{1,2}[/\.])?|"
    r"\b(?:JANEIRO|FEVEREIRO|MAR[CÇ]O|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|"
    r"NOVEMBRO|DEZEMBRO)\s+)(?P<ano2>(?:19|20)\d{2})(?!\d))?",
    re.IGNORECASE,
)

RE_CONSTITUICAO = re.compile(
    r"^\s*CONSTITUI[CÇ][AÃ]O\s+(?:DO\s+ESTADO\s+D[EOA]\s+(?P<estado>[A-ZÀ-Ú ]+)|"
    r"DA\s+REP[UÚ]BLICA\s+FEDERATIVA\s+DO\s+BRASIL|FEDERAL)\s*$",
    re.IGNORECASE | re.M,
)

_ESTADOS = {
    "acre": "ac", "goias": "go", "mato grosso": "mt", "mato grosso do sul": "ms",
}

# Título de aba do Planalto: "L6938", "Lcp 140", "D6514", "Del1413".
RE_TITULO_PLANALTO = re.compile(r"^\s*(?P<tipo>Lcp|L|D|Del|Mpv)\s?(?P<num>\d+)\s*$", re.I)
_TIPO_PLANALTO = {"l": "lei", "lcp": "lei_complementar", "d": "decreto",
                  "del": "decreto_lei", "mpv": "medida_provisoria"}

# Título de aba do leis.org: "Lei Ordinária 9523 2011 de Mato Grosso MT".
RE_TITULO_LEISORG = re.compile(
    r"^\s*(?P<tipo>Lei Ordin[aá]ria|Lei Complementar|Decreto|Portaria|Resolu[cç][aã]o|"
    r"Instru[cç][aã]o Normativa)\s+(?P<num>\d[\d\.]*)\s+(?P<ano>(?:19|20)\d{2})\s+de\s+",
    re.I,
)

# Cabeçalho em tabela da SEFAZ-MT: "Ato: Decreto Número/Complemento … 1031/2017".
RE_ATO_SEFAZ = re.compile(
    r"Ato:\s*(?P<tipo>Lei Complementar|Lei|Decreto|Portaria|Instru[cç][aã]o Normativa|Resolu[cç][aã]o)"
    r"\s+N[úu]mero/Complemento.{0,200}?(?P<num>\d[\d\.]*)/(?P<ano>(?:19|20)\d{2})",
    re.I | re.S,
)

# Órgão como sufixo do número: "Nº 131/2018/GS/SINFRA", "n° 155/GSF/SEFAZ/2018".
RE_SUFIXO_NUMERO = re.compile(
    r"N\s*[º°oO\.]*\s*[:\.]?\s*\d[\d\.]*(?P<suf>(?:\s*[/\-]\s*[A-Za-z0-9]+)+)", re.I
)
_SUFIXO_NAO_ORGAO = frozenset({"gs", "gab", "gsf", "gbse", "gp", "dg", "gbses", "uniscor"})


def _orgao_do_sufixo(linha: str, ente: str) -> tuple[str, int | None]:
    m = RE_SUFIXO_NUMERO.search(linha)
    if not m:
        return "", None
    partes = [p.strip() for p in re.split(r"[/\-]", m.group("suf")) if p.strip()]
    ano = next((int(p) for p in partes if re.fullmatch(r"(?:19|20)\d{2}", p)), None)
    siglas = [
        p for p in partes
        if re.fullmatch(r"[A-Za-z]{2,}", p) and p.lower() not in _SUFIXO_NAO_ORGAO
        and p.lower() != ente and p.lower() not in UFS
    ]
    return (normalizar_orgao(siglas[-1], ente) if siglas else ""), ano


def orgao_do_meio(meio: str, ente: str) -> str:
    palavras = [
        p for p in re.split(r"\s+", meio.strip())
        if p and _sem_acento(p).lower().strip(".") not in _NAO_ORGAO
    ]
    # Órgão é sigla (maiúsculas) ou composição "SEMA/SEFAZ". Palavra comum em
    # caixa baixa ("que", "sobre") não é órgão: é texto corrido.
    siglas = [p for p in palavras if re.fullmatch(r"[A-ZÀ-Ú0-9][A-ZÀ-Ú0-9/\.\-]*", p)]
    if not siglas:
        return ""
    return normalizar_orgao("".join(siglas), ente)


def identidade_de_cabecalho(
    linha: str, *, ente_padrao: str, orgao_contexto: str = ""
) -> IdentidadeNorma | None:
    """Lê espécie, órgão, número e ano de uma linha de cabeçalho ou título.

    ``ente_padrao``: 'br' ou a UF — quem numerou, quando a linha não diz.
    ``orgao_contexto``: órgão achado no contexto de abertura (usado só para as
    espécies numeradas por órgão, e só se a linha não trouxer um).
    """
    mc = RE_CONSTITUICAO.match(linha)
    if mc:
        est = mc.group("estado")
        ente = _ESTADOS.get(_sem_acento(est).lower().strip(), ente_padrao) if est else "br"
        return IdentidadeNorma("constituicao", ente)
    mp = RE_TITULO_PLANALTO.match(linha)
    if mp:
        return IdentidadeNorma(
            _TIPO_PLANALTO[mp.group("tipo").lower()], "br", "",
            normalizar_numero(mp.group("num")), None,
        )
    for rx in (RE_TITULO_LEISORG, RE_ATO_SEFAZ):
        ml = rx.search(linha)
        if ml:
            bruto_tipo = re.sub(r"(?i)lei ordin[aá]ria", "lei", ml.group("tipo"))
            tipo_l = _tipo_canonico(bruto_tipo)
            if tipo_l:
                return IdentidadeNorma(
                    tipo_l, ente_padrao,
                    normalizar_orgao(orgao_contexto, ente_padrao) if tipo_l in TIPOS_POR_ORGAO else "",
                    normalizar_numero(ml.group("num")), int(ml.group("ano")),
                )
    m = RE_CABECALHO.search(linha)
    if not m:
        return None
    tipo = _tipo_canonico(m.group("tipo"))
    if tipo is None:
        return None
    orgao_suf, ano_suf = _orgao_do_sufixo(linha[m.start():], ente_padrao)
    ano = _ano(m.group("ano2")) or _ano(m.group("ano1")) or ano_suf
    orgao = ""
    if tipo in TIPOS_POR_ORGAO:
        orgao = (
            orgao_do_meio(m.group("meio") or "", ente_padrao)
            or orgao_suf
            or normalizar_orgao(orgao_contexto, ente_padrao)
        )
    ente = ente_padrao
    if orgao in ORGAOS_FEDERAIS_SIGLA:
        ente = "br"
    return IdentidadeNorma(tipo, ente, orgao, normalizar_numero(m.group("num")), ano)


# Órgãos cujas normas são federais onde quer que apareçam (ADR-034: esfera vem
# do órgão, nunca da UF da coletânea).
ORGAOS_FEDERAIS_SIGLA = frozenset({
    "conama", "ibama", "icmbio", "mma", "incra", "ana", "sfb", "rfb", "cmn", "ibge",
    "pfe-ibama", "funai", "iphan", "anm", "mapa", "bacen", "cnrh",
})


# ---------------------------------------------------------------------------
# Identificador gravado no legado (`legislation_documents.identifier`)
# ---------------------------------------------------------------------------

def identidade_de_identificador(
    identifier: str | None, *, scope: str | None, uf: str | None,
    agency: str | None, title: str | None = None,
) -> IdentidadeNorma:
    """Identidade de uma norma avulsa a partir do que o legado gravou.

    ``Constituição Federal de 1988``, ``Res. CONAMA 001/1986``, ``IN SEMAD-GO 01/2024``,
    ``Lei GO 18.104/2013``, ``OJN 06/2009 PFE-IBAMA``, ``Decreto 243/1967`` com título
    "Decreto-Lei nº 243/1967". O que não é norma (manual, lista, plano de manejo)
    vira ``documento`` com slug estável — identidade própria, sem se passar por norma.
    """
    ident = (identifier or "").strip()
    ente = "br" if (scope in (None, "federal", "nacional") or not uf) else uf.lower()
    texto = _sem_acento(ident)
    if re.search(r"constitui[cç][aã]o\s+federal", texto, re.I):
        return IdentidadeNorma("constituicao", "br", ano=1988)
    # O título é mais específico que o identificador quando diz "Decreto-Lei".
    if title and re.search(r"decreto[\s-]+lei", _sem_acento(title), re.I) and re.match(
        r"decreto\b", texto, re.I
    ):
        texto = re.sub(r"^decreto", "Decreto-Lei", texto, flags=re.I)
    m = re.match(
        r"^\s*(?P<tipo>[A-Za-z\.\-]+(?:\s+(?:complementar|normativa|delegada|provis[oó]ria|"
        r"jur[ií]dica\s+normativa|lei))?)\.?\s+(?P<resto>.*)$",
        texto, re.I,
    )
    tipo = _tipo_canonico(m.group("tipo")) if m else None
    num = re.search(r"(?P<num>\d[\d\.]*)\s*/\s*(?P<ano>\d{4})", texto)
    if tipo is None or num is None:
        slug = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
        return IdentidadeNorma("documento", ente, "", slug, None)
    resto = m.group("resto") if m else ""
    # Órgão: o que sobra de alfabético no identificador, senão a agência gravada.
    sobras = re.sub(r"\d[\d\.]*\s*/\s*\d{4}", " ", resto)
    siglas = [
        p for p in re.findall(r"[A-Za-z][A-Za-z\-/\.]*", sobras)
        if p.lower().strip(".") not in _NAO_ORGAO and p.lower() != (uf or "").lower()
    ]
    orgao = ""
    if tipo in TIPOS_POR_ORGAO:
        orgao = normalizar_orgao("".join(siglas) or (agency or ""), ente)
    if orgao in ORGAOS_FEDERAIS_SIGLA:
        ente = "br"
    return IdentidadeNorma(
        tipo, ente, orgao, normalizar_numero(num.group("num")), int(num.group("ano"))
    )


def identidade_documento(ente: str, nome: str, tipo: str = "documento") -> IdentidadeNorma:
    """Fonte não normativa (ficha SEMAD, TR, manual): slug estável do nome."""
    slug = re.sub(r"[^a-z0-9]+", "-", _sem_acento(nome).lower()).strip("-")[:160]
    return IdentidadeNorma(tipo, ente, "", slug, None)
