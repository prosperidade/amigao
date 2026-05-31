# VIGIA — sister file

> Documento vivo do agente `vigia`. Toda afirmação aqui é verificável no código
> (referências `arquivo:linha`). Criado em 2026-05-31 a partir do código real
> (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Sentinela de monitoramento. Varre o tenant em busca de prazos vencidos/próximos,
documentos prestes a expirar, processos parados e custo de IA perto do teto —
e gera **alertas factuais**. É agente de **vigilância passiva**: não emite peça
formal, não decide, não conversa; entrega uma lista de alertas para a UI/notificação.

Registrado como `"vigia"` / `VigiaAgent`, `job_type=AIJobType.monitoramento_vigia`
(`app/agents/vigia.py:18-21`). Catalogado no ECOSSISTEMA como output `dict (alerts)`,
`requires_review` não, determinístico (`docs/agentes/ECOSSISTEMA_AGENTICO.md:33`).

## 2. Estado de implementação

- **Implementado.** `execute()` (`app/agents/vigia.py:24-47`) roteia por
  `check_type` (`"deadlines"`, `"documents"`, `"process_status"`, `"billing"`,
  ou `"all"`) e agrega os alertas dos quatro checadores.
- **DETERMINÍSTICO — sem LLM.** O diferencial deste agente: roda só queries e
  regras, sem chamar o gateway. Confirmado no docstring (`app/agents/vigia.py:25`,
  "Executa verificacoes sem LLM — apenas queries e regras") e na ausência de
  qualquer `call_llm`/`complete` no arquivo. `confidence="high"` é fixo com o
  comentário "Sem LLM, dados factuais" (`app/agents/vigia.py:46`).
- **Disparo agendado (Celery Beat):** `vigia_all_tenants` lista tenants ativos e
  faz fan-out de `vigia_scheduled_check` por tenant
  (`app/workers/agent_tasks.py:187-208`). Schedule `vigia-scheduled-check` roda
  às 06:15 e 18:15 BRT (`crontab(hour="6,18", minute=15)`,
  `app/core/celery_app.py:61-67`).

## 3. Skills

Sem skill procedural dedicada. `prompt_slugs = ["vigia_system"]`
(`app/agents/vigia.py:22`) existe por contrato da base, mas o fallback é apenas
um texto descritivo — "Agente de monitoramento — opera por regras, sem LLM."
(`app/agents/vigia.py:192-195`) — e **nunca é consumido**, porque `execute()` não
chama LLM. `prompt_service` mapeia slugs `vigia*` para `PromptCategory.vigia`
(`app/services/prompt_service.py:177-178`), também sem efeito prático aqui.

## 4. Tools que usa

Nenhuma tool de IA. Apenas a sessão SQLAlchemy (`self.ctx.session`) para queries
ORM diretas sobre: `Task`/`TaskStatus` (`app/agents/vigia.py:51`), `Document`
(`:101`), `Process`/`ProcessStatus` (`:133`), `AIJob` (`:167`). Lê a constante
`AI_HOURLY_COST_LIMIT_USD` de `app/core/ai_gateway.py` (`app/agents/vigia.py:166`).

## 5. Inputs aceitos

Por `ctx.metadata`: `check_type` (default `"all"`, `app/agents/vigia.py:26`).
Caminhos de disparo:
1. **Agendado (principal):** Celery Beat → `vigia_all_tenants` →
   `vigia_scheduled_check(tenant_id=...)` com `metadata={"check_type": "all"}`
   (`app/workers/agent_tasks.py:140-148`).
2. **Manual via `/agents/run`** — `run_agent_sync` permite vigia mesmo sem IA
   configurada ("Alguns agentes (vigia, financeiro) funcionam sem IA",
   `app/api/v1/agents.py:68-70`).
3. **Via chain `monitoramento`** (ver seção 9).

## 6. Outputs

`dict` retornado por `execute()` (`app/agents/vigia.py:42-47`):
`{alerts, check_type, alerts_count, confidence}`. Cada item de `alerts` é um dict
com `type`, `severity` (`"warning"`/`"error"`) e campos específicos por checagem:

- `task_overdue` / `task_approaching` (`:79-96`): `task_id`, `process_id`, `title`, `due_date`.
- `document_expiring` (`:118-128`): `document_id`, `process_id`, `document_type`, `expires_at`.
- `process_stale` (`:149-159`): `process_id`, `title`, `status`, `last_updated`.
- `ai_cost_warning` (`:182-189`): `cost_usd`, `limit_usd`, `percentage`.

`requires_review=False`: o output não traz a flag e `confidence="high"`, então
`_needs_review()` retorna `False` (só vira `True` se `requires_review is True` ou
confiança `"low"` — `app/agents/base.py:439-443`). Output é **dict puro**, não
passa por `StageOutputContent`.

## 7. Knowledge essencial

Regras de negócio codificadas (limiares fixos):
- Prazos: vencidas (`due_date < now`) e "vence em breve" (janela de **3 dias**),
  ignorando tarefas em status terminal `concluida`/`cancelada`
  (`app/agents/vigia.py:53-74`).
- Documentos: expiram dentro de **30 dias** (`expires_at` entre `now` e `now+30d`),
  excluindo `deleted_at` não-nulo (`app/agents/vigia.py:103-116`).
- Processos parados: status `aguardando_orgao` com `updated_at` > **30 dias**
  atrás (`app/agents/vigia.py:135-147`).
- Custo IA: soma `AIJob.cost_usd` da **última 1 hora**; alerta a partir de **80%**
  do `AI_HOURLY_COST_LIMIT_USD`, severidade `error` se já estourou
  (`app/agents/vigia.py:169-189`).
- **Tenant isolation:** toda query filtra `tenant_id == self.ctx.tenant_id`
  (`app/agents/vigia.py:58, 109, 140, 173`). Cada checador limita 50 linhas (`.limit(50)`).

## 8. Conversation patterns

Não conversacional. Roda como task — síncrona via `/agents/run` ou agendada via
Celery Beat. Idempotente por execução: cada run recomputa o estado atual e
emite alertas frescos; não persiste os alertas como entidade (só publica e loga).

## 9. Cross-agente

- Participa da chain `monitoramento = ["acompanhamento", "vigia"]`
  (`app/agents/orchestrator.py:39`), mapeada pelo intent `monitor_process`
  (`:65`). Roda **depois** de `acompanhamento`.
- `vigia` **não** está em `NON_BLOCKING_REVIEW_AGENTS` (só `auditor_imovel` está,
  `app/agents/orchestrator.py:54`) — irrelevante na prática, pois nunca marca
  `requires_review=True`.
- Sugerido como agente secundário em macroetapas: `coleta_documental`,
  `diagnostico_tecnico`, `caminho_regulatorio`, `orcamento_negociacao`
  (`app/models/macroetapa.py:212-236`, chave `agent_vigia`).
- Telemetria: como todo agente, `record_agent_execution` registra duração/resultado
  no `run()` da base (`app/agents/base.py:175-182`). `cost_usd` será nulo (sem LLM).

## 10. Dívidas técnicas próprias

- **#15** — Alertas de consulta externa (🔌): embargo (IBAMA), auto de infração,
  licença/outorga aguardam integração (`docs/REGISTRO_DIVIDAS.md:102-103`). Hoje o
  vigia só olha dados internos do tenant; não consulta fontes externas. É a
  extensão natural deste agente.
- Publicação de alertas é best-effort: falha ao publicar via Redis é só logada
  como `warning`, não interrompe o run (`app/workers/agent_tasks.py:167-168`).
- Alertas não são persistidos como entidade própria — só emitidos por
  `publish_realtime_event` (`vigia.alert`, `app/workers/agent_tasks.py:160-166`).
  Sem histórico consultável de alertas. (não verificado como dívida formalizada)

## 11. Próximas frentes

- **Dívida #15** é a frente principal: plugar consultas externas (IBAMA/SEMA/SICAR)
  como novos checadores de alerta. O cofre `Credential` (PR 2.3, dívida #27 fechada)
  já guarda logins de portais por cliente (`docs/REGISTRO_DIVIDAS.md:114-116`),
  insumo para esses crawlers.
- Janela de schedule pode ser revisada com o ciclo da sócia (hoje 2x/dia cobre,
  comentário em `app/core/celery_app.py:63-65`).

## 12. Validação Isis

- **Não verificado** em caso real documentado. A janela de schedule foi calibrada
  pelo "ciclo de trabalho da sócia hoje" (`app/core/celery_app.py:64-65`), mas não
  há registro de validação fim-a-fim da Isis sobre os alertas gerados.
