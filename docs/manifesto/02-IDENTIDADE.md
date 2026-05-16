# 02 · Identidade

**Documento:** Manifesto · Identidade
**Estado:** vivo · ADR-004 vinculado
**Última revisão:** 2026-05-15

---

## Decisão

**Regente Ambiental é o nome do produto.** É a marca pública, o domínio comercial, o que aparece para clientes, parceiros, órgãos públicos, investidores e mídia. Toda comunicação externa usa Regente Ambiental.

**Amigão do Meio Ambiente é codinome técnico interno.** Aparece em identificadores de infraestrutura que não fazem sentido renomear no momento: nome do banco PostgreSQL (`amigao_db`), bucket MinIO (`amigao-docs`), canal Redis pubsub (`amigao_events`), métricas Prometheus (`amigao_*`). Esses identificadores podem migrar em uma sprint futura dedicada à reidentificação de infraestrutura, mas não são prioridade hoje — mudar agora implica migração de dados, quebra de dashboards históricos e risco operacional desproporcional ao ganho.

A relação entre os dois nomes é equivalente à de muitas empresas de tecnologia que mantêm codinomes internos diferentes do nome comercial. Não é incoerência; é separação consciente entre **camada de marca** (visível, importa para mercado) e **camada de infraestrutura** (invisível, importa para custo de manutenção).

## O que muda agora (camadas visíveis)

Esta seção é executável. Cada item lista o arquivo e o que troca.

### Branding visível ao usuário

| Arquivo | Linha | De | Para |
|---|---|---|---|
| `frontend/src/pages/Auth/Login.tsx` | 71 | `Amigão do Meio Ambiente` | `Regente Ambiental` |
| `frontend/src/layouts/PrivateLayout.tsx` | 66 | `Amigão` (header desktop) | `Regente` |
| `frontend/src/layouts/PrivateLayout.tsx` | 119 | `Amigão` (header mobile) | `Regente` |
| `app/services/email.py` | 86 | `<h2>Amigão do Meio Ambiente</h2>` | `<h2>Regente Ambiental</h2>` |
| `app/services/contract_generator.py` | 45 | `{{empresa.nome}} → Amigão do Meio Ambiente` | `Regente Ambiental` |
| `app/services/contract_generator.py` | 138 | `AMIGAO DO MEIO AMBIENTE` | `REGENTE AMBIENTAL` |
| `app/services/contract_generator.py` | 186 | rodapé | `Regente Ambiental` |
| `app/api/v1/proposals.py` | 312 | `<h2>Amigão do Meio Ambiente</h2>` | `<h2>Regente Ambiental</h2>` |
| `app/workers/pdf_generator.py` | 189 | rodapé | `Regente Ambiental` |

### Configuração do produto

| Arquivo | Linha | De | Para |
|---|---|---|---|
| `app/core/config.py` | 52 | `PROJECT_NAME = "Amigão do Meio Ambiente"` | `PROJECT_NAME = "Regente Ambiental"` |
| `app/core/config.py` | 90 | `EMAILS_FROM_NAME = "Amigão do Meio Ambiente"` | `EMAILS_FROM_NAME = "Regente Ambiental"` |
| `app/services/crawlers/dou_crawler.py` | 83 | `Amigao-Meio-Ambiente/1.0` (User-Agent) | `Regente-Ambiental/1.0` |
| `app/services/crawlers/ibama_crawler.py` | 71, 115 | idem | idem |
| `app/services/crawlers/doe_crawler.py` | 105 | idem | idem |
| `.env.example` | 41 | `EMAILS_FROM_NAME=Amigao do Meio Ambiente` | `EMAILS_FROM_NAME=Regente Ambiental` |
| `agents/__init__.py` | 2 | docstring `Sistema de Agentes IA — Amigao do Meio Ambiente` | `Sistema de Agentes IA — Regente Ambiental` |

### Email transacional

Pendência: decidir se `EMAILS_FROM_EMAIL` migra de `noreply@amigao.com` para `noreply@regenteambiental.com.br` agora ou só quando o DNS do `regenteambiental.com.br` tiver MX/SPF/DKIM/DMARC totalmente configurado. Recomendação técnica: migrar junto com a Sprint Waitlist (PR 3 ou 5), que já está fazendo essa transição para Resend.

### Repositório e path local

| O que | Estado atual | Estado alvo |
|---|---|---|
| Repo GitHub | `Amigao_do_Meio_Ambiente` | `regente-ambiental` |
| Path local de dev | `C:\Users\Administrador\Desktop\Amigao_do_Meio_Ambiente\` | livre |
| Domínio principal | `regenteambiental.com.br` (já registrado) | manter |
| Subdomínios | a definir | sugestão: `app.regenteambiental.com.br`, `api.regenteambiental.com.br` |

GitHub redireciona automaticamente links e clones antigos do repo após rename — sem quebra para quem já clonou.

## O que NÃO muda agora (camada técnica)

Identificadores internos que continuam usando `amigao` por enquanto:

| Identificador | Por que mantemos |
|---|---|
| `POSTGRES_DB=amigao_db` | Renomear implica migração de dados em produção. Risco alto, ganho zero (usuário nunca vê). |
| `BUCKET_NAME = "amigao-docs"` em `app/services/storage.py` | Idem. Migrar implica copiar todos os documentos armazenados. |
| `REALTIME_EVENTS_CHANNEL = "amigao_events"` | Rolling deploy ficaria dessincronizado durante a transição. |
| `app/core/metrics.py` — 13 métricas `amigao_*` | Quebra dashboards Grafana e alertas Prometheus configurados. |
| `ops/prometheus-alerts.yml` | Mesmo motivo. |

Quando virar prioridade, essas mudanças entram em uma sprint dedicada com plano de migração próprio — provavelmente combinada com uma evolução maior de infraestrutura.

## Sub-identidades dentro do produto

O Regente Ambiental tem três frentes de software que se tratam como módulos do mesmo produto, não como produtos separados:

| Frente | Nome interno | Audiência | Estado |
|---|---|---|---|
| Painel do consultor | `frontend/` | Consultor que opera dentro da consultoria | **Ativa** — foco do MVP |
| Portal do cliente | `client-portal/` | Cliente final da consultoria | **Congelada** — retomada após validação do painel |
| App de campo | `mobile/` | Equipe técnica em campo, com sincronização offline | **Congelada** — retomada após validação do painel e do portal |

A decisão de congelar as duas frentes secundárias está em [`../adr/009-mobile-clientportal-congelados.md`](../adr/009-mobile-clientportal-congelados.md).

## Sub-marcas (futuro)

O Regente Ambiental opera em modo **white-label** opcional: tenants podem aparecer aos próprios clientes com identidade visual e domínio próprios, usando o Regente como motor invisível. Esse mecanismo está documentado em [`../arquitetura/WHITELABEL.md`](../arquitetura/WHITELABEL.md). Não é uma divisão de marcas comerciais; é uma capacidade arquitetural de personalização por tenant.

## Próximas leituras

- [`../adr/004-regente-vs-amigao.md`](../adr/004-regente-vs-amigao.md) — registro formal da decisão
- [`03-PRINCIPIOS.md`](./03-PRINCIPIOS.md) — princípios inegociáveis
