# MUDANÇAS REGENTE — Amigão vs Arquitetura da Sócia

**Fonte:** mapa mental Whimsical "Regente SaaS (arquitetura principal)", fatiado e transcrito em 2026-04-17.
**Arquitetura:** 4 camadas — Entrada / Visão e memória / Operação / Inteligência e governança.

Este documento lista **todos os gaps** identificados entre o Regente (visão da sócia) e o Amigão (código atual), camada por camada, já priorizados pra virar tickets.

---

> ⚠️ **RESTRIÇÃO DE ESCOPO (2026-04-17):** a configuração dos agentes IA já está pronta e **não será alterada agora**. Isso significa:
> - ❌ NÃO revisar prompts, cadeias, ou orchestration dos agentes existentes.
> - ❌ NÃO criar agentes novos.
> - ✅ PODE criar endpoints que **consomem** agentes existentes (ex: `POST /ai/property-summary` chamando `agent_diagnostico`).
> - ✅ PODE adicionar triggers (quando um agente existente é chamado, em que camada), desde que o agente em si não mude.
>
> Itens deste doc que tocam em configuração de agente estão marcados com 🚫 e devem ser deixados para depois.

---

## Legenda de gravidade

- 🔴 **P0** — Mudança conceitual de produto (quebra premissa atual, precisa migração de dados ou UX nova)
- 🟠 **P1** — Feature/bloco que falta (adicionar sem quebrar o que existe)
- 🟡 **P2** — Refinamento (melhorar o que já existe)
- 🔵 **INFO** — Já existe, só confirmar alinhamento

---

## CAMADA 1 — CADASTRO

### Premissa central do Regente

> **"O card nasce mesmo sem documentos completos. O Regente não deve impedir a criação do card por falta documental. Entrada primeiro, organização depois, aprofundamento em seguida."**

### Estado atual no Amigão

- `POST /intake/create-case` ([app/api/v1/intake.py](../app/api/v1/intake.py)) cria Cliente + Imóvel + Processo numa transação.
- `IntakeCreateCaseRequest` ([app/schemas/intake.py](../app/schemas/intake.py)) exige `description` (min 10 chars).
- Classificação (`classify_demand`) roda na criação e **já define o tipo de demanda** e gera checklist.
- Frontend usa wizard de 4 etapas sequenciais ([frontend/src/pages/Intake/IntakeWizard.tsx](../frontend/src/pages/Intake/IntakeWizard.tsx)): Cliente → Demanda → Imóvel → Notas.
- Processo nasce com `status="triagem"`.
- Não existe conceito de "rascunho" nem "estado do cadastro".

### Gaps e mudanças

#### 🔴 CAM1-001 — Tipo de entrada deve ser o PRIMEIRO passo

**Regente:** a tela começa perguntando "**O que você está cadastrando agora?**" com 5 opções:
1. Novo cliente + novo imóvel
2. Cliente existente + novo imóvel
3. Cliente existente + imóvel existente (nova demanda sobre base)
4. Complementar base já iniciada
5. Importar documentos para análise inicial

**Amigão:** o wizard assume cenário (1) como default e só permite "existing client" dentro da etapa 1. Não há opção "complementar base" nem "importar docs".

**Mudança:**
- Adicionar Step 0 ao wizard: "Tipo de entrada" com as 5 opções acima.
- Cada opção deve carregar um fluxo customizado (ex: "complementar base" busca cliente+imóvel já existentes e abre modal de enriquecimento).
- Adicionar campo `entry_type` no `IntakeCreateCaseRequest` e registrar no processo (ou em `intake_notes` JSON).

#### 🔴 CAM1-002 — Descrição da demanda deixa de ser obrigatória

**Regente:** obrigatórios são apenas **nome/razão social, telefone, e-mail, tipo PF/PJ, nome do imóvel**. A `description` entra como "Resumo inicial da demanda" e é desejável, não bloqueante.

**Amigão:** `description: str = Field(..., min_length=10)` no schema força ≥10 chars.

**Mudança:**
- `description: Optional[str]` no `IntakeCreateCaseRequest` e `IntakeClassifyRequest`.
- Backend deve aceitar criação sem description e atribuir `demand_type="nao_identificado"` até um agente ou consultor classificar depois.
- Frontend: tornar o campo descrição opcional na etapa correspondente.

#### 🔴 CAM1-003 — Classificação de demanda não deve travar criação

**Regente:** "A IA não faz diagnóstico técnico, enquadramento regulatório profundo, nem caminho regulatório nesta camada. A IA organiza e prepara a próxima etapa. A IA não decide o caso nesta camada."

**Amigão:** `classify_demand` roda síncrono em `create-case` e **classifica o processo logo na entrada** (gera `initial_diagnosis`, `required_documents`, `suggested_next_steps`). Isso contamina a etapa de Entrada com análise.

**Mudança:**
- Mover classificação para **depois** da criação, via agente assíncrono (`agent_atendimento` ou um novo `agent_triagem`).
- Processo inicial deve nascer com `demand_type=nao_identificado` e `status="entrada_da_demanda"` (ver CAM1-010).
- `initial_diagnosis` só populado após agente processar.
- Manter endpoint `/intake/classify` separado (opcional, para quando o consultor quiser pré-classificar).

#### 🟠 CAM1-004 — Suporte a "Complementar base já iniciada"

**Regente:** cenário onde cliente+imóvel já existem e só adicionamos docs ou enriquecemos dados. Resultado: "Adicionar dados faltantes / Adicionar documentos / Enriquecer base".

**Amigão:** não existe. Pra enriquecer um cliente/imóvel hoje é necessário editar via CRUD direto (Properties, Clients), sem rastro de "esta edição é parte da entrada de uma nova demanda".

**Mudança:**
- Criar endpoint `POST /intake/enrich` que recebe `client_id` + `property_id` + `new_fields` + `new_documents[]` e registra como evento de "base complementada".
- Gerar entrada no AuditLog.
- UI: em "Complementar base", listar campos faltantes e oferecer upload direto.

#### 🟠 CAM1-005 — Suporte a "Importar documentos para análise inicial"

**Regente:** cenário "Subir arquivos → Ler arquivos com IA → Sugerir preenchimento da base". Permite que o consultor jogue um pacote de docs e a IA preencha o cadastro.

**Amigão:** upload de documentos só acontece **depois** do processo criado (via `/documents/upload`). Não existe OCR/extração de campos.

**Mudança:**
- Criar endpoint `POST /intake/import-documents` que aceita múltiplos arquivos.
- Worker Celery roda OCR + extração (regras + LiteLLM) de campos estruturados: CPF/CNPJ, nome, matrícula, CAR, área, município.
- Retorna um **pré-preenchimento** que o consultor confirma/edita antes de criar o card.
- Reaproveitar agente `ai_summarizer` ou criar `agent_document_reader`.

#### 🟠 CAM1-006 — "Dados desejáveis" separados de "Dados mínimos"

**Regente:** distingue explicitamente:
- **Obrigatórios** (mínimos): nome, telefone, e-mail, tipo PF/PJ, nome do imóvel, resumo.
- **Desejáveis**: CPF/CNPJ, endereço, matrícula, CAR, CCIR, KML.

**Amigão:** schema atual trata todos como `Optional` exceto `full_name`, `name` (property) e `description`. Não há distinção visual ou de validação entre "mínimo" e "desejável".

**Mudança:**
- Reforçar no schema: `email`, `phone`, `client_type` como obrigatórios no `IntakeClientCreate` (atualmente são opcionais!).
- UI: agrupar campos em duas seções visuais — "Dados mínimos" (bordas verdes, obrigatórios) e "Dados desejáveis" (colapsável, opcional).

#### 🟠 CAM1-007 — Upload opcional multi-tipo com estados do documento

**Regente:** "Bloco 3 — Upload opcional" aceita 7 tipos (matrícula, CCIR, CAR, CPF/CNPJ, comprovante de endereço, contrato societário, KML). Cada doc tem estados: **Enviado / Não enviado / Em leitura / Lido**.

**Amigão:** existe `DocumentStatus` no model, mas:
- Não é exposto no intake (upload só após processo criado).
- Estados atuais não incluem "em leitura" (OCR em andamento).

**Mudança:**
- Adicionar estado `processing` ou `reading` no enum `DocumentStatus`.
- No wizard de intake, adicionar Step "Upload opcional" com dropzone multi-tipo e indicador de estado por arquivo.
- Quando usuário anexa na entrada, vincula ao processo no commit final.

#### 🔴 CAM1-008 — Estados do cadastro (Rascunho → Pronto → Criado → Complementado)

**Regente:** 4 estados formais:
1. **Rascunho** — faltam dados mínimos, não pode criar card.
2. **Pronto para criar card** — base mínima OK.
3. **Card criado** — já está no fluxo.
4. **Base complementada** — documentos anexados, próxima etapa preparada.

**Amigão:** não existe estado intermediário. Ou o formulário é submetido (cria tudo) ou é descartado.

**Mudança:**
- Criar tabela/model `IntakeDraft` (ou campo `intake_state` no Process + status flag) com os 4 estados.
- `POST /intake/draft` cria/atualiza rascunho. `POST /intake/draft/{id}/commit` converte em processo real.
- Frontend: botão "Salvar e continuar depois" + indicador visual do estado atual.
- Rascunhos devem ser visíveis numa tela "Meus rascunhos" ou badge no sidebar.

#### 🔴 CAM1-009 — CTA secundário "Salvar e continuar depois"

**Regente:** Bloco 4 (Saída) tem **dois CTAs**:
- Principal: "Criar card na Entrada da demanda"
- Secundário: "Salvar e continuar depois"

**Amigão:** wizard só tem "Criar caso" (step 4 → submit). Abandonar o formulário perde tudo.

**Mudança:** depende de CAM1-008 (precisa de rascunho persistido). Botão secundário salva estado do formulário.

#### 🔴 CAM1-010 — Etapa "Entrada da demanda" como estado inicial do fluxo

**Regente:** regra explícita:
> "O caso NÃO vai direto para Diagnóstico preliminar. Ele nasce primeiro em Entrada da demanda. Daí o consultor complementa documentos. Daí o consultor organiza a passagem para a próxima etapa."

**Amigão:** processo nasce com `status="triagem"`. Não há etapa formal "Entrada da demanda" no enum de macroetapas.

**Mudança:**
- Validar se o enum de macroetapas (Plano Mestre v2 — 7 macroetapas) já tem "Entrada da demanda" como primeira. Se não, adicionar.
- Status inicial do Process deve ser `entrada_demanda` (ou equivalente).
- Transição para "Diagnóstico preliminar" precisa ser **explícita** (ação do consultor) — não automática.

#### 🟠 CAM1-011 — Saída da camada (card com dados estruturados)

**Regente:** ao criar o card, ele deve mostrar:
- Nome do cliente, e-mail, telefone
- Nome da fazenda/imóvel
- Resumo curto da demanda
- Status da entrada
- Indicador de documentos anexados/pendentes

Mais: **"Gate de prontidão para próxima etapa"** com flags:
- Base mínima criada
- Base complementada
- Faltam documentos para diagnóstico preliminar

**Amigão:** card do processo mostra título + tipo + status. Não mostra indicador documental consolidado nem gate de prontidão.

**Mudança:**
- Adicionar campos computados ao retorno de `/processes/{id}`: `has_minimal_base`, `has_complementary_base`, `missing_docs_for_diagnosis`.
- UI do card na lista: adicionar badges de gate (verde/amarelo/vermelho).

#### 🟡 CAM1-012 — Campo "Resumo da demanda" separado de descrição livre

**Regente:** dentro dos "Dados mínimos" tem explicitamente "**Resumo inicial da demanda comentada pelo cliente no primeiro contato**" — parece ser um campo curto, não a descrição técnica.

**Amigão:** só tem `description` (texto livre). `intake_notes` existe como campo extra mas sem semântica clara.

**Mudança:**
- Renomear/dividir: `initial_summary` (resumo do primeiro contato, curto, voz do cliente) vs `description` (descrição técnica elaborada pelo consultor).
- Ou usar `intake_notes` pra notas internas e `description` vira o resumo.

#### 🟡 CAM1-013 — "Dados mínimos do imóvel" inclui área

**Regente:** "Nome do imóvel ou fazenda, **Área do imóvel quando conhecida**".

**Amigão:** `IntakePropertyCreate.area_hectares: Optional[float]`. OK, já existe.

**Status:** 🔵 INFO — já alinhado.

#### 🚫 CAM1-014 — Papel da IA explicitado (ADIADO — mexe em config de agente)

**Regente:** a IA desta camada só extrai/sugere, não decide. Não faz diagnóstico técnico nem caminho regulatório.

**Amigão:** risco de agente `atendimento` fazer "diagnóstico" indevido nesta camada.

**Decisão:** adiado. Config de agentes não será tocada agora. Quando for reaberto: revisar prompt de `agent_atendimento`, adicionar guard rail no orchestrator.

---

## CAMADA 2 — CLIENTE HUB

### Premissa central do Regente

> **"Cliente é relação, não território. O Cliente Hub é memória executiva e relacional — não substitui o Imóvel Hub (técnico) nem o Workspace (operacional). Deve sempre abrir caminhos para outras telas."**

### Estado atual no Amigão

- Não existe um "Cliente Hub" unificado no painel interno.
- Edição de cliente é CRUD simples (sem consolidação de histórico, imóveis, casos, contratos).
- Portal do cliente (Next.js) é a view do próprio cliente — não é o hub 360° do consultor.

### Gaps e mudanças

#### 🔴 CAM2CH-001 — Criar tela "Cliente Hub" no painel interno

**Mudança:** nova rota `/clients/{id}/hub` (ou `/clientes/{id}`) consolidando todos os blocos abaixo.

#### 🔴 CAM2CH-002 — Cabeçalho do cliente (Bloco 1)

Deve conter:
- Identificação: nome/razão social, client_id, CPF/CNPJ, telefone, e-mail, endereço, tipo PF/PJ.
- **Status do cliente** (novo enum): `ativo`, `em_andamento`, `cancelado`, etc.
- **Chips**: cliente ativo, com casos em andamento, sem pendência contratual, com pendência documental, PF/PJ.
- **Ações rápidas**: Novo caso, Ver contratos, Ver diagnósticos, Adicionar imóvel, Gerar resumo, Ver documentos.

**Mudança backend:** adicionar campo `status` no model `Client` (enum). Endpoint agregador `/clients/{id}/summary` com flags computadas.

#### 🔴 CAM2CH-003 — Dashboard resumido (Bloco 2) — cards do cliente

Cards: imóveis vinculados, casos ativos, casos concluídos, contratos emitidos, diagnósticos realizados, pendências críticas, última movimentação.

**Mudança:** queries agregadas (cuidado com N+1) — ver [audit_april_2026.md] na memory. Talvez criar service `ClientSummaryService`.

#### 🔴 CAM2CH-004 — Lista de imóveis vinculados (Bloco 3)

Tabela com: nome, imovel_id, matrícula, CAR, município/UF, área, status geral, etapa atual do caso principal, última atividade. CTA por linha: Abrir Imóvel Hub, Abrir workspace, Novo caso neste imóvel.

**Mudança:** endpoint `/clients/{id}/properties-with-status` (junta Property + último Process + métricas).

#### 🟠 CAM2CH-005 — Atividades por imóvel (Bloco 4) — mini timeline

Eventos por imóvel: cadastro criado, diagnóstico preliminar, coleta documental, diagnóstico técnico, rota regulatória, proposta enviada, contrato formalizado. Formato: mini timeline ou badges por etapa.

**Mudança:** reaproveitar tabela de eventos do processo (se existir) ou criar `PropertyEvent`. Ver se `AuditLog` atende.

#### 🟠 CAM2CH-006 — Timeline do cliente (Bloco 5) — histórico da relação

Eventos: cliente criado, imóvel adicionado, caso aberto, documento enviado, diagnóstico gerado, proposta enviada, contrato assinado, caso concluído, observação importante.

**Mudança:** endpoint `/clients/{id}/timeline` com eventos ordenados. Reutilizar AuditLog filtrado por entity_type in (client, property, process, document, proposal, contract) + client_id.

#### 🔴 CAM2CH-007 — Painel lateral de IA (Bloco 6)

Exemplo real do Regente:
> "Cliente com 3 imóveis vinculados, 2 casos ativos e 1 contrato emitido. O imóvel Fazenda Boa Vista concentra a principal pendência atual..."

**Agentes relevantes:** `agent_atendimento`, `agent_acompanhamento`, `agent_vigia`.

**Mudança:**
- Novo agente `agent_client_summary` (ou reutilizar `acompanhamento` com contexto de cliente).
- Endpoint `POST /ai/client-summary/{client_id}` retorna resumo executivo.
- UI: painel lateral colapsável no Cliente Hub.

#### 🟠 CAM2CH-008 — Abas internas do Hub

5 abas: Visão geral / Imóveis / Casos / Contratos / Histórico.

**Mudança:** componente com tabs já existe em outras páginas (DiagnosisTab etc.). Reaproveitar padrão.

#### 🟠 CAM2CH-009 — Estados do Cliente Hub

5 estados: recém-criado, em construção, ativo, com alertas, consolidado.

**Mudança:** computar estado dinamicamente na API (não salvar). Regra:
- recém-criado: <7 dias e sem imóveis
- em construção: imóveis sendo adicionados
- ativo: ≥2 imóveis ou ≥1 caso ativo
- com alertas: tem pendência crítica
- consolidado: ≥5 casos concluídos

---

## CAMADA 2 — DASHBOARD

### Premissa central do Regente

> **"O Dashboard deve ser executivo, não operacional profundo. Combina volume e prioridade. Em poucos segundos o usuário entende saúde da operação, gargalo principal, prioridade do dia."**

### Estado atual no Amigão

- Dashboard existe ([frontend/src/pages/Dashboard](../frontend/src/pages/Dashboard)) mas conteúdo é básico (cards de contagem).
- Não tem bloco de gargalos, prioridade do dia, leitura da IA.
- Distribuição por etapa não é apresentada.

### Gaps e mudanças

#### 🔴 CAM2D-001 — Bloco 3: Casos por etapa (7 estágios)

Distribuição do volume pelos 7 estágios do Regente:
1. Entrada da demanda
2. Diagnóstico preliminar
3. Coleta documental
4. Diagnóstico técnico consolidado
5. Definição do caminho regulatório
6. Orçamento e negociação
7. Contrato e formalização

**Formato:** gráfico de barras, cards por etapa, ou mini funil. Mostrar tempo médio por etapa, quantidade travada, % de avanço.

**Mudança:**
- Verificar se as 7 macroetapas do Plano Mestre v2 correspondem a essas.
- Endpoint `/dashboard/cases-by-stage` com agregação.
- UI: adicionar componente `CasesByStageChart`.

#### 🔴 CAM2D-002 — Bloco 4: Gargalos e alertas críticos

Cards de alerta como:
- "5 casos com matrícula pendente"
- "3 casos travados na coleta documental"
- "2 contratos aguardando assinatura"
- "1 imóvel com inconsistência crítica entre CAR e matrícula"

**Mudança:**
- Nova tabela `DashboardAlert` (ou computar dinamicamente).
- Regras de alerta: casos parados >N dias, pendência impeditiva, contratos não assinados >X dias.
- Reaproveitar `agent_vigia` para gerar alertas.

#### 🔴 CAM2D-003 — Bloco 5: Casos prioritários do dia

Lista com: cliente, imóvel, etapa, urgência, motivo da prioridade, próximo passo, responsável.

**Mudança:**
- Endpoint `/dashboard/priority-cases` com ranking (urgência + dias parados + pendências).
- UI: tabela compacta no dashboard.

#### 🔴 CAM2D-004 — Bloco 6: Leitura executiva da IA

Exemplo real:
> "Hoje o maior gargalo está em Coleta Documental. 5 casos possuem pendência impeditiva e 2 contratos aguardam assinatura. Priorize primeiro os casos com urgência alta e documentação crítica faltante."

**Agentes:** `agent_vigia`, `agent_acompanhamento`.

**Mudança:**
- Novo endpoint `POST /ai/dashboard-summary` (cacheable, gerado 1x/hora).
- Componente `DashboardAISummary` no topo ou lateral.

#### 🟠 CAM2D-005 — Filtros executivos

Por período, responsável, tipo de demanda, município/UF, urgência, PF/PJ, status documental.

**Mudança:** query params em todos endpoints de dashboard. UI: barra de filtros fixa.

#### 🟠 CAM2D-006 — Visualizações alternativas

Por responsável, por etapa, de gargalos, contratual/comercial.

**Mudança:** tabs no dashboard ou seletor de "visão".

#### 🟡 CAM2D-007 — Ações rápidas no cabeçalho

"Novo caso" e "Ir para fluxo de trabalho" no header.

**Mudança:** simples — adicionar botões no componente existente.

---

## CAMADA 2 — IMÓVEL HUB

### Premissa central do Regente

> **"O imóvel é a unidade técnica principal. Tudo o que é técnico, territorial, fundiário e regulatório fica ancorado nele. O Imóvel Hub é ponto de memória persistente; o workspace é ponto de execução ativa."**

### Estado atual no Amigão

- [frontend/src/pages/Properties/index.tsx](../frontend/src/pages/Properties/index.tsx) é listagem simples (tabela CRUD).
- Não existe "hub" por imóvel com abas, análises, histórico, IA consolidada.
- Documentos são vinculados ao processo, não ao imóvel (possível gap de modelagem).
- Não há score de maturidade nem indicadores de saúde.

### Gaps e mudanças

#### 🔴 CAM2IH-001 — Criar tela "Imóvel Hub"

Nova rota `/properties/{id}/hub` (ou `/imoveis/{id}`) com estrutura de 6 blocos + 5 abas abaixo.

#### 🔴 CAM2IH-002 — Bloco 1: Cabeçalho do imóvel

Identificação: nome, imovel_id, cliente vinculado, matrícula principal, CAR, município/UF, área total, status regulatório geral.
Ações rápidas: Abrir workspace do caso, Ver documentos, Adicionar documento, Novo caso, Gerar resumo.
Chips: situação fundiária, status CAR, status geral, qtd. casos vinculados.

**Mudança:** endpoint `/properties/{id}/summary` agregando tudo + campo `regulatory_status` novo.

#### 🔴 CAM2IH-003 — Bloco 2: Dashboard técnico

Cards: área total, matrícula, CAR vigente, situação fundiária, RL averbada/proposta, APP, principais pendências ambientais, última análise, último documento.

**Mudança:** novos campos no model `Property` (ou tabela `PropertyTechnicalData`): `rl_status`, `app_area_ha`, `regulatory_issues[]`.

#### 🔴 CAM2IH-004 — 5 Abas centrais

**Aba 1 — Informações:** dados estruturados (nome, matrícula, registro/livro/folha/ficha, CAR, SNCR/NIRF/CIB, área documental, área gráfica, situação fundiária, localização, descrição de acesso, tipologia, início da operação, observações estratégicas).

**Aba 2 — Documentos:** lista com atributos (nome, tipo, data upload, data geração, origem, status leitura, status validade, versão, vínculo com caso). Categorias: fundiários, ambientais, fiscais/rurais, societários, espaciais, relatórios gerados.

**Aba 3 — Análises:** uso do solo, análises temporais, APP, RL, remanescente de vegetação nativa, área consolidada, servidão, sobreposições, riscos de erro no CAR. Saídas: mapas, notas técnicas, outputs.

**Aba 4 — Histórico:** eventos cronológicos (documento inserido, CAR revisado, matrícula atualizada, análise concluída, caso aberto, etapa movida, proposta emitida, contrato formalizado, observação estratégica).

**Aba 5 — Casos:** ID, tipo demanda, etapa, urgência, responsável, status, última movimentação, próximo passo, botão "Abrir workspace".

**Mudança:**
- Expandir model `Property` com campos técnicos faltantes (SNCR, NIRF, CIB, area_documental vs area_grafica, tipologia, etc.).
- Nova tabela `PropertyAnalysis` (análises técnicas por imóvel).
- Nova tabela `PropertyDocument` OU vincular `Document` atual ao `property_id` (relação many-to-one).
- Eventos históricos: reaproveitar `AuditLog` ou criar `PropertyEvent`.

#### 🔴 CAM2IH-005 — Bloco 4: Painel lateral de IA

Conteúdo: resumo técnico, principais inconsistências detectadas, alertas documentais, pendências relevantes, última leitura consolidada, recomendação de foco.

**Agentes relevantes:** `agent_extrator`, `agent_diagnostico`, `agent_legislacao`.

**Mudança:**
- Endpoint `POST /ai/property-summary/{property_id}`.
- Ou reaproveitar `agent_diagnostico` com contexto de imóvel (não de processo).
- Guard rail: nesta camada a IA NÃO gera proposta, contrato, triagem de lead nem negociação.

#### 🔴 CAM2IH-006 — Bloco 6: Indicadores de saúde (score de maturidade)

Métricas:
- Completude documental (%)
- Consistência cadastral
- Atualização regulatória
- Qtd. pendências críticas
- Presença de análises técnicas suficientes
- Confiança da base

Exemplos: "Documentação: 78% completa", "Base técnica: média", "Pendência crítica: 2", "Situação do CAR: requer revisão".

**Mudança:**
- Service `PropertyHealthScore` que calcula todas as métricas.
- Pode rodar via agent (batch diário) ou on-demand.

#### 🟠 CAM2IH-007 — Separação "Dado bruto / Dado extraído / Dado validado"

**Regente:** "O que foi extraído pela IA convive com o que foi validado pelo humano":
- Dado bruto
- Dado extraído (pela IA)
- Dado validado (pelo humano)
- Observação estratégica

**Amigão:** não existe essa distinção — todo dado é tratado como validado.

**Mudança:**
- Adicionar campo `data_source` em cada campo estruturado: `raw` / `ai_extracted` / `human_validated`.
- UI: badge visual indicando a origem (ícone IA, ícone humano, ícone documento).
- Fluxo de validação: consultor pode promover `ai_extracted` → `human_validated` com 1 clique.

#### 🟠 CAM2IH-008 — Estados do Imóvel Hub

5 estados: recém-criado, em construção, com memória estruturada, com alertas críticos, consolidado.

**Mudança:** computar dinamicamente baseado em qtd. docs, análises, pendências.

#### 🟠 CAM2IH-009 — CTA "Abrir workspace do caso" no Hub

**Regente:** CTA principal do Bloco 5 é "Abrir workspace do caso". O hub aponta sempre pra operação, nunca é "fim de linha".

**Mudança:** botão fixo sempre visível no Imóvel Hub linkando pro processo ativo (ou escolha se houver múltiplos).

#### 🟡 CAM2IH-010 — Categorias de documento

6 categorias sugeridas: fundiários, ambientais, fiscais/rurais, societários, espaciais, relatórios gerados.

**Mudança:** verificar enum atual de `doc_type` / `category` e alinhar.

---

## CAMADA 3 — OPERAÇÃO (Fluxo de trabalho + Workspace do caso)

### Premissa central do Regente

> **"Cadastro abre, Workspace constrói, Fluxo coordena."**
>
> O Fluxo de Trabalho NÃO cria profundidade — ele reflete o estado produzido no Workspace. O Workspace é o dossiê operacional vivo onde cada etapa complementa a memória do caso.

### Estado atual no Amigão

- **Modelo sólido:** `Macroetapa` enum com 7 etapas alinhadas ao Regente ([app/models/macroetapa.py](../app/models/macroetapa.py)).
- `MACROETAPA_TRANSITIONS` (linear 1→7), `DEFAULT_ACTIONS` (checklist por etapa), `MACROETAPA_AGENT_CHAIN` (1 agente por etapa).
- `MacroetapaChecklist` model com `actions[{id, label, completed}]` + `completion_pct`.
- `Process.macroetapa` (String column).
- Frontend tem kanban em [QuadroAcoes.tsx](../frontend/src/pages/Processes/QuadroAcoes.tsx) com drag-and-drop via `/processes/kanban` + `/processes/{id}/macroetapa`.
- Tem `MacroetapaStepper.tsx`, `MacroetapaSidePanel.tsx`, `QuadroProcessCard.tsx`, `LeituraIA.tsx`, `WorkflowTimeline.tsx`, `ProcessDossier.tsx`.

**Boa notícia:** a fundação está bem alinhada. A maior parte dos gaps aqui é de **refinamento semântico e UX** do workspace, não de reconstrução.

---

### A. FLUXO DE TRABALHO (tela coordenadora)

#### 🟠 CAM3FT-001 — Card do caso no kanban com "Próximo passo" + "Badge de alerta"

**Regente:** cada card no kanban mostra:
- Identidade: cliente + imóvel
- Contexto: tipo de demanda, urgência, responsável
- **Estado da etapa** (ver CAM3FT-004): em andamento / aguardando input / aguardando validação / travado / pronto para avançar
- **Próximo passo** (texto curto e acionável): "Validar checklist inicial", "Solicitar matrícula", "Revisar leitura técnica", "Enviar proposta", "Aguardar assinatura"
- **Badge de alerta**: documento pendente, falta validação humana, dependência externa, risco de atraso, pendência crítica

**Amigão:** `QuadroProcessCard.tsx` mostra cliente/título/macroetapa, mas não tem "próximo passo" destacado nem badge de alerta unificado.

**Mudança:**
- Adicionar campo computado `next_step_label` e `alert_badge` no endpoint `/processes/kanban`.
- Regras: próximo passo = primeira action pendente do `MacroetapaChecklist` da etapa atual. Alert = derivado de pendências documentais / dias parados / flags.
- Atualizar `QuadroProcessCard.tsx` pra exibir os dois.

#### 🟠 CAM3FT-002 — Preview Lateral da Etapa

**Regente:** ao clicar num card do kanban, abre um **preview lateral** (não navega pra página cheia). Preview mostra:
- Identidade do caso
- Etapa atual + progresso da etapa
- Resumo curto do que já foi feito
- O que ainda falta
- Leitura curta da IA da etapa
- CTA principal: "Abrir workspace do caso"

**Regra explícita:** "Não é lugar de executar profundamente. É resumo operacional do estado atual."

**Amigão:** existe `MacroetapaSidePanel.tsx` — validar se ele já segue essa regra ou se precisa ajuste.

**Mudança:**
- Auditar `MacroetapaSidePanel.tsx` vs os 7 elementos acima.
- Garantir que é read-only (não executa ações profundas).
- Adicionar CTA "Abrir workspace" caso não tenha.

#### 🔴 CAM3FT-003 — Kanban Macro mostrando qtd. travada / pronta / total por coluna

**Regente:** cada coluna do kanban deve mostrar, no cabeçalho:
- Nome da etapa
- Quantidade total de casos
- Quantidade **travada** (bloqueio impeditivo)
- Quantidade **pronta para avançar** (output mínimo + validações OK)

**Amigão:** atualmente só agrupa por macroetapa e mostra total. Sem desagregação.

**Mudança:**
- Enriquecer `/processes/kanban` pra retornar `per_stage: [{stage, total, blocked, ready_to_advance}]`.
- UI: header de cada coluna com 3 números.

#### 🔴 CAM3FT-004 — Estados formais por etapa (7 estados)

**Regente:** cada etapa pode estar em um destes estados (mais granular que "in_progress/completed"):
1. **Não iniciada**
2. **Em andamento**
3. **Aguardando input** (consultor precisa inserir algo)
4. **Aguardando validação** (IA produziu algo, humano precisa validar)
5. **Travada** (bloqueio impeditivo, ex: documento crítico ausente)
6. **Pronta para avançar** (output mínimo + validações OK)
7. **Concluída**

**Amigão:** `MacroetapaChecklist` só tem `completion_pct` (0.0 → 1.0) e actions com `completed: bool`. Não tem estado agregado semântico.

**Mudança:**
- Adicionar coluna `state` no `MacroetapaChecklist` (enum `MacroetapaState`).
- Regra de cálculo do estado (pode ser derivado on-the-fly):
  - `completion_pct == 0` → não_iniciada
  - pending actions com prazo vencido → travada
  - tem action com `needs_human_validation: true` e não validada → aguardando_validação
  - todas actions completas + sem trava → pronta_para_avançar
  - `completion_pct == 1.0` e etapa concluída → concluída
- Expor no response de `/processes/kanban` e `/processes/{id}`.

#### 🔴 CAM3FT-005 — Regras formais de avanço entre etapas

**Regente:** "O fluxo só deve permitir avanço quando houver":
- **Output mínimo da etapa atual**:
  - Etapa 2 → diagnóstico preliminar estruturado
  - Etapa 3 → dossiê documental mínimo
  - Etapa 4 → resumo técnico consolidado
  - Etapa 5 → rota regulatória definida
  - Etapa 6 → proposta emitida
  - Etapa 7 → contrato assinado
- **Validação humana** quando aplicável (leitura documental, resumo técnico, caminho regulatório, proposta, contrato)
- **Ausência de trava impeditiva** (documento crítico faltando, vínculo não confirmado, campo essencial sem validação, assinatura pendente)

**Amigão:** `is_valid_macroetapa_transition()` só checa se a transição linear é permitida (etapa X → X+1). Não valida output mínimo nem flags humanas.

**Mudança:**
- Criar service `MacroetapaTransitionGuard` que, dado um processo, retorna `{can_advance: bool, blockers: [...]}`.
- Endpoint `/processes/{id}/can-advance` (consulta) e bloqueio em `/processes/{id}/macroetapa` (ação).
- UI: botão "Avançar etapa" desabilitado + tooltip com blockers quando não pode.

#### 🟡 CAM3FT-006 — Filtros operacionais do cabeçalho

Regente lista: responsável, urgência, tipo de demanda, município/UF, etapa, status de prontidão. Busca: cliente / imóvel / caso. Ações rápidas: novo caso, ordenar por prioridade, filtrar travados, filtrar prontos para avançar.

**Mudança:** expandir query params em `/processes/kanban` e adicionar UI de filtros.

#### 🟠 CAM3FT-007 — Leitura Operacional da IA no Fluxo (≠ Dashboard)

**Regente:** bloco específico no Fluxo (não só no Dashboard):
> "Hoje o maior acúmulo está em Coleta Documental. 4 casos aguardam input no workspace e 2 já estão prontos para avançar após validação humana."

Agentes: `agent_vigia`, `agent_acompanhamento`.

**Amigão:** `LeituraIA.tsx` existe. Validar se o conteúdo segue este foco operacional ou se é genérico.

**Mudança:** revisar conteúdo do `LeituraIA.tsx` — deve responder "etapa com maior acúmulo + casos travados + casos prontos + pendências impeditivas + recomendação de foco operacional". Sem diagnóstico técnico aqui.

#### 🟡 CAM3FT-008 — O que o Fluxo NÃO deve fazer (guard rail de UX)

**Regente:** regras explícitas:
- ❌ Não receber documentos profundamente
- ❌ Não editar base técnica do imóvel
- ❌ Não fazer diagnóstico técnico completo
- ❌ Não comparar cenários regulatórios em profundidade
- ❌ Não montar proposta ou contrato

**Mudança:** auditar o `QuadroAcoes.tsx` e telas do kanban para garantir que não permitem upload de docs pesado, edição profunda, nem execução de diagnóstico. Essas ações devem sempre redirecionar para o Workspace.

---

### B. WORKSPACE DO CASO (dossiê operacional vivo)

#### 🔴 CAM3WS-001 — Estrutura fixa do Workspace (layout macro)

**Regente:** layout padrão com 6 áreas:
1. **Cabeçalho do caso**: cliente, imóvel, ID do caso, ID do imóvel, tipo de demanda, urgência, responsável, status geral
2. **Barra horizontal das 7 etapas**: com estados (concluída / ativa / bloqueada / aguardando pré-requisito)
3. **Menu lateral interno**: Visão geral / Ações / Documentos / Dados / IA da etapa / Histórico / Decisões / Saídas
4. **Área central de trabalho**: conteúdo da etapa ativa
5. **Painel lateral direito**: Agente IA da etapa, Alertas, Lacunas, Validação humana necessária, Próxima ação sugerida, Saída esperada da etapa
6. **Rodapé / timeline**: Eventos, Uploads, Mudanças de status, Decisões, Geração de proposta, Geração de contrato

**Amigão:** `ProcessDetail.tsx` existe com tabs (DiagnosisTab, DocumentsTab, TasksTab, TimelineTab, ProcessCommercial, ProcessChecklist, ProcessDossier). Layout é baseado em **tabs verticais**, não no modelo acima.

**Mudança:**
- Refatorar `ProcessDetail.tsx` para o layout 6-áreas.
- Reutilizar tabs existentes como o **menu lateral** (área 3).
- Adicionar o **painel lateral direito** com IA + alertas + próxima ação.
- Garantir barra horizontal das 7 etapas sempre visível no topo (já existe `MacroetapaStepper.tsx` — promover para topo fixo).

#### 🔴 CAM3WS-002 — Tipos de blocos (permanente / ativo / herdado / condicional)

**Regente:** classificação semântica de blocos dentro do workspace:
- **Permanentes**: identificação do caso, cliente, imóvel, status, histórico, timeline, documentos já existentes, dados-base — **sempre visíveis**.
- **Ativos**: módulos da etapa atual — visíveis no centro.
- **Herdados**: conteúdo das etapas anteriores como histórico validado — acessíveis via menu lateral "Histórico".
- **Condicionais**: aparecem só quando aplicável — procuração, contrato societário, documentos complementares, parceiro técnico, campo, passivo relevante, embargo, análise fundiária adicional.

**Amigão:** não tem essa classificação. Tudo é flat.

**Mudança:**
- Adicionar metadado `block_type` em cada componente/seção do workspace.
- Criar lógica de renderização condicional baseada em contexto do caso (ex: procuração aparece se `client.requires_power_of_attorney`).
- Criar tabela `ProcessBlockCondition` ou usar JSON em `Process.conditional_blocks: list[str]`.

#### 🔴 CAM3WS-003 — Arquitetura detalhada por etapa (Objetivo + Ações + IA + Saída)

**Regente:** cada etapa deve ser renderizada no workspace com:
- **Objetivo** (frase única, visível no topo da área central)
- **Ações** (checklist — já existe parcialmente no Amigão via `MacroetapaChecklist`)
- **IA da etapa** (painel lateral direito — quais agentes rodam aqui)
- **Saída esperada** (o que precisa ser produzido pra avançar)

**Amigão:** tem objetivo implícito no nome da etapa. Actions existem. IA existe. Mas não há bloco explícito "saída esperada da etapa".

**Mudança:**
- Adicionar `stage_objective` e `stage_output` em `MACROETAPA_LABELS` ou estrutura similar:
  ```python
  MACROETAPA_METADATA = {
      Macroetapa.entrada_demanda: {
          "label": "Entrada da Demanda",
          "objective": "Transformar o contato inicial em caso formal aberto",
          "expected_output": ["Caso aberto", "Cliente vinculado ou criado", "Ficha inicial mínima gerada"],
      },
      ...
  }
  ```
- Renderizar "Objetivo" em destaque no workspace + "Saída esperada" no painel lateral direito.

#### 🟠 CAM3WS-004 — Multi-agente por etapa (principal + secundários)

**Regente:** cada etapa tem **um agente principal e vários secundários**:

| Etapa | Principais | Secundários |
|---|---|---|
| 1. Entrada | `agent_atendimento` | `agent_extrator`, `agent_vigia` |
| 2. Diagnóstico preliminar | `agent_atendimento`, `agent_diagnostico` | `agent_legislacao`, `agent_extrator` |
| 3. Coleta documental | `agent_extrator` | `agent_vigia`, `agent_acompanhamento` |
| 4. Diagnóstico técnico | `agent_diagnostico` | `agent_extrator`, `agent_legislacao`, `agent_redator` |
| 5. Caminho regulatório | `agent_legislacao` | `agent_diagnostico`, `agent_redator`, `agent_acompanhamento` |
| 6. Orçamento e negociação | `agent_orcamento`, `agent_financeiro` | `agent_redator`, `agent_acompanhamento`, `agent_vigia` |
| 7. Contrato e formalização | `agent_redator`, `agent_financeiro` | `agent_legislacao`, `agent_acompanhamento`, `agent_vigia` |

**Amigão:** `MACROETAPA_AGENT_CHAIN` só mapeia **1 agente por etapa**.

**Mudança:**
- Estender `MACROETAPA_AGENT_CHAIN` para:
  ```python
  MACROETAPA_AGENTS = {
      Macroetapa.entrada_demanda: {
          "primary": ["agent_atendimento"],
          "secondary": ["agent_extrator", "agent_vigia"],
      },
      ...
  }
  ```
- **NÃO alterar config interna dos agentes** (respeitando restrição 🚫). Só alterar **quem é disparado quando**.
- UI do painel lateral do workspace: listar agentes principais + secundários da etapa atual.

#### 🟠 CAM3WS-005 — Painel "Validação humana necessária"

**Regente:** painel lateral direito contém item explícito "Validação humana necessária". Isso é crítico para o gate de avanço (CAM3FT-005).

**Amigão:** não existe conceito formal de "item aguardando validação humana".

**Mudança:**
- Em cada `action` do `MacroetapaChecklist`, adicionar campos:
  ```json
  {"id": "dt_01", "label": "...", "completed": true, "needs_human_validation": true, "validated_by_user_id": null, "validated_at": null}
  ```
- Quando IA produz algo (ex: leitura técnica), ação volta com `completed=true, needs_human_validation=true` → fica no painel lateral com botão "Validar".

#### 🟠 CAM3WS-006 — Saída da etapa registrada como artefato

**Regente:** cada etapa produz artefatos específicos:
- Etapa 2: ficha inicial estruturada, hipótese preliminar validada, urgência definida, lacunas registradas
- Etapa 4: problema real definido, complexidade classificada, risco inicial mapeado, resumo técnico consolidado
- Etapa 5: caminho regulatório definido, ordem das próximas etapas, plano de contingência, checklist da próxima fase
- etc.

**Amigão:** saídas não são registradas como artefatos separados — ficam soltas (ai_summary, risk_score, etc.).

**Mudança:**
- Criar model `StageOutput` (ou `ProcessArtifact`) com `{process_id, macroetapa, output_type, content, produced_by_agent, validated_at, validated_by}`.
- Endpoint `/processes/{id}/artifacts` para listar.
- UI: aba "Saídas" no menu lateral do workspace.

#### 🟡 CAM3WS-007 — Menu lateral interno do Workspace

**Regente:** 8 itens: Visão geral / Ações / Documentos / Dados / IA da etapa / Histórico / Decisões / Saídas.

**Amigão:** hoje tem tabs (DiagnosisTab, DocumentsTab, TasksTab, TimelineTab, ProcessCommercial, ProcessChecklist, ProcessDossier, LeituraIA). Nomes e organização são diferentes.

**Mudança:**
- Mapear tabs atuais → itens Regente:
  - Visão geral → novo componente (resumo)
  - Ações → ProcessChecklist ✅
  - Documentos → DocumentsTab ✅
  - Dados → novo (dados estruturados do cliente+imóvel no contexto do caso)
  - IA da etapa → LeituraIA (filtrada pela etapa atual) ✅
  - Histórico → TimelineTab / WorkflowTimeline ✅
  - Decisões → novo (registro de decisões tomadas)
  - Saídas → novo (ver CAM3WS-006)
- Adicionar os 3 itens novos.

#### 🟡 CAM3WS-008 — Barra horizontal das 7 etapas com estados visuais

**Regente:** estados das etapas na barra:
- Concluída (verde)
- Ativa (azul, destacada)
- Bloqueada (vermelho)
- Aguardando pré-requisito (amarelo)

**Amigão:** `MacroetapaStepper.tsx` existe. Validar se suporta os 4 estados acima.

**Mudança:** auditar + ajustar cores/ícones do stepper.

#### 🟡 CAM3WS-009 — Rodapé / timeline de eventos

**Regente:** rodapé com eventos: uploads, mudanças de status, decisões, geração de proposta, geração de contrato.

**Amigão:** `WorkflowTimeline.tsx` e `TimelineTab.tsx` existem. Pode atender; validar se rodapé é lugar certo (Regente sugere rodapé, não tab separada).

**Mudança:** promover timeline de tab para **rodapé fixo colapsável** do workspace.

---

### C. PRINCÍPIO ARQUITETURAL ("Cadastro abre, Workspace constrói, Fluxo coordena")

#### 🔴 CAM3PR-001 — Separação clara de responsabilidades

**Regente:** princípio rígido:
- **Cadastro** cria identidade (só entrada, sem profundidade).
- **Workspace** constrói memória (upload, edit, diagnóstico, análise — tudo aqui).
- **Fluxo** coordena visibilidade (só mostra estado, não edita nada).

**Amigão:** existe mistura. Ex: upload de documentos hoje é possível em vários lugares (intake, process detail, documents page). Diagnóstico pode ser editado no detail mas também no intake (via classify).

**Mudança conceitual:**
- Auditar todas as rotas de UI e identificar onde há operações "profundas" fora do Workspace.
- Redirecionar uploads/edições para o workspace da etapa correspondente.
- Essa refatoração atravessa várias Camadas e deveria virar um ticket "arquitetural guard rail".

---

## CAMADA 4 — INTELIGÊNCIA E GOVERNANÇA (Agentes IA + Configurações)

**Status:** não temos o mapa da sócia para esta camada. **Solicitar export do Whimsical.**

---

## PLANO DE ATAQUE SUGERIDO

### Sprint 1 — Coração da Entrada (Camada 1)
Prioridade máxima: corrigir o fluxo de Cadastro pra respeitar a premissa "entrada primeiro, organização depois".

1. CAM1-001 — Tipo de entrada (Step 0 no wizard)
2. CAM1-002 — Descrição não-obrigatória
3. CAM1-003 — Classificação assíncrona (usa agente existente)
4. CAM1-010 — Etapa "Entrada da demanda" como inicial
5. CAM1-008 + CAM1-009 — Estados do cadastro e "salvar depois"
6. CAM1-011 — Gate de prontidão no card

### Sprint 2 — Enriquecimento (Camada 1 — cenários avançados)
7. CAM1-004 — Complementar base
8. CAM1-005 — Importar documentos com IA (usa agente extrator existente)
9. CAM1-007 — Upload multi-tipo com estados

### Sprint 3 — Fluxo + Workspace (Camada 3) — refinamento do que já existe
**Justificativa:** a Camada 3 tem a fundação mais madura (modelo Macroetapa, kanban, stepper). Entregar os refinamentos aqui destrava o ciclo inteiro Cadastro→Fluxo→Workspace.

10. CAM3FT-004 — Estados formais por etapa (7 estados)
11. CAM3FT-005 — Regras formais de avanço (guard de transição)
12. CAM3FT-001 — Próximo passo + badge de alerta nos cards
13. CAM3FT-003 — Kanban mostrando travados/prontos por coluna
14. CAM3WS-001 — Layout 6-áreas do workspace
15. CAM3WS-003 — Objetivo + Saída esperada por etapa
16. CAM3WS-005 — Painel "Validação humana necessária"
17. CAM3WS-006 — Saídas da etapa como artefatos

### Sprint 4 — Cliente Hub (Camada 2)
18. CAM2CH-001 a CAM2CH-007 — Hub completo do cliente

### Sprint 5 — Dashboard executivo (Camada 2)
19. CAM2D-001 a CAM2D-004 — Blocos 3-6 do dashboard

### Sprint 6 — Imóvel Hub (Camada 2)
20. CAM2IH-001 a CAM2IH-006 — Hub completo do imóvel

### Sprint 7 — Refinamentos Camada 3 + Princípio arquitetural
21. CAM3WS-002 — Tipos de blocos (permanente/ativo/herdado/condicional)
22. CAM3WS-004 — Multi-agente por etapa (primary/secondary)
23. CAM3PR-001 — Auditoria da separação Cadastro/Workspace/Fluxo

### Sprint 8+ — Camada 4 (Agentes + Configurações)

> **Nota 2026-04-20:** o material da sócia para Camada 4 já está em [amigao_regente/](../amigao_regente/) — inclui `Camada 4 conifguracao e agente de ia.pdf`, `OEPRACAO.pdf` e os PNGs do Regente Lovable. Quando atacarmos esta camada, começar lendo esses arquivos + respostas consolidadas. Sprint F Bloco 2 já entregou Configurações iniciais.

---

## PERGUNTAS PENDENTES PARA A SÓCIA

1. **Camada 4** (Agentes IA + Configurações): pode exportar o mapa? Mesmo formato @2x do Whimsical.
2. **Núcleo**: o arquivo veio em branco — o que era esperado estar aí? É só um índice/menu central ou é uma camada de dados comum (tipo banco de conhecimento)?
3. **Status do cliente** (Cliente Hub): quais são os estados exatos? (o tile mostrou "andamento", "cancelado" e outros cortados).
4. **Tipo de entrada #4 e #5**: "Complementar base" e "Importar documentos" são fluxos completos separados ou modais leves dentro do cadastro padrão?
5. **Estados do cadastro**: quando um rascunho expira? Fica salvo eternamente?
6. **Leitura da IA (Dashboard)**: frequência de atualização — tempo real, 1x/hora, sob demanda?
7. **Camada 3 — Kanban vs drag-and-drop**: o drag-and-drop atual do Amigão permite mover qualquer caso entre colunas. Regente diz que só pode avançar com gate. **Confirmar se a sócia quer:** (a) desabilitar drag-and-drop e forçar botão "Avançar etapa" com validação, ou (b) manter drag mas validar no drop e reverter se falhar.
8. **Camada 3 — Decisões**: o item "Decisões" no menu lateral do workspace — é um log textual (consultor registra decisões tomadas) ou um campo estruturado (ex: "decisão sobre caminho regulatório: A vs B")?
9. **Camada 3 — Condicionais**: a lista de blocos condicionais (procuração, contrato societário, parceiro técnico, etc.) — quem decide se o bloco aparece? É regra automática baseada em campos do cliente/imóvel, ou o consultor liga/desliga manualmente?

---

## RESPOSTAS DA SÓCIA — 2026-04-19

Respostas vieram via `amigao´regente/amigao-regente.docx` + PDFs de Camada 3, Camada 4 e prints do Lovable (`regente-vista-macro.lovable.app`).

### ✅ Pergunta 3 — Status do cliente

**Decisão:** `ativo` / `em andamento` / `sem casos ativos` / `bloqueado`.

### ✅ Pergunta 5 — Estado do rascunho

**Decisão:** **rascunho expira em 15 dias**. Depois disso descarta automaticamente.

### ✅ Pergunta 6 — Frequência da Leitura IA (Dashboard)

**Decisão:** Preferência inicial era tempo real, mas **se custo/backend for significativo → atualização 1x/dia**. Adotar 1x/dia no MVP; re-avaliar depois.

### ✅ Pergunta 9 — Blocos condicionais

**Decisão:** **desconsiderar por enquanto** — é complexidade desnecessária no MVP. Procuração, contrato societário, parceiro técnico, campo, embargo etc. ficam **fora do escopo atual**. Voltar depois quando a base estabilizar.

### ⚠️ Perguntas ainda em aberto

- **#2 Núcleo** — seguimos interpretando como orchestrator + rooms MemPalace + chains (já mapeado na Camada 4 agora).
- **#4 Tipos de entrada** — a sócia simplificou em 3 tipos no diagrama (`cliente+imóvel existente` / `complementar base` / `importar docs para análise`). Ainda falta definir se são fluxos separados ou toggle.
- **#7 Kanban drag-and-drop** — não foi tocado nas respostas. Assumindo **gate por botão "Avançar etapa"** (coerente com "regras de avanço" da Camada 3 PDF).
- **#8 Decisões** — pelo PDF da Camada 3, é **aba estruturada** (tipo, decisão, justificativa, base, quem validou, data, impacto, próximo passo, status). Muito mais rico que log textual.

---

## ATUALIZAÇÕES DE ESCOPO — CAMADAS 3 E 4 (2026-04-19)

### Camada 3 — Aba "Decisões" como componente de 1ª classe

Baseado em `CAMADA 3 - WORKSPACE EDIT1.pdf`. Cada decisão registrada:

| Campo | Descrição |
|---|---|
| `etapa` | Qual das 7 |
| `tipo_decisao` | triagem, documental, técnica, regulatória, comercial, contratual, bloqueio, avanço de etapa |
| `decisao_tomada` | Texto curto |
| `justificativa` | Por que |
| `base_usada` | Evidências/documentos/leituras IA que sustentaram |
| `quem_validou` | Usuário |
| `data` | Timestamp |
| `impacto_no_caso` | Como mudou o rumo |
| `proximo_passo_gerado` | Ação derivada |
| `status` | proposta / validada / revisada / substituída |

**Valor:** transforma análise em governança. Rastreabilidade, auditoria interna, reaproveitamento de memória entre casos.

### Camada 3 — Camadas do Workspace

- **Camada fixa:** identidade do caso, etapas, dados-base, timeline, painel IA (sempre visível)
- **Camada progressiva:** módulos da etapa ativa, saídas das anteriores, pré-requisitos da próxima
- **Camada de governança:** validação humana, decisões críticas, bloqueios, rastreabilidade

### Camada 4 — Configurações (6 abas)

`Perfil` · `Assinatura e pagamento` · `Notificações` · `Preferências operacionais` · `Preferências de IA` · `Segurança e acesso`. Futuro: `Equipe e permissões`.

Princípio: "configuração boa não parece painel de avião". Baixa fricção, pagamento com destaque, IA configurável sem engenharia exposta.

### Camada 4 — 10 agentes por etapa (mapa formal)

| Etapa | Principal | Secundários |
|---|---|---|
| 1 Entrada | `agent_atendimento` | extrator, vigia |
| 2 Diag. preliminar | atendimento + `agent_diagnostico` | legislacao, extrator |
| 3 Coleta | `agent_extrator` | vigia, acompanhamento |
| 4 Diag. técnico | `agent_diagnostico` | extrator, legislacao, redator |
| 5 Caminho regulatório | `agent_legislacao` | diagnostico, redator, acompanhamento |
| 6 Orçamento | `agent_orcamento` + `agent_financeiro` | redator, acompanhamento, vigia |
| 7 Contrato | `agent_redator` + `agent_financeiro` | legislacao, acompanhamento, vigia |
| Transversal | `agent_vigia`, `agent_acompanhamento` | — |
| Fora do fluxo | `agent_marketing` | — |

**Nota:** configuração dos agentes segue congelada (feedback 2026-04-17). Mapa serve para **orientar endpoints consumidores**, não alterar agentes.

---

## QUADRO DE AÇÕES — SPEC DETALHADA

**Fontes:** `OEPRACAO.pdf` (Camada 3) + prints do Lovable.

### Princípio central

> **"Cadastro abre, Workspace constrói, Fluxo coordena."**

O Quadro de Ações é a **camada de coordenação visual** entre Cadastro e Workspace. Ele **não executa trabalho profundo** — reflete o estado gerado no Workspace e guia o consultor sobre onde agir.

### 5 perguntas que o Quadro responde por caso

1. Onde o caso está?
2. O que já foi concluído na etapa atual?
3. O que falta para concluir essa etapa?
4. Existe bloqueio impeditivo?
5. O caso já pode avançar?

### Estrutura da tela — 5 blocos

#### Bloco 1 — Cabeçalho operacional
- Título: "Quadro de Ações" + subtítulo "Fluxo macro dos casos em andamento"
- Busca: cliente / imóvel / caso
- Filtros: Responsável, Urgência, Tipo de demanda, Município/UF, Etapa, Status de prontidão
- Ações rápidas: `+ Novo Caso`, `Ordenar por prioridade`, `Filtrar travados`, `Filtrar prontos para avançar`
- Contador: "N casos ativos"

#### Bloco 2 — Banner de Leitura IA
Resumo operacional gerado por `agent_vigia` + `agent_acompanhamento`.
Ex do Lovable: *"Hoje o maior acúmulo está em Coleta Documental. 4 casos possuem pendência crítica e 2 estão prontos para seguir para proposta. Priorize os casos com urgência alta e documentos impeditivos."*
Atualização **1x/dia**. Endpoint: `GET /dashboard/board-insights`.

#### Bloco 3 — Kanban horizontal (7 colunas)

Ordem fixa: Entrada da demanda · Diagnóstico preliminar · Coleta documental · Diagnóstico técnico consolidado · Definição do caminho regulatório · Orçamento e negociação · Contrato e formalização.

Header de coluna: nome + contador total (v2: contador travados + prontos).

#### Bloco 4 — Card do caso

Campos: cliente, imóvel, tipo de demanda, badge de urgência (`Urgente`/`Alta`/`Média`/`Baixa`), badge de alerta, avatar+nome responsável, próximo passo sugerido (`→ Validar imóvel vinculado`).

Estados (7): `não iniciada` / `em andamento` / `aguardando input` / `aguardando validação` / `travada` / `pronta para avançar` / `concluída`.

**Card NÃO mostra:** checklist, leitura IA profunda, detalhe técnico, lista de docs. Isso é Workspace.

#### Bloco 5 — Modal lateral (preview)

Drawer à direita, abre ao clicar no card. Não navega — mantém kanban visível.

Conteúdo (do Lovable):
- Cabeçalho: cliente + imóvel + tipo + urgência + responsável
- Barra `Etapa ativa · X/Y ações concluídas`
- Resumo: `PROBLEMA PERCEBIDO`, `OBJETIVO REAL`, `STATUS DA ETAPA`
- Ações da etapa (compacta)
- `URGÊNCIA SUGERIDA`
- `LACUNAS DETECTADAS` (com ⚠️)
- `PRÓXIMA AÇÃO SUGERIDA`
- Seção "No workspace completo você verá"
- **CTA verde:** `Abrir workspace do caso`

### Gate de transição entre etapas

Avanço só com: (1) output mínimo da etapa, (2) validação humana quando necessária, (3) sem trava impeditiva.

**Decisão arquitetural:** botão `Avançar etapa` **no Workspace**, não drag-and-drop no kanban.

---

## BACKLOG DE EXECUÇÃO — QUADRO DE AÇÕES

### Sprint A — Base do Kanban (2026-04-19 → 04-20)

**Objetivo:** trocar layout atual por Kanban horizontal 7 colunas + cards fiéis ao Lovable.

- **QA-001** — Auditar estado atual (arquivo da página, endpoints, modelo de dados)
- **QA-002** — Layout Kanban horizontal 7 colunas com scroll + header (nome + contador)
- **QA-003** — Componente `CaseCard` novo (cliente, imóvel, demanda, urgência, alerta, responsável, próximo passo)
- **QA-004** — Cabeçalho operacional (busca + filtros + `+ Novo Caso`)

### Sprint B — Modal lateral de preview (2026-04-21)

- **QA-005** — Drawer lateral à direita (ESC, clique fora, X)
- **QA-006** — Conteúdo do preview (consome `GET /processes/{id}/preview` — criar se não existir)
- **QA-007** — CTA `Abrir workspace do caso` (link preserva etapa ativa)

### Sprint C — Leitura IA + gate (2026-04-22)

- **QA-008** — Banner Leitura IA (endpoint `GET /dashboard/board-insights`, cache 1x/dia via celery beat)
- **QA-009** — Estados visuais por card (badge + filtros travados/prontos)
- **QA-010** — Botão `Avançar etapa` no Workspace + desabilitar drag no kanban

### Sprint D — Polimento (2026-04-23)

- **QA-011** — Contadores travado/pronto por coluna ✅ já existia desde Regente v3
- **QA-012** — Ordenação por prioridade ✅ entregue 2026-04-19 (commit `50a0a39`)
- **QA-013** — Card → última decisão ⏸ bloqueado até Sprint E existir

### Sprint E — Aba Decisões (Camada 3 · governança do raciocínio) ✅ entregue 2026-04-19

**Objetivo:** materializar a "camada de governança" do Workspace descrita no `CAMADA 3 - WORKSPACE EDIT1.pdf`. Transforma análise em rastreabilidade auditável.

**Valor estratégico:** é a fundação da visão govtech (rastreabilidade, base normativa citada, quem validou) — ver seção "Horizonte Estratégico" no fim deste doc.

- **SE-001** — Model `ProcessDecision` + migration Alembic ✅ migration `a3f5c7b9d2e4`
- **SE-002** — Schemas Pydantic (`DecisionCreate`, `DecisionUpdate`, `DecisionRead`, `DecisionSummary`) ✅
- **SE-003** — Endpoints CRUD: `GET/POST/PATCH/DELETE /processes/{id}/decisions` ✅ + `/latest`
- **SE-004** — Tab "Decisões" no `ProcessDetail.tsx` + `DecisionsTab.tsx` ✅ (form com 8 tipos, 4 status, chain de substituição)
- **SE-005** — **QA-013 destravado** — endpoint `/decisions/latest` renderizado no drawer do Quadro ✅

**Entregue no commit `ded1985`** (2026-04-19).

### Dependências Sprint E

- Backend: confirmar campos em `GET /processes` (`macroetapa`, `stage_state`, `next_action`, `alert_type`).
- IA insight: `agent_vigia` (congelado, só consumir).
- `macroetapa_state` do Plano Mestre v2 precisa ter os 7 estados cobertos.

### Fora do backlog original

- Agentes novos ou alteração de prompts (congelado)
- Aba Decisões do Workspace (sprint próprio — agora entregue)
- Govtech (horizonte estratégico)

---

## SPRINT F — Dashboard + Configurações + Cadastro TTL ✅ entregue 2026-04-19

Três blocos executados em sequência no mesmo dia, cada um com commit próprio.
Todos respondem diretamente ao que a sócia desenhou no Lovable e no `amigao-regente.docx`.

### Sprint F · Bloco 1 — Dashboard Operacional Regente ✅ commit `0332c85`

**Objetivo:** view "operacional" do Dashboard matching com o print Lovable (8 cards + 2 gráficos + filtros). Responde "como está a operação agora e onde preciso agir primeiro?".

**Backend:**
- `GET /dashboard/kpis?days=N&responsible_user_id=&demand_type=` (novo)
- Retorna 8 KPIs + `funnel[]` por macroetapa
- Delta % vs janela anterior (itens criados na janela atual vs anterior)
- 8 KPIs: Clientes Ativos, Casos Ativos, Em Diagnóstico, Em Coleta, Em Caminho Regulatório, Propostas Enviadas, Contratos Enviados, Casos Formalizados
- Schema `KpiValue { key, label, value, delta_pct?, hint? }` + `DashboardKpis`

**Frontend:**
- `DashboardOperacionalRegente.tsx` novo componente
- Filtros: Período (7/30/90/180 dias) · Tipo de demanda (filtro Responsável adiado — precisa `/users`)
- Grid 4×2 de KPI cards com ícone, valor, delta (`TrendingUp`/`Down`), hint
- "Casos por Etapa" — barras horizontais proporcionais
- "Funil Operacional" — 7 degraus decrescentes com degradê verde
- Integrado apenas na view `operacional` do Dashboard; `executivo` intocado
- Zero dependência nova: CSS puro com divs proporcionais

### Sprint F · Bloco 2 — Configurações Camada 4 ✅ commit `9384041`

**Objetivo:** materializar a Camada 4 (governança individual da conta) com 6 abas conforme `Camada 4 conifguracao e agente de ia.pdf` da sócia. Princípio: "configuração boa não parece painel de avião".

**Backend:**
- User model ganha coluna `preferences` JSONB com 4 grupos aninhados: `profile`, `notifications`, `operational`, `ai`
- Migration `b7d9e1f3a5c8` (aditiva, default `{}`)
- Schemas: `UserPreferences` + sub-grupos, `UserProfileUpdate`, `PreferencesUpdate`, `PasswordChangeRequest`, `UserMeResponse`
- 4 novos endpoints em `/auth`:
  - `GET /auth/me/full` — user + preferências expandidas
  - `PATCH /auth/me` — nome/email (valida conflito de email)
  - `PATCH /auth/me/preferences` — merge parcial por grupo
  - `POST /auth/password-change` — exige senha atual correta

**Frontend:**
- Nova página `frontend/src/pages/Settings/index.tsx` com 6 abas:
  1. **Perfil** — nome, email, telefone, cargo, empresa
  2. **Pagamento** — placeholder ("billing em breve")
  3. **Notificações** — canais (email/WhatsApp/in-app/push) + frequência (críticos / resumo diário / semanal)
  4. **Preferências operacionais** — tela inicial, ordenação, formato data, UF padrão, modo compacto
  5. **IA** — nível de assistência (Automático/Equilibrado/Controlado), tamanho de resumo, validação humana, histórico
  6. **Segurança** — trocar senha (validação min 8 + match) + 2FA stub
- Rota `/settings` em `App.tsx`
- Item "Configurações" (ícone Settings) adicionado ao sidebar do `PrivateLayout`
- Helpers reutilizáveis: `Section`, `Field`, `Toggle`, `SaveButton`

### Sprint F · Bloco 3 — Cadastro (Step 0 + rascunho 15 dias) ✅ commit `4a4b282`

**Objetivo:** aplicar a decisão da sócia de 2026-04-19 sobre rascunhos (expirar em 15 dias) e validar o Step 0 do wizard.

**Step 0 do wizard:** **já existia** com 5 opções desde Regente v3 (commit `14462b5`). As 3 opções que a sócia pediu (cliente+imóvel existente / complementar base / importar docs) já estavam cobertas. Sem alteração necessária.

**Rascunho expira em 15 dias (nova feature):**

Backend:
- `IntakeDraft` ganha coluna `expires_at` (DateTime, indexed) + migration `c9f1a3b5d7e2` com backfill (drafts em `rascunho`/`pronto_para_criar` recebem `NOW + 15 days`)
- Helpers `refresh_expiration()` / `is_expired()` no model
- Constante `INTAKE_DRAFT_TTL_DAYS = 15`
- `POST /intake/drafts` e `PATCH /intake/drafts/{id}` chamam `refresh_expiration()` — cada edição renova o prazo
- `GET /intake/drafts` filtra expirados por padrão
- `IntakeDraftResponse` expõe `expires_at`

Celery task:
- `workers.cleanup_expired_intake_drafts` em `app/workers/intake_tasks.py`
- Só remove drafts em `rascunho` / `pronto_para_criar` (preserva `card_criado` / `base_complementada`)
- Beat schedule: **02:30 BRT diário** (off-peak)
- Retry com backoff em caso de falha

Frontend:
- `IntakeWizard` guarda `draftExpiresAt` no state
- Badge "💾 Rascunho salvo · expira em X dias" no header
- Vira **amarelo** quando ≤ 3 dias restantes

### Chain de migrations do Sprint E + F

```
a3f5c7b9d2e4  process_decisions               (Sprint E)
b7d9e1f3a5c8  users.preferences               (Bloco 2)
c9f1a3b5d7e2  intake_drafts.expires_at        (Bloco 3)  ← HEAD
```

Para aplicar: `alembic upgrade head` (aditivas, sem downtime).

### Validações Sprint F

- Frontend `tsc --noEmit`: limpo em todos os 3 blocos
- Backend: imports + schemas smoke-testados, rotas registradas
- 75 testes existentes continuam passando (test_settings + test_state_machines)
- Celery task registrada (`workers.cleanup_expired_intake_drafts` aparece em `celery_app.tasks`)
- Migration chain verificada: HEAD em `c9f1a3b5d7e2`

### Itens intencionalmente adiados (registro de escopo)

- **Filtro Responsável no Dashboard** — precisa endpoint `/users` novo; pragmática: adiar
- **Integração real de billing** (Pagamento em Configurações) — placeholder UI pronto, backend fora de escopo MVP
- **2FA** — placeholder visível, implementação em sprint próprio
- **Cliente Hub / Imóvel Hub** (Camada 2) — Cliente Hub entregue na Sprint G (abaixo); Imóvel Hub pendente

---

## SPRINT G — Cliente Hub (Camada 2) ✅ entregue 2026-04-20

**Contexto:** ao retomar o trabalho em 2026-04-20 descobrimos que **~80% do Cliente Hub já existia no código** (backend: 4 endpoints agregadores em `app/api/v1/clients.py`; frontend: `ClientHub.tsx` com 5 abas, KPIs, painel IA lateral, mini-timeline por imóvel), mas nunca havia sido registrado neste doc. Sprint G fecha os **gaps reais** que restavam para considerar CAM2CH-001 a CAM2CH-009 concluídos.

### Já entregue antes (sem registro)

- **CAM2CH-001** Rota `/clients/:id` + componente `ClientHub.tsx`
- **CAM2CH-003** Dashboard resumido (7 KPI cards)
- **CAM2CH-004** `GET /clients/{id}/properties-with-status`
- **CAM2CH-005** Mini-timeline de eventos por imóvel (via AuditLog)
- **CAM2CH-006** `GET /clients/{id}/timeline`
- **CAM2CH-007** Painel lateral IA (determinístico — `GET /clients/{id}/ai-summary`)
- **CAM2CH-008** Abas: Visão geral / Imóveis / Casos / Contratos (era placeholder) / Histórico
- **CAM2CH-009** Estados computados do hub (`_compute_hub_state`)

### Gaps fechados na Sprint G

#### Bloco 1 — Status operacional conforme decisão da sócia (2026-04-19)

Decisão da sócia: status do cliente = `ativo / em andamento / sem casos ativos / bloqueado`. O enum persistido continua `lead/active/inactive/delinquent` (já havia dados); adicionamos `blocked` e derivamos os outros labels visualmente no `status_label`.

**Backend:**
- Migration `d8b3f7c2e5a9` — `ALTER TYPE clientstatus ADD VALUE IF NOT EXISTS 'blocked'`
- Modelo [app/models/client.py](../app/models/client.py) — novo valor `ClientStatus.blocked`
- Novo helper `_compute_status_label()` em [app/api/v1/clients.py](../app/api/v1/clients.py) mapeando:
  - `status=blocked` → "Bloqueado"
  - `status=active & cases_active>0` → "Em andamento"
  - `status=active & cases_active==0` → "Sem casos ativos"
  - `status=lead/inactive/delinquent` → labels originais
- Schema `ClientHubHeader` ganha campo `status_label: str`

**Frontend:**
- `STATUS_CLS` — mapa de classes CSS por status persistido (blocked vermelho, active verde, lead azul, etc.)
- Cabeçalho agora exibe **dois badges** lado a lado: (1) status operacional Regente (derivado), (2) estado do hub (computed)

#### Bloco 2 — `has_contract_pending` real

Antes: `has_contract_pending: False` hardcoded com TODO. Agora: conta contratos em `status in (draft, sent)` do cliente no tenant atual.

#### Bloco 3 — Aba Contratos real

Era placeholder "Em construção". Agora consome `GET /contracts?client_id=X` (endpoint já existia) e lista contratos com:
- Badge de status (rascunho / enviado / assinado / cancelado) com ícone
- Flag `has_pdf`
- Contexto: caso vinculado, data relevante (signed_at / sent_at / created_at)
- CTA "Abrir caso" quando houver `process_id`

#### Bloco 4 — Aba Documentos (nova)

Nova aba para a ação "Ver documentos" do CAM2CH-002. Precisou de pequena extensão no backend:
- [app/api/v1/documents.py](../app/api/v1/documents.py) `GET /documents/` aceita `client_id` query param quando o usuário é interno (portal continua com escopo fixo em `access_context.client_id`)
- Frontend: novo componente `DocumentsTab` consumindo `/documents?client_id=X` com filename, categoria, status, tamanho e link para o caso vinculado

#### Bloco 5 — Ações rápidas completas (6 itens)

Antes: 4 botões. Agora alinhado com CAM2CH-002 (6 ações):
- `+ Novo caso` → `/intake`
- `Ver contratos` → aba contracts
- `Ver diagnósticos` → aba cases
- `Adicionar imóvel` → `/properties`
- **`Gerar resumo`** (novo) → invalida cache do `ai-summary` e faz scroll suave ao painel lateral IA
- **`Ver documentos`** (novo) → aba documents

### Chain de migrations Sprint F → Sprint G

```
a3f5c7b9d2e4  process_decisions               (Sprint E)
b7d9e1f3a5c8  users.preferences               (Sprint F · Bloco 2)
c9f1a3b5d7e2  intake_drafts.expires_at        (Sprint F · Bloco 3)
d8b3f7c2e5a9  clientstatus.blocked            (Sprint G)      ← HEAD
```

Aditiva e sem downtime: `alembic upgrade head`.

### Decisões de escopo (Sprint G)

- ❌ **Não** trocar `/ai-summary` determinístico por chamada a `agent_acompanhamento` — respeita `feedback_agents_config_frozen` + decisão da sócia sobre IA do Dashboard (1x/dia). Mantém TODO no endpoint.
- ❌ **Não** criar endpoint `/clients/{id}/contracts` — reusa `/contracts?client_id=X` existente.
- ❌ **Não** implementar blocos condicionais (procuração, contrato societário, etc.) — sócia mandou desconsiderar no MVP (pergunta 9, 2026-04-19).
- ✅ Permitir `client_id` em `/documents/` para usuários internos — mudança pequena, preserva escopo do portal.

### Validações Sprint G

- [x] Backend: `ClientStatus.blocked` presente, helper `_compute_status_label` exportado implicitamente via response
- [x] Frontend `tsc --noEmit` limpo em `ClientHub.tsx`
- [x] Migration aplicável idempotentemente (usa `IF NOT EXISTS`) e única HEAD na chain

---

## SPRINT H — Imóvel Hub (Camada 2) ✅ entregue 2026-04-20

**Contexto:** ao auditar o Imóvel Hub descobrimos — mesmo padrão da Sprint G — que ~75% já existia no código sem registro. Backend tinha 5 endpoints agregadores, schemas `PropertyHubSummary/Header/HealthScore/AISummary`, lógica `_compute_health_score` + `_compute_property_hub_state`, field sources com AuditLog (CAM2IH-007), rota `/properties/:id` montada. Frontend tinha `PropertyHub.tsx` com cabeçalho, KPIs, painel IA determinístico, score de saúde, 5 abas (Informações/Documentos/Análises/Histórico/Casos) — Documentos e Análises como placeholder.

### Já entregue antes (sem registro)

- **CAM2IH-001** Rota `/properties/:id` + componente `PropertyHub.tsx`
- **CAM2IH-002** Cabeçalho com identificação técnica + chips + CTAs
- **CAM2IH-005** Painel lateral IA determinístico (`GET /properties/{id}/ai-summary`)
- **CAM2IH-006** Health score 0-100 com 4 componentes (`_compute_health_score`)
- **CAM2IH-007** Field sources (raw/ai_extracted/human_validated) + endpoint `validate-fields`
- **CAM2IH-008** 5 estados do hub (`_compute_property_hub_state`)
- **CAM2IH-009** CTA fixo "Abrir workspace do caso" no cabeçalho

### Gaps fechados na Sprint H

#### Bloco A — Aba Documentos real (CAM2IH-004)

Antes: placeholder "abra o caso para ver detalhes". Agora:

**Backend:**
- `GET /documents/?property_id=X` aceita filtro por imóvel quando o usuário é interno (portal mantém escopo fixo).
- `DocumentRepository._scoped_query` ganha parâmetro `property_id` fazendo `OR` com `Process.property_id` (pega docs vinculados direto OU via processo do imóvel).
- `POST /documents/confirm-upload` agora herda `property_id` do processo, para que uploads feitos em casos apareçam no Imóvel Hub.

**Frontend:**
- Nova `DocumentsTab` com chips de filtro por categoria (6 canônicas Regente + "Outras"), lista de docs com nome, categoria (label pt-BR), OCR status, tamanho, caso vinculado, CTA "Abrir caso".
- Mapa `CATEGORY_LABELS` com os 6 labels pt-BR.

#### Bloco B — Campos técnicos do Property (CAM2IH-003/004)

Antes: Dashboard técnico vazio nos campos RL/APP/pendências. Agora adicionados ao modelo e expostos no `/properties/{id}/summary`:

**Migration `e5a7c9b1f3d6`** — ALTER TABLE aditivo, 7 colunas nullable:
- `rl_status` (averbada / proposta / pendente / cancelada)
- `app_area_ha` (ha)
- `regulatory_issues` (JSONB — `[{tipo, descricao, severidade}]`)
- `area_documental_ha`, `area_grafica_ha` (ha) — comparáveis para detectar divergência
- `tipologia` (agricultura / pecuaria / misto / outro)
- `strategic_notes` (Text — observações estratégicas)

**Schema & endpoint:**
- `PropertyHubHeader` ganha os 7 campos novos.
- `/properties/{id}/summary` popula todos.
- `_TRACKED_FIELDS` do endpoint `validate-fields` inclui `rl_status`, `app_area_ha`, `area_documental_ha`, `area_grafica_ha`, `tipologia` — todos podem ser promovidos IA→validado.

**Frontend Aba Informações — nova seção "Dados técnicos":**
- 5 `InfoField`s com badges de origem + botão Validar.
- Bloco visual de pendências ambientais (amarelo com ícone de alerta) quando `regulatory_issues.length > 0`.
- Bloco de observações estratégicas (texto livre, respeita `\n`).
- Alerta de divergência quando |documental - gráfica| > 0.5 ha.

#### Bloco C — Enum canônico de categoria de documento (CAM2IH-010)

A infraestrutura já existia (`app/models/document_categories.py` com `REGENTE_CATEGORIES`, `normalize_category`, endpoint `GET /documents/categories`), mas os writes não usavam:

- `POST /documents/confirm-upload`: agora chama `normalize_category()` antes de persistir.
- `POST /intake/drafts/{id}/documents`: mesma chamada.
- `app/workers/pdf_generator.py`: categoria do relatório PDF gerado passou de `"relatorio"` (legado) para `"relatorios_gerados"` (canônica).
- Dados existentes seguem como string livre — o normalize é idempotente (já-canônico passa direto; legados conhecidos traduzem; desconhecidos viram None para a UI mostrar "outras").

### Chain de migrations Sprint E → Sprint H

```
a3f5c7b9d2e4  process_decisions               (Sprint E)
b7d9e1f3a5c8  users.preferences               (Sprint F · Bloco 2)
c9f1a3b5d7e2  intake_drafts.expires_at        (Sprint F · Bloco 3)
d8b3f7c2e5a9  clientstatus.blocked            (Sprint G)
e5a7c9b1f3d6  properties.{rl,app,areas,...}   (Sprint H)      ← HEAD
```

Aditiva e sem downtime: `alembic upgrade head`.

### Decisões de escopo (Sprint H)

- ❌ **Não** criar tabela `PropertyAnalysis` — Aba Análises continua apontando pros `StageOutputs` dos casos. Decisão adiada para Sprint I (precisa definir se análise é entidade própria ou agregação).
- ❌ **Não** trocar `/properties/{id}/ai-summary` determinístico por chamada a agentes reais — respeita `feedback_agents_config_frozen`.
- ❌ **Não** migrar dados existentes de `document_category` (ex: "geral", "portal_cliente") — normalize só em writes novos; a UI de listagem trata desconhecido como "Outras".
- ❌ **Não** adicionar SNCR/CIB/access_description/operation_start_date ao modelo — menos prioritários, podem entrar via Sprint I se aparecer demanda.
- ✅ Permitir `property_id` em `/documents/` para usuários internos (mesma lógica do `client_id` da Sprint G).
- ✅ Confirm-upload passa a herdar `property_id` do processo — retrocompatível, só preenche quando existe.

### Validações Sprint H

- [x] Backend: migration `e5a7c9b1f3d6` aplicada (DB = head), 7 colunas presentes em `properties`
- [x] Frontend `tsc --noEmit` limpo em `PropertyHub.tsx`
- [x] `GET /documents/?property_id=X` retorna docs do imóvel (testado com doc vinculado direto; tenant isolation respeitada)
- [x] Upload via `confirm-upload` herda `property_id` do processo (edit em `app/api/v1/documents.py`)
- [x] `normalize_category` aplicado em writes novos (`ambiental` → `ambientais`, `relatorio` → `relatorios_gerados` OK em smoke test)

---

## SPRINT I — Cadastro Camada 1 (polish + gate de prontidão) ✅ entregue 2026-04-20

**Contexto:** ao auditar os 7 tickets CAM1 pendentes (Sprint 1 do plano de ataque) descobrimos — de novo — que **5 deles já estavam 100% entregues** em sprints anteriores (Regente v3, Sprint F) sem registro neste doc. Só 2 tinham gap real. Sprint I fecha os 2 gaps e formaliza o que já existia.

### Já entregue antes (sem registro) — Bloco A documental

Revalidado no código em 2026-04-20:

#### ✅ CAM1-002 — Descrição deixa de ser obrigatória
- `IntakeCreateCaseRequest.description: Optional[str]` em [app/schemas/intake.py:78-81](../app/schemas/intake.py)
- [app/api/v1/intake.py:164-187](../app/api/v1/intake.py): quando `description` < 10 chars, cria `DemandClassification` com `demand_type="nao_identificado"` e segue sem travar
- Frontend: apenas exibe contador informativo, **não bloqueia** submit

#### ✅ CAM1-008 — Estados do cadastro (4 estados formais)
- [app/models/intake_draft.py:33-37](../app/models/intake_draft.py) `IntakeDraftState` enum: `rascunho`, `pronto_para_criar`, `card_criado`, `base_complementada`
- Transições dinâmicas via `_compute_state()` no repositório
- Sprint F Bloco 3 adicionou `expires_at` (TTL 15 dias)

#### ✅ CAM1-009 — CTA "Salvar e continuar depois"
- `POST /intake/drafts` + `PATCH /intake/drafts/{id}` + `POST /intake/drafts/{id}/commit`
- Frontend [IntakeWizard.tsx](../frontend/src/pages/Intake/IntakeWizard.tsx) tem botão "💾 Salvar e continuar depois" + badge de rascunho com expiração

#### ✅ CAM1-010 — Etapa "Entrada da demanda" como inicial
- Enum `Macroetapa.entrada_demanda` em [app/models/macroetapa.py](../app/models/macroetapa.py)
- [app/api/v1/intake.py:209-220](../app/api/v1/intake.py): Process nasce com `macroetapa=Macroetapa.entrada_demanda.value`
- **Caveat aceito:** status legado `"triagem"` é mantido por retrocompat com máquina de estados. `STATUS_TO_MACROETAPA` vincula `triagem` → `entrada_demanda`.
- Transição para `diagnostico_preliminar` é **explícita** via `advance_macroetapa` (sem auto-transição).

#### ✅ CAM1-012 — Resumo da demanda separado de description
- [app/models/process.py:125](../app/models/process.py) `initial_summary` — "resumo curto da demanda na voz do cliente"
- [app/models/process.py:100](../app/models/process.py) `description` — "descrição técnica elaborada pelo consultor"
- Schema `IntakeCreateCaseRequest` aceita ambos; frontend expõe os dois campos.

### Gaps fechados na Sprint I — Bloco B

#### Bloco B.1 — CAM1-011: Gate de prontidão no GET /processes/{id}

**Problema:** o kanban (`GET /processes/kanban`) já tinha `has_minimal_base`, `has_complementary_base`, `missing_docs_count`, mas o detalhe individual (`GET /processes/{id}`) retornava o schema `Process` cru — sem os gates. Consultor vê os sinais no kanban mas perde quando abre o card de detalhe.

**Mudança:**
- Novo schema `ProcessDetail(Process)` em [app/schemas/process.py](../app/schemas/process.py) com 3 campos computados: `has_minimal_base`, `has_complementary_base`, `missing_docs_count`.
- [app/api/v1/processes.py:238+](../app/api/v1/processes.py): `GET /processes/{id}` agora `response_model=ProcessDetail`. Computa os gates reusando a mesma semântica do kanban (cliente com contato + imóvel com nome; `≥1` doc no processo; itens obrigatórios `status=pending` no checklist).

**Validação:** `GET /processes/18` retorna `{has_minimal_base: false, has_complementary_base: true, missing_docs_count: 4}` — consistente com o kanban.

#### Bloco B.2 — CAM1-003 Opção B: Process nasce sempre com `demand_type=nao_identificado`

**Decisão de produto (escolhida pelo user em 2026-04-20):** Opção B (meio-termo) — classificador continua rodando síncrono pra alimentar `initial_diagnosis` + checklist + process_type como **sugestões**, mas o `demand_type` **oficial** é forçado a `nao_identificado` na criação.

**Justificativa:** respeita a premissa "IA não decide na Camada 1" da sócia (Process não nasce classificado oficialmente) sem quebrar o UX (consultor ainda recebe o diagnóstico sugerido e o checklist pronto).

**Mudança:**
- [app/api/v1/intake.py:189-197](../app/api/v1/intake.py): linha `demand_type_enum = DemandType.nao_identificado` hardcoded, com comentário longo explicando o trade-off.
- `process_type=classification.demand_type` continua sendo gravado — é a **sugestão** (string).
- `initial_diagnosis` + `suggested_checklist_template` também continuam — sugestões para o consultor.
- O task Celery existente `run_llm_classification` em [app/workers/ai_tasks.py:76-77](../app/workers/ai_tasks.py) **só sobrescreve** `demand_type` se o valor atual for `nao_identificado` — ou seja, pode promover no futuro, mas nunca contradiz uma decisão manual do consultor.

**Validação:** `create-case` com description "Licenciamento ambiental..." → response devolve `demand_type: "misto"` (sugestão), mas `GET /processes/{id}` mostra `demand_type: "nao_identificado"` (oficial) + `process_type: "misto"` (sugestão guardada).

### Tickets adiados / fora de escopo Sprint I

- **CAM1-004 / CAM1-005 / CAM1-007** (🟠 Sprint 2 do plano original) — Complementar base, importar docs com IA, upload multi-tipo. Ficam para Sprint J.
- **CAM1-006** (🟠) — "Dados desejáveis vs mínimos" na UI. Ficam para Sprint J.
- **CAM1-014** (🚫) — papel da IA / guard rail no agent_atendimento. Adiado por `feedback_agents_config_frozen`.
- **Agente `atendimento` escreve de volta `demand_type`** — hoje `run_agent("atendimento")` executa mas não persiste a classificação no Process. O task `run_llm_classification` (outro caminho) sim. Unificar é refatoração de orchestration; fora do escopo Opção B.
- **Caveat semântico `status="triagem"` vs `macroetapa="entrada_demanda"`** — aceito na Sprint I; futura limpeza pode adicionar `ProcessStatus.entrada_demanda` e migrar dados. Não é urgente.

### Validações Sprint I

- [x] Backend: `GET /processes/{id}` retorna `ProcessDetail` com os 3 gates (validado em processo 18)
- [x] Backend: `create-case` persiste `demand_type=nao_identificado` mesmo com description rica (validado no processo 26, sugestão "misto")
- [x] Backend: imports OK (rebuild + rollout sem erro)
- [x] Frontend: nenhum arquivo alterado (schema extension é retrocompat; gates aparecem como campos extras ignoráveis)

---

## SPRINT J — Workspace polish (Camada 3) ✅ entregue 2026-04-20

**Contexto:** o user sinalizou que o menu lateral do workspace tinha itens que duplicavam o stepper horizontal do topo. Após reler `amigao_regente/CAMADA 3 - WORKSPACE EDIT1.pdf` ficou claro o alvo: alinhar o menu lateral aos 8 itens da sócia (Visão geral / Ações / Documentos / Dados / IA da etapa / Histórico / Decisões / Saídas), tornar o stepper informativo (4 estados) e clicável. A Sprint J entrega isso + remove a duplicata real ("Trilha") + aponta o rodapé colapsável para o conteúdo certo.

### Descobertas do audit (o que já existia)

- **Rodapé colapsável** (CAM3WS-009) **já existia** em [ProcessDetail.tsx:234+](../frontend/src/pages/Processes/ProcessDetail.tsx) — apenas estava exibindo `WorkflowTimeline` (trilha do template), não os eventos (audit log) que a sócia pediu. Troca simples.
- **Endpoint de Saídas** (CAM3WS-006) `GET /processes/{id}/artifacts` já existia em [app/api/v1/processes.py:697](../app/api/v1/processes.py) com `StageOutputResponse` — UI nunca consumiu.
- **MacroetapaState** completo com 7 estados (`nao_iniciada`, `em_andamento`, `aguardando_input`, `aguardando_validacao`, `pronta_para_avancar`, `travada`, `concluida`) exposto em `/can-advance.current_state` + `blockers[]`. Base pronta para o stepper 4 estados.

### Gaps fechados na Sprint J

#### Bloco 1 — Menu lateral reorganizado (CAM3WS-007)

Antes (9 itens): Diagnóstico · Dossiê · **Trilha** · Decisões · Comercial · Tarefas · Documentos · Timeline · IA

Agora (9 itens — alinhado à sócia + Comercial como condicional):
**Visão geral** · **Ações** · Documentos · **Dados** · IA · **Histórico** · Decisões · **Saídas** · Comercial

- ❌ **Removido**: "Trilha" (`workflow` TabKey) — duplicava o stepper horizontal do topo.
- 🏷 **Renomeados**: `Diagnóstico → Visão geral` · `Dossiê → Dados` · `Tarefas → Ações` · `Timeline → Histórico`. Keys preservadas para não quebrar state.
- ➕ **Adicionado**: tab "Saídas" (`saidas`) → novo componente [SaidasTab.tsx](../frontend/src/pages/Processes/SaidasTab.tsx) consumindo `GET /processes/{id}/artifacts`. Agrupa por macroetapa, marca produced_by (usuário/agente) e status de validação humana.
- 🔀 **Rodapé colapsável** agora exibe `TimelineTab` (audit events: uploads, status, decisões, propostas, contratos) conforme sócia — antes exibia `WorkflowTimeline` (redundante com o stepper).

#### Bloco 2 — Stepper com 4 estados + clicável (CAM3WS-008 / Opção A)

Antes: 3 estados visuais (ativo / concluído / futuro), não-clicável.

Agora: 5 visuais alinhados à sócia + futura:

| Estado | Visual | Origem |
|---|---|---|
| Concluída | verde claro + ✓ | etapa < current |
| Ativa | verde destacado | `em_andamento` / `pronta_para_avancar` |
| Bloqueada | vermelho + ! | `travada` (inclui blockers) |
| Aguardando pré-requisito | amarelo + ⏳ | `aguardando_input` / `aguardando_validacao` |
| Futura | cinza | etapa > current |

- Fonte de verdade: novo consumo de `GET /processes/{id}/can-advance` no [ProcessDetail.tsx:81+](../frontend/src/pages/Processes/ProcessDetail.tsx) → `current_state` + `blockers[]`.
- **Opção A clicável** (decisão do user em 2026-04-20): clicar em qualquer etapa seta `viewingStage` (state local). Tabs relevantes passam a filtrar por essa etapa:
  - `SaidasTab` → `?macroetapa=X` no endpoint
  - `DecisionsTab` → prop `currentMacroetapa={viewingStage ?? currentStage}`
  - (IA/AIPanel fica para sprint próxima quando expor filtro por etapa)
- Banner violeta abaixo do stepper quando `viewingStage !== currentStage` com CTA "Voltar à etapa atual".
- Anel violeta (`ring-2 ring-violet-400`) destaca a etapa sendo visualizada.

#### Bloco 3 — CAM3WS-009 já cumprido

O rodapé colapsável já existia; Sprint J só trocou o conteúdo pra `TimelineTab` (audit events). Sem alteração estrutural.

### Decisões de escopo (Sprint J)

- ❌ **Não** refatorar `AIPanel` para aceitar `viewingStage` — o componente hoje usa `processDemandType` e `processDescription`; adicionar filtro por etapa depende de endpoint novo. Adiado.
- ❌ **Não** enriquecer `MacroetapaStatusResponse.steps[].status` com 7 estados no backend — o frontend compõe visual a partir de `can-advance` (fonte já existente), evita mudar contrato de schema estável.
- ❌ **Não** deletar `WorkflowTimeline.tsx` — o componente ainda pode ser útil em outra tela (ex: ver trilha do template do caso). Ficou apenas sem uso em `ProcessDetail`.
- ✅ **Manter** tab Comercial no menu (sócia trata como condicional etapa 6/7) — não compromete.
- ✅ **Histórico** (TimelineTab) aparece em dois lugares: tab lateral + rodapé colapsável. Intencional — sócia sugeriu "Rodapé OU timeline". Ambos acessos OK.

### Validações Sprint J

- [x] Frontend `tsc --noEmit` limpo em `ProcessDetail.tsx` / `SaidasTab.tsx` / `ProcessDetailTypes.ts`
- [x] `GET /processes/{id}/artifacts` já respondia antes da Sprint (endpoint `SaidasTab` consome sem mudança backend)
- [x] `GET /processes/{id}/can-advance` já expõe `current_state` + `blockers` (usado pelo stepper)
- [x] Stepper clicável seta `viewingStage` e aciona banner + filtro em SaidasTab/DecisionsTab

---

## SPRINT K — Cam3 core polish (Lacunas + Validar saídas) ✅ entregue 2026-04-20

**Contexto:** auditoria dos 8 tickets da Sprint 3 (Fluxo + Workspace Cam3) revelou — de novo — que 6 já estavam 100% no código: **CAM3FT-001** (próximo passo + badge alerta), **CAM3FT-003** (counts de travados/prontos por coluna, renderizados em `QuadroAcoes.tsx:276-285`), **CAM3FT-004** (7 estados `MacroetapaState` + `compute_macroetapa_state`), **CAM3FT-005** (gate `can_advance_macroetapa` + enforce em `POST /macroetapa`), **CAM3WS-001** (layout 6-áreas em `ProcessDetail.tsx`), **CAM3WS-003** (`MACROETAPA_METADATA` com objetivo + expected_outputs por etapa + render em `WorkspaceRightPanel`). Apenas 2 tinham gap real: CAM3WS-005 (lacunas separadas de travas) e CAM3WS-006 (botão validar saídas).

### Já entregue antes (sem registro) — 6 tickets

| Ticket | Evidência |
|---|---|
| **CAM3FT-001** | `KanbanProcessCard.next_action` + `has_alerts`; render em [QuadroProcessCard.tsx:94-99](../frontend/src/pages/Processes/QuadroProcessCard.tsx) |
| **CAM3FT-003** | `KanbanColumn.blocked_count/ready_to_advance_count`; agregação em [processes.py:215-230](../app/api/v1/processes.py); render em [QuadroAcoes.tsx:276-285](../frontend/src/pages/Processes/QuadroAcoes.tsx) |
| **CAM3FT-004** | Enum [macroetapa.py:43-56](../app/models/macroetapa.py) com 7 estados; `compute_macroetapa_state` linha 316-348 |
| **CAM3FT-005** | `can_advance_macroetapa` + enforce em `POST /macroetapa` (HTTP 409 com blockers); UI desabilita botão "Avançar" |
| **CAM3WS-001** | 6 áreas em [ProcessDetail.tsx](../frontend/src/pages/Processes/ProcessDetail.tsx): Cabeçalho · Stepper · Menu lateral · Central · Painel direito · Rodapé colapsável |
| **CAM3WS-003** | `MACROETAPA_METADATA.objective` + `expected_outputs` expostos em `/can-advance` e renderizados em `WorkspaceRightPanel` |

### Gaps fechados na Sprint K

#### Bloco 1 — CAM3WS-005: Lacunas separadas de Travas

**Problema:** o painel lateral direito mostrava apenas "Travas" (impeditivos). A sócia pediu explicitamente **Lacunas** como seção distinta — informações faltando que o consultor pode preencher em paralelo, sem bloquear o avanço.

**Mudança:**
- `CanAdvanceResponse.gaps: list[str]` adicionado em [app/schemas/macroetapa.py](../app/schemas/macroetapa.py).
- `_compute_can_advance` em [app/api/v1/processes.py:437+](../app/api/v1/processes.py) agora escaneia o caso e emite lacunas quando encontra:
  - Cliente sem e-mail / telefone
  - Cliente PJ sem razão social
  - Imóvel sem matrícula / CAR / área / bioma
  - Processo sem `initial_summary` (voz do cliente)
- [WorkspaceRightPanel.tsx](../frontend/src/pages/Processes/WorkspaceRightPanel.tsx) ganha bloco amarelo "Lacunas a preencher (não bloqueiam)" distinto do bloco vermelho de Travas.

**Validação:** processo 18 retorna `blockers: [4 docs obrigatórios, checklist incompleto]` + `gaps: [Resumo inicial não registrado]` — seções distintas, confirmado em smoke test.

#### Bloco 2 — CAM3WS-006: Botão Validar saídas

**Problema:** UI da Sprint J já listava artefatos (StageOutputs) com status "Aguardando validação" mas sem CTA para validar. Endpoint `POST /processes/{id}/artifacts/{id}/validate` existia (entregou em sprint anterior).

**Mudança:**
- [SaidasTab.tsx](../frontend/src/pages/Processes/SaidasTab.tsx) ganha `validateMutation` e botão "Validar" verde no card quando `needs_human_validation && !validated_at`.
- Pós-validação, React Query invalida `process-artifacts` e o card vira "Validado" sem reload.

**Validação:** artifact criado com `needs_human_validation=true` → POST `/validate` → `validated_at` e `validated_by_user_id` persistidos (smoke test em processo 18, artifact #2).

### Decisões de escopo (Sprint K)

- ❌ **Não** adicionar UI de criação manual de artefato — endpoint `POST /artifacts` já existe, mas criação ideal é via agente (agent produz → `needs_human_validation=true` → consultor valida). Criação manual fica para quando aparecer caso de uso claro.
- ❌ **Não** refatorar agentes para popularem StageOutput automaticamente — mexe em config de agente (`feedback_agents_config_frozen`). Trigger pós-agente pode ser adicionado em orchestration sem mexer nos agentes em si (Sprint futura).
- ❌ **Não** adicionar categoria "lacuna crítica" vs "lacuna soft" — nível atual (lista plana em amarelo) basta; sócia pode refinar se precisar.
- ✅ **Gaps** computados server-side (não duplica lógica no frontend); backend é fonte única de verdade.

### Validações Sprint K

- [x] Backend: `GET /processes/{id}/can-advance` retorna `gaps` (validado em processo 18: 1 gap distinto de 2 blockers)
- [x] Backend: `POST /processes/{id}/artifacts/{id}/validate` registra `validated_at` + `validated_by_user_id` (validado em artifact #2)
- [x] Frontend `tsc --noEmit` limpo em `SaidasTab.tsx` e `WorkspaceRightPanel.tsx`
- [x] Painel lateral mostra Lacunas (amarelo) distintas de Travas (vermelho)
- [x] Kanban renderiza counts `blocked_count` / `ready_to_advance_count` por coluna (confirmado em `QuadroAcoes.tsx:276-285`)

---

## SPRINT L — Enriquecimento Cam1 (Importar docs c/ IA) ✅ entregue 2026-04-20

**Contexto:** auditoria dos 3 tickets da Sprint 2 (Enriquecimento Cam1) revelou — seguindo o padrão recorrente — que **CAM1-004 e CAM1-007 já estavam 100%** no código, sem registro. Apenas **CAM1-005** tinha gap real: o agente extrator era disparado mas o resultado (`extracted_fields`) ficava apenas no `AIJob.result`, sem exposição ao frontend nem UI de revisão.

### Já entregue antes (sem registro) — 2 tickets

#### ✅ CAM1-004 — "Complementar base já iniciada"
- **Backend**: endpoint `POST /intake/enrich` em [app/api/v1/intake.py:536-633](../app/api/v1/intake.py) — recebe `client_id` + `property_id` + `client_fields` + `property_fields`; registra AuditLog com stamp de hash (action `base_enriched`).
- **Schemas**: `IntakeEnrichRequest` / `IntakeEnrichResponse` em [app/schemas/intake.py:140-178](../app/schemas/intake.py).
- **Frontend**: flow `isEnrichFlow` no [IntakeWizard.tsx:173-256](../frontend/src/pages/Intake/IntakeWizard.tsx) — botão "Complementar base agora" + entry_type `complementar_base_existente` forçando modo existente para cliente/imóvel.

#### ✅ CAM1-007 — "Upload opcional multi-tipo com estados"
- **Backend**: `OcrStatus` enum em [app/models/document.py:10-15](../app/models/document.py) cobre `pending`/`processing`/`done`/`failed`/`not_required`.
- **Backend**: `POST /drafts/{id}/upload-url` + `POST /drafts/{id}/documents` registra Document com `ocr_status=pending`, aceita `document_type` dos 7 tipos Regente.
- **Frontend**: [DraftDocumentUploader.tsx:5-14](../frontend/src/pages/Intake/DraftDocumentUploader.tsx) expõe 7 tipos documentais; `badgeFor()` renderiza 4 estados visuais (Lido/Em leitura/Falhou/Enviado).

### Gap fechado na Sprint L — CAM1-005 em duas partes

#### Parte A — Endpoint de resultados extraídos

**Problema:** o agente `extrator` rodava (via `POST /intake/drafts/{id}/import`), salvava `extracted_fields` em `AIJob.result.extracted_fields`, mas não havia endpoint para o frontend consultar esses resultados. Consultor não via o que a IA extraiu.

**Mudança:**
- Novo endpoint `GET /intake/drafts/{id}/extraction-results` em [app/api/v1/intake.py](../app/api/v1/intake.py).
- Busca AIJobs `agent_name=extrator` + `status=completed`, ordena por `finished_at desc`, mantém o mais recente por `result.document_id` dos docs do draft.
- Schema novo `IntakeExtractionResultsResponse` com:
  - `by_document`: detalhe por doc (filename, type, `extracted_fields`, `fields_count`, `extracted_at`).
  - `suggestions`: dict agregado — primeiro valor não-vazio por campo vence (prioridade pela ordem do `finished_at desc`).
  - Contadores `docs_total`, `docs_with_results`.

**Validação:** smoke test com draft+doc+AIJob simulado — endpoint retorna `suggestions: {matricula, car_code, area_ha, municipio, uf}` + `by_document` populado.

#### Parte B — UI de sugestões no DraftDocumentUploader

**Mudança:**
- [DraftDocumentUploader.tsx](../frontend/src/pages/Intake/DraftDocumentUploader.tsx) ganha:
  - `useQuery` (via `useEffect + setInterval`) para `GET /extraction-results` com polling leve (5s) enquanto houver doc em `processing`.
  - Mapa `FIELD_LABELS` com labels pt-BR dos campos comuns (cpf_cnpj, matricula, car_code, area_ha, município, UF, etc.).
  - Painel violeta "🤖 Sugestões extraídas pela IA" abaixo do botão de importar, com grid 2-col mostrando cada sugestão + botão "Aplicar".
  - Prop nova `onApplySuggestion?: (field, value) => void` permite o wizard consumir e pré-preencher o formulário. Campos aplicados viram verdes com "✓ aplicado".
- Estado local `appliedFields: Set<string>` evita aplicação duplicada.

### Decisões de escopo (Sprint L)

- ❌ **Não** conectar `onApplySuggestion` ao `IntakeWizard` automaticamente nesta sprint — o hook existe, ligar os 5+ inputs do wizard é trabalho de UX/refactor que pode entrar numa sprint seguinte. O consultor ainda vê as sugestões e pode copiar manualmente.
- ❌ **Não** usar WebSocket para notificar fim da extração — polling 5s é suficiente para o UX (agente extrator leva ~10-30s).
- ❌ **Não** modificar agentes (`feedback_agents_config_frozen`) — só agregamos resultado existente.
- ❌ **Não** aplicar `normalize_category` nos documentos importados via draft upload — já feito na Sprint H (commit 36842fc).
- ✅ **Persistir extraction results só em AIJob** (não duplicar em Document) — fonte única de verdade.

### Validações Sprint L

- [x] Backend: endpoint `/intake/drafts/{id}/extraction-results` retorna estrutura correta (testado com draft+doc+AIJob simulado)
- [x] Backend: agrega corretamente quando múltiplos AIJobs existem para o mesmo doc (mais recente vence)
- [x] Frontend `tsc --noEmit` limpo em `DraftDocumentUploader.tsx`
- [x] UI mostra painel só quando há resultados; campos aplicados ficam em verde

---

## SPRINT M — Dashboard executivo (Camada 2) ✅ entregue 2026-04-20

**Contexto:** auditoria dos 4 tickets do Dashboard executivo (Sprint 5 do plano) revelou — padrão das últimas 7 sprints — que **CAM2D-001 e CAM2D-003 já estavam 100%** e **CAM2D-002/004 a 85-90%**. Sprint F Bloco 1 tinha entregue KPIs + funil; endpoints `/dashboard/stages`, `/alerts`, `/priority-cases`, `/ai-summary` existiam todos em [app/api/v1/dashboard.py](../app/api/v1/dashboard.py) com UI consumindo em `DashboardRegente.tsx`.

### Já entregue antes (sem registro) — 2 tickets 100%

#### ✅ CAM2D-001 — Bloco 3: Casos por etapa (7 estágios)
- `GET /dashboard/stages` em [dashboard.py:1017+](../app/api/v1/dashboard.py) retorna `list[StageDistribution]` com `macroetapa`, `label`, `total`, `blocked`, `ready_to_advance`, `avg_days_in_stage`.
- Computa estado via `compute_macroetapa_state` (travada/pronta_para_avancar).
- Filtros: `responsible_user_id`, `urgency`, `demand_type`, `state_uf`, `days`.
- Frontend: componente `StagesBlock` em `DashboardRegente.tsx` renderiza as 7 etapas com ícones 🚫/✓.

#### ✅ CAM2D-003 — Bloco 5: Casos prioritários do dia
- `GET /dashboard/priority-cases` com scoring ponderado: urgência (crítica=400, alta=200, média=50, baixa=0), dias parado>7 (+5/dia cap 150), docs pendentes (+20/doc), etapa travada (+120), aguardando validação (+100), pronto p/ avançar (+80).
- Retorna `client_name`, `property_name`, `macroetapa_label`, `priority_reason`, `next_step`, `responsible_user_name`.
- Frontend: `PriorityCasesBlock` renderiza lista clicável → `/processes/{id}`.

### Gaps fechados na Sprint M

#### Bloco 1 — CAM2D-002: regra de contratos aguardando assinatura

Antes, `/dashboard/alerts` cobria `doc_pendente`, `etapa_travada` e `proposta_sem_retorno`. A sócia pedia explicitamente "2 contratos aguardando assinatura". Agora:

- Nova query em [dashboard.py:get_dashboard_alerts](../app/api/v1/dashboard.py) conta `Contract` com `status=sent` + `sent_at < now - 7d` + `signed_at IS NULL`.
- Alerta `kind="contrato_aguardando_assinatura"`, severity `high` se ≥3 (match doc_pendente), senão `medium`.
- Regra "matrícula pendente" já era coberta implicitamente pelo loop `doc_type_pending` (alertas específicos por tipo); smoke test confirmou: `"7 caso(s) com matricula pendente"`.

#### Bloco 2 — CAM2D-004: cache 24h + fix de Query bug pré-existente

**Cache (nova feature):**
- Constante `DASHBOARD_AI_SUMMARY_CACHE_TTL = 86400s` + helper `_dashboard_ai_summary_cache_key(tenant_id)`.
- Endpoint ganha `refresh: bool = Query(False)` — hit de cache por default, `?refresh=true` força recálculo.
- Leitura Redis com `json.loads(cached)`, escrita com `setex`; falhas no Redis caem silenciosas (degradação graciosa — mesmo padrão do kanban-insights).
- Validado: TTL `86070s` após primeira call.

**Bug pré-existente fixado:**
- `get_dashboard_ai_summary` chamava `get_dashboard_stages(db=db, current_user=current_user)` diretamente sem passar os parâmetros `responsible_user_id`, `urgency`, `demand_type`, `state_uf`, `days`. Quando chamado fora do dispatch FastAPI, esses `Query(None)` vazavam como objetos `Query` (truthy), e `timedelta(days=<Query>)` levantava `TypeError: unsupported type for timedelta days component: Query`.
- Fix: passar `None` explícito para cada parâmetro. Existia desde o commit 14462b5 (Regente v3) — nunca detectado porque a UI não exercitava a rota até ser adicionada ao `DashboardRegente`.

### Decisões de escopo (Sprint M)

- ❌ **Não** integrar `agent_vigia` / `agent_acompanhamento` na Leitura IA — respeita `feedback_agents_config_frozen`; versão determinística atende MVP.
- ❌ **Não** adicionar LLM na Leitura IA — sócia já aceitou "1x/dia" como cadência (veja decisão QA-008 no kanban-insights); determinístico + cache 24h é suficiente.
- ❌ **Não** adicionar filtros `?refresh` aos demais endpoints do dashboard — só `ai-summary` tem cache.
- ✅ **Manter** `source="deterministic"` — transparência para o consultor que a leitura não veio de LLM.
- ✅ **Corrigir** o bug do Query objects — fix pequeno que destrava o endpoint inteiro.

### Validações Sprint M

- [x] Backend: `/dashboard/alerts` retorna 6 alertas incluindo novos tipos (docs por tipo específicos + etapa travada)
- [x] Backend: `/dashboard/ai-summary` responde 200 (bug do Query corrigido), escreve cache no Redis com TTL ~24h
- [x] Backend: `/dashboard/ai-summary?refresh=true` ignora cache e recalcula
- [x] Regra de contratos aguardando assinatura inserida (cobre cenário vazio — sem contratos sent>7d no seed)
- [x] Cache Redis key `tenant:2:dashboard_ai_summary:v1` presente com valor JSON serializado

---

## PENDÊNCIAS PARA AMANHÃ — 2026-04-21

**Última sessão:** fechamos 7 sprints em sequência (G → H → I → J → K → L → M) cobrindo Camada 2 (Cliente/Imóvel Hub), Camada 1 (Cadastro + Enriquecimento), Camada 3 (Workspace polish + gates) e Dashboard executivo. Commits em `main`: `648646c` → `a2eeedd` → `df7b139` → (Sprint M na sequência).

### Próxima sessão (em ordem de prioridade)

1. **Sprint N = Sprint 7 do plano — Refinamentos Camada 3** (~1-2h esperado pelo padrão G-M)
   - **CAM3WS-002** — Tipos de blocos no workspace (permanente / ativo / herdado / condicional). Provavelmente já parcial no `WorkspaceRightPanel` e nos tabs; auditar.
   - **CAM3WS-004** — Multi-agente por etapa (primary + secondary agents). Endpoint `/macroetapa/status` já tem `agent_chain: Optional[str]` — verificar se expõe primary/secondary.
   - **CAM3PR-001** — Princípio arquitetural "Cadastro cria, Workspace executa, Fluxo coordena". Auditoria das rotas de UI para identificar operações "profundas" fora do Workspace e redirecionar. É o mais pesado — possível split em dois blocos.

2. **Sprint O+ = Camada 4 — Agentes + Configurações** (escopo maior)
   - Material da sócia disponível em [amigao_regente/](../amigao_regente/): `Camada 4 conifguracao e agente de ia.pdf` + `regente lovable 1.png` + `1 nucleo.jpeg`.
   - Sprint F Bloco 2 já entregou a UI de Configurações (6 abas). Falta a parte **Agentes** da Camada 4 (gestão de prompts, cadeias, observabilidade, telemetria).
   - ⚠️ Respeitar `feedback_agents_config_frozen`: **não alterar** prompts/chains dos agentes existentes. Pode construir UI de visualização/dashboard dos agentes (read-only) ou endpoints novos que consomem agentes.

### Dívidas técnicas pequenas detectadas (polimento futuro)

- **CAM1-005 Parte B integração** — `DraftDocumentUploader.tsx` expõe `onApplySuggestion?` mas o `IntakeWizard` ainda não liga o callback aos campos do formulário. Ligar requer 5-7 `setField(...)` baseado no nome do campo extraído. ~30 min.
- **Stepper Opção A — AIPanel/tab IA** — Sprint J fez SaidasTab e DecisionsTab aceitarem `viewingStage`, mas `AIPanel` ainda não expõe filtro por etapa. Requer endpoint novo ou parâmetro adicional. ~1-2h.
- **CAM2D-002 agent_vigia** — alertas são determinísticos (regras SQL). `agent_vigia` existe mas não é chamado pelo endpoint. Integração respeitando `feedback_agents_config_frozen` seria apenas orquestração pós-agente.
- **CAM2D-004 leitura IA real** — texto hoje é regras + concat. Upgrade pra LLM respeitando "1x/dia" da sócia (cache 24h já existe) + tracking de tokens/custo.
- **Limpeza do doc** — as seções iniciais "CAMADA 1" → "CAMADA 4" listam tickets como "pendente/mudança necessária" que já foram entregues em G-M. Vale varrer e marcar status com 🔵 INFO linkando ao sprint de entrega.

### Comandos úteis para retomar amanhã

```bash
# Estado geral
docker compose ps
git log --oneline -10
alembic current  # (dentro do container api)

# Subir tudo se Docker dormiu
docker compose up -d db redis minio
docker compose up -d api worker client-portal

# Frontend dev local (fora do Docker)
cd frontend && npm run dev   # → http://localhost:5173
```

---

## HORIZONTE ESTRATÉGICO — AMIGÃO COMO GOVTECH

**Registrado em 2026-04-19 — visão do user.**

Após consolidar o SaaS de consultoria, o Amigão tem vocação para virar govtech que também atende o Estado: IBAMA, ICMBio, secretarias estaduais, órgãos de licenciamento. Palavras do user:

> *"Não adianta a gente ajudar o consultor e não olhar para os órgãos ambientais."*

### Orientação arquitetural

- Estruturas de dados (cliente, imóvel, caso, documento, caminho regulatório, **decisões**) devem permanecer **reutilizáveis como API pública/B2G**.
- **Rastreabilidade e governança** (Aba Decisões, audit log, assinatura digital, base normativa citada) são **investimentos estratégicos** — abrem a porta pro Estado.
- Referência: `docs/DocumentodeIntegraçõesGovTech.md`.
- Trade-offs "simples agora vs preparado para escala pública" devem ser **discutidos explicitamente** quando aparecerem.

**Não implementar agora.** MVP consultor primeiro. Manter no radar ao tomar decisões.
