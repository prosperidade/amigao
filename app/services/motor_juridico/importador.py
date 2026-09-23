"""Importa a tradução formal (YAML versionado no repositório) para `regra`/`regra_versao`.

Idempotente: a mesma regra com o mesmo conteúdo não gera versão nova (hash). Conteúdo
diferente gera a versão seguinte, em `rascunho` — a homologada anterior segue valendo
no conjunto em que está, até outro conjunto ser ativado. Nada aqui homologa.

Regra que a engenharia não consegue formalizar entra `nao_formalizavel`, com motivo e
sem condição, e nunca publica (ADR-073 §2).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.motor_juridico import Regra, RegraVersao
from app.services.motor_juridico.linguagem import validar_aplicabilidade, validar_condicao

REGRAS_DIR = Path(__file__).parent / "regras"
GATE_4B = REGRAS_DIR / "gate_4b.yaml"

TIPOS_EFEITO = ("passo_rota", "coleta", "alerta_critico")


class TraducaoInvalida(ValueError):
    """A tradução formal não passa na validação — erro de engenharia, não do caso."""


@dataclass
class Importacao:
    criadas: list[RegraVersao]
    mantidas: list[RegraVersao]


def carregar(caminho: Path = GATE_4B) -> dict:
    with open(caminho, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def chave_origem(planilha: dict, rule_id: str) -> str:
    """``matriz:versao:id`` — há IDs que colidem entre matrizes (REG-GOV-001/002/003)."""
    return f"{planilha['matriz']}:{planilha['versao_planilha']}:{rule_id}"


def validar_efeitos(consequencia: dict) -> list[str]:
    efeitos = (consequencia or {}).get("efeitos")
    if not isinstance(efeitos, list) or not efeitos:
        return ["consequencia.efeitos: lista não vazia obrigatória"]
    erros = []
    for i, e in enumerate(efeitos):
        if e.get("tipo") not in TIPOS_EFEITO:
            erros.append(f"efeitos[{i}]: tipo {e.get('tipo')!r} fora de {TIPOS_EFEITO}")
        if not (e.get("titulo") or "").strip():
            erros.append(f"efeitos[{i}]: título obrigatório")
    return erros


def conteudo(planilha: dict, r: dict) -> dict:
    """O conteúdo IMUTÁVEL de uma versão — é sobre ele que o hash é calculado."""
    return {
        "descricao": r["descricao"],
        "mensagem": r.get("mensagem"),
        "aplicabilidade": r.get("aplicabilidade") or {},
        "condicao": r.get("condicao"),
        "consequencia": r["consequencia"],
        "fundamento": r.get("fundamento"),
        "severidade": r.get("severidade"),
        "decisao_profissional": r.get("decisao_profissional"),
        "origem": {
            "arquivo": planilha["arquivo"], "pacote": planilha.get("pacote"), "sha256": planilha["sha256"],
            "aba": planilha["aba"], "linha": r["linha"], "versao_planilha": planilha["versao_planilha"],
            "matriz": planilha["matriz"], "rule_id": r["rule_id"],
            "texto_condicao": r.get("texto_condicao"), "texto_resultado": r.get("texto_resultado"),
            "recorte": r.get("recorte"), "nao_formalizavel": r.get("nao_formalizavel"),
        },
    }


def hash_conteudo(c: dict) -> str:
    return hashlib.sha256(json.dumps(c, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validar_regra(r: dict) -> list[str]:
    if r.get("nao_formalizavel"):
        return [] if not r.get("condicao") else ["nao_formalizavel não leva condição"]
    return (validar_aplicabilidade(r.get("aplicabilidade") or {}) + validar_condicao(r.get("condicao"))
            + validar_efeitos(r.get("consequencia")))


def importar(session: Session, dados: dict, *, tenant_id: int | None = None) -> Importacao:
    erros = {r["rule_id"]: e for r in dados["regras"] if (e := validar_regra(r))}
    if erros:
        raise TraducaoInvalida(f"tradução recusada: {erros}")

    criadas: list[RegraVersao] = []
    mantidas: list[RegraVersao] = []
    for r in dados["regras"]:
        planilha = dados["planilhas"][r["planilha"]]
        chave = chave_origem(planilha, r["rule_id"])
        regra = session.query(Regra).filter(
            Regra.chave_origem == chave,
            Regra.tenant_id.is_(None) if tenant_id is None else Regra.tenant_id == tenant_id,
        ).one_or_none()
        if regra is None:
            regra = Regra(chave_origem=chave, rule_id=r["rule_id"], matriz=str(planilha["matriz"]),
                          eixo=r.get("eixo"), familia=r.get("familia"), tenant_id=tenant_id)
            session.add(regra)
            session.flush()

        c = conteudo(planilha, r)
        h = hash_conteudo(c)
        existente = session.query(RegraVersao).filter_by(regra_id=regra.id, hash_conteudo=h).one_or_none()
        if existente is not None:
            mantidas.append(existente)
            continue
        ultima = session.query(func.max(RegraVersao.versao)).filter_by(regra_id=regra.id).scalar() or 0
        rv = RegraVersao(
            regra_id=regra.id, versao=ultima + 1, hash_conteudo=h,
            estado="nao_formalizavel" if r.get("nao_formalizavel") else "rascunho",
            motivo_nao_formalizavel=r.get("nao_formalizavel"), **c,
        )
        session.add(rv)
        session.flush()
        criadas.append(rv)
    return Importacao(criadas=criadas, mantidas=mantidas)
