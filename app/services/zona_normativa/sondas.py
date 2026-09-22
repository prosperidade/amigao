"""Sondas de recuperação (ADR-075 §9) — qualidade medida por ID, nunca por regex no texto.

Cada sonda tem pergunta, contexto e, conforme o grupo:
- ``alvo``: lista de ``{fonte: <identidade canônica>, dispositivo: <artigo>|null}``;
  acerto = algum alvo entre as ``k`` vagas devolvidas, casado por identidade da
  fonte + artigo (o ``art61a`` "recuperado" por regex de hoje é falso positivo);
- ``anexos_esperados``: interpretações que têm de vir ANEXADAS ao alvo;
- ``vazio_esperado``: razão do vazio (controle negativo).

Métricas e portão fixos: recall@5 ≥ 0,9 nas positivas; controle negativo 100%
vazio com a razão certa; anexos presentes; groundedness 100% — toda vaga
devolvida resolve para trecho elegível com fonte e dispositivo (verificado pela
citação por ID); zero citação órfã.

Os vetores das perguntas ficam em cache versionado (`vetores_sondas.json`),
chaveados por modelo + hash da pergunta: a rodada noturna e a de PR não pagam
embedding nem dependem do provedor para medir.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass, field
from datetime import date

import yaml
from sqlalchemy.orm import Session

from app.services.zona_normativa.citacao import Afirmacao, Citacao, envelope_de_resultado, verificar
from app.services.zona_normativa.recuperacao import RAZOES, Contexto, recuperar

RAIZ = pathlib.Path(__file__).resolve().parents[3] / "tests" / "recuperacao"
ARQUIVO_SONDAS = RAIZ / "sondas.yaml"
ARQUIVO_VETORES = RAIZ / "vetores_sondas.json"

PORTAO_RECALL = 0.9
K = 5


def carregar_sondas(caminho: pathlib.Path = ARQUIVO_SONDAS) -> list[dict]:
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))["sondas"]


def chave_vetor(modelo: str, pergunta: str) -> str:
    return f"{modelo}:{hashlib.sha256(pergunta.encode()).hexdigest()[:24]}"


def validar_formato(sondas: list[dict]) -> list[str]:
    """Erros de forma — roda em todo PR, sem banco."""
    erros = []
    ids = [s.get("id") for s in sondas]
    if len(ids) != len(set(ids)):
        erros.append("ids repetidos")
    if not 30 <= len(sondas) <= 50:
        erros.append(f"{len(sondas)} sondas; o ADR pede 30–50")
    for s in sondas:
        sid = s.get("id")
        if not s.get("grupo") or not isinstance(s.get("contexto"), dict):
            erros.append(f"{sid}: sem grupo/contexto")
            continue
        if ("alvo" in s) == ("vazio_esperado" in s):
            erros.append(f"{sid}: exatamente um de alvo / vazio_esperado")
        if "vazio_esperado" in s and s["vazio_esperado"] not in RAZOES:
            erros.append(f"{sid}: razão {s['vazio_esperado']!r} fora das cinco do ADR")
        for a in s.get("alvo") or []:
            if a.get("fonte", "").count("|") != 4:
                erros.append(f"{sid}: alvo {a!r} não é identidade canônica tipo|ente|orgao|numero|ano")
        if s.get("status_alvo") not in ("proposto", "validado"):
            erros.append(f"{sid}: status_alvo deve ser proposto (até a curadoria validar) ou validado")
    return erros


@dataclass
class ResultadoSonda:
    id: str
    grupo: str
    ok: bool
    detalhe: str
    posicao: int | None = None
    vagas: list[str] = field(default_factory=list)


def _ctx(s: dict) -> Contexto:
    c = s["contexto"]
    return Contexto(
        pergunta=s.get("pergunta", ""), uso=c.get("uso", "descoberta"),
        data_referencia=date.fromisoformat(str(c["data_ref"])) if c.get("data_ref") else None,
        objetivo=c.get("objetivo"), esferas=tuple(c.get("esferas") or ()), uf=c.get("uf"),
        norma=c.get("norma"), artigo=c.get("artigo"), limite=K,
    )


def rodar(session: Session, sondas: list[dict], *, vetores: dict[str, list[float]], modelo: str) -> dict:
    resultados: list[ResultadoSonda] = []
    orfas = 0
    nao_ancoradas = 0
    for s in sondas:
        ctx = _ctx(s)

        def _embed(p: str, _s=s) -> list[float]:
            v = vetores.get(chave_vetor(modelo, p))
            if v is None:
                raise KeyError(f"vetor da sonda {_s['id']} fora do cache — rode com --embarcar")
            return v

        r = recuperar(session, ctx, embed_query=_embed, modelo=modelo)
        vagas = [f"{t.identidade_fonte}#{t.artigo or '-'}" for t in r.trechos]
        if "vazio_esperado" in s:
            ok = r.vazio is not None and r.vazio.razao == s["vazio_esperado"]
            det = f"vazio={r.vazio.razao if r.vazio else None}"
            resultados.append(ResultadoSonda(s["id"], s["grupo"], ok, det, vagas=vagas))
            continue
        pos = None
        for i, t in enumerate(r.trechos[:K], 1):
            for a in s["alvo"]:
                if t.identidade_fonte == a["fonte"] and (a.get("dispositivo") in (None, t.artigo)):
                    pos = pos or i
        ok = pos is not None
        det = f"posição {pos}" if ok else (f"vazio={r.vazio.razao}:{r.vazio.filtro_que_esvaziou}"
                                           if r.vazio else "alvo fora das 5 vagas")
        for anexo in s.get("anexos_esperados") or []:
            alvo_t = next((t for t in r.trechos if t.identidade_fonte == s["alvo"][0]["fonte"]), None)
            achou = alvo_t is not None and any(
                _identidade_de(session, i["interpretacao_fonte_id"]) == anexo["fonte"]
                for i in alvo_t.interpretacoes
            )
            if not achou:
                ok = False
                det += f"; anexo {anexo['fonte']} ausente"
        # groundedness: cada vaga citada por ID passa na verificação de pertencimento
        if r.trechos:
            env = envelope_de_resultado(session, r)
            afirm = [Afirmacao("", [Citacao(t.fonte_versao_id, t.artigo or "texto integral")])
                     for t in r.trechos if t.dispositivo_id is not None]
            nao_ancoradas += sum(1 for t in r.trechos if t.dispositivo_id is None)
            ver = verificar(session, afirm, env, destino=ctx.uso, data_referencia=ctx.data_referencia)
            orfas += sum(1 for f in ver.falhas if f.tipo in ("id_fora_do_envelope", "dispositivo_inexistente"))
        resultados.append(ResultadoSonda(s["id"], s["grupo"], ok, det, pos, vagas))

    pos_ = [x for x in resultados if "vazio_esperado" not in _por_id(sondas, x.id)]
    neg = [x for x in resultados if "vazio_esperado" in _por_id(sondas, x.id)]
    recall = sum(x.ok for x in pos_) / len(pos_) if pos_ else 0.0
    negativo = sum(x.ok for x in neg) / len(neg) if neg else 0.0
    return {
        "recall_at_5": round(recall, 3), "positivas": len(pos_), "acertos": sum(x.ok for x in pos_),
        "controle_negativo": round(negativo, 3), "negativas": len(neg),
        "groundedness_falhas": orfas + nao_ancoradas,
        "portao": recall >= PORTAO_RECALL and negativo == 1.0 and orfas + nao_ancoradas == 0,
        "resultados": [x.__dict__ for x in resultados],
    }


def _por_id(sondas: list[dict], sid: str) -> dict:
    return next(s for s in sondas if s["id"] == sid)


def _identidade_de(session: Session, fonte_id: int) -> str:
    from app.models.zona_normativa import FonteNormativa  # noqa: PLC0415

    f = session.get(FonteNormativa, fonte_id)
    return f.identidade if f else ""


def carregar_vetores(caminho: pathlib.Path = ARQUIVO_VETORES) -> dict[str, list[float]]:
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar_vetores(vetores: dict[str, list[float]], caminho: pathlib.Path = ARQUIVO_VETORES) -> None:
    caminho.write_text(
        json.dumps({k: [round(x, 6) for x in v] for k, v in sorted(vetores.items())}, separators=(",", ":")),
        encoding="utf-8",
    )
