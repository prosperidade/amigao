# Teste Isis — Rodada 1 (caso real #10 "Fazenda São Jorge")

> Branch: `fix/teste-isis-rodada1` (base `main`, já com o PR #57 mergeado).
> Caso de referência: #10, tenant 1, property 7 (produção). Equivalente local:
> property 11 (tenant 2) tem issues; o pipeline "Fazenda Boa Vista" rodou local
> e forneceu os shapes reais de AIJob para reproduzir B/C/F.

## Contexto crítico

A sócia (Isis) testou o caso #10 em **produção, sem o PR #57** (que foi mergeado
no início desta sessão). Isso explica por que metade dos defeitos some com o
merge: o #57 entregou `formatLegislacao` (Item C) e o fallback persistido do
diagnóstico (Item F). Os itens **A, B, D** são genuínos e foram corrigidos
nesta rodada; **C e F** foram confirmados como resolvidos pelo #57 (provados
contra os shapes reais); **E** é sintoma downstream de A.

---

## Item A — 500 em `GET /properties/{id}/issues?status=open`

- **Reproduzido:** endpoint retorna **200** para dados limpos (property 11, todos
  os filtros de status). O 500 **não** vinha do enum de status (Literal → daria
  422). Inserindo uma issue com `documentos_cruzados` = **lista de objetos**
  (`[{"doc":"matricula"}]`) o endpoint deu **500** — traceback capturado:
  `fastapi.exceptions.ResponseValidationError: Input should be a valid string`
  em `('response', 0, 'documentos_cruzados', 0)`.
- **Causa medida:** `documentos_cruzados` é JSONB alimentado pelo auditor (path
  guiado por LLM pode gravar lista de **objetos**), mas `RegulatoryIssueOut` o
  declara `list[str]`. Uma única linha malformada derruba a **lista inteira**
  com 500 (o front então re-tenta em loop).
- **Fix:**
  - Read-side: `field_validator` em `RegulatoryIssueOut.documentos_cruzados`
    (`app/schemas/regulatory.py`) coage cada item para string — conserta linhas
    **legadas** já gravadas, **sem migration**.
  - Write-side: `@validates` em `RegulatoryIssue` (`app/models/regulatory.py`)
    normaliza na origem, cobrindo todos os writers.
- **Validação:** com a linha ruim reinserida o endpoint passou a **200** e
  `documentos_cruzados` saiu `["matricula","CAR"]`. Testes:
  `test_documentos_cruzados_objeto_nao_quebra_serializacao` (API) +
  `test_regulatory_issue_out_coerces_object_documentos_cruzados` (read-side).
- **Status:** ✅ corrigido + testado.

## Item B — Extrator na UI: valores `[object Object]`

- **Reproduzido:** shape real do `extract_document` (caso "Boa Esperança"):
  `extracted_fields` traz `confidence` como **objeto** (mapa por-campo); o caso
  #10 (14 campos) usa a variante **aninhada** `{campo: {value, confidence}}`. O
  `ExtratorResult` renderizava `String(value)` → `[object Object]` em todo valor
  que fosse objeto.
- **Causa medida:** `AgentResultRenderer.tsx` linha do `KeyValue` fazia
  `value != null ? String(value) : null` — sem desempacotar objetos.
- **Fix:** helper `extratorFieldValue` desempacota `{value, ...}` e cai em
  `humanizeValue` (que nunca produz `[object Object]`). `confidence` já é
  filtrado por `isMetaField`.
- **Validação:** 2 testes em `fieldLabels.test.tsx` renderizando os renderers
  reais com o shape aninhado e o shape `confidence`-objeto — sem `[object
  Object]`. tsc + eslint + build verdes.
- **Status:** ✅ corrigido + testado.

## Item C — Legislação Aplicável `[object Object]` ×9

- **Reproduzido:** shape real do `consulta_regulatoria` (agent `legislacao`):
  `legislacao_aplicavel = [{identificador, titulo, relevancia}]`.
- **Causa medida:** o `[object Object]` era o estado **pré-#57**. O
  `formatLegislacao` entregue no #57 **cobre** esse shape — produz
  "Lei Federal nº 12.651/2012 — Novo Código Florestal".
- **Fix:** nenhum código novo necessário (resolvido pelo merge do #57); travado
  com teste de regressão.
- **Validação:** teste renderizando `agentName="legislacao"` com o array real —
  cita as leis, sem `[object Object]`.
- **Status:** ✅ resolvido pelo #57 + teste de regressão.

## Item D — Timeout "None seconds" na legislação

- **Reproduzido (simulado):** a legislação passa `model=` explícito ao
  `ai_gateway.complete()` → `models = [(model, "")]` (um único modelo, **sem
  cadeia de fallback**). O loop dava `continue` para o próximo modelo, mas só há
  um → um Timeout transitório vira "Todos os providers falharam" na hora, **sem
  retry**. O "None seconds" indica timeout não-propagado ao provider.
- **Fix (`app/core/ai_gateway.py` + `config.py`):**
  - Retry por modelo só para erros **transitórios** (Timeout, APIConnection,
    ServiceUnavailable, InternalServer, RateLimit), `AI_MAX_RETRIES=2` com
    backoff exponencial curto (`AI_RETRY_BACKOFF_SECONDS=1.0`). Erro permanente
    (auth/schema) continua propagando na hora.
  - Timeout defensivo: `settings.AI_TIMEOUT_SECONDS or 30.0` — nunca `None`.
- **Validação:** `test_transient_error_retries_then_succeeds` (Timeout 2× →
  sucesso na 3ª, `timeout=30.0` confirmado no kwarg),
  `test_transient_error_exhausts_retries_then_raises`,
  `test_timeout_falsy_setting_defaults_to_30`. Settings têm default → não exige
  mudança no docker-compose.
- **Status:** ✅ corrigido + testado.

## Item E — Alertas sem avisos coloridos (severidade)

- **Reproduzido:** o componente é `AlertasTab → AlertaCard`, que consome o
  **mesmo** endpoint do Item A (`useIssues → /properties/{id}/issues`). Em
  `error` (o 500), o `AlertasTab` renderiza só uma caixa vermelha genérica
  ("Falha ao carregar alertas") — **nenhum `AlertaCard`, nenhuma cor**. Os cards
  (com `SEVERITY_CLS`, classes estáticas que o Tailwind escaneia em `.ts` →
  não purgadas) só renderizam no load com sucesso.
- **Causa medida:** sintoma **downstream do Item A** — a lista 500ava, então os
  cards coloridos nunca apareciam. A lógica de cor por severidade já está
  correta.
- **Fix:** resolvido ao corrigir o Item A (endpoint 200 → cards renderizam com
  cor por severidade).
- **Nota:** se TODAS as issues de um imóvel forem `informativo`, elas renderizam
  em cinza-ardósia por design (severidade baixa) — não é bug de cor. Posso semear
  um caso com severidades variadas para a Isis confirmar a paleta.
- **Status:** ✅ resolvido via Item A.

## Item F — Diagnóstico com insumo baixo (`tokens_in=636`)

- **Reproduzido:** histórico de tokens do diagnóstico (entity 30): id 135 =
  **637** (pré-#57) → id 142 = **3491** (pós-#57). O `636` era o estado
  pré-fallback.
- **Causa medida:** o fallback `_load_persisted_extraction` (#57) **não filtra
  por `doc_type`** e agrega `extracted_fields` inteiro — cobre `doc_type
  "outros"`. O insumo baixo era ausência do fallback (pré-#57), não falha de
  shape.
- **Fix:** resolvido pelo merge do #57; travado com testes provando que campos
  de `doc_type "outros"` (e shape `{value, confidence}`) não são descartados.
- **Validação:** `test_fields_from_job_result_extrai_de_doc_type_outros` +
  `test_has_extracted_fields_falso_dispara_fallback`.
- **Status:** ✅ resolvido pelo #57 + testes de regressão.

---

## Suites

- Backend: **760 passed** (`pytest tests/`).
- Frontend: **51 passed** (vitest, 9 arquivos) + tsc + eslint + build verdes.
- Lint backend: ruff limpo; mypy (arquivos alterados) limpo.

## Aberto / próximo

- A e E foram reproduzidos e corrigidos com **dado local equivalente**; vale a
  Isis re-rodar o caso #10 real para confirmar (endpoint 200 + alertas coloridos).
- Oferta: semear um imóvel com issues de severidades variadas para exercitar a
  paleta de cores dos alertas de ponta a ponta.
