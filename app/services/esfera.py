"""Esfera regulatória DERIVADA DO ÓRGÃO — nunca da UF (ADR-034).

**A regra de domínio** (decisão da Isis, 26/07): a esfera de um passivo é dada
por *quem autuou*, não por *onde fica o imóvel*. Um auto do IBAMA sobre uma
fazenda em Goiás é FEDERAL; uma notificação da SEMAD sobre a mesma fazenda é
ESTADUAL. Os dois convivem no mesmo caso — é literalmente o processo 15
(autos/ofícios IBAMA + notificação SEMAD sobre a Fazenda São Jorge).

Por que isso importa mais do que parece: derivar esfera da UF faz o sistema
buscar norma estadual para responder a auto federal. A fundamentação sai
plausível e errada — a classe de falha mais cara que existe aqui, porque o texto
"parece certo" para quem revisa com pressa.

Este módulo não decide rota nem prazo: só responde "de quem é esta exigência".
"""

from __future__ import annotations

import re
from typing import Literal, Optional

Esfera = Literal["federal", "estadual", "municipal"]

__all__ = [
    "Esfera",
    "esfera_do_orgao",
    "esferas_do_texto",
    "ORGAOS_FEDERAIS",
    "ORGAOS_ESTADUAIS",
]


# Órgãos federais — nome por extenso e sigla. Ordem não importa (match por token).
ORGAOS_FEDERAIS: tuple[str, ...] = (
    "ibama",
    "instituto brasileiro do meio ambiente",
    "icmbio",
    "instituto chico mendes",
    "mma",
    "ministerio do meio ambiente",
    "ministério do meio ambiente",
    "incra",
    "instituto nacional de colonizacao",
    "instituto nacional de colonização",
    "ana",
    "agencia nacional de aguas",
    "agência nacional de águas",
    "funai",
    "fundacao palmares",
    "fundação palmares",
    "iphan",
    "dnpm",
    "anm",
    "policia federal",
    "polícia federal",
    "mpf",
    "ministerio publico federal",
    "ministério público federal",
    "receita federal",
    "sfb",
    "servico florestal brasileiro",
    "serviço florestal brasileiro",
)

# Órgãos ambientais estaduais. A lista nomeia os que o piloto encontra; o padrão
# genérico abaixo (`_RE_ESTADUAL_GENERICO`) cobre as demais UFs sem exigir que
# alguém lembre de cadastrar cada sigla — falhar por omissão de cadastro seria
# recriar o problema que este módulo existe para resolver.
ORGAOS_ESTADUAIS: tuple[str, ...] = (
    "semad",       # GO, MG
    "sema",        # vários
    "semas",       # PA
    "secima",      # GO (extinto, aparece em peça antiga)
    "imasul",      # MS
    "inema",       # BA
    "cetesb",      # SP
    "iap", "iat",  # PR
    "fatma", "ima", # SC
    "feam", "igam", # MG
    "inea",        # RJ
    "adema",       # SE
    "iema",        # ES, MA
    "idema",       # RN
    "naturatins",  # TO
    "ipaam",       # AM
    "imac",        # AC
    "sedam",       # RO
    "semace",      # CE
    "cprh",        # PE
    "sudema",      # PB
    "idaf",        # ES
    "fepam",       # RS
    "policia militar ambiental",
    "polícia militar ambiental",
    "ministerio publico estadual",
    "ministério público estadual",
    "secretaria de estado de meio ambiente",
    "secretaria estadual de meio ambiente",
    "secretaria de meio ambiente do estado",
)

ORGAOS_MUNICIPAIS: tuple[str, ...] = (
    "semma",
    "secretaria municipal de meio ambiente",
    "prefeitura",
    "secretaria municipal",
)

# "SEMA-MT", "SEMAD/GO", "SEMA MS" — sigla estadual seguida de UF.
_RE_ESTADUAL_GENERICO = re.compile(
    r"\b(sem[a-z]{1,3}|idema|inema|imasul|naturatins)\s*[-/ ]\s*[a-z]{2}\b"
)

# Palavras que sozinhas indicam a esfera quando nenhum órgão é reconhecido.
_PISTAS_FEDERAIS = ("servico publico federal", "serviço público federal", "uniao", "união")
_PISTAS_ESTADUAIS = ("governo do estado", "estado de", "secretaria de estado")


def _normalizar(texto: str) -> str:
    return " ".join(texto.lower().replace(".", " ").split())


def esfera_do_orgao(orgao: Optional[str]) -> Optional[Esfera]:
    """Esfera do órgão autuante/competente. ``None`` quando não dá para afirmar.

    ``None`` é resposta legítima e importante: sem saber de quem é a exigência, o
    sistema NÃO deve escolher uma esfera por padrão — deve dizer que não sabe e
    deixar a consultora informar. Chutar "estadual porque o imóvel é em GO" é
    exatamente o erro que a ADR-034 proíbe.

    O casamento é por token/substring sobre o texto normalizado, então funciona
    tanto com "IBAMA" quanto com "Superintendência do IBAMA em Goiás".
    """
    if not orgao or not orgao.strip():
        return None

    texto = _normalizar(orgao)

    # Federal primeiro: "IBAMA-GO" tem sigla de UF colada e cairia no padrão
    # estadual genérico se a ordem fosse outra. O órgão nomeado sempre vence a
    # pista geográfica — é a regra inteira deste módulo em uma linha.
    if any(o in texto for o in ORGAOS_FEDERAIS):
        return "federal"

    # Municipal antes de estadual: "secretaria municipal de meio ambiente" contém
    # "secretaria" e "meio ambiente", que também aparecem nos padrões estaduais.
    if any(o in texto for o in ORGAOS_MUNICIPAIS):
        return "municipal"

    if any(_orgao_estadual_bate(o, texto) for o in ORGAOS_ESTADUAIS):
        return "estadual"
    if _RE_ESTADUAL_GENERICO.search(texto):
        return "estadual"

    if any(p in texto for p in _PISTAS_FEDERAIS):
        return "federal"
    if any(p in texto for p in _PISTAS_ESTADUAIS):
        return "estadual"

    return None


def esferas_do_texto(orgao: Optional[str]) -> set[Esfera]:
    """TODAS as esferas nomeadas num texto de órgão — não só a primeira.

    ``esfera_do_orgao`` responde com UMA esfera porque a pergunta dela é "de quem
    é esta exigência?", e uma exigência tem um dono. Mas o campo
    ``Rota.orgao_competente`` é redigido pelo LLM em prosa e frequentemente
    nomeia mais de um órgão. Medido em produção, caso 16:

        "IBAMA (esfera federal) e Secretaria de Estado de Meio Ambiente e
         Desenvolvimento Sustentável de Goiás - SEMAD (esfera estadual)"

    ``esfera_do_orgao`` devolve ``"federal"`` — correto para o IBAMA, e cego para
    a metade estadual. O guard da ADR-034 então pergunta "federal está entre as
    esferas do caso?", ouve "está", e deixa passar um texto que manda o consultor
    à SEMAD por um auto que é do IBAMA. Foi exatamente o que a consultora
    relatou, e o que a correção de 31/07 não alcançou: ela conserta o órgão do
    PASSO (uma sigla por vez), não a prosa do órgão competente da rota.

    Devolve conjunto vazio quando nada é reconhecido — silêncio honesto, mesma
    política do ``None`` de ``esfera_do_orgao``: sem saber, não se chuta.
    """
    if not orgao or not orgao.strip():
        return set()

    texto = _normalizar(orgao)
    achadas: set[Esfera] = set()

    if any(o in texto for o in ORGAOS_FEDERAIS):
        achadas.add("federal")
    if any(o in texto for o in ORGAOS_MUNICIPAIS):
        achadas.add("municipal")
    if any(_orgao_estadual_bate(o, texto) for o in ORGAOS_ESTADUAIS) or (
        _RE_ESTADUAL_GENERICO.search(texto)
    ):
        achadas.add("estadual")

    # As pistas genéricas ("governo do estado", "união") só entram quando NENHUM
    # órgão foi reconhecido — são fracas demais para somar a uma identificação
    # firme, e o texto do caso 16 contém "estado de" dentro do nome próprio da
    # SEMAD, o que faria toda menção a secretaria estadual virar dupla contagem.
    if not achadas:
        if any(p in texto for p in _PISTAS_FEDERAIS):
            achadas.add("federal")
        if any(p in texto for p in _PISTAS_ESTADUAIS):
            achadas.add("estadual")

    return achadas


def _orgao_estadual_bate(sigla: str, texto: str) -> bool:
    """Siglas curtas (``ima``, ``iap``, ``ana``) exigem limite de palavra.

    Sem isso "ima" casaria dentro de "estimativa" e "ana" dentro de "Paraná" —
    e um documento qualquer viraria "estadual" por acidente ortográfico.
    """
    if " " in sigla:
        return sigla in texto
    return re.search(rf"\b{re.escape(sigla)}\b", texto) is not None
