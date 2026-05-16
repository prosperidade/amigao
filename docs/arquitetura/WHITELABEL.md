# White-label

**Documento:** Arquitetura · referência viva
**Estado:** capacidade arquitetural pronta · execução real pendente
**Última revisão:** 2026-05-15

---

Política white-label do Regente Ambiental: como tenants podem operar com identidade visual, domínio e credenciais próprias usando o Regente como motor invisível.

## Princípio

Em modo white-label, **cada tenant pode aparecer aos próprios clientes finais como se a plataforma fosse dele**. O Regente é o motor; a marca pode ser do tenant.

Isso não é "duas marcas comerciais". Isso é **uma capacidade de personalização por tenant** que reduz custo operacional da plataforma central e aumenta autonomia do cliente.

## O que o tenant pode configurar

### Identidade visual

| Item | Como configurado |
|---|---|
| Logotipo no painel | Upload no Settings; persistido como `Tenant.logo_url` (futuro — TODO) |
| Cor primária | Campo `Tenant.brand_primary_color` (futuro — TODO) |
| Nome exibido | `Tenant.display_name` sobrescreve `PROJECT_NAME` em e-mails e PDFs |
| Cabeçalho de PDF | Template customizável por tenant (campo `Tenant.pdf_header_template`) |
| Rodapé de PDF | idem |
| Favicon | Hosted estaticamente, mapping por subdomínio |

### Domínio próprio

- Tenant aponta CNAME do próprio subdomínio (ex: `consultoria-xyz.com.br`) para o domínio do Regente
- TLS via Let's Encrypt automático (Caddy/Traefik na frente do API)
- Cookies/CORS sensíveis a domínio (validar em produção)

### Credenciais externas próprias

Tenant pode conectar e gerenciar:

**IA**
- `Tenant.openai_api_key` (opcional)
- `Tenant.gemini_api_key` (opcional)
- `Tenant.anthropic_api_key` (opcional)

O AI Gateway honra credenciais do tenant quando configuradas; cai no padrão da plataforma quando vazias. Custo da IA vai para a conta do tenant nesses casos.

**E-mail**
- SMTP próprio (`Tenant.smtp_*` — TODO)
- Resend próprio (`Tenant.resend_api_key` — TODO)

Quando o tenant usa credenciais próprias, **a entrega de e-mail vai pela conta do tenant**. Reputação de domínio é do tenant.

**Storage**
- S3 próprio (`Tenant.s3_*` — TODO, baixa prioridade)
- Útil para tenants que exigem residência de dados em conta própria

### Templates de contrato e proposta

- `ContractTemplate.tenant_id` permite contratos por tenant
- `ProposalTemplate.tenant_id` (futuro) permite propostas por tenant
- Cláusulas, formato, marca aplicados conforme o template

### Prompts próprios

- `PromptTemplate.tenant_id` permite override por tenant
- Hierarquia: tenant > global > hardcoded
- Permite tenant ajustar tom, vocabulário, estilo das peças geradas pelos agentes

### Skills próprias (futuro)

Roadmap janela 3 (`../manifesto/04-ROADMAP.md`): marketplace curado de skills. Tenants podem contribuir skills de domínio específico (jurisprudência local, modelos regionais), passar por curadoria central, e ganhar crédito ao serem promovidas.

## Camadas inegociáveis (mesmas para todos)

Mesmo em modo white-label, **algumas coisas permanecem do Regente**:

1. **Núcleo arquitetural** — multi-tenant, audit chain, citation evaluator, cost cap, governança IA
2. **Princípios** — IA propõe, humano decide; tudo é auditável; etc.
3. **Backend único** — todos os tenants rodam no mesmo cluster do Regente
4. **Schema do banco** — não há divergência de schema por tenant
5. **Atualizações de plataforma** — todos os tenants recebem novas features simultaneamente
6. **Conformidade LGPD e segurança** — políticas da plataforma valem para todos

## Modelos comerciais white-label

O modo white-label habilita três modelos comerciais distintos:

| Modelo | Audiência | Como funciona |
|---|---|---|
| Cooperativa de consultorias | Rede com identidade compartilhada | Marca da cooperativa no painel; cada associada é um sub-tenant |
| Plataforma corporativa | Banco/cooperativa de crédito | Cliente do banco acessa "Plataforma Ambiental do Banco X", motor é Regente |
| Reseller premium | Consultoria-mãe revende para parceiras | Consultoria principal opera como master tenant + sub-tenants |

Esses modelos comerciais não estão executados hoje — são possibilidades habilitadas pela arquitetura.

## Implicações em billing

White-label muda o modelo de cobrança:

- **Plano Standard** — tenant usa identidade Regente, credenciais da plataforma, custo de IA incluído (até teto do plano)
- **Plano White-label** — tenant usa identidade própria, pode usar credenciais próprias, paga mensalidade + custo de IA passado adiante (se usa credenciais da plataforma)
- **Plano Enterprise** — white-label + SLA + suporte dedicado + ambiente isolado opcional

Detalhe operacional de billing está em [TODO — formalizar quando primeiro tenant white-label entrar].

## Implicações em suporte

| Item | Standard | White-label |
|---|---|---|
| Suporte ao usuário final | Tenant resolve | Tenant resolve (Regente não fala com cliente final) |
| Suporte ao tenant | Regente atende | Regente atende, com SLA diferenciado |
| Incidentes operacionais | Regente comunica via painel | Regente comunica + auxilia tenant a comunicar ao cliente final |
| Disponibilidade SLA | Best-effort | Negociado por contrato |

## Implicações em responsabilidade

- Tenant é **controlador LGPD** dos dados dos seus clientes (mesmo em white-label)
- Regente é **operador LGPD** (idem)
- Tenant é **responsável legal** pelo conteúdo gerado pelos agentes IA que ele aprovou e protocolou
- Regente é **responsável técnico** pela plataforma (uptime, segurança, conformidade)

Acordo de operador formaliza essa divisão (a redigir antes do primeiro white-label real).

## Pendências para execução white-label real

| Item | Estado |
|---|---|
| `Tenant.display_name`, `logo_url`, `brand_primary_color` | TODO |
| `Tenant.openai_api_key` (e Gemini, Anthropic) com criptografia em repouso | TODO |
| `Tenant.smtp_*` / `Tenant.resend_*` | TODO |
| Roteamento por subdomínio (Caddy/Traefik) | TODO |
| TLS por subdomínio (Let's Encrypt automático) | TODO |
| `ContractTemplate.tenant_id` | ✅ Já existe |
| `PromptTemplate.tenant_id` | ✅ Já existe |
| Acordo de operador escrito | TODO |
| Plano de billing white-label | TODO |
| Onboarding documentado para tenant white-label | TODO |

A capacidade de **prompts por tenant** e **contratos por tenant** já existe e está funcional. Os pedaços visuais e de credenciais externas ainda precisam ser implementados antes do primeiro tenant white-label real.

## Próximas leituras

- [`MULTITENANT_LGPD.md`](./MULTITENANT_LGPD.md) — base do multi-tenant que o white-label estende
- [`GOVERNANCA_IA.md`](./GOVERNANCA_IA.md) — credenciais IA por tenant
- [`../manifesto/04-ROADMAP.md`](../manifesto/04-ROADMAP.md) — quando white-label vira frente ativa
