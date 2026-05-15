# Agente de Curadoria Regulatória — Base de Conhecimento
**Projeto:** Plataforma Ambiental SaaS  
**Versão:** 1.0  
**Data:** 26/03/2026

---

## 1. Por que esse documento existe

O Agente Regulatório é o componente mais estratégico do produto. Ele responde perguntas como:
- "Essa propriedade precisa de PRAD ou basta recompor a APP?"
- "Qual é o prazo para protocolar no IBAMA depois do embargo?"
- "O município de Goiânia aceita CAR como compensação de RL?"

Para responder bem, ele precisa de uma base de conhecimento sólida, atualizada e curada por especialistas. Essa base não existe sozinha — alguém precisa construí-la e mantê-la.

**Essa pessoa é a sócia consultora ambiental.**

O sistema precisa ser desenhado para tornar essa curadoria simples, não técnica, sustentável e auditável.

---

## 2. O que é a base regulatória

A base regulatória é o conjunto de documentos e conhecimentos que o Agente Regulatório vai consultar via RAG (Retrieval-Augmented Generation). Ela é composta por três camadas:

### Camada 1 — Legislação federal e estadual
Leis, decretos, resoluções e portarias que regem o licenciamento ambiental, CAR, outorgas e regularização fundiária.

Exemplos:
- Lei 12.651/2012 (Código Florestal)
- Resolução CONAMA 237/1997 (Licenciamento ambiental)
- Resolução CONAMA 302/2002 (APPs em reservatórios)
- Decreto 7.830/2012 (SICAR e CAR)
- Instrução Normativa MMA 02/2014 (Procedimentos CAR)
- Legislação estadual SEMAD/Goiás
- Instruções normativas municipais relevantes

### Camada 2 — Precedentes internos
Casos resolvidos pelo escritório com descrição do problema, caminho adotado e resultado. São o conhecimento mais valioso — o que diferencia o sistema de uma busca no Google.

Exemplos:
- "Embargo IBAMA em APP de 30m: como conseguimos o desembargo em 45 dias"
- "CAR com sobreposição em terra indígena no MT: tratativa com FUNAI"
- "Retificação de área em matrícula divergente do SIGEF: passo a passo"

### Camada 3 — Checklists e templates operacionais
Listas de documentos exigidos por cada órgão, por tipo de processo e por município. Modelos de ofício, memorial descritivo, PRAD.

---

## 3. Agente de Curadoria Regulatória

### 3.1 Missão

Tornar o processo de manutenção da base regulatória simples para a consultora, garantindo que o conteúdo esteja sempre atualizado, versionado e rastreável.

### 3.2 O que o agente faz

**Curadoria assistida:**
- Quando a consultora faz upload de um novo documento (lei, portaria, acórdão), o agente lê, extrai os pontos-chave, sugere categorização e resumo
- A consultora revisa e aprova ou edita — com um clique
- O documento é indexado, vetorizado e entra na base

**Alerta de atualização:**
- O agente monitora fontes públicas (Diário Oficial da União, Diário Oficial de Goiás, DOU IBAMA) em busca de novas normas relacionadas ao escopo cadastrado
- Quando detecta algo relevante, cria uma tarefa para a consultora revisar
- A consultora decide: incorporar, descartar ou marcar como "verificar depois"

**Revisão de vigência:**
- Periodicamente (sugestão: mensalmente), o agente verifica se alguma norma da base foi revogada, alterada ou substituída
- Gera relatório de "itens que precisam de revisão"
- A consultora confirma ou atualiza

**Vetorização de precedentes:**
- Quando a consultora registra como um caso difícil foi resolvido, o agente estrutura o precedente, extrai palavras-chave e o torna buscável
- Precedentes similares aparecem automaticamente quando o Agente Regulatório analisa um novo caso

### 3.3 Interface para a consultora

A consultora não precisa saber o que é RAG, embedding ou vetorização. Para ela, o sistema deve parecer um **acervo digital organizado** com três ações simples:

```
[Adicionar documento]   [Registrar precedente]   [Ver alertas de atualização]
```

**Fluxo de adição de documento:**
1. Consultora clica em "Adicionar documento"
2. Faz upload do PDF (lei, portaria, resolução)
3. O agente lê e sugere:
   - Título
   - Tipo (lei federal / resolução / portaria estadual / norma interna)
   - Jurisdição (federal / GO / municipal)
   - Resumo em linguagem simples (máx. 5 linhas)
   - Tópicos relacionados (CAR, outorga, APP, embargo...)
4. Consultora revisa, edita se necessário, confirma
5. Documento entra na base com data de vigência

**Fluxo de registro de precedente:**
1. Consultora clica em "Registrar precedente"
2. Preenche campos guiados:
   - Tipo do caso (embargo / CAR / outorga / licença / retificação...)
   - Estado/Município
   - Órgão envolvido
   - Qual era o problema
   - O que foi feito (passo a passo)
   - Resultado final
   - Tempo decorrido
3. O agente enriquece com palavras-chave e vincula a normas relacionadas
4. Precedente entra na base disponível para o Agente Regulatório

---

## 4. Arquitetura técnica do Agente de Curadoria

### 4.1 Componentes

```
Interface (painel web)
   -> API Core (FastAPI)
   -> Worker de curadoria (Python + Celery)
          -> OCR pipeline (documentos PDF)
          -> LLM para extração e resumo (Gemini preferencial — contexto longo)
          -> pgvector (vetorização dos chunks)
   -> Scheduler de monitoramento (Celery Beat)
          -> Leitura de RSS/scraping de fontes regulatórias
          -> Verificação de vigência
```

### 4.2 Provider de IA recomendado

Para curadoria regulatória, o Gemini é a escolha preferencial porque:
- Janela de contexto longa (PDFs extensos de legislação)
- Boa performance em leitura de documentos jurídicos em português
- Suporte a multimodalidade (PDFs escaneados de leis antigas)

Fallback: Claude para síntese e revisão de texto estruturado

### 4.3 Fontes monitoradas automaticamente (sugestão inicial)

```python
FONTES_MONITORAMENTO = [
    # Federais
    "https://www.in.gov.br/servicos/dou-rss",
    "https://www.ibama.gov.br/index.php?option=com_content&view=category&layout=blog&id=197",
    "https://www.ana.gov.br/todas-as-noticias",
    "http://www.planalto.gov.br/ccivil_03/Ato2023-2026/",
    
    # Goiás
    "https://www.gabinetecivil.go.gov.br/paginas/diario_oficial.html",
    "https://semad.go.gov.br/noticias",
    
    # CONAMA
    "https://conama.mma.gov.br/",
]
```

### 4.4 Tabelas do banco envolvidas

```
ai.rag_sources
  -> registra cada documento ou precedente
  -> campos: scope_type, source_type, title, jurisdiction, state, municipality
  -> published_at, effective_at, revoked_at
  -> status: active | revoked | superseded | pending_review

ai.rag_chunks
  -> chunks do texto vetorizados
  -> embedding armazenado em pgvector
  -> vinculado ao rag_source

ai.precedents
  -> precedentes internos estruturados
  -> campos específicos de caso ambiental
  -> vinculado a processos reais do sistema

core.audit_log
  -> toda adição, atualização ou remoção da base é auditada
  -> quem alterou, quando, o que mudou
```

### 4.5 Configuração do Agente de Curadoria

```python
AGENTE_CURADORIA = {
    "agent_type": "curador_regulatorio",
    "description": "Mantém a base de conhecimento regulatório atualizada",
    "triggers": [
        "upload_documento",          # usuário fez upload
        "registro_precedente",       # usuário registrou caso
        "schedule_monitoramento",    # CRON diário
        "schedule_revisao_vigencia", # CRON mensal
    ],
    "provider_strategy": "auto",
    "preferred_provider": "gemini",  # contexto longo para leitura de leis
    "fallback_provider": "anthropic",  # síntese e estruturação
    "review_required": True,         # SEMPRE passa pela consultora
    "output_schema": {
        "title": "str",
        "summary": "str (máx 500 chars)",
        "source_type": "enum",
        "jurisdiction": "enum",
        "key_topics": "list[str]",
        "effective_at": "date",
        "revoked_at": "date|null",
        "confidence": "float 0-1"
    }
}
```

---

## 5. Orientações para a consultora sócia

### 5.1 Por onde começar — base mínima inicial

Antes do sistema ir a ar com clientes, a consultora precisa carregar a base mínima. Sugerimos a seguinte ordem:

**Semana 1 — Legislação federal essencial (prioridade máxima)**
- [ ] Lei 12.651/2012 — Código Florestal completo
- [ ] Decreto 7.830/2012 — SICAR
- [ ] Resolução CONAMA 237/1997 — Licenciamento
- [ ] Resolução CONAMA 302/2002 — APPs
- [ ] IN MMA 02/2014 — Procedimentos CAR
- [ ] Lei 9.985/2000 — SNUC (Unidades de Conservação)

**Semana 2 — Legislação estadual (Goiás)**
- [ ] Lei Estadual 18.104/2013 — Política Estadual de Meio Ambiente GO
- [ ] Decreto Estadual 8.007/2014 — PRAD em Goiás
- [ ] Instruções normativas vigentes da SEMAD
- [ ] Portarias do NATURATINS (se atende MT/TO)
- [ ] Legislação municipal dos principais municípios atendidos

**Semana 3 — Precedentes internos (mais valioso)**
- [ ] Registrar os 10 casos mais frequentes resolvidos pelo escritório
- [ ] Pelo menos 3 casos de embargo IBAMA resolvidos
- [ ] Pelo menos 3 casos de CAR retificado
- [ ] Pelo menos 2 casos de outorga de água

**Semana 4 — Checklists operacionais**
- [ ] Checklist de documentos para cada tipo de processo que atende
- [ ] Lista de exigências por órgão (SEMAD, IBAMA, ANA, INCRA)
- [ ] Modelos de ofício e memorial que já usa

### 5.2 Cadência de manutenção

| Frequência | Atividade |
|---|---|
| Quando ocorrer | Adicionar nova lei ou portaria que impacta o negócio |
| Quando ocorrer | Registrar precedente de caso novo resolvido |
| Semanal | Revisar alertas de atualização gerados pelo agente |
| Mensal | Revisar relatório de vigência (normas possivelmente revogadas) |
| Trimestral | Auditar a base: o que está desatualizado, o que falta |
| Anual | Revisão completa da base com nova legislação do período |

### 5.3 O que NÃO fazer

- Não precisa formatar os PDFs antes de subir — o sistema processa automaticamente
- Não precisa fazer resumos manualmente — o agente sugere, você revisa
- Não precisa saber quais partes são "importantes" — o sistema chunka e indexa tudo
- Não precisa carregar a legislação de uma vez — comece com o essencial e vá crescendo

---

## 6. Métricas de qualidade da base

O sistema deve exibir para a consultora um painel simples de saúde da base:

```
Base Regulatória — Saúde
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Normas ativas:          47
⚠️  Pendentes de revisão:   3
🔴 Revogadas (não limpas):  1
📝 Precedentes internos:   12
🗂️  Checklists operacionais: 8
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Última atualização:  22/03/2026
Próxima revisão de vigência: 26/04/2026
```

---

## 7. Diferencial competitivo desta base

O Agente Regulatório alimentado por uma base bem curada entrega o que nenhum sistema genérico consegue:

- Respostas específicas para o contexto de Goiás e Centro-Oeste
- Precedentes reais do escritório (ninguém mais tem isso)
- Conhecimento sobre o comportamento dos analistas de cada órgão
- Checklists validados por casos reais, não apenas pela legislação formal

**Essa base é o ativo mais valioso do produto. Com o tempo, ela se torna a principal barreira de entrada para concorrentes.**

---

## 8. Roadmap do Agente de Curadoria

| Fase | Funcionalidade |
|---|---|
| Sprint 3 | Upload manual + extração assistida por IA |
| Sprint 3 | Vetorização e integração com Agente Regulatório |
| Sprint 4 | Interface de revisão de alertas |
| Sprint 4 | Registro de precedentes guiado |
| Sprint 5 | Monitoramento automático de fontes |
| Sprint 5 | Relatório mensal de vigência |
| Fase 6 | Integração com bases externas (CONAMA, SISNAMA) |

---

*Documento criado em 26/03/2026. Responsável pela base de conhecimento: sócia consultora ambiental.*
