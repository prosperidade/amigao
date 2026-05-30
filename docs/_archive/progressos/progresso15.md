# Progresso 15 — PROMPT_11: hotfix `ignorada` volta a exigir decisão

## Projeto: Regente Ambiental
## Referências: #23 (PROMPT_10, furo) · #19 (justificativa obrigatória) · ADR-012 / Princípio 2 (auditabilidade)

---

## Objetivo da rodada

Corrigir o furo introduzido no PROMPT_10: a exclusão de `ignorada` do gate
camada 2 abriu um atalho pra silenciar crítico real sem justificativa,
recriando a porta que o #19 fechou. Hotfix urgente — o #10 já estava em
main (PR #12).

---

## Causa raiz (lição)

O PROMPT_10 tratou `descartada`, `resolvida` e `ignorada` como simétricos
("achados terminais"). **Não são:**

- `descartada` = "não é divergência real" → nada a decidir → excluir OK.
- `resolvida` = "corrigida no mundo" → nada a decidir → excluir OK.
- `ignorada` = "consultor optou por não tratar" (achado **REAL** posto de
  lado) → tem o que decidir → **NÃO** excluir.

A exclusão de `ignorada` veio de uma recomendação rasa (apresentada como
"recomendado" num AskUserQuestion durante o PROMPT_10) baseada em
"simetria com descartada", sem checar o impacto cruzado no #19. A pergunta
que faltou: "excluir esse estado abre caminho pra pular uma garantia que
outra regra já estabeleceu?". Abria — o #19 obriga justificativa para
ignorar via decisão, mas `status_achado=ignorada` não exige justificativa
nenhuma (`RegulatoryIssueUpdate` só valida coerência). André pegou na
revisão, antes de qualquer assinatura em produção.

---

## A mudança (escopo fechado)

### Código (1 linha) — `app/api/v1/regulatory.py`
Filtro do gate camada 2:
- Antes (PROMPT_10): `status_achado.in_([suspeita, confirmada])`
- Agora (PROMPT_11): `status_achado.in_([suspeita, confirmada, ignorada])`

Só `descartada`/`resolvida` ficam excluídas. Comentário do gate reescrito
explicando por que `ignorada` é diferente dos outros dois terminais.

### Testes — `tests/api/test_regulatory.py`
`test_200_critica_ignorada_sem_decisao_libera_gate` (do PROMPT_10, que
documentava o furo) virou
`test_422_critica_ignorada_sem_decisao_continua_bloqueando`: ignorada
exige decisão. Os outros 3 cenários do PROMPT_10 seguem intactos
(`descartada`/`resolvida` liberam; `confirmada` continua exigindo).

Subset `TestValidateDiagnosisGateCamada2`: 11/11. Suite cheia: 639/639.

### Docs
- `REGISTRO_DIVIDAS`: #23 corrigido (só `descartada`/`resolvida`
  excluídas; nota sobre por que `ignorada` voltou). Header pós-PROMPT_11.
- `ESTADO_ATUAL`: bullet do gate corrigido + header + frente em revisão.
- `progressoIA`: seção PROMPT_11 (esta rodada).
- `API_v1`: condição do 422 do `/validate` corrigida (2 menções).
- `FLUXOS_E2E`: nota do Fluxo 2 corrigida.
- `GOVERNANCA`: índice 1..15.
- `progresso15.md` (este arquivo).

---

## Sem deadlock

Quem quer ignorar um crítico real registra `decisao=ignorar_justificado`
no PUT /decision (exige justificativa, #19). A Regra B permite porque
`ignorada` ≠ `suspeita`. Fecha só o caminho sem-justificativa; o caminho
justificado fica.

---

## Arquivos tocados

**Código (commit 1):**
- `app/api/v1/regulatory.py` (filtro do gate + comentário)

**Testes (commit 2):**
- `tests/api/test_regulatory.py` (1 teste virado 200→422)

**Docs (commit 3):**
- `docs/REGISTRO_DIVIDAS.md`
- `docs/estado/ESTADO_ATUAL.md`
- `docs/estado/progressoIA.md`
- `docs/arquitetura/API_v1.md`
- `docs/arquitetura/FLUXOS_E2E.md`
- `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md`
- `docs/_archive/progressos/progresso15.md` (este arquivo)

**NÃO tocados:**
- `MODELO_DE_DADOS` — sem schema change. Sem ADR (refina #23/#10). Sem migration.
- Frontend — follow-on do badge fica pra próxima rodada curta.
