# Cruzamento Documentação × Código

**Data:** 2026-05-15
**Escopo:** Onda 3 — toda a documentação nova em `docs/manifesto/`, `docs/arquitetura/`, `docs/operacao/`, `docs/adr/`, `docs/estado/` + `README.md` raiz + `BLOCO5_PLANO_MIGRACAO.md`
**Método:** leitura dos 33 docs novos + verificação direta no código (grep, queries SQL no banco vivo, ls, contagens automatizadas)
**Conclusão:** documentação está **substancialmente correta**, com 11 inconsistências numéricas/de path identificadas e 1 inconsistência semântica crítica entre `README.md` e `seed.py`.

---

## 1. Resumo executivo

| Categoria | Inconsistências | Severidade |
|---|---|---|
| Numéricas (contagens declaradas vs reais) | 8 | Média (cosméticas, mas afetam confiança) |
| Schema técnico (dim de vetor, linha de código) | 2 | Alta (dim do embedding afeta entendimento do RAG) |
| Path / nome de arquivo | 1 | Baixa (typo) |
| Semântica entre dois docs vivos | 1 | **CRÍTICA** (credencial inválida no README) |
| Renomeação visível Amigão → Regente | 9 pontos confirmados como **PENDENTES** | Esperada — docs descreve trabalho a ser feito |

A maior parte das divergências numéricas pode vir de:
- **Trabalho Waitlist em stash** (mexe em `app/main.py`, `models/__init__.py`, `requirements.txt`, adiciona 1 router/migration/worker, 6 testes) — quando voltar do stash, alguns números se aproximam.
- **Renomeação visível** que os docs descrevem como em execução, e o código ainda está em modo legado.
- **Contagens otimistas** (testes 102 declarados vs 39 reais).

---

## 2. Inconsistências numéricas

### 2.1 Routers REST
- **Declarado:** "28 routers REST + WebSocket" — [`docs/estado/ESTADO_ATUAL.md`](./ESTADO_ATUAL.md) linha 15; [`docs/arquitetura/ARQUITETURA_GERAL.md`](../arquitetura/ARQUITETURA_GERAL.md) linha 21
- **Real:** `grep -c "include_router" app/main.py` retorna **26**
- **Provável causa:** Waitlist em stash adiciona `+1`; restante ainda divergente (28 vs 27 mesmo com Waitlist).
- **Correção sugerida:** verificar com Waitlist recuperado e atualizar contagem.

### 2.2 Migrations Alembic
- **Declarado:** "40 migrations aplicadas em produção" — [`docs/estado/ESTADO_ATUAL.md`](./ESTADO_ATUAL.md) linha 66
- **Real:** `ls alembic/versions/*.py | wc -l` retorna **38**
- **Provável causa:** Waitlist em stash adiciona `b1a2c3d4e5f6_sprint_b1_pre_cadastros.py` (+1); resta 1.

### 2.3 Arquivos de teste
- **Declarado:** "102 arquivos de teste em tests/" — [`docs/estado/ESTADO_ATUAL.md`](./ESTADO_ATUAL.md) linha 89
- **Real:** `find tests -name "test_*.py"` retorna **39 arquivos** (`*.py` total: 47, incluindo conftest e __init__)
- **Diferença:** 102 → 39 é muito grande pra ser truncamento. Provavelmente é contagem de **funções de teste** (não arquivos) confundida com arquivos.
- **Correção sugerida:** medir e atualizar. Sugestão: `pytest --collect-only -q | grep "test_" | wc -l` dá contagem real de testes.

### 2.4 Chains do orquestrador
- **Declarado:** "8 chains de orquestração" — [`docs/estado/ESTADO_ATUAL.md`](./ESTADO_ATUAL.md) linha 52; [`docs/arquitetura/ARQUITETURA_GERAL.md`](../arquitetura/ARQUITETURA_GERAL.md) linha 147
- **Real:** `app/agents/orchestrator.py:CHAINS` declara **9 chains**: `intake`, `diagnostico_completo`, `gerar_proposta`, `gerar_documento`, `analise_regulatoria`, `enquadramento_regulatorio`, `analise_financeira`, `monitoramento`, `marketing_content`
- **Correção sugerida:** atualizar para 9.

### 2.5 Telas do frontend
- **Declarado:** "38 telas em 10 áreas" — [`docs/estado/ESTADO_ATUAL.md`](./ESTADO_ATUAL.md) linha 83; [`docs/arquitetura/ARQUITETURA_GERAL.md`](../arquitetura/ARQUITETURA_GERAL.md) linha 91
- **Real:** `find frontend/src/pages -name "*.tsx"` retorna **36 .tsx** em 10 áreas (AI 2, Auth 1, Clients 2, Contracts 1, Dashboard 3, Intake 3, Processes 19, Properties 2, Proposals 2, Settings 1)
- **Áreas:** 10 ✓
- **Telas:** 36, não 38

### 2.6 Workers Celery
- **Declarado:** "11 módulos de tasks" — [`docs/arquitetura/ARQUITETURA_GERAL.md`](../arquitetura/ARQUITETURA_GERAL.md) linha 32
- **Real:** `ls app/workers/*.py` lista **10** módulos (ocr_tasks, ai_tasks, agent_tasks, intake_tasks, legislation_tasks, knowledge_indexer, webhook_tasks, pdf_generator, ai_summarizer, tasks)
- **Lista no doc também tem 10** itens (ARQUITETURA_GERAL linhas 33-41 + 42), mas o cabeçalho diz "11 módulos". Inconsistência interna ao próprio doc.
- **Provável causa:** Waitlist em stash adiciona `waitlist_tasks.py` (+1). Quando voltar do stash, 11 bate.

### 2.7 Serviços
- **Declarado:** "24 serviços" — [`docs/arquitetura/ARQUITETURA_GERAL.md`](../arquitetura/ARQUITETURA_GERAL.md) linha 72
- **Real:** `ls app/services/*.py | grep -v __init__` retorna **23**
- **Provável causa:** Waitlist em stash adiciona `resend_client.py` (+1).

### 2.8 Métricas Prometheus `amigao_*`
- **Declarado:** "13 métricas `amigao_*`" — [`docs/manifesto/02-IDENTIDADE.md`](../manifesto/02-IDENTIDADE.md) linha 71
- **Real:** `grep -c "amigao_" app/core/metrics.py` retorna **17 ocorrências**
- **Nota:** "17 ocorrências" não é "17 métricas únicas". Vale auditar com regex mais específica antes de corrigir o doc.

---

## 3. Inconsistências técnicas (schema)

### 3.1 Dimensão do vetor de embedding ⚠️
- **Declarado:** `vector(1536)` — [`docs/arquitetura/ARQUITETURA_GERAL.md`](../arquitetura/ARQUITETURA_GERAL.md) linhas 97 e 151
- **Real (query SQL direto no DB):** **`vector(768)`** em `knowledge_catalog.embedding`
- **Causa:** `app/services/embeddings.py` linha 38 define `EMBEDDING_DIM = 768`, e na chamada OpenAI passa `"dimensions": EMBEDDING_DIM` (linha 111) — o `text-embedding-3-small` é instanciado com **dim reduzida explicitamente para 768** pra manter compatibilidade com chunks indexados antes (era Gemini `text-embedding-004`, que é 768 nativo).
- **Correção sugerida no doc:**
  ```
  pgvector 0.8 (knowledge_catalog.embedding como vector(768))
  ...
  Embedding por OpenAI text-embedding-3-small com `dimensions=768`
  (reduzido pra compat com base histórica em Gemini text-embedding-004).
  ```
- **Severidade alta** porque quem leia o doc e tentar usar `text-embedding-3-small` no default `1536` vai gerar chunks incompatíveis com a base atual.

### 3.2 Linha de código citada
- **Declarado:** `AI_HOURLY_COST_LIMIT_USD = 5.0` (hardcoded em `ai_gateway.py:46`) — [`docs/arquitetura/GOVERNANCA_IA.md`](../arquitetura/GOVERNANCA_IA.md) linha 90
- **Real:** linha **48** (não 46)
- **Severidade baixa**, mas linha numérica afeta search-and-replace.

---

## 4. Inconsistência de path / nome de arquivo

### 4.1 `_env.example` vs `.env.example`
- **Declarado:** `_env.example:41` — [`docs/manifesto/02-IDENTIDADE.md`](../manifesto/02-IDENTIDADE.md) linha 44; também [`docs/estado/ESTADO_ATUAL.md`](./ESTADO_ATUAL.md) linha 97
- **Real:** arquivo é `.env.example` (com ponto no início, sem underscore)
- **Correção sugerida:** renomear no doc para `.env.example` em todas as ocorrências.

---

## 5. ⚠️ INCONSISTÊNCIA CRÍTICA — Credenciais seed

### 5.1 Email de seed entre `README.md` e `seed.py`
- **Declarado em `README.md` (raiz)** linhas 72-75:
  ```
  - admin@regenteambiental.com.br · Seed@2026 (superuser)
  - consultor@regenteambiental.com.br · Seed@2026
  - cliente@regenteambiental.com.br · Seed@2026
  - campo@regenteambiental.com.br · Seed@2026
  ```
- **Real em `seed.py`** linhas 248, 259, 269, 279, 291:
  ```
  email="admin@amigao.com"
  email="consultor@amigao.com"
  email="cliente@amigao.com"
  email="campo@amigao.com"
  ```
- **Impacto:** desenvolvedor novo lendo `README.md` tenta logar com `admin@regenteambiental.com.br` e **toma 401**. Bloqueio direto de onboarding.
- **Correção:** 2 opções
  - **(a)** Atualizar `seed.py` para os emails novos (impacta dados seedados existentes).
  - **(b)** Atualizar `README.md` para os emails antigos (admite que renomeação está em transição).
- **Recomendação:** (b) agora + (a) na sprint de renomeação visível. Adicionar nota no README explicitando: "estes ainda usam o codinome técnico `amigao` enquanto a renomeação não conclui — ver [`docs/manifesto/02-IDENTIDADE.md`](docs/manifesto/02-IDENTIDADE.md)".

---

## 6. Renomeação visível Amigão → Regente (esperada, confirmada como pendente)

[`docs/manifesto/02-IDENTIDADE.md`](../manifesto/02-IDENTIDADE.md) lista 9 pontos a serem renomeados. **Todos confirmados como ainda em `Amigão` no código** (coerente com a frase "Renomeação Amigão → Regente — em execução" do `ESTADO_ATUAL.md` linha 31):

| Arquivo | Linha | Conteúdo atual |
|---|---|---|
| `app/core/config.py` | 52 | `PROJECT_NAME: str = "Amigão do Meio Ambiente"` |
| `app/core/config.py` | 90 | `EMAILS_FROM_NAME: str = "Amigão do Meio Ambiente"` |
| `frontend/src/pages/Auth/Login.tsx` | 71 | `<h1>...Amigão do Meio Ambiente</h1>` |
| `frontend/src/layouts/PrivateLayout.tsx` | 66 | `<span>Amigão</span>` (header desktop) |
| `frontend/src/layouts/PrivateLayout.tsx` | 119 | `<span>Amigão</span>` (header mobile) |
| `app/services/email.py` | 86 | `<h2>Amigão do Meio Ambiente</h2>` |
| `app/services/contract_generator.py` | 45 | `"{{empresa.nome}}", "Amigão do Meio Ambiente"` |
| `app/services/contract_generator.py` | 138 | `cell..."AMIGAO DO MEIO AMBIENTE"` |
| `app/services/contract_generator.py` | 186 | rodapé `"Amigao do Meio Ambiente"` (sem acento) |
| `app/api/v1/proposals.py` | 312 | `<h2>Amigão do Meio Ambiente</h2>` |
| `app/workers/pdf_generator.py` | 189 | rodapé `"...do Amigao do Meio Ambiente para..."` (sem acento) |
| `app/agents/__init__.py` | 2 | docstring `"Sistema de Agentes IA — Amigao do Meio Ambiente"` |
| `app/services/crawlers/dou_crawler.py` | 83 | User-Agent `Amigao-Meio-Ambiente/1.0` |
| `app/services/crawlers/ibama_crawler.py` | 71, 115 | User-Agent `Amigao-Meio-Ambiente/1.0` |
| `app/services/crawlers/doe_crawler.py` | 105 | User-Agent `Amigao-Meio-Ambiente/1.0` |

**Veredito:** o documento `02-IDENTIDADE.md` é um **plano de migração preciso**. Todas as linhas listadas batem com o código real (módulo o caractere `ã` que está com encoding correto no doc e no código). Quando rodar o patch de renomeação, o doc serve de checklist linha-a-linha.

---

## 7. Confirmações de coerência (documentação acertou)

| Item | Doc | Real |
|---|---|---|
| Versão pgvector | "0.8" | `0.8.2` ✓ |
| Bucket MinIO | `amigao-docs` | `BUCKET_NAME = "amigao-docs"` (storage.py:15) ✓ |
| Total agentes | 10 | 10 (`app/agents/` sem utilitários) ✓ |
| Áreas frontend | 10 | AI/Auth/Clients/Contracts/Dashboard/Intake/Processes/Properties/Proposals/Settings ✓ |
| Total chunks knowledge_catalog | 22.573 | `SELECT COUNT(*) FROM knowledge_catalog` = 22.573 ✓ |
| Chunks Federal | 720 | 720 ✓ |
| Chunks GO | 3855 | 3855 ✓ |
| Chunks MS | 4587 | 4587 ✓ |
| Chunks MT | 13.411 | 13.411 ✓ |
| 4 UFs no corpus | "GO+MS+MT+Federal" | confirmado ✓ |
| `AIResponse` fields | content, model_used, tokens_in, tokens_out, cost_usd, duration_ms, provider | exatamente como em `ai_gateway.py` ✓ |
| `AI_MAX_COST_PER_JOB_USD` default | `$0.10` | `0.10` em settings ✓ |
| `AI_HOURLY_COST_LIMIT_USD` valor | `5.0` | `5.0` em `ai_gateway.py:48` ✓ |
| `BaseAgent.run()` lifecycle | descreve cost cap → execute → registro AIJob → emit event → mark review | confere com `app/agents/base.py` ✓ |
| `StageOutputContent` + derivados | `PecaJuridicaContent`, `DiagnosticoPreliminarContent`, `RespostaNotificacaoContent` | confere com `app/schemas/stage_output.py` ✓ |
| Skills filesystem em `app/skills/<agente>/<dominio>.md` | descreve placeholders `_template` | confere — só placeholders existem ✓ |
| 5 repositories | (não declarado mas implícito) | `app/repositories/` tem client, document, process, property, task = **5 repos** ✓ |
| Modelos SQLAlchemy | "28 entidades" | 28 arquivos `.py` em `app/models/` (26 entidades + base + types — interpretação coerente) ✓ |

---

## 8. Não verificado nesta rodada (fica como dívida)

Itens que dependem de leitura mais profunda dos docs (ainda não percorri linha a linha):

- `docs/operacao/RUNBOOK_DEV.md` (264 linhas) — comandos de subida, credenciais, paths
- `docs/operacao/RUNBOOK_OPS.md` (255 linhas) — deploy, secrets, troubleshooting de prod
- `docs/operacao/TROUBLESHOOTING.md` (431 linhas) — comandos específicos pra debugar problemas
- `docs/operacao/SEED_DADOS.md` (208 linhas) — política e conteúdo do seed
- `docs/operacao/TESTING.md` (262 linhas) — comandos de teste, padrões, fixtures
- `docs/arquitetura/MODELO_DE_DADOS.md` (230 linhas) — schema completo do banco
- `docs/arquitetura/API_v1.md` (216 linhas) — endpoints exatos e shapes
- `docs/arquitetura/FLUXOS_E2E.md` (330 linhas) — fluxos do usuário
- `docs/arquitetura/MULTITENANT_LGPD.md`, `OBSERVABILIDADE.md`, `WHITELABEL.md`, `INTEGRACOES_GOVTECH.md`, `PIPELINE_OCR.md`, `BASE_REGULATORIA.md`
- ADRs (9 arquivos, ~940 linhas)

**Sugestão:** segunda passada (que pode rodar em ~2-3h) percorrendo esses arquivos pra fechar o checklist completo. O que já está coberto representa **a maior parte das afirmações verificáveis "duras"** (números, paths, schemas de banco).

---

## 9. Recomendações priorizadas

### Prioridade alta — afetam onboarding e operação
1. **Corrigir `README.md`** — emails seed devem refletir `seed.py` real (ou vice-versa).
2. **Corrigir dimensão do vetor** em `ARQUITETURA_GERAL.md` (1536 → 768) para evitar bug de quem tente reindexar.

### Prioridade média — afetam confiança nos números
3. Recontar **routers, migrations, workers, services, tests, chains, telas** após recuperar o stash do Waitlist, e atualizar `ESTADO_ATUAL.md` + `ARQUITETURA_GERAL.md`.
4. Trocar `_env.example` por `.env.example` em todas as ocorrências dos docs.

### Prioridade baixa — cosméticas
5. Atualizar linha 46 → 48 em `GOVERNANCA_IA.md`.
6. Reauditar "13 métricas amigao_*" com `grep -E "^[a-z_]*amigao_[a-z_]+\s*="` ou outra regex pra contagem fiel.

### Continuar
7. Fazer segunda passada cobrindo os 13 arquivos não percorridos ainda (seção 8).
8. Executar plano de renomeação visível (seção 6) como **patch único** quando a sprint dedicada chegar — usar `02-IDENTIDADE.md` como checklist.

---

## 10. Apêndice — Como reproduzir as verificações

```bash
# Contagens
grep -c "include_router" app/main.py                              # routers
ls alembic/versions/*.py | wc -l                                  # migrations
find tests -name "test_*.py" | wc -l                              # tests files
ls app/agents/*.py | grep -vE "__init__|base|orchestrator|events|memory|validators" | wc -l  # agentes
ls app/models/*.py | grep -v __init__ | wc -l                     # models
ls app/services/*.py | grep -v __init__ | wc -l                   # services
ls app/workers/*.py | grep -v __init__ | wc -l                    # workers
find frontend/src/pages -name "*.tsx" | wc -l                     # telas frontend
find frontend/src/pages -mindepth 1 -maxdepth 1 -type d | wc -l   # áreas frontend

# Chains
python3 -c "import re; t=open('app/agents/orchestrator.py').read(); m=re.search(r'CHAINS:\s*dict.*?=\s*\{([^}]+)\}', t, re.S); print(len(re.findall(r'\"[a-z_]+\":\s*\[', m.group(1))))"

# DB
docker compose exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c 'SELECT COALESCE(uf,\"federal\") AS uf, COUNT(*) FROM knowledge_catalog GROUP BY uf ORDER BY uf;'"
docker compose exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c 'SELECT atttypmod FROM pg_attribute WHERE attrelid = \"knowledge_catalog\"::regclass AND attname = \"embedding\";'"
docker compose exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT extversion FROM pg_extension WHERE extname='vector';\""

# Strings renomeação
grep -nE "Amig[ãa]o" app/core/config.py
grep -n "Amigão" app/services/email.py
grep -n "Amigao" app/services/crawlers/*.py
grep -n "amigao_db\|amigao-docs\|amigao_events" app/core/config.py app/services/storage.py
```

---

**Gerado em:** 2026-05-15 pelo agente de auditoria documental, com base em leitura direta dos 33 docs novos da Onda 3 e verificação no código vivo (banco PostgreSQL no compose, working tree com stash `waitlist-wip pre-onda3`).
