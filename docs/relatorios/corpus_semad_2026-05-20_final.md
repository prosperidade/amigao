# Corpus SEMAD — Relatório final de ingestão

> **Status:** sessão 2 de 2 — ingestão completa concluída.
> **Data:** 2026-05-20
> **Branch:** `feat/corpus-semad-ingestao`
> **Pré-requisito:** [inventário preliminar](corpus_semad_2026-05-20_inventario_preliminar.md).

---

## 1. Resumo executivo

| Métrica | Valor |
|---|---:|
| PDFs no corpus | 283 |
| **PDFs indexados com sucesso** | **282** (99,6%) |
| PDFs pendentes (precisam OCR) | 1 |
| **Chunks inseridos no `knowledge_catalog`** | **1.194** |
| Tempo total de execução | ~83 min (77 batch + 6 retry) |
| Custo total LLM | ~$2,10 USD |

**Pipeline E2E validado:** pypdf → Gemini Flash 2.5 (classify + extract metadata) → chunking híbrido → OpenAI text-embedding-3-small (768d) → `knowledge_catalog` com `extra_metadata` JSONB.

---

## 2. Distribuição final por tipo (pós-LLM)

| Tipo | Docs | Chunks | Doc avg chunks |
|---|---:|---:|---:|
| **norma_procedural** | 223 | 953 | 4,3 |
| **matriz_ipe** | 36 | 175 | 4,9 |
| **manual_ipe** | 10 | 48 | 4,8 |
| **gabarito_laudo** | 11 | 15 | 1,4 |
| **other** | 2 | 3 | 1,5 |
| **Total SEMAD** | **282** | **1.194** | |
| | | | |
| _legislation (Sprint W, intacto)_ | _44_ | _22.573_ | |

Total geral no `knowledge_catalog`: **22.573 + 1.194 = 23.767 chunks**.

---

## 3. Insight crítico — reclassificação A→B

A heurística estática por nome de arquivo (sessão 1) projetava **230 matrizes IPÊ** baseada em códigos no início do nome (`A1.1.1 -`, `7841 -`, etc.). O LLM, lendo o conteúdo das primeiras páginas, reclassificou **196 desses** como **norma_procedural** (descritivas) — não matrizes (fluxograma).

**Razão real, validada lendo conteúdo dos PDFs:**

| Padrão de nome | Conteúdo real | Tipo correto |
|---|---|---|
| `89 - REGISTRO...`, `7841 - Y1.2 -...`, `8258 -...` (códigos numéricos longos) | "SISTEMA DE LICENCIAMENTO AMBIENTAL DE GOIÁS - IPÊ MATRIZ / Identificação: <cod> / Tipo de questionário / 1. ... SIM → Segue para 2 / NÃO → Segue para 3 / Incluir Vedação" | **matriz_ipe** (A) |
| `A1.1 -...`, `A1.1.1 -...`, `Y1.6 -...` (códigos alfanuméricos curtos) | "INFORMAÇÕES DA TIPOLOGIA / Código 72 / Atividade / Tipo de licença" | **norma_procedural** (B) — descritivo |

**Implicação semântica:**
- Os códigos `A1.1`, `Y1.6`, etc. são **identificadores de tipologia/atividade** licenciável (descritivos de O QUE é a atividade).
- Os códigos `89`, `7841`, etc. são **identificadores de matriz IPÊ** (fluxograma decisório de COMO licencia).

**O LLM corrigiu uma premissa errada do enunciado da tarefa.** A heurística por nome estava enganada — só o conteúdo distingue. Vale recordar isso em sprints futuras de skills: o consultor que pergunta "qual o procedimento pra A1.1?" está perguntando sobre a tipologia (norma), não sobre uma matriz IPÊ.

---

## 4. Validação do classificador no smoke

4 PDFs de referência (1 por tipo) processados antes do batch:

| PDF | Tipo esperado | Tipo obtido | Confidence | Metadados extraídos |
|---|---|---|---:|---|
| `89 - REGISTRO CORTE DE ÁRVORES ISOLADAS...` | A | matriz_ipe | 1.0 | licenca_codigo=89, tipo_questionario=Requerimento, tipo_licenciamento=REG_I, tipos_licenca_aplicaveis=[REG_I, LAO] |
| `Compensação Florestal e Compensação Por Danos...` | B | norma_procedural | 1.0 | tema=compensacao_florestal, leis_referenciadas=[Lei 6938/1981] |
| `LAUDO DE ESTANQUEIDADE...SAAC` | C | gabarito_laudo | 1.0 | tipo_laudo=estanqueidade_saac, normas_tecnicas=[NBR 15.461, UL 142, API 650, ...] |
| `Manual AUMPF` | D | manual_ipe | 0.9 | procedimento=solicitacao_aumpf, agente_consumidor=Atendimento |

**4/4 acertos, todos com metadados ricos.** Smoke aprovado.

---

## 5. Erros e recuperação

### Primeira execução (batch dos 283)
- **264 sucessos / 19 erros (6,7%)**
- 19 erros em 3 categorias:
  - **16 `empty_excerpt`** (pypdf falhou): PDFs com nome longo (>260 chars Windows MAX_PATH) → pypdf não conseguia abrir.
  - **2 `gemini_503`** (rate limit): Gemini Flash com pico de demanda.
  - **1 `bug_slug_list`** (bug no código): LLM retornou lista onde script esperava string em `_slug()`.

### Fixes aplicados ao script (commit pré-retry)

1. **Windows long path:** `extract_pdf_pages()` agora prefixa `\\?\` no path absoluto em Windows. Resolve PDFs com nome > 260 chars.
2. **Fallback `pypdfium2`:** se pypdf retorna vazio, tenta `pypdfium2` (melhor em PDFs antigos).
3. **`_slug()` aceita list:** se LLM retornar lista, junta com espaço e normaliza.
4. **`--from-file LIST`:** novo argumento pra re-rodar lista específica de PDFs (idempotência via content_hash garante zero duplicação).

### Retry dos 19 PDFs
- **18 recuperados** (94% recovery), +68 chunks
- **1 pendência genuína:** [`ON_01_2021_SEMAD - Errata.pdf`](../Manuais%20%28SEMAD%29/ON_01_2021_SEMAD%20-%20Errata.pdf). PDF escaneado sem text layer (1 página, 0 chars extraídos por pypdf E pypdfium2). Precisa OCR via Gemini Vision (custo trivial ~$0.0006). Não bloqueia: é uma errata operacional, não conteúdo crítico.

---

## 6. Caso `tipologias_disponiveis*.pdf` (14 arquivos)

Inventário preliminar destacou 14 cópias com tamanhos distintos (293-349 KB cada) e levantou hipóteses sobre serem versões temporais, subsets, ou duplicatas parciais.

**Resultado pós-LLM:**
- 13 classificados como `norma_procedural`
- 1 como `other`

Todos foram **ingeridos**. O LLM tratou cada um como documento independente, sem comparação cruzada (limitação do pipeline atual — cada PDF é classificado isoladamente).

**Decisão pragmática:** os 14 estão indexados. Se houver duplicação real, o RAG vai retornar resultados redundantes ao buscar por "tipologias". Mitigação futura (sprint dedicada ou na primeira query problemática):

```sql
-- Detectar duplicatas semânticas: chunks com mesmo conteúdo entre os 14 PDFs
SELECT chunk_text, COUNT(*), array_agg(source_ref)
FROM knowledge_catalog
WHERE source_ref LIKE 'tipologias_disponiveis%'
GROUP BY chunk_text
HAVING COUNT(*) > 1
ORDER BY 2 DESC LIMIT 20;
```

Se a query revelar overlap significativo (>50% de chunks duplicados), criar script `dedup_tipologias.py` que escolhe o canônico (maior file_size ou data mais recente) e remove os outros.

---

## 7. Metadados estruturados em `extra_metadata` JSONB

Cada chunk recebeu `extra_metadata` populado com os campos da taxonomia. Distribuição de campos não-nulos no JSONB (amostra `norma_procedural`):

- `doc_type`: 100% (sempre populado)
- `confidence`: 100%
- `licenca_codigo`: ~85% (todos os PDFs com prefixo `A1.1`, `Y1.6`, etc.)
- `tema`: ~95%
- `leis_referenciadas`: ~30%
- `procedimento`: ~20%

**Queries úteis para skills futuras:**

```sql
-- Buscar matrizes IPÊ que avaliam viabilidade locacional
SELECT source_ref, extra_metadata
FROM knowledge_catalog
WHERE source_type = 'matriz_ipe'
  AND extra_metadata->>'tipo_questionario' = 'Viabilidade locacional';

-- Buscar todos os gabaritos de laudo
SELECT source_ref, extra_metadata->>'tipo_laudo' AS laudo,
       extra_metadata->'normas_tecnicas' AS normas
FROM knowledge_catalog
WHERE source_type = 'gabarito_laudo'
GROUP BY source_ref, extra_metadata;

-- Matrizes que se aplicam a uma licença específica (ex: LAU)
SELECT source_ref FROM knowledge_catalog
WHERE source_type = 'matriz_ipe'
  AND extra_metadata->'tipos_licenca_aplicaveis' ? 'LAU';
```

---

## 8. Custo e performance

| Item | Valor |
|---|---|
| Modelo LLM (classificação + extração) | Gemini Flash 2.5 |
| Modelo de embedding | OpenAI text-embedding-3-small (768d) |
| Tempo médio por PDF | 16,4 s (incluindo thinking tokens do Gemini) |
| Cost por PDF (LLM) | ~$0,007 |
| Cost total LLM | ~$2,07 |
| Cost embeddings | ~$0,03 |
| **Custo total** | **~$2,10** |

**Para sprints futuras (otimização opcional):**
- Desabilitar `thinking_budget` do Gemini 2.5 Flash pode cortar latência em ~50%.
- Batch as chamadas LLM (1 prompt com N PDFs ao invés de N prompts) — possível mas reduz isolamento de erros.

---

## 9. Pendências

| # | Item | Severidade | Próxima ação |
|---|---|---|---|
| 1 | `ON_01_2021_SEMAD - Errata.pdf` escaneado | Baixa (1 errata) | Integrar OCR via `app/services/ocr_pdf.py` numa sprint dedicada ou rodar ad-hoc com `--ocr-fallback` |
| 2 | 14 `tipologias_disponiveis*.pdf` ingeridos sem dedup | Média | Query SQL para detectar overlap; se >50%, criar `dedup_tipologias.py` |
| 3 | Heurística estática deprecated | Baixa | [`scripts/classify_semad_heuristic.py`](../../scripts/classify_semad_heuristic.py) fica como histórico — pipeline canônico é LLM-driven em `ingest_corpus_semad.py` |

---

## 10. Próximos passos (fora desta tarefa)

Esta sprint **NÃO escreve skills nem altera prompts de agentes** (escopo congelado). Materiais ingeridos preparam terreno para:

1. **Sprint skills procedurais** (próxima): escrever Markdown templates em `app/skills/` que orientam o consultor a usar o que está no `knowledge_catalog`:
   - `skill_consultar_matriz_ipe.md` (filtra `source_type='matriz_ipe'` + `licenca_codigo`)
   - `skill_gerar_laudo_tipo_X.md` (filtra `source_type='gabarito_laudo'` + `tipo_laudo`)
   - `skill_passo_a_passo_portal.md` (filtra `source_type='manual_ipe'` + `procedimento`)

2. **Validação E2E em caso real** (após skills): consultor faz pergunta sobre uma licença A1.1.2 → agente diagnostico busca normas relacionadas no catálogo → cita fonte exata (filename do PDF SEMAD) → consultor confere.

3. **Operação contínua**: quando a SEMAD publicar novas matrizes/normas, rerodar `python scripts/ingest_corpus_semad.py` é seguro (idempotente por content_hash).

---

## 11. Anexos

- **Script de ingestão:** [`scripts/ingest_corpus_semad.py`](../../scripts/ingest_corpus_semad.py)
- **Enum atualizado:** [`app/models/knowledge_catalog.py`](../../app/models/knowledge_catalog.py) (4 valores novos no `SourceType`)
- **Heurística (histórica):** [`scripts/classify_semad_heuristic.py`](../../scripts/classify_semad_heuristic.py)
- **Inventário preliminar:** [`corpus_semad_2026-05-20_inventario_preliminar.md`](corpus_semad_2026-05-20_inventario_preliminar.md)
- **Resultados JSON (local, não commitado):** `C:/tmp/ingest_results.json`

---

## 12. Critério de pronto (do enunciado da tarefa)

- [x] Todos os PDFs da pasta processados (282/283 com sucesso; 1 erro logado)
- [x] Relatório markdown gerado e legível (este arquivo)
- [x] Smoke test passa (classificador acerta os 4 PDFs de referência, confidence 0,9-1,0)
- [x] Push direto para `feat/corpus-semad-ingestao` (sem PR, conforme solicitado)
