Arquitetura Técnica Detalhada v2
1. Visão arquitetural
A v1 acertou no ponto principal: o sistema precisa ser desacoplado, com frontend, backend transacional, motor de IA, banco e storage bem separados, para permitir evolução independente e escala horizontal 
A diferença da v2 é que removemos o PHP/Laravel da posição de backend core e consolidamos o núcleo em FastAPI, porque você já decidiu por Python como stack principal.
Arquitetura-alvo
1.	Frontend web operacional
React + Vite 
2.	Portal do cliente
Next.js 
3.	App mobile de campo
React Native 
4.	API Core
FastAPI 
5.	Workers assíncronos
Python workers separados da API 
6.	Motor de IA / automação documental
Serviços Python especializados 
7.	Banco transacional e geoespacial
PostgreSQL + PostGIS + pgvector 
8.	Cache, fila e eventos
Redis 
9.	Storage de arquivos
S3 ou Cloudflare R2 
10.	Observabilidade e auditoria
logs, métricas, tracing e trilha imutável 
________________________________________
2. Princípios arquiteturais
2.1 Separação de responsabilidade
A v1 já definia corretamente que frontend, backend transacional e motor de IA não podem ficar misturados 
Na v2 isso continua obrigatório.
2.2 Human-in-the-loop
A v1 também foi correta ao dizer que nenhuma decisão crítica deve ser finalizada sem validação humana 
Na v2 isso vira regra de arquitetura:
•	IA sugere 
•	sistema estrutura 
•	humano valida 
•	sistema registra auditoria 
2.3 Assíncrono por padrão
Processamento pesado de OCR, RAG, parsing, geração documental e monitoramento de e-mail não roda na thread HTTP da API. A v1 já alertava que chamadas síncronas travariam a experiência do usuário 
2.4 Tenant isolation
Toda entidade de negócio carrega tenant_id, como já definido na arquitetura e modelagem base 
2.5 Arquivos fora do banco
A regra de ouro permanece: PostgreSQL guarda metadado e referência; PDFs, imagens, shapefiles e artefatos gerados ficam no storage 
________________________________________
3. Camadas do sistema
3.1 Camada de apresentação
Painel interno
React + Vite
Responsabilidades:
•	dashboard operacional 
•	Kanban 
•	cadastro de clientes/imóveis/processos 
•	visualização de documentos 
•	visualização de mapas 
•	revisão de extrações 
•	aprovação de sugestões da IA 
•	gestão de tarefas e condicionantes 
A escolha de React + Vite continua boa para painel logado, exatamente pelo que a v1 já trazia: não há necessidade de SSR para o sistema autenticado 
Portal do cliente
Next.js
Responsabilidades:
•	login do agricultor/cliente 
•	acompanhamento de processo 
•	download de documentos 
•	envio de anexos 
•	timeline de eventos 
•	status simplificado 
App de campo
React Native
Responsabilidades:
•	coleta offline 
•	fotos 
•	áudio 
•	geolocalização 
•	formulários 
•	checklist 
•	sincronização posterior 
________________________________________
3.2 Camada de API Core
Stack
Python + FastAPI
Responsabilidades:
•	autenticação 
•	autorização 
•	RBAC 
•	CRUD transacional 
•	regras de negócio 
•	workflow 
•	faturamento 
•	integrações por tenant 
•	emissão de eventos 
•	orquestração de jobs 
•	geração de presigned URLs 
•	callbacks de processamento 
Organização recomendada
Eu recomendo arquitetura modular por domínio:
•	auth 
•	tenants 
•	users 
•	clients 
•	properties 
•	processes 
•	tasks 
•	documents 
•	communications 
•	proposals 
•	contracts 
•	billing 
•	portal 
•	field 
•	integrations 
•	audit 
•	ai_orchestration 
Padrão de aplicação
•	FastAPI para borda HTTP 
•	SQLAlchemy 2.0 
•	Alembic para migrations 
•	Pydantic para contratos 
•	service layer por domínio 
•	repository pattern só onde fizer sentido 
•	eventos internos explícitos 
Regra importante
A API Core não chama LLM diretamente dentro da request.
Ela registra intenção, persiste estado, publica job e devolve resposta rápida.
________________________________________
3.3 Camada de processamento assíncrono
Stack
Python workers + Redis
A v1 já previa Redis e fila como espinha dorsal da comunicação assíncrona 
Na v2 eu manteria isso, mas sem acoplamento a Laravel Queues.
Recomendação
•	Redis como broker e cache 
•	RQ, Dramatiq ou Celery 
•	preferência prática: Celery ou Dramatiq 
•	scheduler para CRONs: 
o	Celery Beat 
o	APScheduler 
o	ou cron nativo em jobs isolados 
Tipos de job
•	OCR 
•	extração documental 
•	vetorização de base regulatória 
•	geração de minuta 
•	classificação de e-mail 
•	consulta a data brokers 
•	sincronização de integrações 
•	recomputação geoespacial 
•	alertas de prazo 
•	consolidação de custos de uso 
________________________________________
3.4 Camada de IA
A v1 foi correta em rejeitar LangChain/LangGraph para esse caso e defender SDK nativo com controle de payload, tokens e debug 
Eu manteria isso integralmente.
Estratégia v2
Sem LangChain como base arquitetural.
Usar:
•	SDK nativo OpenAI 
•	SDK nativo Google/Vertex 
•	chamadas controladas 
•	schemas JSON rígidos 
•	tools/function calling nativo 
•	versionamento de prompts 
Submódulos de IA
1.	Atendente 
2.	Extrator 
3.	Regulatório 
4.	Orquestrador 
5.	Redator 
6.	Vigia 
Os seis agentes já estavam bem definidos na v1, com gatilhos e outputs específicos 
Na v2 eles deixam de ser “serviços mágicos” e passam a ser capabilities internas acionadas por jobs.
Padrão de execução recomendado
Cada job de IA:
•	recebe job_id 
•	recebe tenant_id 
•	recebe entity_type/entity_id 
•	busca contexto mínimo necessário 
•	executa pipeline 
•	retorna JSON estruturado 
•	grava resultado 
•	dispara evento de conclusão 
•	registra uso/custo/auditoria 
________________________________________
4. Arquitetura de dados
4.1 Banco principal
PostgreSQL 16 + PostGIS + pgvector
A documentação já consolidou que o banco precisa atender três naturezas ao mesmo tempo: relacional, geoespacial e vetorial 
Extensões obrigatórias
•	postgis 
•	vector 
•	uuid-ossp ou UUID nativo 
•	pg_trgm 
•	pgcrypto 
•	auditoria em nível de aplicação + logs de banco 
A modelagem v1 também propõe schemas separados app, gov e ai, isolando inclusive o microsserviço Python das tabelas de negócio 
Na v2 eu manteria a mesma filosofia, com nomes ajustados para nosso desenho:
•	core 
•	ai 
•	geo 
•	gov 
ou, se quiser manter aderência à documentação anterior:
•	app 
•	ai 
•	gov 
Decisão recomendada
Para manter continuidade com o material já existente, eu usaria:
•	app 
•	ai 
•	gov 
e adicionaria, se necessário:
•	support 
________________________________________
4.2 Estratégia multi-tenant
A modelagem base já é explícita: toda tabela de negócio com tenant_id, e o backend sempre filtrando por tenant corrente 
Regra de implementação
•	nenhum query handler sem contexto de tenant 
•	RLS pode entrar depois 
•	no MVP: enforcement na aplicação + testes automáticos 
•	em fase seguinte: Row Level Security em tabelas críticas 
________________________________________
4.3 Geoespacial
A modelagem v1 já define geom em imóveis e consultas de interseção com áreas protegidas via PostGIS 
V2
Separar:
•	geometria principal do imóvel 
•	geometria de RL 
•	geometria de APP 
•	camadas externas importadas 
•	resultados de sobreposição materializados 
Benefício
•	menos recomputação 
•	histórico de versões 
•	melhor performance 
________________________________________
4.4 Vetorial / RAG
A documentação já acertou ao propor pgvector em vez de serviço vetorial externo, simplificando backup e conformidade 
V2
•	chunks de base regulatória 
•	embeddings por fonte 
•	escopo global e escopo por tenant 
•	precedentes internos vetorizados 
•	versionamento de fonte 
•	marcação de vigência/revogação 
________________________________________
5. Storage de arquivos
A v1 foi muito clara: arquivos grandes jamais devem ir ao PostgreSQL, e o acesso deve ser feito por URL assinada temporária 
Recomendação v2
S3 ou Cloudflare R2
Tipos de arquivo
•	documentos do cliente 
•	matrículas 
•	CCIR 
•	CAR 
•	shapefiles 
•	fotos de campo 
•	áudios 
•	PDFs protocolados 
•	documentos gerados 
•	certificados A1 criptografados 
Regras
•	bucket privado 
•	sem URL pública permanente 
•	presigned URL curta 
•	versionamento ativo 
•	antivírus opcional na entrada 
•	checksum de integridade 
•	metadado sempre no banco 
________________________________________
6. Mensageria, eventos e tempo real
6.1 Fila
A v1 já definia corretamente a comunicação assíncrona entre núcleo transacional e motor de IA via fila 
V2
Padrão mínimo:
•	document.uploaded 
•	document.ocr.requested 
•	document.ocr.completed 
•	document.extraction.completed 
•	process.diagnosis.ready 
•	workflow.plan.requested 
•	workflow.plan.created 
•	draft.generation.requested 
•	email.classification.requested 
•	deadline.alert.triggered 
6.2 WebSocket / realtime
•	atualização de Kanban 
•	status de processamento 
•	progresso de upload 
•	alertas de pendência 
•	eventos do portal do cliente 
Tecnologia
•	FastAPI WebSocket para simples 
•	ou serviço separado com Redis pub/sub 
•	se quiser menor atrito inicial: websocket no próprio backend + Redis 
________________________________________
7. Pipeline documental
A v1 já estabelece algo essencial: OCR clássico antes do LLM, porque mandar matrícula ruim direto para o modelo gera alucinação e desperdício 
Pipeline v2
1.	upload do arquivo 
2.	validação e checksum 
3.	persistência do metadado 
4.	upload no storage 
5.	criação de job de OCR 
6.	pré-processamento 
o	deskew 
o	contraste 
o	limpeza 
o	separação de páginas 
7.	OCR clássico 
o	Tesseract para baixo custo 
o	Google Vision / Textract para casos críticos 
8.	normalização textual 
9.	classificação do documento 
10.	extração estruturada 
11.	score de confiança 
12.	revisão humana se confiança baixa 
13.	persistência do texto bruto + texto limpo + JSON estruturado 
14.	eventos subsequentes para workflow 
Estratégia para melhorar OCR
Como você levantou esse risco, a arquitetura já precisa absorver isso:
•	pipeline híbrido 
•	fallback por criticidade 
•	correção humana alimenta dataset 
•	documentos problemáticos vão para fila de revisão 
•	documentos reprocessáveis com modelos melhores depois 
________________________________________
8. Arquitetura dos agentes
8.1 Agente Atendente
A v1 já o posiciona na entrada via WhatsApp e e-mail, gerando JSON estruturado para início do caso 
V2
Entrada:
•	WhatsApp 
•	e-mail 
•	formulário web 
•	portal cliente 
Saída:
•	lead qualificado 
•	tipo de demanda sugerido 
•	urgência 
•	dados faltantes 
•	criação opcional de pré-processo 
8.2 Agente Extrator
A v1 já descreve o papel dele em OCR + diagnóstico documental 
V2
Saída:
•	dados estruturados 
•	inconsistências 
•	score de confiança 
•	recomendação de revisão 
•	enriquecimento inicial do processo 
8.3 Agente Regulatório
A v1 já amarra esse agente ao RAG regulatório e precedentes internos 
V2
Saída:
•	fundamentação 
•	checklist 
•	normas correlatas 
•	precedentes similares 
•	risco jurídico-operacional 
8.4 Agente Orquestrador
A v1 já o define como montador de sequência operacional e tarefas com dependências 
V2
Saída:
•	plano sugerido 
•	tarefas 
•	ordem 
•	dependências 
•	responsáveis sugeridos 
•	SLA estimado 
8.5 Agente Redator
A v1 já o associa à geração de PRAD, memorial, ofício e resposta a pendência 
V2
Saída:
•	rascunhos DOCX 
•	sumário técnico 
•	resposta a notificação 
•	proposta 
•	contrato 
•	comunicação formal 
8.6 Agente Vigia
A v1 já o liga a leitura recorrente de e-mail e criação de alertas/tarefas 
V2
Monitora:
•	caixas de e-mail 
•	tarefas vencendo 
•	condicionantes 
•	contratos para assinatura 
•	cobranças 
•	sincronizações falhadas 
________________________________________
9. Integrações externas
A arquitetura v1 foi muito lúcida aqui: a integração governamental precisa seguir três pilares — certificado A1, data brokers e human-in-the-loop — porque automação pura em portal governamental é frágil e às vezes inviável 
9.1 Estratégia oficial v2
Pilar 1 — APIs privadas / data brokers
Prioridade quando existirem.
Exemplos já mencionados na documentação:
•	Serpro / Dataprev 
•	BigDataCorp / Assertiva 
•	Agronow / Agrosmart 
•	MapBiomas API 
Pilar 2 — Certificado digital A1
Quando o órgão ou sistema suportar autenticação por certificado, usar esse caminho, com metadado no banco e segredo criptografado no storage/KMS, como já previsto na v1 
Pilar 3 — Human-in-the-loop
Quando não houver API viável nem integração robusta, o sistema cria tarefa operacional para o consultor baixar, subir ou revisar o material, e a IA retoma dali. A v1 tratou isso muito bem e isso deve permanecer como fallback oficial 
9.2 Integrações por tenant
Você já definiu uma estratégia ótima de custo:
•	cada tenant pode configurar sua própria chave de IA 
•	seu próprio provider de WhatsApp 
•	seu próprio e-mail transacional 
•	seu próprio storage/integrações, quando necessário 
Arquiteturalmente isso exige:
•	tabela de contas de integração por tenant 
•	secret manager 
•	healthcheck por integração 
•	limites por plano 
•	métricas de consumo por tenant 
________________________________________
10. Offline-first no app de campo
Esse é um dos pontos mais delicados do projeto.
Estratégia v2
O app de campo nasce com offline-first controlado.
Banco local
•	SQLite no dispositivo 
Dados locais
•	visitas 
•	formulários 
•	checklists 
•	fotos 
•	áudios 
•	pontos GPS 
•	rascunhos de observação 
Sincronização
•	fila local de alterações 
•	sync quando rede disponível 
•	retry automático 
•	resolução de conflitos simples no MVP 
Regra de conflito no MVP
•	metadado sensível: servidor prevalece 
•	notas/fotos/registros de campo: append-only 
•	conflitos relevantes: vão para fila de revisão 
O que não fazer
Não tentar resolver todos os conflitos com “inteligência” desde o início.
Tem que ser simples, previsível e auditável.
________________________________________
11. Segurança
A v1 já coloca padrão alto de segurança, com JWT RS256, TLS forte, criptografia de colunas sensíveis e proteção de certificado A1 
V2 — política mínima
•	JWT com access token curto 
•	refresh token rotativo 
•	cookie HttpOnly quando aplicável 
•	RBAC forte 
•	isolamento por tenant 
•	criptografia de CPF/CNPJ 
•	segredo fora do banco 
•	auditoria append-only 
•	hash de payload de IA 
•	rastreio de quem aprovou o quê 
•	rate limit 
•	proteção anti-abuso em uploads 
•	varredura de arquivo suspeito 
________________________________________
12. Observabilidade e auditoria
A v1 também já amarra muito bem a auditabilidade das decisões de IA: modelo, prompt, consumo e outputs precisam ser registrados 
Stack recomendada
•	logs estruturados JSON 
•	Sentry para erro 
•	Prometheus + Grafana para métricas 
•	OpenTelemetry para tracing 
•	painel de jobs 
•	painel de custo por tenant 
O que medir
•	latência da API 
•	tempo por job 
•	taxa de erro OCR 
•	taxa de revisão humana 
•	custo por agente 
•	custo por tenant 
•	falhas de integração 
•	backlog de filas 
•	taxa de conflito offline 
•	atraso médio por processo 
________________________________________
13. Ambientes e infraestrutura
13.1 Ambientes
•	dev 
•	staging 
•	production 
13.2 Containerização
•	Docker em tudo 
13.3 Orquestração
MVP
•	Docker Compose ou ECS/App Runner/Fly/Render bem organizados 
Escala
•	Kubernetes depois 
13.4 Infra recomendada
•	API FastAPI 
•	worker pool 
•	Redis 
•	PostgreSQL gerenciado 
•	bucket S3/R2 
•	CDN para frontend 
•	serviço de e-mail 
•	serviço de logs/monitoramento 
________________________________________
14. Fluxos principais
14.1 Upload e análise documental
1.	usuário envia documento 
2.	API registra documento 
3.	arquivo vai para storage 
4.	API cria job 
5.	worker executa OCR 
6.	worker executa extração 
7.	resultado salva no banco 
8.	se confiança baixa, cria revisão 
9.	processo recebe diagnóstico 
10.	frontend atualiza em tempo real 
14.2 Intake de WhatsApp
1.	mensagem entra pelo provider 
2.	webhook chega na API 
3.	evento é salvo 
4.	job do atendente é criado 
5.	IA estrutura os dados 
6.	API cria lead/pré-processo 
7.	humano revisa se necessário 
14.3 Geração de workflow
1.	processo recebe diagnóstico 
2.	agente regulatório consulta base 
3.	orquestrador monta plano 
4.	API cria tarefas 
5.	responsáveis são notificados 
14.4 Campo offline
1.	técnico baixa contexto antes da visita 
2.	coleta offline no app 
3.	dados ficam no SQLite 
4.	ao voltar conexão, sincroniza 
5.	conflitos simples são tratados 
6.	documentos e registros entram no processo 
________________________________________
15. Decisões arquiteturais centrais
Manter
Da v1, eu manteria firmemente:
•	separação entre API transacional e motor de IA 
•	Postgres + PostGIS + pgvector 
•	fila assíncrona 
•	storage externo com URL assinada 
•	seis agentes especializados 
•	estratégia de integração governamental em três pilares 
Alterar
Eu alteraria da v1:
•	PHP/Laravel sai 
•	FastAPI assume o backend core 
•	workers Python passam a atender tanto IA quanto automações 
•	fila deixa de ser “Laravel Queue” e vira fila neutra Python-first 
•	módulos passam a ser desenhados já pensando em white-label por tenant 
________________________________________
16. Riscos técnicos e mitigação embutida na arquitetura
Dependência de APIs governamentais
Mitigação:
•	priorizar APIs privadas 
•	fallback A1 
•	fallback human-in-the-loop 
OCR ruim
Mitigação:
•	pipeline híbrido 
•	pré-processamento 
•	score de confiança 
•	fila de revisão 
•	reprocessamento 
Offline complexo
Mitigação:
•	escopo MVP simples 
•	sync assíncrono 
•	regra de conflito limitada 
•	append-only em campo 
Custo de IA
Mitigação:
•	chave por tenant 
•	auditoria de tokens 
•	modelos baratos para triagem 
•	modelos premium só onde faz sentido 
•	cobrança por uso 
Crescimento de complexidade
Mitigação:
•	arquitetura modular 
•	eventos explícitos 
•	separação de contextos 
•	feature flags por tenant 
________________________________________
17. Recomendação final
Minha recomendação oficial para a Arquitetura Técnica Detalhada v2 é:
•	React + Vite para painel 
•	Next.js para portal cliente 
•	React Native para campo 
•	FastAPI como backend core 
•	Python workers para processamento assíncrono 
•	SDKs nativos para IA 
•	Redis para fila e cache 
•	PostgreSQL + PostGIS + pgvector 
•	S3/R2 para arquivos 
•	auditoria forte 
•	multi-tenant 
•	offline-first controlado 
•	fallback operacional quando integração falhar 
Esse desenho continua fiel aos fundamentos da documentação original — microsserviços desacoplados, fila assíncrona, RAG com pgvector, storage externo, agentes especializados e estratégia realista de integração com governo — mas agora alinhado com a decisão certa de stack: Python + FastAPI no centro da operação.
