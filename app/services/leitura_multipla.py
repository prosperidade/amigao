"""ADR-079 — leitura múltipla por rodada.

Uma rodada lê o mesmo documento N vezes e publica a UNIÃO das leituras, com o
dedupe do ADR-078: dois itens de leituras diferentes são o mesmo fato quando têm o
mesmo tipo e discriminante, trechos sobrepostos e — para observação — o mesmo
predicado ou o mesmo valor lido. Dentro da rodada nada é "não reencontrado": o que
uma leitura viu e outra não, entra. A marca "não reencontrada" (ADR-078) só existe
entre rodadas, quando uma rodada nova não reencontra o que a anterior publicou.

Funções puras sobre itens do schema (``EntradaExtraida``); a persistência não muda.
"""

from __future__ import annotations

import re

from app.schemas.entrada_semantica import EntradaExtraida

# Chaves que o modelo inventa para ligar itens entre si; não são o valor lido.
REFERENCIAS = {"chave", "parte_chave", "representado_chave", "falecido_chave", "sujeito", "contratante",
               "contratado", "trecho", "posicao_inicio", "posicao_fim", "confianca", "leituras_na_rodada"}

# Coleções unidas, na ordem: partes antes de quem aponta para elas.
_COLECOES = ("partes", "atos", "participacoes", "contratos", "observacoes", "falecimentos_declarados",
             "referencias_processo")


def _compacto(valor):
    return re.sub(r"\s+", "", str(valor if valor is not None else "")).upper()


def discriminante(colecao, item: dict):
    """O que distingue dois fatos do mesmo tipo no mesmo trecho — a mesma régua de
    ``entrada_semantica._identidade_de_fato`` (ADR-078), aplicada ao item ainda não gravado."""
    if colecao == "partes":
        return re.sub(r"\D", "", str(item.get("identificador") or "")) or _compacto(item.get("nome"))
    if colecao == "atos":
        return re.sub(r"[\s.\-]", "", str(item.get("rotulo") or "")).upper()
    if colecao == "participacoes":
        return item.get("papel")
    if colecao == "referencias_processo":
        return re.sub(r"\D", "", str(item.get("numero") or ""))
    return None


def valor_lido(item: dict):
    return {k: v for k, v in item.items() if k not in REFERENCIAS}


def mesmo_fato(colecao, a: dict, b: dict) -> bool:
    """ADR-078: mesmo tipo e discriminante, trecho sobreposto e, para observação,
    mesmo predicado OU mesmo valor lido (não vazio)."""
    if discriminante(colecao, a) != discriminante(colecao, b):
        return False
    ia, fa, ib, fb = a.get("posicao_inicio"), a.get("posicao_fim"), b.get("posicao_inicio"), b.get("posicao_fim")
    if None in (ia, fa, ib, fb) or not (ia < fb and ib < fa):
        return False
    if a.get("predicado") == b.get("predicado"):
        return True
    valor = _compacto(a.get("valor"))
    return colecao == "observacoes" and valor != "" and valor == _compacto(b.get("valor"))


def agrupar(colecao, leituras):
    """Agrupa os itens de N leituras que são o mesmo fato. ``leituras`` é uma lista
    (uma por leitura) de listas de dicts. Devolve grupos ``[(leitura, índice, item)]``;
    o primeiro membro de cada grupo — o da leitura mais antiga — é o representante."""
    grupos = []
    for n, itens in enumerate(leituras):
        for i, item in enumerate(itens):
            # Um fato por leitura em cada grupo: dois itens da MESMA leitura nunca se fundem
            # (a própria leitura já os distinguiu).
            alvo = next((g for g in grupos if all(m != n for m, _, _ in g)
                         and any(mesmo_fato(colecao, item, o) for _, _, o in g)), None)
            if alvo is None:
                grupos.append([(n, i, item)])
            else:
                alvo.append((n, i, item))
    return grupos


def _renomear(entrada: EntradaExtraida, prefixo: str, mapa: dict):
    """Chaves de uma leitura: prefixadas (``l2:f3:p1``) e, se a parte foi fundida numa
    de leitura anterior, trocadas pela chave dela."""
    def chave(k):
        if k is None:
            return None
        k = prefixo + k
        return mapa.get(k, k)
    for parte in entrada.partes:
        parte.falecido_chave = chave(parte.falecido_chave)
    for part in entrada.todas_participacoes:
        part.parte_chave = chave(part.parte_chave)
        part.representado_chave = chave(part.representado_chave)
    for contrato in entrada.contratos:
        contrato.contratante = [chave(k) for k in contrato.contratante]
        contrato.contratado = [chave(k) for k in contrato.contratado]
    for item in (*entrada.falecimentos_declarados, *entrada.referencias_processo, *entrada.observacoes):
        item.sujeito = chave(item.sujeito)


def unir_leituras(entradas: list[EntradaExtraida]):
    """A união das leituras de uma rodada, sem o mesmo fato em dobro.

    Devolve ``(entrada, relatorio)``. Cada item publicado leva em
    ``_leituras_na_rodada`` quantas leituras o viram. Com o valor lido diferente entre
    as leituras, publica-se o da leitura mais antiga e a divergência vai ao relatório —
    a máquina não escolhe o valor "certo".
    """
    total = len(entradas)
    if total == 1:
        return entradas[0], None
    entradas = [e.model_copy(deep=True) for e in entradas]
    # 1) Partes: agrupadas primeiro; a chave de uma parte fundida passa a ser a do representante.
    mapa = {}
    for n, entrada in enumerate(entradas):
        if n:
            for parte in entrada.partes:
                parte.chave = f"l{n}:{parte.chave}"
    partes = [[p.model_dump(mode="json") for p in e.partes] for e in entradas]
    for grupo in agrupar("partes", partes):
        _, _, rep = grupo[0]
        for _, _, membro in grupo[1:]:
            mapa[membro["chave"]] = rep["chave"]
    for n, entrada in enumerate(entradas):
        _renomear(entrada, f"l{n}:" if n else "", mapa if n else {})
    # 2) Todas as coleções, com as referências já na chave final.
    uniao = {}
    resumo = {"leituras": total, "itens_por_leitura": [0] * total, "uniao": 0, "em_todas": 0, "so_em_uma": 0,
              "valor_divergente": []}
    for colecao in _COLECOES:
        objetos = [getattr(e, colecao) for e in entradas]
        dumps = [[o.model_dump(mode="json") for o in lista] for lista in objetos]
        for n, lista in enumerate(dumps):
            resumo["itens_por_leitura"][n] += len(lista)
        publicados = []
        for grupo in agrupar(colecao, dumps):
            n0, i0, rep = grupo[0]
            viram = len({n for n, _, _ in grupo})
            objeto = objetos[n0][i0]
            objeto._leituras_na_rodada = {"viram": viram, "de": total}
            publicados.append(objeto)
            resumo["uniao"] += 1
            resumo["em_todas"] += viram == total
            resumo["so_em_uma"] += viram == 1
            valores = {repr(sorted(valor_lido(m).items())) for _, _, m in grupo}
            if len(valores) > 1:
                resumo["valor_divergente"].append({
                    "colecao": colecao, "predicado": rep.get("predicado"),
                    "posicao": [rep.get("posicao_inicio"), rep.get("posicao_fim")],
                    "publicado": {"leitura": n0 + 1, "valor": valor_lido(rep)},
                    "outros": [{"leitura": n + 1, "valor": valor_lido(m)} for n, _, m in grupo[1:]
                               if valor_lido(m) != valor_lido(rep)]})
        # Uma parte fundida pode ter sido a única com essa chave numa leitura: a chave
        # que sobra é a do representante, que está publicado.
        uniao[colecao] = publicados
    limites = []
    for entrada in entradas:
        limites += [x for x in entrada.limites if x not in limites]
    return EntradaExtraida(**uniao, limites=limites), resumo
