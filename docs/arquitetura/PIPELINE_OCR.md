# Pipeline OCR

**Documento:** Arquitetura · referência viva
**Estado:** atualizado com Sprint V hardening (08/05)
**Última revisão:** 2026-05-15

---

Como o Regente extrai texto e campos estruturados de documentos PDF. Este pipeline é o que alimenta os Hubs (Cliente, Imóvel) e o agente Extrator com dados confiáveis.

## Visão geral

```
Upload no wizard de Intake
       │
       ▼
POST /api/v1/intake/drafts/{id}/import
       │ Backend: app/api/v1/intake.py
       │ Enqueue: workers.ocr_then_extract
       │
       ▼
ocr_then_extract task (Celery)
       │ Arquivo: app/workers/ocr_tasks.py
       │
       ├── 1. Cache self
       │    Document.extracted_text já populado? → skip OCR
       │
       ├── 2. Cache twin
       │    Outro Document do mesmo tenant com mesmo SHA-256
       │    já tem texto extraído? → copia o texto
       │
       ├── 3. Budget guard
       │    Tenant estourou orçamento mensal de IA?
       │    → marca skipped_budget, alerta, retorna
       │
       └── 4. extract_text_from_pdf
            │ Arquivo: app/services/ocr_pdf.py
            │
            ├── Tentativa A: pypdf (grátis, PDFs digitais)
            │    Se texto extraído >= 100 chars → ok
            │
            ├── Tentativa B: Gemini 2.5 Flash via LiteLLM
            │    PDFs nativos (PDFs com embedded text difícil)
            │    Custo: ~$0.0006 por doc de 8 páginas
            │
            └── Tentativa C: OpenAI gpt-4o-mini Vision
                 PDFs escaneados (precisa rasterizar)
                 Rasteriza com pypdfium2 (max 10 páginas, 200 DPI)
                 Custo maior, último recurso
       │
       ▼
Persiste AIJob (agent_name='ocr_pdf')
Atualiza Document.extracted_text + Document.text_extracted_at
       │
       ▼
run_agent.delay('extrator', metadata={document_id, ...})
       │ Arquivo: app/workers/agent_tasks.py
       │
       ▼
ExtratorAgent.run()
       │ Arquivo: app/agents/extrator.py
       │
       ├── Carrega Document.extracted_text
       ├── Identifica doc_type (matricula, car, ccir, etc.)
       ├── Carrega skill aplicável (extrator/matricula_generica.md, etc.)
       │    ⚠️ Skills reais não existem ainda — placeholder _template
       ├── Chama LLM com prompt específico do tipo
       └── Retorna extracted_fields (JSONB no AIJob.result)
       │
       ▼
Worker pós-extração:
       ├── Atualiza Client.field_sources (origem: extracted, com badge IA)
       ├── Atualiza Property.field_sources
       └── Emite evento WebSocket document_processed
```

## Cache em duas camadas

Cache é o que torna o pipeline viável economicamente.

### Cache self (mesmo documento)

`Document.extracted_text` é o cache. Toda re-execução do `ocr_then_extract` checa esse campo antes de chamar o OCR. **Re-OCR só acontece se forçado** (campo `force_reextract=True` na task).

### Cache twin (documento idêntico de outro lugar)

SHA-256 do arquivo é calculado no upload. Documentos com o mesmo hash dentro do tenant são considerados gêmeos. Se um já tem texto extraído, os outros aproveitam.

Esse cache pega caso comum: cliente envia mesma matrícula 3 vezes (uma no intake, outra na coleta, outra como anexo de proposta). OCR roda uma vez.

## Tentativas de extração — ordem e critério

### A — pypdf (grátis)

- PDFs digitais (gerados por sistema, com texto embarcado correto)
- Limite mínimo: `PYPDF_MIN_CHARS = 100` (PDFs escaneados frequentemente retornam pontuação solta de ruído)
- Falha → tenta B

### B — Gemini 2.5 Flash via LiteLLM

- Modelo: `settings.GEMINI_OCR_MODEL` (env-configurável; default `gemini/gemini-2.5-flash`)
- 2026-06-02: migrado de `gemini-2.0-flash` (descontinuado pelo Google → 404
  no worker). **Quando um modelo for descontinuado, trocar a env `GEMINI_OCR_MODEL`,
  não o código.**
- Aceita PDF nativo (não precisa rasterizar)
- Janela enorme (1M tokens)
- Custo: ~$0.0006 por doc de 8 páginas
- `num_retries=0` (não multiplica o timeout em caso de erro)
- Falha → tenta C

### C — OpenAI gpt-4o-mini Vision

- Rasteriza com `pypdfium2` (máx 10 páginas, 200 DPI)
- Manda imagens base64 ao Vision API
- Custo: maior (tokens de imagem caros)
- `timeout=OPENAI_VISION_TIMEOUT_SECONDS` (75s) + `num_retries=0` — fallback
  não pode pendurar a fila do worker (`pool=solo`); antes do fix pendurava ~272s
- Último recurso

## Constraints e proteções

| Constraint | Valor | Razão |
|---|---|---|
| `MAX_PDF_BYTES` | 50 MB | Proteção anti-DoS |
| `OCR_TIMEOUT_SECONDS` | 90s | Timeout da chamada Gemini |
| `OPENAI_VISION_TIMEOUT_SECONDS` | 75s | Timeout do fallback OpenAI Vision (`num_retries=0` — não pendura a fila) |
| `OPENAI_MAX_PAGES` | 10 páginas | Controla custo do Vision |
| `OPENAI_RASTER_DPI` | 200 | Balanço qualidade × tokens |
| `task.max_retries` | 2 | OCR não é idempotente em custo — não retentar para sempre |
| `task.retry_backoff` | True | Exponencial até 120s |

## Prompt do OCR (Gemini/OpenAI)

```
Extraia TODO o texto deste documento brasileiro
(fundiário, ambiental, cadastral ou fiscal).

Preserve:
- Ordem natural de leitura (cabeçalho → corpo → rodapé)
- Estrutura visual (parágrafos, listas, tabelas)
- Números, datas, códigos e identificadores exatamente como aparecem no documento
[...]
```

Prompt completo em `app/services/ocr_pdf.py:OCR_PROMPT`.

Decisão de design: o OCR **não interpreta**, apenas transcreve. Interpretação (identificar campos como CPF, número de matrícula, área) fica para o `ExtratorAgent` em etapa separada. Isso permite:

- Cache de texto bruto compartilhado entre múltiplas tentativas de extração
- Re-extração com prompt diferente sem refazer OCR
- Auditabilidade clara (texto bruto vs campos extraídos)

## ExtratorAgent — segunda etapa

Após o texto cru chegar em `Document.extracted_text`, o `ExtratorAgent` é despachado com metadata mínima (`document_id`). O agente:

1. Carrega o texto extraído
2. Identifica `doc_type` (matrícula, CAR, CCIR, auto de infração, licença, ofício SEMAD)
3. Carrega skill aplicável (futuro — hoje placeholder)
4. Chama LLM com prompt específico
5. Retorna `extracted_fields` (JSONB)

Exemplo de saída para uma matrícula:

```json
{
  "doc_type": "matricula",
  "fields": {
    "cartorio": "1º Tabelionato de Goiânia",
    "numero_matricula": "12345",
    "livro": "2-AB",
    "folha": "100",
    "proprietario_nome": "...",
    "proprietario_cpf": "...",
    "imovel_area_ha": 250.5,
    "imovel_municipio": "Goiânia",
    "imovel_uf": "GO"
  },
  "confidence": 0.92,
  "requires_review": true
}
```

`requires_review=True` em todo Extrator. Consultor confirma → vai para Cliente Hub / Imóvel Hub com `field_sources.source = "extracted_confirmed"`.

## Audit trail do pipeline

Cada estágio gera um `AIJob`:

| Estágio | `agent_name` | `job_type` |
|---|---|---|
| OCR (pypdf hit) | `ocr_pdf` | `extract_document` (cost=0) |
| OCR (Gemini Vision) | `ocr_pdf` | `extract_document` |
| OCR (OpenAI Vision) | `ocr_pdf` | `extract_document` |
| Extração (campos) | `extrator` | `extract_document` |

Todos com `entity_type="document"` e `entity_id=<document_id>`. Permite reconstruir custo total de OCR + extração por documento.

## Status real (15/05)

- 51 execuções históricas do ExtratorAgent (mais usado do sistema)
- Cache hit rate: a apurar (instrumentar)
- Custo médio por documento: a apurar
- Doc types cobertos com qualidade: matrícula (bom), CAR (bom), CCIR (médio), notificação SEMAD (médio)
- Doc types com falha frequente: ofício SEMAD escaneado (Vision OpenAI necessário; qualidade variável)

## Pendências e dívidas

1. **Skills reais do Extrator** (`extrator/matricula_generica.md`, `extrator/car_sicar.md`) — bloqueio aguardando reunião 16/05.
2. **Métrica de cache hit rate** — instrumentar.
3. **Métrica de custo médio por doc_type** — instrumentar.
4. **Detecção automática de doc_type** — hoje vem do upload (campo informado pelo usuário ou inferido pelo nome). Agente poderia detectar.
5. **OCR para imagens (JPG/PNG)** — hoje só PDF; alguns clientes enviam fotos de documento direto do celular.
6. **Re-OCR forçado via UI** — endpoint existe (`?force=true`), mas botão no frontend ainda não.

## Próximas leituras

- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — política aplicada no pipeline
- [`FLUXOS_E2E.md`](./FLUXOS_E2E.md) — onde este pipeline encaixa no fluxo do usuário
- [`MODELO_DE_DADOS.md`](./MODELO_DE_DADOS.md) — schemas de `Document`, `AIJob`, `Client.field_sources`
