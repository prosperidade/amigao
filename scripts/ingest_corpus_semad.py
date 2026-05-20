"""scripts/ingest_corpus_semad.py — Ingestao do corpus SEMAD-GO no knowledge_catalog.

Sessao 2 do plano (2026-05-20). Pipeline:
    1. Walk pastas "Licenciamento (SEMAD)" e "Manuais (SEMAD)"
    2. Pra cada PDF:
       a. Extrai 2 primeiras paginas via pypdf
       b. Classifica via Gemini Flash (4 tipos A/B/C/D + metadados estruturados)
       c. Extrai texto completo
       d. Persiste via app.services.knowledge_catalog.index_text (chunk+embed+upsert)
    3. Log de erros + sumario final

Idempotencia:
    index_text ja faz dedup por content_hash no knowledge_catalog. Re-rodar
    o script eh seguro: chunks ja indexados sao ignorados (skip silencioso).

Uso:
    # Smoke: classifica + ingere 4 PDFs de referencia (1 por tipo)
    python scripts/ingest_corpus_semad.py --smoke

    # Dry-run completo: classifica todos mas nao persiste
    python scripts/ingest_corpus_semad.py --root "C:/Users/.../Amigao..." --dry-run

    # Ingestao real
    python scripts/ingest_corpus_semad.py --root "C:/Users/.../Amigao..."

    # Limit (debugging / parcial)
    python scripts/ingest_corpus_semad.py --root "..." --limit 10
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Bootstrap sys.path pra importar app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import litellm  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.knowledge_catalog import index_text  # noqa: E402

logger = logging.getLogger("ingest_corpus_semad")

# Modelo barato pra classificacao + extracao de metadata.
CLASSIFY_MODEL = "gemini/gemini-2.5-flash"
CLASSIFY_TIMEOUT_S = 60.0
CLASSIFY_MAX_RETRIES = 2

# Limite de chars do excerpt mandado pro LLM (controla custo + latencia).
EXCERPT_MAX_CHARS = 6000

# 4 PDFs de referencia pro smoke (1 por tipo).
SMOKE_REFERENCES = {
    "matriz_ipe": "Licenciamento (SEMAD)/89 - REGISTRO CORTE DE ÁRVORES ISOLADAS POR HECTARE EM ÁREA RURAL CONSOLIDADA.pdf",
    "norma_procedural": "Manuais (SEMAD)/Compensação Florestal e Compensação Por Danos Ambientais.pdf",
    "gabarito_laudo": "Manuais (SEMAD)/LAUDO DE ESTANQUEIDADE DO SISTEMA DE ARMAZENAMENTO AÉREO DE COMBUSTÍVEIS - SAAC .pdf",
    "manual_ipe": "Manuais (SEMAD)/Manual AUMPF.pdf",
}

CLASSIFY_PROMPT = """Voce esta classificando um PDF do corpus SEMAD-GO (Goias).

Escolha UM tipo da taxonomia:

- "matriz_ipe" -> Fluxograma decisorio IPE. Perguntas numeradas (1, 2, 3...) com
  ramos SIM/NAO, acoes declaradas (Incluir Declaracao, Incluir condicionante,
  Incluir geometria, Incluir Vedacao, Mensagem de impedimento, Encaminhar para
  analise). Sinais: "Identificacao: <codigo> - <NOME>", "Tipo de questionario",
  codigos LAE/REG/LAC/LAU/LC/LP/REG_I/LAO.

- "norma_procedural" -> Texto procedural denso, sem fluxograma. Regras condicionais,
  proporcoes, prazos, modalidades. Marcadores de topicos, tabelas de regras,
  referencias a leis/artigos. SEM perguntas numeradas SIM/NAO.

- "gabarito_laudo" -> Estrutura de UM tipo especifico de laudo. Titulos como
  "Apresentacao", "Objetivos", "Definicoes", "Roteiro de Inspecao", "Criterio
  de Aceitacao", "Normas de Referencia" (NBR, ASME, API).

- "manual_ipe" -> Passo-a-passo no sistema IPE. Capturas de tela, instrucoes
  "Clique em X", "Acesse menu Y", referencias a "Portal IPE", "Portal Ambiental".

- "indefinido" -> nao bate em nenhum dos 4 com confianca razoavel.

INPUT:
Filename: {filename}

Texto das 2 primeiras paginas:
---
{text}
---

OUTPUT: JSON strict (sem ```markdown```, sem comentarios). Schema:

{{
  "tipo": "matriz_ipe" | "norma_procedural" | "gabarito_laudo" | "manual_ipe" | "indefinido",
  "titulo": "<titulo canonico extraido do documento>",
  "vigencia": "AAAA-MM-DD" | null,
  "licenca_codigo": "<ex: 89, 7841, A1.1.1>" | null,
  "licenca_nome": "<ex: Registro Corte de Arvores Isoladas>" | null,
  "tipo_questionario": "Requerimento" | "Viabilidade locacional" | "Questionario" | "Triagem" | null,
  "tipo_licenciamento": "LAE" | "REG" | "LAC" | "LAU" | "LAO" | "LC" | "LP" | "REG_I" | null,
  "tipos_licenca_aplicaveis": ["LAE","REG",...] | null,
  "tema": "<slug em snake_case ex: compensacao_florestal>" | null,
  "leis_referenciadas": ["Lei 12.651/2012","Decreto 7.830/2012",...] | null,
  "tipo_laudo": "<slug ex: estanqueidade_saac>" | null,
  "normas_tecnicas": ["NBR 17505-1","ASME B31.3",...] | null,
  "procedimento": "<slug ex: alteracao_empreendedor>" | null,
  "agente_consumidor": "Atendimento" | "Diagnostico" | "Redator" | "Acompanhamento" | null,
  "confidence": 0.0..1.0
}}

Campos nao aplicaveis ao tipo: null.
Slug snake_case sem acentos.
"""


@dataclass
class IngestResult:
    pdf: str
    tipo: str
    chars_extracted: int
    chunks_inserted: int
    skipped: bool = False
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def setup_llm_env() -> None:
    """LiteLLM le env vars. Sincroniza com settings caso o venv host nao injete."""
    if settings.GEMINI_API_KEY and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
    if settings.OPENAI_API_KEY and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY


def _win_long_path(p: Path) -> str:
    """Workaround Windows MAX_PATH (260 chars). Prefixa '\\\\?\\' em paths absolutos."""
    raw = str(p)
    if sys.platform == "win32" and p.is_absolute() and not raw.startswith("\\\\?\\"):
        return "\\\\?\\" + raw
    return raw


def extract_pdf_pages(pdf_path: Path, max_pages: int | None = None) -> str:
    """Extrai texto do PDF via pypdf. Se max_pages, para depois de N paginas.

    Tenta pypdf primeiro; se vazio (PDF escaneado), cai pra pypdfium2 (rasteriza
    nao ajuda, mas extrai melhor em alguns casos). Em windows, prefixa long path
    pra contornar MAX_PATH.
    """
    raw_path = _win_long_path(pdf_path)
    try:
        reader = PdfReader(raw_path)
        pages = []
        for i, page in enumerate(reader.pages):
            if max_pages is not None and i >= max_pages:
                break
            try:
                t = page.extract_text() or ""
            except Exception as exc:
                logger.debug("page %d extract failed in %s: %s", i, pdf_path.name, exc)
                t = ""
            if t.strip():
                pages.append(t)
        text = "\n\n".join(pages).strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("pypdf falhou em %s: %s", pdf_path.name, exc)

    # Fallback pypdfium2 — melhor em alguns PDFs antigos / com encoding estranho.
    try:
        import pypdfium2 as pdfium  # type: ignore
        pdf = pdfium.PdfDocument(raw_path)
        try:
            pages = []
            for i, page in enumerate(pdf):
                if max_pages is not None and i >= max_pages:
                    break
                textpage = page.get_textpage()
                t = textpage.get_text_range() or ""
                if t.strip():
                    pages.append(t)
                textpage.close()
                page.close()
            return "\n\n".join(pages).strip()
        finally:
            pdf.close()
    except Exception as exc:
        logger.warning("pypdfium2 fallback falhou em %s: %s", pdf_path.name, exc)
        return ""


def _truncate_for_llm(text: str, max_chars: int = EXCERPT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[... truncado ...]\n\n" + text[-half:]


def classify_and_extract(text: str, filename: str) -> dict[str, Any]:
    """Chama LLM, retorna dict com tipo + metadados. Lanca em caso de falha."""
    excerpt = _truncate_for_llm(text)
    prompt = CLASSIFY_PROMPT.format(filename=filename, text=excerpt)

    last_exc: Exception | None = None
    for attempt in range(1, CLASSIFY_MAX_RETRIES + 2):
        try:
            resp = litellm.completion(
                model=CLASSIFY_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=CLASSIFY_TIMEOUT_S,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            # Defensivo: alguns providers vazam ```json ... ```
            raw = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.IGNORECASE)
            return json.loads(raw)
        except Exception as exc:
            last_exc = exc
            backoff = 2 ** attempt
            logger.warning(
                "classify attempt %d/%d failed: %s (sleep %ds)",
                attempt, CLASSIFY_MAX_RETRIES + 1, exc, backoff,
            )
            if attempt <= CLASSIFY_MAX_RETRIES:
                time.sleep(backoff)
    raise RuntimeError(f"classify falhou apos {CLASSIFY_MAX_RETRIES + 1} tentativas: {last_exc}")


def _slug(value: Any) -> str | None:
    """Normaliza valor pra slug snake_case. Aceita str ou list (LLM as vezes retorna lista)."""
    if not value:
        return None
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)
    if not isinstance(value, str):
        value = str(value)
    v = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return v or None


def build_extra_metadata(classification: dict[str, Any]) -> dict[str, Any]:
    """Achata classification em extra_metadata estruturado pro JSONB."""
    md: dict[str, Any] = {
        "doc_type": classification.get("tipo"),
        "confidence": classification.get("confidence"),
    }
    # Tipo A
    for k in ("licenca_codigo", "licenca_nome", "tipo_questionario", "tipo_licenciamento"):
        if classification.get(k):
            md[k] = classification[k]
    if classification.get("tipos_licenca_aplicaveis"):
        md["tipos_licenca_aplicaveis"] = classification["tipos_licenca_aplicaveis"]
    # Tipo B
    if classification.get("tema"):
        md["tema"] = _slug(classification["tema"])
    if classification.get("leis_referenciadas"):
        md["leis_referenciadas"] = classification["leis_referenciadas"]
    # Tipo C
    if classification.get("tipo_laudo"):
        md["tipo_laudo"] = _slug(classification["tipo_laudo"])
    if classification.get("normas_tecnicas"):
        md["normas_tecnicas"] = classification["normas_tecnicas"]
    # Tipo D
    if classification.get("procedimento"):
        md["procedimento"] = _slug(classification["procedimento"])
    if classification.get("agente_consumidor"):
        md["agente_consumidor"] = classification["agente_consumidor"]
    return md


def ingest_one(
    session,
    pdf_path: Path,
    *,
    dry_run: bool = False,
) -> IngestResult:
    name = pdf_path.name
    logger.info("processing %s", name)

    excerpt = extract_pdf_pages(pdf_path, max_pages=2)
    if not excerpt:
        return IngestResult(pdf=name, tipo="-", chars_extracted=0, chunks_inserted=0,
                            error="empty_excerpt")

    try:
        classification = classify_and_extract(excerpt, name)
    except Exception as exc:
        return IngestResult(pdf=name, tipo="-", chars_extracted=len(excerpt),
                            chunks_inserted=0, error=f"classify_failed: {exc}")

    tipo = classification.get("tipo", "indefinido")
    title = classification.get("titulo") or pdf_path.stem
    extra = build_extra_metadata(classification)

    full_text = extract_pdf_pages(pdf_path)  # texto completo
    if not full_text:
        return IngestResult(pdf=name, tipo=tipo, chars_extracted=0, chunks_inserted=0,
                            error="empty_full_text", metadata=classification)

    if dry_run:
        logger.info(
            "DRY-RUN %s | tipo=%s | chars=%d | title=%r | extra_md_keys=%s",
            name, tipo, len(full_text), title[:60], list(extra.keys()),
        )
        return IngestResult(pdf=name, tipo=tipo, chars_extracted=len(full_text),
                            chunks_inserted=0, skipped=True, metadata=classification)

    # source_type usa o tipo classificado (string livre, sem migration)
    source_type = tipo if tipo in {"matriz_ipe", "norma_procedural", "gabarito_laudo",
                                    "manual_ipe"} else "other"

    inserted = index_text(
        session,
        source_type=source_type,
        source_ref=name,
        body=full_text,
        title=title,
        tenant_id=None,             # global
        jurisdiction="estadual",
        uf="GO",
        agency="SEMAD-GO",
        identifier=classification.get("licenca_codigo"),
        effective_date=None,
        extra_metadata=extra,
    )
    session.commit()
    logger.info("  -> tipo=%s chunks_inserted=%d", tipo, inserted)
    return IngestResult(pdf=name, tipo=tipo, chars_extracted=len(full_text),
                        chunks_inserted=inserted, metadata=classification)


def walk_pdfs(root: Path) -> list[Path]:
    """Lista PDFs em 'Licenciamento (SEMAD)' e 'Manuais (SEMAD)'."""
    targets = ["Licenciamento (SEMAD)", "Manuais (SEMAD)"]
    found: list[Path] = []
    for sub in targets:
        d = root / sub
        if not d.is_dir():
            continue
        found.extend(sorted(d.glob("*.pdf")))
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path,
                    default=Path("C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente"))
    ap.add_argument("--smoke", action="store_true",
                    help="So ingere 4 PDFs de referencia (1 por tipo)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Classifica + extrai texto, mas nao persiste")
    ap.add_argument("--limit", type=int, default=None,
                    help="Para depois de N PDFs (debugging)")
    ap.add_argument("--from-file", type=Path, default=None,
                    help="Le lista de paths (relativos ao root) e processa so esses")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    setup_logging(args.verbose)
    setup_llm_env()

    if args.smoke:
        pdfs = [args.root / ref for ref in SMOKE_REFERENCES.values()]
        missing = [p for p in pdfs if not p.exists()]
        if missing:
            for p in missing:
                logger.error("smoke pdf missing: %s", p)
            sys.exit(2)
    elif args.from_file:
        lines = args.from_file.read_text(encoding="utf-8").splitlines()
        # Aceita "Licenciamento (SEMAD)/foo.pdf" ou "Manuais (SEMAD)\bar.pdf".
        pdfs = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Normaliza separador
            line = line.replace("\\", "/")
            pdfs.append(args.root / line)
    else:
        pdfs = walk_pdfs(args.root)
        if args.limit:
            pdfs = pdfs[: args.limit]

    if not pdfs:
        logger.error("nenhum PDF encontrado em %s", args.root)
        sys.exit(2)

    logger.info("ingestion start: %d PDFs (dry_run=%s)", len(pdfs), args.dry_run)
    start = time.time()

    session = SessionLocal()
    results: list[IngestResult] = []
    try:
        for i, pdf in enumerate(pdfs, 1):
            t0 = time.time()
            try:
                r = ingest_one(session, pdf, dry_run=args.dry_run)
            except Exception as exc:
                logger.exception("FATAL in %s", pdf.name)
                r = IngestResult(pdf=pdf.name, tipo="-", chars_extracted=0,
                                 chunks_inserted=0, error=f"unhandled: {exc}")
                session.rollback()
            results.append(r)
            logger.info("[%d/%d] done in %.1fs", i, len(pdfs), time.time() - t0)
    finally:
        session.close()

    # Sumario
    elapsed = time.time() - start
    print("\n=== SUMARIO ===")
    print(f"Total PDFs:      {len(results)}")
    print(f"Tempo total:     {elapsed:.1f}s ({elapsed/max(len(results),1):.1f}s/pdf)")
    print(f"Dry-run:         {args.dry_run}")
    by_tipo: dict[str, int] = {}
    chunks_total = 0
    errors: list[IngestResult] = []
    for r in results:
        by_tipo[r.tipo] = by_tipo.get(r.tipo, 0) + 1
        chunks_total += r.chunks_inserted
        if r.error:
            errors.append(r)
    print("Por tipo:")
    for k in sorted(by_tipo):
        print(f"  {k:<20} {by_tipo[k]}")
    print(f"Chunks inseridos: {chunks_total}")
    print(f"Erros:           {len(errors)}")
    for r in errors:
        print(f"  - {r.pdf}: {r.error}")

    # Dump JSON pra inspecao
    out = Path("/tmp/ingest_results.json")
    out.write_text(json.dumps(
        [{"pdf": r.pdf, "tipo": r.tipo, "chars": r.chars_extracted,
          "chunks": r.chunks_inserted, "error": r.error,
          "metadata": r.metadata} for r in results],
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultados detalhados: {out}")


if __name__ == "__main__":
    main()
