# Corpus SEMAD — Inventário preliminar

> **Status:** sessão 1 de 2 — discovery, decisões arquiteturais e classificação heurística estática (sem LLM, sem ingestão).
> **Data:** 2026-05-20
> **Branch:** `feat/corpus-semad-ingestao` (worktree em `../regente-corpus-semad/`)
> **Próxima sessão:** classificação LLM batch dos 283 PDFs + ingestão no `knowledge_catalog` (pgvector).

---

## 1. Inventário totais

| Origem | PDFs | Outros |
|---|---:|---|
| `Licenciamento (SEMAD)/` | 242 | — |
| `Manuais (SEMAD)/` | 41 | 3 `.xlsx` (fora da taxonomia A/B/C/D) |
| **Total PDFs** | **283** | |

### Classificação heurística por nome de arquivo

| Tipo | Descrição (taxonomia do enunciado) | Qtd | % |
|---|---|---:|---:|
| **A** | Matriz IPÊ (fluxograma decisório) | 230 | 81,3% |
| **C** | Gabarito de laudo técnico | 28 | 9,9% |
| **D** | Manual de uso do sistema IPÊ | 7 | 2,5% |
| **B** | Norma procedural densa | 4 | 1,4% |
| **indefinido** | Sem padrão claro no nome | 14 | 4,9% |
| | | **283** | **100%** |

> **Confiança:** baixa-média. Classificação é baseada SÓ no nome do arquivo (regex). Pode haver falsos positivos especialmente no Tipo A (qualquer arquivo com código `\d+ - ` ou `[A-Z]\d+ - ` no início vira A). A classificação **final exige leitura do conteúdo via LLM** — fica para a próxima sessão. Esta tabela é só pré-classificação para dimensionar o trabalho e identificar anomalias.

### Distribuição esperada vs encontrada

A taxonomia do enunciado descrevia 4 tipos como se fossem comparáveis em volume. A realidade do corpus SEMAD-GO é:

- **Matrizes IPÊ dominam** (~81%). Faz sentido — é o output principal do sistema IPÊ, um fluxograma decisório por tipo de licença/atividade.
- **Gabaritos de laudo (10%)** são poucos mas críticos — definem estrutura dos relatórios técnicos que o consultor entrega.
- **Manuais IPÊ (3%)** são poucos e bem definidos.
- **Normas procedurais (1%)** são minoria — basicamente compensação florestal, DAI, instrução normativa SEMAD, e o documento de inexigibilidade.

Implicação para skills: **a maior parte do corpus serve o Agente Atendimento / Diagnóstico** (matrizes IPÊ orientam questionários de licenciamento). Gabaritos servem **Redator**. Manuais servem **Acompanhamento** (orientar cliente no portal IPÊ).

---

## 2. Tipo A — Matriz IPÊ (230 docs)

Pré-classificados via regex de código no início do nome:
- Códigos numéricos: `89 -`, `7841 -`, `7992 -`, etc.
- Códigos alfanuméricos: `A1.1.1 -`, `Y1.2 -`, etc.
- Palavras-chave fortes: `REQUERIMENTO`, `VIABILIDADE LOCACIONAL`, `QUESTIONÁRIO`

**5 exemplos representativos:**

- `2.2 - Reservatórios barragens REG.pdf`
- `7841 - Y1.2 - CORRETIVO - PECUÁRIA EXTENSIVA E SEMIEXTENSIVA.pdf`
- `7992 - REQUERIMENTO PECUÁRIA.pdf`
- `7996 - REQUERIMENTO PECUÁRIA- CORRETIVO.pdf`
- `8017 - VIABILIDADE LOCACIONAL - REGISTRO DE LIMPEZA DE ÁREA E CAI.pdf`
- `A1.1.1 - Conversão do uso do solo (asv) LAO.pdf`

**Metadados a extrair (próxima sessão):**
- `licenca_codigo` (ex: "89", "7841", "A1.1.1")
- `licenca_nome` (texto após o código)
- `tipo_questionario` (Requerimento / Viabilidade locacional / Questionário / etc.)
- `tipo_licenciamento` (LAE, REG, LAC, LAO, etc.)
- `tipos_licenca_aplicaveis` (lista)

---

## 3. Tipo C — Gabarito de laudo (28 docs)

Pré-classificados via regex de `LAUDO`, `TERMO DE REFERÊNCIA`, `ROTEIRO`, `RELATÓRIO TÉCNICO`, prefixo `TR `.

**5 exemplos representativos:**

- `LAUDO DE ESTANQUEIDADE DO SISTEMA DE ARMAZENAMENTO AÉREO DE COMBUSTÍVEIS - SAAC.pdf`
- `ROTEIRO PLANTIO COMPENSATÓRIO_ Revisão 3.pdf`
- `Termo de Diagnóstico de Fauna - Outros Empreendimentos.pdf`
- `Termo de Referência  Linha de Distribuiçãopdf.pdf`
- `TR  RELATÓRIO TÉCNICO CONCLUSIVO  INSTALAÇÃO DO EMPREENDIMENTO OU PARTES DELE EM ÁREA DE PRESERVAÇÃO PERMANENTE APPpdfpdf.pdf`

**Metadados a extrair:**
- `tipo_laudo` (ex: "estanqueidade_saac", "diagnostico_fauna")
- `normas_tecnicas` (NBRs, ASMEs, APIs)

**Observação:** vários nomes têm `pdfpdf.pdf` no final (download duplicado) ou `pdf` sem extensão (renomeio estranho). Não afeta classificação mas o nome canônico precisa ser normalizado na ingestão.

---

## 4. Tipo D — Manual IPÊ (7 docs — lista completa)

- `Licenciamento (SEMAD)/Portal de Licenciamento Ambiental.pdf`
- `Manuais (SEMAD)/Manual - Ampliação_Alteração.pdf`
- `Manuais (SEMAD)/Manual Alteração de Empreendedor.pdf`
- `Manuais (SEMAD)/Manual AUMPF.pdf`
- `Manuais (SEMAD)/Manual de Autorização para Averbação de Servidão Ambiental.pdf`
- `Manuais (SEMAD)/MANUAL DE DISPENSA D (1).pdf`
- `Manuais (SEMAD)/Manual de Queima Controlada.pdf`

**Metadados a extrair:**
- `procedimento` (ex: "alteracao_empreendedor", "aumpf", "averbacao_servidao_ambiental", "queima_controlada", "dispensa_d")
- `agente_consumidor` (provavelmente Agente Acompanhamento / Atendimento)

---

## 5. Tipo B — Norma procedural (4 docs — lista completa)

- `Manuais (SEMAD)/Atividades Inexigibilidade.html.pdf`
- `Manuais (SEMAD)/Compensação Florestal e Compensação Por Danos Ambientais.pdf`
- `Manuais (SEMAD)/Guia DAI - final.pdf`
- `Manuais (SEMAD)/ON_01_2021_SEMAD - Errata.pdf`

**Metadados a extrair:**
- `tema` (ex: "compensacao_florestal", "dai", "inexigibilidade")
- `leis_referenciadas` (citações de leis/decretos no corpo do texto)

**Observação:** "Atividades Inexigibilidade.html.pdf" parece ser um print/save de HTML — verificar se o conteúdo é navegável ou só captura de tela.

---

## 6. Indefinidos (14 docs — todos precisam revisão)

Todos os 14 indefinidos são variantes do arquivo `tipologias_disponiveis*.pdf` em `Licenciamento (SEMAD)/`:

```
tipologias_disponiveis.pdf
tipologias_disponiveis (1).pdf
tipologias_disponiveis (2).pdf
...
tipologias_disponiveis (13).pdf
```

### Achado importante: NÃO são duplicatas exatas

Tamanhos variam significativamente:

| Arquivo | Tamanho (bytes) |
|---|---:|
| `tipologias_disponiveis.pdf` | 326.238 |
| `tipologias_disponiveis (1).pdf` | 293.850 |
| `tipologias_disponiveis (2).pdf` | 321.235 |
| `tipologias_disponiveis (3).pdf` | 300.494 |
| `tipologias_disponiveis (4).pdf` | 296.792 |
| `tipologias_disponiveis (5).pdf` | 293.818 |
| `tipologias_disponiveis (6).pdf` | 310.506 |
| `tipologias_disponiveis (7).pdf` | 300.652 |
| `tipologias_disponiveis (8).pdf` | 305.070 |
| `tipologias_disponiveis (9).pdf` | 349.820 |
| `tipologias_disponiveis (10).pdf` | 294.230 |
| `tipologias_disponiveis (11).pdf` | 303.185 |
| `tipologias_disponiveis (12).pdf` | 293.385 |
| `tipologias_disponiveis (13).pdf` | 306.373 |

**Hipóteses (a investigar na próxima sessão):**

1. **Versões temporais distintas** (a SEMAD republica a lista de tipologias quando uma nova atividade vira licenciável) — neste caso, manter só a mais recente.
2. **Subset / superset com filtros** (tipologias filtradas por tipo de licença diferente) — neste caso, todas têm valor distinto.
3. **Downloads parciais corrompidos** — alguns truncados; manter só o maior íntegro.

**Ação proposta na sessão de ingestão:**
- (a) Calcular SHA-256 de cada um (mesmo que tamanho varie, o conteúdo pode coincidir em alguns)
- (b) LLM lê primeira página de cada um e compara: mesmo título? Mesma data de revisão? Mesmas N tipologias listadas?
- (c) Se forem versões temporais: pegar a mais recente como canônica, descartar as outras
- (d) Se forem filtragens distintas: ingerir todas com metadado `filtro_aplicado` em `extra_metadata`

---

## 7. Arquivos fora da taxonomia A/B/C/D

Em `Manuais (SEMAD)/`, 3 planilhas Excel:

- `MODELO PLANILHA PARA CAI_DEZ.xlsx` (planilha modelo para Cadastro Ambiental de Imóveis)
- `PLANILHA DE INVENTARIO.xlsx` (planilha modelo de inventário florestal)
- `Simulador Compensação - Versão 08.05.26.xlsx` (calculadora de compensação ambiental)

**Decisão proposta:** **NÃO ingerir no `knowledge_catalog`** — são templates editáveis pelo consultor, não conhecimento textual para RAG. Documentar a existência em `docs/relatorios/` mas armazenar como **assets estáticos** (servir do R2 para download direto pelo consultor), não como chunks indexáveis.

---

## 8. Decisões arquiteturais (aprovadas em 2026-05-20)

### Q1 — Tabela destino: **`knowledge_catalog`** (pgvector)
- `app/models/knowledge_catalog.py:62` (`KnowledgeChunk`)
- Já contém ~22.573 chunks de legislação (Sprint W)
- Tem `vector(768)` compatível com embedding atual (OpenAI text-embedding-3-small)
- Tem `extra_metadata` JSONB livre para campos por tipo

### Q2 — `doc_type` A/B/C/D: **enum estendido** em `source_type`
Estender o enum `SourceType` em `app/models/knowledge_catalog.py:35-43` com 4 valores novos:

```python
class SourceType(str, enum.Enum):
    legislation = "legislation"      # existente
    oficio = "oficio"                 # existente
    manual = "manual"                 # existente — REUSAR p/ Tipo D? ou novo manual_ipe?
    jurisprudence = "jurisprudence"   # existente
    skill = "skill"                   # existente
    other = "other"                   # existente
    # NOVOS (Sprint corpus SEMAD):
    matriz_ipe = "matriz_ipe"           # Tipo A
    norma_procedural = "norma_procedural"  # Tipo B
    gabarito_laudo = "gabarito_laudo"      # Tipo C
    manual_ipe = "manual_ipe"              # Tipo D (NÃO reusar 'manual' — manual genérico vs IPÊ)
```

Justificativa para `manual_ipe` separado de `manual`: o enum `manual` existente é genérico (poderia incluir manuais MMA, ICMBio, INCRA, etc.). O `manual_ipe` é específico de uso do portal SEMAD-GO. Filtragem SQL fica mais limpa.

### Q3 — Escopo desta sessão
**Aprovado: só inventário + smoke + decisão.** Ingestão real adiada para sessão de execução dedicada.

---

## 9. Próximos passos (próxima sessão)

Em ordem:

1. **Migration Alembic** para estender enum `SourceType` com 4 valores novos. Como Postgres trata enum como tipo nominal, será necessário usar `ALTER TYPE ... ADD VALUE`.
2. **Smoke test do classificador LLM** em 4 PDFs de referência (1 por tipo):
   - A: `89 - REGISTRO CORTE DE ÁRVORES ISOLADAS POR HECTARE EM ÁREA RURAL CONSOLIDADA.pdf`
   - B: `Compensação Florestal e Compensação Por Danos Ambientais.pdf`
   - C: `LAUDO DE ESTANQUEIDADE DO SISTEMA DE ARMAZENAMENTO AÉREO DE COMBUSTÍVEIS - SAAC.pdf`
   - D: `Manual AUMPF.pdf`

   Validar prompt + extração de metadados estruturados antes de rodar em 283 PDFs.

3. **Resolução dos 14 `tipologias_disponiveis*.pdf`** — LLM lê primeira página de cada um, compara, decide canônico vs versões distintas.
4. **Script de ingestão batch** em `scripts/ingest_corpus_semad.py` (não estende `ingest_legislation.py` — esse popula outra tabela, semântica diferente).
5. **Chunking + embedding** dos 283 PDFs com a strategy do Sprint W (OpenAI text-embedding-3-small, chunks ~2k chars, overlap ~100).
6. **Relatório final** com counts reais pós-LLM + log de erros.
7. **PR** `feat/corpus-semad-ingestao` → revisão.

**Custo estimado de API LLM (próxima sessão):**
- Classificação Gemini Flash em 283 PDFs × 2 páginas extraídas × ~$0.0005/call ≈ **~$0.15**
- Embedding OpenAI text-embedding-3-small em ~283 × 5 chunks médios × ~500 tokens × $0.02/M tokens ≈ **~$0.014**
- **Total: < $1.** Conservador, considerando re-runs e PDFs maiores.

**Tempo estimado:** 30-45 min de execução automatizada (pode rodar em background).

---

## 10. Anexos

- **TSV completo da pré-classificação:** `/tmp/semad_preclass.tsv` (local, não commitado)
- **Script da heurística:** `scripts/classify_semad_heuristic.py` (commitado neste worktree)
- **Próximo script a criar:** `scripts/ingest_corpus_semad.py` (próxima sessão)
- **Migration a criar:** `alembic/versions/<hash>_sprint_corpus_semad_extend_source_type.py` (próxima sessão)
