# Auditoria do fluxo — 2026-04-29

Documento gerado a partir do briefing da sócia (2026-04-29) e auditoria conjunta de backend, agentes IA e frontend. Define o backlog mínimo para o sistema ser considerado "operacional pronto pra validação".

## Briefing da sócia (norte estratégico)

**Síntese:** *Cadastro é entrada. Diagnóstico é inteligência. Coleta documental é organização.* Separar bem essas camadas evita retrabalho, perda de documentos e decisões regulatórias mal rastreadas.

### Modelo padrão de cada etapa do workflow (10 elementos)
1. **Objetivo da etapa** — para que existe
2. **Entradas** — documentos, dados, informações
3. **Leitura da IA** — o que a IA deve analisar
4. **Dados estruturados** — o que vira tabela ou campo
5. **Ações** — o que precisa ser feito
6. **Checklist** — o que precisa ser concluído
7. **Decisões** — o que foi decidido e por quem
8. **Lacunas** — o que falta saber
9. **Saídas** — o que precisa estar pronto pra avançar
10. **Validação humana** — quem validou

### Resumo executivo do fluxo (12 passos)
1. Consultor cadastra cliente, imóvel e documentos iniciais no Intake
2. IA lê os documentos e extrai dados principais
3. Sistema mostra prévia antes de criar o caso
4. Consultor valida e clica em "Criar card"
5. Caso aparece automaticamente em Entrada da Demanda
6. Documentos e dados acompanham o caso pelo Workspace, Cliente Hub e Imóvel Hub
7. Na Entrada da Demanda, sistema confirma cadastro, vínculo e contato
8. No Diagnóstico Preliminar, IA cruza documentos, entrevista e anotações
9. Sistema gera hipótese preliminar, lacunas, riscos e checklist documental
10. Consultor valida a hipótese
11. Caso avança para Coleta Documental
12. Cliente Hub e Imóvel Hub permanecem atualizados com todo o histórico

### 8 pontos críticos pra corrigir
1. Documentos enviados no Intake precisam aparecer no caso criado
2. Documentos também precisam aparecer no Workspace do Caso
3. Workspace precisa ter aba de Checklist funcional
4. IA precisa transformar documentos em dados estruturados
5. Card lateral mostra resumo; operação completa fica no Workspace
6. Cada etapa precisa ter ações, decisões, checklists e saídas esperadas
7. Cliente Hub e Imóvel Hub precisam ser alimentados automaticamente
8. Sistema precisa diferenciar cadastro de diagnóstico regulatório

### Hubs específicos
- **Imóvel Hub:** mostrar inconsistências (cruzamento entre matrícula, CAR, CCIR e demais documentos)
- **Cliente Hub:** mostrar visão histórica (cliente, imóveis, casos, contratos e diagnósticos)

---

## A. Conformidade com os 8 pontos críticos

| # | Ponto crítico | Backend | Agentes | Frontend | Veredito |
|---|---|---|---|---|---|
| 1 | Docs Intake → caso criado | ✓ migra via UPDATE | — | ⚠ origem não marcada | **PARCIAL** |
| 2 | Docs no Workspace do caso | ✓ `GET /documents?process_id=X` | — | ✓ DocumentsTab | **OK** |
| 3 | Aba Checklist funcional | ✓ ProcessChecklist+MacroetapaChecklist existem | — | ⚠ é sub-componente, não aba | **PARCIAL (UI)** |
| 4 | IA → dados estruturados | ⚠ extrator existe, sem 2nd-pass por etapa | ⚠ sem trigger automático | ⚠ não exibe campos extraídos | **BLOQUEADO** |
| 5 | Card lateral (resumo) vs Workspace (operação) | — | — | ✓ `WorkspaceRightPanel` separado | **OK** |
| 6 | Cada etapa: Ações+Decisões+Checklists+Saídas | ✓ todos modelados | — | ✓ 9 abas | **OK¹** |
| 7 | Hubs auto-alimentados pelo Intake | ✗ commit não dispara enrich nos hubs | ✗ sem hook de auto-fill | ✗ criação manual | **BLOQUEADO** |
| 8 | Cadastro (Intake) ≠ Diagnóstico regulatório (etapa 2) | ⚠ ambos usam `Process.initial_diagnosis` Text | ⚠ sem orquestração | ⚠ DiagnosisTab pouco preenchido | **BLOQUEADO** |

¹ Falta apenas **Lacunas** estruturadas (hoje só existe como label de checklist).

**Resultado:** 3 OK · 2 PARCIAL · 3 BLOQUEADO. Os bloqueios estão na **tríade #4 + #7 + #8** (IA + Hubs + separação cadastro/diagnóstico).

---

## B. 13 gaps consolidados, por camada

### Banco de dados (3 gaps)
| ID | Gap | Modelo proposto | Esforço |
|---|---|---|---|
| **B1** | Não há entidade "Lacuna" — hoje é só label de ação | `StageGap(process_id, macroetapa, type, description, severity, resolved_at)` | M |
| **B2** | `StageOutput` existe mas sem schema obrigatório por macroetapa | Tipos enum + JSON Schema por `output_type` | M |
| **B3** | Diagnóstico regulatório não tem versão própria — mistura com `Process.initial_diagnosis` (Intake) | `RegulatoryDiagnosis(process_id, macroetapa, content_jsonb, validated_by, version)` | M |

### Backend / API (4 gaps)
| ID | Gap | O que precisa | Esforço |
|---|---|---|---|
| **A1** | Commit do draft não enriquece Cliente/Imóvel Hub (campos extraídos não fluem) | Hook em `app/api/v1/intake.py:923` que dispara `enrich_property_from_documents()` e `enrich_client_from_documents()` | M |
| **A2** | Não há `GET /processes/{id}/workspace` agregador | Novo endpoint + schema | L |
| **A3** | Não há `GET /properties/{id}/inconsistencies` | Novo endpoint chamando `auditor_imovel` | M |
| **A4** | `Document.source` não distingue origem (intake vs upload) | Migration: adicionar coluna `source` (enum) | S |

### Agentes IA (4 gaps)
| ID | Gap | O que precisa | Esforço |
|---|---|---|---|
| **I1** | **Agente `legislacao` ignora o `knowledge_catalog`** — busca só por metadados; o RAG da Sprint U não é consumido | Em `app/agents/legislacao.py:execute()` chamar `app.services.knowledge_catalog.search()` antes do prompt | **M (alta prioridade)** |
| **I2** | Sem trigger automático nas etapas 3 (Coleta) e 4 (Diagnóstico Técnico) | Hook em `documents.confirm-upload` + hook em `processes.advance-macroetapa` | M |
| **I3** | Falta agente `auditor_imovel` que cruza matrícula/CAR/CCIR e popula `regulatory_issues` | Novo agente em `app/agents/auditor.py` + chain | M |
| **I4** | Output dos agentes não persiste em local consultável | Expandir `AIJob.output_data` (JSONB) + endpoint `GET /agents/jobs/{id}` | S |

### Frontend (3 gaps)
| ID | Gap | O que precisa | Esforço |
|---|---|---|---|
| **F1** | Aba "Checklist" dedicada não existe (é sub-componente em DocumentsTab) | Adicionar entrada em `TABS` em `ProcessDetailTypes.ts:120` + roteamento | **S** |
| **F2** | Campos extraídos pela IA não aparecem no Dossier/Hubs | Conectar `/agents/jobs/{id}` ao Dossier + auto-fill com badge "extraído pela IA" | M |
| **F3** | Imóvel Hub não mostra flag visual de inconsistências | Card "Inconsistências detectadas" lendo de `regulatory_issues` | S |

**Total estimado:** ~3 S · ~7 M · ~2 L · 1 prioridade altíssima (I1)

---

## C. Plano em sprints temáticos (ordenados por dependência)

### Sprint V — RAG ao vivo + auto-fill de Hub *(destrava #4 e #7)*
1. **I1** — Conectar `legislacao` ao `knowledge_catalog` (RAG semântico)
2. **A4** — `Document.source` = intake | upload | sync
3. **A1** — Hook pós-commit enriquece Property/Client com dados extraídos
4. **F2** — UI mostra campos auto-preenchidos com badge "IA"

→ **Entregável:** consultor cria caso pelo Intake → docs sobem → IA extrai → Cliente Hub e Imóvel Hub povoados automaticamente.

### Sprint W — Lacunas e Saídas como entidades de 1ª classe *(destrava #6 completamente)*
5. **B1** — Modelo `StageGap` + endpoints CRUD
6. **B2** — Schemas formais de Saída por macroetapa
7. **F1** — Aba "Checklist" dedicada

→ **Entregável:** cada etapa exibe "lacunas detectadas" + "saídas validadas" com semântica forte.

### Sprint X — Diagnóstico regulatório formal *(destrava #8)*
8. **B3** — `RegulatoryDiagnosis` com versioning
9. **I2** — Trigger automático de chain `diagnostico_completo` ao avançar pra etapa 2
10. DiagnosisTab populada com hipótese + lacunas + riscos + checklist sugerido

→ **Entregável:** ao avançar Entrada → Diagnóstico Preliminar, IA roda automaticamente e produz hipótese formal versionada.

### Sprint Y — Auditoria de inconsistências do imóvel *(destrava "Imóvel Hub mostra inconsistências")*
11. **I3** — Agente `auditor_imovel` (matrícula × CAR × CCIR contra regras por UF)
12. **A3** — `GET /properties/{id}/inconsistencies`
13. **F3** — Card visual no Imóvel Hub

→ **Entregável:** Imóvel Hub mostra inconsistências detectadas com link pro doc-fonte.

### Sprint Z (opcional) — Workspace agregator + Output IA persistido
14. **A2** — `GET /processes/{id}/workspace` (1 chamada, tudo da etapa atual)
15. **I4** — `AIJob.output_data` consultável

→ **Entregável:** UI mais leve (1 fetch vs 6); revisão de saída IA pelo consultor.

---

## D. Decisão tomada

**Iniciar pela Sprint V**, começando por **I1 (RAG no agente legislacao)**.

Razão: a Sprint U entregou a infra de RAG (pgvector + 1424 chunks indexados) mas o agente `legislacao` ainda busca apenas por metadados. Conectar os dois é o ROI mais alto disponível agora — destrava o "diferencial-chave" do produto (agente regulatório com base de conhecimento) sem novo modelo nem migration.

Sequência prevista de Sprint V:
1. I1 — `legislacao.py` consulta `knowledge_catalog.search()` antes do prompt
2. A4 — migration `Document.source`
3. A1 — hook de enriquecimento pós-commit
4. F2 — exibe extração na UI

---

## Apêndice: arquivos-chave citados

**Backend:**
- `app/models/`: client.py, property.py, process.py, document.py, intake_draft.py, macroetapa.py, process_decision.py, stage_output.py, checklist_template.py, task.py
- `app/api/v1/`: intake.py, processes.py, clients.py, properties.py, decisions.py, documents.py, checklists.py
- `app/services/`: intake_classifier.py, macroetapa_engine.py, knowledge_catalog.py
- `app/workers/`: agent_tasks.py

**Agentes:**
- `app/agents/`: atendimento.py, extrator.py, diagnostico.py, legislacao.py, orcamento.py, redator.py, acompanhamento.py, vigia.py, financeiro.py, marketing.py, orchestrator.py

**Frontend:**
- `frontend/src/App.tsx`
- `frontend/src/pages/Processes/`: ProcessDetail.tsx, ProcessDetailTypes.ts, DocumentsTab.tsx, DiagnosisTab.tsx, TasksTab.tsx, DecisionsTab.tsx, SaidasTab.tsx, TimelineTab.tsx, AIPanel.tsx, ProcessChecklist.tsx, WorkspaceRightPanel.tsx
- `frontend/src/pages/Intake/IntakeWizard.tsx`
- `frontend/src/pages/Clients/ClientHub.tsx`
- `frontend/src/pages/Properties/PropertyHub.tsx`
