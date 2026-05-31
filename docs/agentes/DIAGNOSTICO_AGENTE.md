# DIAGNOSTICO — sister file

> Documento vivo do agente `diagnostico`. Toda afirmação aqui é verificável no
> código (referências `arquivo:linha`). Criado em 2026-05-31 a partir do código
> real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Destila o cenário do caso em uma visão acionável — situação geral, hipóteses,
lacunas, riscos, divergências documentais e checklist — para orientar a coleta
do consultor e alimentar `legislacao` e `redator`. É o agente da macroetapa de
**diagnóstico**: interpreta, não refaz a conta do auditor (o auditor é o radar,
o diagnóstico é a interpretação — `app/agents/diagnostico.py:53-56`).

Registrado como `"diagnostico"` / `DiagnosticoAgent`,
`job_type=AIJobType.diagnostico_propriedade` (`app/agents/diagnostico.py:111-115`).
Catálogo transversal em `docs/agentes/ECOSSISTEMA_AGENTICO.md`.

## 2. Estado de implementação

- **Implementado.** `execute()` (`diagnostico.py:122`) monta contexto do processo,
  chama o LLM, constrói `DiagnosticoPreliminarContent` e faz **dual-emit** das
  chaves antigas (`situacao_geral`, `passivos_identificados`, `acoes_remediacao`,
  `prioridade_acoes`, `risco_estimado`, `observacoes`) no payload final
  (`diagnostico.py:444-455`).
- **Fallback sem IA:** `_rules_based_diagnosis()` (`diagnostico.py:254`) emite o
  mesmo `Content` com `Source(type="manual", ref="rules_engine")` quando
  `settings.ai_configured` é falso (`diagnostico.py:133`).
- **Consome o auditor (PROMPT_4 Onda A):** `_consume_auditor_findings()`
  (`diagnostico.py:472`) lê `chain_data["auditor_imovel"]["findings_raw"]` e os
  transforma em `Divergencia` + `Risco` (com `grau` em 4 níveis) — em ambos os
  paths IA e regras (`diagnostico.py:178-180`, `:276-280`).
- **citation_evaluator (Sprint A3):** `_evaluate_citations()` (`diagnostico.py:598`)
  marca citações sem match no contexto legislativo como suspeitas, sem derrubar
  a execução (`diagnostico.py:457-464`).
- **Gate Pydantic↔JSONB:** `POST /processes/{id}/diagnoses`
  (`app/api/v1/regulatory.py:151-216`) valida o `content` contra
  `DiagnosticoPreliminarContent` via `validate_diagnostic_content`; falha vira
  HTTP 422 (`regulatory.py:179-192`).

## 3. Skills

Skill procedural única: `diagnostico/situacao_ambiental_imovel_rural`
(`app/skills/diagnostico/situacao_ambiental_imovel_rural/SKILL.md`, v1.1.0,
`applies_to: agent diagnostico, uf [GO, MS, MT]`). Cobre os movimentos 2
(preliminar) e 4 (consolidado) do método e opera em **três estágios** do mesmo
caso com o mesmo schema — `preliminar`, `consolidado`, `saneamento` — via
`ctx.metadata.stage` (`SKILL.md:25-40`). Princípio operacional declarado:
"Radar, não cancela" e `requires_review=True` (`SKILL.md:42-54`). Skills são
compiladas no system prompt (ADR-006) — ver `ECOSSISTEMA_AGENTICO.md`.

## 4. Tools que usa

- **LiteLLM gateway** via `call_llm` (`diagnostico.py:148`) — nunca chama provider
  direto.
- **`OutputValidationPipeline.parse_llm_json`** (`diagnostico.py:149`) — parsing
  do JSON do LLM.
- **`citation_evaluator`** (`extract_citations`/`validate_citations`,
  `diagnostico.py:612-615`) — gate de citações.
- **Sessão SQLAlchemy** — `_load_process_data()` consulta `Process`, `Property`,
  `Document` filtrando por `tenant_id` (`diagnostico.py:195-252`).

## 5. Inputs aceitos

- **Precondição:** `ctx.process_id` obrigatório (`validate_preconditions`,
  `diagnostico.py:118-120`).
- **Chain data:** `chain_data["extrator"]`, `chain_data["legislacao"]` e
  `chain_data["auditor_imovel"]` (`diagnostico.py:129-130`, `:179`).
- **`ctx.metadata.stage`** ∈ `{preliminar, consolidado, saneamento}` (lido pela
  skill — `SKILL.md:37`).
- Disparo via chain `diagnostico_completo` ou `gerar_proposta` (ver seção 9), ou
  via `/agents`.

## 6. Outputs

`DiagnosticoPreliminarContent` (`app/schemas/stage_output.py:280-301`) serializado
com `model_dump(mode="json")` + dual-emit (`diagnostico.py:447-455`). Mapeamento
(`diagnostico.py:357-466`):
- `situacao_geral` → `content`; `passivos_identificados` → `hipoteses`;
  `acoes_remediacao` → `checklist_documental`; `prioridade_acoes`/`observacoes`
  → `metadata`.
- `riscos` = riscos do auditor (`grau` 4 níveis preservado) **+** risco do LLM
  (severidade legada `{baixo,medio,alto}`) (`diagnostico.py:406-410`).
- `divergencias` = matriz de cruzamento do auditor (`diagnostico.py:436`).
- `nivel_risco_geral` derivado do "pior" grau entre os riscos do auditor;
  `None` quando não há auditor na chain (`_derive_nivel_risco_geral`,
  `diagnostico.py:577-596`).
- `lacunas` = `[]` (schema-only em V1 — `diagnostico.py:417-422`).
- `requires_review=True` é forçado no payload (`diagnostico.py:447-448`); a skill
  reforça (`SKILL.md:44`). **Nota:** a tabela-catálogo do mestre listava
  `requires_review`="não" para este agente (não batia com o código) — corrigido
  para "sim" na mesma rodada de criação deste sister file (31/05).

## 7. Knowledge essencial

- Régua de severidade de **4 faixas** mapeada do `grade` do auditor para `grau`:
  `informativo / atencao / alto / critico → critico_impeditivo_potencial`
  (`_GRADE_TO_GRAU`, `diagnostico.py:64-69`). `critico` NÃO é colapsado com o
  `severity` de 3 níveis do `RegulatoryIssue` (`diagnostico.py:58-63`).
- Mapa de Riscos: 7 `RiscoCategoria` + 4 `RiscoGrau`
  (`stage_output.py:60-74`); `familia` (11 valores) → categoria (7) via
  `_FAMILIA_TO_CATEGORIA` (`diagnostico.py:77-89`).
- `Risco` é dual-emit: aceita payload antigo (`descricao/severidade`) e novo
  (`risco_identificado/grau`), reconciliados em `model_validator`
  (`stage_output.py:158-214`).
- `Divergencia` exige `tema`+`divergencia`+`impacto` não-vazios
  (`stage_output.py:251-262`); finding sem os 3 vira só `Risco`
  (`diagnostico.py:519-525`).
- Não inventa: campo ausente fica vazio; `sources` nunca vazio (fallback
  `no_evidence_available` + warning — `diagnostico.py:345-355`).

## 8. Conversation patterns

Não conversacional. Roda como task (síncrona via `/agents` ou async via Celery na
chain). Degrada com elegância: sem IA cai no path de regras; sem auditor na chain
`_consume_auditor_findings` retorna `([], [])` (`diagnostico.py:485-495`); sem
contexto legal `_evaluate_citations` retorna `None` (`diagnostico.py:626-627`).
Sem `process_id` levanta `ValueError` (`diagnostico.py:118-120`).

## 9. Cross-agente

- Participa de **`diagnostico_completo`** `["extrator", "auditor_imovel",
  "legislacao", "diagnostico"]` e de **`gerar_proposta`** `["diagnostico",
  "orcamento"]` (`app/agents/orchestrator.py:33-34`).
- **Consome** `chain_data["auditor_imovel"]` (matriz de cruzamento — primeiro
  movimento) e `chain_data["legislacao"]` (contexto de citação)
  (`diagnostico.py:129-130`, `:179`).
- **Alimenta** `redator` via `chain_data["diagnostico"]` (dual-emit garante que o
  Redator recebe o dict sem patch — `diagnostico.py:12-14`) e `orcamento` na chain
  `gerar_proposta`.
- `auditor_imovel` é non-blocking na chain (ADR-011) — ver `ECOSSISTEMA_AGENTICO.md`.

## 10. Dívidas técnicas próprias

- `lacunas` é **schema-only em V1** — sempre `[]`, populado só quando as skills do
  Redator consumirem lacunas do prompt (`diagnostico.py:417-422`).
- `nivel_risco_geral` fica `None` sem auditor na chain — o LLM não popula esse
  campo diretamente hoje (`diagnostico.py:412-415`, `:580-581`).
- Plano de deprecação das chaves antigas (dual-emit) pendente — referenciado em
  `docs/sprints/sprint_a2_diagnostico.md` (`diagnostico.py:444-446`). [caminho do
  doc não verificado neste levantamento].
- Concorrência na geração de versão em `POST /diagnoses` não é tratada; conta com
  o `UniqueConstraint` → 409 (`regulatory.py:173-175`).

## 11. Próximas frentes

- **Camada 2 do Princípio 1:** `PATCH /diagnoses/{version}/validate` fecha a
  camada 1 (assinatura humana + AuditLog hash chain, `regulatory.py:219-244`); o
  gate da camada 2 (rejeitar validação sem `ProcessIssueDecision` em alerta
  crítico) está descrito no header do router (`regulatory.py:11`).
- `matriz_notificacao` / estágio `saneamento`: schema pronto
  (`NotificacaoItem`, `stage_output.py:265-301`); população pelo agente é frente
  futura (a skill descreve, o `execute()` não preenche hoje).

## 12. Validação Isis

- **Não verificado.** Não há, no código lido, marcação de validação fim-a-fim
  pela Isis específica do diagnóstico. A skill `situacao_ambiental_imovel_rural`
  codifica o método da sócia (3 estágios, Mapa de Riscos, "radar não cancela"),
  mas a confirmação de validação em caso real fica como pendência a registrar
  quando ocorrer.
