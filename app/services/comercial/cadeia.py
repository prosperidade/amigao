"""Os passos ``redator`` e ``orcamento`` da cadeia ``gerar_proposta`` (ADR-074 §1).

Executados pelo agendador persistido do ADR-069 (execução, snapshot, cursor, retomada),
sem LLM. Cada passo devolve referências de ARTEFATO, e a dependência se resolve pelo
artefato mais novo do caso — não pela revisão de conclusão do diagnóstico, que saiu da
cadeia comercial (ruptura 4).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.process import Process
from app.services.comercial import base as base_mod
from app.services.comercial import orcamento as orcamento_mod
from app.services.comercial import redator as redator_mod

AGENTES_COMERCIAIS = frozenset({"redator", "orcamento"})


def executar_passo(db: Session, *, agent: str, tenant_id: int, process_id: int, user_id: int
                   ) -> tuple[list[dict], dict]:
    """``(outputs, resultado)`` do passo; falha levanta ``ComercialError`` (ValueError)."""
    process = db.query(Process).filter(Process.id == process_id, Process.tenant_id == tenant_id).one()
    if agent == "redator":
        rel, esc = redator_mod.gerar(db, process=process, tenant_id=tenant_id, user_id=user_id)
        return ([{"artefato": "especificacao_escopo", "id": esc.id}],
                {"status": "awaiting_review", "relatorio_preliminar_id": rel.id, "especificacao_escopo_id": esc.id,
                 "requires_review": True, "llm": False})
    o = orcamento_mod.gerar(db, process=process, tenant_id=tenant_id, user_id=user_id)
    return ([{"artefato": "orcamento", "id": o.id}],
            {"status": "awaiting_review", "orcamento_id": o.id, "total": str(o.total),
             "ressalvas": o.ressalvas, "requires_review": True, "llm": False})


def _ultimo(db: Session, *, tenant_id: int, process_id: int, ref: dict):
    if ref["artefato"] == "orcamento":
        return base_mod.ultimo_orcamento(db, tenant_id, process_id)
    return base_mod.ultima_redacao(db, tenant_id, process_id, ref["artefato"])


def artefato_desatualizado(db: Session, *, tenant_id: int, process_id: int, ref: dict) -> bool:
    """Retomada com recálculo: o artefato mais novo ficou desatualizado — o passo roda de novo."""
    artefato = _ultimo(db, tenant_id=tenant_id, process_id=process_id, ref=ref)
    return artefato is None or base_mod.atualidade(db, artefato)["estado"] != "vigente"


def artefato_resolvido(db: Session, *, tenant_id: int, process_id: int, ref: dict) -> bool:
    """O artefato MAIS NOVO do tipo está aprovado e atual. Versão nova feita pela API conta."""
    artefato = _ultimo(db, tenant_id=tenant_id, process_id=process_id, ref=ref)
    return (artefato is not None and artefato.estado_revisao == "aprovada"
            and base_mod.atualidade(db, artefato)["estado"] == "vigente")
