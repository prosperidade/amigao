# Registro de dívidas — Regente (consolidado pós-PROMPT_11 · 2026-05-26)

Reúne num lugar só as dívidas que estavam espalhadas por relatórios do agente, rodapés de skill,
memórias do desenvolvedor e análises de coordenação. Ordenadas por prioridade de desbloqueio.
Cada item: o que é, de onde veio, o que destrava, e o estado.

> **Convenção de governança:** este documento é VIVO (`docs/REGISTRO_DIVIDAS.md`) — atualizado ao
> fim de cada sprint. Itens fechados saem para a seção "Fechadas (histórico)" abaixo; não somem.
> Ver `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.

## P0 — fecham o pipeline ponta a ponta

*Nenhuma aberta nesta camada — as duas que estavam (#1 e #2) foram fechadas pelo PROMPT_4.
Pipeline ponta-a-ponta no nível de código: auditor cruza → diagnóstico consome → grava
versionado → consultor assina.*

## P1 — (esvaziada após PROMPT_7)

*A re-modelagem do ADR-012 (dívida #20) foi implementada nesta rodada. Ver
tabela "Fechadas (histórico)" abaixo.*

## P2 — (esvaziada após PROMPT_8)

*A coerência entre os status (dívida #17) foi implementada nesta rodada
via 2 regras: helper `assert_status_coerente` sobre estado resultante no
PATCH `/issues` + bloqueio do PUT `/decision` quando achado em `suspeita`
(`assert_decisao_permitida`). Sem máquina de estados completa — barrou só
o absurdo óbvio. Ver tabela "Fechadas" abaixo.*

## P2 — produto/domínio (precisam da sócia)

**6. Conjunto canônico de documentos esperados** (para `DOCUMENTO_AUSENTE`). A régua de
área não gera finding quando um lado é `None`; falta definir quais documentos são essenciais
por tipo de caso. Conecta com a planilha de checklist 1.2.1 da sócia. **Origem:** Onda C
(24/05).

**7. Marcador de aplicação de citação** (`confirmada`/`aplicacao_preliminar`/
`hipotese_a_confirmar`) no `EnquadramentoRegulatorioContent` do Legislação. Distinto da
validação de existência (o `citation_evaluator`, que não muda). **Origem:** P3.

**8. Tool determinística de cálculo de uso do solo** — função Python, não LLM. Fórmula por
**período × localização jurídica** (ver "Regime de compensação por supressão em GO" na
skill de Diagnóstico). Pós-contrato. **Origem:** skill de Diagnóstico (gabarito Romilton).

**29. Critério do "Valor Estratégico — nível Baixo" não definido.** Na triagem do intake,
o eixo `valor_estrategico` tem 3 níveis (alto/médio/baixo). Para o nível **baixo**, a Isis
respondeu "não sei responder" — é label sem régua escrita; hoje o consultor decide livre.
Validar o critério na tela quando a Isis testar o wizard. **Proibido** implementar critério
agora (decisão pendente da sócia). **Origem:** PR intake campos derivados (30/05).

**21. Criar WorkflowTemplate para demand_types sem cobertura.** Auditoria de cobertura
em `docs/arquivo/auditorias/2026-05-28_cobertura_templates.md` aponta ausência de
template ativo para: `prad`, `sobreposicao`, `supressao`, `due_diligence`,
`arrendamento`, `condicionantes_antigas`, `misto`, `nao_identificado`. **Origem:**
Eixo 2 workflow por tipo (29/05). **Nota:** a rodada atual proibiu criar templates;
ficou apenas o erro explícito e o relatório. **Confirmada por rodada real
(2026-05-30, `fix/pr2.2-fechar-testes`):** script rodou contra o banco dev ativo e
reproduziu exatamente esses 8 gaps de template. Adicionalmente, mediu os gaps de base
regulatória (`LegislationDocument` com 0 documentos): `exigencia_bancaria`,
`sobreposicao`, `supressao`, `due_diligence`, `arrendamento`, `condicionantes_antigas`,
`misto`, `nao_identificado` — os 8 sem template (exceto `prad`, que tem 2 docs) + `exigencia_bancaria`.

## P3 — robustez e higiene (sem urgência, sem risco externo)

**9. `except Exception` genérico no `pdf_generator.py:234`** devolve `{"error": str(e)}` sem
`status` — engole qualquer erro. O logo foi só o gatilho (resolvido na Onda A do PROMPT_3);
o tratamento de erro continua frágil. **Origem:** Onda A (24/05).

**10. Testes que dependem de storage externo sem mock.** O `test_pdf_generator` não era o
único caso latente provável. Varredura quando der folga. **Origem:** Onda A (24/05).

**11. Race no versionamento `MAX(version)+1`** — capturado por `UniqueConstraint`, mas
devolve 500 + retry manual. Tratar com retry server-side. Improvável para consultor único.
**Origem:** Onda B (24/05).

**28. OCR do PDF SEMAD pendente.** A ingestão do corpus SEMAD (PR #24) indexou 282/283 PDFs;
`ON_01_2021_SEMAD - Errata.pdf` é escaneado e ficou de fora (sem camada de texto). Rodar pelo
pipeline OCR existente (`docs/arquitetura/PIPELINE_OCR.md`) e reingerir o único documento.
Baixo impacto (1 errata). **Origem:** corpus SEMAD (30/05).

**31. Histórico do git carrega 254 MB de corpus SEMAD removido.** A PR #31 tirou
`docs/base_regulatoria/` do HEAD (destravou o `git clone` do Render — ver `TROUBLESHOOTING`
categoria 8), mas os blobs seguem no histórico, então todo `git clone` ainda baixa ~254 MB.
Enxugar exige reescrita de histórico (`git filter-repo` + `push --force`) — **invasivo**:
reescreve SHAs e quebra os worktrees/branches ativos de outros trabalhos. Fazer em janela
dedicada, combinada com o Andre, com todos os worktrees fechados. **Origem:** fix deploy
Render (30/05).

## Bloqueada por terceiros / coordenação (NÃO tocar sozinho)

**13. R1 — contratos externos.** Headers `X-Amigao-*` em `alerts.py`, `User-Agent` dos
crawlers. Risco de quebrar webhook receiver e allowlists de SEMAs. **Coordenar com os
consumidores antes.**

## Aguardando infraestrutura (D1 = `Property.geom`)

**14. Sobreposição e alertas geoespaciais** (🛰️ na skill do auditor): CAR deslocado,
polígono deslocado, sobreposição com terceiro, confrontantes, datum/fuso, RL × realidade,
APP, supressão, restrição territorial. O helper `grade_overlap_severity()` já está
preparado sem chamador; pluga direto quando o `geom` existir.

**15.** Alertas de consulta externa (🔌): embargo (IBAMA), auto de infração,
licença/outorga — aguardam integração.

**27. Aplicar `EncryptedString` em colunas reais.** A infraestrutura de cripto de
segredos (Fernet + `EncryptedString` + `CREDENTIAL_ENCRYPTION_KEY`) foi entregue pela
Frente D ([ADR-014](adr/014-cripto-segredos-usuario.md)), mas **nenhuma coluna real a usa
ainda**. Plugar quando a **PR 2.3** (`Credential` — logins de portal por cliente) e a
**PR LLM** (`User.preferences.ai.api_key` — chave de IA do consultor, white label)
entrarem. **Origem:** Frente D (28/05). **Parcialmente fechada (30/05, PR LLM):** a chave de
IA do consultor já é gravada criptografada — mas em `User.preferences['ai']['api_key_encrypted']`
(JSONB), via `encrypt_str`/`decrypt_str` no service (NÃO `EncryptedString`, que é só p/ coluna
String). Resta a **PR 2.3** (`Credential` — aí sim usa `EncryptedString` em coluna real).
**✅ FECHADA (30/05, PR 2.3):** o modelo `Credential` (tabela `credentials`) usa `EncryptedString`
na coluna `password_encrypted` — primeiro uso real do type decorator em coluna de tabela. Cofre de
logins de portais por cliente (SEMA/IBAMA/SICAR/INCRA/banco). Ver tabela "Fechadas" abaixo.

**30. Auditoria de uso de IA por usuário/tenant (white label).** Com o consultor trazendo a
própria chave, falta rastrear gasto/tokens consumidos POR chave de consultor (hoje os limites de
custo — horário/mensal — são por tenant, e o cost cap por job não distingue chave do sistema vs
do consultor). Útil para billing/transparência quando o white label escalar. **Origem:** PR LLM (30/05).

## Backlog de produto (já versionado em ADR)

**16. Loop de aprendizado com material dos consultores** — ADR-010.

## Reveladas na revisão do PROMPT_6 (26/05)

*Régua de prioridade aplicada após classificação do Andre.*

### P3 — com marco condicional

**21. Pares de status semanticamente incoerentes fora das 2 regras do PROMPT_8.**
As 2 regras de `regulatory_coherence.py` foram desenhadas como "barrar o
absurdo óbvio" — escopo fechado, não máquina de estados completa. Sobram
pares teoricamente incoerentes que o sistema aceita por desenho:
`status_achado=resolvida` com `status_saneamento=pendente` (achado já
sanado mas saneamento ainda pendente); `descartada+pendente`,
`ignorada+pendente` e variações com `nao_aplicavel`/`descartado` no
saneamento sobre achados terminais. **Dimensionamento:** consultor não é
adversário (P2 da rodada, agora P3 do que sobrou) — não cria isso de
propósito; UI dos 5 botões pode até prevenir naturalmente pelo fluxo de
clique. **Marco para revisitar:** apenas se aparecer dado real bagunçando
o estado (ex.: import legado, regressão de UI deixando registros em
combinações fantasmas). Aí valeria considerar máquina de estados completa
ou regras adicionais. **Origem:** revisão pós-PROMPT_8 (26/05 — Andre
notou ao revisar o escopo).

**22. Workaround `--experimental-require-module` no runner do Vitest.**
Os primeiros testes de componente do frontend (PROMPT_9) usam jsdom 27,
que puxa `@asamuzakjp/css-color` (CJS) que `require()` `@csstools/css-calc`
(ESM). Node 22.11 só aceita isso com a flag experimental
`--experimental-require-module`. Como `poolOptions.execArgv` do Vitest não
propaga aos workers Tinypool, o workaround é o runner
`frontend/scripts/run-vitest.mjs` que injeta a flag via `NODE_OPTIONS`.
**Marco para remover:** quando o jsdom corrigir a dep CJS/ESM upstream
**ou** quando o projeto subir pra Node 22.12+ (que ativou `require(esm)`
por default). Sem urgência — o runner é local, isolado e cross-platform.
**Origem:** PROMPT_9 (26/05).

**26. Unificação `Process.status` × `Process.macroetapa` (eixo 3 — PR3-agressivo).**
Hoje o sistema mantém duas máquinas de estado paralelas: o enum legado
`ProcessStatus` (em `app/models/process.py`) e o novo enum `Macroetapa`
(em `app/models/macroetapa.py`), conectados pelo dicionário fixo
`STATUS_TO_MACROETAPA`. Card do kanban lê `macroetapa`; outras telas e
endpoints legados ainda olham `status`; cada update precisa decidir qual
fonte respeitar. **Por que continua aberta:** o fix
`fix/diagnostico-propaga-estado` (PR atual) foi deliberadamente
conservador — só propaga o estado da assinatura para a `macroetapa` e
adiciona um gate em `can_advance_macroetapa`. A unificação propriamente
dita (eleger uma fonte única, migrar dados, ajustar as 4 tabelas
denormalizadas que carregam o status, podar `STATUS_TO_MACROETAPA`)
ficou para um PR3 agressivo, isolado, com migration própria. **Marco
para destravar:** quando alguma feature ou bug exigir resolver
divergências entre os dois eixos (e.g. relatório que mistura `status` e
`macroetapa`, regra de negócio que conflita por causa do mapeamento
fixo). **Origem:** PR `fix/diagnostico-propaga-estado` (2026-05-28).

**18. Hash chain de `AuditLog` sem rotina de verificação.**
`app/services/audit_hash.py` tem **só escritores** (`compute_audit_hash`,
`get_last_hash_for_tenant`, `stamp_audit_hash`) — não existe função que
percorra a cadeia de um tenant e detecte se algum elo foi quebrado.
Hash chain sem verificador é cerimônia. **Marco:** implementar **antes do
primeiro uso jurídico da trilha** (auditoria de órgão, disputa com banco,
contestação de decisão do consultor). Até lá, **não vender** "auditabilidade
garantida" como se o verificador existisse. **Resolver:** adicionar
`verify_audit_chain(db, tenant_id) -> list[BrokenLink]` que recomputa cada
hash em ordem e compara com o `hash_sha256` persistido; expor via endpoint
admin (read-only, auth restrita). **Origem:** revisão do PROMPT_6 (26/05).
**Nota:** dívida pré-existente (vem do A1).

---

## Fechadas (histórico — não revoga, só comprova fechamento)

| # | Item | Fechada em | Como |
|---|---|---|---|
| **1** | Diagnóstico não consome `chain_data["auditor_imovel"]` | 2026-05-25 (PROMPT_4 Onda A) | `_consume_auditor_findings()` em `app/agents/diagnostico.py` — findings viram `Divergencia` + `Risco` com `grau` 4-níveis preservado. Commit `f93b4b4`. |
| **2** | "Humano assina" — ciclo do Princípio 1 (camada 1) | 2026-05-25 (PROMPT_4 Onda B) | `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` grava `validated_by_user_id` + `validated_at` + AuditLog hash chain SHA-256. 409 ao revalidar. Commit `c74ff2e`. *(A camada 2 — 5 botões P4 — continua aberta, pós-PROMPT_5.)* |
| **3** | Remodelar `RegulatoryIssue` (família + codigo_alerta + 4 níveis) | 2026-05-25 (PROMPT_5 Onda A) | Enum `RegulatoryFamilia` (11 estável) + model `RegulatoryIssueCatalog` (PK = codigo_alerta string; catálogo evolutivo via INSERT, NÃO migration) + colunas `codigo_alerta`/`familia`/`muda_rota_regulatoria`/`muda_escopo_preco_prazo`/`documentos_cruzados` em `RegulatoryIssue`. `severity` passa para 4 níveis. Migration `c1b2d3e4f5a7` cria, popula 45 entradas seed (via `app/models/regulatory_catalog_seed.py`, fonte única) e migra dados antigos. `type` legado fica nullable (deprecated). |
| **4** | Mapeamento `grade` 4→`severity` 3 que colapsava alto+crítico | 2026-05-25 (PROMPT_5 Onda A) | `_GRADE_TO_SEVERITY` removido de `property_audit.py`. `AuditFinding.grade` e `RegulatoryIssue.severity` agora compartilham 4 níveis (`informativo`/`atencao`/`alto`/`critico`). Auditor emite codigos reais (📄) e grade direto; 🛰️/🔌 ficam no catálogo mas não emitidos até infra. Diagnóstico mapeia `familia` (11) → `RiscoCategoria` (7) via `_FAMILIA_TO_CATEGORIA` (substitui `_FINDING_TYPE_TO_CATEGORIA` do PROMPT_4). |
| **5** | Reconciliar `status_saneamento` × `status` do auditor × `decisao_consultor` (3 status circulantes) | 2026-05-26 (PROMPT_6 — Opção A do RECONCILIACAO_STATUS_ALERTAS) | 3 enums novos: `StatusAchado` (5 valores), `DecisaoConsultor` (os 5 botões P4), `StatusSaneamento` (5 valores). 5 colunas em `RegulatoryIssue`: `status_achado` (NOT NULL default `suspeita`), `decisao_consultor` (nullable), `decisao_consultor_justificativa`, `decisao_consultor_at`, `status_saneamento` (NOT NULL default `pendente`). PATCH `/properties/{prop}/issues/{id}` edita com AuditLog granular por campo. Gate no PATCH `/validate` rejeita 422 se houver crítica sem decisão (camada 2 do Princípio 1 fechada). Migration `d2c3e4f5a6b8`. |
| **Camada 2 P1** | 5 botões da P4 — decisão obrigatória por alerta crítico antes da assinatura | 2026-05-26 (PROMPT_6) | `decisao_consultor` enum com os 5 valores + gate no `PATCH /validate` retornando 422 com lista de pendentes. Frontend dos botões fica para rodada futura (UI consome `RegulatoryIssueOut` + PATCH). |
| **19** | Justificativa obrigatória para `ignorar_justificado` e `fora_escopo` (camada 2 completa) | 2026-05-26 (revisão pós-PROMPT_6) | `@model_validator` no `RegulatoryIssueUpdate` rejeita 422 quando `decisao_consultor in {ignorar_justificado, fora_escopo}` no body sem `justificativa` preenchida (str_strip cuida de strings só-espaços). Aplica APENAS quando `decisao_consultor` está no body — PATCH parcial que só toca outros campos não força re-confirmação. 5 testes em `TestUpdatePropertyIssueJustificativaObrigatoria`. PROMPT_7 migrou o validator para `ProcessIssueDecisionCreate` (mesma regra, schema novo). |
| **20** | Re-modelar `decisao_consultor` como entidade contextual ao processo (ADR-012) | 2026-05-26 (PROMPT_7) | Nova entidade `ProcessIssueDecision` (FK composta `(process_id, issue_id)` unique). Campos `decisao`/`justificativa`/`decided_at`/`decided_by_user_id` (renomeados em relação ao PROMPT_6; `decided_by_user_id` é novo). Migration `e3d4f5g6a7b8` cria tabela e dropa as 3 colunas do `RegulatoryIssue` (drop sem backfill — sem dados em prod). Endpoints novos: `GET` e `PUT /api/v1/processes/{pid}/issues/{iid}/decision` com upsert + AuditLog granular por campo (hash chain SHA-256). Gate `PATCH /validate` cruza issues críticas × `ProcessIssueDecision` deste processo. Validator de justificativa obrigatória migrou para o schema novo. Cada processo recomeça do zero (titularidade torta pesa diferente para venda e para crédito). `TestProcessIssueDecision` (11 testes novos) + `test_decisao_de_outro_processo_nao_libera_gate` confirma comportamento contextual. |
| **17** | Coerência entre os status reconciliados | 2026-05-26 (PROMPT_8) | Helper puro `app/services/regulatory_coherence.py` com 2 regras semânticas (escopo fechado, sem máquina de estados completa). **Regra A — perenes:** `assert_status_coerente(status_achado, status_saneamento)` exige `status_achado in {confirmada, resolvida}` quando `status_saneamento in {em_validacao, saneado}`. Aplicada (i) no `@model_validator` do `RegulatoryIssueUpdate` (fast-fail quando os 2 status vêm juntos no body) e (ii) no endpoint `PATCH /properties/.../issues/{id}` sobre o estado **resultante** (fonte da verdade — cobre PATCH parcial). **Regra B — cross-entidade:** `assert_decisao_permitida(status_achado)` rejeita `PUT /processes/.../decision` quando `status_achado == suspeita`. Mensagens de erro acionáveis: a primeira cita `confirmada`/`resolvida`, a segunda diz "Confirme ou descarte o achado antes de decidir". Sem migration (validação, não modelagem). `TestCoerenciaStatusPerene` (7 testes) + `TestDecisaoBloqueadaSeAchadoSuspeita` (3 testes). Suite 635/635 verde. |
| **23** | Gate camada 2 cobrando decisão em achado terminal (trap revelado pós-PROMPT_9) | 2026-05-26 (PROMPT_10, corrigido por PROMPT_11) | Gate de `PATCH /diagnoses/{version}/validate` filtra `status_achado in {suspeita, confirmada, ignorada}` — só `descartada` ("não é divergência real") e `resolvida` ("corrigida no mundo") são excluídas, pois nelas não há o que decidir. **PROMPT_11 corrigiu a versão original do #10**, que excluía `ignorada` por erro de simetria: `ignorada` significa "achado REAL posto de lado" e setá-la via `PATCH /issues` não exige justificativa — excluí-la abriria atalho pra silenciar crítico real sem registro, recriando a porta que o #19 fechou. Quem quer ignorar registra `decisao=ignorar_justificado` (com justificativa, #19); a Regra B permite porque `ignorada` ≠ `suspeita`. `suspeita` permanece pra forçar adjudicação antes de assinar (não é deadlock). `resolved_at IS NULL` mantido como critério ortogonal. Testes no `TestValidateDiagnosisGateCamada2`: `descartada`/`resolvida` liberam; `suspeita`/`confirmada`/`ignorada` continuam exigindo (422). Sem migration, sem ADR. **Follow-on aberto:** badge "N pendentes" do `DiagnosisAssinatura` (PROMPT_9) precisa espelhar a mesma exclusão (`descartada`/`resolvida`) pra não super-contar. |
| **12** | `PROJECT_NAME='Amigão'` em `config.py:52` | 2026-05-23 (Fase 0) | Já estava `"Regente Ambiental"` quando a Fase 0 auditou. Commit `7877652` documentou. |
| **24** | Upload de documento não casava com item do checklist + UI de exclusão sem cascata (ciclo de teste travado) | 2026-05-28 (`fix/upload-checklist-binding`) | (i) `DocumentConfirmRequest` ganhou `checklist_item_id?: str`; `confirm_upload` persiste a coluna e chama `auto_link_document` quando o `document_type` casa com um item pendente. (ii) `ProcessChecklist.handleReceived` passa `item.document_id` no PATCH. (iii) `DocumentsTab` renderiza `Object.entries(AIJob.result)` em `<dl>` (antes era só badge sem dado). (iv) Cascade delete service `app/services/cascade_delete.py` + endpoints `GET /{clients,properties}/{id}/delete-preview` + `DELETE` com cascata em ordem segura (RESTRICT-friendly) + `AuditLog cascade_deleted` com hash chain SHA-256 (LGPD); nunca toca doc de outro cliente. (v) Modais de confirmação em Clients/Properties listam contagens exatas antes de confirmar. Suite 186 testes verde, tsc verde. Sem migration. |
| **Sintoma "card discorda do diagnóstico assinado"** | Card lia só `completion_pct` enquanto `RegulatoryDiagnosis.validated_at` ficava em outro bloco; nem `can_advance_macroetapa` cobrava assinatura | 2026-05-28 (`fix/diagnostico-propaga-estado`) | `compute_macroetapa_state` e `can_advance_macroetapa` ganharam kwargs `current_macroetapa` + `diagnosis_validated` — etapa de diagnóstico vira `aguardando_validacao` enquanto não houver assinatura, e o gate de saída cobra o `validated_at`. `PATCH /processes/{id}/diagnoses/{version}/validate` chama `advance_macroetapa` automaticamente quando o gate passa (mesmo critério do botão manual: docs obrigatórios + checklist 100% + agora assinatura). Conservador: NÃO toca `Process.status` nem consolida as 2 chains — isso é o **eixo 3** (dívida nova **#26**, abaixo). Kanban (`processes.py`) consulta uma única vez o set de `process_id` com `RegulatoryDiagnosis.validated_at IS NOT NULL` para evitar N+1. 4 testes unitários (`tests/models/test_macroetapa_gate.py`) + 3 de API (`TestValidateAdvancesMacroetapa`). |
| **25** | Extrator no-op silencioso + sem caminho de extração por processo | 2026-05-28 (`fix/extrator-por-processo`) | Novo `POST /api/v1/processes/{id}/extract` enfileira `workers.run_agent(extrator)` para docs com `extracted_text` cacheado e `workers.ocr_then_extract` (chain OCR→extrator) para docs sem texto, com `force=true` opcional pra re-OCR. `AuditLog(action="extractor_dispatched")` rastreia o disparo. Mensagens do `ExtratorAgent` ganharam orientação acionável (apontam pro endpoint novo) — tanto o `reason` do skipped sem args quanto o `ValueError` quando `document_id` existe mas `extracted_text` é NULL. UI: card do `extrator` no `/agents` agora mostra "Rodar no processo #N" (disabled sem ID); Step 4 do `IntakeWizard` trava avanço se há docs sem leitura disparada; `DraftDocumentUploader` ganha botão 🗑 por linha (habilitado pra `ocr_status` em `{null, pending}`). Sem migration. 3 testes novos em `tests/api/test_processes.py` + 1 em `tests/agents/test_extrator_cache.py`. Suite verde (9 do processes / 4 do extrator). **Marco condicional:** o `_dispatch_extrator` em `app/workers/ocr_tasks.py` ainda passa `process_id=None` ao `run_agent` — `AIJob` resultante perde o link com o processo no caminho da chain OCR. Fora do escopo deste PR; abrir nova dívida se isso passar a doer. |
| **Eixo 2 workflow/RAG** | Silent failure de workflow sem template + RAG sem filtro estruturado por tipo | 2026-05-29 | `knowledge_catalog.search(demand_type=...)` filtra via `LegislationDocument.demand_types`; `LegislacaoAgent` usa o filtro; `apply_workflow_template` levanta `TemplateNotFoundError`; API retorna 422 acionável; enum `DemandType` expandido com 5 valores. |
| **Frente D** | Cripto de segredos por usuário (white label LLM + credenciais de portal) | 2026-05-28 (ADR-014) | Padrão Fernet (AES-128-CBC + HMAC-SHA256): módulo `app/core/encryption.py` (`get_fernet`/`encrypt_str`/`decrypt_str` com MultiFernet pra rotação), type decorator `EncryptedString` em `app/models/types.py`, `CREDENTIAL_ENCRYPTION_KEY` obrigatória (falha no startup, sem fallback), `tools/gen_encryption_key.py`. 8 testes verdes. **Nenhuma coluna real alterada** — aplicação fica pra dívida #27 (PR 2.3 + PR LLM). |
| **27** | Aplicar `EncryptedString` em colunas reais | 2026-05-30 (PR LLM + PR 2.3) | **PR LLM:** chave de IA do consultor cifrada em `User.preferences['ai']['api_key_encrypted']` (JSONB, via `encrypt_str`). **PR 2.3:** modelo `Credential` (tabela `credentials`) com `password_encrypted` usando o type decorator `EncryptedString` — **primeiro uso real em coluna de tabela**. Cofre de logins de portais por cliente (SEMA/IBAMA/SICAR/INCRA/banco), CRUD tenant-scoped, AuditLog hash chain, senha nunca em plaintext na API (verificado por SQL nos testes). Migration `c0d1e2f3a4b5` também **reunificou 2 heads do Alembic** (PROMPT_7 `e3d4f5g6a7b8` + PR 2.2 `e6f7a8b9c0d1`, ambas de `d2c3e4f5a6b8`) que quebravam `alembic upgrade head`. |

---

*Atualizar este registro ao fim de cada sprint. Itens fechados vão para a tabela acima,
não se apagam — comprova o trajeto e ajuda auditoria. Ver
`docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.*
