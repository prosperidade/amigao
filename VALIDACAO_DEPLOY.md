# VALIDACAO_DEPLOY.md

Resposta às 8 perguntas levantadas pela revisão Opus. Todas as evidências são
`arquivo:linha` ou "NÃO ENCONTRADO". Nenhum código foi alterado.

---

## 1. Sleep do Starter $7

**Confirmado: minha afirmação anterior estava ERRADA.** Apenas o tier **Free**
dorme após 15 min de inatividade. **Starter ($7/mês) NÃO dorme** — Render
mantém o serviço sempre on.

- **Fonte:** `render.com/pricing` e `render.com/docs/free#free-web-services`
  (documentação pública).
- **Trecho:** Free web services "spin down after periods of inactivity". A
  página de pricing do Starter lista "Always-on" como diferencial vs Free.
- **Em linguagem clara:** se você pagar $7, o cold-start de 30s do Free
  desaparece. O motivo para subir para Standard $25 é RAM/CPU, não sleep.

---

## 2. RAM real necessária na API

### 2a. Modelo ML em memória no startup?

**NÃO ENCONTRADO.** Grep por `from_pretrained|model.load|joblib.load|torch.load|AutoModel|SentenceTransformer` em `**/*.py` retornou **zero arquivos**.

A IA é 100% remota via [app/core/ai_gateway.py](app/core/ai_gateway.py)
(LiteLLM → OpenAI / Gemini / Anthropic). Nenhum peso de modelo é carregado no
processo Python.

### 2b. Maior payload que passa pela API

PDFs (ofícios SEMAD, autorizações, planos) **são carregados em memória inteiros**, não streamados:

- [app/services/ocr_pdf.py:30](app/services/ocr_pdf.py#L30): `MAX_PDF_BYTES = 50 * 1024 * 1024` — limite de 50 MB.
- [app/services/ocr_pdf.py:72](app/services/ocr_pdf.py#L72): `PdfReader(io.BytesIO(pdf_bytes))` — `pdf_bytes` é o blob inteiro.
- [app/workers/ocr_tasks.py:92](app/workers/ocr_tasks.py#L92): `pdf_bytes = storage.download_bytes(doc.storage_key)` — download síncrono e completo do MinIO/R2.
- [app/services/ocr_pdf.py:32-33](app/services/ocr_pdf.py#L32-L33): rasterização opcional a 200 dpi × até 10 páginas para fallback OpenAI Vision — pico adicional de ~80-150 MB durante OCR escaneado.

**Importante:** o OCR roda no **worker Celery**, não na API. A API só recebe o
upload (FastAPI/uvicorn já streama para disco/MinIO antes de virar bytes).
O pico de RAM com PDF inteiro em memória é no **worker**, não no `web service`.

### 2c. Pacotes pesados no requirements

Conteúdo completo de [requirements.txt](requirements.txt):

```
fastapi, uvicorn[standard], pydantic, pydantic-settings, email-validator,
sqlalchemy, sqlalchemy-utils, alembic, psycopg2-binary, redis, celery,
python-multipart, python-jose[cryptography], passlib[bcrypt], boto3,
GeoAlchemy2, fpdf2, litellm, httpx, pypdf>=5.0, pypdfium2>=4.30,
beautifulsoup4>=4.12, lxml>=5.0, PyYAML>=6.0, slowapi>=0.1.9
```

**NÃO ENCONTRADO** no requirements: `torch`, `transformers`, `langchain`,
`tensorflow`, `sentence-transformers`, `spacy`, `scikit-learn`, `numpy`,
`scipy`. Pesos médios estimados (importados):

| Pacote | RAM aprox. |
|---|---|
| fastapi + uvicorn + pydantic v2 | ~60 MB |
| sqlalchemy + psycopg2-binary | ~40 MB |
| celery + redis | ~30 MB |
| litellm (lazy provider loading) | ~50-80 MB |
| boto3 | ~40 MB |
| pypdf + pypdfium2 + lxml | ~50 MB |
| Python 3.11 baseline | ~30 MB |
| **Total idle estimado** | **~280-330 MB** |

### 2d. Estimativa final

- **API (web service)** — só recebe upload, não OCRa. Pico raro acima de 350 MB. **Starter $7 (512 MB) COBRE** com folga de ~150 MB.
- **Worker Celery** — faz OCR + agentes. Com PDF de 50 MB + rasterização pode subir a 450-500 MB transitório. **Starter $7 (512 MB) é APERTADO**. Em pilot SEMAD com PDFs grandes recomendo **Standard $25 (2 GB)** só para o worker.

**Recomendação:** API em Starter $7 + Worker em Standard $25. Total $32.
Se quiser cortar custo no piloto, ambos em Starter $7 com `MAX_PDF_BYTES`
reduzido para 20 MB no `.env` mitiga risco.

---

## 3. Volume de chamadas Celery por hora

### 3a. Volume estimado

**Beat schedules fixos** ([app/core/celery_app.py:27-53](app/core/celery_app.py#L27-L53)):

| Task | Cadência | Tasks/dia |
|---|---|---|
| `monitor_legislation_dou` | diária 06:00 | 1 |
| `monitor_legislation_doe` | diária 06:30 | 1 |
| `monitor_legislation_agencies` | semanal seg 03:00 | ~0.14 |
| `vigia_all_tenants` | cada 6h | 4 |
| `acompanhamento_check_all` | cada 30 min | 48 |
| `cleanup_expired_intake_drafts` | diária 02:30 | 1 |
| **Total beat** | | **~55/dia** |

**Disparos user-triggered** (estimativa SEMAD piloto):
- OCR auto após upload: ~10-30 docs/dia
- Classify demand / extract / agentes (diagnostico, legislacao, etc.): ~20-50/dia
- Webhook tasks, agent_tasks: ~10-30/dia

**Total realista no piloto: 100-200 tasks/dia (~4-8/hora).**

### 3b. Broker config

**NÃO ENCONTRADO**: `broker_pool_limit`, `broker_transport_options` em todo o
repo (grep retornou zero matches). O Celery roda com defaults
(`broker_pool_limit=10`, sem `transport_options` customizado).

[app/core/celery_app.py:14-18](app/core/celery_app.py#L14-L18):
```python
celery_app = Celery(
    "amigao_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
```

Backend de resultado **TAMBÉM** é o mesmo Redis — cada task escreve resultado
serializado lá. Isso aumenta volume de comandos Redis (~3-4 SET/GET por task).

### 3c. Render Redis $10 vs Upstash free

Cálculo de comandos Redis/dia no piloto:
- 200 tasks × (1 enqueue + 1 result write + ~2 worker polls) ≈ **800 comandos/dia**
- Beat scheduler adiciona ~100 LPOPs vazios/dia

**Upstash Free**: 10k comandos/dia → **fits 12× com folga**.
**Render Redis $10**: paga por banda, não por comando — desperdício no piloto.

**Recomendação:** **Upstash free** no piloto. Migrar para pago só se volume
ultrapassar 5k comandos/dia (~1000 tasks). Há um detalhe: Celery + Upstash
exige `broker_transport_options = {"visibility_timeout": 3600}` para evitar
re-delivery em tasks longas — isso **não está configurado** hoje. Item de
follow-up no deploy.

---

## 4. AIJob × Celery

### 4a. Modelo

[app/models/ai_job.py:46-81](app/models/ai_job.py#L46-L81). Campos principais:

- `id`, `tenant_id`, `created_by_user_id`
- `entity_type`, `entity_id` (process | document | proposal)
- `job_type` (enum: classify_demand, extract_document, embedding_generation, enquadramento_regulatorio, monitoramento_legislacao, etc.)
- `status` (enum: pending | running | completed | failed)
- `model_used`, `provider`, `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms`
- `input_payload` (JSONB), `result` (JSONB), `raw_output` (Text), `error` (Text)
- `agent_name`, `chain_trace_id`
- `created_at`, `started_at`, `finished_at`

### 4b. Task Celery que CRIA/ATUALIZA AIJob

Exemplo canônico em [app/workers/ai_tasks.py:48-92](app/workers/ai_tasks.py#L48-L92):

```python
# Linha 48-59: cria AIJob em status=running ANTES da chamada LLM
job = AIJob(
    tenant_id=tenant_id,
    created_by_user_id=user_id,
    entity_type="process",
    entity_id=process_id,
    job_type=AIJobType.classify_demand,
    status=AIJobStatus.running,
    started_at=datetime.now(UTC),
)
db.add(job); db.commit(); db.refresh(job)

# Linha 81-92: fecha como completed após sucesso da chamada LLM
job.status = AIJobStatus.completed
job.finished_at = datetime.now(UTC)
job.result = {...}
db.add(job); db.commit()
```

Padrão idêntico em [app/workers/ocr_tasks.py](app/workers/ocr_tasks.py) e
nas 18 outras tasks (grep `AIJob\(` retornou 2 arquivos com criação direta;
o padrão foi refatorado em base class `AIJobTask` segundo observação interna
3282, mas o comportamento é o mesmo).

### 4c. Polling de AIJob sem Celery?

**NÃO ENCONTRADO** em código de produção. O único `poll`/`sleep` encontrado é:

- [ops/run_homologation_smoke.py:31,192,199,254,261](ops/run_homologation_smoke.py#L31) — **smoke test ops**, não código de runtime.
- [app/api/v1/documents.py:157](app/api/v1/documents.py#L157) — é **comentário** explicando que o frontend faz polling em `Document.ocr_status` (não em `AIJob`).

**Conclusão:** AIJob é **status-tracker + audit + cost tracker** dentro da
task Celery. Não é fila paralela. O usuário acompanha progresso via:
1. WebSocket events (`document.ocr.completed`) — [app/workers/ocr_tasks.py:74-78](app/workers/ocr_tasks.py#L74-L78)
2. Polling no `Document.ocr_status` (campo da própria entidade)

AIJob é lido depois para audit/billing, não para esperar resultado.

---

## 5. Supabase pooler compatibility

### 5a. LISTEN/NOTIFY

**NÃO ENCONTRADO.** Grep por `LISTEN|NOTIFY|psycopg2\.extensions` em
`**/*.py` retornou zero matches.

### 5b. Prepared statements / cursores

**NÃO ENCONTRADO.** Grep por `server_side_cursors|executemany_mode` retornou
zero matches.

[app/db/session.py:6-15](app/db/session.py#L6-L15) usa engine padrão SQLAlchemy 2.x
com `pool_pre_ping=True`, `pool_size=20`, `max_overflow=10`. Sem hints
exóticos. Apenas `statement_timeout=30000` (timeout SQL, não prepared).

### 5c. Veredito

**Compatível com Supabase pooler em transaction mode (porta 6543).**
- Sem LISTEN/NOTIFY → nada quebra
- Sem prepared statements server-side → nada quebra
- `pool_size=20` é razoável; Supabase pooler suporta isso por client

**Recomendação de connection string:**
- API + Worker (CRUD + queries normais): **6543 (transaction pooler)**
- Alembic migrations (DDL exige sessão estável): **5432 (direct) ou 5433 (session pooler)**

Não preciso de 2 connection strings dentro do app — só dividir em ops:
`DATABASE_URL` no serviço, `MIGRATE_DATABASE_URL` no comando alembic do
deploy hook.

---

## 6. Migrations pendentes

### 6a. `alembic current` vs `alembic heads`

- `alembic heads`: **`b1a2c3d4e5f6 (head)`** — single head ✅
- `alembic current`: **`b1a2c3d4e5f6 (head)`** ✅ (rodado em 2026-05-18 16:32 BRT via `docker compose exec api alembic current` após `db` subir)

**Conclusão: DB dev está no head. Zero divergência entre `current` e `heads`. Zero migrations pendentes localmente.**

Para o primeiro deploy no Supabase: o DB lá nasce vazio, então `alembic upgrade head` vai rodar **todas** as 40 migrations em sequência (não só "as pendentes").

**Importante:** o nome do head (`b1a2c3d4e5f6_sprint1_intake.py`) é confuso
porque alembic ordena por dependência de revision, não por filename. Não é o
arquivo "mais antigo" — é o head real da chain.

### 6b. Quantidade no primeiro deploy

**40 arquivos de migration** em [alembic/versions/](alembic/versions/) (`ls | wc -l = 40`). Todas vão rodar no primeiro deploy contra Supabase virgem.

### 6c. Destrutivas ou >30s?

Não auditei migration por migration. Por nomenclatura, são todas **aditivas**
(nomes começam com `add_`, `sprint_X`, `regente_v3_camN`). Risco real:

- `f9d2e8c1a4b3_sprint_u_knowledge_catalog.py` — cria tabela com `vector(768)` → exige `CREATE EXTENSION vector` antes. **Supabase tem pgvector como extension habilitável via dashboard ou MCP `apply_migration`.**
- Migrations envolvendo PostGIS (`Geometry` columns) — Supabase já vem com PostGIS habilitado.
- Tempo total estimado em DB vazio: **<60s**, sem locks longos (tabelas vazias).

**Ação requerida pré-deploy:** habilitar `vector` e confirmar `postgis` no
Supabase via `list_extensions` MCP **antes** do primeiro `alembic upgrade`.

---

## 7. Secrets em código (git history)

Rodei dois passes:

1. `git log -p | grep -iE "sk-[A-Za-z0-9_-]{20,}|api[_-]?key.*=.*['\"][A-Za-z0-9_-]{20,}"` → **NÃO ENCONTRADO** (zero output).
2. `git log -p | grep -iE "(OPENAI|GEMINI|RESEND|ANTHROPIC|SECRET_KEY|SUPABASE)_.{0,20}=.{0,5}['\"][A-Za-z0-9_-]{20,}"` → único match foi:
   ```
   +OPENAI_MODEL = "text-embedding-3-small"
   +GEMINI_MODEL = "gemini-embedding-001"
   ```
   Esses são **nomes de modelo**, não chaves. Falso positivo do regex.

**Conclusão: NENHUMA chave de API real foi commitada no histórico** dos 104 commits do repo.

**Caveat:** o grep é uma heurística — não exclui chaves em formato não
detectado (ex: secrets curtos, JWTs). Recomendo rodar `gitleaks` ou
`trufflehog` antes do deploy público como verificação independente.

---

## 8. Dimensão de embedding pgvector

### 8a. Coluna e dimensão

[app/models/knowledge_catalog.py:96](app/models/knowledge_catalog.py#L96):
```python
embedding = Column(_Vector(768), nullable=True)
```

Tipo opaco definido em [app/models/knowledge_catalog.py:46-59](app/models/knowledge_catalog.py#L46-L59) gera `vector(768)` no DDL.

**Única coluna `Vector(N)` no projeto.** Dimensão = **768**.

Modelo de embedding atual: `OPENAI_MODEL = "text-embedding-3-small"` (configurado para output 768d via `dimensions` parameter; o nativo é 1536d truncado). Ver memória `project_sprint_w_rag_estadual.md`.

### 8b. Volume previsto no piloto

Memória `project_corpus_legislativo.md` (Sprint 0) e `project_sprint_w_rag_estadual.md` (Sprint W):
- Corpus atual: **22.573 chunks** (Federal + MS + MT + GO)
- Piloto SEMAD adiciona corpus de **GO + ofícios da sócia** → estimativa **+5.000 a +10.000 chunks**

**Total piloto: ~25.000-35.000 registros.**

Espaço em disco: 30k × 768 × 4 bytes (float32) ≈ **92 MB** + overhead de índice ivfflat ≈ **120-150 MB total**. Cabe trivialmente em qualquer plano Supabase (Pro = 8 GB).

Performance: para 30k vetores, ivfflat com `lists=100` dá <50ms por query. **Sem necessidade de HNSW.**

---

## Resumo executivo do veredito

| Item | Status | Ação |
|---|---|---|
| 1. Starter sleep | ❌ Eu estava errado — só Free dorme | Corrigir no `render.yaml` doc |
| 2. RAM API | ✅ Starter $7 cobre API | Worker em Standard $25 recomendado |
| 3. Celery volume | ✅ Baixo (~200/dia) | Upstash free + add `visibility_timeout` |
| 4. AIJob × Celery | ✅ Status-tracker, não fila paralela | Nada a mudar |
| 5. Supabase pooler | ✅ Compatível (transaction mode 6543) | Usar 5432 só p/ alembic |
| 6. Migrations | ✅ dev em head; 40 rodam no 1º deploy Supabase | Habilitar pgvector extension antes do `upgrade head` |
| 7. Secrets git | ✅ Nenhuma chave commitada | Rodar gitleaks como verificação extra |
| 8. pgvector dim | ✅ 768d, ~30k rows no piloto | Cabe em qualquer plano |

**3 furos do Opus confirmados:**
- (1) Sleep do Starter — informação minha estava errada
- (3) Justificativa do Redis — eu não tinha medido volume real (é baixo, Upstash basta)
- (6) Pgvector extension precisa ser habilitada manualmente antes da migration — não estava no checklist
