# Consolidação do caso 13 não gravava (500) + limpeza do staging na origem

**Branch:** `fix/consolidacao-clique-grava` (base `main`)
**Data:** 2026-06-29
**Relacionado:** `fix_consolidacao.md` (#79, gate + parcial), `matriz_v2_rag.md` (#72,
`_is_doc_title`), `parse_consolidacao.md`, Princípio 11 (fonte/não inventar),
Princípio 2 (auditável).

## Sintoma medido (prod, caso 13)

O consultor rodou os agentes, decidiu os campos e clicou **"Consolidar na base"** —
e **nada gravava**. `audit_logs action='consolidar'` (entity_id=13) = **vazio**;
`properties.field_sources = {}`; 0 matrículas. O painel ainda mostrava as lacunas
("Matrícula não preenchida", "Área não informada") e a tela estava **poluída**
(valores repetidos, lixo em campos de código).

## TASK 1 — por que o clique não gravava (o 500)

O console do navegador entregou a prova: `POST /processes/13/consolidar → 500`.
Reproduzido **localmente** (Postgres real) com os dados do painel:

```
psycopg2.ProgrammingError: can't adapt type 'dict'
UPDATE matriculas SET averbacao_app=%(averbacao_app)s ...
parameters: {'averbacao_app': {'area': '186,1647', 'referencia': 'matrícula n° 4.655'}}
```

**Causa-raiz:** o extrator às vezes stage `averbacao_app`/`averbacao_rl` (e outros)
como **dict estruturado**; `consolidate_process` tentava gravar esse dict numa
coluna **Text** → o driver recusa → **500** → **rollback de toda a transação** →
nada grava, e por isso nem o `audit` aparece. O botão, o endpoint e o gate estavam
corretos; quebrava no **commit**.

**Fix** (`app/services/staging_consolidation.py`): `_coerce` passou a **serializar
dict/list em texto legível** (`_stringify_structured` → "chave: valor · …") quando
a coluna de destino é `String`/`Text`. Colunas JSON portáveis (ex.: `proprietarios`)
**não** são `String` → preservam o dict. Degradar com elegância, nunca crashar.

Provado: `tests/api/test_repro_caso13.py` — consolidação grava (matrícula criada,
averbação como texto, `audit='consolidar'`, 3 ações de divergência), 200 (era 500).

## TASK 2 — limpar o staging na ORIGEM (a "tela horrível")

Três classes de sujeira, corrigidas em `app/services/ficha01_extraction.py`:

- **2a — duplicata de formato.** "349.9022" e "349,9022" (mesmo dado, formatos
  diferentes) viravam 2 linhas porque a dedup comparava string crua. Novo
  `_numeric_dedup_key` (último separador = decimal) canoniza o número; campos com
  unidade deduplicam por valor numérico. "349.9022" ≡ "349,9022" ≡ "349,9022 ha".
- **2b — lixo em campo de código.** "Código de certificação SIGEF" recebia frases
  ("Certidão de Embargo", "Coordenadas não disponíveis", "Plano de Recuperação
  (PRAD)", "Área embargada em…"). `_is_garbage_for_code` (reusa `_is_doc_title` do
  #72 + heurística de frase-sem-token-de-código) **descarta** esses valores nos
  campos `_CODE_FIELDS` — UUID/código real passa intacto.
- **2c — lista virando N linhas.** "Regulatory issues · 4 itens" ×8, "Ônus · 6
  itens" repetido. Campos-lista (`pendencias_rat`, `onus`) **colapsam em 1** por
  (campo, matrícula), mesmo que re-extrações produzam listas ligeiramente
  diferentes (`_dedup_token` → `__list__`).

A dedup agora vale **intra-doc** (`build_staging_fields`) e **cross-run**
(`extract_and_stage`, contra o que já está no banco) — re-extrair não acumula.

Provado: `tests/services/test_ficha01_staging_limpeza.py` (7 testes: normalização,
descarte de lixo, colapso, e dedup cross-run em Postgres real).

> Observação: a limpeza age em extrações **novas**. O staging atual do caso 13 já
> está poluído; re-extrair (pós-deploy) produz o staging limpo. A consolidação (TASK 1)
> funciona com o staging atual — não depende da limpeza.

## Validação

- `test_repro_caso13.py` 1 verde (consolidação grava).
- `test_ficha01_staging_limpeza.py` 7 verdes (limpeza).
- Regressão: `test_fase4_consolidacao` + `test_acoes` + `test_auditor_matriz` +
  `test_matricula_staging` (29) + `test_ficha01_extraction` + validators + extrator
  (28) — todas verdes. ruff limpo. Sem migration (mudança só de lógica).
- **Pós-deploy (André):** clicar "Consolidar na base" uma vez → Hub enche
  (Matrícula/Área/RL); divergências viram ações; audit registra.

## Fora de escopo / proibido
- Não alterar prompts/chains dos agentes (config congelada). A limpeza é
  pós-extração (mapeamento staging), não prompt.
- `client-portal/`, `mobile/` congelados (ADR-009).
