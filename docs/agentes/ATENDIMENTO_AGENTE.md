# ATENDIMENTO — sister file

> Documento vivo do agente `atendimento`. **Regra de ouro deste arquivo:**
> documentar SOMENTE o que está construído. Transcrição de áudio (Whisper) NÃO
> está implementada — é frente futura, registrada como tal, não documentada
> como existente. Criado em 2026-05-30 a partir do código real.

## 1. Papel no ecossistema

Ponto de entrada (macroetapa 1 — `entrada_demanda`): recebe o contato inicial,
qualifica a demanda e sugere o `demand_type`. Secundariamente apoia a macroetapa
2. Registrado como `"atendimento"` / `AtendimentoAgent`,
`job_type="classify_demand"` (`app/agents/atendimento.py`).

## 2. Estado de implementação

- **Implementado.** `execute()` lê `ctx.metadata["description"]` e chama
  `classify_demand_with_llm()`; retorna `demand_type`, `confidence`,
  `initial_diagnosis`, `checklist_template`, `urgency_flag`,
  `relevant_agencies` (dict). `requires_review=False`.
- **Áudio:** `audio_url` é apenas **armazenado** no `IntakeDraft`
  (`form_data`/`ManualFields.audio_url`, `app/schemas/intake.py`). **HOJE não há
  transcrição automática** — confirmado: nenhum Whisper/`transcri`/`speech` no
  código. O consultor digita o que ouviu; o `audio_url` fica guardado para uma
  frente futura de transcrição (PR própria do agente).

## 3. Skills

Sem skill procedural formal em `app/skills/atendimento/`. A classificação vive em
`classify_demand_with_llm()` + regras estáticas do `intake_classifier`.

## 4. Tools que usa

- **LiteLLM gateway** (`ai_gateway.complete`). **Sem RAG** hoje.
- Apoio das regras estáticas de `app/services/intake_classifier.py`
  (`classify_demand`, 16 demand_types).

## 5. Inputs aceitos

Por `ctx.metadata`: `description` (texto livre — obrigatório), `process_type`,
`urgency`, `source_channel`. `audio_url` (apenas armazenado; transcrição é
frente futura, não consumida aqui).

## 6. Outputs

`dict` com `demand_type` sugerido + diagnóstico inicial + checklist template +
urgency_flag + órgãos relevantes. **Sugestão, não decisão:** o `Process` nasce
sempre com `demand_type="nao_identificado"`; só o consultor (ou a promoção via
`/processes/{id}/classify`) muda o `demand_type` oficial.

## 7. Knowledge essencial

- Taxonomia `DemandType`: 16 valores (`app/models/process.py`).
- **Sintoma/dor** são interpretação do consultor — NÃO entram como campo do
  sistema (decisão Isis 2026-05-28; confirmado: ausentes do `IntakeDraft`/schemas).
- **Caso só nasce por mão do consultor** (decisão de produto fechada): o agente
  qualifica/sugere; não cria processo sozinho.

## 8. Conversation patterns

- Na chain `intake` (`["atendimento"]`), disparada ao avançar para a macroetapa
  `entrada_demanda` (`MACROETAPA_AGENT_CHAIN`).
- Recebe entrada manual do `IntakeWizard` (texto que o consultor digita).
- **Canal inbound (PR 2.1):** mensagens de WhatsApp do cliente entram no
  `CommunicationThread` do caso **já aberto** (webhook `/messaging/whatsapp/webhook`),
  virando contexto vivo do processo (e mídia → `Document`). O agente **não** cria
  caso a partir de inbound (decisão fechada 2026-05-28); hoje a ingestão alimenta o
  thread/documentos — disparo automático do `atendimento` sobre inbound é frente futura.

## 9. Cross-agente

- Alimenta `legislacao` (que usa `chain_data["atendimento"].demand_type` como
  fallback do `demand_type`).
- Alimenta o `diagnostico` com o contexto inicial.

## 10. Dívidas técnicas próprias

- **Transcrição de áudio (Whisper ou equivalente):** frente futura, sem PR.
  `audio_url` já é capturado e armazenado; falta o consumidor.
- **Ingestão de mensagens externas (WhatsApp/email) em caso ABERTO:** PR 2.1 (em
  fila; depende de Resend Inbound + URL/key da Evolution). Referência:
  `docs/arquitetura/INTEGRACOES_GOVTECH.md`.

## 11. Próximas frentes

- **PR 2.1** — canal de mensagens externas (entra como input do atendimento).
- Frente futura de transcrição de áudio.

## 12. Validação Isis

- **Pendente:** wizard de entrada testado pela Isis fim-a-fim.
- **Pendente:** confirmar que o `demand_type` sugerido bate com a prática dela.
