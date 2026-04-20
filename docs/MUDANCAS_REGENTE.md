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

### Sprint 8+ — Camada 4 (quando mapa chegar)

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
- **Cliente Hub / Imóvel Hub** (Camada 2) — próximo alvo natural (gaps listados em CAM2CH e CAM2IH neste doc)

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
