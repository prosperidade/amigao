"""Diagnóstico por afirmação no contrato de evidência (ADR-080, dívida #285).

Duas peças:

- ``PROMPT_BASE`` — o prompt-base do diagnóstico no contrato 069. Substitui o
  ``diagnostico_system`` legado, que pedia ``situacao_geral`` e fazia o modelo ignorar o
  contrato (job 201 do #25 de dev).
- ``recusas`` — regras de admissão D1 a D7, determinísticas. A afirmação que viola uma regra é
  recusada e a execução falha com a lista; nada é gravado.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.evidence import (
    Contract,
    EvidenceObject,
    EvidenceRef,
    ExecutionEnvelope,
    Knowledge,
    canonical_hash,
)

CONTRATO_VERSAO = "080.3"

CERTEZAS = ("alta", "media", "baixa")
IMPACTOS = ("informativo", "atencao", "alto", "critico_impeditivo_potencial")
URGENCIAS = ("alta", "media", "baixa")
# Classes que afirmam algo sobre o mundo ou comprometem serviço: exigem premissa documental.
CLASSES_DOCUMENTAIS = ("risco", "fato_documental", "escopo_proposto")
ORIGENS_DOCUMENTAIS = ("documento", "consulta")

PROMPT_BASE = """\
Você é o agente Diagnóstico do Regente Ambiental. Sua tarefa é ler o envelope do caso e propor
AFIRMAÇÕES de diagnóstico para o consultor revisar uma a uma. Você não decide: propõe.

FORMATO (obrigatório, único): um objeto JSON com a chave "objects", uma lista. Cada item é UMA
afirmação, no schema ao final. Não use outro formato: nada de situacao_geral,
passivos_identificados, riscos ou hipoteses soltos. Nenhum texto fora do JSON. Não inclua id,
version, kind nem origin: o servidor atribui.

CADA AFIRMAÇÃO TEM:
- statement: uma frase afirmativa, verificável, sobre este caso.
- conclusion_class: fato_documental (o documento diz), divergencia (fontes discordam), lacuna
  (falta o dado), hipotese (plausível, sem prova suficiente), risco (pode comprometer o caso),
  orientacao (próximo passo de verificação), escopo_proposto (serviço sugerido).
- premises: lista de {"id", "version"} COPIADOS do envelope (sources, observations, derivations,
  conclusions). Pelo menos uma. Nunca invente id. Premissa é o que sustenta a afirmação.
- attributes.certainty: alta, media ou baixa. "alta" só com premissa documental (fonte primária
  de documento ou observação extraída de documento).
- attributes.impact (obrigatório em risco): informativo, atencao, alto ou
  critico_impeditivo_potencial — os 4 níveis do método.
- attributes.urgency (opcional): alta, media ou baixa. "alta" só em risco aplicável.
- risco e escopo_proposto: applicability="aplicavel" e applicability_reason dizendo por que se
  aplica a ESTE caso.
- limits: o que a afirmação não cobre.

A classe (risco, lacuna, orientacao, escopo_proposto…) vai em "conclusion_class", em todos os itens.
Exemplo de UM item (os ids de premissa são ilustrativos; use os do envelope):
{"statement": "…", "conclusion_class": "risco",
 "attributes": {"certainty": "media", "impact": "alto", "urgency": "media"},
 "applicability": "aplicavel", "applicability_reason": "…",
 "premises": [{"id": "<id do envelope>", "version": 1}], "limits": ["…"]}

REGRAS DE SUPORTE (o servidor recusa o que as viola):
- Ausência de informação é LACUNA (ou hipótese), nunca risco nem fato. "Não consta nos autos" não
  prova que não existe.
- risco, fato_documental e escopo_proposto exigem premissa documental; inventário, declaração do
  cadastro ou outra conclusão, sozinhos, não bastam.
- "Ausência verificada" exige consulta e resposta preservadas; sem isso, lacuna.
- Não afirme obrigação legal sem regra ou norma do envelope; normas citadas no método são
  referência a conferir, não fundamento.
- Poucas afirmações bem sustentadas valem mais que muitas fracas. Se nada se sustenta, devolva
  {"objects": []}.
"""


class AtributosAfirmacao(Contract):
    """As três dimensões que o modelo decide. Referências a documento, fragmento ou cobertura
    não são dele: não passariam pela conferência do envelope."""

    certainty: str | None = None
    impact: str | None = None
    urgency: str | None = None


class AfirmacaoDiagnostico(Contract):
    """O que o modelo decide numa afirmação. Identidade, espécie e origem são do servidor."""

    statement: str = Field(min_length=1)
    conclusion_class: Literal[
        "fato_documental", "divergencia", "lacuna", "hipotese", "risco", "orientacao", "escopo_proposto",
    ]
    premises: list[EvidenceRef] = Field(default_factory=list)
    attributes: AtributosAfirmacao = Field(default_factory=AtributosAfirmacao)
    knowledge: Knowledge = Field(default_factory=Knowledge)
    applicability: str | None = None
    applicability_reason: str | None = None
    norms: list[EvidenceRef] = Field(default_factory=list)
    rules: list[EvidenceRef] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)


SCHEMA_AFIRMACAO = AfirmacaoDiagnostico.model_json_schema()
_DO_SERVIDOR = ("id", "version", "origin")


def para_objetos(itens: list) -> list[EvidenceObject]:
    """Afirmações do modelo → conclusões do contrato. Campos de identidade são descartados
    (o servidor atribui); ``kind`` diferente de ``conclusao`` é erro nomeado, nunca corrigido."""
    from pydantic import TypeAdapter

    limpos, erros = [], []
    for n, item in enumerate(itens, start=1):
        if not isinstance(item, dict):
            erros.append(f"item {n} não é objeto")
            continue
        kind = item.get("kind", "conclusao")
        if kind != "conclusao":
            erros.append(f"item {n}: kind={kind!r}; a classe vai em conclusion_class")
            continue
        limpos.append({k: v for k, v in item.items() if k not in _DO_SERVIDOR and k != "kind"})
    if erros:
        raise ValueError(f"Afirmação fora do contrato {CONTRATO_VERSAO}: " + "; ".join(erros))
    afirmacoes = TypeAdapter(list[AfirmacaoDiagnostico]).validate_python(limpos)
    return [EvidenceObject(id=f"afirmacao:{n}", version=1, kind="conclusao", origin="diagnostico",
                           **a.model_dump()) for n, a in enumerate(afirmacoes, start=1)]


def prompt_base_registro() -> dict:
    return {"slug": "diagnostico_contrato", "hash": canonical_hash(PROMPT_BASE), "content": PROMPT_BASE,
            "version": CONTRATO_VERSAO, "origin": "contrato_080"}


def sem_cerca(conteudo: str) -> str:
    """Tira uma cerca markdown (```json … ```) em volta da resposta inteira — e só isso."""
    texto = (conteudo or "").strip()
    if texto.startswith("```") and texto.endswith("```"):
        texto = texto[3:-3].strip()
        if texto.lower().startswith("json"):
            texto = texto[4:].strip()
    return texto


def erro_de_sintaxe(conteudo: str) -> str | None:
    """Mensagem do parser quando a resposta não é JSON (sem cerca); None quando é."""
    import json

    try:
        json.loads(sem_cerca(conteudo))
    except (json.JSONDecodeError, TypeError) as exc:
        return str(exc)
    return None


def faltou_objects(parsed) -> str | None:
    """Mensagem nomeada quando a resposta não segue o contrato (antes: KeyError 'objects')."""
    if isinstance(parsed, dict) and isinstance(parsed.get("objects"), list):
        return None
    veio = ", ".join(sorted(parsed)[:8]) if isinstance(parsed, dict) else type(parsed).__name__
    return f"Resposta fora do contrato {CONTRATO_VERSAO}: faltou a lista 'objects'; veio {veio}"


def _documentais(envelope: ExecutionEnvelope) -> set[tuple[str, int]]:
    # Observação legada não conferida (staging antigo) não sustenta certeza alta nem passivo.
    out = {(o.id, o.version) for o in envelope.observations if not o.legacy_unverified}
    out |= {(o.id, o.version) for o in envelope.sources if o.origin in ORIGENS_DOCUMENTAIS}
    return out


def recusas(objects: list[EvidenceObject], envelope: ExecutionEnvelope) -> list[str]:
    """D1 a D7 (ADR-080 §3). Lista vazia = todas as afirmações admitidas."""
    documentais = _documentais(envelope)
    falhas: list[str] = []
    for n, obj in enumerate(objects, start=1):
        rotulo = f"afirmação {n} ({(obj.statement or '')[:60]!r})"
        attrs = obj.attributes
        premissas = {(p.id, p.version) for p in obj.premises}
        tem_documental = bool(premissas & documentais)
        if not obj.premises:
            falhas.append(f"D1: {rotulo} — sem premissa")
        if attrs.certainty not in CERTEZAS:
            falhas.append(f"D2: {rotulo} — certeza ausente ou fora de {CERTEZAS}")
        elif attrs.certainty == "alta" and not tem_documental:
            falhas.append(f"D2: {rotulo} — certeza alta sem premissa documental")
        if obj.conclusion_class in CLASSES_DOCUMENTAIS and not tem_documental:
            falhas.append(f"D3: {rotulo} — {obj.conclusion_class} sem premissa documental (lacuna, não passivo)")
        if obj.conclusion_class == "risco" and attrs.impact not in IMPACTOS:
            falhas.append(f"D4: {rotulo} — risco sem impacto em {IMPACTOS}")
        if attrs.impact is not None and attrs.impact not in IMPACTOS:
            falhas.append(f"D4: {rotulo} — impacto fora de {IMPACTOS}")
        if obj.conclusion_class == "escopo_proposto" and (
            obj.applicability != "aplicavel" or not obj.applicability_reason
        ):
            falhas.append(f"D5: {rotulo} — serviço sem aplicabilidade e razão")
        if attrs.urgency is not None and attrs.urgency not in URGENCIAS:
            falhas.append(f"D6: {rotulo} — urgência fora de {URGENCIAS}")
        elif attrs.urgency == "alta" and not (
            obj.conclusion_class == "risco" and obj.applicability == "aplicavel"
        ):
            falhas.append(f"D6: {rotulo} — urgência alta fora de risco aplicável")
    return falhas
