# Corpus federal — pacote A (direito sancionador e processual)

**Branch:** `feat/corpus-federal-defesa` · **Data:** 2026-07-31 · **ADR:** 037

> O PR do polimento (#126) mergeou durante esta sprint. As dívidas foram para
> `docs/REGISTRO_DIVIDAS.md` (**#95 a #99**, renumeradas — o polimento havia
> usado #91–94) e o pulso para `docs/estado/progressoIA.md`. Este documento é o
> registro do trabalho.

---

## O que foi feito

Medição de 31/07 concluiu que o corpus federal era pequeno por **escopo**, não
por falha: `scripts/ingest_federais_canonicos.py` era uma lista fixa de 10
diplomas de 23/04. O pacote A cobre o buraco que o caso 15 sangra — o direito
sancionador e processual federal.

**9 diplomas ingeridos, 815 chunks, US$ 0,0030 de embedding.**
Federal + nacional: 785 → 1.600 chunks.

| diploma | chunks | vigência | fonte |
|---|---:|---|---|
| Decreto 6.514/2008 | 272 | vigente | Planalto (oficial) |
| IN IBAMA 19/2023 | 146 | vigente | DOU (oficial) |
| IN IBAMA 10/2012 | 144 | histórica até 29/01/2020 | **LegisWeb (não-oficial)** |
| Lei 9.784/1999 | 81 | vigente | Planalto (oficial) |
| Decreto 3.179/1999 | 70 | histórica até 22/07/2008 | Planalto (oficial) |
| Lei 4.771/1965 | 65 | histórica até 25/05/2012 | Planalto (oficial) |
| MPV 780/2017 | 14 | histórica até 24/10/2017 | Planalto (oficial) |
| Lei 13.494/2017 | 13 | vigente | Planalto (oficial) |
| Decreto 11.373/2023 | 10 | vigente | Planalto (oficial) |

Medição A/B (mesma pergunta, mesmo modelo, corpus como única variável):
`ops/medicao_corpus_federal/{antes,depois}.json`.

---

## Dívidas abertas

Registradas em `docs/REGISTRO_DIVIDAS.md`:

- **#95** — corpus antigo com mojibake (`U+FFFD`), vindo de abril
- **#96** — espaço não-quebrável em 998 chunks do corpus antigo
- **#97** — proveniência sem campo próprio no modelo (com proposta de colunas)
- **#98** — IN IBAMA 10/2012 de fonte não-oficial (pedido de PDF à Isis)
- **#99** — pacotes B e C, backlog nomeado, não executar sem decisão
- **encaixe com #85** (vigia de revogação): esta sprint entrega a metade de
  baixo; falta o gatilho, e ele precisa **reindexar** o documento que marcar

---

## Auditoria de proveniência (item 0) — resultado

| origem | esfera | docs | chars | % do texto | oficial? | rastreável? |
|---|---|---:|---:|---:|---|---|
| PDF de disco (origem não declarada) | estadual | 37 | 27.758.126 | 83,9% | não se sabe | **não** |
| Arquivo `.md` compilado | estadual (AC) | 10 | 4.422.133 | 13,4% | não (compilação) | **não** |
| Planalto | federal | 7 | 407.768 | 1,2% | **sim** | sim (URL) |
| PDF de disco (origem não declarada) | federal | 6 | 376.775 | 1,1% | não se sabe | **não** |
| Arquivo `.md` compilado | nacional | 1 | 65.573 | 0,2% | não (compilação) | **não** |
| Portal `.gov.br` | federal | 2 | 52.854 | 0,2% | **sim** | sim (URL) |
| CONAMA/MMA | federal | 1 | 13.438 | 0,0% | **sim** | sim (URL) |

**10 de 64 documentos (15,6%) têm origem oficial rastreável — e eles são 1,4% do
texto.** Os compêndios estaduais (`MT-NUC01`, 3.024.075 chars) são PDFs de disco
sem qualquer registro de quem os compilou ou de que fonte. Os 10 documentos do
Acre são `.md` — texto já compilado por alguém, não coleta oficial.

O campo de proveniência **não existe** no modelo: há `url` (nulo em 54 dos 64) e
`file_path` (caminho local), e nenhum campo diz se a fonte é oficial. Proposta
na dívida #93.
