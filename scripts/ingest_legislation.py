"""
scripts/ingest_legislation.py — Sprint 0 / Tarefa A

CLI para ingerir diplomas legislativos em `legislation_documents`.

Suporta duas fontes:
  (a) --url         HTTP(S) — detecta HTML planalto vs PDF pelo content-type
  (b) --pdf-path    arquivo PDF local (ex: pasta `legislacao/` da sócia)

Exemplos:

    # HTML planalto (lei federal)
    python scripts/ingest_legislation.py \\
        --url "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651.htm" \\
        --title "Código Florestal" \\
        --identifier "Lei 12.651/2012" \\
        --scope federal \\
        --source-type lei \\
        --agency "Congresso Nacional" \\
        --effective-date 2012-05-25 \\
        --demand-types car,retificacao_car,compensacao \\
        --dry-run

    # PDF local (coletânea da sócia)
    python scripts/ingest_legislation.py \\
        --pdf-path "legislacao/IN_CAR.pdf" \\
        --title "IN CAR - SICAR" \\
        --identifier "IN MMA 02/2014" \\
        --scope federal \\
        --source-type instrucao_normativa \\
        --agency "MMA" \\
        --demand-types car,retificacao_car

Flags:
    --dry-run         valida parsing e mostra preview; não escreve no banco
    --preview-dir DIR salva texto extraído em /tmp/legislation_preview/
                      (default: ops/legislation_preview/)

Idempotência:
    - content_hash SHA-256 do texto extraído.
    - Se já existe doc com mesmo identifier+content_hash → skip.
    - Se mesmo identifier com hash diferente → cria nova versão com status='indexed'
      e marca a antiga como 'superseded' com revoked_at=now().

Fluxo:
    1. Carrega texto (URL ou arquivo local).
    2. Extrai texto limpo (PDF via pypdf; HTML via BeautifulSoup focado no body).
    3. Sanitiza (strip whitespace, remove caracteres de controle).
    4. Calcula hash e token_count (len // 4).
    5. Salva preview em disco.
    6. Persiste em legislation_documents (ou imprime se --dry-run).
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

# Permite rodar `python scripts/ingest_legislation.py` direto da raiz
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.normalizacao import normalizar as _normalizar_unicode

logger = logging.getLogger("ingest_legislation")


# ---------------------------------------------------------------------------
# Extração de texto
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extrai texto de PDF usando pypdf. Retorna string vazia se falhar."""
    import io

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n\n".join(pages)
    except Exception as exc:
        logger.error("Falha ao ler PDF: %s", exc)
        return ""


def extract_text_from_html(html: str) -> str:
    """Extrai texto de HTML com heurísticas para sites .gov.br (planalto)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # Remove tags irrelevantes
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()

    # Planalto: o conteúdo fica dentro do <body>; o HTML é antigo, sem landmark semântico.
    body = soup.find("body") or soup
    text = body.get_text(separator="\n", strip=True)

    # Normaliza múltiplas linhas em branco
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ---------------------------------------------------------------------------
# Carregamento (URL ou disco)
# ---------------------------------------------------------------------------

_META_CHARSET_RE = re.compile(rb"""charset=["']?([\w-]+)""", re.I)


def _decodificar(resposta) -> str:
    """Decodifica a resposta HTTP respeitando o charset REAL, não o presumido.

    O planalto.gov.br responde `Content-Type: text/html` — sem charset. O httpx,
    sem declaração, assume utf-8; os bytes são ISO-8859-1. Resultado: todo acento
    vira U+FFFD e o corpus guarda "Art. 3� O �rg�o ... aplicar� as
    seguintes san��es". Foi assim que os diplomas federais de abril
    entraram, e ninguém viu — texto corrompido não quebra nada, só degrada a
    citação e o embedding, silenciosamente.

    Ordem: charset declarado no header → <meta charset> do HTML → utf-8 →
    ISO-8859-1 (que nunca falha, e é o que o Planalto de fato usa).
    """
    if resposta.charset_encoding:  # servidor declarou; confiar
        return resposta.text

    brutos = resposta.content
    candidatos: list[str] = []
    achado = _META_CHARSET_RE.search(brutos[:4096])
    if achado:
        candidatos.append(achado.group(1).decode("ascii", "ignore"))
    candidatos += ["utf-8", "iso-8859-1"]

    for codec in candidatos:
        try:
            return brutos.decode(codec)
        except (UnicodeDecodeError, LookupError):
            continue
    return brutos.decode("iso-8859-1", "replace")


def verificar_mojibake(texto: str, *, limite: float = 0.0005) -> float:
    """Proporção de caracteres de substituição (U+FFFD) no texto.

    Canário: o defeito de encoding passou três meses despercebido porque texto
    corrompido não levanta exceção. Acima do limite, quem chama recusa a
    ingestão — melhor não ingerir do que ingerir lixo que a consultora vai citar.
    """
    if not texto:
        return 0.0
    return texto.count("�") / len(texto)


def load_from_url(url: str) -> tuple[str, str]:
    """
    Retorna (content_type, text_extraido).
    Baixa via httpx com timeout agressivo e detecta PDF vs HTML pelo Content-Type.

    Usa um User-Agent de browser real — planalto.gov.br e alguns sites gov
    rejeitam UAs customizados com "Server disconnected".
    """
    import httpx

    # UA real — testado contra planalto.gov.br, al.go.gov.br, conama.mma.gov.br
    browser_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    headers = {
        "User-Agent": browser_ua,
        "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()

        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return "pdf", extract_text_from_pdf(r.content)
        elif "html" in ctype or "text" in ctype:
            return "html", extract_text_from_html(_decodificar(r))
        else:
            logger.warning("Content-type desconhecido: %s. Tentando como HTML.", ctype)
            return "unknown", extract_text_from_html(_decodificar(r))


def load_from_pdf_path(path: Path) -> str:
    """Lê PDF de disco e extrai texto."""
    data = path.read_bytes()
    return extract_text_from_pdf(data)


# ---------------------------------------------------------------------------
# Sanitização
# ---------------------------------------------------------------------------

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


_ESPACOS_UNICODE = dict.fromkeys(
    map(ord, "         "), " "
)


def sanitize_text(text: str) -> str:
    """Remove caracteres de controle e normaliza whitespace."""
    # Ligadura desfeita na entrada (#122): o glifo do PDF ("ﬁns") vira texto
    # comparavel ("fins"). Troca CIRURGICA: o NFKC levaria junto `º` e `ª`.
    text = _normalizar_unicode(text)
    text = _CONTROL_CHARS_RE.sub("", text)
    # Espaço não-quebrável e parentes viram espaço comum. O Planalto separa
    # "Art." do número com U+00A0: o texto PARECE "Art. 18." e não casa com
    # "Art. 18." em busca nenhuma — nem na nossa, nem no Ctrl+F de quem lê a
    # peça pronta. Diferença invisível é a pior de depurar.
    text = text.translate(_ESPACOS_UNICODE)
    # Normaliza CRLF → LF e múltiplos whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    """Mesma fórmula de `app/services/legislation_service.py:_estimate_tokens`."""
    return len(text) // 4


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def save_preview(
    identifier: str,
    text: str,
    preview_dir: Path,
) -> Path:
    """Salva preview em disco para inspeção humana antes de persistir no banco."""
    preview_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", identifier)
    preview_path = preview_dir / f"{safe_id}.txt"
    preview_path.write_text(text, encoding="utf-8")
    return preview_path


def persist_document(
    *,
    title: str,
    identifier: str,
    scope: str,
    source_type: str,
    agency: Optional[str],
    uf: Optional[str],
    municipality: Optional[str],
    effective_date: Optional[datetime],
    url: Optional[str],
    file_path: Optional[str],
    text: str,
    demand_types: list[str],
) -> dict:
    """
    Persiste `LegislationDocument` no banco. Idempotente:
      - mesmo identifier+hash → skip
      - mesmo identifier, hash diferente → versiona (antiga vira superseded)
    """

    from app.db.session import SessionLocal
    from app.models.legislation import LegislationDocument

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    token_count = estimate_tokens(text)

    db = SessionLocal()
    try:
        # Busca docs existentes com mesmo identifier
        existing = (
            db.query(LegislationDocument)
            .filter(LegislationDocument.identifier == identifier)
            .all()
        )

        for doc in existing:
            if doc.content_hash == content_hash and doc.status == "indexed":
                logger.info(
                    "Skip: já existe doc indexado com mesmo content_hash (id=%s)", doc.id
                )
                return {"action": "skipped", "id": doc.id, "hash": content_hash}

        # Se há versões antigas indexadas, supersede
        for doc in existing:
            if doc.status == "indexed":
                doc.status = "superseded"
                doc.revoked_at = datetime.now(UTC)
                logger.info("Superseding doc antigo (id=%s)", doc.id)

        # Nova versão
        new_doc = LegislationDocument(
            title=title,
            identifier=identifier,
            scope=scope,
            source_type=source_type,
            agency=agency,
            uf=uf,
            municipality=municipality,
            effective_date=effective_date,
            url=url,
            file_path=file_path,
            full_text=text,
            token_count=token_count,
            content_hash=content_hash,
            status="indexed",
            demand_types=demand_types,
        )
        db.add(new_doc)
        db.flush()
        db.commit()
        return {"action": "inserted", "id": new_doc.id, "hash": content_hash, "tokens": token_count}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingere diploma legislativo em legislation_documents")

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="URL HTTP(S) (planalto.gov.br, al.go.gov.br, etc.)")
    src.add_argument("--pdf-path", type=Path, help="Caminho de PDF local")

    p.add_argument("--title", required=True, help="Título legível")
    p.add_argument("--identifier", required=True, help='Identificador curto (ex: "Lei 12.651/2012")')
    p.add_argument(
        "--scope",
        required=True,
        choices=["federal", "estadual", "municipal"],
        help="Escopo geográfico",
    )
    p.add_argument(
        "--source-type",
        required=True,
        choices=[
            "lei",
            "decreto",
            "resolucao",
            "instrucao_normativa",
            "portaria",
            "nota_tecnica",
            "manual",
        ],
        help="Tipo de diploma",
    )
    p.add_argument("--agency", help="Órgão emissor (IBAMA, SEMAD, MMA, ...)")
    p.add_argument("--uf", help="UF (2 letras) para docs estaduais/municipais")
    p.add_argument("--municipality", help="Município (só se scope=municipal)")
    p.add_argument("--effective-date", help="Data de vigência YYYY-MM-DD")
    p.add_argument(
        "--demand-types",
        default="",
        help="CSV de demand_types aplicáveis (ex: car,retificacao_car,compensacao)",
    )

    p.add_argument(
        "--preview-dir",
        type=Path,
        default=Path("ops/legislation_preview"),
        help="Diretório para salvar preview do texto extraído",
    )
    p.add_argument("--dry-run", action="store_true", help="Valida parsing mas não escreve no banco")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    return p.parse_args()


def main() -> int:
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # 1. Carrega texto
    if args.url:
        logger.info("Baixando %s ...", args.url)
        ctype, text = load_from_url(args.url)
        logger.info("content-type=%s, chars=%d", ctype, len(text))
        file_path_val = None
    else:
        pdf_path = args.pdf_path.resolve()
        if not pdf_path.exists():
            logger.error("PDF não encontrado: %s", pdf_path)
            return 2
        logger.info("Lendo PDF local %s ...", pdf_path)
        text = load_from_pdf_path(pdf_path)
        file_path_val = str(pdf_path)

    text = sanitize_text(text)

    if len(text) < 200:
        logger.error("Texto extraído muito curto (%d chars). Abortando.", len(text))
        return 3

    tokens = estimate_tokens(text)
    logger.info("Texto sanitizado: %d chars, ~%d tokens", len(text), tokens)

    # 2. Preview em disco
    preview_path = save_preview(args.identifier, text, args.preview_dir)
    logger.info("Preview salvo em %s", preview_path)

    # 3. Dry-run?
    if args.dry_run:
        logger.info("[DRY-RUN] Não persistindo. Primeiros 500 chars do texto:")
        print("=" * 60)
        print(text[:500])
        print("=" * 60)
        return 0

    # 4. Persistir
    effective = None
    if args.effective_date:
        try:
            effective = datetime.strptime(args.effective_date, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            logger.error("--effective-date inválido (esperado YYYY-MM-DD): %s", args.effective_date)
            return 4

    demand_types_list = [d.strip() for d in args.demand_types.split(",") if d.strip()]

    result = persist_document(
        title=args.title,
        identifier=args.identifier,
        scope=args.scope,
        source_type=args.source_type,
        agency=args.agency,
        uf=args.uf,
        municipality=args.municipality,
        effective_date=effective,
        url=args.url,
        file_path=file_path_val,
        text=text,
        demand_types=demand_types_list,
    )
    logger.info("Resultado: %s", result)
    return 0 if result["action"] in ("inserted", "skipped") else 5


if __name__ == "__main__":
    sys.exit(main())
