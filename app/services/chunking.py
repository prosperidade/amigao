"""Chunking hibrido para o knowledge_catalog.

Estrategia:
1. Tenta cortar por marcadores estruturais de texto legislativo brasileiro
   ("Art. N", "CAPITULO X", "SECAO Y", "TITULO Z").
2. Se o chunk resultante exceder MAX_TOKENS, sub-divide em janelas de
   tamanho TARGET_TOKENS com OVERLAP_TOKENS de superposicao.
3. Se nenhuma marcacao for encontrada (ex: doutrina, oficio, manual),
   cai direto na janela deslizante.

Estimativa de tokens via heuristica de 4 chars/token (boa aproximacao
para portugues juridico — confirmado contra Gemini tokenizer no Sprint 0).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)

# Marcadores estruturais. Ordem importa: do mais externo para o mais interno.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("titulo", re.compile(r"^\s*T[ÍI]TULO\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE)),
    ("capitulo", re.compile(r"^\s*CAP[ÍI]TULO\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE)),
    ("secao", re.compile(r"^\s*SE[ÇC][ÃA]O\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE)),
    ("artigo", re.compile(r"^\s*Art\.\s*\d+", re.MULTILINE)),
]

TARGET_TOKENS = 800
MAX_TOKENS = 1500
OVERLAP_TOKENS = 100
_CHARS_PER_TOKEN = 4

# --------------------------------------------------------------------------
# Teto do ARTIGO (#118)
# --------------------------------------------------------------------------
# `MAX_TOKENS = 1500` e escolha nossa, nao limite de modelo — e ela corta
# artigo ao meio. O objetivo aqui NAO e "subir o teto": e o teto deixar de
# cortar a unidade semantica do dominio, que e o artigo. Chunk pequeno continua
# pequeno (p50 = 129 tokens); corte por tamanho continua existindo, como ULTIMO
# recurso, e agora e logado quando acontece.
#
# Precisam caber INTEIROS, medidos: 4.644 (Art. 61-A do Codigo Florestal),
# 5.578 (art. 100 da CF) e 6.289 (art. 19 da Lei 6.938). 7.000 cobre os tres
# com folga e fica abaixo do limiar da guarda (8.000).
#
# O teto ampliado vale SO para fatia de artigo. Capitulo, secao e preludio
# seguem em MAX_TOKENS: para eles, 7.000 tokens num chunk so nao e "dispositivo
# inteiro", e sim diluicao — o vetor vira um ponto que representa tudo
# vagamente e perde justamente o dispositivo especifico, que e o que a peca
# cita.
MAX_ARTIGO_TOKENS = 7000

# --------------------------------------------------------------------------
# Guarda de sanidade (#117)
# --------------------------------------------------------------------------
# `_split_by_pattern` assume que o documento e articulado do inicio ao fim: tudo
# entre um cabecalho e o proximo pertence aquele cabecalho. A premissa e falsa.
# Quando o texto DEIXA de ser articulado — sumario paginado, rodape de captura
# web, anexo, lista de diretrizes — todo o rabo nao-normativo e atribuido ao
# ultimo cabecalho visto.
#
# Medido em 04/08 sobre 24.577 fatias de artigo em 102 documentos:
#
#     p50 = 129 | p90 = 499 | p95 = 737 | p99 = 2.144 | p99,9 = 23.483
#     max = 261.280 tokens  ("Art. 51." do MT-NUC01)
#
# Aquele "Art. 51." tem 1.045.121 chars, 12.768 linhas e **nenhum outro
# cabecalho de artigo dentro** — 15 ocorrencias de "Art. N", todas citacoes
# inline ("art. 225, caput, da CF/88"). Nao e fronteira perdida: e ausencia de
# fronteira. Nenhum regex melhor corrige, porque nao ha o que casar.
#
# O LIMIAR nao foi escolhido no olho:
#   · maior artigo confirmadamente genuino do corpus: ~6.289 tokens;
#   · toda fatia acima de 8.000 que foi inspecionada era absorvedora — artigo de
#     vigencia ("Esta Lei entra em vigor...", que e sempre uma frase) engolindo
#     o anexo, cabecalho falso vindo de referencia inline ("Art. 10 desta
#     Resolucao (Juntar copia..."), ou prosa doutrinaria numerada;
#   · 8.000 tokens sao ~32.000 chars sob UM numero de artigo — deixa de ser
#     descricao plausivel de dispositivo.
LIMITE_ARTIGO_TOKENS = 8000

# Rotulo honesto para o material que cai na estrategia alternativa. O conteudo
# NAO some — continua indexado; o que ele perde e a etiqueta mentirosa.
ROTULO_NAO_ARTICULADO = "[trecho nao articulado]"

# Mesma expressao do padrao "artigo", usada para conferir se a fatia REALMENTE
# comeca em cabecalho de artigo (e nao e o preludio da passada estrutural).
_RE_ARTIGO = re.compile(r"^\s*Art\.\s*\d+")


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


# --------------------------------------------------------------------------
# Estrutura da norma como DADO (#119)
# --------------------------------------------------------------------------
# O texto entrega de graca tres coisas que o corpus jogava fora:
#   (a) hierarquia — o chunker usava o padrao mais granular que quebrava e
#       descartava titulo/capitulo/secao;
#   (b) identidade do dispositivo — 93,1% dos chunks federais mencionam um
#       artigo, e o numero nao estava em campo consultavel;
#   (c) referencias cruzadas — 329 chunks federais com "na forma do art.",
#       "nos termos do art.", "previsto/disposto no art.": arestas viradas
#       texto corrido.
#
# EXTRACAO SIM, NAVEGACAO NAO. Referencia e gravada como dado; resolver,
# seguir ou expandir e decisao futura, nao subproduto desta fase.

# Numero do dispositivo: "Art. 61-A", "Art. 5o", "Art. 22".
_RE_DISPOSITIVO = re.compile(r"^\s*Art\.\s*(\d+(?:\s*-\s*[A-Za-z])?)")

# Referencia cruzada explicita. Captura a formula, o numero e — quando o texto
# nomear — a norma alvo. NAO tenta adivinhar a norma quando ela nao esta escrita.
_RE_REFERENCIA = re.compile(
    r"(?P<formula>na forma d[oa]s?|nos termos d[oa]s?|previst[oa]s? n[oa]s?|"
    r"disposto n[oa]s?|conforme|de acordo com)\s+"
    r"art(?:igo)?s?\.?\s*(?P<artigo>\d+(?:\s*-\s*[A-Za-z])?)(?:\s*[ºo°]\.?)?"
    # Lookahead: o `resto` e OLHADO, nao consumido. Consumindo, uma segunda
    # referencia logo depois era engolida pela primeira — e o `trecho` gravado
    # continha texto de outra citacao.
    r"(?=(?P<resto>[^;\n]{0,60}))",
    re.IGNORECASE,
)

# Norma nomeada LOGO APOS o artigo ("art. 12 da Lei 12.651/2012").
#
# ANCORADA no inicio do `resto`, aceitando so o conector. A norma tem de seguir
# o artigo diretamente: sem a ancora, "art. 8 aplica-se conforme resolucao
# CONAMA 369" ligava o art. 8 a uma resolucao que e OUTRA referencia. Alvo
# errado e pior que alvo ausente, porque tem cara de dado.
#
# O numero aceita ponto: sem isso, "Lei 12.651/2012" virava "Lei 12".
_RE_CONSTITUICAO = re.compile(
    r"^[\s,]*(?:d[aeo]s?\s+)?constitui[çc][ãa]o(\s+federal)?", re.IGNORECASE
)

_RE_NORMA_ALVO = re.compile(
    r"^[\s,]*(?:d[aeo]s?\s+)?"
    r"(?P<tipo>lei complementar|lei|decreto-lei|decreto|resolu[çc][ãa]o|"
    r"instru[çc][ãa]o normativa|portaria|medida provis[óo]ria)\b"
    r"[^0-9\n]{0,20}?(?P<numero>\d[\d.]*)(?:\s*/\s*(?P<ano>\d{4}))?",
    re.IGNORECASE,
)

# Alvo declarado quando o texto NAO nomeia a norma. Nao e "a norma atual" —
# assumir isso seria inferencia apresentada como leitura (familia #121/#123).
ALVO_NAO_DECLARADO = "nao_declarado_no_texto"

ORIGEM_LIDA = "lido"        # o cabecalho do dispositivo esta NESTE chunk
ORIGEM_HERDADA = "herdado"  # veio da fatia-mae; este pedaco nao o contem


@dataclass
class TextChunk:
    """Pedaco de texto resultante do chunking."""

    text: str
    section: str | None
    index: int
    tokens: int
    # Estrutura da norma (#119) — dado extraido, nao inferencia.
    hierarquia: dict[str, str] | None = None
    dispositivo: str | None = None
    dispositivo_origem: str | None = None
    referencias: list[dict[str, str]] | None = None


def _split_by_pattern(text: str, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    """Quebra texto pelos matches de `pattern`. Retorna [(start_offset, slice), ...]."""
    matches = list(pattern.finditer(text))
    if not matches:
        return [(0, text)]
    out: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((start, text[start:end]))
    # Conteudo antes do primeiro match — ex: ementa, preambulo.
    if matches[0].start() > 0:
        prelude = text[: matches[0].start()].strip()
        if prelude:
            out.insert(0, (0, prelude))
    return out


def _label_section(slice_text: str) -> str | None:
    """Extrai um label curto do inicio do slice (ex: 'Art. 12', 'Capitulo III')."""
    head = slice_text.lstrip()[:120]
    first_line = head.splitlines()[0] if head else ""
    return first_line.strip() or None


def _mapa_hierarquico(text: str) -> dict[str, list[tuple[int, str]]]:
    """Posicoes de titulo/capitulo/secao no texto, para reconstruir o caminho.

    O chunker corta pelo padrao mais granular que quebra e descarta os demais.
    A hierarquia nao precisa ser inferida: ela esta escrita, so nao estava sendo
    guardada. Aqui e lida uma vez, por deslocamento.
    """
    mapa: dict[str, list[tuple[int, str]]] = {}
    for nome, padrao in _PATTERNS:
        if nome == "artigo":
            continue
        marcas: list[tuple[int, str]] = []
        for m in padrao.finditer(text):
            linha = text[m.start() : m.start() + 120].splitlines()[0].strip()
            marcas.append((m.start(), linha))
        if marcas:
            mapa[nome] = marcas
    return mapa


def _hierarquia_em(mapa: dict[str, list[tuple[int, str]]], offset: int) -> dict[str, str]:
    """Ultimo titulo/capitulo/secao ANTES do deslocamento — o caminho do trecho."""
    caminho: dict[str, str] = {}
    for nome, marcas in mapa.items():
        anterior = [rotulo for pos, rotulo in marcas if pos <= offset]
        if anterior:
            caminho[nome] = anterior[-1]
    return caminho


def _extrair_dispositivo(slice_text: str) -> str | None:
    """Numero do artigo, lido do cabecalho. `None` quando nao ha cabecalho."""
    m = _RE_DISPOSITIVO.match(slice_text)
    if not m:
        return None
    return re.sub(r"\s*-\s*", "-", m.group(1)).upper()


def _extrair_referencias(texto: str) -> list[dict[str, str]]:
    """Referencias cruzadas explicitas, como DADO.

    Extracao apenas. Nao resolve, nao seque, nao expande — grafo e decisao
    futura. E quando o texto nao nomeia a norma alvo, isso e gravado como
    `nao_declarado_no_texto`: supor "e a norma atual" seria inferencia
    apresentada como leitura, que e a familia da #121/#123. Referencia que nao
    casa com norma conhecida tambem e dado legitimo — nunca descartada em
    silencio nem "consertada" por aproximacao.
    """
    achadas: list[dict[str, str]] = []
    vistas: set[tuple[str, str]] = set()
    for m in _RE_REFERENCIA.finditer(texto):
        artigo = re.sub(r"\s*-\s*", "-", m.group("artigo")).upper()
        resto = m.group("resto") or ""
        alvo = ALVO_NAO_DECLARADO
        if _RE_CONSTITUICAO.match(resto):
            alvo = "Constituicao Federal"
        norma = _RE_NORMA_ALVO.match(resto)
        if norma:
            partes = [norma.group("tipo").strip()]
            partes.append(norma.group("numero"))
            if norma.group("ano"):
                partes[-1] = f"{norma.group('numero')}/{norma.group('ano')}"
            alvo = " ".join(partes)
        chave = (artigo, alvo)
        if chave in vistas:
            continue
        vistas.add(chave)
        achadas.append({
            "artigo": artigo,
            "norma_alvo": alvo,
            "formula": " ".join(m.group("formula").split()).lower(),
            "trecho": " ".join((m.group(0) + resto).split())[:160],
        })
    return achadas


def _sliding_window(
    text: str,
    base_section: str | None,
    base_index: int,
    hierarquia: dict[str, str] | None = None,
    dispositivo: str | None = None,
) -> list[TextChunk]:
    """Janela deslizante por tokens aproximados, com overlap."""
    chunks: list[TextChunk] = []
    target_chars = TARGET_TOKENS * _CHARS_PER_TOKEN
    overlap_chars = OVERLAP_TOKENS * _CHARS_PER_TOKEN
    step = max(1, target_chars - overlap_chars)

    pos = 0
    sub_idx = 0
    while pos < len(text):
        window = text[pos : pos + target_chars]
        if not window.strip():
            break
        corpo = window.strip()
        # O dispositivo so e "lido" quando o cabecalho esta NESTE pedaco. Nos
        # demais ele vem da fatia-mae — e isso e declarado, nao disfarcado.
        lido_aqui = dispositivo is not None and _RE_DISPOSITIVO.match(corpo) is not None
        chunks.append(
            TextChunk(
                text=corpo,
                section=f"{base_section} (parte {sub_idx + 1})" if base_section else None,
                index=base_index + sub_idx,
                tokens=_approx_tokens(window),
                hierarquia=dict(hierarquia) if hierarquia else None,
                dispositivo=dispositivo,
                dispositivo_origem=(
                    None
                    if dispositivo is None
                    else (ORIGEM_LIDA if lido_aqui else ORIGEM_HERDADA)
                ),
                referencias=_extrair_referencias(corpo) or None,
            )
        )
        sub_idx += 1
        pos += step
    return chunks


def chunk_text(text: str) -> list[TextChunk]:
    """Aplica chunking hibrido sobre o texto. Retorna lista ordenada."""
    text = (text or "").strip()
    if not text:
        return []

    # Hierarquia lida UMA vez, por deslocamento: o corte usa o padrao mais
    # granular e descarta os outros niveis, mas eles continuam escritos no
    # texto — so nao estavam sendo guardados (#119).
    mapa = _mapa_hierarquico(text)

    # 1. Tenta marcadores estruturais. Usa o mais granular que retorna >1 split.
    structural: list[tuple[str, int, str]] = []  # (label, offset, texto)
    for label, pattern in reversed(_PATTERNS):
        slices = _split_by_pattern(text, pattern)
        if len(slices) > 1:
            for offset, slice_text in slices:
                structural.append((label, offset, slice_text))
            break

    # 2. Se nenhum padrao quebrou — janela deslizante direta.
    if not structural:
        return _sliding_window(text, base_section=None, base_index=0)

    # 3. Para cada slice estrutural: aceita inteiro se cabe; senao sub-divide.
    chunks: list[TextChunk] = []
    next_index = 0
    for _label, _offset, slice_text in structural:
        slice_text = slice_text.strip()
        if not slice_text:
            continue
        section = _label_section(slice_text)
        tokens = _approx_tokens(slice_text)
        caminho = _hierarquia_em(mapa, _offset) or None
        dispositivo = _extrair_dispositivo(slice_text)

        # Guarda de sanidade: fatia rotulada como artigo acima do plausivel NAO
        # e artigo, e nao pode herdar o rotulo. Cai em estrategia DECLARADA —
        # com log, nunca em silencio — e o conteudo continua indexado sob um
        # rotulo honesto. Rotulo mentiroso e pior que ausencia de rotulo: passa
        # na conferencia.
        # Só vale para fatia que REALMENTE comeca com cabecalho de artigo. O
        # preludio (ementa, cabecalho de Diario Oficial, formulario) tambem cai
        # nesta passada estrutural e tambem pode ser gigante — mas ele nao alega
        # ser artigo nenhum, entao nao ha etiqueta mentirosa para corrigir.
        # Medido: 4 preludios acima do limite, 474 chunks. Trocar o rotulo deles
        # seria mexer no que nao esta quebrado, e perder o pouco de contexto que
        # a primeira linha carrega.
        if (
            _label == "artigo"
            and _RE_ARTIGO.match(slice_text)
            and tokens > LIMITE_ARTIGO_TOKENS
        ):
            logger.warning(
                "chunking.fatia_absorvedora rotulo=%r tokens=%d limite=%d "
                "estrategia=janela_deslizante_sem_rotulo_de_artigo",
                (section or "")[:60],
                tokens,
                LIMITE_ARTIGO_TOKENS,
            )
            # A fatia perde o rotulo de artigo E o dispositivo: ela nao e
            # aquele artigo. A hierarquia, essa, continua valendo — o trecho
            # esta mesmo dentro daquele titulo/capitulo.
            sub_chunks = _sliding_window(
                slice_text, ROTULO_NAO_ARTICULADO, next_index, hierarquia=caminho
            )
            chunks.extend(sub_chunks)
            next_index += len(sub_chunks)
            continue

        # Artigo tem teto proprio: e a unidade semantica do dominio e deve
        # entrar inteiro sempre que couber.
        e_artigo = _label == "artigo" and bool(_RE_ARTIGO.match(slice_text))
        teto = MAX_ARTIGO_TOKENS if e_artigo else MAX_TOKENS

        if tokens <= teto:
            chunks.append(
                TextChunk(
                    text=slice_text,
                    section=section,
                    index=next_index,
                    tokens=tokens,
                    hierarquia=caminho,
                    dispositivo=dispositivo,
                    dispositivo_origem=ORIGEM_LIDA if dispositivo else None,
                    referencias=_extrair_referencias(slice_text) or None,
                )
            )
            next_index += 1
        else:
            # Corte por tamanho e ULTIMO recurso — e deixa rastro. Sem o log,
            # um dispositivo partido ao meio some do radar: a busca devolve
            # meio artigo e ninguem fica sabendo que houve corte.
            if e_artigo:
                logger.info(
                    "chunking.artigo_cortado_por_tamanho rotulo=%r tokens=%d teto=%d",
                    (section or "")[:60],
                    tokens,
                    teto,
                )
            sub_chunks = _sliding_window(
                slice_text, section, next_index,
                hierarquia=caminho, dispositivo=dispositivo,
            )
            chunks.extend(sub_chunks)
            next_index += len(sub_chunks)

    return chunks
