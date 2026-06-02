"""
ocr_pdf — Extração de texto de PDFs (Sprint V hardening, 2026-05-08).

Pipeline pré-extrator. Tenta `pypdf` primeiro (PDFs digitais, grátis) e cai
para Gemini Vision (PDFs escaneados, ~$0.0006 por documento de 8 páginas).

Não lê do MinIO nem persiste — orquestração e audit ficam em
`app/workers/ocr_tasks.py`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# PDFs com pelo menos PYPDF_MIN_CHARS de texto extraído pelo pypdf são tratados
# como digitais e não passam pelo Gemini (economia). PDFs escaneados costumam
# devolver 0-30 chars (pontuação solta de ruído OCR embutido).
PYPDF_MIN_CHARS = 100

# Modelo Gemini do OCR vem de settings.GEMINI_OCR_MODEL (env-configurável).
# Hardcode anterior ("gemini/gemini-2.0-flash") foi descontinuado pelo Google
# e derrubou o worker em prod com 404 — ver app/core/config.py:GEMINI_OCR_MODEL.
OPENAI_VISION_MODEL = "gpt-4o-mini"
MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB — proteção anti-DoS
OCR_TIMEOUT_SECONDS = 90  # Gemini (PDF inline, costuma ser rápido)
# Fallback OpenAI Vision: timeout mais curto e SEM retries do litellm. O worker
# é pool=solo — uma task pendurada bloqueia a fila inteira. Em prod o fallback
# pendurou ~272s (≈ 3 × 90s = timeout × num_retries default do litellm) antes de
# desistir. Capamos wall-time real com timeout explícito + num_retries=0.
OPENAI_VISION_TIMEOUT_SECONDS = 75
OPENAI_MAX_PAGES = 10  # rasteriza no máximo 10 páginas pra controlar custo
OPENAI_RASTER_DPI = 200  # 200 dpi balanço qualidade × tokens

OCR_PROMPT = """Extraia TODO o texto deste documento brasileiro (fundiário, ambiental, cadastral ou fiscal).

Preserve:
- Ordem natural de leitura (cabeçalho → corpo → rodapé)
- Estrutura visual (parágrafos, listas, tabelas)
- Números, datas, códigos e identificadores exatamente como aparecem no documento
- Acentuação portuguesa correta

Retorne APENAS o texto extraído, sem comentários, sem explicações, sem wrapper de markdown.
Se o documento estiver ilegível ou em branco, retorne uma string vazia.""".strip()


@dataclass
class OcrResult:
    text: str
    method: str  # "pypdf" | "gemini" | "none"
    chars: int
    cost_usd: float
    tokens_in: int
    tokens_out: int
    duration_ms: int
    model_used: str
    provider: str
    error: Optional[str] = None


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_text_with_pypdf(pdf_bytes: bytes) -> str:
    """Tenta extrair texto via pypdf. PDFs digitais devolvem texto rico;
    escaneados costumam devolver vazio ou ruído pontuado."""
    if not pdf_bytes:
        return ""
    try:
        from pypdf import PdfReader  # noqa: PLC0415
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append((page.extract_text() or "").strip())
            except Exception:
                continue
        return "\n\n".join(p for p in parts if p).strip()
    except Exception as exc:
        logger.warning("ocr_pdf.pypdf falhou: %s", exc)
        return ""


def extract_text_with_gemini(pdf_bytes: bytes, mime_type: str = "application/pdf") -> OcrResult:
    """Chama Gemini 2.0 Flash com o PDF inline. Devolve OcrResult com custo/tokens
    para que o caller persista em AIJob."""
    if not pdf_bytes:
        return OcrResult("", "none", 0, 0.0, 0, 0, 0, "", "", error="empty_bytes")

    from app.core.config import settings  # noqa: PLC0415

    if not settings.GEMINI_API_KEY:
        return OcrResult("", "none", 0, 0.0, 0, 0, 0, "", "", error="gemini_api_key_missing")

    model = settings.GEMINI_OCR_MODEL

    import litellm  # noqa: PLC0415

    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    t0 = time.monotonic()
    try:
        response = litellm.completion(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {"type": "image_url", "image_url": f"data:{mime_type};base64,{b64}"},
                    ],
                }
            ],
            api_key=settings.GEMINI_API_KEY,
            max_tokens=8000,
            temperature=0,
            timeout=OCR_TIMEOUT_SECONDS,
            num_retries=0,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = (response.choices[0].message.content or "").strip()
        usage = response.usage or {}
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        try:
            cost = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:
            cost = 0.0
        provider = model.split("/", 1)[0]
        return OcrResult(
            text=text,
            method="gemini",
            chars=len(text),
            cost_usd=cost,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=elapsed_ms,
            model_used=model,
            provider=provider,
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("ocr_pdf.gemini falhou: %s", exc)
        return OcrResult(
            text="",
            method="gemini",
            chars=0,
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
            duration_ms=elapsed_ms,
            model_used=model,
            provider="gemini",
            error=str(exc),
        )


def _rasterize_pdf_pages_to_jpegs(
    pdf_bytes: bytes,
    *,
    max_pages: int = OPENAI_MAX_PAGES,
    dpi: int = OPENAI_RASTER_DPI,
    jpeg_quality: int = 80,
) -> list[bytes]:
    """Rasteriza páginas do PDF em JPEGs via pypdfium2 (Apache 2.0).

    Limita a `max_pages` pra controlar custo de tokens/imagens. Retorna lista
    de bytes JPEG (uma por página). Vazia se rasterização falhar."""
    try:
        import pypdfium2 as pdfium  # noqa: PLC0415
    except ImportError as exc:
        logger.warning("ocr_pdf: pypdfium2 indisponível: %s", exc)
        return []

    images: list[bytes] = []
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        n_pages = min(len(pdf), max_pages)
        scale = dpi / 72.0  # pypdfium2 usa scale (1.0 = 72 dpi)
        for i in range(n_pages):
            page = pdf[i]
            pil_image = page.render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil_image.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
            images.append(buf.getvalue())
        return images
    except Exception as exc:
        logger.warning("ocr_pdf: rasterização falhou: %s", exc)
        return []


def extract_text_with_openai_vision(pdf_bytes: bytes) -> OcrResult:
    """Fallback final: rasteriza PDF e manda imagens pro gpt-4o-mini Vision.

    Usado quando pypdf não tira texto e Gemini falha (rate limit/erro). Custo
    ~$0.001-0.005 por PDF de até 10 páginas dependendo do modelo."""
    if not pdf_bytes:
        return OcrResult("", "none", 0, 0.0, 0, 0, 0, "", "", error="empty_bytes")

    from app.core.config import settings  # noqa: PLC0415

    if not settings.OPENAI_API_KEY:
        return OcrResult("", "none", 0, 0.0, 0, 0, 0, "", "", error="openai_api_key_missing")

    t0 = time.monotonic()
    images = _rasterize_pdf_pages_to_jpegs(pdf_bytes)
    if not images:
        return OcrResult(
            text="", method="openai_vision", chars=0,
            cost_usd=0.0, tokens_in=0, tokens_out=0,
            duration_ms=int((time.monotonic() - t0) * 1000),
            model_used=OPENAI_VISION_MODEL, provider="openai",
            error="rasterization_failed",
        )

    import litellm  # noqa: PLC0415

    content: list[dict] = [{"type": "text", "text": OCR_PROMPT}]
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
        })

    try:
        response = litellm.completion(
            model=OPENAI_VISION_MODEL,
            messages=[{"role": "user", "content": content}],
            api_key=settings.OPENAI_API_KEY,
            max_tokens=8000,
            temperature=0,
            timeout=OPENAI_VISION_TIMEOUT_SECONDS,
            num_retries=0,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = (response.choices[0].message.content or "").strip()
        usage = response.usage or {}
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        try:
            cost = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:
            cost = 0.0
        return OcrResult(
            text=text, method="openai_vision", chars=len(text),
            cost_usd=cost, tokens_in=tokens_in, tokens_out=tokens_out,
            duration_ms=elapsed_ms, model_used=OPENAI_VISION_MODEL, provider="openai",
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("ocr_pdf.openai_vision falhou: %s", exc)
        return OcrResult(
            text="", method="openai_vision", chars=0,
            cost_usd=0.0, tokens_in=0, tokens_out=0,
            duration_ms=elapsed_ms, model_used=OPENAI_VISION_MODEL, provider="openai",
            error=str(exc),
        )


def extract_text_from_pdf(pdf_bytes: bytes, mime_type: str = "application/pdf") -> OcrResult:
    """Orquestrador em cascata: pypdf → Gemini Vision → OpenAI Vision.

    pypdf é grátis e cobre PDFs digitais; Gemini cobre escaneados a custo baixo;
    OpenAI Vision rasteriza+vision como último recurso quando Gemini falha
    (rate limit, billing inativo, indisponibilidade)."""
    if not pdf_bytes:
        return OcrResult("", "none", 0, 0.0, 0, 0, 0, "", "", error="empty_bytes")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return OcrResult(
            "", "none", 0, 0.0, 0, 0, 0, "", "",
            error=f"oversized:{len(pdf_bytes)}>{MAX_PDF_BYTES}",
        )

    # 1) pypdf — grátis, rápido, funciona em PDFs digitais
    t0 = time.monotonic()
    text = extract_text_with_pypdf(pdf_bytes)
    pypdf_ms = int((time.monotonic() - t0) * 1000)
    if len(text) >= PYPDF_MIN_CHARS:
        return OcrResult(
            text=text, method="pypdf", chars=len(text),
            cost_usd=0.0, tokens_in=0, tokens_out=0,
            duration_ms=pypdf_ms, model_used="pypdf", provider="pypdf",
        )

    # 2) Gemini Vision — barato, suporta PDFs nativamente
    logger.info(
        "ocr_pdf: pypdf retornou %d chars (< %d), tentando Gemini",
        len(text), PYPDF_MIN_CHARS,
    )
    gemini_result = extract_text_with_gemini(pdf_bytes, mime_type)
    if gemini_result.text:
        return gemini_result

    # 3) OpenAI Vision — último recurso, rasteriza páginas e roda gpt-4o-mini
    logger.info(
        "ocr_pdf: Gemini falhou (%s), tentando OpenAI Vision",
        gemini_result.error or "empty_response",
    )
    openai_result = extract_text_with_openai_vision(pdf_bytes)
    if openai_result.text:
        return openai_result

    # Todos falharam — retorna o último com erro composto
    openai_result.error = (
        f"pypdf:{len(text)}chars; gemini:{gemini_result.error}; "
        f"openai:{openai_result.error}"
    )
    return openai_result
