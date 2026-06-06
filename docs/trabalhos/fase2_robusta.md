# Fase 2 robusta — extração real completa no staging

> PR `feat/fase2-robusta-docs-reais` (base main). Medido contra os documentos
> REAIS do caso #11 (São Jorge), puxados do Supabase de produção. 2026-06-06.

## Medição (ANTES) — staging real do processo 11

| doc | OCR | classificou | deveria | causa |
|---|---|---|---|---|
| 141 Certidão **4698** | done (117k) | `matricula` ✅ | matricula | `document_type` já setado |
| 165 Certidão **6776** | done (33k) | **`sigef`** ❌ | matricula | regra `sigef` (keyword "memorial descritivo") vinha **antes** de `matricula` |
| 164 **RAT** | done (13k) | `rat` ✅ | rat | header "go-rat"/"análise técnica" |
| CCIR / ITR / recibo CAR | **failed/pending** | — | — | **OCR falhou** (upstream) |

**Causa raiz da matriz "denominação consistente":** a certidão 6776 (que tem
"Lote 01-C"/"Shangri-lá") caía em `sigef` → a denominação vinha de 1 fonte só.
Confirmado nos textos reais: ambas as certidões têm "Inteiro Teor da Matrícula",
"Registro de Imóveis", "Oficial Registrador"; nenhuma tem "sigef".

## O que mudou

**1. Classificação (`ficha01_extraction.py:classify_doc_type`)** — ordem
determinística por IDENTIDADE do documento ("o tipo é do DOCUMENTO, não de uma
menção interna"): `rat → matricula → car → ccir → itr → sigef → rg_cpf → endereco`.
`matricula` usa marcadores ÚNICOS ("inteiro teor", "oficial registrador",
"certidão de matrícula") — **não** "registro de imóveis"/"cartório de registro"
(um recibo CAR lista matrículas com esses termos no corpo) nem "matrícula nº"
(um memorial SIGEF cita o número). Fixtures = textos reais (doc 141/165/164).

**2. Completude (item 3)** — o prompt do CAR **já** pedia `area_declarada_ha` (o
"car sem área" em prod foi porque o único doc `car` com texto era um arquivo de
códigos, não o recibo — o recibo real falhou OCR). Prompt de matrícula enriquecido
(sem quebrar shape do `AIJob.extracted_fields`): ônus com tipo/credor/valor,
denominação atual + anterior, código de certificação sem vértice grudado. Novos
`field_name` de staging: `denominacao_anterior`, `codigo_certificacao` (matricula).

**3. Precisão de campo (4b — `field_validators.py`)** — validação de FORMATO por
campo (SIGEF/CAR/SNCR/NIRF/CPF/datas/áreas). Fora do formato → `confidence="low"`
+ flag `format_ok=False`, **valor bruto preservado** para revisão. Motivador real:
o código SIGEF saiu com vértice grudado ("029231.2.0006776-55 inicia-se no
vértice…") → reprovado e marcado, sem perder o bruto.

**4. Dedup (4c — `build_staging_fields` + `extract_and_stage`)** — informação
repetida (mesma fonte + campo + hint + valor) vira UMA linha; resolve a
triplicação de re-extrações. Valores DIFERENTES da mesma fonte são MANTIDOS
(divergência interna → insumo da matriz).

**5. Chain "0 campos" (item 4 — `extrator.py`)** — quando a chain roda sem doc
novo com OCR, em vez do enganoso "0 campos, tipo outro", **reutiliza** a extração
já em staging (`_reuse_staging_fields`): resultado explícito ("extração reutilizada,
N linhas, fontes X") carregando os campos para os próximos agentes da chain.

## DEPOIS (matriz)

Com a 6776 classificada como `matricula`, as duas matrículas chegam ao staging e a
matriz mostra **denominação DIVERGENTE**: 4698 = "Fazenda São Jorge - Gleba 01 B"
× 6776 = "Fazenda Shangri-lá (Parte 2)", cada uma na sua fonte; área multi-fonte
(soma 1010,5583 × RAT 1010,7113). Provado em `tests/services/test_fase2_depois_matriz.py`.

## Validação

- Classificação: `test_classify_doc_type_real.py` (fixtures = textos reais) — 6776→matricula, 4698→matricula, RAT→rat, sigef puro→sigef.
- 4b/4c: `test_fase2_validators_dedup.py` (código SIGEF com vértice grudado → low + bruto; re-extração não duplica; valores distintos mantidos).
- Depois: `test_fase2_depois_matriz.py` (denominação divergente, área multi-fonte).
- Sem regressão: `test_ficha01_extraction.py`, `test_extrator_ficha01_staging.py` verdes. ruff + mypy limpos (nenhum erro novo).

## Fora de escopo — follow-on de OCR

A causa de **CCIR/ITR/recibo CAR ausentes** no staging é **OCR falhando** (`ocr_status=failed`)
em produção — upstream da Fase 2. Sem texto, não há classificação nem extração.
Registrar como follow-on (investigar a falha de OCR desses PDFs). A denominação
divergente — coração da validação — não depende disso (vem das 2 certidões).
Matriz **não alterada** (PR #65 é a calibração; aqui só os campos novos a alimentam).
