# Base Regulatória (RAG)

**Documento:** Arquitetura · referência viva
**Estado:** atualizar quando estratégia de embedding/chunking mudar ou novos UFs forem ingeridos
**Última revisão:** 2026-05-15
**Estado real:** 22.573 chunks em 4 UFs (GO, MS, MT, Federal)

---

A base de conhecimento regulatório do Regente Ambiental — como ela é curada, indexada, consultada e mantida atualizada. Esta base é o que dá fundamento legal a tudo que os agentes IA produzem.

## Princípio

**Citação rastreável é princípio inegociável** (manifesto, Princípio 2). Toda referência legal gerada por agente é confrontada contra esta base. Citação que não existe aqui é marcada como suspeita.

Isso só funciona se a base for: **completa o suficiente** (cobre as normas aplicáveis), **curada** (não tem lixo), **rastreável** (chunk lookup leva ao texto original), e **atualizada** (acompanha mudanças normativas).

## Arquitetura

### Modelos envolvidos

| Modelo | Tabela | Função |
|---|---|---|
| `LegislationDocument` | `legislation_documents` | Diploma legal (lei, decreto, resolução, IN). Metadado + arquivo original. |
| `KnowledgeChunk` | `knowledge_catalog` | Chunk indexável (pedaço de texto + embedding vetorial). |
| `LegislationAlert` | `legislation_alerts` | Alerta gerado por mudança normativa relevante. |

### Serviços

| Serviço | Local | Função |
|---|---|---|
| `legislation_service.py` | `app/services/` | CRUD de diplomas, ingestão, re-indexação |
| `legislation_monitor.py` | `app/services/` | Crawlers e detecção de novidades |
| `knowledge_catalog.py` | `app/services/` | Busca semântica (similaridade cosseno) |
| `embeddings.py` | `app/services/` | Geração de embeddings via LiteLLM |
| `chunking.py` | `app/services/` | Estratégia de chunking híbrida |

### Crawlers (esqueleto pronto, não ativos)

| Crawler | Local | Função |
|---|---|---|
| `dou_crawler.py` | `app/services/crawlers/` | Diário Oficial da União |
| `doe_crawler.py` | `app/services/crawlers/` | Diários Oficiais Estaduais |
| `ibama_crawler.py` | `app/services/crawlers/` | Portal IBAMA |

User-Agent identificável: `Regente-Ambiental/1.0 (monitoramento-legislativo)`.

## Estratégia de embedding

### Provider atual

- **OpenAI** `text-embedding-3-small` — usado com `dimensions=768` explícito
- Custo: ~$0.02 / 1M tokens (extremamente barato)
- Vantagem: melhor qualidade em PT-BR técnico (legal/ambiental)
- **Dim 768 (não 1536 default)** — escolha consciente pra compatibilidade com base histórica gerada em Gemini `text-embedding-004` (768 nativo). Mudar dim implica re-indexação completa de 22.573 chunks.

### Histórico

- Início (Sprint U, 27/04): Gemini `text-embedding-004` (768 dim, grátis até 1500 RPM)
- Migração (Sprint W): para OpenAI `text-embedding-3-small` (qualidade superior em PT-BR)

A coluna `knowledge_catalog.embedding` é declarada como `vector(768)` no PostgreSQL (compat com base histórica em Gemini `text-embedding-004`). Mudança de dim no futuro exige re-indexação completa.

## Estratégia de chunking

### Híbrida

`app/services/chunking.py` decide chunking automaticamente:

**1. Estruturada (preferida)** — quando o documento tem marcadores legislativos detectáveis:

```regex
\bArt\.\s*\d+
\bCapítulo\s+[IVXLCDM]+
\bSeção\s+[IVXLCDM]+
\bTítulo\s+[IVXLCDM]+
```

Cada artigo (ou seção curta) vira um chunk. Vantagem: preserva unidade lógica da norma. Lei 12.651/2012 vira ~150 chunks bem delimitados.

**2. Janela deslizante (fallback)** — quando não há estrutura clara:

- Tamanho: 800 tokens
- Overlap: 100 tokens

Usado em: documentos não-estruturados (manuais, jurisprudências, ofícios curados).

## Estrutura do `KnowledgeChunk`

```python
class KnowledgeChunk:
    id: int
    tenant_id: int | None        # NULL = global
    source_type: SourceType      # legislation | oficio | manual | jurisprudence | skill | other
    source_ref: str              # ID do documento original (legislation_document_id, file_id, etc.)
    chunk_index: int             # ordem dentro do documento
    chunk_text: str              # texto do chunk
    embedding: vector(768)       # pgvector
    title: str | None            # título do documento ("Lei 12.651/2012")
    section: str | None          # "Art. 3º", "Capítulo II", etc.
    identifier: str | None       # "Lei 12.651/2012"
    jurisdiction: str | None     # "federal" | "estadual" | "municipal"
    uf: str | None               # "GO", "MS", etc.
    agency: str | None           # "SEMAD", "IBAMA", "ICMBio", etc.
    demand_types: list[str]      # JSONB array — filtragem por tipo de demanda
    indexed_at: datetime
```

`tenant_id IS NULL` = chunk global (visível a todos os tenants). Útil para legislação pública (toda lei é compartilhada).

## Busca semântica

### Endpoint

`GET /api/v1/knowledge/search`

### Função interna

`app/services/knowledge_catalog.py:search()` aceita:

| Parâmetro | Tipo | Default | Uso |
|---|---|---|---|
| `query` | str | (obrigatório) | Texto da consulta |
| `tenant_id` | int? | None | Filtro por tenant + globais |
| `source_type` | str? | None | legislation, oficio, etc. |
| `jurisdiction` | str? | None | federal, estadual, municipal |
| `uf` | str? | None | GO, MS, MT, etc. |
| `agency` | str? | None | SEMAD, IBAMA, etc. |
| `identifier` | str? | None | "Lei 12.651/2012" |
| `demand_types` | list[str]? | None | Filtra documentos com `demand_types` em comum |
| `limit` | int | 10 | máximo retornado |
| `min_similarity` | float | 0.7 | corte de relevância |

### SQL puro (não usa ORM para o vector)

O ORM SQLAlchemy não tem suporte nativo a operador `<=>` (cosine distance) do pgvector sem importar o pacote `pgvector` Python. Para evitar essa dependência só pelo ORM, o serviço faz a query em SQL puro:

```sql
SELECT id, source_type, source_ref, title, section,
       identifier, chunk_text, jurisdiction, uf, agency,
       1 - (embedding <=> %s::vector) AS similarity
FROM knowledge_catalog
WHERE (tenant_id IS NULL OR tenant_id = %s)
  AND (%s IS NULL OR source_type = %s)
  AND ...
ORDER BY embedding <=> %s::vector
LIMIT %s;
```

Resultado retorna como `SearchResult` (dataclass) com campo `similarity` (0.0 a 1.0).

### Índices

`knowledge_catalog` tem 9 índices:

- btree em `tenant_id`, `source_type`, `uf`, `jurisdiction`, `identifier`
- GIN em `demand_types` (JSONB)
- IVFFlat em `embedding` (cosine distance) — para busca aproximada rápida
- 2 índices compostos para os padrões de query mais comuns

## Como uma norma chega na base

### Caminho 1 — Ingestão manual (hoje)

```bash
# Federal canônicos
python scripts/ingest_federais_canonicos.py

# Estadual (GO/MS/MT)
python scripts/ingest_legislacao_estadual.py --uf GO

# Pasta da sócia (curadoria interna)
python scripts/ingest_pasta_socia.py /caminho/da/pasta
```

Cada script:
1. Lê PDFs/HTMLs locais
2. Extrai texto (pypdf ou parser HTML)
3. Cria `LegislationDocument` com metadado
4. Chunka o texto (estrutura ou janela)
5. Gera embeddings em batch (até 100 textos por chamada)
6. Inserts em `knowledge_catalog`
7. Marca `LegislationDocument.status = 'indexed'`

### Caminho 2 — Crawler periódico (futuro)

Quando os crawlers estiverem ativos:

1. Celery Beat aciona `monitor_legislation_dou` às 06:00 BRT
2. Crawler busca novidades publicadas desde a última execução
3. Para cada novidade relevante (filtro: keywords ambientais, jurisdição):
   - Cria `LegislationDocument`
   - Enfileira task de indexação
   - Cria `LegislationAlert` para tenants que monitoram a norma
4. Task de indexação processa o chunking + embedding
5. Notifica via WebSocket os tenants alertados

## Cobertura atual

| Jurisdição/UF | Chunks | Status |
|---|---|---|
| Federal | 720 | Núcleo: Código Florestal (Lei 12.651/2012), LGPD (Lei 13.709/2018), PNMA (Lei 6.938/1981), Resoluções CONAMA principais |
| GO | 3.855 | Lei 18.104/2013 + decretos + IN SEMAD |
| MS | 4.587 | Lei estadual + decretos + IN SEMADESC/IMASUL |
| MT | 13.411 | Lei estadual + decretos + IN SEMA (volume alto por causa de cobertura mais ampla) |
| **Total** | **22.573** | — |

Próximos UFs na fila (semana de 19-23/05): SP, MG, TO.

## Re-indexação

Quando muda o provider de embeddings, ou quando a estratégia de chunking evolui, precisa re-indexar tudo:

```bash
# Endpoint admin
POST /api/v1/knowledge/reindex-legislation
{
  "uf": "GO",   # opcional — só reindex GO
  "force": true
}
```

Backend:
- Enfileira task `reindex_legislation`
- Itera por `LegislationDocument.status='indexed'` (ou todos com `force=true`)
- Re-chunka, re-embed, sobrescreve `knowledge_catalog` rows
- Idempotente (chunks têm UNIQUE constraint em `source_ref + chunk_index`)

## Citation evaluator (visão de consumo)

Após o agente Redator gerar peça, o `citation_evaluator`:

1. Extrai todas as citações do texto (regex multi-formato cobre `Lei N/AAAA`, `Decreto N/AAAA`, `Resolução CONAMA N/AAAA`, etc.)
2. Para cada citação, faz lookup em `knowledge_catalog` por `identifier`
3. Citação que não bate com nenhum chunk → suspeita
4. Citação que bate → vincula `chunk_id` no `CitationRef`

Detalhes em [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md).

## Auditabilidade

Cada `KnowledgeChunk` mantém:
- `source_ref` — aponta para o `LegislationDocument` original
- `chunk_index` — posição dentro do documento
- `indexed_at` — quando foi indexado

`LegislationDocument` mantém:
- `original_file_path` — arquivo PDF/HTML no MinIO
- `source_url` — URL pública (DOU, planalto.gov.br, al.go.gov.br, etc.)
- `hash` — SHA-256 do conteúdo
- `published_at` — data de publicação

Permite, para qualquer citação: encontrar o chunk → encontrar o documento → ler o original.

## Pendências e dívidas

1. **Crawlers DOU/DOE/IBAMA não ativos em produção.** Esqueleto + classes prontas; falta habilitar schedule e monitorar primeiras semanas.
2. **Cobertura limitada a 4 UFs.** SP, MG, TO entram semana de 19-23/05. Cobertura nacional só na janela 3 do roadmap.
3. **Sem ingestão de ofícios curados da sócia.** Existe script (`ingest_pasta_socia.py`), mas nenhum ofício ingerido ainda. Skills do Redator desbloqueiam esse caminho.
4. **Sem ingestão de jurisprudência.** Roadmap longo prazo.
5. **Re-indexação manual.** Não há gatilho automático quando provider de embedding muda.
6. **`min_similarity = 0.7` é heurístico.** Avaliar se está pegando relevância demais ou de menos.

## Próximas leituras

- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — como o citation evaluator consome essa base
- [`INTEGRACOES_GOVTECH.md`](./INTEGRACOES_GOVTECH.md) — crawlers e estratégia de ingestão
- [`MODELO_DE_DADOS.md`](./MODELO_DE_DADOS.md) — schema completo de `KnowledgeChunk`
