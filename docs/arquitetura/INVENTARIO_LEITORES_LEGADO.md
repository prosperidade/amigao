# Inventário de leitores das colunas legadas

**Documento:** Arquitetura · insumo do Incremento 6 (contração)
**Decisão que o exige:** colunas legadas saem no Incremento 6, com inventário de leitores;
nunca no mesmo passo que cria as novas ([ADR-070 §15](../adr/070-modelo-de-dados-alvo.md#15-migração)).
**Base:** `origin/main` @ `d7ad252`. Levantamento por leitura de código (grep com limite de
palavra + leitura do trecho), sem tocar banco. `client-portal/` e `mobile/` (congelados) fora.

## Como ler

| Sigla | Leitor | Por que importa no corte |
|---|---|---|
| **L** | lógica — o valor decide ramo, cálculo ou conteúdo de prompt | tem de migrar para a leitura nova **antes** do corte, com teste |
| **S** | serialização — sai numa resposta de API | adaptador serve o formato antigo até o frontend migrar |
| **Q** | consulta — filtro, ordenação ou SQL cru | quebra em tempo de execução, não de compilação |
| **F** | frontend — componente ou tipo TS lê o campo | build do front (`tsc -b`) pega o tipo; a lógica de tela não |
| **T** | só teste | conta de arquivos |
| **X** | `scripts/` e seed | |
| *st* | lê o **nome** da coluna como `target_field` do staging, não o valor | o nome é dado gravado: renomear quebra sem erro de compilação |
| *label* | só mapa nome → rótulo | trivial, mas some da tela se esquecido |

**Leitores que valem para várias colunas de matrícula e representante:**
- `_write_entity` ([staging_consolidation.py:1214](../../app/services/staging_consolidation.py#L1214))
  faz `getattr(obj, col)` e confere `field_sources[col]` (`:1220–1221`) para toda coluna de
  `_MATRICULA_FIELDS` (`:99–106`) e `_REPRESENTANTE_FIELDS` (`:76`). `field_selo.SELO_FIELDS`
  ([field_selo.py:42](../../app/services/field_selo.py#L42)) reusa a mesma lista.
- Schema `Matricula` ([schemas/matricula.py](../../app/schemas/matricula.py)) sai em quatro
  endpoints: `GET/POST /properties/{id}/matriculas`, `PATCH …/move`, `PATCH …/vigencia`
  ([properties.py:139, 152, 184, 237](../../app/api/v1/properties.py#L139)). Abaixo: "4 endpoints".
- Dossiê ([dossier.py:143–163](../../app/services/dossier.py#L143-L163)), servido por
  `GET /processes/{id}/dossier` e `POST …/dossier/refresh`.
- Nenhuma coluna de matrícula tem consulta (Q) viva; o único SQL cru é backfill histórico
  ([f2a4c6e8b0d2:34–56](../../alembic/versions/f2a4c6e8b0d2_sprint3_matricula_field_sources.py#L34-L56)).

## Resumo

| Coluna / estrutura | L | S | Q | F | T (arq.) | X | Escritores |
|---|---|---|---|---|---|---|---|
| `properties.has_embargo` | 8 | 4 | 0 | 4 arquivos | 3 + 1 FE | 1 | 2 (API) + formulário |
| `properties.registry_number` | 7 | 4 | 0 (+ UNIQUE no banco) | 2 arquivos | 4 + 1 FE | 1 | 3 |
| `properties.total_area_ha` | 12 | 4 | 0 | 4 arquivos | 11 + 3 FE | 3 | 5 |
| `properties.area_documental_ha` | 2 | 2 | 0 | 2 arquivos | 5 + 1 FE | 0 | 1 (consolidação) |
| `properties.area_grafica_ha` | 2 | 2 | 0 | 2 arquivos | 2 + 1 FE | 0 | 1 (consolidação) |
| `properties.car_status` | 8 | 3 | 0 | 2 arquivos | 4 + 1 FE | 1 | 3 |
| `properties.ccir` / `nirf` | 0 / 1 | 3 / 3 | 0 | 2 arquivos | 3 / 1 | 0 | 2 / 3 ativos (+1 latente cada) |
| `properties.regulatory_issues` (JSON) | 0 | 1 | 0 | 1 arquivo | 0 | 0 | **0** — sempre vazia |
| `properties.geom` | 2 | 1 (`has_geom`) | 1 | 1 arquivo | 5 + 1 FE | 0 | **0** |
| `documents.extracted_text` | 22 | 3 | 3 | 1 arquivo (indireto) | 22 + 1 FE | 3 | 5 |
| `documents.filename` / `original_file_name` | 14 / 7 | 8 / 9 | 0 | 7 / 5 arquivos | ~40 / 39 | 0 / 1 | 4 |
| `documents.s3_key` / `storage_key` | 1 / 6 | 0 / 1 | 0 | 0 | 0 / 44 | 0 / 2 | 3 / 4 |
| `documents.size` / `file_size_bytes` | **0** / 0 | 0 / 3 | 0 | 0 / 7 arquivos | 0 / 8 | 0 / 1 | 4 |
| `documents.content_type` / `mime_type` | 6 / 6 | 1 / 0 | 0 | 2 / 0 arquivos | 38 / 8 | 0 / 1 | 4 |
| `documents.version_number` | 1 | 0 | 0 | 0 | 0 | 0 | 0 (default 1) |
| `processes.process_type` | 7 | 2 | 0 | 2 arquivos | 80 | 3 | 3 (+ seed/ops) |
| `matriculas.proprietarios` | 2 (+2 *st*, +1 *label*) | 2 | 0 | 1 componente | 7 | 0 | 2 |
| `matriculas.area_ha` | 6 diretos + 8 via `area_total_matriculas` (+2 *st*) | 5 | 0 (+1 *st*) | 5 componentes | 27* + 2 FE | 1 (mock) | 2 |
| `matriculas.cartorio` | 2 (+4 *st*) | 3 | 0 | 2 componentes | 18* | 0 | 2 |
| `matriculas.registro_livro_folha_ficha` | 1 | 2 | 0 | 2 componentes | 0 | 0 | 2 |
| `matriculas.onus_gravames` | 1 (+2 *st*) | 2 | 0 | 1 componente | 2 | 0 | 2 |
| `matriculas.averbacao_app` / `averbacao_rl` | 2 (+1 *st*) | 2 | 0 | 1 componente | 9 | 0 | 2 |
| `matriculas.geo_certificacao_codigo` / `_status` | 2 (+1 *st*) | 2 | 0 | 1 componente | 6 | 0 | código 2; status só manual |
| `matriculas.vigencia` | 5 diretos + ~20 indiretos | 2 | 0 | 1 componente | ~3 | 1 (mock) | 3 |
| `extracted_field_staging.status` | 15 | 7 | 9 | 2 componentes | 33 + 2 FE | 1 | 10 |
| `extracted_field_staging.consolidated_at` | 4 | 1 (+2 derivados) | 0 | 1 componente | 8 + 1 FE | 0 | 9 |
| tabela `client_representatives` | 6 | 3 grupos (9 endpoints) | 3 | 1 componente | 3 | 0 | 5 |
| chaves de `atributos` (`baixado_por`, `retificado_por`, `altera_ato`, `adquirentes`, `transmitentes`, `partes`) | 2 do valor gravado (+~6 antes de gravar) | 1 | 0 | 0 | 5 | 0 | 3 |

\* inclui chaves homônimas de outros documentos.

## Imóvel

Não há SQL cru sobre `properties`, `documents` ou `processes` fora do alembic.

### `properties.has_embargo` — [property.py:32](../../app/models/property.py#L32)
Congelada pela decisão 6: **todos os 8 leitores L deixam de ler** no Incremento 2.
- **L:** [properties.py:505](../../app/api/v1/properties.py#L505) (estado `com_alertas` do hub), [:728, :744](../../app/api/v1/properties.py#L728) (resumo IA); [dossier.py:405](../../app/services/dossier.py#L405) (PROPERTY_EMBARGO); [diagnostico.py:386](../../app/agents/diagnostico.py#L386) (prompt), [:801, :823](../../app/agents/diagnostico.py#L801) (fallback de regras: passivo + `risco_estimado=alto`); [legislacao.py:561](../../app/agents/legislacao.py#L561) (prompt).
- **S:** [schemas/property.py:19](../../app/schemas/property.py#L19) (`/properties`); [property_hub.py:25, 78](../../app/schemas/property_hub.py#L25); [dossier.py:131](../../app/services/dossier.py#L131).
- **F:** PropertyHub.tsx:51, 98, 339, 609; Properties/index.tsx:25, 206, 377–378 (formulário grava); ProcessDossier.tsx:367, 373; ProcessHeader.tsx:25, 48 (`saudeOk`).
- **Escritores:** só POST/PATCH `/properties`. Nenhuma extração, consolidação ou agente grava. [test_evidence_execution.py:111](../../tests/e2e/test_evidence_execution.py#L111) já exige que ela **não** entre no payload de evidência.

### `properties.registry_number` — [property.py:19](../../app/models/property.py#L19)
- **L:** [properties.py:348–349](../../app/api/v1/properties.py#L348-L349) (nota de saúde); [dossier.py:362, 482](../../app/services/dossier.py#L362); [processes.py:950](../../app/api/v1/processes.py#L950) (gate de avanço); [mirante_documents.py:295–296](../../app/services/mirante_documents.py#L295-L296); [contract_generator.py:72](../../app/services/contract_generator.py#L72) (`{{imovel.matricula}}`); guarda de escrita em [intake_enrichment.py:203](../../app/services/intake_enrichment.py#L203).
- **S:** schemas/property.py:10; hub ([properties.py:519, 532](../../app/api/v1/properties.py#L519) — **a coluna tem precedência** sobre o agregado das matrículas); dossiê ([dossier.py:116–117](../../app/services/dossier.py#L116-L117), mesma precedência); [clients.py:479](../../app/api/v1/clients.py#L479).
- **F:** PropertyHub.tsx:42, 300, 596; ProcessDossier.tsx:340.
- **Banco:** `UNIQUE(tenant_id, registry_number)` ([a7b8c9d0e1f2:129–133](../../alembic/versions/a7b8c9d0e1f2_add_fk_cascade_rules_and_unique_registry.py#L129-L133)) — cai junto com a coluna.

### `properties.total_area_ha` — [property.py:25](../../app/models/property.py#L25)
- **L (12):** [properties.py:348, 521, 525](../../app/api/v1/properties.py#L521) (precedência sobre a soma; suprime a nota da soma); [dossier.py:427](../../app/services/dossier.py#L427); [processes.py:957](../../app/api/v1/processes.py#L957); [mirante_documents.py:288](../../app/services/mirante_documents.py#L288); [contract_generator.py:75](../../app/services/contract_generator.py#L75); prompts [diagnostico.py:382](../../app/agents/diagnostico.py#L382), [legislacao.py:560](../../app/agents/legislacao.py#L560); [auditor_imovel.py:268](../../app/agents/auditor_imovel.py#L268) (**leitura morta**: o `property_audit` não usa); guardas [intake_enrichment.py:203](../../app/services/intake_enrichment.py#L203), [intake.py:736](../../app/api/v1/intake.py#L736).
- **S:** schemas/property.py:15; hub (:545); dossiê (:127); [clients.py:483](../../app/api/v1/clients.py#L483).
- **F:** PropertyHub.tsx:47, 325–328, 602–605; Properties/index.tsx:22, 201; ClientHub.tsx:118, 574; ProcessDossier.tsx:345.
- **Escritores (5):** POST/PATCH `/properties`, [intake.py:194](../../app/api/v1/intake.py#L194), [:731–737](../../app/api/v1/intake.py#L731-L737), intake_enrichment. A consolidação recusa ([staging_consolidation.py:67, 1615](../../app/services/staging_consolidation.py#L1615)).

### `properties.area_documental_ha` / `area_grafica_ha` — [property.py:59–60](../../app/models/property.py#L59-L60)
- **L:** [auditor_imovel.py:269–270](../../app/agents/auditor_imovel.py#L269-L270) → [property_audit.py:247–248](../../app/services/property_audit.py#L247-L248) (cruzamentos de área que viram achado persistido); `_write_entity`.
- **S:** hub ([properties.py:557–558](../../app/api/v1/properties.py#L557-L558)); [dossier.py:167–168](../../app/services/dossier.py#L167-L168).
- **F:** PropertyHub.tsx:59–60, 707–721; ProcessDossier.tsx:77–78, 307–314.
- **Escritor:** só a consolidação (documental ← recibo do CAR, [ficha01_extraction.py:362](../../app/services/ficha01_extraction.py#L362); gráfica ← RAT, [:446](../../app/services/ficha01_extraction.py#L446)). Viram `medicao` no Incremento 3.

### `properties.car_status` — [property.py:23](../../app/models/property.py#L23)
- **L:** [properties.py:484, 496, 732](../../app/api/v1/properties.py#L484); [diagnostico.py:385, 808](../../app/agents/diagnostico.py#L808) (regra "CAR com pendências"); [legislacao.py:562](../../app/agents/legislacao.py#L562); [auditor_imovel.py:272](../../app/agents/auditor_imovel.py#L272) (**leitura morta**); `_write_entity`.
- **S:** schemas/property.py:14; hub (:544); dossiê (:126). **F:** PropertyHub.tsx:46, 307, 597; ProcessDossier.tsx:344.
- **Escritores:** POST/PATCH `/properties`; consolidação (CAR [ficha01_extraction.py:353](../../app/services/ficha01_extraction.py#L353) e RAT :445).

### `properties.ccir` / `nirf` — [property.py:20–21](../../app/models/property.py#L20-L21)
- **L:** `ccir` nenhum (o dossiê já usa `Matricula.codigo_incra_sncr`); `nirf` só guarda de escrita.
- **S:** schemas/property.py:11–12; hub (:537–538) e dossiê (:119–120) — **a coluna tem precedência** sobre o agregado das matrículas.
- **F:** PropertyHub.tsx:43–44, 313, 319, 598–599; ProcessDossier.tsx:341–342.
- **Achado #240:** a depreciação de `ccir` não é cumprida — `PropertyBase`/`PropertyUpdate` ainda aceitam o campo ([schemas/property.py:11, 34](../../app/schemas/property.py#L34)), e ele segue na allowlist de consolidação (latente). O `MODELO_DE_DADOS` o declara não-gravável.

### `properties.regulatory_issues` (JSON) — [property.py:58](../../app/models/property.py#L58)
- **Zero escritores:** a consolidação recusa o alvo ([staging_consolidation.py:1619](../../app/services/staging_consolidation.py#L1619)); a coluna é sempre lista vazia.
- **S:** hub ([properties.py:556](../../app/api/v1/properties.py#L556)). **F:** bloco "Pendências ambientais" ([PropertyHub.tsx:748–754](../../frontend/src/pages/Properties/PropertyHub.tsx#L748-L754)), que portanto nunca mostra nada por esta via.
- **Corte:** candidata imediata — só o serializador e um bloco de tela.

### `properties.geom` — [property.py:30](../../app/models/property.py#L30)
- **L:** [dossier.py:414](../../app/services/dossier.py#L414) (MISSING_GEOM); [auditor_imovel.py:274](../../app/agents/auditor_imovel.py#L274) carrega o blob inteiro só para um booleano.
- **Q:** [api/v1/regulatory.py:642](../../app/api/v1/regulatory.py#L642) (`isnot(None)`). **S:** `has_geom` derivado. **Escritores: 0.**
- **Corte:** não sai — vira projeção de `feicao` (ADR-070 §9).

## Documento

### `documents.extracted_text` — [document.py:89](../../app/models/document.py#L89)
Não sai: vira **projeção da versão corrente** (ADR-070 §6). Os leitores abaixo tratam o texto como verdade e passam a ler `documento_versao` onde precisarem de versão fixa.
- **L — OCR/transcrição:** cache e cópia de gêmeo ([ocr_tasks.py:128–142, 241](../../app/workers/ocr_tasks.py#L241); [audio_tasks.py:120–133, 198](../../app/workers/audio_tasks.py#L198)); decisão de `/extract` ([processes.py:603](../../app/api/v1/processes.py#L603)).
- **L — extração e âncoras:** [extrator.py:56, 63, 79, 143, 156](../../app/agents/extrator.py#L56) → `ficha01_extraction` → `text_anchor`; [ai_tasks.py:156](../../app/workers/ai_tasks.py#L156); [extracao_lote.py:67–69](../../app/services/extracao_lote.py#L67-L69); [document_classification.py:191](../../app/services/document_classification.py#L191).
- **L — evidência e agentes:** [evidence.py:195–200](../../app/services/evidence.py#L195-L200); [diagnostico.py:446, 714](../../app/agents/diagnostico.py#L446); [passivos_esfera.py:114](../../app/services/passivos_esfera.py#L114); estado derivado ([document.py:104](../../app/models/document.py#L104); [document_lifecycle.py:75](../../app/services/document_lifecycle.py#L75)).
- **Q:** `isnot(None)` em extrator.py:51, ocr_tasks.py:235, audio_tasks.py:192. **S:** `GET /documents/{id}/text` ([documents.py:419–427](../../app/api/v1/documents.py#L419-L427)); `tem_texto`, `lifecycle_status`.
- **Escritores (5):** ocr_tasks.py:242, 363; audio_tasks.py:199, 337; extrator.py:157.

### Pares-alias e `version_number` — [document.py:44–53, 59](../../app/models/document.py#L44-L59)
- **Não dá para só apagar o "legado" do par:** `filename` e `mime_type` dirigem lógica — `is_audio` e `is_geospatial` ([ocr_tasks.py:111](../../app/workers/ocr_tasks.py#L111) usa **só** `mime_type`, que é nulável enquanto `content_type` é NOT NULL; [intake.py:978, 1000](../../app/api/v1/intake.py#L978); [documents.py:490](../../app/api/v1/documents.py#L490); [processes.py:609](../../app/api/v1/processes.py#L609)).
- **`size`: zero leitores** em todo o código — sai quando os 4 escritores pararem.
- `s3_key`: um leitor (fallback em [reset_casos_teste.py:297, 304](../../app/services/reset_casos_teste.py#L297)); o WhatsApp ([messaging.py:144–152](../../app/api/v1/messaging.py#L144-L152)) nem grava.
- `storage_key` é o canônico (download, OCR, evidência) e tem UNIQUE.
- `version_number`: um leitor ([evidence.py:193](../../app/services/evidence.py#L193)), zero escritores — substituído por `documento_versao`.
- `upload_file()` de [storage.py:241–249](../../app/services/storage.py#L241-L249) monta o mesmo dicionário e não tem chamador.

## Processo

### `processes.process_type` — [process.py:106](../../app/models/process.py#L106)
Sai em **frente própria** (MIGRACAO §3), separando objetivo validado de demanda classificada.
- **L:** [processes.py:1138–1139](../../app/api/v1/processes.py#L1138-L1139) → [atendimento.py:33](../../app/agents/atendimento.py#L33) → [intake_classifier.py:506–507](../../app/services/intake_classifier.py#L506-L507), onde o tipo informado vira `demand_type` com confiança **declarada**; [evidence.py:234](../../app/services/evidence.py#L234) (objetivo, marcado como sugestão não promovida); prompts ([diagnostico.py:358](../../app/agents/diagnostico.py#L358), [legislacao.py:548](../../app/agents/legislacao.py#L548), [orcamento.py:90](../../app/agents/orcamento.py#L90), [redator.py:282](../../app/agents/redator.py#L282)); [pdf_generator.py:177](../../app/workers/pdf_generator.py#L177).
- **S:** `ProcessBase` em todo `/processes`; [dossier.py:285](../../app/services/dossier.py#L285). **F:** ProcessDetailTypes.ts:21; DiagnosisTab.tsx:332.
- **Achado #241:** `ProcessBase.process_type` tem default `"licenciamento"` ([schemas/process.py:10](../../app/schemas/process.py#L10)), que é chave de `_DEMAND_RULES`: processo criado sem tipo chega ao classificador como **declaração** de licenciamento. Latente enquanto o Atendimento estiver congelado (ADR-069).


## Matrícula

### `matriculas.proprietarios` — [matricula.py:90](../../app/models/matricula.py#L90)
- **L:** [diagnostico.py:596–603](../../app/agents/diagnostico.py#L596-L603) → [auto_infracao_extraction.py:398–402](../../app/services/auto_infracao_extraction.py#L398-L402) (nota "autuado difere do titular"); `_write_entity`. *st:* [reconciliation_decisions.py:327](../../app/services/reconciliation_decisions.py#L327), [:817](../../app/services/reconciliation_decisions.py#L817). *label:* [acao_generator.py:411](../../app/services/acao_generator.py#L411).
- **S:** [schemas/matricula.py:28](../../app/schemas/matricula.py#L28) (4 endpoints); [dossier.py:159](../../app/services/dossier.py#L159).
- **F:** [ProcessDossier.tsx:70, 523–526, 535](../../frontend/src/pages/Processes/ProcessDossier.tsx#L523-L526).
- **Escritores:** `_write_entity` ([staging_consolidation.py:1240](../../app/services/staging_consolidation.py#L1240)) a partir da certidão; POST manual ([properties.py:173–178](../../app/api/v1/properties.py#L173-L178)). CCIR `detentor` e SIGEF `proprietario` barrados pelo ADR-062.

### `matriculas.area_ha` — [matricula.py:66](../../app/models/matricula.py#L66)
- **L direto:** [property.py:124](../../app/models/property.py#L124) (`area_total_matriculas`), [:149](../../app/models/property.py#L149); [matricula_chain.py:143, 164, 177](../../app/services/matricula_chain.py#L143); `_write_entity`; [staging_consolidation.py:1323, 1328](../../app/services/staging_consolidation.py#L1323).
- **L via `area_total_matriculas()`:** [diagnostico.py:391–393](../../app/agents/diagnostico.py#L391-L393) (entrada do LLM); [processes.py:956](../../app/api/v1/processes.py#L956); [properties.py:520–521](../../app/api/v1/properties.py#L520-L521); [dossier.py:112, 127, 170, 426](../../app/services/dossier.py#L112); [staging_consolidation.py:1046](../../app/services/staging_consolidation.py#L1046); [mirante_documents.py:284–289](../../app/services/mirante_documents.py#L284-L289).
- *st:* [confronto_identidade.py:147, 156](../../app/services/confronto_identidade.py#L147).
- **Homônimos que NÃO são esta coluna:** `atributos.area_ha` ([reconciliation_decisions.py:580](../../app/services/reconciliation_decisions.py#L580)), [inconsistency_matrix.py:80–83](../../app/services/inconsistency_matrix.py#L80-L83), [observacao_registral.py:322](../../app/services/observacao_registral.py#L322), `ctx["area_ha"]` de [legislacao.py:560](../../app/agents/legislacao.py#L560) (vem de `total_area_ha`).
- **S:** schemas/matricula.py:21 (4 endpoints) e `MatriculaVigenteMini` (:100, `GET /processes/{id}/matriculas-vigentes`); dossiê (:124, :127, :152, :170); `GET /properties/{id}/summary` ([property_hub.py:67](../../app/schemas/property_hub.py#L67)); `POST /processes/{id}/consolidar` ([schemas/extracted_field_staging.py:148, 155–156](../../app/schemas/extracted_field_staging.py#L148)).
- **F:** [PropertyHub.tsx:796, 848–851, 869, 907](../../frontend/src/pages/Properties/PropertyHub.tsx#L848-L851); ProcessDossier.tsx:58, 253, 319, 356; CadeiaFichasPanel.tsx:31, 37; ProcessHeader.tsx:120–124; ConsolidacaoPanel.tsx:93, 542.
- **Achado:** o Hub soma no cliente e inclui matrícula rejeitada — **#238** (§Achados).

### `matriculas.cartorio` — [matricula.py:49](../../app/models/matricula.py#L49)
- **L:** `agregar_das_matriculas("cartorio")` ([property.py:149](../../app/models/property.py#L149)) chamado em [properties.py:539](../../app/api/v1/properties.py#L539) e [dossier.py:121](../../app/services/dossier.py#L121); `_write_entity`. *st:* [reconciliation_decisions.py:97, 118, 157, 436–439](../../app/services/reconciliation_decisions.py#L436-L439).
- **S:** schemas/matricula.py:11; dossiê (:121, :153); [property_hub.py:61](../../app/schemas/property_hub.py#L61).
- **F:** PropertyHub.tsx:72, 614, 803, 813; ProcessDossier.tsx:64, 352, 529.

### `matriculas.registro_livro_folha_ficha` — [matricula.py:50](../../app/models/matricula.py#L50)
- **L:** só `_write_entity`. **S:** schemas/matricula.py:12; dossier.py:155. **F:** PropertyHub.tsx:807, 814; ProcessDossier.tsx:66, 530.

### `matriculas.onus_gravames` — [matricula.py:86](../../app/models/matricula.py#L86)
- **L:** só `_write_entity` — nenhuma regra de negócio lê o valor. *st:* [reconciliation_decisions.py:321, 598](../../app/services/reconciliation_decisions.py#L598).
- **S:** schemas/matricula.py:27; dossier.py:158. **F:** ProcessDossier.tsx:69, 534.
- **Escritor:** lista de `onus_vigentes` achatada em texto por `_stringify_structured` ([staging_consolidation.py:144–155](../../app/services/staging_consolidation.py#L144-L155)).

### `matriculas.averbacao_app` / `averbacao_rl` — [matricula.py:84–85](../../app/models/matricula.py#L84-L85)
- **L:** `averbacao_rl` deriva `Property.rl_status='averbada'` ([staging_consolidation.py:1031](../../app/services/staging_consolidation.py#L1031)) — **leitor de lógica real**; ambos via `_write_entity`. *st:* [reconciliation_decisions.py:500](../../app/services/reconciliation_decisions.py#L500) (`averbacao_app`, dívida #225).
- **S:** schemas/matricula.py:25–26; dossier.py:156–157. **F:** ProcessDossier.tsx:67–68, 532–533.

### `matriculas.geo_certificacao_codigo` / `_status` — [matricula.py:80–81](../../app/models/matricula.py#L80-L81)
- **L:** [api/v1/regulatory.py:694–698](../../app/api/v1/regulatory.py#L694-L698) (escolhe o texto da nota espacial); `_write_entity`; allowlist do selo ([field_selo.py:42](../../app/services/field_selo.py#L42)). *st:* [reconciliation_decisions.py:376](../../app/services/reconciliation_decisions.py#L376).
- **S:** schemas/matricula.py:23–24; dossier.py:147–148. **F:** ProcessDossier.tsx:53–54 (tipos), 256 (código + selo); `status` nunca renderizado.
- **Escritores:** código pela certidão e manual; `status` **sem escritor automático** (a rota SIGEF é barrada pelo ADR-062).

### `matriculas.vigencia` (vigente | historica) — [matricula.py:122](../../app/models/matricula.py#L122)
- **L direto:** [matricula.py:144–146](../../app/models/matricula.py#L144-L146) (`is_vigente`); [property.py:104, 113](../../app/models/property.py#L104); [matricula_chain.py:207, 250](../../app/services/matricula_chain.py#L207).
- **L indireto (~20):** tudo que usa `matriculas_vigentes()`/`historicas()`/`is_vigente` — detecção de cadeia, dossiê (MISSING_MATRICULA, contiguidade, CAR_NO_MATRICULA_DOC), `/matriculas-rotulos`, `/matriculas-vigentes`, [mirante_documents.py:138](../../app/services/mirante_documents.py#L138) (bloqueia geração de contrato), `nota_soma` no contexto do LLM ([diagnostico.py:394](../../app/agents/diagnostico.py#L394), [legislacao.py:566](../../app/agents/legislacao.py#L566)) e todos os leitores de `area_total_matriculas`.
- **S:** schemas/matricula.py:61; dossier.py:161. **F:** PropertyHub.tsx:798, 836 (PATCH), 848–849.
- **Corte:** é **rename** (colide com a vigência do ato), não remoção; ~25 leitores lógicos passam pelos três helpers do model — trocar o nome dentro deles cobre a maioria.

## Staging

### `extracted_field_staging.status` — [extracted_field_staging.py:35–43, 102–107](../../app/models/extracted_field_staging.py#L102-L107)
Eixo lido: **[C]** comparação (`consistente`, `divergente_*`) · **[R]** revisão (`pendente`, `aceito`, `rejeitado`) · **[B]** valor cru.
- **L (15):** staging_consolidation.py:508 [C], 516 [C], 531 [C], 402 [B], 616 [R], 1917 [R], 1934 [R], 1937 [C]; reconciliation_decisions.py:710, 714 [R]; process_indicators.py:112–117 [R]; document_lifecycle.py:139 [R]; ficha01_extraction.py:1577, 1588 [R], 1651 [B]; evidence.py:290–293 [R].
- **Q (9):** staging_consolidation.py:634 [C], 677 [R], 1411 [R], 1778 [R]; acao_generator.py:252 [C]; consolidacao_lineage.py:308 [R] (só testes chamam); staging_repo.py:29 [B]; document_lifecycle.py:160, 198 [B].
- **S (7):** `GET /processes/{id}/staging-fields` ([schemas/extracted_field_staging.py:32](../../app/schemas/extracted_field_staging.py#L32)); `POST …/decidir` (:98); `Evidencia.status` em `GET /staging-decisions` ([schemas/reconciliation.py:30](../../app/schemas/reconciliation.py#L30)); `GET /confronto-identidade` ([confronto_identidade.py:218](../../app/services/confronto_identidade.py#L218)); derivados em `/progresso`, `lifecycle_status` e `review_states` do envelope.
- **F:** ConsolidacaoPanel.tsx:62, 117–124, 268, 270, 274, 360–361, 442, 447, 462; ConfrontoIdentidade.tsx:29, 54–58, 107; reconciliation.ts:22.
- **Achado — o eixo de comparação está morto na prática:** o app só grava `divergente_transcricao` ([staging_consolidation.py:949](../../app/services/staging_consolidation.py#L949)). `consistente` e `divergente_fundo` **nunca** são gravados: `inconsistency_matrix.build_matrix` calcula `status_updates` ([inconsistency_matrix.py:753–926](../../app/services/inconsistency_matrix.py#L753-L926)) e nenhum chamador fora dos testes os aplica. O aceite em lote de `consistente` ([staging_consolidation.py:634](../../app/services/staging_consolidation.py#L634)) e o contador do painel ([ConsolidacaoPanel.tsx:268](../../frontend/src/pages/Processes/ConsolidacaoPanel.tsx#L268)) leem valores que só linha legada ou teste produz. Reforça a separação dos eixos do ADR-070; não abre dívida própria.

### `extracted_field_staging.consolidated_at` — [extracted_field_staging.py:136](../../app/models/extracted_field_staging.py#L136)
- **L:** [staging_consolidation.py:1791](../../app/services/staging_consolidation.py#L1791); [reconciliation_decisions.py:709, 712](../../app/services/reconciliation_decisions.py#L709); [process_indicators.py:113](../../app/services/process_indicators.py#L113).
- **S:** `gravado`/`gravado_em` em `/staging-fields` ([processes.py:1530–1531](../../app/api/v1/processes.py#L1530-L1531)); derivado em `Decisao.estado`, `/progresso`, dossiê.
- **F:** ConsolidacaoPanel.tsx:74–75, 278, 352, 354, 449; DecisoesPanel.tsx:252 (via `estado`).

### Chaves de relação entre atos em `atributos` — [extracted_field_staging.py:94–100](../../app/models/extracted_field_staging.py#L94-L100)
- **L do valor gravado:** `adquirentes`/`transmitentes` em [reconciliation_decisions.py:784–835](../../app/services/reconciliation_decisions.py#L784-L835) (cadeia e `titular_atual` propostos); `reclassificar` ([staging_consolidation.py:450–475](../../app/services/staging_consolidation.py#L450-L475)) regenera o resumo. `altera_ato` não tem leitor do valor gravado.
- **L antes de gravar:** [observacao_registral.py:475, 495, 520, 524, 556, 619–623](../../app/services/observacao_registral.py#L475); `partes` termina como texto em `onus_gravames`.
- **S:** o dicionário inteiro em `/staging-fields`. **F:** nenhum.

## Representante

### tabela `client_representatives` — [client_representative.py:47–90](../../app/models/client_representative.py#L47-L90)
- **L:** `_resolve_representante` ([staging_consolidation.py:1527–1552](../../app/services/staging_consolidation.py#L1527-L1552)); `_write_entity`; [staging_consolidation.py:1673–1681](../../app/services/staging_consolidation.py#L1673-L1681); [diagnostico.py:588–592](../../app/agents/diagnostico.py#L588-L592) → auto de infração; [mirante_documents.py:495–505](../../app/services/mirante_documents.py#L495-L505) (bloco do contrato); [clients.py:720](../../app/api/v1/clients.py#L720).
- **S:** hub (`GET /clients/{id}/summary`, [client_hub.py:36–39](../../app/schemas/client_hub.py#L36-L39)); `Client.representatives` ([schemas/client.py:98](../../app/schemas/client.py#L98)) em todo endpoint que devolve `Client`; `GET/POST/PATCH /representatives` ([clients.py:665, 682, 707](../../app/api/v1/clients.py#L665)).
- **Q:** staging_consolidation.py:1528–1535; clients.py:655–657, 674–677.
- **F:** só o hub ([ClientHub.tsx:40–343](../../frontend/src/pages/Clients/ClientHub.tsx#L335)).
- **Achado:** `Client.representatives` serializa representante apagado — **#239**.
- **Corte:** a tabela vira projeção de `participacao` (ADR-070 §7); os três grupos de endpoint precisam de adaptador.

## Achados

| Dívida | Achado | Confirmação |
|---|---|---|
| **#238** | Hub soma área de matrícula rejeitada: `GET /properties/{id}/matriculas` não filtra `deactivated_at` ([matricula_repo.py:14–24](../../app/repositories/matricula_repo.py#L14-L24), base só filtra tenant) e [PropertyHub.tsx:848–851](../../frontend/src/pages/Properties/PropertyHub.tsx#L848-L851) filtra só `vigencia`; `Property.area_total_matriculas` exclui a desativada ([property.py:117–126](../../app/models/property.py#L117-L126)) | Lido no código; não reproduzido na tela |
| **#239** | Representante apagado sai em `Client.representatives`: relação sem filtro de `deleted_at` ([client.py:94–98](../../app/models/client.py#L94-L98)), schema serializa a lista ([schemas/client.py:98](../../app/schemas/client.py#L98)) | Lido no código; o frontend não lê esse campo hoje |
| — | Eixo de comparação do `staging.status` nunca gravado (ver Staging) | Lido no código; sem dívida própria — entra na separação de eixos |
| **#240** | Depreciação de `Property.ccir` não cumprida: `POST/PATCH /properties` ainda aceitam o campo ([schemas/property.py:11, 34](../../app/schemas/property.py#L34)); segue na allowlist de consolidação | Lido no código |
| **#241** | Default `process_type="licenciamento"` ([schemas/process.py:10](../../app/schemas/process.py#L10)) chega ao classificador como tipo declarado | Lido no código; latente (Atendimento congelado) |
| — | Leituras mortas no auditor: carrega `total_area_ha`, `car_status` e o blob de `geom`, e o `property_audit` não usa os dois primeiros ([auditor_imovel.py:268–274](../../app/agents/auditor_imovel.py#L268-L274)) | Lido no código; sem dívida — sai no Auditor unificado (Incremento 3) |

## Ordem de corte por coluna (Incremento 6)

1. Leitores **L** e **Q** passam para a fonte nova, com teste que falha se voltarem a ler a coluna.
2. **S** passa a ser servido por adaptador a partir da fonte nova; o formato da resposta não muda.
3. **F** migra para o campo novo; o adaptador sai.
4. Escritores param de gravar (a coluna fica congelada, ainda legível para auditoria).
5. Nova leitura do inventário: zero leitores L/Q/S/F. Só então o `DROP COLUMN`, em janela, com
   backup e API + worker + frontend na mesma versão.

Chaves *st* e *label* entram no passo 1: o nome da coluna está gravado como dado em
`target_field`, em `field_sources` e na auditoria, e pede backfill da chave no mesmo passo.
