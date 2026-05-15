SPRINT 1 — Fundação Executável (Semana 1–2)
🎯 Objetivo da sprint
Sair de zero → sistema rodando com base sólida
Ao final você deve ter:
•	API rodando 
•	autenticação funcionando 
•	multi-tenant ativo 
•	estrutura de banco criada 
•	logs funcionando 
•	primeiro endpoint real 
________________________________________
🧱 1. Setup do Projeto (Dia 1)
Backend (FastAPI)
Criar estrutura:
/app
  /api
  /core
  /models
  /schemas
  /services
  /repositories
  /workers
  /integrations
________________________________________
Tasks
•	 Criar repo Git 
•	 Setup FastAPI 
•	 Setup Poetry ou pip + venv 
•	 Configurar lint (ruff/black) 
•	 Configurar ENV loader 
________________________________________
Infra local
•	 PostgreSQL + PostGIS 
•	 Redis 
•	 MinIO (S3 local) 
________________________________________
🔐 2. Autenticação + Multi-tenant (Dia 2–3)
Modelos iniciais
tenants
users
user_roles
________________________________________
Tasks
•	 Criar tabela tenants 
•	 Criar tabela users 
•	 Criar relação user ↔ tenant 
•	 Implementar JWT auth 
•	 Middleware de tenant (X-Tenant-Id) 
________________________________________
Endpoint
POST /auth/login
GET /auth/me
________________________________________
Critério de pronto
✔ login funcionando
✔ user autenticado
✔ tenant isolado
________________________________________
🧩 3. Estrutura base de banco (Dia 3–4)
Entidades principais
•	clients 
•	properties 
•	processes 
•	tasks 
________________________________________
Tasks
•	 Criar migrations 
•	 Definir schemas base 
•	 Relacionamentos básicos 
________________________________________
Critério
✔ criar processo via DB já possível
________________________________________
⚙️ 4. API Core (Dia 4–5)
Endpoints mínimos
POST /clients
GET /clients

POST /processes
GET /processes
GET /processes/{id}
________________________________________
Tasks
•	 CRUD clients 
•	 CRUD processes 
•	 validação por tenant 
•	 response padrão 
________________________________________
Critério
✔ criar processo via API
________________________________________
🧾 5. Documentos (base) (Dia 5–6)
Tasks
•	 upload endpoint 
•	 salvar metadata 
•	 integrar com S3/MinIO 
________________________________________
Endpoint
POST /documents/upload
________________________________________
Critério
✔ arquivo sobe e registra no banco
________________________________________
📊 6. Logs e Observabilidade básica (Dia 6)
Tasks
•	 middleware de request_id 
•	 log estruturado JSON 
•	 incluir tenant_id nos logs 
________________________________________
Critério
✔ todos endpoints logando corretamente
________________________________________
🔄 7. Worker base (Dia 7)
Tasks
•	 setup fila (Celery / RQ / dramatiq) 
•	 worker rodando 
•	 primeiro job simples 
________________________________________
Exemplo
def test_job():
    print("worker funcionando")
________________________________________
Critério
✔ job executando fora da API
________________________________________
📱 8. Mobile (início leve) (Dia 7–8 paralelo)
Tasks
•	 criar projeto React Native 
•	 tela login 
•	 salvar token 
•	 chamada básica API 
________________________________________
Critério
✔ login mobile funcionando
________________________________________
🧪 9. Testes básicos
Tasks
•	 teste de login 
•	 teste de criação de processo 
________________________________________
📦 Entregável final da Sprint 1
Você deve conseguir:
👉 logar
👉 criar cliente
👉 criar processo
👉 subir documento
👉 ver logs
👉 rodar worker
________________________________________
🧠 Decisões travadas (não pensar mais)
•	Backend: FastAPI 
•	DB: PostgreSQL + PostGIS 
•	Mobile: React Native 
•	Storage: S3/R2 
•	Fila: Redis + worker 
•	IA: entra depois (Sprint 3) 
________________________________________
⚠️ Armadilhas para evitar
❌ não tentar fazer IA agora
❌ não tentar fazer mobile completo
❌ não tentar integrar gov
❌ não tentar deixar “perfeito”
👉 objetivo = funcionar
________________________________________
📅 Plano de execução (resumido)
Dia 1: setup + infra
Dia 2–3: auth + tenant
Dia 3–4: banco
Dia 4–5: API core
Dia 5–6: documentos
Dia 6: logs
Dia 7: worker
Dia 7–8: mobile básico
________________________________________
🎯 Missão do primeiro dia (amanhã)
Se você fizer só isso, já está perfeito:
👉 criar repo
👉 subir FastAPI
👉 conectar PostgreSQL
👉 rodar primeiro endpoint
________________________________________
💬 Última recomendação (importante)
Não tente validar tudo mentalmente.
👉 Construa pequeno → rode → veja funcionando
Isso aqui não é mais projeto.
👉 Agora é produto.
________________________________________
Se amanhã você quiser, volta aqui e eu te ajudo com:
•	estrutura real de código 
•	models iniciais 
•	primeiro endpoint completo 
Vamos levar isso até produção.
