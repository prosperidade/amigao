# Progresso 12 — PROMPT_8: coerência entre status do alerta (#17)

## Projeto: Regente Ambiental
## Referências: REGISTRO_DIVIDAS #17 · `RECONCILIACAO_STATUS_ALERTAS.md` · ADR-012 (já implementado em PROMPT_7)

---

## Objetivo da rodada

Fechar a dívida #17. Após PROMPT_7, os 3 status (`status_achado` e
`status_saneamento` perenes em `RegulatoryIssue`; `decisao` em
`ProcessIssueDecision`) eram enums soltos no DB — o sistema aceitava
combinações que o negócio considera absurdas. Esta rodada adiciona guarda
de coerência sem mudança de schema (validação, não modelagem). Barra só o
absurdo óbvio, sem construir máquina de estados completa (over-eng para
P2 — o consultor não é adversário).

---

## Estado pré-rodada

- `main` em `49a7e6a` (PR #9 do PROMPT_7 mergeado).
- Suite 625 verdes.
- Decisão semântica confirmada pelo Andre antes de codar:
  - **Regra A — quem habilita saneamento ativo/concluído:** `confirmada` E
    `resolvida`. Justificativa: `resolvida` é evolução terminal de
    `confirmada` (a divergência foi sanada no mundo); bloquear a transição
    simultânea `confirmada → resolvida` + `em_validacao → saneado` em um
    único PATCH forçaria salvar em duas etapas, sem ganho de invariante.

---

## Sprints executados (PROMPT_8 — 26/05)

### Onda A — helper puro

Novo módulo `app/services/regulatory_coherence.py`:

- `StatusCoherenceError(ValueError)` — subclasse do `ValueError` para que
  o `@model_validator` do Pydantic converta automaticamente em
  `ValidationError` (FastAPI traduz em 422).
- `assert_status_coerente(status_achado, status_saneamento)` — **Regra A**.
  Levanta `StatusCoherenceError` quando `status_saneamento in
  {em_validacao, saneado}` e `status_achado not in {confirmada, resolvida}`.
- `assert_decisao_permitida(status_achado)` — **Regra B**. Levanta
  `StatusCoherenceError` quando `status_achado == suspeita`.

Conjuntos `_SANEAMENTO_EXIGE_ACHADO_VALIDADO` e
`_ACHADOS_QUE_HABILITAM_SANEAMENTO` são `frozenset` — leitura barata,
imutáveis. 100% de coverage no helper.

### Onda B — schema (fast-fail)

`app/schemas/regulatory.py` — `RegulatoryIssueUpdate` ganha
`@model_validator(mode="after")` que delega ao mesmo helper QUANDO os 2
status vêm juntos no body. Não duplica a regra. PATCH parcial (só 1
campo) não dispara — endpoint valida.

### Onda C — endpoints (fonte da verdade)

`app/api/v1/regulatory.py`:

- `PATCH /properties/{prop}/issues/{id}` — antes de aplicar as mudanças,
  monta o **estado resultante** (`body.get(campo) or issue.campo`) e chama
  `assert_status_coerente`. Captura `StatusCoherenceError` → `HTTPException
  422` com `detail=str(exc)`. Só roda se ao menos um dos dois status vem
  no body (issue não tocada nesses campos não é responsabilidade da
  requisição).
- `PUT /processes/{pid}/issues/{iid}/decision` — após carregar a issue,
  ANTES do upsert e do AuditLog, chama `assert_decisao_permitida(
  issue.status_achado)`. Mesma tradução para 422. Garante zero efeito
  colateral no DB quando bloqueia.

### Onda D — testes

`tests/api/test_regulatory.py`:

**`_seed_issue` ganha parâmetro `status_achado: StatusAchado` com default
`suspeita`** (mantém comportamento legado).

**`TestCoerenciaStatusPerene` (7 testes) — Regra A:**
- `test_body_completo_suspeita_mais_em_validacao_eh_422` — fast-fail no
  schema (caminho mais comum do absurdo).
- `test_body_completo_descartada_mais_saneado_eh_422` — absurdo simétrico.
- `test_patch_parcial_estado_resultante_invalido_eh_422` — issue em
  `(suspeita, pendente)`, body manda só `status_saneamento=saneado`;
  estado resultante `(suspeita, saneado)` proibido. Mensagem cita
  `confirmada` e `resolvida`.
- `test_patch_parcial_estado_resultante_valido_eh_200` — issue em
  `(confirmada, pendente)`, mesmo body → 200.
- `test_transicao_simultanea_confirmada_em_validacao_eh_200` — caminho
  feliz.
- `test_resolvida_mais_saneado_eh_200` — confirma a decisão de UX
  (transição terminal).
- `test_saneamento_descartado_aceita_qualquer_achado` — `descartado`/
  `pendente`/`nao_aplicavel` não constrangem.

**`TestDecisaoBloqueadaSeAchadoSuspeita` (3 testes) — Regra B:**
- `test_put_decision_com_achado_suspeita_eh_422` — mensagem cita
  "Confirme ou descarte".
- `test_put_decision_com_achado_confirmada_eh_200` — caminho feliz.
- `test_put_decision_com_suspeita_nao_grava_decision_nem_auditlog` —
  defensivo: zero efeito colateral no DB.

**7 testes pré-existentes adaptados** — seedavam issue em `suspeita`
(default) e faziam `PUT /decision` esperando 200; agora passam
`status_achado=StatusAchado.confirmada` ao seed. (`TestProcessIssueDecision`
× 5 + `TestProcessIssueDecisionJustificativaObrigatoria` × 2.)

---

## Resultado

- Suite 635 verdes (+10 vs 625 baseline).
- Coverage 100% no helper novo. `app\schemas\regulatory.py` segue em 100%.
- Sem migration; sem mudança de schema de banco. Os enums seguem soltos
  no DB; a coerência é enforçada na borda (schema + endpoint).

## Dívidas fechadas

- **#17** (coerência entre os 3 status reconciliados) — escopo fechado em
  2 regras semânticas. P2 regulatória esvaziada.

## Heads-up para a próxima rodada (UI dos 5 botões)

Pela Regra B, alertas críticos em `suspeita` não aceitam decisão — e o
gate de `/validate` exige decisão. Logo, a UI da aba "Alertas" precisa
deixar o consultor **mover o `status_achado`** (`suspeita → confirmada`/
`descartada`) na mesma tela em que ele decide o que fazer, senão trava no
gate sem caminho. A mensagem 422 da Regra B é acionável o suficiente para
a UI orientar a ação.

## Arquivos tocados

**Código (Onda A/B/C — 1 commit):**
- `app/services/regulatory_coherence.py` (novo)
- `app/schemas/regulatory.py` (import + `@model_validator`)
- `app/api/v1/regulatory.py` (2 imports + chamadas + comentários)

**Testes (Onda D — 1 commit):**
- `tests/api/test_regulatory.py` (`_seed_issue` estendido; 7 adaptações;
  2 classes novas)

**Docs (1 commit):**
- `docs/REGISTRO_DIVIDAS.md` (move #17 para Fechadas, remove dos abertos)
- `docs/estado/ESTADO_ATUAL.md` (header + bullet PROMPT_8 no pipeline)
- `docs/estado/progressoIA.md` (seção PROMPT_8)
- `docs/arquitetura/API_v1.md` (gatilho de estrutura: 2 endpoints e
  subseção "Coerência entre status do alerta" com shape do 422)
- `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` (índice 1..12)
- `docs/_archive/progressos/progresso12.md` (este arquivo)

**NÃO tocados** (deliberadamente):
- `docs/arquitetura/MODELO_DE_DADOS.md` (sem mudança de schema)
- Sem novo ADR (implementa o ADR-012 já aceito)
