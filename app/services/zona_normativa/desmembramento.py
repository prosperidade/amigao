"""Desmembramento determinístico das coletâneas (ADR-075 §5).

A coletânea é **proveniência**, não fonte citável: um "Art. 70" dela não diz de
que lei é. Aqui ela é cortada em atos por **regra fixa**, sem LLM e sem OCR —
a fronteira tem sinal medido, e cortar por modelo seria cortar sem trilha.

Sinais, em ordem de força:

1. **Impressão do navegador.** MS, MT, GO e AC são páginas impressas e
   concatenadas. Cada página termina num bloco ``dd/mm/aaaa, hh:mm <título da
   aba>`` + ``<URL> n/m`` (no Acre o ``n/m`` pode vir linhas abaixo). Troca de
   URL, ou a paginação voltando a 1, fecha um documento e abre outro. O título
   da aba ("L6938", "DECRETO Nº 16.588 DE 12/03/2025") confirma a identidade.
2. **Cabeçalho formal em contexto de abertura**, nas regiões sem impressão:
   linha própria em maiúsculas (``DECRETO Nº 1.473, DE …``) seguida de ementa ou
   preâmbulo ("Dispõe sobre…", "O GOVERNADOR…", "RESOLVE"). Cabeçalho citado no
   meio do texto não tem abertura e não corta.

Paginação solta (``1/01``) NÃO é sinal: no MT-NUC04 ela é código CNAE de
tabela (``0152-1/01``). Só conta ``n/m`` preso a uma URL.

O que não fecha fica marcado para a revisão humana — nunca decidido por
aproximação: identidade sem ano, início de documento estimado, mais de um ato na
mesma impressão, título da aba divergente do cabeçalho.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass, field

from app.services.normalizacao import normalizar
from app.services.zona_normativa.identidade import (
    ORGAOS_FEDERAIS_SIGLA,
    RE_ATO_SEFAZ,
    RE_CABECALHO,
    RE_CONSTITUICAO,
    IdentidadeNorma,
    identidade_de_cabecalho,
)

# ---------------------------------------------------------------------------
# Sinal 1 — mobiliário de impressão
# ---------------------------------------------------------------------------

RE_CABECALHO_IMPRESSAO = re.compile(
    r"^[ \t\ufeff]*(?P<data>\d{2}/\d{2}/\d{4}), (?P<hora>\d{2}:\d{2})(?:[ \t]+(?P<titulo>.*\S))?[ \t]*$",
    re.M,
)
RE_URL_RODAPE = re.compile(
    r"^[ \t]*(?P<url>(?:https?://|www\.)\S+?)(?:[ \t]+(?P<n>\d+)/(?P<m>\d+))?[ \t]*$", re.M
)
RE_PAGINA_SOLTA = re.compile(r"^[ \t]*(?P<n>\d+)/(?P<m>\d+)[ \t]*$")

# Cromo do portal LEGIS (AC) e glifos de ícone da área de uso privado.
_RE_GLIFO = re.compile(r"[\ue000-\uf8ff\U000f0000-\U0010ffff]")
_CROMO_LEGIS = re.compile(
    r"^\s*(LEGIS :: Portal da Legisla[çc][ãa]o.*|Voltar|Relacionados Servi[çc]os Links Externos|"
    r"Governo do Estado do Acre Perguntas Frequentes.*|Secretaria de Estado da Casa Civil Reporte um erro.*|"
    r"Di[áa]rio Oficial do Estado do Acre Fale Conosco.*|Assembleia Legislativa do Estado do Acre Mapa do Site.*|"
    r"Tribunal de Contas do Estado do Acre|Secretaria de Estado da Casa Civil \| CASA CIVIL|"
    r"Av\. Brasil, 307-447.*|\d{4} Governo do Estado do Acre|Copyright Todos os direitos reservados|"
    r"Diretoria de Moderniza[çc][ãa]o)\s*$",
    re.I,
)

# ---------------------------------------------------------------------------
# Sinal 2 — abertura de ato
# ---------------------------------------------------------------------------

RE_ABERTURA_ANTES = re.compile(
    r"(ESTADO D[OE]|GOVERNO DO ESTADO|ASSEMBLEIA LEGISLATIVA|SECRETARIA DE ESTADO|"
    r"Presid[êe]ncia da Rep[úu]blica|Casa Civil|Subchefia|Compilado|CONSELHO ESTADUAL|"
    r"PODER EXECUTIVO|GABINETE|Publicad[oa] no D)",
    re.I,
)
RE_ABERTURA_DEPOIS = re.compile(
    r"^\s*(Disp[õo]e|Altera|Institui|Estabelece|Regulamenta|Aprova|Cria|Define|Revoga|"
    r"Autoriza|Declara|Prorroga|Fixa|Homologa|Disciplina|Normatiza|Consolida|Publicad[oa]|"
    r"O GOVERNADOR|A GOVERNADORA|O PRESIDENTE|A PRESIDENTE|O SECRET[ÁA]RIO|A SECRET[ÁA]RIA|"
    r"O CONSELHO|A ASSEMBLEIA|O DIRETOR|FA[ÇC]O SABER|DECRETA|RESOLVE)",
    re.I | re.M,
)

# Órgão emissor pelo contexto de abertura — só para espécie numerada por órgão
# cuja linha de cabeçalho não diz o órgão ("PORTARIA Nº 183/2020").
_ORGAO_CONTEXTO: tuple[tuple[str, str], ...] = (
    (r"\bIMASUL\b|INSTITUTO DE MEIO AMBIENTE DE MATO GROSSO DO SUL", "imasul"),
    (r"\bSEMADESC\b", "semadesc"),
    (r"\bSEMAGRO\b", "semagro"),
    (r"\bSEMADE\b", "semade"),
    (r"\bSEMAD\b|MEIO AMBIENTE E DESENVOLVIMENTO SUSTENT[ÁA]VEL", "semad"),
    (r"\bCEMAm\b", "cemam"),
    (r"\bCONSEMA\b", "consema"),
    (r"\bCECA\b", "ceca"),
    (r"\bCEMACT\b", "cemact"),
    (r"\bCERH\b|CONSELHO ESTADUAL DE RECURSOS H[ÍI]DRICOS", "cerh"),
    (r"\bIMAC\b|INSTITUTO DE MEIO AMBIENTE DO ACRE", "imac"),
    (r"\bSEMAPI\b", "semapi"),
    (r"\bSEMA\b|SECRETARIA DE ESTADO DE MEIO AMBIENTE\b", "sema"),
    (r"\bSEFAZ\b", "sefaz"),
    (r"\bINDEA\b", "indea"),
    (r"\bIDAF\b", "idaf"),
)

RE_FEDERAL = re.compile(r"Presid[êe]ncia da Rep[úu]blica|planalto\.gov\.br", re.I)

MOTIVO_IDENTIDADE_ND = "identidade_nao_determinada"
MOTIVO_INICIO_ESTIMADO = "inicio_estimado"
MOTIVO_SEM_PAGINA_1 = "impressao_sem_pagina_1"
MOTIVO_MULTIPLOS_ATOS = "multiplos_atos_na_impressao"
MOTIVO_TITULO_DIVERGE = "titulo_da_aba_diverge_do_cabecalho"
MOTIVO_SEM_SINAL = "regiao_sem_sinal_de_fronteira"

SINAL_IMPRESSAO = "impressao"
SINAL_CABECALHO = "cabecalho_formal"
SINAL_NENHUM = "sem_sinal"


@dataclass
class Rodape:
    inicio: int
    fim: int
    url: str
    url_norm: str
    n: int
    m: int
    titulo: str | None
    impresso_em: str | None


@dataclass
class Segmento:
    inicio: int
    fim: int
    sinal: str
    url: str | None = None
    impresso_em: str | None = None
    pagina_inicio: int | None = None   # ordinal da página impressa na coletânea (1-based)
    pagina_fim: int | None = None
    titulo_aba: str | None = None
    cabecalho: str | None = None
    identidade: IdentidadeNorma | None = None
    motivos: list[str] = field(default_factory=list)
    texto: str = ""

    @property
    def determinado(self) -> bool:
        return self.identidade is not None and self.identidade.determinada

    @property
    def hash_texto(self) -> str:
        return hash_texto_normalizado(self.texto)


def hash_texto_normalizado(texto: str) -> str:
    """Hash do texto do ato sem mobiliário, com espaço colapsado.

    Duas impressões do mesmo ato (datas de impressão diferentes) têm de colidir;
    duas redações diferentes do mesmo ato, não — essas são versões.
    """
    corpo = re.sub(r"\s+", " ", texto).strip()
    return hashlib.sha256(corpo.encode("utf-8")).hexdigest()


def _normalizar_url(url: str) -> str:
    u = url.strip().rstrip("…").rstrip(".").rstrip("/")
    u = re.sub(r"^https?://", "", u, flags=re.I)
    return re.sub(r"^www\.", "", u, flags=re.I).lower()


def _linhas_com_pos(texto: str, inicio: int, fim: int):
    pos = inicio
    for linha in texto[inicio:fim].split("\n"):
        yield pos, linha
        pos += len(linha) + 1


def encontrar_rodapes(texto: str) -> list[Rodape]:
    """Blocos ``[cabeçalho de impressão] + URL n/m`` — o fim de cada página impressa."""
    out: list[Rodape] = []
    for m in RE_URL_RODAPE.finditer(texto):
        n, mm = m.group("n"), m.group("m")
        fim = m.end()
        if n is None:
            # Acre: "URL" e, linhas abaixo, "n/m" sozinho.
            resto = texto[m.end() : m.end() + 400].split("\n")
            pos = m.end() + len(resto[0]) + 1
            achou = None
            for linha in resto[1:9]:
                if not linha.strip():
                    pos += len(linha) + 1
                    continue
                pm = RE_PAGINA_SOLTA.match(linha)
                if pm:
                    achou = pm
                    fim = pos + len(linha)
                break
            if achou is None:
                continue  # URL citada no corpo do texto: não é rodapé
            n, mm = achou.group("n"), achou.group("m")
        ni, mi = int(n), int(mm)
        if ni < 1 or mi < 1 or ni > mi or mi > 2000:
            continue
        # Cabeçalho de impressão colado ANTES da URL (MS/MT/GO): título da aba.
        antes = texto[max(0, m.start() - 400) : m.start()].rstrip("\n").split("\n")
        titulo = impresso = None
        inicio = m.start()
        for recuo, linha in enumerate(reversed(antes[-3:])):
            ch = RE_CABECALHO_IMPRESSAO.match(linha)
            if ch:
                titulo = ch.group("titulo")
                impresso = f"{ch.group('data')} {ch.group('hora')}"
                inicio = m.start() - sum(len(x) + 1 for x in antes[len(antes) - recuo - 1 :])
                break
            if linha.strip():
                break
        out.append(Rodape(inicio, fim, m.group("url"), _normalizar_url(m.group("url")),
                          ni, mi, titulo, impresso))
    return out


def mesma_url(a: str, b: str) -> bool:
    """URL longa sai truncada com '…' numa largura fixa: quando a página passa de
    '9/18' para '10/18', a URL perde um caractere. Prefixo comum longo é a mesma."""
    if a == b:
        return True
    curta, longa = sorted((a, b), key=len)
    return len(curta) >= 25 and longa.startswith(curta)


def agrupar_impressoes(rodapes: list[Rodape]) -> list[list[Rodape]]:
    """Rodapés consecutivos da mesma URL, com paginação crescente, são um documento."""
    grupos: list[list[Rodape]] = []
    for r in rodapes:
        g = grupos[-1] if grupos else None
        if (
            g is None
            or not mesma_url(r.url_norm, g[-1].url_norm)
            or r.n <= g[-1].n
            or r.m != g[-1].m
            or r.n == 1
        ):
            grupos.append([r])
        else:
            g.append(r)
    return grupos


# ---------------------------------------------------------------------------
# Cabeçalho formal
# ---------------------------------------------------------------------------

def _maiusculas(linha: str) -> bool:
    corpo = re.sub(r"[^A-Za-zÀ-ú]", "", linha)
    return bool(corpo) and sum(c.isupper() for c in corpo) / len(corpo) >= 0.7


def _eh_linha_cabecalho(linha: str) -> bool:
    if len(linha.strip()) > 170:
        return False
    if RE_CONSTITUICAO.match(linha):
        return True
    m = RE_CABECALHO.match(linha.strip())
    return bool(m) and _maiusculas(linha)


def _tem_abertura(texto: str, pos_linha: int, fim_linha: int) -> bool:
    antes = texto[max(0, pos_linha - 400) : pos_linha]
    depois = texto[fim_linha : fim_linha + 900]
    return bool(RE_ABERTURA_ANTES.search(antes)) or bool(RE_ABERTURA_DEPOIS.search(depois))


def cabecalhos_de_abertura(texto: str, inicio: int, fim: int) -> list[tuple[int, str]]:
    out = []
    for pos, linha in _linhas_com_pos(texto, inicio, fim):
        if _eh_linha_cabecalho(linha) and _tem_abertura(texto, pos, pos + len(linha)):
            out.append((pos, linha.strip()))
    return out


def orgao_do_contexto(trecho: str) -> str:
    for padrao, sigla in _ORGAO_CONTEXTO:
        if re.search(padrao, trecho):
            return sigla
    return ""


def _ano_da_constituicao(trecho: str) -> int | None:
    m = re.search(r"promulgad[ao][^\n]{0,60}?((?:19|20)\d{2})", trecho, re.I) or re.search(
        r"\b(19[4-9]\d|20[0-2]\d)\b", trecho
    )
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Limpeza
# ---------------------------------------------------------------------------

def limpar_mobiliario(trecho: str) -> str:
    """Tira cabeçalho/rodapé de impressão e cromo de portal. O texto do ato fica."""
    out: list[str] = []
    linhas = trecho.split("\n")
    pular_pagina = False
    for linha in linhas:
        if RE_CABECALHO_IMPRESSAO.match(linha) or _CROMO_LEGIS.match(linha):
            continue
        mu = RE_URL_RODAPE.match(linha)
        if mu:
            pular_pagina = mu.group("n") is None
            continue
        if pular_pagina:
            if not linha.strip():
                continue
            pular_pagina = False
            if RE_PAGINA_SOLTA.match(linha):
                continue
        limpa = _RE_GLIFO.sub("", linha)
        if linha.strip() and not limpa.strip():
            continue
        out.append(limpa)
    texto = "\n".join(out)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return normalizar(texto).strip()


# ---------------------------------------------------------------------------
# Identidade do segmento
# ---------------------------------------------------------------------------

def _identidade(seg: Segmento, bruto: str, uf: str) -> None:
    ente = uf.lower()
    limpo = seg.texto
    abertura = limpo[:3000]
    federal = bool(RE_FEDERAL.search(abertura[:1500])) or (
        seg.url is not None and "planalto.gov.br" in seg.url
    )
    ente_seg = "br" if federal else ente

    # (a) cabeçalho formal nas primeiras linhas do ato
    ident_cab = None
    for linha in abertura.split("\n")[:60]:
        if _eh_linha_cabecalho(linha):
            pos = abertura.find(linha)
            ctx = abertura[max(0, pos - 600) : pos + 1500]
            ident_cab = identidade_de_cabecalho(
                linha, ente_padrao=ente_seg, orgao_contexto=orgao_do_contexto(ctx)
            )
            if ident_cab is not None:
                seg.cabecalho = linha.strip()[:200]
                if ident_cab.tipo == "constituicao" and ident_cab.ano is None:
                    ident_cab = IdentidadeNorma(
                        "constituicao", ident_cab.ente, ano=_ano_da_constituicao(limpo[:6000])
                    )
                break

    # (a') cabeçalho em tabela da SEFAZ-MT ("Ato: Decreto Número/Complemento … 1031/2017")
    if ident_cab is None:
        ms = RE_ATO_SEFAZ.search(abertura[:1500])
        if ms:
            ident_cab = identidade_de_cabecalho(
                ms.group(0), ente_padrao=ente_seg, orgao_contexto=orgao_do_contexto(abertura[:2000])
            )
            seg.cabecalho = re.sub(r"\s+", " ", ms.group(0))[:200]

    # (b) título da aba de impressão
    ident_tit = None
    if seg.titulo_aba:
        tit = re.split(r"\s+-\s+(?:Casa Civil|Leis\.org|Estadual|LegisWeb|Legisweb)", seg.titulo_aba)[0]
        ident_tit = identidade_de_cabecalho(
            tit, ente_padrao=ente_seg, orgao_contexto=orgao_do_contexto(abertura[:2000])
        )

    ident = ident_cab or ident_tit
    if ident_cab and ident_tit and ident_tit.determinada:
        a, b = ident_cab, ident_tit
        if (a.tipo, a.numero) != (b.tipo, b.numero):
            seg.motivos.append(MOTIVO_TITULO_DIVERGE)
    # Título do Planalto não traz ano: o cabeçalho do corpo completa, se casar.
    if ident is not None and ident.ano is None and ident.tipo != "constituicao":
        for m in RE_CABECALHO.finditer(abertura):
            outra = identidade_de_cabecalho(m.group(0), ente_padrao=ident.ente)
            if outra and (outra.tipo, outra.numero) == (ident.tipo, ident.numero) and outra.ano:
                ident = IdentidadeNorma(ident.tipo, ident.ente, ident.orgao, ident.numero, outra.ano)
                break
    if ident is not None and ident.orgao in ORGAOS_FEDERAIS_SIGLA and ident.ente != "br":
        ident = IdentidadeNorma(ident.tipo, "br", ident.orgao, ident.numero, ident.ano)
    seg.identidade = ident
    if ident is None or not ident.determinada:
        seg.motivos.append(MOTIVO_IDENTIDADE_ND)


# ---------------------------------------------------------------------------
# Corte
# ---------------------------------------------------------------------------

def _segmentar_regiao(texto: str, inicio: int, fim: int) -> list[Segmento]:
    """Região sem impressão: corta só em cabeçalho formal com abertura."""
    if not texto[inicio:fim].strip():
        return []
    heads = cabecalhos_de_abertura(texto, inicio, fim)
    segs: list[Segmento] = []
    cortes = [p for p, _ in heads]
    if not cortes or texto[inicio : cortes[0]].strip():
        # O que vem antes do primeiro cabeçalho não tem sinal: fica como está,
        # marcado. Nunca é descartado em silêncio.
        primeiro_fim = cortes[0] if cortes else fim
        segs.append(Segmento(inicio, primeiro_fim, SINAL_NENHUM, motivos=[MOTIVO_SEM_SINAL]))
    for i, p in enumerate(cortes):
        segs.append(Segmento(p, cortes[i + 1] if i + 1 < len(cortes) else fim, SINAL_CABECALHO))
    return segs


def desmembrar(texto: str, uf: str) -> list[Segmento]:
    """Corta a coletânea em segmentos (candidatos a ato) com identidade e motivos."""
    rodapes = encontrar_rodapes(texto)
    grupos = agrupar_impressoes(rodapes)
    ordinal = {id(r): i + 1 for i, r in enumerate(rodapes)}

    distancias = [b.fim - a.fim for a, b in zip(rodapes, rodapes[1:], strict=False) if b.n == a.n + 1]
    pagina_tipica = int(statistics.median(distancias)) if distancias else 4000
    limite = max(6000, int(pagina_tipica * 2.0))

    segs: list[Segmento] = []
    cursor = 0
    for g in grupos:
        primeiro, ultimo = g[0], g[-1]
        gap_inicio = cursor
        inicio = cursor
        motivos: list[str] = []
        if primeiro.n != 1:
            motivos.append(MOTIVO_SEM_PAGINA_1)
        if len(texto[cursor : primeiro.inicio].strip()) > limite:
            # Material sem impressão antes da página 1: achar onde a página 1 começa.
            janela_ini = max(cursor, primeiro.inicio - limite)
            cands = [
                (p, lin) for p, lin in _linhas_com_pos(texto, janela_ini, primeiro.inicio)
                if _eh_linha_cabecalho(lin)
            ]
            if cands:
                inicio = cands[0][0]
                # Linhas de abertura logo acima ("ESTADO DE…", "Presidência…") vão junto.
                acima = texto[max(cursor, inicio - 300) : inicio].split("\n")
                for linha in reversed(acima[:-1] if acima and acima[-1] == "" else acima):
                    if linha.strip() and RE_ABERTURA_ANTES.search(linha) and len(linha) < 120:
                        inicio -= len(linha) + 1
                    elif linha.strip():
                        break
            else:
                inicio = texto.rfind("\n", cursor, max(cursor, primeiro.inicio - pagina_tipica)) + 1
                motivos.append(MOTIVO_INICIO_ESTIMADO)
            inicio = max(inicio, cursor)
            segs.extend(_segmentar_regiao(texto, gap_inicio, inicio))
        seg = Segmento(
            inicio, ultimo.fim, SINAL_IMPRESSAO, url=primeiro.url,
            impresso_em=primeiro.impresso_em, pagina_inicio=ordinal[id(primeiro)],
            pagina_fim=ordinal[id(ultimo)], titulo_aba=primeiro.titulo, motivos=motivos,
        )
        internos = cabecalhos_de_abertura(texto, inicio, ultimo.fim)
        ids = {
            (x.tipo, x.numero)
            for _, lin in internos
            if (x := identidade_de_cabecalho(lin, ente_padrao=uf.lower())) is not None
        }
        if len(ids) > 1:
            seg.motivos.append(MOTIVO_MULTIPLOS_ATOS)
        segs.append(seg)
        cursor = ultimo.fim
    segs.extend(_segmentar_regiao(texto, cursor, len(texto)))

    # Pedaço sem sinal pequeno demais para ser ato vai para o segmento anterior —
    # continuação de página, não documento. Grande, fica próprio e marcado.
    fundidos: list[Segmento] = []
    for s in segs:
        corpo = texto[s.inicio : s.fim].strip()
        if not corpo:
            continue
        if s.sinal == SINAL_NENHUM and len(corpo) < 400 and fundidos:
            fundidos[-1].fim = s.fim
            continue
        fundidos.append(s)

    for s in fundidos:
        s.texto = limpar_mobiliario(texto[s.inicio : s.fim])
        _identidade(s, texto, uf)

    # Ficha do portal seguida do texto do mesmo ato (LEGIS/AC: "LEI ORDINÁRIA Nº
    # 1022…" e logo abaixo "LEI N. 1.022…") é UM ato: vizinhos com a mesma
    # identidade determinada, cortados só por cabeçalho, se juntam.
    juntos: list[Segmento] = []
    for s in fundidos:
        ant = juntos[-1] if juntos else None
        if (
            ant is not None and s.sinal == SINAL_CABECALHO and ant.fim == s.inicio
            and s.determinado and ant.determinado
            and ant.identidade.chave == s.identidade.chave
        ):
            ant.fim = s.fim
            ant.texto = limpar_mobiliario(texto[ant.inicio : ant.fim])
            continue
        juntos.append(s)
    return [s for s in juntos if s.texto]
