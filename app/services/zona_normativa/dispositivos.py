"""Dispositivos endereçáveis (ADR-075 adendo A1) e trechos de busca.

O dispositivo é a chave que a citação por ID confere: ``Lei 12.651/2012, art.
61-A, § 4º``. Aqui ele é lido da estrutura do texto — cabeçalho de artigo e de
parágrafo em linha própria — sem inferência.

Regra de ordem: artigo novo só abre se o número for MAIOR que o do artigo
corrente. Um "Art. 3º" depois do "Art. 5º" é texto citado (alteração de outra
lei, redação anterior impressa pelo Planalto) e continua dentro do dispositivo
corrente. Sem essa regra, a lei que altera outra "ganharia" os artigos da
alterada.

Remissão não é cabeçalho (dívida #274). "Art. 29 da Lei número 5.172…" no começo de
uma linha é a continuação de uma frase que cita OUTRA norma — o PDF quebrou a linha
antes do "Art.". Com a regra de ordem, esse falso "art. 29" ainda engolia os artigos
reais seguintes de número menor. Sinal: nenhum separador depois do número e, em
seguida, palavra de ligação ("da", "do", "desta", "e", "inciso", "caput"), vírgula ou
"§" ("e)" é alínea, não conjunção). Artigo real tem separador ("Art. 10. as pessoas") ou começa a frase ("Art. 7º
revogar", "Art. 1 o Estabelecer") — minúscula sozinha não serve de sinal.

Anexo (linha "ANEXO …" em maiúsculas depois do articulado) é dispositivo próprio:
tabela de anexo não é parágrafo do último artigo.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.services.chunking import _enc, contar_tokens

# Medido no corpus: o PDF quebra "Art. \n79." (o art. 79 do Decreto 6.514 — descumprir
# embargo — sumia) e "Art. 3\no". O sufixo de artigo acrescido ("61-A") tem o hífen
# COLADO no número e a letra seguida de ponto ou de maiúscula; "Art. 2º- A licença"
# e "Art. 8º - O órgão" são o artigo 2 e o 8 começando a frase, não 2-A e 8-O.
RE_ARTIGO = re.compile(
    r"^[ \t]*Art(?:igo)?\.?[ \t]*\n?[ \t]*(?P<num>\d+)(?:[º°ª]|o(?![a-z]))?"
    r"(?:-(?P<letra>[A-Z])(?=\.|[ \t]+[A-ZÀ-Ú]|[ \t]*$))?",
    re.M,
)
# Depois do número (e do sufixo), sem separador, a frase continua citando outra norma.
RE_REMISSAO = re.compile(
    r"(?:[ \t]*,|[ \t]*§|[ \t\n]+(?:da|do|das|dos|desta|deste|dessa|desse|esta|este|e(?!\))|inciso|incisos|caput|"
    r"par[áa]grafos?|al[íi]nea)\b)"
)
RE_PARAGRAFO = re.compile(
    r"^[ \t]*(?:§[ \t]*(?P<num>\d+)[ \t]*[º°o]?|(?P<unico>Par[áa]grafo[ \t]+[úu]nico))", re.M | re.I
)
RE_ANEXO = re.compile(r"^[ \t]*ANEXO(?:[ \t]+(?P<id>[IVXLC\d]+|[ÚU]NICO))?\b[^\n]{0,120}$", re.M)

# Teto do trecho de busca. Artigo maior é dividido nos parágrafos; parágrafo
# maior, em janela. O artigo inteiro continua sendo UM dispositivo — o teto é da
# unidade de vetor, não da unidade de citação.
MAX_TRECHO_TOKENS = 1200
JANELA_TOKENS = 900
SOBREPOSICAO_TOKENS = 120


def e_remissao(texto: str, m: re.Match) -> bool:
    """O "Art. N" casado é citação dentro de frase, não cabeçalho de artigo."""
    return RE_REMISSAO.match(texto, m.end()) is not None


def _chave_artigo(num: str, letra: str | None) -> tuple[int, str]:
    return int(num), (letra or "")


def rotulo_artigo(artigo: str) -> str:
    base = re.match(r"(\d+)(.*)", artigo)
    if base and int(base.group(1)) < 10 and not base.group(2):
        return f"art. {artigo}º"
    return f"art. {artigo}"


def rotulo_paragrafo(paragrafo: str) -> str:
    if paragrafo == "unico":
        return "parágrafo único"
    return f"§ {paragrafo}º" if int(paragrafo) < 10 else f"§ {paragrafo}"


@dataclass
class DispositivoExtraido:
    tipo: str                          # preambulo | artigo | paragrafo | anexo
    rotulo: str                        # "art. 18", "§ 1º", "preâmbulo", "anexo I"
    artigo: str | None
    paragrafo: str | None
    ordem: int
    texto: str
    filhos: list[DispositivoExtraido] = field(default_factory=list)

    @property
    def hash(self) -> str:
        return hashlib.sha256(re.sub(r"\s+", " ", self.texto).strip().encode()).hexdigest()

    def caminho(self, rotulo_fonte: str, pai: DispositivoExtraido | None = None) -> str:
        partes = [rotulo_fonte]
        if pai is not None:
            partes.append(pai.rotulo)
        partes.append(self.rotulo)
        return ", ".join(partes)


def _paragrafos(texto_artigo: str, artigo: str) -> list[DispositivoExtraido]:
    marcas = []
    ultimo = 0
    unico_visto = False
    for m in RE_PARAGRAFO.finditer(texto_artigo):
        if m.group("unico"):
            if unico_visto or ultimo:
                continue
            unico_visto = True
            marcas.append((m.start(), "unico"))
            continue
        n = int(m.group("num"))
        if n <= ultimo or unico_visto:
            continue  # parágrafo citado ou fora de ordem: continua no corrente
        ultimo = n
        marcas.append((m.start(), str(n)))
    out = []
    for i, (pos, par) in enumerate(marcas):
        fim = marcas[i + 1][0] if i + 1 < len(marcas) else len(texto_artigo)
        corpo = texto_artigo[pos:fim].strip()
        if corpo:
            out.append(DispositivoExtraido("paragrafo", rotulo_paragrafo(par), artigo, par, i + 1, corpo))
    return out


def extrair_dispositivos(texto: str) -> list[DispositivoExtraido]:
    """Preâmbulo, artigos (com parágrafos como filhos) e anexos, em ordem."""
    cortes: list[tuple[int, str, str | None]] = []   # (pos, tipo, id)
    atual: tuple[int, str] | None = None
    for m in RE_ARTIGO.finditer(texto):
        if e_remissao(texto, m):
            continue
        chave = _chave_artigo(m.group("num"), m.group("letra"))
        if atual is not None and chave <= atual:
            continue
        atual = chave
        ident = m.group("num") + (f"-{m.group('letra')}" if m.group("letra") else "")
        cortes.append((m.start(), "artigo", ident))
    if cortes:
        anexos_vistos = 0
        for m in RE_ANEXO.finditer(texto, cortes[0][0]):
            linha = m.group(0).strip()
            corpo = re.sub(r"[^A-Za-zÀ-ú]", "", linha)
            if corpo and sum(c.isupper() for c in corpo) / len(corpo) < 0.7:
                continue
            anexos_vistos += 1
            cortes.append((m.start(), "anexo", m.group("id") or str(anexos_vistos)))
        cortes.sort()
        # Depois do primeiro anexo, "Art. N" é conteúdo do anexo, não artigo.
        prim_anexo = next((p for p, t, _ in cortes if t == "anexo"), None)
        if prim_anexo is not None:
            cortes = [c for c in cortes if c[1] == "anexo" or c[0] < prim_anexo]

    out: list[DispositivoExtraido] = []
    ordem = 0
    inicio_art = cortes[0][0] if cortes else len(texto)
    preambulo = texto[:inicio_art].strip()
    if preambulo:
        out.append(DispositivoExtraido("preambulo", "preâmbulo", None, None, ordem, preambulo))
        ordem += 1
    usados_anexo: set[str] = set()
    for i, (pos, tipo, ident) in enumerate(cortes):
        fim = cortes[i + 1][0] if i + 1 < len(cortes) else len(texto)
        corpo = texto[pos:fim].strip()
        if not corpo:
            continue
        if tipo == "artigo":
            d = DispositivoExtraido("artigo", rotulo_artigo(ident), ident, None, ordem, corpo)
            d.filhos = _paragrafos(corpo, ident)
        else:
            rot = f"anexo {ident}"
            k = 2
            while rot in usados_anexo:
                rot = f"anexo {ident} ({k})"
                k += 1
            usados_anexo.add(rot)
            d = DispositivoExtraido("anexo", rot, None, None, ordem, corpo)
        out.append(d)
        ordem += 1
    return out


def _janelas(texto: str) -> list[str]:
    enc = _enc()
    ids = enc.encode(texto)
    passo = JANELA_TOKENS - SOBREPOSICAO_TOKENS
    out = []
    pos = 0
    while pos < len(ids):
        pedaco = enc.decode(ids[pos : pos + JANELA_TOKENS]).strip()
        if pedaco:
            out.append(pedaco)
        if pos + JANELA_TOKENS >= len(ids):
            break
        pos += passo
    return out


def trechos_do_dispositivo(d: DispositivoExtraido) -> list[tuple[str, int]]:
    """Pedaços de busca de um dispositivo: inteiro se couber; senão pelos
    parágrafos agrupados; parágrafo grande demais, em janela. (texto, tokens)."""
    tokens = contar_tokens(d.texto)
    if tokens <= MAX_TRECHO_TOKENS:
        return [(d.texto, tokens)]
    blocos: list[str] = []
    if d.filhos:
        cabeca = d.texto[: d.texto.find(d.filhos[0].texto)].strip() if d.filhos[0].texto in d.texto else ""
        partes = ([cabeca] if cabeca else []) + [f.texto for f in d.filhos]
        atual = ""
        for p in partes:
            cand = f"{atual}\n{p}".strip() if atual else p
            if atual and contar_tokens(cand) > MAX_TRECHO_TOKENS:
                blocos.append(atual)
                atual = p
            else:
                atual = cand
        if atual:
            blocos.append(atual)
    else:
        blocos = [d.texto]
    out: list[tuple[str, int]] = []
    for b in blocos:
        tb = contar_tokens(b)
        if tb <= MAX_TRECHO_TOKENS:
            out.append((b, tb))
        else:
            out.extend((j, contar_tokens(j)) for j in _janelas(b))
    return out
