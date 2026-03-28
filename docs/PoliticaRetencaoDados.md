# Política de Retenção de Dados e Conformidade LGPD
**Projeto:** Plataforma Ambiental SaaS  
**Versão:** 1.0  
**Data:** 26/03/2026  
**Base legal:** Lei Geral de Proteção de Dados (Lei 13.709/2018)

---

## 1. Objetivo

Definir como os dados são tratados ao longo do ciclo de vida de um tenant: desde a contratação até o cancelamento e a exclusão definitiva. Isso é obrigação legal sob a LGPD e proteção jurídica tanto para a plataforma quanto para os tenants.

---

## 2. Categorias de dados e prazos de retenção

### 2.1 Dados de negócio (processos, clientes, imóveis, documentos)

| Evento | Ação | Prazo |
|--------|------|-------|
| Tenant ativo | Dados armazenados normalmente | Durante a vigência do contrato |
| Cancelamento do contrato | Dados ficam em modo somente-leitura | 90 dias após cancelamento |
| Fim do período de graça | Dados são anonimizados ou excluídos conforme opção do tenant | Após os 90 dias |
| Solicitação explícita de exclusão | Exclusão imediata do que for possível | Até 15 dias úteis após a solicitação |

**Exceção:** Dados que precisam ser mantidos por obrigação legal (ex: notas fiscais, contratos assinados, laudos com valor regulatório) seguem o prazo determinado pela legislação específica aplicável (geralmente 5 anos para documentos fiscais).

---

### 2.2 Dados pessoais dos usuários do sistema

| Tipo | Prazo de retenção | Fundamento |
|------|-------------------|------------|
| Dados de login e sessão | Excluídos após 30 dias do cancelamento da conta | Minimização |
| Logs de auditoria | 5 anos | Obrigação legal + segurança |
| Dados de uso (telemetria, métricas) | Anonimizados após 12 meses | Interesse legítimo |
| Dados de cobrança | 5 anos | Obrigação fiscal |

---

### 2.3 Dados de clientes finais (agricultores/produtores)

Esses dados pertencem ao tenant (escritório de consultoria), não à plataforma. A plataforma é operadora, não controladora desses dados.

| Tipo | Responsabilidade | Prazo sugerido |
|------|-----------------|----------------|
| CPF/CNPJ | Tenant (controlador) | Seguir prazo do tenant |
| Documentos pessoais | Tenant | Seguir prazo do tenant |
| Dados de processo ambiental | Tenant | Prazo regulatório aplicável |

**Recomendação para os tenants:** Incluir cláusula de retenção de dados nos contratos com seus clientes finais, alinhada à LGPD.

---

## 3. Fluxo de cancelamento de tenant

### Fase 1 — Notificação (Dia 0)
- Tenant solicita cancelamento ou inadimplência gera cancelamento automático
- Sistema envia e-mail de confirmação com:
  - Data de encerramento do acesso ativo
  - Data limite para exportar dados (90 dias)
  - Opção de solicitar exclusão antecipada
  - Link para exportar todos os dados

### Fase 2 — Período de graça (Dias 1–90)
- Tenant pode fazer login somente para exportar dados
- Nenhum processamento novo (sem IA, sem OCR, sem integrações)
- Sistema mantém todos os dados intactos
- Lembretes automáticos: Dia 30, Dia 60, Dia 80, Dia 88

### Fase 3 — Encerramento (Dia 91+)
- Sistema executa rotina de exclusão/anonimização
- O que é **excluído fisicamente:**
  - Arquivos no storage (PDFs, fotos, documentos)
  - Credenciais e chaves de integração
  - Dados pessoais identificáveis (nomes, CPFs, telefones, e-mails de clientes finais)
  - Tokens e sessões
- O que é **anonimizado** (mantido para fins estatísticos internos):
  - Contagens agregadas (quantos processos, quantos documentos)
  - Dados geoespaciais sem vínculo com pessoa
  - Metadados de uso do sistema (sem identificação)
- O que é **mantido integralmente:**
  - Registros fiscais e financeiros (5 anos — obrigação legal)
  - Logs de auditoria relevantes para obrigações legais (5 anos)
  - Dados necessários para defesa em processos judiciais em curso

### Fase 4 — Confirmação (Após exclusão)
- Sistema envia relatório de exclusão ao e-mail do admin do tenant
- Relatório contém: o que foi excluído, o que foi anonimizado, o que foi retido e por qual fundamento legal

---

## 4. Direitos dos titulares

A plataforma deve oferecer mecanismo para que os titulares de dados (clientes finais dos tenants) exercitem seus direitos sob a LGPD:

| Direito | Como exercer | Prazo de atendimento |
|---------|-------------|----------------------|
| Acesso aos dados | Solicitação por e-mail ao tenant | 15 dias úteis |
| Correção | Solicitação ao tenant → tenant corrige na plataforma | 15 dias úteis |
| Eliminação | Solicitação ao tenant → tenant executa na plataforma | 15 dias úteis |
| Portabilidade | Export em JSON/CSV disponível no painel | Imediato |
| Revogação de consentimento | Solicitação por e-mail ao tenant | 15 dias úteis |
| Informação sobre compartilhamento | Política de privacidade pública | Imediato |

**Nota:** A plataforma é operadora. O tenant é o controlador. Os direitos dos titulares são exercidos perante o tenant, que usa a plataforma para executá-los.

---

## 5. Dados sensíveis — tratamento especial

Os seguintes dados recebem tratamento adicional:

### 5.1 Certificados digitais A1
- Armazenados **apenas** com referência ao secret manager (nunca em texto puro no banco)
- Acesso restrito a processos autenticados específicos
- Todo uso auditado com timestamp, tenant e propósito
- Excluídos imediatamente se o tenant solicitar
- Alerta automático 30 dias antes do vencimento

### 5.2 Documentos de identidade (CPF, RG, passaporte)
- Armazenados com criptografia de coluna (pgcrypto) ou tokenização
- Visíveis apenas para usuários com permissão explícita
- Não aparecem em logs
- Não enviados para APIs de IA sem necessidade específica justificada

### 5.3 Coordenadas geográficas de propriedades
- Não são dados pessoais por si só, mas podem identificar o dono indiretamente
- Tratados com o mesmo cuidado de dados pessoais quando vinculados a CPF/CNPJ
- Não compartilhados fora do tenant sem autorização explícita

---

## 6. Compartilhamento de dados com terceiros

| Terceiro | Dados compartilhados | Fundamento | Contrato |
|----------|---------------------|------------|----------|
| Providers de IA (OpenAI, Gemini, Claude) | Texto de documentos (não dados pessoais brutos) | Execução do contrato | DPA assinado |
| Storage (AWS S3 / R2) | Arquivos binários | Execução do contrato | DPA assinado |
| Provedores de OCR | Imagens de documentos | Execução do contrato | DPA assinado |
| Data brokers governamentais | CPF/CNPJ para consulta | Execução do contrato | Contrato específico |
| WhatsApp / E-mail | Apenas dados de contato e conteúdo de mensagens | Execução do contrato | Termos do provider |

**Regra geral:** Nunca compartilhar mais do que o necessário para a tarefa específica. Para IA especificamente: anonimizar ou pseudonimizar sempre que possível antes de enviar ao LLM.

---

## 7. Implementação técnica obrigatória

### 7.1 Endpoint de exportação de dados
```
GET /tenant/export
```
Retorna ZIP com:
- Todos os clientes em CSV/JSON
- Todos os processos em JSON
- Lista de todos os documentos com URLs assinadas temporárias
- Histórico de tarefas e comunicações
- Metadados de configuração do tenant

### 7.2 Endpoint de solicitação de exclusão
```
POST /tenant/request-deletion
```
- Inicia fluxo de cancelamento
- Registra data da solicitação
- Envia confirmação por e-mail
- Agenda execução para 90 dias após (ou imediato se solicitado)

### 7.3 Job de exclusão agendada
```python
# Celery Beat — executar diariamente
@app.task
def process_tenant_deletions():
    tenants = get_tenants_past_grace_period()
    for tenant in tenants:
        execute_deletion_routine(tenant.id)
        send_deletion_confirmation(tenant.admin_email)
        log_deletion_audit(tenant.id)
```

### 7.4 Auditoria de exclusão
Todo processo de exclusão deve gerar registro em `core.audit_log` com:
- O que foi excluído
- O que foi anonimizado
- O que foi retido e por qual fundamento
- Hash de verificação de integridade
- Timestamp e usuário responsável (ou "sistema automatizado")

---

## 8. Responsabilidades

| Responsável | Obrigação |
|-------------|-----------|
| Plataforma (nós) | Infraestrutura segura, isolamento de tenants, ferramentas de exportação e exclusão, logs de auditoria |
| Tenant (escritório de consultoria) | Consentimento dos clientes finais, uso adequado dos dados, resposta aos direitos dos titulares |
| Cliente final (agricultor) | Fornecer dados corretos, informar mudanças |

---

## 9. Revisão desta política

Esta política deve ser revisada:
- A cada 12 meses
- Quando houver mudança relevante na LGPD ou regulamentação da ANPD
- Quando houver mudança na arquitetura que impacte o fluxo de dados
- Antes de qualquer expansão para GovTech (requisitos adicionais de dados públicos)

---

*Documento criado em 26/03/2026. Requer revisão jurídica antes do go-live comercial.*
