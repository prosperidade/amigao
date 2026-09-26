"""Motor jurídico determinístico (ADR-073).

Dois grupos:

- **Caso** (`/processes/{id}/motor/...`): avaliar, gerar a Rota pelo motor, ler a última
  execução, registrar ciência de alerta crítico. Todo usuário interno do tenant.
- **Regras** (`/motor-juridico/...`): importar a tradução do gate (superusuário — é
  engenharia), listar, homologar (papel `homologar_regra` na área), montar conjunto,
  publicar e ativar (papel `homologar_regra`). Nenhum LLM traduz nem ativa regra.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_internal_user, get_db
from app.models.audit_log import AuditLog
from app.models.motor_juridico import (
    AvaliacaoRegra,
    CienciaAlerta,
    ConjuntoRegras,
    ExecucaoMotor,
    Regra,
    RegraVersao,
)
from app.models.process import Process
from app.models.user import User
from app.schemas.rota import RotaMaterializeOut, RotaOut
from app.services.audit_hash import stamp_audit_hash
from app.services.motor_juridico import ciclo, importador
from app.services.motor_juridico.avaliador import (
    SemConjuntoAtivo,
    alertas_sem_ciencia,
    ciencias_vigentes,
    executar,
    ultima_execucao,
)
from app.services.motor_juridico.rota import gerar_rota_pelo_motor
from app.services.zona_normativa.curadoria import CuradoriaNegada, TransicaoInvalida

process_router = APIRouter()
regras_router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_internal_user)]


def _negar(exc: Exception) -> HTTPException:
    if isinstance(exc, CuradoriaNegada):
        return HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


def _processo(db: Session, process_id: int, tenant_id: int) -> Process:
    p = db.query(Process).filter(Process.id == process_id, Process.tenant_id == tenant_id).first()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processo não encontrado")
    return p


def _audit(db: Session, *, tenant_id: int, user_id: int, entity_type: str, entity_id: int, action: str,
           details: str) -> None:
    log = AuditLog(tenant_id=tenant_id, user_id=user_id, entity_type=entity_type, entity_id=entity_id,
                   action=action, details=details)
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)


def _relatorio(db: Session, ex: ExecucaoMotor) -> dict:
    """Relatório da execução: avaliadas, estados, faltantes, fundamento e alertas."""
    avs = (db.query(AvaliacaoRegra, Regra.rule_id)
           .join(RegraVersao, RegraVersao.id == AvaliacaoRegra.regra_versao_id)
           .join(Regra, Regra.id == RegraVersao.regra_id)
           .filter(AvaliacaoRegra.execucao_id == ex.id, AvaliacaoRegra.tenant_id == ex.tenant_id)
           .order_by(Regra.rule_id).all())
    pendentes = {a.id for a in alertas_sem_ciencia(db, execucao_id=ex.id, tenant_id=ex.tenant_id)}
    # Ciência própria ou herdada de execução anterior de mesmo conteúdo (#289).
    vigentes = ciencias_vigentes(db, execucao_id=ex.id, tenant_id=ex.tenant_id)
    contagem: dict[str, int] = {}
    linhas = []
    for a, rule_id in avs:
        contagem[a.estado] = contagem.get(a.estado, 0) + 1
        efeitos = (a.consequencia or {}).get("efeitos", [])
        linhas.append({
            "avaliacao_id": a.id, "rule_id": rule_id, "regra_versao_id": a.regra_versao_id,
            "estado": a.estado, "faltantes": a.faltantes or [], "efeitos": efeitos,
            "fundamento": {
                "fonte_versao_id": a.fundamento_fonte_versao_id, "dispositivo_id": a.fundamento_dispositivo_id,
                "caminho": a.fundamento_caminho, "razao": a.fundamento_razao,
            },
            "alerta_critico_sem_ciencia": a.id in pendentes,
            "ciencia": ({"id": vigentes[a.id].id, "avaliacao_id": vigentes[a.id].avaliacao_id,
                         "herdada": vigentes[a.id].avaliacao_id != a.id} if a.id in vigentes else None),
            "detalhe_erro": a.detalhe_erro,
        })
    return {
        "execucao_id": ex.id, "process_id": ex.process_id, "conjunto_id": ex.conjunto_id,
        "conjunto_tenant_id": ex.conjunto_tenant_id, "data_referencia": ex.data_referencia.isoformat(),
        "fatos": ex.fatos, "fatos_hash": ex.fatos_hash, "contagem": contagem,
        # "Zero regras disparadas" não é regularidade: sai escrito como é.
        "disparadas": contagem.get("aplicavel_disparou", 0),
        "avaliacoes": linhas, "alertas_sem_ciencia": sorted(pendentes),
    }


# ---------------------------------------------------------------------------
# Caso
# ---------------------------------------------------------------------------

@process_router.post("/{process_id}/motor/avaliar")
def avaliar(process_id: int, db: Db, user: UserDep) -> dict:
    process = _processo(db, process_id, user.tenant_id)
    try:
        out = executar(db, process=process, tenant_id=user.tenant_id, user_id=user.id)
    except SemConjuntoAtivo as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return _relatorio(db, out.execucao)


@process_router.get("/{process_id}/motor/execucoes/ultima")
def ultima(process_id: int, db: Db, user: UserDep) -> dict:
    _processo(db, process_id, user.tenant_id)
    ex = ultima_execucao(db, process_id=process_id, tenant_id=user.tenant_id)
    if ex is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "O motor ainda não avaliou este caso")
    return _relatorio(db, ex)


@process_router.post("/{process_id}/rota/gerar-motor", status_code=status.HTTP_201_CREATED)
def gerar_rota_motor(process_id: int, db: Db, user: UserDep) -> dict:
    process = _processo(db, process_id, user.tenant_id)
    try:
        result, execucao = gerar_rota_pelo_motor(db, process=process, tenant_id=user.tenant_id, user_id=user.id)
    except SemConjuntoAtivo as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    _audit(db, tenant_id=user.tenant_id, user_id=user.id, entity_type="rota", entity_id=result.rota.id,
           action="rota_materializada_motor",
           details=(f"execucao={execucao.execucao.id} created={result.created} matched={result.matched} "
                    f"suprimidos={result.suprimidos} diff={result.is_diff}"))
    db.commit()
    db.refresh(result.rota)
    saida = RotaMaterializeOut(
        created=result.created, matched=result.matched, is_diff=result.is_diff,
        rota=RotaOut.model_validate(result.rota), orgaos_corrigidos=result.orgaos_corrigidos,
        versao_preservada=result.versao_preservada, suprimidos=result.suprimidos,
    )
    return {"rota": saida.model_dump(mode="json"), "execucao": _relatorio(db, execucao.execucao)}


class CienciaRequest(BaseModel):
    justificativa: str = Field(min_length=1)


@process_router.post("/{process_id}/motor/alertas/{avaliacao_id}/ciencia", status_code=status.HTTP_201_CREATED)
def dar_ciencia(process_id: int, avaliacao_id: int, body: CienciaRequest, db: Db, user: UserDep) -> dict:
    _processo(db, process_id, user.tenant_id)
    av = (db.query(AvaliacaoRegra)
          .join(ExecucaoMotor, ExecucaoMotor.id == AvaliacaoRegra.execucao_id)
          .filter(AvaliacaoRegra.id == avaliacao_id, AvaliacaoRegra.tenant_id == user.tenant_id,
                  ExecucaoMotor.process_id == process_id)
          .first())
    if av is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avaliação não encontrada")
    if av.estado != "aplicavel_disparou" or not any(
            e.get("tipo") == "alerta_critico" for e in (av.consequencia or {}).get("efeitos", [])):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Esta avaliação não emitiu alerta crítico")
    if db.query(CienciaAlerta.id).filter(CienciaAlerta.avaliacao_id == av.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Ciência já registrada para este alerta")
    justificativa = body.justificativa.strip()
    if not justificativa:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ciência exige justificativa")
    c = CienciaAlerta(tenant_id=user.tenant_id, avaliacao_id=av.id, user_id=user.id, justificativa=justificativa)
    db.add(c)
    db.flush()
    _audit(db, tenant_id=user.tenant_id, user_id=user.id, entity_type="avaliacao_regra", entity_id=av.id,
           action="motor_alerta_ciencia", details=justificativa[:500])
    db.commit()
    return {"id": c.id, "avaliacao_id": av.id, "user_id": user.id, "justificativa": c.justificativa}


# ---------------------------------------------------------------------------
# Regras e conjuntos
# ---------------------------------------------------------------------------

def _versao_out(rv: RegraVersao, rule_id: str) -> dict:
    return {"id": rv.id, "rule_id": rule_id, "versao": rv.versao, "estado": rv.estado,
            "descricao": rv.descricao, "aplicabilidade": rv.aplicabilidade, "condicao": rv.condicao,
            "consequencia": rv.consequencia, "fundamento": rv.fundamento, "severidade": rv.severidade,
            "origem": rv.origem, "hash_conteudo": rv.hash_conteudo, "homologada_por_id": rv.homologada_por_id,
            "homologada_em": rv.homologada_em.isoformat() if rv.homologada_em else None,
            "nota_homologacao": rv.nota_homologacao, "area": ciclo.area_da_regra(rv)}


@regras_router.post("/regras/importar-gate")
def importar_gate(db: Db, user: UserDep) -> dict:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Importar a tradução formal é de superusuário")
    try:
        out = importador.importar(db, importador.carregar())
    except importador.TraducaoInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    db.commit()
    return {"criadas": [rv.id for rv in out.criadas], "mantidas": [rv.id for rv in out.mantidas]}


@regras_router.get("/regras")
def listar_regras(db: Db, user: UserDep) -> list[dict]:
    rows = (db.query(RegraVersao, Regra.rule_id).join(Regra, Regra.id == RegraVersao.regra_id)
            .filter((Regra.tenant_id.is_(None)) | (Regra.tenant_id == user.tenant_id))
            .order_by(Regra.rule_id, RegraVersao.versao).all())
    return [_versao_out(rv, rule_id) for rv, rule_id in rows]


class NotaRequest(BaseModel):
    nota: str = Field(min_length=1)


@regras_router.post("/regras/versoes/{versao_id}/homologar")
def homologar(versao_id: int, body: NotaRequest, db: Db, user: UserDep) -> dict:
    try:
        rv = ciclo.homologar(db, user=user, regra_versao_id=versao_id, nota=body.nota)
    except (CuradoriaNegada, TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    rule_id = db.query(Regra.rule_id).filter(Regra.id == rv.regra_id).scalar()
    db.commit()
    return _versao_out(rv, rule_id)


class ConjuntoRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    regra_versao_ids: list[int] = Field(min_length=1)


def _conjunto_out(db: Session, c: ConjuntoRegras) -> dict:
    return {"id": c.id, "nome": c.nome, "estado": c.estado, "tenant_id": c.tenant_id,
            "publicado_por_id": c.publicado_por_id,
            "regra_versao_ids": [rv.id for rv in ciclo.versoes_do_conjunto(db, c.id)]}


@regras_router.post("/conjuntos", status_code=status.HTTP_201_CREATED)
def criar_conjunto(body: ConjuntoRequest, db: Db, user: UserDep) -> dict:
    try:
        ciclo.exigir_papel(db, user, ciclo.PAPEL)
        existentes = {i for (i,) in db.query(RegraVersao.id).filter(RegraVersao.id.in_(body.regra_versao_ids))}
        if faltam := sorted(set(body.regra_versao_ids) - existentes):
            raise TransicaoInvalida(f"versões inexistentes: {faltam}")
        c = ciclo.criar_conjunto(db, nome=body.nome, regra_versao_ids=body.regra_versao_ids)
    except (CuradoriaNegada, TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return _conjunto_out(db, c)


@regras_router.post("/conjuntos/{conjunto_id}/publicar")
def publicar(conjunto_id: int, db: Db, user: UserDep) -> dict:
    try:
        c = ciclo.publicar(db, user=user, conjunto_id=conjunto_id)
    except (CuradoriaNegada, TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return _conjunto_out(db, c)


@regras_router.post("/conjuntos/{conjunto_id}/ativar")
def ativar(conjunto_id: int, db: Db, user: UserDep) -> dict:
    try:
        c = ciclo.ativar(db, user=user, conjunto_id=conjunto_id)
    except (CuradoriaNegada, TransicaoInvalida) as exc:
        raise _negar(exc) from exc
    db.commit()
    return _conjunto_out(db, c)
