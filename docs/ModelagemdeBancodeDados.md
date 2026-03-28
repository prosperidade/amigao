Modelagem de Banco de Dados v2 — MVP
1. Princípios da modelagem
Esta modelagem nasce com 7 regras:
1.	multi-tenant desde o dia 1 
2.	arquivo pesado fora do banco; no banco só metadado e referência de storage 
3.	geodados nativos com PostGIS, porque imóvel, APP, RL e sobreposição são core do produto 
4.	RAG regulatório dentro do PostgreSQL com pgvector, evitando serviço vetorial externo no MVP 
5.	auditabilidade total, incluindo ações humanas e de IA 
6.	customização por tenant, inclusive credenciais próprias de APIs/IA 
7.	preparação para GovTech, mas sem contaminar o núcleo do MVP com complexidade excessiva 
________________________________________
2. Estratégia de schemas
2.1 Schemas recomendados
core
núcleo transacional do produto:
•	tenants 
•	users 
•	roles 
•	clients 
•	properties 
•	processes 
•	tasks 
•	documents 
•	communications 
•	proposals 
•	contracts 
•	billing 
•	integrations 
•	audit_log 
ai
camada de IA:
•	jobs 
•	prompts 
•	model_usage 
•	extracted_entities 
•	rag_sources 
•	rag_chunks 
•	ai_decisions 
geo
camada geoespacial:
•	protected_areas 
•	embargo_areas 
•	hydrography 
•	biome_layers 
•	property_overlaps 
•	geospatial_import_jobs 
gov
camada futura GovTech:
•	órgãos 
•	fila_analise 
•	pareceres 
•	analistas 
support
tabelas auxiliares:
•	enums parametrizáveis 
•	templates 
•	tags 
•	webhooks 
•	feature_flags 
________________________________________
3. Estratégia multi-tenant
abordagem escolhida
Para o MVP, usar coluna tenant_id em todas as tabelas de negócio, como já proposto na documentação base 
por que essa abordagem
•	mais simples de operar 
•	reduz complexidade de migrations 
•	facilita analytics cross-tenant interno 
•	permite evoluir mais rápido 
regra obrigatória
Toda tabela de negócio deve ter:
•	id UUID 
•	tenant_id UUID NOT NULL 
•	created_at 
•	updated_at 
•	opcionalmente deleted_at 
________________________________________
4. Entidades principais do MVP
________________________________________
4.1 core.tenants
Representa cada empresa cliente do SaaS.
campos principais
•	id 
•	name 
•	legal_name 
•	document_number 
•	tenant_type 
o	consultoria 
o	cooperativa 
o	parceiro 
o	white_label 
•	plan 
•	status 
•	primary_color 
•	logo_file_key 
•	settings_json 
•	created_at 
•	updated_at 
observações
Aqui entra a configuração de white-label e limites de uso.
________________________________________
4.2 core.tenant_settings
Separar configurações do tenant da tabela principal.
campos
•	id 
•	tenant_id 
•	timezone 
•	locale 
•	currency 
•	storage_provider 
•	ai_billing_mode 
o	internal 
o	own_key 
•	allow_client_portal 
•	allow_whatsapp 
•	allow_email 
•	allow_field_app 
•	settings_json 
________________________________________
4.3 core.integration_accounts
Conta/configuração por tenant para integrações externas.
campos
•	id 
•	tenant_id 
•	provider 
o	openai 
o	google_ai 
o	resend 
o	smtp 
o	zapi 
o	evolution 
o	google_drive 
o	mapbiomas 
o	sicar_proxy 
o	signature_provider 
o	payment_provider 
•	label 
•	status 
•	credential_ref 
•	config_json 
•	last_sync_at 
•	created_at 
observação crítica
Nunca guardar segredo puro nesta tabela. Guardar apenas referência segura:
•	secret manager 
•	KMS 
•	vault 
________________________________________
4.4 core.users
Usuários internos e externos.
campos
•	id 
•	tenant_id 
•	person_type 
•	name 
•	email 
•	phone 
•	password_hash 
•	status 
•	is_portal_user 
•	last_login_at 
•	created_at 
•	updated_at 
•	deleted_at 
________________________________________
4.5 core.roles
campos
•	id 
•	tenant_id 
•	name 
•	description 
•	is_system_role 
4.6 core.permissions
campos
•	id 
•	key 
•	module 
•	description 
4.7 core.user_roles
campos
•	user_id 
•	role_id 
4.8 core.role_permissions
campos
•	role_id 
•	permission_id 
papéis mínimos do MVP
•	admin 
•	gestor 
•	consultor 
•	técnico_campo 
•	parceiro 
•	cliente_portal 
A documentação já previa RBAC forte e perfis separados, então aqui só estamos formalizando isso melhor no modelo 
________________________________________
5. CRM e cadastro
5.1 core.clients
Cliente dono da demanda.
campos
•	id 
•	tenant_id 
•	client_type 
o	pf 
o	pj 
•	name 
•	legal_name 
•	cpf_cnpj 
•	email 
•	phone 
•	secondary_phone 
•	birth_date 
•	status 
o	lead 
o	active 
o	inactive 
o	delinquent 
•	source_channel 
•	notes 
•	extra_json 
•	created_at 
•	updated_at 
observação
CPF/CNPJ deve ser protegido com criptografia de coluna ou tokenização, alinhado com a preocupação de segurança já descrita na arquitetura 
________________________________________
5.2 core.client_addresses
campos
•	id 
•	tenant_id 
•	client_id 
•	address_type 
•	street 
•	number 
•	district 
•	city 
•	state 
•	zip_code 
•	country 
•	is_primary 
________________________________________
5.3 core.client_contacts
Permite múltiplos contatos por cliente.
campos
•	id 
•	tenant_id 
•	client_id 
•	name 
•	role_name 
•	email 
•	phone 
•	whatsapp 
•	is_primary 
________________________________________
6. Imóveis rurais e geografia
6.1 core.properties
Entidade central fundiária.
campos
•	id 
•	tenant_id 
•	client_id 
•	name 
•	registry_number 
•	ccir 
•	nirf 
•	car_code 
•	car_status 
•	total_area_ha 
•	municipality 
•	state 
•	biome 
•	has_embargo 
•	status 
•	notes 
•	created_at 
•	updated_at 
________________________________________
6.2 core.property_geometries
Separar geometria da tabela principal é uma boa decisão.
campos
•	id 
•	tenant_id 
•	property_id 
•	geometry_type 
o	perimeter 
o	app 
o	rl 
o	usage_area 
•	source 
o	manual 
o	uploaded_shape 
o	sicar 
o	sigef 
o	map_import 
•	srid 
•	geom GEOMETRY(MULTIPOLYGON, 4674) 
•	area_ha_computed 
•	version 
•	is_active 
•	created_at 
por que separar
•	histórico de versões 
•	múltiplas geometrias por imóvel 
•	comparações futuras 
•	simplifica revisão técnica 
________________________________________
6.3 core.property_documents
Vínculo específico entre imóvel e documento.
campos
•	id 
•	tenant_id 
•	property_id 
•	document_id 
•	document_purpose 
________________________________________
6.4 geo.property_overlaps
Tabela materializada de resultados geoespaciais.
campos
•	id 
•	tenant_id 
•	property_id 
•	layer_type 
•	layer_ref_id 
•	overlap_area_ha 
•	overlap_percent 
•	analysis_date 
•	analysis_job_id 
motivo
Não recalcular tudo em toda tela.
A modelagem base já prevê consultas PostGIS de interseção; aqui estamos persistindo resultado para performance e histórico 
________________________________________
7. Processos ambientais
7.1 core.process_types
Cadastro parametrizável de tipos de processo.
campos
•	id 
•	tenant_id 
•	code 
•	name 
•	category 
•	requires_property 
•	default_sla_days 
•	active 
________________________________________
7.2 core.processes
A entidade central do sistema.
campos
•	id 
•	tenant_id 
•	client_id 
•	property_id 
•	process_type_id 
•	title 
•	description 
•	status 
o	triagem 
o	diagnostico 
o	planejamento 
o	execucao 
o	protocolo 
o	acompanhamento 
o	pendencia 
o	concluido 
o	cancelado 
•	priority 
•	urgency 
•	responsible_user_id 
•	destination_agency 
•	external_protocol_number 
•	opened_at 
•	due_date 
•	closed_at 
•	ai_summary 
•	risk_score 
•	created_at 
•	updated_at 
•	deleted_at 
observação
A documentação técnica já colocava processo/case como unidade central de trabalho. Aqui só refinamos para escalar melhor o produto 
________________________________________
7.3 core.process_status_history
Histórico de transições.
campos
•	id 
•	tenant_id 
•	process_id 
•	from_status 
•	to_status 
•	changed_by_user_id 
•	changed_by_ai_job_id 
•	reason 
•	created_at 
________________________________________
7.4 core.process_participants
campos
•	id 
•	tenant_id 
•	process_id 
•	user_id 
•	participant_role 
________________________________________
7.5 core.process_tags
campos
•	id 
•	tenant_id 
•	process_id 
•	tag 
________________________________________
8. Workflow e tarefas
8.1 core.tasks
campos
•	id 
•	tenant_id 
•	process_id 
•	parent_task_id 
•	title 
•	description 
•	task_type 
o	campo 
o	escritorio 
o	protocolo 
o	documento 
o	revisão_ia 
o	cliente 
o	integração 
•	status 
o	backlog 
o	a_fazer 
o	em_progresso 
o	aguardando 
o	revisao 
o	concluida 
o	cancelada 
•	priority 
•	assigned_user_id 
•	assigned_partner_id 
•	origin 
o	manual 
o	rule 
o	ai 
o	webhook 
•	due_at 
•	completed_at 
•	created_by_user_id 
•	created_by_ai_job_id 
•	created_at 
•	updated_at 
________________________________________
8.2 core.task_dependencies
campos
•	id 
•	tenant_id 
•	task_id 
•	depends_on_task_id 
observação
Melhor do que array de dependências para consulta, integridade e workflow.
________________________________________
8.3 core.task_comments
campos
•	id 
•	tenant_id 
•	task_id 
•	user_id 
•	comment 
•	created_at 
________________________________________
8.4 core.task_attachments
campos
•	id 
•	tenant_id 
•	task_id 
•	document_id 
________________________________________
9. Gestão documental
A documentação já acertou em cheio aqui: binário no storage, metadado no banco 
9.1 core.documents
campos
•	id 
•	tenant_id 
•	client_id 
•	property_id 
•	process_id 
•	task_id 
•	document_type 
•	document_category 
•	original_file_name 
•	storage_key 
•	storage_provider 
•	mime_type 
•	extension 
•	file_size_bytes 
•	checksum_sha256 
•	version_number 
•	source 
o	upload_manual 
o	email 
o	whatsapp 
o	integration 
o	generated_ai 
o	field_app 
•	ocr_status 
o	pending 
o	processing 
o	done 
o	failed 
o	not_required 
•	extraction_status 
•	confidence_score 
•	review_required 
•	uploaded_by_user_id 
•	created_at 
•	updated_at 
________________________________________
9.2 core.document_versions
campos
•	id 
•	tenant_id 
•	document_id 
•	version_number 
•	storage_key 
•	checksum_sha256 
•	created_by_user_id 
•	created_at 
________________________________________
9.3 core.document_extractions
Resultado estruturado do OCR + parser.
campos
•	id 
•	tenant_id 
•	document_id 
•	extractor_job_id 
•	document_type_detected 
•	raw_text 
•	normalized_text 
•	structured_data_json 
•	confidence_score 
•	human_validated 
•	validated_by_user_id 
•	validated_at 
•	created_at 
ponto importante
Isso resolve o seu risco de OCR:
•	guarda texto bruto 
•	guarda texto normalizado 
•	guarda estrutura 
•	permite reprocessar depois com modelo melhor 
________________________________________
9.4 core.document_review_queue
Fila de revisão humana para documentos com baixa confiança.
campos
•	id 
•	tenant_id 
•	document_id 
•	reason 
•	priority 
•	status 
•	assigned_user_id 
•	created_at 
•	resolved_at 
regra sugerida
•	confiança abaixo de 80 → entra revisão automática
A arquitetura já sugere esse cuidado com OCR ruim antes de jogar no LLM 
________________________________________
10. Comunicação
10.1 core.communication_threads
campos
•	id 
•	tenant_id 
•	client_id 
•	process_id 
•	channel 
o	whatsapp 
o	email 
o	portal 
o	internal 
•	subject 
•	status 
•	external_thread_ref 
•	created_at 
•	updated_at 
________________________________________
10.2 core.messages
campos
•	id 
•	tenant_id 
•	thread_id 
•	direction 
o	inbound 
o	outbound 
•	channel 
•	sender_type 
o	client 
o	user 
o	system 
o	ai 
•	sender_ref_id 
•	message_text 
•	message_payload_json 
•	attachment_count 
•	sent_at 
•	delivered_at 
•	read_at 
•	created_at 
________________________________________
10.3 core.message_attachments
campos
•	id 
•	tenant_id 
•	message_id 
•	document_id 
________________________________________
11. Comercial: propostas e contratos
11.1 core.proposals
campos
•	id 
•	tenant_id 
•	client_id 
•	process_id 
•	title 
•	status 
o	draft 
o	sent 
o	viewed 
o	accepted 
o	rejected 
o	expired 
•	total_amount 
•	currency 
•	valid_until 
•	generated_by_ai_job_id 
•	created_by_user_id 
•	created_at 
•	updated_at 
________________________________________
11.2 core.proposal_items
campos
•	id 
•	tenant_id 
•	proposal_id 
•	description 
•	quantity 
•	unit_price 
•	total_price 
•	billing_stage 
•	sort_order 
________________________________________
11.3 core.contracts
campos
•	id 
•	tenant_id 
•	client_id 
•	process_id 
•	proposal_id 
•	title 
•	status 
o	draft 
o	awaiting_signature 
o	signed 
o	cancelled 
•	signature_provider 
•	external_signature_ref 
•	effective_date 
•	expires_at 
•	generated_by_ai_job_id 
•	created_by_user_id 
•	created_at 
•	updated_at 
________________________________________
11.4 core.contract_documents
campos
•	id 
•	tenant_id 
•	contract_id 
•	document_id 
•	document_role 
o	draft 
o	signed 
o	annex 
________________________________________
12. Cobrança
12.1 core.billing_accounts
campos
•	id 
•	tenant_id 
•	provider 
•	external_customer_ref 
•	status 
•	created_at 
12.2 core.invoices
campos
•	id 
•	tenant_id 
•	client_id 
•	process_id 
•	contract_id 
•	provider 
•	external_invoice_ref 
•	amount 
•	currency 
•	status 
•	due_date 
•	paid_at 
•	created_at 
12.3 core.usage_charges
Custos variáveis repassáveis.
campos
•	id 
•	tenant_id 
•	client_id 
•	process_id 
•	source_type 
o	ai 
o	ocr 
o	data_broker 
o	whatsapp 
o	signature 
•	source_ref_id 
•	quantity 
•	unit_cost 
•	total_cost 
•	currency 
•	billable 
•	created_at 
isso conversa diretamente com sua estratégia
o custo de IA e integrações pode ser por uso, e cada tenant pode até usar sua própria chave/conta.
________________________________________
13. Portal do cliente
13.1 core.client_portal_access
campos
•	id 
•	tenant_id 
•	client_id 
•	user_id 
•	status 
•	invited_at 
•	activated_at 
•	last_access_at 
13.2 core.portal_events
campos
•	id 
•	tenant_id 
•	client_id 
•	process_id 
•	event_type 
•	title 
•	description 
•	visibility 
•	created_by_user_id 
•	created_at 
________________________________________
14. Mobile e offline
Como o app já nasce com uso em campo, eu recomendo modelagem explícita para sincronização.
14.1 core.field_visits
campos
•	id 
•	tenant_id 
•	process_id 
•	property_id 
•	assigned_user_id 
•	status 
•	scheduled_at 
•	started_at 
•	finished_at 
•	notes 
•	created_at 
________________________________________
14.2 core.field_records
campos
•	id 
•	tenant_id 
•	field_visit_id 
•	record_type 
o	photo 
o	audio 
o	note 
o	form_answer 
o	gps_point 
o	polygon 
•	payload_json 
•	captured_at 
•	captured_by_user_id 
•	sync_status 
o	pending 
o	synced 
o	conflict 
o	failed 
•	source_device_id 
•	created_at 
________________________________________
14.3 core.sync_devices
campos
•	id 
•	tenant_id 
•	user_id 
•	device_uuid 
•	platform 
•	app_version 
•	last_sync_at 
•	status 
________________________________________
14.4 core.sync_conflicts
campos
•	id 
•	tenant_id 
•	entity_type 
•	entity_id 
•	device_id 
•	server_payload_json 
•	client_payload_json 
•	resolution_status 
•	resolved_by_user_id 
•	created_at 
recomendação
No MVP, conflito simples:
•	server wins para metadado sensível 
•	append-only para notas/fotos/formulários
Isso reduz bastante o risco do offline. 
________________________________________
15. IA e observabilidade
A documentação original já prevê jobs, agentes e custo por tokens 
15.1 ai.jobs
campos
•	id 
•	tenant_id 
•	agent_type 
o	atendente 
o	extrator 
o	regulatorio 
o	orquestrador 
o	redator 
o	vigia 
•	trigger_type 
•	entity_type 
•	entity_id 
•	status 
o	queued 
o	processing 
o	done 
o	failed 
o	timeout 
•	input_payload_json 
•	output_payload_json 
•	error_message 
•	started_at 
•	finished_at 
•	created_at 
________________________________________
15.2 ai.model_usage
campos
•	id 
•	tenant_id 
•	job_id 
•	provider 
•	model_name 
•	prompt_version 
•	input_tokens 
•	output_tokens 
•	cached_tokens 
•	estimated_cost_usd 
•	latency_ms 
•	created_at 
________________________________________
15.3 ai.prompts
campos
•	id 
•	tenant_id 
•	agent_type 
•	name 
•	version 
•	prompt_text 
•	is_active 
•	created_at 
________________________________________
15.4 ai.ai_decisions
Guarda decisões/sugestões relevantes da IA.
campos
•	id 
•	tenant_id 
•	job_id 
•	entity_type 
•	entity_id 
•	decision_type 
•	decision_payload_json 
•	confidence_score 
•	human_review_required 
•	reviewed_by_user_id 
•	reviewed_at 
•	created_at 
________________________________________
16. Base regulatória e RAG
16.1 ai.rag_sources
campos
•	id 
•	tenant_id 
•	scope_type 
o	global 
o	tenant 
•	source_type 
o	lei 
o	decreto 
o	portaria 
o	norma_interna 
o	precedente 
o	parecer 
o	template 
•	title 
•	code 
•	jurisdiction 
•	state 
•	municipality 
•	published_at 
•	effective_at 
•	revoked_at 
•	status 
o	active 
o	revoked 
o	superseded 
•	source_url 
•	document_id 
•	created_at 
•	updated_at 
________________________________________
16.2 ai.rag_chunks
campos
•	id 
•	tenant_id 
•	source_id 
•	chunk_index 
•	chunk_text 
•	embedding 
•	metadata_json 
•	created_at 
________________________________________
16.3 ai.precedents
campos
•	id 
•	tenant_id 
•	process_id 
•	title 
•	summary 
•	outcome 
•	jurisdiction 
•	tags_json 
•	document_id 
•	created_at 
motivo
Você deixou claro que a manutenção da base regulatória será um ativo dos sócios. Então ela merece modelagem própria, e não só “texto vetorizado”.
________________________________________
17. Auditoria
A documentação está correta em exigir trilha append-only e imutável 
17.1 core.audit_log
campos
•	id 
•	tenant_id 
•	user_id 
•	ai_job_id 
•	action 
•	entity_type 
•	entity_id 
•	before_json 
•	after_json 
•	ip_address 
•	user_agent 
•	request_id 
•	created_at 
regra
Sem update e sem delete.
________________________________________
18. Certificados e credenciais sensíveis
18.1 core.digital_certificates
campos
•	id 
•	tenant_id 
•	client_id 
•	certificate_type 
o	a1 
•	owner_name 
•	owner_document 
•	storage_key 
•	secret_ref 
•	expires_at 
•	status 
•	last_used_at 
•	created_at 
observação
A arquitetura original já trata certificado A1 como sensível e nunca exposto ao frontend 
Aqui a recomendação é: banco guarda só metadado e referência segura.
________________________________________
19. Índices essenciais
btree
•	tenant_id 
•	status 
•	created_at 
•	process_id 
•	client_id 
•	property_id 
gist
•	geometrias em property_geometries.geom 
•	camadas em geo.*.geom 
gin
•	campos JSONB 
•	busca textual parametrizável 
•	trigram para nome de cliente/documento 
vector
•	ai.rag_chunks.embedding 
________________________________________
20. Regras de modelagem que eu mudaria em relação à v1
A v1 está boa, mas eu faria estes ajustes:
1. trocar nomes genéricos por domínio consistente
•	cases → processes 
•	users dentro de core 
•	padronizar tudo em inglês técnico ou português técnico, mas não misturar 
2. separar geometria da tabela de imóvel
isso facilita versionamento e múltiplas fontes.
3. separar extração documental de documento
não deixar tudo em um único JSONB.
4. modelar explicitamente:
•	propostas 
•	contratos 
•	cobrança 
•	comunicação 
•	offline/sync 
•	integrações por tenant 
5. não acoplar IA direto às tabelas transacionais
a separação core / ai continua correta e deve ser mantida 
________________________________________
21. Ordem recomendada de implementação do banco
Sprint 1
•	tenants 
•	users 
•	roles 
•	permissions 
•	clients 
•	properties 
•	property_geometries 
•	processes 
Sprint 2
•	tasks 
•	documents 
•	document_versions 
•	document_extractions 
•	communications 
•	portal access 
Sprint 3
•	proposals 
•	contracts 
•	invoices 
•	usage_charges 
•	integration_accounts 
Sprint 4
•	ai.jobs 
•	ai.model_usage 
•	rag_sources 
•	rag_chunks 
•	audit_log 
Sprint 5
•	field_visits 
•	field_records 
•	sync_devices 
•	sync_conflicts 
•	geo.property_overlaps 
________________________________________
22. Recomendação final de arquitetura de banco
Minha recomendação oficial para este projeto é:
•	PostgreSQL 16 
•	PostGIS 
•	pgvector 
•	UUID em tudo 
•	tenant_id em toda entidade de negócio 
•	storage externo para binários 
•	separação de schemas core, ai, geo, gov 
•	audit_log imutável 
•	modelo preparado para offline e white-label desde o MVP 
Esse desenho preserva o que a documentação já definiu como fundação — multi-tenant, geoespacial, vetorial, auditável e pronto para expansão GovTech
