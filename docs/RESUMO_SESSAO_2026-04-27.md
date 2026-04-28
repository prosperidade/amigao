# Resumo — sessão de 2026-04-27

**Destinatário:** continuação amanhã (2026-04-28+) e brainstorm arquitetural externo.
**Commit da sessão:** `c449df0 feat(sprint-u): knowledge_catalog com pgvector + busca semântica`.
**Sprint executada:** **Sprint U** — knowledge_catalog (RAG semântico via pgvector).
**Duração estimada:** ~2h de trabalho efetivo.

---

## 1. Estado antes × depois

| Eixo | Antes | Depois |
|---|---|---|
| **pgvector** | Não instalado (imagem `postgis/postgis:15-3.3` pura) | **Instalado 0.8.2** via imagem custom estendida |
| **knowledge_catalog** | Não existia | Tabela criada com 9 índices (btree/GIN/IVFFlat cosseno) |
| **Embeddings** | Inexistente — só comentários preparatórios em 3 arquivos | Service Gemini `text-embedding-004` (768 dim, batch até 100, custo zero) |
| **Chunking** | Inexistente | Híbrido: regex `Art./Capítulo/Seção/Título` → fallback janela deslizante 800 tok / 100 overlap |
| **Busca semântica** | Não existia (busca legacy só por keyword) | Função `search()` por similaridade cosseno com filtros (tenant/source_type/jurisdiction/uf/identifier) |
| **Tasks Celery** | Sem indexação automatizada | 3 tasks: 1 doc / texto avulso / re-indexação completa |
| **Endpoints REST** | Inexistentes | 3: `GET /knowledge/search`, `POST /knowledge/index`, `POST /knowledge/reindex-legislation` |
| **knowledge_catalog populado** | — | **Vazio** (re-indexação dos 25 docs aguarda autorização) |

---

## 2. Decisões arquiteturais confirmadas (registradas em memória 1031)

1. **Skills do sistema** vs **skills públicas do tenant** — sistema tem skills próprias (escritas por nós); tenants podem ter espaço público de skills que o sistema pode aproveitar (curadoria manual para promover ao nível do produto). Marketplace peer-to-peer **não** entra no V1.
2. **knowledge_catalog genérico** (não específico de legislação) — aceita `legislation`, `oficio`, `manual`, `jurisprudence`, `skill`, `other`. Schema com `source_type` + `source_ref` para qualquer fonte.
3. **Provider de embeddings:** Gemini `text-embedding-004` (já configurado, gratuito até 1500 RPM, dim 768).
4. **Chunking:** híbrido (estrutura legislativa quando detectada, janela deslizante caso contrário).
5. **Endpoint REST + uso interno** pelos agentes (caminho i, não apenas função privada).

---

## 3. Arquivos novos (10) e modificados (4)

### Novos
- [docker/db/Dockerfile](../docker/db/Dockerfile) — imagem custom `postgis/postgis:15-3.3` + `postgresql-15-pgvector`
- [alembic/versions/f9d2e8c1a4b3_sprint_u_knowledge_catalog.py](../alembic/versions/f9d2e8c1a4b3_sprint_u_knowledge_catalog.py) — migration: `CREATE EXTENSION vector` + tabela com 9 índices
- [app/models/knowledge_catalog.py](../app/models/knowledge_catalog.py) — `KnowledgeChunk` + `SourceType` enum + tipo opaco `_Vector`
- [app/services/embeddings.py](../app/services/embeddings.py) — wrapper Gemini via `httpx` direto (single + batch)
- [app/services/chunking.py](../app/services/chunking.py) — chunking híbrido com regex de marcadores legislativos
- [app/services/knowledge_catalog.py](../app/services/knowledge_catalog.py) — `index_legislation_document` / `index_text` / `search` (idempotente via `content_hash`)
- [app/workers/knowledge_indexer.py](../app/workers/knowledge_indexer.py) — 3 tasks Celery
- [app/schemas/knowledge.py](../app/schemas/knowledge.py) — Pydantic v2
- [app/api/v1/knowledge.py](../app/api/v1/knowledge.py) — router com 3 endpoints

### Modificados
- [docker-compose.yml](../docker-compose.yml) — `db` agora usa `build:` ao invés de `image:`
- [app/main.py](../app/main.py) — registra router `knowledge`
- [app/models/__init__.py](../app/models/__init__.py) — exporta `KnowledgeChunk, SourceType`
- [app/workers/__init__.py](../app/workers/__init__.py) — importa as 3 tasks novas

---

## 4. Schema da tabela `knowledge_catalog`

```
id              bigserial PK
tenant_id       int  NULL  → tenants(id) ON DELETE CASCADE  (NULL = global)
source_type     varchar(50)  NOT NULL    -- legislation | oficio | manual | jurisprudence | skill | other
source_ref      varchar(255) NOT NULL    -- ex: "legislation_documents:42" ou "oficio:5"
chunk_index     int  NOT NULL  default 0
title           varchar(500)
section         varchar(255)             -- ex: "Art. 12", "Capítulo III"
chunk_text      text NOT NULL
chunk_tokens    int  NOT NULL  default 0
jurisdiction    varchar(20)              -- federal | estadual | municipal
uf              varchar(2)
agency          varchar(100)
identifier      varchar(255)             -- ex: "Lei 12.651/2012"
effective_date  date
embedding       vector(768)              -- gravado/lido via SQL puro
embedding_model varchar(100)             -- "text-embedding-004"
embedding_dim   int                      -- 768
content_hash    varchar(64) UNIQUE NOT NULL  -- sha256(source_type|source_ref|chunk_index|body)
extra_metadata  jsonb
created_at      timestamptz default now()
updated_at      timestamptz
```

**Índices:**
- `ix_knowledge_catalog_source` (source_type, source_ref)
- `ix_knowledge_catalog_uf`, `ix_knowledge_catalog_jurisdiction`, `ix_knowledge_catalog_identifier`
- `ix_knowledge_catalog_content_hash` UNIQUE
- `ix_knowledge_catalog_metadata` GIN (extra_metadata)
- `ix_knowledge_catalog_embedding_cosine` IVFFlat vector_cosine_ops WITH (lists=100)

---

## 5. Smoke test passou

| Teste | Status |
|---|---|
| `docker compose build db` | ✅ |
| `docker compose up -d` (db, redis, minio, api, worker, portal saudáveis) | ✅ |
| `pg_extension` mostra `vector 0.8.2` | ✅ |
| `\d knowledge_catalog` confirma 21 colunas + 9 índices | ✅ |
| `/health` → 200 | ✅ |
| `/api/v1/openapi.json` lista os 3 endpoints novos | ✅ |

---

## 6. Próximos passos (continuação amanhã)

### Imediato
1. **Disparar re-indexação dos 25 documentos:**
   ```bash
   docker compose exec api python -c \
     "from app.workers.knowledge_indexer import reindex_all_legislation; reindex_all_legislation.delay()"
   ```
   - Custo: $0 (Gemini grátis)
   - Tempo: ~2–5 min (1.69M tokens em batches de 100)
   - Idempotente

2. **Smoke test de busca** via Swagger (`http://localhost:8000/docs`):
   - "intervenção em APP" — deveria retornar trechos da CONAMA 369/2006
   - "regularização ambiental Goiás" — coletânea regularização GO 2024
   - "cancelamento de CAR" — IN SEMAD 09/2024

3. **Avaliar qualidade** dos chunks retornados antes de plugar no agente.

### Curto prazo
4. **Atualizar agente `legislacao`** para chamar `knowledge_catalog.search()` antes da geração da resposta — injetar top-k chunks no contexto Gemini ao invés de mandar `full_text` inteiro. Reduz custo e melhora foco.

5. **Sprint 1 (Skills)** — destravada quando a sócia chegar com 2-3 PDFs de ofícios "bem feitos":
   - **Tarefa A:** estrutura `app/skills/public/{redator,extrator}/`
   - **Tarefa B:** registry com fallback tenant → public
   - **Tarefa C:** integração no `BaseAgent` (compila skill no system prompt)
   - **Tarefa D:** primeira skill `redator/oficio_semad` ponta-a-ponta

### Médio prazo
6. **Indexar ofícios e modelos da sócia** no `knowledge_catalog` quando chegarem (já tem 2 modelos `.docx` de Anuência/Desembargo na pasta `legislacao/`).

7. **Avaliar IVFFlat → HNSW** quando o catálogo passar de ~50k linhas (HNSW tem recall melhor mas usa mais memória).

8. **Fila de re-embedding** automática quando `legislation_documents.full_text` mudar (hoje é manual).

---

## 7. Decisões pendentes para a sócia (carregadas da Sprint 1)

1. Quais 2-3 PDFs de ofícios "bem feitos" servem como gabarito?
2. Confirmar Decisão 1 (skills do tenant em MinIO, sem tabela `skills` no Postgres no V1).
3. Confirmar Decisão 2 (skills compiladas no system_prompt na instanciação, não tool dinâmica).

---

## 8. Estado operacional pós-Sprint U

| Controle | Estado |
|----------|--------|
| Docker stack | api, worker, db (custom), redis, minio, client-portal — todos saudáveis |
| Migrations aplicadas | head: `f9d2e8c1a4b3` |
| pgvector | 0.8.2 instalado |
| `knowledge_catalog` | 0 linhas (re-indexação não disparada) |
| `legislation_documents` | 25 docs, 1.69M tokens, todos `indexed` |
| Endpoints novos | 3 (`/knowledge/*`) |
| Custo desta sessão (IA) | $0.00 (nenhuma chamada de modelo) |
| Restrição "não mexer em agentes" | Respeitada — 0 alterações em `app/agents/` |
| Tests | Não rodados nesta sessão (mudanças puramente aditivas + smoke test manual) |

---

## 9. Observações para retomada

- **Imagem custom do Postgres** agora exige `docker compose build db` ao trocar de máquina/CI. Tag local: `amigao_do_meio_ambiente-db:latest`.
- **GEMINI_API_KEY** precisa estar no `.env` para os endpoints de busca/index funcionarem. Se ausente, retorna `503 Service Unavailable` com mensagem clara.
- **`embedding` é coluna `vector(768)`** — não tem reflexão automática no SQLAlchemy. Inserts e queries usam SQL puro em `app/services/knowledge_catalog.py`. Não tente fazer `chunk.embedding = [...]` direto no ORM.
- **Idempotência via `content_hash`** — mesma fonte/chunk não duplica. Re-indexar é seguro.
- **Lists=100 no IVFFlat** funciona bem até ~100k linhas. Quando crescermos, ajustar para `~sqrt(n_rows)`.
