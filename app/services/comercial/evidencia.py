"""Evidência por ID de cada afirmação (ADR-074 §2).

Uma afirmação é ``{id, texto, evidencias: [{tipo, id, rotulo}]}``. Este módulo confere que
cada evidência EXISTE no banco e pertence ao tenant (e ao caso, quando é dado do caso). É a
trava que a redação por LLM terá de satisfazer quando entrar (dívida #282): ela poderá
reescrever ``texto``, nunca ``evidencias``.

Nada aqui procura por semelhança: um ID que não resolve é erro nomeado, não "parecido".
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.evidence import EvidenceVersion
from app.models.motor_juridico import AvaliacaoRegra, CienciaAlerta, ExecucaoMotor
from app.models.rota import Rota, RotaPasso
from app.models.zona_normativa import Dispositivo, FonteNormativa, FonteNormativaVersao
from app.services.comercial import ComercialError

TIPOS = ("dispositivo", "fonte_versao", "observacao", "fonte_primaria", "conclusao", "documento",
         "avaliacao_regra", "ciencia_alerta", "execucao_motor", "rota", "rota_passo")

# Evidência do caso: `evidence_versions` guarda observação, fonte primária e conclusão;
# o tipo declarado precisa bater com o `kind` gravado.
_KIND = {"observacao": "observacao", "fonte_primaria": "fonte_primaria", "conclusao": "conclusao"}


def ref(tipo: str, id_: int, rotulo: str) -> dict:
    if tipo not in TIPOS:
        raise ValueError(f"tipo de evidência desconhecido: {tipo}")
    return {"tipo": tipo, "id": int(id_), "rotulo": rotulo}


def afirmacao(chave: str, texto: str, evidencias: list[dict]) -> dict:
    # Mesma evidência citada duas vezes não reforça nada: dedup por (tipo, id), ordem preservada.
    vistas, unicas = set(), []
    for e in evidencias:
        if (e["tipo"], e["id"]) not in vistas:
            vistas.add((e["tipo"], e["id"]))
            unicas.append(e)
    return {"id": chave, "texto": texto, "evidencias": unicas}


def _existentes(db: Session, tipo: str, ids: set[int], *, tenant_id: int, process_id: int) -> set[int]:
    if tipo in _KIND:
        q = db.query(EvidenceVersion.id).filter(
            EvidenceVersion.id.in_(ids), EvidenceVersion.tenant_id == tenant_id,
            EvidenceVersion.process_id == process_id, EvidenceVersion.kind == _KIND[tipo])
    elif tipo == "documento":
        q = db.query(Document.id).filter(Document.id.in_(ids), Document.tenant_id == tenant_id,
                                         Document.process_id == process_id)
    elif tipo == "dispositivo":
        # Catálogo global ou do próprio tenant (precedente privado, ADR-075).
        q = (db.query(Dispositivo.id)
             .join(FonteNormativaVersao, FonteNormativaVersao.id == Dispositivo.fonte_versao_id)
             .join(FonteNormativa, FonteNormativa.id == FonteNormativaVersao.fonte_id)
             .filter(Dispositivo.id.in_(ids),
                     or_(FonteNormativa.tenant_id.is_(None), FonteNormativa.tenant_id == tenant_id)))
    elif tipo == "fonte_versao":
        q = (db.query(FonteNormativaVersao.id)
             .join(FonteNormativa, FonteNormativa.id == FonteNormativaVersao.fonte_id)
             .filter(FonteNormativaVersao.id.in_(ids),
                     or_(FonteNormativa.tenant_id.is_(None), FonteNormativa.tenant_id == tenant_id)))
    elif tipo == "avaliacao_regra":
        q = (db.query(AvaliacaoRegra.id)
             .join(ExecucaoMotor, ExecucaoMotor.id == AvaliacaoRegra.execucao_id)
             .filter(AvaliacaoRegra.id.in_(ids), AvaliacaoRegra.tenant_id == tenant_id,
                     ExecucaoMotor.process_id == process_id))
    elif tipo == "ciencia_alerta":
        q = db.query(CienciaAlerta.id).filter(CienciaAlerta.id.in_(ids), CienciaAlerta.tenant_id == tenant_id)
    elif tipo == "execucao_motor":
        q = db.query(ExecucaoMotor.id).filter(ExecucaoMotor.id.in_(ids), ExecucaoMotor.tenant_id == tenant_id,
                                              ExecucaoMotor.process_id == process_id)
    elif tipo == "rota":
        q = db.query(Rota.id).filter(Rota.id.in_(ids), Rota.tenant_id == tenant_id, Rota.process_id == process_id)
    elif tipo == "rota_passo":
        # Inclui lápides: o passo removido é evidência do que saiu do escopo.
        q = (db.query(RotaPasso.id).join(Rota, Rota.id == RotaPasso.rota_id)
             .filter(RotaPasso.id.in_(ids), RotaPasso.tenant_id == tenant_id, Rota.process_id == process_id))
    else:  # pragma: no cover — TIPOS fecha o conjunto
        raise ValueError(tipo)
    return {r[0] for r in q.all()}


def verificar(db: Session, secoes: list[dict], *, tenant_id: int, process_id: int) -> list[str]:
    """Falhas de evidência, por afirmação. Lista vazia = toda afirmação se sustenta por ID."""
    falhas: list[str] = []
    pedidos: dict[str, set[int]] = defaultdict(set)
    for secao in secoes:
        for a in secao["afirmacoes"]:
            if not a["evidencias"]:
                falhas.append(f"{a['id']}: afirmação sem evidência")
            for e in a["evidencias"]:
                if e["tipo"] not in TIPOS:
                    falhas.append(f"{a['id']}: tipo de evidência desconhecido {e['tipo']!r}")
                else:
                    pedidos[e["tipo"]].add(int(e["id"]))
    achados = {t: _existentes(db, t, ids, tenant_id=tenant_id, process_id=process_id)
               for t, ids in pedidos.items()}
    for secao in secoes:
        for a in secao["afirmacoes"]:
            for e in a["evidencias"]:
                if e["tipo"] in achados and int(e["id"]) not in achados[e["tipo"]]:
                    falhas.append(f"{a['id']}: {e['tipo']} {e['id']} não resolvido neste caso")
    return falhas


def exigir(db: Session, secoes: list[dict], *, tenant_id: int, process_id: int) -> None:
    falhas = verificar(db, secoes, tenant_id=tenant_id, process_id=process_id)
    if falhas:
        raise ComercialError("Afirmação sem evidência resolvida por ID: " + "; ".join(falhas))
