"""Curadoria do catálogo normativo (ADR-075 §4, decisão 2, adendos A1 e A2).

**Papel, não pessoa.** Dois papéis delegáveis por área (``*``, ``federal`` ou a
UF): ``curar_corpus`` (ingerir, corrigir, classificar, ``bruto → proposto``) e
``validar_fonte_normativa`` (``proposto → validado``, devolução). A Ísis é a
titular hoje; um advogado ambiental entra com uma concessão, sem mudar o
desenho. Superusuário CONCEDE papel; não o tem por ser superusuário.

**A2 — corpus é leitura para o tenant.** Toda escrita no catálogo passa por
`exigir_papel`, no serviço; o endpoint repete a checagem.

**A1 — `validacao_norma` é append-only** (gatilho no banco) e encadeada por hash
numa cadeia própria do catálogo global — o catálogo não tem tenant, então não
entra na cadeia de auditoria de nenhum tenant.

Transições (§4):

| de → para | papel | exige |
|---|---|---|
| bruto → proposto | curar_corpus | identidade determinada; URL oficial; texto conferido (hash ou palavra-chave); vigência declarada ou "não sei" |
| proposto → validado | validar_fonte_normativa | nível ≠ nao_determinado; original com hash e sem bloqueio (A5) |
| proposto → bruto | validar_fonte_normativa | nota (devolução com motivo) |
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.zona_normativa import (
    FonteNormativa,
    FonteNormativaProveniencia,
    FonteNormativaVersao,
    PapelCuradoria,
    ValidacaoNorma,
)

PAPEIS = ("validar_fonte_normativa", "curar_corpus", "homologar_regra")
_LOCK_CADEIA = 750_075  # pg_advisory_xact_lock — serializa a cadeia global


class CuradoriaNegada(PermissionError):
    """Usuário sem o papel de curadoria para a área."""


class TransicaoInvalida(ValueError):
    """Pré-condição da transição não atendida."""


def area_da_fonte(fonte: FonteNormativa) -> str:
    return "federal" if fonte.ente == "br" else (fonte.uf or fonte.ente.upper())


def tem_papel(session: Session, user: User, papel: str, area: str | None = None) -> bool:
    q = session.query(PapelCuradoria.id).filter(
        PapelCuradoria.user_id == user.id,
        PapelCuradoria.papel == papel,
        PapelCuradoria.revogado_em.is_(None),
    )
    if area is not None:
        q = q.filter(PapelCuradoria.area.in_(("*", area)))
    return q.first() is not None


def exigir_papel(session: Session, user: User, papel: str, area: str | None = None) -> None:
    if not tem_papel(session, user, papel, area):
        onde = f" na área {area}" if area else ""
        raise CuradoriaNegada(f"é preciso o papel '{papel}'{onde} para escrever no catálogo normativo")


def conceder_papel(
    session: Session, *, concedente: User, user_id: int, papel: str, area: str, motivo: str | None = None
) -> PapelCuradoria:
    if not concedente.is_superuser:
        raise CuradoriaNegada("só superusuário concede papel de curadoria")
    if papel not in PAPEIS:
        raise TransicaoInvalida(f"papel desconhecido: {papel}")
    area = area if area in ("*", "federal") else area.upper()
    p = PapelCuradoria(user_id=user_id, papel=papel, area=area, concedido_por_id=concedente.id,
                       motivo=motivo)
    session.add(p)
    session.flush()
    return p


def revogar_papel(session: Session, *, concedente: User, papel_id: int, motivo: str) -> PapelCuradoria:
    if not concedente.is_superuser:
        raise CuradoriaNegada("só superusuário revoga papel de curadoria")
    p = session.get(PapelCuradoria, papel_id)
    if p is None or p.revogado_em is not None:
        raise TransicaoInvalida("papel inexistente ou já revogado")
    p.revogado_em = datetime.now(UTC)
    p.revogado_por_id = concedente.id
    p.motivo = ((p.motivo or "") + f" | revogado: {motivo}").strip(" |")
    session.flush()
    return p


# ---------------------------------------------------------------------------
# Hash chain do catálogo
# ---------------------------------------------------------------------------

def _canonico(ev: dict) -> bytes:
    return json.dumps(ev, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()


def _payload(v: ValidacaoNorma) -> dict:
    return {
        "fonte_versao_id": v.fonte_versao_id, "acao": v.acao, "status_de": v.status_de,
        "status_para": v.status_para, "validador_id": v.validador_id,
        "papel_na_curadoria": v.papel_na_curadoria, "area": v.area, "decisao": v.decisao,
        "nota": v.nota, "hash_texto": v.hash_texto, "evidencias": v.evidencias,
        # UTC explícito: o banco devolve no fuso da sessão, e o hash tem de ser o mesmo.
        "registrado_em": v.registrado_em.astimezone(UTC).isoformat() if v.registrado_em else None,
    }


def _hash_evento(payload: dict, anterior: str | None) -> str:
    return hashlib.sha256((anterior or "").encode() + b"\x00" + _canonico(payload)).hexdigest()


def verificar_cadeia(session: Session) -> dict:
    anterior = None
    n = 0
    for v in session.query(ValidacaoNorma).order_by(ValidacaoNorma.id):
        if v.hash_anterior != anterior:
            return {"integra": False, "evento": v.id, "motivo": "hash_anterior não encadeia"}
        if _hash_evento(_payload(v), anterior) != v.hash_evento:
            return {"integra": False, "evento": v.id, "motivo": "conteúdo não confere com hash_evento"}
        anterior = v.hash_evento
        n += 1
    return {"integra": True, "eventos": n, "ultimo_hash": anterior}


def _registrar_evento(
    session: Session, *, versao: FonteNormativaVersao, user: User, papel: str, area: str,
    acao: str, para: str, decisao: str, nota: str, evidencias: dict | None,
) -> ValidacaoNorma:
    if not (nota or "").strip():
        raise TransicaoInvalida("toda transição exige nota (justificativa)")
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_CADEIA})
    anterior = session.execute(
        text("SELECT hash_evento FROM validacao_norma ORDER BY id DESC LIMIT 1")
    ).scalar_one_or_none()
    ev = ValidacaoNorma(
        fonte_versao_id=versao.id, acao=acao, status_de=versao.status_validacao, status_para=para,
        validador_id=user.id, papel_na_curadoria=papel, area=area, decisao=decisao, nota=nota.strip(),
        hash_texto=versao.hash_texto, evidencias=evidencias,
        registrado_em=datetime.now(UTC).replace(microsecond=0), hash_anterior=anterior,
    )
    ev.hash_evento = _hash_evento(_payload(ev), anterior)
    session.add(ev)
    versao.status_validacao = para
    session.flush()
    return ev


# ---------------------------------------------------------------------------
# Transições
# ---------------------------------------------------------------------------

def _exigir_nota(nota: str) -> None:
    if not (nota or "").strip():
        raise TransicaoInvalida("toda transição exige nota (justificativa)")


def _carregar(session: Session, versao_id: int) -> tuple[FonteNormativaVersao, FonteNormativa]:
    v = session.get(FonteNormativaVersao, versao_id)
    if v is None:
        raise TransicaoInvalida(f"versão {versao_id} inexistente")
    return v, session.get(FonteNormativa, v.fonte_id)


def propor(
    session: Session, *, versao_id: int, user: User, url_oficial: str, texto_conferido_por: str,
    vigencia: str, vigencia_inicio: date | None = None, vigencia_fim: date | None = None,
    nota: str, validation_keyword: str | None = None,
) -> ValidacaoNorma:
    """bruto → proposto: engenharia/curadoria conferiu identidade, texto e vigência."""
    _exigir_nota(nota)
    v, f = _carregar(session, versao_id)
    area = area_da_fonte(f)
    exigir_papel(session, user, "curar_corpus", area)
    if v.status_validacao != "bruto":
        raise TransicaoInvalida(f"versão está {v.status_validacao}; propor parte de bruto")
    if not f.identidade_determinada:
        raise TransicaoInvalida("identidade não determinada — resolver a revisão de fronteira antes")
    if not (url_oficial or "").strip().lower().startswith(("http://", "https://")):
        raise TransicaoInvalida("URL oficial obrigatória para conferir a identidade")
    if texto_conferido_por not in ("hash", "validation_keyword"):
        raise TransicaoInvalida("texto conferido por 'hash' ou 'validation_keyword' (ADR-038)")
    if texto_conferido_por == "validation_keyword":
        # Espaço colapsado dos dois lados: o texto extraído quebra linha no meio da frase.
        def _c(s: str) -> str:
            return " ".join((s or "").split())

        if not validation_keyword or _c(validation_keyword) not in _c(v.texto):
            raise TransicaoInvalida("validation_keyword ausente do texto da versão")
    if vigencia not in ("vigente", "revogada", "nao_sei"):
        raise TransicaoInvalida("vigência declarada: 'vigente', 'revogada' ou 'nao_sei'")
    if vigencia == "revogada" and vigencia_fim is None:
        raise TransicaoInvalida("revogada exige data de fim")
    if vigencia != "nao_sei":
        v.vigencia_estado = "determinada"
        v.vigencia_inicio = vigencia_inicio
        v.vigencia_fim = vigencia_fim if vigencia == "revogada" else None
    return _registrar_evento(
        session, versao=v, user=user, papel="curar_corpus", area=area, acao="propor", para="proposto",
        decisao="aprovado", nota=nota,
        evidencias={"url_oficial": url_oficial, "texto_conferido_por": texto_conferido_por,
                    "validation_keyword": validation_keyword, "vigencia": vigencia,
                    "vigencia_inicio": vigencia_inicio.isoformat() if vigencia_inicio else None,
                    "vigencia_fim": vigencia_fim.isoformat() if vigencia_fim else None},
    )


def validar(
    session: Session, *, versao_id: int, user: User, nota: str, lote: dict | None = None
) -> ValidacaoNorma:
    """proposto → validado: leitura da ficha pelo curador com alçada na área."""
    _exigir_nota(nota)
    v, f = _carregar(session, versao_id)
    area = area_da_fonte(f)
    exigir_papel(session, user, "validar_fonte_normativa", area)
    if v.status_validacao != "proposto":
        raise TransicaoInvalida(f"versão está {v.status_validacao}; validar parte de proposto")
    if f.nivel_autoridade == "nao_determinado":
        raise TransicaoInvalida("nível de autoridade não determinado")
    if not v.hash_original or not v.original_storage_key:
        raise TransicaoInvalida("sem hash e objeto do original não há como conferir adulteração (A5)")
    if v.bloqueio_citacao:
        raise TransicaoInvalida(f"versão bloqueada: {v.bloqueio_citacao}")
    return _registrar_evento(
        session, versao=v, user=user, papel="validar_fonte_normativa", area=area, acao="validar",
        para="validado", decisao="aprovado", nota=nota, evidencias={"lote": lote} if lote else None,
    )


def devolver(session: Session, *, versao_id: int, user: User, nota: str) -> ValidacaoNorma:
    _exigir_nota(nota)
    v, f = _carregar(session, versao_id)
    area = area_da_fonte(f)
    exigir_papel(session, user, "validar_fonte_normativa", area)
    if v.status_validacao != "proposto":
        raise TransicaoInvalida("só se devolve o que está proposto")
    return _registrar_evento(
        session, versao=v, user=user, papel="validar_fonte_normativa", area=area, acao="devolver",
        para="bruto", decisao="devolvido", nota=nota, evidencias=None,
    )


# ---------------------------------------------------------------------------
# Lote por coletânea desmembrada (§4: a Ísis confere uma coletânea de uma vez)
# ---------------------------------------------------------------------------

def versoes_da_coletanea(session: Session, legislation_document_id: int) -> list[FonteNormativaVersao]:
    return (
        session.query(FonteNormativaVersao)
        .join(FonteNormativaProveniencia, FonteNormativaProveniencia.fonte_versao_id == FonteNormativaVersao.id)
        .filter(FonteNormativaProveniencia.legislation_document_id == legislation_document_id)
        .distinct()
        .order_by(FonteNormativaVersao.id)
        .all()
    )


def propor_lote_coletanea(
    session: Session, *, legislation_document_id: int, user: User, nota: str,
    excluir_versoes: set[int] | frozenset[int] = frozenset(),
) -> dict:
    """Propõe os atos da coletânea com a URL impressa de cada um como fonte oficial
    de conferência. Ato sem URL impressa, identidade não fechada ou com motivo de
    revisão de fronteira fica de fora — relatado, não forçado."""
    out = {"propostas": 0, "puladas": []}
    for v in versoes_da_coletanea(session, legislation_document_id):
        if v.id in excluir_versoes or v.status_validacao != "bruto":
            continue
        prov = (
            session.query(FonteNormativaProveniencia)
            .filter(FonteNormativaProveniencia.fonte_versao_id == v.id,
                    FonteNormativaProveniencia.legislation_document_id == legislation_document_id)
            .first()
        )
        fonte = session.get(FonteNormativa, v.fonte_id)
        motivo = None
        if not fonte.identidade_determinada or fonte.nivel_autoridade == "nao_determinado":
            motivo = "identidade ou nível não determinado"
        elif prov.motivos_revisao:
            motivo = f"fronteira em revisão: {prov.motivos_revisao}"
        elif not prov.url_impressa:
            motivo = "sem URL impressa para conferir"
        if motivo:
            out["puladas"].append({"versao": v.id, "rotulo": fonte.rotulo, "motivo": motivo})
            continue
        url = prov.url_impressa if prov.url_impressa.startswith("http") else f"https://{prov.url_impressa}"
        propor(session, versao_id=v.id, user=user, url_oficial=url, texto_conferido_por="hash",
               vigencia="nao_sei", nota=nota)
        out["propostas"] += 1
    return out


def validar_lote_coletanea(
    session: Session, *, legislation_document_id: int, user: User, nota: str,
    excluir_versoes: set[int] | frozenset[int] = frozenset(),
) -> dict:
    out = {"validadas": 0, "puladas": []}
    lote = {"coletanea": legislation_document_id, "excluidas": sorted(excluir_versoes)}
    for v in versoes_da_coletanea(session, legislation_document_id):
        if v.id in excluir_versoes or v.status_validacao != "proposto":
            continue
        try:
            validar(session, versao_id=v.id, user=user, nota=nota, lote=lote)
            out["validadas"] += 1
        except TransicaoInvalida as exc:
            out["puladas"].append({"versao": v.id, "motivo": str(exc)})
    return out
