"""Fechamento comercial (ADR-074): Redator pré-contratação, orçamento e métodos do tenant.

- **Caso** (`/processes/{id}/comercial/...`): gerar e ler o relatório preliminar e a
  especificação de escopo, revisar; gerar e ler o orçamento, escolher método/quantidade de um
  passo (gera versão nova), revisar.
- **Tenant** (`/comercial/metodos`): métodos e preços, versionados.

Todo usuário interno do tenant. Nada aqui chama LLM, muda etapa ou regenera sozinho: a
atualidade é devolvida na leitura, com os motivos.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.comercial import Orcamento, OrcamentoMetodo, RedacaoComercial
from app.models.process import Process
from app.models.user import User
from app.services.comercial import ComercialError
from app.services.comercial import base as base_mod
from app.services.comercial import orcamento as orcamento_mod
from app.services.comercial import redator as redator_mod

process_router = APIRouter()
tenant_router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]


def _processo(db: Session, process_id: int, tenant_id: int) -> Process:
    p = db.query(Process).filter(Process.id == process_id, Process.tenant_id == tenant_id,
                                 Process.deleted_at.is_(None)).first()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processo não encontrado")
    return p


def _recusa(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


def _gravar(db: Session, fn):
    """Executa e comita; versão concorrente (UNIQUE da versão) vira 409, não 500."""
    try:
        out = fn()
        db.commit()
        return out
    except ComercialError as exc:
        # Sem commit, a sessão da requisição descarta o que tiver sido escrito.
        raise _recusa(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Versão gerada por outra sessão; recarregue.") from exc


def _dinheiro(v) -> str | None:
    return None if v is None else f"{Decimal(v):.2f}"


def _revisao(a) -> dict:
    return {"estado_revisao": a.estado_revisao, "revisado_por_id": a.revisado_por_id, "revisado_em": a.revisado_em,
            "justificativa": a.justificativa}


def _redacao_out(db: Session, r: RedacaoComercial) -> dict:
    return {"id": r.id, "tipo": r.tipo, "versao": r.versao, "rota_id": r.rota_id,
            "execucao_motor_id": r.execucao_motor_id, "criado_por_id": r.criado_por_id, "created_at": r.created_at,
            "superada_em": r.superada_em, **_revisao(r), "atualidade": base_mod.atualidade(db, r),
            "conteudo": r.conteudo}


def _orcamento_out(db: Session, o: Orcamento) -> dict:
    return {"id": o.id, "versao": o.versao, "rota_id": o.rota_id, "escopo_id": o.escopo_id,
            "total": _dinheiro(o.total), "fora": o.fora, "ressalvas": o.ressalvas, "created_at": o.created_at,
            "criado_por_id": o.criado_por_id, "superada_em": o.superada_em, **_revisao(o),
            "atualidade": base_mod.atualidade(db, o),
            "itens": [{"id": i.id, "ordem": i.ordem, "rota_passo_id": i.rota_passo_id, "descricao": i.descricao,
                       "fundamento": i.fundamento, "metodo": {"id": i.metodo_id, "codigo": i.metodo.codigo,
                                                              "versao": i.metodo.versao, "nome": i.metodo.nome},
                       "escolha": i.escolha, "unidade": i.unidade, "quantidade": _dinheiro(i.quantidade),
                       "valor_unitario": _dinheiro(i.valor_unitario), "total": _dinheiro(i.total),
                       "calculo": i.calculo} for i in o.itens]}


def _metodo_out(m: OrcamentoMetodo) -> dict:
    return {"id": m.id, "codigo": m.codigo, "versao": m.versao, "nome": m.nome, "unidade": m.unidade,
            "valor_unitario": _dinheiro(m.valor_unitario), "quantidade_padrao": _dinheiro(m.quantidade_padrao),
            "rule_ids": list(m.rule_ids or []), "padrao": m.padrao, "ativo": m.ativo, "created_at": m.created_at}


class RevisaoIn(BaseModel):
    acao: Literal["aprovar", "rejeitar"]
    justificativa: str = Field(min_length=1)


class MetodoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=60)
    nome: str = Field(min_length=1, max_length=200)
    unidade: Literal["hora", "fixo", "unidade"]
    valor_unitario: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    quantidade_padrao: Decimal = Field(default=Decimal(1), gt=0, max_digits=10, decimal_places=2)
    rule_ids: list[str] = Field(default_factory=list)
    padrao: bool = False
    ativo: bool = True


class EscolhaIn(BaseModel):
    metodo_codigo: str | None = None
    quantidade: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)


# ---------------------------------------------------------------------------
# Redator
# ---------------------------------------------------------------------------

@process_router.post("/{process_id}/comercial/redacao", status_code=status.HTTP_201_CREATED)
def gerar_redacao(process_id: int, db: Db, user: UserDep) -> dict:
    process = _processo(db, process_id, user.tenant_id)
    rel, esc = _gravar(db, lambda: redator_mod.gerar(db, process=process, tenant_id=user.tenant_id,
                                                        user_id=user.id))
    return {"relatorio_preliminar": _redacao_out(db, rel), "especificacao_escopo": _redacao_out(db, esc)}


@process_router.get("/{process_id}/comercial/redacao")
def ler_redacao(process_id: int, db: Db, user: UserDep) -> dict:
    _processo(db, process_id, user.tenant_id)
    out = {}
    for tipo in ("relatorio_preliminar", "especificacao_escopo"):
        r = base_mod.ultima_redacao(db, user.tenant_id, process_id, tipo)
        out[tipo] = _redacao_out(db, r) if r else None
    out["versoes"] = [{"id": r.id, "tipo": r.tipo, "versao": r.versao, "estado_revisao": r.estado_revisao,
                       "superada_em": r.superada_em, "created_at": r.created_at}
                      for r in db.query(RedacaoComercial).filter(RedacaoComercial.tenant_id == user.tenant_id,
                                                                 RedacaoComercial.process_id == process_id)
                      .order_by(RedacaoComercial.tipo, RedacaoComercial.versao)]
    return out


@process_router.post("/{process_id}/comercial/redacao/{redacao_id}/revisar")
def revisar_redacao(process_id: int, redacao_id: int, body: RevisaoIn, db: Db, user: UserDep) -> dict:
    _processo(db, process_id, user.tenant_id)
    r = db.query(RedacaoComercial).filter(RedacaoComercial.id == redacao_id, RedacaoComercial.tenant_id == user.tenant_id,
                                          RedacaoComercial.process_id == process_id).first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    _gravar(db, lambda: orcamento_mod.revisar(db, r, user_id=user.id, acao=body.acao,
                                              justificativa=body.justificativa))
    return _redacao_out(db, r)


# ---------------------------------------------------------------------------
# Orçamento
# ---------------------------------------------------------------------------

@process_router.post("/{process_id}/comercial/orcamento", status_code=status.HTTP_201_CREATED)
def gerar_orcamento(process_id: int, db: Db, user: UserDep) -> dict:
    process = _processo(db, process_id, user.tenant_id)
    o = _gravar(db, lambda: orcamento_mod.gerar(db, process=process, tenant_id=user.tenant_id, user_id=user.id))
    return _orcamento_out(db, o)


@process_router.get("/{process_id}/comercial/orcamento")
def ler_orcamento(process_id: int, db: Db, user: UserDep) -> dict:
    _processo(db, process_id, user.tenant_id)
    o = base_mod.ultimo_orcamento(db, user.tenant_id, process_id)
    versoes = [{"id": x.id, "versao": x.versao, "total": _dinheiro(x.total), "estado_revisao": x.estado_revisao,
                "superada_em": x.superada_em, "created_at": x.created_at}
               for x in db.query(Orcamento).filter(Orcamento.tenant_id == user.tenant_id,
                                                   Orcamento.process_id == process_id).order_by(Orcamento.versao)]
    return {"orcamento": _orcamento_out(db, o) if o else None, "versoes": versoes}


@process_router.patch("/{process_id}/comercial/orcamento/passos/{passo_id}", status_code=status.HTTP_201_CREATED)
def escolher_no_passo(process_id: int, passo_id: int, body: EscolhaIn, db: Db, user: UserDep) -> dict:
    """Escolha do consultor para um passo; gera a versão seguinte do orçamento."""
    process = _processo(db, process_id, user.tenant_id)

    def fazer():
        orcamento_mod.escolher(db, process=process, tenant_id=user.tenant_id, user_id=user.id,
                               rota_passo_id=passo_id, metodo_codigo=body.metodo_codigo, quantidade=body.quantidade)
        return orcamento_mod.gerar(db, process=process, tenant_id=user.tenant_id, user_id=user.id)
    try:
        o = _gravar(db, fazer)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _orcamento_out(db, o)


@process_router.post("/{process_id}/comercial/orcamento/{orcamento_id}/revisar")
def revisar_orcamento(process_id: int, orcamento_id: int, body: RevisaoIn, db: Db, user: UserDep) -> dict:
    _processo(db, process_id, user.tenant_id)
    o = db.query(Orcamento).filter(Orcamento.id == orcamento_id, Orcamento.tenant_id == user.tenant_id,
                                   Orcamento.process_id == process_id).first()
    if o is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Orçamento não encontrado")
    _gravar(db, lambda: orcamento_mod.revisar(db, o, user_id=user.id, acao=body.acao,
                                              justificativa=body.justificativa))
    return _orcamento_out(db, o)


# ---------------------------------------------------------------------------
# Métodos e preços do tenant
# ---------------------------------------------------------------------------

@tenant_router.get("/metodos")
def listar_metodos(db: Db, user: UserDep) -> dict:
    todas = (db.query(OrcamentoMetodo).filter(OrcamentoMetodo.tenant_id == user.tenant_id)
             .order_by(OrcamentoMetodo.codigo, OrcamentoMetodo.versao).all())
    correntes = orcamento_mod.metodos_correntes(db, user.tenant_id)
    return {"correntes": [_metodo_out(m) for m in correntes.values()], "versoes": [_metodo_out(m) for m in todas]}


@tenant_router.post("/metodos", status_code=status.HTTP_201_CREATED)
def criar_metodo(body: MetodoIn, db: Db, user: UserDep) -> dict:
    m = _gravar(db, lambda: orcamento_mod.criar_versao_metodo(
        db, tenant_id=user.tenant_id, user_id=user.id, codigo=body.codigo, nome=body.nome, unidade=body.unidade,
        valor_unitario=body.valor_unitario, quantidade_padrao=body.quantidade_padrao, rule_ids=body.rule_ids,
        padrao=body.padrao, ativo=body.ativo))
    return _metodo_out(m)
