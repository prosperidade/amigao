# Estado Atual — Regente Ambiental

**Data do instantâneo:** 2026-05-30 (pós-PR #23 fechamento do PR 2.2 — testes integrados 42/42 + cobertura real; pós-PR #24 corpus SEMAD operacional em main; + faxina de repositório: de ~23 branches remotas / 6 worktrees para só `main`)
**Próxima atualização:** eixo 3 — unificação `Process.status` × `Process.macroetapa` (PR3-agressivo; dívida nova #26) ou follow-on do badge crítico-pendente
**Responsável de atualização:** quem fechar a próxima sprint
**Frente em revisão:** `fix/diagnostico-propaga-estado` (PR a abrir — assinatura propaga macroetapa, gate cobra `validated_at`, badge espelha). `fix/extrator-por-processo` (PR #15) já em main.
**Pulso 2026-06-18 (Histórico de eventos — humanizar + fonte — `fix/historico-eventos-humanizado`):** a tela "Histórico de eventos do caso" (rodapé de `/processes/{id}`) mostrava **JSON cru** ao consultor (`{"field_id":401,"acao":"aceitar","target_field":"geo_certificacao_codigo","matricula_hint":"4655","fonte":null,...}`), quebrando a identidade do produto. **Item 1 (humanizar):** novo módulo `frontend/.../historicoEventos.ts` (`describeEvento`) converte cada AuditLog em frase PT-BR ("Código de certificação SIGEF da matrícula 4655 aceito."), cobrindo todos os tipos do caso real (staging_decidir aceitar/rejeitar/escolher_fonte/editar, lote, consolidar, status, macroetapa, notificação, created, classificação) + fallback genérico que nunca imprime JSON. Rótulos via módulo central `fieldLabels.ts` (`labelFor`), **estendido** com os target_field de destino do staging; concordância de gênero do particípio; ícone/cor por tipo reusando o padrão de severidade. `TimelineTab.tsx` reescrito. **Item 2 (fonte — medido):** o `fonte:null` vinha de `decide_field` gravando o param `body.fonte` (a fonte opcional do escolher_fonte, nunca passada em aceitar/rejeitar/lote) — é a fonte da *decisão* (do humano), não do *dado*. A fonte real estava ignorada: `ExtractedFieldStaging.document_id`. Tratamento: `GET /timeline` (`_enrich_timeline_origin`) resolve no read-time `field_id → staging.document_id → Document` e entrega `origin_document`; a UI mostra "Origem do dado: <documento>" e **nunca** "fonte: null". Read-time → eventos já gravados (process 13) também ganham origem, sem reescrever audit imutável. Validação: `historicoEventos.test.ts` 11 casos (zero termo técnico), `test_timeline_enriches...` backend, `npm test` 64 verdes, tsc/build verdes. Escopo restrito ao histórico. Doc: `docs/trabalhos/historico_eventos.md`.

**Pulso 2026-06-18 (Ficha 07 — Aba Ações + Quadro de Ações global — `feat/ficha07-aba-acoes`):** onde o diagnóstico vira trabalho. Entidade nova **`Acao`** (tabela `acoes`, migration `ac7f01b9e3d5`): ação de remediação triável vinculada a um caso, com origem + fonte (#70), `vinculo_passivo` (JSON solto, **sem FK**), `responsavel_id` **nullable** (MVP sem Bloco 0), `prioridade`, `status` (a_fazer/em_andamento/concluida/bloqueada), `tipo_triagem` (pendente/tarefa/escopo/dispensada), `dedupe_key` (idempotência). Distinta de `Task` (genérica). **Geração** (`POST /processes/{id}/acoes/generate`, idempotente) lê o diagnóstico mais recente e cria ações `pendente` de `riscos[*].proximo_passo` + `afirmacoes categoria=acao`, cada uma com fonte (sem fonte → `sem_fonte`, nunca inventa). **Triagem** (`POST .../triagem`: tarefa/escopo/dispensar — Princípio 1; `escopo` só marca candidata a proposta, não constrói Orçamento). **Quadro global** `/acoes` (kanban por status, ações de todos os casos, card mostra o caso de origem, move entre colunas). Decisão de domínio (Isis 16/06) registrada em **ADR-016**: concluir uma ação **NÃO** resolve o passivo — não há caminho de escrita `Acao`→`RegulatoryIssue`/achado. Renomeação: board `/processes` (casos por macroetapa) virou **"Casos"** no menu (liberou o nome "Quadro de Ações"). Validação: `tests/api/test_acoes.py` **10 verdes** (geração c/ fonte, idempotência, triagem, conclusão não altera passivo, kanban c/ caso de origem, tenant isolation); `tsc`+`build` verdes. Doc: `docs/trabalhos/ficha07_acoes.md`.

**Pulso 2026-06-07 (consistência dos agentes LLM — `fix/llm-consistencia`):** três causas do "uma hora vai, outra não" no caso real #12 (São Jorge), medidas em prod (ai_jobs reais). **(1) Truncamento (Item 1):** diagnóstico rodava `gpt-4.1` com teto global `AI_MAX_TOKENS=2048` — o formato pós-#70 (`{afirmacao,fonte,confianca}`) estourava e o JSON chegava cortado → `[json_parse]` intermitente (jobs 399/405/398 `failed`; os `completed` tinham `tokens_out`<2048). Fix: gateway captura `finish_reason` sempre, retry automático com `max_tokens` dobrado (até `AI_MAX_TOKENS_CEILING`) e `AITruncationError` legível se persistir; diagnóstico ganhou teto dedicado **32.768** (máx. do gpt-4.1) + cost cap próprio; teto global 2048→4096; `base.run()` propaga `.message`. **(2) Legislação refém do 503 (Item 2):** `model=` explícito desligava o fallback (jobs 373/397/365 `failed` com `ServiceUnavailableError: GeminiException`). Fix: nova **matriz de equivalência agente×provider** (`app/core/model_matrix.py`) — resolve por providers DISPONÍVEIS, preserva o primário e adiciona equivalentes de outros providers só como fallback; BYOK de 1 provider não quebra. **(3) RAG zero trechos (Item 4 — diagnóstico):** `knowledge_catalog` e `legislation_documents` estão **VAZIOS em prod** (corpus ingerido só em dev/local; Supabase prod criado 19/05) → legislação com `tokens_in≈572/694`. Causa ESTRUTURAL (dado ausente, não bug de busca); reportado + dívida **#47** + log de observabilidade quando RAG=0. **Item 3:** golden tests no CI (`tests/agents/golden/` + gateway/matriz). Validação: bug provado em prod, fix provado deterministicamente (`tests/agents`+`tests/core` **223 verdes**); caso #12 real 3× é validação pós-deploy. Doc: `docs/trabalhos/llm_consistencia.md`. Branch `fix/llm-consistencia`. Embeddings seguem com chave da casa (não migrados).

**Pulso 2026-06-07 (calibração v2 da matriz + recuperação do RAG — `fix/matriz-v2-rag-recuperacao`):** 5 defeitos do caso real **#12** (São Jorge/GO), todos medidos no dump de prod antes de corrigir. **A (parse decimal):** a matrícula 4655 tinha a área como **dict** (`{"value":349.9022,...}`) e `_to_float_br` recebia `str(dict)` — a vírgula do repr disparava o ramo PT-BR → `3499022`, e a soma das matrículas dava **3.502.448 ha**. Fix: parser rejeita dict/lista, desembrulha `{value}`, separador decimal = o último entre `.`/`,`; `parse_area_ha` única (m²→ha); sanidade >100k→linha de revisão; origem (`ficha01_extraction`) desembrulha o envelope `{value,confidence}`. **B (hint poluído):** `{'value':'4655'}`, `MATR. 2.923 R-01`, `4655 (2 de 3)`, `6.776`, TAD `492262` viravam colunas → `_clean_matricula_hint` (regex) normaliza/colapsa; área sem hint (ITR) não confronta (linha `area_sem_vinculo`). **C (denominação):** `"Certidão de Embargo"` (título de doc) saía como denominação → `_is_doc_title` filtra prefixos (`LOTE 02AA` é real — intake multi-lote). **D (recomendação cruzada):** pendência "Documentos" com "Autorização de **Desmat**amento" casava `supressao` e nascia falsa "Supressão pós-2008" com ação de acesso → `_classificar_pendencia` respeita a categoria "Documentos". **E (RAG zero c/ corpus populado):** `demand_type="nao_identificado"` (sentinela) virava JOIN impossível → **0 linhas** (medido); e `uf=:uf` excluía os 761 federais. Fix: sentinela→None + fallback que solta demand_type; `search` inclui federal (`uf=:uf OR uf IS NULL`). **Provado:** matriz re-rodada no #12 sem 3,5M/colunas-lixo/embargo/supressão-cruzada; RAG no corpus local → **8 trechos** (sim ~0,69, normas GO reais) onde antes dava 0. Suite **895 verde** (+11 testes: `test_matriz_caso12_real`, `test_knowledge_catalog_search`). Não tocou no contrato de fontes do #70 nem no chunking. Doc: `docs/trabalhos/matriz_v2_rag.md`.

**Pulso 2026-06-05 (intake — roteamento geoespacial + card lateral):** dois sintomas de produção corrigidos. (1) **`.kml` caía no OCR de PDF** e estourava cascata técnica (`pypdf` 0 chars → Gemini `400 Unsupported MIME type: application/octet-stream` → `rasterization_failed`). Causa medida: `import_draft_documents` enfileirava `ocr_then_extract` para TODOS os docs do draft sem guard por tipo. Fix (só ROTEIA — geometria real é o gap D1): novo `app/services/geo_files.py` (`is_geospatial` por extensão `kml/kmz/shp/shx/dbf/prj/geojson/gpx` **ou** MIME + `zip_contains_shapefile`); no `/import` e `/confirm-upload` o geo entra `ocr_status=not_required`/`document_type=geoespacial` sem dispatch (resposta agrega `docs_skipped_geo`); guard no worker (extensão/MIME antes do download; `.zip`-com-shapefile após) com falha LIMPA; guard no orquestrador (`ocr_pdf` sem assinatura `%PDF` → `not_a_pdf`, sem cascata). (2) **Card do intake não atualizava** ao job concluir (preso em "Aguardando", consultor achava que falhou). Causa medida: o polling de `DraftDocumentUploader` só ligava com doc em `processing`, mas o `/import` marca `pending` → intervalo nunca iniciava. Fix: flag `awaitingOcr` + polling enquanto houver doc não-terminal; pill "Armazenado" + mensagem honesta para `not_required`. **Validação:** backend venv+Testcontainers (30 testes novos; regressão workers/services/intake **190 passed**; ruff limpo); frontend `tsc`/`build` limpos, `npm test` **53 passed** (regressão polling pós-import + pill geo), eslint limpo. NÃO validado ao vivo: E2E browser→MinIO→Celery (prova por integração+unit). Doc: `docs/trabalhos/intake_geo_routing.md`. Branch `fix/intake-geo-routing`. Gap **D1** (parser KML/SHP → `Property.geom`; dívidas #14/#15) segue frente própria.
**Pulso 2026-06-05 (Ficha 01 / FASE 4 — Decisão + Consolidação, fecho do ciclo):** o consultor decide o staging e a consolidação DETERMINÍSTICA (sem LLM) grava na base real. Endpoints: `POST /processes/{id}/staging-fields/{fid}/decidir` (`aceitar`/`escolher_fonte`/`editar`/`rejeitar`; **gate** aceitar divergente_transcricao → 422; divergente_fundo = achado sem valor), `POST .../aceitar-consistentes` (lote), `POST /processes/{id}/consolidar` (serviço `staging_consolidation.py`, idempotente: aceito → Client/Property/Matricula com **upsert por matricula_hint**; allowlist+alias; **NÃO sobrescreve `total_area_ha`** — área é derivada; auditável). UI: `ConsolidacaoPanel` estende a aba Alertas (grupos por entidade, ações por campo, banner lote, botão consolidar + resumo) — fluxo de issues intacto. **Validação real rodando (ciclo completo São Jorge, processo 30):** lote 2 aceitos → gate 422 → escolher_fonte denominação → aceitar pendentes → consolidar = 7 campos, **2 matrículas criadas** (4.698 area 660,6561/cartório/denom/RL; 6.776 area 349,9022), Client+Property atualizados, **`area_total_matriculas`=1.010,5583**, `total_area_ha`=250 intacto; **idempotente** (re-consolidar 0 criadas); auditoria completa. **Ciclo Ficha 01 fechado (Fases 1-4).** Suite verde; ruff/tsc/build/eslint limpos. Doc: `docs/trabalhos/ficha01_fase4.md` + `FLUXOS_E2E.md` (Fluxo 8). Branch `feat/ficha01-fase4-decisao-consolidacao`.
**Pulso 2026-06-05 (Ficha 02 / FASE 3 — Auditor → Matriz de Inconsistências):** a saída canônica do `auditor_imovel` virou a MATRIZ (Ficha 02): confronto multi-fonte DETERMINÍSTICO (sem LLM) lendo o staging da Fase 2. Novo `app/services/inconsistency_matrix.py`: colunas dinâmicas por fonte (cada matrícula via `matricula_hint` + ccir/itr/car/rat/sigef), linhas canônicas (area_total/denominacao/codigo_incra/sigef/car_presenca/acesso) + linhas técnicas das `pendencias_rat` (`profundidade=tecnica`, gap D1), âncora=SIGEF, taxonomia §4 (enum `MatrixSituacao`: critico/inconsistente/divergente±subtipo/atencao) com destino. Efeitos: marca o staging (consistente/divergente_transcricao/divergente_fundo — decisão aceito/rejeitado é Fase 4); persiste `matriz_inconsistencias` no AIJob do auditor (campo NOVO, shape antigo intacto); diagnóstico ganhou `_load_persisted_auditor` (padrão atendimento) e cita a matriz; UI `AuditorResult` ganhou a tabela (item×situação×ação, cores). Fase 2 ajustada (matrícula `denominacao`, ITR `numero_car`). Skill auditor → v1.2.0 (nota da matriz; `situacao` ≠ `grade`). **Validação real rodando (caso São Jorge §7):** area_total divergente "0,153 ha", denominacao divergente, codigo_incra atencao, sigef critico, car/ITR inconsistente, acesso atencao, 3 técnicas critico; staging marcado; diagnóstico re-rodado citando a matriz. Suites verdes; ruff/tsc/build limpos. Doc: `docs/trabalhos/ficha02_fase3.md`. Branch `feat/ficha02-fase3-matriz-inconsistencias`. NÃO nesta fase: tela de decisão (4), LLM no auditor, confronto espacial (D1).
**Pulso 2026-06-05 (Ficha 01 / FASE 2 — extração estruturada → staging):** o Extrator passou a preencher `ExtractedFieldStaging` com extração ESTRUTURADA por tipo (1 chamada LLM dedicada/doc, reusando o texto do OCR). Novo `app/services/ficha01_extraction.py`: classificador por conteúdo (`classify_doc_type`, rule-based) reconhece os 8 tipos canônicos (`rg_cpf, endereco, car, ccir, matricula, itr, sigef, rat` + outro); `build_staging_fields` mapeia o JSON por tipo → linhas de staging (escalares + `car.matriculas[]` → `matricula_listada` por item com `matricula_hint`; `rat.pendencias[]` → `pendencias_rat`). `ExtratorAgent._stage_ficha01` grava no staging nos 2 caminhos SEM alterar `AIJob.extracted_fields` (UI/diagnóstico intactos); `base.py` expõe `self._current_job` p/ `ai_job_id`. **Decisão `rat` (Ficha 02 §8):** RELATÓRIO DE ANÁLISE TÉCNICA do CAR (não "retificação", que é ato). Validação real rodando (equivalentes São Jorge, docs `outro` → classificados certo): Recibo CAR → 9 linhas (nº CAR, área 1010,5583, **2 matrículas hints 4.698/6.776**); RAT → 7 linhas (protocolo, situação Pendente, **`pendencias_rat` estruturado**); certidão → 6 linhas (hint 4.698). 22 linhas `pendente`/`extrator`/`ai_job_id`; `extracted_fields` não regrediu. Suite verde + ruff limpo. Doc: `docs/trabalhos/ficha01_fase2.md`. Branch `feat/ficha01-fase2-extracao-estruturada`. NÃO nesta fase: reconciliação (3), tela de Alertas (4), gravar base real.
**Pulso 2026-06-04 (Ficha 01 / FASE 1 — Matrícula + staging):** instalada a fundação da Ficha 01 (espec fechada pela dupla) — **só schema**, comportamento de extrator/auditor/intake inalterado. Entidade **`Matricula`** (1 Imóvel : N Matrículas — nº matrícula, cartório/registro, INCRA/SNCR, NIRF/CIB, SIGEF, `area_ha`, averbações APP/RL, ônus, `proprietarios` JSON) + tabela **`ExtractedFieldStaging`** (agentes propõem, consultor decide; enum `extractedfieldstatus` de 6 valores, `confidence`, `target_entity/field`, `matricula_hint`, rastreabilidade `created_by_agent`/`ai_job_id`). `Property` ganhou `matriculas` (1:N) + `area_total_matriculas()` (soma derivada); `total_area_ha` mantido por compatibilidade. Migration `a1f2c3d4e5f6` provada up→down→up limpa (enum criado/dropado explícito). Endpoints: `GET`/`POST /properties/{id}/matriculas`, `GET /processes/{id}/staging-fields` (filtro por status, 422 em status inválido, 404/401). Soma do caso real validada: matrículas 4.698 (660,6561) + 6.776 (349,9022) = **1.010,5583 ha**. ADR-015 + MODELO_DE_DADOS atualizados. Suite completa verde + ruff limpo. Doc: `docs/trabalhos/ficha01_fase1.md`. Branch `feat/ficha01-fase1-matricula-staging`. NÃO neste PR: fases 2-4 (extrator→staging, reconciliação, tela de Alertas).
**Pulso 2026-06-04 (teste Isis rodada 2):** 5 achados (orquestração + contexto entre agentes), reproduzidos no análogo local processo 30/tenant 2. **B+C** (auditor some do histórico / disparo fica "agendada pra sempre"): causa-raiz única medida = `validate_preconditions()` levanta `ValueError` **antes** de `_create_running_job()` → nenhum AIJob criado (some do histórico) e `run_agent` faz `self.retry()` de erro determinístico (retry storm + UI presa em "agendada"). Fix: `BaseAgent.run()` cria o job antes e valida **dentro do try** (falha vira job `failed` visível); `run_agent` não faz retry de `ValueError`. Provado: auditor sem processo → job 146 `failed` em 0.79s sem retry. **A** (só Extrator reagia ao processo): cards de agente em `AgentsPage.tsx` agora process-aware (habilitam/rotulam com processo válido). **E** (atendimento não chega ao diagnóstico): `diagnostico.py` passa a injetar narrativa do processo (`description`/`initial_summary`/`intake_notes`) + AIJob do `atendimento` (SEMPRE, fonte adicional) — sem tocar prompt-template. Provado no processo 30: diag passou de "Não há embargo vigente" para "relato verbal de embargo… sem documentação". **D** confirmado resolvido pela rodada 1 (kanban 200/20 cards, issues 200/5). Suites: `tests/agents/` 183, suite completa verde, tsc+build verdes. Doc: `docs/trabalhos/teste_isis_rodada2.md`. Branch `fix/teste-isis-rodada2`.
**Pulso 2026-06-04 (teste Isis rodada 1):** 6 defeitos do caso real #10. **A** (500 em `/properties/{id}/issues`): causa medida = `documentos_cruzados` gravado como lista de objetos vs `list[str]` no schema → `ResponseValidationError` derruba a lista inteira; fix coage na leitura (`RegulatoryIssueOut`, sem migration) + na escrita (`@validates` no model). **B** (`[object Object]` no extrator): `String(value)` em campo-objeto `{value,confidence}`; fix `extratorFieldValue` desempacota via `humanizeValue`. **D** (timeout "None seconds" na legislação): modelo explícito = sem fallback nem retry; fix retry só p/ transitórios (`AI_MAX_RETRIES=2` + backoff) e timeout defensivo `or 30.0`. **C** e **F** confirmados resolvidos pelo #57 (formatLegislacao + fallback persistido cobre `doc_type "outros"`), travados com testes. **E** = sintoma downstream de A (AlertasTab em `error` não renderiza os cards coloridos). Suites: backend 760, frontend 51, build/tsc/eslint/ruff verdes. Doc: `docs/trabalhos/teste_isis_rodada1.md`. Branch `fix/teste-isis-rodada1`.
**Pulso 2026-05-31 (PR I — visual):** wizard de intake (`/intake`) padronizado ao design system — tema claro alinhado ao Dashboard, tokens (`bg-background`/`bg-card`/`bg-primary`) no lugar do tema escuro próprio (gradiente slate→emerald + glassmorphism). Só estilo; funcionalidade inalterada; `npm run build` verde. Pendência: `DiagnosisPanel`/`DraftDocumentUploader` ainda escuros (fora de escopo). Origem: auditoria `docs/arquivo/auditorias/2026-05-31_ui_credenciais_intake.md` (Frente C).
**Pulso 2026-05-31 (UI Credenciais):** Cliente Hub ganhou aba **Credenciais** consumindo `/api/v1/credentials` (CRUD completo por cliente). A resposta mostra `has_password` como badge "Senha protegida"; a UI não tenta revelar senha e no edit omite `password` quando o campo fica vazio, preservando a senha atual no backend. Contrato real confirmado: campos `portal`, `label`, `login`, `password`, `url`, `notes` — não há `valid_until` no backend atual (dívida #36 aberta para validade/alerta proativo).
**Pulso 2026-06-01 (Evolution fora do boot):** `docker compose up -d` voltou a subir o core. A definição do serviço `evolution` exigia `EVOLUTION_API_KEY` (`${EVOLUTION_API_KEY:?...}`) e abortava o startup inteiro mesmo com a Evolution dormente. Decisão do André: tirar o Evolution do compose/boot AGORA para o sistema ser validável E2E; o canal WhatsApp volta depois. O serviço `evolution` e o profile `whatsapp` saíram do `docker-compose.yml`; o provider (`app/services/messaging/`) e o webhook permanecem no código, e o webhook responde **503 "WhatsApp não configurado"** sem as envs. Evidência: `docker compose up -d db redis minio api worker` → todos healthy/up, `curl /health` → 200. Dívida #37 aberta para reintegrar a Evolution; reativação documentada no RUNBOOK_OPS.

**Pulso 2026-06-01 (mergulho fluxo agêntico):** diagnóstico por EXECUÇÃO (sistema rodando) do fluxo intake→agentes. Reproduzido ponta a ponta: OCR+extrator+atendimento **funcionam** (caso de teste: matrícula → 12 campos). O que trava a entrega do diagnóstico: (1) `create-case` dispara só `atendimento` — a chain `diagnostico_completo` não auto-roda; (2) na chain o `extrator` pulava sem `document_id`; (3) a `legislacao` é bloqueante e flaky (timeout/json_parse) e ao falhar **aborta a chain antes do `diagnostico`** → 0 diagnósticos. **Corrigidos neste PR (revalidados rodando):** CORS-mascara-500 (500 agora carrega ACAO+request_id), path do WS (`/api/v1/ws` conecta), gap do extrator (resolve docs do processo → 9 campos, não pula). **Viram dívida:** #38 (chain aborta na legislacao — ALTA), #39 (robustez legislacao), #40 (2 SKILL.md inválidos), #41 (auto-trigger pós-case — decisão produto), #42 (bucket MinIO presigned), #43 (Error Boundary global). Doc: `docs/arquivo/auditorias/2026-06-01_mergulho_fluxo_agentico.md`. Branch `fix/mergulho-fluxo-agentico`.

**Pulso 2026-06-01 (storage R2 + Redis SSL + download silencioso):** corrigida a causa-raiz do "OCR não extrai nada" — clients boto3 com `region="us-east-1"` hardcoded (R2 exige `auto` → `SignatureDoesNotMatch` no GET) + `download_bytes` que engolia o erro como `no_bytes`. Também: Redis `rediss://` normaliza `ssl_cert_reqs` (evento realtime voltou) e endpoint respeita `MINIO_SECURE`. Provado rodando local (MinIO sem regressão, repro+fix do SignatureDoesNotMatch e do CERT do Redis, 20 testes). Detalhe e snippet de prova R2 pro Render Shell: `docs/trabalhos/storage_r2_redis.md`. Branch `fix/storage-r2-region-redis`.

**Pulso 2026-06-02 (OCR — modelo Gemini descontinuado):** com o storage corrigido o OCR roda, mas doc escaneado ficava `ocr_failed` — `app/services/ocr_pdf.py` tinha `gemini-2.0-flash` **hardcoded** (descontinuado pelo Google → 404) e o fallback OpenAI Vision pendurava ~272s (litellm re-tentando 3×). Fix: modelo virou env `GEMINI_OCR_MODEL` (default `gemini/gemini-2.5-flash`); fallback OpenAI com timeout próprio (75s) + `num_retries=0`. Provado rodando local (PDF imagem-only → Gemini 2.5-flash → `chars=146`, sem 404). Doc: `docs/trabalhos/ocr_gemini_model.md`. Branch `fix/ocr-gemini-model`.

**Pulso 2026-06-02 (OCR multipágina — só lia 1 página):** a escritura do Romilton (doc 118, 6 págs) saía com 832 chars = só a certidão da capa; o Gemini, com o PDF enviado inline, transcrevia só a 1ª página (provado no PDF real). Fix: `extract_text_with_gemini` agora rasteriza cada página e faz 1 chamada por página, concatenando (`reasoning_effort=disable` + retry próprio p/ 503). Também: `cache_twin` passou a respeitar `force=True` (não mascara reprocessamento) e `soft_time_limit` 180→300s. Provado rodando no PDF real: 832 → ~18-21k chars, área/matrícula/CAR presentes. Doc: `docs/trabalhos/ocr_multipagina.md`. Branch `fix/ocr-multipagina`.

**Pulso 2026-06-02 (extrator truncava em 3000 chars):** com o OCR já entregando o texto inteiro (~20.8k chars), o extrator devolvia só nome+CPF (da capa) e os 9 campos do imóvel vinham `None` — `document_extractor.py:183` cortava o texto em `text[:3000]` e os campos do imóvel ficam depois disso. Fix: janela configurável `EXTRACTOR_MAX_CHARS` (default 30k) + prompt da matrícula avisa que o doc tem várias seções. Provado rodando no texto real do doc 118: área 58,7654 / município Uirapuru / UF GO / denominação / comarca / cartório passaram de `None` a preenchidos (numero_matricula segue None — correto: 6253 é dos confrontantes lotes 31/33). Doc: `docs/trabalhos/extrator_truncamento.md`. Branch `fix/extrator-truncamento`.

**Pulso 2026-06-02 (UI renderer + seletores):** resultado dos agentes saía como JSON cru e o card mostrava `Agente —` / `Modelo —`. Causa raiz (não a hipótese do prompt): `agent_name` **estava** no banco (chain inclusa), mas `_serialize_job` (`GET /ai/jobs`) **não o serializava** → front recebia `undefined` → `GenericResult`/`JSON.stringify`. Fix: serializer expõe `agent_name`+`chain_trace_id`; novo `AuditorResult`; `GenericResult` à prova de `[object Object]`; `IntakeWizard` troca inputs de ID por dropdowns com busca (cliente via `/clients/`, imóvel via `/properties/?client_id=`). Provado rodando: API devolve `agent_name`, 16 clientes/1 imóvel nos seletores, `tsc` verde. Fecha #UX-1/#UX-2. Doc: `docs/trabalhos/ui_renderer_seletores.md`. Branch `fix/ui-renderer-seletores`.

**Pulso 2026-06-01 (PR #38 — chain legislação):** `diagnostico_completo` agora entrega diagnóstico mesmo quando `legislacao` falha ou pede revisão. Medição rodando mostrou RAG local em ~4,5s, contexto por metadados em ~0,5s e timeout real na chamada Gemini (`gemini/gemini-2.5-flash`, `litellm.Timeout`) em ~33s. Correção escopada em `app/agents/orchestrator.py`: em `diagnostico_completo`, `legislacao` é insumo intermediário e fica não-bloqueante para `requires_review=True` e falha; o erro fica em `chain_data["legislacao"]` e `diagnostico` continua com contexto parcial. Revalidado rodando no `process_id=30`/`tenant_id=2`: cenário com timeout → `diagnostico` rodou depois e entregou 3 passivos (AIJob 135); cenário sem timeout mas com `requires_review=True` → `diagnostico` também rodou e entregou 3 passivos (AIJob 139). Dívida #38 fechada; #39 permanece para robustez própria da legislação. Doc: `docs/arquivo/auditorias/2026-06-01_chain_legislacao.md`.

**Pulso 2026-06-01 (front-matter dos 2 SKILL.md — dívida #40 fechada):** os 2 únicos SKILL.md formais (`diagnostico/situacao_ambiental_imovel_rural` e `auditor_imovel/analise_divergencias_documentais`) tinham front-matter inválido e `discover_skills` os **ignorava silenciosamente** — os agentes rodavam sem a skill. Corrigido **só o front-matter** (corpo de domínio intacto): diagnóstico ganhou `agent: diagnostico` + `name` com prefixo + `applies_to: {uf: [GO, MS, MT]}`; auditor ganhou `name` com prefixo + `applies_to: {doc_types: []}` + descrição. **Provado rodando** (container `api`): `discover_skills()` lista as 2 sem warning, `load_skill()` retorna `SkillContent`, e `DiagnosticoAgent._compose_system_with_skills()` com `ctx.metadata={"uf":"MS"}` **injeta** o corpo (~55 KB) entre `<!-- skills:start -->`/`<!-- skills:end -->`; sem `uf` não injeta. 26 testes de skills verdes. O auditor segue determinístico (skill no catálogo, não injetada). **Gap novo (dívida #44, ligada à #38):** a chain não deriva `uf` do imóvel/processo — fora do escopo deste PR. Docx Word duplicados movidos para `docs/_archive/skills-fontes-word/`. Branch `fix/skills-frontmatter-40`.

**Pulso 2026-06-02 (diagnóstico → GPT-4.1):** o agente de diagnóstico saiu de `gpt-4o-mini` para **`gpt-4.1`** via novo setting `AI_DIAGNOSTICO_MODEL` (default `gpt-4.1`, por env — mesma convenção do `GEMINI_LEGAL_MODEL`, nunca hardcoded no agente). Só o diagnóstico mudou; os demais agentes seguem no default. Adicionado em `docker-compose.yml` (api+worker) e `render.yaml`. Provado rodando: `settings.AI_DIAGNOSTICO_MODEL='gpt-4.1'` e chamada real ao gateway `complete(model='gpt-4.1')` → `model_used=gpt-4.1`, `content='OK'`. Reversível por env. Doc: `docs/trabalhos/diagnostico_modelo_gpt41.md`. Branch `fix/diagnostico-modelo-gpt41`.

**Pulso 2026-06-03 (CI — backend inteiro verde, 1ª vez):** começou como "Backend Lint verde" e a cascata expôs que **3 jobs de backend nunca rodaram no CI** (ficavam *skipping* atrás do lint vermelho desde #52). Diagnóstico do lint: **(A) infra + (B) código** — o CI instalava só `requirements.txt` mas ruff/mypy vivem em `requirements-dev.txt` → `ruff: command not found` (127). Entregue: (1) **lint** — `requirements-dev.txt` nos jobs, ruff 77→0 (62 autofix + 15 manuais sem mudar comportamento; 2 `# noqa` justificados), mypy **advisory** (`continue-on-error`, dívida #46), ruff/mypy pinados; (2) **backend-test** — `python -m pytest` (sys.path), build da imagem custom PostGIS+pgvector pro Testcontainers, `CREDENTIAL_ENCRYPTION_KEY`+`AI_ENABLED`+chave fake (testes IA mockados), `--cov-fail-under=0` (cobertura 63%, gate 70% era TODO) → **753/753**; (3) **backend-migrations** — build+run da imagem custom, e **2 bugs reais de migration** corrigidos (decisão André): `UnsafeNewEnumValueUsage` do enum `lead` em `afcea9834c04` (→ `autocommit_block`) e `op.execute(text, dict)` no downgrade da seed `024fe3f5dbeb` (→ `.bindparams`) — ambos só quebravam em `upgrade head` do zero (deploy novo). **CI 100% verde** (6 jobs), `mergeStateStatus: CLEAN`. RUNBOOK_DEV ganhou seção de lint. Doc: `docs/trabalhos/backend_lint.md`. Branch `fix/backend-lint` (PR #56).

**Pulso 2026-06-03 (CI — zerar lint react-hooks):** o check **Frontend Lint** estava cronicamente vermelho com 6 problemas pré-existentes (5 erros + 1 warning, `--max-warnings=0` quebra com warning) em `IntakeWizard`, `AlertaCard`, `QuadroAcoes`, `CredentialModal`, `PriorityStep` — escondia erros novos. Cada um classificado e corrigido **na estrutura, sem `eslint-disable`**: `Date.now()` no render → lazy `useState` (purity); 2× `set-state-in-effect` → sync durante render (AlertaCard) e lazy init + `key` no pai (CredentialModal); `columns` instável → `useMemo` (exhaustive-deps); constantes exportadas junto do componente → movidas p/ `priorityOptions.ts` (react-refresh). Validado: lint **0**, tsc/build verdes, 48/48 testes, e anti-loop nas 2 telas de setState (11/11 sem `Maximum update depth`). Backend Lint segue dívida separada. Doc: `docs/trabalhos/lint_react_hooks.md`. Branch `fix/lint-react-hooks`.

**Pulso 2026-06-03 (UI — termos técnicos):** termos técnicos vazavam pra tela (`snake_case` cru, JSON cru, `[object Object]`, `demand_type.toUpperCase()`) porque os dicionários de rótulo de campo eram fragmentados/incompletos e vários pontos humanizavam com `key.replace(/_/g,' ')`. Centralizado em `frontend/src/lib/labels/fieldLabels.ts` (`labelFor`, `humanizeValue`, `isMetaField` + `FIELD_LABELS` com matrícula/RG). Corrigidos `AgentResultRenderer` (extrator+genérico), `DocumentsTab` (fim do `JSON.stringify`), `WorkflowTimeline` (usa `DEMAND_TYPE_LABELS`), `PreviewPanel`/`DraftDocumentUploader` (importam o módulo). Achado: os 2 `CATEGORY_LABELS` **não** eram duplicados (taxonomias distintas) — mantidos. Provado por teste de render (8 casos: matrícula+RG+genérico, sem termo técnico/JSON/meta) + 48/48 suite + tsc/build verdes. Doc: `docs/trabalhos/ui_termos_tecnicos.md`. Branch `fix/ui-termos-tecnicos`.

**Pulso 2026-06-03 (diagnóstico enxerga o insumo):** o diagnóstico rodava com `tokens_in≈358` e saía genérico quando chamado avulso (aba Agentes) ou com extrator falho na rodada — `extracted_fields`/`legal_context` vinham **só** de `chain_data` (efêmero). Fix em `app/agents/diagnostico.py`: fallback persistido que, sem `chain_data`, recupera os campos extraídos do `AIJob` do extrator (ambos os shapes) e o enquadramento do `AIJob` da legislação do mesmo processo, e enriquece o `property` do prompt a partir dos campos extraídos (sem gravar na Property); `chain_data` segue prioritário (sem regressão). Confirmado `model_used=gpt-4.1`. UI: citações de lei deixaram de sair `[object Object]` (novo `formatLegislacao`). Provado rodando (processo 30): `tokens_in` **359→3491**, output cita "Fazenda Boa Vista"/Auto de Infração, 44 testes de diagnóstico verdes, tsc+build verdes. Doc: `docs/trabalhos/diagnostico_insumo.md`. Branch `fix/diagnostico-insumo`.

> Este documento é regenerado a cada sprint. Reflete o estado real da plataforma agora, não o estado planejado. Quando algo muda no código, muda aqui.

---

## Visão de uma página

**O que está funcionando hoje em produção/dev:**

- Backend FastAPI com 27 routers REST + WebSocket
- 11 agentes de IA via LiteLLM (multi-provider, fallback, cost cap enforced) — `auditor_imovel` ativo na chain `diagnostico_completo` desde 2026-05-24
- Painel do consultor (React + Vite) com 36 telas em 10 áreas
- Multi-tenant com isolamento por `tenant_id` validado no JWT
- AuditLog com hash chain SHA-256 encadeado
- RAG semântico via pgvector (~23.000 chunks em 4 UFs; +466 chunks de 9 normas-chave GO/federal)
- Sprint Waitlist B1 mergeada (commit `148c25b`)
- Sprint A2 fechada (redator + diagnóstico + legislacao migrados para schema validado)
- **Fase 2 (skill diagnóstico) fechada em 2026-05-23:** Risco 8+1 (taxonomia oficial),
  citation_evaluator no Diagnóstico, `auditor_imovel` + `property_audit` determinístico,
  9 normas-chave indexadas. Ver `docs/auditoria/MAPA_GAPS_CONFIRMADO_2026-05-23.md`.
- **Pós-Fase 2 (Ondas A/B/C) fechada em 2026-05-24:** `auditor_imovel` ativo na chain
  `diagnostico_completo` via `NON_BLOCKING_REVIEW_AGENTS`; `POST /processes/{id}/diagnoses`
  versionado com gate A4 Pydantic↔JSONB; régua de 4 faixas para divergência (≤1%
  informativo / 1-5% atenção / 5-10% alto / >10% crítico) — **sempre emite** o finding.
- **PROMPT_4 (fechar-pipeline) mergeado em 2026-05-25** (commits `f93b4b4` + `c74ff2e`):
  - **Onda A** — `DiagnosticoAgent` consome `chain_data["auditor_imovel"]`. Cada finding
    vira `Divergencia` + `Risco` com `grau` 4 níveis preservado.
  - **Onda B** — `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` fecha a
    **camada 1 do Princípio 1** (consultor assina). AuditLog hash chain SHA-256.
- **PROMPT_5 (remodelar `RegulatoryIssue`) mergeado em 2026-05-25** (3c8ac8f):
  - **Onda A** — `RegulatoryIssue` ganha taxonomia rica: `familia` (enum estável 11) +
    `codigo_alerta` (FK em `regulatory_issue_catalog`, catálogo evolutivo via INSERT) +
    campos `muda_rota_regulatoria`/`muda_escopo_preco_prazo`/`documentos_cruzados`.
    `severity` passa de 3 para 4 níveis (`informativo`/`atencao`/`alto`/`critico`) — sai
    o `_GRADE_TO_SEVERITY` que colapsava (dívida #4 fechada). `type` legado fica nullable.
    Migration `c1b2d3e4f5a7` cria, popula 45 entradas seed e migra dados antigos.
  - **Onda B** — auditor emite codigos reais (📄: AREA_MATRICULA_X_CAR, GEO_AUSENTE,
    RL_MATRICULA_DIVERGENTE_RL_CAR, etc.); 🛰️ e 🔌 ficam no catálogo mas não emitidos.
  - **Onda C** — proposta de reconciliação dos 3 status em
    `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md` (Opção A recomendada).
- **PROMPT_6 (camada 2 do Princípio 1) mergeado em 2026-05-26** (62740ae):
  - **Onda A1** — `RegulatoryIssue` ganhou 3 status reconciliados (Opção A):
    `status_achado` (default `suspeita`), `decisao_consultor` (nullable),
    `decisao_consultor_justificativa`, `decisao_consultor_at`, `status_saneamento`
    (default `pendente`). Migration `d2c3e4f5a6b8` (aditiva).
  - **Onda B** — `PATCH /api/v1/properties/{prop}/issues/{id}` edita os 3 status +
    decisão. AuditLog **granular por campo** com hash chain SHA-256.
  - **Onda D (camada 2)** — `PATCH /validate` com gate: **422** se houver
    `RegulatoryIssue` com `severity=critico` sem `decisao_consultor`.
    5 botões P4 (`corrigir_antes` / `seguir_com_ressalva` / `solicitar_doc` /
    `fora_escopo` / `ignorar_justificado`) obrigatórios para críticas.
  - **Revisão pós-rodada (PR #7)** — validator de justificativa obrigatória para
    `ignorar_justificado` e `fora_escopo` (#19 fechada); MODELO_DE_DADOS e API_v1
    atualizados (gatilhos de estrutura).
- **ADR-012 aceito em 2026-05-26** — Isis validou: a decisão do consultor é
  **contextual ao processo**, não perene no imóvel.
- **PROMPT_7 mergeado em 2026-05-26** — implementa o ADR-012:
  - Nova entidade `ProcessIssueDecision` (FK composta `(process_id, issue_id)`
    única) com `decisao`/`justificativa`/`decided_by_user_id`/`decided_at`.
    Migration `e3d4f5g6a7b8`.
  - 3 campos de decisão **saem** do `RegulatoryIssue` (drop sem backfill —
    sem dados em prod ainda). Restam só os 2 status perenes (`status_achado`
    e `status_saneamento`).
  - Endpoints novos: `GET` e `PUT /api/v1/processes/{pid}/issues/{iid}/decision`
    (upsert; AuditLog granular por campo com hash chain SHA-256).
  - Gate `PATCH /validate` ajustado: cruza issues críticas × `ProcessIssueDecision`
    deste processo (não mais campo no `RegulatoryIssue`). Decisão tomada
    no processo A não libera o processo B (titularidade torta pesa diferente
    para venda e para crédito).
  - Validator de justificativa obrigatória (#19) migrou para o schema novo.
  - `decided_by_user_id` é melhoria proporcional ao Princípio 2 — autor
    explícito além do timestamp.
- **Skill `auditor_imovel/analise_divergencias_documentais` validada
  integralmente pela sócia** em 2026-05-26 — separação 📄/🛰️/🔌 confirmada.
- **PROMPT_8 mergeado em 2026-05-26** — fecha a dívida #17 (coerência entre status):
  - Helper puro `app/services/regulatory_coherence.py` com 2 regras semânticas
    (escopo fechado — sem máquina de estados completa).
  - **Regra A (perenes):** saneamento em `em_validacao`/`saneado` exige
    `status_achado in {confirmada, resolvida}`. Aplicada no `@model_validator`
    do `RegulatoryIssueUpdate` (fast-fail) E no endpoint `PATCH
    /properties/.../issues/{id}` sobre o **estado resultante** (fonte da
    verdade, cobre PATCH parcial).
  - **Regra B (cross-entidade):** `PUT /processes/.../decision` rejeita
    `status_achado == suspeita` com mensagem acionável ("Confirme ou
    descarte o achado antes de decidir").
  - Sem migration (validação, não modelagem). Suite 635/635 verde.
- **PROMPT_9 mergeado em 2026-05-26** — UI da camada 2 do Princípio 1
  (consome o backend regulatório sem inventar contrato):
  - Aba **"Alertas"** nova no `ProcessDetail` (block_type "active", entre
    "Visão geral" e "Ações"). Lista `RegulatoryIssue` do imóvel, críticos
    no topo. Cada `AlertaCard` tem: dois `<select>` pros status perenes
    + 5 radios da decisão + textarea de justificativa.
  - **Regra B preventiva na UI:** enquanto `status_achado === 'suspeita'`,
    o fieldset da decisão fica `disabled` com hint "Confirme ou descarte
    o achado para poder decidir". O consultor adjudica primeiro, aí a
    decisão libera. O 422 do backend é rede de segurança, não a primeira
    linha. **#19 (justificativa) validada client-side** + 422 inline.
  - **Bloco "Assinar diagnóstico vN"** no topo do `DiagnosisTab` com
    badge "N pendentes" (`useQueries` cruza issues críticas × decisões).
    Click → `PATCH /validate`. 422 do gate abre modal listando
    `alertas_pendentes`; click no item troca pra aba "Alertas" e faz
    `scrollIntoView` do card `#alerta-{id}`. **Autoridade do backend:**
    se cálculo client-side divergir do 422 (cache stale), confiamos no
    422 e mostramos o que veio.
  - **PropertyHub.AnalysesTab aumentado** (era stub com 5 casos sem
    contexto): vira lente do ADR-012 — lista issues do imóvel + chips
    de TODOS os processos da property, mais recente primeiro. Cada chip
    "Processo #N (demand) · {decisão|pendente} · Decidir/Ver" com
    verbo-por-estado via `useDecision`. Cor emerald = decidida, amber =
    pendente. Teto visual "+N mais" se overflow. Read-only — click leva
    à aba Alertas do processo.
  - **Camada de dados:** `frontend/src/lib/regulatory/{types,labels,hooks}.ts`
    espelha o contrato sem inventar campo nem renomear valor. Cache do
    `useDecision` é compartilhado entre AlertaCard, DiagnosisAssinatura
    e IssueProcessChip — três telas vêem a mesma decisão sem refetch.
  - **Testes:** 10 novos (Vitest+RTL), 31/31 verde. Runner
    `frontend/scripts/run-vitest.mjs` injeta `--experimental-require-module`
    via `NODE_OPTIONS` (workaround pro jsdom 27 + Node 22.11 — registrado
    no commit, removível quando upstream corrigir).
- **PROMPT_10 + PROMPT_11 mergeados em 2026-05-26** — fecha #23 (gate cobrando
  decisão em achado terminal — trap revelado pós-PROMPT_9):
  - Filtro do `PATCH /diagnoses/{version}/validate` cobra decisão em críticos
    com `status_achado in {suspeita, confirmada, ignorada}`. Excluídos só
    `descartada` ("não é divergência real") e `resolvida` ("corrigida no
    mundo") — neles não há o que decidir.
  - **PROMPT_11 corrigiu a versão original do #10**, que excluía `ignorada`
    por erro de simetria. `ignorada` = "achado REAL posto de lado"; setá-la
    via PATCH /issues não exige justificativa, então excluí-la abriria atalho
    pra silenciar crítico real sem registro (bypassa o #19). Quem quer ignorar
    registra `decisao=ignorar_justificado` (com justificativa); a Regra B
    permite porque `ignorada` ≠ `suspeita`.
  - `suspeita` permanece dentro do filtro pra **forçar adjudicação** antes
    de assinar — não é deadlock, o consultor pode mover o estado via
    PATCH /issues.
  - `resolved_at IS NULL` continua como critério ortogonal.
  - Sem migration, sem ADR. Testes no `TestValidateDiagnosisGateCamada2`:
    `descartada`/`resolvida` liberam; `suspeita`/`confirmada`/`ignorada`
    continuam exigindo (422).
  - **Follow-on aberto:** badge "N pendentes" do `DiagnosisAssinatura`
    (PROMPT_9) precisa espelhar a mesma exclusão (`descartada`/`resolvida`)
    pra não super-contar.
- **`fix/upload-checklist-binding` mergeado em 2026-05-28 (PR #14)** — destrava o ciclo de teste da Isis:
  - **Vínculo doc ↔ item de checklist no upload.** `DocumentConfirmRequest` ganha
    `checklist_item_id?: str` (opcional). O endpoint `POST /documents/confirm-upload`
    persiste a coluna `Document.checklist_item_id` (já existia no model) e — se o
    frontend não enviou um `checklist_item_id` explícito mas o `document_type`
    casa com um item pendente — chama `auto_link_document` para marcar o item
    como `received`. Sintoma original: documento subido não virava "recebido"
    no checklist mesmo com tipo correto.
  - **Campos extraídos visíveis na DocumentsTab.** Lista `Object.entries(AIJob.result)`
    do extrator (excluindo `document_id`/`doc_type`/`tenant_id`/`process_id`)
    em `<dl>` abaixo de cada documento processado — antes só aparecia o badge
    "Campos extraídos" sem mostrar o que foi extraído.
  - **`document_id` no PATCH "Recebido" do ProcessChecklist.** `handleReceived`
    passa `item.document_id` (quando existe) no payload — antes só mandava
    `action`, perdendo o vínculo se o consultor desfizesse + refizesse manualmente.
  - **Exclusão em cascata controlada de cliente e imóvel** (`app/services/cascade_delete.py`):
    `cascade_delete_client` apaga, em ordem: documentos do escopo do cliente
    (Document.client_id OU process_id no escopo OU property_id no escopo —
    nunca toca doc de outro cliente), checklists, processos, imóveis, contratos,
    propostas, cliente. Satisfaz FKs RESTRICT (Process/Property/Contract/Proposal
    em client_id). `cascade_delete_property` apaga documentos, checklists e
    processos do imóvel + o próprio imóvel. Cada cascata grava `AuditLog`
    `cascade_deleted` com `details` JSON `{"client_name"/"property_name", "cascade": {counts}}`
    e hash chain SHA-256 (LGPD).
  - **Preview da cascata antes de confirmar.** Endpoints novos
    `GET /clients/{id}/delete-preview` e `GET /properties/{id}/delete-preview`
    devolvem `{properties, processes, documents, checklists, contracts, proposals}`.
    Os modais (`Clients/index.tsx`, `Properties/index.tsx`) carregam o preview
    e listam contagens exatas antes do botão "Confirmar exclusão".
  - **Comportamento de DELETE de documento NÃO mudou:** `DELETE /documents/{id}`
    continua soft delete (`deleted_at`). A cascata acima é hard delete porque
    o caso de uso é resubir os mesmos dados de teste.
  - Suite ampliada das frentes afetadas: **186 testes passando**, tsc `--noEmit`
    zero erros. Sem migration (todas as colunas já existem no schema).
- **`fix/extrator-por-processo` em revisão (2026-05-28, logo após PR #14)** — fecha #25
  (extrator no-op silencioso + falta de extração por processo):
  - **Backend:** `POST /api/v1/processes/{id}/extract` enfileira por
    documento: `workers.run_agent("extrator")` quando há
    `extracted_text` cacheado (com `force=true` opcional pra re-OCR);
    `workers.ocr_then_extract` (chain OCR→extrator) quando o texto
    falta. Resposta separa `jobs` × `pending_ocr`; AuditLog
    `extractor_dispatched` rastreia o disparo. **404** sem docs.
  - **`ExtratorAgent` agora orienta:** sem `document_id`/`text`, o
    `reason` aponta pros 3 caminhos (incluindo o endpoint novo); com
    `document_id` mas `extracted_text` NULL, o `ValueError` diz "OCR
    ainda não rodou — use POST /processes/{id}/extract" em vez do
    críptico "texto extraido".
  - **UI consultor:** card do `extrator` em `/agents` mostra **"Rodar
    no processo #N"** (disabled sem ID — sem mais no-op silencioso).
    Step 4 do `IntakeWizard` **trava avanço** se há docs anexados sem
    "Ler documentos com IA" disparado. `DraftDocumentUploader` ganha
    botão 🗑 por linha (habilitado pra `ocr_status` em `{null,
    pending}`) — exclui antes da IA processar. Doc já processado
    continua removível pela aba Documentos do processo.
  - **Sem migration. Sem ADR.** Reuso de `ocr_then_extract`,
    `run_agent`, `ProcessRepository.add_audit`, `DELETE
    /documents/{id}`. 9 testes em `tests/api/test_processes.py` (3
    novos) + 4 em `tests/agents/test_extrator_cache.py` (1 novo) verde.
    Frontend tsc/build verde.
- **Pipeline ponta a ponta no nível de código + UI:** `extrator → auditor_imovel
  → legislacao → diagnostico → POST /diagnoses (versionado + gate Pydantic) →
  consultor adjudica status_achado e decide alerta por alerta (aba Alertas) →
  consultor assina (DiagnosisAssinatura — gate camada 2 cross-entidades + AuditLog,
  excluindo só achados descartados/resolvidos — PROMPT_10/11)`.
  Princípio 1 fechado em UI também — **a IA propõe, o consultor decide e assina,
  alerta por alerta.**
- **`fix/diagnostico-propaga-estado` em revisão (2026-05-28, logo após PR #15)**
  — fecha o sintoma "card discorda do diagnóstico assinado" e abre a dívida
  **#26** (unificação `Process.status` × `Process.macroetapa` para o eixo 3):
  - **`compute_macroetapa_state`** e **`can_advance_macroetapa`** ganham os
    kwargs `current_macroetapa` + `diagnosis_validated`. Etapa de diagnóstico
    com checklist 100% mas sem `RegulatoryDiagnosis.validated_at` agora
    devolve `aguardando_validacao` (badge passa a concordar com o bloco
    "diagnóstico assinado"); o gate de saída de `diagnostico_preliminar` /
    `diagnostico_tecnico` cobra `validated_at` preenchido.
  - **`PATCH /processes/{id}/diagnoses/{version}/validate`** chama
    `advance_macroetapa` automaticamente quando o gate passa — mesmo
    critério do botão "Avançar" manual: docs obrigatórios + checklist 100%
    + agora a assinatura. Quando o gate trava, o `validated_at` ainda é
    gravado; só a transição de etapa fica suspensa.
  - **Conservador por desenho:** NÃO toca `Process.status`, nem consolida
    as duas chains, nem mexe nas 4 tabelas denormalizadas. A unificação
    propriamente dita virou a dívida **#26** (eixo 3 — PR3-agressivo,
    isolado, com migration própria).
  - **Kanban (`processes.py`)** executa uma única query agregada por
    `tenant_id` para carregar o set de `process_id` com diagnóstico
    assinado — evita N+1 na listagem.
  - 4 testes unitários (`tests/models/test_macroetapa_gate.py`) + 3 de
    API (`TestValidateAdvancesMacroetapa`). Sem migration.
- **Eixo 2 workflow por tipo — ajuste pontual em 2026-05-29:** RAG vetorial do
  `LegislacaoAgent` agora filtra `demand_type` de forma estruturada via
  `LegislationDocument.demand_types`; `WorkflowEngine` levanta
  `TemplateNotFoundError` e API devolve 422 quando não existe template ativo;
  `DemandType` ganhou `sobreposicao`, `supressao`, `due_diligence`,
  `arrendamento`, `condicionantes_antigas`. Relatório:
  `docs/arquivo/auditorias/2026-05-28_cobertura_templates.md`.
- **Frente D (cripto de segredos) fechada em 2026-05-28** — [ADR-014](../adr/014-cripto-segredos-usuario.md):
  padrão Fernet (AES-128-CBC + HMAC-SHA256) para segredos de terceiros no banco
  (white label LLM + credenciais de portal). Entregue: `app/core/encryption.py`
  (`get_fernet`/`encrypt_str`/`decrypt_str` com MultiFernet pra rotação), type decorator
  `EncryptedString` (`app/models/types.py`), `CREDENTIAL_ENCRYPTION_KEY` obrigatória (falha no
  startup, sem fallback inseguro, separada do `SECRET_KEY`), `tools/gen_encryption_key.py`.
  8 testes verdes. **Nenhuma coluna real alterada** — aplicação fica para a PR `Credential`
  (PR 2.3) e a PR LLM (dívida #27). Infraestrutura, não feature de usuário.

**O que está congelado:**

- Portal do cliente (`client-portal/`, Next.js 16) — ver [`../adr/009-mobile-clientportal-congelados.md`](../adr/009-mobile-clientportal-congelados.md)
- App de campo (`mobile/`, Expo) — idem

**O que está em transição:**

- Renomeação Amigão → Regente: rebrand interno feito (`PROJECT_NAME`, docstrings); 8 contratos
  externos (`X-Amigao-*` headers em `alerts.py` + crawlers User-Agent) pendentes — coordenação
  com consumidores antes (dívida #13).
- **Remodelagem do `RegulatoryIssue`** (família + codigo_alerta + 4 níveis) — próxima rodada
  (PROMPT_5), aguardando validação da skill `auditor_imovel/analise_divergencias_documentais`
  pela sócia.

## Backend

### Agentes ativos (11)

| Agente | Arquivo | Status A2 | Custo médio observado |
|---|---|---|---|
| atendimento | `app/agents/atendimento.py` | dict legado | baixo (4 execuções) |
| extrator | `app/agents/extrator.py` | dict legado | 51 execuções históricas — mais usado |
| diagnostico | `app/agents/diagnostico.py` | ✅ A2+A3 (DiagnosticoPreliminarContent + citation_evaluator) | $0.0002 smoke |
| legislacao | `app/agents/legislacao.py` | ✅ A2 (EnquadramentoRegulatorioContent) | $0.0047 acumulado (Gemini 2.0 Flash) |
| redator | `app/agents/redator.py` | ✅ A2 (PecaJuridicaContent) | $0.0030 smoke 7 templates |
| auditor_imovel | `app/agents/auditor_imovel.py` | ✅ A2-Fase2 (deterministic tools, sem LLM) | $0 — cruzamento via `app/services/property_audit.py` |
| orcamento | `app/agents/orcamento.py` | dict legado | baixo |
| financeiro | `app/agents/financeiro.py` | dict legado | baixo |
| acompanhamento | `app/agents/acompanhamento.py` | dict legado | 1 execução |
| vigia | `app/agents/vigia.py` | rules-based (sem LLM) | $0 |
| marketing | `app/agents/marketing.py` | dict legado | baixo |

### Chains de orquestração (9)

Definidas em `app/agents/orchestrator.py:CHAINS`: `intake`, `diagnostico_completo`, `gerar_proposta`, `gerar_documento`, `analise_regulatoria`, `enquadramento_regulatorio`, `analise_financeira`, `monitoramento`, `marketing_content`. Chain principal: `diagnostico_completo` (extrator → auditor_imovel → legislacao → diagnostico).

### Models SQLAlchemy (28 entidades)

Tabelas principais: `tenants`, `users`, `clients`, `properties`, `processes`, `tasks`, `documents`, `communications`, `proposals`, `contracts`, `ai_jobs`, `audit_logs`, `prompt_templates`, `intake_drafts`, `regulatory_diagnosis`, `regulatory_issues`, `knowledge_catalog`, `legislation_documents`, `pre_cadastros`, `intake_classification_feedback`, etc.

### Routers REST (27 + 1 WebSocket)

Ver `app/main.py:135-161`. Áreas: auth, clientes, processos, documentos, propriedades, tarefas, threads, intake, intake-feedback, checklists, workflows, dossier, decisions, regulatory, proposals, contracts, ai, agents, dashboard, legislation, legislation_alerts, knowledge, waitlist.

**Endpoints regulatórios (2026-05-25):**
- `GET   /api/v1/processes/{id}/diagnoses` — lista versões (mais nova primeiro)
- `GET   /api/v1/processes/{id}/diagnoses/{version}` — versão específica
- `POST  /api/v1/processes/{id}/diagnoses` — cria versão nova (gate A4 Pydantic↔JSONB)
- `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` — **(PROMPT_4 Onda B)** consultor assina; AuditLog hash chain; 409 se já validado
- `GET   /api/v1/properties/{id}/issues?status=open|resolved|all` — issues do imóvel

### Migrations Alembic

39 migrations aplicadas em produção. Convenção: `<8-hex>_sprint_<X>_<descricao>.py`.

## Corpus regulatório (RAG)

| UF | Chunks indexados | Provider de embedding |
|---|---|---|
| Federal | 720 | OpenAI `text-embedding-3-small` (migração de Gemini concluída) |
| GO | 3.855 | idem |
| MS | 4.587 | idem |
| MT | 13.411 | idem |
| GO — SEMAD operacional | 1.194 | Gemini Flash classify + OpenAI 768d (PR #24, 30/05) |
| **Total** | **23.767** | — |

Corpus SEMAD operacional (PR #24): 282/283 PDFs, 4 source types novos (`norma_procedural`/`matriz_ipe`/`manual_ipe`/`gabarito_laudo`). 1 PDF pendente de OCR (dívida #28). Detalhe em `docs/arquitetura/BASE_REGULATORIA.md`.

Próximos estados na fila: SP, MG, TO (próxima semana).

## Frontend (painel consultor)

- React 19 + Vite + TypeScript + TailwindCSS + React Query + Zustand
- 37+ telas/abas em 10 áreas (Auth, Clients, Processes, Properties, Intake, Contracts, Proposals, Dashboard, AI, Settings)
  - **PROMPT_9:** aba **Alertas** nova no ProcessDetail (Regra B preventiva + 5 botões da P4 + textarea de justificativa); **AnalysesTab** do PropertyHub agora é lente do ADR-012 com chips verbo-por-estado.
  - **Sidebar (2026-06-28):** item único **"Quadro de ações" → `/processes`** (revertido o rename "Casos" + a aba global `/acoes` do #74; `QuadroAcoesGlobal` deletado). Aba "Ações" do workspace (`AcoesTab`) e backend Ficha 07 preservados — ver `docs/trabalhos/reverter_sidebar.md`.
- TypeScript strict, zero `any` explícito, mutations uniformizadas via async/await
- Token em Zustand persist + interceptor de 401/403 em `frontend/src/lib/api.ts`
- **Vitest+RTL:** 31/31 verde (4 testes pré-existentes + 10 do PROMPT_9 em `AlertaCard.test.tsx` e `DiagnosisAssinatura.test.tsx`). Runner `frontend/scripts/run-vitest.mjs` injeta `NODE_OPTIONS=--experimental-require-module` (workaround pro jsdom 27 + Node 22.11).

## Testes

- 42+ arquivos de teste em `tests/`
- Testcontainers PostgreSQL+PostGIS (function-scoped session em transação rollback)
- pytest + pytest-cov, `fail_under=70` em coverage
- **Estado verde após PROMPT_4:** **585 passed, 0 failed** (vs 562 antes da rodada — +23 testes:
  15 do `test_diagnostico_consume_auditor.py` + 8 do `TestValidateDiagnosis` em `test_regulatory.py`).
- 4 falhas pré-existentes em main resolvidas na Onda A do PROMPT_3 (24/05) — não há mais falhas
  pré-existentes mascarando o estado.
- **Pulso 2026-05-30 (`fix/pr2.2-fechar-testes` — fecha pendência (a) do PR 2.2):** rodada dos
  testes integrados do motor de workflow contra o banco dev ativo (Docker up, `db` healthy
  na 55432). `test_workflow_engine.py` + `test_regulatory.py` + `test_workflows.py`: **23 passed,
  0 failed**; `test_legislacao_a2.py`: **19 passed**. Total **42 passed, 0 failed, 0 skipped**
  (2 warnings de teardown de transação, infra de teste). Divergências do prompt registradas:
  (1) `tests/api/test_legislacao.py` não existe no repo — não rodado; (2) não há marker
  `pytest.mark.integration` na suíte, então `-m integration` deselecionava tudo — os arquivos
  foram rodados diretamente (eles *são* os testes integrados via Testcontainers).
- **Pulso 2026-05-30 (`feat/intake-campos-backend` — campos derivados do intake, decisões Isis,
  PR 1 de 2):** e-mail obrigatório no contato (422 se vazio); 3 famílias de schema (`ManualFields`/
  `ExtractedFields`/`TriagemFields`); 2 endpoints novos no draft (`GET .../extracted-fields` preview,
  `POST .../reconcile` Opção A → `field_sources`); `audio_url` aceito; regra `prad` no classifier
  (16/16 demand_types classificáveis). **25 testes novos verdes** (`test_intake.py` + 18 do
  `test_intake_classifier.py`), 14 pré-existentes sem regressão. Frontend (PreviewPanel/Reconcile/
  PriorityStep) + docs de agente/UX = **PR 2 (follow-up)**. Validação com a Isis pendente.
- **Pulso 2026-05-30 (`feat/intake-ux-frontend` — PR 2 de 2):** `IntakeWizard` em 2 colunas com
  `PreviewPanel` (polling do `extracted-fields`, badges de confiança, divergência → `ReconcileModal`
  Opção A) + `PriorityStep` (2 eixos: urgência 4 / valor estratégico 3) + áudio da entrevista
  anexável. `npx tsc --noEmit` limpo. `npm run build`/Vitest não rodam neste ambiente (node_modules
  sem dev-deps — `vite`/`@types/node`/`vitest`; pré-existente). Validação fim-a-fim com a Isis pendente.
- **Pulso 2026-05-30 (`feat/llm-provider-por-consultor` — white label):** consultor traz a própria
  chave de LLM (anthropic/google/openai/deepseek). Schema `AiPreferences` + service que cifra a chave
  (`api_key_encrypted` no JSONB, ADR-014, nunca plaintext) + `GET .../ai/available-models` +
  `ai_gateway.complete(user_preferences=...)` (sem fallback global em erro de auth) +
  `BaseAgent.call_llm` via `ctx.user_id` + UI na aba Settings > IA. **28 testes verdes** (incl.
  verificação SQL de cripto); `tsc --noEmit` limpo. Fecha parcialmente a dívida #27; abre #30
  (auditoria de uso por chave). Validação com o André pendente.
- **Pulso 2026-05-30 (`feat/credenciais-portal` — PR 2.3, cofre de credenciais):** modelo `Credential`
  (tabela `credentials`) com `password_encrypted` usando `EncryptedString` — **1º uso real em coluna**
  (fecha #27). CRUD tenant-scoped em `/api/v1/credentials` (senha cifrada, nunca plaintext na API,
  AuditLog hash chain). Migration `c0d1e2f3a4b5` também **reunificou 2 heads divergentes do Alembic**
  (bug pré-existente que quebrava `alembic upgrade head`). **6 testes verdes** (incl. SQL de cripto +
  isolamento de tenant). UI no Client Hub = follow-up; auditoria de leitura de campo sensível segue aberta.
- **Pulso 2026-05-30 (`docs/sistema-agentico-no-repo` — quitação documental, doc-only):** criados
  `docs/agentes/` com `ECOSSISTEMA_AGENTICO.md` (mestre) + sister files `EXTRATOR`/`LEGISLACAO`/
  `ATENDIMENTO`, `docs/MEMORIA_CHAT.md` e a auditoria de leitura sensível — **tudo verificado contra
  o código** (a doc anterior tinha alegações fabricadas). Achado: `AuditLog` cobre escrita, não uso
  de segredo decifrado → dívida **#33**. Dívida **#32** (8 sister files restantes). Whisper/transcrição
  documentada como frente futura (não construída).
- **Pulso 2026-05-31 (`docs/sister-files-agentes` — quita #32, doc-only):** criados os 8 sister files
  restantes (`DIAGNOSTICO`, `AUDITOR_IMOVEL`, `ORCAMENTO`, `FINANCEIRO`, `REDATOR`, `ACOMPANHAMENTO`,
  `VIGIA`, `MARKETING`), verificados contra o código real → **os 11 agentes têm sister file**. A
  verificação corrigiu uma alegação errada do mestre (`diagnostico` `requires_review`: "não" → **sim**,
  `diagnostico.py:448`) e registrou divergências docstring×código na seção 10 de cada sister file.
  **Dívida #32 FECHADA.**
- **Pulso 2026-05-31 (`feat/divida-33-audit-uso-api-key` — código):** a `api_key` do consultor
  (white label) passou a ser auditada no uso: `BaseAgent.call_llm` emite `AuditLog`
  `action="ai_key_used"` (hash chain) por execução, chave mascarada, best-effort
  (`emit_ai_key_use_event`). 5 testes novos; **199 verdes** sem regressão. **Dívida #33 parcialmente
  fechada** (resta a senha de portal, sem consumidor hoje). Também registrada a **dívida #34** (duas
  trilhas de orçamento desalinhadas).
- **Pulso 2026-05-31 (`feat/divida-18-verify-audit-chain` — código):** a hash chain de `AuditLog`
  ganhou verificador: `verify_audit_chain(db, tenant_id)` recomputa conteúdo + elo de cada registro e
  `GET /api/v1/admin/audit/verify-chain` (superusuário, read-only) expõe os elos quebrados. 10 testes
  novos. **Dívida #18 FECHADA** — auditabilidade deixa de ser cerimônia. Fecha também o item 3 da
  auditoria de leitura sensível (30/05).
- **Pulso 2026-05-31 (`feat/whatsapp-email-inbound-canal` — PR 2.1, código+infra):** canal **WhatsApp
  inbound a caso já aberto** (inbound NÃO cria caso). `POST /messaging/whatsapp/webhook` (HMAC) →
  identifica `Client` por telefone → `Message` no thread do caso aberto; mídia → `Document`; sem caso →
  thread órfão + alerta; sem Client → ignora. Provider plugável (`EvolutionProvider` real, `ZAPIProvider`
  stub). `CommunicationThread.provider`/`provider_account_id` (migration `pr21_wa_provider`). Serviço
  `evolution` no docker-compose (profile `whatsapp`). **13 testes novos.** **DORMENTE** até creds no
  `.env`. E-mail inbound (Resend) adiado → **dívida #35**.

- **Pulso 2026-05-31 (`fix/intake-uploads-criticos-isis` — 2 críticos da Isis):** **#2 (persistência):**
  `POST /intake/create-case` passou a aceitar `draft_id` e migra os `Document`s do rascunho
  (`process_id` NULL → processo) com `auto_link` no checklist, em uma transação (404 draft inexistente/
  outro tenant; 409 já finalizado; no-op sem docs). `/commit` deprecated (mantido). Antes os docs do
  Step 4 ficavam órfãos do processo. **#1 (upload em massa):** `DraftDocumentUploader` reescrito — pool
  de 4 simultâneos, retry 3× com backoff 1/2/4s, timeout backend 20s→30s, **botão remover sempre
  visível**, feedback por item + "tentar novamente" individual; visual migrado pros tokens do design
  system. **Testes:** 6 backend (migração) + 5 frontend (uploader); build/tsc/vitest verdes.
- **Pulso 2026-05-31 (`feat/ui-credenciais-cliente-hub` — UI):** aba **Credenciais** no Cliente Hub,
  com listagem, empty/loading/error, modal create/edit e confirmação de exclusão contra
  `/api/v1/credentials`. Respeita a decisão de produto: senha nunca volta/é revelada; `has_password`
  vira badge visual; PATCH sem senha preserva a senha. Testes focados do componente: **4/4 verdes**;
  `npm run build` verde. Docker/compose e verificação SQL manual ficaram bloqueados pelo ambiente
  local (`docker ps` sem acesso ao pipe; `EVOLUTION_API_KEY` ausente no compose).

## Infraestrutura

- Docker Compose com serviços: db (Postgres+PostGIS+pgvector), redis, minio, api, worker, client-portal (congelado)
- Variáveis de ambiente em `.env.example` (40+ variáveis)
- Métricas Prometheus em `/metrics`
- Health check em `/health`
- OpenAPI em `/docs`

## Sprints concluídas (últimas 6)

| Sprint | Conteúdo | Status |
|---|---|---|
| Sprint -1 (faxina) | Cost cap, filtro demand_type, cache OCR, MemPalace stub | ✅ |
| Sprint 0 (ingestão) | Corpus federal+GO+MS+MT no `knowledge_catalog` | ✅ |
| Sprint U (RAG) | pgvector instalado, busca semântica, embeddings | ✅ |
| Sprint A1 (infra) | `app/skills/`, `StageOutputContent`, RegulatoryDiagnosis, CitationEvaluator | ✅ |
| Sprint A2-redator | RedatorAgent emite `PecaJuridicaContent` (7 templates) | ✅ |
| Sprint A2-diagnostico | DiagnosticoAgent emite `DiagnosticoPreliminarContent` | ✅ |
| Sprint A2-legislacao | LegislacaoAgent emite `EnquadramentoRegulatorioContent` (18 testes A2) | ✅ |
| Fase 0 (auditoria skill) | Skill `situacao_ambiental_imovel_rural` posicionada + ADR-010 + mapa de gaps | ✅ commit `7877652` |
| Fase 2 Onda 1 — A4 (schema) | Risco estendido (8+1), Divergencia, NotificacaoItem, dual-emit, validate_diagnostic_content | ✅ commit `43ac9d5` |
| Fase 2 Onda 1 — K3 (RAG) | 9 normas-chave ingeridas + reindex (466 chunks novos) | ✅ commit `92f6376` |
| Fase 2 Onda 2 — A3 (citation) | citation_evaluator no DiagnosticoAgent (espelha RedatorAgent) | ✅ commit `5c4dd33` |
| Fase 2 Onda 2 — A2 (auditor) | AuditorImovelAgent + property_audit determinístico | ✅ commit `1830e70` |
| Pós-Fase 2 (Ondas A/B/C — PROMPT_3) | 4 fixes pré-existentes + `auditor_imovel` na chain + `POST /diagnoses` + régua 4 faixas | ✅ commits `357993c` + `5e64db4` (mergeado em main) |
| PROMPT_4 — fechar pipeline | Diagnóstico consome auditor + `PATCH /validate` (camada 1 do Princípio 1) | ✅ commits `f93b4b4` + `c74ff2e` (PR aberto, pendente de merge) |
| Upstash polling redução | `polling_interval=5.0`, `vigia 6h→12h`, `acompanhamento 30min→2h` (-85% de comandos Redis) | ✅ commit `a746eb0` (PR #2 mergeado, `bc98c93`) |
| Matriz calibração (caso real #11) | Área 2 níveis + RAT, pendências por tema (categoria+detalhamento), SIGEF código/status real, dedup; medido no dump de produção do São Jorge | ✅ `fix/matriz-calibracao-caso-real` — ver `docs/trabalhos/matriz_calibracao.md` |
| Hardening pós-deploy | Migration automática no deploy (`preDeployCommand` na API); erro de disparo visível na UI (rota `/extract` existe); retry só p/ transitório (determinístico falha sem retry) | ✅ `fix/hardening-deploy-rotas` — ver `docs/trabalhos/hardening_deploy.md` |
| Fase 2 robusta (docs reais) | Classificação por identidade (certidão 6776 não cai mais em sigef); validadores de formato por campo (4b); dedup de re-extração (4c); chain reutiliza staging (fim do "0 campos"). Follow-on: OCR falho em CCIR/ITR/recibo CAR | ✅ `feat/fase2-robusta-docs-reais` — ver `docs/trabalhos/fase2_robusta.md` |
| OCR failed (docs reais) | Causa medida: falha de download do storage (05-31, pré-fix R2), nunca reprocessada. Fixes: reprocesso `/documents/{id}/reprocess-ocr` (draft+processo) + botão; coluna `ocr_error` (fim do failed silencioso); fim do "preso em processing"; docx honesto. Validação real do failed→done é pós-deploy (consultor reprocessa) | ✅ `fix/ocr-failed-docs-reais` — ver `docs/trabalhos/ocr_failed.md` |
| Rastreabilidade (P1 — nenhuma afirmação sem fonte) | Princípio 11 no manifesto; `SourceRef`/`Afirmacao` comuns; matriz `fontes_detalhe` (doc+valor por linha) + UI; diagnóstico `afirmacoes` com fonte/"sem fonte"; legislação `prazo_fonte` (estimativa marcada) + trechos RAG. Aditivo. Validação LLM pós-deploy | ✅ `feat/rastreabilidade-fontes` — ver `docs/trabalhos/rastreabilidade.md` |
| Parse BR + Consolidação Ficha 05 + rastreabilidade total (Isis 16/06) | **(1)** `parse_area_ha` porta única (BR/US/m²/dict, último separador = decimal) + `is_area_plausible` + defesa relativa na matriz — mata falso passivo "1.010,7113→1,01"; **(2)** consolidação Ficha 05 (multi-fonte→âncora SIGEF, upsert versionado + audit por campo, reconciliação, achado não grava) + Imóvel Hub deriva Matrícula/Área das matrículas (fim dos "—"); **(3)** diagnóstico 100% dos passivos com fonte. Bug `decide_field` (achado gravava valor) corrigido. Aditivo; validação LLM E2E pós-deploy | ✅ `fix/parse-br-consolidacao-rastreabilidade` — ver `docs/trabalhos/parse_consolidacao.md` |

## Sprints em curso

| Sprint | Conteúdo | Estado |
|---|---|---|
| Waitlist | Endpoint público + Resend + drip educativo | PR 2 mergeado, PR 3 pendente |
| Governança documental | Mover/arquivar docs conforme `GOVERNANCA_DOCUMENTAL.md`; capturar duráveis | Em curso (esta rodada) |

## Pendências críticas

| Item | Bloqueio | Janela |
|---|---|---|
| Reprocessar OCR dos failed do São Jorge (prod) | Fix shipado (`fix/ocr-failed-docs-reais`): há botão "↻ tentar de novo" + endpoint. **Falta o consultor reprocessar em prod** os CCIR/ITR/recibo CAR e confirmar failed→done → então a matriz multi-fonte fica completa. Ver `docs/trabalhos/ocr_failed.md` | Curto (pós-deploy) |
| Remodelagem `RegulatoryIssue` (dívida #3) | PROMPT_5 — aguarda sócia validar skill `auditor_imovel/analise_divergencias_documentais` | Próxima rodada |
| Camada 2 do Princípio 1 (5 botões P4) | Depende da remodelagem do `RegulatoryIssue` + reconciliação de status (dívida #5) | Pós-PROMPT_5 |
| UI consultor-assina (frontend do `PATCH /validate`) | Endpoint pronto desde PROMPT_4; frontend precisa consumir e renderizar | Curto |
| Extração Fase 2 incompleta (caso #11) | Certidão/CCIR/ITR/CAR não viraram `extracted_field_staging` (OCR `pending`/classificação `document_type`); staging triplicado sem dedup. (`area_vetorizada_ha` mal-parseada já resolvida em `fix/parse-br-consolidacao-rastreabilidade` — porta única `parse_area_ha`.) Upstream da matriz — destrava denominação 3-variações e área por matrícula. Ver `docs/trabalhos/matriz_calibracao.md` §5 | Curto |
| Property.geom populado | Falta parser shapefile + ingestão de KML/SHP — destrava alertas geoespaciais (dívidas #14/#15) | Médio |
| Crawlers DOU/DOE ativados em prod | Apenas esqueleto pronto | Médio |
| Connector e-mail inbound (acompanhamento) | Sem integração de inbound hoje | Médio |
| R1 polish dos 8 contratos externos (dívida #13) | Headers `X-Amigao-*` em `alerts.py` + crawlers User-Agent — quebra webhook + allowlists SEMAs; coordenar antes | Médio |
| Hardening de produção (secrets, CORS, Swagger desabilitado) | Checklist em `ops/production-secrets-checklist.md` | Curto |
| State-leakage entre testes em suite (29 fails que passam isolados) | Pytest e2e desbloqueado em 17/05 (`0e17ebd`). Sprint dedicada: fixture `autouse=True` resetando `slowapi.Limiter._storage` + auditar testes que committam manualmente. Não bloqueia deploy. | Curto |

## Próximos marcos

- **PROMPT_5 — remodelar `RegulatoryIssue`**: `familia` (enum estável) + `codigo_alerta`
  (catálogo evolutivo) + 4 níveis em severity. Pré-requisito: skill da sócia validada.
- **Camada 2 do Princípio 1** (5 botões P4) — após reconciliação de status (PROMPT_5 Onda C
  só **propõe**).
- **UI do consultor-assina** — frontend consome `PATCH /validate`.
- **Property.geom + parser shapefile** (D1) — destrava overlay PostGIS para
  `auditor_imovel` (sobreposição com APP/UC/terceiros).

## Métricas operacionais

(Esta seção precisa ser preenchida com query SQL real do banco de produção. Marcador para próxima atualização.)

- Clientes cadastrados: a apurar
- Processos abertos: a apurar
- Documentos extraídos: a apurar
- AI Jobs (últimos 30 dias): a apurar
- Custo total IA (últimos 30 dias): a apurar
- Tenant ativo: 1 (sócia)
