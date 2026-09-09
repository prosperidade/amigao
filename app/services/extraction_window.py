"""Janela completa — o extrator lê o documento INTEIRO (ADR-064, contenção 2).

Motivador REAL, medido na confirmação da entrada de 09/09 (erro OCR-002):

    Doc 547, matrícula 3.181, 82.117 chars. `EXTRACTOR_MAX_CHARS = 30.000`.
    O NIRF verdadeiro do imóvel (`2.974.457-1`) está no caractere **53.775** —
    fora da janela. O extrator nunca o viu. O único código INCRA-like DENTRO da
    janela era o do CONFRONTANTE (`050.041.396.737-1`, caractere 1.286, na
    frase "cravado na confrontação da Fazenda Posse, da Nascente Agro
    Industrial, Código INCRA nº..."). Foi ele que virou `nirf_cib` do imóvel.

Não é alucinação do modelo: ele respondeu certo sobre o texto que recebeu. O
texto é que estava cortado em 36% do documento — e o corte é silencioso.

**A decisão (medida, ver ADR-064):** chunking sequencial com sobreposição, e
mesclagem por REGRA. Três candidatas foram consideradas:

- *prompt maior numa tacada* — cabe no contexto do modelo (82k chars ≈ 20k
  tokens), é a mais barata, e foi descartada porque não resolve o documento de
  200k e degrada com a distância ("lost in the middle") exatamente nos campos
  que aparecem tarde, que são os que estamos consertando;
- *passes múltiplos com prompt especializado por campo* — melhor qualidade,
  custo multiplicado pelo número de campos;
- *chunking sequencial com sobreposição* — cobre o documento inteiro num número
  de chamadas proporcional ao TAMANHO (2 chamadas para o doc 547, 1 para os de
  até 45k, que são a maioria), e a sobreposição impede que um valor partido na
  fronteira suma dos dois lados.

**A mesclagem é o que fecha o gate do doc 547.** Com dois candidatos para
`nirf_cib` — o do confrontante (chunk 1) e o do imóvel (chunk 2) — "o primeiro
vence" manteria o errado. A regra prefere quem passa na validação de FORMATO do
próprio campo (`field_validators.check_format`, item 4b): `050.041.396.737-1` é
um código SNCR/INCRA de 13 dígitos e reprova como NIRF; `2.974.457-1` passa. A
validação de formato já existia e só sinalizava; aqui ela decide entre iguais.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_ORDEM_CONFIANCA = {"high": 3, "medium": 2, "low": 1}


@dataclass
class Fatia:
    """Um pedaço do documento e onde ele começa no texto original."""

    indice: int
    inicio: int
    fim: int

    @property
    def rotulo(self) -> str:
        return f"chunk{self.indice}[{self.inicio}:{self.fim}]"


@dataclass
class JanelaResultado:
    """O JSON mesclado + o que precisa aparecer na auditoria."""

    parsed: dict[str, Any]
    fatias: list[Fatia] = field(default_factory=list)
    total_chars: int = 0
    cobertura_chars: int = 0
    truncado: bool = False
    """True quando o teto de fatias impediu de cobrir o documento inteiro."""

    origem: dict[str, int] = field(default_factory=dict)
    """campo → índice da fatia que forneceu o valor vencedor."""

    preteridos: dict[str, list[Any]] = field(default_factory=dict)
    """campo → valores de outras fatias que a regra descartou."""

    def resumo(self) -> dict[str, Any]:
        """O que vai para o `field_value` / log — pequeno e legível."""
        out: dict[str, Any] = {
            "fatias": len(self.fatias),
            "cobertura_chars": self.cobertura_chars,
            "total_chars": self.total_chars,
        }
        if self.truncado:
            out["truncado"] = True
        return out


def fatiar(
    texto: str, *, chunk_chars: int, overlap_chars: int, max_chunks: int
) -> list[Fatia]:
    """Divide o texto em fatias sequenciais com sobreposição.

    Documento que cabe numa fatia devolve UMA fatia — o caminho de sempre, sem
    chamada extra. A sobreposição existe para o valor que cai na emenda: um
    NIRF no caractere 44.995 com fatia de 45.000 ficaria partido em dois pedaços
    e não seria lido por nenhum dos lados.
    """
    total = len(texto)
    if total == 0:
        return []
    chunk_chars = max(1, chunk_chars)
    overlap_chars = max(0, min(overlap_chars, chunk_chars - 1))

    fatias: list[Fatia] = []
    inicio = 0
    while inicio < total and len(fatias) < max_chunks:
        fim = min(inicio + chunk_chars, total)
        fatias.append(Fatia(indice=len(fatias), inicio=inicio, fim=fim))
        if fim >= total:
            break
        inicio = fim - overlap_chars
    return fatias


def _vazio(value: Any) -> bool:
    return value in (None, "", [], {}) or (isinstance(value, str) and not value.strip())


def _chave_item(item: Any) -> str:
    if isinstance(item, (dict, list)):
        return json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
    return str(item).strip().lower()


def _mesclar_listas(candidatos: list[tuple[int, Any]]) -> list[Any]:
    """Concatena listas de todas as fatias, preservando ordem e sem repetir."""
    saida: list[Any] = []
    vistos: set[str] = set()
    for _, valor in candidatos:
        for item in valor:
            if _vazio(item):
                continue
            k = _chave_item(item)
            if k in vistos:
                continue
            vistos.add(k)
            saida.append(item)
    return saida


def _escolher_escalar(
    campo: str,
    candidatos: list[tuple[int, Any, Optional[str]]],
    validar: Optional[Callable[[str, Any], Optional[bool]]],
) -> tuple[int, Any, list[Any]]:
    """Elege o candidato de um campo escalar. Devolve (fatia, valor, preteridos).

    Ordem de preferência, do mais forte para o mais fraco:
    1. **passa na validação de formato do campo** — é o degrau que separa o NIRF
       do imóvel do código SNCR do confrontante, e é determinístico;
    2. **maior confiança declarada** pelo modelo;
    3. **fatia mais cedo** — desempate estável, para que duas execuções sobre o
       mesmo texto elejam o mesmo valor.
    """
    def ranking(c: tuple[int, Any, Optional[str]]) -> tuple[int, int, int]:
        idx, valor, conf = c
        fmt = validar(campo, valor) if validar else None
        fmt_score = 0 if fmt is False else 1
        conf_score = _ORDEM_CONFIANCA.get((conf or "").lower(), 0)
        return (fmt_score, conf_score, -idx)

    vencedor = max(candidatos, key=ranking)
    preteridos = [
        v for (i, v, _) in candidatos
        if i != vencedor[0] and _chave_item(v) != _chave_item(vencedor[1])
    ]
    return vencedor[0], vencedor[1], preteridos


def mesclar(
    por_fatia: list[tuple[Fatia, dict[str, Any]]],
    *,
    validar: Optional[Callable[[str, Any], Optional[bool]]] = None,
) -> JanelaResultado:
    """Funde os JSONs das fatias num só, com origem e descartes registrados."""
    resultado = JanelaResultado(parsed={})
    if not por_fatia:
        return resultado

    # Todas as chaves vistas, na ordem em que aparecem (estabilidade do output).
    chaves: list[str] = []
    for _, parsed in por_fatia:
        for k in parsed:
            if k != "confidence" and k not in chaves:
                chaves.append(k)

    confianca_final: dict[str, Any] = {}

    for campo in chaves:
        candidatos_lista: list[tuple[int, Any]] = []
        candidatos_escalar: list[tuple[int, Any, Optional[str]]] = []
        for fatia, parsed in por_fatia:
            valor = parsed.get(campo)
            if _vazio(valor):
                continue
            conf = (parsed.get("confidence") or {}).get(campo) \
                if isinstance(parsed.get("confidence"), dict) else None
            if isinstance(valor, list):
                candidatos_lista.append((fatia.indice, valor))
            else:
                candidatos_escalar.append((fatia.indice, valor, conf))

        if candidatos_lista and candidatos_escalar:
            # O mesmo campo veio como LISTA numa fatia e como ESCALAR noutra —
            # forma inconsistente do modelo. O escalar segue (é o shape que o
            # mapeamento espera) e a lista entra em `preteridos`: descartar sem
            # dizer é exatamente o silêncio que esta frente existe para matar.
            resultado.preteridos.setdefault(campo, []).extend(
                v for _, v in candidatos_lista
            )
            logger.warning(
                "extraction_window: %s veio como lista em %d fatia(s) e escalar "
                "em %d — a lista foi preterida",
                campo, len(candidatos_lista), len(candidatos_escalar),
            )

        if candidatos_lista and not candidatos_escalar:
            fundido = _mesclar_listas(candidatos_lista)
            if fundido:
                resultado.parsed[campo] = fundido
                resultado.origem[campo] = candidatos_lista[0][0]
                for _fatia, parsed in por_fatia:
                    c = parsed.get("confidence")
                    if isinstance(c, dict) and c.get(campo):
                        confianca_final[campo] = c[campo]
                        break
            continue

        if not candidatos_escalar:
            continue

        idx, valor, preteridos = _escolher_escalar(campo, candidatos_escalar, validar)
        resultado.parsed[campo] = valor
        resultado.origem[campo] = idx
        if preteridos:
            resultado.preteridos[campo] = preteridos
            logger.info(
                "extraction_window: %s eleito da fatia %d; preteridos=%r",
                campo, idx, preteridos[:3],
            )
        conf_vencedora = next((c for (i, _v, c) in candidatos_escalar if i == idx), None)
        if conf_vencedora:
            confianca_final[campo] = conf_vencedora

    if confianca_final:
        resultado.parsed["confidence"] = confianca_final
    return resultado
