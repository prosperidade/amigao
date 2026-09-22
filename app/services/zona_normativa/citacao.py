"""Citação por claim, verificada por ID ANTES de emitir (ADR-075 §8).

Cada afirmação carrega ``[fonte_versao_id, dispositivo, localizador]``. O
envelope entrega ao modelo só as fontes elegíveis, com IDs; a verificação aqui é
**pertencimento a conjunto, não semelhança**:

1. todo ID citado está no envelope;
2. o dispositivo existe naquela versão (``art. 999`` da Lei 12.651/2012 não passa);
3. o status serve ao destino (peça só cita ``validado``);
4. a vigência vale na data de referência;
5. a versão não está bloqueada por original divergente (A5).

E o detector de menção sem vínculo: norma mencionada no texto da afirmação sem
ID correspondente é **citação órfã e bloqueia a saída** — inclusive artigo
mencionado de norma citada quando esse artigo não está entre as citações. É o
papel que o `citation_evaluator` passa a ter: detector, não validador por regex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.zona_normativa.identidade import (
    _tipo_canonico,
    identidade_de_identificador,
    normalizar_numero,
)
from app.services.zona_normativa.recuperacao import POLITICAS, Resultado

FALHAS = (
    "id_fora_do_envelope", "dispositivo_inexistente", "status_nao_serve_ao_destino",
    "fora_da_vigencia", "vigencia_nao_determinada", "versao_bloqueada", "citacao_orfa",
    "artigo_mencionado_sem_vinculo",
)


@dataclass(frozen=True)
class Citacao:
    fonte_versao_id: int
    dispositivo: str            # "art. 18", "18", "art. 61-A, § 4º", "texto integral"
    localizador: str | None = None


@dataclass
class Afirmacao:
    texto: str
    citacoes: list[Citacao] = field(default_factory=list)


@dataclass
class FonteNoEnvelope:
    fonte_versao_id: int
    identidade: str
    rotulo: str
    status_validacao: str
    vigencia_estado: str
    vigencia_inicio: date | None
    vigencia_fim: date | None
    bloqueio_citacao: str | None


@dataclass
class Falha:
    afirmacao: int
    tipo: str
    detalhe: str


@dataclass
class Veredito:
    emitir: bool
    falhas: list[Falha]


def envelope_de_resultado(session: Session, res: Resultado) -> dict[int, FonteNoEnvelope]:
    """As fontes que a recuperação entregou (inclui interpretações anexadas)."""
    ids = {t.fonte_versao_id for t in res.trechos}
    ids |= {i["fonte_versao_id"] for t in res.trechos for i in t.interpretacoes}
    return carregar_envelope(session, ids)


def carregar_envelope(session: Session, versao_ids) -> dict[int, FonteNoEnvelope]:
    if not versao_ids:
        return {}
    rows = session.execute(text(
        "SELECT v.id, f.identidade, f.rotulo, v.status_validacao, v.vigencia_estado, v.vigencia_inicio, "
        "v.vigencia_fim, v.bloqueio_citacao FROM fonte_normativa_versao v "
        "JOIN fonte_normativa f ON f.id = v.fonte_id WHERE v.id = ANY(:ids)"
    ), {"ids": list(versao_ids)}).all()
    return {r.id: FonteNoEnvelope(*r) for r in rows}


_RE_DISP = re.compile(
    r"^(?:art(?:igo)?\.?\s*)?(?P<art>\d+(?:\s*-\s*[A-Za-z])?)\s*[º°o]?"
    r"(?:\s*,?\s*(?:§\s*(?P<par>\d+)\s*[º°o]?|(?P<unico>par[áa]grafo\s+[úu]nico)))?",
    re.I,
)


def _dispositivo_existe(session: Session, versao_id: int, dispositivo: str) -> bool:
    d = dispositivo.strip()
    if d.lower() in ("texto integral", "preâmbulo", "preambulo"):
        return session.execute(text(
            "SELECT 1 FROM dispositivo WHERE fonte_versao_id = :v AND tipo = 'preambulo' LIMIT 1"
        ), {"v": versao_id}).first() is not None
    m = _RE_DISP.match(d)
    if not m:
        return False
    art = re.sub(r"\s*-\s*", "-", m.group("art")).upper()
    par = "unico" if m.group("unico") else m.group("par")
    sql = "SELECT 1 FROM dispositivo WHERE fonte_versao_id = :v AND artigo = :a"
    params = {"v": versao_id, "a": art}
    if par:
        sql += " AND paragrafo = :p"
        params["p"] = par
    return session.execute(text(sql + " LIMIT 1"), params).first() is not None


# Menção a norma no texto livre.
_RE_MENCAO = re.compile(
    r"\b(?P<tipo>Lei\s+Complementar|LC|Lei|Decreto(?:-Lei)?|Resolu[çc][ãa]o|Res\.|"
    r"Instru[çc][ãa]o\s+Normativa|IN|Portaria|OJN|Orienta[çc][ãa]o\s+Jur[ií]dica\s+Normativa)"
    r"(?P<meio>(?:\s+(?!n[º°o.]|de\b)[A-Z][A-Za-z\-/]{1,15}){0,3})"
    r"\s*(?:n[º°o.]*\s*)?(?P<num>\d{1,3}(?:\.\d{3})*|\d+)"
    r"(?:\s*/\s*(?P<ano>(?:19|20)\d{2})|,?\s+de\s+(?:\d{1,2}\s+de\s+\w+\s+de\s+)?(?P<ano2>(?:19|20)\d{2}))?"
)
_RE_ART_DE = re.compile(
    r"\bart(?:igo)?s?\.?\s*(?P<art>\d+(?:\s*-\s*[A-Z]\b)?)\s*[º°o]?[^;.\n]{0,12}?\b(?:d[oa])\s+"
    r"(?=(?:Lei|LC|Decreto|Resolu|Res\.|Instru|IN\b|Portaria))",
    re.I,
)


def mencoes(texto: str) -> list[dict]:
    """Normas mencionadas: tipo+número (+ano quando escrito) e artigo associado."""
    out = []
    for m in _RE_MENCAO.finditer(texto):
        tipo = _tipo_canonico(m.group("tipo"))
        if tipo is None:
            continue
        ano = m.group("ano") or m.group("ano2")
        num = normalizar_numero(m.group("num"))
        artigo = None
        base = max(0, m.start() - 40)
        for ma in _RE_ART_DE.finditer(texto[base : m.end()]):
            if base + ma.end() == m.start():   # "art. 18 do " termina onde a norma começa
                artigo = re.sub(r"\s*-\s*", "-", ma.group("art")).upper()
        chave = None
        if ano:
            ident = identidade_de_identificador(
                f"{m.group('tipo')}{m.group('meio') or ''} {m.group('num')}/{ano}",
                scope="federal", uf=None, agency=None,
            )
            chave = ident.chave if ident.determinada else None
        out.append({"literal": m.group(0).strip(), "tipo": tipo, "numero": num,
                    "ano": int(ano) if ano else None, "chave": chave, "artigo": artigo})
    return out


def _casa(mencao: dict, fonte: FonteNoEnvelope) -> bool:
    tipo, ente, orgao, numero, ano = (fonte.identidade.split("|") + [""] * 5)[:5]
    if mencao["chave"] is not None and mencao["chave"].split("|")[0] == tipo:
        # Com ano escrito: tipo + número + ano. O ente/órgão da menção pode faltar
        # ("Lei 18.104/2013" para a Lei GO) — o ID citado desambigua.
        return mencao["numero"] == numero and str(mencao["ano"]) == ano
    return mencao["tipo"] == tipo and mencao["numero"] == numero


def verificar(
    session: Session,
    afirmacoes: list[Afirmacao],
    envelope: dict[int, FonteNoEnvelope],
    *,
    destino: str,
    data_referencia: date,
) -> Veredito:
    pol = POLITICAS[destino]
    falhas: list[Falha] = []
    for i, a in enumerate(afirmacoes):
        citadas: list[tuple[FonteNoEnvelope, Citacao]] = []
        for c in a.citacoes:
            f = envelope.get(c.fonte_versao_id)
            if f is None:
                falhas.append(Falha(i, "id_fora_do_envelope", f"fonte_versao_id={c.fonte_versao_id}"))
                continue
            citadas.append((f, c))
            if not _dispositivo_existe(session, c.fonte_versao_id, c.dispositivo):
                falhas.append(Falha(i, "dispositivo_inexistente", f"{f.rotulo}, {c.dispositivo}"))
            if f.status_validacao not in pol.status:
                falhas.append(Falha(i, "status_nao_serve_ao_destino",
                                    f"{f.rotulo} está {f.status_validacao}; {destino} aceita {list(pol.status)}"))
            if f.bloqueio_citacao and not pol.aceita_bloqueada:
                falhas.append(Falha(i, "versao_bloqueada", f"{f.rotulo}: {f.bloqueio_citacao}"))
            if f.vigencia_estado == "nao_determinada":
                if not pol.aceita_vigencia_nao_determinada:
                    falhas.append(Falha(i, "vigencia_nao_determinada", f.rotulo))
            elif (f.vigencia_inicio and f.vigencia_inicio > data_referencia) or (
                f.vigencia_fim and f.vigencia_fim < data_referencia
            ):
                falhas.append(Falha(i, "fora_da_vigencia", f"{f.rotulo} em {data_referencia}"))
        for m in mencoes(a.texto):
            casadas = [(f, c) for f, c in citadas if _casa(m, f)]
            if not casadas:
                falhas.append(Falha(i, "citacao_orfa", f"'{m['literal']}' mencionada sem ID citado"))
                continue
            if m["artigo"]:
                arts = set()
                for _f, c in casadas:
                    md = _RE_DISP.match(c.dispositivo.strip())
                    if md:
                        arts.add(re.sub(r"\s*-\s*", "-", md.group("art")).upper())
                if m["artigo"] not in arts:
                    falhas.append(Falha(i, "artigo_mencionado_sem_vinculo",
                                        f"art. {m['artigo']} de '{m['literal']}' não está entre as citações"))
    return Veredito(emitir=not falhas, falhas=falhas)
