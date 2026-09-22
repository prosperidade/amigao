"""Nível de autoridade por REGRA FIXA sobre o que está gravado (ADR-075 §1).

Só classifica onde o gravado basta (ZONA_NORMATIVA_RAG §1.1). O resto nasce
``nao_determinado`` — e ``nao_determinado`` não entra em nenhum uso de busca: é
fila de revisão, não candidato.

Cada decisão sai com a regra que a tomou (`nivel_origem`). Parâmetro provisório
sai declarado como tal: as fichas de tipologia SEMAD são ``exigencia`` **até a
resposta da Ísis à Q-ISIS-18** (exigência ou procedimento) — a regra está aqui,
num lugar só, para ser trocada sem caça.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.zona_normativa.identidade import IdentidadeNorma

ESPECIES_NORMA = frozenset({
    "lei", "lei_complementar", "lei_delegada", "decreto", "decreto_lei", "decreto_legislativo",
    "emenda_constitucional", "constituicao", "medida_provisoria", "in", "resolucao", "portaria",
    "deliberacao",
})
ESPECIES_INTERPRETACAO = frozenset({"ojn", "orientacao_normativa", "parecer", "nota_tecnica"})

# Parâmetro provisório declarado (Q-ISIS-18 pendente).
NIVEL_TIPOLOGIA_SEMAD = "exigencia"
ORIGEM_TIPOLOGIA_SEMAD = "parametro_provisorio_Q-ISIS-18"

# Documentos avulsos do legado que a medição mandou RELER (§1.1): manuais,
# listas ATIV-INEX e plano de manejo. Não se classificam pelo nome.
_RELER_AVULSO = re.compile(r"^(manual|matriz ipe|anexo ativ-inex|plano de manejo)", re.I)

_RE_TIPOLOGIA = re.compile(r"^\s*[A-Z]\d+(?:\.\d+)*(?:\.pdf)?\s*(?:-|\.pdf|$)")
_RE_TR = re.compile(r"\b(termo de refer[êe]ncia|^tr\b|gabarito|laudo)", re.I)


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def nivel_de_norma_avulsa(
    ident: IdentidadeNorma, *, source_type: str | None, identifier: str | None
) -> tuple[str, str]:
    """Norma avulsa do legado (`legislation_documents` fora das coletâneas)."""
    if source_type == "referencia_bibliografica":
        return "radar", "source_type=referencia_bibliografica"
    if ident.tipo in ESPECIES_INTERPRETACAO:
        return "interpretacao", f"especie={ident.tipo}"
    if ident.tipo in ESPECIES_NORMA:
        return "norma", f"especie={ident.tipo}"
    if identifier and _RELER_AVULSO.match(_sem_acento(identifier)):
        return "nao_determinado", "exige_releitura(ZONA_NORMATIVA_RAG §1.1)"
    return "nao_determinado", "sem_regra"


def nivel_de_ato_desmembrado(ident: IdentidadeNorma | None) -> tuple[str, str]:
    """Ato cortado de coletânea. Identidade não fechada não recebe nível."""
    if ident is None or not ident.determinada:
        return "nao_determinado", "identidade_nao_determinada"
    if ident.tipo in ESPECIES_INTERPRETACAO:
        return "interpretacao", f"especie={ident.tipo}"
    if ident.tipo in ESPECIES_NORMA:
        return "norma", f"especie={ident.tipo}"
    return "nao_determinado", "sem_regra"


def tipo_e_nivel_semad(source_type: str, source_ref: str) -> tuple[str, str, str]:
    """Fonte SEMAD-GO que só existe como chunk. (tipo, nivel, origem).

    O `source_type` gravado não basta: 28 dos 36 `matriz_ipe` são fichas de
    tipologia e só o NOME DO ARQUIVO separa (§1.1).
    """
    nome = source_ref.strip().replace("_", " ")
    if nome.lower().startswith("tipologias disponiveis"):
        # Lista de tipologias disponíveis, não ficha de uma tipologia.
        return "documento", "nao_determinado", "exige_releitura(lista_de_tipologias)"
    if _RE_TIPOLOGIA.match(nome):
        return "ficha_tipologia", NIVEL_TIPOLOGIA_SEMAD, ORIGEM_TIPOLOGIA_SEMAD
    if source_type == "gabarito_laudo" or _RE_TR.search(_sem_acento(nome)):
        return "termo_referencia", "exigencia", "nome_do_arquivo=TR/gabarito"
    if source_type == "matriz_ipe":
        return "matriz_ipe", "exigencia", "nome_do_arquivo=matriz_ipe"
    if source_type == "manual_ipe":
        return "manual_ipe", "procedimento", "source_type=manual_ipe"
    return "documento", "nao_determinado", "exige_releitura(ZONA_NORMATIVA_RAG §1.1)"


# Objetivos canônicos (DemandType). Núcleo de coletânea → objetivos é PARÂMETRO
# PROVISÓRIO: a coletânea foi montada por tema, não por objetivo de caso. Sai
# declarado (`objetivos_origem`) e a curadoria corrige na validação.
ORIGEM_OBJETIVO_NUCLEO = "nucleo_da_coletanea(provisorio)"
TRANSVERSAL = "transversal"
_OBJETIVOS_NUCLEO: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"constitucional|politica_ambiental", (TRANSVERSAL,)),
    (r"territorial|cadastro", ("car", "retificacao_car", "regularizacao_fundiaria", "sobreposicao")),
    (r"florestal|car_pra|regularizacao_servicos", ("car", "retificacao_car", "prad", "compensacao", "supressao")),
    (r"licenciamento", ("licenciamento", "condicionantes_antigas")),
    (r"hidrico|outorga|saneamento", ("outorga",)),
    (r"infrac", ("defesa",)),
    (r"credito", ("exigencia_bancaria",)),
    (r"biomas|ucs|biodiversidade|fauna|fogo|queimada", ("licenciamento", "supressao", "defesa")),
    (r"ativos|carbono", ("compensacao",)),
    (r"regulariza", ("car", "prad", "compensacao")),
)

# demand_types gravados no legado que não são DemandType canônico.
_SINONIMOS_DEMANDA = {
    "reserva_legal": "car", "cadastro": "car", "auto_infracao": "defesa",
    "credito_rural": "exigencia_bancaria", "queimada": "licenciamento", "fauna": "licenciamento",
    "biodiversidade": "licenciamento", "carbono": "compensacao", "geral": TRANSVERSAL,
}


def objetivos_do_nucleo(rotulo_coletanea: str) -> list[str] | None:
    r = _sem_acento(rotulo_coletanea).lower()
    for padrao, objs in _OBJETIVOS_NUCLEO:
        if re.search(padrao, r):
            return list(objs)
    return None


def objetivos_de_demand_types(demand_types: list[str] | None) -> list[str] | None:
    if not demand_types:
        return None
    out: list[str] = []
    for d in demand_types:
        c = _SINONIMOS_DEMANDA.get(d, d)
        if c not in out:
            out.append(c)
    return out
