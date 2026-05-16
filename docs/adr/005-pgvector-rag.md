# ADR-005 · pgvector como motor de RAG e busca semântica

**Status:** Aceito
**Data:** 2026-04-27 (Sprint U); formalizada como ADR em 2026-05-15
**Decisores:** tecnologia
**Substitui:** [`./003-mempalace-REVOKED.md`](./003-mempalace-REVOKED.md) (parcialmente — a parte de "memória vetorial")

---

## Contexto

Após a revogação do MemPalace (ADR-003), o Regente precisava de uma solução para **dois casos de uso vetoriais distintos**:

1. **Base regulatória semântica** — buscar trechos de legislação por similaridade ("retificação CAR APP < 50m de curso d'água") — necessária para o `LegislacaoAgent` e para o `citation_evaluator`
2. **Memória dos agentes** — recuperar casos anteriores similares para informar o agente atual

Opções consideradas no mercado:

- **pgvector** — extensão PostgreSQL nativa
- **Pinecone / Weaviate / Qdrant** — vector DBs gerenciados
- **Chroma** — vector DB local em Python
- **Milvus** — open-source, alta performance

O Regente já roda Postgres como banco principal. A pergunta: vale subir um vector DB separado, ou manter tudo num só motor?

## Decisão

**pgvector como motor único** de busca semântica e (futuramente) memória dos agentes.

Materializado em:

- **Extensão pgvector** instalada na imagem custom do Postgres (`docker/db/Dockerfile`)
- **Tabela `knowledge_catalog`** com coluna `embedding vector(768)` e ~9 índices (btree + GIN + IVFFlat cosine)
- **Serviço `app/services/knowledge_catalog.py`** com função `search()` que faz query em SQL puro (cosine distance via operador `<=>`) para evitar dependência do pacote Python `pgvector` no ORM
- **Geração de embeddings via LiteLLM** (mesmo gateway que faz LLM): OpenAI `text-embedding-3-small` com `dimensions=768` explícito ou Gemini `text-embedding-004` (768 dim nativo — base histórica da Sprint U)

Sobre o segundo caso de uso (memória dos agentes): **deprorizado**. A decisão implícita foi que **base de conhecimento curada** vale mais que **memória auto-aprendida**, especialmente em domínio regulatório onde reproduzir aprendizado errado é mais perigoso que esquecer.

## Consequências

**Positivas:**
- **Um único motor de dados** — backup, replicação, monitoramento, ops em geral é unificado
- **Custo zero adicional** — extensão já vem em imagens Postgres comuns
- **Joins SQL nativos** — `JOIN knowledge_catalog ON tenant_id` etc. funciona como qualquer query
- **Transações ACID** — mudanças no `knowledge_catalog` participam de transação com outras tabelas (importante quando ingestão de legislação cria `LegislationDocument` + chunks no mesmo commit)
- **Multi-tenant nativo** — `tenant_id` (NULL = global) usa o mesmo padrão da arquitetura
- **Performance suficiente** — IVFFlat index resolve dezenas de milhares de chunks com latência < 100ms
- **Sem dependência adicional** — não precisa subir nem operar outro componente

**Negativas:**
- **Escala** — quando o volume passar de 1M-10M chunks, pgvector com IVFFlat começa a ficar limitado vs vector DBs especializados
- **Sem features avançadas** — sem reranking embutido, sem hybrid search keyword+vetor out-of-the-box (precisamos implementar manualmente quando precisar)
- **Dim fixa em 768** — coluna `vector(768)` decidida pra compat com Gemini histórico; trocar pra outra dim exige re-indexação completa dos 22.573 chunks
- **ORM SQLAlchemy** sem suporte nativo a operador `<=>` — query é SQL puro (compensação: claro e auditável)

**Mitigações:**
- Migração para vector DB especializado é caminho documentado quando volume crescer (sem urgência hoje)
- Coluna `vector(768)` é a aposta de curto/médio prazo (compat com base histórica em Gemini); migração futura pra 1024 ou 1536 — caso providers de embedding consolidem nessas dim — implica re-indexação total documentada

## Estratégia de embedding

| Provider | Modelo | Dim configurada | Custo (entrada) | Uso |
|---|---|---|---|---|
| OpenAI | `text-embedding-3-small` | 768 (explícito via `dimensions=768`) | ~$0.02 / 1M tokens | Default atual |
| Gemini | `text-embedding-004` | 768 (nativo) | grátis até 1500 RPM | Uso inicial Sprint U, base histórica |

Dim 768 foi escolhida pra compatibilidade com a base histórica gerada inicialmente em Gemini. OpenAI `text-embedding-3-small` suporta `dimensions=768` reduzindo o vetor padrão de 1536. Coluna `knowledge_catalog.embedding` declarada como `vector(768)`.

Migração para OpenAI ocorreu na Sprint W (qualidade superior em PT-BR técnico). Re-indexação total foi executada (~22.573 chunks).

## Estratégia de chunking

Híbrida em `app/services/chunking.py`:

**1. Estruturada (preferida)** — para legislação. Regex captura `Art. N`, `Capítulo N`, `Seção N`. Cada artigo vira chunk com unidade lógica preservada.

**2. Janela deslizante (fallback)** — para texto não-estruturado (manuais, ofícios). 800 tokens, overlap de 100.

Decisão de design: prefere preservar **unidade lógica** (artigo de lei) a uniformidade de tamanho. Trade-off aceito: chunks variam de 50 a 2000 tokens; busca semântica adapta.

## Cobertura atual

22.573 chunks indexados em 4 jurisdições:

| Jurisdição/UF | Chunks |
|---|---|
| Federal | 720 |
| GO | 3.855 |
| MS | 4.587 |
| MT | 13.411 |

Próximos UFs: SP, MG, TO (semana de 19-23/05).

## Status de execução

| Item | Estado |
|---|---|
| Extensão pgvector na imagem custom | ✅ |
| Tabela `knowledge_catalog` com índices | ✅ Sprint U |
| Serviço `knowledge_catalog.py` com `search()` | ✅ |
| Geração de embeddings via LiteLLM | ✅ |
| Chunking híbrido | ✅ |
| Ingestão inicial federal + GO | ✅ Sprint 0 |
| Ingestão MS + MT | ✅ Sprint W |
| `citation_evaluator` consumindo a base | ✅ Sprint A1 |
| Filtro `demand_types` em busca | ✅ Sprint -1 C |
| Re-indexação automática quando provider muda | ❌ Pendente (`scripts/reindex_sync.py` manual hoje) |
| Hybrid search (keyword + vetor) | ❌ Pendente, sem urgência |
| Reranking pós-recall | ❌ Pendente, sem urgência |

## Relação com outros ADRs

- [`./003-mempalace-REVOKED.md`](./003-mempalace-REVOKED.md) — substituído por este ADR no que diz respeito a vetorização
- [`./002-multi-llm-gateway.md`](./002-multi-llm-gateway.md) — embeddings consomem o mesmo gateway
- [`./006-skills-procedurais.md`](./006-skills-procedurais.md) — skills podem futuramente entrar no `knowledge_catalog` como `source_type='skill'`
