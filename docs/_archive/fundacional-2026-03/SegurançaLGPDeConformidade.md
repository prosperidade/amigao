Segurança, LGPD e Conformidade
Projeto: Plataforma Ambiental SaaS (App Ambiental)
Versão: 1.0
________________________________________
1. Objetivo
Definir:
•	como os dados são protegidos 
•	como o sistema atende à LGPD 
•	como funciona isolamento multi-tenant 
•	como tratar dados sensíveis 
•	como garantir segurança operacional 
•	como preparar o sistema para GovTech 
________________________________________
2. Princípios de Segurança
2.1 Segurança por design (Security by Design)
•	segurança não é camada final 
•	está presente em: 
o	arquitetura 
o	API 
o	mobile 
o	IA 
o	storage 
________________________________________
2.2 Princípio do menor privilégio
•	usuário acessa apenas o necessário 
•	serviços também 
________________________________________
2.3 Isolamento por tenant (crítico)
•	nenhum dado de tenant mistura com outro 
•	isolamento lógico obrigatório 
•	possível evolução para isolamento físico 
________________________________________
2.4 Auditoria total
•	toda ação relevante é registrada 
•	histórico imutável 
________________________________________
2.5 Zero trust interno
•	nenhum serviço confia implicitamente em outro 
•	tudo autenticado e autorizado 
________________________________________
3. Classificação de Dados
3.1 Tipos de dados no sistema
Dados pessoais
•	nome 
•	CPF 
•	telefone 
•	e-mail 
Dados sensíveis (alto risco)
•	documentos oficiais 
•	matrícula de imóvel 
•	CAR 
•	dados ambientais 
•	coordenadas geográficas 
Dados operacionais
•	tarefas 
•	processos 
•	logs 
•	mensagens 
Dados de integração
•	tokens 
•	API keys 
•	certificados A1 
________________________________________
3.2 Classificação de risco
Tipo	Nível
Dados públicos	baixo
Dados pessoais	médio
Dados ambientais/documentais	alto
Credenciais	crítico
________________________________________
4. LGPD — Conformidade
4.1 Base legal
O sistema deve operar sob:
•	execução de contrato 
•	legítimo interesse 
•	cumprimento de obrigação legal 
________________________________________
4.2 Direitos do titular
O sistema deve permitir:
•	acesso aos dados 
•	correção 
•	anonimização 
•	exclusão (quando aplicável) 
•	exportação 
________________________________________
4.3 Responsabilidade
Plataforma
•	garante infraestrutura segura 
•	garante isolamento 
•	garante logs 
Tenant
•	responsável pelo uso dos dados 
•	responsável por consentimento do cliente 
________________________________________
4.4 Minimização de dados
•	só coletar o necessário 
•	evitar duplicação 
•	evitar envio desnecessário para IA 
________________________________________
5. Arquitetura de Segurança
________________________________________
5.1 Autenticação
Backend
•	JWT (curta duração) 
•	refresh token controlado 
Mobile
•	armazenamento seguro (secure storage) 
•	logout remoto futuro 
________________________________________
5.2 Autorização (RBAC)
Perfis:
•	admin 
•	consultor 
•	técnico de campo 
•	parceiro 
•	cliente 
Regras
•	acesso por tenant obrigatório 
•	acesso por função 
•	acesso por contexto (processo, tarefa, etc) 
________________________________________
5.3 Multi-tenant (crítico)
Estratégia atual:
•	isolamento lógico por tenant_id 
Garantias:
•	todas queries filtram por tenant 
•	storage separado por prefixo 
•	logs separados 
Evolução futura:
•	schema por tenant 
•	banco por tenant (enterprise/gov) 
________________________________________
6. Segurança de API
________________________________________
6.1 Regras obrigatórias
•	autenticação em todos endpoints 
•	validação de entrada 
•	rate limiting 
•	proteção contra replay 
•	uso de idempotency-key 
________________________________________
6.2 Headers obrigatórios
Authorization: Bearer
X-Tenant-Id
X-Request-Id
Idempotency-Key
________________________________________
6.3 Proteções
•	SQL injection → ORM + validação 
•	XSS → sanitização 
•	CSRF → tokens 
•	brute force → rate limit 
________________________________________
7. Segurança de Storage
________________________________________
7.1 Estrutura
{tenant_id}/processes/{process_id}/...
________________________________________
7.2 Regras
•	arquivos privados por padrão 
•	acesso via URL assinada 
•	tempo limitado de acesso 
•	logs de acesso 
________________________________________
7.3 Dados críticos
•	documentos legais 
•	evidências de campo 
•	contratos 
Devem ter:
•	rastreabilidade 
•	versionamento 
•	integridade 
________________________________________
8. Gestão de Segredos
________________________________________
8.1 Nunca armazenar segredo em texto puro
8.2 Uso de referências
secret://tenant/openai/main
________________________________________
8.3 Segredos incluem
•	API keys 
•	tokens 
•	certificados A1 
•	credenciais de integração 
________________________________________
8.4 Regras
•	criptografia em repouso 
•	rotação de chave 
•	acesso restrito 
•	audit log de uso 
________________________________________
9. Segurança de IA
________________________________________
9.1 Dados enviados para IA
•	apenas o necessário 
•	nunca enviar: 
o	tokens 
o	credenciais 
o	dados irrelevantes 
________________________________________
9.2 Isolamento
•	prompts não misturam tenants 
•	logs separados 
________________________________________
9.3 Auditoria
•	registrar tudo: 
o	input (hash) 
o	output (hash) 
o	provider 
o	custo 
________________________________________
9.4 Risco de vazamento
Mitigação:
•	controle de payload 
•	anonimização quando possível 
________________________________________
10. Segurança Mobile
________________________________________
10.1 Dados locais
•	armazenados em SQLite 
•	dados sensíveis minimizados 
•	possível criptografia local 
________________________________________
10.2 Regras
•	não armazenar credenciais 
•	não armazenar tokens longos 
•	limpar dados em logout 
________________________________________
10.3 Perda de dispositivo
•	sessão expira 
•	futuro: wipe remoto 
________________________________________
11. Auditoria e Logs
________________________________________
11.1 O que deve ser logado
•	login/logout 
•	acesso a dados 
•	mudanças de estado 
•	chamadas de IA 
•	uso de integração 
•	uploads/downloads 
________________________________________
11.2 Características
•	imutável 
•	por tenant 
•	rastreável 
________________________________________
11.3 Exemplo
{
  "tenant_id": "...",
  "user_id": "...",
  "action": "document.validated",
  "entity_id": "...",
  "timestamp": "...",
  "ip": "...",
  "device": "mobile"
}
________________________________________
12. Integrações externas
________________________________________
12.1 Tipos
•	IA 
•	WhatsApp 
•	e-mail 
•	pagamento 
•	gov APIs 
________________________________________
12.2 Regras
•	credencial por tenant 
•	isolamento total 
•	health check obrigatório 
•	fallback obrigatório 
________________________________________
12.3 Certificado A1
•	armazenado com segurança 
•	nunca exposto 
•	acesso controlado 
•	auditado 
________________________________________
13. Conformidade Operacional
________________________________________
13.1 Backup
•	diário 
•	retenção definida 
•	teste de restauração 
________________________________________
13.2 Disaster Recovery
•	plano documentado 
•	RTO/RPO definidos 
________________________________________
13.3 Monitoramento
•	erros 
•	latência 
•	falhas de integração 
•	falhas de sync 
________________________________________
14. Preparação para GovTech
________________________________________
Já atendido:
•	auditoria 
•	rastreabilidade 
•	controle de estado 
•	logs 
•	segregação 
________________________________________
Ainda necessário (futuro):
•	logs imutáveis (WORM) 
•	assinatura digital forte 
•	carimbo do tempo 
•	cadeia de custódia 
•	trilha legal completa 
•	compliance institucional 
________________________________________
15. Riscos e Mitigações
________________________________________
Vazamento de dados
✔ criptografia + controle de acesso
________________________________________
Acesso indevido
✔ RBAC + auditoria
________________________________________
Erro humano
✔ logs + versionamento
________________________________________
Falha de integração
✔ fallback + monitoramento
________________________________________
Uso indevido de IA
✔ governança + auditoria
________________________________________
16. Conclusão
Esse modelo garante:
•	segurança real do sistema 
•	conformidade com LGPD 
•	isolamento multi-tenant 
•	base para escala SaaS 
•	preparação para GovTech
