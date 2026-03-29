# Plano Executivo — Execução do Dia

## Projeto: Amigão do Meio Ambiente
## Referência: Auditoria + Continuidade da Sprint 5

---

## Objetivo do dia

Fechar os riscos operacionais mais críticos do ambiente atual antes de abrir novas frentes funcionais, com foco em homologação integrada, segurança operacional mínima e consistência de banco de dados.

---

## Plano Executivo

### 1. Homologação integrada da stack
**Objetivo:** validar a operação fim a fim da aplicação em ambiente integrado.

**Escopo:**
- subir a stack completa com `docker compose up --build`
- validar comunicação entre `api`, `worker`, `db`, `redis`, `minio` e `client-portal`
- executar o fluxo principal do portal do cliente

**Entregáveis:**
- stack operacional sem falha crítica de inicialização
- checklist funcional executado
- registro dos erros reais encontrados na integração

**Critério de aceite:**
- portal autentica corretamente
- API responde sem erro nas rotas principais
- upload/download de documentos funciona
- mudança de status dispara automações esperadas
- PDF e notificações executam no fluxo integrado

### 2. Parametrização de produção e hardening mínimo
**Objetivo:** remover configurações inseguras e evitar falso positivo operacional.

**Escopo:**
- revisar `SECRET_KEY`, SMTP e domínios finais
- definir variáveis obrigatórias por ambiente
- garantir comportamento fail-fast para produção

**Entregáveis:**
- mapa de variáveis críticas do ambiente
- configuração separada para `dev` e `prod`
- erro explícito para segredo crítico ausente ou inválido

**Critério de aceite:**
- produção não opera com `SECRET_KEY` insegura
- SMTP inválido não retorna sucesso falso
- URLs principais do portal e da API ficam parametrizadas

### 3. Consistência de banco e migrations
**Objetivo:** eliminar risco de drift de schema entre ambientes.

**Escopo:**
- confirmar Alembic como estratégia única de schema
- revisar `init_db` e remover dependência indevida de `create_all` fora de teste
- validar fluxo de bootstrap e atualização do banco

**Entregáveis:**
- estratégia única de schema formalizada
- setup de banco revisado
- fluxo de migration validado por smoke test

**Critério de aceite:**
- schema sobe por migrations versionadas
- não existe caminho paralelo conflitante para criação de estrutura
- setup fica reproduzível entre ambientes

---

## Sequência de Execução

### Etapa 1 — Homologação integrada
1. Validar arquivos de ambiente e pré-requisitos da stack.
2. Subir os serviços com `docker compose up --build`.
3. Confirmar saúde dos containers principais.
4. Testar autenticação do portal do cliente.
5. Testar listagem de processos, timeline e documentos.
6. Validar upload, download, mudança de status e geração de PDF.
7. Registrar falhas reais encontradas na integração.

### Etapa 2 — Correção de configuração e segurança mínima
1. Revisar defaults sensíveis no backend.
2. Parametrizar `SECRET_KEY`, SMTP e domínios do portal/API.
3. Ajustar validações para falhar explicitamente em produção.
4. Revisar o comportamento do serviço de e-mail para impedir sucesso simulado indevido.
5. Reexecutar a subida da stack após os ajustes.

### Etapa 3 — Banco e migrations
1. Inspecionar o uso atual de Alembic e `init_db`.
2. Identificar pontos em que `create_all` pode conflitar com migrations.
3. Consolidar a estratégia oficial de bootstrap do banco.
4. Validar `upgrade` da migration em ambiente limpo.
5. Registrar pendências ou correções adicionais de schema.

### Etapa 4 — Fechamento do dia
1. Reexecutar o checklist funcional principal.
2. Atualizar o status do progresso com os resultados reais.
3. Separar o que foi concluído, o que foi corrigido e o que ficou pendente.
4. Preparar a próxima frente: observabilidade e integridade de regras de negócio.

---

## Resultado esperado ao final do dia

- stack integrada validada
- configuração crítica revisada
- riscos imediatos de produção reduzidos
- estratégia de banco mais consistente
- base pronta para a próxima frente de observabilidade e endurecimento operacional

---

## Execução realizada em 29/03/2026

### Itens validados
- `docker compose up --build -d` executado com sucesso para `api`, `worker`, `db`, `redis`, `minio` e `client-portal`
- `GET /health` retornando `200` na API
- `http://localhost:3000/login` respondendo `200` no portal
- autenticação real do cliente validada com `cliente@amigao.com`
- listagem de processos do portal validada com escopo por `client_id`
- fluxo documental fim a fim validado: presigned upload, `PUT` no MinIO, confirmação no backend e URL de download
- worker consumindo a task `workers.notify_document_uploaded` com sucesso

### Correções aplicadas durante a execução
- `docker-compose.yml` passou a consumir variáveis de ambiente em vez de segredos hard-coded
- bootstrap da API alinhado com `python -m app.db.init_db` como fluxo oficial de schema
- `app/core/config.py` endurecido para produção:
  - `SECRET_KEY` mínima de 32 caracteres
  - bloqueio de chave insegura
  - bloqueio de credenciais default do MinIO
  - bloqueio de URLs locais em produção
  - exigência de SMTP configurado em produção
- `app/services/storage.py` corrigido para usar endpoint interno do MinIO no backend e endpoint público nas URLs assinadas
- imagem base da API/worker ajustada para rodar com usuário não privilegiado

### Bug real encontrado e corrigido
- as URLs assinadas de upload/download estavam sendo geradas com host interno `minio:9000`
- isso quebrava o upload real no navegador/host, embora o backend ainda confirmasse o documento
- a correção introduziu `MINIO_PUBLIC_URL` para emissão de URLs públicas acessíveis fora da rede Docker

### Validações executadas
- `.\venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_settings.py tests\test_storage_service.py -q` -> `9 passed`
- `docker compose config` -> configuração resolvida sem erros
- `docker compose up --build -d` -> stack integrada operacional
- upload real homologado via URL assinada com `PUT 200` no MinIO

### Pendências que seguem abertas
- parametrizar SMTP real de produção para substituir o modo sem envio em `development`
- revisar os alertas de latência observados em `auth/login`, `documents/upload-url` e `documents/confirm-upload`
- consolidar o fechamento da frente de migrations com smoke de upgrade/downgrade
