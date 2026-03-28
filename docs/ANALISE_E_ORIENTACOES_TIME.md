# Análise Técnica e Orientações para o Time
**Projeto:** Plataforma Ambiental SaaS  
**Data:** 26/03/2026  
**Autor:** Claude (Anthropic) — revisão independente  
**Destinatários:** Claude Code · Codex · Gemini 3.1 · Dev Lead

---

## 1. Propósito deste documento

Este documento consolida a revisão completa da documentação produzida até agora e serve como guia de ação para os agentes de desenvolvimento do time. Cada seção identifica um problema real, explica o impacto e define o que precisa ser feito — com prioridade clara.

Não é uma crítica ao trabalho feito. A base está acima da média. Este documento existe para fechar as lacunas antes que elas se tornem dívida técnica cara.

---

## 2. Correções imediatas obrigatórias

### 2.1 Arquivo `progresso1.md` — atropelamento de ordem de execução

**Problema identificado:**  
O arquivo `progresso1.md` lista como próximos passos da Sprint 2:
```
- [ ] Testes automatizados (pytest) para auth e CRUD
- [ ] Setup inicial mobile (React Native)
- [ ] Integração com GovTech APIs   ← PROBLEMA
- [ ] Agente IA Ambiental (Sprint 3+)
```

A integração com GovTech APIs está listada como Sprint 2, mas o `PlanodeExecucao.md` define explicitamente:
- Fase 1 (MVP Operacional): sem integrações gov
- Fase 3 (IA funcional): agentes básicos
- Fase 5 (Escala): preparação GovTech
- Fase 6 (GovTech): integração real

**Impacto:** Se o time iniciar integração com GovTech agora, vai gastar semanas num problema instável (APIs governamentais mudam, têm Captcha, autenticação complexa) antes de ter um produto utilizável pelo primeiro usuário. O MVP vai atrasar.

**Ação corretiva:**  
Substituir os próximos passos no `progresso1.md` pelos itens corretos abaixo. Ver documento `progresso1_CORRIGIDO.md` entregue junto.

---

### 2.2 Arquivo `progressopadrão.md` — documento de outro projeto

**Problema identificado:**  
O arquivo `progressopadrão.md` contém o progresso de um projeto completamente diferente chamado **EnjoyFun 2.0**, com controllers PHP, sistema de PDV, check-in de eventos, Workforce Ops e Financial Layer para organizadores de eventos. Nada disso pertence à Plataforma Ambiental.

**Impacto:** Qualquer agente de IA que ler esse arquivo como contexto do projeto vai receber informação incorreta sobre a arquitetura (PHP vs FastAPI, controllers de eventos vs processos ambientais). Isso causa confusão nos agentes e pode gerar código errado.

**Ação corretiva:**  
Remover o arquivo `progressopadrão.md` da base de documentação deste projeto imediatamente. Se ele pertence ao EnjoyFun 2.0, mova para o repositório correto.

---

### 2.3 `ai.prompts` — campos insuficientes para versionamento seguro

**Problema identificado:**  
A tabela `ai.prompts` na modelagem atual tem apenas `is_active` como controle de estado. Isso não é suficiente para:
- Fazer rollout gradual de prompt novo sem derrubar o anterior
- Reverter para versão anterior em caso de regressão
- Distinguir prompt em teste de prompt em produção

**Campos que precisam ser adicionados:**
```sql
status VARCHAR(20) DEFAULT 'active'
  -- valores: active | experimental | deprecated | archived
version_string VARCHAR(20)
  -- ex: "1.0.0", "1.1.0", "2.0.0"
rollout_percent INTEGER DEFAULT 100
  -- para rollout gradual: 0-100%
previous_version_id UUID REFERENCES ai.prompts(id)
  -- para rollback imediato
notes TEXT
  -- descrição da mudança nessa versão
```

**Ação corretiva:**  
Adicionar migration com esses campos antes do Sprint 3 (quando os agentes entram em produção). Ver documento `ModelagemdeBancodeDados_ADITIVOV1.md` entregue junto.

---

### 2.4 `core.audit_log` — sem encadeamento para trilha imutável

**Problema identificado:**  
A tabela `core.audit_log` atual não tem campo `hash_previous`. Para GovTech real — e para qualquer auditoria jurídica séria — os registros precisam ser encadeados de forma que qualquer adulteração retroativa seja detectável.

**Campo a adicionar:**
```sql
hash_sha256 VARCHAR(64)
  -- hash do registro atual (conteúdo + timestamp + hash_previous)
hash_previous VARCHAR(64)
  -- hash do registro anterior da mesma entidade
```

**Nota:** Não precisa implementar no MVP. Mas o campo precisa existir na tabela desde o início para não exigir migração em produção depois. Deixe `NULL` agora, implemente o preenchimento no Sprint 4 ou 5.

---

### 2.5 Política de retenção de dados pós-cancelamento — ausente

**Problema identificado:**  
Nenhum documento define o que acontece com os dados de um tenant quando ele cancela o contrato. Isso é obrigação legal da LGPD (Art. 16).

**O que precisa ser definido:**
- Período de retenção após cancelamento (sugestão: 90 dias)
- O tenant recebe export dos dados antes da exclusão?
- Quais dados são anonimizados vs excluídos fisicamente?
- Quem executa a exclusão? Processo manual ou automatizado?

**Ação corretiva:**  
Ver documento `PoliticaRetencaoDados.md` entregue junto.

---

## 3. Lacunas que precisam de documento novo

### 3.1 Base regulatória — CRÍTICO

Este é o gap mais importante de toda a documentação.

O Agente Regulatório é descrito em detalhes — capabilities, providers de IA, roteamento. Mas o que ele vai consultar não está definido. O RAG precisa de uma base. Essa base precisa de alguém para construí-la, mantê-la e atualizá-la.

**Decisão de arquitetura humana:**  
A sócia consultora ambiental é a especialista. Ela é quem vai curar essa base. O sistema precisa ser desenhado para tornar essa curadoria fácil, não técnica.

**Solução proposta:**  
Um Agente de Curadoria Regulatória dedicado, com interface simples de upload para a consultora. Ver documento `AgenteRegulatorio_BaseCuradoria.md` entregue junto.

---

### 3.2 Estratégia de versionamento da API — ausente

**Problema:**  
Toda a API está definida como `/api/v1/`. Quando a v2 existir (e vai existir), tenants white-label que integraram na v1 vão quebrar se não houver política clara.

**O que precisa ser definido:**
- Quantas versões simultâneas serão suportadas
- Qual o período de suporte de cada versão após deprecação
- Como comunicar breaking changes aos tenants
- Como o backend suporta múltiplas versões sem duplicar código

**Ação corretiva:**  
Ver documento `EstrategiaVersaoAPI.md` entregue junto.

---

### 3.3 Seed de dados e ambiente de desenvolvimento — ausente

**Problema:**  
Não há definição de como popular o banco para desenvolvimento e homologação. Sem seed padronizado, cada dev/agente trabalha com dados diferentes, os testes ficam inconsistentes e a homologação com a cliente fica difícil.

**O que o seed precisa conter:**
- 1 tenant de exemplo com configurações completas
- Usuários nos 5 perfis (admin, consultor, técnico, parceiro, cliente)
- 3 clientes com tipos diferentes (PF, PJ, cooperativa)
- 3 imóveis com geometrias reais do Cerrado goiano
- 1 processo em cada status da máquina de estados
- Documentos de exemplo de cada tipo (matrícula, CAR, CCIR)
- Base regulatória mínima (5 normas de referência)

**Ação corretiva:**  
Ver documento `SeedDadosDev.md` entregue junto.

---

## 4. Observações por documento — resumo para o time

| Documento | Status | Prioridade | Ação |
|---|---|---|---|
| `Arquiteturadetalhada.md` | ✅ Sólido | Baixa | Decidir: WebSocket no FastAPI + Redis pub/sub (não deixar em aberto) |
| `ModelagemdeBancodeDados.md` | ✅ Sólido | Média | Adicionar campos em `ai.prompts` e `core.audit_log` |
| `Backlogfuncionalportela.md` | ✅ Sólido | Baixa | Adicionar tela "Saúde das Integrações" |
| `DocumentodeFluxosEndtoEnd.md` | ✅ Sólido | Baixa | Detalhar Fluxo 10 (proposta rejeitada/expirada) |
| `Aditivo_arquitetural_política_multi_LLM.md` | ✅ Sólido | Média | Avaliar LiteLLM como base do AI Gateway antes de construir do zero |
| `SegurançaLGPDeConformidade.md` | ✅ Sólido | Alta | Adicionar política de retenção pós-cancelamento |
| `Governança_deIA.md` | ✅ Melhor doc | Baixa | Definir 3 faixas de confiança (alta/média/baixa) |
| `PlanodeExecucao.md` | ✅ Sólido | Baixa | Avaliar MVP mobile na Fase 1 |
| `DocumentodeRegrasdeNegocio.md` | ✅ Sólido | Nenhuma | Nenhuma ação necessária |
| `DocumentodeIntegraçõesGovTech.md` | ✅ Sólido | Nenhuma | Nenhuma ação necessária |
| `DocumentodeObservabilidade.md` | ✅ Sólido | Nenhuma | Nenhuma ação necessária |
| `Formalizaçãodapolíticawhitelabel.md` | ✅ Sólido | Nenhuma | Nenhuma ação necessária |
| `EspecificaçãodaAPIv1.md` | ✅ Sólido | Média | Adicionar estratégia de versionamento |
| `PRDPRODUCTREQUIREMENTSDOCUMENT.md` | ✅ Sólido | Nenhuma | Nenhuma ação necessária |
| `SPRINT1.md` | ✅ Entregue | Nenhuma | Sprint concluída conforme planejado |
| `progresso1.md` | ⚠️ Corrigir | Alta | Remover GovTech APIs dos próximos passos |
| `progressopadrão.md` | ❌ Remover | Crítica | Pertence ao projeto EnjoyFun 2.0 — remover desta base |

---

## 5. Sugestão sobre o AI Gateway — avalie antes de construir

O Aditivo Multi-LLM descreve um AI Gateway completo com registry de capabilities, roteamento automático, fallback encadeado e policy por tenant. Isso é correto como arquitetura-alvo.

Antes de construir do zero, o time deve avaliar o **LiteLLM** (MIT license, Python nativo):

```
pip install litellm
```

O que ele já entrega:
- Proxy unificado para OpenAI, Gemini, Claude, Cohere e 100+ providers
- Fallback automático configurável
- Cost tracking por modelo e por tenant
- Structured output normalizado
- Rate limiting e budget por chave

O que vocês ainda constroem por cima:
- Policy de roteamento por capability do sistema (nosso formato interno)
- Auditoria vinculada ao `ai.model_usage` do banco
- Configuração por tenant via `integration_accounts`

Avaliem em 1 dia. Se atender, economizam 2-3 semanas de engenharia. Se não atender, constroem sabendo exatamente o que o LiteLLM não resolve.

---

## 6. Checklist de ações para o time — ordem de execução

### Hoje / próxima sessão
- [ ] Remover `progressopadrão.md` da base do projeto
- [ ] Aplicar correção nos próximos passos do `progresso1.md`
- [ ] Comunicar ao time a mudança de prioridade (GovTech APIs sai do Sprint 2)

### Sprint 2 (próximas semanas)
- [ ] Adicionar migration com campos novos em `ai.prompts`
- [ ] Adicionar campos `hash_sha256` e `hash_previous` em `core.audit_log` (nullable por ora)
- [ ] Criar script de seed de dados para desenvolvimento
- [ ] Definir política WebSocket (FastAPI + Redis pub/sub)
- [ ] Avaliar LiteLLM para AI Gateway

### Antes do Sprint 3 (quando IA entra)
- [ ] Base regulatória mínima carregada (ver `AgenteRegulatorio_BaseCuradoria.md`)
- [ ] Agente de Curadoria configurado e testado com a sócia consultora
- [ ] Política de retenção de dados documentada e aprovada

### Antes do go-live com primeiro usuário real
- [ ] Seed de homologação aplicado em staging
- [ ] Sócia consultora operou o sistema por pelo menos 2 semanas em ambiente de teste
- [ ] Feedback da sócia incorporado antes de ampliar escopo

---

## 7. Nota sobre o time de agentes

O time formado por Claude Code, Codex e Gemini 3.1 tem perfis complementares. Uma recomendação operacional baseada nos pontos fortes de cada um:

**Claude Code / Claude:** melhor para redação técnica longa, revisão de documentação, análise de consistência entre documentos, geração de contratos e pareceres (Agente Redator).

**Codex (OpenAI):** melhor para geração de código estruturado, schemas JSON rígidos, function calling, migrations de banco, endpoints REST com validação forte.

**Gemini 3.1:** melhor para análise de documentos longos, PDFs de matrículas e laudos, contexto muito extenso, multimodalidade (Agente Extrator).

Isso está alinhado com a matriz do `Aditivo_arquitetural_política_multi_LLM.md` e deve guiar a divisão de tarefas também no desenvolvimento, não só nos agentes do produto.

---

*Documento produzido em 26/03/2026. Revisão recomendada a cada início de fase.*
