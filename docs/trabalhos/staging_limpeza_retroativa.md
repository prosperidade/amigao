# Limpeza RETROATIVA do staging + tradução de termos técnicos (caso 13)

**Branch:** `fix/staging-limpeza-retroativa-e-traducao` (base `main`)
**Data:** 2026-06-29
**Relacionado:** #81 (`fix_consolidacao.md` / `parse_consolidacao.md` — limpeza na
origem), #72 (`matriz_v2_rag.md` — `_is_doc_title`), `ui_termos_tecnicos.md`
(dicionário central de rótulos), Ficha 01 Fase 4.

## Problema

O Hub do caso 13 **já enche** (item zero fechado no #81). O que faltava era a
**qualidade da tela "Decisão & Consolidação"** (Conferência). O #81 limpou a
extração para casos NOVOS, mas o staging do caso 13 **já estava sujo de antes** —
a limpeza-na-origem não retroage. Persistiam 3 sujeiras + 1 termo cru em inglês:

1. **Duplicata de formato** — mesmo dado como 2 linhas: `349.9022` e `349,9022`;
   `660.6561`/`660,6561`; `14.44`/`14,4400`.
2. **Lixo em campo de código** — `numero_car`/`codigo_certificacao` preenchidos
   com frase/título (`"Certidão de Embargo"`, `"Coordenadas não disponíveis…"`,
   `"PRAD"`) que **não é código**.
3. **Lista repetida** — `pendencias_rat` ("Pendências regulatórias · 4 itens")
   e `onus` ("Ônus e gravames") duplicados N vezes.
4. **Termo cru em inglês** — `regulatory_issues` (target_field do `pendencias_rat`)
   caía no fallback humanizado → **"Regulatory issues"** na tela do consultor.

## TASK 1 — Saneamento retroativo (mesma regra do #81 aplicada ao staging gravado)

Toda a regra **reusa os helpers da origem** — nenhuma heurística nova:
`_dedup_token`, `_numeric_dedup_key`, `_is_garbage_for_code` (+`_is_doc_title` do
#72), `_CODE_FIELDS`, `_LIST_COLLAPSE_FIELDS`.

Novo serviço `sanear_staging_process(db, *, tenant_id, process_id, dry_run=False)`
em `app/services/ficha01_extraction.py`:

- **2b LIXO em código** — `field_name ∈ _CODE_FIELDS` e `_is_garbage_for_code(value)`
  → remove. **Preserva** se a linha já tem decisão do consultor
  (`aceito`/`rejeitado`) — não apagamos decisão sem necessidade.
- **2a DUPLICATA DE FORMATO** — agrupa por `(fonte, campo, hint, token)`; o `token`
  numérico (`_numeric_dedup_key`) iguala `349.9022`≡`349,9022`. Grupo com >1 →
  mantém 1 canônica.
- **2c LISTA REPETIDA** — `pendencias_rat`/`onus` têm `token = "__list__"` →
  colapsa em 1 por `(fonte, campo, hint)`.

**Garantias:**
- A chave de grupo inclui o **token** do `_dedup_token`, então valores
  genuinamente diferentes (token distinto) **nunca** se fundem — divergências
  reais seguem como insumo da matriz. **Fontes diferentes não se fundem** (a
  fonte está na chave): cada fonte é insumo da matriz.
- **Preserva decisão na canônica** — a escolha da sobrevivente prioriza a linha
  decidida (`_pick_canonical`: decidida > `aceito` sobre `rejeitado` > lista mais
  rica / escalar em formato BR > menor id). Pôr a decidida como sobrevivente
  preserva a decisão sem transferência.
- **Idempotente** — após a 1ª passada cada grupo tem 1 linha; a 2ª remove 0.

### Comando de saneamento (`scripts/sanear_staging.py`)

Padrão `reindex_sync.py` (`SessionLocal` + `argparse`, rodável no container `api`
ou no venv host com o `.env` de prod). Deriva o tenant do processo se omitido.

```bash
python scripts/sanear_staging.py --process-id 13            # aplica
python scripts/sanear_staging.py --process-id 13 --dry-run  # só relata
python scripts/sanear_staging.py --process-id 13 -v         # lista cada linha tocada
```

Reporta antes×depois e linhas removidas/coalescidas (lixo / formato / lista) +
quantas decisões do consultor foram preservadas.

## TASK 2 — Tradução de termos técnicos na UI

`frontend/src/lib/labels/fieldLabels.ts` (fonte única de rótulos — `labelFor`):
- `regulatory_issues` → **"Pendências regulatórias"** (mata o "Regulatory issues"
  cru). `pendencias_rat` idem (defensivo, caso renderizado por `field_name`).
- Cobertos também os `field_name` de CAR que cairiam em fallback feio:
  `rl_declarada_ha`, `app_declarada_ha`, `area_declarada_ha`.

`ConsolidacaoPanel.tsx` já passava **tudo** por `labelFor(f.target_field || f.field_name)`
e `STATUS_LABEL` — o único furo era a ausência de `regulatory_issues` no dicionário.

## Validação

- `pytest tests/services/test_staging_saneamento_retroativo.py` — **10 verdes**:
  dedup de formato, valores reais não fundem, fontes não fundem, lixo em código,
  lixo decidido preservado, colapso `pendencias_rat`/`onus`, duplicata decidida
  mantém a decisão, idempotência (2×), dry-run não grava.
- `tests/services/test_ficha01_staging_limpeza.py` — **7 verdes** (limpeza do #81
  intacta, sem regressão).
- Suíte completa verde · `tsc --noEmit` verde.

### Aceite pós-deploy (caso 13 real)
- Rodar `python scripts/sanear_staging.py --process-id 13` (ver `RUNBOOK_DEV.md`).
- Tela de Conferência do caso 13: sem duplicata de formato, sem lixo em código,
  sem lista repetida, sem "Regulatory issues" nem outro termo em inglês.
- Casos novos continuam nascendo limpos (#81 intacto).
- Re-rodar o script: idempotente (remove 0).

## Fora de escopo / proibido
- Não apagar decisões do consultor; não quebrar a limpeza do #81; não exibir
  termo técnico cru.
- Outras frentes (Agentes IA do workspace, "0 gravados") são PRs separados — não
  tocadas.
- `client-portal/` e `mobile/` congelados (ADR-009) — não tocados.
