"""Execução do motor sobre um caso (ADR-073 §4–§6).

Uma execução = retrato de fatos + conjuntos ativos + data de referência. Cada regra
homologada do conjunto vira UMA linha append-only em `avaliacao_regra`, num dos seis
estados. A aplicabilidade é decidida ANTES da condição: regra que não se aplica ao caso
nem chega a ler os fatos da condição.

"Zero regras disparadas" aparece como tal — o relatório lista avaliadas, não aplicáveis
e faltantes; nunca vira "caso regular".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.motor_juridico import AvaliacaoRegra, ConjuntoRegras, ExecucaoMotor, Regra, RegraVersao
from app.models.process import Process
from app.services.motor_juridico import fundamento as fund
from app.services.motor_juridico.ciclo import conjuntos_ativos, versoes_do_conjunto
from app.services.motor_juridico.fatos import hash_fatos, montar_fatos
from app.services.motor_juridico.linguagem import ROTULOS, avaliar, fatos_da_condicao

logger = get_logger(__name__)


class SemConjuntoAtivo(RuntimeError):
    """Não há conjunto de regras publicado e ativo — o motor não inventa regra."""


@dataclass
class Execucao:
    execucao: ExecucaoMotor
    avaliacoes: list[AvaliacaoRegra] = field(default_factory=list)
    # regra_versao_id → RegraVersao, para quem consome a execução sem nova query.
    versoes: dict[int, RegraVersao] = field(default_factory=dict)
    rule_ids: dict[int, str] = field(default_factory=dict)


def _aplicabilidade(rv: RegraVersao, fatos: dict) -> tuple[bool | None, set[str]]:
    """True = aplica; False = não aplica; None = não dá para decidir (falta a UF)."""
    ufs = (rv.aplicabilidade or {}).get("ufs")
    if not ufs:
        return True, set()
    uf = fatos.get("caso.uf") or {}
    if uf.get("estado") != "determinado":
        return None, {"caso.uf"}
    return uf["valor"] in {u.upper() for u in ufs}, set()


def _coletas_dos_faltantes(rv: RegraVersao, rule_id: str, faltantes: set[str]) -> list[dict]:
    """Indeterminado vira coleta: um passo por fato faltante (ADR-073 §5)."""
    return [
        {"tipo": "coleta", "titulo": f"Confirmar: {ROTULOS.get(f, f)}",
         "descricao": f"A regra {rule_id} precisa deste dado para decidir: {rv.descricao}",
         "orgao": None, "fase": "coleta", "fato": f}
        for f in sorted(faltantes)
    ]


def avaliar_regra(
    session: Session, rv: RegraVersao, rule_id: str, fatos: dict, *, tenant_id: int, data_referencia: date
) -> dict:
    """Os campos de uma `AvaliacaoRegra` (sem execução). Nunca levanta: erro vira estado."""
    try:
        aplica, faltam_apl = _aplicabilidade(rv, fatos)
        lidos = fatos_da_condicao(rv.condicao) | ({"caso.uf"} if (rv.aplicabilidade or {}).get("ufs") else set())
        entradas = {f: fatos.get(f) for f in sorted(lidos)}
        if aplica is False:
            return {"estado": "nao_aplicavel", "entradas": entradas}
        if aplica is None:
            valor, faltantes = None, faltam_apl
        else:
            valor, faltantes = avaliar(rv.condicao, fatos)

        if valor is False:
            return {"estado": "aplicavel_nao_disparou", "entradas": entradas}
        if valor is True:
            estado, efeitos = "aplicavel_disparou", list(rv.consequencia["efeitos"])
        else:
            estado, efeitos = "indeterminado", _coletas_dos_faltantes(rv, rule_id, faltantes)

        res = fund.resolver(session, rv.fundamento, tenant_id=tenant_id, data_referencia=data_referencia)
        return {
            "estado": estado, "entradas": entradas,
            "faltantes": sorted(faltantes) or None,
            "consequencia": {"efeitos": efeitos},
            "fundamento_fonte_versao_id": res.fonte_versao_id,
            "fundamento_dispositivo_id": res.dispositivo_id,
            "fundamento_caminho": res.caminho,
            "fundamento_razao": res.razao,
            "detalhe_erro": None,
            "_resolucao": res,
        }
    except Exception as exc:  # noqa: BLE001 — erro de execução é ESTADO registrado, nunca silêncio
        logger.error("motor_juridico: erro ao avaliar regra",
                     extra={"regra_versao_id": rv.id, "rule_id": rule_id, "erro": repr(exc)})
        return {"estado": "erro_execucao", "detalhe_erro": f"{type(exc).__name__}: {exc}"}


def executar(
    session: Session, *, process: Process, tenant_id: int, user_id: int | None,
    data_referencia: date | None = None,
) -> Execucao:
    conjuntos = conjuntos_ativos(session, tenant_id)
    base = next((c for c in conjuntos if c.tenant_id is None), None)
    camada: ConjuntoRegras | None = next((c for c in conjuntos if c.tenant_id is not None), None)
    principal = base or camada
    if principal is None:
        raise SemConjuntoAtivo(
            "Nenhum conjunto de regras publicado e ativo. A tradução do gate nasce em rascunho e "
            "depende de homologação (Q-ISIS-22) e publicação."
        )

    data_referencia = data_referencia or date.today()
    fatos = montar_fatos(session, process=process, tenant_id=tenant_id)
    ex = ExecucaoMotor(
        tenant_id=tenant_id, process_id=process.id, conjunto_id=principal.id,
        conjunto_tenant_id=camada.id if (camada and principal is base) else None,
        data_referencia=data_referencia, fatos=fatos, fatos_hash=hash_fatos(fatos), iniciado_por_id=user_id,
    )
    session.add(ex)
    session.flush()

    versoes: dict[int, RegraVersao] = {}
    for c in (x for x in (base, camada) if x is not None):
        for rv in versoes_do_conjunto(session, c.id):
            versoes.setdefault(rv.id, rv)
    rule_ids = dict(
        session.query(RegraVersao.id, Regra.rule_id)
        .join(Regra, Regra.id == RegraVersao.regra_id)
        .filter(RegraVersao.id.in_(list(versoes)))
        .all()
    )

    out = Execucao(execucao=ex, versoes=versoes, rule_ids=rule_ids)
    for rv_id in sorted(versoes, key=lambda i: (rule_ids[i], i)):
        rv = versoes[rv_id]
        campos = avaliar_regra(session, rv, rule_ids[rv_id], fatos,
                               tenant_id=tenant_id, data_referencia=data_referencia)
        campos.pop("_resolucao", None)
        av = AvaliacaoRegra(tenant_id=tenant_id, execucao_id=ex.id, regra_versao_id=rv.id, **campos)
        session.add(av)
        out.avaliacoes.append(av)
    session.flush()
    logger.info(
        "motor_juridico_execucao",
        extra={"process_id": process.id, "tenant_id": tenant_id, "execucao_id": ex.id,
               "estados": _contagem(out.avaliacoes)},
    )
    return out


def _contagem(avaliacoes: list[AvaliacaoRegra]) -> dict[str, int]:
    cont: dict[str, int] = {}
    for a in avaliacoes:
        cont[a.estado] = cont.get(a.estado, 0) + 1
    return cont


def ultima_execucao(session: Session, *, process_id: int, tenant_id: int) -> ExecucaoMotor | None:
    return (
        session.query(ExecucaoMotor)
        .filter(ExecucaoMotor.process_id == process_id, ExecucaoMotor.tenant_id == tenant_id)
        .order_by(ExecucaoMotor.id.desc())
        .first()
    )


def alertas_sem_ciencia(session: Session, *, execucao_id: int, tenant_id: int) -> list[AvaliacaoRegra]:
    """Alertas críticos da execução que ainda não têm ciência registrada."""
    from app.models.motor_juridico import CienciaAlerta  # noqa: PLC0415

    avs = (
        session.query(AvaliacaoRegra)
        .filter(AvaliacaoRegra.execucao_id == execucao_id, AvaliacaoRegra.tenant_id == tenant_id,
                AvaliacaoRegra.estado == "aplicavel_disparou")
        .order_by(AvaliacaoRegra.id)
        .all()
    )
    com_ciencia = {
        a for (a,) in session.query(CienciaAlerta.avaliacao_id)
        .filter(CienciaAlerta.tenant_id == tenant_id, CienciaAlerta.avaliacao_id.in_([a.id for a in avs]))
    } if avs else set()
    return [
        a for a in avs
        if a.id not in com_ciencia
        and any(e.get("tipo") == "alerta_critico" for e in (a.consequencia or {}).get("efeitos", []))
    ]
