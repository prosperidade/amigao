"""Linguagem restrita das condições e lógica de três valores (ADR-073 §2).

A condição é uma árvore JSON de vocabulário fechado:

- combinadores ``{"todos": [...]}``, ``{"algum": [...]}``, ``{"nao": {...}}``;
- folha ``{"fato": <nome>, "op": <operador>, "valor": ...}``.

**Fato desconhecido é desconhecido, nunca falso.** ``todos`` é falso se algum filho é
falso, verdadeiro se todos são verdadeiros, desconhecido nos demais casos; ``algum`` é o
dual; ``nao`` inverte e preserva o desconhecido (Kleene).

Nada aqui executa código vindo da regra: é interpretação de uma árvore com operadores
de uma lista fechada. Regra com fato fora do vocabulário, operador desconhecido ou tipo
incompatível é recusada na PUBLICAÇÃO (`validar_condicao`), não vira erro no caso.
"""

from __future__ import annotations

from typing import Any

# Vocabulário do gate (ADR-073 §3). Tipo → o que o operador aceita comparar.
FATOS: dict[str, str] = {
    "caso.uf": "texto",
    "imovel.natureza": "texto",
    "car.no_dossie": "booleano",
    "dominio.matriculas_no_dossie": "inteiro",
    "ccir.no_dossie": "booleano",
    "titular.falecimento_declarado": "booleano",
}

# Como o fato aparece no passo de coleta quando falta ("Confirmar: ...").
ROTULOS: dict[str, str] = {
    "caso.uf": "UF do imóvel",
    "imovel.natureza": "natureza do imóvel (rural ou urbano)",
    "car.no_dossie": "CAR do imóvel",
    "dominio.matriculas_no_dossie": "matrículas do imóvel",
    "ccir.no_dossie": "CCIR do imóvel",
    "titular.falecimento_declarado": "situação do titular (falecimento)",
}

OPERADORES = ("eq", "ne", "in", "gt", "ge", "lt", "le", "existe", "verdadeiro")
_ORDEM = ("gt", "ge", "lt", "le")
COMBINADORES = ("todos", "algum", "nao")

Valor3 = bool | None  # True, False ou desconhecido (None)


def _tipo_ok(tipo: str, valor: Any) -> bool:
    if tipo == "booleano":
        return isinstance(valor, bool)
    if tipo == "inteiro":
        return isinstance(valor, int) and not isinstance(valor, bool)
    return isinstance(valor, str)


def validar_condicao(no: Any, caminho: str = "condicao") -> list[str]:
    """Motivos de recusa da condição. Lista vazia = publicável."""
    if not isinstance(no, dict) or not no:
        return [f"{caminho}: nó precisa ser objeto não vazio"]
    combinadores = [k for k in no if k in COMBINADORES]
    if combinadores:
        if len(no) != 1:
            return [f"{caminho}: combinador não aceita chave extra ({sorted(no)})"]
        chave = combinadores[0]
        filhos = no[chave]
        if chave == "nao":
            return validar_condicao(filhos, f"{caminho}.nao")
        if not isinstance(filhos, list) or not filhos:
            return [f"{caminho}.{chave}: precisa de lista não vazia"]
        erros: list[str] = []
        for i, filho in enumerate(filhos):
            erros += validar_condicao(filho, f"{caminho}.{chave}[{i}]")
        return erros

    extras = set(no) - {"fato", "op", "valor"}
    if extras:
        return [f"{caminho}: chave desconhecida {sorted(extras)}"]
    fato, op = no.get("fato"), no.get("op")
    if fato not in FATOS:
        return [f"{caminho}: fato {fato!r} fora do vocabulário"]
    if op not in OPERADORES:
        return [f"{caminho}: operador {op!r} desconhecido"]
    tipo = FATOS[fato]
    if op in ("existe", "verdadeiro"):
        if "valor" in no:
            return [f"{caminho}: '{op}' não leva valor"]
        if op == "verdadeiro" and tipo != "booleano":
            return [f"{caminho}: 'verdadeiro' exige fato booleano; {fato} é {tipo}"]
        return []
    if "valor" not in no:
        return [f"{caminho}: '{op}' exige valor"]
    valor = no["valor"]
    if op in _ORDEM and tipo != "inteiro":
        return [f"{caminho}: '{op}' exige fato inteiro; {fato} é {tipo}"]
    if op == "in":
        if not isinstance(valor, list) or not valor or not all(_tipo_ok(tipo, v) for v in valor):
            return [f"{caminho}: 'in' exige lista não vazia de {tipo}"]
        return []
    if not _tipo_ok(tipo, valor):
        return [f"{caminho}: valor {valor!r} incompatível com {fato} ({tipo})"]
    return []


def validar_aplicabilidade(apl: Any) -> list[str]:
    """``{"ufs": [..]|null, "esferas": null, "objetivos": null}``.

    Esfera e objetivo ainda não são fatos do vocabulário: regra que dependa deles é
    recusada na publicação em vez de ser avaliada como se se aplicasse a tudo.
    """
    if not isinstance(apl, dict):
        return ["aplicabilidade: precisa ser objeto"]
    extras = set(apl) - {"ufs", "esferas", "objetivos"}
    if extras:
        return [f"aplicabilidade: chave desconhecida {sorted(extras)}"]
    erros = []
    ufs = apl.get("ufs")
    if ufs is not None and (not isinstance(ufs, list) or not ufs
                            or not all(isinstance(u, str) and len(u) == 2 for u in ufs)):
        erros.append("aplicabilidade.ufs: lista de siglas de UF ou null")
    for chave in ("esferas", "objetivos"):
        if apl.get(chave) is not None:
            erros.append(f"aplicabilidade.{chave}: ainda não é fato do vocabulário; use null")
    return erros


def fatos_da_condicao(no: Any) -> set[str]:
    """Todos os fatos que a condição lê — o que entra em ``entradas`` da avaliação."""
    if not isinstance(no, dict):
        return set()
    for chave in COMBINADORES:
        if chave in no:
            filhos = no[chave] if chave != "nao" else [no[chave]]
            return set().union(*(fatos_da_condicao(f) for f in filhos))
    return {no["fato"]} if "fato" in no else set()


def _folha(no: dict, fatos: dict[str, dict]) -> tuple[Valor3, set[str]]:
    nome, op = no["fato"], no["op"]
    fato = fatos.get(nome) or {"estado": "desconhecido"}
    conhecido = fato.get("estado") == "determinado"
    if op == "existe":
        return conhecido, set()
    if not conhecido:
        return None, {nome}
    v = fato.get("valor")
    alvo = no.get("valor")
    if op == "verdadeiro":
        return v is True, set()
    if op == "eq":
        return v == alvo, set()
    if op == "ne":
        return v != alvo, set()
    if op == "in":
        return v in alvo, set()
    comparacoes = {"gt": v > alvo, "ge": v >= alvo, "lt": v < alvo, "le": v <= alvo}
    return comparacoes[op], set()


def avaliar(no: dict, fatos: dict[str, dict]) -> tuple[Valor3, set[str]]:
    """Avalia a condição contra o retrato de fatos.

    Devolve ``(valor, faltantes)``: ``valor`` é True, False ou None (desconhecido);
    ``faltantes`` só vem preenchido quando o valor é desconhecido — são os fatos cuja
    determinação decidiria a regra.
    """
    if "nao" in no:
        v, faltantes = avaliar(no["nao"], fatos)
        return (None if v is None else not v), faltantes
    if "todos" in no or "algum" in no:
        eh_todos = "todos" in no
        filhos = [avaliar(f, fatos) for f in no["todos" if eh_todos else "algum"]]
        # `todos` decide no primeiro falso; `algum`, no primeiro verdadeiro.
        decisivo = not eh_todos
        if any(v is decisivo for v, _ in filhos):
            return decisivo, set()
        if all(v is not None for v, _ in filhos):
            return (not decisivo), set()
        return None, set().union(*(f for v, f in filhos if v is None))
    return _folha(no, fatos)
