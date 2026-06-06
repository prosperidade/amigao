# OCR failed — documentos reais (CCIR/ITR/recibo CAR) presos em failed

> PR `fix/ocr-failed-docs-reais` (base main). Origem: achado do PR #68 — no caso
> #11 (São Jorge), CCIR/ITR/recibo CAR estavam `ocr_status=failed`. Medido via
> Supabase MCP (read-only). 2026-06-06.

## PASSO 1 — Medição (causa raiz)

| fato medido | evidência |
|---|---|
| Falharam no **download do storage**, antes da cascata de OCR | `checksum_sha256 = NULL` em TODOS os failed (o checksum é computado após baixar os bytes); **nenhum AIJob** criado (o ramo de storage retorna antes de criar o AIJob de OCR) |
| São de **2026-05-31** (draft 15); o mesmo arquivo re-uploadado em **06-02** deu `done` (117k chars) | `created_at` + comparação 4698/6776 (failed em 05-31, done em 06-02) |
| Bate com o **bug de region/signature do R2** corrigido ~06-02 (memória `r2_region_auto`) | re-upload pós-fix funcionou; os de 05-31 nunca foram reprocessados |
| **Failed silencioso** — o motivo não ficava gravado no documento | sem coluna de erro; os ramos storage/no_bytes só emitiam evento efêmero |
| **Drafts não tinham reprocesso** | `POST /processes/{id}/extract` só cobre docs de PROCESSO; os do São Jorge estão em draft (`process_id` null) |
| **Bug do "preso em processing"** | no `except`, `raise self.retry()` levantava `Retry`, mas um `except Exception` interno **engolia** o `Retry` → a task nunca reexecutava e o doc ficava em `processing` para sempre |

**Conclusão:** a causa dominante NÃO é o modelo de OCR — é **falha de download do storage** (histórica, pré-fix R2), nunca reprocessada, sem motivo visível e sem caminho de retry para drafts.

## PASSO 2 — Correções

| # | fix | arquivo |
|---|---|---|
| A | **Reprocesso** `POST /documents/{id}/reprocess-ocr` — funciona para doc de **processo E de rascunho**; `force=True` re-baixa do storage. Botão **"↻ tentar de novo"** no card failed do `DraftDocumentUploader` | `app/api/v1/documents.py`, `DraftDocumentUploader.tsx` |
| B | **Fim do failed silencioso** — coluna `documents.ocr_error` (migration) gravada em todos os ramos de falha (storage, no_bytes, cascata, retries); limpa no sucesso. Exposta na API de docs do draft e na UI ("⚠️ motivo") | `models/document.py`, `workers/ocr_tasks.py`, migration `b2c3d4e5f6a7` |
| C | **Fim do "preso em processing"** — `Retry` propaga (Celery reexecuta); ao esgotar retries (`MaxRetriesExceededError`), `_mark_ocr_failed` marca `failed` com motivo | `workers/ocr_tasks.py` |
| D | **Formato honesto** — Word/.docx e não-PDF devolvem mensagem clara ("converta para PDF e reenvie") em vez de código técnico | `services/ocr_pdf.py` |

## PASSO 3 — Validação

- Unitário/integração (mock de storage, como a suíte de OCR já faz): reprocesso re-enfileira + limpa erro (`test_documents_reprocess.py`); guards de formato honestos (`test_ocr_pdf_guards.py`); `ocr_tasks` sem regressão. Frontend `tsc` + `build` verdes.
- **Validação real (failed → done com os arquivos reais):** depende do storage de produção (R2), fora do alcance local. **Acontece pós-deploy:** o consultor (André) reprocessa os docs failed do São Jorge via o botão "↻ tentar de novo" e confirma o resultado. Hipótese forte: os arquivos estão no R2 e o reprocesso baixa+OCRa com sucesso (region já corrigida).

## Report — doc → causa → fix → status

| doc (São Jorge) | causa medida | fix | status |
|---|---|---|---|
| CCIR 39/40/105/106 | download falhou (05-31, pré-fix R2); sem motivo gravado | reprocesso + ocr_error | pronto p/ reprocesso (validação prod) |
| ITR 44/45 | idem | idem | idem |
| recibo SIGCAR 46 | idem | idem | idem |
| certidões 41/42/43 | idem (já há gêmeo `done` 141/165 → cache-twin acelera) | reprocesso reusa o gêmeo | idem |
| docx (35/56/65) | formato sem OCR, failed sem motivo | mensagem honesta | resolvido (mensagem) |

PROIBIDO respeitado: não troquei o modelo de OCR (a causa não era o modelo); Fase 2/matriz intocadas (só consumem os docs destravados).
