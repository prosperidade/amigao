# FINANCEIRO — sister file

> Documento vivo do agente `financeiro`. Toda afirmação aqui é verificável no
> código (referências `arquivo:linha`). Criado em 2026-05-31 a partir do código
> real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Agrega dados financeiros do processo/tenant — custos de IA, propostas e
contratos — e produz análise financeira; opcionalmente enriquece com insights e
recomendações via LLM. É agente de **apoio**: não emite peça formal, não decide;
entrega números agregados e (quando pedido) leitura qualitativa.

Registrado como `"financeiro"` / `FinanceiroAgent`,
`job_type=AIJobType.analise_financeira` (`app/agents/financeiro.py:20-24`).

## 2. Estado de implementação

- **Implementado.** `execute()` (`app/agents/financeiro.py:27-48`) sempre agrega
  os dados via `_aggregate_financial_data()` e retorna o `dict`. O enriquecimento
  LLM (insights/recommendations/confidence) só roda quando
  `settings.ai_configured` **e** `ctx.metadata["generate_insights"]` é truthy
  (`financeiro.py:32-46`); caso contrário retorna só os agregados
  (`financeiro.py:32-33`).
- **Funciona sem IA.** A API o reconhece explicitamente como agente que roda sem
  IA configurada (`app/api/v1/agents.py:69`).
- No ecossistema: `analise_financeira | dict (insights) | review não |
  Implementado` (`docs/agentes/ECOSSISTEMA_AGENTICO.md:30`).

## 3. Skills

Sem skill procedural dedicada — não existe `app/skills/financeiro/`. O
comportamento vive em `_aggregate_financial_data()` + prompts de fallback
(`financeiro.py:117-130`). A injeção de skills do `BaseAgent`
(`_compose_system_with_skills`, `base.py:336-349`) continua valendo, mas hoje
nenhuma skill casa o contexto `agent="financeiro"`.

## 4. Tools que usa

- **Queries SQLAlchemy** sobre `AIJob`, `Proposal`, `Contract` — `func.sum`,
  `func.count`, `.all()` (`financeiro.py:66-99`).
- **LiteLLM gateway** via `self.call_llm()` (`base.py:263-278`) — só no caminho
  de insights (`financeiro.py:41`).
- **`OutputValidationPipeline.parse_llm_json`** para parsear o JSON do LLM
  (`financeiro.py:42`).
- **AIJob** — persiste cada execução (tokens, custo, `result`) via o template
  method do `BaseAgent` (`base.py:353-396`).

## 5. Inputs aceitos

- Do contexto: `ctx.tenant_id` (sempre filtra), `ctx.process_id` (opcional — se
  presente, escopo = processo; senão escopo = tenant) (`financeiro.py:55-63,114`).
- De `ctx.metadata`: `generate_insights` (bool; default `False`) liga o caminho
  LLM (`financeiro.py:32`).
- Disparo: via `/agents` (execução individual, `app/api/v1/agents.py`) ou via a
  chain `analise_financeira` (intent `financial_analysis`)
  (`orchestrator.py:38,66`). Não consta em worker/scheduled tasks
  (`app/workers/` sem referência).

## 6. Outputs

`dict` com:
`ai_cost_usd`, `ai_job_count`, `proposals` (lista `{id,title,total_value,status}`),
`proposals_count`, `total_proposed_value`, `accepted_value`, `contracts` (lista
`{id,title,status}`), `contracts_count`, `scope` (`"process"|"tenant"`)
(`financeiro.py:105-115`). `accepted_value` soma propostas com
`status.value == "accepted"` (`financeiro.py:103`).

Quando o caminho LLM roda, acresce `insights` (list), `recommendations` (list) e
`confidence` (`high|medium|low`, default `"medium"`) (`financeiro.py:44-46`).

Não existe schema Pydantic dedicado em `app/schemas/` para este output — é um
`dict` livre (não passa por `StageOutputContent`). `validate_output` herdado é
no-op (`base.py:235-237`).

`requires_review` = **não**. O agente nunca seta `requires_review` no dict; o
`_needs_review` do `BaseAgent` só marca `True` se `confidence == "low"`
(`base.py:439-443`), e o default de confidence é `"medium"` (`financeiro.py:46`,
`base.py:430-437`).

## 7. Knowledge essencial

- Três fontes financeiras: custo de IA (`AIJob.cost_usd`), valor proposto
  (`Proposal.total_value`) e contratos (`Contract`) (`financeiro.py:52-99`).
- Distingue **proposto** × **aceito**: `total_proposed_value` soma todas;
  `accepted_value` só as `status == "accepted"` (`financeiro.py:102-103`).
- Tolerância a nulos: `total_value or 0` (`financeiro.py:102-103`); custo/contagem
  caem para `0.0`/`0` via `func.coalesce` e `or` (`financeiro.py:67-76`).
- `status` é enum — lido por `.value` com guarda `if status else None`
  (`financeiro.py:85,96`).

## 8. Conversation patterns

Não conversacional. Roda como task (síncrona via `/agents` ou dentro da chain).
Reentrante e idempotente quanto à leitura: cada execução recalcula os agregados
do estado atual do banco; uma nova execução cria novo `AIJob`
(`base.py:353-371`).

## 9. Cross-agente

- Single-agent: a chain `analise_financeira` tem só `["financeiro"]`
  (`orchestrator.py:38`). Não consome `chain_data` de outros agentes nem é
  consumido por outro na chain.
- Lê dados produzidos indiretamente por todo o ecossistema (os `AIJob` de
  qualquer agente entram no `ai_cost_usd`/`ai_job_count` quando o escopo é o
  tenant) (`financeiro.py:66-76`).
- Cross-cutting (cost cap, AIJob, telemetria, multi-provider): ver
  `docs/agentes/ECOSSISTEMA_AGENTICO.md`.

## 10. Dívidas técnicas próprias

- **Output sem schema:** retorna `dict` livre, fora de `StageOutputContent`
  (Princípio 6 "schema antes de escala") — `financeiro.py:105-115`. Não
  verificado se há dívida registrada para isso.
- **`_extract_confidence` lê chave `confidence` crua do dict** — o valor vem do
  LLM sem validação de domínio além do default (`financeiro.py:46`,
  `base.py:430-437`).
- Bug correlato em dashboard financeiro: `GET /dashboard/kpis` retorna vazio
  mesmo com processos (investigação pendente — `app/api/v1/dashboard.py`). Não
  confirmado se afeta este agente.

## 11. Próximas frentes

- Projeção de custos / acompanhamento de pagamentos: a docstring promete
  "projecao de custos, acompanhamento" (`financeiro.py:1-6,23`), mas o código
  hoje só agrega o estado atual — não há projeção temporal nem fluxo de pagamento
  verificável. Frente em aberto.
- Schema validado para o output (alinhar ao Princípio 6).

## 12. Validação Isis

- **Pendente.** Não há registro de validação fim-a-fim da análise financeira pela
  Isis em dados reais. No quadro de status do ecossistema o sister file constava
  como pendente até esta data (`docs/agentes/ECOSSISTEMA_AGENTICO.md:158`).
