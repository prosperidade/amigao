# Auditoria Completa da Plataforma Amigão (Frontend, Backend, Arquitetura, Documentação, Bugs, Dashboard, IA e Operação Real)

**Data da auditoria:** 2026-04-03  
**Escopo analisado:** API FastAPI (`app/`), frontends (`frontend/` e `client-portal/`), documentação (`docs/`), testes (`tests/`), infraestrutura local (`docker-compose.yml`).

---

## 1) Resumo Executivo

A plataforma está **bem avançada em visão de produto e cobertura funcional de domínio**, com pilares claros: multi-tenant, trilha operacional, dashboard, jobs assíncronos e camada de IA.  
Porém, o estado atual indica um cenário de **“MVP funcional com risco técnico elevado para produção”** por três fatores principais:

1. **Qualidade de entrega inconsistente entre módulos** (backend está mais estruturado que frontends).
2. **Débitos de engenharia no frontend principal** (build quebrando por erros de TypeScript).
3. **Pipeline de testes parcialmente quebrado** (testes dependem de SQLite, mas modelo usa `JSONB` sem fallback).

Diagnóstico geral:
- **Produto e arquitetura:** nota alta de direção.
- **Confiabilidade de execução real:** nota média/baixa enquanto não corrigir build/testes críticos.

---

## 2) Funcionamento Real (o que roda hoje)

### Pontos positivos observáveis
- API com inicialização robusta (warm-up de DB, segurança, storage, websocket/redis) e métricas dedicadas.  
- Separação explícita API + worker assíncrono (Celery) em containers diferentes.  
- Estrutura de domínios de negócio ampla (clientes, imóveis, processos, tarefas, documentos, contratos, propostas, IA, dashboard).

### Limitações que impactam operação real
- **Frontend Vite (`frontend/`) não fecha build** por erros de tipagem e imports não usados.
- **Suite backend falha parcialmente** por incompatibilidade do modelo `JSONB` com banco de testes SQLite.
- **Portal Next (`client-portal/`) falha em build em ambiente sem acesso externo ao Google Fonts** (dependência remota sem fallback local).

Conclusão operacional: há recursos implementados, mas o fluxo de “build verde + testes verdes + deploy previsível” ainda não está sólido.

---

## 3) Auditoria de Arquitetura

## Forças
- Arquitetura orientada a camadas e domínio (API, serviços, workers, schemas, models, repos, docs).
- Padrão assíncrono para tarefas pesadas (IA/documentos) com enfileiramento.
- Isolamento de tenant presente em queries principais e dependências de acesso.
- Preocupação com segurança de configuração em produção (`Settings.validate_security`).

## Riscos
1. **Acoplamento de execução à configuração global**: `settings = Settings()` em import-time exige `SECRET_KEY` sempre; isso dificulta testes e scripts isolados.
2. **Divergência entre stack alvo e stack de teste**: uso de tipos PostgreSQL (`JSONB`) sem estratégia de compatibilidade no ambiente de teste.
3. **Heterogeneidade de frontends**: coexistência de Vite + Next + mobile sem um padrão único de qualidade (lint/build/test gate) aumenta risco de regressão.

## Recomendação arquitetural
- Padronizar esteira “quality gate” por app: lint + typecheck + unit + smoke API.
- Definir política oficial de banco de testes (preferencialmente PostgreSQL efêmero em CI, evitando SQLite para casos com recursos PG nativos).
- Criar “Definition of Done” transversal (backend/frontend/docs/observabilidade).

---

## 4) Auditoria Backend

## Pontos fortes
- Organização madura de módulos e rotas.
- Camada de autenticação/escopo com perfil interno vs portal do cliente.
- Endpoint de dashboard com agregações úteis para operação.
- Camada de IA com fallback entre providers e registro de custo/tokens.

## Bugs e fragilidades
1. **Testes falhando por `JSONB` em SQLite**: bloqueia confiança de regressão.
2. **Uso de `class Config` (Pydantic legado) em modelos da dashboard**: gera warning de depreciação para Pydantic v2.
3. **Dependências injetadas e variáveis não usadas em endpoints IA** (`db` em alguns endpoints síncronos) indicam inconsistência de limpeza de código.

## Soluções propostas (backend)
- Curto prazo:
  - Introduzir tipo JSON portável para ambiente de teste (ou mudar testes para PostgreSQL real).
  - Atualizar `Config` para `ConfigDict` nos schemas Pydantic v2.
  - Rodar cobertura mínima por domínio crítico: auth, processos, documentos, tarefas, IA.
- Médio prazo:
  - Adicionar testes de contrato para APIs consumidas pelos dois frontends.
  - Enriquecer observabilidade com SLOs por endpoint e fila.

---

## 5) Auditoria Frontend (Vite – painel interno)

## Pontos fortes
- UX visual moderna no dashboard e páginas de operação.
- Uso de React Query e Zustand, com fluxo de autenticação relativamente simples.
- Cobertura de telas de negócio relevante (intake, processos, clientes, propostas, contratos, IA).

## Bugs encontrados
- Build falha por:
  - imports não usados em múltiplos arquivos;
  - assinaturas de mutação com retorno inconsistente (`Promise<void>` vs `Promise<AxiosResponse>`);
  - tipos incorretos em checklist (`boolean` onde se espera `void`).

## Impacto
- Não há garantia de pacote de produção compilável.
- Risco alto de regressão silenciosa em alterações pequenas.

## Soluções propostas (frontend Vite)
1. Corrigir imediatamente os erros de TypeScript e bloquear merge sem `npm run build` verde.
2. Habilitar regra estrita de lint/typecheck no CI.
3. Adotar testes de smoke de navegação e APIs críticas (Dashboard, Processos, Documentos).

---

## 6) Auditoria Frontend (Next – client portal)

## Pontos fortes
- Fluxo do cliente final bem orientado: login, lista de processos, detalhe, timeline e upload/download de documentos.
- Layout e escrita UX mais amigáveis para não técnicos.

## Fragilidade operacional
- Build de produção depende de fetch externo de fonte Google (`Inter`), falhando em ambiente restrito.

## Soluções propostas
- Empacotar fonte local (self-host) ou fallback robusto sem rede externa no build.
- Incluir cenário “offline build” no pipeline para ambientes corporativos e CI restrito.

---

## 7) Dashboard

## Estado atual
- Backend entrega resumo com processos ativos, tarefas vencidas, clientes/imóveis, atividades e tarefas do usuário.
- Frontend consome e apresenta bem os principais indicadores operacionais.

## Oportunidades
- Incluir filtros por período, responsável e tipo de demanda.
- Evoluir para métricas de SLA (tempo em etapa, aging por processo, taxa de retrabalho, throughput semanal).
- Definir “dashboard executivo” separado do “dashboard operacional”.

---

## 8) IA (Inteligência Artificial)

## Pontos positivos
- Arquitetura de gateway com fallback multi-provider.
- Registro de custo/tokens/duração por job.
- Suporte síncrono + assíncrono via Celery.

## Riscos
- Governança de prompts/modelos ainda depende de disciplina de código (faltam evidências de versionamento formal de prompts em repositório dedicado).
- Necessidade de política explícita de avaliação de qualidade (precision/recall por tarefa de classificação/extração).

## Soluções propostas
- Instituir dataset de avaliação e testes automáticos de regressão de IA.
- Registrar versão de prompt + modelo + política de fallback em cada job.
- Definir guardrails de segurança semântica (validação de saída JSON estrita + regras de negócio pós-LLM).

---

## 9) Documentação

## Pontos fortes
- Grande volume de documentação estratégica e funcional.
- Arquitetura alvo está descrita com riqueza de contexto de negócio.

## Déficits
- Parte dos READMEs técnicos está genérica/desatualizada (ex.: README de `frontend/` ainda padrão de template Vite).
- Falta “manual único de operação real” com comandos canônicos de subir, validar, testar, monitorar e diagnosticar incidentes.

## Soluções propostas
- Criar `docs/OPERACAO_REAL.md` com:
  - pré-requisitos,
  - bootstrap local,
  - variáveis obrigatórias,
  - health checks,
  - playbooks de falha.
- Atualizar README de cada app com estado real, não template padrão.

---

## 10) Priorização de Correções (90 dias)

## P0 (esta semana)
1. Corrigir build do `frontend/` (TypeScript).
2. Corrigir quebra de testes por `JSONB` vs SQLite (ou migrar testes para Postgres).
3. Tornar build do `client-portal/` resiliente sem dependência externa de fonte.

## P1 (2–4 semanas)
1. Consolidar pipeline CI com gates obrigatórios por app.
2. Padronizar qualidade de código frontend/backend.
3. Atualizar documentação operacional mínima.

## P2 (1–3 meses)
1. Observabilidade orientada a SLO/SLA.
2. Testes E2E de jornada crítica (cliente e operação interna).
3. Governança formal de IA (prompt/versionamento/avaliação).

---

## 11) Matriz de Maturidade (nota rápida)

- **Backend (arquitetura e domínio):** 8/10  
- **Backend (testabilidade e CI):** 5/10  
- **Frontend interno (entrega contínua):** 4/10  
- **Client portal (resiliência de build):** 6/10  
- **Documentação técnica operacional:** 6/10  
- **IA (arquitetura):** 7/10  
- **IA (governança e validação):** 5/10  
- **Prontidão de produção hoje:** 5/10

---

## 12) Conclusão

A plataforma tem **base técnica e visão de produto fortes**, especialmente no backend e na direção arquitetural.  
Para atingir “funcionamento real” com previsibilidade de produção, o foco deve sair de novas features por algumas sprints e entrar em **estabilização técnica disciplinada**:

- build verde em todos os apps,
- testes confiáveis no stack correto,
- documentação operacional executável,
- governança de IA com critérios mensuráveis.

Com isso, a solução tende a evoluir rapidamente de MVP robusto para operação escalável de verdade.
