"""Recuperação normativa — filtro antes do ranking, vazio com razão (ADR-075 §7).

Ordem fixa:

1. **Consulta por identidade.** Se o contexto (ou a própria pergunta) traz norma
   e dispositivo — "art. 18 do Decreto 6.514/2008" —, busca-se por ID, sem
   similaridade.
2. **Conjunto elegível.** Nível permitido para o uso, status conforme o destino,
   vigência na data de referência, esfera/UF, objetivo, tenant e espaço
   vetorial. A similaridade não participa daqui.
3. **Ranking híbrido só dentro do elegível.** `tsvector` (portuguese) + pgvector,
   fusão por RRF (k=60). Busca EXATA — sem índice ANN — enquanto o elegível
   couber (#247: ivfflat + filtro devolvia menos que o pedido, em silêncio).
4. **Uma vaga por dispositivo.** A mesma norma em duas coletâneas é uma fonte; o
   mesmo artigo em duas versões ocupa uma vaga. Interpretação NUNCA ocupa vaga:
   é anexada ao dispositivo que ela refere (emenda ao ADR-038 §6).

**Se o filtro esvazia, a resposta é vazia com a razão.** Nunca relaxa: não tira
UF, não tira objetivo, não baixa limiar. As cinco razões são as do ADR.

Regras fixas de marcação (aplicadas antes do ranking, iguais para qualquer
resultado — não são relaxamento):
- vigência `nao_determinada` só entra no uso que a aceita, e sai marcada;
- fonte sem objetivo declarado entra marcada `objetivo_nao_declarado`
  (a classificação por objetivo ainda é parâmetro provisório; esconder a fonte
  por falta de etiqueta seria o ADR-037 ao contrário);
- versão bloqueada por original divergente (A5) não entra em `peca` nem `interno`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.zona_normativa.dispositivos import rotulo_artigo
from app.services.zona_normativa.identidade import (
    IdentidadeNorma,
    identidade_de_cabecalho,
    identidade_de_identificador,
)

logger = logging.getLogger(__name__)

RAZOES = (
    "contexto_insuficiente", "sem_fonte_elegivel", "fora_da_cobertura", "falha_de_busca",
    "espaco_vetorial_incompativel",
)
RRF_K = 60
CANDIDATOS_POR_RAMO = 50
ESFERAS = ("federal", "estadual", "municipal")


@dataclass(frozen=True)
class Politica:
    niveis: tuple[str, ...]
    status: tuple[str, ...]
    aceita_vigencia_nao_determinada: bool
    aceita_bloqueada: bool


# Destino → o que pode aparecer (ADR-075 §4: peça só cita validado; proposto é
# interno com selo; bruto é candidato de descoberta, sem selo de citável).
POLITICAS: dict[str, Politica] = {
    "peca": Politica(("norma", "exigencia"), ("validado",), False, False),
    "interno": Politica(("norma", "exigencia", "procedimento"), ("validado", "proposto"), True, False),
    "descoberta": Politica(
        ("norma", "exigencia", "procedimento"), ("validado", "proposto", "bruto"), True, True
    ),
}


@dataclass
class Contexto:
    pergunta: str
    uso: str
    data_referencia: date | None
    objetivo: str | None
    esferas: tuple[str, ...]
    uf: str | None = None
    tenant_id: int | None = None
    # Consulta por identidade: identificador da norma ("Decreto 6.514/2008") + artigo.
    norma: str | None = None
    artigo: str | None = None
    limite: int = 5


@dataclass
class Vazio:
    razao: str
    filtro_que_esvaziou: str | None
    detalhe: str


@dataclass
class TrechoRecuperado:
    trecho_id: int
    fonte_id: int
    fonte_versao_id: int
    dispositivo_id: int | None
    caminho: str
    artigo: str | None
    rotulo_fonte: str
    identidade_fonte: str
    nivel: str
    status_validacao: str
    vigencia_estado: str
    texto: str
    rrf: float = 0.0
    rank_vetor: int | None = None
    rank_lexico: int | None = None
    marcas: list[str] = field(default_factory=list)
    interpretacoes: list[dict] = field(default_factory=list)


@dataclass
class Resultado:
    trechos: list[TrechoRecuperado]
    vazio: Vazio | None
    filtros_aplicados: dict[str, Any]
    modelo: str | None
    metodo: str   # identidade | hibrido_rrf | nenhum

    def como_dict(self) -> dict:
        return {
            "trechos": [t.__dict__ for t in self.trechos],
            "interpretacoes_anexadas": {
                str(t.dispositivo_id): t.interpretacoes for t in self.trechos if t.interpretacoes
            },
            "vazio": None if self.vazio is None else self.vazio.__dict__,
            "filtros_aplicados": self.filtros_aplicados,
            "modelo": self.modelo,
            "metodo": self.metodo,
        }


def _vazio(ctx_filtros: dict, razao: str, filtro: str | None, detalhe: str, modelo=None) -> Resultado:
    assert razao in RAZOES
    return Resultado([], Vazio(razao, filtro, detalhe), ctx_filtros, modelo, "nenhum")


# ---------------------------------------------------------------------------
# Identidade na pergunta
# ---------------------------------------------------------------------------

_RE_ART_NORMA = re.compile(
    r"\bart(?:igo)?\.?\s*(?P<art>\d+(?:\s*-\s*[A-Za-z]\b)?)\s*[º°o]?\s*,?\s*(?:d[oa]|n[oa])\s+"
    r"(?P<norma>(?:lei\s+complementar|lei|decreto(?:-lei)?|resolu[çc][ãa]o|instru[çc][ãa]o\s+normativa|in|lc)"
    r"[^\d\n]{0,25}\d[\d\.]*\s*/\s*\d{4})",
    re.I,
)


def identidade_na_pergunta(pergunta: str, ente_padrao: str = "br") -> tuple[IdentidadeNorma, str] | None:
    """'art. 18 do Decreto 6.514/2008' → (identidade, '18'). Só com norma NOMEADA e ano."""
    m = _RE_ART_NORMA.search(pergunta or "")
    if not m:
        return None
    bruto = re.sub(r"(?i)\s*\b(federal|estadual)\b", "", m.group("norma"))
    ident = identidade_de_identificador(bruto, scope="federal", uf=None, agency=None)
    if not ident.determinada:
        cab = identidade_de_cabecalho(bruto, ente_padrao=ente_padrao)
        if cab is None or not cab.determinada:
            return None
        ident = cab
    return ident, re.sub(r"\s*-\s*", "-", m.group("art")).upper()


# ---------------------------------------------------------------------------
# Elegibilidade
# ---------------------------------------------------------------------------

def _filtros(ctx: Contexto, pol: Politica, modelo: str | None) -> tuple[list[tuple[str, str]], dict]:
    """Predicados, em ordem, cada um com nome — o nome é o que o vazio relata."""
    params: dict[str, Any] = {
        "niveis": list(pol.niveis), "status": list(pol.status), "esferas": list(ctx.esferas),
        "uf": ctx.uf, "objetivo": ctx.objetivo, "data_ref": ctx.data_referencia,
        "tenant": ctx.tenant_id, "modelo": modelo,
    }
    preds = [
        ("tenant", "(f.tenant_id IS NULL OR f.tenant_id = :tenant) AND (t.tenant_id IS NULL OR t.tenant_id = :tenant)"),
        ("esfera", "f.esfera = ANY(:esferas)"),
        ("uf", "(f.uf IS NULL OR f.uf = :uf)"),
        ("nivel", "f.nivel_autoridade = ANY(:niveis) AND f.identidade_determinada"),
        ("status", "v.status_validacao = ANY(:status)"),
        ("vigencia",
         "((v.vigencia_estado = 'determinada' AND (v.vigencia_inicio IS NULL OR v.vigencia_inicio <= :data_ref) "
         "AND (v.vigencia_fim IS NULL OR v.vigencia_fim >= :data_ref))"
         + (" OR v.vigencia_estado = 'nao_determinada')" if pol.aceita_vigencia_nao_determinada else ")")),
        ("objetivo", "(f.objetivos IS NULL OR 'transversal' = ANY(f.objetivos) OR :objetivo = ANY(f.objetivos))"),
    ]
    if not pol.aceita_bloqueada:
        preds.append(("bloqueio_original", "v.bloqueio_citacao IS NULL"))
    if modelo is not None:
        preds.append(("espaco_vetorial", "t.embedding_model = :modelo AND t.embedding IS NOT NULL"))
    return preds, params


_BASE = (
    "FROM trecho_normativo t "
    "JOIN fonte_normativa_versao v ON v.id = t.fonte_versao_id "
    "JOIN fonte_normativa f ON f.id = v.fonte_id "
    "LEFT JOIN dispositivo d ON d.id = t.dispositivo_id "
)


def _contar(session: Session, preds: list[tuple[str, str]], params: dict, extra: str = "") -> int:
    where = " AND ".join(p for _, p in preds) or "TRUE"
    return session.execute(text(f"SELECT count(*) {_BASE} WHERE {where} {extra}"), params).scalar_one()


def _diagnosticar_vazio(session: Session, preds, params) -> str:
    """Qual filtro esvaziou — só para RELATAR. O resultado continua vazio."""
    for i in range(1, len(preds) + 1):
        if _contar(session, preds[:i], params) == 0:
            return preds[i - 1][0]
    return preds[-1][0]


def _checar_contexto(ctx: Contexto) -> tuple[str, str] | None:
    if ctx.uso not in POLITICAS:
        return "uso", f"uso {ctx.uso!r} desconhecido; aceitos: {sorted(POLITICAS)}"
    if not (ctx.pergunta and ctx.pergunta.strip()) and not ctx.norma:
        return "pergunta", "pergunta vazia e sem norma para consulta por identidade"
    if ctx.data_referencia is None:
        return "data_referencia", "data de referência é obrigatória: vigência sem data não se decide"
    if not ctx.objetivo or ctx.objetivo == "nao_identificado":
        return "objetivo", "objetivo não resolvido — sem ele o elegível não se define"
    if not ctx.esferas or any(e not in ESFERAS for e in ctx.esferas):
        return "esferas", "esfera(s) ausente(s) ou inválida(s) (ADR-034: vem do órgão, não da UF)"
    if "estadual" in ctx.esferas and not ctx.uf:
        return "uf", "esfera estadual pedida sem UF"
    return None


def _cobertura(session: Session, ctx: Contexto) -> int:
    """Existe ALGUMA fonte identificada para a esfera/UF pedida, sem outro filtro?"""
    return session.execute(text(
        "SELECT count(*) FROM fonte_normativa f WHERE f.identidade_determinada "
        "AND f.esfera = ANY(:esferas) AND (f.uf IS NULL OR f.uf = :uf) "
        "AND (f.tenant_id IS NULL OR f.tenant_id = :tenant)"
    ), {"esferas": list(ctx.esferas), "uf": ctx.uf, "tenant": ctx.tenant_id}).scalar_one()


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

def _vetor_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


_SELECT_TRECHO = (
    "SELECT t.id AS trecho_id, f.id AS fonte_id, v.id AS versao_id, t.dispositivo_id, "
    "coalesce(d.caminho, t.cabecalho) AS caminho, d.artigo, f.rotulo, f.identidade, "
    "f.nivel_autoridade, v.status_validacao, v.vigencia_estado, v.vigencia_fim, f.objetivos, "
    "v.bloqueio_citacao, t.texto "
)


def _marcas(row, ctx: Contexto) -> list[str]:
    m = []
    if row.vigencia_estado == "nao_determinada":
        m.append("vigencia_nao_determinada")
    elif row.vigencia_fim is not None:
        m.append("historica")
    if row.objetivos is None:
        m.append("objetivo_nao_declarado")
    if row.status_validacao == "bruto":
        m.append("bruto_sem_selo_de_citavel")
    elif row.status_validacao == "proposto":
        m.append("proposto_com_selo")
    if row.bloqueio_citacao:
        m.append(f"bloqueada:{row.bloqueio_citacao}")
    return m


def _trecho(row, ctx: Contexto, **extra) -> TrechoRecuperado:
    return TrechoRecuperado(
        trecho_id=row.trecho_id, fonte_id=row.fonte_id, fonte_versao_id=row.versao_id,
        dispositivo_id=row.dispositivo_id, caminho=row.caminho, artigo=row.artigo,
        rotulo_fonte=row.rotulo, identidade_fonte=row.identidade, nivel=row.nivel_autoridade,
        status_validacao=row.status_validacao, vigencia_estado=row.vigencia_estado,
        texto=row.texto, marcas=_marcas(row, ctx), **extra,
    )


def _por_identidade(
    session: Session, ctx: Contexto, pol: Politica, ident: IdentidadeNorma, artigo: str | None,
    filtros_aplicados: dict,
) -> Resultado:
    fonte = session.execute(
        text("SELECT id FROM fonte_normativa WHERE identidade = :i AND (tenant_id IS NULL OR tenant_id = :t)"),
        {"i": ident.chave, "t": ctx.tenant_id},
    ).scalar_one_or_none()
    filtros_aplicados["identidade"] = {"norma": ident.chave, "artigo": artigo}
    if fonte is None:
        return _vazio(filtros_aplicados, "fora_da_cobertura", "identidade",
                      f"{ident.rotulo} não está no catálogo normativo")
    preds, params = _filtros(ctx, pol, None)
    preds = [("identidade", "f.id = :fonte")] + preds
    params["fonte"] = fonte
    if artigo:
        preds.insert(1, ("dispositivo", "d.artigo = :artigo"))
        params["artigo"] = artigo
    where = " AND ".join(p for _, p in preds)
    rows = session.execute(
        text(f"{_SELECT_TRECHO} {_BASE} WHERE {where} ORDER BY v.id DESC, t.ordem"), params
    ).all()
    if not rows:
        filtro = _diagnosticar_vazio(session, preds, params)
        return _vazio(filtros_aplicados, "sem_fonte_elegivel", filtro,
                      f"{ident.rotulo}{', ' + rotulo_artigo(artigo) if artigo else ''}: "
                      f"filtro '{filtro}' deixou o conjunto vazio")
    # Uma versão só (a mais recente elegível): a identidade já decidiu a fonte.
    versao = rows[0].versao_id
    trechos = [_trecho(r, ctx) for r in rows if r.versao_id == versao][: max(ctx.limite, 1) * 4]
    return Resultado(trechos, None, filtros_aplicados, None, "identidade")


def recuperar(
    session: Session,
    ctx: Contexto,
    *,
    embed_query: Callable[[str], list[float]],
    modelo: str,
) -> Resultado:
    """Contrato único de busca normativa. Nunca relaxa; vazio vem com a razão."""
    filtros_aplicados: dict[str, Any] = {
        "uso": ctx.uso, "data_referencia": ctx.data_referencia.isoformat() if ctx.data_referencia else None,
        "objetivo": ctx.objetivo, "esferas": list(ctx.esferas), "uf": ctx.uf,
        "tenant": ctx.tenant_id, "espaco_vetorial": modelo,
    }
    falta = _checar_contexto(ctx)
    if falta:
        return _vazio(filtros_aplicados, "contexto_insuficiente", falta[0], falta[1])
    pol = POLITICAS[ctx.uso]
    filtros_aplicados.update({"niveis": list(pol.niveis), "status": list(pol.status),
                              "aceita_vigencia_nao_determinada": pol.aceita_vigencia_nao_determinada})
    # Savepoint: erro de SQL na busca não pode envenenar a transação de quem chamou,
    # e rollback da sessão inteira desfaria trabalho alheio. Só a busca volta.
    try:
        with session.begin_nested():
            return _executar(session, ctx, pol, filtros_aplicados, embed_query, modelo)
    except Exception as exc:  # noqa: BLE001 — sobe como razão, nunca como lista vazia muda
        logger.exception("zona_normativa.recuperar falha_de_busca")
        return _vazio(filtros_aplicados, "falha_de_busca", None, f"{type(exc).__name__}: {exc}", modelo)


def _executar(
    session: Session, ctx: Contexto, pol: Politica, filtros_aplicados: dict,
    embed_query: Callable[[str], list[float]], modelo: str,
) -> Resultado:
    # (1) identidade
    alvo = None
    if ctx.norma:
        ident = identidade_de_identificador(ctx.norma, scope="federal", uf=None, agency=None)
        if not ident.determinada:
            ident = identidade_de_cabecalho(ctx.norma, ente_padrao=(ctx.uf or "br").lower()) or ident
        if not ident.determinada:
            return _vazio(filtros_aplicados, "contexto_insuficiente", "norma",
                          f"norma {ctx.norma!r} sem identidade determinável (tipo, número, ano)")
        alvo = (ident, ctx.artigo)
    else:
        alvo = identidade_na_pergunta(ctx.pergunta, (ctx.uf or "br").lower())
    if alvo is not None:
        return _anexar(session, ctx, pol, _por_identidade(session, ctx, pol, alvo[0], alvo[1],
                                                           filtros_aplicados), embed_query)

    # (2) cobertura e elegível
    if _cobertura(session, ctx) == 0:
        return _vazio(filtros_aplicados, "fora_da_cobertura", "esfera/uf",
                      f"nenhuma fonte identificada para {list(ctx.esferas)} / UF {ctx.uf}")
    preds_sem_modelo, params = _filtros(ctx, pol, None)
    if _contar(session, preds_sem_modelo, params) == 0:
        filtro = _diagnosticar_vazio(session, preds_sem_modelo, params)
        return _vazio(filtros_aplicados, "sem_fonte_elegivel", filtro,
                      f"filtro '{filtro}' deixou o conjunto elegível vazio")
    preds, params = _filtros(ctx, pol, modelo)
    n_elegivel = _contar(session, preds, params)
    if n_elegivel == 0:
        return _vazio(filtros_aplicados, "espaco_vetorial_incompativel", "espaco_vetorial",
                      f"há trechos elegíveis, mas nenhum no espaço vetorial {modelo!r}", modelo)
    filtros_aplicados["elegivel"] = n_elegivel

    # (3) ranking híbrido só no elegível
    qv = embed_query(ctx.pergunta)
    params["q"] = _vetor_literal(qv)
    params["texto"] = ctx.pergunta
    params["n"] = CANDIDATOS_POR_RAMO
    where = " AND ".join(p for _, p in preds)
    sql = f"""
        WITH elegivel AS (
            SELECT t.id, t.embedding, t.tsv {_BASE} WHERE {where}
        ),
        consulta AS (
            SELECT to_tsquery('simple', coalesce(string_agg(quote_literal(lexeme), ' | '), '')) AS tsq
            FROM unnest(to_tsvector('portuguese', :texto))
        ),
        vet AS (
            SELECT id, row_number() OVER (ORDER BY embedding <=> CAST(:q AS vector)) AS r
            FROM elegivel ORDER BY embedding <=> CAST(:q AS vector) LIMIT :n
        ),
        lex AS (
            SELECT e.id, row_number() OVER (ORDER BY ts_rank_cd(e.tsv, c.tsq) DESC, e.id) AS r
            FROM elegivel e, consulta c WHERE e.tsv @@ c.tsq
            ORDER BY ts_rank_cd(e.tsv, c.tsq) DESC, e.id LIMIT :n
        ),
        fusao AS (
            SELECT id, sum(1.0 / ({RRF_K} + r)) AS rrf,
                   min(r) FILTER (WHERE fonte = 'v') AS rv, min(r) FILTER (WHERE fonte = 'l') AS rl
            FROM (SELECT id, r, 'v' AS fonte FROM vet UNION ALL SELECT id, r, 'l' FROM lex) u
            GROUP BY id
        )
        {_SELECT_TRECHO}, fu.rrf, fu.rv, fu.rl
        FROM fusao fu JOIN trecho_normativo t ON t.id = fu.id
        JOIN fonte_normativa_versao v ON v.id = t.fonte_versao_id
        JOIN fonte_normativa f ON f.id = v.fonte_id
        LEFT JOIN dispositivo d ON d.id = t.dispositivo_id
        ORDER BY fu.rrf DESC, t.id
    """
    rows = session.execute(text(sql), params).all()

    # (4) uma vaga por dispositivo (fonte + artigo; sem artigo, fonte + caminho)
    vagas: dict[tuple, TrechoRecuperado] = {}
    for r in rows:
        chave = (r.fonte_id, r.artigo) if r.artigo else (r.fonte_id, r.caminho.split(", ", 1)[-1])
        if chave in vagas:
            continue
        vagas[chave] = _trecho(r, ctx, rrf=float(r.rrf), rank_vetor=r.rv, rank_lexico=r.rl)
        if len(vagas) >= ctx.limite:
            break
    res = Resultado(list(vagas.values()), None, filtros_aplicados, modelo, "hibrido_rrf")
    return _anexar(session, ctx, pol, res, embed_query)


def _anexar(
    session: Session, ctx: Contexto, pol: Politica, res: Resultado,
    embed_query: Callable[[str], list[float]],
) -> Resultado:
    """Interpretação anexada ao dispositivo que ela refere — não disputa vaga."""
    if not res.trechos:
        return res
    alvos = {(t.fonte_id, t.artigo) for t in res.trechos if t.nivel == "norma"}
    if not alvos:
        return res
    rows = session.execute(text(
        """
        SELECT i.norma_fonte_id, i.artigo AS art_alvo, i.citacao_literal, i.status_validacao AS status_ligacao,
               fi.id AS interp_id, fi.rotulo AS interp_rotulo, v.id AS versao_id, v.status_validacao
        FROM interpretacao_norma i
        JOIN fonte_normativa fi ON fi.id = i.interpretacao_fonte_id
        JOIN fonte_normativa_versao v ON v.fonte_id = fi.id
        WHERE i.norma_fonte_id = ANY(:fontes) AND v.status_validacao = ANY(:status)
          AND (fi.tenant_id IS NULL OR fi.tenant_id = :tenant)
        """
    ), {"fontes": list({a[0] for a in alvos}), "status": list(pol.status), "tenant": ctx.tenant_id}).all()
    if not rows:
        return res
    q = _vetor_literal(embed_query(ctx.pergunta)) if ctx.pergunta else None
    for t in res.trechos:
        for r in rows:
            if r.norma_fonte_id != t.fonte_id or (r.art_alvo and r.art_alvo != t.artigo):
                continue
            if any(a["interpretacao_fonte_id"] == r.interp_id for a in t.interpretacoes):
                continue
            ordem = "embedding <=> CAST(:q AS vector)" if q else "ordem"
            melhor = session.execute(text(
                f"SELECT id, texto FROM trecho_normativo WHERE fonte_versao_id = :v "
                f"AND embedding IS NOT NULL ORDER BY {ordem} LIMIT 1"
            ), {"v": r.versao_id, "q": q}).first()
            t.interpretacoes.append({
                "interpretacao_fonte_id": r.interp_id, "rotulo": r.interp_rotulo,
                "fonte_versao_id": r.versao_id, "status_validacao": r.status_validacao,
                "ligacao": {"artigo": r.art_alvo, "citacao_literal": r.citacao_literal,
                            "status": r.status_ligacao},
                "trecho_id": melhor.id if melhor else None,
                "texto": melhor.texto if melhor else None,
            })
    return res
