<!-- Versionado em docs/auditoria/ como FONTE da triagem em TRIAGEM_AUDITORIA_CODEX.md.
Origem: auditoria_codex_regente.md (raiz do repositório), idêntico ao AuditoriaCodexRegente.docx.
SHA auditado: 11ab1afcd133042f985918ff855fc029684b3fb0. Conteúdo não editado — só este cabeçalho
de procedência foi acrescentado no versionamento. Não editar: nova auditoria = arquivo novo. -->

AUD-01 — Inventário e arquitetura real
Resumo
•	Raiz: C:\Users\Administrador\Desktop\Amigao_do_Meio_Ambiente
•	Branch: main
•	SHA obrigatório: 11ab1afcd133042f985918ff855fc029684b3fb0
•	Origin: https://github.com/prosperidade/amigao.git
•	Worktree: limpo; main...origin/main
•	Linguagens: Python, TypeScript/TSX, JavaScript/JSX, YAML, Markdown.
•	Lockfiles: frontend/package-lock.json, client-portal/package-lock.json, mobile/package-lock.json.
•	Python: 513 arquivos no repositório; 231 em app/.
•	TypeScript: 161 arquivos.
•	Migrations Alembic: 73.
•	Modelos ORM: 38 tabelas.
•	Endpoints HTTP/WS identificados por decorators: 199.
•	Routers declarados: 33.
•	Testes Python: 172 arquivos; frontend: 23 arquivos.
[CONFIRMADO NO CÓDIGO] Evidência: git rev-parse, git status, app/, client-portal/, frontend/, mobile/, alembic/.
Mapa de componentes
Clientes
├── frontend/       React + Vite: painel interno
├── client-portal/  Next.js: portal de cliente/tenant
└── mobile/         Expo React Native: operação de campo

Backend
└── app.main:app
    ├── FastAPI
    ├── routers REST /api/v1/*
    ├── WebSocket /ws e /api/v1/ws
    ├── SQLAlchemy + PostgreSQL/PostGIS/pgvector
    ├── Redis + Celery
    ├── MinIO/S3/Cloudflare R2
    ├── LiteLLM: OpenAI/Gemini/Anthropic/DeepSeek
    ├── SMTP/Resend
    └── Evolution API para WhatsApp

Background
└── app.core.celery_app:celery_app
    ├── workers de OCR, IA, áudio, PDF
    ├── ingestão/indexação RAG
    ├── legislação
    ├── notificações/webhooks
    └── Celery Beat
[CONFIRMADO NO CÓDIGO] Evidência: [app/main.py (line 109)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/main.py:109), [Dockerfile (line 39)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/Dockerfile:39), package.json dos três clientes.
Entrypoints e roteamento
Componente	Entrypoint	Dependências	Dados	Riscos
API	uvicorn app.main:app	FastAPI, config, PostgreSQL, Redis, storage	Todos os domínios	/health não verifica dependências
Worker	celery -A app.core.celery_app worker	Redis, PostgreSQL, storage, providers externos	Jobs, AIJob, documentos	Falha do broker impede processamento assíncrono
Painel interno	frontend/src/main.tsx	Vite, React Router, API HTTP	Clientes, processos, tarefas	Deploy não aparece no render.yaml
Portal cliente	Next.js App Router	API backend, Axios, Zustand	Processos e timeline	Depende de URL/API corretamente configurada
Mobile	Expo Router	API, SecureStore, SQLite local	Processos, tarefas, evidências	Sincronização eventual e fila local
[CONFIRMADO NO CÓDIGO] Evidência: [frontend/src/main.tsx (line 6)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/frontend/src/main.tsx:6), [client-portal/package.json](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/client-portal/package.json), [mobile/package.json](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/mobile/package.json).
Routers
Módulo	Montagem	Endpoints
auth.py	/api/v1/auth	8
clients.py	/api/v1/clients	11
processes.py	/api/v1/processes	32
documents.py	/api/v1/documents	9
properties.py	/api/v1/properties	15
intake.py	/api/v1/intake	18
checklists.py	/api/v1/processes	4
workflows.py	/api/v1/workflows e /api/v1/processes	4
regulatory.py	/api/v1/processes e /api/v1/properties	10
rotas.py	/api/v1/processes e /api/v1/rotas	3
acoes.py	/api/v1/processes	5
contracts.py	/api/v1/contracts	9
proposals.py	/api/v1/proposals	10
ai.py	/api/v1/ai	7
agents.py	/api/v1/agents	7
Demais routers	dashboard, legislação, RAG, messaging, tasks etc.	47
[CONFIRMADO NO CÓDIGO] Evidência: [app/main.py (line 165)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/main.py:165), arquivos em [app/api/v1](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1).
Banco, ORM e transações
•	PostgreSQL como banco principal.
•	PostGIS habilitado por migration.
•	pgvector habilitado por migration.
•	SQLAlchemy síncrono com pool 10, max_overflow=5, pool_pre_ping=True.
•	statement_timeout=30000.
•	Alembic importa todos os modelos via [app/models/__init__.py (line 1)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/__init__.py:1).
•	Existem queries SQL textuais para embeddings e vetores.
•	Não há arquivos .sql de schema; o schema está em modelos e migrations.
•	Repositórios explícitos: client_repo, document_repo, matricula_repo, process_repo, property_repo, staging_repo, task_repo.
[CONFIRMADO NO CÓDIGO] Evidência: [app/db/session.py (line 6)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/db/session.py:6), [alembic/env.py (line 9)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/alembic/env.py:9), migration f9d2e8c1a4b3.
Domínios persistidos
tenants, users, clients, processes, properties, documents, matriculas, tasks, acoes, checklists, rotas, regulatory_diagnoses, regulatory_issues, proposals, contracts, credentials, communication_threads, messages, audit_logs, ai_jobs, prompt_templates, knowledge_catalog, legislation_documents, legislation_alerts, stage_outputs, extracted_field_staging, entre outros.
[CONFIRMADO NO CÓDIGO] Evidência: 38 declarações __tablename__ em [app/models](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models).
Autenticação, autorização e tenant
•	JWT HS256 com sub, tenant_id, profile e opcionalmente client_id.
•	Senhas com bcrypt.
•	Contextos:
o	usuário interno;
o	portal de cliente;
o	tenant;
o	cliente vinculado.
•	get_access_context() valida coerência entre usuário, tenant, perfil e cliente.
•	Há dependências específicas para usuário interno.
•	O middleware extrai tenant do JWT ou de X-Tenant-Id para logging; a autorização real usa o usuário autenticado.
[CONFIRMADO NO CÓDIGO] Evidência: [app/api/deps.py (line 22)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/deps.py:22), [app/core/security.py (line 26)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/security.py:26).
[RISCO ESTRUTURAL] O header X-Tenant-Id participa do contexto de observabilidade antes da autorização; qualquer uso posterior desse valor fora das dependências autenticadas merece revisão.
Storage, uploads e arquivos
•	Abstração única em StorageService.
•	Compatível com MinIO, S3 e Cloudflare R2.
•	Bucket fixo: regente-docs.
•	Upload primário por presigned URL.
•	Upload direto de bytes para PDFs gerados e documentos assinados.
•	Download por presigned URL.
•	Chaves incluem tenant_id e process_id ou draft_id.
•	Documentos possuem checksum SHA-256.
•	PDF gerado por app/workers/pdf_generator.py.
•	OCR e conversão de áudio dependem de ffmpeg, pypdfium2 e providers externos.
[CONFIRMADO NO CÓDIGO] Evidência: [app/services/storage.py (line 45)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/storage.py:45), [app/api/v1/documents.py (line 130)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:130).
Filas, jobs, schedulers e webhooks
•	Celery usa Redis como broker e backend.
•	autodiscover_tasks(["app.workers"]).
•	12 módulos de workers.
•	Celery Beat agenda:
o	monitoramento DOU/DOE;
o	agências;
o	vigia de prazos;
o	acompanhamento de processos;
o	expiração de drafts.
•	Jobs assíncronos para:
o	classificação;
o	extração;
o	OCR;
o	áudio;
o	agentes;
o	indexação RAG;
o	PDF;
o	e-mail;
o	webhooks.
[CONFIRMADO NO CÓDIGO] Evidência: [app/core/celery_app.py (line 14)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/celery_app.py:14), [app/core/celery_app.py (line 56)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/celery_app.py:56).
[RISCO ESTRUTURAL] O render.yaml usa Beat embarcado com worker --pool=solo -B; múltiplas instâncias podem duplicar tarefas agendadas.
Agentes, prompts e IA
Agentes registrados:
•	AtendimentoAgent
•	AcompanhamentoAgent
•	AuditorImovelAgent
•	DiagnosticoAgent
•	ExtratorAgent
•	FinanceiroAgent
•	LegislacaoAgent
•	MarketingAgent
•	OrcamentoAgent
•	RedatorAgent
•	VigiaAgent
•	Orquestração determinística em CHAINS e INTENT_TO_CHAIN.
•	Prompts primários vêm de prompt_templates no banco.
•	Fallbacks estão implementados nos próprios agentes.
•	Skills são carregadas de app/skills/**/SKILL.md.
•	Gateway central: app/core/ai_gateway.py.
•	Providers:
o	OpenAI;
o	Gemini;
o	Anthropic;
o	DeepSeek via prefixo LiteLLM.
•	Fallback global conforme chaves/modelos disponíveis.
•	Limites por job, hora e mês por tenant.
•	Registro em ai_jobs.
[CONFIRMADO NO CÓDIGO] Evidência: [app/agents/base.py (line 69)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/agents/base.py:69), [app/agents/orchestrator.py (line 23)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/agents/orchestrator.py:23), [app/core/ai_gateway.py (line 196)](C:/Users/Administrador/Desktop/Amigao/Desktop/Amigao_do_Meio_Ambiente/app/core/ai_gateway.py:196), migration 024fe3f5dbeb.
[RISCO ESTRUTURAL] Há prompts persistidos, fallbacks em código e skills externas ao Python; divergência entre esses três níveis pode alterar comportamento sem mudança do executor.
RAG e ingestão
Fluxo identificado:
documento/texto
  → extração
  → chunking estrutural
  → embedding
  → knowledge_catalog.embedding
  → busca cosine via pgvector
  → contexto no prompt do agente
•	Tabela: knowledge_catalog.
•	Coluna: vector(768).
•	Índice: IVFFlat com distância cosseno.
•	Providers de embedding:
o	OpenAI text-embedding-3-small, reduzido para 768 dimensões;
o	Gemini gemini-embedding-001.
•	O modelo do embedding é persistido por chunk.
•	A busca filtra pelo mesmo embedding_model.
•	Reindexação ocorre via Celery.
•	Legislação possui ingestão por scripts e crawler.
[CONFIRMADO NO CÓDIGO] Evidência: [app/services/knowledge_catalog.py (line 303)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:303), [app/models/knowledge_catalog.py (line 125)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/knowledge_catalog.py:125), migration f9d2e8c1a4b3.
[RISCO ESTRUTURAL] Trocar o provider de embedding exige reindexação completa; caso contrário, a busca opera em espaços vetoriais incompatíveis.
Observabilidade e health
•	Logging estruturado.
•	request_id.
•	traceparent e contexto de tracing.
•	Métricas HTTP, Celery, uploads e IA.
•	Alertas operacionais para latência, erros HTTP e falhas de tasks.
•	Headers de segurança OWASP.
•	CORS configurável.
•	Endpoints:
o	/
o	/health
o	/metrics
[CONFIRMADO NO CÓDIGO] Evidência: [app/api/middleware.py (line 54)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/middleware.py:54), [app/main.py (line 211)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/main.py:211).
[RISCO ESTRUTURAL] /health retorna {"status": "ok"} sem consultar banco, Redis, storage ou Celery. Não existe readiness real verificável pelo endpoint.
Inicialização e falhas de dependências
Dependência	Comportamento observado
Configuração inválida	Falha no import de Settings; API não inicia
SECRET_KEY ausente/curta	Falha de validação no startup
Chave Fernet ausente/inválida	Falha de validação no startup
Configuração de produção insegura	Falha de validação no startup
PostgreSQL indisponível	Warm-up registra warning; API continua iniciando; requests dependentes falham depois
Redis no WebSocket indisponível	Warning no startup; aplicação continua; realtime fica indisponível
Redis do Celery indisponível	Worker depende da conexão; tasks ficam indisponíveis ou aguardam retry
Storage indisponível	Construção do cliente não valida bucket; operações reais falham
IA desabilitada/sem chave	Gateway não deve chamar provider; caminhos de IA dependem de fallback ou retorno degradado
SMTP ausente	Em produção, configuração é rejeitada; fora de produção, envio retorna falha controlada
Resend ausente em produção	Configuração é rejeitada
WhatsApp sem Evolution configurada	Provider retorna erro de configuração
pgvector ausente	Migration falha; busca RAG não funciona
Provider de embedding indisponível	Indexação/busca falham com erro de embedding
[CONFIRMADO NO CÓDIGO] Evidência: [app/core/config.py (line 483)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/config.py:483), [app/main.py (line 55)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/main.py:55), [app/main.py (line 92)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/main.py:92).
[PROVÁVEL — DEPENDE DE RUNTIME] O impacto final de indisponibilidade de Redis, providers e storage depende de timeouts, retries e estado do processo Celery.
Inventário de arquivos e símbolos principais
Execução
•	[app/main.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/main.py): app, lifespan, health_check, metrics.
•	[app/core/config.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/config.py): Settings, get_settings.
•	[app/core/celery_app.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/celery_app.py): celery_app, sinais e beat_schedule.
•	[Dockerfile](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/Dockerfile): imagem da API/worker.
API
•	[app/api/deps.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/deps.py): get_db, get_current_user, get_access_context.
•	[app/api/middleware.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/middleware.py): middlewares de segurança, contexto, tracing e métricas.
•	[app/api/v1](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1): routers de auth, clientes, processos, documentos, intake, workflow, regulatório, propostas, contratos, IA e legislação.
•	[app/api/websockets.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/websockets.py): WebSocket e Redis pub/sub.
Domínio e persistência
•	[app/models](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models): 38 tabelas.
•	[app/repositories](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/repositories): persistência especializada.
•	[app/services](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services): regras de negócio, extração, documentos, contratos, legislação, RAG e storage.
•	[alembic/versions](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/alembic/versions): 73 migrations.
Clientes
•	[frontend/src/App.tsx](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/frontend/src/App.tsx): roteamento interno.
•	[client-portal/src/app](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/client-portal/src/app): páginas Next.js.
•	[mobile/app](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/mobile/app): rotas Expo.
•	[mobile/src/services/SyncService.ts](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/mobile/src/services/SyncService.ts): sincronização local/API.
•	[mobile/src/services/EvidenceService.ts](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/mobile/src/services/EvidenceService.ts): upload de evidências.
Testes e CI
•	[tests/api](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/tests/api): 47 arquivos.
•	[tests/services](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/tests/services): 67 arquivos.
•	[tests/agents](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/tests/agents): 25 arquivos.
•	[tests/workers](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/tests/workers): 3 arquivos.
•	[.github/workflows/ci.yml](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/.github/workflows/ci.yml): lint, mypy advisory, testes PostgreSQL, migrations, frontend, portal e mobile.
[CONFIRMADO NO CÓDIGO] Contagens obtidas por listagem e busca estática; nenhum teste foi executado.
Acoplamentos relevantes
[RISCO ESTRUTURAL]
1.	API, workers e Alembic importam a mesma configuração e o mesmo registro de modelos.
2.	Processos, documentos, propriedades, clientes, matrículas e diagnóstico estão fortemente acoplados por tenant_id e chaves estrangeiras.
3.	Upload de documento dispara tasks de notificação, OCR, classificação e extração.
4.	AIJob é dependência transversal de agentes, workers, orçamento e auditoria.
5.	Agentes dependem simultaneamente de prompts persistidos, fallbacks em código, skills Markdown e modelos externos.
6.	RAG depende de PostgreSQL + pgvector + provider de embedding + corpus consistente.
7.	Contratos/propostas dependem de storage para PDF e SMTP/serviço externo para envio.
8.	WebSocket depende de Redis, mas a API HTTP não depende dele para iniciar.
9.	Mobile mantém SQLite local e fila de sincronização; consistência depende de reenvio e ordenação.
10.	O frontend Vite e o mobile não têm serviço correspondente declarado no render.yaml.
Pontos para aprofundamento
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Estado real do banco e versão Alembic aplicada em produção.
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Quantidade real de tenants, documentos, embeddings e jobs.
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Configuração efetiva de secrets e providers no ambiente de deploy.
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Se o bucket R2/MinIO existe e possui permissões corretas.
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Se Redis suporta simultaneamente Celery, backend de resultados e WebSocket.
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Semântica real de retries e redelivery sob falha de worker.
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Deploy efetivo do frontend Vite e do mobile.
•	[NÃO VERIFICÁVEL ESTATICAMENTE] Existência de readiness externo no provedor de infraestrutura.
Limitações
•	Auditoria exclusivamente estática.
•	Não foram executados testes, imports, migrações, servidores, workers ou builds.
•	Não foram consultados bancos, Redis, storage, APIs externas ou provedores de IA.
•	READMEs, ADRs, handoffs, comentários e documentação narrativa não foram usados como prova de comportamento.
•	Linhas são referências aproximadas baseadas no estado fixado pelo SHA acima.



AUD-02 — Banco: modelos, migrations e integridade
Escopo e estado
•	SHA auditado: 11ab1afcd133042f985918ff855fc029684b3fb0
•	Worktree limpo.
•	Auditoria estática, somente leitura.
•	Não houve conexão ao banco, execução de SQL ou migrations.
•	Não foi localizado artefato explícito do AUD-01; portanto, não foi possível confirmar o SHA externo de referência.
Grafo de migrations
•	73 arquivos de migration.
•	Raiz: a8905cb51eb1.
•	Head atual: d3b8a1f0c94e.
•	Branch labels: nenhuma.
•	Merge explícito:
d2c3e4f5a6b8
├── e3d4f5g6a7b8
└── e6f7a8b9c0d1
    └── c0d1e2f3a4b5
•	O merge c0d1e2f3a4b5 também cria credentials.
•	Não há múltiplas heads no grafo final após considerar o merge.
•	Não foram encontrados down_revision apontando para revision inexistente.
•	O head atual é a migration de 2026-08-07 que adiciona tombstones em rota_passos.
Problemas no grafo/downgrade
d1a4b7e93c60_rota_passo_proveniencia.py adiciona as colunas origem_issue_id e origem_acao_id, mas não cria as FKs no upgrade; o downgrade tenta removê-las.
Evidência: [d1a4b7e93c60_rota_passo_proveniencia.py (line 37)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/alembic/versions/d1a4b7e93c60_rota_passo_proveniencia.py:37) e [d1a4b7e93c60_rota_passo_proveniencia.py (line 52)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/alembic/versions/d1a4b7e93c60_rota_passo_proveniencia.py:52).
Matriz de tabelas
Tabela	Finalidade inferida	PK/FKs principais	Tenant	Constraints/índices	Versionamento	Risco principal
tenants	Organizações	id	própria	índice id, name	timestamps	name não é unique
users	Usuários internos	tenant_id → tenants	obrigatório	email unique global	timestamps	usuários de tenants diferentes não podem compartilhar email
clients	Clientes	tenant_id → tenants	obrigatório	índices por tenant/CPF; CPF não unique	soft delete	duplicidade de CPF/CNPJ aceita
properties	Imóveis	client_id, tenant_id	obrigatório	índices tenant/client	timestamps	registry_number, CAR, CCIR e NIRF sem unique/check
processes	Casos/processos	client, property, responsible user	obrigatório	índices tenant/status/due date	soft delete	FK não garante que client/property pertençam ao mesmo tenant
documents	Arquivos e extrações	process, client, property, draft, user	obrigatório	storage_key unique; índices OCR/tipo	version_number, soft delete	aliases size/file_size_bytes e s3_key/storage_key permitem divergência
matriculas	Matrículas e cadeia histórica	property, self superseded_by_id	obrigatório	índice tenant/property	vigencia, desativação, lineage	número da matrícula nullable; cadeia não impõe consistência
regulatory_diagnoses	Diagnóstico versionado	process, validator	obrigatório	unique (process_id, version)	explícito	tenant não participa da chave lógica
regulatory_issues	Achados regulatórios	property, document, catálogo	obrigatório	índices por tenant/property/document/type	status e datas	documento/propriedade podem ser de outro tenant
process_issue_decisions	Decisão humana sobre achado	process, issue, user	obrigatório	unique (process_id, issue_id)	timestamps	não há FK composta garantindo mesmo tenant
regulatory_issue_catalog	Catálogo de achados	PK textual codigo_alerta	global	índices de família/factibilidade	timestamps	flags e enums podem divergir do issue persistido
acoes	Ações corretivas	process, tenant, users	obrigatório	unique (tenant_id, dedupe_key)	timestamps	dedupe_key nullable; múltiplas ações sem chave lógica
ai_jobs	Execuções de IA	tenant, user	obrigatório	índices status/type/agent	timestamps de execução	relação genérica sem FK
audit_logs	Auditoria	tenant, user	obrigatório	índices entity/action/time	hash opcional	entidade auditada genérica e hash não obrigatório
intake_drafts	Rascunhos de intake	tenant, user, process	obrigatório	índice state/expiry	timestamps/expiry	form_data livre, sem schema DB
intake_classification_feedback	Correções da classificação	process, draft, AI job, user	obrigatório	índices básicos	corrected_at	não há unique para impedir feedback duplicado
extracted_field_staging	Campos extraídos pendentes	process, document, AI job, user	obrigatório	índices status/process/document	decisão/consolidação	identidade lógica (process, field, document) não é unique
checklist_templates	Templates globais/tenant	tenant nullable	opcional	índice tenant/demand	timestamps	nomes duplicados e templates concorrentes aceitos
process_checklists	Checklist por processo	process, template	obrigatório	unique process	timestamps	items JSON é fonte operacional sem constraint
macroetapa_checklists	Estado por macroetapa	process, tenant	obrigatório	unique (process_id, macroetapa)	estado atual	actions JSON requer flag_modified
workflow_templates	Templates de workflow	tenant nullable	opcional	índice demand/tenant	timestamps	steps JSON sem validação estrutural
tasks	Tarefas	process/property/document/user	obrigatório	tabela associativa de dependências	timestamps/status	tabela de dependências precisa validar tenant via entidades
communication_threads	Threads de comunicação	process/client/tenant	obrigatório	índices process/client	timestamps	process e client podem ser de tenants diferentes
messages	Mensagens	thread, sender	indireto	índice thread	timestamp	tenant não está na própria linha
credentials	Credenciais de portais	client, tenant	obrigatório	apenas índices simples	soft delete	nenhuma unique (tenant, client, portal)
proposals	Propostas comerciais	process/client/rota/self/user	obrigatório	índices básicos	version_number, previous_version_id	versão não possui unique por entidade
contracts	Contratos	proposal/process/client/template/user	obrigatório	índices básicos	timestamps de assinatura	estado de assinatura não possui check
contract_templates	Modelos de contrato	tenant nullable	opcional	índice demand/tenant	timestamps	nomes duplicados
rotas	Rota regulatória	process, AI job, user	obrigatório	unique process/tenant	status/validação	demand_type é string e não enum SQL
rota_versoes	Snapshot histórico de rota	rota, user	obrigatório	unique (rota_id, versao)	explícito	cascade apaga todo o histórico ao apagar rota
rota_passos	Passos da rota	rota, issue, ação, user	obrigatório	unique lógico com soft delete	tombstone	downgrade apaga dados tombstoned
stage_outputs	Saídas de agentes	process, users	obrigatório	índice process/macroetapa	timestamps	content e content_data podem divergir
prompt_templates	Prompts versionados	tenant nullable	opcional	unique (slug, version, tenant)	version, active	regra de “apenas uma versão ativa” não existe
knowledge_catalog	Chunks RAG	tenant nullable	opcional	content_hash unique global	soft delete	chunks globais e tenantizados compartilham dedupe global
legislation_documents	Normas/documentos legais	tenant nullable, self successor	opcional	poucos índices	vigência/revogação	content_hash, identificador e vigência não formam chave histórica
legislation_alerts	Alertas de legislação	legislação/tenant conforme modelo	variável	índices específicos	estado atual	enum/status implementado como string em partes
pre_cadastros	Leads pré-conversão	sem tenant operacional	não aplicável	índices UTM/data	timestamps	sem dedupe por email/telefone
process_decisions	Decisões históricas do processo	process, self supersession	indireto	sem chave lógica forte	histórico/self-FK	atualizações podem substituir decisão sem trilha própria
Achados
ID	Severidade	Estado	Arquivo/classe/tabela	Migration/linha	Evidência e cenário inválido	Impacto	Teste	Recomendação	Aceite
AUD-02-001	P1	Aberto	RotaPasso / rota_passos	d1a4b7e93c60:37,52	upgrade cria origem_issue_id/origem_acao_id, mas downgrade tenta remover FKs nunca criadas	downgrade pode falhar	Revisar upgrade/downgrade em ambiente isolado com metadata, sem dados reais	Criar explicitamente as duas FKs ou remover os drop_constraint	Obrigatório antes de considerar downgrade confiável
AUD-02-002	P1	Aberto	RotaPasso / rota_passos	d3b8a1f0c94e:47-55	downgrade executa DELETE FROM rota_passos WHERE deleted_at IS NOT NULL	perda irreversível do histórico de remoção	Teste de downgrade com passo tombstoned e verificação de preservação	Não apagar dados; manter migration aditiva ou exigir procedimento de retenção explícito	Aceite arquitetural explícito para perda, caso contrário corrigir
AUD-02-003	P1	Aberto	múltiplas tabelas tenantizadas	process.py:99-102	processes.tenant_id, client_id e property_id são FKs independentes	schema aceita processo do tenant A apontando para cliente/imóvel do tenant B	Inserir combinações cross-tenant em schema isolado usando role não-owner	FKs compostas (tenant_id,id) ou validação DB equivalente	Teste cross-tenant deve falhar no banco
AUD-02-004	P1	Aberto	AIJob, AuditLog	ai_job.py:54-55; audit_log.py:16-17	entity_type + entity_id não tem FK	job/auditoria pode apontar para entidade inexistente ou de outro tenant	Inserir entity_id inexistente e cross-tenant	Substituir por FKs específicas/tabelas de associação ou constraint de integridade	Aceitar genericidade somente com controle DB verificável
AUD-02-005	P2	Aberto	Matricula	matricula.py:48-67	número, cartório e área são nullable	registro histórico sem número de matrícula ou área é aceito	Caso com numero_matricula=NULL e vigencia='vigente'	Definir campos mínimos por estado e checks de vigência	Regras devem estar no schema ou aplicação + teste
AUD-02-006	P2	Aberto	Property, RegulatoryIssue	property.py:12+; regulatory.py:314+	properties.regulatory_issues JSON coexiste com regulatory_issues normalizada	JSON pode dizer “resolvido” enquanto linha normalizada permanece aberta	Criar divergência entre JSON e tabela normalizada	Escolher fonte única; deixar JSON somente como cache derivado	Documentar e testar reconciliação
AUD-02-007	P2	Aberto	JSON/PortableJSON	macroetapa.py:384; rota.py:248,302; proposal.py:47,56	vários JSON não usam MutableDict/MutableList; o próprio código exige flag_modified	obj.items.append(...) pode não gerar UPDATE	Teste por mutação in-place e inspeção da sessão/flush	Usar tipos mutáveis ou impor cópia + flag_modified em todos os caminhos	Cobertura deve provar persistência
AUD-02-008	P2	Aberto	Credential	credential.py:47; migration c0d1e2f3a4b5:34	PortalType existe em Python, mas coluna é String(50) e API aceita str	"portal": "qualquer_valor" é aceito	POST/insert com portal fora do catálogo	Enum DB ou check constraint sincronizado com API	Enum deve ter uma fonte de verdade
AUD-02-009	P2	Aberto	credentials	c0d1e2f3a4b5:29-48	não há unique lógico por cliente/portal	duas credenciais ativas para o mesmo cliente e portal	Inserir duplicatas (tenant,client,portal)	Unique parcial considerando deleted_at IS NULL	Duplicata deve falhar ou ter regra explícita
AUD-02-010	P2	Aberto	audit_logs	audit_log.py:28-31; ca481d367022:23-45	hash e hash anterior são nullable, sem constraint de cadeia	evento sem integridade criptográfica é aceito como auditoria	Criar log com hashes nulos ou cadeia quebrada	NOT NULL após saneamento, trigger/serviço transacional e verificação de sequência	Aceite depende de política de retenção
AUD-02-011	P2	Aberto	regulatory_issues	regulatory.py:343-352	família, flags e documentos cruzados são nullable	achado sem classificação ou sem semântica de origem é persistido	Criar issue sem familia, type e documentos_cruzados	Separar campos realmente opcionais dos obrigatórios por status	Definir matriz de estados válida
AUD-02-012	P2	Aberto	proposals	proposal.py:31-56	versionamento tem version_number, mas não há unique por entidade	duas propostas “versão 2” podem coexistir para o mesmo processo	Inserir duas versões iguais	Unique (tenant_id, process_id, version_number) ou chave equivalente	Definir política para propostas sem processo
AUD-02-013	P2	Aberto	documents	document.py:49-60	storage_key é unique, mas checksum_sha256 é nullable e não unique	mesmo arquivo físico pode ser armazenado várias vezes com chaves diferentes	Inserir duas linhas com mesmo checksum	Unique parcial por tenant/checksum, se deduplicação for requisito	Confirmar regra funcional
AUD-02-014	P2	Aberto	legislation_documents	legislation.py:68-123; d3e4f5a6b7c8:37-55	vigência, revogação, identificador e hash não formam identidade histórica	mesma norma pode ser duplicada ou uma versão vigente pode coexistir sem regra	Inserir duplicatas de identificador/hash	Chave lógica por fonte, identificador e vigência; checks de datas	Aceitar duplicidade apenas se explicitamente versionada
AUD-02-015	P2	Aberto	demandtype/taskstatus	e6f7a8b9c0d1:43-79; f2a1c4b6d8e9:26-72	downgrades fazem mapeamentos com perda sem preservar valor original	cancelada → review e novas demandas → nao_identificado perdem semântica	Teste round-trip upgrade/downgrade com todos os valores	Migrations irreversíveis devem ser marcadas e bloquear downgrade automático	Aceite formal do produto
AUD-02-016	P2	Aberto	documents, proposals, stage_outputs	modelos correspondentes	dados derivados e aliases coexistem (size/file_size_bytes, content/content_data, s3_key/storage_key)	atualizações parciais deixam fontes divergentes	Atualizar apenas um campo e consultar consumidores distintos	Definir fonte de verdade e remover aliases ou sincronizar em DB	Teste de round-trip API/modelo
Conclusão
O schema possui PKs, FKs básicas e uma única head final, mas a integridade multi-tenant é principalmente uma convenção da aplicação, não uma propriedade do banco. Os riscos mais importantes são:
1.	downgrade inválido em d1a4b7e93c60;
2.	downgrade destrutivo em d3b8a1f0c94e;
3.	relações cross-tenant aceitas pelo schema;
4.	referências genéricas sem FK;
5.	versionamento/histórico parcialmente implementado;
6.	múltiplas fontes para dados derivados e JSON mutável sem rastreamento uniforme.
Não considero o banco estruturalmente pronto para aceite sem correção ou aceite formal dos achados P1.
AUD-03 / AUD-04 — Auditoria read-only
Escopo auditado no SHA:
11ab1afcd133042f985918ff855fc029684b3fb0
Nenhuma aplicação, migration, teste ou serviço externo foi executado. As conclusões abaixo são baseadas apenas em leitura do código e migrations.
AUD-03 — Transações, concorrência e performance
Principais achados
Operação	Transação/commit	Efeitos externos	Retry/idempotência	Concorrência	Falha parcial
GET /processes/{id}/macroetapa/status	GET executa db.commit() ao criar checklist lazy em [processes.py (line 767)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:767)	Nenhum	Duas requisições podem disputar o backfill	Unique (process_id, macroetapa) existe, mas não há tratamento de IntegrityError	GET pode retornar 500 e deixar sessão em estado abortado
GET /proposals/generate-draft	Não commita, mas faz processamento pesado	Nenhum	Repetição recalcula tudo	Sem lock; leitura pode ocorrer enquanto rota/checklist muda	Resultado pode refletir estado intermediário
Criação/edição de caso, cliente, imóvel, tarefa, decisão, documento	Geralmente uma sessão por request, commit explícito	Auditoria e eventos	Sem optimistic locking	PUT/PATCH fazem read-modify-write sem versão	Última gravação vence; alterações anteriores desaparecem
Avanço de macroetapa/status	Gate é lido e depois estado é alterado em outra etapa da mesma sessão; [processes.py (line 985)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:985)	Cache Redis é invalidado após commit	Sem idempotency key	Dois avanços podem validar o mesmo estado e executar transições conflitantes	Auditoria pode registrar transição diferente do estado esperado
Checklist, rota e passos	Várias operações fazem check-then-insert/update	Eventos/cache após commit	Existem uniques para rota e dedupe de passos	Não há SELECT FOR UPDATE	Segunda requisição pode falhar por unique ou retornar 500
Proposta send, accept, reject	Commit separado por transição	E-mail em send, após commit, [proposals.py (line 368)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:368)	Retry HTTP pode reenviar e-mail; não há chave idempotente	Duas requisições leem draft/sent simultaneamente	Estado persistido e e-mail podem divergir
Nova versão de proposta	Calcula próxima versão em aplicação; não há unique (tenant_id, version_number)	Nenhum	Retry pode criar versões duplicadas	Duas renegociações podem usar o mesmo número	Cadeia de versões ambígua
Geração de contrato/PDF	Faz flush, renderização e upload MinIO antes do commit; [contracts.py (line 307)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:307)	MinIO	Repetição gera novos PDFs/chaves	Sem lock do contrato	PDF pode existir sem registro; conteúdo pode persistir sem PDF
Assinatura	Upload do PDF antes do commit; marca contrato e processo depois; [contracts.py (line 456)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:456)	Storage	Retry pode duplicar upload; sem idempotency key	Duas assinaturas podem concorrer e ambas fechar o processo	Assinatura persistida sem PDF assinado
Upload de documento	Commit do Document, depois enqueue Celery; [documents.py (line 181)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:181)	MinIO ocorre antes, Celery depois	Falha do enqueue deixa documento sem processamento	Dois confirm-upload para mesma chave são bloqueados apenas pelo unique storage_key, sem resposta idempotente	Documento persistido sem worker
Webhook WhatsApp	Mensagem, thread e mídia ficam na mesma transação; download HTTP e upload MinIO ocorrem antes do commit	Rede externa e storage dentro da transação; [messaging.py (line 119)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/messaging.py:119)	external_msg_id não é unique; retry do provider duplica mensagem	_get_or_create_thread é check-then-insert	Mídia pode estar no storage e mensagem ser rollbackada
Jobs OCR/áudio/LLM	Workers mantêm sessão aberta durante storage/LLM e só depois commit	LLM, storage e Redis dentro do ciclo operacional	Celery retry pode reprocessar o mesmo documento	Não há claim/lock atômico de item	Duas execuções podem sobrescrever OCR, AIJob e status
RAG/indexação	Indexação chama embeddings/rede antes do commit; [knowledge_indexer.py (line 27)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/workers/knowledge_indexer.py:27)	APIs de embedding	content_hash único ajuda, mas não há lock de processamento	Dois workers podem calcular o mesmo embedding	Custo externo sem persistência; transação longa
Monitor legislativo	Worker global processa crawlers e commita documentos/alertas	HTTP para órgãos externos	Não há lock distribuído de crawler	Dois disparos podem processar o mesmo documento	Documentos parcialmente ingeridos e alertas duplicados
Cenários concorrentes obrigatórios
1.	Avanço de etapa
o	Requisição A e B leem o processo em E2.
o	Ambas calculam can_advance=True.
o	A avança para E3 e commita.
o	B ainda possui objeto antigo e pode avançar novamente ou receber transição inválida.
o	Estado final possível: etapa incorreta, auditoria duplicada ou erro de transição.
2.	Proposta
o	A e B leem a proposta como sent.
o	A aceita; B rejeita.
o	Ambas passam na validação anterior ao commit.
o	Estado final depende da ordem dos commits: accepted ou rejected, com auditorias contraditórias.
3.	Webhook WhatsApp
o	O provider reenvia o mesmo external_msg_id.
o	A e B não encontram mensagem existente.
o	Ambas inserem Message.
o	Estado final: duas mensagens e possivelmente dois documentos de mídia.
4.	Worker OCR
o	Worker A e B recebem o mesmo document_id.
o	Ambos baixam o arquivo e chamam OCR/LLM.
o	O último commit sobrescreve extracted_text, status e custo.
o	Estado final: custo duplicado e resultado não determinístico.
5.	Assinatura
o	A e B leem contrato como sent.
o	Ambas fazem upload e marcam como signed.
o	Ambas podem fechar o mesmo processo e gerar auditorias distintas.
o	Estado final: último PDF/chave prevalece; ambos podem ter sido armazenados.
Performance
•	Paginações usam offset/limit sem desempate por chave primária; por exemplo [proposals.py (line 197)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:197). Inserções concorrentes podem causar duplicação ou salto de itens.
•	Repositório base pagina sem ORDER BY, [repositories/base.py (line 36)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/repositories/base.py:36).
•	Há índices isolados em tenant_id, mas várias consultas combinam tenant_id + created_at, tenant_id + process_id ou tenant_id + status; a compatibilidade real precisa de EXPLAIN ANALYZE.
•	Kanban, dashboards e hubs fazem múltiplas consultas e carregam coleções em memória; há risco de N+1 e full scan conforme o volume cresce.
•	Documentos legislativos são paginados, mas sem filtro tenant e sem índice composto correspondente.
•	O RAG filtra por tenant/global, mas geração de embedding acontece antes do commit e pode manter conexão ocupada durante chamada externa.
Testes necessários
•	Teste concorrente com duas sessões para cada transição de processo, proposta, contrato, rota e checklist.
•	Teste de retry do mesmo webhook, upload, assinatura, envio de proposta e worker OCR.
•	Mutation test removendo unique, lock e filtro tenant para confirmar que os testes detectam a regressão.
•	Teste de falha controlada após upload e antes do commit.
•	Teste de EXPLAIN ANALYZE com dados representativos e verificação de paginação estável.
•	Teste que confirma que nenhum GET altera contagem, timestamps ou registros.
________________________________________
AUD-04 — Multi-tenant, autenticação e autorização
Identidade e tenant
•	O usuário é localizado pelo e-mail em [auth.py (line 33)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/auth.py:33).
•	tenant_id do token é comparado com User.tenant_id em [deps.py (line 77)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/deps.py:77).
•	O tenant efetivo dos endpoints vem do usuário autenticado, não do corpo.
•	X-Tenant-Id é usado pelo middleware para logging/contexto, não deve ser considerado controle de autorização; [middleware.py (line 38)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/middleware.py:38).
•	JWT é stateless: logout não revoga token, conforme [auth.py (line 245)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/auth.py:245).
•	O único atributo de role efetivo é is_superuser. get_current_internal_user() não valida superusuário; portanto “interno” não equivale a “admin”.
Inventário de endpoints sensíveis
Endpoint/família	Método	Entidade	Auth/role	Tenant/filtro	Relações validadas	Risco
/auth/me, /auth/me/full, /auth/me/preferences, /auth/password-change	GET/PATCH/POST	User	JWT ativo	User do token	Próprio usuário	Sem optimistic locking; logout não revoga
/clients/*	GET/POST/PUT/PATCH/DELETE	Client	Interno	Repository por tenant	Cliente validado por tenant	Lost update
/processes/*	GET/POST/PUT/DELETE/POST	Process	Interno/portal conforme rota	Repository por tenant	Em geral processo; alguns joins usam somente ID	
/properties/*	GET/POST/PATCH/DELETE	Property/Matricula	Interno	Filtro tenant	Maioria validada; relações devem ser confirmadas	Concorrência em matrícula e atualização
/documents/*	GET/POST/PATCH/DELETE	Document	Interno ou AccessContext	Tenant + client portal	Processo/documento filtrados	URL pré-assinada depende do storage; confirmação não é idempotente
/tasks/*	GET/POST/PATCH/PUT	Task	Interno	Repository por tenant	Dependência verifica tenant	Lost update e dependência concorrente
/threads/*	GET/POST	Thread/Message	Interno	Thread tenant-scoped	Thread validada; mensagem não possui tenant próprio	Duplicação e falta de unique externo
/processes/{id}/decisions/*	GET/POST/PATCH/DELETE	Decision	Interno	Processo/tenant	Deve validar decisão e processo	Transições concorrentes
/processes/{id}/diagnoses/*	GET/POST/PATCH	Diagnosis	Interno	Processo/tenant	Processo validado	Versionamento sem lock
/processes/{id}/acoes/*	GET/POST/PATCH	Acao	Interno	Processo/tenant	Processo e ação tenant-scoped	Dedupe ajuda, mas update sem versão
/processes/{id}/rota/*, /rotas/*	GET/POST/PATCH/DELETE	Rota/Passo	Interno	Tenant	Rota e passo filtrados	Reordenação/fechamento concorrente
/processes/{id}/consolidar, vinculo-*, chain-proposals/*	POST/GET	Consolidação/lineage	Interno	Processo tenant	Escopo explícito	Retry pode duplicar efeitos
/proposals/*	GET/POST/PATCH	Proposal	Interno	Proposta tenant	Criação não valida client/process/rota do body	Possível vínculo cross-tenant se IDs válidos de outro tenant
/contracts/*	GET/POST	Contract	Interno	Contrato tenant	create_contract não valida client/process/proposal por tenant	IDOR lógico e relações cross-tenant
/contracts/{id}/generate-pdf, /assinar	POST	Contract/Storage	Interno	Contrato tenant	Processo carregado sem filtro tenant em assinatura	Pode fechar processo de outro tenant se relação inconsistente
/legislation/documents/*, /legislation/search	GET/POST	Corpus legislativo	Interno, sem superuser	Sem filtro tenant	doc_id consultado globalmente	Qualquer usuário interno acessa/modifica documentos globais e privados
/knowledge/search	GET	Knowledge/RAG	Interno	Global + tenant no serviço	Filtro explícito	Precisa confirmar isolamento real no SQL
/knowledge/reindex-legislation	POST	RAG global	Superuser	Global	Sem tenant, intencionalmente global	Operação cara; sem lock/idempotência de job
/legislation/alerts/*	GET/PATCH	Alert	Interno	Tenant filtrado	Alert tenant	Trigger de monitor não exige superuser
/admin/audit/verify-chain	GET	AuditLog	Superuser	Tenant da sessão	Role explícita	Boa barreira, mas depende de is_superuser correto
/admin/intake-feedback/stats	GET	Feedback	Interno	Deve ser revisto	Não foi localizado guard de superuser	Possível exposição administrativa
/agents/*, /ai/*	GET/POST	AIJob/agentes	Interno	Jobs filtrados por tenant	Processo geralmente filtrado	Retry e custo duplicado
/processes/{id}/macroetapa/status	GET	Checklist	Interno	Tenant no processo	GET grava	Efeito colateral e corrida
/dashboard/*	GET	Agregações	Interno	Consultas majoritariamente tenant	Alguns joins dependem de IDs derivados	Vazamento se dados inconsistentes
/messaging/whatsapp/webhook	POST	Message/Document	HMAC, sem JWT	Tenant derivado do telefone/client	Cliente encontrado por telefone	Não há unique para external_msg_id
/waitlist	POST público	Pré-cadastro	Público	Sem tenant por desenho	E-mail unique global	Fora do escopo tenant, mas exige teste de corrida
Achados de isolamento
1.	Corpus legislativo sem isolamento de tenant — alto
[legislation.py (line 74)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:74) consulta por id sem tenant_id; a listagem também não filtra tenant. Além disso, criação força tenant_id=None em [legislation.py (line 39)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:39).
Cenário: usuário do tenant A consulta /legislation/documents/{id} pertencente ao tenant B. O registro é retornado. O mesmo vale para upload e reindex.
2.	Relações cross-tenant não são verificadas na criação — alto
create_contract() atribui o tenant do usuário, mas aceita client_id, proposal_id e process_id sem validar que pertencem ao mesmo tenant. O mesmo padrão aparece na criação de proposta.
Cenário: usuário A envia client_id de B junto com dados de A. Se a FK aceitar o ID, o contrato fica no tenant A apontando para cliente B.
3.	Joins posteriores sem filtro tenant — médio/alto
Em [processes.py (line 364)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:364), cliente e imóvel são carregados apenas por id depois de validar o processo. A integridade atual depende de todas as escritas anteriores terem validado relações, o que não é garantido.
4.	Autorização administrativa inconsistente — médio/alto
get_current_internal_user() somente bloqueia portal; não verifica is_superuser. Operações de monitoramento, feedback e outros endpoints administrativos podem estar disponíveis para qualquer usuário interno. Apenas auditoria e reindex explicitamente verificam is_superuser.
5.	RLS não comprovado e aparentemente ausente no código/migrations
Não foram encontrados ENABLE ROW LEVEL SECURITY, CREATE POLICY, SET ROLE ou current_setting em app/alembic. O isolamento depende da camada de aplicação. Sem RLS, uma query sem filtro tenant expõe diretamente dados de outros tenants.
6.	Revogação de JWT inexistente
O logout apenas instrui o cliente a apagar o token. Um token roubado continua válido até expirar.
7.	Jobs globais e background
A maioria dos jobs recebe tenant_id, mas reindex_all_legislation() busca todos os documentos e enfileira por doc_id, sem tenant. A segurança depende do worker tratar corretamente a natureza global/privada do corpus.
Cenários de abuso
•	Usuário autenticado do tenant A usa um doc_id legislativo conhecido de B e lê ou reindexa o documento.
•	Usuário interno comum chama endpoint administrativo de monitoramento ou feedback.
•	Usuário A cria contrato usando client_id de B; a resposta pode conter dados relacionais de B.
•	Um JWT antigo continua funcionando após logout.
•	Dois webhooks com o mesmo evento criam duas mensagens no mesmo caso.
Testes negativos necessários
•	Dois tenants com documentos legislativos distintos; confirmar que GET, upload, reindex e busca não cruzam dados.
•	Criar proposta/contrato usando IDs de cliente, processo e rota de outro tenant; esperar 403 ou 404.
•	Usuário interno não-superuser tentando endpoints administrativos; esperar 403.
•	Token pós-logout e token com tenant adulterado; esperar rejeição.
•	Relações inconsistentes entre processo, cliente, imóvel, proposta e contrato; confirmar que a resposta nunca atravessa tenant.
•	Webhook repetido com o mesmo external_msg_id; confirmar apenas uma mensagem/documento.
•	Teste real de RLS com usuário não proprietário (SET ROLE), caso RLS seja adotado; conexão proprietária não prova isolamento.
Conclusão
O isolamento básico do caminho JWT → usuário → tenant está presente e muitos repositories aplicam filtro por tenant. Porém, há falhas relevantes:
•	corpus legislativo acessível sem filtro tenant;
•	relações cross-tenant não validadas em criação;
•	autorização administrativa incompleta;
•	ausência de RLS comprovável;
•	GET com commit;
•	ausência sistemática de optimistic locking e locks de transição;
•	workers e webhooks sem deduplicação forte;
•	efeitos externos misturados com transações de banco.
Esses pontos devem ser tratados como bloqueadores antes de considerar o fluxo transacional e multi-tenant robusto.

AUD-04 — Autenticação, autorização e isolamento multi-tenant
Escopo
Auditoria somente leitura no checkout atual:
•	SHA analisado: 11ab1af
•	Não existe referência local identificável a “AUD-01”; portanto, este SHA foi tratado como alvo efetivo.
•	Não usei documentação nem subagentes.
•	Não executei testes ou mutações.
Fluxo de identidade e tenant
1.	Login recebe email/senha em POST /api/v1/auth/login.
2.	O usuário é localizado globalmente por email; users.email é globalmente único.
3.	O backend origina user_id e tenant_id do registro User, não do cliente.
4.	O JWT contém sub, tenant_id, profile e opcionalmente client_id.
5.	Em requests HTTP, sub é validado contra users.id e o tenant_id do token é comparado ao tenant do usuário.
6.	O tenant efetivo dos endpoints vem de current_user.tenant_id.
7.	is_superuser é lido do banco; não há um sistema geral de roles/permissions.
8.	X-Auth-Profile é controlável pelo cliente, mas a seleção client_portal ainda exige um cliente correspondente no mesmo tenant.
9.	X-Tenant-Id é aceito pelo middleware para logging quando não há Bearer; não deve autorizar acesso, mas polui contexto de observabilidade com tenant controlável pelo cliente: [middleware.py (line 38)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/middleware.py:38).
JWT não possui refresh token, jti, blacklist ou revogação server-side. Logout apenas instrui o cliente a remover o token: [auth.py (line 245)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/auth.py:245).
Achados principais
AUD-04-01 — Alta — Relações entre tenants não são validadas na criação
POST /processes grava client_id, property_id e responsible_user_id recebidos no payload, mas não verifica que pertencem ao tenant autenticado: [processes.py (line 111)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:111).
Os modelos possuem apenas FKs globais, sem garantia composta (tenant_id, id): [process.py (line 99)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/process.py:99).
O mesmo problema existe em propriedades: PropertyRepository.create() aplica o tenant da sessão, mas aceita client_id arbitrário: [property_repo.py (line 11)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/repositories/property_repo.py:11).
Impacto:
•	tenant A pode criar processo apontando para cliente/imóvel/usuário do tenant B;
•	respostas e dashboards podem carregar dados relacionados do tenant B;
•	jobs, PDFs, RAG e auditoria podem operar sobre relações inconsistentes;
•	IDs inteiros globais tornam a enumeração de objetos prática.
AUD-04-02 — Alta — Contratos aceitam referências cross-tenant
POST /contracts consulta o processo apenas por Process.id, sem Process.tenant_id, e grava no contrato os IDs enviados pelo cliente: [contracts.py (line 157)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:157).
Serviços posteriores também resolvem cliente, processo, imóvel e proposta somente por ID:
•	[contract_generator.py (line 38)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/contract_generator.py:38)
•	[contracts.py (line 117)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:117)
Cenário: usuário do tenant A cria contrato com process_id, client_id ou proposal_id do tenant B. O contrato nasce com tenant_id=A, mas a geração de conteúdo/PDF pode incorporar dados de B.
AUD-04-03 — Alta — Corpus legislativo global pode ser lido e alterado por qualquer usuário interno
Os endpoints legislativos criam documentos com tenant_id=None, mas não exigem superusuário:
•	criação: [legislation.py (line 31)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:31)
•	upload por ID global: [legislation.py (line 65)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:65)
•	listagem sem tenant filter: [legislation.py (line 86)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:86)
•	leitura por ID global: [legislation.py (line 112)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:112)
•	reindexação por ID global: [legislation.py (line 146)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:146)
POST /legislation/monitor/trigger também está descrito como admin, mas só exige usuário interno: [legislation_alerts.py (line 78)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation_alerts.py:78).
Isso não é vazamento entre tenants privados, mas é ausência de autorização administrativa e permite adulterar o corpus compartilhado usado por todos os tenants.
AUD-04-04 — Alta — storage_key é controlável no cliente
Os endpoints de confirmação de upload aceitam body.storage_key diretamente:
•	[documents.py (line 176)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:176)
•	[intake.py (line 814)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/intake.py:814)
Não há validação de que a chave:
•	foi emitida pelo backend;
•	pertence ao tenant corrente;
•	corresponde ao processo/draft corrente;
•	possui o prefixo tenant_{current_user.tenant_id}/.
O download apenas gera URL presignada para a chave persistida: [documents.py (line 343)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:343).
Cenário: usuário conhece ou enumera uma chave de outro tenant e a envia na confirmação. O banco do tenant A passa a referenciar objeto armazenado sob tenant B; o endpoint de download de A gera URL para o objeto de B.
AUD-04-05 — Alta — WebSocket não valida escopo completo do JWT
O WebSocket:
•	busca apenas User.id;
•	não verifica is_active;
•	não compara token_data.tenant_id com user.tenant_id;
•	não valida que client_id pertence ao tenant do usuário;
•	aceita o token como query parameter.
Evidência: [websockets.py (line 126)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/websockets.py:126).
Eventos Redis confiam em tenant_id e client_id presentes na mensagem recebida, sem uma segunda validação de entidade: [websockets.py (line 63)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/websockets.py:63).
AUD-04-06 — Alta — Webhook WhatsApp deriva tenant por telefone global
_find_client_by_phone() consulta todos os clientes de todos os tenants e retorna o primeiro telefone que coincidir pelos últimos oito dígitos: [messaging.py (line 63)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/messaging.py:63).
Depois disso, o tenant é derivado do cliente encontrado: [messaging.py (line 193)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/messaging.py:193).
Se o mesmo número existir em dois tenants, mensagens, mídia, threads e auditoria podem ser atribuídas ao tenant errado.
AUD-04-07 — Média — Jobs assíncronos aceitam IDs sem validação suficiente no endpoint
Os endpoints de IA e agentes propagam process_id/document_id diretamente para Celery:
•	[agents.py (line 172)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/agents.py:172)
•	[ai.py (line 173)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/ai.py:173)
As tasks de OCR/extração validam tenant, mas run_agent_chain contém busca por processo somente por ID: [agent_tasks.py (line 200)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/workers/agent_tasks.py:200).
O pipeline de agentes usa tenant_id no contexto, mas a validação deve ocorrer antes do enqueue e em cada mutação subsequente.
AUD-04-08 — Média — Ausência comprovável de RLS
Não foram encontrados CREATE POLICY, ENABLE ROW LEVEL SECURITY, current_setting(...) ou mecanismo equivalente nas migrations/SQL executáveis pesquisadas.
O isolamento depende exclusivamente dos filtros ORM e de disciplina dos serviços. Portanto, qualquer query direta sem tenant filter é uma falha efetiva; não existe segunda barreira no banco.
AUD-04-09 — Média — Revogação de sessão inexistente
Senha alterada não invalida tokens já emitidos. Logout não revoga token. Um token roubado permanece utilizável até expirar, aproximadamente 30 minutos por configuração: [security.py (line 26)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/security.py:26).
Inventário de endpoints sensíveis
Todas as rotas abaixo exigem JWT, salvo indicação contrária. internal significa get_current_internal_user; isso não representa uma role granular.
Endpoint(s)	Método	Entidade	Autenticação	Role	Tenant/origem	Filtro/relações	Risco
/auth/login	POST	User/JWT	pública + rate limit	nenhuma	DB por email	email global	sem refresh/revogação
/auth/me, /auth/me/full	GET	User	JWT	interno/portal	User.tenant_id	por sub	baixo
/auth/me, /auth/me/preferences, /auth/password-change, /auth/logout	PATCH/POST	User	JWT	interno/portal	usuário autenticado	próprio usuário	logout não revoga
/clients/, /{client_id}, delete-preview, summary, properties-with-status, ai-summary, timeline	GET/POST/PUT/PATCH/DELETE	Client	JWT interno	nenhuma granular	JWT	repository tenant-scoped; hubs usam IDs derivados	médio
/credentials, /{cred_id}	GET/POST/PATCH/DELETE	Credential	JWT interno	nenhuma granular	JWT	tenant filter	baixo
/processes/, /kanban, /{process_id}, requisitos, timeline, artifacts, staging-fields, confronto-identidade, matrículas, cadeia, decisões e macroetapas	GET/PATCH/POST/PUT/DELETE	Process e relacionados	JWT interno ou AccessContext	nenhuma granular	JWT	em geral Process.tenant_id; relações não são consistentemente validadas	alto na criação/relacionamento
/processes/ criação	POST	Process	JWT interno	nenhuma	JWT	repo.create()	AUD-04-01
/processes/{id}/extract, run-agents, macroetapa	POST	Process/Document/Agent	JWT interno	nenhuma	JWT + Celery	parte das tasks valida tenant	risco de enqueue com ID de outro tenant
/documents/categories, /documents/	GET	Document	JWT interno/portal	portal limitado	JWT + client_id	repository scoped	baixo
/documents/upload-url, /{id}/download-url, /{id}/text, /{id}, reprocess/delete	POST/GET/PATCH/DELETE	Document/Storage	JWT interno/portal	nenhuma granular	JWT	documento tenant-scoped	storage_key não confiável
/properties/, /{id}, matrículas, summary, cases, events, ai-summary	GET/POST/PATCH/DELETE	Property/Matricula	JWT interno	nenhuma	JWT	repository tenant-scoped	criação não valida client_id
/tasks/, /{id}, status, dependencies	GET/POST/PATCH/PUT	Task	JWT interno	nenhuma	JWT	repository tenant-scoped	baixo; processo relacionado deve ser validado
/threads/, /{thread_id}/messages	GET/POST	Thread/Message	JWT interno	nenhuma	JWT	thread tenant-scoped	baixo
/intake/classify, create-case, enrich	POST	Intake/Process	JWT interno	nenhuma	JWT	maioria filtra tenant	relações de entrada precisam validação composta
/intake/drafts, /{draft_id}, documentos, import, extraction-results, extracted-fields, reconcile, commit	GET/POST/PATCH/DELETE	Draft/Document	JWT interno	nenhuma	JWT	draft/document tenant-scoped	storage_key arbitrário
/workflows/templates, /workflows/...	GET/POST/PATCH	Workflow	JWT interno	nenhuma	JWT	mistura global/tenant	confirmar fallback global
/processes/{id}/checklist...	GET/POST/PATCH	Checklist	JWT interno	nenhuma	JWT	processo scoped; checklist por process ID	médio
/processes/{id}/dossier...	GET/POST	Dossier	JWT interno	nenhuma	JWT	processo tenant-scoped; buscas relacionadas sem tenant em alguns pontos	médio
/processes/{id}/decisions...	GET/POST/PATCH/DELETE	Decision	JWT interno	nenhuma	JWT	processo scoped	médio
/properties/... e /processes/... regulatory	GET/POST/PATCH	Regulatory	JWT interno	nenhuma	JWT	filtros geralmente tenant-scoped	verificar invariantes relacionadas
/processes/.../acoes, /processes/.../rotas, /rotas/...	GET/POST/PATCH	Ações/Rotas	JWT interno	nenhuma	JWT	helpers recebem tenant	baixo/médio
/processes/{id}/classify	POST	Feedback	JWT interno	nenhuma	JWT	process + feedback tenant	baixo
/admin/intake-feedback/stats	GET	Feedback agregado	JWT interno	deveria ser admin	JWT	tenant filter	qualquer usuário interno acessa
/admin/audit/verify-chain	GET	AuditLog	JWT interno	superuser	JWT	tenant filter	controle correto
/messaging/whatsapp/webhook	POST	Message/Thread/Document	HMAC público	nenhuma	telefone do payload	busca global por telefone	AUD-04-06
/proposals/...	GET/POST/PATCH	Proposal	JWT interno	nenhuma	JWT	list/get normalmente tenant-scoped	validar relações de cliente/processo
/contracts/...	GET/POST/PATCH	Contract/PDF	JWT interno	nenhuma	JWT	contrato scoped; entidades relacionadas não	AUD-04-02
/ai/status, classify, extract, jobs	GET/POST	AIJob	JWT interno	nenhuma	JWT	jobs tenant-scoped	endpoints async aceitam IDs sem precheck
/agents/run, /chain, /run-async, /chain-async, registry, chains, budget	GET/POST	Agent/AIJob	JWT interno	nenhuma	JWT	contexto tenant; async aceita process ID livre	AUD-04-07
/dashboard/*	GET	agregados de tenant	JWT interno	nenhuma	JWT	processo inicial tenant-scoped; joins derivados	risco se relações cross-tenant já existirem
/legislation/documents*, /search	GET/POST	Corpus legislativo	JWT interno	deveria ser admin para escrita	global tenant_id=NULL	sem tenant filter	AUD-04-03
/legislation/alerts, /{alert_id}/read	GET/PATCH	Alert	JWT interno	nenhuma	JWT	tenant filter	baixo
/legislation/monitor/trigger	POST	Crawler global	JWT interno	declarado admin, não aplicado	global	dispara task global	AUD-04-03
/knowledge/search	GET	Knowledge/RAG	JWT interno	nenhuma	JWT	(tenant_id IS NULL OR tenant_id=current)	correto, mas mistura corpus global por desenho
/knowledge/index	POST	Knowledge/RAG	JWT interno	nenhuma	JWT	grava tenant corrente	qualquer usuário interno injeta corpus privado
/knowledge/reindex-legislation	POST	Knowledge/RAG	JWT + superuser	superuser	global	reindexa todos os documentos	controle correto
/ws e /api/v1/ws	WebSocket	eventos realtime	JWT em query string	nenhuma	usuário DB + client_id token	tenant derivado do usuário; client não revalidado	AUD-04-05
/waitlist	POST	PreCadastro	pública + rate limit	nenhuma	sem tenant	tabela deliberadamente global	esperado
/, /health, /metrics	GET	operacional	pública	nenhuma	global	sem dados de negócio ou depende da configuração	revisar exposição de métricas
Storage
O prefixo de chaves é teoricamente tenant-scoped:
tenant_{tenant_id}/process_{process_id}/...
tenant_{tenant_id}/draft_{draft_id}/...
Evidência: [storage.py (line 98)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/storage.py:98).
Entretanto, o serviço de download aceita qualquer storage_key e os endpoints persistem a chave enviada pelo cliente. O prefixo não é uma garantia se o valor não for validado contra o tenant autenticado.
RAG
A busca semântica aplica corretamente:
kc.tenant_id IS NULL OR kc.tenant_id = :tenant_id
Evidência: [knowledge_catalog.py (line 303)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:303).
Conclusão:
•	corpus global e privado são misturados intencionalmente;
•	chunks privados de outro tenant não deveriam aparecer pela query;
•	porém, ausência de RLS deixa qualquer chamada direta ao serviço sem tenant_id perigosa;
•	reindexação legislativa é global;
•	ingestão de texto privado pode ser feita por qualquer usuário interno, sem role específica.
Cenários de abuso e testes negativos
Não foram executados por causa do requisito somente leitura. Os testes negativos necessários são:
1.	Usuário A solicita GET /processes/{id_B} e deve receber 404, não 403 nem dados.
2.	Usuário A cria processo com client_id_B, property_id_B e responsible_user_id_B; deve receber 422/403.
3.	Usuário A cria contrato com process_id_B; deve ser rejeitado antes do commit.
4.	Usuário A confirma upload usando storage_key de B; deve ser rejeitado.
5.	Usuário A acessa /legislation/documents/{id} de qualquer documento global; confirmar se a leitura global é intencional e restringir escrita a superuser.
6.	Usuário interno não-superuser chama /legislation/monitor/trigger; deve receber 403.
7.	Dois tenants com o mesmo telefone enviam webhook WhatsApp; a atribuição deve ser determinística por conta/provider/tenant, nunca pelo primeiro registro.
8.	Token de usuário desativado conecta no WebSocket; deve ser rejeitado.
9.	Token client portal de A com client_id de B deve ser rejeitado por relação tenant.
10.	Token emitido antes de troca de senha/logout deve deixar de funcionar, caso revogação seja requisito.
11.	POST /agents/chain-async com process_id_B deve ser rejeitado no endpoint e novamente na task.
12.	Chunks privados de B devem permanecer ausentes em busca feita por A; chunks globais podem aparecer.
Conclusão
O isolamento básico está implementado por filtros ORM e repositories tenant-scoped, mas não há RLS nem integridade composta entre tenant e entidades relacionadas. Os riscos mais importantes são:
1.	relações cross-tenant aceitas na criação;
2.	contratos que resolvem entidades relacionadas sem tenant;
3.	storage_key controlável;
4.	corpus legislativo global mutável por usuário interno;
5.	webhook WhatsApp que deriva tenant por telefone global;
6.	jobs de agentes com validação tardia/incompleta;
7.	ausência de revogação server-side.
O sistema não deve ser considerado isolado multi-tenant robusto enquanto esses caminhos não forem corrigidos e cobertos por testes negativos reais.
AUD-05 — Fluxos e máquinas de estado
Escopo e premissa
Auditoria somente leitura, sequencial, sem subagentes.
Não havia referência textual explícita a AUD-01. Usei o HEAD atual como SHA auditado:
11ab1afcd133042f985918ff855fc029684b3fb0
Nenhum arquivo foi alterado.
1. Mapa geral
Caso/Processo
  ├─ Process.status: lifecycle legado
  └─ Process.macroetapa: workflow efetivo E1..E7
       ├─ Checklist documental
       ├─ Documentos → OCR → extração → conferência
       ├─ Diagnóstico versionado → validação humana
       ├─ Achados regulatórios → decisão → saneamento
       ├─ Ações → triagem → execução
       ├─ Rota → validação → fechamento
       ├─ Proposta → envio → aceite/recusa/expiração
       ├─ Contrato → envio → assinatura
       └─ Saídas/StageOutput
O sistema possui dois eixos não sincronizados:
•	Process.status: lead → triagem → diagnostico → planejamento → execucao → protocolo → aguardando_orgao → pendencia_orgao → concluido/arquivado.
•	Process.macroetapa: entrada_demanda → diagnostico_preliminar → coleta_documental? → diagnostico_tecnico → caminho_regulatorio → orcamento_negociacao → contrato_formalizacao.
Evidência: [process.py (line 10)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/process.py:10), [process.py (line 74)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/process.py:74), [macroetapa.py (line 67)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/macroetapa.py:67).
2. Transições principais
| Domínio | Anterior | evento | validações/gate | seguinte | Efeitos / transação / idempotência / falha parcial / teste |
|---|---|---|---|---|
| Processo legado | status atual | POST /status | transição enum + tarefas incompletas | próximo status | Commit único e audit; sem lock de linha; não verifica gates da macroetapa. Testes: tests/test_state_machines.py:127-211. |
| Macroetapa | etapa atual | POST /macroetapa | checklist 100%, documentos, diagnóstico assinado, consolidação, rota e proposta conforme etapa | próxima etapa | Gate recalculado antes do update; audit e commit. Sem FOR UPDATE; duas requisições concorrentes podem avaliar o mesmo estado. [processes.py (line 985)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:985). |
| E2 | diagnostico_preliminar | avanço humano | consolidação + diagnóstico assinado + checklist | E3 se há documento essencial, E4 caso contrário | Ramo correto no backend; ambos os destinos são válidos. Testes: test_ramo_e2.py, test_avanco_e2_duas_portas.py. |
| Checklist documental | pending | received ou waived | nenhum validador real de arquivo; waived exige justificativa | estado agregado | received aceita document_id=None; 100% pode significar somente marcação manual. [checklist_engine.py (line 122)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/checklist_engine.py:122), [checklists.py (line 137)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/checklists.py:137). |
| Agentes da etapa | etapa atual | worker conclui chain | apenas marca completed, agent_suggestion e percentual | pronta_para_avancar | Não avança automaticamente. Retry transitório pode reexecutar a chain; não há chave de execução única. [macroetapa_engine.py (line 490)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/macroetapa_engine.py:490). |
| Documento | upload | OCR | cache/status do OCR | done, failed ou not_required | OCR, extração e revisão são eixos independentes; não existe estado único de documento. [document.py (line 10)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/document.py:10). |
| Conferência | staging pendente/consistente/divergente | decisão humana | aceita/rejeitada/escolha de fonte | aceito ou rejeitado | Consolidação grava apenas aceito; operação é idempotente em condições normais. Não existe estado gravado; após sucesso continua aceito. [extracted_field_staging.py (line 35)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/extracted_field_staging.py:35), [processes.py (line 1674)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:1674). |
| Diagnóstico | versão não validada | PATCH /diagnoses/{version}/validate | schema na criação + decisões críticas por processo | validada | 409 ao revalidar; audit. Criação calcula max(version)+1, sem lock; a própria documentação reconhece race. [regulatory.py (line 164)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/regulatory.py:164), [regulatory.py (line 352)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/regulatory.py:352). |
| Achado | suspeita | decisão/edição humana | coerência entre status_achado e status_saneamento | confirmada, descartada, ignorada, resolvida; saneamento pode ir a em_validacao/saneado | Coerência validada sobre o estado resultante; não há máquina de transições explícita, apenas combinações permitidas. [regulatory_coherence.py (line 68)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/regulatory_coherence.py:68). |
| Ação | pendente | triagem humana | escolha tarefa/escopo/dispensada | triada | Geração é idempotente por dedupe_key; PATCH permite marcar concluida. Concluir ação não altera o achado/passivo. [acoes.py (line 190)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/acoes.py:190), [acoes.py (line 236)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/acoes.py:236). |
| Rota | proposta | materialização IA | diagnóstico assinado; passos novos propostos | rota proposta | Reexecução reconcilia por dedupe_key, preserva edição humana; snapshot anterior é salvo. [rota_materializer.py (line 406)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/rota_materializer.py:406). |
| Rota | passo proposto | classificação + validação humana | classificacao != NULL | passo validado | Sem fonte normativa pode validar; classificação é o gate. [rotas.py (line 469)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/rotas.py:469). |
| Rota | validada | nova materialização com diferença | diff IA | desatualizada | Conteúdo humano não é apagado; novos passos bloqueiam fechamento. [rota_materializer.py (line 607)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/rota_materializer.py:607). |
| Rota | desatualizada | fechar com zero pendências | todos os passos vivos validados | validada | Backend aceita remoção IA sem novo passo como aceite explícito. Frontend está alinhado: podeFechar = pendentes === 0. [rotas.py (line 525)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/rotas.py:525), [RotaTab.tsx (line 410)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/frontend/src/pages/Processes/RotaTab.tsx:410). |
| Proposta | draft | enviar | rascunho | sent | Renova validade a partir do envio; e-mail é best-effort. [proposals.py (line 368)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:368). |
| Proposta | sent | aceite | não expirada | accepted | Expiração é derivada no read; aceite bloqueado quando efetivamente expirada. [proposals.py (line 408)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:408). |
| Proposta | sent/expired | recusa | estado enviado/expirado | rejected | Nova versão preserva anterior e cria previous_version_id. [proposals.py (line 441)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:441). |
| Contrato | proposta aceita | /contracts/gerar | status accepted + escopo/parcelas/matrículas válidos | contrato draft | Gera texto/PDF/StageOutput no mesmo fluxo; PDF é best-effort. [mirante_documents.py (line 423)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/mirante_documents.py:423). |
| Contrato | draft | aprovar/enviar | status draft | sent | Audit + commit. [contracts.py (line 416)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:416). |
| Assinatura | sent | assinar | status sent; PDF opcional | signed | A assinatura é persistida mesmo que o upload do PDF falhe; depois o processo recebe closed_at. [contracts.py (line 456)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:456). |
| Saída | inexistente | geração de proposta/contrato/diagnóstico | conteúdo e needs_human_validation | nova StageOutput | Não há supersedes, invalidated_at, versão ou ponte de invalidação. [stage_output.py (line 29)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/stage_output.py:29). |
3. Achados confirmados
AUD-05.1 — Checklist 100% sem evidência documental
Confirmado.
received pode ser gravado sem document_id; o percentual considera received + waived. Portanto, checklist 100% não prova que exista arquivo, que o arquivo pertença ao item ou que esteja processado.
Evidência:
•	[checklist_engine.py (line 122)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/checklist_engine.py:122)
•	[checklist_engine.py (line 168)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/checklist_engine.py:168)
•	[checklists.py (line 137)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/checklists.py:137)
Impacto: o gate valida marcação declarativa, não evidência vinculada.
AUD-05.2 — Gate de consolidação valida efeito de auditoria, não verdade da base
has_consolidated() procura apenas AuditLog(action="consolidar"). A própria implementação declara que detecta “consolidação produziu efeito”, não que a operação foi executada com resultado completo.
Evidência: [macroetapa_engine.py (line 107)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/macroetapa_engine.py:107).
Além disso, a Conferência não tem estado gravado; depois da consolidação, a linha permanece aceito.
Evidência: [extracted_field_staging.py (line 101)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/extracted_field_staging.py:101).
AUD-05.3 — Endpoint alternativo permite concluir o processo sem os gates da macroetapa
POST /processes/{id}/status usa apenas a máquina legada e contagem de tarefas. Não exige diagnóstico assinado, rota validada, proposta aceita ou contrato assinado.
Evidência: [processes.py (line 448)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:448).
Resultado possível:
Process.status = concluido
Process.macroetapa != contrato_formalizacao
Contract.signed_at = NULL
Isso diverge do gate E7, que exige assinatura para considerar a etapa terminal concluída.
Evidência: [macroetapa.py (line 459)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/macroetapa.py:459).
AUD-05.4 — Edição de rota validada não invalida a assinatura
PATCH /rotas/{id}/passos/{id} permite editar qualquer passo vivo, inclusive passo validado, sem alterar Rota.status.
Evidência: [rotas.py (line 377)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/rotas.py:377).
Assim, uma rota pode continuar validada após alteração de título, prazo, órgão ou classificação. A invalidação só ocorre quando a IA materializa um diff, não quando o consultor edita diretamente.
AUD-05.5 — Saída nova não invalida derivadas antigas
StageOutput não possui ponte de substituição ou invalidação. A listagem retorna todos os artefatos por data, sem selecionar um vigente.
Evidência:
•	[stage_output.py (line 29)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/stage_output.py:29)
•	[processes.py (line 1266)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/processes.py:1266)
Diagnósticos são versionados, mas uma nova versão não invalida automaticamente rota, proposta, contrato ou StageOutput derivado.
AUD-05.6 — Assinatura conclui mesmo sem arquivo assinado
Confirmado por implementação e teste.
O PDF assinado é opcional. Falha de storage gera warning, mas o contrato segue para signed e o processo pode receber closed_at.
Evidência: [contracts.py (line 482)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:482).
Teste existente: tests/api/test_signature_e2e_s5c.py:87-131.
AUD-05.7 — Contrato manual pode contornar a origem em proposta aceita
O endpoint genérico POST /contracts aceita proposal_id sem validar que a proposta esteja accepted.
Evidência: [contracts.py (line 157)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:157).
O endpoint correto /contracts/gerar valida a proposta aceita via build_contrato, mas o endpoint alternativo mantém uma porta de bypass.
AUD-05.8 — Concorrência de diagnóstico explicitamente não protegida
A criação usa max(version) + 1 e a própria docstring reconhece race.
Evidência: [regulatory.py (line 171)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/regulatory.py:171).
A constraint evita duplicação persistida, mas não fornece transição limpa: uma requisição pode terminar em IntegrityError/409.
Não foram encontrados with_for_update ou FOR UPDATE nos fluxos auditados.
AUD-05.9 — Retry pode repetir efeitos de agentes
Workers fazem retry para falhas transitórias, mas o fluxo de chain não apresenta uma chave idempotente de execução nem uma constraint por execução.
Evidência: [agent_tasks.py (line 150)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/workers/agent_tasks.py:150), [agent_tasks.py (line 241)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/workers/agent_tasks.py:241).
A geração de ações e materialização de rota têm deduplicação própria; o efeito completo da chain não é atomicamente protegido contra reexecução.
4. Estados inalcançáveis ou problemáticos
•	ProcessStatus.arquivado só é alcançável após concluido ou cancelado; não há caminho direto de lead para cancelado.
•	RotaStatus.em_validacao existe, mas não representa claramente “validação em andamento”; o primeiro passo validado pode alterar a rota mesmo com passos pendentes.
•	ProcessChecklist.completed_at existe no modelo, mas não participa do cálculo de conclusão.
•	Document.extraction_status é string livre; estados inválidos são possíveis.
•	ProposalStatus.expired existe no enum, mas expiração normal não é persistida; é derivada.
•	ContractStatus.cancelled existe, mas não foi encontrado fluxo de cancelamento correspondente.
•	DecisionStatus.revisada e substituida existem, mas não há uma tabela de transições explícita.
•	Rota.validada pode coexistir com passo editado posteriormente e assinatura antiga.
•	Process.status=concluido pode coexistir com E7 não assinada.
5. Deadlocks e falhas parciais
Deadlocks funcionais
1.	Rota desatualizada com passos pendentes sem validação: bloqueia fechamento até validação.
2.	Rota desatualizada sem passos pendentes: backend e frontend corrigem o deadlock permitindo fechamento explícito.
3.	Checklist 100% com diagnóstico não assinado: permanece em aguardando_validacao.
4.	E7 com checklist 100% e contrato não assinado: permanece em aguardando_validacao.
5.	Consolidação sem AuditLog(action="consolidar"): gate pode permanecer bloqueado mesmo após chamada sem efeitos.
Falhas parciais confirmadas
•	Proposta: texto/StageOutput pode ser persistido quando PDF não é armazenado.
•	Contrato: conteúdo pode ser persistido sem PDF.
•	Assinatura: contrato pode ser assinado sem PDF assinado.
•	Consolidação: exceção desfaz a transação principal, mas o endpoint registra falha em trilha separada.
•	E-mail de proposta: falha não reverte o estado sent.
6. Testes ausentes
Não foram encontrados testes específicos para:
•	concorrência de duas chamadas simultâneas a /macroetapa;
•	concorrência em aceite de proposta;
•	concorrência em assinatura de contrato;
•	duas criações simultâneas da mesma versão de diagnóstico, além da constraint;
•	edição de passo já validado mantendo rota validada;
•	contrato criado por POST /contracts a partir de proposta draft, sent ou expired;
•	checklist 100% com received e document_id=None;
•	invalidação de StageOutput antigo após nova entrada;
•	nova versão de diagnóstico invalidando rota/proposta/contrato;
•	retry da mesma chain produzindo efeitos duplicados;
•	assinatura com falha do upload e posterior correção/reconciliação do PDF;
•	Process.status=concluido enquanto E7 não está assinada.
Existem bons testes unitários para enums e gates, mas eles não cobrem a consistência entre as duas máquinas de processo nem as fronteiras de transação.
Conclusão
O núcleo humano está razoavelmente protegido em diagnóstico, rota e proposta, mas a integridade global ainda depende de convenções paralelas.
Os riscos mais relevantes são:
1.	checklist 100% sem evidência;
2.	processo legado podendo ser concluído fora dos gates da macroetapa;
3.	rota validada editável sem invalidação;
4.	saídas antigas permanecendo vigentes junto de novas;
5.	assinatura válida mesmo sem arquivo assinado;
6.	endpoint genérico de contrato contornando proposta aceita;
7.	ausência de proteção concorrente nas transições críticas.
Esses pontos são falhas de consistência de estado, não apenas lacunas de interface.
AUD-06 — Agentes, prompts, skills e workflows
Escopo auditado: SHA 11ab1afcd133042f985918ff855fc029684b3fb0, checkout limpo. Auditoria somente leitura; nenhuma chamada a LLM, provider, banco externo ou ferramenta de agente foi disparada.
1. Cadeia comum executável
Para agentes registrados:
API/Celery
  → AgentContext(tenant_id, user_id, process_id, metadata)
  → AgentRegistry.create()
  → OrchestratorAgent.execute_chain()
  → BaseAgent.run()
  → PromptTemplate/ fallback local
  → skills aplicáveis anexadas ao system prompt
  → BaseAgent.call_llm()
  → ai_gateway.complete()
  → LiteLLM/provider
  → parser JSON ou parser de domínio
  → AgentResult
  → AIJob
  → chain_data / staging / entidade final
  → consumidor/API/UI
Evidências principais: app/agents/base.py:127-238, app/agents/base.py:268-306, app/agents/base.py:402-477, app/agents/orchestrator.py:125-227.
O orquestrador é determinístico: não usa LLM para decidir a rota. As chains estão em app/agents/orchestrator.py:23-40.
2. Inventário das operações reais
operação/agente	chamador / entrada real	prompt efetivamente carregado	modelo/provider	ferramentas	schema/validação	persistência / consumidor	revisão, retry, fallback, custo
atendimento / classificação	metadata.description, process_type, urgency, source_channel; app/agents/atendimento.py:28-35	classify_demand_system + classify_demand_user; DB ativo ou fallback local app/agents/atendimento.py:53-63	Matriz econômica: OpenAI default, Gemini Flash, Anthropic Haiku; app/core/model_matrix.py:83-103	Nenhuma	Parser JSON e validação de demand_type; app/services/llm_classifier.py:177-191	Resultado em AIJob; classificação também alimenta chain_data e dados de atendimento	Retry de gateway; fallback de provider; baixa confiança requer revisão.
extrator	Texto real de Document.extracted_text ou metadata.text, não apenas ID; filtros por tenant_id; app/agents/extrator.py:44-69, 127-165	extract_document_system e prompt por tipo de documento; seed v1 em alembic/versions/024fe3f5dbeb_seed_prompt_templates_data.py:131-208	Matriz econômica	OCR já executado; staging Ficha 01	Parser tolerante; não há schema forte no BaseAgent; _EXTRACT_OUTPUT_SCHEMA é fraco, exigindo apenas estrutura geral	Resultado em AIJob; campos adicionais em ExtractedFieldStaging; não grava diretamente todos os campos da entidade final; app/agents/extrator.py:167-190	Pode retornar skipped; falha determinística sem retry; staging é best-effort e pode ser ignorado; custo do LLM é registrado apenas quando o job é preenchido.
legislacao	Query, UF, tipo de demanda, contexto do processo, RAG e legislação ampla; trechos reais são inseridos no prompt; app/agents/legislacao.py:139-185	legislacao_system + legislacao_user, com RAG, contexto de esfera e fundamento anexados; fallback em app/agents/legislacao.py:894-935	Primário Gemini Flash; contexto grande Gemini Pro; fallback OpenAI/Anthropic pela matriz; configuração app/core/config.py:232-238	Busca RAG determinística, sem tool-calling do LLM	parse_llm_json; depois normalização e construção de conteúdo regulatório/Pydantic; app/agents/legislacao.py:245-279	AIJob; conteúdo usado por diagnóstico e rota regulatória; diagnóstico jurídico formal é criado em entidade versionada	Sempre requires_review=True; no diagnostico_completo, falha/revisão é explicitamente não bloqueante; timeout/retry no gateway; custo com teto específico.
diagnostico	Propriedade, processo, documentos com trechos, extrações, achados do auditor e contexto legal; app/agents/diagnostico.py:225-235	diagnostico_system + diagnostico_user; acrescenta instruções executáveis sobre documentos, vocabulário e fontes; app/agents/diagnostico.py:237-267	AI_DIAGNOSTICO_MODEL default gpt-4.1; fallbacks equivalentes	Nenhuma ferramenta LLM; usa dados determinísticos e citações	Parser JSON; construção de DiagnosticoPreliminarContent; validações de citações e fontes; app/agents/diagnostico.py:286-313	AIJob; diagnóstico formal versionado; gravação exige validação humana posterior	Sempre revisão humana; 32.768 tokens, retry de truncamento, teto de custo $0.50; porém o erro jurídico é não bloqueante quando ocorre dentro de diagnostico_completo.
redator	Diagnóstico, legislação, cliente, propriedade e instruções livres; todos serializados em JSON/texto; app/agents/redator.py:71-91	redator_system + prompt por tipo (PRAD, memorial, ofício etc.); fallback app/agents/redator.py:289-343	Matriz pesada: GPT/ Gemini Pro/ Claude Sonnet	Avaliador determinístico de citações	Resposta é texto; construção de PecaJuridicaContent; citações avaliadas, mas não necessariamente bloqueiam toda resposta	AIJob; consumidor esperado é StageOutput/artefato de processo	Sempre revisão humana; max_tokens=4096; retry/fallback do gateway; custo registrado pelo AIJob.
orcamento	Diagnóstico, tipo de demanda, contexto do processo e estimativa base; app/agents/orcamento.py:32-62	orcamento_system + orcamento_user; fallback app/agents/orcamento.py:140-158	Matriz econômica	Nenhuma	Parser JSON; valores ausentes caem para estimativas determinísticas; não há schema forte global	AIJob; saída serve para proposta/orçamento, mas a persistência final depende do consumidor	requires_review=True; fallback de provider; sem evidência de idempotência própria.
financeiro	Dados financeiros em metadata; só chama IA quando generate_insights=True; app/agents/financeiro.py:27-46	financeiro_system + financeiro_user; fallback app/agents/financeiro.py:117-129	Matriz econômica	Nenhuma	Parser JSON; nenhuma validação estrutural forte	AIJob; saída retorna insights/recomendações	Revisão por confiança; retry/fallback gateway.
marketing	Tema, audiência, tom e metadata.instructions; app/agents/marketing.py:30-48	marketing_system + prompt por tipo; fallback app/agents/marketing.py:59-107	Matriz econômica	Nenhuma	Texto livre; não há schema estrutural	AIJob; conteúdo retorna para consumidor de marketing	Sempre revisão; instruções livres são interpoladas diretamente.
acompanhamento	Conteúdo integral de mensagem, protocolo e órgão; app/agents/acompanhamento.py:32-61	acompanhamento_system + acompanhamento_parse_email; fallback app/agents/acompanhamento.py:138-157	Matriz econômica	Nenhuma	Parser JSON tolerante; defaults para campos ausentes	AIJob; resultado usado no monitoramento	Regras locais são fallback sem LLM; retry/fallback gateway.
auditor_imovel	Propriedade, documentos e extrações; não usa LLM; app/agents/auditor_imovel.py:35-113	Nenhum; prompt_slugs=[] e fallback vazio; app/agents/auditor_imovel.py:40-43, 214-216	Não aplicável	Tools determinísticas property_audit	Regras determinísticas	Persiste RegulatoryIssue; possui deduplicação por tenant/propriedade/achado; app/agents/auditor_imovel.py:242-266	Marca revisão, mas é não bloqueante na chain; idempotência explícita.
vigia	Dados de monitoramento	Nenhum LLM; fallback declara operação por regras; app/agents/vigia.py:192-195	Não aplicável	Regras determinísticas	Validação local	AIJob de agente, se executado pelo ciclo base	Não é operação real de IA.
OCR PDF	PDF real; pypdf primeiro, Gemini Vision por página, OpenAI Vision como fallback; app/services/ocr_pdf.py:120-223, 226-379	OCR_PROMPT + imagem base64 real	Gemini Vision primário; OpenAI Vision fallback	Rasterização PDF e upload inline de imagem/PDF	Não é JSON; aceita texto parcial; página falha vira texto vazio	Document.extracted_text, OcrStatus, AIJob; app/workers/ocr_tasks.py:294-339	Retry por página; limite de tentativas; timeout por página; texto parcial é aceito e persistido.
Transcrição	Bytes integrais do áudio, filename, idioma e vocabulário; app/services/transcricao_audio.py:177-184	Prompt Whisper com vocabulário de domínio	OpenAI Whisper; não há fallback Gemini/Anthropic	Conversão automática para MP3 quando necessário	Texto livre; vazio é sinalizado como erro funcional	Worker persiste texto/transcrição e métricas; custo por duração	Timeout de 300s; sem retry interno; erro retorna ao usuário; custo medido ou estimado.
Resumo de reunião	Transcrição integral inserida em RESUMO_PROMPT; app/services/transcricao_audio.py:221-257	Prompt estruturado de resumo	Gateway com agente atendimento	Nenhuma	Texto livre; vazio não falha a transcrição	Retorno é acréscimo; não encontrei persistência própria nesta função	Feature flag; falha é engolida e retorna resumo vazio; custo não é associado a AIJob nesta função.
Resumo semanal	Processo, tarefas e audit logs do tenant; app/workers/ai_summarizer.py:18-54	Prompt montado diretamente no worker	gpt-4o-mini direto via LiteLLM; bypass de ai_gateway	Nenhuma	Sem parser ou schema	Grava diretamente Process.ai_summary e AuditLog; app/workers/ai_summarizer.py:75-91	Sem timeout explícito, retry, limite de custo ou AIJob; sem chave retorna texto simulado que é persistido como resumo.
Embeddings	Texto real de chunks/query	Nenhum prompt textual	OpenAI text-embedding-3-small ou Gemini gemini-embedding-001, 768 dimensões; app/services/embeddings.py:43-55, 360-420	HTTP direto via httpx	Valida dimensão 768 e quantidade de resultados	Persiste vetor/modelo no catálogo de conhecimento	Até cinco retries em 429/5xx; não troca silenciosamente de espaço vetorial; custo não passa por AIJob.
3. Prompt resolution e versionamento
Há duas fontes concorrentes de prompt:
1.	PromptTemplate no banco.
2.	fallback hardcoded em cada agente.
A resolução é:
tenant + slug + is_active + maior version
  → fallback global tenant_id=NULL
  → fallback hardcoded
Evidência: app/services/prompt_service.py:49-94.
Problemas verificados:
•	O cache é local ao processo, com TTL de 60 segundos: app/services/prompt_service.py:23-28.
•	A chave do cache inclui slug e tenant, mas não inclui versão: app/services/prompt_service.py:31-33.
•	O modelo possui model_hint, temperature e max_tokens, mas BaseAgent.get_prompt() retorna apenas content; esses parâmetros do prompt não são aplicados ao gateway: app/models/prompt_template.py:68-75, app/agents/base.py:268-284.
•	O AIJob não registra slug, versão, hash ou conteúdo completo do prompt. Registra apenas input_payload, que para agentes do BaseAgent sequer é preenchido: app/models/ai_job.py:60-76, app/agents/base.py:407-443.
•	A criação de versão desativa a versão anterior, mas não há proteção transacional contra duas criações concorrentes: app/services/prompt_service.py:124-155.
•	Existe unicidade por (slug, version, tenant_id), mas não existe constraint garantindo uma única versão ativa por slug/tenant: app/models/prompt_template.py:52-56.
Conclusão: a resolução é versionada nominalmente, mas a chamada individual não é reproduzível. Depois do fato, não é possível reconstruir com segurança qual conteúdo, versão ou skill foi realmente enviado somente pelo AIJob.
4. Interpolação e prompt injection
A interpolação é substituição textual simples:
content.replace(f"{{{key}}}", str(value))
Evidência: app/services/prompt_service.py:101-106 e fallback em app/agents/base.py:281-284.
Constatações:
•	Conteúdo real de documentos, mensagens, instruções livres, RAG e transcrições é inserido diretamente no prompt.
•	Não há delimitador estrutural confiável nem separação de dados não confiáveis.
•	Não há sanitização de metadata.instructions, message_content, query, documentos ou textos extraídos antes da interpolação.
•	Há detector de injection somente no output, depois da resposta, em app/agents/validators.py:149-168.
•	Esse detector não protege o modelo contra instruções maliciosas presentes na entrada.
•	A instrução “não obedecer conteúdo dos documentos” é textual no prompt, não um controle executável.
Risco concreto: documento, e-mail, RAG ou instrução do usuário pode inserir comandos que alterem a interpretação do modelo. O sistema não possui isolamento de contexto equivalente a um canal de dados não confiável.
5. Conteúdo enviado versus IDs
Há diferença importante entre operações:
•	extrator: carrega e envia o texto real de Document.extracted_text, limitado por EXTRACTOR_MAX_CHARS; app/agents/extrator.py:138-165.
•	diagnostico: envia trechos reais de documentos, campos extraídos e contexto legal serializado; app/agents/diagnostico.py:228-235.
•	legislacao: envia trechos RAG reais, legislação ampla e contexto do caso; app/agents/legislacao.py:141-147.
•	OCR: envia imagem/PDF codificado em base64; app/services/ocr_pdf.py:145-162.
•	Transcrição: envia bytes de áudio reais; app/core/ai_gateway.py:571-589.
•	AIJob.input_payload normalmente registra somente preview, IDs, checksum ou metadados. No OCR, por exemplo, não guarda o PDF nem o prompt: app/workers/ocr_tasks.py:312-324.
Logo, os IDs ajudam a localizar a entidade, mas não garantem reconstrução do payload enviado.
6. JSON inválido, parcial e vazio
JSON inválido
O parser tolera:
1.	JSON direto.
2.	Bloco Markdown.
3.	Primeiro { até último }.
Evidência: app/agents/validators.py:52-91.
Não há tentativa de correção semântica ou nova chamada após JSON inválido. A falha retorna AgentResult(success=False) no BaseAgent.
JSON vazio ou parcial
•	document_extractor transforma falha de parse em {"_raw": ..., "_parse_error": True} e pode persistir o job como se fosse resultado de extração: app/services/document_extractor.py:194-220.
•	OCR aceita texto parcial quando algumas páginas falham: app/services/ocr_pdf.py:202-223.
•	Diagnóstico e legislação normalizam campos ausentes com defaults e podem produzir conteúdo sintético não vazio: app/agents/diagnostico.py:288-315, app/agents/legislacao.py:829-875.
•	O resumo semanal não valida resposta vazia antes de persistir.
•	O BaseAgent.validate_output() passa o dicionário diretamente; por padrão não aplica schema: app/agents/base.py:258-264.
7. Timeout, retry, fallback e limite de rodadas
Gateway principal:
•	Timeout padrão de 30s.
•	Até AI_MAX_RETRIES=2 por modelo para timeout, rate limit, 503 e erros transitórios.
•	Backoff exponencial.
•	Retry adicional quando finish_reason="length", dobrando max_tokens até o teto.
•	Fallback entre providers disponíveis.
•	Custo acima do teto gera falha imediata e não usa o próximo provider.
Evidências: app/core/config.py:246-258, app/core/ai_gateway.py:334-414, app/core/ai_gateway.py:473-493.
Workers:
•	run_agent: max_retries=2, soft_time_limit=300; app/workers/agent_tasks.py:82-87.
•	run_agent_chain: max_retries=1, soft_time_limit=600; app/workers/agent_tasks.py:159-164.
•	Erros determinísticos não devem repetir; erros transitórios repetem via Celery: app/workers/agent_tasks.py:129-154, 230-245.
Falhas específicas:
•	OCR possui retry por página e continua com resultado parcial.
•	Transcrição não possui retry de provider.
•	Resumo semanal bypassa o gateway e não tem timeout/retry/custo.
•	Não há loop de agente autônomo ou limite de rodadas LLM; as chains são listas finitas.
•	Há risco operacional de duplicidade por retry Celery, pois a execução gera novo AIJob e vários agentes não possuem chave de idempotência.
8. Bloqueio, não bloqueio e falha jurídica
O comportamento efetivo da chain é:
auditor_imovel review  → continua
legislacao review       → continua somente em diagnostico_completo
legislacao failure      → continua somente em diagnostico_completo
diagnostico review      → bloqueia
redator review          → bloqueia
demais reviews          → bloqueiam por padrão
Evidência: app/agents/orchestrator.py:42-75, 174-202.
Achado jurídico relevante:
•	legislacao marca revisão humana, mas sua falha ou timeout é explicitamente não bloqueante em diagnostico_completo.
•	O diagnóstico pode ser produzido com contexto jurídico parcial ou erro registrado em chain_data.
•	Isso permite conclusão de diagnóstico sem base legal disponível, embora o diagnóstico final permaneça marcado para revisão.
•	O endpoint de assinatura do diagnóstico possui gate adicional de validação humana e decisões críticas: app/api/v1/regulatory.py:352-478.
•	Portanto, a falha jurídica não permite diretamente assinar o diagnóstico regulatório, mas permite produzir e encaminhar uma conclusão preliminar sem legislação válida.
9. Decisão humana e sobrescrita
Há dois mecanismos:
•	RegulatoryDiagnosis: criado sem validação e validado posteriormente por usuário; versão já validada não pode ser validada novamente; app/api/v1/regulatory.py:352-401.
•	StageOutput: possui needs_human_validation, validated_at e validated_by_user_id; app/api/v1/processes.py:1327-1355.
Decisões críticas sobre achados são por processo e exigem decisão registrada antes da assinatura: app/api/v1/regulatory.py:403-477.
Não encontrei caminho executável que permita ao LLM sobrescrever uma decisão humana já validada. Porém:
•	A criação de novo diagnóstico gera nova versão.
•	O sistema permite múltiplas versões.
•	O consumidor precisa escolher corretamente a versão validada; não há evidência, neste escopo, de uma única “versão final” globalmente imutável.
10. Tenant e isolamento
Pontos positivos verificados:
•	AgentContext carrega tenant_id.
•	Consultas de documentos, processos, jobs, prompts e issues filtram por tenant em vários caminhos.
•	Prompt tenant-specific tem precedência sobre prompt global.
•	Limites de custo horário e mensal usam AIJob.tenant_id: app/core/ai_gateway.py:101-193.
•	AIJob registra tenant, entidade e usuário: app/agents/base.py:407-417.
Riscos:
•	A chamada direta de resumo semanal usa filtros de tenant para coleta, mas grava em Process/AuditLog fora de AIJob.
•	O gateway aceita user_preferences com api_key, provider e modelo; a resolução é best-effort e falha silenciosamente para o modelo global: app/agents/base.py:329-345, app/core/ai_gateway.py:240-316.
•	Prompt global é usado quando não há prompt tenant-specific; isso é intencional, mas torna o fallback hardcoded uma terceira versão concorrente.
•	Embeddings são globais por provider/modelo, não tenant-scoped.
11. Persistência e idempotência
Persistência intermediária
•	AIJob.result guarda saída estruturada e raw_output guarda texto bruto.
•	ExtractedFieldStaging é staging e precisa de consolidação humana/determinística.
•	OCR grava Document.extracted_text.
•	Diagnóstico e legislação possuem entidades formais versionadas.
•	O auditor grava RegulatoryIssue final com deduplicação.
Idempotência
•	Auditor de imóvel possui deduplicação explícita: app/agents/auditor_imovel.py:242-266.
•	Validação de diagnóstico é idempotente de forma negativa: repetição retorna 409.
•	PromptTemplate e AIJob não têm idempotency key de execução.
•	Retries Celery podem gerar novos jobs e novas versões/artefatos.
•	run_agent_chain pode ser repetido depois de falha transitória sem uma chave que identifique a mesma execução lógica.
•	Agentes como redator, orçamento e marketing não apresentam deduplicação própria.
12. Modelo/provider/tokens/custo registrados
Para agentes através do gateway:
•	modelo, provider, tokens de entrada/saída, custo e duração são coletados pela resposta;
•	BaseAgent._complete_job() grava esses campos no AIJob;
•	raw_output é preservado.
Evidência: app/core/ai_gateway.py:416-471, app/agents/base.py:425-443.
Lacunas verificadas:
•	versão/hash do prompt não é gravada;
•	skills anexadas não são gravadas;
•	parâmetros efetivos (temperature, max_tokens) não são gravados no AIJob;
•	AIJob.input_payload não é preenchido pelo caminho padrão dos agentes;
•	resumo semanal não registra AIJob, tokens, modelo efetivamente retornado nem custo;
•	embeddings não usam AIJob;
•	transcrição registra custo/duração no worker, mas não há evidência, no trecho auditado, de associação universal a AIJob;
•	quando LiteLLM não calcula preço, o custo vira 0.0, indistinguível de algumas situações sem custo real no caminho genérico.
Conclusão
O sistema possui uma arquitetura real de agentes, gateway, fallback, tenant, staging e revisão humana. Os principais riscos AUD-06 são:
1.	Não reprodutibilidade: AIJob não registra prompt/versão/skills/parâmetros efetivos.
2.	Três fontes concorrentes de prompt: banco, fallback hardcoded e instruções anexadas dinamicamente.
3.	Interpolação textual direta de conteúdo não confiável, sem isolamento contra prompt injection.
4.	Validação estrutural incompleta: vários agentes apenas extraem JSON e aceitam defaults.
5.	Extração pode persistir resultado de parse inválido como resultado de job.
6.	OCR aceita saída parcial como sucesso operacional.
7.	Falha jurídica é não bloqueante no diagnóstico completo e pode produzir diagnóstico com base legal parcial.
8.	Resumo semanal bypassa gateway, auditoria de custo, timeout, retry e AIJob.
9.	Idempotência é desigual: forte no auditor e validação humana, ausente na maioria das execuções de agentes.
10.	Skills são instruções anexadas ao system prompt, não controles executáveis nem permissões de ferramenta.
Não foi possível confirmar, em somente leitura do checkout, quais prompts estão atualmente ativos no banco de produção, quais chaves/modelos existem no ambiente real ou se a configuração de CI bloqueia todos os caminhos descritos.
AUD-07 — RAG: ingestão, corpus e proveniência
Escopo e referência
Auditoria somente leitura concluída no HEAD 11ab1af (main/origin/main). Não foi feito download, conversão, ingestão, reindexação ou execução de testes.
Não encontrei marcador literal AUD-01; portanto, o SHA acima é a referência observável adotada para esta auditoria.
Fluxo reconstruído
URL/PDF local
   ↓
httpx ou leitura de disco
   ↓
detecção MIME superficial
   ↓
pypdf / BeautifulSoup
   ↓
sanitização Unicode e whitespace
   ↓
metadados informados pelo operador
   ↓
LegislationDocument.status=indexed
   ↓
chunking estrutural ou janela deslizante
   ↓
normalização de ligaduras
   ↓
embedding
   ↓
knowledge_catalog
   ↓
busca por tenant, jurisdição e vigência
Uploads de documentos seguem outro caminho:
JWT + presigned URL
   ↓
PUT direto no MinIO
   ↓
confirm-upload
   ↓
Document
   ↓
OCR pypdf → Gemini → OpenAI
   ↓
Document.extracted_text
   ↓
agente extrator
Apenas LegislationDocument possui integração explícita com o knowledge_catalog. Document.extracted_text não entra automaticamente no corpus RAG.
Matriz
Tipo de fonte	Entrada	Validações observadas	Metadados obrigatórios	Idempotência	Falhas relevantes
Legislação por URL	URL HTTP(S) arbitrária	HTTP status, Content-Type, extensão .pdf, texto mínimo de 200 caracteres, mojibake �, sanitização	title, identifier, scope, source_type; agency, UF, URL e data são opcionais	identifier + content_hash; versão anterior vira superseded	Sem allowlist/autenticação de coletor; SSRF; URL pode retornar HTML errado; não valida identidade da norma nem assinatura real do PDF
PDF local	Caminho informado ao script	existência do arquivo, extração via pypdf, texto mínimo	mesmos metadados manuais	igual à URL	Sem validação de assinatura, tamanho ou bomb; páginas problemáticas podem desaparecer; file_path é apenas registrado
Upload de tenant	presigned PUT + confirm-upload	extensão allowlist, MIME declarado compatível, tamanho declarado entre 1 e 100 MB; assinatura %PDF somente no worker OCR	tenant/processo, nome, MIME, storage key, tamanho declarado	checksum somente é calculado depois, no worker; cache por checksum dentro do tenant	confirmação não verifica que a key pertence ao tenant/processo, nem que o tamanho/checksum corresponde ao objeto; falha no enqueue deixa documento persistido
Texto arbitrário/manual	index_text(source_type, source_ref, body, metadata...)	apenas corpo não vazio após normalização; embedding e chunking	nenhum campo de proveniência é obrigatório	hash de source_type + source_ref + índice + texto	source_ref, título, agência, jurisdição, identificador e origem podem ser inventados ou omitidos
ZIP/geoespacial	upload de ZIP, KML, SHP, GeoJSON etc.	extensão/MIME; ZIP é inspecionado apenas para detectar .shp	metadados de Document	não há deduplicação robusta no confirm-upload	não há limite de expansão, validação de path interno ou proteção explícita contra ZIP bomb; parser geoespacial não existe
Achados principais
1. Proveniência não é requisito de entrada
O modelo legislativo possui fonte_origem, fonte_oficial e fonte_conferida_em, mas todos podem chegar vazios; fonte_oficial apenas assume false por default ([legislation.py (line 100)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/legislation.py:100)).
O script de ingestão recebe URL e metadados, mas não exige órgão oficial, comprovação de oficialidade, autenticação, checksum do arquivo original ou evidência de conferência ([ingest_legislation.py (line 259)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/scripts/ingest_legislation.py:259)).
O caminho genérico é mais permissivo: index_text() aceita source_ref, title, agency, identifier e demais metadados como opcionais ([knowledge_catalog.py (line 187)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:187)).
Consequência: texto sem origem recuperável pode entrar diretamente no corpus.
2. Coletor sem autenticação e SSRF
load_from_url() aceita URL arbitrária, segue redirects e usa somente User-Agent de navegador; não há allowlist de host, bloqueio de IPs privados, autenticação de coletor ou validação de destino ([ingest_legislation.py (line 165)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/scripts/ingest_legislation.py:165)).
Isso permite:
•	consultar endpoints internos;
•	seguir redirect para host não oficial;
•	ingerir resposta de qualquer servidor;
•	registrar uma URL oficial enquanto o conteúdo veio de outro destino.
3. MIME, assinatura e tamanho são insuficientes
No upload, a API valida extensão e MIME declarado, não o conteúdo real ([documents.py (line 60)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:60)).
No confirm-upload, o cliente informa storage_key, tamanho e MIME; esses valores são persistidos sem comparação com o objeto real ([documents.py (line 160)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:160)).
A assinatura %PDF só é conferida no caminho OCR ([ocr_pdf.py (line 398)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/ocr_pdf.py:398)), e não no coletor legislativo por URL, que decide por Content-Type ou sufixo .pdf.
O limite de 100 MB é do valor declarado na requisição. O upload direto ao storage não passa pelo backend para medir o objeto real.
4. Path traversal e isolamento de storage
As keys geradas pelo serviço usam UUID e prefixo tenant_{id}/process_{id} ([storage.py (line 98)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/storage.py:98)), mas confirm-upload aceita uma key arbitrária enviada pelo cliente.
Não há verificação explícita de que:
storage_key == key originalmente emitida
storage_key começa com tenant_{tenant_id}/process_{process_id}
objeto existe
objeto pertence ao tenant
O worker então baixa diretamente essa key ([ocr_tasks.py (line 147)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/workers/ocr_tasks.py:147). Isso torna possível associar a um documento de um tenant uma key de outro tenant, caso o storage permita a leitura.
Para ZIPs, a implementação apenas chama namelist() e procura extensões de shapefile ([geo_files.py (line 80)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/geo_files.py:80)). Não há validação de:
•	tamanho descompactado;
•	razão de compressão;
•	número de entradas;
•	nomes absolutos;
•	..;
•	symlinks;
•	arquivos aninhados perigosos.
5. OCR parcial pode ser persistido como completo
O OCR Gemini:
•	limita a quantidade de páginas;
•	tenta cada página três vezes;
•	pula páginas que falham;
•	retorna o texto restante;
•	marca erro apenas no objeto OcrResult.
O código explicitamente devolve texto parcial quando alguma página falha ([ocr_pdf.py (line 183)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/ocr_pdf.py:183)).
Porém o worker considera qualquer result.text como sucesso, grava extracted_text e define ocr_status=done ([ocr_tasks.py (line 332)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/workers/ocr_tasks.py:332)).
Portanto:
5 páginas → 1 página falha → 4 páginas retornadas
→ Document.extracted_text preenchido
→ ocr_status = done
→ extrator recebe como texto completo
Não há metadado persistido com pages_total, pages_failed, partial=true ou uma exigência de revisão para esse caso.
Também há truncamento estrutural: Gemini limita a 15 páginas e OpenAI Vision a 10 ([ocr_pdf.py (line 41)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/ocr_pdf.py:41)).
6. Páginas silenciosamente perdidas no pypdf
A extração legislativa ignora páginas vazias ou que retornem texto vazio, sem registrar quais páginas falharam ([ingest_legislation.py (line 77)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/scripts/ingest_legislation.py:77)).
O OCR PDF também captura exceção por página e simplesmente continua ([ocr_pdf.py (line 87)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/ocr_pdf.py:87)).
Não existe retomada por página nem artefato de auditoria que permita distinguir:
documento realmente curto
documento parcialmente extraído
páginas ilegíveis
páginas não processadas por limite
7. Encoding e Unicode: melhoria parcial, mas caminhos inconsistentes
O coletor legislativo trata charset, U+FFFD, NBSP, whitespace e ligaduras ([ingest_legislation.py (line 122)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/scripts/ingest_legislation.py:122) e [ingest_legislation.py (line 219)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/scripts/ingest_legislation.py:219)).
O catálogo normaliza apenas ligaduras na entrada ([normalizacao.py (line 60)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/normalizacao.py:60)), não valida mojibake nem exige Unicode válido para texto arbitrário.
Assim, um texto com corrupção de encoding pode entrar via index_text() mesmo que o caminho legislativo por URL o recusasse.
8. Deduplicação e versionamento são incompletos
A ingestão legislativa usa:
identifier + content_hash do texto normalizado
e marca versões antigas como superseded, com revoked_at indicando que o registro foi substituído ([ingest_legislation.py (line 288)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/scripts/ingest_legislation.py:288)).
Limitações:
•	content_hash é do texto extraído, não do arquivo original;
•	PDFs diferentes com texto igual colapsam;
•	PDFs iguais com extração diferente geram versões;
•	o hash de chunk inclui source_ref, então o mesmo conteúdo em dois documentos nunca deduplica entre fontes ([knowledge_catalog.py (line 82)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:82));
•	não existe relação formal entre duplicata documental e fonte canônica;
•	reindexação não remove automaticamente chunks antigos de uma versão substituída.
9. Revogação, vigência e sucessão
A modelagem suporta vigência histórica, sucessora e rótulo de norma revogada ([legislation.py (line 79)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/legislation.py:79)).
A busca, entretanto, trata vigencia_fim IS NULL como vigente. A própria implementação declara que documentos antigos sem curadoria temporal continuam sendo considerados vigentes ([knowledge_catalog.py (line 400)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:400)).
Além disso, revoked_at não é usado como revogação jurídica; significa apenas que o registro foi superado pelo ingestor. Se a norma for revogada juridicamente, mas vigencia_fim permanecer nulo, ela pode ser recuperada como vigente.
10. Global versus tenant
O catálogo implementa:
•	tenant_id IS NULL como global;
•	consulta de tenant retorna global + tenant;
•	consulta sem tenant retorna somente global ([knowledge_catalog.py (line 318)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:318)).
Isso é coerente no caminho de busca, mas a API genérica de indexação permite que o caller escolha tenant_id=None ou qualquer tenant. Não há validação de que o chamador está autorizado a publicar conteúdo global.
11. Erro capturado deixando registro válido
Há dois casos claros:
1.	LegislationService.ingest_legislation_document() grava status="failed" e error_message, mas mantém uma entidade documental válida no banco ([legislation_service.py (line 64)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/legislation_service.py:64)).
2.	confirm-upload persiste o Document antes de enfileirar OCR. Se o enqueue falhar, a exceção é apenas logada ([documents.py (line 305)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:305)). O documento pode permanecer persistido em estado pendente, sem job associado e sem garantia de retomada.
Demonstração de entrada de material incorreto
Texto incorreto
URL oficial declarada: https://orgao.gov.br/lei.pdf
redirect → servidor externo
conteúdo HTML ou outra norma
Content-Type aceito / texto > 200 chars
→ operador fornece identifier e title esperados
→ status=indexed
→ corpus contém o texto errado
Causa: não há validação semântica da identidade da norma, órgão, número ou assinatura.
Texto incompleto
PDF com 10 páginas
página 7 falha no OCR
restante retorna texto
result.text != vazio
→ Document.extracted_text é gravado
→ ocr_status=done
→ extrator/RAG tratam como leitura completa
Causa: result.text é suficiente para sucesso; parcialidade não é persistida.
Norma revogada como vigente
norma antiga ingerida
vigencia_fim = NULL
ou somente revoked_at preenchido pelo versionamento
→ busca sem vigente_em recupera
→ busca com vigente_em também pode tratá-la como vigente
Causa: revoked_at é substituição de registro, não revogação jurídica; vigencia_fim ausente equivale a vigente.
Texto sem origem
index_text(
    source_type="manual",
    source_ref="manual-42",
    body="texto arbitrário",
    tenant_id=None,
    title=None,
    agency=None,
    identifier=None,
)
Resultado: chunk global, semanticamente recuperável, com source_ref não verificável e sem origem oficial obrigatória.
Conclusão
O pipeline possui bons controles pontuais — checksum de arquivo no worker, normalização de ligaduras, filtros tenant/global, chunking com contagem real e rótulo de norma histórica —, mas eles não formam um gate de proveniência e integridade de ponta a ponta.
Os riscos mais graves são:
1.	coletor URL sem allowlist/autenticação anti-SSRF;
2.	confirm-upload aceita storage key não vinculada ao tenant;
3.	OCR parcial é persistido como completo;
4.	origem, oficialidade e checksum original não são obrigatórios;
5.	index_text() permite publicar texto global sem procedência;
6.	ausência temporal (vigencia_fim=NULL) pode significar “vigente” por default;
7.	ZIP bomb/path traversal não possuem guard dedicado;
8.	falha de enqueue pode deixar registro persistido sem processamento garantido.
Não há evidência, neste SHA, de um gate único que impeça texto incorreto, incompleto, revogado ou sem origem de alcançar knowledge_catalog.
AUD-08 — RAG
Base auditada
Não existe referência textual ao SHA do AUD-01 no repositório. Auditei o estado disponível em HEAD:
11ab1afcd133042f985918ff855fc029684b3fb0
O pipeline RAG relevante foi introduzido/corrigido principalmente até 322b15b412ad1b39be02ae11330eeaa9efc4fd30. Não consultei serviços, banco externo, APIs nem reindexei.
Pipeline função por função
Chunking
Em [chunking.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/chunking.py):
•	normalizar() aplica somente expansão de ligaduras (ﬁ → fi), preservando º, ª e §.
•	contar_tokens() usa tiktoken, encoding cl100k_base.
•	_split_by_pattern() divide pelas ocorrências estruturais e preserva prelúdio anterior ao primeiro marcador.
•	_mapa_hierarquico() e _hierarquia_em() preservam último título, capítulo e seção anteriores ao chunk.
•	_extrair_dispositivo() captura apenas cabeçalho iniciado por Art. <número>, incluindo variantes como 61-A.
•	_extrair_referencias() captura referências com fórmulas específicas; não resolve nem navega o grafo.
•	_sliding_window() usa alvo de 800 tokens, overlap de 100 e corte por tokens.
•	chunk_text() tenta, nesta ordem: artigo, seção, capítulo, título; se não houver múltiplas fronteiras, usa janela deslizante.
Configuração:
•	TARGET_TOKENS = 800
•	MAX_TOKENS = 1500
•	OVERLAP_TOKENS = 100
•	MAX_ARTIGO_TOKENS = 7000
•	LIMITE_ARTIGO_TOKENS = 8000
•	teto da API: 8192
Achados:
•	Não há fronteiras próprias para parágrafos, incisos, alíneas ou itens.
•	As regex exigem cabeçalho no início da linha; OCR, HTML mal formatado e títulos inline podem não gerar fronteira.
•	A regex de artigo é mais restritiva que as demais: reconhece Art., não genericamente ARTIGO, nem todas as variantes editoriais.
•	Capítulos/seções só aceitam algarismos romanos.
•	O overlap só ocorre em chunks partidos por tamanho; artigos que cabem inteiros não têm overlap.
•	O corte por token pode ocorrer no meio de palavra/frase. Não há ajuste por sentença, parágrafo ou inciso.
•	Artigo genuinamente maior que 7.000 tokens é partido; acima de 8.000 perde o dispositivo e recebe [trecho nao articulado].
•	A guarda impede uma fatia absorvedora de herdar um rótulo falso, mas não consegue descobrir estrutura inexistente.
•	A hierarquia é armazenada, porém não chega ao resultado da busca nem ao prompt.
•	Referências são extraídas somente para fórmulas pré-definidas; menções como “prazo do art. 225” ficam fora.
•	O alvo da referência pode ser nao_declarado_no_texto; isso é honesto, mas não há resolução posterior.
•	O hash é por source_type + source_ref + chunk_index + texto; portanto, deduplicação é idempotência por fonte, não deduplicação semântica ou entre documentos.
•	chunk_tokens usa a contagem real; LegislationDocument.token_count continua usando len(text)//4 no caminho legado, produzindo metadados divergentes.
Embeddings
Em [embeddings.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/embeddings.py):
•	OpenAI: text-embedding-3-small, dimensions=768.
•	Gemini: gemini-embedding-001, outputDimensionality=768.
•	Dimensão persistida: 768.
•	Query Gemini usa RETRIEVAL_QUERY; chunks usam RETRIEVAL_DOCUMENT.
•	OpenAI ignora task_type.
•	Não há normalização explícita dos vetores; a distância cosseno do pgvector é usada diretamente.
•	O provider é selecionado por EMBEDDING_PROVIDER; vazio significa OpenAI por default.
•	A chave não seleciona mais silenciosamente o provider.
•	O modelo é gravado em embedding_model; dimensão em embedding_dim.
•	A busca filtra pelo modelo esperado e levanta EspacoVetorialIncompativel quando encontra corpus em outro espaço.
Riscos:
•	EMBEDDING_MODEL é avaliado no import time, enquanto current_model() lê configuração dinâmica; callers antigos podem observar valores diferentes após override/reload.
•	Não há versão de pipeline, versão de tokenizer, parâmetros de embedding ou checksum do modelo; há apenas nome e dimensão.
•	OpenAI e Gemini podem ocupar a mesma dimensão, mas continuam semanticamente incompatíveis.
•	tiktoken é importado em runtime, porém não aparece em requirements.txt nem requirements-dev.txt. Em instalação limpa, o chunking/validação pode falhar com ModuleNotFoundError.
Índice e busca
Em [knowledge_catalog.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py) e na migration:
•	Índice: IVFFlat.
•	Distância: vector_cosine_ops.
•	lists = 100.
•	RAG_IVFFLAT_PROBES = 10.
•	Não há HNSW, ef_search nem iterative_scan.
•	LIMIT é aplicado diretamente ao resultado aproximado.
•	Não há overfetch para compensar filtros.
•	Não há reranking.
•	Não há MMR/diversidade por documento.
•	Não há deduplicação na busca geral.
•	O agente deduplica apenas IDs quando agrega resultados por esfera.
Filtros:
•	tenant_id: retorna chunks globais (NULL) e do tenant; sem tenant, apenas globais.
•	source_type.
•	jurisdiction.
•	uf: inclui a UF solicitada e legislação federal com uf IS NULL.
•	identifier.
•	demand_type, via legislation_documents.demand_types.
•	vigente_em, via início/fim de vigência.
•	min_similarity, default 0.0; portanto, por default todo resultado retornado pelo índice é aceito.
Problemas:
•	Filtros seletivos são aplicados junto à consulta aproximada, mas não existe mecanismo para buscar candidatos adicionais. Com tenant, UF, esfera ou vigência restritivos, o top-k efetivo pode ter recall inferior.
•	min_similarity é aplicado depois do LIMIT; se vários resultados abaixo do limiar ocuparem as vagas, não há reposição.
•	Corpus vazio retorna [].
•	Provider incompatível pode ser detectado no serviço, mas LegislacaoAgent._load_rag_chunks() captura qualquer exceção e converte em [], ocultando a diferença entre corpus vazio, erro de configuração e indisponibilidade.
•	Não há fallback de recuperação lexical/híbrida.
•	Não há fallback específico quando um artigo é conhecido pelo identificador, mas não aparece semanticamente.
•	A migração não mostra RLS/policy específica para knowledge_catalog; a proteção observada é filtro SQL por tenant. Isso não prova isolamento em nível de banco.
Agente e contexto
Em [legislacao.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/agents/legislacao.py):
•	O agente usa LEGISLATION_RAG_TOP_K = 8.
•	Compõe a query com query + demand_type + uf.
•	Divide o orçamento por esfera, com mínimo de 3 chunks por esfera.
•	Faz fallback removendo UF e depois demand_type.
•	Não passa data de fato (vigente_em) para a busca RAG.
•	_format_rag_context() envia ao modelo somente:
o	título ou source_ref;
o	section;
o	identifier;
o	similarity;
o	chunk_text.
Não chegam ao modelo:
•	dispositivo;
•	dispositivo_origem;
•	hierarquia;
•	referencias;
•	fonte_origem;
•	fonte_oficial;
•	página;
•	data de vigência;
•	sucessora_ref;
•	UF/jurisdição/agência como campos explícitos.
Assim, o banco possui metadados melhores que os efetivamente entregues ao LLM.
A API também omite vigência, proveniência, artigo, hierarquia e referências em [schemas/knowledge.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/schemas/knowledge.py).
Segundo caminho: documento integral
[legislation_service.py](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/legislation_service.py) mantém outro caminho:
•	armazena full_text;
•	estima tokens com len(text)//4;
•	seleciona documentos por UF, escopo, agência e demand_type;
•	ordena por escopo/data;
•	envia o texto integral ao modelo;
•	default: até 20 documentos e até 1.900.000 tokens no caminho longo.
Esse caminho não usa chunking, embedding, página ou citações estruturadas. O header contém identificador, escopo, UF e agência, mas não vigência ou fonte oficial.
Cenários em que a norma correta existe e não aparece
1.	Norma federal excluída por filtro de UF — corrigido no código atual com uf = :uf OR uf IS NULL, mas permanece um risco em outros callers SQL.
2.	demand_type sentinela nao_identificado — produzia zero resultados; corrigido no agente.
3.	Provider/modelo divergente entre consulta e índice — agora tende a falhar alto no serviço, mas o agente mascara o erro como RAG vazio.
4.	Artigo correto fora do top-k por IVFFlat aproximado.
5.	Norma correta perde para parecer/doutrina semanticamente mais próxima.
6.	Filtro de vigência ou demanda reduz candidatos, mas não há overfetch.
7.	Artigo é conhecido por número, mas o embedding do artigo inteiro dilui o dispositivo.
8.	Corpus vazio ou não ingerido — o sistema apenas retorna ausência de trechos.
9.	Norma existe no chunk, mas sua identidade só está em dispositivo, que não é enviado ao modelo.
10.	Referência cruzada exige artigo/norma relacionada, mas o grafo não é seguido.
Resultados convincentes, porém errados
•	A medição de 322b15b registrou a OJN 06/2009 ocupando 6 das 8 vagas para uma pergunta que exigia norma legal.
•	O art. 61-A passou de posição 2 para 29 quando virou artigo inteiro; o vetor ficou semanticamente diluído.
•	A métrica anterior considerava o art. 61-A “recuperado” porque encontrou menções ao texto em chunks do art. 61-B — confundia menção com identidade.
•	Vetores de providers diferentes podem produzir similaridades numericamente normais e conteúdo aleatório; a trava atual reduz esse risco no serviço.
•	similarity não é limiar de relevância: default 0.0 aceita qualquer resultado retornado pelo índice.
Evals e testes existentes
Existem testes para:
•	sanidade do chunking;
•	artigo longo e corte;
•	hierarquia;
•	dispositivo lido/herdado;
•	referências;
•	teto de tokens;
•	ivfflat.probes;
•	filtro federal/UF;
•	sentinela de demand_type;
•	vigência histórica;
•	incompatibilidade de espaço vetorial;
•	regressões do agente de legislação.
Lacunas:
•	não há teste de recall com filtros combinados tenant + UF + vigência + demanda;
•	não há eval lexical/híbrido;
•	não há teste de MRR/Recall@k/NDCG em corpus real;
•	não há teste de diversidade por norma/documento;
•	não há teste de artigo, parágrafo, inciso e alínea como unidades de recuperação;
•	não há teste de página/proveniência chegando ao modelo;
•	não há teste que diferencie corpus vazio de provider incompatível no agente;
•	não há teste de instalação limpa verificando tiktoken;
•	não há teste de regressão para ef_search/HNSW porque não existem;
•	não há prova de RLS real para knowledge_catalog;
•	os testes de embedding usam mocks, portanto não demonstram compatibilidade real provider–índice.
Conclusão
A estrutura do chunking melhorou: há contagem real, teto explícito, guarda contra âncoras falsas, hierarquia e referências como dados. Porém a recuperação continua essencialmente:
embedding → IVFFlat → top-k aproximado → filtro/limiar → prompt
Sem reranking, overfetch, diversidade, busca lexical ou navegação de referências.
O maior risco operacional atual é a combinação de:
1.	contexto RAG pobre em metadados;
2.	ausência de reranking por tipo de fonte;
3.	artigo inteiro semanticamente diluído;
4.	filtros aplicados sem recuperação adicional;
5.	exceções convertidas em “nenhum trecho”;
6.	dependência runtime tiktoken não declarada.
Nenhum arquivo foi alterado e nenhum teste/serviço foi executado.
AUD-09 — resultado
Snapshot auditado: 11ab1afcd133042f985918ff855fc029684b3fb0 (HEAD). Não foi localizado artefato literal “AUD-01”; esta é uma premissa da auditoria.
Conclusão: existem bons controles de rastreabilidade e alguns gates humanos, mas os controles epistemológicos são majoritariamente parciais. O citation_evaluator valida apenas identidade textual da norma — tipo, número e ano — contra o contexto carregado. Não valida trecho, oficialidade, vigência, jurisdição aplicável, entidade emissora ou sustentação da conclusão ([citation_evaluator.py (line 303)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/citation_evaluator.py:303), [citation_evaluator.py (line 322)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/citation_evaluator.py:322)).
A própria implementação declara que citação inválida apenas marca requires_review; a saída continua entregue ([citation_evaluator.py (line 1)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/citation_evaluator.py:1), [citation_evaluator.py (line 8)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/citation_evaluator.py:8)).
Falha	Prevenção	Detecção	Reação	Bloqueia persistência?	Bloqueia entrega?	Humano?	Teste	Contorno	Classificação
Afirmação sem fonte	Afirmacao.fontes; sem_fonte previsto ([stage_output.py (line 161)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/schemas/stage_output.py:161))	UI exibe “sem fonte”; não há verificador universal de cobertura	Marca visualmente; revisão manual	Não	Não	Recomendado	test_rastreabilidade_contract.py, test_golden_agents.py	LLM pode emitir afirmação fora de afirmacoes	PARCIAL
Fonte inexistente ou que não sustenta conclusão	Citação confrontada com contexto	Só detecta ausência de identidade; não verifica existência real nem conteúdo sustentador	citation_issues, requires_review	Não	Não	Sim, teoricamente	test_citation_evaluator.py cobre match/mismatch	Contexto pode conter string arbitrária	PARCIAL
Fonte não oficial	Corpus possui fonte_oficial e classificação de origem ([knowledge_catalog.py (line 60)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:60))	Classificação de ingestão	Exibe procedência; não invalida citação	Não	Não	Não obrigatório	test_saneamento_corpus.py	Redator reduz contexto a strings e o evaluator ignora fonte_oficial	PARCIAL
Norma revogada/tempo errado	Busca aceita vigente_em e guarda vigencia_fim ([knowledge_catalog.py (line 323)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/knowledge_catalog.py:323))	Rótulo histórico no corpus	Aviso de norma histórica	Não	Não	Não obrigatório	Testes de vigência do catálogo	citation_evaluator não recebe nem compara vigência; fallback usa normas fixas	PARCIAL
Jurisdição errada	RAG filtra esfera, UF e jurisdição; passivos preservam órgão/esfera	Metadados são carregados no CitationRef	Nenhum bloqueio semântico	Não	Não	Não obrigatório	test_citation_evaluator.py, test_esfera_por_orgao.py	A citação é aceita mesmo se a jurisdição da norma não corresponder ao caso	PARCIAL
Entidade/órgão errado	Extração do órgão pelo cabeçalho do documento ([passivos_esfera.py (line 103)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/passivos_esfera.py:103))	Detecta órgão reconhecível	Rotula esfera; não valida conclusão gerada	Não	Não	Não obrigatório	test_esfera_por_orgao.py	Texto livre do LLM pode atribuir competência a outro órgão	PARCIAL
Fusão de processos/atos	Passivos são separados por documento e origem	Algumas fontes preservadas por item	Revisão/decisão humana na rota	Não	Não	Parcial	test_chain_fonte_unica.py, test_rota_contexto.py	Não há teste semântico que impeça juntar auto, notificação e licença em uma obrigação	PARCIAL
Extrapolação espacial	Há filtros de UF e tratamento de documentos geoespaciais	Lacunas espaciais podem aparecer como risco	Sinalização/recomendação	Não	Não	Parcial	test_geo_files.py, testes de auditoria espacial	Nenhum gate impede concluir sobre área/perímetro não verificado	PARCIAL
Ilegível tratado como ausente	Motor documental distingue documento presente, OCR pendente e sem texto ([requisito_documental.py (line 217)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/requisito_documental.py:217))	ocr_status, erro e confiança são persistidos	Reprocessamento e indicação de leitura falha	Em parte	Em parte	Sim para confirmação	test_ocr_tasks.py, test_requisito_documental*	OCR com texto parcial/confiança 0,70 pode seguir como texto utilizável	PARCIAL
Relato tratado como ato	Passivo de relato recebe tipo=atendimento, confiança baixa ([passivos_esfera.py (line 155)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/passivos_esfera.py:155))	UI rotula “relato não conferido”; rota instrui não usar como fundamento ([rota_contexto.py (line 190)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/rota_contexto.py:190))	Revisão humana	Não	Não	Parcial	test_rota_contexto.py	Outros agentes recebem description e podem reproduzir o ato como fato	PARCIAL / APENAS PROMPT fora da rota
Prazo, preço, procedimento ou obrigação inventados	Alguns prazos têm prazo_fonte; proposta usa tabela determinística ([proposal_generator.py (line 40)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/proposal_generator.py:40))	sem_fonte/estimativa em partes da rota	Aviso de estimativa; não há validador geral	Não	Não	Parcial	test_rota_materializer.py cobre prazo sem fonte	Fallback legislativo gera lista fixa de normas e propostas têm preços/prazos default	PARCIAL
Passivo sem qualificação	PassivoEsfera registra origem, órgão, esfera e fonte	Confiança baixa para relato; fonte visual	Recomendação de conferência	Não	Não	Parcial	test_passivos_esfera*, test_esfera_por_orgao.py	Não impede que diagnóstico transforme “relato” em passivo confirmado	PARCIAL
Recomendação virando serviço sem humano	Proposta exige rota validada; artefato nasce needs_human_validation=True ([proposals.py (line 303)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:303))	Estado de validação do artefato	Rascunho e revisão declarada	Não em todos os caminhos	Não	Sim apenas na geração declarada	Testes de proposta/rota	POST /proposals/{id}/send verifica apenas status draft e envia e-mail ([proposals.py (line 368)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:368))	PARCIAL
Revisão pendente não bloqueia saída	requires_review=True em peças formais	Badge/UI e campo persistido	Marca revisão pendente	Não	Não	Declarado, não imposto	test_redator_citation_hook.py, test_diagnostico_a3_citations.py	Consumidor pode ignorar o flag; endpoint retorna normalmente	AUSENTE como bloqueio; PARCIAL como sinalização
O que as citações realmente verificam
•	Formato: sim, por regex para leis, decretos, portarias, resoluções etc. ([citation_evaluator.py (line 84)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/citation_evaluator.py:84)).
•	Presença de citação: não. Texto sem citações é considerado validamente coberto (total=0, valid=True) ([citation_evaluator.py (line 318)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/citation_evaluator.py:318)).
•	Existência textual no contexto: parcialmente sim, por igualdade de (kind, número, ano).
•	Trecho literal: não.
•	Artigo/dispositivo: capturado, mas descrito como apenas informativo e não usado no cruzamento ([stage_output.py (line 197)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/schemas/stage_output.py:197)).
•	Vigência: não no evaluator.
•	Data do fato: não no evaluator.
•	Oficialidade: não.
•	Jurisdição aplicável ao caso: não; apenas copia a jurisdição do contexto.
•	Órgão/entidade competente: não.
•	Sustentação da conclusão: não.
•	Ausência de fonte em afirmações gerais: não há gate global.
Caso adversarial teórico
Entrada:
“O imóvel está sujeito ao embargo do IBAMA e deve protocolar defesa perante a SEMAD/GO em 20 dias, conforme Lei 12.651/2012.”
Contexto carregado:
•	Lei 12.651/2012 presente no catálogo;
•	trecho apenas sobre Reserva Legal, sem embargo, defesa ou prazo;
•	fonte não oficial;
•	jurisdição estadual incompatível;
•	relato do cliente mencionando “IBAMA”, mas nenhum auto anexado.
Resultado provável:
1.	Lei 12.651/2012 passa no evaluator por identidade.
2.	A afirmação sobre embargo, órgão, prazo e procedimento não é decomposta nem confrontada.
3.	O relato pode ser preservado como fonte fraca, mas a entrega continua possível.
4.	requires_review=True apenas produz sinalização.
5.	A saída persiste e pode ser exibida/encaminhada.
Esse caso demonstra que o sistema evita algumas citações totalmente inventadas, mas não impede uma conclusão falsa apoiada em uma fonte real porém inadequada.
Veredito
O controle mais forte é o de assinatura humana do diagnóstico e fechamento da rota: diagnóstico não assinado bloqueia a rota, e rota só fecha com todos os passos validados ([rota_contexto.py (line 234)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/rota_contexto.py:234), [rotas.py (line 508)](C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/rotas.py:508)).
Para guardrails epistemológicos, porém, o sistema está em nível PARCIAL. O principal gap AUD-09 é estrutural: requires_review é metadado de workflow, não enforcement de entrega. Prompts e rótulos honestos melhoram o comportamento esperado, mas não constituem bloqueio confiável sem validação posterior e gate obrigatório.
AUD-10 — Bugs silenciosos, idempotência e falhas parciais
SHA auditado: 11ab1afcd133042f985918ff855fc029684b3fb0
Execução somente leitura. Nenhum fluxo ou teste foi executado.
1. Upload confirmado sem garantia de objeto no storage — alta
Causa raiz: confirmação de metadados é tratada como upload concluído.
•	Estado inicial: URL presigned gerada; objeto pode não existir ou estar incompleto.
•	Evento: POST /documents/confirm-upload.
•	Caminho: app/api/v1/documents.py:184-238.
•	Estado incorreto final: Document persistido, checklist marcado como recebido e upload contabilizado como sucesso sem verificar storage_key.
•	Sinal observável: documento aparece na lista com ocr_status=pending; OCR depois termina em no_bytes.
•	Teste ausente: confirmar upload com objeto inexistente, chave de outro processo/tenant ou tamanho real divergente.
Além disso, falha ao enfileirar OCR, transcrição ou extrator é absorvida em app/api/v1/documents.py:311-339; a API continua retornando documento confirmado e métrica success.
2. Documento recebido, mas pipeline não processado — alta
Causa raiz: persistência do documento e despacho assíncrono não formam uma operação rastreável.
•	Estado inicial: documento confirmado e commitado.
•	Evento: .delay() falha, broker indisponível ou worker não registrado.
•	Caminho: app/api/v1/documents.py:241-256, :284-303, :311-336.
•	Estado incorreto final: documento permanece pendente, sem job de processamento e sem estado explícito de despacho falho.
•	Sinal observável: apenas log Falha ao enfileirar...; UI vê documento normal/pending.
•	Teste ausente: simular falha do broker após o commit e verificar estado recuperável/reprocessável.
3. Chain parcial reportada como completa — alta
Causa raiz: status externo da task ignora o resultado dos passos.
•	Estado inicial: chain executa vários agentes; um ou mais retornam success=False.
•	Evento: run_agent_chain.
•	Caminho: app/workers/agent_tasks.py:188-229.
•	Estado incorreto final: retorno contém "status": "success" mesmo com passos falhos.
•	Sinal observável: consumidor que olha apenas status pode liberar fluxo; os detalhes internos mostram success=False.
•	Teste ausente: chain com falha no primeiro, intermediário e último agente; exigir status geral failed ou partial.
A API síncrona calcula corretamente completed em app/api/v1/agents.py:155-164, mas a task assíncrona não mantém o mesmo contrato.
4. Extração calculada sem persistência funcional — alta
Causa raiz: caminho legado grava o resultado somente no AIJob.
•	Estado inicial: documento possui texto extraído.
•	Evento: /ai/extract ou run_document_extraction.
•	Caminho: app/workers/ai_tasks.py:174-191; o modelo Document possui extracted_text, mas não extracted_fields, em app/models/document.py:86-90.
•	Estado incorreto final: resposta/job informa campos extraídos, mas documento/staging não recebe os campos.
•	Sinal observável: nova consulta ao documento não encontra a extração; diagnóstico/checklist não evolui.
•	Teste ausente: executar extração assíncrona e verificar persistência em staging ou entidade derivada.
5. JSON inválido convertido em extração “concluída” — alta
Causa raiz: erro de parser vira dicionário de dados.
•	Estado inicial: LLM retorna JSON inválido.
•	Evento: _parse_json falha.
•	Caminho: app/services/document_extractor.py:194-227.
•	Estado incorreto final: parsed={"_raw": ..., "_parse_error": True}; o job pode ser salvo como concluído e fields_count fica positivo.
•	Sinal observável: AIJob completed com _parse_error, sem falha funcional para o chamador.
•	Teste ausente: resposta inválida, JSON truncado, lista JSON e objeto com esquema incompatível; exigir failed e nenhuma consolidação.
6. Persistência de AIJob e conclusão de agente são best-effort — alta
Causa raiz: falha de auditoria/persistência é absorvida.
•	persist_ai_job retorna None após erro em app/services/ai_job_persistence.py:79-83.
•	_complete_job absorve falha de flush em app/agents/base.py:425-445.
•	_fail_job também absorve falha de flush em app/agents/base.py:447-477.
Estado final possível: agente entrega sucesso ou falha, mas o histórico, custo, tokens e resultado não existem.
Sinal observável: resposta funcional sem ai_job_id, ou job permanece running.
Teste ausente: falhar commit/flush do AIJob e verificar que a execução não é apresentada como auditada.
7. Retry pós-commit pode duplicar custo e AIJobs — alta
Causa raiz: retry não é idempotente e ocorre depois de efeitos persistidos.
•	Estado inicial: OCR/transcrição conclui e grava Document + AIJob.
•	Evento: falha no despacho do extrator ou em etapa posterior.
•	Caminho: app/workers/ocr_tasks.py:347-388, :393-406; áudio em app/workers/audio_tasks.py:303-343.
•	Estado incorreto final: retry reexecuta OCR/transcrição, podendo criar novo AIJob e consumir IA novamente.
•	Sinal observável: múltiplos AIJobs para o mesmo documento/checksum e custos duplicados.
•	Teste ausente: falhar _dispatch_extrator depois do commit; executar retry e verificar unicidade/idempotência.
O mesmo padrão existe em run_llm_classification e run_document_extraction, que criam novo job a cada chamada (app/workers/ai_tasks.py:47-59, :150-162).
8. Soft delete ignorado em caminhos de leitura — média/alta
Causa raiz: ausência de filtro global para deleted_at.
•	Dossier inclui documentos excluídos: app/services/dossier.py:175-193.
•	Contagem de documentos por processo inclui excluídos: app/api/v1/processes.py:195-204.
•	Vínculo candidato pode buscar documento excluído: app/api/v1/processes.py:1604-1607.
•	Workers OCR/extração carregam documento sem deleted_at IS NULL: app/workers/ocr_tasks.py:91-95, app/agents/extrator.py:127-134.
Estado final: documento removido pode aparecer, ser contado, processado ou vinculado.
Teste ausente: soft-delete antes de cada leitura/worker e confirmar que não há exposição nem processamento.
9. Histórico substituído pode ser exibido como vigente — média
Causa raiz: endpoint “latest” usa apenas created_at.
•	Estado inicial: decisão A é substituída pela decisão B.
•	Evento: consulta da última decisão.
•	Caminho: app/api/v1/decisions.py:134-143.
•	Estado incorreto final: uma decisão com status=substituida pode ser retornada como “última decisão”.
•	Sinal observável: drawer/resumo mostra conteúdo histórico como vigente.
•	Teste ausente: criar decisão, substituí-la e consultar /decisions/latest; exigir exclusão de substituida.
Também há uso de datetime.utcnow() em colunas timezone-aware (app/api/v1/decisions.py:202, :262; app/models/process_decision.py:150-151), criando risco de comparação temporal inconsistente.
10. Fallback sem proveniência semântica — média
Causa raiz: fallback retorna resultado normal, sem marcar sua origem.
•	LLM falha e classificador retorna regras estáticas: app/services/llm_classifier.py:169-174.
•	Task grava esse resultado como AIJob concluído: app/workers/ai_tasks.py:75-98.
•	Prompt ausente cai para prompt hardcoded: app/services/document_extractor.py:180-190.
•	Estado final: usuário/custo/auditoria podem tratar resultado heurístico como resultado LLM.
•	Sinal observável: status=completed, embora o provider não tenha produzido a classificação.
•	Teste ausente: falha do provider e verificação de fallback_source, confiança e revisão obrigatória.
11. Enum/confiança desconhecida aceita como válida — média
Causa raiz: valor externo é convertido para string sem validação estrita.
•	Caminho: app/services/llm_classifier.py:131-140 aceita confidence arbitrário.
•	Base preserva qualquer valor: app/agents/base.py:479-486.
•	Estado final: confiança desconhecida pode ser exibida como válida; _needs_review só reconhece exatamente "low" (app/agents/base.py:488-492).
•	Sinal observável: valor como "certain", "0.8" ou "HIGH" não dispara revisão.
•	Teste ausente: resposta LLM com cada valor desconhecido e exigência de normalização/rejeição.
12. Health verde falso — média
Causa raiz: health endpoint não verifica dependências em tempo de requisição.
•	Caminho: app/main.py:211-213.
•	Estado inicial: API está viva, mas banco, Redis, storage, broker ou worker podem estar indisponíveis.
•	Estado final: /health sempre responde {"status":"ok"}.
•	Sinal observável: health verde enquanto uploads, WebSockets ou tasks falham.
•	Teste ausente: health com Redis/storage/banco indisponível e contrato separado de liveness/readiness.
O warm-up apenas registra falhas e continua (app/main.py:55-73).
13. Métricas medem execução Celery, não resultado de negócio — média
Causa raiz: estado do broker é confundido com sucesso funcional.
•	Caminho: app/core/celery_app.py:108-127.
•	Exemplo: tasks retornam {"status":"failed"} após retries esgotados, mas o postrun pode registrar estado Celery SUCCESS.
•	run_agent_chain é outro exemplo: retorno geral success mesmo com passo falho.
•	Sinal observável: dashboards mostram tasks verdes enquanto documentos/jobs/alertas falharam.
•	Teste ausente: comparar métricas com resultado funcional para tasks que retornam failed, partial ou skipped.
Além disso, persistência Redis de métricas absorve qualquer exceção em app/core/metrics.py:347-375; a métrica pode simplesmente desaparecer sem alerta.
14. Crawlers podem retornar resultado parcial como completo — média
Causa raiz: erro por termo é absorvido sem entrar no resultado do crawler.
•	Caminho: app/services/crawlers/dou_crawler.py:57-69.
•	Estado inicial: alguns termos são consultados com sucesso.
•	Evento: falha em outro termo.
•	Estado final: documentos dos termos bem-sucedidos são retornados como resultado normal; o erro só aparece em log.
•	Sinal observável: documents_found menor que o esperado, sem campo de erro por consulta.
•	Teste ausente: falhar um termo e verificar que o resultado fica explicitamente parcial.
Não confirmados como defeitos neste SHA
•	Não encontrei conversão inequívoca entre escala 0–1 e 0–100; há usos separados de confidence_score em 0.95/0.70 e health score em 0–100.
•	Não encontrei, nesta leitura, mutação silenciosa de JSON sem nenhum marcador; o parser registra _parse_error, embora o erro ainda seja tratado como sucesso.
•	Webhook operacional propaga retry corretamente em app/workers/webhook_tasks.py:34-48, mas não há idempotency key; duplicidade após timeout depois da entrega continua possível.
Priorização
1.	Corrigir contrato de upload/dispatch e estados pending/processing/failed.
2.	Tornar OCR, transcrição, classificação e chains idempotentes.
3.	Impedir que parse inválido, persistência ausente ou chain parcial sejam classificados como sucesso.
4.	Centralizar filtros de soft delete e separar health/readiness.
5.	Alinhar métricas de execução com resultado funcional.
AUD-11 — Threat modeling estático
Snapshot auditado: 11ab1afcd133042f985918ff855fc029684b3fb0.
Não existe marcador textual AUD-01 no repositório; portanto, usei o HEAD local como snapshot. Auditoria somente leitura. .env real não foi aberto.
Trust boundaries
•	Navegador interno/portal do cliente → API FastAPI.
•	Webhook WhatsApp externo → API.
•	API → PostgreSQL, Redis e Celery.
•	API/workers → MinIO/R2/S3.
•	Workers → parsers PDF, ffmpeg, OCR e LLMs externos.
•	API/workers → SMTP, Resend, Evolution API e webhook operacional.
•	Usuário interno/superusuário → dados globais, prompts, legislação e conhecimento.
•	Tenants → isolamento lógico por tenant_id; não há evidência suficiente de RLS ativo neste snapshot.
Ativos principais: documentos, PII cadastral, credenciais de portais, tokens JWT, chaves de IA, corpus legislativo, prompts, logs/auditoria, storage e orçamento de LLM.
Matriz da superfície
Superfície	Entrada	Controle observado	Bypass/limitação	Impacto
Upload de documentos	storage_key, nome, MIME, tamanho	extensão e MIME declarado	chave e tamanho não são vinculados ao presign; MIME não é detectado por conteúdo	leitura indevida, malware, DoS
Upload de intake	storage_key, metadata	tenant do draft	mesma referência de storage é aceita diretamente	isolamento/storage poisoning
Download	ID do documento	escopo por tenant	URL assinada concede acesso por 5 minutos	exposição se chave/registro forem comprometidos
WhatsApp webhook	JSON, telefone, media_url	HMAC somente se segredo configurado	segredo ausente aceita qualquer payload; URL é baixada diretamente	SSRF, ingestão falsa, custo e PII
Contratos/propostas	IDs de cliente/processo/proposta	autenticação interna	criação não valida que IDs pertencem ao tenant	corrupção cross-tenant
Legislação/RAG	texto, PDF, URL	usuário interno	documentos globais sem checagem de superusuário	poisoning do corpus e decisões incorretas
IA/OCR/transcrição	documentos e texto não confiável	limites de custo/tokens	texto é inserido diretamente no prompt	prompt injection, extração/manipulação
Login	credenciais	bcrypt, limite 5/min	token longo e sem revogação	abuso de conta
WebSocket	JWT e eventos Redis	JWT assinado	sem rate limit/conexão máxima visível	abuso de recursos
Dependências	lockfiles e requirements	npm lockfiles	Python sem lockfile/versionamento completo	supply-chain drift
Achados confirmados
P1 — Storage key não vinculada ao upload autorizado
DocumentConfirmRequest aceita storage_key arbitrário e confirm_upload persiste esse valor sem verificar se pertence ao presign, ao tenant ou ao processo: [document.py (line 21)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/schemas/document.py:21), [documents.py (line 176)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:176), [intake.py (line 819)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/intake.py:819).
Cenário: usuário obtém ou descobre uma chave válida de outro tenant e a confirma em processo próprio; workers baixam essa chave posteriormente.
Impacto: leitura/cópia cross-tenant, processamento de documento indevido e possível exposição de PII.
Aceite: confirmar somente chaves emitidas pelo servidor, com prefixo tenant/processo/draft correto; validar existência, tamanho real, MIME mágico e checksum antes de persistir.
P1 — IDs relacionais sem validação de tenant em contratos e propostas
Contratos usam process_id, client_id e proposal_id enviados pelo cliente sem validação completa de pertencimento: [contracts.py (line 157)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/contracts.py:157). Propostas fazem o mesmo: [proposals.py (line 219)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/proposals.py:219).
Cenário: usuário interno de um tenant referencia IDs pertencentes a outro tenant.
Impacto: corrupção de integridade, associação indevida de documentos/contratos e possível vazamento em fluxos posteriores.
Aceite: resolver cada entidade com filtro obrigatório por tenant_id; rejeitar relações entre tenants.
P1 — SSRF no download de mídia WhatsApp
A URL vem do payload externo e é baixada diretamente por httpx.get: [messaging.py (line 119)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/messaging.py:119). O webhook aceita payload sem assinatura quando o segredo não está configurado: [messaging.py (line 47)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/messaging.py:47), [messaging.py (line 273)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/messaging.py:273).
Cenário: atacante envia webhook forjado com media_url apontando para rede interna, metadata service ou endpoint administrativo.
Impacto: SSRF, exfiltração de respostas e gravação de conteúdo arbitrário no storage.
Aceite: HMAC obrigatório em produção; allowlist de hosts/protocolos; bloquear IPs privados, redirects não confiáveis e respostas acima do limite.
P1 — Escrita em corpus legislativo global por qualquer usuário interno
O endpoint grava tenant_id=None e não exige superusuário; upload/reindex também não têm controle administrativo: [legislation.py (line 31)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:31), [legislation.py (line 146)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:146).
Cenário: usuário interno injeta norma falsa ou altera o texto usado pelo RAG global.
Impacto: poisoning de conhecimento, respostas regulatórias incorretas para múltiplos tenants.
Aceite: escrita/reindex/upload restritos a papel curador/admin; versionamento, aprovação e hash de origem.
P2 — Upload sem inspeção real, limite efetivo ou antivírus
O backend valida somente extensão e MIME declarado: [documents.py (line 60)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:60). Upload legislativo lê o arquivo inteiro em memória sem limite visível: [legislation.py (line 65)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/legislation.py:65). O storage também aceita o conteúdo informado sem validação de magic bytes: [storage.py (line 151)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/storage.py:151).
Impacto: ZIP/document bombs, consumo de memória, arquivos maliciosos persistidos e parsers vulneráveis.
Aceite: limite real no storage/presign, HEAD obrigatório, magic-byte validation, decompression limits, sandbox de parsers e antivírus.
P2 — Replay e duplicação de webhooks
external_msg_id é armazenado, mas não há unicidade nem deduplicação antes de criar Message: [communication.py (line 31)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/models/communication.py:31), [messaging.py (line 221)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/messaging.py:221).
Impacto: mensagens e anexos duplicados, custo repetido e possível abuso operacional.
Aceite: idempotency key/índice único por provider, conta e external_msg_id; janela temporal e validação de timestamp.
P2 — Logout não revoga JWT
O endpoint apenas informa que o cliente deve apagar o token: [auth.py (line 245)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/auth.py:245). Em produção, o template configura expiração de até 1440 minutos: [render.yaml (line 126)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/render.yaml:126).
Impacto: token roubado permanece utilizável até expirar.
Aceite: refresh tokens rotativos, jti/denylist para revogação, revogação após troca de senha e TTL menor para access token.
P2 — Rate limit insuficiente
Há limites explícitos apenas para login e waitlist: [auth.py (line 66)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/auth.py:66), [waitlist.py (line 46)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/waitlist.py:46).
Não há limite equivalente visível para IA, upload/confirm, OCR, webhook, WebSocket ou geração de documentos.
Impacto: abuso de custo LLM, CPU, memória, filas e storage.
Aceite: limites por IP, usuário e tenant; quotas de jobs; limites de concorrência e tamanho.
Segredos potenciais
Reportados apenas por tipo, arquivo e linha:
•	Credenciais/defaults de banco e storage: [app/core/config.py (line 120)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/config.py:120).
•	Credenciais/defaults no Compose: [docker-compose.yml (line 80)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/docker-compose.yml:80).
•	Segredo JWT e chave de criptografia: [app/core/config.py (line 152)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/config.py:152).
•	Chaves de provedores de IA e mensageria: [app/core/config.py (line 183)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/config.py:183).
Nenhum valor do .env real foi aberto ou reproduzido.
Hardening, não vulnerabilidades confirmadas
•	SQL injection: não encontrei query de aplicação claramente concatenada com entrada externa; os usos dinâmicos observados são migrações ou valores inteiros limitados.
•	Command injection: chamadas ffmpeg/ffprobe usam lista de argumentos, sem shell=True: [audio_convert.py (line 100)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/audio_convert.py:100).
•	Traversal: a chave S3 usa UUID e prefixo controlado pelo servidor: [storage.py (line 98)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/storage.py:98).
•	XSS: não encontrei dangerouslySetInnerHTML/innerHTML no frontend pesquisado; React escapa texto por padrão.
•	CSRF: autenticação observada usa Bearer header, não cookie; não há vulnerabilidade CSRF confirmada.
•	Deserialização perigosa: YAML usa safe_load; não encontrei pickle ou equivalente perigoso.
•	Criptografia: bcrypt, JWT e Fernet estão presentes; a validação de produção exige tamanho/formato das chaves: [config.py (line 483)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/core/config.py:483).
•	Prompt injection: texto de documento é inserido diretamente no prompt: [document_extractor.py (line 180)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/document_extractor.py:180). É uma fraqueza de robustez P2, mas não confirmei exfiltração automática porque não há ferramenta externa exposta diretamente ao modelo neste caminho.
•	Dependências Python: requirements.txt não fixa versões; há lockfiles npm, mas não lockfile Python. [requirements.txt (line 1)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/requirements.txt:1)
•	Retenção/exportação: há predominância de soft-delete, por exemplo documentos: [documents.py (line 500)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/api/v1/documents.py:500). Não encontrei mecanismo geral comprovado de exportação LGPD, eliminação criptográfica, política de retenção ou backup automatizado no código auditado.
•	Logs: existem logs contendo filename, storage key e exceções: [storage.py (line 217)](/C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente/app/services/storage.py:217). Recomenda-se redaction e proibição de PII/URLs assinadas.
Não foram identificados P0 neste snapshot. A auditoria não prova configuração real de produção, RLS, IAM do storage, regras de firewall, antivírus, backups ou CI; esses pontos permanecem não determináveis por análise estática local.
AUD-12 — Auditoria de observabilidade e custos de IA
Escopo e revisão
•	Worktree limpo.
•	SHA auditado: 11ab1af (main, origin/main).
•	Não existe ref/commit identificado como AUD-01; portanto, o SHA acima foi usado como revisão efetiva.
•	Auditoria estática, somente leitura. Não executei chamadas externas, testes ou queries de banco.
•	Documentação foi ignorada como evidência.
Veredito
A implementação possui bons componentes isolados de rastreabilidade e custo, mas não existe uma trilha completa e uniforme por request → job → agente → chamada de IA.
Principais riscos:
1.	/health é apenas um endpoint estático; não testa banco, Redis, storage, fila ou worker.
2.	Embeddings e algumas chamadas diretas de IA não entram em AIJob.
3.	Jobs assíncronos de classificação/extração podem ficar persistidos sem tokens, modelo, provider, custo ou latência.
4.	request_id/trace_id HTTP não são propagados para Celery.
5.	Orçamento mensal padrão é zero, mas zero significa ilimitado.
6.	Não há retenção/expurgo observável para prompts, respostas brutas e logs.
7.	Não há métricas específicas para tokens, custo, retries, fallback, modelo/provider, embeddings ou áudio.
8.	Não há idempotência geral para jobs de IA; retries podem gerar duplicidade.
Rastreabilidade encontrada
Campo	Situação
Request ID	Existe em app/api/middleware.py:63-77; aceita X-Request-Id, mas gera ID de apenas 8 caracteres.
Trace ID	Existe contexto W3C básico em app/core/tracing.py:5-69, mas não há OpenTelemetry nem spans reais.
Usuário/tenant	Extraídos do JWT/header em app/api/middleware.py:38-51; workers recebem tenant_id e user_id explicitamente.
Caso/processo/documento	AIJob.entity_type/entity_id, app/models/ai_job.py:53-55.
Agente	agent_name, app/models/ai_job.py:74-76.
Chain	chain_trace_id, mas AgentContext cria ID separado em app/agents/base.py:38-48; não é o trace HTTP.
Prompt	Alguns prompts são persistidos em AIJob.input_payload; agentes centrais não gravam uniformemente o prompt completo.
Modelo/provider	Persistidos quando a resposta passa pelo BaseAgent; ausentes em diversos caminhos diretos.
Corpus/chunks	RAG filtra tenant e embedding_model em app/services/knowledge_catalog.py:333-364; não há vínculo universal desses chunks ao AIJob.
Tokens	Presentes em AIJob, mas não para embeddings, áudio ou vários jobs assíncronos.
Custo	cost_usd existe, mas pode virar 0.0 quando LiteLLM não conhece a tabela.
Latência	Persistida em alguns AIJob; métricas HTTP/Celery existem.
Retry/fallback	Logados parcialmente; não há contadores específicos nem persistência por tentativa.
Erro	AIJob.error e logs existem, mas auditoria é frequentemente best-effort.
Gate	Limites horário/mensal/job existem no gateway.
Persistência	AIJob e AuditLog existem; falha de persistência pode ser engolida.
Revisão humana	requires_review existe em agentes, especialmente legislação, mas não há métrica geral de gate/revisão.
Logs, métricas e tracing
Logs JSON incluem tenant, usuário, request, trace e span em app/core/logging.py:23-60.
Contudo:
•	não existe sanitização central;
•	há logs com e-mail, filename, storage key e trechos de output;
•	llm_classifier.py:191 registra até 200 caracteres do output;
•	app/api/v1/documents.py:151,339 registra nomes de arquivos;
•	exceções podem carregar conteúdo sensível;
•	a chave BYOK é mascarada somente no evento específico de ai_key_used, app/agents/base.py:308-327.
Métricas disponíveis em app/core/metrics.py:195-282:
•	HTTP;
•	Celery;
•	profundidade de fila;
•	alertas;
•	WebSocket;
•	resumos;
•	execução de agentes;
•	custo de agentes.
Ausências relevantes:
•	tokens de entrada/saída;
•	custo por modelo/provider;
•	custo de embeddings;
•	custo e duração de áudio;
•	retries;
•	fallbacks;
•	truncamento;
•	rejeições por orçamento;
•	jobs duplicados;
•	erros por provider;
•	quantidade de chunks recuperados;
•	latência de retrieval;
•	persistência falha.
/metrics apenas renderiza métricas locais/Redis compartilhadas em app/core/metrics.py:587-615; não há garantia de persistência entre processos para todas as métricas.
Health/readiness/liveness
/health é:
@app.get("/health")
def health_check():
    return {"status": "ok", ...}
Evidência: app/main.py:206-218.
Portanto, ele não testa:
•	PostgreSQL;
•	Redis;
•	Celery;
•	storage S3/R2/MinIO;
•	chaves de IA;
•	disponibilidade de provider;
•	migrations;
•	capacidade do worker;
•	profundidade de filas.
Há healthchecks separados apenas no Docker Compose:
•	PostgreSQL: docker-compose.yml:18-22;
•	Redis: docker-compose.yml:31-35;
•	MinIO: docker-compose.yml:48-53.
Não há endpoints distintos de readiness/liveness.
Todas as chamadas de IA encontradas
Operação	Gatilho/modelo	Limite/retry/fallback	Contabilização	Risco
LLM geral	ai_gateway.complete, modelos configuráveis; app/core/ai_gateway.py:303-335	Até 3 tentativas por modelo; fallback entre providers; retry adicional para truncamento, :347-395	AIResponse e AIJob somente em callers que persistem	Até 3 providers × 3 tentativas; custo parcial por fallback não é armazenado por tentativa
Classificação	llm_classifier.py:124	Prompt limitado a 2.000 caracteres, :116-120; fallback para regras	Persistido somente se save_job=True, :143-161	Falha do LLM pode desaparecer como resultado determinístico
Extração documental	document_extractor.py:192-220	Entrada limitada a EXTRACTOR_MAX_CHARS, default 30.000	Persistida quando save_job=True	Prompt completo não é persistido; falhas retornam {}
Agentes	BaseAgent.call_llm, app/agents/base.py:286-305	Limite global 4.096, teto 32.768; agentes podem sobrescrever	AIJob atualizado em :425-443	Apenas a última resposta fica no job; múltiplas chamadas no mesmo agente não são individualizadas
Legislação	Claude direto em app/agents/legislacao.py:282-288	ClaudeClient; 8.192 tokens por default	Retorno pode ser anexado ao AIJob do agente	Client direto bypassa parte dos gates/retries do gateway
OCR Gemini	ocr_pdf.py:151-172	Até 15 páginas, 3 tentativas/página, backoff de 4s	Um AIJob agregado em ocr_tasks.py:294-329	Custo por tentativa não é separado; falhas parciais agregadas
OCR OpenAI Vision	ocr_pdf.py:364-381	Fallback final; 50 MB PDF	AIJob agregado	Se custo LiteLLM falhar, custo vira zero
Embeddings OpenAI	embeddings.py:159-213,242-255	Batch de 100; até 6 tentativas por batch	Não há AIJob, tokens ou custo persistido	Reindexação e chamadas de query ficam fora do orçamento
Embeddings Gemini	embeddings.py:293-353	Até 6 tentativas por chunk; throttle de 2s	Não há contabilização central	Uma reindexação pode gerar milhares de chamadas sem auditoria de custo
Transcrição	ai_gateway.py:522-661	Whisper; sem fallback; arquivo máximo 25 MB; timeout 300s	AIJob de áudio agrega transcrição + resumo	Tokens não aplicáveis; retry do Celery pode repetir cobrança
Resumo de áudio	transcricao_audio.py:221-257	LLM opcional, falha silenciosa	Apenas custo agregado no AIJob de áudio	Modelo, tokens e latência do resumo não são persistidos separadamente
Ingestão SEMAD	scripts/ingest_corpus_semad.py:218-246	Modelo Gemini, 3 tentativas, timeout 60s	Não há AIJob	Chamada operacional direta fora do controle de tenant/orçamento
Orçamento e custos
A fórmula correta é:
custo_total =
  chamadas × tokens_entrada × preço_entrada
+ chamadas × tokens_saida × preço_saida
+ tokens_embedding × preço_embedding
+ minutos_audio × preço_audio
+ custo_das_tentativas_e_fallbacks
O código usa:
custo_LLM =
  tokens_in / 1.000.000 × preço_in
+ tokens_out / 1.000.000 × preço_out
E, para áudio:
custo_audio =
  audio_seconds / 60 × AUDIO_TRANSCRIPTION_USD_PER_MINUTE
O valor default de áudio no código é 0.006/min, app/core/config.py:357-372. Isso é configuração do SHA auditado, não validação de preço atual.
Gates encontrados:
•	limite horário default: $5, app/core/ai_gateway.py:98-128;
•	orçamento mensal default: 0.0, app/core/config.py:275-279;
•	limit <= 0 significa ilimitado, app/core/ai_gateway.py:176-193;
•	custo máximo geral por job: $0.10;
•	diagnóstico: $0.50;
•	legislação: $0.30 ou $5.00;
•	transcrição: $1.00.
O maior problema é que “orçamento zero” não bloqueia nada: significa ilimitado.
Além disso, AIJob.cost_usd aceita nulo e LiteLLM pode retornar 0.0 quando não conhece o modelo, app/core/ai_gateway.py:423-427,431-434.
Modelos de carga
Sem inventar preços, os limites codificados permitem:
Pequeno
•	classificação: prompt com até 2.000 caracteres;
•	modelo default configurável;
•	saída default de até 4.096 tokens;
•	até 3 tentativas por modelo;
•	fallback entre até 3 providers.
Médio
•	extração: até 30.000 caracteres;
•	OCR: até 15 páginas Gemini, com até 3 tentativas por página;
•	embeddings: lotes OpenAI de 100 itens;
•	Gemini: uma chamada por chunk, até 6 tentativas.
Pesado
•	diagnóstico: até 60.000 caracteres de trechos documentais;
•	legislação: contexto configurado em 900.000 tokens, podendo chegar a 1.900.000;
•	saída do diagnóstico até 32.768 tokens;
•	legislação pode usar Gemini Flash, Gemini Pro, OpenAI ou Claude.
Pior caso lógico
•	LLM geral: até 3 providers × 3 tentativas = 9 chamadas em falhas transitórias;
•	truncamento: até 4 tamanhos de saída até o teto de 32.768;
•	OCR Gemini: 15 páginas × 3 tentativas = 45 chamadas;
•	embeddings Gemini: chunks × 6 tentativas;
•	áudio: até 2 retries do Celery, além de eventual resumo LLM;
•	reindexação não possui orçamento central nem idempotência universal.
Tenant, duplicação e idempotência
Há proteções corretas:
•	workers filtram documento/processo por tenant_id;
•	busca RAG usa (tenant_id IS NULL OR tenant_id = :tenant_id), knowledge_catalog.py:360-364;
•	cache de áudio por checksum é restrito ao tenant, audio_tasks.py:170-181.
Riscos restantes:
•	index_text() aceita tenant_id=None, tornando o conteúdo global, knowledge_catalog.py:187-202;
•	embeddings não possuem AIJob nem orçamento;
•	jobs assíncronos não têm chave idempotente;
•	retries Celery podem criar nova execução;
•	force=True no áudio ignora cache e permite nova cobrança;
•	AIJob não possui constraint de unicidade por operação/idempotency key;
•	request_id e trace_id não são enviados nos argumentos das tasks.
Persistência incompleta
As tasks assíncronas criam AIJob em estado running, mas não copiam a resposta do gateway para os campos financeiros:
•	classificação: cria job em app/workers/ai_tasks.py:47-59, mas encerra sem preencher modelo, tokens, custo ou duração, :80-98;
•	extração: mesmo padrão em :150-191.
Consequentemente, esses jobs podem aparecer como concluídos sem custo real.
persist_ai_job() também retorna None e engole erro de persistência, app/services/ai_job_persistence.py:79-83.
Retenção e alertas
Não encontrei no código auditado:
•	TTL de AIJob;
•	expurgo de AuditLog;
•	retenção diferenciada para prompts/raw output;
•	política de anonimização;
•	alerta de orçamento mensal;
•	alerta de custo por provider;
•	alerta de retry storm;
•	alerta de fallback;
•	alerta de custo zero desconhecido;
•	alerta de embeddings fora do billing;
•	alerta de fila parada/worker ausente.
Alertas existentes cobrem principalmente latência HTTP, erro HTTP, Redis/realtime e falhas operacionais.
Variáveis ausentes
Para observabilidade e custo reais ainda faltam:
•	llm_call_id;
•	attempt_number;
•	parent_job_id;
•	request_id e trace_id no AIJob;
•	prompt_hash;
•	prompt_tokens por tentativa;
•	completion_tokens por tentativa;
•	cached_tokens;
•	retry_count;
•	fallback_from/fallback_to;
•	provider_request_id;
•	embedding_tokens;
•	embedding_cost_usd;
•	audio_seconds_billed;
•	custo conhecido versus estimado em todos os tipos;
•	versão do prompt/skill;
•	corpus version/chunk IDs no job;
•	idempotency key;
•	revisão humana concluída/data/revisor;
•	status de gate/budget antes e depois da chamada;
•	retenção/expiração.
Conclusão
A base possui bons mecanismos locais: AIJob, AuditLog com hash, logs estruturados, limites por tenant, cache de áudio, filtro RAG por tenant e métricas HTTP/Celery.
Mas a auditoria não demonstra observabilidade de custo real ponta a ponta. O maior risco financeiro é a combinação de:
embeddings sem AIJob
+ orçamento mensal zero = ilimitado
+ custo desconhecido convertido em 0.0
+ retries/fallbacks não individualizados
+ jobs assíncronos sem copiar métricas
+ ausência de idempotência
Esses pontos impedem afirmar, neste SHA, quanto custou uma requisição, quais chamadas foram feitas, quantas foram retries/fallbacks e se todo consumo foi atribuído ao tenant correto.
Não foi possível confirmar comportamento em produção, configuração real de providers, execução de filas, estado do banco, retenção efetiva ou preços atuais — somente o comportamento codificado no SHA auditado.
AUD-13 — resultado
Auditoria somente leitura no HEAD 11ab1af (main, alinhado a origin/main). Não executei testes, CI, build, migrations ou scanners.
Conclusão: há boa densidade de testes unitários e de API, mas a capacidade de detectar falhas críticas é inferior ao aparente. Os maiores riscos são:
1.	cobertura de código explicitamente não bloqueante;
2.	migrations não exercitadas pelos testes funcionais;
3.	ausência de teste RLS real com SET ROLE;
4.	E2E externo praticamente inexistente;
5.	ausência de SAST, secrets scan, dependency scan e SBOM;
6.	mocks substituindo storage, Redis, Celery e LLM;
7.	downgrades de enums deliberadamente sem efeito;
8.	CI potencialmente verde apesar dessas lacunas.
Inventário das suites
Área	Evidência	O que prova	Limitação
Banco/modelos	tests/models/, tests/api/, tests/services/	Regras ORM, constraints e endpoints contra PostgreSQL	Fixture usa Base.metadata.create_all() (tests/conftest.py:63-107), não o schema das migrations
Tenant	tests/api/test_tenant_isolation.py:40-117	Token com tenant incorreto e leitura cross-tenant retornam 403/404	Não prova RLS do banco
Autorização	tests/api/test_auth.py, tests/api/test_credentials.py	Login, perfis, isolamento de credenciais	Poucos testes sistemáticos por matriz papel × endpoint × método
Fluxos	tests/api/ — 47 arquivos; tests/e2e/ — 3 arquivos	Vários fluxos HTTP e estados de domínio	E2E usa TestClient e dependências substituídas
Concorrência	buscas por concurr, race, threading, asyncio.gather	Há testes de retry e idempotência	Não há teste concorrente real com duas transações/processos
Agentes	tests/agents/ — 26 arquivos	Parser, cadeia, estados, revisão e falhas sintéticas	LLM, custo e persistência frequentemente mockados
Schemas	tests/schemas/test_stage_output.py, tests/models/	Shapes, validação e invariantes	Não cobre todos os contratos de resposta da API
RAG	tests/services/test_knowledge_catalog_search.py, test_rag_ivfflat_probes.py	Filtros de modelo, espaço vetorial e busca	Embeddings são substituídos; não prova qualidade semântica
Citações	tests/services/test_citation_evaluator.py, tests/agents/test_*citation*	Matching de fonte, chunk_id, fonte ausente	Não há golden corpus de precisão/recall nem avaliação adversarial ampla
Upload/OCR/áudio	tests/workers/test_ocr_tasks.py, test_audio_tasks.py, test_storage_service.py	Estados persistidos, custo, dispatch e falhas controladas	MinIO/S3, Celery, WebSocket e provedor de IA são fakeados
Segurança	tests/api/test_auth.py, test_credentials.py, test_waitlist_endpoint.py	Hash, segredo mascarado, rate limit e credenciais	Não há SAST, fuzzing, scan de segredos ou dependency scan no CI
Custos	tests/core/test_ai_gateway.py, tests/api/test_agents_budget.py	Limite por job, orçamento mensal e retry	Não prova corrida entre chamadas nem custo real do provider
Observabilidade	tests/api/test_observability.py, tests/test_alerts.py	Formato de métricas, traceparent e webhook	Não prova coleta/alerta em stack implantada
Frontend	frontend/src/**/*.test.{ts,tsx}; workflow roda Vitest (ci.yml:175-176)	Componentes, store, utils e alguns fluxos de UI	Sem browser E2E; portal e mobile não têm testes
E2E	tests/e2e/	Dois fluxos internos com TestClient	Não envolve browser, Redis, storage, worker ou deploy
Matriz de risco priorizada
Risco	Teste existente	Arquivo	Asserção atual	Cobertura real	Lacuna / teste que deveria falhar
P0 — migration quebrada passa despercebida	Migration job	.github/workflows/ci.yml:94-142	upgrade head, downgrade base, upgrade head	Exercita Alembic em banco vazio	Não testa upgrade de banco legado com dados
P0 — migrations vazias/incompletas	Testes de modelos	tests/conftest.py:63-107	Base.metadata.create_all()	Cria tabelas a partir dos modelos atuais	Pode passar mesmo com migration ausente ou incompatível
P0 — rollback falso	Migration check	.github/workflows/ci.yml:140-142	Comandos terminam sem erro	Só prova reversibilidade estrutural parcial	b3d5...:32-35, d8b3...:31-38, a3b5...:pass e c8d4...:pass têm downgrade no-op; fixture: aplicar enum + inserir valor + downgrade + assert valor removido ou downgrade explicitamente bloqueado
P0 — RLS inexistente ou permissivo	test_tenant_isolation	tests/api/test_tenant_isolation.py:40-117	404/403 em endpoints	Filtro da aplicação/JWT	Não há SET ROLE, policy, BYPASSRLS ou conexão não-owner; fixture: dois tenants, role não-owner, SELECT/UPDATE direto; assert zero linhas cross-tenant
P0 — “E2E” mascarado	Intake/document flow	tests/e2e/test_intake_flow.py, tests/conftest.py:126-146	Status HTTP e entidades	API em processo, banco transacional	Redis é substituído por fake_connect_redis; storage, worker e provider não são reais; fixture: stack real API+DB+Redis+MinIO, upload efetivo, worker processando, assert documento e evento final
P0 — upload autorizado, objeto errado	OCR/storage	tests/workers/test_ocr_tasks.py:101-168	download_bytes fake e AIJob persistido	Banco real; storage falso	Não prova presigned URL, tenant prefix, checksum nem ACL; fixture: objeto tenant A, request tenant B, assert 403/404 e nenhum download
P0 — duplicação sob corrida	OCR/idempotência	tests/workers/test_ocr_tasks.py:293-345	Um twin evita AIJob	Execução sequencial	Não prova duas chamadas simultâneas; fixture: duas transações com mesmo SHA, barreira antes do commit, assert exatamente um job/documento efetivo
P0 — retry cria efeitos duplicados	Retry	tests/workers/test_agent_tasks_retry.py	Inspeciona self.retry mockado	Chamada direta da task	Não executa Celery real; fixture: broker real, task falha após commit parcial, retry, assert uma única escrita
P0 — CI verde com tipagem quebrada	Mypy	.github/workflows/ci.yml:35-42	continue-on-error: true	Mypy roda, mas não bloqueia	Erro de tipo pode entrar em main; tornar bloqueante por pacote ou baseline versionado
P0 — cobertura abaixo do requisito	Coverage	pyproject.toml:47-50, .github/workflows/ci.yml:87-91	Configuração diz 70%; CI usa --cov-fail-under=0	Relatório informativo apenas	Mutação em autorização, tenant e estados pode passar; exigir 70% ou thresholds por domínio
P1 — IA sempre “passa” com provider quebrado	Gateway/agentes	tests/core/test_ai_gateway.py, tests/agents/test_golden_agents.py:66-74,103-105	MagicMock/patch retornam respostas controladas	Parser e orquestração	Não testa schema/provider/timeouts reais; fixture: provider HTTP fake com payload inválido, timeout, 429 e resposta truncada; assert fallback, custo e estado
P1 — RAG incorreto mas teste verde	Knowledge catalog	tests/services/test_knowledge_catalog_search.py:107-165	Filtro por modelo e recusa de espaço incompatível	Busca SQL e embedding fake	Não mede ranking, recall, documentos adversariais ou citação incorreta; fixture golden com documentos quase idênticos e fonte conflitante
P1 — golden stale	Golden agents	tests/agents/test_golden_agents.py:1-14	Shape e contagens esperadas	Parser determinístico sobre arquivos versionados	Não há hash/versionamento do dataset nem avaliação de qualidade; mudança conjunta de golden e parser pode mascarar regressão
P1 — autorização incompleta	Auth/credentials	tests/api/test_auth.py, tests/api/test_credentials.py	Alguns perfis e cross-tenant	Casos positivos/negativos pontuais	Falta matriz de endpoints, métodos, objetos inexistentes e enumeração 403/404
P1 — schema só valida caminho feliz	Schemas	tests/schemas/test_stage_output.py	Campos e shapes válidos	Casos selecionados	Adicionar payloads com campos extras, null, Unicode extremo, listas enormes e tipos numéricos inválidos
P1 — frontend quebra interação humana	Vitest	frontend/vitest.config.ts, frontend/src/**/*.test.*	Componentes isolados	Node/jsdom apenas quando declarado por teste	Não há Playwright/Cypress no workflow; gesto drag/drop, upload real e navegação multi-tela não são exercitados
P1 — portal cliente sem regressão funcional	Portal CI	.github/workflows/ci.yml:184-209	ESLint, tsc, build	Compilação estática	client-portal/package.json não tem script de teste; nenhuma asserção de UI
P1 — mobile sem regressão funcional	Mobile CI	.github/workflows/ci.yml:214-236	Expo lint e tsc	Estático	Não há testes de componente, integração ou dispositivo
P1 — segurança de supply chain não detectada	CI	.github/workflows/ci.yml inteiro	Nenhum scanner dedicado	Apenas npm ci/pip install	Ausentes CodeQL/SAST, gitleaks, pip-audit/npm audit, Trivy/Grype e SBOM
P1 — deploy aplica migration mas não valida aplicação	Render	render.yaml:35-44	preDeployCommand: alembic upgrade head	Deploy executa migration	Não há smoke pós-deploy, health funcional, rollback ou compatibilidade app/schema
P2 — observabilidade falsa	Alertas	tests/test_alerts.py, tests/api/test_observability.py	Payload/header e chamada mockada	Unidade de formatação	Não prova Prometheus, logs, tracing distribuído ou alerta recebido
P2 — determinismo contaminado	Fixture global	tests/conftest.py:110-163	Rollback e reset do limiter	Isolamento nominal por teste	Testes que fazem commit() podem escapar da transação esperada; não há execução paralela/ordem aleatória configurada
P2 — contrato frontend/backend divergente	Frontend tests	frontend/src/**/*.test.*	Estados locais e mocks	UI isolada	Não há geração/verificação OpenAPI nem teste contra API real
Testes prioritários a adicionar
1.	RLS real
o	Fixture: PostgreSQL migrado, role vereda_app sem ownership/BYPASSRLS, tenants A e B.
o	Ação: SET ROLE vereda_app; consultar e atualizar objeto de A usando contexto B.
o	Asserção: SELECT retorna zero; UPDATE afeta zero; tentativa cross-tenant gera erro/404 conforme contrato.
2.	Upgrade de banco legado
o	Fixture: banco criado em cada revisão relevante, com dados representativos.
o	Ação: aplicar migrations uma a uma até head.
o	Asserção: nenhuma perda de dados, constraints presentes, enums e índices corretos.
3.	Concorrência de idempotência
o	Fixture: duas conexões independentes e mesma chave de deduplicação.
o	Ação: iniciar duas operações simultâneas usando barreira.
o	Asserção: uma operação vence; a outra retorna resultado idempotente; não há duplicação nem efeitos parciais.
4.	E2E real de upload
o	Fixture: API, PostgreSQL, Redis, MinIO e worker reais.
o	Ação: presign → PUT do arquivo → confirmação → processamento assíncrono.
o	Asserção: arquivo correto, tenant correto, checksum correto, AIJob único, evento final emitido.
5.	Adversarial de autorização
o	Fixture: usuários interno, cliente, inativo, superuser e dois tenants.
o	Ação: variar JWT, tenant, client_id, objeto inexistente e método HTTP.
o	Asserção: contrato consistente de 401/403/404; nenhuma enumeração de objeto.
6.	Golden RAG/citações
o	Fixture: corpus com fontes conflitantes, fonte inexistente, documento quase duplicado e jurisdições distintas.
o	Ação: consultas determinísticas com embeddings fixos.
o	Asserção: fonte correta, nenhuma citação órfã, recusa quando não há evidência, ranking dentro do limite definido.
7.	CI negativo
o	Introduzir temporariamente erro de tipo, segredo fictício, dependência vulnerável conhecida e falha de migration.
o	Asserção: cada job requerido falha e impede merge.
Verificado, não determinável e não verificado
Verificado por leitura:
•	único workflow em .github/workflows/ci.yml;
•	mypy advisory;
•	coverage configurada em 70%, mas CI usa limiar zero;
•	migrations em banco separado do fixture funcional;
•	downgrades de enum no-op;
•	frontend interno tem Vitest no CI;
•	portal e mobile não têm testes no CI;
•	ausência de jobs explícitos de SAST, secrets scan, dependency scan e SBOM;
•	ausência de RLS real nos testes pesquisados.
Não determinável sem execução:
•	se o CI remoto estava verde no SHA;
•	se a imagem PostGIS/pgvector builda atualmente;
•	se a suíte completa termina;
•	cobertura percentual real atual;
•	se os testes frontend são estáveis em runner limpo;
•	se Render executou rollback ou smoke pós-deploy.
Portanto, não é correto declarar esse SHA “verde” apenas pela configuração. O CI bloqueia lint Ruff, testes backend, migrations e build frontend quando falham, mas permite falhas de tipagem, aceita cobertura abaixo da meta e não verifica várias fronteiras críticas de produção.
AUD-14 — Consolidação final
Resultado e prontidão
Status: não pronto para consolidação válida.
Os artefatos AUD-01 a AUD-13 não estão presentes no checkout atual, nem foram encontrados com esses identificadores nos arquivos rastreados. Portanto, não é possível consolidar achados, deduplicar causas, recalibrar severidades ou atribuir IDs de origem sem inventar evidência.
O checkout analisado está em:
SHA: 11ab1afcd133042f985918ff855fc029684b3fb0
Branch: main
Worktree: limpo
Evidência encontrada
Foram encontrados somente documentos gerais de auditoria do fluxo ISIS:
•	AUDITORIA_FLUXO_ISIS_2026-08-06.md
o	commit do arquivo: 50d8c7e3ed656b000eba9b221acc374811ff86d5
o	evidência: cabeçalho nas linhas 1–13
o	declara auditoria read-only e medição em produção.
•	docs/trabalhos/auditoria_fluxo_validacoes_isis_2026-08-06.md
o	commit do arquivo: 19223ef1b0272e68533b77acf352564a6a934702
o	evidência: cabeçalho nas linhas 1–13
o	também declara auditoria read-only.
Esses documentos não são identificados como AUD-01 a AUD-13. Seus SHAs de introdução também divergem entre si, embora o estado atual esteja consolidado no SHA 11ab1af....
Confirmações possíveis
Item	Estado
AUD-01 a AUD-13 presentes	Não verificável / não encontrados
SHA único dos AUD-01 a AUD-13	Não verificável
Evidência original por arquivo, símbolo e linha	Ausente para os AUDs
Deduplicação por causa raiz	Não executável com segurança
Top 10 riscos consolidados	Não determinável
Matriz causa raiz → sintomas → componentes	Não determinável
Plano P0–P3 consolidado	Não determinável
Critérios de aceite derivados dos AUDs	Não determinável
Alterações no repositório	Nenhuma
Conflito de SHA identificado
Há pelo menos dois documentos de auditoria relacionados, introduzidos por SHAs diferentes:
50d8c7e3ed656b000eba9b221acc374811ff86d5
19223ef1b0272e68533b77acf352564a6a934702
Eles não podem ser tratados como um mesmo pacote AUD sem os relatórios originais e sua identificação formal.
Conclusão
Não aceito declarar AUD-14 concluído. Faltam os insumos primários necessários:
1.	AUD-01 até AUD-13 completos;
2.	SHA declarado em cada relatório;
3.	evidência original contendo arquivo, símbolo e linha;
4.	distinção entre achado confirmado, hipótese e narrativa;
5.	resultados de runtime read-only, quando aplicáveis.
Com os relatórios primários disponíveis, a consolidação poderá ser feita preservando a rastreabilidade exigida e separando corretamente achados confirmados, estruturais, prováveis e não verificáveis.
