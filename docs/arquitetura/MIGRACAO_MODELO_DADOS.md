# Migração do modelo de dados — confronto, constraints e roteiro

**Documento:** Arquitetura · roteiro para o Incremento 2 (e seguintes)
**Decisões:** [ADR-070](../adr/070-modelo-de-dados-alvo.md) · **Nomes:** [Ontologia v1](ONTOLOGIA_REGENTE_v1.md) (#175)
**Base:** código em `b6df7e6` (o #175, mergeado depois, só acrescenta docs); banco dev `amigao_db` @ `127.0.0.1:15432`, alembic
`c7e1a94d2f60` (o `069ce001` do #172 **não** está aplicado em dev). Leituras só com SELECT.
**Estado:** análise. **Nenhuma migration escrita, nenhum schema alterado.** SQL abaixo é
esboço para dimensionar, não migration.

> **Alvo usado.** `ARQUITETURA_DADOS_RAG_REGENTE_v1.md` não foi entregue. Entidades-alvo:
> [Plano v1.1 §6.2](PLANO_DIRETOR_REGENTE_v1.1.md#62-entidades-novas) + objetos do
> [Mergulho §2.3](MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md#23-contrato-alvo-evidência-observação-derivação-e-conclusão).
> Os sete grupos do §4 são os do [Plano §6.3](PLANO_DIRETOR_REGENTE_v1.1.md#63-migração)
> / [Mergulho §5.7](MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md#57-estratégia-de-migração).
> Divergência com o §3/§5/§10 do documento, quando ele chegar, reabre esta tabela.

Legenda de caminho: `ev.py` = `app/models/evidence.py`; `sev.py` = `app/schemas/evidence.py`;
`svev.py` = `app/services/evidence.py`; `obs.py` = `app/services/observacao_registral.py`;
`f01.py` = `app/services/ficha01_extraction.py`; `ca.py` = `app/services/connected_agents.py`.

---

## 1. Confronto schema real × alvo

| Entidade alvo | Hoje (nome · onde) | Falta (campo, relação, constraint) | Errado por **nome** | Errado por **semântica** |
|---|---|---|---|---|
| **documento_versao** | Não existe. `documents` é linha mutável ([document.py:32–95](../../app/models/document.py#L32-L95)); `version_number` sempre 1, nunca escrito ([:59](../../app/models/document.py#L59)); ADR-069 copia o texto em `EvidenceVersion document:{id}` só na captura ([svev.py:191–201](../../app/services/evidence.py#L191-L201)) | Tabela imutável (n, sha256 bytes, texto, sha256 texto, páginas lidas/total, método/modelo/parâmetros, origem); `UNIQUE(documento, n)`; checksum obrigatório (dev: 9/47 preenchidos) | `version_number` promete cadeia que não existe | `extracted_text` sobrescrito ([ocr_tasks.py:363](../../app/workers/ocr_tasks.py#L363), gêmeo [:242](../../app/workers/ocr_tasks.py#L242), [audio_tasks.py:337](../../app/workers/audio_tasks.py#L337), [extrator.py:157](../../app/agents/extrator.py#L157)); pode conter resumo LLM + transcrição e vira literal de fonte primária ([audio_tasks.py:287–291](../../app/workers/audio_tasks.py#L287-L291) → [svev.py:195](../../app/services/evidence.py#L195)); `OcrStatus` mistura pipeline e aplicabilidade (`not_required`), `done` ≠ legível ([document.py:10–15](../../app/models/document.py#L10-L15)); `extraction_status` texto com estado+motivo ([:67](../../app/models/document.py#L67)); `confidence_score` constante por método ([ocr_tasks.py:369](../../app/workers/ocr_tasks.py#L369)); colunas-alias duplicadas ([document.py:44–53](../../app/models/document.py#L44-L53)) |
| **fragmento** | Não existe. `Ancora(pos, trecho, metodo)` dentro de `field_value` do staging ([text_anchor.py:52–66](../../app/services/text_anchor.py#L52-L66); [f01.py:849–857](../../app/services/ficha01_extraction.py#L849-L857)); `page/position/anchor` do contrato nunca preenchidos na captura ([svev.py:211–219](../../app/services/evidence.py#L211-L219)) | FK à versão, página, fim do span, hash do texto, bbox, id citável | — | `pos` é offset do texto **corrente**: re-OCR envelhece a âncora em silêncio; `trecho` é janela ±90 com espaço colapsado, não o span ([text_anchor.py:49](../../app/services/text_anchor.py#L49)); `ancora` tem três formas |
| **observacao** | `extracted_field_staging` ([extracted_field_staging.py:46–156](../../app/models/extracted_field_staging.py#L46-L156)) + `EvidenceVersion kind=observacao` ([ev.py:22–38](../../app/models/evidence.py#L22-L38); mapeamento [svev.py:205–223](../../app/services/evidence.py#L205-L223)) | Validador próprio (predicado/fonte/âncora são opcionais, [sev.py:112–126](../../app/schemas/evidence.py#L112-L126)); unidade, papel, tempo e âncora nunca preenchidos; coluna indexável de predicado/sujeito; unicidade no staging (dedup só na app e **sem `document_id` na chave**, [f01.py:1461–1485](../../app/services/ficha01_extraction.py#L1461-L1485)) | `object` recebe `source_doc_type` e `subject` recebe `matricula_hint` ([svev.py:214–215](../../app/services/evidence.py#L214-L215)); `normalized` recebe `decided_value` (decisão humana apresentada como normalização, [:216](../../app/services/evidence.py#L216)) | `status` mistura comparação e revisão ([:35–43](../../app/models/extracted_field_staging.py#L35-L43)); `consolidated_at` é terceiro eixo na mesma linha; `field_value` guarda valor+unidade+âncora+motivo+fatia; `atributos` mistura extraído e derivado (`baixado_por`, `vigencia`, [:94–100](../../app/models/extracted_field_staging.py#L94-L100)); captura descarta linha de documento nulo/apagado/gerado ([svev.py:188–190](../../app/services/evidence.py#L188-L190)); listas `onus/proprietarios/pendencias_rat` deduplicam por `"__list__"` ([f01.py:808–809](../../app/services/ficha01_extraction.py#L808-L809)) |
| **derivacao** | `EvidenceVersion kind=derivacao`, exige premissas + `method_version` ([sev.py:116–117](../../app/schemas/evidence.py#L116-L117)); produtores `case:material` ([svev.py:250–255](../../app/services/evidence.py#L250-L255)) e `comparison:{uuid}` ([ca.py:132–135](../../app/services/connected_agents.py#L132-L135)) | Registro de método com hash do código ligado à derivação (hoje só no manifesto, [agent_capabilities.py:45–48](../../app/services/agent_capabilities.py#L45-L48)); resultado tipado; arestas; identidade estável (uuid novo por execução gera duplicata) | `method_version` guarda etiqueta de política ("069.2"), não versão de método | Resultado em `attributes.normalized` (Any), no mesmo saco dos campos de observação; derivação legada vive em `staging.status` |
| **conclusao** | `EvidenceVersion kind=conclusao`, 7 classes ([sev.py:101–103](../../app/schemas/evidence.py#L101-L103)); paralelos legados: `RegulatoryDiagnosis.content` ([regulatory.py:184–236](../../app/models/regulatory.py#L184-L236)), `RegulatoryIssue` ([:300–453](../../app/models/regulatory.py#L300-L453)), `StageOutput` ([stage_output.py:29–79](../../app/models/stage_output.py#L29-L79)) | impacto, urgência, finalidade; regra por classe além de `risco`; `conclusion_class` hoje aceito em kind ≠ conclusão; nada no app produz `norms` nem consulta (só testes) | `Afirmacao.categoria` tem vocabulário próprio `passivo\|acao\|hipotese\|lacuna` e recebe a classe ([stage_output.py:181](../../app/schemas/stage_output.py#L181) × [sev.py:133](../../app/schemas/evidence.py#L133)) | Conclusão do auditor usa `acao_recomendada` como texto e classe lacuna/divergência ([ca.py:137–142](../../app/services/connected_agents.py#L137-L142)); `as_assertion` rotula toda premissa como `auditor`, inclusive documento ([sev.py:135–137](../../app/schemas/evidence.py#L135-L137)); materializador inventa fonte `ai_job:N` e lê o último AIJob `completed` ([diagnosis_materializer.py:91–99](../../app/services/diagnosis_materializer.py#L91-L99); [api/v1/regulatory.py:294–305](../../app/api/v1/regulatory.py#L294-L305)) — rota paralela vedada pelo ADR-069; `issue_ids` JSON em vez de FK; `UNIQUE(process_id, version)` sem tenant ([regulatory.py:194](../../app/models/regulatory.py#L194)); `needs_human_validation` default False ([stage_output.py:68](../../app/models/stage_output.py#L68)); `DecisionCreate` default `validada` ([schemas/process_decision.py:26](../../app/schemas/process_decision.py#L26)) |
| **revisao** | `EvidenceReview` ([ev.py:41–53](../../app/models/evidence.py#L41-L53)), eco na hash chain ([svev.py:390–399](../../app/services/evidence.py#L390-L399)) | CHECK de `action`; FK da revisão `corrigir` para a versão criada; FK composta tenant/processo contra a evidência; `server_default` de `created_at` | Serviço grava `substituida_por_nao_aplicavel`, fora do Literal de 4 ações ([svev.py:374](../../app/services/evidence.py#L374) × [sev.py:167](../../app/schemas/evidence.py#L167)) | `EvidenceInvalidation` atualizada no lugar e `UNIQUE(evidence_id)` impede segunda invalidação ([api/v1/evidence.py:98–101](../../app/api/v1/evidence.py#L98-L101); [ev.py:61](../../app/models/evidence.py#L61)); revisões legadas sobrescrevíveis (staging `decided_*`, `validated_*`, upsert de `ProcessIssueDecision`); `AuditLog.entity_id` inteiro não endereça `object_id` texto ([audit_log.py:17](../../app/models/audit_log.py#L17)) |
| **parte / pessoa** | Não existe. Identidade em cinco lugares: `Client` ([client.py:44](../../app/models/client.py#L44)), `ClientRepresentative` ([client_representative.py:47](../../app/models/client_representative.py#L47)), `ManualPessoa` ([schemas/intake.py:345–348](../../app/schemas/intake.py#L345-L348)), `proprietarios` ([matricula.py:90](../../app/models/matricula.py#L90)), `atributos.partes` ([obs.py:321–324](../../app/services/observacao_registral.py#L321-L324)) | Tabela `pessoa`; identificadores qualificados; aliases; natureza indeterminada; espólio (`ClientType` só pf/pj, [client.py:22–24](../../app/models/client.py#L22-L24)) | "titular" usado para `Client` ([staging_consolidation.py:1479–1492](../../app/services/staging_consolidation.py#L1479-L1492); [f01.py:1376–1399](../../app/services/ficha01_extraction.py#L1376-L1399); [diagnostico.py:576–585](../../app/agents/diagnostico.py#L576-L585)) | `Client` mistura identidade, situação comercial/financeira/acesso e contato ([client.py:27–32](../../app/models/client.py#L27-L32)); mesma pessoa representando duas PJ = duas linhas por desenho ([client_representative.py:19–21](../../app/models/client_representative.py#L19-L21)); `partes` é str ou dict sem papel |
| **participacao** | Só `ClientRepresentative` (representação de PJ). Adquirente/transmitente são chaves JSON em `atributos`; `cadeia_titularidade` é dict em memória ([obs.py:672–694](../../app/services/observacao_registral.py#L672-L694)) | Tabela; FK a pessoa/ato/matrícula/caso; fundamento além de `source_document_id`; poderes e limites; intervalo; extensão/fração | `Property.client_id` é vínculo comercial lido como domínio ([property.py:16](../../app/models/property.py#L16)) | Papel em três vocabulários sem relação: `PAPEIS_REPRESENTANTE` ([client_representative.py:37–44](../../app/models/client_representative.py#L37-L44)), chave JSON, `role` livre ([sev.py:63](../../app/schemas/evidence.py#L63)) |
| **ato_registral** | `Observacao` em memória ([obs.py:327–393](../../app/services/observacao_registral.py#L327-L393)); persiste como staging `tipo_observacao` + `atributos`; depois da consolidação vira texto em `averbacao_app/rl` e `onus_gravames` ([matricula.py:84–86](../../app/models/matricula.py#L84-L86)) | Tabela; FK à matrícula (hoje `matricula_hint` texto); serventia (hoje `cartorio` texto, [matricula.py:49](../../app/models/matricula.py#L49)); espécie registro × averbação; chave (matrícula, rótulo); data tipada com precisão | `registro_livro_folha_ficha` junta três identificadores ([matricula.py:50](../../app/models/matricula.py#L50)); alias `certificacao → georreferenciamento` ([obs.py:212](../../app/services/observacao_registral.py#L212)) | Vocabulário de tipo mistura natureza do negócio, objeto da averbação, medida (`area_registrada`, [obs.py:70](../../app/services/observacao_registral.py#L70)) e ato-relação; sinônimos fundem espécies (retificação→aditivo [:247](../../app/services/observacao_registral.py#L247); cancelamento/quitação→baixa [:239–244](../../app/services/observacao_registral.py#L239-L244)); literal do LLM descartado ([:431–438](../../app/services/observacao_registral.py#L431-L438)); id de staging usado como cronologia ([reconciliation_decisions.py:784](../../app/services/reconciliation_decisions.py#L784)) |
| **relacao_ato** | `altera_ato` texto na origem; `baixado_por/retificado_por` escritos no JSON do destino ([obs.py:345–351](../../app/services/observacao_registral.py#L345-L351), [:481](../../app/services/observacao_registral.py#L481), [:495](../../app/services/observacao_registral.py#L495)) | Aresta com ids; `cancelamento` distinto; referência entre documentos e matrículas (só resolve rótulos da mesma lista, [:458–471](../../app/services/observacao_registral.py#L458-L471)) | `vigencia` com dois vocabulários: `Matricula.vigencia` vigente/historica ([matricula.py:122](../../app/models/matricula.py#L122)) × vigência do ato, 5 estados ([obs.py:193–197](../../app/services/observacao_registral.py#L193-L197)) | Um `baixado_por` por destino; o último sobrescreve ([:495](../../app/services/observacao_registral.py#L495)); aditivo e retificação fundidos |
| **arquivo_geo** | Não existe. [geo_files.py:68–94](../../app/services/geo_files.py#L68-L94) só detecta extensão/MIME e lista nomes do ZIP; upload marca `geoespacial` + `not_required` e para ([documents.py:296–314](../../app/api/v1/documents.py#L296-L314); [intake.py:995–1009](../../app/api/v1/intake.py#L995-L1009)) | Tudo: formato, componentes, CRS, hash por arquivo interno | — | `_GEOREF_DOC_TYPES` não contém `geoespacial` ([api/v1/regulatory.py:681–685](../../app/api/v1/regulatory.py#L681-L685) × [geo_files.py:30](../../app/services/geo_files.py#L30)): KMZ enviado não conta como georreferenciamento presente (#235) |
| **feicao** | `Property.geom` GEOMETRY/4674 ([property.py:30](../../app/models/property.py#L30); [e91d20acba9c:69–70](../../alembic/versions/e91d20acba9c_sprint_2_models.py#L69-L70)); dev 0/11 preenchidas; nenhum escritor | Tabela; arquivo de origem; id interno; tipo; geometria original + SRID; validade | MODELO_DE_DADOS dizia `geometry(Polygon)`; é GEOMETRY (corrigido neste PR) | Coluna usada só como booleano de presença ([api/v1/regulatory.py:637–648](../../app/api/v1/regulatory.py#L637-L648); [dossier.py:414–420](../../app/services/dossier.py#L414-L420)) |
| **medicao** | Não existe. Áreas escalares em `Property` ([property.py:25](../../app/models/property.py#L25), [:59–60](../../app/models/property.py#L59-L60)) e `Matricula.area_ha` ([matricula.py:66](../../app/models/matricula.py#L66)) | Tabela; objeto medido; fonte; método+versão; modelo de cálculo; unidade | `area_ha` com três sentidos; `area_declarada_ha` é área gráfica no CAR e declarada no ITR ([f01.py:478–484](../../app/services/ficha01_extraction.py#L478-L484), [:598](../../app/services/ficha01_extraction.py#L598)) | `area_grafica_ha` vem de texto do RAT, não de geometria ([f01.py:446](../../app/services/ficha01_extraction.py#L446)); `compare_areas` usa o **maior** valor como denominador e não registra qual ([property_audit.py:180–182](../../app/services/property_audit.py#L180-L182)) |
| **regra** | Não existe. Regras são funções Python com limiares fixos ([property_audit.py:34](../../app/services/property_audit.py#L34), [:50–72](../../app/services/property_audit.py#L50-L72), [:209–373](../../app/services/property_audit.py#L209-L373)); `regulatory_issue_catalog` (50 linhas) é vocabulário de saída ([regulatory.py:239–297](../../app/models/regulatory.py#L239-L297)) | id, versão, eixo, objetivo, UF, competência, predicados, condição, fonte normativa, dispositivo, origem | `familia` (11 famílias de cruzamento) não é `eixo` (8 eixos das matrizes) | `GEO_AUSENTE` é heurística e sai `critico` — severidade no lugar de certeza ([property_audit.py:297–312](../../app/services/property_audit.py#L297-L312)) |
| **conjunto_regras** | Não existe. Seed insere só com tabela vazia, sem versão ([regulatory_catalog_seed.py:230–242](../../app/models/regulatory_catalog_seed.py#L230-L242)); único snapshot versionado do código é `rota_versoes` ([rota.py:215–258](../../app/models/rota.py#L215-L258)) | Tudo: versão publicada, homologação, ativação por escopo, rollback | — | — |
| **avaliacao_regra** | `regulatory_issues` como substituto parcial (dev: 7 linhas, todas de código aposentado) | Estados não-disparados, faltantes, versão da regra, trilha | — | Dado ausente → `continue`: indeterminado vira "não disparou" ([property_audit.py:262–263](../../app/services/property_audit.py#L262-L263)); `status_achado` mistura conhecimento, revisão e saneamento ([regulatory.py:140–150](../../app/models/regulatory.py#L140-L150)) |
| **execucao** | `AgentExecution` + `case_snapshots` ([ev.py:10–19](../../app/models/evidence.py#L10-L19), [:68–83](../../app/models/evidence.py#L68-L83)) | Histórico de snapshots; `updated_at`; CHECK de status; FK de `AIJob.chain_trace_id` ([ai_job.py:76](../../app/models/ai_job.py#L76)) | — | `snapshot_id` trocado na retomada ([ca.py:262](../../app/services/connected_agents.py#L262)); status mistura ciclo, gate e capacidade ([ca.py:302–304](../../app/services/connected_agents.py#L302-L304)); chave idempotente opcional vira uuid aleatório ([ca.py:55](../../app/services/connected_agents.py#L55)); AIJob `completed` com resultado `awaiting_review` ([ca.py:241–242](../../app/services/connected_agents.py#L241-L242)) |
| **manifesto** | Dict em `AIJob.input_payload["manifest"]` ([ca.py:160–162](../../app/services/connected_agents.py#L160-L162); [agent_capabilities.py:16–50](../../app/services/agent_capabilities.py#L16-L50)). Manifesto de corpus (ADR-038) só como CSV em `data/corpus_manifesto/` | Tabela endereçada por hash; hash de skill **com** front-matter (hoje só corpo, [agent_capabilities.py:43](../../app/services/agent_capabilities.py#L43)); parâmetros efetivos (só `agent_name`, [ca.py:191](../../app/services/connected_agents.py#L191)); `rules[]`/`templates[]` sempre vazios; linha do manifesto de corpus gravada no documento | Três etiquetas de versão de contrato ("1.0", "069.1", política "069.1") | `base_prompt.version` é ora inteiro, ora hash ([ca.py:193](../../app/services/connected_agents.py#L193)); caminho legado `BaseAgent` não registra manifesto ([base.py:469–505](../../app/agents/base.py#L469-L505)) |
| **fonte_normativa** (zona normativa, documento) | `legislation_documents` ([legislation.py:53–127](../../app/models/legislation.py#L53-L127)), 113 linhas, só legislação; **282 fontes SEMAD existem só como chunks** | Linha de documento para SEMAD; `nivel_autoridade`; `status_validacao`; identidade por ato dentro dos 29 compêndios | `source_type='lei'` gravado para toda linha do manifesto ([scripts/ingest_manifesto.py:193](../../scripts/ingest_manifesto.py#L193), #234); `status` é processamento e colide com o futuro `status_validacao`; `revoked_at` = substituído por nós, não revogado ([legislation.py:79–83](../../app/models/legislation.py#L79-L83)) | `source_type` de chunk SEMAD é rótulo do LLM ([ingest_corpus_semad.py:329–330](../../scripts/ingest_corpus_semad.py#L329-L330)): 28 dos 36 `matriz_ipe` são fichas de tipologia; `demand_types/keywords/extra_metadata` são `json`, não `jsonb`; `keywords` nulo nos 113 |
| **dispositivo / fragmento normativo** | `knowledge_catalog` ([knowledge_catalog.py:75–135](../../app/models/knowledge_catalog.py#L75-L135)); `dispositivo` em 24.949 chunks, só legislação | FK chunk → documento (hoje `source_ref` texto); versão do texto normativo; chave estável de norma para a regra | Docstring diz Gemini; o banco tem 100% `text-embedding-3-small` ([knowledge_catalog.py:6](../../app/models/knowledge_catalog.py#L6)) | `confidence` do classificador SEMAD (0,8–1,0) no metadata parece validação e não é |

---

## 2. As três constraints no PostgreSQL 15

**Estado de partida:** nenhuma CHECK e nenhum trigger do app em todo o `alembic/versions`
(dev: só `spatial_ref_sys_srid_check` e o trigger de topologia do PostGIS). Tudo abaixo é novo.

**Pré-requisitos comuns**
1. Colunas **geradas** a partir de `content` em `evidence_versions` (ADR-070 §2). Sem elas, a
   CHECK teria de repetir o caminho JSON e a FK não teria coluna.
2. **Imutabilidade** (`BEFORE UPDATE OR DELETE → RAISE`) em `evidence_versions` e na tabela de
   arestas. Sem isso, um trigger de validação no insert não é garantia: a linha referida
   poderia mudar depois.
3. Tabela de arestas `evidence_premissa`, materializada por trigger a partir de `content.premises`.

| Invariante | Dá em constraint/trigger | Só dá na aplicação | Por quê | Custo |
|---|---|---|---|---|
| **`ausencia_verificada_no_escopo` sem `consulta_ref` é rejeitada** | ① `CHECK (knowledge_state IS DISTINCT FROM 'ausencia_verificada_no_escopo' OR consulta_object_id IS NOT NULL)`; ② FK composta `(tenant_id, process_id, consulta_object_id, consulta_version) → evidence_versions(tenant_id, process_id, object_id, version)`, `DEFERRABLE INITIALLY DEFERRED` — mesma consultoria, mesmo caso; ③ trigger `BEFORE INSERT`: a referida é `fonte_primaria` com `origin='consulta'` | Consulta **adequada** à pergunta (base certa, identificadores certos); limites da base; atualidade (muda no tempo → invalidação) | FK prova existência, não atributo da linha referida — daí o trigger; a imutabilidade impede o atributo de mudar depois | Por linha: desprezível. `ADD CONSTRAINT … NOT VALID` + `VALIDATE` (lock `SHARE UPDATE EXCLUSIVE`, sem bloquear escrita). Tabela quase vazia |
| **`risco` exige ≥1 premissa `fato_documental` e justificativa de aplicabilidade** | ① `CHECK (conclusion_class IS DISTINCT FROM 'risco' OR nullif(btrim(applicability_reason), '') IS NOT NULL)`; ② `CONSTRAINT TRIGGER … AFTER INSERT … DEFERRABLE INITIALLY DEFERRED WHEN (NEW.conclusion_class = 'risco')` que exige `EXISTS` aresta para versão com `conclusion_class = 'fato_documental'` | Premissa **aprovada e atual** — verificação no consumo, na montagem do envelope (ADR-069); suporte semântico do fato ao risco | CHECK não aceita subconsulta; "existe filho que satisfaz" é agregado → constraint trigger adiado para o fim da transação (as arestas nascem depois da linha). Aprovação **não** pode ser regra de escrita: o radar deixa o risco nascer "aguardando revisão" | Uma consulta indexada por conclusão de risco no commit. Divergência a alinhar: o Pydantic hoje isenta `nao_aplicavel` e exige `applicability == 'aplicavel'` ([sev.py:120–123](../../app/schemas/evidence.py#L120-L123)); a CHECK tem de espelhar exatamente a regra da app ou rejeita escrita válida |
| **`escopo_proposto` exige finalidade e passo de rota aprovado** | ① `CHECK (conclusion_class IS DISTINCT FROM 'escopo_proposto' OR (nullif(btrim(finalidade), '') IS NOT NULL AND rota_passo_id IS NOT NULL))`; ② FK `(tenant_id, rota_passo_id) → rota_passos(tenant_id, id)` (exige `UNIQUE(tenant_id, id)` aditivo em `rota_passos`); ③ trigger `BEFORE INSERT`: passo `validado`, `deleted_at IS NULL`, rota do **mesmo processo** | Passo que perde a aprovação ou é removido depois → **invalidação** do escopo (padrão ADR-068/069), não bloqueio; coerência finalidade × passo | `RotaPasso.status` e `deleted_at` são mutáveis ([rota.py:349](../../app/models/rota.py#L349), [:371](../../app/models/rota.py#L371)); bloquear a edição da Rota por haver escopo seria pior que invalidar. `rota_passos` não tem `process_id` — FK composta não atravessa `rotas`, daí o trigger | `finalidade` e `rota_passo_ref` **não existem** no contrato hoje; entram no `EvidenceObject` antes. Custo por linha desprezível |

**Esboço (dimensionamento, não migration):**

```sql
-- pré-requisito: coluna gerada + imutabilidade
ALTER TABLE evidence_versions
  ADD COLUMN knowledge_state text GENERATED ALWAYS AS (content->'knowledge'->>'state') STORED,
  ADD COLUMN conclusion_class text GENERATED ALWAYS AS (content->>'conclusion_class') STORED;
CREATE TRIGGER evidence_versions_imutavel BEFORE UPDATE OR DELETE ON evidence_versions
  FOR EACH ROW EXECUTE FUNCTION rejeitar_mutacao();
-- invariante 2, parte agregada
CREATE CONSTRAINT TRIGGER risco_exige_fato_documental AFTER INSERT ON evidence_versions
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
  WHEN (NEW.conclusion_class = 'risco') EXECUTE FUNCTION exigir_premissa_fato_documental();
```

**Ressalvas:** (a) FK sobre coluna gerada — confirmar em teste de migration (plano B: coluna
comum + trigger). (b) Triggers e colunas geradas são PostgreSQL-only; a suíte já roda em
PostgreSQL. (c) O `DEFERRABLE` exige que o serviço não faça `SET CONSTRAINTS ALL IMMEDIATE`.
(d) Nada disso substitui o gate de consumo do ADR-069.

**Por que no banco e não só no serviço:** o defeito que se quer matar é a escrita que contorna
o serviço — script de saneamento, SQL de correção direto em produção (já usado no wipe dos
casos 8/13), backfill, agente novo. O serviço continua validando primeiro; o banco é a
segunda linha.

---

## 3. O que a ontologia obriga a renomear

Contagem com `grep -rw`, formato `arquivos/ocorrências`, por backend (`app/`) · alembic ·
testes · frontend. "Consultas" = uso em filter/where/order_by/SQL cru.

**Regra geral:** nenhuma é `ALTER … RENAME` puro. Nome de coluna está gravado como dado em
`extracted_field_staging.target_field`, em toda chave de `field_sources`
([client.py:66](../../app/models/client.py#L66), [property.py:38](../../app/models/property.py#L38),
[matricula.py:95](../../app/models/matricula.py#L95)), em `lineage.campos`, na auditoria e nos
mapas do frontend (`fieldLabels.ts`, `historicoEventos.ts`). Toda troca é expandir → projetar →
contrair, com backfill da chave gravada.

| Nome atual | Alvo canônico | Tipo | Impacto | Consultas | Onde cabe |
|---|---|---|---|---|---|
| `Matricula.proprietarios` `[{nome,cpf}]` ([matricula.py:90](../../app/models/matricula.py#L90)) — alimentado por cadeia da certidão, `detentor` do CCIR e `proprietario` do SIGEF | observação literal → `participacao` (adquirente/transmitente) → conclusão `titular_atual` | split + relação nova | 12/31 · 2/2 · 6/38 · 2/5 | 0 ORM; SQL cru em [f2a4c6e8b0d2:37,50–56](../../alembic/versions/f2a4c6e8b0d2_sprint3_matricula_field_sources.py#L37-L56) | **Incremento 2** (é o núcleo) |
| `proprietario` (SIGEF) ([f01.py:607](../../app/services/ficha01_extraction.py#L607)) | literal de `sigef_documental` + participação com papel não resolvido | split | 1/5 · 0 · 2/6 · 0 | 0 | Incremento 2 |
| `titular_atual` ([obs.py:697–721](../../app/services/observacao_registral.py#L697-L721)) e "titular" = Client | conclusão temporal (direito, fração, cadeia, cobertura, data) × `cliente` | redefinição semântica | `titular` 19/60 · 2/2 · 7/28 · 4/8 | 0 | Incremento 2 |
| `cartorio` texto ([matricula.py:49](../../app/models/matricula.py#L49)) | `serventia` (entidade) | relação nova | 10/23 · 3/3 · 18/57 · 4/11 | SQL cru em f2a4c6e8b0d2:34 | Incremento 2 |
| `registro_livro_folha_ficha` ([matricula.py:50](../../app/models/matricula.py#L50)) | livro, folha, ficha separados | split | pequeno | 0 | Incremento 2 |
| `onus_gravames`, `averbacao_app`, `averbacao_rl` (texto, [matricula.py:84–86](../../app/models/matricula.py#L84-L86)) | `ato_registral` + `relacao_ato` (+ `area_averbada` como medição) | relação nova | 8/15 · 11/22 · 10/19 (backend) | 0 | Incremento 2 |
| alias `certificacao → georreferenciamento` ([obs.py:212](../../app/services/observacao_registral.py#L212)); `geo_certificacao_codigo` recebe também resumo de coordenadas ([f01.py:435](../../app/services/ficha01_extraction.py#L435)) | `certificacao_sigef` separado de `georreferenciamento` | remover alias + split | alias 1 linha; `geo_certificacao_*` 21 arquivos/48 | 0 | Incremento 2 (literal perdido não volta) |
| `Matricula.vigencia` vigente/historica ([matricula.py:122](../../app/models/matricula.py#L122)) | situação na linhagem (nome distinto da vigência do ato) | rename | `vigencia` 15/76 · 1/3 · 9/48 · 5/11 (inclui a do ato) | 0 | Incremento 2 |
| `Property.has_embargo` bool, default Python False ([property.py:32](../../app/models/property.py#L32)) | estado de conhecimento + relação embargo (fonte, órgão, auto) | split + relação | 7/22 · 1/1 · 3/6 · 5/15 | 0 | Incremento 2 (sem DDL: a coluna já é nula e sem default no banco) |
| `car_status` texto ([property.py:23](../../app/models/property.py#L23)) | situação de `car_documental` com fonte e data | split | 11/26 · 1/1 · 4/5 · 5/7 | 0 | Incremento 2 (consumidor no 4) |
| `total_area_ha`, `area_documental_ha`, `area_grafica_ha`, `Matricula.area_ha`, chave `area_declarada_ha` | `medicao` qualificada (natureza, objeto, fonte, método) | split | `total_area_ha` 20/53 · 1/1 · 11/30 · 10/31; `area_ha` 18/55 · 3/4 · 27/140 · 7/17; documental 11/22; gráfica 10/17 | 1 ORM ([confronto_identidade.py:147](../../app/services/confronto_identidade.py#L147)) | **Incremento 3** (entra com `medicao`); colunas ficam como projeção |
| `Property.registry_number` ([property.py:19](../../app/models/property.py#L19)) — com `UNIQUE(tenant_id, registry_number)` no banco que o model não declara ([a7b8c9d0e1f2:130–134](../../alembic/versions/a7b8c9d0e1f2_add_fk_cascade_rules_and_unique_registry.py#L130-L134)) | projeção de matrícula (serventia + número) | drop → projeção | 12/27 · 2/5 · 4/11 · 4/10 | SQL cru a7b8c9d0e1f2:20 | **Frente própria** (a UNIQUE impede imóvel com várias matrículas) |
| `process_type` texto ([process.py:106](../../app/models/process.py#L106)) × `demand_type` enum ([process.py:127](../../app/models/process.py#L127)) | `objetivo_atendimento` validado × `demanda` classificada | split | `process_type` 17/40 · 1/1 · 80/112 · 2/2; `demand_type` 49/357 · 8/37 · 50/131 · 18/46 | ~17 ORM + SQL cru | **Frente própria** (maior impacto do inventário; `demand_type` também é coluna em rotas, checklist, workflow e contract templates) |
| `Risco.grau`/`Risco.severidade` + 5 escalas de severidade + 5 de confiança | certeza, impacto, urgência, probabilidade separadas | split | `severity` 25/102 · 4/21 · 15/76 · 12/36; `confidence` 36/153 · 2/12 · 28/94 · 15/67 | 0 (JSON) | **Incremento 4** (motor jurídico; Q-ISIS-07 respondida) |
| `PecaJuridicaContent` ([stage_output.py:375](../../app/schemas/stage_output.py#L375)) | catálogo `tipo_de_peca` | rename + split | 3/16 · 0 · 3/14 · 1/1 | 0 | Incremento 5 |
| `Contract` (modelo comercial, [contract.py:21](../../app/models/contract.py#L21)) | `contrato_comercial` | rename de classe | 14/72 · 0 · 4/12 · 1/2 | ~17 ORM | **Não fazer** agora: ganho só de nome; qualificar na documentação |
| `Contract` (base de schema, [sev.py:23](../../app/schemas/evidence.py#L23)) | nome técnico (ex.: `StrictModel`) | rename puro | 1/9 | 0 | Qualquer PR (trivial) |
| `Property.client_id` ([property.py:16](../../app/models/property.py#L16)) | vínculo comercial, **não** domínio | semântica, sem rename | 50/346 · 7/34 · 86/279 · 14/68 | muitas | Incremento 2 (documentar + participação; não renomear) |
| colunas `status` que misturam eixos (staging, `Process`, `Client`, `status_achado`, `status_saneamento`, `rl_status`, `Rota`, `extraction_status`) | eixos R / K / processamento / atendimento / comercial / vigência separados | split | `ExtractedFieldStatus` 10/48 · 0 · 26/114; `ProcessStatus` 10/99 · 1/2 · 77/242 | `Process.status` 18; staging 9 | Staging no **Incremento 2**; `Process.status` e `Client.status` em **frente própria** |

**Fora da lista, sem ocorrência:** `owner`, `comprador` (0); `vendedor` (1, texto de UI); `dono` (só comentário).

---

## 4. Caminho de migração por grupo

Regra dura: **nenhum backfill inferido**. "Backfill permitido" abaixo é só **cópia ou
medição do que foi registrado** (texto gravado, hash recalculável dos bytes que existem, id
que o registro já aponta), sempre marcado `legado`/`legacy_unverified`.

| Grupo | `ALTER` aditivo | Backfill permitido | Exige decisão humana | Não volta | Janela? |
|---|---|---|---|---|---|
| **1. Documentos e extrações** | `CREATE documento_versao, fragmento, evidence_premissa`; colunas geradas e imutabilidade em `evidence_*`; `extracted_field_staging.observacao_ref` nulo | 1 versão `legado` por documento com o `extracted_text` atual, `checksum_sha256` (recalculado dos bytes do bucket onde faltar), `extracted_at`, método do AIJob quando ligado; fragmento **só** onde a âncora gravada casa com esse texto; staging → observação `legacy_unverified` sob demanda (já existe) | Reextração paga dos originais; o que fazer com documento cujo objeto sumiu do bucket | Página, papel, trecho e data não registrados; texto anterior a re-OCR; origem de cópia de gêmeo | **Não.** Tabelas novas; backfill em lote idempotente fora de pico |
| **2. Pessoas e atos** | `CREATE pessoa, pessoa_identificador, espolio, participacao, serventia, ato_registral, relacao_ato`; `Client.pessoa_id`, `Matricula.serventia_id` nulos | `pessoa` a partir de `Client` (identidade declarada no cadastro) com `cpf_cnpj`; participação de representação a partir de `ClientRepresentative` + `source_document_id`; `ato_registral` a partir de staging tipado com `ato` literal e matrícula resolvida; `relacao_ato` só onde `altera_ato` resolveu rótulo explícito | Fusão de pessoas duplicadas; serventia de cada `cartorio` texto; menções em `proprietarios` ficam **pendentes de revisão**, nunca viram participação | Papel de quem está em `proprietarios`; literal do tipo de ato descartado; cronologia onde `ordem` era id; baixas sobrescritas | **Não** |
| **3. Conclusões antigas** | Nenhum novo; `RegulatoryDiagnosis`, `RegulatoryIssue`, `StageOutput` viram leitura legada | Importar como `legacy_unverified` com texto, fonte conhecida e cobertura explícita; revisões legadas como eventos com o autor/data gravados | Nenhuma importação vira aprovada; consultor reabre o que precisar | Snapshot do que o LLM leu; `completed` não é aprovação; fonte inventada `ai_job:N` não vira fonte | **Não** |
| **4. `has_embargo=False`** | **Nenhum DDL**: a coluna já é nula e sem default no banco (`is_nullable=YES`, default nulo). Remover o default do ORM ([property.py:32](../../app/models/property.py#L32)) e dos schemas ([schemas/property.py:19](../../app/schemas/property.py#L19)); embargo vira observação/consulta | Onde a auditoria registrar que uma pessoa marcou o campo, preservar como **declaração** com autor e data (dev: 0 registros em `audit_logs`) | Anular os falsos legados ou congelar a coluna (dev: 11/11 falsos) | Distinguir "alguém disse não" de "default" quando não há trilha | **Não** |
| **5. Valores cadastrais** | Proveniência como referência: decisão/evidência que gravou o valor | Ligar o valor atual à linha de staging/decisão que `field_sources` já registra | Identidade corrompida e duplicados históricos | Valor sem `field_sources`: fonte desconhecida, marcada como tal | Expansão **não**; **contração sim** (remover `registry_number`, colunas de área, `proprietarios` exige API + worker + frontend na mesma versão) |
| **6. Regras** | `CREATE regra, regra_versao, conjunto_regras, conjunto_regras_item, avaliacao_regra` vazias | Nenhum a partir do Python; regra Python só vira `regra_versao` se a Ísis homologar a equivalência | Homologação; PENDENTE-1 a 5 do ADR-042; catálogo global ou por tenant | Avaliações passadas: "não disparou" histórico não separa indeterminado | **Não** |
| **7. Geometria** | `CREATE arquivo_geo, feicao, medicao`; `Property.feicao_escolhida_id` nulo | Ingerir originais que existem no storage (dev: 0 arquivos geo; produção: medir); área textual existente vira medição **declarada** com a fonte registrada | Tolerância (Q-ISIS-04); método (ADR-071); qual feição representa o imóvel | Número de área não reconstrói polígono; área sem fonte | **Não** |
| *Zona normativa (fora dos sete)* | `ADD COLUMN nivel_autoridade, status_validacao` em nível de documento; linha de documento para as 282 fontes SEMAD | Classificação por regra determinística sobre campo gravado (nome de arquivo, espécie), registrada como derivação com método e **mantida `bruto`**; o que não casa fica `nao_determinado` | Tipologias SEMAD como exigência ou procedimento; 8 manuais; valores de `status_validacao` | Autoridade dos 29 compêndios sem re-derivar o ato | **Não** (fast default, ver §7) |

---

## 5. Ordem de migração

Cada passo é aditivo e deixa o sistema funcionando: o código antigo continua lendo o que lia,
um adaptador serve a UI legada, e só há uma escrita canônica por vez. Passos 1–10 são
reversíveis removendo o que entrou; só o 11 não volta.

| # | Passo | Depende de | Mantém funcionando porque… | Incremento |
|---|---|---|---|---|
| 0 | **Medir**: extensões e versões de produção (#236); `069ce001` aplicada em produção?; contagem por tabela em produção; inventário de consumidores de cada coluna a contrair | — | só leitura | antes do 2 |
| 1 | Imutabilidade + colunas geradas + CHECK de `kind` e `action` em `evidence_*`; `execucao_snapshot`; tabela `manifesto` | 0 | tabelas do #172 são novas e pequenas; o serviço já só insere | 2 |
| 2 | `documento_versao` + `fragmento`; backfill da versão `legado`; OCR/áudio passam a gravar versão e atualizar `extracted_text` como projeção na mesma transação | 1 | `extracted_text` continua existindo para quem lê | 2 |
| 3 | `evidence_premissa` + invariantes 1 e 2 (`NOT VALID` → `VALIDATE`) | 1, 2 | constraints só afetam escrita nova; validação sem bloquear | 2 |
| 4 | `pessoa`/`espolio`/`participacao` + `serventia`/`ato_registral`/`relacao_ato`; extrator grava observação apontando as entidades; staging recebe `observacao_ref` e vira projeção | 2, 3 | Conferência continua lendo staging; o adaptador projeta a partir da observação | 2 |
| 5 | `has_embargo` sem default; consumidores leem o eixo de conhecimento | 4 | coluna continua existindo | 2 |
| 6 | `arquivo_geo`/`feicao`/`medicao` + ingestão KMZ/KML; `Property.geom` e áreas viram projeção | 2 | colunas de área continuam como projeção | 3 |
| 7 | `fonte_normativa` para as 282 fontes SEMAD + `nivel_autoridade`/`status_validacao` no documento; classificação determinística | — (independente; pode correr em paralelo desde o 1) | coluna nova com default constante; busca não filtra por ela | 4 (pode antecipar) |
| 8 | `regra`/`regra_versao`/`conjunto_regras`/`avaliacao_regra`; `property_audit` passa a gravar avaliação com os seis estados | 3, 7 | catálogo de alertas continua como vocabulário de saída | 4 |
| 9 | `finalidade` + `rota_passo_ref` no contrato; invariante 3 | 3 | só `escopo_proposto` novo é afetado | 5 |
| 10 | Cada consumidor migra para a leitura nova, com prova (teste + gate de navegador onde há UI) | 4–9 | adaptador cobre o resto | 2–5 |
| 11 | **Contração**: remover escritas e depois colunas legadas (`staging.status` como revisão, `proprietarios`, `registry_number`, áreas achatadas, `has_embargo`) | 10, por coluna | — | **janela**; backup; API + worker + frontend na mesma versão; irreversível |

---

## 6. Geometria — o levantamento que faltava

**Extensões.** Dev (medido): `postgis 3.3.4` (GEOS 3.9.0, PROJ 7.2.1), `postgis_topology`,
`postgis_tiger_geocoder`, `fuzzystrmatch`, `vector 0.8.2`, `plpgsql`; topology/tiger vêm da
imagem `postgis/postgis:15-3.3`, não de migration. As migrations criam só `postgis`
([e91d20acba9c:25](../../alembic/versions/e91d20acba9c_sprint_2_models.py#L25)) e `vector`
([f9d2e8c1a4b3:29](../../alembic/versions/f9d2e8c1a4b3_sprint_u_knowledge_catalog.py#L29)).
**Produção: não medido.** O repositório só tem afirmações ([render.yaml:13](../../render.yaml#L13),
[DEPLOY_REGENTE.md:61–74](../DEPLOY_REGENTE.md#L61-L74) pede para validar e não registra o
resultado). Inferência indireta: se o preDeploy rodou `e91d20acba9c`, `postgis` existe;
versão desconhecida (#236).

**O que `geo_files.py` faz com KMZ/KML.** Só identifica: extensão/MIME
([:68–77](../../app/services/geo_files.py#L68-L77)) e nomes dentro do ZIP
([:80–94](../../app/services/geo_files.py#L80-L94)). O upload marca `geoespacial` +
`not_required` e para. Nada descompacta, lê o KML, extrai coordenada, calcula área ou grava
`geom`. Nenhuma função `ST_*` é chamada em `app/`. Dev: 0 documentos geoespaciais.

**Área em CRS métrico — opções:**

| Método | Como | Distorção | Custo | Uso |
|---|---|---|---|---|
| **Geodésico no elipsoide** | `ST_Area(geom::geography)` sobre 4674 (GRS80) | nenhuma de projeção; não precisa de zona | zero: PostGIS já instalado | **método v1 canônico** (proposta ao ADR-071) |
| UTM SIRGAS 2000 por centróide | `ST_Transform` para EPSG 31978–31985 (zonas 18S–25S; 31981–31985 conferidas em dev) | fator de escala: da ordem de 0,1% na área, maior perto da borda do fuso; escolha de zona na divisa é regra | zero | alternativo, quando o documento declara UTM (dívida #76: matrícula em UTM × SIGEF geodésico) |
| Sistema Geodésico Local | projeção topocêntrica por parcela | referência da certificação SIGEF (**confirmar trecho da norma técnica do Incra antes de homologar**) | SRS customizado ou pyproj | alternativo, para reproduzir área certificada |
| ~~Albers~~ | `102033` em dev é **SAD69**; `5880` é Policônica (não preserva área) | — | — | descartado |

**Bibliotecas.** Presentes: `geoalchemy2 0.19.0`, `lxml 6.1.0`. Ausentes: shapely, pyproj,
fiona, fastkml, GDAL, geopandas, pykml. Mínimo viável: `zipfile` (stdlib) com limite de
descompressão + parser XML protegido contra XXE para o KML (KML é sempre lon/lat WGS84) +
`ST_GeomFromKML`/`ST_GeomFromGeoJSON`/`ST_IsValid`/`ST_MakeValid` no PostGIS. Shapefile exige
leitor (`pyshp`, Python puro) e resolução do `.prj` (`pyproj`); GDAL no container é
desproporcional. Transformação WGS84 → SIRGAS 2000 é submétrica e deve constar no método.

**`grade_overlap_severity` ([property_audit.py:75–84](../../app/services/property_audit.py#L75-L84)).**
Não recebe argumento e retorna sempre `critico`; nenhum chamador de produção, só
[test_property_audit.py:245](../../tests/services/test_property_audit.py#L245). **Não serve** para
overlay: interseção, camada identificada, área e percentual precisam ser escritos. O que
sobra é uma política ("qualquer sobreposição é crítica") — candidata a `regra_versao` a
homologar; a função sai quando a regra entrar. **Refaz.**

**Mesmo arquivo, a corrigir no Incremento 3:** `compare_areas` usa `max(a, b)` como
denominador e não registra qual ([:180–182](../../app/services/property_audit.py#L180-L182)); a
Ísis usa a área documental. E área zero derruba o auditor (#233).

---

## 7. Zona normativa — o que muda no corpus atual

**Medido em dev:** 32.161 chunks de **395** fontes: 113 de legislação (30.967 chunks, com linha
em `legislation_documents`) + **282 PDFs SEMAD-GO (1.194 chunks) sem linha de documento**.
Compêndios (`compendio_regente`) são 29 documentos e 22.725 chunks (70,7%).

**Dá para classificar retroativamente?** Em parte.

| Balde | Documentos | Chunks | Como |
|---|---|---|---|
| Determinável do que está gravado | 339 | 6.168 (19,2%) | norma por espécie (74 docs); interpretação por identificador (1: OJN 06/2009 PFE-IBAMA, gravada como `lei`); exigência por nome de arquivo (256: 223 tipologias, 6 matrizes IPE, 27 TR/gabarito); procedimento (8) |
| Exige releitura | 56 | 25.993 (80,8%) | **29 compêndios**: identidade do ato por chunk tem de ser re-derivada dos cabeçalhos embutidos no texto (engenharia, não leitura humana); **8 manuais/coletâneas**: classificação humana; 18 PDFs SEMAD diversos; 1 referência bibliográfica (doutrina, fora dos seis níveis) |
| precedente / radar | 0 | 0 | fontes ainda não ingeridas (INS-005 indeferimentos, INS-006 SEI) |

Só o **nome do arquivo** separa tipologia de matriz IPE; `licenca_codigo` foi extraído por LLM e
não distingue. Tipologia ser exigência ou procedimento é **uma** decisão de domínio para a
classe inteira, não releitura por documento. A espécie foi perdida para toda linha do
manifesto: `ingest_manifesto.py:193` grava `lei` fixo (#234).

**Custo de `status_validacao` nascendo `bruto`:**

| Operação | Reescreve? | Lock | Custo aqui |
|---|---|---|---|
| `ADD COLUMN status_validacao varchar NOT NULL DEFAULT 'bruto'` | não (default constante do PG11+: `attmissingval`) | `ACCESS EXCLUSIVE` por milissegundos — usar `lock_timeout`, porque fila atrás de busca em curso | ~0. Precedente no próprio banco: `legislation_documents.fonte_oficial` (`atthasmissing = t`) |
| `ADD CONSTRAINT … CHECK … NOT VALID` + `VALIDATE` | não | breve + `SHARE UPDATE EXCLUSIVE` | menos de 1 s em 69 MB de heap |
| `UPDATE` em massa dos 32 mil chunks | sim (tupla nova por linha, entrada nova nos 11 índices, **inclusive o ivfflat de 249 MB**) | `ROW EXCLUSIVE` | inchaço + VACUUM — **motivo para classificar no documento**, não no chunk |

**Onde a coluna mora:** no documento, com o chunk herdando por junção (como a vigência já faz).
No chunk ela zeraria a cada reindex (ADR-041) e se multiplicaria por provider (ADR-040).
**O que `bruto` não pode fazer:** sumir da busca (ADR-037) nem sair da contagem de cobertura
(ADR-036, [auto_infracao_extraction.py:229–247](../../app/services/auto_infracao_extraction.py#L229-L247)).
Nome: `legislation_documents.status` já é estado de processamento — o novo campo não pode se
chamar `status`.

---

## 8. Achados laterais (registrados, fora do escopo desta frente)

| Dívida | Achado | Evidência |
|---|---|---|
| **#233** | `audit_property` levanta `TypeError` quando uma área do par é 0: `compare_areas` devolve `diff_pct=None` e a descrição faz `None * 100` | [property_audit.py:262–275](../../app/services/property_audit.py#L262-L275) com [:173–178](../../app/services/property_audit.py#L173-L178). Caminho confirmado lendo o código; não reproduzido |
| **#234** | `ingest_manifesto.py` grava `source_type="lei"` para toda linha do manifesto: decretos, IN e a OJN 06/2009 viram `lei` | [scripts/ingest_manifesto.py:193](../../scripts/ingest_manifesto.py#L193) |
| **#235** | KMZ/KML enviado recebe `document_type="geoespacial"`, que não está em `_GEOREF_DOC_TYPES`: a nota diz "geom indisponível" em vez de "georreferenciamento presente" | [geo_files.py:30](../../app/services/geo_files.py#L30) × [api/v1/regulatory.py:681–685](../../app/api/v1/regulatory.py#L681-L685) |
| **#236** | Extensões e versões do banco de produção nunca foram medidas e registradas | [DEPLOY_REGENTE.md:61–74](../DEPLOY_REGENTE.md#L61-L74) pede; nenhum resultado no repositório |

Também observado, sem dívida nova: tabelas `t_frentel_probe`/`t_frentel_probe2` no banco dev
sem referência no repositório.
