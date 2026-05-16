# 04 · Roadmap

**Documento:** Manifesto · Horizonte temporal
**Estado:** vivo · revisar mensalmente
**Última revisão:** 2026-05-15

---

Este documento mostra o horizonte de evolução do Regente Ambiental em três janelas temporais. Não é cronograma de sprint (isso vive em [`../estado/PROGRESSO_*.md`](../estado/)); é direção estratégica.

## Janela 1 — Curto prazo (próximas 4-8 semanas)

**Objetivo:** validar o painel do consultor com a sócia (primeira usuária real) e fechar o ciclo do MVP de consultoria.

### Frentes ativas

**Skills procedurais do agente Redator** — destrava o bloqueio mais antigo do projeto (skills aguardando PDFs-gabarito da sócia desde 23/04). Skills prioritárias:

1. `redator/oficio_semad_go.md` — ofício para o órgão ambiental de Goiás
2. `redator/memorial_car_sicar.md` — memorial descritivo para retificação CAR
3. `redator/resposta_notificacao_semad.md` — resposta a notificação com prazo
4. `redator/prad.md` — Plano de Recuperação de Área Degradada
5. `extrator/matricula_generica.md` — extração de matrícula imobiliária
6. `extrator/car_sicar.md` — extração de espelho CAR

**Sprint A2-legislacao** — formaliza o output do `LegislacaoAgent` com `LegislationContextContent`. Próximo agente a ser migrado para schema validado (conforme padrão A2-redator e A2-diagnostico).

**Ingestão de mais 3 estados** — adicionar SP, MG e TO ao corpus regulatório do `knowledge_catalog`. Atualmente: GO (3855 chunks), MS (4587), MT (13411), Federal (720). Próximo passo: 7 UFs cobertas.

**Cirurgia MemPalace** — remover stub no-op e referências espalhadas (58 ocorrências em 16 arquivos). Limpeza pendente desde 23/04.

**Hardening de produção** — finalizar checklist `ops/production-secrets-checklist.md` antes do primeiro deploy real com a sócia.

**Reunião institucional SEMAD-GO** — preparação de demo, deck e pitch específico. Objetivo: carta de anuência ou acesso a programa piloto regulatório.

### Critério de fim da janela

- Sócia consegue rodar 1 caso real do início ao fim no painel sem precisar de suporte técnico
- 6 skills prioritárias em produção
- 7 UFs no `knowledge_catalog`
- MemPalace excisado
- Deploy de produção homologado

## Janela 2 — Médio prazo (3-6 meses)

**Objetivo:** ampliar do MVP da sócia para os primeiros 5-10 tenants pagantes (outras consultorias), começar diálogo institucional concreto com órgãos públicos e abrir frente comercial bancária.

### Frentes principais

**Onboarding de tenants externos** — formalizar processo de criação de novo tenant, migração de dados iniciais, treinamento básico. Cada tenant que entra ensina o que o produto precisa virar.

**Frente cliente final (descongelar `client-portal/`)** — retomar Next.js do portal do cliente, com foco em três fluxos: cliente acompanha andamento do caso, cliente aprova proposta/contrato, cliente assina documentos. Hoje congelado.

**Frente campo (descongelar `mobile/`)** — retomar Expo do app de campo. Foco: coleta offline em campo (foto georreferenciada, ponto GPS, formulário de checklist) com sincronização posterior. Hoje congelado.

**Auditor de inconsistências do imóvel** — agente novo (`auditor_imovel`) que cruza CAR × matrícula × APP × Reserva Legal × Unidades de Conservação × embargo/MapBiomas usando PostGIS. Hoje a coluna `Property.geom` existe mas está vazia em todas as propriedades — o auditor depende de popular essa coluna primeiro (parser shapefile + ingestão por upload de KML/SHP).

**Conectores de e-mail inbound** — `AcompanhamentoAgent` lê inbox do tenant, identifica mensagens de órgão (IBAMA/SEMA/ICMBio), vincula ao processo correto e detecta exigência/prazo. Hoje só envio (SMTP/Resend); falta receber.

**Crawlers DOU/DOE automatizados** — `legislation_monitor.py` tem o esqueleto pronto e o Celery Beat tem o agendamento, mas os crawlers concretos por portal (DOU, DOE-GO, DOE-MG etc.) ainda não foram ativados em produção. Sair de ingestão manual via CLI para captura automática.

**Modelo comercial bancário** — desenhar e formalizar parceria com primeiro banco/cooperativa interessado em padronizar comprovação ambiental para crédito rural. Modelo provável: indicação de consultorias parceiras + lastro auditável da plataforma.

### Critério de fim da janela

- 5-10 tenants pagantes em produção
- Portal cliente e app mobile em uso real
- Primeiro contrato (ou MoU) com banco/cooperativa
- Primeira chancela institucional formal de órgão público (anuência, piloto, ou similar)
- Auditor de imóvel operacional em pelo menos 1 UF com geom populado

## Janela 3 — Longo prazo (6-18 meses)

**Objetivo:** consolidar o Regente como infraestrutura regulatória do consultor ambiental brasileiro e abrir frente concreta de GovTech.

### Diretrizes estratégicas

**Cobertura nacional do corpus regulatório** — alcançar 27 UFs no `knowledge_catalog`, com atualização automática via crawlers. Hoje 4 UFs (GO, MS, MT, Federal). Meta intermediária: 10 UFs até final da Janela 2.

**Integrações GovTech reais** — sair de "Carta de Anuência" para integração técnica concreta com pelo menos 1 órgão estadual: API bidireccional (consulta de status de protocolo, envio de dossiê estruturado, recebimento de despacho). Esse é o salto de "fornecedor de software" para "infraestrutura institucional".

**Marketplace de skills** — habilitar consultorias parceiras a contribuírem com skills de domínio específico (jurisprudência local, modelo de ofício regional, padrão de PRAD por bioma). Curadoria continua centralizada — skills validadas viram patrimônio do produto, com crédito ao tenant contribuidor.

**White-label operacional** — tenants grandes (cooperativa de consultorias, banco que oferece a plataforma como benefício) operam com identidade visual e domínio próprios. Capacidade já existe no design ([`../arquitetura/WHITELABEL.md`](../arquitetura/WHITELABEL.md)); falta primeira execução real.

**Previsibilidade preditiva** — sair de RAG (busca semântica do que existe) para sugestão preditiva (próximo passo provável, risco de pendência, prazo provável do órgão). Esse salto depende de massa de dados histórica que a Janela 2 vai gerar.

### Não-objetivos explícitos

Para clareza, eis o que **não** está no horizonte do Regente, mesmo em janela longa:

- Substituição de consultor por agente autônomo
- Decisão regulatória automática sem revisão humana
- Concorrência direta com SiCAR, Sinaflor ou módulos oficiais de licenciamento
- Marketplace peer-to-peer de consultoria (não intermediamos relação consultor-cliente)
- Geração automatizada de peças jurídicas para protocolo direto sem revisão da sócia/consultor responsável

## Como este roadmap se atualiza

A cada fechamento de janela curta (mensal), este documento é revisto. Decisões grandes (entrar em GovTech ativo, descongelar frente cliente, mudar modelo comercial) viram ADR antes de virar parágrafo aqui. O roadmap reflete decisões tomadas — não as propõe.
