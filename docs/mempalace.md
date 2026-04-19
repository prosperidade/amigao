# MemPalace — Memoria de Longo Prazo para IA

## O que e

MemPalace e um sistema open-source (MIT) de memoria persistente para LLMs. Funciona como um "Palacio da Memoria" digital: armazena absolutamente tudo (decisoes, debug, raciocinio, resultados) em uma estrutura semantica local, usando ChromaDB (busca vetorial) + SQLite (knowledge graph).

**Score**: 96.6% no benchmark LongMemEval (maior registrado sem API externa).
**Custo**: 100% local, zero chamadas de nuvem para memoria.
**Versao instalada**: 3.0.0

---

## Por que usamos no Amigao

### Problema
- Cada sessao de IA comeca do zero (amnesia de sessao)
- Reinserir historico = explosao de tokens ($507/ano/dev com RAG tradicional)
- Agentes de producao nao aprendem entre execucoes

### Solucao
- Startup com ~170 tokens (vs 650k de RAG tradicional)
- Reducao de custo de ate 98% ($10/ano/dev)
- Agentes acumulam conhecimento ao longo do tempo
- Knowledge graph conecta processos, decisoes e agentes

### Vantagens em producao
1. **Agentes com memoria**: legislacao lembra que ja analisou 15 casos similares em MT
2. **Knowledge graph cumulativo**: conecta processos → agentes → decisoes → confianca
3. **Cross-tenant intelligence**: padroes anonimizados entre tenants (ex: "CAR em MT leva ~45 dias")
4. **Auditoria enriquecida**: diary guarda raciocinio, nao so resultado
5. **Busca semantica gratis**: ChromaDB local no container, sem API

---

## Arquitetura — 5 Camadas

```
Wing (Ala)
  └── Room (Sala)
       └── Hall (Corredor) — tipos: facts, events, discoveries, preferences, advice
            └── Closet (Armario) — resumo AAAK comprimido (~30x)
                 └── Drawer (Gaveta) — transcricao verbatim original
```

**Tunnels (Tuneis)**: cross-references automaticos entre rooms homonimas de wings diferentes.

### Niveis de carregamento
| Nivel | Conteudo | Tokens |
|-------|----------|--------|
| L0 | Identidade da IA, projeto | ~50 |
| L1 | Fatos criticos em AAAK | ~120 |
| L2 | Room recall (sob demanda) | variavel |
| L3 | Semantic search ChromaDB (sob demanda) | variavel |

**Startup = L0 + L1 = ~170 tokens**

### AAAK (Artificial Agent Abstract Knowledge)
Dialeto de compressao ~30x. Nao requer decoder nem fine-tuning. Interpretado nativamente por Claude, GPT, Llama, Mistral.

---

## Estrutura no Amigao

### Wing principal: `amigao_do_meio_ambiente`

### Rooms (27 mapeadas):

**Backend Core:**
- `app_core` — config, security, celery, logging, metrics, ai_gateway
- `app_models` — SQLAlchemy ORM (16 entidades)
- `app_api` — FastAPI routers (14 routers), deps, middleware
- `app_services` — business logic
- `app_workers` — Celery tasks
- `app_schemas` — Pydantic DTOs
- `app_repositories` — data access layer
- `alembic` — database migrations

**Agentes IA (1 room por agente):**
- `agent_atendimento` — qualificacao de lead, classificacao de demanda
- `agent_extrator` — extracao de campos de documentos via OCR+LLM
- `agent_diagnostico` — analise da situacao do imovel
- `agent_redator` — geracao de documentos formais (PRAD, oficios, propostas)
- `agent_orcamento` — geracao de orcamento com escopo detalhado
- `agent_financeiro` — analise financeira e projecao de custos
- `agent_acompanhamento` — monitoramento de email/respostas de orgaos
- `agent_vigia` — monitoramento agendado (prazos, documentos, custos)
- `agent_marketing` — geracao de conteudo para campanhas
- `agent_legislacao` — enquadramento regulatorio (RAG sobre legislacao)
- `agents_core` — framework base (BaseAgent, orchestrator, validators)

**Frontend:**
- `frontend` — React + Vite (dashboard interno)
- `client_portal` — Next.js 16 (portal do cliente)
- `mobile` — Expo React Native

**Infra & Ops:**
- `docker` — Docker Compose
- `testing` — pytest
- `documentation` — docs do projeto
- `ops` — scripts operacionais
- `general` — root config, CI/CD

---

## Arquivos do projeto

### Criados
| Arquivo | Funcao |
|---------|--------|
| `app/agents/memory.py` | Modulo helper — todas as operacoes MemPalace (fire-and-forget) |
| `mempalace.yaml` | Configuracao de wing/rooms do projeto |
| `entities.json` | Entidades detectadas pelo `mempalace init` |
| `.git/hooks/post-commit` | Hook que salva contexto de cada commit no palace |

### Modificados
| Arquivo | Mudanca |
|---------|---------|
| `app/agents/base.py` | `palace_room` + `recall_memory()`, `remember()`, `remember_fact()` + auto-log no `run()` |
| `app/agents/orchestrator.py` | `_mempalace_log_chain()` — loga chains completas |
| `app/agents/atendimento.py` | `palace_room = "agent_atendimento"` |
| `app/agents/extrator.py` | `palace_room = "agent_extrator"` |
| `app/agents/diagnostico.py` | `palace_room = "agent_diagnostico"` |
| `app/agents/legislacao.py` | `palace_room = "agent_legislacao"` |
| `app/agents/redator.py` | `palace_room = "agent_redator"` |
| `app/agents/orcamento.py` | `palace_room = "agent_orcamento"` |
| `app/agents/financeiro.py` | `palace_room = "agent_financeiro"` |
| `app/agents/acompanhamento.py` | `palace_room = "agent_acompanhamento"` |
| `app/agents/vigia.py` | `palace_room = "agent_vigia"` |
| `app/agents/marketing.py` | `palace_room = "agent_marketing"` |
| `requirements.txt` | `mempalace>=3.0.0` adicionado |
| `docker-compose.yml` | Volume `mempalace_data` + `mempalace init` no startup (api + worker) |
| `.gitignore` | `.mempalace/` e `entities.json` excluidos |

---

## Como funciona — Automatico

### A cada execucao de agente (`agent.run()`):
1. **Diary entry** gravado: sucesso/falha, confianca, duracao, contexto resumido
2. **Knowledge graph fact** adicionado: `process_X → analyzed_by_legislacao → confidence=high`
3. Nenhuma acao humana necessaria

### A cada chain do orchestrator:
1. **Diary entry**: `[CHAIN OK] diagnostico_completo agents=[extrator,legislacao,diagnostico] ms=4500`
2. **KG fact**: `process_42 → chain_diagnostico_completo_completed → agents=extrator,legislacao,diagnostico`

### A cada git commit (hook post-commit):
1. Captura: mensagem, arquivos alterados, diff stat, branch, timestamp
2. Salva no palace wing `amigao_do_meio_ambiente`, room `general`, hall `hall_events`

---

## Como usar — Acoes do desenvolvedor

### No Claude Code / AntiGravity (IDE):
```
# Inicio de sessao — buscar contexto
"busca no mempalace o que ja fizemos sobre tenant isolation"

# Apos decisao importante — salvar
"salva no mempalace que decidimos usar CONAMA 237 art. 10 para licenciamento em SP"

# Ver historico de um agente
"mostra o diary do agente legislacao"

# Ver knowledge graph
"quais fatos existem sobre process_42 no mempalace?"
```

### No codigo Python (dentro de agentes):
```python
# Em qualquer execute() de agente:

# 1. Buscar contexto historico
memory = self.recall_memory("licenciamento CONAMA 237 em MT")
# Retorna: { "recent_diary": [...], "search_results": [...] }

# 2. Salvar nota manualmente
self.remember("Decisao: usar CONAMA 237 art. 10 para este caso")

# 3. Salvar fato estruturado no knowledge graph
self.remember_fact("CONAMA_237", "regula", "licenciamento_ambiental")
```

### Via modulo memory.py diretamente:
```python
from app.agents.memory import (
    diary_write, diary_read, kg_add, kg_query,
    search, save_to_room, recall_agent_context,
)

# Busca semantica
results = search("agente regulatorio legislacao", room="agent_legislacao", limit=5)

# Diary de um agente
entries = diary_read("legislacao", last_n=10)

# Knowledge graph
kg_add("ibama", "fiscaliza", "licenciamento_federal")
facts = kg_query("ibama")
```

---

## Como usar — MCP Server (19 tools)

O MemPalace esta configurado globalmente no Claude Code via MCP:

```json
// ~/.claude.json
"mcpServers": {
  "mempalace": {
    "type": "stdio",
    "command": "python",
    "args": ["-m", "mempalace.mcp_server"]
  }
}
```

### Tools disponiveis:
| Tool | Funcao |
|------|--------|
| `tool_search` | Busca semantica no palace |
| `tool_add_drawer` | Salva conteudo numa wing/room |
| `tool_diary_write` | Escreve diario de um agente |
| `tool_diary_read` | Le diario recente de um agente |
| `tool_kg_add` | Adiciona fato ao knowledge graph |
| `tool_kg_query` | Consulta entidade no grafo |
| `tool_kg_timeline` | Timeline cronologica de fatos |
| `tool_kg_invalidate` | Marca fato como obsoleto |
| `tool_kg_stats` | Metricas do knowledge graph |
| `tool_find_tunnels` | Encontra conexoes entre wings |
| `tool_traverse_graph` | Navega o grafo a partir de uma room |
| `tool_list_wings` | Lista wings do palace |
| `tool_list_rooms` | Lista rooms de uma wing |
| `tool_status` | Estado geral do palace |
| `tool_get_aaak_spec` | Especificacao do dialeto AAAK |
| `tool_check_duplicate` | Verifica duplicatas antes de salvar |
| `tool_delete_drawer` | Remove entrada do palace |
| `tool_get_taxonomy` | Taxonomia completa do palace |
| `tool_graph_stats` | Estatisticas do grafo |

---

## Deploy — Docker

### Configuracao:
- **Volume persistente**: `mempalace_data:/root/.mempalace` (api + worker compartilham)
- **Init no startup**: `python -m mempalace init --yes . || true` (fire-and-forget)
- **Dependencia**: `mempalace>=3.0.0` em `requirements.txt`

### Re-indexar apos mudancas grandes:
```bash
# Local
python -m mempalace mine .

# Docker
docker compose exec api python -m mempalace mine .
```

### Backup do palace:
```bash
# O palace fica no volume Docker "mempalace_data"
docker run --rm -v amigao_do_meio_ambiente_mempalace_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/mempalace-backup.tar.gz /data
```

---

## Principio de design: Fire-and-Forget

**MemPalace NUNCA quebra a execucao de agentes.**

Toda operacao em `app/agents/memory.py`:
- Esta envolvida em `try/except`
- Falha silenciosamente com `logger.debug()`
- Retorna valor neutro (lista vazia, None)

Se o MemPalace nao estiver instalado, nao estiver inicializado, ou o ChromaDB falhar:
- Os agentes continuam rodando normalmente
- AIJob no PostgreSQL continua sendo gravado
- AuditLog continua funcionando
- Zero impacto no fluxo de negocio

---

## Comparativo de custos

| Abordagem | Tokens/Prompt | Custo Anual/Dev |
|-----------|--------------|-----------------|
| Historico completo | 19.5M (inviavel) | Impossivel |
| RAG/Resumos nativos | ~650k | ~$507/ano |
| MemPalace (L0+L1) | ~170 | ~$0.70/ano |
| MemPalace + 5 buscas/dia | ~13.5k | ~$10/ano |

---

## Links de referencia

- **GitHub**: github.com/milla-jovovich/mempalace
- **Deep-dive tecnico**: recca0120.github.io/en/2026/04/08/mempalace-ai-memory-system/
- **Reddit**: r/ContextEngineering — discussao sobre o sistema
- **Twitter**: @bensig (co-criador), @BrianRoemmele (deploy para 79 funcionarios)
- **Protocolo MCP**: modelcontextprotocol.io (padrao Anthropic)

---

## Integracao ativa nos agentes (2026-04-09)

### Auto-log em todos os agentes (BaseAgent.run())
Toda execucao de agente grava automaticamente:
- **Diary entry**: sucesso/falha, confianca, duracao, contexto resumido
- **Knowledge graph fact**: `process_X → analyzed_by_legislacao → confidence=high`

### MemPalace recall (agentes inteligentes)
Dois agentes usam `recall_memory()` ativamente:
- **legislacao**: busca casos regulatorios passados similares por demand_type + UF
- **diagnostico**: busca diagnosticos anteriores por state + biome + demand_type

O contexto recuperado e anexado ao prompt LLM como "CASOS ANTERIORES SIMILARES".

### Orchestrator
Cada chain logada no diary com: nome da chain, agentes executados, duracao, processo.
Knowledge graph: `process_X → chain_diagnostico_completo_completed → agents=extrator,legislacao,diagnostico`

### Metodos disponiveis em qualquer agente
```python
# Dentro de execute():
memory = self.recall_memory("licenciamento CONAMA 237 em MT")
self.remember("Decisao: usar CONAMA 237 art. 10")
self.remember_fact("CONAMA_237", "regula", "licenciamento_ambiental")
```

---

## Dados atuais do palace (2026-04-09)

- **Embeddings indexados**: 588+
- **Palace path local**: `~/.mempalace/palace/`
- **Palace path Docker**: `/root/.mempalace/palace/` (volume `mempalace_data`)
- **Agentes com diary ativo**: 10 (todos) + orchestrator
- **Agentes com recall ativo**: legislacao, diagnostico
- **MCP server**: configurado globalmente em `~/.claude.json`
- **Git hook**: `post-commit` ativo
- **IA providers**: OpenAI (gpt-4o-mini) + Gemini (legislacao contexto grande)
- **Custo medio/execucao**: ~$0.0004 - $0.0007
- **Primeira execucao real**: legislacao ($0.000651) + diagnostico ($0.000210) = $0.000861
