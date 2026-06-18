# Fluxos End-to-End

**Documento:** Arquitetura · referência viva
**Estado:** atualizar quando o fluxo principal mudar
**Última revisão:** 2026-05-15

---

Fluxos completos do consultor dentro do Regente, ponta a ponta. Cada fluxo cita os arquivos do código que materializam cada passo. Use este documento quando precisar entender "o que acontece quando o consultor faz X".

## Fluxo 1 — Entrada de demanda (Intake)

Materializa as 3 primeiras macroetapas do briefing 29/04: entrada, diagnóstico inicial, coleta documental.

```
Consultor abre wizard de Intake (5 passos)
       │
       ▼
Passo 1 — Entrada do cenário
       │ (entry_type: novo_cliente, cliente_existente, etc.)
       │ Frontend: IntakeWizard.tsx
       ▼
Passo 2 — Dados do cliente
       │ Auto-preenche se cliente existente
       │ Backend: POST /api/v1/intake/drafts → cria IntakeDraft
       ▼
Passo 3 — Dados do imóvel
       │ Auto-preenche se imóvel existente
       │ Validação inicial de CAR (se informado)
       ▼
Passo 4 — Descrição da demanda + canal
       │ (texto livre + intake_source)
       │ Backend: AtendimentoAgent classifica (proposta de demand_type)
       │ Resultado: demand_type sugerido + confidence + requires_review
       ▼
Passo 5 — Upload inicial de documentos
       │ Frontend: DraftDocumentUploader.tsx
       │ Backend: POST /api/v1/documents/upload-url → presigned URL MinIO
       │ Frontend: PUT direto no MinIO
       │ Backend: POST /api/v1/documents/confirm-upload
       │ Backend dispara: ocr_then_extract task (Celery)
       │   ├── extract_text_from_pdf (cache hit por SHA-256, ou OCR)
       │   ├── ExtratorAgent (campos estruturados)
       │   └── Auto-fill no Cliente Hub / Imóvel Hub (com field_sources)
       ▼
Consultor revisa diagnóstico preliminar (DiagnosticoAgent)
       │ Backend: POST /api/v1/intake/drafts/{id}/diagnose
       │ Backend: chain diagnostico_completo (extrator → legislacao → diagnostico)
       │ Output: DiagnosticoPreliminarContent (hipóteses, lacunas, riscos, checklist)
       │
       ▼
Consultor aprova ou ajusta hipótese
       │ Frontend: DiagnosisPanel.tsx
       ▼
Consultor confirma draft → cria Process
       │ Backend: POST /api/v1/intake/drafts/{id}/commit
       │ Process.demand_type nasce como nao_identificado
       │ Process.status = lead
       │
       ▼
Consultor promove demand_type específico
       │ Backend: POST /api/v1/processes/{id}/classify
       │ → registra IntakeClassificationFeedback (diff IA × consultor)
       │ → Process.status pode avançar para triagem ou diagnostico
```

**Preview lateral + reconciliação (campos derivados — decisões Isis 2026-05-28):**
o wizard tem layout em 2 colunas quando há rascunho: à esquerda o formulário
multi-step; à direita o `PreviewPanel`, que faz polling de
`GET /intake/drafts/{id}/extracted-fields` (5s) e mostra cada campo extraído pela
IA com badge de confiança (verde >0.9 / amarelo 0.7–0.9 / vermelho <0.7) e
documento de origem. Quando o valor digitado diverge do extraído, abre o
`ReconcileModal` (Opção A): o consultor escolhe a origem vencedora →
`POST /intake/drafts/{id}/reconcile` grava em `field_sources`. A triagem usa
2 eixos independentes (`PriorityStep`: urgência 4 níveis + valor estratégico
3 níveis). O áudio da entrevista é anexável (Step 4) e vai para transcrição.

**Onde isso vive no código:**

| Passo | Backend | Frontend |
|---|---|---|
| Wizard 5 passos + preview/reconciliação | `app/api/v1/intake.py` | `frontend/src/pages/Intake/IntakeWizard.tsx` + `frontend/src/components/IntakeWizard/{PreviewPanel,ReconcileModal,PriorityStep}.tsx` |
| Preview de extração | `GET /intake/drafts/{id}/extracted-fields` | `PreviewPanel.tsx` (polling 5s) |
| Reconciliação cliente×IA | `POST /intake/drafts/{id}/reconcile` | `ReconcileModal.tsx` |
| Auto-extração | `app/workers/ocr_tasks.py` + `app/agents/extrator.py` | (background) |
| Diagnóstico preliminar | `app/agents/diagnostico.py` + chain `diagnostico_completo` | `DiagnosisPanel.tsx` |
| Commit do draft | `app/api/v1/intake.py:commit_draft` | (segue para `/processes/{id}`) |
| Classify para promover demand_type | `app/api/v1/intake_feedback.py:classify_router` | `frontend/src/pages/Intake/...` |

## Fluxo 2 — Operação do processo

Após commit, o caso vive como `Process`. O consultor opera nele até protocolar.

```
Process criado (status=lead)
       │
       ▼ (consultor inicia trabalho)
Status: triagem
       │ Auto-fill confirmações (Cliente Hub / Imóvel Hub)
       │ Frontend: ClientHub.tsx, PropertyHub.tsx
       ▼
Status: diagnostico
       │ Diagnóstico técnico aprofundado:
       │  ├── Mais documentos coletados (checklist por demand_type)
       │  │   ↳ Upload (`POST /documents/confirm-upload`) vincula automaticamente
       │  │     ao item pendente do checklist por `document_type` ou via
       │  │     `checklist_item_id` explícito do frontend; campos extraídos
       │  │     pelo `extrator` aparecem na DocumentsTab abaixo do badge
       │  │     (fix/upload-checklist-binding, 2026-05-28).
       │  ├── RegulatoryDiagnosis versionado registrado
       │  └── RegulatoryIssue cadastrado para cada inconsistência
       │ Gate camada 2 do `/validate` (PROMPT_6/7/10/11): exige decisão por
       │ crítica com `status_achado in {suspeita, confirmada, ignorada}`.
       │ Só `descartada`/`resolvida` ficam de fora (nada a decidir). Descartar
       │ libera; `ignorada` (achado real posto de lado) ainda cobra decisão —
       │ ignorar um real passa por `ignorar_justificado` (com justificativa).
       │ Frontend: ProcessDetail.tsx + DiagnosisTab + DocumentsTab
       │
       │ PROMPT_9 — UI da camada 2 do Princípio 1:
       │  ├── Aba "Alertas" lista RegulatoryIssue do imóvel (críticos no topo)
       │  ├── Consultor adjudica status_achado (suspeita → confirmada/descartada/…)
       │  ├── Decide alerta por alerta — 5 botões da P4 (decisão contextual ao
       │  │   processo, ADR-012). Regra B: decisão fica desabilitada enquanto
       │  │   achado = suspeita ("Confirme ou descarte antes de decidir").
       │  ├── Justificativa obrigatória em ignorar_justificado / fora_escopo (#19)
       │  └── Botão "Assinar diagnóstico vN" — gate camada 2 (422 com lista de
       │      pendentes; modal navega pro card correspondente)
       │ Frontend: AlertasTab + AlertaCard + DiagnosisAssinatura
       │
       │ fix/diagnostico-propaga-estado (28/05/2026): a assinatura propaga
       │ o estado. PATCH /validate, depois de gravar `validated_at`, recalcula
       │ `can_advance_macroetapa(current_macroetapa, diagnosis_validated=True)`
       │ — se passa (docs obrigatórios + checklist 100% + assinatura), chama
       │ `advance_macroetapa` no mesmo request e `Process.macroetapa` sobe
       │ pra próxima etapa (`diagnostico_preliminar → coleta_documental`
       │ ou `diagnostico_tecnico → caminho_regulatorio`). Gate travado mantém
       │ `validated_at` gravado mas a etapa fica onde estava — badge do kanban
       │ vira `aguardando_validacao` para refletir a assinatura. NÃO afeta
       │ `Process.status` (eixo 3, dívida #26).
       ▼
Status: planejamento
       │ Workflow template aplicado (por demand_type)
       │ Se não houver WorkflowTemplate ativo para o tipo:
       │   POST /processes/{id}/apply-workflow retorna 422 acionável
       │ Macroetapas planejadas + gates definidos
       │ Frontend: MacroetapaStepper.tsx
       ▼
Status: execucao
       │ Tarefas criadas e distribuídas (Kanban):
       │  ├── Tarefa de campo (foto, ponto GPS — futuro mobile)
       │  ├── Tarefa de redação (RedatorAgent gera proposta inicial)
       │  └── Tarefa de revisão (consultor revisa peça)
       │ Frontend: QuadroAcoes.tsx + TasksTab.tsx
       │
       │ Peças geradas pelo Redator (chain ou agente direto):
       │  ├── PRAD
       │  ├── Memorial descritivo
       │  ├── Ofício SEMAD/IBAMA/etc.
       │  ├── Resposta a notificação
       │  ├── Proposta
       │  ├── Contrato
       │  └── Comunicação livre
       │ Cada peça: requires_review=True → revisão humana obrigatória
       │
       ▼
Status: protocolo
       │ Documentação consolidada (dossiê técnico):
       │ Backend: GET /api/v1/processes/{id}/dossier
       │ Frontend: ProcessDossier.tsx
       │ Consultor protocola fora do sistema (portal do órgão)
       │ Registra número de protocolo + data
       ▼
Status: aguardando_orgao
       │ Vigia (sem LLM) monitora prazos
       │ Acompanhamento (com LLM) lê e-mails de retorno do órgão (quando inbox conectado)
       │
       ▼ (retorno positivo)        ▼ (retorno negativo)
Status: concluido           Status: pendencia_orgao
       │                            │
       ▼                            │ Plano de ação para resolver
Status: arquivado                   │
                                    └─→ retorna para execucao
```

## Fluxo 3 — Geração de peça (Redator)

Detalhe do que acontece quando o consultor pede uma peça.

```
Consultor pede peça (ex: "gerar ofício SEMAD-GO")
       │ Frontend: ProcessDetail / SaidasTab
       │ Backend: POST /api/v1/agents/redator/run
       │   { entity_type: "process", entity_id: X,
       │     metadata: { template: "oficio", demand_type: "car", uf: "GO" } }
       ▼
RedatorAgent.run() (BaseAgent lifecycle)
       │
       ├── Cria AIJob (status=running)
       │
       ├── Valida cost cap (per-job + per-tenant-hour + per-tenant-month)
       │   Falha → AIJob.status=cost_exceeded + HTTPException 429
       │
       ├── Carrega contexto:
       │    ├── Process + Client + Property data
       │    ├── chain_data (output do Legislacao quando em chain)
       │    └── Skills aplicáveis (redator/oficio_semad_go.md, etc.)
       │
       ├── Resolve prompt (PromptTemplate hierarchy: tenant > global > hardcoded)
       │
       ├── Chama ai_gateway.complete()
       │    ├── Tenta provider primário (OpenAI gpt-4o-mini default)
       │    ├── Em falha → fallback automático
       │    └── Retorna AIResponse(content, cost, tokens, model)
       │
       ├── Constrói PecaJuridicaContent (Sprint A2)
       │    ├── template (computed_field = document_type, defesa em profundidade)
       │    ├── content (texto da peça)
       │    ├── legal_citations (extraídas pelo citation_evaluator)
       │    ├── addressee (cascata metadata → process)
       │    ├── prazo_dias (se aplicável — para RespostaNotificacao)
       │    └── ato_regulatorio (se aplicável)
       │
       ├── Executa citation_evaluator
       │    ├── Extrai todas as citações do texto (regex multi-formato)
       │    ├── Valida cada uma contra knowledge_catalog
       │    └── Citações suspeitas → AIJob.result["citation_issues"]
       │
       ├── Marca requires_review=True (hardcoded para peças formais)
       │
       ├── Persiste AIJob (status=completed, cost_usd, tokens, model_used)
       │
       └── Emite evento WebSocket ai_job_completed
       ▼
Consultor recebe notificação em realtime
       │ Frontend: RedatorResult.tsx exibe peça + badges:
       │   ├── "Aguardando revisão" (requires_review=True)
       │   ├── "Citações suspeitas" (se citation_issues != [])
       │   └── Addressee + template type
       ▼
Consultor revisa, edita, aprova
       │ Backend: PATCH /api/v1/ai/jobs/{id} → requires_review=False + final_content
       │ AuditLog hash chain registra aprovação
       ▼
Peça aprovada → PDF gerado por pdf_generator worker
       │ Backend: AIJob.result["pdf_path"] aponta para MinIO
       │ Frontend: link para download
```

**Smoke test real (Sprint A2-redator, 09/05):** 7 templates × gpt-4o-mini × custo total `$0.0030`. 100x abaixo do orçamento (`$0.35`). Detalhes em [`../estado/progressoIA.md`](../estado/progressoIA.md).

## Fluxo 4 — Acompanhamento de retorno do órgão

```
E-mail do órgão chega no inbox (IBAMA, SEMAD, ICMBio)
       │ ⚠️ Hoje: integração de inbound NÃO existe ainda.
       │     Consultor encaminha manualmente.
       │ Futuro: connector IMAP/Gmail webhook
       │
       ▼
AcompanhamentoAgent processa o e-mail
       │ Input: corpo + assunto + lista de processos abertos do tenant
       │
       ├── Identifica órgão emissor (heurística + LLM)
       │
       ├── Vincula ao Process correto (regex em número de protocolo + LLM)
       │
       ├── Classifica tipo:
       │    ├── notificacao
       │    ├── exigencia
       │    ├── despacho
       │    └── resposta
       │
       ├── Detecta prazo (regex + parsing de data)
       │
       └── Sugere ações
       ▼
Sistema cria:
       ├── Task no processo (Kanban)
       ├── AuditLog do recebimento
       └── Notificação WebSocket para o consultor responsável
       ▼
Em paralelo: Vigia (rules-based, sem LLM) atualiza calendário de prazos
       │ Backend: app/agents/vigia.py + Celery beat
       ▼
Consultor revisa, prioriza, age
```

## Fluxo 5 — Waitlist (lead público do Regente)

Fluxo isolado, pré-conta. Não tem `tenant_id`.

```
Lead chega na landing https://regenteambiental.com.br
       │ (HTML/CSS/JS estático em Netlify Drop)
       │
       ▼
Lead preenche form da seção 09
       │ Campos: nome, email, telefone, perfil_profissional,
       │         tipo_licenciamento, volume_mensal, ferramenta_atual,
       │         preco_aceito (Van Westendorp), expectativa, deal_breaker,
       │         interesse_grupo, consentimento (LGPD), UTM
       │
       ▼ (JS faz POST)
POST https://api.regenteambiental.com.br/api/v1/waitlist
       │ Rate limit: 10/min por IP
       │ Pydantic v2 valida (email lowercase, estado uppercase + whitelist 27 UFs,
       │   telefone só dígitos 10-13 chars, consentimento bloqueante)
       │ Idempotência: segundo POST mesmo email → 200 silencioso
       │
       ├── Persiste em pre_cadastros (sem tenant_id)
       │
       ├── Enqueue Celery: send_welcome_email (autoretry 3× backoff)
       │   └── Resend API: send_email + upsert_audience_contact
       │
       └── Beat-scan task scan_due_drip_emails (a cada 15 min):
            ├── d+7  → send_drip_d7  (educativo)
            ├── d+14 → send_drip_d14 (bastidor)
            └── d+21 → send_drip_d21 (convite beta)
                 │
                 └── Idempotente via UNIQUE (lead_id, step) em pre_cadastros_drip_log
       ▼
Lead engaja, equipe avalia, lead convertido manualmente em usuário
       │ ⚠️ Conversão é manual hoje (sem self-onboarding)
       ▼
Lead vira User dentro de um Tenant (Regente como cliente operador, por exemplo)
```

Detalhes operacionais em [`../estado/PROGRESSO_WAITLIST.md`](../estado/PROGRESSO_WAITLIST.md).

## Fluxo 6 — Hardening de produção (deploy)

```
Sprint pronta na branch main
       │
       ▼
Checklist pré-deploy (ops/production-secrets-checklist.md):
       │
       ├── SECRET_KEY robusta (≥32 chars, não default)
       ├── POSTGRES_PASSWORD não-default
       ├── REDIS_PASSWORD configurado
       ├── MINIO_ACCESS_KEY/SECRET não-default
       ├── SMTP real (Mailtrap só em dev)
       ├── RESEND_API_KEY configurada (para waitlist)
       ├── BACKEND_CORS_ORIGINS = ['https://regenteambiental.com.br', ...]
       ├── ENVIRONMENT=production → /docs desabilitado
       ├── ALERT_WEBHOOK_URL configurado (alertas operacionais)
       ├── AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT definido
       └── Backup de Postgres configurado
       │
       ▼
docker compose up (com .env de prod) ou plataforma equivalente
       │
       ▼
Smoke test ops/run_homologation_smoke.py
       │
       ▼
Health check /health responde 200
Métricas /metrics expõem todos os contadores
Alembic upgrade head aplicou todas as migrations
       │
       ▼
Sócia roda 1 caso end-to-end (validação humana)
```

## Fluxo 7 — WhatsApp inbound a caso já aberto (PR 2.1)

Cliente manda WhatsApp; a mensagem entra no caso aberto correspondente. Inbound
**nunca cria caso** (decisão fechada 2026-05-28) — só anexa a um `Process` existente.
Dormente até as credenciais da Evolution serem configuradas.

```
Cliente manda mensagem de WhatsApp
       │ Provider externo (Evolution API — serviço docker sob profile "whatsapp")
       │
       ▼
POST /api/v1/messaging/whatsapp/webhook   (sem JWT — provider externo chama)
       │ Backend: app/api/v1/messaging.py
       │
       ├── Valida HMAC-SHA256 do corpo cru (header X-Hub-Signature-256 ×
       │   EVOLUTION_WEBHOOK_SECRET). Sem secret → não exige (modo dormente).
       │   HMAC inválido → 401. Corpo não-JSON / não parseável → 200 {ignored}.
       │
       ├── get_whatsapp_provider().parse_inbound_webhook(payload) → InboundMessage
       │   (provider plugável: EvolutionProvider real, ZAPIProvider stub)
       │
       ▼
Identifica o Client pelo telefone
       │ Normaliza dígitos, casa pelos ÚLTIMOS 8 dígitos (phone/secondary_phone).
       │ tenant_id é derivado do Client encontrado.
       │
       ├─────────────────────────────┬──────────────────────────────┐
       ▼ (Client + caso aberto)       ▼ (Client, sem caso aberto)     ▼ (sem Client)
Pega Process mais recente        Thread órfã (process_id NULL)    Ignora com log
NÃO terminal (status ∉           + Message gravada                 → 200 {ignored,
{concluido, arquivado,           + alerta interno:                   reason:
cancelado}, deleted_at NULL)       publish_realtime_event              "unknown_sender"}
       │                            ("messaging.inbound_orphan")     (NÃO cria caso)
       ▼                            + AuditLog action="inbound_orphan"
Grava Message na                        │
CommunicationThread do caso             ▼
(channel="whatsapp",              200 {status:"ok", orphan:true, ...}
 provider="evolution",
 external_msg_id = id do provider)
       │
       ├── Se media_url presente: baixa via httpx e grava Document
       │   (source="whatsapp", document_category="whatsapp_inbound").
       │   Best-effort — falha no download não derruba o webhook.
       │
       ▼
200 {status:"ok", thread_id, message_id, orphan:false, document_id}
```

**Onde isso vive no código:**

| Passo | Backend |
|---|---|
| Webhook + identificação + persistência | `app/api/v1/messaging.py` |
| Provider plugável (parse do payload) | `app/services/messaging/` (`EvolutionProvider`, `ZAPIProvider` stub, `registry.get_whatsapp_provider()`) |
| Thread + mensagem + colunas de provider | `CommunicationThread` (`provider`/`provider_account_id`) + `Message.external_msg_id` |
| Alerta órfão | `publish_realtime_event` + `register_notification_audit` (`app/services/notifications.py`) |

> **Limitação:** sem idempotência por `external_msg_id` — reentrega do provider duplica
> `Message`. **E-mail inbound (Resend) NÃO existe** nesta PR — só placeholders de config.
> Detalhe da superfície em [`API_v1.md`](./API_v1.md); contexto de integração em
> [`INTEGRACOES_GOVTECH.md`](./INTEGRACOES_GOVTECH.md).

## Fluxo 8 — Staging → Decisão → Consolidação (Ficha 01, Fases 1-4)

A entrada estruturada do imóvel (Ficha 01) é um pipeline de 4 fases:
"agentes propõem (staging), consultor decide (Alertas), sistema grava (base)".

1. **Extração → staging (Fase 2).** O `extrator` lê o OCR e, por tipo de
   documento, grava cada campo extraído em `ExtractedFieldStaging`
   (`status=pendente`, `source_doc_type`, `target_entity`/`target_field`,
   `matricula_hint`, `confidence`, rastreabilidade `created_by_agent`/`ai_job_id`).
   O `AIJob.extracted_fields` legado continua intacto (staging é adicional).
2. **Confronto → matriz (Fase 3).** O `auditor_imovel` (determinístico) lê o
   staging, monta a **Matriz de Inconsistências** (colunas por fonte, âncora =
   SIGEF), classifica pela Ficha 02 §4 e **marca o status** das linhas
   confrontadas (`consistente` / `divergente_transcricao` / `divergente_fundo`).
   A matriz vai para `AIJob.result.matriz_inconsistencias` e alimenta o
   diagnóstico.
3. **Decisão do consultor (Fase 4).** Na aba **Alertas**
   (`ConsolidacaoPanel`): `aceitar` / `escolher_fonte` / `editar` / `rejeitar`
   por campo, ou `aceitar-consistentes` em lote. Endpoints:
   `POST /processes/{id}/staging-fields/{field_id}/decidir`,
   `POST /processes/{id}/staging-fields/aceitar-consistentes`. **Gate:** aceitar
   um `divergente_transcricao` direto → 422 (exige escolha ativa). Marca
   `status=aceito|rejeitado` + `decided_value`/`decided_by`/`decided_at`.
4. **Consolidação na base (Fase 4 — Ficha 05).** `POST /processes/{id}/consolidar`
   (`staging_consolidation.py`, determinístico, idempotente): grava o
   `status=aceito` em `Client`/`Property`/`Matricula` (upsert por
   `matricula_hint`). Detalhes Ficha 05:
   - **Multi-fonte → vencedora por destino** `(entidade,[hint],campo)`: ordem
     edição-consultor > **âncora SIGEF** (`area_ha`/`denominacao_imovel`) >
     confiança > id.
   - **UPSERT versionado + audit por campo** (`anterior→novo+fonte`); **reconciliação**:
     doc novo divergente de campo já consolidado NÃO sobrescreve — volta como alerta.
   - **Idempotente**: re-gravar o mesmo valor é no-op. **Achado** (`divergente_fundo`
     aceito, `decided_value=None`) não grava valor. Área implausível não grava.
   - **Não** sobrescreve `Property.total_area_ha` — a área do imóvel é derivada
     (`area_total_matriculas()`).
5. **Imóvel Hub (resultado visível).** `GET /properties/{id}/summary` **deriva**
   Matrícula (`"; ".join` dos números) e Área (soma das matrículas) das `Matricula`
   consolidadas quando as colunas cruas de `Property` estão vazias — fim dos "—"
   após "Confirmar e gravar".

Gap D1: linhas técnicas da matriz (APP/RL/hidrografia/cobertura) ficam
registradas, sem confronto espacial, até `Property.geom` chegar.

## Pendências e dívidas

1. **Inbox connector para Acompanhamento** — fluxo 4 hoje é manual. (WhatsApp inbound — fluxo 7 — já cobre o canal de mensagem; e-mail inbound via Resend segue não construído.)
2. **Self-onboarding pós-waitlist** — fluxo 5 termina em conversão manual.
3. **Mobile offline-first** — fluxo de campo (foto, GPS, checklist) congelado.
4. **Portal cliente** — cliente final não acompanha próprio caso ainda; congelado.
5. **`Property.geom`** — fluxo 2 não cruza dados espaciais hoje (auditor_imovel pendente).

## Diagnóstico → Ação → Triagem (Ficha 07)

Onde o diagnóstico vira trabalho.

1. **Diagnóstico** existe (`RegulatoryDiagnosis` com `riscos`/`afirmacoes`, cada um com fonte #70).
2. **Gerar** — `POST /processes/{id}/acoes/generate` cria uma `Acao` `pendente` por ação de remediação
   (`risco.proximo_passo` + `afirmacao categoria=acao`), preenchendo origem e fonte. Idempotente
   (`dedupe_key` por process+passivo+título).
3. **Triar** — na aba Ações, o consultor decide cada pendente: `tarefa` (trabalho interno), `escopo`
   (candidata a item de proposta — só marca) ou `dispensar`. Princípio 1.
4. **Trabalhar** — status de kanban (`a_fazer`→`em_andamento`→`concluida`/`bloqueada`), editável na
   aba ou no **Quadro de Ações global** (`/acoes`, todos os casos).
5. **Concluir ≠ resolver passivo** — concluir a ação carimba `concluida_at` mas **não** toca
   `RegulatoryIssue`/achado (ADR-016). O saneamento real do passivo é gesto separado, pós-contratação.

## Próximas leituras

- [`API_v1.md`](./API_v1.md) — endpoints que materializam cada passo
- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — política aplicada nos fluxos 3 e 4
- [`PIPELINE_OCR.md`](./PIPELINE_OCR.md) — detalhe do fluxo de extração (passo 5 do Intake)
