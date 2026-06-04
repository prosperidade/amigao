# Teste Isis — Rodada 2 (orquestração + contexto entre agentes)

**Branch:** `fix/teste-isis-rodada2` (base `main` @ 61899d0)
**Data:** 2026-06-04
**Caso real:** #10 (tenant 1, prod-like, com Isis). **Análogo local reproduzível:**
processo **30** / propriedade **11** / tenant **2** (`admin@amigao.com`) — único caso
com pipeline completo (extrator + auditor + legislacao + diagnostico) no DB de dev.
A base prod-like com usuários Isis não roda localmente; toda reprodução foi feita
no processo 30, que exercita exatamente os mesmos caminhos de código.

Formato por item: **causa medida → fix → evidência**.

---

## Item A — Aba Agentes: só o Extrator habilita botão no contexto do processo

**Causa medida.** Em `frontend/src/pages/AI/AgentsPage.tsx`, os cards dos agentes
tinham dois comportamentos divergentes:
- **Extrator:** botão dedicado, `disabled={!processIdInput || ...}`, rótulo
  dinâmico `"Rodar no processo #X"` → reagia ao ID do processo.
- **Demais agentes:** botão genérico `"Executar"`, `disabled={isPending && variables===name}`
  → não refletia o processo. Para o consultor, só o Extrator "ativava" com o caso;
  os outros pareciam soltos do contexto.

**Fix.** Generalizei o card: todo agente executável agora habilita **com um
processo válido selecionado**, desabilita sem ele (com dica), e dispara no
contexto do caso (rótulo `"Rodar no processo #X"`). O Extrator mantém a mutation
dedicada (`/processes/{id}/extract`); os demais usam `runAgentMutation` (que já
envia `process_id`). Rodar agente avulso (sem processo) continua possível pelo
seletor **"Executar agente"** abaixo.

**Evidência.** `npx tsc --noEmit` exit 0; `npm run build` exit 0. Os cards agora
ficam desabilitados sem processo e habilitam/rotulam com o processo informado.

---

## Item B — Auditor não aparece no Histórico de execuções

**Causa medida.** Reproduzido o mecanismo: quando um agente que exige processo
(ex.: `auditor_imovel`) é disparado **sem `process_id` válido**, o
`validate_preconditions()` levanta `ValueError("process_id obrigatório…")` **antes**
de `_create_running_job()` (`app/agents/base.py`, ordem original: cost-check →
preconditions → cria job). Resultado: **nenhum AIJob é criado** → a execução não
aparece em `GET /ai/jobs` (nem global, nem por processo). property_audit.py só é
chamado pelo agente (não há caminho paralelo que grave issues sem AIJob), então o
"resultado existe mas histórico não lista" vinha justamente das execuções que
morriam na pré-condição sem registrar job.

**Fix.** Em `BaseAgent.run()`, o AIJob passa a ser criado **antes** da validação
de pré-condições, e a validação entra **dentro do `try`**. Falha de pré-condição
vira job `failed` + `AgentResult(success=False)` — registro visível no histórico.
(Cost-cap segue antes do job: hard limit inalterado.)

**Evidência.** Disparo do auditor sem processo, **pós-fix** → job **146**
`status=failed`, `error="process_id obrigatório para auditor_imovel"`,
`entity_type=agent`, visível em `GET /ai/jobs`. Disparo do auditor **com**
processo 30 → job **143** `completed`, `entity_type=process entity_id=30`, listado
no histórico por processo. Toda execução agora aparece.

---

## Item C — Execução pela aba IA fica "agendada" pra sempre

**Causa medida.** Mesmo gatilho do Item B no worker. Em `app/workers/agent_tasks.py`,
`run_agent` capturava **qualquer** exceção e fazia `self.retry(exc=exc, countdown=30)`.
Quando `run()` levantava `ValueError` de pré-condição (erro determinístico, retry
nunca resolve), a task entrava em **retry storm** (`received` → `retry in 30s` →
`received`…), enquanto a UI já dizia otimisticamente "Execução agendada" e fazia
poll de um histórico que nunca ganhava linha → "agendada pra sempre, nada roda,
não aparece nem após refresh".

Reprodução do log: dispatch do auditor sem processo levava a
`Task … retry: Retry in 30s: ValueError('process_id obrigatório…')` em loop.

(Observado também: worker roda `pool=solo` — serial. Um agente lento prendendo o
worker — ex.: `legislacao` em 115s de timeout do Gemini — atrasa os disparos
seguintes. Latência, não "pra sempre"; o bug "pra sempre" é o retry storm acima.)

**Fix.** (1) `BaseAgent.run()` não propaga mais erro de pré-condição (vira job
`failed`, ver Item B). (2) `run_agent` ganhou branch `except ValueError`: erro
determinístico **não** entra em retry — faz `commit` (o job `failed` já persistiu),
loga e retorna `status=failed`. Falha rápida e visível em vez de "agendada".

**Evidência.** Pós-fix, dispatch do auditor sem processo:
`Task … succeeded in 0.79s: {'status': 'failed', …}` — **sem retry** — e job 146
`failed` no histórico. Disparo pela aba IA com processo válido executa de fato
(jobs 143/145/147 `completed`).

---

## Item D — Quadro de Ações vazio ("detectando…", Dados vazios)

**Causa medida / verificação.** A causa era o 500 das issues
(`ResponseValidationError` em `documentos_cruzados`), corrigido na rodada 1 (#58).
Na main atual o Quadro e as issues **populam**.

**Evidência.**
- `GET /processes/kanban` → HTTP **200**, `total_active=20`, colunas preenchidas
  (entrada_demanda=12, diagnostico_preliminar=2, caminho_regulatorio=1,
  contrato_formalizacao=5).
- `GET /properties/11/issues?status=open` → HTTP **200**, 5 issues
  (`VERIFICACAO_ESPACIAL_PENDENTE`, família `geoespacial`).

**Resolvido pela rodada 1.** Sem mudança de código nesta rodada.

---

## Item E — Contexto do ATENDIMENTO não chega ao DIAGNÓSTICO

**Causa medida.** O `diagnostico` montava o contexto do prompt a partir de
documento (extrator) + legislação, mais um subconjunto curado do processo
(`initial_diagnosis`) — **sem** a narrativa de abertura (`description`,
`initial_summary`, `intake_notes`) e **sem** o resultado do agente `atendimento`.
Como o `atendimento` **não** participa da chain `diagnostico_completo` (roda no
create-case), a informação inicial do consultor — inclusive o que só existe no
relato e não em doc (ex.: **embargo relatado sem documento**) — nunca chegava.

Reprodução: diagnostico do processo 30 (job 145) concluía **"Não há embargo
vigente"**, mesmo com relato de embargo na abertura.

**Fix.** Em `app/agents/diagnostico.py`, sem tocar em prompt-template (proibido) —
apenas enriquecendo os dados dos placeholders existentes:
1. `_load_process_data()` passa a incluir `description`, `initial_summary`,
   `intake_notes` no bloco `process` (placeholder `{process_data}`).
2. Novo `_load_persisted_atendimento()` busca o AIJob `atendimento` mais recente do
   processo e injeta como `process["relato_demanda_consultor"]`. Carregado
   **SEMPRE** (não só com `chain_data` vazio), pois o atendimento nunca vem na
   chain. Fonte **ADICIONAL** — extrator/legislação seguem prioritários.

**Evidência.** Relato de embargo injetado em `intake_notes` do processo 30 (cenário
"consultor relatou, sem doc"); re-rodado o diagnostico (job 147). Log:
`diagnostico.atendimento_context process=30 job=121 — relato/demanda do consultor
injetado como fonte adicional`. Saída pós-fix:
> "Há relato verbal de embargo ambiental, mas sem documentação comprobatória
> anexada." + ações: "confirmar e obter documentação do embargo ambiental junto
> ao órgão competente", "possível embargo ambiental (a confirmar junto ao órgão)".

Contraste com o pré-fix (job 145): "Não há embargo vigente". Injeção de dados de
teste revertida após validação.

---

## Validação geral

- **A:** todos os agentes habilitam/rotulam com processo válido. tsc + build verdes.
- **B:** auditor (e qualquer agente) sempre registra job no histórico — `completed`
  ou `failed`.
- **C:** disparo executa de fato; erro determinístico falha rápido e visível (sem
  retry storm / "agendada pra sempre").
- **D:** Quadro e issues populam (kanban 200/20 cards; issues 200/5).
- **E:** diagnostico do processo 30 menciona o embargo do relato do atendimento.
- **Suites:** `tests/agents/` 183 passed; suite completa (ver report); tsc exit 0;
  build exit 0.

## Arquivos tocados

- `app/agents/base.py` — cria AIJob antes das pré-condições; valida dentro do try (B/C).
- `app/workers/agent_tasks.py` — `run_agent` não faz retry de `ValueError` (C).
- `app/agents/diagnostico.py` — narrativa do processo + `_load_persisted_atendimento` (E).
- `frontend/src/pages/AI/AgentsPage.tsx` — cards de agente process-aware (A).
