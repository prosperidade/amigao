Backlog funcional por tela
1.1 Painel de Login
Objetivo
Autenticar usuários internos e externos com segurança, respeitando RBAC e multi-tenant. A documentação já prevê JWT RS256, refresh token em cookie HttpOnly e perfis distintos como Admin, Consultor, Técnico de Campo, Parceiro e Cliente Final. 
Funcionalidades
•	login com e-mail e senha 
•	recuperação de senha 
•	logout 
•	refresh de sessão 
•	identificação do tenant 
•	redirecionamento por perfil 
Critérios de aceite
•	usuário autenticado recebe contexto do tenant 
•	perfil define acesso inicial 
•	parceiro não entra no painel principal 
•	cliente final é enviado ao portal 
________________________________________
1.2 Dashboard Operacional
Objetivo
Dar visão executiva da operação: processos, prazos, tarefas, pendências e alertas. A arquitetura base já define dashboard central com métricas e tarefas pendentes. 
Widgets
•	processos por status 
•	tarefas vencidas 
•	tarefas por responsável 
•	documentos aguardando revisão 
•	alertas do vigia 
•	custos de IA por período 
•	processos críticos 
Funcionalidades
•	filtros por período 
•	filtros por responsável 
•	filtros por tipo de processo 
•	cards clicáveis 
•	atalhos rápidos 
Critérios de aceite
•	dashboard carrega em menos de 2 segundos com paginação e cache 
•	cada widget respeita tenant_id 
•	dados refletem status do fluxo real 
________________________________________
1.3 Tela de Clientes
Objetivo
Centralizar cadastro e histórico de clientes. A modelagem v1 já define cliente como entidade raiz operacional com tipo PF/PJ, canal de origem e status CRM. 
Funcionalidades
•	listar clientes 
•	buscar por nome, CPF/CNPJ, telefone 
•	criar cliente 
•	editar cliente 
•	ver timeline do cliente 
•	anexar documentos 
•	ver processos vinculados 
Campos principais
•	nome/razão social 
•	CPF/CNPJ 
•	e-mail 
•	telefone 
•	município/UF 
•	origem 
•	status CRM 
Critérios de aceite
•	CPF/CNPJ protegido 
•	duplicidade controlada por tenant 
•	busca rápida com paginação 
________________________________________
1.4 Tela de Imóveis
Objetivo
Gerenciar propriedades rurais, dados fundiários e geoespaciais. O documento técnico e a modelagem já tratam PostGIS como inegociável e o imóvel como núcleo do cruzamento espacial. 
Funcionalidades
•	cadastro de imóvel 
•	vínculo com cliente 
•	georreferenciamento 
•	upload de geometria 
•	exibição em mapa 
•	exibição de CAR, CCIR, NIRF 
•	visualização de embargo e passivos 
Blocos da tela
•	dados cadastrais 
•	dados fundiários 
•	dados ambientais 
•	mapa 
•	documentos vinculados 
•	processos vinculados 
Critérios de aceite
•	geometria salva em EPSG 4674 
•	mapa exibe perímetro 
•	imóvel pode existir antes do processo 
•	integração futura com SICAR não quebra o cadastro manual 
________________________________________
1.5 Tela de Processos
Objetivo
Ser a unidade central de trabalho do sistema. A modelagem já define processo como núcleo do fluxo com status, urgência, órgão, prazo e diagnóstico de IA. 
Funcionalidades
•	criar processo 
•	vincular cliente e imóvel 
•	definir tipo 
•	definir urgência 
•	definir responsável 
•	mudar status 
•	registrar protocolo externo 
•	ver timeline 
•	ver resumo 
•	ver diagnóstico IA 
Abas da tela
•	visão geral 
•	tarefas 
•	documentos 
•	comunicação 
•	custos 
•	histórico 
•	IA 
Critérios de aceite
•	mudança de status gera histórico 
•	prazo pode disparar alerta 
•	dados do processo alimentam agentes 
________________________________________
1.6 Kanban de Tarefas
Objetivo
Executar a operação. A arquitetura já coloca o Kanban com responsáveis, prazos e dependências como uma das entregas mais importantes da Fase 1, e o orquestrador futuro cria tarefas com responsáveis e dependências. 
Colunas
•	backlog 
•	a fazer 
•	em progresso 
•	aguardando 
•	revisão 
•	concluída 
•	cancelada 
Funcionalidades
•	criar tarefa manual 
•	mover tarefa entre colunas 
•	atribuir responsável 
•	definir prazo 
•	adicionar dependência 
•	comentar 
•	anexar documento 
•	marcar origem IA 
Critérios de aceite
•	drag-and-drop funcional 
•	tarefas filtráveis por processo/responsável/prazo 
•	tarefas vencidas destacadas 
•	parceiro vê só o que foi atribuído a ele 
________________________________________
1.7 Tela de Documentos
Objetivo
Controlar upload, organização e processamento documental. A documentação é explícita: arquivo pesado não entra no PostgreSQL; só metadado e s3_key, com presigned URLs. 
Funcionalidades
•	upload via drag-and-drop 
•	categorização por tipo 
•	preview 
•	download seguro 
•	versionamento 
•	vínculo com processo/imóvel/cliente 
•	status OCR 
•	confiança OCR 
•	fila de revisão humana 
Critérios de aceite
•	upload usa presigned URL 
•	documento fica vinculado corretamente 
•	confiança baixa sinaliza revisão 
•	sem URL pública permanente 
________________________________________
1.8 Tela de Revisão de OCR/Extração
Objetivo
Mitigar risco de OCR ruim antes que ele contamine o fluxo. A arquitetura técnica exige OCR clássico antes do LLM e alerta que matrículas ruins geram alucinação se forem enviadas direto ao modelo. 
Funcionalidades
•	comparar arquivo e texto extraído 
•	editar campos extraídos 
•	aprovar/rejeitar extração 
•	reenfileirar processamento 
•	marcar documento como validado 
•	criar tarefa de revisão 
Critérios de aceite
•	usuário consegue corrigir dados 
•	correção fica auditada 
•	reprocessamento preserva histórico 
________________________________________
1.9 Tela de Comunicação
Objetivo
Centralizar WhatsApp, e-mail e mensagens internas ligadas ao processo. O agente atendente e o vigia dependem disso. 
Funcionalidades
•	lista de threads 
•	mensagens inbound/outbound 
•	anexos 
•	vínculo com processo 
•	resposta manual 
•	classificação IA futura 
•	status de entrega/leitura quando disponível 
Critérios de aceite
•	uma thread pode existir sem processo e virar processo depois 
•	mensagens ficam auditáveis 
•	usuário vê o histórico consolidado 
________________________________________
1.10 Tela de Propostas e Contratos
Objetivo
Cobrir o fluxo comercial que você definiu como parte do produto.
Funcionalidades
•	criar proposta 
•	itens da proposta 
•	gerar contrato 
•	enviar para assinatura 
•	acompanhar status 
•	histórico de versões 
Critérios de aceite
•	proposta pode nascer de processo ou lead 
•	contrato pode ser gerado a partir de proposta aceita 
•	status de assinatura sincroniza com provider 
________________________________________
1.11 Tela de Configurações do Tenant
Objetivo
Permitir white-label e custo por tenant. Isso conversa diretamente com sua estratégia de cada cliente usar sua própria chave de IA, seu próprio provider de WhatsApp, e-mail e integrações.
Funcionalidades
•	dados do tenant 
•	branding 
•	usuários 
•	perfis e permissões 
•	integrações 
•	chaves externas 
•	limites de uso 
•	módulos habilitados 
Critérios de aceite
•	segredos nunca expostos em texto puro 
•	health check por integração 
•	alteração auditada 
________________________________________
1.12 Portal do Cliente
Objetivo
Trazer transparência e reduzir pressão sobre o consultor. A documentação já prevê cliente final com acesso read-only ao próprio processo. 
Funcionalidades
•	login do cliente 
•	listagem de processos 
•	timeline 
•	download de documentos liberados 
•	upload de anexos 
•	mensagens 
•	status simplificado 
Critérios de aceite
•	cliente só vê os próprios dados 
•	evento relevante aparece na timeline 
•	upload do cliente entra no fluxo correto 
________________________________________
1.13 App de Campo
Objetivo
Coleta em campo com sincronização posterior. A estrutura de storage já prevê pasta específica para dados de campo. 
Funcionalidades
•	login 
•	baixar contexto da visita 
•	fotos 
•	áudios 
•	localização 
•	formulários 
•	checklist 
•	sincronização 
Critérios de aceite
•	funciona offline 
•	sincroniza quando houver rede 
•	conflito simples tratado sem perda de evidência 
________________________________________
2. Backlog técnico por endpoint
Vou sugerir padrão REST inicial, porque é o melhor equilíbrio entre clareza e velocidade para o MVP.
2.1 Auth
Endpoints
•	POST /auth/login 
•	POST /auth/refresh 
•	POST /auth/logout 
•	POST /auth/forgot-password 
•	POST /auth/reset-password 
•	GET /auth/me 
Regras
•	JWT curto 
•	refresh rotativo 
•	contexto de tenant obrigatório 
•	RBAC no payload ou resolvido em backend 
________________________________________
2.2 Tenants
•	GET /tenants/current 
•	PATCH /tenants/current 
•	GET /tenants/current/settings 
•	PATCH /tenants/current/settings 
________________________________________
2.3 Users e RBAC
•	GET /users 
•	POST /users 
•	GET /users/{id} 
•	PATCH /users/{id} 
•	DELETE /users/{id} 
•	GET /roles 
•	POST /roles 
•	PATCH /roles/{id} 
•	GET /permissions 
Regras
•	parceiro e cliente final têm escopo reduzido 
•	soft delete preferencial 
•	auditoria de alteração de permissão 
________________________________________
2.4 Clientes
•	GET /clients 
•	POST /clients 
•	GET /clients/{id} 
•	PATCH /clients/{id} 
•	GET /clients/{id}/processes 
•	GET /clients/{id}/documents 
•	GET /clients/{id}/timeline 
________________________________________
2.5 Imóveis
•	GET /properties 
•	POST /properties 
•	GET /properties/{id} 
•	PATCH /properties/{id} 
•	POST /properties/{id}/geometry 
•	GET /properties/{id}/map 
•	GET /properties/{id}/documents 
•	GET /properties/{id}/processes 
•	GET /properties/{id}/overlaps 
Regras
•	geometrias salvas separadamente 
•	análises espaciais pesadas podem virar job assíncrono depois 
________________________________________
2.6 Processos
•	GET /processes 
•	POST /processes 
•	GET /processes/{id} 
•	PATCH /processes/{id} 
•	POST /processes/{id}/status 
•	GET /processes/{id}/timeline 
•	GET /processes/{id}/tasks 
•	GET /processes/{id}/documents 
•	GET /processes/{id}/communications 
•	GET /processes/{id}/ai-summary 
Regras
•	transição de status validada por máquina de estados 
•	protocolo externo fica rastreável 
•	timeline consolidada 
________________________________________
2.7 Tarefas
•	GET /tasks 
•	POST /tasks 
•	GET /tasks/{id} 
•	PATCH /tasks/{id} 
•	POST /tasks/{id}/move 
•	POST /tasks/{id}/assign 
•	POST /tasks/{id}/complete 
•	POST /tasks/{id}/comments 
•	GET /tasks/kanban 
Regras
•	dependência impede conclusão prematura 
•	tarefa criada por IA fica marcada 
•	tarefa de parceiro respeita escopo isolado 
________________________________________
2.8 Documentos
•	POST /documents/upload-url 
•	POST /documents/confirm-upload 
•	GET /documents 
•	GET /documents/{id} 
•	PATCH /documents/{id} 
•	GET /documents/{id}/download-url 
•	POST /documents/{id}/analyze 
•	GET /documents/{id}/extraction 
•	POST /documents/{id}/review 
•	POST /documents/{id}/reprocess 
Regras
•	upload em duas etapas 
•	metadado antes do processamento 
•	OCR e extração sempre assíncronos 
________________________________________
2.9 Comunicação
•	GET /threads 
•	GET /threads/{id} 
•	POST /threads/{id}/messages 
•	POST /communications/webhooks/whatsapp 
•	POST /communications/webhooks/email 
•	POST /communications/classify 
•	POST /communications/link-process 
Regras
•	webhook cria thread se não existir 
•	classificação IA vira job 
•	thread pode ser associada depois ao processo 
________________________________________
2.10 Propostas
•	GET /proposals 
•	POST /proposals 
•	GET /proposals/{id} 
•	PATCH /proposals/{id} 
•	POST /proposals/{id}/send 
•	POST /proposals/{id}/accept 
•	POST /proposals/{id}/reject 
________________________________________
2.11 Contratos
•	GET /contracts 
•	POST /contracts 
•	GET /contracts/{id} 
•	PATCH /contracts/{id} 
•	POST /contracts/{id}/generate 
•	POST /contracts/{id}/send-signature 
•	POST /contracts/webhooks/signature 
________________________________________
2.12 Billing e uso
•	GET /billing/invoices 
•	GET /billing/usage 
•	GET /billing/usage/ai 
•	GET /billing/usage/integrations 
•	POST /billing/webhooks/provider 
Regras
•	custo variável por IA e APIs precisa ser registrável e repassável, como a documentação já recomenda para data brokers e tokens. 
________________________________________
2.13 Integrações por tenant
•	GET /integrations 
•	POST /integrations 
•	PATCH /integrations/{id} 
•	POST /integrations/{id}/test 
•	POST /integrations/{id}/disable 
Providers iniciais
•	OpenAI / Gemini 
•	Resend / SMTP 
•	Z-API / Evolution 
•	Google Drive 
•	assinatura eletrônica 
•	billing provider 
•	MapBiomas 
•	broker SICAR/dados 
________________________________________
2.14 Portal do cliente
•	POST /portal/auth/login 
•	GET /portal/me 
•	GET /portal/processes 
•	GET /portal/processes/{id} 
•	GET /portal/processes/{id}/timeline 
•	GET /portal/processes/{id}/documents 
•	POST /portal/processes/{id}/documents 
•	GET /portal/threads 
•	POST /portal/threads/{id}/messages 
________________________________________
2.15 Campo / offline
•	GET /field/visits 
•	GET /field/visits/{id} 
•	POST /field/sync 
•	POST /field/uploads/upload-url 
•	POST /field/uploads/confirm 
•	GET /field/checklists/{id} 
Regras
•	sync idempotente 
•	lote por dispositivo 
•	logs por conflito 
________________________________________
2.16 IA / Jobs
A documentação já prevê ai.jobs, custo por modelo, payload de entrada, resultado, duração e erro. 
•	POST /ai/jobs 
•	GET /ai/jobs/{id} 
•	POST /ai/jobs/{id}/retry 
•	GET /ai/jobs?entity_type=...&entity_id=... 
•	POST /ai/redactor/generate 
•	POST /ai/orchestrator/plan 
•	POST /ai/extractor/run 
•	POST /ai/regulatory/query 
Regras
•	API core cria job 
•	worker processa 
•	callback atualiza entidade 
•	auditoria em todas as etapas 
________________________________________
3. Ordem ideal de implementação
Onda 1 — fundação
•	auth 
•	multi-tenant 
•	RBAC 
•	users 
•	tenants 
•	audit log 
•	infra base 
Onda 2 — operação principal
•	clients 
•	properties 
•	processes 
•	tasks 
•	dashboard 
Onda 3 — documental
•	storage 
•	upload seguro 
•	documents 
•	preview 
•	fila assíncrona 
Onda 4 — comunicação e portal
•	threads/messages 
•	webhooks WhatsApp/e-mail 
•	portal cliente 
Onda 5 — IA inicial
•	jobs 
•	atendente v1 
•	extrator v1 
•	revisão OCR 
Onda 6 — comercial
•	proposals 
•	contracts 
•	signature 
•	usage billing 
Onda 7 — campo
•	field visits 
•	sync 
•	uploads mobile 
________________________________________
4. MVP realista da Fase 1
Se eu fosse fechar o escopo executável agora, eu travaria a Fase 1 em:
•	login + RBAC 
•	clientes 
•	imóveis 
•	processos 
•	kanban 
•	documentos com upload seguro 
•	dashboard básico 
•	portal do cliente v1 
•	integrações por tenant v1 
•	jobs assíncronos prontos, mesmo que a IA ainda entre em parte na fase seguinte 
Isso ainda respeita a lógica do roadmap original de começar com workflow + CRM antes de despejar toda a complexidade dos agentes de uma vez
