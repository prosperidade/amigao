"""O que está por trás de uma evidência por ID — o clique da tela (dívidas #278 e #282).

A afirmação do relatório, do escopo e o passo da Rota citam evidência como ``{tipo, id}``
(ADR-074 §2). A tela precisa abrir cada uma: o texto do dispositivo, a observação com a âncora
no documento, a avaliação da regra com os fatos que faltaram. Este módulo devolve essa leitura
com as MESMAS travas de :func:`evidencia._existentes` (tenant e caso): um ID que não resolve
aqui é 404, nunca "o mais parecido".

Somente leitura. Cada detalhe traz ``refs`` — as evidências que ele mesmo cita (o passo cita o
dispositivo; a observação cita o documento) —, para a tela seguir a cadeia por ID.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.evidence import EvidenceVersion
from app.models.motor_juridico import AvaliacaoRegra, CienciaAlerta, ExecucaoMotor, Regra, RegraVersao
from app.models.rota import Rota, RotaPasso
from app.models.zona_normativa import Dispositivo, FonteNormativa, FonteNormativaVersao
from app.services.comercial import evidencia as ev

# Texto de norma pode ter centenas de milhares de caracteres; a tela mostra o começo e diz que cortou.
_LIMITE_TEXTO = 6000


def _v(valor: Any) -> str | None:
    if valor is None or valor == "" or valor == []:
        return None
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(getattr(valor, "value", valor))


def _campos(*pares: tuple[str, Any]) -> list[dict]:
    return [{"rotulo": r, "valor": _v(v)} for r, v in pares if _v(v) is not None]


def _texto(texto: str | None) -> tuple[str | None, bool]:
    if not texto:
        return None, False
    return (texto[:_LIMITE_TEXTO], True) if len(texto) > _LIMITE_TEXTO else (texto, False)


def _fonte_de(db: Session, fonte_versao_id: int) -> tuple[FonteNormativaVersao, FonteNormativa]:
    return (db.query(FonteNormativaVersao, FonteNormativa)
            .join(FonteNormativa, FonteNormativa.id == FonteNormativaVersao.fonte_id)
            .filter(FonteNormativaVersao.id == fonte_versao_id).one())


def _dispositivo(db: Session, id_: int) -> dict:
    d = db.query(Dispositivo).filter(Dispositivo.id == id_).one()
    fv, f = _fonte_de(db, d.fonte_versao_id)
    texto, cortado = _texto(d.texto)
    # O caminho costuma já trazer a norma ("Lei 12.651/2012, art. 29"); não repetir.
    titulo = d.caminho if d.caminho.startswith(f.rotulo) else f"{f.rotulo} — {d.caminho}"
    return {"titulo": titulo, "texto": texto, "texto_cortado": cortado,
            "campos": _campos(("Norma", f.rotulo), ("Dispositivo", d.caminho), ("Versão da fonte", fv.id),
                              ("Validação da fonte", fv.status_validacao), ("Vigência", fv.vigencia_estado),
                              ("Hash do dispositivo", d.hash)),
            "refs": [ev.ref("fonte_versao", fv.id, f"{f.rotulo} (versão {fv.id})")]}


def _fonte_versao(db: Session, id_: int) -> dict:
    fv, f = _fonte_de(db, id_)
    texto, cortado = _texto(fv.texto)
    return {"titulo": f.rotulo, "texto": texto, "texto_cortado": cortado,
            "campos": _campos(("Título", f.titulo), ("Identidade", f.identidade), ("Esfera", f.esfera),
                              ("Validação", fv.status_validacao), ("Vigência", fv.vigencia_estado),
                              ("Início da vigência", fv.vigencia_inicio), ("Fim da vigência", fv.vigencia_fim),
                              ("Hash do texto", fv.hash_texto)),
            "refs": []}


def _evidencia_do_caso(db: Session, id_: int) -> dict:
    e = db.query(EvidenceVersion).filter(EvidenceVersion.id == id_).one()
    c = e.content or {}
    at = c.get("attributes") or {}
    literal = at.get("literal") or at.get("anchor")
    texto, cortado = _texto(c.get("statement") or literal)
    refs = []
    if e.source_document_id:
        refs.append(ev.ref("documento", e.source_document_id, f"documento #{e.source_document_id}"))
    return {"titulo": f"{e.kind} {e.object_id} v{e.version}", "texto": texto, "texto_cortado": cortado,
            "campos": _campos(("Objeto", e.object_id), ("Versão", e.version), ("Classe", c.get("conclusion_class")),
                              ("Predicado", at.get("predicate")), ("Valor", at.get("value")),
                              ("Âncora no documento", at.get("anchor") if c.get("statement") else None),
                              ("Página", at.get("page")), ("Certeza", at.get("certainty")),
                              ("Estado do conhecimento", (c.get("knowledge") or {}).get("state")),
                              ("Premissas", ", ".join(f"{p.get('id')} v{p.get('version')}"
                                                      for p in c.get("premises") or [])),
                              ("Limites", " · ".join(c.get("limits") or [])), ("Hash", e.content_hash)),
            "refs": refs}


def _documento(db: Session, id_: int) -> dict:
    d = db.query(Document).filter(Document.id == id_).one()
    return {"titulo": d.original_file_name or d.filename, "texto": None, "texto_cortado": False,
            "campos": _campos(("Tipo", d.document_type), ("Categoria", d.document_category),
                              ("Versão", d.version_number), ("SHA-256", d.checksum_sha256)),
            "refs": [], "documento_id": d.id}


def _avaliacao(db: Session, id_: int) -> dict:
    a, rv, rule_id = (db.query(AvaliacaoRegra, RegraVersao, Regra.rule_id)
                      .join(RegraVersao, RegraVersao.id == AvaliacaoRegra.regra_versao_id)
                      .join(Regra, Regra.id == RegraVersao.regra_id)
                      .filter(AvaliacaoRegra.id == id_).one())
    efeitos = (a.consequencia or {}).get("efeitos", [])
    refs = [ev.ref("execucao_motor", a.execucao_id, f"execução do motor #{a.execucao_id}")]
    if a.fundamento_dispositivo_id:
        refs.append(ev.ref("dispositivo", a.fundamento_dispositivo_id, a.fundamento_caminho or "dispositivo"))
    ciencia = db.query(CienciaAlerta).filter(CienciaAlerta.avaliacao_id == a.id).first()
    if ciencia:
        refs.append(ev.ref("ciencia_alerta", ciencia.id, f"ciência #{ciencia.id}"))
    return {"titulo": f"{rule_id} — {a.estado}", "texto": rv.mensagem or rv.descricao, "texto_cortado": False,
            "campos": _campos(("Regra", f"{rule_id} v{rv.versao}"), ("Estado", a.estado),
                              ("Severidade", rv.severidade),
                              ("Fatos que faltaram", ", ".join(a.faltantes or [])),
                              ("Efeitos", ", ".join(str(x.get("tipo")) for x in efeitos)),
                              ("Fundamento", a.fundamento_caminho),
                              ("Sem fundamento resolvido", a.fundamento_razao if not a.fundamento_dispositivo_id else None),
                              ("Erro", a.detalhe_erro)),
            "refs": refs}


def _ciencia(db: Session, id_: int) -> dict:
    c = db.query(CienciaAlerta).filter(CienciaAlerta.id == id_).one()
    return {"titulo": f"Ciência do alerta (avaliação #{c.avaliacao_id})", "texto": c.justificativa,
            "texto_cortado": False,
            "campos": _campos(("Registrada por (usuário)", c.user_id), ("Registrada em", c.registrada_em)),
            "refs": [ev.ref("avaliacao_regra", c.avaliacao_id, f"avaliação #{c.avaliacao_id}")]}


def _execucao(db: Session, id_: int) -> dict:
    x = db.query(ExecucaoMotor).filter(ExecucaoMotor.id == id_).one()
    fatos = x.fatos or {}
    determinados = sorted(k for k, v in fatos.items() if isinstance(v, dict) and v.get("estado") != "nao_determinado")
    return {"titulo": f"Execução do motor #{x.id}", "texto": None, "texto_cortado": False,
            "campos": _campos(("Data de referência", x.data_referencia), ("Conjunto de regras", x.conjunto_id),
                              ("Conjunto do tenant", x.conjunto_tenant_id), ("Fatos lidos", len(fatos)),
                              ("Fatos determinados", ", ".join(determinados)), ("Hash dos fatos", x.fatos_hash),
                              ("Criada em", x.criado_em)),
            "refs": []}


def _rota(db: Session, id_: int) -> dict:
    r = db.query(Rota).filter(Rota.id == id_).one()
    return {"titulo": f"Rota #{r.id}", "texto": r.caminho_regulatorio, "texto_cortado": False,
            "campos": _campos(("Estado", r.status), ("Órgão competente", r.orgao_competente),
                              ("Assinada em", r.validated_at), ("Assinada por (usuário)", r.validated_by)),
            "refs": []}


def _passo(db: Session, id_: int) -> dict:
    from app.services.comercial.base import motivo_remocao  # noqa: PLC0415

    p = db.query(RotaPasso).filter(RotaPasso.id == id_).one()
    refs = [ev.ref("rota", p.rota_id, f"Rota #{p.rota_id}")]
    if p.fundamento_dispositivo_id:
        refs.append(ev.ref("dispositivo", p.fundamento_dispositivo_id, p.norma_ref or "dispositivo"))
    if p.origem_avaliacao_id:
        refs.append(ev.ref("avaliacao_regra", p.origem_avaliacao_id, f"avaliação #{p.origem_avaliacao_id}"))
    return {"titulo": p.titulo, "texto": p.descricao, "texto_cortado": False,
            "campos": _campos(("Origem", p.origem), ("Estado", p.status), ("Classificação", p.classificacao),
                              ("Órgão", p.orgao), ("Norma", p.norma_ref),
                              ("Removido em", p.deleted_at),
                              ("Motivo da remoção", motivo_remocao(db, p) if p.deleted_at else None)),
            "refs": refs}


_LEITORES = {"dispositivo": _dispositivo, "fonte_versao": _fonte_versao, "observacao": _evidencia_do_caso,
             "fonte_primaria": _evidencia_do_caso, "conclusao": _evidencia_do_caso, "documento": _documento,
             "avaliacao_regra": _avaliacao, "ciencia_alerta": _ciencia, "execucao_motor": _execucao,
             "rota": _rota, "rota_passo": _passo}


def detalhar(db: Session, tipo: str, id_: int, *, tenant_id: int, process_id: int) -> dict | None:
    """A evidência ``(tipo, id)`` deste caso, pronta para a tela; ``None`` se não resolve aqui."""
    if tipo not in _LEITORES:
        return None
    if id_ not in ev._existentes(db, tipo, {id_}, tenant_id=tenant_id, process_id=process_id):
        return None
    return {"tipo": tipo, "id": id_, "documento_id": None, **_LEITORES[tipo](db, id_)}
