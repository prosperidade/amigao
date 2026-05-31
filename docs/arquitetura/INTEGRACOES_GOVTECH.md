# Integrações GovTech

**Documento:** Arquitetura · referência viva
**Estado:** roadmap arquitetural · execução parcial
**Última revisão:** 2026-05-15

---

Como o Regente Ambiental integra (e pode integrar) com órgãos governamentais brasileiros. Este documento descreve o que existe hoje, o que está pronto para ativar, e o que entra em janela futura.

## Princípio

O Regente não compete com sistemas oficiais (SiCAR, Sinaflor, módulos de licenciamento estadual). O Regente:

1. **Consome dados oficiais** (legislação, normas, despachos) para alimentar o consultor
2. **Prepara dossiês** que entram nesses sistemas de forma organizada e rastreável
3. **Espelha decisões** dos órgãos para acompanhamento do consultor

Em janela futura (`../manifesto/04-ROADMAP.md`), pode ter integração bidirecional formal com órgãos parceiros — esse salto depende de chancela institucional e contratos.

## Tipos de integração

### Tipo 1 — Crawler legislativo (consumo unilateral)

**O quê:** captura periódica de normas publicadas no Diário Oficial da União e Diários Oficiais estaduais. Sem interação com o órgão; apenas leitura pública.

**Estado atual:**

- Esqueleto pronto em `app/services/legislation_monitor.py` (205 linhas)
- Tasks Celery em `app/workers/legislation_tasks.py`
- Schedule no Celery Beat:
  - `monitor-legislation-dou-daily` — DOU às 06:00 BRT
  - `monitor-legislation-doe-daily` — DOEs estaduais às 06:00 BRT
  - `monitor-legislation-agencies-weekly` — portais IBAMA/SEMAD às 03:00 segunda
- Crawlers concretos em `app/services/crawlers/`:
  - `dou_crawler.py` (com User-Agent identificável)
  - `ibama_crawler.py`
  - `doe_crawler.py`

**Status real:** crawlers existem mas **não estão ativos em produção**. Hoje a ingestão é manual via CLI (`scripts/ingest_legislacao_estadual.py`, `scripts/ingest_federais_canonicos.py`). 25 diplomas iniciais foram ingeridos manualmente.

**Para ativar:** descomentar schedule no `celery_app.py` em produção + monitorar primeiras semanas com cuidado (variabilidade de UA, captcha, mudança de layout dos portais).

### Tipo 2 — Consulta de status de protocolo (futuro)

**O quê:** dado um número de protocolo SEMAD-GO (ou outro órgão), buscar o estado atual do processo (deferido, em análise, com pendência, etc.).

**Estado atual:** **não existe.** Sistemas estaduais variam enormemente — alguns têm API pública, alguns exigem login institucional, alguns só têm HTML para scrape.

**Quando entra:** janela 2 do roadmap, condicionado a parceria institucional com pelo menos 1 órgão estadual.

### Tipo 3 — Envio de dossiê estruturado (futuro distante)

**O quê:** em vez do consultor logar no portal do órgão e fazer upload manual de PDFs, o Regente envia o dossiê via API (ou padrão de troca de dados estruturado) e recebe número de protocolo de volta.

**Estado atual:** **não existe.** Depende de acordo formal e protocolo técnico definido com o órgão.

**Quando entra:** janela 3 do roadmap. Este é o salto de "fornecedor de software" para "infraestrutura institucional" mencionado no manifesto.

### Tipo 4 — Recebimento de despacho/notificação (futuro)

**O quê:** órgão envia despacho ou notificação ao Regente (via webhook, e-mail formal, ou API), Regente vincula automaticamente ao processo correto e gera tarefa no Kanban do consultor.

**Estado atual:**
- Esqueleto em `AcompanhamentoAgent` (`app/agents/acompanhamento.py`)
- **WhatsApp inbound — IMPLEMENTADO (dormente) na PR 2.1.** Webhook
  `POST /api/v1/messaging/whatsapp/webhook` (`app/api/v1/messaging.py`) recebe a mensagem
  do cliente, identifica o `Client` pelo telefone e integra a um **caso já aberto** (inbound
  nunca cria caso — decisão 2026-05-28). Sem caso → thread órfão + alerta interno; sem `Client`
  → ignora. Autenticado por **HMAC-SHA256** (`X-Hub-Signature-256` × `EVOLUTION_WEBHOOK_SECRET`);
  sem secret configurado, fica **dormente** (não exige assinatura). Detalhe da superfície em
  [`API_v1.md`](./API_v1.md); fluxo ponta a ponta em [`FLUXOS_E2E.md`](./FLUXOS_E2E.md) (fluxo 7).
  Provider plugável (abaixo). **Falta:** credenciais reais da Evolution + idempotência por
  `external_msg_id`.
- **Connector de e-mail inbound (Resend) — NÃO existe ainda.** Recebimento de e-mail do órgão
  segue manual (consultor encaminha). Só há placeholders de config (`EMAIL_INBOUND_PROVIDER`,
  `RESEND_INBOUND_WEBHOOK_SECRET`) — Resend Inbound não habilitado no plano/domínio.

**Provider plugável de WhatsApp** (`app/services/messaging/`):

| Componente | Estado |
|---|---|
| `WhatsAppProvider` (abstrato) + `InboundMessage` (schema) | Contrato comum |
| `EvolutionProvider` (httpx) | **Real** — default (`WHATSAPP_PROVIDER=evolution`) |
| `ZAPIProvider` | **Stub** (`NotImplementedError`) — placeholder de config `ZAPI_*` |
| `registry.get_whatsapp_provider()` | Resolve o provider por `settings.WHATSAPP_PROVIDER` |

A **instância Evolution** está disponível no `docker-compose` (image
`atendai/evolution-api:v2.1.1`) sob `profiles: ["whatsapp"]` — fica dormente e sobe sob demanda
com `docker compose --profile whatsapp up -d evolution`.

**Quando entra:** WhatsApp inbound já entrou (dormente, aguardando credenciais). O connector de
e-mail inbound (Resend) segue na **janela 2** — vale para qualquer órgão e para banco/cooperativa também.

### Tipo 5 — Cruzamento de dados espaciais (consumo)

**O quê:** dado um polígono de imóvel (Property.geom), verificar sobreposição com:
- APP (Áreas de Preservação Permanente)
- Reserva Legal declarada
- Unidades de Conservação federais (ICMBio) e estaduais
- Terras indígenas (FUNAI)
- Quilombolas (INCRA)
- Embargos do IBAMA
- Desmatamento detectado (PRODES/MapBiomas)

**Estado atual:**
- `Property.geom` (PostGIS, SIRGAS 2000) existe, mas **vazia em todas as propriedades**
- Sem parser de shapefile/KML para popular
- Sem agente `auditor_imovel` que faça o cruzamento
- Sem base de dados de UCs/TI/Embargos carregada no Postgres local

**Quando entra:** janela 2. Sequência: parser shapefile → ingestão de bases públicas (CNUC, base FUNAI, base IBAMA) → agente auditor → endpoint `POST /properties/{id}/audit`.

## Órgãos no roadmap

### Estadual (prioritário)

Onde o CAR é operado de fato (Lei 12.651). Lista priorizada por nível de digitalização e potencial de parceria:

| Estado | Órgão | Sistema próprio | Estado da relação |
|---|---|---|---|
| GO | SEMAD-GO | Cadastro estadual + integração SiCAR | **Possível reunião institucional** |
| MG | SEMAD-MG / IEF | SLA estadual + SiCAR | A explorar |
| MT | SEMA-MT | Sistema próprio + SiCAR | A explorar |
| MS | IMASUL / SEMADESC | Sistema próprio + SiCAR | A explorar |
| SP | CETESB / IF-SP | SIGAM + SiCAR | A explorar |
| Outros | Diversos | Variado | Janela 3 |

### Federal

| Órgão | Sistema | Quando |
|---|---|---|
| SFB (Serviço Florestal Brasileiro) | SiCAR (módulo nacional do CAR) | Janela 3 — conversa estratégica longa |
| IBAMA | Sinaflor (DOF), CNUC, SIBBR, fiscalização | Janela 3 |
| ICMBio | Sistema de manejo, UCs federais | Janela 3 |

### Municipal

Geralmente sem sistema próprio. Quando existe (capitais e municípios grandes), integração ad-hoc por contrato. Não está no roadmap principal.

## Base de conhecimento já indexada (hoje)

`knowledge_catalog` tem **22.573 chunks** distribuídos em:

| Jurisdição/UF | Chunks | Cobertura |
|---|---|---|
| Federal | 720 | Código Florestal, LGPD, PNMA, principais resoluções CONAMA |
| GO | 3.855 | Lei 18.104/2013 + decretos + IN SEMAD |
| MS | 4.587 | Lei estadual + decretos + IN SEMADESC/IMASUL |
| MT | 13.411 | Lei estadual + decretos + IN SEMA (volume alto por causa de cobertura mais completa) |

Próximos UFs na fila (semana de 19-23/05): SP, MG, TO.

## Padrões técnicos para integrações futuras

Diretrizes para quando novas integrações entrarem em produção:

### Inbound (recebimento de notificação)

**Preferência de protocolo:**
1. **Webhook HTTPS com assinatura HMAC** (ideal)
2. **Push via API REST com auth Bearer**
3. **E-mail formal com PGP/S-MIME** (legacy mas funcional)
4. **E-mail sem assinatura + heurística + LLM** (fallback)

**Validação obrigatória:**
- Verificação de origem (whitelist de IPs, assinatura HMAC, certificado mTLS)
- Idempotência por message_id
- Replay protection (timestamp + nonce)

> **Aplicado hoje (WhatsApp inbound, PR 2.1):** assinatura **HMAC-SHA256** do corpo cru
> (`X-Hub-Signature-256`) já é a verificação de origem. **Idempotência por message_id ainda
> NÃO implementada** — reentrega do provider duplica `Message`. Replay protection idem.
> Endurecer junto com a ativação das credenciais.

**Persistência:**
- Cria `Communication` com `source=govtech_inbound`
- Vincula ao `Process` correspondente
- Cria `Task` para o consultor responsável
- Registra em `AuditLog` com hash chain

> **Aplicado hoje (WhatsApp inbound, PR 2.1):** grava `Message` em `CommunicationThread`
> (`channel="whatsapp"`, `provider="evolution"`) do caso aberto; sem caso → thread órfão
> (`process_id NULL`) + `AuditLog action="inbound_orphan"` + evento realtime. Mídia vira
> `Document` (`source="whatsapp"`). Ainda **não cria `Task`** automática.

### Outbound (envio de dossiê / consulta)

**Padrão:**
- HTTP client com retry + circuit breaker (`tenacity` ou similar)
- Timeout duro (30s)
- Logging completo (request + response + duração + status)
- Métrica Prometheus dedicada por órgão
- Idempotência por `process_id + action`
- Audit log de cada envio

**Credenciais:**
- Por tenant quando o órgão exige login institucional do tenant
- Centralizadas no Regente quando o órgão dá acesso por API com credencial única

## Pendências críticas

| Item | Status |
|---|---|
| Crawlers DOU/DOE em produção | Esqueleto + crawlers prontos, **não ativados** |
| `Property.geom` popular | Bloqueia agente `auditor_imovel` |
| Parser shapefile/KML | Não existe |
| Ingestão de base de UCs/TI/Embargos | Não existe |
| Canal WhatsApp inbound (Evolution) | **Implementado, dormente** — webhook + provider plugável prontos; falta credencial real + idempotência |
| Connector e-mail inbound (Resend) | Não existe — só placeholders de config |
| Primeira parceria institucional formal | A negociar (SEMAD-GO mais provável) |

## Próximas leituras

- [`BASE_REGULATORIA.md`](./BASE_REGULATORIA.md) — detalhe da base `knowledge_catalog`
- [`PIPELINE_OCR.md`](./PIPELINE_OCR.md) — pipeline que prepara documentos do consultor
- [`../manifesto/04-ROADMAP.md`](../manifesto/04-ROADMAP.md) — quando cada integração entra
