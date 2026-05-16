# 03 · Princípios

**Documento:** Manifesto · Princípios inegociáveis
**Estado:** vivo · alteração requer discussão explícita
**Última revisão:** 2026-05-15

---

Princípios não são "boas práticas que tentamos seguir quando dá". São regras que **vencem feature**, **vencem velocidade** e **vencem pressão comercial**. Quando aparecer conflito entre um princípio e uma demanda, o princípio ganha — ou o princípio muda em discussão explícita e registrada.

Esta é a lista. Está curta de propósito.

## Princípio 1 — A IA propõe; o humano decide e assina

Nenhum agente do Regente toma decisão que tenha consequência regulatória, jurídica, financeira ou processual sem revisão humana explícita. Peças que vão para órgão público, banco, cartório ou cliente passam por gate de aprovação do consultor. O campo técnico que materializa esse princípio é `requires_review=True` em todo `AgentResult` que produza peça formal.

Isso é o que separa o Regente de produtos que prometem "automação total". Automação total é vendável e perigosa em domínio regulatório. O Regente escolhe outro caminho: amplificar capacidade do consultor sem retirar autoridade dele.

A diferença operacional é simples: a IA propõe; o humano decide e assina. Se a feature pode operar sem o "decide e assina" no meio, ela passa por revisão de design antes de subir.

## Princípio 2 — Tudo é auditável

Toda saída produzida pela plataforma tem rastreabilidade encadeada e verificável:

- **Origem do dado.** Quando o sistema preenche um campo do Cliente Hub ou Imóvel Hub a partir de extração documental, marca a origem (`field_sources`) e quem confirmou.
- **Citação rastreável.** Toda referência legal (`Lei X/AAAA`, `Decreto Y/AAAA`, `Resolução CONAMA Z`) gerada por agente passa pelo `citation_evaluator`, que confronta cada citação contra o `knowledge_catalog` (RAG). Citação inventada vira `citation_issues` no `AIJob.result` e marca a peça para revisão obrigatória.
- **Hash chain.** Toda escrita relevante no `AuditLog` é encadeada por SHA-256, permitindo verificação posterior de integridade temporal.
- **Custo, tokens, modelo.** Toda chamada LLM grava custo em USD, tokens de entrada/saída, modelo usado, latência. Falhas preservam esses campos para autópsia.

Auditabilidade não é compliance teatral. É a condição para o Regente conversar com órgão público em pé de igualdade técnica, e para o consultor defender em juízo qualquer peça gerada na plataforma.

## Princípio 3 — Cadastro, Diagnóstico e Coleta são camadas separadas

Sintetizado no briefing de 29/04: *cadastro é entrada, diagnóstico é inteligência, coleta é organização.* Cada uma é uma camada distinta com responsabilidade clara, e misturar as três é o erro recorrente das ferramentas que tentam fazer tudo no mesmo lugar.

- **Cadastro** (Cliente Hub, Imóvel Hub) — quem é o cliente, qual é o imóvel, dados imutáveis ou de lenta mudança.
- **Diagnóstico** — análise técnica e regulatória aplicada ao caso específico (`RegulatoryDiagnosis` versionado por processo).
- **Coleta documental** — o conjunto de documentos pertinentes ao caso, organizados por checklist.

Decisão de design: o Intake captura o caso, mas **não promove demand_type automaticamente**. O diagnóstico classifica. O consultor confirma. Os Hubs auto-alimentam a partir de extrações, sempre com origem rastreável.

## Princípio 4 — Multi-tenant desde o dia 1

Toda query toca em `tenant_id`. Toda criação de entidade passa por validação de tenant no JWT. O `tenant_id` no token tem que bater com o `tenant_id` da entidade — quem manipula entidade de outro tenant toma 403.

Isso vale para humano, para agente IA, para worker Celery, para webhook externo, para job batch. Não existe operação "global" no Regente que ignore tenant. As únicas exceções são endpoints de infraestrutura (`/health`, `/metrics`, `/`) e o `POST /api/v1/waitlist` (lead anônimo pré-conta).

## Princípio 5 — Multi-provider de IA

Nenhum fluxo do Regente depende de um único vendor. O AI Gateway em `app/core/ai_gateway.py` usa LiteLLM como camada de abstração com fallback automático entre OpenAI, Gemini e Anthropic. Quando um provider falha, o próximo assume. Quando um provider sobe preço, há alternativa pronta.

Isso é estratégico para custo (cada provider tem janela diferente, preço diferente, força diferente em PT-BR) e para risco (lockin em provider de IA hoje é insanidade — o mercado se move trimestralmente).

A escolha de modelo por tipo de tarefa fica documentada em [`../arquitetura/GOVERNANCA_IA.md`](../arquitetura/GOVERNANCA_IA.md).

## Princípio 6 — Schema antes de escala

Toda saída de agente que vai ser consumida por outro agente ou pela API tem schema Pydantic v2 validado. Trabalho começa em `app/schemas/stage_output.py` (`StageOutputContent` base + derivados). Migração de agentes para emitir schema validado é gradual e dual-emit (mantém chaves antigas durante a transição), conforme padrão da Sprint A2.

Isso é o que separa "IA que funciona em demo" de "IA que escala para 100 tenants sem virar circo de exceções de runtime".

## Princípio 7 — Cost cap é hard limit

Toda chamada LLM tem custo máximo enforced em `app/core/ai_gateway.py:complete()` via `AI_MAX_COST_PER_JOB_USD` (default `$0.10`), com override por job possível mas auditado. Cada tenant tem orçamento mensal próprio (`Tenant.ai_monthly_budget_usd`) e tarefas que estourariam o orçamento retornam 429 antes de gastar.

Sem cost cap, um bug de prompt loop ou um documento gigante errado pode queimar centenas de dólares em uma única requisição. Princípio: o sistema falha barato, nunca falha caro.

## Princípio 8 — Skills são procedurais, dados são curados

Existem dois mecanismos distintos de conhecimento no Regente:

- **Skills** (`app/skills/<agente>/<dominio>.md`) — instruções procedurais que orientam *como* um agente deve trabalhar para uma demanda específica. Skills são escritas por humanos com expertise de domínio (sócia, consultor sênior), versionadas no repositório e carregadas automaticamente pelo `BaseAgent.call_llm` quando o contexto bate.
- **Knowledge Catalog** (`app/services/knowledge_catalog.py`, `pgvector`) — base de conhecimento factual (legislação, ofícios-modelo, manuais) com busca semântica. Alimentada por curadoria explícita.

Skill diz "como redigir". Knowledge diz "o que citar". Não confundir os dois.

## Princípio 9 — Frontend strict, sem any

TypeScript do frontend roda com `strict: true`, `noUnusedLocals: true`, `noUnusedParameters: true`. Não usamos `any` explícito — usamos tipos concretos ou `typeof` de valores existentes. Mutations retornam tipo consistente (uniformizando com `async/await`).

Frontend frouxo é dívida que se paga em produção, com bug de cliente reclamando.

## Princípio 10 — Migrations governam o schema

`alembic` é o único caminho para evolução de schema. Não usamos `Base.metadata.create_all()` fora de teste. Toda mudança de modelo passa por migration nomeada com convenção `<8-hex>_sprint_<X>_<descricao>.py` e revisada como qualquer código.

Schema é contrato. Contrato muda por escrito.

---

## Quando um princípio precisa mudar

Princípios não são imutáveis para sempre, mas mudam por mecanismo formal:

1. Quem quer mudar abre discussão explícita (issue, ADR draft, sessão registrada).
2. O motivo de mudança fica documentado.
3. Se a mudança for aprovada, vira ADR específico e este documento é atualizado com referência ao ADR.
4. Princípios antigos não somem; ganham nota histórica.

**Tudo o que não está nessa lista é negociável.** Tudo o que está, não é.
