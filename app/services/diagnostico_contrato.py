"""Diagnóstico por afirmação no contrato de evidência (ADR-079, dívida #285).

Duas peças:

- ``PROMPT_BASE`` — o prompt-base do diagnóstico no contrato 069. Substitui o
  ``diagnostico_system`` legado, que pedia ``situacao_geral`` e fazia o modelo ignorar o
  contrato (job 201 do #25 de dev).
- ``recusas`` — regras de admissão D1 a D7, determinísticas. A afirmação que viola uma regra é
  recusada e a execução falha com a lista; nada é gravado.
"""

from __future__ import annotations

from app.schemas.evidence import EvidenceObject, ExecutionEnvelope, canonical_hash

CONTRATO_VERSAO = "079.1"

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
afirmação, um objeto do schema ao final com kind="conclusao". Não use outro formato: nada de
situacao_geral, passivos_identificados, riscos ou hipoteses soltos. Nenhum texto fora do JSON.

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


def prompt_base_registro() -> dict:
    return {"slug": "diagnostico_contrato", "hash": canonical_hash(PROMPT_BASE), "content": PROMPT_BASE,
            "version": CONTRATO_VERSAO, "origin": "contrato_079"}


def faltou_objects(parsed) -> str | None:
    """Mensagem nomeada quando a resposta não segue o contrato (antes: KeyError 'objects')."""
    if isinstance(parsed, dict) and isinstance(parsed.get("objects"), list):
        return None
    veio = ", ".join(sorted(parsed)[:8]) if isinstance(parsed, dict) else type(parsed).__name__
    return f"Resposta fora do contrato {CONTRATO_VERSAO}: faltou a lista 'objects'; veio {veio}"


def _documentais(envelope: ExecutionEnvelope) -> set[tuple[str, int]]:
    out = {(o.id, o.version) for o in envelope.observations}
    out |= {(o.id, o.version) for o in envelope.sources if o.origin in ORIGENS_DOCUMENTAIS}
    return out


def recusas(objects: list[EvidenceObject], envelope: ExecutionEnvelope) -> list[str]:
    """D1 a D7 (ADR-079 §3). Lista vazia = todas as afirmações admitidas."""
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
