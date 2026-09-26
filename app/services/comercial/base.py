"""Base de dependências dos artefatos comerciais e a atualidade deles (ADR-074 §3).

Cada relatório, escopo e orçamento grava a ``base`` de que dependeu. A atualidade é
LEITURA: a base gravada comparada à atual — ``vigente`` ou ``desatualizado`` com os motivos.
Não muda estado, não retrocede etapa, não regenera, não apaga a aprovação (ADR-068).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.comercial import Orcamento, OrcamentoEscolha, OrcamentoMetodo, RedacaoComercial
from app.models.evidence import EvidenceInvalidation, EvidenceReview, EvidenceVersion
from app.models.regulatory import RegulatoryDiagnosis
from app.models.rota import Rota, RotaPasso, RotaStatus
from app.schemas.evidence import canonical_hash


def rotas_validadas(db: Session, tenant_id: int, process_id: int) -> list[Rota]:
    return (db.query(Rota)
            .filter(Rota.tenant_id == tenant_id, Rota.process_id == process_id, Rota.status == RotaStatus.validada)
            .order_by(Rota.id).all())


def motivo_remocao(db: Session, passo: RotaPasso) -> str:
    """O motivo gravado no passo; lápide anterior à coluna lê a trilha (fonte registrada)."""
    if passo.remocao_motivo:
        return passo.remocao_motivo
    log = (db.query(AuditLog)
           .filter(AuditLog.tenant_id == passo.tenant_id, AuditLog.entity_type == "rota",
                   AuditLog.entity_id == passo.rota_id, AuditLog.action == "rota_passo_removido",
                   AuditLog.details.like(f"passo {passo.id} ·%"))
           .order_by(AuditLog.id.desc()).first())
    if log and log.details and " · motivo: " in log.details:
        return log.details.split(" · motivo: ", 1)[1]
    return "motivo não registrado"


def _passo(p: RotaPasso) -> dict:
    return {"id": p.id, "titulo": p.titulo, "status": getattr(p.status, "value", p.status),
            "classificacao": getattr(p.classificacao, "value", p.classificacao),
            "dispositivo": p.fundamento_dispositivo_id, "fonte_versao": p.fundamento_fonte_versao_id}


def base_rotas(db: Session, tenant_id: int, process_id: int) -> list[dict]:
    """Todas as Rotas do caso (não só as validadas): a que deixou de estar validada conta."""
    rotas = (db.query(Rota).filter(Rota.tenant_id == tenant_id, Rota.process_id == process_id)
             .order_by(Rota.id).all())
    return [{
        "id": r.id, "status": getattr(r.status, "value", r.status),
        "validada_em": r.validated_at.isoformat() if r.validated_at else None,
        "passos": [_passo(p) for p in r.passos],
        "removidos": [{"id": p.id, "titulo": p.titulo, "motivo": motivo_remocao(db, p)}
                      for p in r.passos_removidos],
    } for r in rotas]


def base_diagnostico(db: Session, tenant_id: int, process_id: int) -> dict:
    """Estado do diagnóstico: versão legada e conclusões do agente com a última revisão."""
    legado = (db.query(RegulatoryDiagnosis)
              .filter(RegulatoryDiagnosis.tenant_id == tenant_id, RegulatoryDiagnosis.process_id == process_id)
              .order_by(RegulatoryDiagnosis.version.desc()).first())
    linhas = (db.query(EvidenceVersion)
              .filter(EvidenceVersion.tenant_id == tenant_id, EvidenceVersion.process_id == process_id,
                      EvidenceVersion.kind == "conclusao", EvidenceVersion.agent_name == "diagnostico")
              .order_by(EvidenceVersion.object_id, EvidenceVersion.version).all())
    ultimas: dict[str, EvidenceVersion] = {}
    for row in linhas:
        ultimas[row.object_id] = row
    ids = [r.id for r in ultimas.values()]
    revisoes: dict[int, str] = {}
    invalidas: set[int] = set()
    if ids:
        for rv in (db.query(EvidenceReview).filter(EvidenceReview.evidence_id.in_(ids))
                   .order_by(EvidenceReview.evidence_id, EvidenceReview.revision)):
            revisoes[rv.evidence_id] = rv.action
        invalidas = {i for (i,) in db.query(EvidenceInvalidation.evidence_id)
                     .filter(EvidenceInvalidation.evidence_id.in_(ids))}
    return {
        "legado": ({"id": legado.id, "versao": legado.version, "validado": legado.validated_at is not None}
                   if legado else None),
        "conclusoes": [{"id": r.id, "objeto": r.object_id, "versao": r.version,
                        "revisao": revisoes.get(r.id), "invalida": r.id in invalidas}
                       for r in sorted(ultimas.values(), key=lambda x: x.object_id)],
    }


def ressalvas_do_diagnostico(diag: dict) -> list[dict]:
    """Diagnóstico em revisão é RESSALVA registrada, nunca bloqueio (ruptura 4)."""
    out = []
    em_revisao = [c for c in diag["conclusoes"] if c["revisao"] is None and not c["invalida"]]
    if em_revisao:
        out.append({"tipo": "diagnostico_em_revisao",
                    "texto": f"{len(em_revisao)} conclusão(ões) do diagnóstico em revisão; o documento "
                             "se apoia na Rota validada, não nelas.",
                    "conclusoes": [c["id"] for c in em_revisao]})
    if diag["legado"] and not diag["legado"]["validado"]:
        out.append({"tipo": "diagnostico_nao_validado",
                    "texto": f"Diagnóstico v{diag['legado']['versao']} ainda não validado.",
                    "diagnostico_id": diag["legado"]["id"]})
    if not diag["conclusoes"] and not diag["legado"]:
        out.append({"tipo": "sem_diagnostico",
                    "texto": "Caso sem diagnóstico registrado; a Rota foi validada pelo motor jurídico."})
    return out


def base_metodos(db: Session, tenant_id: int, codigos: list[str]) -> dict[str, int | None]:
    """Versão CORRENTE de cada método usado (None = o método deixou de existir ou está inativo)."""
    out: dict[str, int | None] = {}
    for codigo in sorted(set(codigos)):
        m = (db.query(OrcamentoMetodo).filter(OrcamentoMetodo.tenant_id == tenant_id,
                                              OrcamentoMetodo.codigo == codigo)
             .order_by(OrcamentoMetodo.versao.desc()).first())
        out[codigo] = m.versao if m is not None and m.ativo else None
    return out


def base_escolhas(db: Session, tenant_id: int, process_id: int) -> dict[str, list]:
    rows = (db.query(OrcamentoEscolha)
            .filter(OrcamentoEscolha.tenant_id == tenant_id, OrcamentoEscolha.process_id == process_id)
            .order_by(OrcamentoEscolha.rota_passo_id).all())
    # Normalizado na escala da coluna: o valor recém-escrito ("10") e o relido do banco ("10.00")
    # são a mesma escolha.
    return {str(r.rota_passo_id): [r.metodo_codigo,
                                   str(Decimal(r.quantidade).quantize(Decimal("0.01"))) if r.quantidade is not None
                                   else None]
            for r in rows}


def conteudo_motor(db: Session, execucao_id: int | None) -> dict | None:
    """``{fatos_hash, regras_hash}`` da execução — o que o motor leu e com que regras (#289)."""
    if execucao_id is None:
        return None
    from app.models.motor_juridico import ExecucaoMotor  # noqa: PLC0415
    from app.services.motor_juridico.avaliador import conteudo_execucao  # noqa: PLC0415

    ex = db.get(ExecucaoMotor, execucao_id)
    return conteudo_execucao(db, ex) if ex is not None else None


def base_redacao(db: Session, tenant_id: int, process_id: int, execucao_id: int | None) -> dict:
    # O ID da execução fica para a auditoria; a atualidade compara o CONTEÚDO (#289): reexecutar o
    # motor sem fato nem regra novos não desatualiza nada.
    return {"rotas": base_rotas(db, tenant_id, process_id),
            "diagnostico": base_diagnostico(db, tenant_id, process_id),
            "execucao_motor": execucao_id,
            "motor": conteudo_motor(db, execucao_id)}


def base_orcamento(db: Session, tenant_id: int, process_id: int, escopo: RedacaoComercial | None,
                   codigos: list[str], resolucao: dict[str, list]) -> dict:
    return {"rotas": base_rotas(db, tenant_id, process_id),
            "diagnostico": base_diagnostico(db, tenant_id, process_id),
            "escopo": {"id": escopo.id, "versao": escopo.versao} if escopo else {"id": None, "versao": None},
            "metodos": base_metodos(db, tenant_id, codigos),
            "resolucao": resolucao,
            "escolhas": base_escolhas(db, tenant_id, process_id)}


def hash_base(base: dict) -> str:
    return canonical_hash(base)


# ---------------------------------------------------------------------------
# Atualidade
# ---------------------------------------------------------------------------

def _motivos_rotas(antes: list[dict], agora: list[dict]) -> list[str]:
    motivos = []
    agora_por_id = {r["id"]: r for r in agora}
    for r in antes:
        atual = agora_por_id.get(r["id"])
        if atual is None:
            motivos.append(f"Rota {r['id']} não existe mais")
            continue
        if atual["status"] != r["status"] or atual["validada_em"] != r["validada_em"]:
            motivos.append(f"Rota {r['id']} mudou de estado ({r['status']} → {atual['status']})")
        passos_antes = {p["id"]: p for p in r["passos"]}
        passos_agora = {p["id"]: p for p in atual["passos"]}
        removidos_agora = {p["id"]: p for p in atual["removidos"]}
        for pid, p in passos_antes.items():
            if pid in removidos_agora:
                motivos.append(f"Passo {pid} \"{p['titulo']}\" removido: {removidos_agora[pid]['motivo']}")
            elif pid not in passos_agora:
                motivos.append(f"Passo {pid} \"{p['titulo']}\" saiu da Rota")
            elif passos_agora[pid] != p:
                motivos.append(f"Passo {pid} \"{p['titulo']}\" mudou (classificação, validação ou fundamento)")
        for pid, p in passos_agora.items():
            if pid not in passos_antes:
                motivos.append(f"Passo novo na Rota: {pid} \"{p['titulo']}\"")
    for r in agora:
        if r["id"] not in {x["id"] for x in antes} and r["status"] == RotaStatus.validada.value:
            motivos.append(f"Rota {r['id']} validada depois desta versão")
    return motivos


def motivos_de_desatualizacao(antes: dict, agora: dict) -> list[str]:
    motivos = _motivos_rotas(antes.get("rotas", []), agora.get("rotas", []))
    if antes.get("diagnostico") != agora.get("diagnostico"):
        motivos.append("O diagnóstico mudou desde esta versão (nova conclusão, revisão ou versão)")
    if "motor" in antes and antes["motor"] != agora.get("motor"):
        a, b = antes["motor"] or {}, agora.get("motor") or {}
        ex = agora.get("execucao_motor")
        if a.get("fatos_hash") != b.get("fatos_hash"):
            motivos.append(f"Os fatos lidos pelo motor jurídico mudaram (execução #{ex})")
        if a.get("regras_hash") != b.get("regras_hash"):
            motivos.append(f"As regras do motor jurídico mudaram (execução #{ex})")
    if "escopo" in antes and antes["escopo"] != agora.get("escopo"):
        motivos.append(f"A especificação de escopo mudou (v{antes['escopo']['versao']} → "
                       f"v{(agora.get('escopo') or {}).get('versao')})")
    for codigo, versao in (antes.get("metodos") or {}).items():
        atual = (agora.get("metodos") or {}).get(codigo)
        if atual != versao:
            motivos.append(f"Método \"{codigo}\" mudou (v{versao} → " + (f"v{atual})" if atual else "inativo)"))
    for passo, antes_m in (antes.get("resolucao") or {}).items():
        agora_m = (agora.get("resolucao") or {}).get(passo)
        so_versao = bool(agora_m) and agora_m[0] == antes_m[0] and agora_m[2:] == antes_m[2:]
        if agora_m != antes_m and not so_versao and not any(f"Passo {passo} " in m for m in motivos):
            motivos.append(f"O método do passo {passo} mudaria ({' '.join(map(str, antes_m))} → "
                           f"{' '.join(map(str, agora_m or []))})")
    if "escolhas" in antes and antes["escolhas"] != agora.get("escolhas"):
        motivos.append("Escolha de método ou quantidade do consultor mudou")
    return motivos


def _ultima(db: Session, modelo, **filtros):
    q = db.query(modelo)
    for k, v in filtros.items():
        q = q.filter(getattr(modelo, k) == v)
    return q.order_by(modelo.versao.desc()).first()


def ultima_redacao(db: Session, tenant_id: int, process_id: int, tipo: str) -> RedacaoComercial | None:
    return _ultima(db, RedacaoComercial, tenant_id=tenant_id, process_id=process_id, tipo=tipo)


def ultimo_orcamento(db: Session, tenant_id: int, process_id: int) -> Orcamento | None:
    return _ultima(db, Orcamento, tenant_id=tenant_id, process_id=process_id)


def base_atual_de(db: Session, artefato) -> dict:
    if isinstance(artefato, Orcamento):
        from app.services.comercial.orcamento import resolver_metodos  # noqa: PLC0415

        escopo = ultima_redacao(db, artefato.tenant_id, artefato.process_id, "especificacao_escopo")
        passos = [int(p) for p in (artefato.base.get("resolucao") or {})]
        return base_orcamento(db, artefato.tenant_id, artefato.process_id, escopo,
                              list((artefato.base.get("metodos") or {}).keys()),
                              resolver_metodos(db, artefato.tenant_id, artefato.process_id, passos))
    from app.services.motor_juridico.avaliador import ultima_execucao  # noqa: PLC0415
    ex = ultima_execucao(db, process_id=artefato.process_id, tenant_id=artefato.tenant_id)
    return base_redacao(db, artefato.tenant_id, artefato.process_id, ex.id if ex else None)


def atualidade(db: Session, artefato) -> dict[str, Any]:
    """``{"estado": vigente|desatualizado|superada, "motivos": [...]}`` — só leitura."""
    if artefato.superada_em is not None:
        return {"estado": "superada", "motivos": ["Há versão mais nova deste documento"]}
    antes = artefato.base
    if "execucao_motor" in antes and "motor" not in antes:
        # Base gravada antes do #289 (só o ID): lê o conteúdo daquela execução.
        antes = {**antes, "motor": conteudo_motor(db, antes["execucao_motor"])}
    motivos = motivos_de_desatualizacao(antes, base_atual_de(db, artefato))
    if isinstance(artefato, Orcamento):
        # O orçamento só vale sobre o escopo de que nasceu, aprovado e atual: escopo rejeitado ou
        # desatualizado depois (execução nova do motor, documento novo) arrasta o orçamento junto.
        escopo = db.query(RedacaoComercial).filter(RedacaoComercial.id == artefato.escopo_id,
                                                   RedacaoComercial.tenant_id == artefato.tenant_id).first()
        if escopo is None or escopo.estado_revisao != "aprovada":
            motivos.append("A especificação de escopo de origem não está aprovada "
                           f"({escopo.estado_revisao if escopo else 'ausente'})")
        elif escopo.superada_em is None:
            estado_escopo = atualidade(db, escopo)
            if estado_escopo["estado"] != "vigente":
                motivos += [f"Escopo de origem: {m}" for m in estado_escopo["motivos"]]
    # Documento novo ou decisão da Conferência depois da geração (ADR-068): mesmo aviso
    # que a Rota e a proposta já recebem.
    from app.services.artifact_staleness import checar_desatualizacao  # noqa: PLC0415
    aviso = checar_desatualizacao(db, tenant_id=artefato.tenant_id, process_id=artefato.process_id,
                                  cutoff=artefato.created_at)
    if aviso is not None:
        motivos.append(aviso.motivo)
    return {"estado": "desatualizado" if motivos else "vigente", "motivos": motivos}
