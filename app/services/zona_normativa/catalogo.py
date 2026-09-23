"""Construção do catálogo normativo a partir do corpus legado (ADR-075 §5, D2).

Não é UPDATE de classificação: é **reingestão** — as 32 coletâneas são cortadas
em atos, cada ato vira fonte com identidade, e a coletânea vira proveniência.

Duas fases, separadas de propósito:

1. `planejar()` — só leitura. Desmembra, identifica, agrupa por identidade (o
   mesmo ato em N coletâneas é UMA fonte com N proveniências; redação diferente
   do mesmo ato é versão) e classifica o nível. Devolve o plano e o relatório
   por coletânea — é o dry-run que a revisão humana das fronteiras lê.
2. `aplicar()` — grava fonte, versão, proveniência, dispositivo, trecho e as
   tarefas de revisão; embarca os trechos. Recusa rodar sobre catálogo que já
   tem validação registrada: validação é trilha, não se apaga para reconstruir.

O que NÃO entra na busca: fonte com identidade não fechada ou nível
`nao_determinado`. Ela é gravada (versão + proveniência + tarefa), mas sem
dispositivo nem trecho — é fila de revisão, não candidato.

Fontes (dev, medido em 22/09): 32 coletâneas, 81 normas avulsas e as 284 fontes
SEMAD-GO que só existem como chunk (`knowledge_catalog`, sem linha de documento).
"""

from __future__ import annotations

import collections
import hashlib
import logging
import pathlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.legislation import LegislationDocument
from app.models.zona_normativa import (
    Dispositivo,
    FonteNormativa,
    FonteNormativaProveniencia,
    FonteNormativaVersao,
    InterpretacaoNorma,
    TarefaRevisaoNormativa,
    ValidacaoNorma,
)
from app.services.normalizacao import normalizar
from app.services.zona_normativa import hierarquia
from app.services.zona_normativa.desmembramento import (
    MOTIVO_IDENTIDADE_ND,
    desmembrar,
    hash_texto_normalizado,
)
from app.services.zona_normativa.dispositivos import (
    DispositivoExtraido,
    extrair_dispositivos,
    trechos_do_dispositivo,
)
from app.services.zona_normativa.identidade import (
    IdentidadeNorma,
    identidade_de_cabecalho,
    identidade_de_identificador,
    identidade_documento,
)

logger = logging.getLogger(__name__)

# As 3 coletâneas de Goiás gravadas como `manual` (ZONA_NORMATIVA_RAG §1.1).
COLETANEAS_GO_COMO_MANUAL = (12, 13, 15)

# Interpretação e documento não normativo não são articulados: "Art. 21" numa
# OJN é citação no começo da linha, não dispositivo dela.
NIVEIS_ARTICULADOS = frozenset({"norma"})

MOTIVOS_FRONTEIRA = frozenset({
    "inicio_estimado", "impressao_sem_pagina_1", "multiplos_atos_na_impressao",
    "titulo_da_aba_diverge_do_cabecalho", "regiao_sem_sinal_de_fronteira",
})

PRECO_EMBEDDING_USD_POR_MTOK = 0.02  # text-embedding-3-small (medição de custo, não cobrança)


@dataclass
class PlanoProveniencia:
    legislation_document_id: int | None
    source_ref: str | None
    documento_origem_rotulo: str
    sinal_fronteira: str
    trecho_hash: str
    offset_inicio: int | None = None
    offset_fim: int | None = None
    pagina_inicio: int | None = None
    pagina_fim: int | None = None
    url_impressa: str | None = None
    impresso_em: str | None = None
    motivos: list[str] = field(default_factory=list)


@dataclass
class PlanoVersao:
    texto: str
    hash_texto: str
    origem_ingestao: str
    proveniencias: list[PlanoProveniencia] = field(default_factory=list)
    vigencia_estado: str = "nao_determinada"
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    # Fontes SEMAD: os chunks do legado já são a unidade de busca; o vetor é reaproveitado.
    trechos_legado: list[tuple[str, str]] | None = None   # (texto, vetor literal)


@dataclass
class PlanoFonte:
    identidade: str
    determinada: bool
    tipo: str
    ente: str
    orgao: str
    numero: str
    ano: int | None
    esfera: str
    uf: str | None
    rotulo: str
    titulo: str | None
    nivel: str
    nivel_origem: str
    objetivos: list[str] | None
    objetivos_origem: str | None
    versoes: dict[str, PlanoVersao] = field(default_factory=dict)


@dataclass
class Plano:
    fontes: dict[str, PlanoFonte] = field(default_factory=dict)
    relatorio_coletaneas: list[dict] = field(default_factory=list)
    originais: dict[int, tuple[str, str]] = field(default_factory=dict)  # doc_id -> (sha, caminho)

    def resumo(self) -> dict:
        niveis = collections.Counter(f.nivel for f in self.fontes.values())
        buscaveis = [f for f in self.fontes.values() if _buscavel(f)]
        return {
            "fontes": len(self.fontes),
            "fontes_identidade_determinada": sum(f.determinada for f in self.fontes.values()),
            "versoes": sum(len(f.versoes) for f in self.fontes.values()),
            "proveniencias": sum(
                len(v.proveniencias) for f in self.fontes.values() for v in f.versoes.values()
            ),
            "por_nivel": dict(niveis),
            "fontes_buscaveis": len(buscaveis),
            "fontes_com_mais_de_uma_proveniencia": sum(
                1 for f in self.fontes.values()
                if sum(len(v.proveniencias) for v in f.versoes.values()) > 1
            ),
            "documentos_com_original": len(self.originais),
        }


def _buscavel(f: PlanoFonte) -> bool:
    return f.determinada and f.nivel != "nao_determinado"


# ---------------------------------------------------------------------------
# Originais (A5)
# ---------------------------------------------------------------------------

def localizar_original(file_path: str | None, raizes: Iterable[pathlib.Path]) -> pathlib.Path | None:
    """O legado gravou caminhos de máquinas diferentes (`legislacao\\X.pdf`,
    `/app/legislacao_estadual/MS/…`, `C:\\…\\normas_k3\\…`). Procura-se o NOME do
    arquivo nas raízes informadas; o hash dos bytes é que identifica."""
    if not file_path:
        return None
    nome = re.split(r"[\\/]", file_path.strip())[-1]
    for raiz in raizes:
        cand = raiz / nome
        if cand.is_file():
            return cand
    return None


def sha256_arquivo(caminho: pathlib.Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Planejamento (só leitura)
# ---------------------------------------------------------------------------

def _chave_nd(doc_id: int, offset: int) -> str:
    return f"nao_determinado|doc{doc_id}|{offset}"


def _registrar(
    plano: Plano, *, ident: IdentidadeNorma | None, chave: str, determinada: bool,
    rotulo: str, titulo: str | None, nivel: str, nivel_origem: str,
    objetivos: list[str] | None, objetivos_origem: str | None,
    versao: PlanoVersao, uf_padrao: str | None,
) -> None:
    f = plano.fontes.get(chave)
    if f is None:
        ente = ident.ente if ident else (uf_padrao or "br").lower()
        f = PlanoFonte(
            identidade=chave, determinada=determinada,
            tipo=ident.tipo if ident else "nao_determinado", ente=ente,
            orgao=ident.orgao if ident else "", numero=ident.numero if ident else "",
            ano=ident.ano if ident else None,
            esfera="federal" if ente == "br" else "estadual",
            uf=None if ente == "br" else ente.upper(), rotulo=rotulo[:220], titulo=titulo,
            nivel=nivel, nivel_origem=nivel_origem, objetivos=objetivos,
            objetivos_origem=objetivos_origem,
        )
        plano.fontes[chave] = f
    else:
        # Mesmo ato vindo de outra origem: objetivos se somam, nível mais específico fica.
        if objetivos:
            f.objetivos = sorted(set(f.objetivos or []) | set(objetivos))
        if f.titulo is None and titulo:
            f.titulo = titulo
    existente = f.versoes.get(versao.hash_texto)
    if existente is None:
        f.versoes[versao.hash_texto] = versao
    else:
        existente.proveniencias.extend(versao.proveniencias)
        if existente.vigencia_estado == "nao_determinada" and versao.vigencia_estado == "determinada":
            existente.vigencia_estado = versao.vigencia_estado
            existente.vigencia_inicio = versao.vigencia_inicio
            existente.vigencia_fim = versao.vigencia_fim


def planejar(
    session: Session, *, raizes_originais: Iterable[pathlib.Path] = (),
    apenas_documentos: Iterable[int] | None = None,
) -> Plano:
    plano = Plano()
    raizes = [pathlib.Path(r) for r in raizes_originais]
    q = session.query(LegislationDocument).filter(LegislationDocument.full_text.isnot(None))
    if apenas_documentos is not None:
        q = q.filter(LegislationDocument.id.in_(list(apenas_documentos)))
    docs = q.order_by(LegislationDocument.id).all()

    for doc in docs:
        orig = localizar_original(doc.file_path, raizes)
        if orig is not None:
            plano.originais[doc.id] = (sha256_arquivo(orig), str(orig))
        rotulo_doc = doc.identifier or doc.title
        eh_coletanea = doc.source_type == "compendio_regente" or doc.id in COLETANEAS_GO_COMO_MANUAL
        if eh_coletanea:
            _planejar_coletanea(plano, doc, rotulo_doc)
        else:
            _planejar_avulso(plano, doc, rotulo_doc)

    if apenas_documentos is None:
        _planejar_semad(plano, session)
    return plano


def _planejar_coletanea(plano: Plano, doc: LegislationDocument, rotulo_doc: str) -> None:
    uf = (doc.uf or "br").lower()
    segs = desmembrar(doc.full_text or "", uf)
    objs = hierarquia.objetivos_do_nucleo(rotulo_doc)
    rel = {
        "documento_id": doc.id, "coletanea": rotulo_doc, "uf": doc.uf,
        "segmentos": len(segs),
        "por_sinal": dict(collections.Counter(s.sinal for s in segs)),
        "identidade_determinada": sum(s.determinado for s in segs),
        "motivos": dict(collections.Counter(m for s in segs for m in s.motivos)),
        "atos": [],
    }
    for s in segs:
        prov = PlanoProveniencia(
            legislation_document_id=doc.id, source_ref=None, documento_origem_rotulo=rotulo_doc[:255],
            sinal_fronteira=s.sinal, trecho_hash=s.hash_texto, offset_inicio=s.inicio,
            offset_fim=s.fim, pagina_inicio=s.pagina_inicio, pagina_fim=s.pagina_fim,
            url_impressa=s.url, impresso_em=s.impresso_em, motivos=list(s.motivos),
        )
        versao = PlanoVersao(s.texto, s.hash_texto, "desmembramento_coletanea", [prov])
        if s.determinado:
            nivel, origem = hierarquia.nivel_de_ato_desmembrado(s.identidade)
            chave, rotulo, det = s.identidade.chave, s.identidade.rotulo, True
        else:
            nivel, origem = "nao_determinado", MOTIVO_IDENTIDADE_ND
            chave = _chave_nd(doc.id, s.inicio)
            parcial = s.identidade.rotulo if s.identidade else "sem cabeçalho"
            rotulo, det = f"[não determinado] {parcial} — {rotulo_doc}, offset {s.inicio}", False
        _registrar(
            plano, ident=s.identidade if s.determinado else None, chave=chave, determinada=det,
            rotulo=rotulo, titulo=s.cabecalho, nivel=nivel, nivel_origem=origem,
            objetivos=objs if s.determinado else None,
            objetivos_origem=hierarquia.ORIGEM_OBJETIVO_NUCLEO if (objs and s.determinado) else None,
            versao=versao, uf_padrao=doc.uf,
        )
        rel["atos"].append({
            "offset": [s.inicio, s.fim], "sinal": s.sinal, "paginas": [s.pagina_inicio, s.pagina_fim],
            "identidade": chave if det else None, "rotulo": rotulo[:120], "cabecalho": s.cabecalho,
            "titulo_aba": s.titulo_aba, "caracteres": len(s.texto), "motivos": s.motivos,
        })
    plano.relatorio_coletaneas.append(rel)


def _planejar_avulso(plano: Plano, doc: LegislationDocument, rotulo_doc: str) -> None:
    ident = identidade_de_identificador(
        doc.identifier, scope=doc.scope, uf=doc.uf, agency=doc.agency, title=doc.title
    )
    nivel, origem = hierarquia.nivel_de_norma_avulsa(
        ident, source_type=doc.source_type, identifier=doc.identifier
    )
    texto = normalizar(doc.full_text or "").strip()
    vig_estado, vig_ini, vig_fim = "nao_determinada", None, None
    if doc.vigencia_fim is not None:
        # Revogação declarada pela curadoria (ADR-037): data de fim conhecida.
        vig_estado, vig_ini, vig_fim = "determinada", doc.vigencia_inicio, doc.vigencia_fim
    prov = PlanoProveniencia(
        legislation_document_id=doc.id, source_ref=None, documento_origem_rotulo=rotulo_doc[:255],
        sinal_fronteira="documento_inteiro", trecho_hash=hash_texto_normalizado(texto),
        url_impressa=doc.url,
    )
    versao = PlanoVersao(
        texto, hash_texto_normalizado(texto), "avulso_legislation_documents", [prov],
        vig_estado, vig_ini, vig_fim,
    )
    objs = hierarquia.objetivos_de_demand_types(doc.demand_types)
    _registrar(
        plano, ident=ident, chave=ident.chave, determinada=ident.determinada,
        rotulo=ident.rotulo if ident.tipo != "documento" else rotulo_doc, titulo=doc.title,
        nivel=nivel, nivel_origem=origem, objetivos=objs,
        objetivos_origem="demand_types_do_legado" if objs else None, versao=versao,
        uf_padrao=doc.uf,
    )


def _planejar_semad(plano: Plano, session: Session) -> None:
    rows = session.execute(text(
        """
        SELECT source_type, source_ref, chunk_index, chunk_text, embedding::text AS vetor,
               uf, embedding_model
        FROM knowledge_catalog
        WHERE source_type <> 'legislation' AND tenant_id IS NULL
        ORDER BY source_ref, chunk_index
        """
    )).all()
    por_ref: dict[tuple[str, str], list] = collections.defaultdict(list)
    for r in rows:
        por_ref[(r.source_type, r.source_ref)].append(r)
    for (st, ref), chunks in por_ref.items():
        tipo, nivel, origem = hierarquia.tipo_e_nivel_semad(st, ref)
        uf = (chunks[0].uf or "GO").lower()
        ident = identidade_documento(uf, ref, tipo=tipo)
        texto = "\n\n".join(normalizar(c.chunk_text) for c in chunks).strip()
        h = hash_texto_normalizado(texto)
        prov = PlanoProveniencia(
            legislation_document_id=None, source_ref=ref[:255],
            documento_origem_rotulo=f"SEMAD-GO {st}: {ref}"[:255],
            sinal_fronteira="documento_inteiro", trecho_hash=h,
        )
        versao = PlanoVersao(
            texto, h, "semad_knowledge_catalog", [prov],
            trechos_legado=[(normalizar(c.chunk_text), c.vetor) for c in chunks],
        )
        _registrar(
            plano, ident=ident, chave=ident.chave, determinada=True, rotulo=f"SEMAD-GO — {ref}",
            titulo=ref, nivel=nivel, nivel_origem=origem, objetivos=["licenciamento"],
            objetivos_origem="fonte_semad_licenciamento", versao=versao, uf_padrao="GO",
        )


# ---------------------------------------------------------------------------
# Unidades de busca de uma versão (para custo e para gravação)
# ---------------------------------------------------------------------------

def dispositivos_da_versao(fonte: PlanoFonte, versao: PlanoVersao) -> list[DispositivoExtraido]:
    if fonte.nivel in NIVEIS_ARTICULADOS:
        return extrair_dispositivos(versao.texto)
    return [DispositivoExtraido("preambulo", "texto integral", None, None, 0, versao.texto)]


def estimar_embedding(plano: Plano) -> dict:
    trechos = tokens = reaproveitados = 0
    for f in plano.fontes.values():
        if not _buscavel(f):
            continue
        for v in f.versoes.values():
            if v.trechos_legado is not None:
                reaproveitados += len(v.trechos_legado)
                continue
            for d in dispositivos_da_versao(f, v):
                for _t, n in trechos_do_dispositivo(d):
                    trechos += 1
                    tokens += n
    return {
        "trechos_a_embarcar": trechos, "tokens": tokens,
        "custo_estimado_usd": round(tokens / 1e6 * PRECO_EMBEDDING_USD_POR_MTOK, 4),
        "trechos_com_vetor_reaproveitado": reaproveitados,
    }


# ---------------------------------------------------------------------------
# Aplicação (escrita)
# ---------------------------------------------------------------------------

def _vetor_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


def catalogo_vazio(session: Session) -> bool:
    return session.query(FonteNormativa.id).first() is None


def limpar_catalogo(session: Session) -> None:
    """Só para reconstruir o que ainda não tem validação. Validação é trilha."""
    if session.query(ValidacaoNorma.id).first() is not None:
        raise RuntimeError(
            "O catálogo tem validação registrada (validacao_norma). Reconstruir apagaria a "
            "trilha de quem assinou — recusado. Nova ingestão entra como versão nova."
        )
    for tabela in (
        "interpretacao_norma", "trecho_normativo", "dispositivo", "tarefa_revisao_normativa",
        "fonte_normativa_proveniencia", "fonte_normativa_versao", "fonte_normativa",
    ):
        session.execute(text(f"DELETE FROM {tabela}"))  # noqa: S608 — nomes fixos


def aplicar(
    session: Session, plano: Plano, *,
    embed: Callable[[list[str]], list[list[float]]],
    modelo_embedding: str,
    originais_storage: dict[int, str] | None = None,
    lote: int = 96,
    progresso: Callable[[str], None] = lambda _m: None,
) -> dict:
    """Grava o plano. `embed` recebe textos e devolve vetores (768d)."""
    if not catalogo_vazio(session):
        raise RuntimeError("Catálogo não está vazio — use limpar_catalogo() antes (dev) ou versão nova.")
    originais_storage = originais_storage or {}
    fila_embed: list[tuple[int, str]] = []   # (trecho_id, texto para o vetor)
    contagem = collections.Counter()

    def _descarregar() -> None:
        if not fila_embed:
            return
        vetores = embed([t for _, t in fila_embed])
        if len(vetores) != len(fila_embed):
            raise RuntimeError("embedding devolveu quantidade diferente da pedida")
        for (tid, _), vec in zip(fila_embed, vetores, strict=True):
            session.execute(
                text("UPDATE trecho_normativo SET embedding = CAST(:v AS vector), embedding_model = :m "
                     "WHERE id = :id"),
                {"v": _vetor_literal(vec), "m": modelo_embedding, "id": tid},
            )
        contagem["trechos_embarcados"] += len(fila_embed)
        fila_embed.clear()

    for i, f in enumerate(plano.fontes.values(), 1):
        fonte = FonteNormativa(
            identidade=f.identidade, identidade_determinada=f.determinada, tipo=f.tipo,
            ente=f.ente, orgao=f.orgao, numero=f.numero[:200], ano=f.ano, esfera=f.esfera,
            uf=f.uf, rotulo=f.rotulo, titulo=f.titulo, nivel_autoridade=f.nivel,
            nivel_origem=f.nivel_origem, objetivos=f.objetivos, objetivos_origem=f.objetivos_origem,
        )
        session.add(fonte)
        session.flush()
        contagem["fontes"] += 1
        if f.determinada and f.nivel == "nao_determinado":
            session.add(TarefaRevisaoNormativa(
                tipo="nivel_nao_determinado",
                detalhe={"fonte": f.identidade, "rotulo": f.rotulo, "regra": f.nivel_origem},
            ))
        for v in f.versoes.values():
            doc_orig = next(
                (p.legislation_document_id for p in v.proveniencias
                 if p.legislation_document_id in plano.originais), None,
            )
            versao = FonteNormativaVersao(
                fonte_id=fonte.id, texto=v.texto, hash_texto=v.hash_texto,
                origem_ingestao=v.origem_ingestao, vigencia_estado=v.vigencia_estado,
                vigencia_inicio=v.vigencia_inicio, vigencia_fim=v.vigencia_fim,
                hash_original=plano.originais[doc_orig][0] if doc_orig else None,
                original_storage_key=originais_storage.get(doc_orig) if doc_orig else None,
            )
            session.add(versao)
            session.flush()
            contagem["versoes"] += 1
            for p in v.proveniencias:
                session.add(FonteNormativaProveniencia(
                    fonte_versao_id=versao.id, legislation_document_id=p.legislation_document_id,
                    source_ref=p.source_ref, documento_origem_rotulo=p.documento_origem_rotulo,
                    offset_inicio=p.offset_inicio, offset_fim=p.offset_fim,
                    pagina_inicio=p.pagina_inicio, pagina_fim=p.pagina_fim,
                    url_impressa=p.url_impressa, impresso_em=p.impresso_em,
                    sinal_fronteira=p.sinal_fronteira, motivos_revisao=p.motivos or None,
                    trecho_hash=p.trecho_hash,
                ))
                contagem["proveniencias"] += 1
                fronteira = [m for m in p.motivos if m in MOTIVOS_FRONTEIRA]
                if not f.determinada or fronteira:
                    session.add(TarefaRevisaoNormativa(
                        fonte_versao_id=versao.id, legislation_document_id=p.legislation_document_id,
                        tipo="identidade_nao_determinada" if not f.determinada else "fronteira_ambigua",
                        detalhe={
                            "rotulo": f.rotulo, "offset": [p.offset_inicio, p.offset_fim],
                            "paginas": [p.pagina_inicio, p.pagina_fim], "motivos": p.motivos,
                            "url_impressa": p.url_impressa,
                        },
                    ))
                    contagem["tarefas_fronteira_identidade"] += 1
            if not _buscavel(f):
                continue
            ordem = 0
            if v.trechos_legado is not None:
                disp = Dispositivo(
                    fonte_versao_id=versao.id, caminho=f"{f.rotulo[:260]}, texto integral",
                    tipo="preambulo", ordem=0, texto=v.texto,
                    hash=hash_texto_normalizado(v.texto),
                )
                session.add(disp)
                session.flush()
                for t, vetor in v.trechos_legado:
                    session.execute(text(
                        "INSERT INTO trecho_normativo (fonte_versao_id, dispositivo_id, ordem, cabecalho, "
                        "texto, tokens, embedding, embedding_model, content_hash) VALUES (:v, :d, :o, :c, :t, "
                        "0, CAST(:e AS vector), :m, :h)"
                    ), {"v": versao.id, "d": disp.id, "o": ordem, "c": disp.caminho[:300], "t": t,
                        "e": vetor, "m": modelo_embedding, "h": hashlib.sha256(t.encode()).hexdigest()})
                    ordem += 1
                    contagem["trechos_reaproveitados"] += 1
                continue
            for d in dispositivos_da_versao(f, v):
                pai = Dispositivo(
                    fonte_versao_id=versao.id, caminho=d.caminho(f.rotulo)[:300], tipo=d.tipo,
                    artigo=d.artigo, paragrafo=d.paragrafo, ordem=d.ordem, texto=d.texto, hash=d.hash,
                )
                session.add(pai)
                session.flush()
                contagem["dispositivos"] += 1
                for filho in d.filhos:
                    session.add(Dispositivo(
                        fonte_versao_id=versao.id, caminho=filho.caminho(f.rotulo, d)[:300],
                        tipo="paragrafo", artigo=d.artigo, paragrafo=filho.paragrafo,
                        parent_id=pai.id, ordem=filho.ordem, texto=filho.texto, hash=filho.hash,
                    ))
                    contagem["dispositivos"] += 1
                for t, n in trechos_do_dispositivo(d):
                    tid = session.execute(text(
                        "INSERT INTO trecho_normativo (fonte_versao_id, dispositivo_id, ordem, cabecalho, "
                        "texto, tokens, content_hash) VALUES (:v, :d, :o, :c, :t, :n, :h) RETURNING id"
                    ), {"v": versao.id, "d": pai.id, "o": ordem, "c": pai.caminho[:300], "t": t, "n": n,
                        "h": hashlib.sha256(t.encode()).hexdigest()}).scalar_one()
                    ordem += 1
                    fila_embed.append((tid, f"{pai.caminho}\n{t}"))
                    if len(fila_embed) >= lote:
                        _descarregar()
        # A sessão cresce a cada dispositivo e todo flush a percorre inteira — o custo
        # vira quadrático (medido: 100 fontes em 20 min). Daqui para frente só se usa
        # id, então a sessão é esvaziada a cada fonte (a fila de embedding guarda só
        # id e texto, não objeto ORM).
        session.flush()
        session.expunge_all()
        if i % 50 == 0:
            progresso(f"{i}/{len(plano.fontes)} fontes; {contagem['trechos_embarcados']} trechos embarcados")
    _descarregar()

    # A5 — documento de origem sem original disponível: uma tarefa por documento.
    docs_com_prov = {
        p.legislation_document_id
        for f in plano.fontes.values() for v in f.versoes.values() for p in v.proveniencias
        if p.legislation_document_id is not None
    }
    for doc_id in sorted(docs_com_prov - set(plano.originais)):
        session.add(TarefaRevisaoNormativa(
            legislation_document_id=doc_id, tipo="original_ausente",
            detalhe={"motivo": "bytes originais não localizados; sem hash do original a versão não "
                               "pode ser validada (A5)"},
        ))
        contagem["tarefas_original_ausente"] += 1
    semad = sum(
        1 for f in plano.fontes.values() for v in f.versoes.values()
        if v.origem_ingestao == "semad_knowledge_catalog"
    )
    if semad:
        session.add(TarefaRevisaoNormativa(
            tipo="original_ausente",
            detalhe={"motivo": "fontes SEMAD-GO existem só como chunk no legado; PDFs originais "
                               "não vinculados", "fontes": semad},
        ))
        contagem["tarefas_original_ausente"] += 1

    contagem["interpretacoes_ligadas"] = ligar_interpretacoes(session)
    session.flush()
    return dict(contagem)


# ---------------------------------------------------------------------------
# Interpretação → norma (emenda ao ADR-038 §6)
# ---------------------------------------------------------------------------

_RE_REF_NORMA = re.compile(
    r"\bart(?:igo)?s?\.?\s*(?P<art>\d+(?:\s*-\s*[A-Z]\b)?)\s*[º°o]?"
    r"(?:[^;\n]{0,40}?)\b(?:d[oa]|na|no)\s+"
    r"(?P<norma>(?:Lei\s+Complementar|Lei|Decreto(?:-Lei)?|Resolu[çc][ãa]o(?:\s+CONAMA)?|"
    r"Instru[çc][ãa]o\s+Normativa(?:\s+[A-Z]+)?|IN(?:\s+[A-Z]+)?)"
    r"(?:\s+(?:Federal|Estadual))?\s*(?:n[º°o.]*\s*)?(?P<num>\d[\d\.]*)"
    r"(?:\s*/\s*(?P<ano1>\d{4})|,?\s+de\s+(?:\d{1,2}\s+de\s+\w+\s+de\s+)?(?P<ano2>\d{4}))?)",
    re.I,
)


def referencias_a_normas(texto: str) -> list[tuple[str, str, str]]:
    """(artigo, identificador bruto, trecho) — só referência com norma NOMEADA.
    Referência sem norma nomeada não é ligada: supor 'a norma atual' seria
    inferência apresentada como leitura."""
    out = []
    for m in _RE_REF_NORMA.finditer(texto):
        ano = m.group("ano1") or m.group("ano2")
        if not ano:
            continue
        tipo = re.sub(r"\s+", " ", m.group("norma").split(m.group("num"))[0]).strip()
        tipo = re.sub(r"(?i)\s*(federal|estadual|n[º°o.]*)\s*$", "", tipo)
        ident = f"{tipo} {m.group('num')}/{ano}"
        art = re.sub(r"\s*-\s*", "-", m.group("art")).upper()
        out.append((art, ident, m.group(0)[:200]))
    return out


def ligar_interpretacoes(session: Session) -> int:
    """Liga cada interpretação às normas/dispositivos que ela cita pelo nome.

    Origem `extraida_do_texto`, status `bruto`: a curadoria confirma. Só liga a
    norma que EXISTE no catálogo — referência sem alvo não vira aresta.
    """
    alvos = {
        f.identidade: f.id
        for f in session.query(FonteNormativa).filter(FonteNormativa.nivel_autoridade == "norma")
    }
    interps = (
        session.query(FonteNormativa, FonteNormativaVersao)
        .join(FonteNormativaVersao, FonteNormativaVersao.fonte_id == FonteNormativa.id)
        .filter(FonteNormativa.nivel_autoridade == "interpretacao")
        .all()
    )
    criadas = 0
    vistos: set[tuple[int, int, str]] = set()
    for fonte, versao in interps:
        for art, ident_bruto, literal in referencias_a_normas(versao.texto):
            ident = identidade_de_identificador(
                ident_bruto, scope="federal" if fonte.ente == "br" else "estadual",
                uf=fonte.uf, agency=None,
            )
            if not ident.determinada:
                cab = identidade_de_cabecalho(ident_bruto, ente_padrao=fonte.ente)
                ident = cab if cab and cab.determinada else ident
            alvo = alvos.get(ident.chave)
            if alvo is None:
                continue
            chave = (fonte.id, alvo, art)
            if chave in vistos:
                continue
            vistos.add(chave)
            session.add(InterpretacaoNorma(
                interpretacao_fonte_id=fonte.id, norma_fonte_id=alvo, artigo=art,
                citacao_literal=literal, origem="extraida_do_texto",
            ))
            criadas += 1
    session.flush()
    return criadas


def resumo_relatorio(plano: Plano) -> list[str]:
    """Linhas do relatório de dry-run (sem texto de norma, só contagens e cabeçalhos)."""
    linhas = [f"{k}: {v}" for k, v in plano.resumo().items()]
    for r in plano.relatorio_coletaneas:
        linhas.append(
            f"[{r['documento_id']}] {r['coletanea']} ({r['uf']}): {r['segmentos']} segmentos "
            f"{r['por_sinal']} | identidade fechada {r['identidade_determinada']} | motivos {r['motivos']}"
        )
    return linhas


def ligar_originais_por_nome(
    session: Session, *, raizes: Iterable[pathlib.Path],
    guardar: Callable[[pathlib.Path, str], str],
) -> dict:
    """A5 para as fontes SEMAD que só existiam como chunk: o `source_ref` é o nome do
    arquivo; achado nas raízes (ex.: MANUAIS_SEMAD.rar da Ísis, INS-004), o original
    é guardado e a versão ganha hash e chave. Só preenche o que está vazio — hash de
    original nunca é sobrescrito (divergência é caso da conferência, não daqui).
    Resolve a tarefa agregada de `original_ausente` só quando não sobra nenhuma."""
    import unicodedata  # noqa: PLC0415

    def _n(s: str) -> str:
        return unicodedata.normalize("NFC", s.strip())

    arquivos: dict[str, pathlib.Path] = {}
    for raiz in raizes:
        for p in pathlib.Path(raiz).rglob("*"):
            if p.is_file():
                arquivos.setdefault(_n(p.name), p)
    rows = session.execute(text(
        "SELECT DISTINCT v.id, p.source_ref FROM fonte_normativa_versao v "
        "JOIN fonte_normativa_proveniencia p ON p.fonte_versao_id = v.id "
        "WHERE p.source_ref IS NOT NULL AND v.hash_original IS NULL"
    )).all()
    ligadas = 0
    for versao_id, ref in rows:
        caminho = arquivos.get(_n(ref))
        if caminho is None:
            continue
        sha = sha256_arquivo(caminho)
        chave = guardar(caminho, sha)
        session.execute(text(
            "UPDATE fonte_normativa_versao SET hash_original = :h, original_storage_key = :k "
            "WHERE id = :v AND hash_original IS NULL"
        ), {"h": sha, "k": chave, "v": versao_id})
        ligadas += 1
    restantes = session.execute(text(
        "SELECT count(DISTINCT v.id) FROM fonte_normativa_versao v JOIN fonte_normativa_proveniencia p "
        "ON p.fonte_versao_id = v.id WHERE p.source_ref IS NOT NULL AND v.hash_original IS NULL"
    )).scalar_one()
    session.execute(text(
        "UPDATE tarefa_revisao_normativa SET detalhe = jsonb_set(detalhe, '{fontes}', to_jsonb(CAST(:n AS int))) "
        "WHERE tipo = 'original_ausente' AND legislation_document_id IS NULL AND resolvida_em IS NULL"
    ), {"n": restantes})
    session.flush()
    return {"candidatas": len(rows), "ligadas": ligadas, "ainda_sem_original": restantes}


# ---------------------------------------------------------------------------
# Correção de corte no lugar (dívida #274)
# ---------------------------------------------------------------------------

# Quem aponta para um dispositivo por ID fora do próprio catálogo. `rota_passos` é
# SET NULL: apagar o dispositivo zeraria o fundamento de um passo validado em silêncio.
REFERENCIAS_EXTERNAS = (
    ("avaliacao_regra", "fundamento_dispositivo_id"),
    ("rota_passos", "fundamento_dispositivo_id"),
)


class DispositivoCitado(RuntimeError):
    """Um dispositivo que o corte novo remove está citado por ID fora do catálogo."""


@dataclass
class Recorte:
    versao_id: int
    mantidos: int = 0
    saem: list[int] = field(default_factory=list)
    entram: list[str] = field(default_factory=list)
    trechos_removidos: int = 0
    trechos_novos: int = 0


def _extraidos_planos(texto: str) -> list[tuple[DispositivoExtraido, DispositivoExtraido | None]]:
    out: list[tuple[DispositivoExtraido, DispositivoExtraido | None]] = []
    for d in extrair_dispositivos(texto):
        out.append((d, None))
        out.extend((f, d) for f in d.filhos)
    return out


def reaplicar_dispositivos(
    session: Session, versao_id: int, *, rotulo: str, texto: str,
    embed: Callable[[list[str]], list[list[float]]] | None, modelo_embedding: str | None,
    aplicar: bool = False,
) -> Recorte:
    """Recorta os dispositivos de UMA versão com a regra atual, preservando IDs.

    Dispositivo com o mesmo caminho e o mesmo hash continua com o mesmo ID (e os
    mesmos trechos e vetores); só ``ordem`` e ``parent_id`` são atualizados. O que sai é
    apagado com seus trechos; o que entra é criado, cortado em trechos e embarcado.
    Sem ``aplicar``, só mede. Recusa (``DispositivoCitado``) se algo que sai estiver
    citado pelo motor ou pela Rota — isso é decisão de curadoria, não de corte.
    """
    atuais = session.execute(text(
        "SELECT id, caminho, hash, parent_id FROM dispositivo WHERE fonte_versao_id = :v"
    ), {"v": versao_id}).all()
    por_chave = {(r.caminho, r.hash): r for r in atuais}
    novos = _extraidos_planos(texto)
    chaves_novas = {(d.caminho(rotulo, pai)[:300], d.hash) for d, pai in novos}
    rec = Recorte(versao_id=versao_id)
    rec.saem = sorted(r.id for k, r in por_chave.items() if k not in chaves_novas)
    rec.entram = [d.caminho(rotulo, pai)[:300] for d, pai in novos
                  if (d.caminho(rotulo, pai)[:300], d.hash) not in por_chave]
    rec.mantidos = len(novos) - len(rec.entram)
    if rec.saem:
        for tabela, coluna in REFERENCIAS_EXTERNAS:
            citados = session.execute(text(
                f"SELECT DISTINCT {coluna} FROM {tabela} WHERE {coluna} = ANY(:ids)"  # noqa: S608
            ), {"ids": rec.saem}).scalars().all()
            if citados:
                raise DispositivoCitado(f"versão {versao_id}: dispositivos {sorted(citados)} citados em {tabela}")
    if not aplicar or (not rec.saem and not rec.entram):
        return rec
    if embed is None or not modelo_embedding:
        raise ValueError("aplicar exige embed e modelo_embedding")

    if rec.saem:
        rec.trechos_removidos = session.execute(text(
            "DELETE FROM trecho_normativo WHERE dispositivo_id = ANY(:ids)"), {"ids": rec.saem}).rowcount
        # parent_id é RESTRICT: solta quem fica e aponta para quem sai (é refeito abaixo),
        # depois apaga filhos antes dos pais.
        session.execute(text("UPDATE dispositivo SET parent_id = NULL WHERE parent_id = ANY(:ids) "
                             "AND NOT (id = ANY(:ids))"), {"ids": rec.saem})
        session.execute(text("DELETE FROM dispositivo WHERE id = ANY(:ids) AND parent_id IS NOT NULL"),
                        {"ids": rec.saem})
        session.execute(text("DELETE FROM dispositivo WHERE id = ANY(:ids)"), {"ids": rec.saem})

    ordem_trecho = session.execute(text(
        "SELECT coalesce(max(ordem), -1) + 1 FROM trecho_normativo WHERE fonte_versao_id = :v"
    ), {"v": versao_id}).scalar_one()
    ids: dict[tuple[str, str], int] = {k: r.id for k, r in por_chave.items() if k in chaves_novas}
    fila: list[tuple[int, str]] = []
    for d, pai in novos:
        chave = (d.caminho(rotulo, pai)[:300], d.hash)
        pai_id = ids[(pai.caminho(rotulo)[:300], pai.hash)] if pai is not None else None
        if chave in ids:
            session.execute(text("UPDATE dispositivo SET ordem = :o, parent_id = :p WHERE id = :id"),
                            {"o": d.ordem, "p": pai_id, "id": ids[chave]})
            continue
        ids[chave] = session.execute(text(
            "INSERT INTO dispositivo (fonte_versao_id, caminho, tipo, artigo, paragrafo, parent_id, ordem, texto, "
            "hash) VALUES (:v, :c, :t, :a, :p, :pid, :o, :x, :h) RETURNING id"
        ), {"v": versao_id, "c": chave[0], "t": d.tipo, "a": d.artigo if pai is None else pai.artigo,
            "p": d.paragrafo, "pid": pai_id, "o": d.ordem, "x": d.texto, "h": d.hash}).scalar_one()
        if pai is not None:
            continue  # trecho de busca é do artigo (pai), como em `aplicar`
        for t, n in trechos_do_dispositivo(d):
            tid = session.execute(text(
                "INSERT INTO trecho_normativo (fonte_versao_id, dispositivo_id, ordem, cabecalho, texto, tokens, "
                "content_hash) VALUES (:v, :d, :o, :c, :t, :n, :h) RETURNING id"
            ), {"v": versao_id, "d": ids[chave], "o": ordem_trecho, "c": chave[0], "t": t, "n": n,
                "h": hashlib.sha256(t.encode()).hexdigest()}).scalar_one()
            ordem_trecho += 1
            fila.append((tid, f"{chave[0]}\n{t}"))
    if fila:
        vetores = embed([t for _, t in fila])
        if len(vetores) != len(fila):
            raise RuntimeError("embedding devolveu quantidade diferente da pedida")
        for (tid, _), vec in zip(fila, vetores, strict=True):
            session.execute(text(
                "UPDATE trecho_normativo SET embedding = CAST(:e AS vector), embedding_model = :m WHERE id = :id"
            ), {"e": _vetor_literal(vec), "m": modelo_embedding, "id": tid})
    rec.trechos_novos = len(fila)
    session.flush()
    return rec
