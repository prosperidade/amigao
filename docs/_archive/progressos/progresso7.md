# Progresso 7 — Skill do Diagnóstico: da auditoria ao pipeline ativo

Padrao deste arquivo:

- linguagem executiva e de historico de execucao
- foco em resultado, decisao, validacao, risco e pendencia
- evitar instrucoes operacionais detalhadas; isso pertence ao `RunbookOperacional.md`

## Projeto: Regente Ambiental
## Referencias: `app/skills/diagnostico/situacao_ambiental_imovel_rural/SKILL.md` v1.1 + `docs/auditoria/MAPA_GAPS_CONFIRMADO_2026-05-23.md` + `docs/arquitetura/FLUXOS_E2E.md` (Fluxo 2)

---

## Objetivo da rodada

Pegar a **skill de diagnostico v1.1** (validada pela socia em 22/05) e levar de "skill escrita no .md" ate **pipeline ponta-a-ponta em producao**, fechando as 4 pecas que ela pressupunha (taxonomia oficial de risco, citation_evaluator no Diagnostico, auditor_imovel, 9 normas-chave indexadas) + ativando-as numa chain real + endpoint de escrita do RegulatoryDiagnosis. Tudo mergeado em `main` e pushado em 2 dias.

---

## Restricao de escopo observada

- **Skill `auditor_imovel/analise_divergencias_documentais` esta sendo escrita pelo coordenador** — a taxonomia da socia (40 alertas, familias, codigo_alerta) virou input para essa skill, mas a **remodelagem do `RegulatoryIssue`** que ela pede e a **sprint seguinte**. Nesta rodada, `RegulatoryIssue.type` continua sendo o enum de 5 valores existente; finding sem tipo proprio cai em `outro` com `finding_type` preservado em `payload` JSONB. Mexer agora = retrabalho garantido.
- **Contratos externos do R1 (rebrand)** — headers `X-Amigao-*` em `alerts.py` e `User-Agent` "Amigao-Meio-Ambiente/1.0" nos 3 crawlers — **nao tocados**. Webhook receiver e allowlists de SEMAs/IBAMA dependem dessas strings; coordenar com consumidores antes. Apenas a docstring de `app/agents/__init__.py` foi rebrandeada (interno, zero risco).
- **`diagnostico.py` nao foi alterado** no PROMPT_3 (decisao explicita). Consumo de `chain_data["auditor_imovel"]` pelo Diagnostico fica para o **PROMPT_4** (proxima rodada).

---

## Sprints executados (4 rodadas, 23-24/05)

### Fase 0 — Auditoria do estado real (PROMPT_1, 23/05)

Auditoria documental confrontada com o codigo. **Surpresa de escopo:** varios gaps que o doc afirmava abertos ja estavam fechados em commits anteriores.

| Achado | Estado real |
|---|---|
| `RegulatoryDiagnosis` + `RegulatoryIssue` versionados | **Ja existiam** (`app/models/regulatory.py:63/118`, Sprint A1 Tarefa D1). Gap B3 da auditoria 2026-04-29 ja estava fechado. |
| `app/agents/memory.py` (MemPalace stub) | **Ja deletado** (commit `757b7de`, Sprint Z). |
| `PROJECT_NAME = "Regente Ambiental"` em `config.py` | **Ja rebrandeado**. Sobravam apenas 9 ocorrencias em arquivos secundarios (todas contratos externos — ver restricao). |
| `feat/ocr-automatico` (memoria dizia "aguarda rebase") | **Branch fantasma** — sem commits exclusivos vs `main`. Apagada localmente; remoto preservado (Andre decide). |
| K3 — 9 normas-chave da skill no `knowledge_catalog` | **9 de 11 ausentes** com `identifier` proprio. So IN SEMAD 1/2024 e CEMAm 259/2024 estavam la. |
| Suite de testes | **411 funcoes em 42 arquivos** (docs diziam 102 e 39 — ambos errados). |
| Pytest e Testcontainers | **Destravado** (commit `0e17ebd` de 17/05, ja vivia). |

Entregaveis:
- `app/skills/diagnostico/situacao_ambiental_imovel_rural/SKILL.md` posicionado (skill v1.0, depois v1.1 validada pela socia)
- `docs/adr/010-loop-aprendizado-consultores.md` (ADR Proposto)
- `docs/auditoria/AUDITORIA_DOCUMENTAL_2026-05-23.md` (insumo)
- `docs/auditoria/MAPA_GAPS_CONFIRMADO_2026-05-23.md` (saida)
- Adendo de convencao de nomenclatura de skills no ADR-006
- Commit unico `7877652`

### Fase 2 — Implementacao das 4 dependencias (PROMPT_2, 23/05)

Em 4 worktrees paralelos isolados.

| Onda | Commit | O que entregou |
|---|---|---|
| 1 (paralela) — A4 | `43ac9d5` | `Risco` estendido para **8+1 campos** (taxonomia oficial + `prioridade_triagem`). Dual-emit via `model_validator(mode='after')` reconciliando ida (antigo->novo) e volta (novo->antigo). `RiscoSeveridade` ganhou `"critico"` (aditivo). Novos: `Divergencia`, `NotificacaoItem`. `DiagnosticoPreliminarContent` ganhou 6 campos opcionais. `validate_diagnostic_content(dict)` como gate Pydantic↔JSONB. |
| 1 (paralela) — K3 | `92f6376` | 9 normas-chave ingeridas no `knowledge_catalog` via `scripts/ingest_normas_k3.py`. IN SEMAD 3/2025 (55), IN SEMAD 7/2024 (8), Lei GO 18.102/2013 (128), 18.104/2013 (96), 21.231/2022 (48), Decreto GO 9.710/2020 (90), IN INCRA 131/2023 (18 — via OpenAI Vision, escaneado), CONAMA 428/2010 (11), CONAMA 429/2011 (12). **+466 chunks novos.** |
| 2 (apos 1) — A3 | `5c4dd33` | `citation_evaluator` no `DiagnosticoAgent` espelhando padrao do Redator. Citaçoes de `situacao_geral + passivos + acoes + observacoes` cruzadas com `chain_data["legislacao"]["legislacao_aplicavel"]/normas_estaduais/rag_chunks_meta`. Citaçoes sem match viram `citation_issues` no payload — nao derrubam execucao. |
| 2 (apos 1) — A2 | `1830e70` | `AuditorImovelAgent` registrado + `app/services/property_audit.py` deterministico (matricula × CAR × CCIR/ITR + GEO INCRA + RL averbada × declarada). LLM **nao** faz a conta. Persiste `RegulatoryIssue` por finding. Sem `geom`, marca verificacao espacial como pendente e nao quebra (radar-nao-cancela). |

Apos as Ondas:
- `1aa8274` — atualiza `ESTADO_ATUAL.md` e `GOVERNANCA_IA.md` com numeros reais e pecas vivas
- `f9f559d` — rebrand parcial seguro (docstring interna)
- `c6eac9e` — teste de regressao do A4 vs LegislacaoAgent (15 invariantes do dual-emit, exigencia explicita do Andre: provar que `Risco` compartilhado nao quebra `EnquadramentoRegulatorioContent.riscos`)

### Pos-Fase 2 — Quitar dividas (PROMPT_3, 24/05)

Tres ondas em paralelo, branches separadas pra contextos disjuntos.

| Onda | Branch | Commits | O que entregou |
|---|---|---|---|
| A (4 falhas pre-existentes) | `chore/fix-pre-existing-test-failures` | 5 (`e9c1a00`, `d9c021d`, `9ea9069`, `742a398`, `d062f71`) | `pytest.approx` no #1 (float); aceita 202 no #2 (endpoint virou async); `cost_usd=0.0` no #4 (sem `or None` — auditabilidade); `_load_tenant_logo` ganhou degradacao graciosa + `warnings` no payload no #3 (radar-nao-cancela aplicado ao codigo). |
| B (pipeline ativo) | `feat/onda-bc-pipeline-ativacao` | 3 (`6b25602`, `7d6377e`, `b601ac7`) | **B1:** `auditor_imovel` na chain `diagnostico_completo` (extrator->auditor->legislacao->diagnostico) via `NON_BLOCKING_REVIEW_AGENTS` (agente sinaliza review mas pipeline segue). **B2:** `POST /api/v1/processes/{id}/diagnoses` versionado, chama `validate_diagnostic_content` antes de persistir (gate A4 vivo). Fix de serializacao: `exc.errors(include_url=False, include_context=False)`. |
| C (regua de divergencia) | mesma branch B | 1 (`2348096`) | Regua de **4 faixas** validada pela socia: ≤1% informativo, 1-5% atencao, 5-10% alto, >10% critico. **Sempre emite o finding** (areas iguais viram informativo — auditoria sabe que o cruzamento foi feito). Tolerancia configuravel (gravada na evidencia). `grade_overlap_severity()` helper preparado pra D1. |

Merges finais em `main`:
- `357993c` — merge Onda A
- `5e64db4` — merge Fase 2 + Onda B + Onda C

**Push em `origin/main` em 24/05 23:30**: `5e3780a..5e64db4`, 23 commits.

---

## Resumo numerico

| Dimensao | Quantidade |
|----------|------------|
| Rodadas (PROMPTs executados) | 3 (PROMPT_1, PROMPT_2, PROMPT_3) |
| Worktrees isolados criados | 8 (Fase 0, A4, K3, A3, A2, integracao, fix-pre-existing, onda-bc) |
| Commits novos em main (`5e3780a..5e64db4`) | 23 |
| Testes novos | +63 (15 schemas A4 + 15 regressao Legislacao + 7 A3 + 9 auditor + 26 property_audit + 6 orchestrator + 13 POST RegulatoryDiagnosis + 2 pdf_generator degradacao) |
| Suite total apos push | **562 passed, 0 failed** em 12min |
| Chunks novos no `knowledge_catalog` | 466 (9 normas-chave da skill) |
| Endpoints novos | 1 (`POST /processes/{id}/diagnoses`) |
| Agentes registrados ativos | 11 (10 antigos + `auditor_imovel`) |

---

## Decisoes arquiteturais

### Dual-emit do `Risco` via `model_validator`, nao `Field(alias=...)`

O reconcile e **bidirecional** (precisa preencher AMBOS os lados — payload antigo de 3 campos chega, sai com 8+1 preenchidos; payload novo de 8 chega, sai com 3 aliases antigos preenchidos). Alias do Pydantic so renomeia. `_StrictModel` com `extra="forbid"` mantido — anti-drift preservado.

### `RiscoSeveridade` aditivo (`baixo/medio/alto/critico`)

Antes era `Literal["baixo","medio","alto"]`. Adicionar `"critico"` permite mapeamento limpo 1:1 com o novo `grau="critico_impeditivo_potencial"` da taxonomia oficial. Mudanca aditiva — nenhum consumidor existente envia `"critico"` (ja era rejeitado antes), so amplia o que e aceito.

### `NON_BLOCKING_REVIEW_AGENTS` no orchestrator

Principio 1 do manifesto ("a IA propoe, o humano decide e assina") continua valendo: o `auditor_imovel` segue marcando `requires_review=True` (UI exibe badge). O que muda e so o efeito no pipeline em batch: agentes **produtores de findings/contexto** (insumo para chain_data, nao produto final) seguem alimentando os proximos da chain. Sem isso, qualquer chain incluindo auditor_imovel quebraria antes do diagnostico rodar.

Criterio para entrar nesta lista: agente cujo output e INSUMO (chain_data), nao produto final entregue ao consultor. Hoje so `auditor_imovel`. Documentado em `app/agents/orchestrator.py`.

### `AuditFinding.grade` ortogonal a `severity`

Dois eixos convivem:

- `severity` (3 niveis: `info/warning/critical`) — alinha com `RegulatoryIssueSeverity` do model; usado na persistencia.
- `grade` (4 niveis: `informativo/atencao/alto/critico`) — alinha com `RiscoGrau` da skill (taxonomia oficial); usado para sinalizacao no payload e UI.

Mapeamento 4->3 em `_GRADE_TO_SEVERITY`. A distincao alto-vs-critico nao se perde no caminho — a UI consome `grade`, o banco persiste `severity`.

### Regua "sempre emite" — areas iguais viram `informativo`, nao silencio

Auditor e **radar**, nao filtro. Mesmo `Δ=0` entre matricula e CAR vira finding `informativo` ("cruzamento foi feito, sem divergencia detectada"). Antes da Onda C: silencio. Agora: auditoria sabe que o cruzamento ocorreu — base para SLA de "todos os cruzamentos foram executados" em sprint futura.

Excecao: pares com **um lado None** (dado faltante) **nao** viram `area_divergente` — dominio proprio "documento esperado ausente" fica como divida para sprint posterior (precisa de validacao da socia do conjunto canonico por demand_type).

### Radar-nao-cancela aplicado ao proprio sistema (Onda A #3)

O `pdf_generator.generate_process_visit_report` abortava a geracao inteira se MinIO ficasse indisponivel ao buscar logo do tenant. Diagnostico do Andre: "o sistema esta cancelando por motivo banal" — logo e cosmetico, nao conteudo, nenhum orgao indefere por logo. Fix: `_load_tenant_logo` envolvido em try/except amplo, fallback `b""` ja existente para "logo nao cadastrado" estendido para "logo inacessivel". PDF segue sendo gerado; retorno ganhou `warnings: list[str]` (white-label: UI sinaliza ao consultor que o documento saiu sem a marca do tenant). Principio 2 (auditabilidade) preservado — warning sobe ate o caller, nao morre so no log.

### POST `/processes/{id}/diagnoses` versionado, sem PUT/PATCH/DELETE ainda

Cada POST cria nova versao (`MAX(version) + 1`). Workflow de validacao humana (`validated_by_user_id` / `validated_at`) fica para sprint posterior — precisa de UI de aprovacao. Concorrencia no MAX(version)+1 capturada via `UniqueConstraint(process_id, version)` -> IntegrityError -> 500; cenario improvavel pra consultor unico.

Gate Pydantic↔JSONB vivo: `validate_diagnostic_content(payload.content)` antes de persistir. ValidationError vira 422 com `exc.errors(include_url=False, include_context=False)` (custom validators levantam ValueError que nao seria JSON-serializavel — fix `b601ac7`).

---

## Principais arquivos criados/modificados

### Backend
- `app/schemas/stage_output.py` — `Risco` estendido + `Divergencia` + `NotificacaoItem` + `validate_diagnostic_content` + 4 StrEnum/Literal de graus/categorias/status/prioridade
- `app/agents/auditor_imovel.py` (novo) + registro em `app/agents/__init__.py`
- `app/services/property_audit.py` (novo) — bateria deterministica + regua de 4 faixas + helpers `grade_area_divergence` / `grade_overlap_severity`
- `app/agents/diagnostico.py` — `_evaluate_citations` adicionado (Onda A do PROMPT_2 / A3)
- `app/agents/orchestrator.py` — chain `diagnostico_completo` reescrita + `NON_BLOCKING_REVIEW_AGENTS`
- `app/api/v1/regulatory.py` — POST de escrita versionada
- `app/schemas/regulatory.py` — `RegulatoryDiagnosisCreate`
- `app/workers/ocr_tasks.py` — `cost_usd` preservado (Onda A #4)
- `app/workers/pdf_generator.py` — `_load_tenant_logo` degrada graciosamente (Onda A #3)
- `scripts/ingest_normas_k3.py` (novo) — pipeline de ingestao das 9 normas

### Skills e ADR
- `app/skills/diagnostico/situacao_ambiental_imovel_rural/SKILL.md` (v1.1, validada pela socia)
- `docs/adr/010-loop-aprendizado-consultores.md` (Proposto)
- `docs/adr/006-skills-procedurais.md` — adendo de convencao de nomenclatura

### Documentacao
- `docs/auditoria/AUDITORIA_DOCUMENTAL_2026-05-23.md`
- `docs/auditoria/MAPA_GAPS_CONFIRMADO_2026-05-23.md`
- `docs/estado/ESTADO_ATUAL.md` — atualizado com numeros reais e pecas vivas
- `docs/arquitetura/GOVERNANCA_IA.md` — pendencia "citation_evaluator so no Redator" fechada; nova pendencia "auditor_imovel sem chain dedicada" -> fechada pela Onda B; nova divida do `except Exception` generico em pdf_generator.py:234

### Testes (8 arquivos novos + extensoes)
- `tests/agents/test_auditor_imovel.py`
- `tests/agents/test_diagnostico_a3_citations.py`
- `tests/agents/test_legislacao_a4_regressao.py` (15 invariantes do dual-emit)
- `tests/agents/test_orchestrator_chain.py`
- `tests/services/test_property_audit.py`
- `tests/schemas/test_stage_output.py` — estendido com 30+ casos A4 (taxonomia, dual-emit, round-trip, validate utilitario)
- `tests/api/test_regulatory.py` — estendido com `TestCreateDiagnosis` (13 casos do POST)
- `tests/test_pdf_generator.py` — mock correto + caso de degradacao com warning

---

## Aprendizados (memoria de feedback do Andre, salvos em `~/.claude/projects/.../memory/`)

| Memoria | Resumo da regra |
|---|---|
| `feedback_diagnostico_substantivo_falhas.md` | Nunca rotular falha de teste como "pre-existente em main" sem **causa raiz + fix proposto + nivel de risco**. Em resumos, sempre oferecer output dos testes. |
| `feedback_vermelho_canario_e_modelagem.md` | (1) Antes de "ajustar teste", checar o consumidor real — teste vermelho pode ser canario de bug em prod silencioso. (2) `0.0` informativo nunca colapsar com `or None` (Principio 2 auditabilidade). (3) `KeyError` em retorno exige listar paths antes de decidir teste-vs-codigo. |
| `feedback_radar_nao_cancela_sistema.md` | Principio da skill diagnostico vale pro proprio codigo: degradar com elegancia (logo faltou -> PDF sem logo + warning), nunca abortar por motivo banal, sinalizacao sobe ate o retorno. |
| `feedback_extrapolacao_sem_janela.md` | Nunca propor custo recorrente $X/mes sem **confirmar a janela em que a metrica foi observada**. Erro real: assumi mes ao ver "533k cmds Upstash" quando eram 3 dias — 10x diferenca. |

---

## Dividas e pendencias

### Bloqueio operacional (resolver hoje, 25/05)

1. **Upstash Redis Free atingiu cap mensal** (500k cmds; 533k em 3 dias = ~177k/dia; 96% sao reads = polling idle do Celery worker + slowapi + WebSocket pub/sub). **`regente-worker` indisponivel no Render** desde ~3pm de 24/05. Acao imediata: ligar Upstash Pay-as-you-go (~$10/mes nesta taxa). Acao seguinte (apos liga): investigar quem mais usa Redis pra reduzir polling em ~50-70% (target ~$3/mes).

### Pendencias do PROMPT_4 (proxima rodada, NAO executada ainda)

1. **DiagnosticoAgent consumir `chain_data["auditor_imovel"]`** — o auditor produz divergencias, o Diagnostico ainda nao le. Restricao "nao tocar diagnostico.py" do PROMPT_3 foi suspensa no PROMPT_4 (consumir chain_data e exatamente o que estava faltando).
2. **Ato de validacao/assinatura humana do RegulatoryDiagnosis** — POST cria a versao mas nao ha workflow para `validated_by_user_id`/`validated_at`.

### Dividas anotadas (do PROMPT_3 "Backlog consciente" + Onda A)

- **Skill `auditor_imovel/analise_divergencias_documentais/SKILL.md`** — coordenador escrevendo; socia valida em 25/05.
- **Remodelagem do `RegulatoryIssue`**: `familia` (enum estavel ~11) + `codigo_alerta` (catalogo evolutivo, nao enum) + campos novos. Sprint propria, depende da skill acima.
- **Reconciliacao dos 3 conjuntos de status conflitantes**: `status_saneamento` (skill) × `status` do auditor × `decisao_consultor` (5 acoes da P4).
- **Marcador de aplicacao de citacao** (`confirmada`/`aplicacao_preliminar`/`hipotese_a_confirmar`) no `EnquadramentoRegulatorioContent` do Legislacao.
- **Tool deterministica de calculo de uso do solo** (periodo × localizacao juridica — "Regime de compensacao por supressao em GO").
- **Loop de aprendizado com material dos consultores** (ADR-010).
- **`except Exception` generico em `pdf_generator.py:234`** — engole qualquer erro como `{"error": str(e)}` sem `"status"`. Logo foi so o gatilho que o #3 da Onda A pegou; tratamento generico continua fragil.
- **Varredura de testes que dependem de storage externo sem mock** — `#3` da Onda A pode nao ser o unico caso latente.
- **R1 polish dos 8 contratos externos** (`X-Amigao-*` headers + crawlers User-Agent) — risco de quebrar webhook consumer e allowlists de SEMAs; coordenar antes.
- **`feat/ocr-automatico` remoto** — fantasma. Apagada localmente; remoto preservado (Andre confirma `git push origin --delete`).
- **Skills de classificacao e encaminhamento** (planilhas 1.1.2 da socia) — Atendimento + Legislacao; reuniao com Isis.

---

## Estado da base apos esta rodada

- `main` em `5e64db4` (origin sincronizado, pushado em 24/05).
- 11 agentes registrados (10 + `auditor_imovel` ativo na chain `diagnostico_completo`).
- 4 dependencias da skill diagnostico **vivas** (A2 + A3 + A4 + K3).
- Suite **562/562 verde**, 0 falhas.
- Gate Pydantic↔JSONB ativo via `POST /processes/{id}/diagnoses`.
- Knowledge catalog com 9 normas-chave novas (+466 chunks).
- 1 bloqueio operacional (Upstash) impedindo deploy do worker em prod.
