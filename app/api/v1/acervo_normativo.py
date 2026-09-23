"""Acervo normativo (ADR-075): recuperação, citação por ID e curadoria.

Leitura é de todo usuário interno (A2: o corpus é leitura para o tenant).
Escrita — propor, validar, devolver, lote por coletânea — exige papel de
curadoria na área da fonte. Conceder papel é de superusuário.

Nada aqui religa a Legislação: o agente continua desligado até as sondas verdes
(decisão 6). Estes endpoints expõem o contrato para percurso e conferência.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.user import User
from app.models.zona_normativa import (
    Dispositivo,
    FonteNormativa,
    FonteNormativaProveniencia,
    FonteNormativaVersao,
    PapelCuradoria,
    TarefaRevisaoNormativa,
    ValidacaoNorma,
)
from app.services.zona_normativa import citacao, curadoria, recuperacao

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]


def _negar(exc: Exception) -> HTTPException:
    # Sem rollback aqui: o serviço valida antes de escrever, e a sessão da
    # requisição fecha sem commit.
    if isinstance(exc, curadoria.CuradoriaNegada):
        return HTTPException(403, str(exc))
    return HTTPException(422, str(exc))


# ---------------------------------------------------------------------------
# Recuperação e citação
# ---------------------------------------------------------------------------

class RecuperarRequest(BaseModel):
    pergunta: str = ""
    uso: Literal["peca", "interno", "descoberta"]
    data_referencia: date | None = None
    objetivo: str | None = None
    esferas: list[Literal["federal", "estadual", "municipal"]] = Field(default_factory=list)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    norma: str | None = None
    artigo: str | None = None
    limite: int = Field(default=5, ge=1, le=20)


def _embed_query(pergunta: str) -> list[float]:
    from app.services.embeddings import embed_text  # noqa: PLC0415

    return embed_text(pergunta, task_type="RETRIEVAL_QUERY")


def _modelo() -> str:
    from app.services.embeddings import current_model  # noqa: PLC0415

    return current_model()


@router.post("/recuperar")
def recuperar(body: RecuperarRequest, db: Db, user: UserDep):
    ctx = recuperacao.Contexto(
        pergunta=body.pergunta, uso=body.uso, data_referencia=body.data_referencia,
        objetivo=body.objetivo, esferas=tuple(body.esferas), uf=body.uf.upper() if body.uf else None,
        tenant_id=user.tenant_id, norma=body.norma, artigo=body.artigo, limite=body.limite,
    )
    return recuperacao.recuperar(db, ctx, embed_query=_embed_query, modelo=_modelo()).como_dict()


class CitacaoIn(BaseModel):
    fonte_versao_id: int
    dispositivo: str
    localizador: str | None = None


class AfirmacaoIn(BaseModel):
    texto: str
    citacoes: list[CitacaoIn] = Field(default_factory=list)


class VerificarRequest(BaseModel):
    destino: Literal["peca", "interno", "descoberta"]
    data_referencia: date
    envelope_versoes: list[int]
    afirmacoes: list[AfirmacaoIn]


@router.post("/citacoes/verificar")
def verificar_citacoes(body: VerificarRequest, db: Db, user: UserDep):  # noqa: ARG001
    env = citacao.carregar_envelope(db, set(body.envelope_versoes))
    ver = citacao.verificar(
        db,
        [citacao.Afirmacao(a.texto, [citacao.Citacao(**c.model_dump()) for c in a.citacoes])
         for a in body.afirmacoes],
        env, destino=body.destino, data_referencia=body.data_referencia,
    )
    return {"emitir": ver.emitir, "falhas": [f.__dict__ for f in ver.falhas]}


# ---------------------------------------------------------------------------
# Leitura do acervo (ficha da fonte, coletânea desmembrada, tarefas)
# ---------------------------------------------------------------------------

@router.get("/fontes")
def listar_fontes(
    db: Db, user: UserDep,  # noqa: ARG001
    nivel: str | None = None, status: str | None = None, uf: str | None = None,
    q: str | None = None, limite: int = Query(50, ge=1, le=500),
):
    sql = (
        "SELECT f.id, f.identidade, f.rotulo, f.nivel_autoridade, f.nivel_origem, f.uf, f.esfera, "
        "f.identidade_determinada, array_agg(DISTINCT v.status_validacao) AS status "
        "FROM fonte_normativa f JOIN fonte_normativa_versao v ON v.fonte_id = f.id "
        "WHERE (f.tenant_id IS NULL OR f.tenant_id = :t)"
    )
    params: dict = {"t": user.tenant_id, "lim": limite}
    if nivel:
        sql += " AND f.nivel_autoridade = :nivel"
        params["nivel"] = nivel
    if status:
        sql += " AND v.status_validacao = :status"
        params["status"] = status
    if uf:
        sql += " AND f.uf = :uf"
        params["uf"] = uf.upper()
    if q:
        sql += " AND (f.rotulo ILIKE :q OR f.identidade ILIKE :q)"
        params["q"] = f"%{q}%"
    sql += " GROUP BY f.id ORDER BY f.rotulo LIMIT :lim"
    return [dict(r._mapping) for r in db.execute(text(sql), params)]


@router.get("/fontes/{fonte_id}")
def ficha_da_fonte(fonte_id: int, db: Db, user: UserDep):
    f = db.get(FonteNormativa, fonte_id)
    if f is None or (f.tenant_id is not None and f.tenant_id != user.tenant_id):
        raise HTTPException(404, "Fonte não encontrada")
    versoes = []
    for v in db.query(FonteNormativaVersao).filter_by(fonte_id=f.id).order_by(FonteNormativaVersao.id):
        provs = db.query(FonteNormativaProveniencia).filter_by(fonte_versao_id=v.id).all()
        eventos = db.query(ValidacaoNorma).filter_by(fonte_versao_id=v.id).order_by(ValidacaoNorma.id).all()
        n_disp = db.query(Dispositivo).filter_by(fonte_versao_id=v.id).count()
        versoes.append({
            "id": v.id, "status_validacao": v.status_validacao, "vigencia_estado": v.vigencia_estado,
            "vigencia_inicio": v.vigencia_inicio, "vigencia_fim": v.vigencia_fim,
            "hash_texto": v.hash_texto, "hash_original": v.hash_original,
            "original_storage_key": v.original_storage_key, "original_conferido_em": v.original_conferido_em,
            "bloqueio_citacao": v.bloqueio_citacao, "origem_ingestao": v.origem_ingestao,
            "dispositivos": n_disp, "abertura": v.texto[:600],
            "proveniencias": [{
                "legislation_document_id": p.legislation_document_id, "source_ref": p.source_ref,
                "documento_origem": p.documento_origem_rotulo, "paginas": [p.pagina_inicio, p.pagina_fim],
                "offset": [p.offset_inicio, p.offset_fim], "url_impressa": p.url_impressa,
                "impresso_em": p.impresso_em, "sinal_fronteira": p.sinal_fronteira,
                "motivos_revisao": p.motivos_revisao,
            } for p in provs],
            "validacoes": [{
                "id": e.id, "acao": e.acao, "de": e.status_de, "para": e.status_para,
                "validador_id": e.validador_id, "papel": e.papel_na_curadoria, "area": e.area,
                "decisao": e.decisao, "nota": e.nota, "registrado_em": e.registrado_em,
                "hash_evento": e.hash_evento,
            } for e in eventos],
        })
    return {
        "id": f.id, "identidade": f.identidade, "identidade_determinada": f.identidade_determinada,
        "rotulo": f.rotulo, "titulo": f.titulo, "nivel_autoridade": f.nivel_autoridade,
        "nivel_origem": f.nivel_origem, "esfera": f.esfera, "uf": f.uf, "objetivos": f.objetivos,
        "objetivos_origem": f.objetivos_origem, "area_de_curadoria": curadoria.area_da_fonte(f),
        "versoes": versoes,
    }


@router.get("/coletaneas/{documento_id}")
def coletanea_desmembrada(documento_id: int, db: Db, user: UserDep):  # noqa: ARG001
    """Os atos que saíram de uma coletânea — a tela da validação em lote (§4)."""
    rows = db.execute(text(
        "SELECT p.fonte_versao_id, p.pagina_inicio, p.pagina_fim, p.offset_inicio, p.offset_fim, "
        "p.url_impressa, p.sinal_fronteira, p.motivos_revisao, f.id AS fonte_id, f.rotulo, f.identidade, "
        "f.identidade_determinada, f.nivel_autoridade, v.status_validacao, length(v.texto) AS caracteres "
        "FROM fonte_normativa_proveniencia p JOIN fonte_normativa_versao v ON v.id = p.fonte_versao_id "
        "JOIN fonte_normativa f ON f.id = v.fonte_id WHERE p.legislation_document_id = :d "
        "ORDER BY p.offset_inicio NULLS FIRST"
    ), {"d": documento_id}).all()
    if not rows:
        raise HTTPException(404, "Documento de origem sem atos no catálogo")
    return {"documento_id": documento_id, "atos": [dict(r._mapping) for r in rows]}


@router.get("/tarefas")
def tarefas(db: Db, user: UserDep, tipo: str | None = None, limite: int = Query(100, ge=1, le=1000)):  # noqa: ARG001
    q = db.query(TarefaRevisaoNormativa).filter(TarefaRevisaoNormativa.resolvida_em.is_(None))
    if tipo:
        q = q.filter(TarefaRevisaoNormativa.tipo == tipo)
    contagem = dict(db.execute(text(
        "SELECT tipo, count(*) FROM tarefa_revisao_normativa WHERE resolvida_em IS NULL GROUP BY tipo"
    )).all())
    return {"abertas_por_tipo": contagem, "tarefas": [{
        "id": t.id, "tipo": t.tipo, "fonte_versao_id": t.fonte_versao_id,
        "legislation_document_id": t.legislation_document_id, "detalhe": t.detalhe, "aberta_em": t.aberta_em,
    } for t in q.order_by(TarefaRevisaoNormativa.id).limit(limite)]}


@router.get("/cadeia")
def cadeia(db: Db, user: UserDep):  # noqa: ARG001
    return curadoria.verificar_cadeia(db)


# ---------------------------------------------------------------------------
# Escrita (curadoria)
# ---------------------------------------------------------------------------

class ProporRequest(BaseModel):
    url_oficial: str
    texto_conferido_por: Literal["hash", "validation_keyword"]
    validation_keyword: str | None = None
    vigencia: Literal["vigente", "revogada", "nao_sei"]
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    nota: str = Field(min_length=1)


class NotaRequest(BaseModel):
    nota: str = Field(min_length=1)


class LoteRequest(BaseModel):
    nota: str = Field(min_length=1)
    excluir_versoes: list[int] = Field(default_factory=list)


def _evento(e: ValidacaoNorma) -> dict:
    return {"id": e.id, "acao": e.acao, "de": e.status_de, "para": e.status_para,
            "hash_evento": e.hash_evento, "hash_anterior": e.hash_anterior}


@router.post("/versoes/{versao_id}/propor")
def propor(versao_id: int, body: ProporRequest, db: Db, user: UserDep):
    try:
        ev = curadoria.propor(db, versao_id=versao_id, user=user, **body.model_dump())
    except (curadoria.CuradoriaNegada, curadoria.TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return _evento(ev)


@router.post("/versoes/{versao_id}/validar")
def validar(versao_id: int, body: NotaRequest, db: Db, user: UserDep):
    try:
        ev = curadoria.validar(db, versao_id=versao_id, user=user, nota=body.nota)
    except (curadoria.CuradoriaNegada, curadoria.TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return _evento(ev)


@router.post("/versoes/{versao_id}/devolver")
def devolver(versao_id: int, body: NotaRequest, db: Db, user: UserDep):
    try:
        ev = curadoria.devolver(db, versao_id=versao_id, user=user, nota=body.nota)
    except (curadoria.CuradoriaNegada, curadoria.TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return _evento(ev)


@router.post("/coletaneas/{documento_id}/propor-lote")
def propor_lote(documento_id: int, body: LoteRequest, db: Db, user: UserDep):
    try:
        out = curadoria.propor_lote_coletanea(
            db, legislation_document_id=documento_id, user=user, nota=body.nota,
            excluir_versoes=frozenset(body.excluir_versoes),
        )
    except (curadoria.CuradoriaNegada, curadoria.TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return out


@router.post("/coletaneas/{documento_id}/validar-lote")
def validar_lote(documento_id: int, body: LoteRequest, db: Db, user: UserDep):
    try:
        out = curadoria.validar_lote_coletanea(
            db, legislation_document_id=documento_id, user=user, nota=body.nota,
            excluir_versoes=frozenset(body.excluir_versoes),
        )
    except (curadoria.CuradoriaNegada, curadoria.TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return out


class ConcederRequest(BaseModel):
    user_id: int
    papel: Literal["validar_fonte_normativa", "curar_corpus", "homologar_regra"]
    area: str = Field(min_length=1, max_length=20)
    motivo: str | None = None


@router.post("/curadores")
def conceder(body: ConcederRequest, db: Db, user: UserDep):
    alvo = db.get(User, body.user_id)
    if alvo is None or alvo.tenant_id != user.tenant_id:
        raise HTTPException(404, "Usuário não encontrado")
    try:
        p = curadoria.conceder_papel(db, concedente=user, **body.model_dump())
    except (curadoria.CuradoriaNegada, curadoria.TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return {"id": p.id, "user_id": p.user_id, "papel": p.papel, "area": p.area}


@router.get("/curadores")
def listar_curadores(db: Db, user: UserDep):
    rows = (
        db.query(PapelCuradoria, User)
        .join(User, User.id == PapelCuradoria.user_id)
        .filter(User.tenant_id == user.tenant_id, PapelCuradoria.revogado_em.is_(None))
        .all()
    )
    return [{"id": p.id, "user_id": u.id, "email": u.email, "papel": p.papel, "area": p.area,
             "concedido_em": p.concedido_em} for p, u in rows]


@router.delete("/curadores/{papel_id}")
def revogar(papel_id: int, db: Db, user: UserDep, motivo: str = Query(min_length=1)):
    p = db.get(PapelCuradoria, papel_id)
    alvo = db.get(User, p.user_id) if p else None
    if p is None or alvo is None or alvo.tenant_id != user.tenant_id:
        raise HTTPException(404, "Papel não encontrado")
    try:
        curadoria.revogar_papel(db, concedente=user, papel_id=papel_id, motivo=motivo)
    except (curadoria.CuradoriaNegada, curadoria.TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return {"revogado": papel_id}
