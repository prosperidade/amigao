# Ficha 01 / FASE 2 — extração estruturada por tipo de documento → staging

**Branch:** `feat/ficha01-fase2-extracao-estruturada` (base `main`, requer Fase 1 #60)
**Data:** 2026-06-05
**Espec:** Ficha 01 §5.1-5.7 (+ Ficha 02 §8 para o RAT)
**Relacionada a:** ADR-015 (entidade Matrícula + staging)

Esta FASE 2 faz o **Extrator preencher o staging** (`ExtractedFieldStaging`) com
extração ESTRUTURADA por tipo de documento. A base real (Client/Property/
Matricula) NÃO é gravada — só staging (consolidação = fase 4). O resultado atual
do extrator no AIJob (`extracted_fields`) **continua igual** — staging é gravação
ADICIONAL (1 chamada LLM dedicada por documento, reusando o texto do OCR).

## Decisões

- **doc_types canônicos:** `rg_cpf, endereco, car, ccir, matricula, itr, sigef, rat`
  (+ `outro`). Em `app/services/ficha01_extraction.py:CANONICAL_DOC_TYPES`.
- **Nomenclatura `rat` (Ficha 02 §8):** RELATÓRIO DE ANÁLISE TÉCNICA do CAR. A
  "Retificação" é um ATO, não um documento — não há doc_type para ela.
- **Compatibilidade:** `extract_document_fields` (→ `AIJob.extracted_fields`)
  intocado. UI e diagnóstico continuam lendo de lá.

## Implementação

- **Serviço `app/services/ficha01_extraction.py`:**
  - `classify_doc_type(text, current)` — classificação por conteúdo (rule-based,
    sem LLM). Respeita tipo específico já atribuído; só `outro`/None dispara a
    heurística. Ordem importa (rat antes de car, que compartilham termos).
  - `_STAGING_PROMPTS` + `_FIELD_SPECS` — esquema de extração e mapa Ficha 01 por
    tipo. `build_staging_fields()` mapeia o JSON → linhas de staging (escalares +
    listas especiais: `car.matriculas[]` → 1 linha `matricula_listada` por item
    com `matricula_hint`; `rat.pendencias[]` → `pendencias_rat`).
  - `extract_and_stage()` — 1 chamada LLM por doc + persiste `ExtractedFieldStaging`
    (field_name, field_value `{value[, unidade]}`, confidence, source_doc_type,
    target_entity/field, matricula_hint, created_by_agent="extrator", ai_job_id,
    status=pendente). Best-effort: falha → 0 linhas, sem derrubar o extrator.
- **`ExtratorAgent._stage_ficha01()`** — chamado nos 2 caminhos (doc único e
  processo inteiro), após o `extracted_fields` (não o altera). `base.py` passou a
  expor `self._current_job` para o `ai_job_id` ser rastreável durante `execute()`.
- **matricula_hint:** matrícula (próprio nº) · ccir/itr/sigef (nº quando presente)
  · recibo CAR (por item da lista de matrículas).

## Validação real (rodando — equivalentes locais do corpus São Jorge)

3 documentos inseridos com `document_type="outro"` (prova o classificador por
conteúdo), extrator disparado, staging conferido via `GET /processes/30/staging-fields`:

**Recibo CAR → classificado `car`, 9 linhas:** `numero_car` (GO-5221080-…),
`area_declarada_ha` = `{value:1010.5583, unidade:"ha"}`, município/UF, APP/RL,
`status_car`, + **2 `matricula_listada` com `matricula_hint` 4.698 e 6.776**.

**RAT → classificado `rat`, 7 linhas:** `protocolo` (GO-RAT-2025-000123),
`situacao` = Pendente, `numero_car`, `data_emissao`, `area_vetorizada_ha`,
`modulos_fiscais`, + **`pendencias_rat`** (JSON estruturado: sobreposição APA,
supressões pós-2008, hidrografias/APP, acesso) — insumo da Fase 3.

**Certidão de matrícula → classificado `matricula`, 6 linhas:** `numero_matricula`,
`registro_livro_folha`, `cartorio`, `area_registrada_ha` (660,6561), `averbacao_rl`,
`onus` — **todas com `matricula_hint=4.698`**.

Todas as 22 linhas: `status=pendente`, `created_by_agent=extrator`, `ai_job_id`
preenchido. **`extracted_fields` não regrediu** (AIJob 148 = dict plano + `confidence`,
shape igual ao atual). Dados de teste removidos após a validação.

## Testes

- `tests/services/test_ficha01_extraction.py` — classificador (car/rat/matricula,
  respeita tipo específico, fallback outro), mapeamento por tipo (CAR 2 matrículas
  + hints, RAT `pendencias_rat`, matrícula hint próprio, pula vazios), persistência
  (LLM mockado).
- `tests/agents/test_extrator_ficha01_staging.py` — integração pelo ExtratorAgent:
  `extracted_fields` intacto + staging populado (hints 4.698/6.776, `ai_job_id`).
- `tests/agents/test_extrator_cache.py` — fixture autouse stuba o staging (não
  dispara LLM real; mesma disciplina do mock de `extract_document_fields`).

## Não nesta fase

- Reconciliação multi-fonte do auditor (Fase 3).
- Consolidação/tela de Alertas (Fase 4).
- Gravar na base real (Client/Property/Matricula).

## Custo / dívida conhecida

Staging adiciona 1 chamada LLM por documento (além do `extract_document_fields`
legado). Tradeoff aceito para não tocar o shape de `extracted_fields`; unificar as
duas extrações numa só chamada fica como otimização futura.

## Arquivos

- `app/services/ficha01_extraction.py` (novo)
- `app/agents/extrator.py` (`_stage_ficha01` + 2 call sites)
- `app/agents/base.py` (`self._current_job`)
- `tests/services/test_ficha01_extraction.py`, `tests/agents/test_extrator_ficha01_staging.py` (novos)
- `tests/agents/test_extrator_cache.py` (fixture stub)
- Governança: `MODELO_DE_DADOS.md` (doc_types + RAT), ESTADO_ATUAL, MEMORIA_CHAT.
