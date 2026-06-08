# Calibração v2 da Matriz + Recuperação do RAG — caso real #12

> PR `fix/matriz-v2-rag-recuperacao`. Base `main`.
> Continua a calibração v1 (`matriz_calibracao.md`, caso #11) com os 5 defeitos
> que o caso **#12** (Fazenda São Jorge — Leonardo Ribeiro, São João d'Aliança/GO)
> expôs após o #70 passar a mostrar as fontes por linha da matriz.
> Data: 2026-06-07. Método: **medir no dump real de produção antes de corrigir.**

Fontes da medição (Supabase prod, `project_id=diquycxxkfrjhxtrcmzb`):
`extracted_field_staging` do `process_id=12`; `knowledge_catalog` (24.233 chunks);
`legislation_documents` (53 docs, 52 com `demand_types`).

---

## A. Parse decimal PT-BR — a "fazenda de 3,5 milhões de ha"

**Medido.** A matrícula `4655` tinha DOIS registros no staging (doc 171):
- `area_ha` = `349.9022` com hint `"4655"` (ok);
- `area_ha` = `{"value": 349.9022, "confidence": "high"}` (um **dict** no `value`!)
  com hint `"{'value': '4655', 'confidence': 'high'}"`.

Causa raiz: `_to_float_br` recebia o dict via `_row_value`. `str(dict)` vira
`"{'value': 349.9022, 'confidence': 'high'}"`; após limpar não-numéricos sobra
`"349.9022,"` — e a **vírgula do separador do dict** disparava o ramo PT-BR
(`.replace(".","").replace(",",".")`) → `3499022.0`. Esse valor entrava na
`soma_matriculas`, que dava **3.502.448 ha** (≈ metade de Goiás).

**Fix** (`inconsistency_matrix.py`):
- `_to_float_br` rejeita dict/lista crus e **desembrulha** `{value}` → escalar.
- `_normalize_number_str`: separador decimal = o **último** entre `.` e `,`
  (`1.010,7113`→`1010.7113`; `1,234.56`→`1234.56`; `349,9022`→`349.9022`;
  `660.6561` permanece decimal).
- `parse_area_ha(value, unidade)`: função **única** de parse de área, com m²→ha
  quando a unidade está marcada (`3.502.445,851 m²`→`350,2445851 ha`).
- Sanidade: área > **100.000 ha** sai do confronto/soma e vira linha
  `area_revisao` (atenção). Defesa em profundidade — com o parse corrigido o
  dict já vira `349,9022` e a linha de revisão nem aparece no #12.
- Origem (`ficha01_extraction.py`): `_unwrap_llm_value` desembrulha o envelope
  `{value, confidence}` que o LLM às vezes devolve, antes de persistir — fecha o
  vazamento na fonte (afeta extrações novas).

**Antes × depois (matriz do #12):** soma das matrículas `3.502.448 ha` →
plausível (`< 100.000`); imóvel ~`1.010,7 ha`. Sem `area_revisao`.

## B. matricula_hint poluído

**Medido.** Hints reais que viravam matrículas/colunas distintas:
`"{'value': '4655', ...}"` (dict serializado), `"492262"` (nº de TAD),
`"4655 (2 de 3)"` (fatia de georref), `"MATR. 2.923 R-01"`, `"6.776"` (ponto de
milhar). ITR vinha **sem** hint (`numero_matricula` ausente).

**Fix:** `_clean_matricula_hint` (regex) — desembrulha dict, remove anotações
(`R-01`, `AV-3`, `(2 de 3)`) e prefixo (`MATR.`), normaliza milhar
(`4.655`→`4655`); `"?"`/vazio → `None`. Aplicado em `_group_sources`,
`_collect_areas`, no confronto `car_mats × staging_mats` (os dois lados) e na
origem (`ficha01_extraction.py`, hint e `matriculas[].numero`).
Área de nível matrícula **sem hint** (ITR) não confronta — vai para a linha de
atenção `area_sem_vinculo` ("campos sem vínculo de matrícula").

**Antes × depois:** colunas `{'value'...}`, `MATR. 2.923 R-01`, `4655 (2 de 3)`,
`6.776` → colapsam em `4655`/`2923`/`6776`/`4698` (chaves só-dígitos).

## C. Denominação com lixo

**Medido.** `sigef.denominacao = "Certidão de Embargo"` (doc 193) — título de
documento, não nome do imóvel. (`itr: "FAZENDA SAO JORGE - LOTE 02AA"` é **real**:
o intake do #12 reúne vários lotes — 01-A, 01-B, 01-C, 02AA, 02AC — cada ITR de um
lote; não é lixo, é multi-imóvel. Reportado, não tratado como erro.)

**Fix:** `_is_doc_title` descarta candidatos a denominação que começam com
prefixos de título de documento (`certidao`, `recibo`, `relatorio`, `parecer`,
`embargo`, `auto de`, …).

**Antes × depois:** `"Certidão de Embargo"` some da `denominacao_imovel`; só
denominações reais (`Fazenda …`) permanecem.

## D. Recomendação cruzada

**Medido.** A pendência de **categoria "Documentos"** cujo `detalhamento` lista
"…Licença Ambiental e **Autorização de Desmatamento**…" casava o tema
`supressao` (keyword `"desmat"`, que vinha antes de `documentos` na ordem). Como
essa mesma pendência tinha `recomendacao` de **acesso** ("…detalhando a descrição
de acesso…"), nascia a falsa linha **"Supressão pós-2008"** com a ação de acesso
e a fonte listando os documentos exigidos.

**Fix:** `_classificar_pendencia` respeita a **categoria** "Documentos" — vira
`documentos` (lista de documentos solicitados), salvo quando o detalhamento fala
de acesso (caso #11, onde acesso vinha rotulado "Documentos"), aí vira `acesso`.
Um pedido de documentos nunca mais vira linha técnica de supressão.

**Antes × depois:** sem `tecnica:supressao`; cada linha técnica
(cobertura/UC/hidrografia) leva a recomendação **da sua própria** pendência;
o pedido de documentos vai para `documentos_solicitados`.

## E. RAG: zero trechos com corpus populado

**Medido em prod (mesma busca do agente).** Corpus **presente**:
`knowledge_catalog = 24.233`, `legislation_documents = 53`, embeddings
`text-embedding-3-small:768` (mesmo provedor da consulta — **sem** incompatibilidade
de espaço vetorial). Mesmo assim, 0 trechos. Duas causas:

1. **Sentinela `demand_type`.** O processo #12 tem `demand_type="nao_identificado"`.
   O agente passava isso ao filtro `demand_types @> ["nao_identificado"]` — e essa
   tag **não existe** no corpus (tags reais: `licenciamento`, `car`,
   `retificacao_car`, …). Contagem real do JOIN: **0 linhas** (stage 1 e o
   fallback que solta a UF). É a causa primária.
2. **UF exclui federal.** `kc.uf = :uf` com `uf='GO'` retornava 4.280 chunks e
   **excluía os 761 federais** (`uf IS NULL`).

| filtro | linhas (medido) |
|---|---|
| `uf=GO` + `demand_type=nao_identificado` | **0** |
| fallback (sem UF) + `demand_type=nao_identificado` | **0** |
| `uf=GO`, sem demand_type | 4.280 |
| `uf=GO OR federal`, sem demand_type | **5.041** |

**Fix:**
- `legislacao.py`: `demand_type` sentinela (`nao_identificado`, …) → `None`
  (sem filtro de demanda); fallback adicional que **solta o demand_type** quando
  o JOIN estrito zera (similaridade pura ainda recupera).
- `knowledge_catalog.search`: filtro de UF passa a incluir federal —
  `(kc.uf = :uf OR kc.uf IS NULL)`.

**Provado (corpus local, embeddings reais):** a mesma consulta do #12 retorna
**8 trechos** (sim ~0,69) citando normas GO reais (IN SEMAD 3/2025,
Lei GO 18.104/2013, Lei GO 21.231/2022). Antes: **0**. Teste DB-backed
(`test_knowledge_catalog_search.py`) trava `uf=GO ⇒ GO+federal`.

> Nota: a **ausência do corpus em produção** (dívida #47) é separada — aqui o
> corpus está populado; estes fixes garantem que, populado, a recuperação funciona.

---

## Escopo / proibições respeitadas

- **Não** mexi no contrato de fontes do #70 (`fontes_detalhe` intacto).
- **Não** refiz chunking/corpus do RAG — só a **recuperação** (filtros do
  `search` + saneamento de `demand_type` no agente).
- Prompts dos agentes inalterados.

## Testes

- `tests/services/test_matriz_caso12_real.py` (7) — shapes reais do #12, um por
  defeito A–D, no STAGING bruto de produção.
- `tests/services/test_knowledge_catalog_search.py` (4) — uf inclui federal
  (DB+pgvector) e sentinela `demand_type` → None.
- `test_matriz_caso11_real.py` / `test_inconsistency_matrix.py` /
  `test_ficha01_extraction.py` atualizados (hint normalizado) — verdes.
- Suíte completa: **895 passed**.
