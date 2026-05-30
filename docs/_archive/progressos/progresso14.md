# Progresso 14 — PROMPT_10: gate camada 2 exclui achados terminais (#23)

## Projeto: Regente Ambiental
## Referências: #17 (PROMPT_8 — coerência) · #20 (PROMPT_7 — ADR-012) · PROMPT_9 (UI da camada 2, revelou o trap)

---

## Objetivo da rodada

Fechar o trap descoberto na revisão do PROMPT_9 (UI da camada 2): o gate
de `PATCH /diagnoses/{version}/validate` filtrava apenas
`severity=critico AND resolved_at IS NULL`, sem olhar `status_achado`.
Resultado: um crítico já adjudicado como falso positivo (`status_achado=
descartada`) AINDA cobrava decisão no gate — dupla negação.

Saída #1 do trio do Andre: estreitar o filtro do gate, não complicar a UI.
Backend apenas.

---

## Estado pré-rodada

- `main` em `0f3f6de` (pós-merge do PR #10 = PROMPT_8).
- `feat/prompt9-ui-alertas-decisao` (UI da camada 2) em revisão — PR
  pushado, ainda não mergeado.
- Suite 635/635 verde no PROMPT_8.
- Decisão sobre `ignorada` resolvida via AskUserQuestion (Andre): excluir
  do gate (terminal simétrico a `descartada`).

---

## Sprints executados (PROMPT_10 — 26/05)

### Passo 0 — leituras antes de mexer

- Filtro real do gate em `regulatory.py:266-275`.
- Enum `StatusAchado` em `models/regulatory.py:138-148` — 5 valores
  (suspeita, confirmada, descartada, resolvida, ignorada).
- **Descoberta:** grep `resolved_at\s*=` em `app/**/*.py` retorna **zero
  matches**. Nenhum fluxo do produto seta `resolved_at` — só os testes
  via `_seed_issue(resolved=True)`. Significa que `status_achado=resolvida`
  e o critério `resolved_at IS NULL` estão **desacoplados**: precisa do
  filtro explícito por `status_achado` para o trap fechar.

### Onda A — filtro do gate

Em `app/api/v1/regulatory.py`:
- Adicionado `RegulatoryIssue.status_achado.in_([StatusAchado.suspeita,
  StatusAchado.confirmada])` na query do gate.
- Filtro positivo (`in [não-terminais]`) em vez de negativo
  (`not_in [terminais]`) — mais fácil de raciocinar quando lê o código.
- Import de `StatusAchado` adicionado.
- Comentário inline explica: terminais não cobram; `suspeita` permanece
  pra forçar adjudicação; `resolved_at IS NULL` continua como critério
  ortogonal (cobertura futura quando algum fluxo setar).

### Onda B — testes

4 cenários novos em `TestValidateDiagnosisGateCamada2` (em
`tests/api/test_regulatory.py`):

- `test_200_critica_descartada_sem_decisao_libera_gate` — falso positivo,
  sem decisão, passa.
- `test_200_critica_status_achado_resolvida_sem_decisao_libera_gate` —
  sanada no mundo, sem decisão, passa. Documenta que `status_achado=
  resolvida` e `resolved_at IS NULL` são critérios desacoplados (cobre
  o `status_achado` mesmo com `resolved_at` ainda nulo).
- `test_200_critica_ignorada_sem_decisao_libera_gate` — terminal por
  decisão prévia do consultor (não confundir com `decisao=
  ignorar_justificado`).
- `test_422_critica_confirmada_sem_decisao_continua_bloqueando` —
  regressão explícita: o estreitamento não esvaziou o gate em todos os
  casos; `confirmada` continua exigindo decisão.

Pré-existentes do gate passam sem mudança (todos usavam `suspeita`
default no `_seed_issue` — que continua dentro do filtro). `_seed_issue`
já tinha o parâmetro `status_achado` desde o PROMPT_8.

Resultado:
- `test_regulatory.py`: 85/85 (+4 vs 81 do PROMPT_8).
- Suite cheia: **639/639** (+4 vs 635 do PROMPT_8).

### Onda C — docs

- `REGISTRO_DIVIDAS`: #23 entra fechada (refinamento do gate). Header
  passa pra "pós-PROMPT_10". Follow-on do badge (PROMPT_9) anotado na
  descrição da #23.
- `ESTADO_ATUAL`: header + bullet PROMPT_10 + frente em revisão (PROMPT_9
  pré-merge).
- `progressoIA`: seção PROMPT_10 completa (motivação, Passo 0,
  decisão sobre `ignorada`, ondas, dívidas fechadas, follow-on).
- `API_v1`: filtro do 422 do gate atualizado (lista o `status_achado in
  {suspeita, confirmada}`); resumo da Camada 2 menciona PROMPT_10.
- `FLUXOS_E2E`: nota no bloco `Status: diagnostico` sobre "descartar
  libera o gate sem dupla negação".
- `GOVERNANCA`: índice `1..12 → 1..14` com nota sobre o `progresso13`
  vir junto do merge do PR do PROMPT_9.
- `progresso14.md` (este arquivo) — snapshot histórico imutável.

---

## Decisão sobre `ignorada`

Prompt antecipou ambiguidade: poderia soar como `decisao=
ignorar_justificado` ou como adjudicação terminal do achado. AskUserQuestion
→ Andre confirmou **excluir** (recomendado). Semântica fechada:
`status_achado=ignorada` significa "consultor optou por não tratar como
fato do imóvel" — terminal simétrico a `descartada`. Sem ambiguidade com
`ignorar_justificado` (que é ação no contexto do processo).

## Decisões arquiteturais (resumo)

- **Estreitar o filtro, não complicar a UI.** A UI já habilita decisão
  em todos os achados não-suspeita (PROMPT_9) — backend mais permissivo
  evita dupla negação.
- **`suspeita` permanece dentro do gate** — força adjudicação antes de
  assinar. Não é deadlock porque o consultor pode mover `status_achado`
  pelo `PATCH /issues`.
- **`resolved_at IS NULL` mantido** como critério ortogonal — mesmo
  sendo vacuoso hoje (nada seta), reflete intenção semântica.
- **Filtro positivo** (`in [não-terminais]`) — leitura mais clara.
- **Sem migration, sem ADR, sem schema change** — refinamento de query.

## Dívidas fechadas

- **#23** — gate cobrando decisão em achado terminal (trap revelado
  pós-PROMPT_9).

## Follow-on aberto

- **Badge do `DiagnosisAssinatura` (PROMPT_9)** precisa espelhar a mesma
  exclusão pra não super-contar pendentes. Aplicado depois que PROMPT_9
  estiver em main (1 linha no filtro client-side de `criticasAbertas`).
  Modal já consome `alertas_pendentes` do 422 (autoridade), então sempre
  estará correto independente do badge.

## Arquivos tocados

**Código (commit 1):**
- `app/api/v1/regulatory.py` (filtro do gate + import + comentário)

**Testes (commit 2):**
- `tests/api/test_regulatory.py` (4 testes novos em
  `TestValidateDiagnosisGateCamada2`)

**Docs (commit 3):**
- `docs/REGISTRO_DIVIDAS.md` (#23 fechada, header pós-PROMPT_10)
- `docs/estado/ESTADO_ATUAL.md`
- `docs/estado/progressoIA.md`
- `docs/arquitetura/API_v1.md`
- `docs/arquitetura/FLUXOS_E2E.md`
- `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` (índice 1..14)
- `docs/_archive/progressos/progresso14.md` (este arquivo)

**NÃO tocados (deliberadamente):**
- `docs/arquitetura/MODELO_DE_DADOS.md` — sem schema change.
- Sem novo ADR — refina ADR-012 / Princípio 1 já firmados.
- Frontend — follow-on do badge fica pra depois do merge do PROMPT_9.
