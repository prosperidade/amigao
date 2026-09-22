"""Catálogo normativo sintético para os testes de contrato (ADR-075 §9, camada "Contrato").

Vetores da base canônica: ``base(i)`` tem 1.0 na posição i. Dois vetores de
índices diferentes são ortogonais (distância cosseno 1); o mesmo índice, idênticos.
Assim a similaridade é controlada no teste, sem API de embedding.
"""

from __future__ import annotations

import hashlib
from datetime import date

from sqlalchemy import text

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.models.zona_normativa import (
    Dispositivo,
    FonteNormativa,
    FonteNormativaVersao,
    InterpretacaoNorma,
)

MODELO = "modelo-sintetico-768"


def base(i: int, dim: int = 768) -> list[float]:
    v = [0.0] * dim
    v[i] = 1.0
    return v


def literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.4f}" for x in v) + "]"


def usuario(db, sufixo: str, *, superuser: bool = False, tenant_id: int | None = None) -> User:
    if tenant_id is None:
        t = Tenant(name=f"T {sufixo}")
        db.add(t)
        db.flush()
        tenant_id = t.id
    u = User(email=f"u-{sufixo}@example.com", full_name=sufixo, hashed_password=get_password_hash("x"),
             tenant_id=tenant_id, is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    return u


def fonte(
    db, identidade: str, *, rotulo: str | None = None, nivel: str = "norma", ente: str = "br",
    objetivos: list[str] | None = None, determinada: bool = True, tenant_id: int | None = None,
) -> FonteNormativa:
    tipo = identidade.split("|")[0]
    f = FonteNormativa(
        identidade=identidade, identidade_determinada=determinada, tipo=tipo, ente=ente,
        orgao=identidade.split("|")[2] if identidade.count("|") >= 2 else "",
        numero=identidade.split("|")[3] if identidade.count("|") >= 3 else "",
        esfera="federal" if ente == "br" else "estadual", uf=None if ente == "br" else ente.upper(),
        rotulo=rotulo or identidade, nivel_autoridade=nivel, nivel_origem="teste",
        objetivos=objetivos, tenant_id=tenant_id,
    )
    db.add(f)
    db.flush()
    return f


def versao(
    db, f: FonteNormativa, *, status: str = "bruto", texto: str | None = None,
    vigencia_estado: str = "determinada", inicio: date | None = None, fim: date | None = None,
    bloqueio: str | None = None, hash_original: str | None = None, storage_key: str | None = None,
) -> FonteNormativaVersao:
    texto = texto or f"texto de {f.identidade} {status} {fim}"
    v = FonteNormativaVersao(
        fonte_id=f.id, status_validacao=status, vigencia_estado=vigencia_estado, vigencia_inicio=inicio,
        vigencia_fim=fim, texto=texto, hash_texto=hashlib.sha256(texto.encode()).hexdigest(),
        bloqueio_citacao=bloqueio, origem_ingestao="teste", hash_original=hash_original,
        original_storage_key=storage_key,
    )
    db.add(v)
    db.flush()
    return v


def dispositivo(db, v: FonteNormativaVersao, artigo: str | None, *, rotulo_fonte: str = "Norma",
                paragrafo: str | None = None, parent_id: int | None = None) -> Dispositivo:
    caminho = f"{rotulo_fonte}, art. {artigo}" if artigo else f"{rotulo_fonte}, texto integral"
    if paragrafo:
        caminho += f", § {paragrafo}º"
    d = Dispositivo(fonte_versao_id=v.id, caminho=caminho, tipo="paragrafo" if paragrafo else (
        "artigo" if artigo else "preambulo"), artigo=artigo, paragrafo=paragrafo, parent_id=parent_id,
        ordem=0, texto=caminho, hash=hashlib.sha256(caminho.encode()).hexdigest())
    db.add(d)
    db.flush()
    return d


_ordem: dict[int, int] = {}


def trecho(db, v: FonteNormativaVersao, d: Dispositivo | None, texto: str, vetor: int | list[float],
           *, modelo: str = MODELO, tenant_id: int | None = None) -> int:
    vec = base(vetor) if isinstance(vetor, int) else vetor
    o = _ordem.get(v.id, 0)
    _ordem[v.id] = o + 1
    return db.execute(text(
        "INSERT INTO trecho_normativo (fonte_versao_id, dispositivo_id, ordem, cabecalho, texto, tokens, "
        "embedding, embedding_model, content_hash, tenant_id) VALUES (:v, :d, :o, :c, :t, 1, "
        "CAST(:e AS vector), :m, :h, :tn) RETURNING id"
    ), {"v": v.id, "d": d.id if d else None, "o": o, "c": d.caminho if d else "x", "t": texto,
        "e": literal(vec), "m": modelo, "h": hashlib.sha256(texto.encode()).hexdigest(),
        "tn": tenant_id}).scalar_one()


def ligar(db, interp: FonteNormativa, norma: FonteNormativa, artigo: str | None) -> None:
    db.add(InterpretacaoNorma(interpretacao_fonte_id=interp.id, norma_fonte_id=norma.id, artigo=artigo,
                              citacao_literal=f"art. {artigo}", origem="extraida_do_texto"))
    db.flush()
