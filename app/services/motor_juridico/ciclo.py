"""Ciclo de vida das regras e dos conjuntos (ADR-073 §10).

- `regra_versao`: ``rascunho → homologada`` por quem tem o papel ``homologar_regra`` na
  área da regra (UF da aplicabilidade, ou ``federal``). Superusuário concede o papel, não
  o tem por ser superusuário (mesma tabela e mesma regra do A2).
- `conjunto_regras`: ``rascunho → publicado → ativo``. Publicar exige TODAS as versões
  homologadas e a condição válida de novo. Ativar desativa o ativo do mesmo escopo;
  rollback é ativar o anterior.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.motor_juridico import ConjuntoRegras, ConjuntoRegrasItem, RegraVersao
from app.models.user import User
from app.services.motor_juridico.importador import validar_efeitos
from app.services.motor_juridico.linguagem import validar_aplicabilidade, validar_condicao
from app.services.zona_normativa.curadoria import TransicaoInvalida, exigir_papel

PAPEL = "homologar_regra"


def area_da_regra(rv: RegraVersao) -> str:
    ufs = (rv.aplicabilidade or {}).get("ufs") or []
    return ufs[0].upper() if len(ufs) == 1 else "federal"


def _motivos_de_recusa(rv: RegraVersao) -> list[str]:
    return (validar_aplicabilidade(rv.aplicabilidade) + validar_condicao(rv.condicao)
            + validar_efeitos(rv.consequencia))


def homologar(session: Session, *, user: User, regra_versao_id: int, nota: str) -> RegraVersao:
    rv = session.get(RegraVersao, regra_versao_id)
    if rv is None:
        raise TransicaoInvalida("versão de regra inexistente")
    exigir_papel(session, user, PAPEL, area_da_regra(rv))
    if rv.estado != "rascunho":
        raise TransicaoInvalida(f"versão {rv.id} está {rv.estado}; só rascunho se homologa")
    if not (nota or "").strip():
        raise TransicaoInvalida("homologação exige nota")
    if motivos := _motivos_de_recusa(rv):
        raise TransicaoInvalida(f"regra recusada: {motivos}")
    rv.estado = "homologada"
    rv.homologada_por_id = user.id
    rv.homologada_em = datetime.now(UTC)
    rv.nota_homologacao = nota.strip()
    session.flush()
    return rv


def criar_conjunto(
    session: Session, *, nome: str, regra_versao_ids: list[int], tenant_id: int | None = None
) -> ConjuntoRegras:
    if not regra_versao_ids:
        raise TransicaoInvalida("conjunto sem regras")
    c = ConjuntoRegras(nome=nome, tenant_id=tenant_id, estado="rascunho")
    session.add(c)
    session.flush()
    for rid in sorted(set(regra_versao_ids)):
        session.add(ConjuntoRegrasItem(conjunto_id=c.id, regra_versao_id=rid))
    session.flush()
    return c


def versoes_do_conjunto(session: Session, conjunto_id: int) -> list[RegraVersao]:
    return (
        session.query(RegraVersao)
        .join(ConjuntoRegrasItem, ConjuntoRegrasItem.regra_versao_id == RegraVersao.id)
        .filter(ConjuntoRegrasItem.conjunto_id == conjunto_id)
        .order_by(RegraVersao.id)
        .all()
    )


def publicar(session: Session, *, user: User, conjunto_id: int) -> ConjuntoRegras:
    exigir_papel(session, user, PAPEL)
    c = session.get(ConjuntoRegras, conjunto_id)
    if c is None or c.estado != "rascunho":
        raise TransicaoInvalida("só conjunto em rascunho se publica")
    recusas = {}
    for rv in versoes_do_conjunto(session, conjunto_id):
        if rv.estado != "homologada":
            recusas[rv.id] = f"estado {rv.estado}"
        elif motivos := _motivos_de_recusa(rv):
            recusas[rv.id] = motivos
    if recusas:
        raise TransicaoInvalida(f"publicação recusada: {recusas}")
    c.estado = "publicado"
    c.publicado_por_id = user.id
    c.publicado_em = datetime.now(UTC)
    session.flush()
    return c


def ativar(session: Session, *, user: User, conjunto_id: int) -> ConjuntoRegras:
    exigir_papel(session, user, PAPEL)
    c = session.get(ConjuntoRegras, conjunto_id)
    if c is None or c.estado not in ("publicado", "inativo"):
        raise TransicaoInvalida("só conjunto publicado (ou inativo, no rollback) se ativa")
    q = session.query(ConjuntoRegras).filter(ConjuntoRegras.estado == "ativo")
    q = q.filter(ConjuntoRegras.tenant_id.is_(None)) if c.tenant_id is None else q.filter(
        ConjuntoRegras.tenant_id == c.tenant_id)
    for atual in q.all():
        atual.estado = "inativo"
    session.flush()
    c.estado = "ativo"
    c.ativado_em = datetime.now(UTC)
    session.flush()
    return c


def conjuntos_ativos(session: Session, tenant_id: int) -> list[ConjuntoRegras]:
    """Base global + camada do tenant (que só ACRESCENTA — ADR-073 §11)."""
    return (
        session.query(ConjuntoRegras)
        .filter(ConjuntoRegras.estado == "ativo")
        .filter((ConjuntoRegras.tenant_id.is_(None)) | (ConjuntoRegras.tenant_id == tenant_id))
        .order_by(ConjuntoRegras.tenant_id.nulls_first(), ConjuntoRegras.id)
        .all()
    )
