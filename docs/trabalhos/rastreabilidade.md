# Rastreabilidade — "nenhuma afirmação sem fonte" (P1 da validação 06/06)

> PR `feat/rastreabilidade-fontes` (base main). Princípio 11 do produto
> (`docs/manifesto/03-PRINCIPIOS.md`). Contrato: `{afirmação, fonte, confiança}`.
> Aditivo: nenhum shape antigo quebra. Validação LLM (diagnóstico/legislação) é
> pós-deploy (rodar a chain no caso real); matriz é validada já (determinístico).

## Contrato comum

`app/schemas/stage_output.py`:
- **`SourceRef`** `{tipo, ref, descricao, valor, confianca, sem_fonte}` — reusável por
  todos os agentes. `tipo ∈ {documento, matriz, rat, legislacao, atendimento, auditor, sem_fonte}`.
- **`Afirmacao`** `{texto, categoria, fontes: list[SourceRef]}`.
- `sources: list[SourceRef]` aditivo em `Divergencia`, `Risco`, `Etapa`.
- `afirmacoes: list[Afirmacao]` aditivo em `DiagnosticoPreliminarContent`.
- `Etapa.prazo_fonte` ∈ {`norma`, `estimativa_profissional`}.

**Regra dura (anti-invenção):** fonte específica OU `sem_fonte=True` (marcado na UI).
Nunca genérico ("conforme documentos"). Preferir omitir a inventar.

## 1. Auditor / Matriz (determinístico — só expor)

`inconsistency_matrix.py`: `MatrixRow.fontes_detalhe` (aditivo; `fontes` dict mantido).
`_Source` captura `document_id`; pós-pass por linha gera
`[{fonte, tipo, source_doc_type, document_id, valor, protocolo?}]`. Linhas técnicas
referenciam o RAT (protocolo). UI: chips de fonte por linha (`AgentResultRenderer`).

| linha | ANTES | DEPOIS |
|---|---|---|
| denominação | "divergente" | + fontes_detalhe: `[{documento, id 141, "Gleba 01 B"}, {documento, id 165, "Shangri-lá"}]` |
| área | "atenção" | + `[{matriz, soma_matriculas: 349,9}, {rat, valor 1010,7, protocolo GO-RAT-2024-002207}]` |
| técnica UC | "crítico" | + `[{rat, protocolo GO-RAT-2024-002207}]` |

## 2. Diagnóstico (LLM — fonte do contexto)

`diagnostico.py`: prompt lista insumos com identificadores + **regra inviolável**
("cada passivo/ação cita a fonte ou 'sem fonte identificada'; nunca inventar").
Parser `_build_afirmacoes`: usa o `afirmacoes` do LLM (com `fonte`) ou, no piso,
gera afirmações dos passivos/ações marcadas `sem_fonte` (honesto). UI: seção
"Afirmações com fonte" com chips (sem fonte = badge âmbar).

| afirmação | ANTES | DEPOIS |
|---|---|---|
| "houve supressão" | sem fonte | `{texto, fontes:[{rat, GO-RAT-2024-002207 — cobertura}]}` |
| "ação: retificar CAR" | string solta | `{texto, fontes:[{matriz, linha cobertura}]}` |
| afirmação sem base | invisível | `{fontes:[{sem_fonte:true}]}` → "⚠️ sem fonte identificada" |

## 3. Legislação (LLM + RAG — grounding)

`legislacao.py`: os trechos do RAG já entram no prompt numerados `[N]` com IDs.
**Regra dura:** cada norma/prazo aponta o `[N]`; sem base → `prazo_fonte=
"estimativa_profissional"`. `_normalize_etapas` aplica o piso (prazo sem trecho →
estimativa marcada + `SourceRef(sem_fonte)`); com trecho → `prazo_fonte="norma"` +
`SourceRef(legislacao)`. UI: badge "⚠️ estimativa profissional — sem fonte normativa".

| item | ANTES | DEPOIS |
|---|---|---|
| prazo 30 dias | "Prazo: ~30 dias" | + trecho `[3]` (norma) OU "⚠️ estimativa profissional" |
| norma citada | identificador solto | aponta o trecho `[N]` do RAG recuperado |
| prazo "da cabeça" | indistinguível | marcado estimativa (mata o prazo inventado) |

## Escopo / proibições respeitadas

- **Aditivo**: `fontes` (matriz), `hipoteses`/`checklist_documental` (diag),
  shapes de `AIJob.result` — todos intactos. Renderers antigos não quebram
  (testes de contrato + tsc/build verdes).
- Escopo TEMÁTICO da legislação **não** ampliado (rodada de base/skill é separada).
- Atendimento/Orçamento/Redator **não** tocados — mas o `SourceRef` nasceu genérico
  (schema comum) para eles aderirem na rodada deles.

## Validação

- Determinístico (agora): `test_rastreabilidade_contract.py` (aditividade + matriz
  fontes_detalhe com doc/valor + linha técnica → RAT); matriz/auditor sem regressão;
  ruff + mypy limpos; tsc + build verdes.
- LLM (pós-deploy, por André): rodar a chain no caso #11 e conferir 3-5 itens de
  diagnóstico/legislação contra os docs — nenhuma fonte inventada; itens sem base
  marcados.
