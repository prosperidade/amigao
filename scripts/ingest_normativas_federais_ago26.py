"""
scripts/ingest_normativas_federais_ago26.py — pacote NORMATIVAS (Isis, 2026-08-04)

Ingere 13 normas federais entregues em `legislacao/NORMATIVAS.rar` no corpus RAG
(`legislation_documents` + `knowledge_catalog`), jurisdição federal, pelo pipeline
da casa: chunking híbrido → OpenAI text-embedding-3-small, 768 dim.

Operação ADITIVA. O script nunca apaga, nunca sobrescreve e nunca supersede:
identificador que já existe no corpus é PULADO e relatado. Isso é deliberado e
difere de `ingest_pasta_socia.py` / `ingest_federais_canonicos.py`, que marcam a
versão antiga como `superseded`. Aqui o pacote é uma DOAÇÃO de terceiro; decidir
que o PDF da sócia substitui um texto já curado (e possivelmente vindo de fonte
oficial melhor) é decisão humana, não de ingestor.

Três dos PDFs são impressões de página web e vêm com mobiliário de impressão
(data da captura, URL, "N/M", menu do site). Esse lixo NÃO pode virar chunk:
já aconteceu neste corpus de "Página Inicial / Legislações / Voltar" ser o trecho
mais similar de uma busca de defesa federal. Ver `limpar_moldura()`.

Uso:
    python scripts/ingest_normativas_federais_ago26.py --inventario   # Passo 0
    python scripts/ingest_normativas_federais_ago26.py --dry-run      # chunking real, sem gravar
    python scripts/ingest_normativas_federais_ago26.py                # ingere + indexa
    python scripts/ingest_normativas_federais_ago26.py --only "INCRA"
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import math
import re
import sys
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_legislation import (  # noqa: E402
    estimate_tokens,
    sanitize_text,
    save_preview,
    verificar_mojibake,
)

logger = logging.getLogger("ingest_normativas_ago26")

PASTA_PADRAO = Path("legislacao/NORMATIVAS")

# text-embedding-3-small: US$ 0,02 por 1M tokens (app/services/embeddings.py).
USD_POR_MILHAO_DE_TOKENS = 0.02
# Teto de sanidade do pacote inteiro. ~200 páginas embedam por centavos; qualquer
# coisa perto de um dólar significa que estamos embedando outra coisa.
TETO_CUSTO_USD = 1.0


# ---------------------------------------------------------------------------
# Curadoria — metadados canônicos (ementa lida no PDF)
# ---------------------------------------------------------------------------
# `arquivo`     nome no pacote, tal como veio
# `identifier`  identificador CANÔNICO — nem sempre igual ao nome do arquivo
# `sha256`      hash do PDF, conferido contra o manifesto do despacho
# `moldura`     True = PDF é impressão de página web, passa pela limpeza
# `corte_fim`   âncora de rodapé de site que a detecção por repetição não pega
#               (aparece uma vez só, na última página)
CURADORIA: list[dict] = [
    {
        "arquivo": "IN MMA 02-2014.pdf",
        "identifier": "IN MMA 2/2014",
        "title": "Instrução Normativa MMA 2/2014 — integração e execução do SICAR e procedimentos gerais do CAR",
        "source_type": "instrucao_normativa",
        "agency": "MMA",
        "published_at": "2014-05-06",
        "ementa": "Integração/execução do SICAR e procedimentos gerais do CAR",
        "demand_types": ["car", "retificacao_car"],
        "sha256": "ee5ebc03621fa71c9d90bf9356edacb599011164b1867f6fdff5ab721e438a2d",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — sem marcador de publicação oficial no documento",
        "fonte_oficial": False,
    },
    {
        "arquivo": "IN INCRA 77-2013.pdf",
        "identifier": "IN INCRA 77/2013",
        "title": "Instrução Normativa INCRA 77/2013 — certificação da poligonal de imóveis rurais (art. 176, §5º, Lei 6.015/1973)",
        "source_type": "instrucao_normativa",
        "agency": "INCRA",
        "published_at": "2013-08-23",
        "ementa": "Certificação da poligonal de imóveis rurais (art. 176 §5º, Lei 6.015/73)",
        "demand_types": ["regularizacao_fundiaria", "sobreposicao", "due_diligence"],
        "sha256": "c24df636e38d0d1adeae5b02f8f61cad863c97cac778aee41a767a5cdc9578ab",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — sem marcador de publicação oficial no documento",
        "fonte_oficial": False,
    },
    {
        "arquivo": "IN RFB 2.203-2024.pdf",
        "identifier": "IN RFB 2.203/2024",
        "title": "Instrução Normativa RFB 2.203/2024 — Cadastro de Imóveis Rurais (Cafir)",
        "source_type": "instrucao_normativa",
        "agency": "RFB",
        "published_at": "2024-07-17",
        "ementa": "Cadastro de Imóveis Rurais — Cafir",
        "demand_types": ["regularizacao_fundiaria", "due_diligence"],
        "sha256": "d2260fe418d744fe29131d8d95e901fb357af3abaf90be7dfe5658ce043a2949",
        "moldura": True,
        # A norma acaba em "ANEXO ÚNICO (exclusivo para assinantes)"; daí em diante
        # é blog da LEX — e o pior dele não é o menu, são os TÍTULOS DE OUTRAS
        # NORMAS ("Postagens Recentes": Resolução ANA 298/2026, Portaria MIDR
        # 2.458/2026, Lei 15.481/2026). Sem este corte, esses títulos viram chunk
        # sob a identidade da IN RFB 2.203/2024 e a busca devolve norma trocada.
        "corte_fim": "Post seguinte",
        "fonte_origem": "captura de www.lex.com.br (LEX EDITORA) — agregador comercial, NÃO é fonte oficial",
        "fonte_oficial": False,
    },
    {
        "arquivo": "Resolução CMN 5.193-2024.pdf",
        "identifier": "Resolução CMN 5.193/2024",
        "title": "Resolução CMN 5.193/2024 — impedimentos sociais, ambientais e climáticos ao crédito rural (MCR 2-9)",
        "source_type": "resolucao",
        "agency": "CMN/Bacen",
        "published_at": "2024-12-19",
        "ementa": "Altera MCR 2-9 (impedimentos sociais, ambientais e climáticos ao crédito rural)",
        "demand_types": ["exigencia_bancaria", "car", "defesa"],
        "sha256": "16f891b50bc019f00ec4b50fe5d135bb66e7db787659c5f8dc87c601e2e1af06",
        "moldura": True,
        "corte_fim": "Siga o BC\nGarantir a estabilidade de preços",
        "fonte_origem": "captura de www.bcb.gov.br/estabilidadefinanceira/exibenormativo (Banco Central — oficial)",
        "fonte_oficial": True,
    },
    {
        "arquivo": "RESOLUCAO CONAMA 369-2006.pdf",
        "identifier": "Resolução CONAMA 369/2006",
        "title": "Resolução CONAMA 369/2006 — intervenção/supressão de vegetação em APP em casos excepcionais",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "published_at": "2006-03-28",
        "ementa": "Intervenção/supressão de vegetação em APP — casos excepcionais",
        "demand_types": ["licenciamento", "supressao", "compensacao"],
        "sha256": "f32f483b401a14e74558135993cd5968e32a1ec78c10777cad27abdddbdf9a15",
        "moldura": True,
        "fonte_origem": "captura de www.siam.mg.gov.br/sla (SIAM/SEMAD-MG — espelho estadual oficial)",
        "fonte_oficial": True,
    },
    {
        "arquivo": "RESOLUCAO CONAMA 406-2009.pdf",
        "identifier": "Resolução CONAMA 406/2009",
        "title": "Resolução CONAMA 406/2009 — parâmetros técnicos de PMFS madeireiro no bioma Amazônia",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "published_at": "2009-02-02",
        "ementa": "Parâmetros técnicos de PMFS madeireiro, bioma Amazônia",
        "demand_types": ["licenciamento", "supressao"],
        "sha256": "cc968152331c6643f4b66ca5ebb3064a359fb3302594073078bd1d19a7c82178",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — traz 'Publicado no DOU nº 26, de 06/02/2009, pág. 100'",
        "fonte_oficial": True,
    },
    {
        "arquivo": "RESOLICAO CONAMA 411-2009.pdf",
        "identifier": "Resolução CONAMA 411/2009",
        "title": "Resolução CONAMA 411/2009 — inspeção de indústrias madeireiras, nomenclatura e coeficientes de rendimento",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "published_at": "2009-05-06",
        "ementa": "Inspeção de indústrias madeireiras; nomenclatura e coeficientes de rendimento",
        "demand_types": ["licenciamento", "defesa"],
        "sha256": "97b3d314861ca40affc51c9be31c3d6a010116c478fdc4291f9cb201b305d16f",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — sem marcador de publicação oficial no documento",
        "fonte_oficial": False,
    },
    {
        "arquivo": "IN IBAMA 21-2014.pdf",
        "identifier": "IN IBAMA 21/2014",
        "title": "Instrução Normativa IBAMA 21/2014 — Sistema DOF (texto consolidado com as IN 9/2016 e 13/2017)",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "published_at": "2014-12-24",
        "ementa": "Sistema DOF (alterada por IN 9/2016 e IN 13/2017)",
        "demand_types": ["supressao", "licenciamento"],
        "sha256": "bb98bf58c2b5536d348ce66e6e02de3fd366ea1fc45c572b51f137ef15283fe6",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — traz 'Publicada no DOU de 27/12/2014, Seção 1, páginas 102 a 107'",
        "fonte_oficial": True,
        "nota": (
            "Texto CONSOLIDADO: o rodapé declara não substituir os publicados no DOU "
            "de 27/12/2014, 13/12/2016 e 20/12/2017 — ou seja, já incorpora as "
            "IN 9/2016 e 13/2017 citadas na ementa."
        ),
    },
    {
        "arquivo": "IN IBAMA 16-2022.pdf",
        "identifier": "IN IBAMA 16/2022",
        "title": "Instrução Normativa IBAMA 16/2022 — institui o DOF+ Rastreabilidade",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "published_at": "2022-11-25",
        "ementa": "Institui o DOF+ Rastreabilidade",
        "demand_types": ["supressao", "licenciamento"],
        "sha256": "e533d6703cba9a595bc58309d2d13ef2c092efe15ec66497ee7b75435bade54c",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — layout DOU/in.gov.br, 'não substitui o publicado na versão certificada'",
        "fonte_oficial": True,
    },
    {
        "arquivo": "IN IBAMA 11-2025.pdf",
        "identifier": "IN IBAMA 11/2025",
        "title": "Instrução Normativa IBAMA 11/2025 — migração de saldos de produtos florestais no DOF",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "published_at": "2025-06-18",
        "ementa": "Migração de saldos de produtos florestais no DOF",
        "demand_types": ["supressao", "licenciamento"],
        "sha256": "bd6b58b372ae3770a2fe5b3ea85f9fadcbd2b10b4cd53444395ce4a0d1e505e4",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — layout DOU/in.gov.br, 'não substitui o publicado na versão certificada'",
        "fonte_oficial": True,
    },
    {
        "arquivo": "IN IBAMA 21-2023.pdf",
        "identifier": "IN IBAMA 21/2023",
        "title": "Instrução Normativa IBAMA 21/2023 — conversão de multas ambientais em serviços de preservação, melhoria e recuperação",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "published_at": "2023-06-02",
        "ementa": "Conversão de multas ambientais em serviços ambientais",
        "demand_types": ["defesa"],
        "sha256": "f7009749bc5a460be241b1dc90b084f492360ead9b33de5d98ad9b28ed79d221",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — layout DOU/in.gov.br",
        "fonte_oficial": True,
        "nota": (
            "Texto CONSOLIDADO: traz alterações 'publicada no DOU de 5 de janeiro de "
            "2026' — é a versão atualizada, não a redação original de 2023."
        ),
    },
    {
        "arquivo": "PORTARIA IBAMA 15-2026.pdf",
        "identifier": "Portaria IBAMA 15/2026",
        "title": "Portaria IBAMA 15/2026 — restabelece a adesão à conversão de multas (ref. Portaria 109/2025)",
        "source_type": "portaria",
        "agency": "IBAMA",
        "published_at": "2026-01-30",
        "ementa": "Restabelece adesão à conversão de multas (ref. Portaria 109/2025)",
        "demand_types": ["defesa"],
        "sha256": "c86365b146095faa8cc83165feea34814afd44e3f7370151b6a298b3b99a45ca",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — layout DOU/in.gov.br, 'não substitui o publicado na versão certificada'",
        "fonte_oficial": True,
    },
    {
        # GATE DO DESPACHO: o arquivo se chama "4-2024" porque foi nomeado pelo DIA
        # da assinatura (04/12/2024). O documento é a IN 24/2024. Ingerir com o
        # número do arquivo plantaria no corpus uma norma que não existe — e o
        # sistema cita norma em peça que a consultora assina.
        "arquivo": "IN IBAMA 4-2024.pdf",
        "identifier": "IN IBAMA 24/2024",
        "title": "Instrução Normativa IBAMA 24/2024 — controle ambiental da importação de resíduos",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "published_at": "2024-12-04",
        "ementa": "Controle ambiental da importação de resíduos",
        "demand_types": ["licenciamento"],
        "sha256": "9fc10dcdcf6db7c660697bac46829a6a19514f40c86ade936649cb0d40cc0ff1",
        "fonte_origem": "PDF do pacote NORMATIVAS (Isis, 2026-08-04) — layout DOU/in.gov.br",
        "fonte_oficial": True,
        "nota": (
            "Divergência de nomenclatura no pacote: arquivo nomeado 'IN IBAMA 4-2024.pdf' "
            "(dia da assinatura), documento é a IN 24/2024. Ingerido com o identificador "
            "correto por determinação do despacho."
        ),
    },
]


# ---------------------------------------------------------------------------
# Passo 0 — normalização de identificador para dedupe
# ---------------------------------------------------------------------------
# O corpus não é consistente na grafia: convivem "Res. CONAMA 369/2006" e
# "Resolução CONAMA 428/2010" para o mesmo tipo de norma. Comparar string crua
# deixaria passar duplicata — que é exatamente o que este passo existe para
# impedir. A normalização reduz a norma ao que ela é: tipo + órgão + número + ano.

_SINONIMOS_TIPO = [
    (r"\binstru[çc][ãa]o\s+normativa\b|\bin\b", "in"),
    (r"\bresolu[çc][ãa]o\b|\bres\.?\b", "resolucao"),
    (r"\bportaria\b", "portaria"),
    (r"\bdecreto\b", "decreto"),
    (r"\blei\s+complementar\b|\blc\b", "lei_complementar"),
    (r"\blei\b", "lei"),
    (r"\bmedida\s+provis[óo]ria\b|\bmpv?\b", "mpv"),
]

_ACENTOS = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
                         "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")


def normalizar_identificador(bruto: str | None) -> str:
    """'Res. CONAMA 369/2006' e 'Resolução CONAMA 369/2006' → mesma chave.

    Retorna '<tipo>|<orgao>|<numero>|<ano>'. Número perde zeros à esquerda e
    separadores de milhar ('2.203' e '2203' são a mesma IN; '02' e '2' também).
    """
    if not bruto:
        return ""
    t = bruto.translate(_ACENTOS).lower().strip()

    tipo = ""
    for padrao, nome in _SINONIMOS_TIPO:
        if re.search(padrao, t):
            tipo = nome
            t = re.sub(padrao, " ", t, count=1)
            break

    # número/ano: "77/2013", "2.203/2024", "nº 21 de 2014"
    m = re.search(r"(\d[\d.]*)\s*[/\-]\s*(\d{4})", t)
    numero = ano = ""
    if m:
        numero = m.group(1).replace(".", "").lstrip("0") or "0"
        ano = m.group(2)
        t = t[: m.start()] + " " + t[m.end() :]

    # o que sobra e é alfabético vira o órgão (conama, ibama, incra, mma, rfb...)
    palavras = [p for p in re.findall(r"[a-z]{2,}", t) if p not in {"no", "num", "de", "da", "do"}]
    orgao = "".join(palavras)

    # Sem número E ano isto não é identificador de norma — é rótulo de corpus
    # ("Anexo ATIV-INEX GO 308p", "AC-N03-florestal_car_pra"). Reduzi-los ao
    # mesmo esqueleto vazio faria dois rótulos DIFERENTES casarem como duplicata:
    # medido no corpus, 'Anexo ATIV-INEX GO 308p' e 'Anexo ATIV-INEX GO 7p'
    # caíam na mesma chave. Nesse caso a chave é o texto cru normalizado, que
    # só casa consigo mesmo.
    if not numero or not ano:
        return "cru|" + re.sub(r"\s+", " ", bruto.translate(_ACENTOS).lower().strip())

    return f"{tipo}|{orgao}|{numero}|{ano}"


# ---------------------------------------------------------------------------
# Passo 2 — limpeza de mobiliário de impressão
# ---------------------------------------------------------------------------

_ZONA = 3          # quantas linhas de cada ponta da página são candidatas
_MIN_PAGINAS = 3   # abaixo disso "repetido" não significa nada
_FRACAO = 0.6      # em que fração das páginas a linha precisa reaparecer
_MAX_CHARS = 200   # cabeçalho/rodapé é curto; parágrafo longo nunca é moldura


def _assinatura(linha: str) -> str:
    """Reduz a linha ao que ela tem de estável entre páginas.

    Cada CORRIDA de dígitos vira um único '#': é o que faz '1/13' e '10/13'
    (mesmo rodapé, páginas diferentes) colapsarem na mesma assinatura. Trocar
    dígito a dígito não colapsaria, e o rodapé escaparia da detecção.
    """
    return re.sub(r"\d+", "#", linha.lower()).strip()


def limpar_moldura(paginas: list[str]) -> tuple[list[str], list[str]]:
    """Remove linhas que se repetem nas pontas das páginas.

    Retorna (páginas limpas, amostras do que foi removido). A amostra volta para
    o relatório: limpeza que ninguém consegue conferir é limpeza em que ninguém
    consegue confiar.
    """
    if len(paginas) < _MIN_PAGINAS:
        return paginas, []

    contagem: Counter[str] = Counter()
    for texto in paginas:
        linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
        candidatas = linhas[:_ZONA] + linhas[-_ZONA:]
        # set(): a mesma linha duas vezes NA MESMA página conta uma só, senão
        # uma página com repetição interna sozinha atingiria o limiar.
        for ln in {c for c in candidatas if len(c) <= _MAX_CHARS}:
            contagem[_assinatura(ln)] += 1

    limiar = max(_MIN_PAGINAS, math.ceil(_FRACAO * len(paginas)))
    molduras = {a for a, n in contagem.items() if n >= limiar}
    if not molduras:
        return paginas, []

    limpas: list[str] = []
    amostras: list[str] = []
    for texto in paginas:
        linhas = [ln for ln in texto.splitlines()]
        vivos = [i for i, ln in enumerate(linhas) if ln.strip()]
        alvo = set(vivos[:_ZONA] + vivos[-_ZONA:])
        mantidas = []
        for i, ln in enumerate(linhas):
            if i in alvo and ln.strip() and _assinatura(ln.strip()) in molduras:
                if len(amostras) < 6:
                    amostras.append(ln.strip())
                continue
            mantidas.append(ln)
        limpas.append("\n".join(mantidas))
    return limpas, amostras


def _cortar_rodape_de_site(texto: str, ancora: str) -> tuple[str, str | None]:
    """Corta o menu/rodapé que aparece UMA vez, no fim — a repetição não o pega.

    Se a âncora não bater, ou bater cedo demais para ser rodapé, o texto passa
    inteiro com um aviso. Perder o corte é ruim; decapitar a norma é pior.
    """
    pos = texto.rfind(ancora)
    if pos < 0:
        return texto, f"âncora de corte não encontrada: {ancora.splitlines()[0]!r}"
    if pos < len(texto) * 0.6:
        return texto, (
            f"âncora {ancora.splitlines()[0]!r} apareceu a {pos / len(texto):.0%} do "
            "documento — cedo demais para ser rodapé; nada foi cortado"
        )
    return texto[:pos].rstrip(), None


def extrair_texto(pdf: Path, entrada: dict) -> tuple[str, dict]:
    """PDF → texto pronto para chunking. Retorna (texto, diagnóstico)."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    paginas = [(p.extract_text() or "") for p in reader.pages]
    diag: dict = {"paginas": len(paginas), "chars_brutos": sum(len(p) for p in paginas)}

    if entrada.get("moldura"):
        paginas, amostras = limpar_moldura(paginas)
        diag["moldura_removida"] = amostras
        diag["linhas_moldura"] = len(amostras)

    texto = sanitize_text("\n\n".join(p for p in paginas if p.strip()))

    ancora = entrada.get("corte_fim")
    if ancora:
        texto, aviso = _cortar_rodape_de_site(texto, ancora)
        if aviso:
            diag["aviso_corte"] = aviso
            logger.warning("%s: %s", entrada["identifier"], aviso)

    diag["chars"] = len(texto)
    diag["tokens"] = estimate_tokens(texto)
    return texto, diag


# ---------------------------------------------------------------------------
# Passo 0 — inventário
# ---------------------------------------------------------------------------

def _sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def inventariar(pasta: Path) -> list[dict]:
    """Passo 0 — para cada norma: NOVA ou JÁ EXISTE. Não escreve nada."""
    from app.db.session import SessionLocal
    from app.models.legislation import LegislationDocument

    db = SessionLocal()
    try:
        existentes = db.query(LegislationDocument).all()
        por_chave: dict[str, list] = {}
        for doc in existentes:
            por_chave.setdefault(normalizar_identificador(doc.identifier), []).append(doc)
        hashes_no_banco = {d.content_hash: d for d in existentes if d.content_hash}

        linhas: list[dict] = []
        for entrada in CURADORIA:
            caminho = pasta / entrada["arquivo"]
            item: dict = {
                "arquivo": entrada["arquivo"],
                "identifier": entrada["identifier"],
                "chave": normalizar_identificador(entrada["identifier"]),
            }
            if not caminho.exists():
                item["situacao"] = "ARQUIVO AUSENTE"
                linhas.append(item)
                continue

            sha = _sha256_arquivo(caminho)
            item["sha256"] = sha
            item["sha256_confere"] = sha == entrada["sha256"]

            colisoes = por_chave.get(item["chave"], [])
            por_hash = hashes_no_banco.get(sha)

            if colisoes:
                doc = colisoes[0]
                item["situacao"] = "JÁ EXISTE"
                item["db_id"] = doc.id
                item["db_identifier"] = doc.identifier
                item["db_status"] = doc.status
                # `content_hash` do corpus antigo é hash do TEXTO extraído, não
                # do arquivo. Só dá para afirmar "hash igual" quando o registro
                # antigo também guardou hash de arquivo — senão é incomparável.
                if doc.content_hash == sha:
                    item["hash"] = "igual"
                elif por_hash is not None:
                    item["hash"] = f"arquivo já ingerido em outro registro (id={por_hash.id})"
                else:
                    item["hash"] = "diferente/incomparável (registro antigo guarda hash do texto)"
            elif por_hash is not None:
                item["situacao"] = "JÁ EXISTE (por hash de arquivo)"
                item["db_id"] = por_hash.id
                item["db_identifier"] = por_hash.identifier
                item["hash"] = "igual"
            else:
                item["situacao"] = "NOVA"
            linhas.append(item)
        return linhas
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Passo 3 — ingestão
# ---------------------------------------------------------------------------

def _data(valor: str | None) -> date | None:
    if not valor:
        return None
    ano, mes, dia = (int(p) for p in valor.split("-"))
    return date(ano, mes, dia)


def processar(
    entrada: dict,
    pasta: Path,
    preview_dir: Path,
    *,
    dry_run: bool,
    ja_existe: dict[str, dict],
) -> dict:
    info: dict = {"arquivo": entrada["arquivo"], "identifier": entrada["identifier"]}

    situacao = ja_existe.get(entrada["identifier"])
    if situacao and situacao["situacao"].startswith("JÁ EXISTE"):
        info["acao"] = "pulado_ja_existe"
        info["db_id"] = situacao.get("db_id")
        info["db_identifier"] = situacao.get("db_identifier")
        info["hash"] = situacao.get("hash")
        return info

    caminho = pasta / entrada["arquivo"]
    if not caminho.exists():
        info["acao"] = "falhou_arquivo_ausente"
        return info

    sha = _sha256_arquivo(caminho)
    if sha != entrada["sha256"]:
        info["acao"] = "falhou_hash"
        info["erro"] = f"SHA-256 do arquivo diverge do manifesto: {sha}"
        return info
    info["sha256"] = sha

    texto, diag = extrair_texto(caminho, entrada)
    info.update(diag)

    if len(texto) < 500:
        info["acao"] = "falhou_texto_curto"
        return info

    sujeira = verificar_mojibake(texto)
    if sujeira > 0.0005:
        info["acao"] = "falhou_encoding"
        info["erro"] = f"{sujeira:.2%} do texto é U+FFFD — charset mal detectado"
        return info

    info["preview"] = str(save_preview(entrada["identifier"], texto, preview_dir))

    from app.services.chunking import chunk_text

    pedacos = chunk_text(texto)
    info["chunks_previstos"] = len(pedacos)
    info["chunk_tokens"] = sum(c.tokens for c in pedacos)
    info["custo_usd"] = info["chunk_tokens"] / 1_000_000 * USD_POR_MILHAO_DE_TOKENS

    if dry_run:
        info["acao"] = "dry_run"
        info["amostras"] = [c.text[:400] for c in pedacos[:2]]
        return info

    from app.db.session import SessionLocal
    from app.models.legislation import LegislationDocument
    from app.services.knowledge_catalog import index_legislation_document

    db = SessionLocal()
    try:
        doc = LegislationDocument(
            title=entrada["title"],
            identifier=entrada["identifier"],
            scope="federal",
            source_type=entrada["source_type"],
            agency=entrada["agency"],
            uf=None,
            municipality=None,
            effective_date=datetime.strptime(entrada["published_at"], "%Y-%m-%d").replace(tzinfo=UTC),
            url=None,
            file_path=str(caminho),
            full_text=texto,
            token_count=info["tokens"],
            # Hash do PDF ORIGINAL, por determinação do despacho — e não do texto
            # extraído, como faz o resto do corpus. É o que torna o dedupe do
            # Passo 0 possível numa próxima entrega do mesmo pacote: o texto muda
            # com a versão do pypdf, o arquivo não. O hash do texto não se perde:
            # vai em `extra_metadata.texto_sha256`.
            content_hash=sha,
            status="indexed",
            demand_types=entrada["demand_types"],
            vigencia_inicio=_data(entrada["published_at"]),
            vigencia_fim=None,
            fonte_origem=entrada["fonte_origem"],
            fonte_oficial=entrada["fonte_oficial"],
            fonte_conferida_em=None,  # ninguém conferiu à mão; não fingir que sim
            extra_metadata={
                "ementa": entrada["ementa"],
                "pacote": "NORMATIVAS (Isis, 2026-08-04)",
                "arquivo_nome": entrada["arquivo"],
                "arquivo_sha256": sha,
                "texto_sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
                "moldura_removida": bool(entrada.get("moldura")),
                "nota_curadoria": entrada.get("nota"),
            },
        )
        db.add(doc)
        db.flush()
        info["db_id"] = doc.id
        info["chunks"] = index_legislation_document(db, doc.id)
        db.commit()
        info["acao"] = "inserido"
        return info
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pasta", type=Path, default=PASTA_PADRAO)
    p.add_argument("--preview-dir", type=Path, default=Path("ops/legislation_preview"))
    p.add_argument("--inventario", action="store_true", help="Passo 0 — só o relatório de dedupe")
    p.add_argument("--dry-run", action="store_true", help="chunking real, nada gravado, nenhuma API")
    p.add_argument("--only", help="substring do arquivo ou do identificador")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.pasta.exists():
        logger.error("Pasta não encontrada: %s (extraia NORMATIVAS.rar ali)", args.pasta)
        return 1

    linhas = inventariar(args.pasta)

    print("\n=== PASSO 0 — INVENTÁRIO / DEDUPE ===")
    print(f"{'arquivo':<32} {'identificador':<26} {'situação':<32} detalhe")
    for it in linhas:
        detalhe = ""
        if it.get("db_id"):
            detalhe = f"id={it['db_id']} ({it.get('db_identifier')}) hash={it.get('hash')}"
        if it.get("sha256_confere") is False:
            detalhe = "SHA-256 DIVERGE DO MANIFESTO — " + detalhe
        print(f"{it['arquivo'][:31]:<32} {it['identifier']:<26} {it['situacao']:<32} {detalhe}")

    novas = [it for it in linhas if it["situacao"] == "NOVA"]
    print(f"\n  NOVA: {len(novas)} · JÁ EXISTE: {len(linhas) - len(novas)} · total: {len(linhas)}")

    if args.inventario:
        return 0

    if any(it.get("sha256_confere") is False for it in linhas):
        logger.error("Há arquivo com SHA-256 divergente do manifesto. Abortado.")
        return 3

    por_identifier = {it["identifier"]: it for it in linhas}

    entradas = CURADORIA
    if args.only:
        alvo = args.only.lower()
        entradas = [
            e for e in CURADORIA
            if alvo in e["arquivo"].lower() or alvo in e["identifier"].lower()
        ]
        if not entradas:
            logger.error("Nenhuma entrada bate com --only=%s", args.only)
            return 2

    resultados = []
    for entrada in entradas:
        try:
            r = processar(
                entrada, args.pasta, args.preview_dir,
                dry_run=args.dry_run, ja_existe=por_identifier,
            )
        except Exception as exc:
            logger.exception("Falha ao processar %s", entrada["arquivo"])
            r = {
                "arquivo": entrada["arquivo"], "identifier": entrada["identifier"],
                "acao": "falhou_excecao", "erro": str(exc),
            }
        resultados.append(r)
        logger.info(
            "→ %s | acao=%s db_id=%s chunks=%s",
            r["identifier"], r.get("acao"), r.get("db_id"),
            r.get("chunks", r.get("chunks_previstos")),
        )

    print(f"\n=== PASSO 3 — {'DRY-RUN' if args.dry_run else 'INGESTÃO'} ===")
    print(f"{'identificador':<26} {'ação':<20} {'id':>5} {'chunks':>7} {'tokens':>9} {'US$':>9}")
    total_chunks = total_tokens = 0
    total_custo = 0.0
    for r in resultados:
        chunks = r.get("chunks", r.get("chunks_previstos")) or 0
        total_chunks += chunks
        total_tokens += r.get("chunk_tokens") or 0
        total_custo += r.get("custo_usd") or 0.0
        print(
            f"{r['identifier']:<26} {str(r.get('acao')):<20} {str(r.get('db_id') or '-'):>5} "
            f"{chunks:>7} {(r.get('chunk_tokens') or 0):>9,} {(r.get('custo_usd') or 0):>9.4f}"
        )
        if r.get("erro"):
            print(f"    ERRO: {r['erro']}")
        if r.get("aviso_corte"):
            print(f"    AVISO: {r['aviso_corte']}")
        if r.get("linhas_moldura"):
            print(f"    moldura removida ({r['linhas_moldura']} amostras): "
                  f"{r['moldura_removida'][0][:90]!r}")

    print(f"\n  chunks: {total_chunks:,} | tokens embedados: {total_tokens:,} "
          f"| custo: US$ {total_custo:.4f}")
    if total_custo > TETO_CUSTO_USD:
        logger.error(
            "Custo US$ %.4f acima do teto de US$ %.2f — sinal de erro, conferir antes de repetir.",
            total_custo, TETO_CUSTO_USD,
        )
        return 4

    falhas = [r for r in resultados if str(r.get("acao", "")).startswith("falhou")]
    return 5 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
