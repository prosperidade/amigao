# Pipeline OCR + Extração — Sprint V hardening (2026-05-08)

## Visão geral

```
Upload no wizard
   │
   ▼
POST /intake/drafts/{id}/import
   │
   ▼
workers.ocr_then_extract  (Celery, app/workers/ocr_tasks.py)
   │  ├─ cache_hit_self  → skip OCR
   │  ├─ cache_hit_twin  → copia texto de outro doc com mesmo SHA-256
   │  ├─ check_tenant_monthly_budget → 429 se estourou
   │  └─ extract_text_from_pdf  (app/services/ocr_pdf.py)
   │        1. pypdf  (grátis, PDFs digitais)         → texto
   │        2. Gemini 2.0 Flash via LiteLLM           → texto (PDFs nativos)
   │        3. OpenAI gpt-4o-mini Vision via LiteLLM  → texto (rasteriza com pypdfium2)
   │
   ▼
Persiste AIJob (agent_name='ocr_pdf')
   │
   ▼
run_agent.delay('extrator', metadata={document_id, ...})
   │
   ▼
ExtratorAgent  → AIJob(extracted_fields)
   │
   ▼
commit_draft  → enrich_from_intake_extraction  → Property/Client.field_sources={...: 'ai_extracted'}
```

## Custos observados (caso Romilton, 8 PDFs)

| Estágio | Provider | Cost USD |
|---|---|---|
| pypdf (3 docs digitais) | grátis | $0.000 |
| OpenAI Vision (5 docs escaneados) | gpt-4o-mini | $0.080 |
| Extrator (8 docs) | gpt-4o-mini | ~$0.005 |
| **Total por caso** | — | **~$0.085** |

Projeção: 1.000 casos / mês ≈ $85. Cabe folgado num pricing SaaS.

## Dívidas técnicas conhecidas (DEFER pós-pilot)

### Operacional
- **A. Migração para região BR** — Gemini/OpenAI processam PDFs em servidores fora do Brasil. Para conformidade LGPD plena, migrar para Bedrock (São Paulo) ou Azure (Brazil South). Hoje a UI exibe aviso explícito ao consultor (`IntakeWizard.tsx` etapa 4) com checkbox de ciência.
- **B. UX assíncrona com progresso** — pool=solo + sequencial → 1 caso de 8 docs leva ~5 min. Pra 45 usuários simultâneos vai ficar visível. Pós-pilot: pool=prefork com N workers + WebSocket de progresso por doc.
- **C. Quota Gemini Free Tier** — chave atual do `.env` está no Free Tier com `limit: 0`. Habilitar billing no Google AI Studio para Gemini virar fallback útil em vez de OpenAI Vision-only.

### Mapeamento de campos
- **D. `_CLIENT_KEY_MAP` em `app/services/intake_enrichment.py:50`** só procura CPF em `proprietario_cpf_cnpj | cpf_cnpj_proprietario | infrator_cpf_cnpj`. Doc types como `comprovante_endereco` extraem CPF na chave plain `cpf_cnpj` e ficam de fora. Expandir o mapping conforme novos doc types entrarem em uso real.

### Qualidade
- **E. Anti-alucinação por doc type** — Gemini/OpenAI Vision podem "preencher" campos inventados. Para docs críticos (escritura, CAR, matrícula), exibir confidence + flag `requires_review` na UI antes do auto-fill. Hoje `Document.confidence_score` é setado (0.95 pypdf, 0.70 vision) mas não há UI usando.
- **F. Inconsistências cruzadas Imóvel × Cliente** — caso Romilton já mostrou: CAR diz município "Uruaçu", form_data diz "Goiás". CPFs diferentes em comprovante (`641.946.801-97`) vs CAR (`541.846.961-47`). É exatamente o gap que o **agente `auditor_imovel` da Sprint Y** vai cobrir. Não cabe na Sprint V.

### Resiliência
- **G. Cache invalidation em re-upload** — hoje cache_hit_twin assume que mesmo SHA-256 → mesmo conteúdo. Se um doc é "substituído" (mesmo storage_key, conteúdo novo), a lógica não vê. Quando existir flow de "trocar arquivo", invalidar checksum no upload.
- **H. Fallback de provedor mais granular** — hoje a cadeia é hardcoded pypdf → gemini → openai. Tornar configurável por tenant/feature flag (ex.: tenant gov só usa Bedrock-SP).

## Limites operacionais

| Limite | Valor | Onde |
|---|---|---|
| Tamanho máximo do PDF | 50 MB | `MAX_PDF_BYTES` em `ocr_pdf.py` |
| pypdf min chars (gatilho fallback) | 100 | `PYPDF_MIN_CHARS` |
| OpenAI Vision páginas máx | 10 | `OPENAI_MAX_PAGES` |
| Rasterização DPI | 200 | `OPENAI_RASTER_DPI` |
| Timeout LLM | 90s | `OCR_TIMEOUT_SECONDS` |
| Budget mensal por tenant | configurável | `Tenant.ai_monthly_budget_usd` |

## Como reativar Gemini quando billing for habilitado

Nada a mudar no código. Após habilitar billing em https://ai.google.dev/, a próxima chamada vai funcionar e o orquestrador para de cair pra OpenAI Vision automaticamente (Gemini é mais barato pra PDFs nativos).
