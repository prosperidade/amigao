# Máquinas de Estado

**Documento:** Arquitetura · referência viva
**Estado:** validado contra código (15/05/2026)
**Última revisão:** 2026-05-15
**Fonte canônica:** `app/models/process.py`, `app/models/task.py`, `app/models/document.py`, `app/models/ai_job.py`

---

Catálogo completo das máquinas de estado do Regente Ambiental. Cada máquina aqui foi validada **contra o código vivo**, não contra plano de design. Quando o doc divergir do código, o código vence — e este documento é atualizado.

## Princípios das máquinas de estado

Aplicam a todas as entidades versionadas por status:

1. **Estado é obrigatório.** Toda entidade crítica tem `status` definido em todo momento.
2. **Transições são explícitas.** Cada máquina tem `VALID_TRANSITIONS` mapeado em código; transição inválida levanta exceção.
3. **Estado terminal não regride.** Entidade em estado terminal (`arquivado`, `cancelado`) não volta atrás — só pra outros estados terminais.
4. **Mudança de estado gera audit.** Todo mudança importante registra `AuditLog` com hash chain SHA-256 encadeado.
5. **IA não muda estado crítico sozinha.** Princípio 1 do manifesto materializado: agentes IA **propõem** mudança de estado; humano valida e confirma.

---

## 1. Máquina de estados — Processo

**Fonte canônica:** `app/models/process.py:ProcessStatus` + `VALID_TRANSITIONS`

### Estados (11)

```
lead → triagem → diagnostico → planejamento → execucao →
protocolo → aguardando_orgao → pendencia_orgao
                                       ↓
                                  concluido → arquivado
                                       ↑
                                  cancelado → arquivado
```

| Estado | Significado |
|---|---|
| `lead` | Demanda chegou (WhatsApp, e-mail, indicação). Ainda não estruturada. Pode não virar processo. |
| `triagem` | Dados mínimos coletados, classificação inicial de demanda. Decisão: vira processo real ou cancela. |
| `diagnostico` | Análise documental aprofundada. Agentes IA (extrator + legislação + diagnóstico) atuam. `RegulatoryDiagnosis` versionado é gerado. |
| `planejamento` | Workflow template aplicado por `demand_type`. Macroetapas planejadas, gates definidos. |
| `execucao` | Operação ativa: tarefas no Kanban, coleta de documentos, redação de peças, campo. |
| `protocolo` | Dossiê consolidado, envio ao órgão (manual ou via integração futura). Número de protocolo externo registrado. |
| `aguardando_orgao` | Esperando retorno do órgão. Vigia monitora prazos. Acompanhamento lê e-mails de retorno (quando inbox conectado). |
| `pendencia_orgao` | Órgão devolveu com exigência. Plano de ação criado. Volta para `execucao`. |
| `concluido` | Processo finalizado com sucesso (licença, deferimento). |
| `arquivado` | Encerrado, sem necessidade de ação. Estado terminal. |
| `cancelado` | Interrompido antes da conclusão. Pode arquivar. |

### Transições válidas

```python
# app/models/process.py
VALID_TRANSITIONS = {
    ProcessStatus.lead:             [ProcessStatus.triagem],
    ProcessStatus.triagem:          [ProcessStatus.diagnostico, ProcessStatus.cancelado],
    ProcessStatus.diagnostico:      [ProcessStatus.planejamento, ProcessStatus.cancelado],
    ProcessStatus.planejamento:     [ProcessStatus.execucao],
    ProcessStatus.execucao:         [ProcessStatus.protocolo, ProcessStatus.cancelado],
    ProcessStatus.protocolo:        [ProcessStatus.aguardando_orgao],
    ProcessStatus.aguardando_orgao: [ProcessStatus.pendencia_orgao, ProcessStatus.concluido],
    ProcessStatus.pendencia_orgao:  [ProcessStatus.execucao],
    ProcessStatus.concluido:        [ProcessStatus.arquivado],
    ProcessStatus.cancelado:        [ProcessStatus.arquivado],
    ProcessStatus.arquivado:        [],
}

TERMINAL_PROCESS_STATUSES = {ProcessStatus.arquivado}
```

### Regras de negócio

- **Criação de processo:** sempre precisa de cliente. Imóvel pode ser opcional inicialmente. Tipo de demanda obrigatório.
- **Promoção de `demand_type`:** acontece via `POST /api/v1/processes/{id}/classify`. Decisão do consultor; IA propõe via `AtendimentoAgent`, humano confirma.
- **Mudança de estado:** registrada em `AuditLog`. Hash chain encadeado.
- **Notificação realtime:** evento `process.status.changed` no canal Redis pubsub do tenant.

---

## 2. Máquina de estados — Tarefa

**Fonte canônica:** `app/models/task.py:TaskStatus` + `VALID_TASK_TRANSITIONS`

### Estados (7)

```
backlog → a_fazer → em_progresso ⇄ aguardando
                          ↓
                        revisao → concluida
                          
qualquer (exceto cancelada) → cancelada
```

| Estado | Significado |
|---|---|
| `backlog` | Tarefa criada, ainda não puxada para o fluxo ativo. |
| `a_fazer` | Priorizada, pronta para alguém pegar. |
| `em_progresso` | Alguém está trabalhando ativamente. |
| `aguardando` | Bloqueada por dependência externa (cliente, parceiro, órgão). |
| `revisao` | Trabalho terminado, esperando validação humana. |
| `concluida` | Finalizada e validada. |
| `cancelada` | Cancelada antes da conclusão (ou até depois — ver transições). |

### Transições válidas

```python
# app/models/task.py
VALID_TASK_TRANSITIONS = {
    TaskStatus.backlog:      [TaskStatus.a_fazer, TaskStatus.cancelada],
    TaskStatus.a_fazer:      [TaskStatus.em_progresso, TaskStatus.cancelada],
    TaskStatus.em_progresso: [TaskStatus.aguardando, TaskStatus.revisao, TaskStatus.cancelada],
    TaskStatus.aguardando:   [TaskStatus.em_progresso, TaskStatus.cancelada],
    TaskStatus.revisao:      [TaskStatus.concluida, TaskStatus.cancelada],
    TaskStatus.concluida:    [TaskStatus.cancelada],
    TaskStatus.cancelada:    [],
}
```

### Regras de negócio

- **Origem:** humano (`origem_humana`) ou IA (`origem_ia=True`).
- **Dependência:** tarefa com dependência pendente não pode passar pra `concluida`.
- **Tarefa vencida:** dispara alerta (Vigia, rules-based, sem LLM).
- **Tarefa concluída:** pode voltar pra `cancelada` (caso especial — auditoria humana). Não pode voltar pra `em_progresso` ou outros estados ativos — abrir nova tarefa.
- **`cancelada` é terminal.**
- **Visibilidade do parceiro:** parceiro terceirizado só vê tarefas atribuídas a ele.

---

## 3. Documento — não tem máquina monolítica

**Fonte canônica:** `app/models/document.py`

⚠️ **Decisão de design:** o Regente **não usa máquina de estados monolítica** para documento (ao contrário de Processo e Tarefa). Em vez disso, o documento tem **três campos independentes** que rastreiam aspectos distintos do ciclo de vida:

### Campo 1 — `ocr_status` (Enum)

Rastreia o pipeline de OCR.

```python
# app/models/document.py
class OcrStatus(str, enum.Enum):
    pending      = "pending"       # Upload feito, OCR ainda não rodou
    processing   = "processing"    # OCR em execução (worker Celery)
    done         = "done"          # OCR concluído com sucesso
    failed       = "failed"        # OCR falhou após retries
    not_required = "not_required"  # Tipo de arquivo dispensa OCR
```

Transições são **lineares simples** (sem regras complexas — pipeline define).

### Campo 2 — `extraction_status` (String livre)

Rastreia a extração estruturada de campos pelo agente Extrator, separadamente do OCR. Sem enum rígido — convenção textual usada pelo pipeline.

### Campo 3 — `requires_review` (Boolean, em outros lugares)

Indica se o documento ou o output dele precisa de revisão humana. Aplicado em `AIJob`, `AgentResult` e `RegulatoryDiagnosis` — não no `Document` em si.

### Por que essa abordagem (e não máquina monolítica)

A versão de design (`Documento_de_Regras_de_Negócio v2`) propunha máquina única: `uploaded → processing → processed → review_required → validated → rejected → archived`. Foi **simplificada na implementação real** porque:

1. **OCR e extração são pipelines independentes.** OCR pode terminar com sucesso e extração ainda nem ter rodado. Misturar os dois numa máquina única gera estados híbridos confusos.
2. **Validação é decisão humana descentralizada.** Não é estado do documento — é flag em jobs e diagnósticos. Mesmo doc pode ser válido pra um propósito e inválido pra outro.
3. **Arquivamento é metadado, não estado.** Documento "arquivado" é uma flag (`is_archived`, ou seguindo o processo arquivado) — não mudança de estado.

**Resultado prático:** documento é mais simples de manipular, e cada camada (OCR, extração, revisão, arquivamento) tem sua própria lógica.

### Eventos importantes

- `document.uploaded` — upload concluído (presigned URL confirmada)
- `document.ocr.completed` — OCR terminou com `done` ou `failed`
- `document.extracted` — extração estruturada terminou (campos populados nos Hubs)
- `document.processed` — fluxo OCR + extração ambos terminaram (evento sintético, usado pelo frontend)

---

## 4. Máquina de estados — AI Job

**Fonte canônica:** `app/models/ai_job.py:AIJobStatus`

### Estados (4)

```
pending → running → completed
              ↓
            failed
```

| Estado | Significado |
|---|---|
| `pending` | Job criado, na fila do worker. |
| `running` | Worker pegou o job, IA está sendo chamada (ou pré/pós-processamento). |
| `completed` | Job terminou com sucesso. `result` populado. Custo/tokens/modelo persistidos. |
| `failed` | Job falhou. Pode ter sido erro de provider, cost cap excedido, validação de schema, etc. Erro registrado em `error_message`. |

### Comparação com proposta de design

O design v2 propunha 6 estados: `queued, processing, done, failed, timeout, cancelled`. Foi **consolidado em 4** na implementação:

- `queued` → `pending`
- `processing` → `running`
- `done` → `completed`
- `failed` → `failed`
- `timeout` → cai em `failed` com `error_message` específico
- `cancelled` → não implementado (decisão: jobs IA não cancelam, eles terminam ou falham)

### Regras de negócio

- **Não bloqueia usuário.** Todo agente roda async; usuário recebe `job_id` e poll/WebSocket avisa.
- **Sempre auditado.** Toda transição grava em `AuditLog`. `result` (JSONB) preserva resposta crua + metadados.
- **Cost cap enforced.** Tentativa de exceder `AI_MAX_COST_PER_JOB_USD` resulta em `failed` com `error_message="cost_exceeded"`, sem chamar o provider.
- **Retry parcial.** Falhas transientes (rate limit do provider, timeout de rede) podem retentar via Celery (`max_retries=3`, `retry_backoff=True`). Falhas duras (schema inválido, cost cap) não retentam.
- **Fallback de provider.** Se OpenAI falha, LiteLLM tenta Gemini, depois Anthropic — tudo dentro do mesmo job (não cria novo). Provider final usado fica em `result["provider"]`.

### Métricas associadas

- `amigao_agent_executions_total{agent, status}` — Counter
- `amigao_agent_execution_duration_seconds{agent}` — Histogram
- `amigao_agent_execution_cost_usd{agent, provider, model}` — Counter

Ver [`OBSERVABILIDADE.md`](./OBSERVABILIDADE.md).

---

## 5. Sincronização Mobile — prevista, não implementada

⚠️ **Status:** congelado conforme [`../adr/009-mobile-clientportal-congelados.md`](../adr/009-mobile-clientportal-congelados.md). A máquina abaixo descreve o **design previsto** para o app de campo (`mobile/`), mas **não está implementada** no estado atual do projeto.

Quando o mobile descongelar (Janela 2 do roadmap), esta seção vira fonte canônica para a implementação. Por enquanto, fica como **referência de design**.

### Estados locais previstos

```
draft → pending_sync → syncing → synced
                          ↓
                        failed → (retry)
                          ↓
                       conflict → (resolução manual)
```

| Estado | Significado |
|---|---|
| `draft` | Dado criado offline no SQLite local, ainda não marcado para sync. |
| `pending_sync` | Marcado para sincronizar quando houver internet. |
| `syncing` | Sync em andamento. |
| `synced` | Sincronizado com sucesso ao backend. |
| `failed` | Falha transiente (sem rede, timeout). Retentará. |
| `conflict` | Versão remota mais nova que a local — exige resolução. **Nunca apaga dado.** |

### Princípios

- **Offline-first absoluto.** Nada depende de internet pra criar/editar dado em campo.
- **Sync idempotente.** Reenvio do mesmo dado não duplica.
- **Conflito nunca apaga.** Em caso de conflito, ambas as versões ficam preservadas até resolução manual.

---

## Estados em outras entidades — referência rápida

Outras entidades têm campos de estado mais simples (enum) sem máquina de transições enforced no código. Lista pra referência:

| Entidade | Campo | Enum |
|---|---|---|
| `Tenant` | `is_active` | Boolean |
| `User` | `is_active`, `is_superuser` | Boolean |
| `Client` | `status_crm` | String livre |
| `Proposal` | `status` | draft, sent, accepted, rejected, expired |
| `Contract` | `status` | draft, signed, active, terminated |
| `RegulatoryDiagnosis` | `status` | draft, validated, superseded (versionado) |
| `PreCadastro` (waitlist) | `status` | pending, contacted, converted, declined |

Quando alguma dessas evoluir para máquina enforced (com transições), entra como nova seção neste documento.

---

## Como adicionar nova máquina de estados

Quando uma entidade ganhar máquina de estados enforced:

1. Criar enum em `app/models/<entidade>.py:<NomeEntidade>Status`
2. Criar dict `VALID_<ENTIDADE>_TRANSITIONS` no mesmo arquivo
3. Implementar função `is_valid_transition(from_status, to_status)` ou usar dependency injection com a função genérica
4. Validar transição em todo service que mude o status
5. Registrar `AuditLog` em cada transição
6. Adicionar seção neste documento com a mesma estrutura (estados, transições, regras de negócio)
7. Atualizar [`MODELO_DE_DADOS.md`](./MODELO_DE_DADOS.md) com referência cruzada

## Próximas leituras

- [`MODELO_DE_DADOS.md`](./MODELO_DE_DADOS.md) — entidades que carregam as máquinas
- [`API_v1.md`](./API_v1.md) — endpoints que disparam transições
- [`FLUXOS_E2E.md`](./FLUXOS_E2E.md) — fluxos do usuário que passam pelas transições
- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — política aplicada às transições de `AIJob`
