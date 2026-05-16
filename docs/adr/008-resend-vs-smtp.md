# ADR-008 · Resend para waitlist, SMTP mantido para fluxos internos

**Status:** Aceito (coexistência transicional)
**Data:** 2026-05-13 (Sprint Waitlist B1); formalizada como ADR em 2026-05-15
**Decisores:** sócia + tecnologia
**Relacionado:** [`./004-regente-vs-amigao.md`](./004-regente-vs-amigao.md)

---

## Contexto

Até a Sprint Waitlist, todos os e-mails do Regente saíam por **SMTP**: provedor configurável (Mailtrap em dev, qualquer SMTP real em prod), serviço único em `app/services/email.py`, cobre notificações ao consultor, ao cliente final no portal, comunicação institucional.

A Sprint Waitlist (lead público do Regente Ambiental) trouxe três necessidades novas:

1. **Domínio próprio do produto** — leads recebem e-mail de `contato@regenteambiental.com.br`, não de `noreply@amigao.com`
2. **Audience como ativo de marketing** — leads precisam aparecer como contatos em CRM/audience para campanhas futuras
3. **Deliverability** — domínio `regenteambiental.com.br` é novo; precisa de provider com reputação consolidada e ferramentas de warmup/monitoring

SMTP atende #1 (configurar `EMAILS_FROM_EMAIL`), mas não atende #2 e #3 sem trabalho operacional extra.

Opções consideradas:

1. **Migrar tudo para Resend** — substitui SMTP em todos os fluxos
2. **Manter SMTP e adicionar Resend só para waitlist** — coexistência
3. **Manter SMTP e construir audience própria** — sem provider terceiro

## Decisão

**Coexistência transicional.**

- **SMTP** (configurado em `SMTP_*`) continua cobrindo: notificações do consultor, e-mails do portal cliente (quando descongelar), comunicação interna entre tenant e cliente final
- **Resend** (configurado em `RESEND_*`) cobre **exclusivamente** o fluxo da waitlist: welcome email, drip campaign (D+7, D+14, D+21), upsert no Audience

Migração completa do `EmailService` para Resend fica para sprint dedicada futura — sem urgência enquanto SMTP atende bem os fluxos internos.

### Variáveis de ambiente

```bash
# SMTP — fluxos internos (mantido)
SMTP_HOST=...
SMTP_USER=...
SMTP_PASSWORD=...
EMAILS_FROM_EMAIL=noreply@amigao.com   # domínio interno; renomeação futura
EMAILS_FROM_NAME=Regente Ambiental      # marca visível (renomeação já feita)

# Resend — waitlist (novo)
RESEND_API_KEY=re_...
RESEND_AUDIENCE_ID=...
RESEND_FROM_EMAIL=contato@regenteambiental.com.br
RESEND_FROM_NAME=Regente Ambiental
```

## Por que essa divisão (e não migrar tudo)

**Risco de mudar provider de e-mail crítico (fluxos internos):**
- Deliverability é frágil — domínio com reputação muda comportamento ao mudar provider
- Fluxos internos rodam para clientes pagantes; falha de e-mail aqui é perda comercial direta
- Mudança implicaria refactor de `email.py` + testes + rollout cuidadoso

**Benefício de Resend só para waitlist:**
- Domínio `regenteambiental.com.br` ainda jovem — Resend é melhor para warmup
- Audience nativa do Resend é trivial de usar (`POST /audiences/{id}/contacts`)
- Drip campaign + métricas de deliverability vêm de graça
- Zero risco para fluxos internos (escopo isolado)

## Consequências

**Positivas:**
- Waitlist sai com infra adequada desde o dia 1 (domínio próprio, audience como ativo)
- Fluxos internos seguem estáveis em SMTP confiável
- Risco operacional mínimo (escopos isolados)
- Mantém porta aberta para migração total no futuro

**Negativas:**
- **Dois caminhos de e-mail no código** — `email.py` (SMTP) + `resend_client.py` (Resend) — complexidade leve
- **Templates duplicados** — welcome em SMTP e em Resend seguiriam HTMLs separados se quisermos paridade total (mitigação: hoje template welcome existe só em Resend)
- **Métricas separadas** — entrega via SMTP vai para `EMAIL_DELIVERY_TOTAL` simples; via Resend depende de webhook + dashboard externo

**Mitigações:**
- Camada de abstração futura (`EmailService.send(template, audience, ...)` que escolhe SMTP ou Resend pelo contexto) — não urgente
- Quando todos os fluxos internos forem migrados, manter um único arquivo `email.py` com adapter pattern

## Drip campaign (escopo do Resend)

| Passo | Quando dispara | Conteúdo |
|---|---|---|
| Welcome | imediato após cadastro | Boas-vindas + próximos passos |
| Drip D+7 | 7 dias após cadastro | Educativo (regulação, casos comuns) |
| Drip D+14 | 14 dias após cadastro | Bastidor da plataforma |
| Drip D+21 | 21 dias após cadastro | Convite para beta |

Idempotência via UNIQUE (lead_id, step) em tabela `pre_cadastros_drip_log`. Beat scheduler scan a cada 15 min.

## Migração futura (não decidida hoje)

Quando justificar, migração completa para Resend seguiria:

1. **Fase 1:** envolver Resend SDK em `EmailService.send(...)`
2. **Fase 2:** rotear por config (`EMAIL_PROVIDER=resend|smtp`)
3. **Fase 3:** validar deliverability paralelo (shadow envios em ambiente teste)
4. **Fase 4:** rollout gradual (10% → 50% → 100%)
5. **Fase 5:** depreciação de `SMTP_*` em config (mantém código por mais 1 ciclo de release)

Sem data marcada. Quando entrar, vira ADR próprio.

## Status de execução

| Item | Estado |
|---|---|
| `app/services/resend_client.py` | ✅ |
| `RESEND_*` em `.env.example` | ✅ |
| Welcome email funcional | ✅ Sprint Waitlist PR 2 |
| Audience upsert | ✅ |
| Drip D+7 / D+14 / D+21 | ⚠️ Em curso (Sprint Waitlist PR 3) |
| Tabela `pre_cadastros_drip_log` | ✅ |
| Beat scheduler `scan_due_drip_emails` | ⚠️ Implementado, ajustes em curso |

## Relação com outros ADRs

- [`./004-regente-vs-amigao.md`](./004-regente-vs-amigao.md) — `RESEND_FROM_EMAIL=contato@regenteambiental.com.br` materializa identidade pública; `EMAILS_FROM_EMAIL=noreply@amigao.com` é codinome técnico interno
