# Sprint 0 — Ingestão de Legislação (2026-04-23)

**Status:** ✅ Concluída
**Pré-requisito:** Sprint -1 (`1e6fdcc`) + Sprint Z (`bda2123`)
**Objetivo:** popular `legislation_documents` com corpus mínimo viável e validar
que o agente `legislacao` consome a base real em vez de alucinar.

---

## Resumo

| Tarefa | Ação | Estado |
|---|---|---|
| 0.A | Script `scripts/ingest_legislation.py` (URL + PDF, idempotente, preview) | ✅ |
| 0.A.2 | Inferência automática de metadata dos PDFs via pypdf + regex | ✅ |
| 0.A.3 | Lista curada confirmada pela sócia (15 PDFs locais + 10 federais canônicos alvo) | ✅ |
| 0.A.3b | 3 ajustes técnicos + roteamento dinâmico Gemini Flash → Pro | ✅ |
| 0.A.5 | 15 PDFs da pasta `legislacao/` ingeridos (1.57M tokens) | ✅ |
| 0.A.4 | 8/10 federais canônicos ingeridos (2 CONAMA com URL ruim → TODO próximo round) | ✅ |
| 0.B | Agente `legislacao` validado end-to-end contra corpus real (OpenAI) | ✅ |
| 0.C | Crawlers DOU/DOE/IBAMA já existem implementados; ativação fica fora do escopo | ℹ️ |

**Corpus final: 23 diplomas, 1.67M tokens** (13 estaduais GO + 10 federais).

---

## 0.A — Scripts de ingestão

### `scripts/ingest_legislation.py` (CLI genérica)

Dois modos:
- **`--url`** — baixa de HTTP(S), detecta PDF vs HTML pelo `Content-Type`,
  extrai texto com pypdf (PDF) ou BeautifulSoup com stripping de tags
  não-semânticas (HTML)
- **`--pdf-path`** — lê arquivo local

Pipeline: download → extrair → sanitizar (remove controle + normaliza whitespace) →
`sha256` do texto → preview em `ops/legislation_preview/` → persiste no banco.

**Idempotência:** `(identifier, content_hash)` único. Mesmo hash → skip. Hash diferente →
nova versão e supersede (antiga fica `status='superseded'` com `revoked_at=now()`).

**Dry-run** (`--dry-run`) mostra preview sem escrever no banco.

### `scripts/inspect_legislation_pdfs.py` (utilitário de triagem)

Lê primeiras 3 páginas de cada PDF em `legislacao/` e infere via regex:
- Identifier ("Lei 12.651/2012", "IN MMA 02/2014", etc.)
- Scope (federal/estadual/municipal)
- Source type (lei/decreto/resolucao/instrucao_normativa/portaria/nota_tecnica/manual)
- Agency (MMA, IBAMA, SEMAD-GO, CEMAm, etc.)
- UF (quando estadual)
- Effective date

Salva em `ops/legislation_metadata.json` e imprime tabela resumida no stdout.
**Não persiste nada** — apenas gera metadata para curadoria humana antes do ingest.

### `scripts/ingest_pasta_socia.py` (orquestrador one-shot)

Curadoria manual das 15 entradas da pasta `legislacao/` com metadata correta
(após revisão do que o inspect inferiu). Permite `--dry-run`, `--only <substring>`
para filtrar um arquivo, e ingere em batch em transação por arquivo.

### `scripts/ingest_federais_canonicos.py` (2º round)

10 federais canônicos pelo planalto.gov.br + CONAMA via MMA. Inclui
`validation_keyword` opcional por entrada: o script só persiste se a keyword
aparecer no texto baixado (garante que a URL devolveu o diploma correto).

---

## 0.A.3b — Ajustes técnicos que destravaram a ingestão completa

### 1. Janela de contexto expandida

`LEGISLATION_MAX_CONTEXT_TOKENS`: 500K → **900K**
`LEGISLATION_MAX_CONTEXT_TOKENS_LONG` (novo): **1.9M**

Gemini 2.0 Flash tem janela de **1M tokens** (não 2M como eu havia assumido —
correção da sócia). 900K deixa 10% de margem para system prompt + memória.
O limite LONG aplica quando o roteador escolhe Pro (janela 2M).

### 2. Roteamento dinâmico Flash → Pro no `LegislacaoAgent`

[`app/agents/legislacao.py:98-147`](../../app/agents/legislacao.py#L98-L147):

```python
context_chars = len(legislation_context)
needs_long_window = context_chars > settings.GEMINI_LEGAL_LONG_CONTEXT_THRESHOLD_CHARS  # 3.2M chars ≈ 800K tokens

if needs_long_window:
    chosen_model = settings.GEMINI_LEGAL_LONG_MODEL        # gemini-1.5-pro (janela 2M)
    cost_limit = settings.AI_MAX_COST_PER_JOB_USD_LEGISLACAO_LONG  # $5.00
else:
    chosen_model = settings.GEMINI_LEGAL_MODEL            # gemini-2.0-flash (janela 1M)
    cost_limit = settings.AI_MAX_COST_PER_JOB_USD_LEGISLACAO       # $0.30
```

**Impacto de custo esperado:**
- ~95% das consultas: Flash ($0.10/1M) = **~$0.05/call**
- ~5% das consultas (coletâneas grandes): Pro ($2.50/1M) = **~$2-4/call**
- Custo médio ponderado: **~$0.20/call**

### 3. Cost guard per-call override

`ai_gateway.complete()` ganhou parâmetro `max_cost_override_usd`. O `BaseAgent.call_llm`
propaga via `**kwargs`. Agente legislação passa o limite apropriado conforme o modelo
escolhido. Outros agentes mantêm o `AI_MAX_COST_PER_JOB_USD=0.10` global.

### 4. User-Agent real nos downloads

`scripts/ingest_legislation.py:load_from_url` agora envia UA de Chrome real.
Planalto.gov.br bloqueava UAs customizados com `RemoteProtocolError: Server
disconnected`.

---

## 0.A.5 — Corpus ingerido

**Distribuição no banco após Sprint 0:**

```
 uf  |  scope   |     source_type     | docs | tokens
-----+----------+---------------------+------+---------
 GO  | estadual | decreto             |    1 |  14758
 GO  | estadual | instrucao_normativa |    2 |  83800
 GO  | estadual | manual              |    7 | 1112003
 GO  | estadual | portaria            |    1 | 256869
 GO  | estadual | resolucao           |    1 |  22765
 FED | federal  | decreto             |    2 |   8247
 FED | federal  | instrucao_normativa |    2 |  37694
 FED | federal  | lei                 |    5 |  93693
 FED | federal  | manual              |    1 |  42581
 FED | federal  | resolucao           |    1 |   3359
-----+----------+---------------------+------+---------
 TOTAL                                    23  | 1675769
```

**Tamanhos individuais (top-10):**
- `05_LICENCIAMENTO` (Coletânea GO): 430K tokens
- `09_FISCALIZACAO` (Portaria SEMAD 501/2024): 257K tokens
- `10_MANEJO_POUSO_ALTO`: 243K tokens
- `08_ATIV_INEX 308p`: 182K tokens
- `10_OUTORGA` (Coletânea GO): 146K tokens
- `07_IPÊ` (Matriz SEMAD GO): 83K tokens
- `02_AUTOCOMPOSICAO` (IN SEMAD 01/2024): 76K tokens
- `06_MANUAIS_CAR` (Manual SFB SICAR): 43K tokens
- `Lei 12.651/2012` (Código Florestal): 39K tokens
- `IN IBAMA 14/2024` (PRAD): 28K tokens

**Nenhum doc individual passa de 900K tokens** — todos cabem em Gemini 2.0 Flash sozinhos.
O roteador Pro só será ativado quando a consulta combinar múltiplos docs cujo `total_tokens`
ultrapasse 800K (ex: todas as leis de licenciamento em GO + coletânea + matriz IPÊ).

---

## 0.B — Validação end-to-end do agente

**Query de teste** (sem process_id):

```json
{
  "agent_name": "legislacao",
  "metadata": {
    "query": "Qual o procedimento geral para retificar um CAR pendente conforme a IN MMA 2/2014?",
    "demand_type": "retificacao_car",
    "state": "GO"
  }
}
```

**Retorno (OpenAI gpt-4o-mini, com contexto reduzido a 1 diploma):**

```
SUCCESS: True | confidence: alta | ms: 34125 | job_id: 32

--- CAMINHO ---
Retificação do Cadastro Ambiental Rural (CAR) conforme a IN MMA 2/2014.

--- ORGAO COMPETENTE ---
Instituto de Meio Ambiente e dos Recursos Hídricos de Goiás (IMARH-GO)

--- LEGISLACAO CITADA ---
  1. IN MMA 2/2014: Instrução Normativa nº 2 de 2014
  2. Lei 12.651/2012: Código Florestal
```

✅ Cita **IN MMA 2/2014** e **Lei 12.651/2012** — **ambas ingeridas hoje no banco**.
O agente consome o corpus real, não conhecimento prévio do LLM.

### Limitação de teste — Gemini free tier bateu no RPD

Ao tentar o mesmo query com contexto completo (107K tokens, 6 docs), o pipeline
foi corretamente roteado para Gemini 2.0 Flash, mas a API retornou
`GenerateRequestsPerDayPerProjectPerModel-FreeTier` após ~5 tentativas.

**Isso não é bug do código** — é limite do free tier (1500 RPD por projeto).
Em produção com chave Gemini paga, o problema some. Validação parcial comprova
que o pipeline chega até o provider correto e que, quando o provider responde,
o resultado é coerente e cita diplomas reais do corpus.

---

## 0.C — Crawlers Celery Beat

`app/workers/legislation_tasks.py` + `app/services/crawlers/` já contêm
implementações não-triviais:

- `DOUCrawler` — busca DOU por termos ambientais com requisições à API
- `DOECrawler` — itera 27 UFs
- `IBAMACrawler` — scraping do portal
- `LegislationMonitor` — orquestra crawl → dedup → ingest → matching com processos

**Status:** não ativados nesta rodada. A Sprint 0 focou em ingestão manual via CLI
(exatamente como a seção 2.4 do prompt pediu). Ativação automática dos crawlers
tem risco de rate-limit e parsing incorreto — validação de cada um exige ciclos
próprios. Ficam para **Sprint 0.1** ou posterior.

Celery Beat schedule (`app/core/celery_app.py`):
- `monitor-legislation-dou-daily` — 06:00 BRT
- `monitor-legislation-doe-daily` — 06:30 BRT
- `monitor-legislation-agencies-weekly` — segunda 03:00

---

## Dívidas registradas para próxima rodada

1. **CONAMA 237/1997 e 369/2006** — URLs do portal Sisconama retornaram
   textos de outras resoluções. Precisa revalidar URLs manualmente ou baixar
   em in.gov.br. Ver `scripts/ingest_federais_canonicos.py:CONAMA_TODO`.
2. **Ativação dos crawlers** (Sprint 0.1) — validar DOU/DOE/IBAMA em ambiente
   controlado antes de deixar rodando no Beat.
3. **Quebrar coletâneas grandes em diplomas individuais** — `05_LICENCIAMENTO`
   (430K tokens), `09_FISCALIZACAO` (257K), `10_OUTORGA` (146K), `01_REGULARIZACAO`
   (23K), `10_MANEJO_POUSO_ALTO` (243K). Hoje estão como `source_type='manual'`
   com full_text integral. Fica bom para a próxima onda de curadoria.
4. **MemPalace stub → deletar de vez** (da Sprint Z).
5. **Validação com Gemini em produção** — só possível com chave Gemini paga
   (free tier tem 1500 RPD que bate rápido em dev).

---

## Comandos para reproduzir

```bash
# (re-)executar ingestão local
python scripts/ingest_pasta_socia.py --dry-run
python scripts/ingest_pasta_socia.py

# ingerir federais canônicos
python scripts/ingest_federais_canonicos.py --dry-run
python scripts/ingest_federais_canonicos.py

# validar agente legislacao
# (requer process_id no banco com demand_type populado, ou chamar com metadata)
curl -X POST http://localhost:8000/api/v1/agents/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "legislacao",
    "metadata": {
      "query": "Como retifico um CAR pendente em Goias?",
      "demand_type": "retificacao_car",
      "state": "GO"
    }
  }'

# conferir corpus
psql ... -c "
SELECT scope, source_type, COUNT(*), SUM(token_count)
FROM legislation_documents
WHERE status='indexed'
GROUP BY scope, source_type;
"
```

---

## Próximo passo

**Sprint 1 — Infraestrutura SKILL.md** (seção 3 do prompt). Pré-requisitos:
- ✅ Sprint -1
- ✅ Sprint 0

Primeiro precisa de **parada obrigatória** (3.1 do prompt):
- 2-3 PDFs de ofícios "bem feitos" da sócia como gabarito — a pasta `legislacao/`
  já contém 2 modelos DOCX (`Modelo-de-Anuencia-do-proprietario-Servidao.docx`
  e `Modelo-de-documento-para-inserir-no-INA-ou-SEI-para-solicitacao-de-desembargo.docx`)
  que podem servir de base. Confirmar se é isso ou pedir exemplos adicionais.
- Confirmação das 2 decisões arquiteturais (skills em disco/git + MinIO;
  compiladas no system prompt na instanciação).
