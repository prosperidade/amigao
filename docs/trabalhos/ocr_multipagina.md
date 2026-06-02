# Trabalho — OCR só lia 1 página de PDF multipágina

> Arquivo único de trabalho. Problema → causa medida → fix → validação → status.
> Branch: `fix/ocr-multipagina` (base `main`). Data: 2026-06-02.

## Problema (provado rodando, produção)

Doc 118 = `ESCRITURA_PUBLICA_COMPRA_VENDA_ROMILTON.pdf`, **6 páginas, 2,3 MB**,
escaneada. O `extracted_text` saiu com só **832 chars = apenas a página 1** (uma
certidão CNIB da capa). As páginas 2-6 (a escritura real: área 58,7654 ha,
matrícula 6253, CAR GO-5221577, CCIR, georreferenciamento) **não foram extraídas**.
O extrator de campos, sem texto, devolvia quase tudo `None` (só nome+CPF da capa).

## Causa (medida — sem assumir)

Reproduzi a falha localmente com o PDF real (cópia no container):

- `extract_text_from_pdf` (código antigo, **Gemini inline** = PDF inteiro num
  `image_url`): **832 chars, $0,0200, 35s** — idêntico a prod. O texto é 100% a
  certidão CNIB ("...Página 1 de 1... RESULTADO: NEGATIVO"). área/matrícula/CAR
  ausentes.
- O custo alto (~9x o de um RG de 1 página) prova que o Gemini **recebeu as 6
  páginas** — mas transcreveu só a 1ª. Ou seja: enviar o PDF inline faz o Gemini
  parar na primeira página em docs escaneados multipágina.
- Testei estratégias no doc real:
  | estratégia | chars | área/matríc./CAR |
  |---|---|---|
  | inline (antigo) | 832 | ✗ ✗ ✗ |
  | rasterizar + **1 imagem por página** | ~18-21k | ✓ ✓ ✓ |

  Rasterizar cada página e mandar **uma imagem por chamada** transcreve o
  documento inteiro.

## O que mudou

| Arquivo | Mudança |
|---|---|
| `app/services/ocr_pdf.py` | `extract_text_with_gemini` reescrito: rasteriza as páginas (`_rasterize_pdf_pages_to_jpegs`, já usado no fallback OpenAI) e faz **1 chamada Gemini por página**, concatenando. Página que falha (503 transitório) é pulada com log — não derruba o doc (texto parcial). `reasoning_effort="disable"` (OCR é transcrição, não precisa do "thinking" do 2.5 → ~2x mais rápido e mais barato). **Retry próprio** (3 tentativas, backoff) p/ 503 — litellm `num_retries` exige `tenacity` (ausente) e falhava. Inline antigo virou `_extract_text_with_gemini_inline`, fallback só quando a rasterização não está disponível. |
| `app/workers/ocr_tasks.py` | **`cache_twin` agora respeita `force=True`** (era o bug que mascarava reprocessamento: copiava o texto curto de um gêmeo em vez de re-OCR). `soft_time_limit` 180→300s (OCR multipágina é mais longo; folga sem travar o worker `pool=solo`). |

Constantes novas: `GEMINI_OCR_DPI=200`, `GEMINI_OCR_MAX_PAGES=15`,
`GEMINI_OCR_PAGE_TIMEOUT_SECONDS=75`, `GEMINI_OCR_PAGE_ATTEMPTS=3`,
`GEMINI_OCR_RETRY_BACKOFF_SECONDS=4`.

## Validação (rodando — doc real, código real)

`extract_text_from_pdf(<escritura_romilton.pdf>)` no worker local, chaves reais:

```
ANTES (inline):  chars=832    área✗  matrícula✗  CAR✗
DEPOIS (fix):    chars=21241  área✓  matrícula✓  CAR✓   (cost $0,062, 137s)
DEPOIS +nothink: chars=17437  área✓  matrícula✓  CAR✓   (cost $0,019, 88s)
```

```python
t = extract_text_from_pdf(open('escritura.pdf','rb').read(),'application/pdf').text
'58,7654' in t  # área      → True
'6253'    in t  # matrícula → True
'5221577' in t  # CAR       → True
```

> Nota: nas rodadas o Gemini estava em 503 "high demand" (eu havia disparado
> dezenas de chamadas na hora). O retry por página recuperou as páginas e os 3
> campos saíram mesmo quando 1 página caiu — degradação elegante.

### Reprocessar em produção (Render Shell do worker, pós-deploy)

doc 115 ficou `pending` e o doc 118 com texto truncado. Com o fix + `force=True`
(que agora ignora o cache twin) eles re-extraem de fato:

```python
from app.workers.ocr_tasks import ocr_then_extract
ocr_then_extract(doc_id=118, tenant_id=1, user_id=1, force=True)
ocr_then_extract(doc_id=115, tenant_id=1, user_id=1, force=True)
```

## Status

✅ OCR de PDF multipágina extrai todas as páginas (832 → ~18-21k chars no doc real).
✅ área/matrícula/CAR presentes (provado rodando no doc real).
✅ `cache_twin` respeita `force` — reprocessamento não é mascarado.
✅ Mais rápido e barato (thinking off) e resiliente a 503 (retry por página).
⏳ doc 115/118 em prod: destravam ao reprocessar com `force=True` pós-deploy (snippet acima).
