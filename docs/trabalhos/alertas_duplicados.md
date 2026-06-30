# Alertas regulatórios duplicados 11× na Visão geral — medição e fix

> Branch: `fix/alertas-regulatorios-duplicados`. Data: 2026-06-30.
> Caso medido: #13 São Jorge (process_id=13 → property_id=10), tenant 1,
> Supabase prod `diquycxxkfrjhxtrcmzb` (queries **read-only**).

---

## VEREDITO (TASK 0) — é GERAÇÃO, não exibição

O mesmo achado `VERIFICACAO_ESPACIAL_PENDENTE / geoespacial / informativo`
aparecia **11× idêntico** na Visão geral. A contagem real no banco prova que o
problema é de **geração** (duplicatas persistidas), não de render:

```
property_id=10 · codigo_alerta=VERIFICACAO_ESPACIAL_PENDENTE · tema=geometria
  n = 11   ids = [18,19,20,21,22,23,24,25,26,27,28]
  first_seen = 2026-06-13 22:53   last_seen = 2026-06-29 22:42
  payload (tema+descricao) IDÊNTICO nas 11 linhas
```

As 11 linhas são byte-idênticas e o `detected_at` está espalhado por ~2 semanas:
o auditor rodou 11 vezes (cada re-execução da chain `diagnostico_completo` em
E2/E4) e **cada execução inseriu uma duplicata nova**. O endpoint de leitura
(`GET /properties/{id}/issues`) faz `.all()` sem `distinct` — fiel ao banco. Logo
a tela mostra 11 porque há 11 linhas.

**Causa raiz:** `AuditorImovelAgent._persist_issues` fazia `session.add(...)` por
finding a cada execução, **sem dedupe** e sem unique constraint em
`regulatory_issues`.

### Sinal humano nas duplicatas (não apagar)

`status_achado` (perene no imóvel, ADR-012) carrega a decisão do consultor:

| ids | status_achado |
|-----|---------------|
| 18,19,20,21,24,25,26,27,28 (9) | `suspeita` (default — sem decisão) |
| 22 | `confirmada` |
| 23 | `descartada` |

Há **2 decisões CONFLITANTES** (uma confirmada, uma descartada) sobre o mesmo
achado lógico. Nenhuma tem `ProcessIssueDecision` vinculada (tabela vazia para
estas). `ProcessIssueDecision.issue_id` é `ondelete=CASCADE` — apagar uma issue
apagaria silenciosamente sua decisão contextual.

**Escopo global:** apenas **1 grupo** de duplicatas em todo o banco (este). Nenhum
outro imóvel afetado.

---

## TASK 1 — Fix (lado da geração)

1. **Idempotência na criação** (`app/agents/auditor_imovel.py` `_persist_issues`):
   antes de inserir, consulta as issues NÃO resolvidas do imóvel e pula o insert
   se já existe uma com a mesma `issue_dedupe_key` — reusando a issue existente
   (preserva `status_achado`/decisão). Re-rodar o auditor **não duplica**.

2. **Chave de dedupe** (`app/services/regulatory_dedupe.py`):
   `(property_id, codigo_alerta|type, tema, descricao)`. Por imóvel (achado é
   perene em `Property`). Inclui `descricao` para **não** colapsar achados
   distintos que só compartilham o código (ex.: duas divergências de área em
   matrículas diferentes coexistem).

3. **Saneamento retroativo** (`scripts/sanear_alertas_duplicados.py` +
   `sanear_alertas_duplicados()`), idempotente, espelha `sanear_staging.py`:
   - linhas DECIDIDAS são SEMPRE preservadas;
   - havendo ≥1 decidida, as não decididas do grupo são removidas (ruído);
   - sem decisão, mantém-se a mais recente;
   - grupos com **≥2 decididas conflitantes** são **reportados** e nada é apagado
     entre elas — resolução é humana (não destruímos julgamento).

   Rodar em prod (pós-deploy, dentro do container api):
   ```
   python scripts/sanear_alertas_duplicados.py --process-id 13 --dry-run
   python scripts/sanear_alertas_duplicados.py --process-id 13
   ```
   Efeito no caso 13: remove as **9** `suspeita` (ids 18,19,20,21,24,25,26,27,28),
   preserva **22** (confirmada) e **23** (descartada), e **reporta o conflito**.

### Pendência para o André (decisão humana)

Depois do saneamento, o caso 13 fica com **2 cards** (confirmada × descartada),
não 1. As duas são decisões humanas conflitantes sobre o mesmo achado — provável
fallout do bug (consultor clicou em duplicatas). Como decidir:

- **(A)** Foram cliques de teste → resetar ambas para `suspeita` e deixar o dedupe
  manter 1. (Posso adicionar um passo/flag explícito quando o André confirmar.)
- **(B)** Uma decisão vale → o André diz qual; mantemos essa 1.

Enquanto não houver definição, o script **não** apaga nenhuma das 2 decididas.

---

## Validação

- `tests/services/test_regulatory_dedupe.py` (9 testes): chave de dedupe,
  saneamento (colapso, preservação de decisão, conflito reportado, idempotência,
  não toca resolvidas) e **geração idempotente** (2 execuções de `_persist_issues`
  → 1 linha).
- Regressão: `test_auditor_imovel.py`, `test_regulatory.py`,
  `test_diagnostico_consume_auditor.py` — verdes (55 passed com `.env` de dev).
- Aceite pós-deploy (caso 13): rodar o script; Visão geral mostra o alerta sem as
  9 duplicatas; re-rodar o auditor não recria; decisões (22/23) preservadas.
