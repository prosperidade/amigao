Formalização da política white-label
Isso precisa entrar oficialmente na documentação porque muda arquitetura, billing, suporte e responsabilidade operacional.
1.1 Princípio
Em modo white-label, cada tenant poderá operar com suas próprias credenciais e contas externas, reduzindo o custo operacional da plataforma central e aumentando a autonomia do cliente.
1.2 O que o tenant pode configurar
Cada tenant poderá conectar e gerenciar:
•	IA 
o	OpenAI 
o	Google Gemini / Google AI 
o	Anthropic Claude 
o	Vertex AI, se entrar depois 
•	WhatsApp 
o	Z-API 
o	Evolution API 
o	outros adapters futuros 
•	Pagamentos 
o	gateway próprio do tenant 
o	conta própria de cobrança/recebimento 
•	E-mail transacional 
o	Resend 
o	SMTP próprio 
o	outros provedores 
•	Storage e integrações 
o	Google Drive 
o	assinatura eletrônica 
o	brokers e APIs de dados, quando aplicável 
1.3 Regra de responsabilidade
Em white-label:
•	a plataforma fornece a infraestrutura de software 
•	o tenant fornece as credenciais operacionais 
•	o consumo de IA, WhatsApp, OCR, brokers e pagamentos pode ser faturado diretamente no ambiente dele 
1.4 Regras técnicas obrigatórias
•	segredo nunca fica salvo em texto puro no banco 
•	banco guarda apenas secret_ref / credential_ref 
•	segredo real fica em cofre seguro 
•	toda alteração de credencial precisa ser auditada 
•	toda integração precisa de: 
o	status 
o	health check 
o	data do último teste 
o	escopo por tenant 
1.5 Texto oficial para o documento
Em modo white-label, cada tenant poderá utilizar suas próprias credenciais de provedores externos, incluindo IA, WhatsApp, e-mail transacional, gateway de pagamento e outras integrações. A plataforma deverá oferecer camada de configuração segura por tenant, com isolamento completo de credenciais, auditoria de alterações e abstração por adapters, evitando acoplamento rígido a fornecedores específicos. O custo variável de uso desses provedores poderá ser assumido diretamente pelo tenant, reduzindo risco financeiro da operação central.
________________________________________
2. Arquitetura Mobile Offline-First — detalhada
Esse é um dos documentos mais importantes do projeto porque a própria demanda já deixou claro que o time vai a campo, registra foto, áudio, ponto, checklist e observações, e sofre com perda de informação, internet ruim e dados soltos em celular/WhatsApp; o produto precisa ter modo offline com sincronização posterior ao processo do cliente. 
2.1 Objetivo
Permitir que técnicos de campo trabalhem em ambiente com:
•	internet intermitente 
•	upload pesado 
•	coleta multimídia 
•	necessidade de prova técnica 
•	sincronização posterior sem perda de evidência 
2.2 Princípio de arquitetura
O app mobile deve nascer como offline-first, e não apenas “offline-capable”.
Isso significa:
•	o técnico consegue trabalhar sem internet 
•	os dados são gravados primeiro no dispositivo 
•	a sincronização ocorre depois 
•	o backend não é requisito para cada ação da interface 
2.3 Estratégia de plataforma
Decisão recomendada
•	React Native para Android e iOS 
•	SQLite local no dispositivo 
•	API FastAPI como backend central 
•	S3/R2 para mídia pesada 
•	fila local de sincronização 
PWA
Minha recomendação continua sendo:
•	não usar PWA como solução principal de campo 
•	PWA pode existir depois para uso leve do portal 
•	para coleta real em campo, PWA é inferior a app mobile nativo/híbrido 
2.4 Escopo do app mobile
O que entra
•	login 
•	download de contexto da visita 
•	checklist 
•	formulários 
•	fotos 
•	áudios 
•	notas 
•	GPS/pontos 
•	anexos 
•	sincronização posterior 
O que não precisa entrar no começo
•	edição geoespacial avançada 
•	workflow complexo de aprovação 
•	dashboards pesados 
•	IA local embarcada 
________________________________________
3. Estrutura lógica do app
3.1 Camadas
Mobile App (React Native)
  -> UI
  -> Local State
  -> SQLite Local DB
  -> Sync Engine
  -> Upload Manager
  -> Auth Session
  -> API Client
3.2 Módulos internos
•	auth 
•	field_visits 
•	forms 
•	media_capture 
•	gps 
•	sync_queue 
•	conflicts 
•	uploads 
•	settings 
•	logs 
________________________________________
4. Banco local no dispositivo
4.1 Tecnologia recomendada
•	SQLite 
4.2 Tabelas locais mínimas
local_users
•	sessão local 
•	permissões básicas 
•	tenant_id 
•	device_id 
local_field_visits
•	visita 
•	processo 
•	imóvel 
•	responsável 
•	status local 
local_forms
•	formulário baixado 
•	schema 
•	versão 
local_form_answers
•	respostas preenchidas 
•	timestamps 
•	sync_status 
local_media
•	fotos 
•	áudios 
•	vídeos, se entrarem depois 
•	path local 
•	metadata 
•	upload_status 
local_gps_points
•	lat 
•	lng 
•	precisão 
•	timestamp 
•	visit_id 
local_notes
•	anotações 
•	autor 
•	referência de visita/processo 
local_sync_queue
•	operação pendente 
•	tipo 
•	payload 
•	prioridade 
•	retry_count 
•	next_retry_at 
local_sync_conflicts
•	entidade 
•	payload local 
•	payload servidor 
•	status de resolução 
________________________________________
5. Modelo de dados offline
5.1 Regra principal
Toda ação importante gera um registro local antes de qualquer tentativa de envio.
Exemplos:
•	tirar foto 
•	preencher checklist 
•	gravar áudio 
•	adicionar observação 
•	marcar item como concluído 
5.2 Estados locais recomendados
Para qualquer entidade móvel:
•	draft 
•	pending_sync 
•	syncing 
•	synced 
•	conflict 
•	failed 
________________________________________
6. Engine de sincronização
6.1 Estratégia
A sincronização precisa ser:
•	assíncrona 
•	resiliente 
•	idempotente 
•	observável 
•	reprocessável 
6.2 Fluxo
1. usuário registra dado no app
2. dado vai para SQLite
3. item entra em sync_queue
4. app detecta conectividade
5. sync engine envia lote
6. backend confirma processamento
7. item muda para synced
8. se erro, agenda retry
9. se conflito, envia para resolução
6.3 Tipos de sync
Pull
baixar para o celular:
•	visitas atribuídas 
•	formulários 
•	processos resumidos 
•	tarefas do dia 
•	anexos essenciais 
Push
enviar do celular:
•	respostas 
•	fotos 
•	áudio 
•	GPS 
•	observações 
•	conclusão de visita 
6.4 Estratégia de envio
•	push em lote pequeno 
•	anexos grandes enviados separadamente 
•	metadado primeiro 
•	mídia depois 
________________________________________
7. Estratégia de upload de mídia
A documentação já prevê storage privado, URLs assinadas e pasta específica para dados coletados em campo. 
7.1 Fluxo recomendado
1. app captura mídia
2. salva arquivo local
3. registra metadata no SQLite
4. cria item na fila
5. pede upload-url ao backend
6. envia arquivo ao bucket
7. confirma upload ao backend
8. backend vincula mídia ao processo/visita
7.2 Regras importantes
•	comprimir imagem antes do upload 
•	manter original opcional só se necessário 
•	tentar Wi-Fi primeiro para arquivos muito grandes 
•	permitir retry sem duplicar evidência 
•	cada upload precisa de idempotency_key 
________________________________________
8. Estratégia de conflitos
A documentação já alertava para concorrência entre consultores, parceiros e atualizações de campo simultâneas. 
8.1 Regra do MVP
Não tentar “resolver tudo automaticamente”.
8.2 Política por tipo de dado
Metadado crítico
Exemplo:
•	status do processo 
•	responsável 
•	prazos 
•	vínculo contratual 
Regra: servidor prevalece
Evidência de campo
Exemplo:
•	fotos 
•	áudio 
•	notas 
•	respostas de formulário 
•	pontos GPS 
Regra: append-only
Não sobrescrever; adicionar.
Checklist binário
Exemplo:
•	item marcado/desmarcado 
Regra inicial: última alteração vence, mas registrar auditoria
Observação textual
Regra: não sobrescrever; criar nova versão ou novo registro
8.3 Quando abrir conflito manual
•	mesmo formulário alterado em dois lugares 
•	alteração de valor sensível depois da coleta 
•	inconsistência de vínculo entre visita e processo 
•	tentativa de editar registro já fechado no servidor 
________________________________________
9. Autenticação e segurança no mobile
9.1 Sessão
•	access token curto 
•	refresh controlado 
•	armazenamento seguro 
•	logout remoto suportado depois 
9.2 Dados locais sensíveis
•	criptografia local quando possível 
•	não armazenar segredo de integração 
•	não armazenar credencial de certificado 
•	limpar cache local em revogação/roubo do dispositivo 
9.3 Escopo
Técnico de campo só vê:
•	visitas atribuídas 
•	processos mínimos necessários 
•	anexos autorizados 
•	nada de financeiro 
Isso bate com o RBAC já previsto no documento técnico. 
________________________________________
10. Performance e experiência de uso
10.1 Regras
•	abrir app rápido mesmo offline 
•	visita deve carregar com dados locais 
•	mídia pesada não pode travar a UI 
•	sync em background quando possível 
•	feedback visual claro: 
o	salvo localmente 
o	aguardando envio 
o	sincronizado 
o	conflito 
o	falhou 
10.2 UX obrigatória
O usuário de campo precisa saber:
•	o que já está seguro no aparelho 
•	o que já subiu 
•	o que falhou 
•	o que precisa reenviar 
________________________________________
11. API necessária para suportar offline
A API já começou a prever /field/sync, uploads e visitas. Agora isso precisa ficar fechado como contrato de arquitetura.
Endpoints mínimos
Contexto
•	GET /field/visits 
•	GET /field/visits/{id} 
•	GET /field/forms/{id} 
•	GET /field/process-summary/{id} 
Sync
•	POST /field/sync 
•	POST /field/uploads/upload-url 
•	POST /field/uploads/confirm 
Conflitos
•	GET /field/conflicts 
•	POST /field/conflicts/{id}/resolve 
Logs/diagnóstico
•	POST /field/device-heartbeat 
•	POST /field/sync-errors 
________________________________________
12. Observabilidade mobile
O que medir
•	dispositivos ativos 
•	última sincronização por device 
•	taxa de falha de sync 
•	tamanho médio de upload 
•	conflitos por entidade 
•	tempo médio de sincronização 
•	visitas sem sync há mais de X horas 
Alerta importante
Se uma visita ficou muito tempo sem sincronizar, o sistema deve alertar gestor/consultor.
________________________________________
13. Relação com o backend e storage
13.1 Backend
•	recebe sync 
•	valida tenant e usuário 
•	aplica regras de negócio 
•	grava no PostgreSQL 
•	cria auditoria 
•	responde status por item 
13.2 Storage
A pasta de campo já faz sentido na hierarquia do bucket: dados coletados em campo ficam vinculados por tenant e processo. 
Estrutura recomendada:
{tenant_id}/processes/{process_id}/field/{visit_id}/photos/
{tenant_id}/processes/{process_id}/field/{visit_id}/audio/
{tenant_id}/processes/{process_id}/field/{visit_id}/forms/
________________________________________
14. Roadmap mobile
Fase M1 — fundação
•	login 
•	download de visitas 
•	SQLite 
•	checklist offline 
•	notas 
•	sync básico 
Fase M2 — evidências
•	fotos 
•	áudio 
•	GPS 
•	upload robusto 
•	retry 
Fase M3 — robustez
•	conflitos 
•	logs 
•	compressão inteligente 
•	melhorias de UX 
•	cache seletivo 
________________________________________
15. Riscos reais do mobile
Risco 1
sincronização concorrente
Mitigação
•	idempotência 
•	fila local 
•	append-only onde possível 
Risco 2
mídia pesada
Mitigação
•	compressão 
•	envio separado 
•	retry controlado 
Risco 3
falso senso de “salvou”
Mitigação
•	estados visuais claros 
Risco 4
perda de aparelho
Mitigação
•	sessão segura 
•	limpeza remota futura 
•	mínimo de dado local 
Risco 5
querer sofisticar demais cedo
Mitigação
•	MVP simples 
•	resolver o fluxo principal primeiro 
________________________________________
16. Relação com GovTech
Estamos contemplando?
Sim, estruturalmente sim. Ainda não funcionalmente completo.
O app já fica preparado para GovTech porque:
•	trabalha com trilha de auditoria 
•	evidencia coleta em campo 
•	vincula dado a processo 
•	mantém rastreabilidade 
•	suporta operação distribuída 
•	respeita multi-tenant e perfis distintos 
O que ainda falta para GovTech de verdade
Depois precisaremos de um documento próprio de GovTech com:
•	cadeia de custódia de evidência 
•	assinatura forte e carimbo temporal 
•	logs imutáveis de nível institucional 
•	trilha de decisão humano + IA 
•	perfis de analista público, supervisor, auditor 
•	relatórios oficiais e exportações regulatórias 
•	política de retenção e arquivamento público 
Então a resposta correta é:
•	o projeto já está preparado para evoluir para GovTech 
•	mas o módulo GovTech ainda não está documentado em profundidade suficiente
