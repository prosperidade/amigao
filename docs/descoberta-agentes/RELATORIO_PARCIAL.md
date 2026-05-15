# Relatório Parcial de Descoberta — Amigão do Meio Ambiente

**Data:** 2026-05-08
**Branch:** `main` @ `ad1ce5d`
**Audit prévio usado:** `docs/AUDITORIA_FLUXO_2026-04-29.md` (norte estratégico + 13 gaps + plano sprints V→Z), complementado por `docs/progressoIA.md` (histórico Sprints IA-1, IA-2 e seguintes) e `prompt_claude_code_sprints.md` (Sprints -1/0/1 com auditoria de execução em conversa).
**Escopo deste relatório:** Seções 8, 11, 13, 14 (catálogo de tarefas, fluxo humano, pontuação, perguntas).

> Para informações sobre identidade do projeto, stack (FastAPI + PostgreSQL/PostGIS + Redis + Celery + MinIO + LiteLLM + pgvector), domínio (consultoria ambiental brasileira multi-tenant), documentação, integrações, automações existentes, tentativas anteriores com IA e compliance, ver os 3 audits referenciados acima. Estado atual do banco: 25 diplomas legislativos / 1 424 chunks indexados / 18 clientes / 9 imóveis / 28 processos / 46 documentos / 7 drafts.

---

## 8. Catálogo de tarefas candidatas a agente

> 8 tarefas catalogadas. Para cada uma, todos os campos foram preenchidos com base em código real **ou** marcados como `PRECISA CONFIRMAÇÃO HUMANA`. As tarefas C1–C5 já têm agente em produção (mas com gaps relevantes); C6–C8 são lacunas estruturais identificadas pelo audit.

### Tarefa C1 — Extração estruturada de documentos (matrícula, CAR, CCIR, auto de infração, licença)

- **Descrição em uma frase:** transformar PDF/imagem de documento ambiental ou fundiário em campos estruturados (área, CAR-ID, número de matrícula, partes, datas, polígono).
- **Onde acontece hoje:** `ExtratorAgent` em `app/agents/extrator.py:16` invocado por `app/workers/agent_tasks.py` e por `POST /intake/drafts/{id}/import`. 51 execuções históricas (mais usado do sistema) — ver `ai_jobs WHERE agent_name='extrator'`.
- **Input concreto:** `Document.extracted_text` (Text) já populado por OCR + `doc_type` (enum) + `document_id`.
- **Output concreto:** `dict` de `extracted_fields` persistido em `AIJob.output_data` (JSONB). Exemplo conhecido: 13 campos por CAR documentados na sessão de 2026-05-08 (memória S314, observação 2014).
- **Frequência:** sob demanda — a cada upload no Intake ou Workspace, em batch quando consultor reabre processo.
- **Critério de sucesso verificável:** `fields_count > 0` + validação por schema esperado por `doc_type` em `app/services/document_extractor.py`. Hoje retorna `requires_review=True` automaticamente — humano sempre confere.
- **Risco se for feito errado:** **médio** — número de matrícula errado contamina cadastro e diagnóstico, mas há revisão humana antes de virar peça oficial.
- **Reversibilidade:** totalmente reversível — `extracted_fields` fica no `AIJob` e em `Document.extracted_text`; nada disso é commitado em `Client`/`Property` sem o passo de auto-fill (Sprint V A1) cuja origem fica registrada em `Client.field_sources`.
- **Tempo humano gasto hoje:** 5–15 min por documento se fosse digitação manual; com a IA o consultor só revisa.
- **Padrão de arquitetura sugerido (preliminar):** **agente único com evaluator** (campos por documento têm validação determinística — CPF/CNPJ válido, área > 0, CAR-ID com formato regex). O orquestrador `diagnostico_completo` (Sprint IA-2) já encadeia extrator → legislacao → diagnostico.
- **Tools que já existem e podem ser reaproveitadas:** `document_extractor.extract_document_fields`, `ai_gateway.complete()` com fallback OpenAI/Gemini/Claude, fila Celery `agent_tasks.run_agent`.
- **Tools que precisariam ser criadas:** validador formal de CPF/CNPJ + checagem de coerência de área CAR vs. matrícula (existe parcial no `auditor_imovel` proposto pelo audit — gap I3).
- **Skills de domínio que precisariam ser criadas:** `extrator/matricula_generica.md`, `extrator/car_sicar.md` (pendência da Sprint 1 do `prompt_claude_code_sprints.md`, ainda não implementadas — não há `app/skills/`).
- **Evidências:** `app/agents/extrator.py:27-87`, `app/services/document_extractor.py`, Audit § B Backend (gap A4 source intake/workspace), Sprint -1 Tarefa D (cache `extracted_text`).

### Tarefa C2 — Geração de documentos formais (PRAD, memorial CAR, ofício SEMAD/IBAMA, resposta a notificação, proposta)

- **Descrição em uma frase:** redigir peças jurídico-técnicas a partir do contexto do processo + corpus legislativo + dados do cliente/imóvel.
- **Onde acontece hoje:** `RedatorAgent` em `app/agents/redator.py:18` com 7 templates (`prad`, `memorial`, `oficio`, `proposta`, `resposta_notificacao`, `contrato`, `comunicacao`). Geração suplementar via `app/services/proposal_generator.py` (301 linhas) e `app/services/contract_generator.py` (243 linhas).
- **Input concreto:** `process_data` (carregado por `_load_process_context`), `legal_data` (chain do `legislacao`), `client_data`, `property_data`, `instructions` em texto livre, `document_template`.
- **Output concreto:** texto/markdown estruturado + `requires_review=True` por padrão; PDF gerado por `app/workers/pdf_generator.py`.
- **Frequência:** sob demanda — múltiplas vezes por caso ativo (1 PRAD, vários ofícios de réplica em retificação CAR, 1 proposta inicial).
- **Critério de sucesso verificável:** **PARCIAL** — hoje só "LLM retornou texto > X chars". Audit propõe schema por macroetapa (gap B2). Validação real é feita pelo consultor no aceite.
- **Risco se for feito errado:** **alto** — peça com erro factual ou citação legal inventada vai para o órgão e tem consequência regulatória/processual. Mitigado por `requires_review=True` + revisão humana obrigatória.
- **Reversibilidade:** totalmente reversível enquanto não for assinada/protocolada; o documento gerado fica em MinIO com versão.
- **Tempo humano gasto hoje:** 1–3 h por peça se redigida do zero; com IA estima-se 20-40 min de revisão (PRECISA CONFIRMAÇÃO HUMANA do tempo real).
- **Padrão de arquitetura sugerido (preliminar):** **orchestrator-workers** — chain `legislacao → redator → evaluator factual` (todo artigo citado tem que estar em `legislation_context`). A Sprint 1 do `prompt_claude_code_sprints.md` propõe skill `redator/oficio_semad.md` com checklist de validação ("todo artigo citado aparece no `legislation_context`?") — ainda não implementada.
- **Tools que já existem e podem ser reaproveitadas:** `legislacao` agent (consulta RAG via `knowledge_catalog.search`, commit `3b6a6c5`), `pdf_generator` worker, `redator_*` prompts no banco com fallback hardcoded.
- **Tools que precisariam ser criadas:** evaluator de citação legal (verifica se cada `Lei N/AAAA` citada está em `knowledge_catalog`), gerador de cabeçalho a partir de `Tenant`/`User`.
- **Skills de domínio que precisariam ser criadas:** `redator/oficio_semad.md`, `redator/memorial_car.md`, `redator/prad.md` (definidas no prompt mas não escritas — exigem PDFs-gabarito da sócia, gate § 3.1 do `prompt_claude_code_sprints.md`).
- **Evidências:** `app/agents/redator.py:18-60`, `app/services/proposal_generator.py`, `app/services/contract_generator.py`, prompt `prompt_claude_code_sprints.md` § 3.5, Audit § B Frontend gap F2.

### Tarefa C3 — Consulta regulatória com RAG (legislação federal + estadual)

- **Descrição em uma frase:** responder pergunta jurídica do consultor citando artigos específicos de leis/decretos/resoluções aplicáveis ao caso (UF + tipo de demanda + agência).
- **Onde acontece hoje:** `LegislacaoAgent` em `app/agents/legislacao.py` (commit `3b6a6c5` conectou ao `knowledge_catalog`). 11 execuções históricas, $0.0047 acumulado.
- **Input concreto:** `query` (texto livre), `demand_type` (enum: car, retificacao_car, licenciamento, regularizacao_fundiaria, outorga, defesa, compensacao, exigencia_bancaria), `state` (UF), `agency` (IBAMA, SEMAD, ICMBio, etc.).
- **Output concreto:** `legislation_context` com lista de artigos + resposta narrativa do LLM. Modelo Gemini 2.0 Flash quando contexto < 800 K tokens, Gemini 1.5 Pro acima (roteamento implementado em `app/agents/legislacao.py`).
- **Frequência:** sob demanda — 1–5x por caso ativo, mais em casos de exigência bancária ou notificação.
- **Critério de sucesso verificável:** **VERIFICÁVEL** — "Resposta cita pelo menos 1 artigo presente em `knowledge_catalog`?". Hoje não há gate automático, é validado em revisão humana.
- **Risco se for feito errado:** **alto** — alucinação de lei inexistente ou citação de artigo revogado leva consultor a fundamentação errada. Mitigado pelo RAG (só cita o que está no banco), mas ainda sem evaluator que **bloqueie** citações fora do contexto.
- **Reversibilidade:** totalmente reversível — só consulta, não persiste decisão.
- **Tempo humano gasto hoje:** 30 min – 2 h de pesquisa manual por consulta jurídica complexa.
- **Padrão de arquitetura sugerido (preliminar):** **agente único com evaluator** + RAG. Já é o desenho atual; falta o evaluator de citação.
- **Tools que já existem e podem ser reaproveitadas:** `app/services/knowledge_catalog.py` (busca semântica pgvector cosseno), `app/services/embeddings.py` (Gemini text-embedding-004 → migrado para `gemini-embedding-001` em `03ccda9`), filtro `demand_type` corrigido na Sprint -1 C.
- **Tools que precisariam ser criadas:** evaluator que valida cada citação contra `knowledge_catalog`; tool de normalização de identificador de norma ("Lei nº 12.651/2012" vs "Lei 12651/12").
- **Skills de domínio que precisariam ser criadas:** PRECISA CONFIRMAÇÃO HUMANA — possivelmente não há skill procedural pra isso; o prompt já é suficientemente específico.
- **Evidências:** `app/agents/legislacao.py`, commit `3b6a6c5` (`feat(sprint-v): agente legislacao consome knowledge_catalog (RAG)`), Audit § B Agentes IA gap I1, Sprint 0 § 2.3.

### Tarefa C4 — Triagem/classificação de demanda no Intake

- **Descrição em uma frase:** ler texto livre + documentos iniciais e classificar tipo de demanda (CAR, retificação, licenciamento, defesa, etc.) + urgência + sugerir macroetapa inicial.
- **Onde acontece hoje:** `AtendimentoAgent` em `app/agents/atendimento.py` + `app/services/llm_classifier.py` + `app/services/intake_classifier.py` (388 linhas). 4 execuções históricas como `agent_name='atendimento'`.
- **Input concreto:** texto livre da entrevista + documentos do draft (`intake_drafts.documents`).
- **Output concreto:** `demand_type` (enum), `confidence` (float), `requires_review` (bool), `suggested_next_macroetapa`.
- **Frequência:** 1× por novo caso (ao confirmar draft → criar processo).
- **Critério de sucesso verificável:** classificação confere com a do consultor em ≥80% dos casos. Hoje não medido — PRECISA CONFIRMAÇÃO HUMANA da taxa real.
- **Risco se for feito errado:** **baixo** — só sugere; consultor confirma. Erro custa só re-roteamento manual.
- **Reversibilidade:** totalmente reversível.
- **Tempo humano gasto hoje:** 5–10 min de leitura por caso.
- **Padrão de arquitetura sugerido (preliminar):** **workflow simples 2-stage** (já é o desenho — regras determinísticas primeiro, LLM só na incerteza, ver `llm_classifier.py`).
- **Tools que já existem e podem ser reaproveitadas:** `intake_classifier`, `llm_classifier`, `llm_classifier.classify_with_rules`.
- **Tools que precisariam ser criadas:** logger de "classificação X foi corrigida pra Y pelo consultor" → feedback loop pra melhorar regras.
- **Skills de domínio que precisariam ser criadas:** PRECISA CONFIRMAÇÃO HUMANA (provavelmente nenhuma — é classificação simples).
- **Evidências:** `app/agents/atendimento.py`, `app/services/intake_classifier.py:1-388`, `app/services/llm_classifier.py`, audit § Resumo Executivo passo 1.

### Tarefa C5 — Diagnóstico preliminar do imóvel (cruzamento entre documentos)

- **Descrição em uma frase:** combinar matrícula + CAR + CCIR + entrevista + documentos para gerar hipótese regulatória, riscos, lacunas e checklist documental.
- **Onde acontece hoje:** `DiagnosticoAgent` em `app/agents/diagnostico.py:1-185` (8 execuções, $0.0008 — alto custo nominal por job pequeno). Chain `diagnostico_completo` em `app/agents/orchestrator.py`.
- **Input concreto:** `process_data` agregado, output do `extrator` (campos), output do `legislacao` (contexto legal aplicável).
- **Output concreto:** hipótese textual + lacunas + riscos + checklist sugerido — hoje persistido em `Process.initial_diagnosis` (Text livre, sem schema).
- **Frequência:** 1–2× por caso (preliminar na Entrada da Demanda + revisão na etapa Diagnóstico Técnico). Audit gap #8 aponta que hoje os dois usam o mesmo campo.
- **Critério de sucesso verificável:** **PARCIAL** — não há schema; consultor lê e julga.
- **Risco se for feito errado:** **médio-alto** — hipótese preliminar enviesa toda a coleta documental seguinte. Mitigado por gate humano antes de avançar para a próxima macroetapa.
- **Reversibilidade:** parcialmente reversível — diagnóstico vira histórico no caso.
- **Tempo humano gasto hoje:** 1–4 h por caso.
- **Padrão de arquitetura sugerido (preliminar):** **orchestrator-workers + evaluator**. Audit gap B3 propõe modelo `RegulatoryDiagnosis(content_jsonb, validated_by, version)` para versionar.
- **Tools que já existem e podem ser reaproveitadas:** chain `diagnostico_completo`, `auditor_imovel` (proposto, gap I3, ainda não criado).
- **Tools que precisariam ser criadas:** `auditor_imovel` (cruza matrícula × CAR × CCIR contra regras por UF, gap I3 do audit), gerador de checklist documental por demand_type.
- **Skills de domínio que precisariam ser criadas:** `diagnostico/car_pendencias.md`, `diagnostico/exigencia_bancaria.md` (PRECISA CONFIRMAÇÃO HUMANA de quais cenários priorizar).
- **Evidências:** `app/agents/diagnostico.py`, `app/agents/orchestrator.py`, Audit § A linha 8 ("BLOQUEADO"), Audit § B gap B3 + gap I3.

### Tarefa C6 — Auditoria de inconsistências do imóvel (matrícula × CAR × CCIR)

- **Descrição em uma frase:** detectar e listar discrepâncias entre os documentos do mesmo imóvel (área que diverge entre matrícula e CAR, sobreposição com APP/Reserva, polígono fora da matrícula).
- **Onde acontece hoje:** **NÃO ACONTECE** — gap I3 do audit. Hoje o consultor faz manualmente.
- **Input concreto:** documentos do mesmo `property_id` com campos extraídos + (se houver) `property.geom`.
- **Output concreto:** lista de `regulatory_issues` (entidade ainda inexistente — PRECISA CONFIRMAÇÃO HUMANA do nome final do modelo) com `severity` e link ao documento-fonte.
- **Frequência:** sob demanda + automaticamente após cada novo doc anexado ao mesmo imóvel.
- **Critério de sucesso verificável:** sim — comparação numérica/geométrica determinística (área CAR vs área matrícula com tolerância X%, cálculo de overlay PostGIS).
- **Risco se for feito errado:** **médio** — falso positivo gera retrabalho; falso negativo deixa passar problema regulatório real. Mitigado por revisão humana antes de oficiar o cliente.
- **Reversibilidade:** totalmente reversível.
- **Tempo humano gasto hoje:** 30 min – 1 h por imóvel; é tarefa especializada.
- **Padrão de arquitetura sugerido (preliminar):** **agente único com tools determinísticas** — a maior parte é cálculo (PostGIS overlay, comparação numérica), LLM só explica e prioriza. Sprint Y do audit.
- **Tools que já existem e podem ser reaproveitadas:** PostgreSQL/PostGIS 3.3.4 já instalado; `Property.geom` modelado (mas vazio em todas as 9 propriedades — auditoria do prompt indica 0 com `geom` preenchida; PRECISA CONFIRMAÇÃO HUMANA se mudou).
- **Tools que precisariam ser criadas:** parser de shapefile (Sprint 4 declarada fora-de-escopo no `prompt_claude_code_sprints.md` § 4 mas é pré-requisito desta tarefa), endpoint `GET /properties/{id}/inconsistencies` (gap A3).
- **Skills de domínio que precisariam ser criadas:** `auditor/regras_app.md`, `auditor/sobreposicao_reserva.md`.
- **Evidências:** Audit § B gap I3, gap A3, gap F3; Sprint Y do audit.

### Tarefa C7 — Acompanhamento de respostas de órgãos por e-mail

- **Descrição em uma frase:** ler inbox de e-mail do tenant, identificar mensagens de IBAMA/SEMA/ICMBio, vincular ao processo correto e detectar exigência/notificação/intimação com prazo.
- **Onde acontece hoje:** `AcompanhamentoAgent` em `app/agents/acompanhamento.py` (160 linhas; 1 execução histórica) — wraps de parsing por regex + LLM. Chain `monitoramento` em `app/agents/orchestrator.py`.
- **Input concreto:** corpo + assunto do e-mail + lista de processos abertos do tenant.
- **Output concreto:** `process_id` vinculado, `tipo` (notificação | exigência | despacho | resposta), `prazo_dias`, `acoes_sugeridas`.
- **Frequência:** sob demanda — gatilho seria webhook do IMAP/Gmail. PRECISA CONFIRMAÇÃO HUMANA da integração real (hoje sem connector visível).
- **Critério de sucesso verificável:** verificável — vínculo correto a processo ≥ 90% e detecção de prazo ≥ 95%.
- **Risco se for feito errado:** **alto** — perder prazo de exigência custa ao cliente (perda de licença, multa). Mitigado por revisão humana + monitor `vigia` que controla prazos cadastrados.
- **Reversibilidade:** parcialmente reversível.
- **Tempo humano gasto hoje:** 5–15 min por e-mail; volume cresce com a base de clientes.
- **Padrão de arquitetura sugerido (preliminar):** **agente único com tool de busca em processos abertos** + evaluator de prazo (regex + parsing de data).
- **Tools que já existem e podem ser reaproveitadas:** `acompanhamento` agent + `vigia` agent (deadline tracking sem LLM).
- **Tools que precisariam ser criadas:** connector IMAP/Gmail (PRECISA CONFIRMAÇÃO HUMANA — só achei `app/services/email.py` mas não inspecionei se é só envio).
- **Skills de domínio que precisariam ser criadas:** `acompanhamento/exigencia_semad.md`, `acompanhamento/notificacao_ibama.md` (formatos típicos por órgão).
- **Evidências:** `app/agents/acompanhamento.py:1-160`, `app/agents/orchestrator.py`, `app/agents/vigia.py:1-196`.

### Tarefa C8 — Monitoramento contínuo de novidades legislativas (DOU/DOE/agências)

- **Descrição em uma frase:** varrer Diário Oficial da União, DO estaduais e portais de IBAMA/SEMAD/ICMBio, capturar normas novas com impacto ambiental e atualizar `knowledge_catalog`.
- **Onde acontece hoje:** **PARCIAL** — `app/services/legislation_monitor.py` (205 linhas), `app/workers/legislation_tasks.py`, `app/api/v1/legislation_alerts.py`, agendamentos no Celery Beat (`monitor-legislation-dou-daily`, `monitor-legislation-doe-daily`, `monitor-legislation-agencies-weekly`). Crawlers em `app/services/crawlers/` — Sprint 0 Tarefa C declarou crawlers automatizados como `@TODO Sprint 0.1` e fez ingestão manual via CLI (25 diplomas hoje).
- **Input concreto:** URLs de DOU/DOE + portais de agência.
- **Output concreto:** novos `legislation_documents` com `status='indexed'` + chunks em `knowledge_catalog` (re-índexação automática).
- **Frequência:** diária (DOU/DOE 06:00 BRT) + semanal (agências, segunda 03:00).
- **Critério de sucesso verificável:** sim — contagem de novos diplomas/dia + taxa de cobertura comparada com lista oficial DOU.
- **Risco se for feito errado:** **médio** — perder diploma novo desatualiza RAG, mas isso é detectável e fixable; falso-positivo entulha base.
- **Reversibilidade:** totalmente reversível.
- **Tempo humano gasto hoje:** ~1–2 h/semana de leitura manual de boletins legislativos por consultor.
- **Padrão de arquitetura sugerido (preliminar):** **workflow de ingestão + evaluator de relevância** (regra: keyword "ambiental" + jurisdição + tipo de norma; LLM só descarta cinza). Já existe esqueleto.
- **Tools que já existem e podem ser reaproveitadas:** `scripts/ingest_legislation.py`, `scripts/ingest_federais_canonicos.py`, `app/services/knowledge_catalog.py` (re-indexação idempotente), task Celery `legislation_tasks`.
- **Tools que precisariam ser criadas:** crawlers concretos por portal (DOU/DOE/IBAMA/SEMAD GO/SEMA MT/SEMA MS) — alta variabilidade de UA/captcha. Marcado como `@TODO Sprint 0.1` no `prompt_claude_code_sprints.md`.
- **Skills de domínio que precisariam ser criadas:** `vigia_legis/relevancia_dou.md` (heurística de filtragem).
- **Evidências:** `app/services/legislation_monitor.py:1-205`, `app/workers/legislation_tasks.py`, `app/api/v1/legislation_alerts.py`, Sprint 0 § 2.4 do `prompt_claude_code_sprints.md`, commit `c009bcf` (25 diplomas ingeridos manualmente).

---

## 11. Stakeholders e fluxo humano

- **Quem aprova decisões importantes:**
  - **Consultor ambiental** (perfil JWT `internal`) — aprova: criação de caso a partir do draft (Audit Resumo Executivo passo 4), validação de hipótese de diagnóstico (passo 10), aceite de cada peça gerada pelo `redator` (`requires_review=True` por padrão), avanço entre macroetapas. Evidência: `app/agents/base.py` (lifecycle com `requires_review`), `app/services/macroetapa_engine.py`.
  - **Sócia ambientalista** — define norte estratégico, padrões de etapa (10 elementos), prioridades de sprint. Evidência: Audit § Briefing da sócia; memória `feedback_filter_socia_ideas` ("nem toda ideia dela vira sprint").
  - **Cliente** (perfil JWT `client_portal`) — confirma propostas, aceita contratos. Evidência: `app/agents/base.py`, JWT split com header `X-Auth-Profile` documentado em `CLAUDE.md`.

- **Onde precisa de revisão humana antes de seguir adiante:**
  1. Confirmação do draft do Intake antes de criar processo — `app/api/v1/intake.py:923` (commit do draft) — Audit Resumo Executivo passo 4.
  2. Aceite da hipótese de diagnóstico preliminar — Audit passo 10.
  3. Aceite de toda peça gerada pelo `redator` — `requires_review=True` em `app/agents/redator.py` por padrão.
  4. Auto-fill de Cliente/Imóvel Hub a partir da extração — Sprint V (commit `65110a0`) marca origem em `Client.field_sources` com badge "extraído pela IA" (commit `93355c3`); consultor pode reverter.
  5. Avanço entre macroetapas — `app/services/macroetapa_engine.py` checa gates (PRECISA CONFIRMAÇÃO HUMANA dos gates exatos).
  6. Toda chain de orquestrador para automaticamente quando um agente retorna `requires_review=True` (`stop_on_review=True` default — `progressoIA.md` linha 101).

- **Onde dá pra ser totalmente automatizado sem revisão:**
  - Re-OCR de documentos (cache em `Document.extracted_text`, Sprint -1 D).
  - Re-indexação do `knowledge_catalog` quando novo diploma é ingerido (`feat(sprint-u)` commit `c449df0`).
  - Cálculo de prazos pelo `vigia` (sem LLM, só queries) — `app/agents/vigia.py:1-196`.
  - Crawl de DOU/DOE diário (quando os crawlers existirem) — não decide nada, só ingere.
  - Filtro `demand_type` em buscas legislativas (Sprint -1 C).

- **Stakeholders externos relevantes:**
  - **Órgãos ambientais brasileiros** — IBAMA, ICMBio, SEMAD-GO, SEMA-MT, SEMA-MS (citados em `app/agents/acompanhamento.py`, audit § Hubs).
  - **Bancos** (exigência ambiental para crédito rural) — `demand_type='exigencia_bancaria'` no enum.
  - **Cartórios** (matrículas) e **INCRA** (CCIR).
  - **Plataformas oficiais de norma:** planalto.gov.br, al.go.gov.br, sisconama, SUDEMA-PB, CETESB (utilizadas como fonte na Sprint 0 — commits `c009bcf` e `0a3d758`).
  - **Provedores LLM:** OpenAI, Google (Gemini), Anthropic via LiteLLM (`app/core/ai_gateway.py`).

---

## 13. Pontuação preliminar (1-5) para priorização entre projetos

| Critério | Nota | Justificativa em 1 frase + evidência |
|---|---|---|
| Valor de negócio / urgência | 5 | Diferencial-chave do produto é o agente regulatório com RAG e a auto-alimentação dos Hubs; sem isso o sistema é só CRUD de documentos. Evidência: memória `project_govtech_vision` + Audit § D (Sprint V escolhida pelo "ROI mais alto disponível agora"). |
| Repetitividade das tarefas candidatas | 5 | Histórico real: 51 execuções do `extrator` + 11 do `legislacao` + 8 do `diagnostico` em 25 diplomas ingeridos; todas as 8 tarefas catalogadas se repetem por caso. Evidência: `SELECT agent_name, COUNT(*) FROM ai_jobs`. |
| Clareza dos critérios de sucesso | 3 | Críticas claras para C1/C3/C6/C8 (verificáveis por schema/regex/cálculo); fracas para C2/C5 (julgamento humano prevalece) — Audit gap B2 ("StageOutput sem schema obrigatório") confirma. |
| Maturidade do escopo (doc, dados, infra) | 4 | 3 audits convergentes + corpus de 25 diplomas + pgvector + 10 agentes operacionais + 18 testes novos na Sprint -1; mas frontend tem 3 gaps abertos (F1/F2/F3) e `app/skills/` ainda não existe. |
| Risco/reversibilidade favoráveis | 4 | Quase tudo é reversível (gate humano antes de virar peça oficial); risco residual: peça gerada pelo `redator` que vá direto pra órgão (mitigado por `requires_review=True`); cost cap enforced (Sprint -1 B). |
| Prontidão técnica (tem tools, integrações, etc.) | 4 | LiteLLM + 3 providers + fallback + cost cap + RAG + 7 routers de API + 11 workers Celery + storage MinIO. Faltas conhecidas: parser shapefile (C6), connector IMAP (C7), crawlers DOU/DOE (C8). |
| **Total (soma)** | **25/30** | Projeto altamente pronto para evoluir agentes; diferencial está em fechar **C2-skills** + **C6-auditor** + **C8-crawlers**. |

> Nenhuma nota provisória — todas estão ancoradas em código ou no audit prévio.

---

## 14. Perguntas em aberto

1. **Tempo humano real por peça do `redator`** (Tarefa C2) — o audit não quantifica; estimativas variam 20–40 min para revisão. Quanto a sócia leva hoje em média para revisar um ofício SEMAD?
2. **PDFs-gabarito de ofícios reais** (Sprint 1 § 3.1 do `prompt_claude_code_sprints.md`, gate ainda aberto) — sem 2-3 exemplos da sócia, as skills `redator/oficio_semad.md`, `redator/memorial_car.md` e `redator/prad.md` continuam não escritas. Esse é o bloqueio mais antigo do projeto (15 dias).
3. **Connector de e-mail para `acompanhamento`** (C7) — `app/services/email.py` existe mas só vi referência a envio. Há integração de inbound (IMAP/SES inbound/Gmail webhook) ou está tudo manual hoje?
4. **`Property.geom` em produção** — auditoria de 2026-04-23 declarou "0 propriedades com `geom`"; com 9 propriedades hoje, alguma já tem polígono carregado? Sem isso a Tarefa C6 (auditor) opera só sobre dados textuais.
5. **Taxa de acerto do `AtendimentoAgent`** (C4) — não há instrumentação de "classificação X foi corrigida pra Y pelo consultor". Vale instrumentar antes de evoluir o agente?
6. **Schema obrigatório de `StageOutput` por macroetapa** (Audit gap B2) — quem decide o schema (sócia? consultor sênior?) e em que ordem priorizar as 7 macroetapas?
7. **Modelo `RegulatoryDiagnosis`** (Audit gap B3) — o nome final do modelo (e da entidade `regulatory_issues` citada na Tarefa C6) está confirmado, ou ainda é proposta de audit?
8. **Crawlers DOU/DOE** (C8) — o `prompt_claude_code_sprints.md` § 4 listou crawlers como **fora de escopo** explícito; o audit de 2026-04-29 não retoma. Essa decisão segue de pé ou Sprint W4 (OCR worker já priorizado pela memória S315) tem precedência sobre C8?
9. **Sprint 1 (Skills)** — o `prompt_claude_code_sprints.md` previa Skills como camada procedural; o projeto pulou para Sprint U (RAG) e nunca implementou `app/skills/`. Continua diferida indefinidamente, ou volta junto com C2?
10. **Volume real de casos por consultor** — sem isso a estimativa de "tempo humano gasto" em todas as tarefas é fraca; quantos casos ativos por consultor por semana?
