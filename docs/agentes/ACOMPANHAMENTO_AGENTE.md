# ACOMPANHAMENTO — sister file

> Documento vivo do agente `acompanhamento`. Toda afirmação aqui é verificável no
> código (referências `arquivo:linha`). Criado em 2026-05-31 a partir do código
> real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Monitora mensagens recebidas (e-mail, portal) para detectar **respostas de órgãos
ambientais** (IBAMA, SEMA, ICMBio), classificar o tipo de resposta, extrair prazos
e sugerir o próximo status do processo. É agente de **apoio/monitoramento** — não
emite peça formal, não decide status; entrega uma leitura estruturada da mensagem
para o consultor agir.

Registrado como `"acompanhamento"` / `AcompanhamentoAgent`,
`job_type=AIJobType.acompanhamento_processo`
(`app/agents/acompanhamento.py:18-22`; enum em `app/models/ai_job.py:37`).

## 2. Estado de implementação

- **Implementado.** `execute()` analisa `message_content` (ou carrega mensagens
  recentes da thread do processo) e retorna a leitura via LLM
  (`app/agents/acompanhamento.py:30-75`).
- **Disparo agendado real:** `acompanhamento_check_all` (Celery Beat) varre
  processos em `ProcessStatus.aguardando_orgao` e dispara `run_agent` por processo
  (`app/workers/agent_tasks.py:217-258`). Agendado a cada 2h
  (`app/core/celery_app.py:68-74`, `crontab(minute=0, hour="*/2")`).
- **Sem inbox connector real:** o comentário em `celery_app.py:70-72` registra que,
  sem connector de e-mail ativo, o acompanhamento atual é leve; a cadência foi
  reduzida de 30min para 2h. Connector real é dívida P2.

## 3. Skills

Sem skill procedural dedicada em `app/skills/acompanhamento/` (diretório não existe
— verificado por glob). O comportamento vive nos prompts
(`prompt_slugs = ["acompanhamento_system", "acompanhamento_parse_email"]`,
`acompanhamento.py:23`) com fallback hardcoded em `_fallback_prompts()`
(`acompanhamento.py:139-159`). Skills aplicáveis ao contexto ainda assim seriam
injetadas pelo `BaseAgent._compose_system_with_skills` (`base.py:336-349`), mas
nenhuma casa hoje com `agent="acompanhamento"`.

## 4. Tools que usa

- **LiteLLM gateway** via `self.call_llm()` (`acompanhamento.py:62`; wrapper em
  `base.py:263-278`) — análise estruturada da mensagem.
- **`OutputValidationPipeline.parse_llm_json`** (`acompanhamento.py:63`) — parse do
  JSON retornado pelo LLM.
- **DB (SQLAlchemy):** `CommunicationThread` + `Message` para `_load_recent_messages`
  (`acompanhamento.py:77-99`) e `Process` para `_load_process_context`
  (`acompanhamento.py:101-115`). Ambos filtram por `tenant_id`.
- **AIJob** — persistido pelo template `BaseAgent.run()` (`base.py:120-188`).

## 5. Inputs aceitos

Por `ctx.metadata`: `message_content`, `message_source` (default `"email"`,
`acompanhamento.py:33-34`). Alternativamente `ctx.process_id` sozinho.
**Precondição** (`validate_preconditions`, `acompanhamento.py:25-28`): exige
`message_content` não-vazio **ou** `process_id` — senão `ValueError`.

Caminhos de disparo:
1. **Agendado:** `acompanhamento_check_all` → `run_agent.delay(agent_name="acompanhamento", ...)`
   com `metadata={"check_type": "scheduled"}` (`agent_tasks.py:244-249`).
2. **Chain `monitoramento`** (`["acompanhamento", "vigia"]`, `orchestrator.py:39`),
   mapeada a partir do `job_type` `"monitor_process"` (`orchestrator.py:65`).
3. Execução direta por agente via API `/agents` / `run_agent`.

Quando há `process_id` sem mensagem e a thread não tem conteúdo, retorna
`is_agency_response=False` / `action_required=False` (não é erro,
`acompanhamento.py:37-44`).

## 6. Outputs

`dict` simples (NÃO é `StageOutputContent`). Caminho LLM
(`acompanhamento.py:65-75`): `is_agency_response`, `agency`, `response_type`
(`aprovacao|exigencia|indeferimento|informacao`), `summary`, `deadlines_detected`,
`action_required`, `suggested_next_status`, `extracted_protocol`, `confidence`
(`high|medium|low`).

`requires_review`: **não definido pelo agente** — derivado no `BaseAgent.run()`.
`_needs_review` retorna `True` só se o dict trouxer `requires_review=True` (não traz)
ou se `confidence == "low"` (`base.py:439-443`). O caminho LLM default usa
`confidence="medium"` (`acompanhamento.py:74`) → normalmente `requires_review=False`.
O fallback por regras retorna `confidence="low"` (`acompanhamento.py:136`) →
`requires_review=True`.

## 7. Knowledge essencial

- Órgãos/keywords reconhecidos no fallback por regras
  (`_rules_based_parse`, `acompanhamento.py:117-137`): `ibama`, `sema`, `icmbio`,
  `protocolo`, `despacho`, `notificacao`, `auto de infracao`, `licenca`,
  `condicionante`; gatilhos de ação: `prazo`, `exigencia`, `pendencia`,
  `comparecer`, `apresentar`.
- Sem IA configurada (`settings.ai_configured` falso), cai no fallback por regras
  (`acompanhamento.py:46-47`) — degrada com elegância, não aborta.
- Mensagem é truncada em 3000 chars antes de ir ao LLM (`acompanhamento.py:56`).

## 8. Conversation patterns

Não conversacional. Roda como task — síncrona via API ou assíncrona via Celery
(agendada de 2h em 2h, ou na chain `monitoramento`). Reentrante: cada execução
relê as mensagens recentes (`limit(10)`, mais novas primeiro,
`acompanhamento.py:92-98`) e cria um novo `AIJob`.

## 9. Cross-agente

- Compõe a chain `monitoramento` antes de `vigia` (`orchestrator.py:39`). Como
  `acompanhamento` **não** está em `NON_BLOCKING_REVIEW_AGENTS`
  (`orchestrator.py:54`, que contém só `auditor_imovel`), se ele retornasse
  `requires_review=True` (via `confidence="low"`) a chain pararia antes do `vigia`
  (human-in-the-loop, `orchestrator.py:5-6,145`).
- `suggested_next_status` é uma **sugestão** de transição de status do processo;
  a decisão/escrita de status fica fora do agente (Princípio 1: a IA propõe).

## 10. Dívidas técnicas próprias

- **Inbox connector de e-mail ausente (P2):** sem fonte real de mensagens, o
  monitoramento opera quase em vazio (`celery_app.py:70-72`).
- **`response_type` / `suggested_next_status` sem enum validado:** vêm livres do
  LLM (`acompanhamento.py:68,72`); não há schema Pydantic que restrinja os valores
  (não há schema dedicado em `app/schemas/` — verificado por grep).
- **Confiança default fixa em `"medium"`** (`acompanhamento.py:74`): não há cálculo
  real de confiança no caminho LLM.

## 11. Próximas frentes

- Connector real (WhatsApp/e-mail, PR 2.1 de mensagens externas) alimentaria
  `CommunicationThread`/`Message` e daria substância ao monitoramento.
- Validar `suggested_next_status` contra `ProcessStatus` e propor a transição na UI.

## 12. Validação Isis

- **Não verificado.** Sem evidência no código de validação fim-a-fim pela Isis em
  caso real (depende do inbox connector, ainda ausente). O fluxo agendado existe e
  dispara, mas sem mensagens reais não há leitura substantiva a validar.
