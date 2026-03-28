1. Diagrama textual completo da arquitetura
1.1 Visão macro
[ Usuário Interno ]
    | web
    v
[ Painel Operacional - React/Vite ]
    |
    | HTTPS + JWT
    v
[ API Core - FastAPI ]
    | \
    |  \--> [ PostgreSQL + PostGIS + pgvector ]
    |  \--> [ Redis ]
    |  \--> [ Object Storage S3/R2 ]
    |  \--> [ WebSocket / Realtime ]
    |
    +--> [ Workers Python ]
            |
            +--> [ OCR Pipeline ]
            +--> [ Agente Atendente ]
            +--> [ Agente Extrator ]
            +--> [ Agente Regulatório ]
            +--> [ Agente Orquestrador ]
            +--> [ Agente Redator ]
            +--> [ Agente Vigia ]
            |
            +--> [ Provedores LLM ]
            +--> [ APIs externas / data brokers ]
            +--> [ Gmail / Outlook / WhatsApp ]
[ Cliente Final / Agricultor ]
    | web/mobile
    v
[ Portal do Cliente - Next.js ]
    |
    | HTTPS
    v
[ API Core - FastAPI ]
[ Técnico de Campo ]
    | offline-first
    v
[ App Mobile - React Native + SQLite local ]
    |
    | sync quando houver rede
    v
[ API Core - FastAPI ]
________________________________________
1.2 Componentes
A. Camada de interface
Painel interno — React + Vite
Mantemos esse padrão para o sistema autenticado porque a própria documentação já diferencia bem o painel operacional do site institucional: React/Vite para o painel, e Next.js apenas onde SEO importa. 
Módulos:
•	dashboard 
•	kanban 
•	clientes 
•	imóveis 
•	processos 
•	documentos 
•	mapas 
•	revisão de OCR 
•	propostas/contratos 
•	integrações 
•	custo/uso de IA 
B. Portal do cliente — Next.js
Módulos:
•	login do agricultor 
•	timeline do processo 
•	documentos 
•	mensagens 
•	upload de anexos 
•	status simplificado 
C. App de campo — React Native
Módulos:
•	visitas 
•	formulários 
•	fotos 
•	áudios 
•	GPS 
•	sync offline 
________________________________________
1.3 Núcleo transacional
API Core — FastAPI
Papel:
•	autenticação 
•	autorização 
•	multi-tenant 
•	regras de negócio 
•	CRUD 
•	geração de tarefas 
•	contratos e propostas 
•	faturamento 
•	portal 
•	integrações por tenant 
•	publicação de jobs 
A documentação original colocava esse papel no backend core: centralizar negócio, persistir no PostgreSQL e despachar jobs para o motor Python. A v2 preserva exatamente isso, só trocando PHP por FastAPI. 
Módulos internos recomendados
app/
  auth/
  tenants/
  users/
  clients/
  properties/
  processes/
  tasks/
  documents/
  communications/
  proposals/
  contracts/
  billing/
  portal/
  field/
  integrations/
  audit/
  ai_orchestration/
________________________________________
1.4 Processamento assíncrono
Redis
Usos:
•	fila de jobs 
•	cache 
•	websocket pub/sub 
•	locks distribuídos 
•	rate limiting 
A documentação já trata a mensageria assíncrona como obrigatória para evitar travamento do usuário durante OCR e leitura de matrículas longas. 
Workers Python
Separados da API HTTP.
Tipos:
•	worker-ocr 
•	worker-ai 
•	worker-rag 
•	worker-sync 
•	worker-monitoring 
•	worker-geospatial 
________________________________________
1.5 Motor de IA
A documentação foi correta em rejeitar LangChain/LangGraph como base arquitetural e defender SDK nativo com controle fino de prompt, tokens e payload. 
Estratégia v2
•	SDK nativo OpenAI / Google 
•	function calling nativo 
•	saída JSON estruturada 
•	prompts versionados 
•	jobs auditáveis 
•	custo por tenant 
Agentes
•	Atendente 
•	Extrator 
•	Regulatório 
•	Orquestrador 
•	Redator 
•	Vigia 
Todos já estão previstos com outputs estruturados e gatilhos específicos. 
________________________________________
1.6 Banco de dados
PostgreSQL + PostGIS + pgvector
Esse trio já está bem consolidado na documentação:
•	relacional/ACID 
•	geoespacial 
•	vetorial/RAG 
Schemas
app      -> negócio transacional
ai       -> jobs, uso de modelo, RAG, decisões
gov      -> preparação futura GovTech
support  -> tabelas auxiliares, templates, flags
Regras
•	tenant_id em tudo 
•	UUID em tudo 
•	arquivos fora do banco 
•	audit trail append-only 
•	isolamento do worker de IA em schema próprio, como a modelagem v1 já propõe. 
________________________________________
1.7 Storage
S3 / R2
A regra de ouro já está definida na documentação: PDF, shapefile, imagem e laudo nunca entram no PostgreSQL; só referência. 
Estrutura sugerida:
/tenant/{tenant_id}/clients/{client_id}/
/tenant/{tenant_id}/properties/{property_id}/
/tenant/{tenant_id}/processes/{process_id}/documents/
/tenant/{tenant_id}/processes/{process_id}/generated/
/tenant/{tenant_id}/field/{visit_id}/
/tenant/{tenant_id}/certificates/{certificate_id}/
________________________________________
1.8 Integrações externas
Estratégia oficial
A documentação já formalizou os 3 pilares para superar gov.br e portais fechados:
•	certificado A1 
•	data brokers 
•	human-in-the-loop 
Fluxo unificado
[ API Core ]
   |
   +--> [ Integration Adapter ]
            |
            +--> WhatsApp provider
            +--> E-mail provider
            +--> Google Drive
            +--> Signature provider
            +--> Billing provider
            +--> MapBiomas
            +--> SICAR proxy / broker
            +--> Serpro / BigData / outros
            +--> Certificado A1 flow
            +--> fallback tarefa manual
Padrão de integração
Cada tenant terá:
•	credenciais próprias 
•	status da integração 
•	limite por plano 
•	logs de falha 
•	health check 
•	retry policy 
________________________________________
2. Diagramas de sequência dos fluxos críticos
2.1 Upload e análise documental
Usuário -> Painel: envia PDF
Painel -> API Core: POST /documents
API Core -> PostgreSQL: cria metadado
API Core -> Storage: gera upload seguro
API Core -> Redis: publica job OCR
Worker OCR -> Storage: baixa arquivo
Worker OCR -> OCR engine: extrai texto
Worker OCR -> LLM: interpreta texto limpo
Worker OCR -> PostgreSQL: salva extração
Worker OCR -> API Core/Event Bus: resultado pronto
API Core -> WebSocket: notifica frontend
Painel -> Usuário: mostra diagnóstico/revisão
Baseado no fluxo assíncrono já proposto na arquitetura original. 
________________________________________
2.2 Intake por WhatsApp
Cliente -> WhatsApp provider: manda mensagem
Provider -> API Core: webhook inbound
API Core -> PostgreSQL: salva mensagem/thread
API Core -> Redis: cria job atendente
Worker AI -> contexto: carrega histórico
Worker AI -> LLM: classifica e coleta dados
Worker AI -> PostgreSQL: salva JSON estruturado
API Core -> PostgreSQL: cria lead/pré-processo
API Core -> Painel: notifica consultor
O Agente Atendente já foi desenhado para triagem de entrada com JSON estruturado. 
________________________________________
2.3 Geração do workflow
Diagnóstico pronto -> API Core
API Core -> Redis: cria job regulatório
Worker Regulatório -> pgvector: busca base normativa
Worker Regulatório -> PostgreSQL: salva fundamentos/checklist
API Core -> Redis: cria job orquestrador
Worker Orquestrador -> LLM: gera sequência de tarefas
Worker Orquestrador -> API Core/DB: cria tarefas e dependências
API Core -> WebSocket: atualiza kanban
Essa separação entre diagnóstico, consulta regulatória e orquestração também já está coerente com o desenho dos agentes. 
________________________________________
2.4 Integração governamental com fallback
Processo precisa de dado externo
API Core -> Integration Adapter
Adapter -> verifica rota disponível

[rota 1] API privada disponível
    -> consulta broker
    -> retorna dado
    -> processo segue

[rota 2] portal aceita certificado A1
    -> obtém certificado seguro
    -> assina requisição
    -> captura resposta
    -> processo segue

[rota 3] portal fechado / inviável
    -> cria tarefa manual
    -> consultor sobe PDF
    -> OCR/extrator retomam fluxo
Essa é a principal mitigação para dependência de gov.br e portais fechados. 
________________________________________
3. Backlog técnico da Fase 1
Objetivo da Fase 1
Entregar o núcleo operacional vendável, com:
•	autenticação 
•	multi-tenant 
•	clientes/imóveis/processos 
•	documentos 
•	tarefas 
•	portal inicial 
•	intake 
•	base da mensageria 
•	fundação para OCR e IA 
A própria documentação recomenda fatiar o projeto para não tentar entregar os 6 agentes de uma vez. 
________________________________________
Epic 1 — Fundação do repositório e arquitetura
Entregas
•	monorepo ou polyrepo definido 
•	padrão de branches 
•	lint/format/test 
•	Docker base 
•	CI/CD inicial 
•	ambientes dev/staging/prod 
Tarefas
•	criar estrutura do backend FastAPI 
•	criar estrutura do painel React/Vite 
•	criar estrutura do portal Next.js 
•	criar boilerplate do mobile React Native 
•	configurar pre-commit 
•	configurar pytest 
•	configurar ESLint/Prettier 
•	configurar build/publish 
________________________________________
Epic 2 — Infraestrutura base
Entregas
•	PostgreSQL 
•	Redis 
•	storage S3/R2 
•	secret manager 
•	observabilidade mínima 
Tarefas
•	provisionar banco 
•	habilitar PostGIS e pgvector 
•	provisionar Redis 
•	provisionar bucket 
•	configurar variáveis por ambiente 
•	configurar Sentry/logging 
•	configurar backup inicial 
________________________________________
Epic 3 — Autenticação, RBAC e multi-tenant
Entregas
•	cadastro de tenant 
•	login 
•	refresh token 
•	roles/permissões 
•	tenant context obrigatório 
Tarefas
•	tabela de tenants 
•	tabela de usuários 
•	roles/permissões 
•	middleware de tenant 
•	JWT + refresh 
•	guards de permissão 
•	subdomínio/roteamento por tenant 
•	trilha de auditoria de login 
________________________________________
Epic 4 — CRM base
Entregas
•	clientes 
•	contatos 
•	endereço 
•	histórico 
Tarefas
•	CRUD clientes 
•	busca por nome/documento 
•	mask/encryption de CPF/CNPJ 
•	timeline do cliente 
•	anexos do cliente 
•	vínculo com processos 
________________________________________
Epic 5 — Imóveis e geoespacial
Entregas
•	cadastro de imóveis 
•	geometria 
•	mapa básico 
•	vínculo cliente-imóvel 
Tarefas
•	CRUD imóveis 
•	upload/import de geometria 
•	visualização em mapa 
•	cálculo básico de área 
•	estrutura para sobreposição futura 
•	validação SRID 
________________________________________
Epic 6 — Processos ambientais
Entregas
•	criação de processo 
•	status 
•	prioridade 
•	responsável 
•	histórico de status 
Tarefas
•	CRUD processos 
•	máquina de estados inicial 
•	associação cliente/imóvel 
•	painel de listagem 
•	filtros por status/responsável 
•	timeline de mudanças 
________________________________________
Epic 7 — Tarefas e Kanban
Entregas
•	board kanban 
•	tarefas por processo 
•	dependências 
•	prazos 
•	comentários 
Tarefas
•	CRUD tarefas 
•	board drag-and-drop 
•	responsáveis 
•	prioridade 
•	checklist básico 
•	comentários 
•	anexos 
•	notificações internas 
O workflow por tarefas e dependências já é um pilar central da arquitetura funcional do produto. 
________________________________________
Epic 8 — Gestão documental
Entregas
•	upload seguro 
•	listagem 
•	preview 
•	versionamento simples 
•	metadados 
Tarefas
•	presigned upload/download 
•	tabela de documentos 
•	categorização 
•	preview PDF/imagem 
•	vínculo com cliente/imóvel/processo/tarefa 
•	checksum 
•	fila de OCR pendente 
________________________________________
Epic 9 — Base assíncrona e jobs
Entregas
•	publicação e consumo de jobs 
•	dashboard técnico de jobs 
•	retries e DLQ simplificada 
Tarefas
•	escolher stack de workers 
•	criar filas por tipo 
•	criar contrato de payload 
•	criar estados de job 
•	retry policy 
•	dead-letter queue 
•	métricas de fila 
A comunicação assíncrona é mandatória no desenho original. 
________________________________________
Epic 10 — Agente Atendente v1
Entregas
•	webhook de entrada 
•	classificação inicial 
•	criação de lead/pré-processo 
Tarefas
•	integração WhatsApp inbound 
•	integração e-mail inbound 
•	persistência de thread/mensagens 
•	prompt v1 do atendente 
•	schema JSON de saída 
•	criação automática de lead 
•	revisão humana do intake 
________________________________________
Epic 11 — Portal do cliente v1
Entregas
•	login do cliente 
•	lista de processos 
•	timeline 
•	download de documentos liberados 
Tarefas
•	acesso portal_user 
•	listagem de processos visíveis 
•	eventos do processo 
•	upload de anexos pelo cliente 
•	mensagens simples 
•	políticas de visibilidade 
________________________________________
Epic 12 — Configuração por tenant
Entregas
•	tela de integrações 
•	credenciais por tenant 
•	chaves de IA / e-mail / WhatsApp 
Tarefas
•	modelar integration_accounts 
•	UI de configuração 
•	validação de conexão 
•	health check 
•	secret reference 
•	limites por plano 
Isso conversa diretamente com sua estratégia de repassar custo de IA e integrações por tenant. 
________________________________________
Epic 13 — Observabilidade e auditoria
Entregas
•	audit log 
•	logs estruturados 
•	métricas básicas 
•	custo por tenant 
Tarefas
•	audit middleware 
•	request_id 
•	log JSON 
•	métricas de API 
•	métricas de worker 
•	métricas de consumo de IA 
•	dashboard operacional 
A documentação coloca auditabilidade total e logs imutáveis como requisito de fundação. 
________________________________________
4. Ordem recomendada de execução
Sprint 0
•	repositórios 
•	padrão de engenharia 
•	Docker 
•	CI/CD 
•	ambientes 
Sprint 1
•	infra base 
•	auth 
•	multi-tenant 
•	RBAC 
Sprint 2
•	clientes 
•	imóveis 
•	processos 
Sprint 3
•	tarefas/kanban 
•	documentos 
•	storage 
Sprint 4
•	jobs assíncronos 
•	websocket 
•	audit log 
Sprint 5
•	atendente v1 
•	portal cliente v1 
•	integrações por tenant 
Sprint 6
•	hardening 
•	testes E2E 
•	observabilidade 
•	preparação piloto 
________________________________________
5. Critério de “Fase 1 pronta”
A Fase 1 está pronta quando:
•	um tenant consegue operar clientes, imóveis, processos e tarefas sem planilha paralela 
•	documentos sobem com segurança e ficam organizados 
•	o portal do cliente reduz parte da pressão operacional 
•	o intake por WhatsApp/e-mail já gera registro estruturado 
•	a arquitetura assíncrona já está pronta para OCR e expansão dos agentes 
•	a fundação multi-tenant, auditável e geoespacial já está estabelecida.
