# Progresso 11 — PROMPT_7: decisão do consultor contextual ao processo (ADR-012)

## Projeto: Regente Ambiental
## Referências: ADR-012 (validado pela Isis em 26/05) + REGISTRO_DIVIDAS #20

---

## Objetivo da rodada

Implementar o ADR-012 da Isis: a decisão do consultor é **contextual ao
processo**, não perene no imóvel. O PROMPT_6 colocou `decisao_consultor` +
`justificativa` + `at` como campos de `RegulatoryIssue` (Property — perene);
esta rodada move para uma nova entidade `ProcessIssueDecision` (FK composta
`(process_id, issue_id)`, unique). Fecha a dívida #20.

Cada processo agora **recomeça do zero**: titularidade torta pesa diferente
para venda e para crédito, não dá pra herdar a decisão.

---

## Estado pre-rodada

- `main` em `2c2d8ce` (ADR-012 + skill auditor validada integralmente).
- Suite 609 verdes (após PROMPT_6 + revisão #19).
- Decisões confirmadas pelo Andre antes de codar:
  - **Nomes encurtados** na tabela nova: `decisao` / `justificativa` /
    `decided_at` / `decided_by_user_id`.
  - **Drop sem backfill** — sem dados em prod ainda.

---

## Sprints executados (PROMPT_7 — 26/05)

### Onda A — model + migration

**Model** `ProcessIssueDecision` em `app/models/regulatory.py`:
- FK: `tenant_id`, `process_id`, `issue_id`. Unique `(process_id, issue_id)`.
- Campos: `decisao` (NOT NULL), `justificativa` (nullable), `decided_by_user_id`
  (FK users, **novo** vs PROMPT_6), `decided_at` (NOT NULL), `created_at`,
  `updated_at`.
- Enum `regulatory_decisao_consultor` reaproveitado (criado no PROMPT_6).
- Relacionamentos: `process`, `issue`, `decided_by`.

**RegulatoryIssue** perdeu 3 colunas:
- `decisao_consultor` → moveu para `ProcessIssueDecision.decisao`
- `decisao_consultor_justificativa` → `ProcessIssueDecision.justificativa`
- `decisao_consultor_at` → `ProcessIssueDecision.decided_at`

Restaram em `RegulatoryIssue`: `status_achado` (natureza do indício — perene)
e `status_saneamento` (saneamento real no mundo — perene). YAGNI no
"saneamento contextual": só se aparecer demanda. Anotado no doc do model.

**Migration `e3d4f5g6a7b8`**:
- Cria tabela `process_issue_decisions` + 3 índices + FK composta única.
- Drop colunas + índice `ix_regulatory_issues_decisao_consultor` do `RegulatoryIssue`.
- Drop sem backfill (sem dados em prod).
- Downgrade recria as 3 colunas vazias + drop tabela nova.

### Onda B — schemas

- `RegulatoryIssueOut`: perdeu 3 campos. Mantém `status_achado`/`status_saneamento`.
- `RegulatoryIssueUpdate`: perdeu `decisao_consultor`/`justificativa`; sai o
  `@model_validator` (migra). Mantém só `status_achado` e `status_saneamento`.
- **Novo** `ProcessIssueDecisionCreate` (body do PUT): `decisao` (obrigatória),
  `justificativa` (nullable + obrigatória via validator quando
  `decisao in {ignorar_justificado, fora_escopo}`).
- **Novo** `ProcessIssueDecisionOut` (read).
- `decided_by_user_id` e `decided_at` são **server-side** (body PUT não aceita).

### Onda C — endpoints

- `PATCH /api/v1/properties/{prop_id}/issues/{issue_id}`: enxugou — só
  edita `status_achado` e `status_saneamento`. AuditLog granular mantido.

- **Novo** `GET /api/v1/processes/{pid}/issues/{iid}/decision`: retorna a
  decisão ou 404 (cada processo recomeça — explícito na mensagem com
  referência ADR-012).

- **Novo** `PUT /api/v1/processes/{pid}/issues/{iid}/decision`: upsert.
  - Valida: processo do tenant, issue pertence à property do processo.
  - Cria primeira decisão: `AuditLog(action="created")`.
  - Atualiza decisão existente: AuditLog **granular** por campo
    (`decisao_changed`, `justificativa_changed`).
  - No-op por campo: PUT com mesmos valores não gera AuditLog.
  - Hash chain SHA-256 em todos os AuditLog (Princípio 2).

- **Gate camada 2** do `PATCH /validate` (PROMPT_6) ajustado:
  - Antes: filtro `RegulatoryIssue.decisao_consultor.is_(None)`.
  - Agora: cruza `RegulatoryIssue` críticas vs `ProcessIssueDecision` do
    processo atual; pendentes = críticas sem decisão DESTE processo.
  - Mensagem do 422 atualizada: "sem decisão do consultor **neste processo**".

### Testes

**Adaptados:**
- `TestUpdatePropertyIssue` perdeu 3 testes obsoletos (campos de decisão
  sumiram do PATCH /issues); demais testes ajustados para os 2 status
  perenes.
- `TestUpdatePropertyIssueJustificativaObrigatoria` →
  `TestProcessIssueDecisionJustificativaObrigatoria` (5 testes — todos
  testando PUT em vez de PATCH).
- `TestValidateDiagnosisGateCamada2` adaptado: positivos criam
  `ProcessIssueDecision` via helper `_seed_decision`; negativos não criam.
- Helper `_seed_issue` perdeu o parâmetro `decisao_consultor`; novo helper
  `_seed_decision` adicionado.

**Novos:**
- `TestProcessIssueDecision` (11 testes):
  - 401/404 GET sem decisão / processo inexistente.
  - PUT cria primeira decisão; AuditLog `action="created"`.
  - PUT atualiza decisão existente (upsert via unique constraint).
  - PUT gera AuditLog granular por campo.
  - PUT mesmo valor = no-op (zero AuditLog).
  - PUT 404 quando issue não pertence à property do processo.
  - Tenant isolation.
  - GET retorna decisão existente.

**Adicional ao gate:**
- `test_decisao_de_outro_processo_nao_libera_gate` — exercita o caso real
  do ADR-012: decisão tomada no processo A não vale no processo B (mesma
  property). Gate rejeita 422 mesmo com `ProcessIssueDecision` existente
  em outro processo.

---

## Resumo numérico

| Dimensão | Quantidade |
|---|---|
| Worktree dedicado | 1 (`impl-prompt7`) |
| Migrations novas | 1 (`e3d4f5g6a7b8`) |
| Tabelas novas | 1 (`process_issue_decisions`) |
| Endpoints novos | 2 (`GET` + `PUT /processes/{pid}/issues/{iid}/decision`) |
| Endpoints com escopo reduzido | 1 (`PATCH /issues/{id}` — perdeu 3 campos) |
| Endpoints com gate atualizado | 1 (`PATCH /validate`) |
| Testes finais alvo | 91/91 verdes em `test_regulatory.py` (model + api) |

---

## Decisões arquiteturais

### Nomes encurtados em `ProcessIssueDecision`

`decisao_consultor` → `decisao`, `decisao_consultor_at` → `decided_at`,
`decisao_consultor_justificativa` → `justificativa`. O contexto da tabela
(`process_issue_decisions`) já indica; redundância sai. Andre confirmou.

### Drop sem backfill

Sem dados em prod ainda (dev/staging). Migration destrutiva pras colunas
antigas; mais simples que backfill best-effort. Downgrade recria as
colunas vazias. Andre confirmou.

### `decided_by_user_id` é novo (melhoria proporcional)

PROMPT_6 só tinha `decisao_consultor_at`. PROMPT_7 ganhou o autor explícito
no campo (não só via AuditLog). Princípio 2 ganha clareza — "quem decidiu"
não depende de cruzar com AuditLog.

### `status_achado` e `status_saneamento` ficam em `RegulatoryIssue`

`status_achado` é fato do imóvel ("auditor errou?" não muda por processo).
`status_saneamento` é saneamento **real** no mundo (cliente corrigiu a
matrícula no cartório? vale pra todos os processos). Se aparecer demanda
de avaliação contextual de saneamento, criar campo separado em
`ProcessIssueDecision`. YAGNI por ora.

### Helper `_seed_decision` nos testes

Adicionado depois do `_seed_issue`. Padrão consistente com seed de outras
entidades; cobre os parâmetros mais usados (decisao, justificativa,
decided_by_user_id).

---

## Principais arquivos criados/modificados

### Backend
- `app/models/regulatory.py` — novo `ProcessIssueDecision`; `RegulatoryIssue` perdeu 3 colunas
- `app/models/__init__.py` — re-export `ProcessIssueDecision`
- `app/schemas/regulatory.py` — `RegulatoryIssueOut/Update` enxugados; novos `ProcessIssueDecisionCreate/Out`
- `app/api/v1/regulatory.py` — gate atualizado + PATCH /issues enxugado + novos GET/PUT /processes/.../decision

### Migration
- `alembic/versions/e3d4f5g6a7b8_prompt7_decisao_contextual.py` (novo)

### Testes
- `tests/api/test_regulatory.py` — adapta 3 classes + adiciona `TestProcessIssueDecision` (11 testes)

---

## Dívidas

### Fechadas nesta rodada

- **#20** (re-modelagem ADR-012) — implementada inteira.

### Continuam abertas, sem mudança

- **#17** (coerência entre os 3 status). PROMPT_6 indicava que dependia da
  re-modelagem. Agora pode ser implementada — `status_achado` e
  `status_saneamento` ficam no `RegulatoryIssueUpdate` (validator simples
  no schema), `decisao` está em outro schema (`ProcessIssueDecisionCreate`)
  onde a justificativa já é validada. As 3 regras propostas no PROMPT_6
  ficaram menores: 2 sobre os 2 campos perenes, e a 3ª (suspeita +
  decisao) move para um validator cruzado entre `RegulatoryIssue` e
  `ProcessIssueDecision` no endpoint PUT (se issue.status_achado=suspeita,
  bloqueia criar ProcessIssueDecision — força confirmar/descartar primeiro).
- **#18** (verificador de hash chain) — P3 com marco.
- Demais dívidas P2/P3/bloqueadas (#6, #7, #8, #9, #10, #11, #13, #14, #15, #16) —
  sem mudança.

### Bloqueia agora a UI

- **UI dos 5 botões** desbloqueada: a estrutura está estável (ADR-012
  implementado). Frontend pode começar a consumir `RegulatoryIssueOut`
  (read-only nos 2 status) + `PUT /processes/.../decision` (consultor
  decide alerta por alerta neste processo).

---

## Estado da base após esta rodada

- `feat/prompt7-decisao-contextual` aguardando PR.
- Princípio 1 fechado em 2 camadas: 1 (PROMPT_4 — assinatura) + 2 (PROMPT_6
  + PROMPT_7 — decisão contextual por processo).
- Estrutura conforme ADR-012: fato perene na Property, decisão contextual
  no Process.
- Suite alvo verde (91/91 em `test_regulatory.py`). Suite completa rodando
  em background no fechamento desta rodada.
