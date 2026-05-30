# Modelo de Dados

**Documento:** Arquitetura · referência viva
**Estado:** atualizar a cada migration que altere entidade-chave
**Última revisão:** 2026-05-15
**Verificado em:** 40 migrations aplicadas, 28 entidades ORM ativas

---

Esquema completo do banco do Regente Ambiental. Toda mudança aqui passa por migration Alembic — `Base.metadata.create_all()` é proibido fora de teste.

## Princípios de modelagem

1. **Multi-tenant por linha.** Toda tabela transacional tem `tenant_id INT NOT NULL REFERENCES tenants(id)`. Exceção: `pre_cadastros` (lead anônimo).
2. **Arquivo pesado fora do banco.** O banco guarda apenas metadado + referência ao objeto no MinIO.
3. **Geodados nativos.** `Property.geom` é `geometry(Polygon, 4674)` (SIRGAS 2000), usando PostGIS.
4. **RAG no Postgres.** `knowledge_catalog.embedding` é `vector(768)` (pgvector). Sem serviço vetorial externo. Dim 768 foi escolhida pra compatibilidade histórica (base inicial gerada com Gemini `text-embedding-004`); OpenAI `text-embedding-3-small` é hoje usado com `dimensions=768` explícito.
5. **JSON onde a estrutura varia.** Campos como `Client.field_sources`, `AIJob.result`, `StageOutput.content_data` usam JSONB.
6. **Auditoria total.** `AuditLog` registra hash chain SHA-256 para mudanças relevantes.
7. **Soft delete onde a recuperação importa.** Tabelas críticas têm `deleted_at` em vez de DELETE físico.

## Schema overview

```
                              ┌──────────────┐
                              │   tenants    │
                              └──────┬───────┘
                                     │
        ┌────────────┬────────────┬──┴────────┬──────────────┐
        ▼            ▼            ▼            ▼              ▼
   ┌────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐
   │ users  │  │ clients  │  │properties│  │processes │  │ai_jobs   │
   └────────┘  └────┬─────┘  └────┬────┘  └─────┬────┘  └──────────┘
                   │              │              │
                   │              │              ├──tasks
                   │              │              ├──documents
                   │              │              ├──proposals
                   │              │              ├──contracts
                   │              │              ├──regulatory_diagnosis
                   │              │              └──stage_outputs
                   │              │
                   └──────────────┴── property_clients (N-N)
```

## Entidades (agrupadas por área)

### Núcleo organizacional

| Entidade | Tabela | Função |
|---|---|---|
| `Tenant` | `tenants` | Empresa/consultoria que opera no Regente. Tem `ai_monthly_budget_usd` (override por tenant). |
| `User` | `users` | Usuário do sistema. Perfil em `User.role` (consultor, admin, cliente, etc). |

### Cadastro (entrada — Princípio 3 do manifesto)

| Entidade | Tabela | Função |
|---|---|---|
| `Client` | `clients` | Cliente da consultoria (PF/PJ). Tem `field_sources` (JSONB) marcando origem de cada campo: manual / extraído / confirmado. |
| `Property` | `properties` | Imóvel rural. `geom` (PostGIS polígono SIRGAS 2000). Hoje vazia em todas as 9 propriedades — pendência. |
| `PreCadastro` | `pre_cadastros` | Lead da landing. **Sem `tenant_id`** (lead anônimo). |

### Processo (núcleo transacional)

| Entidade | Tabela | Função |
|---|---|---|
| `Process` | `processes` | Caso da consultoria. Máquina de estados de 11 estados (`lead → triagem → diagnostico → planejamento → execucao → protocolo → aguardando_orgao → pendencia_orgao → concluido → arquivado`; mais `cancelado`). |
| `Macroetapa` | `macroetapa_*` | 7 macroetapas conforme briefing 29/04. Engine em `app/services/macroetapa_engine.py`. |
| `ChecklistTemplate` | `checklist_templates` | Templates de checklist documental por `demand_type`. |
| `WorkflowTemplate` | `workflow_templates` | Trilha regulatória por demand_type. Engine em `app/services/workflow_engine.py`. |
| `Task` | `tasks` | Tarefa atrelada a processo. Kanban no painel. |
| `IntakeDraft` | `intake_drafts` | Rascunho do Intake (5 passos do wizard). Commit gera Process. |
| `IntakeClassificationFeedback` | `intake_classification_feedback` | Registro de divergência entre classificação IA × consultor. Loop de aprendizado. |

### Coleta documental (organização — Princípio 3)

| Entidade | Tabela | Função |
|---|---|---|
| `Document` | `documents` | Metadado + referência MinIO. Tem `extracted_text` (cache de OCR) e `doc_type` (matricula, car, ccir, oficio, etc.). |
| `DocumentCategory` | `document_categories` | Taxonomia de categorias documentais. |

### Diagnóstico (inteligência — Princípio 3)

| Entidade | Tabela | Função |
|---|---|---|
| `RegulatoryDiagnosis` | `regulatory_diagnoses` | Diagnóstico técnico-regulatório do caso. Versionado por processo (`(process_id, version)` único — sprint A1-D1). Tem `validated_by_user_id` + `validated_at` para a **camada 1 do Princípio 1** (consultor assina; PROMPT_4 Onda B). |
| `RegulatoryIssue` | `regulatory_issues` | Inconsistência detectada no imóvel. Taxonomia rica (PROMPT_5) + 2 status perenes (PROMPT_6 + ADR-012). Detalhes na subseção abaixo. |
| `RegulatoryIssueCatalog` | `regulatory_issue_catalog` | **Catálogo evolutivo** de `codigo_alerta` (PROMPT_5). PK = `codigo_alerta` string (45 entradas seed). Adicionar código novo é `INSERT`, **não migration de schema**. Vocabulário canônico da skill `auditor_imovel/analise_divergencias_documentais` v1.1.0. |
| `ProcessIssueDecision` | `process_issue_decisions` | **Decisão contextual** do consultor sobre uma `RegulatoryIssue` no contexto de um `Process` (PROMPT_7 — ADR-012). FK composta `(process_id, issue_id)` única. Detalhes na subseção abaixo. |
| `ProcessDecision` | `process_decisions` | Decisões tomadas no caso (escolha de caminho regulatório, mudança de estratégia). |
| `StageOutput` | `stage_outputs` | Output estruturado de cada macroetapa. `content_data` (JSONB) validado por `StageOutputContent` (Pydantic, opt-in nos agentes). |

#### `RegulatoryIssue` — taxonomia rica + 2 status perenes

Anatomia atual da tabela (após PROMPT_5 + PROMPT_6 + PROMPT_7):

**Identificação (PROMPT_5 Onda A):**
- `codigo_alerta` (`String(80)`, FK → `regulatory_issue_catalog.codigo_alerta`, nullable só por retrocompat com registros antigos). Identifica o "tipo exato" do alerta (`AREA_MATRICULA_X_CAR`, `GEO_AUSENTE`, etc.).
- `familia` (Enum `regulatory_familia`, 11 valores: `identificacao` / `titularidade` / `area` / `geoespacial` / `geo_incra` / `car` / `ambiental` / `fiscal` / `restricao_risco` / `licenciamento` / `validade_documental`). Enum estável; acréscimo de família é decisão arquitetural.

**Severidade (PROMPT_5 — sai o colapso 3→3):**
- `severity` (Enum `regulatory_severity_v2`, 4 valores: `informativo` / `atencao` / `alto` / `critico`). Substituiu o enum antigo de 3 (`info`/`warning`/`critical`). A migração mapeou `info→informativo`, `warning→atencao`, `critical→alto`. **Só `critico` dispara o gate da camada 2** (PROMPT_6).

**2 status PERENES (PROMPT_6 + ADR-012 / PROMPT_7):**
- `status_achado` (Enum `regulatory_status_achado`, 5 valores: `suspeita` default / `confirmada` / `descartada` / `resolvida` / `ignorada`) — **natureza do indício** ("auditor errou ou é real?"). É fato do imóvel, não muda com o processo.
- `status_saneamento` (Enum `regulatory_status_saneamento`, 5 valores: `pendente` default / `em_validacao` / `saneado` / `descartado` / `nao_aplicavel`) — **saneamento REAL no mundo**. Se a matrícula foi de fato corrigida no cartório, vale para todos os processos.

> **A decisão do consultor (`decisao`/`justificativa`/`at`) MIGROU** para
> `ProcessIssueDecision` no PROMPT_7 (ADR-012) — é contextual ao processo,
> não perene no imóvel.

**Overrides do catálogo (PROMPT_5 Onda A):**
- `muda_rota_regulatoria` (`Boolean`, nullable) — override do default do catálogo.
- `muda_escopo_preco_prazo` (`Boolean`, nullable) — override.
- `documentos_cruzados` (`PortableJSON`, lista de strings) — override.

**Legados / deprecated:**
- `type` (Enum `regulatory_issue_type`, nullable, 5 valores: `area_divergente` / `sobreposicao_app` / `sobreposicao_reserva` / `poligono_fora_matricula` / `outro`) — **DEPRECATED** desde PROMPT_5. Mantido nullable para retrocompat de leitura. Novos registros têm `type=None` + `codigo_alerta` preenchido.

**Migrations relevantes:**
- `a8e1d4c7f3b6` (A1) — cria `regulatory_issues` + enums originais.
- `c1b2d3e4f5a7` (PROMPT_5) — `regulatory_issue_catalog` + colunas ricas + migra `severity` 3→4.
- `d2c3e4f5a6b8` (PROMPT_6) — 3 enums dos status reconciliados + 5 colunas.
- `e3d4f5g6a7b8` (PROMPT_7) — cria `process_issue_decisions`; dropa as 3 colunas de decisão do `RegulatoryIssue` (ADR-012).

#### `ProcessIssueDecision` — decisão contextual ao processo (ADR-012)

Nova entidade introduzida pelo PROMPT_7. Anatomia:

**Identificação:**
- `id` (PK).
- `tenant_id` (FK `tenants.id` ondelete=RESTRICT, indexed) — tenant isolation.
- `process_id` (FK `processes.id` ondelete=CASCADE, indexed).
- `issue_id` (FK `regulatory_issues.id` ondelete=CASCADE, indexed).
- **UNIQUE** `(process_id, issue_id)` — uma decisão por par.

**Conteúdo:**
- `decisao` (Enum `regulatory_decisao_consultor`, **NOT NULL**, 5 valores = **os 5 botões P4**: `corrigir_antes` / `seguir_com_ressalva` / `solicitar_doc` / `fora_escopo` / `ignorar_justificado`).
- `justificativa` (`String`, nullable). **Obrigatória** quando `decisao in {ignorar_justificado, fora_escopo}` (validator no schema `ProcessIssueDecisionCreate`).
- `decided_by_user_id` (FK `users.id` ondelete=SET NULL, nullable) — autor da decisão (Princípio 2 — explicito além do AuditLog).
- `decided_at` (`DateTime`, NOT NULL) — server-side em toda criação/atualização.

**Por que separada de `RegulatoryIssue`** (ADR-012): a sócia (Isis) validou em 26/05 que cada trabalho recomeça do zero. Titularidade torta pesa diferente para vender e para dar como garantia ao banco; não dá pra herdar decisão. O fato da divergência é perene (Property), mas a avaliação é contextual.

**Endpoints:**
- `GET /api/v1/processes/{pid}/issues/{iid}/decision` — lê (404 se não existe; cada processo recomeça).
- `PUT /api/v1/processes/{pid}/issues/{iid}/decision` — upsert. AuditLog granular por campo com hash chain SHA-256.

**Gate camada 2 do Princípio 1** (PROMPT_6 + ADR-012): o `PATCH /processes/{id}/diagnoses/{version}/validate` cruza issues críticas × `ProcessIssueDecision` **deste processo**. Decisão tomada em outro processo da mesma property **não** libera o gate.

### Comercial

| Entidade | Tabela | Função |
|---|---|---|
| `Proposal` | `proposals` | Proposta comercial gerada por `proposal_generator.py`. |
| `Contract` | `contracts` | Contrato gerado por `contract_generator.py`. |
| `ContractTemplate` | `contract_templates` | Templates de contrato (white-label por tenant). |

### Comunicação e tarefa

| Entidade | Tabela | Função |
|---|---|---|
| `Communication` | `communications` | E-mails, threads do portal cliente, mensagens internas. |
| `Thread` | `threads` (via `Communication`) | Conversa agrupada por contexto. |

### IA — execução e configuração

| Entidade | Tabela | Função |
|---|---|---|
| `AIJob` | `ai_jobs` | Toda chamada LLM. Tem `agent_name`, `entity_type`/`entity_id`, `result` (JSONB), `cost_usd`, `tokens_in/out`, `model_used`, `status`, `chain_trace_id`. **Pivot central de auditoria de IA.** |
| `PromptTemplate` | `prompt_templates` | Prompts versionados no banco. Override por tenant possível. Hierarquia: tenant > global. Cache TTL 60s. |

### Base regulatória (RAG)

| Entidade | Tabela | Função |
|---|---|---|
| `LegislationDocument` | `legislation_documents` | Diploma legal (lei, decreto, resolução, IN). Metadado, status, hash. |
| `LegislationAlert` | `legislation_alerts` | Alerta gerado por mudança normativa relevante. |
| `KnowledgeChunk` | `knowledge_catalog` | Chunk indexável. `embedding vector(768)` (compat com base histórica em Gemini), `source_type ∈ {legislation, oficio, manual, jurisprudence, skill, other}`, filtros: `tenant_id` (NULL = global), `uf`, `jurisdiction`, `agency`, `identifier`. |
| `KnowledgeCatalog` | (camada de serviço) | API de busca em `app/services/knowledge_catalog.py`. |

### Auditoria

| Entidade | Tabela | Função |
|---|---|---|
| `AuditLog` | `audit_logs` | Hash chain SHA-256 encadeado. Campos: `entity_type`, `entity_id`, `action`, `old_value`, `new_value`, `details` (JSON), `ip_address`, `user_agent`, `hash_sha256`, `hash_previous`. |

## Detalhes que importam

### Enum `ProcessStatus` (máquina de estados)

```
lead → triagem → diagnostico → planejamento → execucao →
protocolo → aguardando_orgao → pendencia_orgao → concluido → arquivado
                                       ↓                           ↑
                                       └─→ (volta a execucao)     │
                                                                   │
cancelado ─────────────────────────────────────────────────────────┘
```

Transições válidas estão em `app/models/process.py:VALID_TRANSITIONS`. Tentativa de transição inválida levanta exceção.

### Enum `DemandType`

`car`, `retificacao_car`, `licenciamento`, `regularizacao_fundiaria`, `outorga`, `defesa`, `compensacao`, `exigencia_bancaria`, `prad`, `sobreposicao`, `supressao`, `due_diligence`, `arrendamento`, `condicionantes_antigas`, `misto`, `nao_identificado`.

Migration `e6f7a8b9c0d1` adiciona os 5 valores observados na prática pela planilha da Isis. O downgrade recria o enum sem esses valores e remapeia processos nesses tipos para `nao_identificado`.

Decisão de design: novo Process **sempre nasce com `nao_identificado`**. Promoção para demand_type específico é decisão do consultor, registrada via `POST /processes/{id}/classify` (Sprint A1-E).

### Enum `IntakeSource`

Canal de entrada da demanda: `whatsapp`, `email`, `presencial`, `banco`, `cooperativa`, `parceiro`, `indicacao`, `site`.

### Enum `EntryType` (Regente Cam1)

Cenário escolhido pelo consultor no Intake: `novo_cliente_novo_imovel`, `cliente_existente_novo_imovel`, `cliente_existente_imovel_existente`, `complementar_base_existente`, `importar_documentos`.

### `Client.field_sources` (JSONB)

Mapeia origem de cada campo do cliente:

```json
{
  "nome": {"source": "manual", "user_id": 3, "ts": "..."},
  "cpf": {"source": "extracted", "document_id": 42, "ai_job_id": 18, "ts": "..."},
  "endereco": {"source": "manual_confirmed_extracted", "user_id": 3, "ts": "..."}
}
```

Sprint V (commit `65110a0`) implementou. Sprint V follow-up (commit `93355c3`) adicionou badge no frontend "extraído pela IA".

### `AIJob.result` (JSONB)

Estrutura variável por agente. Convenção:
- Resultado bruto do LLM em `result["content"]` ou `result["text"]`
- Campos estruturados do agente em `result["extracted_fields"]`, `result["citations"]`, etc.
- Issues detectadas pelo `citation_evaluator` em `result["citation_issues"]`
- Quando o agente migra para `StageOutputContent`, o conteúdo segue o schema do tipo (`PecaJuridicaContent`, `DiagnosticoPreliminarContent`, etc.)

### `knowledge_catalog` — filtros disponíveis

A função `search()` em `app/services/knowledge_catalog.py` aceita:

| Filtro | Tipo | Uso |
|---|---|---|
| `query` | str | Busca semântica (embedding cosseno) |
| `tenant_id` | int? | NULL → busca apenas globais; com valor → globais + do tenant |
| `source_type` | enum? | legislation, oficio, manual, jurisprudence, skill, other |
| `jurisdiction` | str? | federal, estadual, municipal |
| `uf` | str? | UF (GO, MS, MT, etc.) |
| `agency` | str? | SEMAD, IBAMA, ICMBio, etc. |
| `identifier` | str? | Identificador da norma (Lei 12.651/2012) |
| `demand_type` | str? | Filtro estruturado no RAG vetorial: `knowledge_catalog.source_ref` faz JOIN lógico com `legislation_documents.id` e exige `LegislationDocument.demand_types @> [demand_type]`. Usado pelo `LegislacaoAgent`; a string da query continua carregando o tipo como reforço semântico. |
| `limit` | int | Default 10 |
| `min_similarity` | float | Default 0.7 |

### `AuditLog` — hash chain

Cada inserção:
1. Lê o `hash_sha256` do último `AuditLog` desse tenant (ou string vazia)
2. Calcula `hash_sha256 = SHA256(prev_hash + serialize(payload))`
3. Persiste `hash_previous = prev_hash` e o novo `hash_sha256`

Verificação posterior: refazer a cadeia do início e confirmar que cada elo bate. Implementação em `app/services/audit_hash.py`. Usado em 7 pontos críticos do sistema (mudança de status, atribuição de tarefa, geração de peça, classificação, etc.).

## Migrations

40 migrations aplicadas. Convenção de nome: `<8-hex>_sprint_<X>_<descricao>.py`.

Migrations notáveis:

| Migration | O que faz |
|---|---|
| `a8905cb51eb1_initial_schema` | Schema inicial (sprint 1) |
| `afcea9834c04_correct_models_processstatus_11_states` | Expansão para 11 estados |
| `c449df0_sprint_u_knowledge_catalog` | pgvector + knowledge_catalog (sprint U, 27/04) |
| `a8e1d4c7f3b6_sprint_a1_regulatory_diagnosis_issue` | Diagnóstico regulatório versionado (A1) |
| `b9d2e5a8f4c1_sprint_a1_intake_classification_feedback` | Loop de feedback IA × consultor (A1) |
| `b1a2c3d4e5f6_sprint_b1_pre_cadastros` | Tabela de waitlist (Sprint Waitlist B1) |

## Pendências e dívidas

1. **`Property.geom` vazia em todas as propriedades.** A coluna existe, o tipo está pronto, mas não há parser de shapefile/KML para popular. Bloqueia o agente `auditor_imovel`.
2. **`Document.extracted_text` sem cache_twin populado em alguns docs antigos.** Sprint -1 D introduziu cache por SHA-256 mas docs anteriores podem precisar de re-OCR.
3. **`AIJob.output_data` mencionado em alguns docs antigos — não existe.** O campo correto é `result` (JSONB). Documentação antiga errada.
4. **Migração da chave antiga do dual-emit do A2-diagnostico.** Frontend lê schema novo com fallback; consolidar em sprint cleanup futura.

## Próximas leituras

- [`API_v1.md`](./API_v1.md) — como acessar essas entidades pela superfície REST
- [`MULTITENANT_LGPD.md`](./MULTITENANT_LGPD.md) — política de isolamento e retenção
- [`BASE_REGULATORIA.md`](./BASE_REGULATORIA.md) — detalhe do RAG sobre `knowledge_catalog`
