# Trabalho — OCR: modelo Gemini descontinuado + timeout do fallback

> Arquivo único de trabalho (padrão novo). Contexto → causa raiz provada → o que
> mudou → validação → status. Branch: `fix/ocr-gemini-model` (base `main`).
> Data: 2026-06-02.

## Contexto (sintoma)

Depois do fix de storage R2 (PR #48), o PDF passou a ser **baixado** e o OCR
**roda** — mas o intake "fica rodando" e nunca extrai. Documento escaneado
(ex.: doc 114 em prod), `chars=0`, status `ocr_failed`.

Log do worker (Render, 2026-06-02):
```
ocr_pdf: pypdf retornou 0 chars (< 100), tentando Gemini
ocr_pdf.gemini falhou: ... 404 models/gemini-2.0-flash is no longer available
ocr_pdf: Gemini falhou (404 ...), tentando OpenAI Vision
ocr_pdf.openai_vision falhou: ... Timeout (após ~272s)
status=ocr_failed chars=0
```

## Causa raiz (PROVADA no log)

1. **Modelo Gemini descontinuado (a causa do `ocr_failed`).**
   `app/services/ocr_pdf.py:28` tinha `GEMINI_OCR_MODEL =
   "gemini/gemini-2.0-flash"` **hardcoded**. O Google descontinuou esse modelo
   → 404 `is no longer available`. O `config.py` já havia migrado o
   `GEMINI_LEGAL_MODEL` para `gemini-2.5-flash` (Sprint W, com o comentário
   "descontinuado") — o `ocr_pdf.py` ficou para trás.

2. **Fallback OpenAI pendura o worker ~4,5 min.** Com o Gemini 404, caía no
   `gpt-4o-mini` Vision. O `timeout=90s` já estava na chamada, mas o litellm
   **re-tenta por padrão** (`num_retries` default) → ~3 × 90s ≈ **272s** antes
   de desistir. O worker é `pool=solo`: uma task pendurada **bloqueia a fila**.

## O que mudou

| Arquivo | Mudança |
|---|---|
| `app/core/config.py` | `+ GEMINI_OCR_MODEL: str = "gemini/gemini-2.5-flash"` (env-configurável, alinhado ao `GEMINI_LEGAL_MODEL`). |
| `app/services/ocr_pdf.py` | Remove o hardcode `gemini-2.0-flash`; lê `settings.GEMINI_OCR_MODEL`. Gemini com `num_retries=0`. Fallback OpenAI Vision com `timeout=OPENAI_VISION_TIMEOUT_SECONDS` (75s) **explícito** + `num_retries=0` — capa o wall-time real. |
| `.env.example` | Documenta `GEMINI_OCR_MODEL=gemini/gemini-2.5-flash` com nota "troque AQUI no próximo deprecation". |

## Validação (rodando — obrigatória)

No container `worker` local, com chaves Gemini/OpenAI reais do `.env`.

1. **Settings carrega** — `settings.GEMINI_OCR_MODEL == "gemini/gemini-2.5-flash"`,
   `gemini_key_set=True`, `openai_key_set=True`.
2. **PDF escaneado de teste** — imagem-only (PIL → PDF, sem camada de texto);
   `extract_text_with_pypdf()` → **0 chars** (confirma que cai no Gemini).
3. **OCR real ponta a ponta** — `extract_text_from_pdf(data)`:
   ```
   method:   gemini
   chars:    146          (> 0 ✓)
   model:    gemini/gemini-2.5-flash   (modelo novo ✓)
   provider: gemini
   cost_usd: 0.0005678
   duration: 13788 ms
   error:    None         (sem 404 ✓)
   ```
   Texto extraído bate com o conteúdo do PDF (CAR / Fazenda Boa Vista / etc.).

Snippet para reconfirmar pós-deploy no Render Shell do worker (doc real):
```python
from app.db.session import SessionLocal
from app.models.document import Document
from app.workers.ocr_tasks import ocr_then_extract
db = SessionLocal(); doc = db.query(Document).order_by(Document.id.desc()).first(); db.close()
print(ocr_then_extract(doc_id=doc.id, tenant_id=1, user_id=1, force=True))
# esperado: status='ocr_ok', chars>0
```

## Status

✅ Causa raiz corrigida e provada rodando (Gemini 2.5-flash, chars>0, sem 404).
✅ Fallback OpenAI endurecido (timeout 75s + sem retries → não pendura minutos).
✅ Modelo env-configurável — próximo deprecation é troca de env, não de código.
