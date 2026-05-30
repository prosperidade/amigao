# Auditoria Eixo 2 — Remanescente + Configuração de LLM por consultor

> **Tipo:** constatação read-only (EXISTE / PARCIAL / FALTA).
> **Data:** 2026-05-28
> **Working dir:** `c:\Users\Administrador\Desktop\Amigao_do_Meio_Ambiente` (clone independente)
> **Branch:** `feat/dashboard-redesign-v2`
> **Escopo:** estado atual no código de 4 frentes (A–D). Sem propor correção, sem priorizar, sem comparar com outros sistemas.
> Complementa `2026-05-28_eixo_2.md` (itens 2.1–2.3).

---

## Frente A — Resend Inbound

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| 1 | `RESEND_API_KEY` em config + domínio próprio mencionado | **PARCIAL** | [app/core/config.py:101-104](app/core/config.py#L101-L104) | `RESEND_API_KEY`, `RESEND_AUDIENCE_ID`, `RESEND_FROM_EMAIL` (`contato@regenteambiental.com.br`), `RESEND_FROM_NAME`. Domínio `regenteambiental.com.br` também em `EMAILS_FROM_EMAIL`. Tudo orientado a **envio**; comentário no código declara escopo "send + Audience". |
| 2 | Endpoint de inbound do Resend (`/webhook/resend`, `email.received`) | **FALTA** | [app/services/resend_client.py:17-20](app/services/resend_client.py#L17-L20) | Nenhuma rota de inbound. O próprio docstring do cliente lista "Inbound webhooks (bounce/open/click)" como **fora de escopo**. Cobertura atual: `send_email` + `upsert_audience_contact`. |
| 3 | Pacote `resend` (SDK Python) em `requirements.txt` | **FALTA** | [requirements.txt](requirements.txt); [app/services/resend_client.py:26](app/services/resend_client.py#L26) | Não há SDK `resend`. A integração é feita com `httpx` direto contra `https://api.resend.com` (`ResendClient._request`). Logo, "features suportadas" = só o que o cliente HTTP implementa (POST `/emails`, POST/PATCH `/audiences/{id}/contacts`). |
| 4 | Docs internos mencionam inbound de e-mail | **PARCIAL** | [docs/arquitetura/INTEGRACOES_GOVTECH.md:62-68,133-147,174](docs/arquitetura/INTEGRACOES_GOVTECH.md#L62) | Doc **descreve** inbound como desenho futuro (webhook HMAC → cria `Communication` com `source=govtech_inbound`), mas afirma explicitamente: "Connector IMAP/Gmail webhook **não existe ainda** — recebimento é manual hoje" e tabela final "Connector e-mail inbound \| Não existe". É roadmap, não implementação. |
| 5 | DNS/MX no repo (terraform/render.yaml/setup) apontando p/ Resend Inbound | **FALTA** | [render.yaml:16,141-148](render.yaml#L141-L148) | `render.yaml` declara apenas env vars de Resend **outbound** (`RESEND_API_KEY/AUDIENCE_ID/FROM_EMAIL/FROM_NAME`; comentário "emails transacionais"). Nenhum registro MX/DNS nem env de inbound. Não há terraform no repo. |

---

## Frente B — Provider WhatsApp (Evolution agora, Z-API depois)

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| 6 | Abstração de provider WhatsApp (`WhatsAppProvider`/`MessagingProvider`/Channel) | **FALTA** | grep `app/` | Nenhuma classe-base ou abstração de provider. `whatsapp` aparece só como: valor de enum `IntakeSource` ([app/models/process.py:49](app/models/process.py#L49)), enum de origem de documento ([app/models/document.py:21](app/models/document.py#L21)), string de canal ([app/models/communication.py:17](app/models/communication.py#L17)), tipo de conteúdo do agente marketing ([app/agents/marketing.py:23](app/agents/marketing.py#L23)) e toggle de notificação ([app/schemas/user_preferences.py:30](app/schemas/user_preferences.py#L30)). |
| 7 | Cliente Evolution/Z-API/Twilio em `requirements.txt` | **FALTA** | [requirements.txt](requirements.txt) | Nenhum (`evolution-*`, `zapi`, `twilio` ausentes). Lista runtime: fastapi, uvicorn, pydantic(-settings), sqlalchemy(-utils), alembic, psycopg2, redis, celery, python-jose, passlib, boto3, GeoAlchemy2, fpdf2, litellm, httpx, pypdf/pypdfium2, beautifulsoup4, lxml, PyYAML, slowapi. |
| 8 | `EVOLUTION_*`/`ZAPI_*`/`WHATSAPP_*` em config.py | **FALTA** | [app/core/config.py:35-169](app/core/config.py#L35-L169) | Nenhuma variável de provider de mensageria. Settings cobre DB, Redis, MinIO, JWT, SMTP, Resend, CORS, IA/LLM, alertas/webhook (de saída). |
| 9 | Campos `provider`/`provider_account_id` em `CommunicationThread`/`Message` | **PARCIAL** | [app/models/communication.py:8-44](app/models/communication.py#L8-L44) | Existem `channel` e `external_id` (Thread) e `external_msg_id`/`status` (Message). **Não há** coluna `provider` nem `provider_account_id` — não há separação por provider caso o tenant troque (Evolution → Z-API). |
| 10 | Endpoint webhook genérico de WhatsApp em `app/api/v1/` | **FALTA** | [app/api/v1/threads.py:14-66](app/api/v1/threads.py#L14-L66) | Confirmado: nenhum webhook. Rotas existentes em `threads.py`: `POST /` (`create_thread`), `GET /` (`get_threads`), `POST /{thread_id}/messages` (`add_message`). Todas exigem `get_current_internal_user` e gravam `sender_id=current_user.id` — entrada manual de usuário interno. Não há router `communication`/`messaging` separado. |

---

## Frente C — UI e persistência de configuração de LLM por consultor

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| 11 | Gateway LiteLLM hoje — providers/modelos; config por tenant ou global | **PARCIAL** | [app/core/ai_gateway.py:146-208](app/core/ai_gateway.py#L146-L208) | Gateway é **global**: `_build_model_list(settings)` monta a ordem de fallback a partir das **env keys** + `AI_DEFAULT_MODEL`/`AI_FALLBACK_MODEL` + `claude-haiku-4-5-20251001`. `complete(..., model=...)` aceita override **por chamada** (não por usuário). Único ajuste por tenant é orçamento (`Tenant.ai_monthly_budget_usd`, ref. [config.py:125-127](app/core/config.py#L125-L127)), não escolha de modelo/provider. |
| 12 | Coluna/tabela de "preferências de IA" por usuário/tenant | **PARCIAL** | [app/models/user.py:22-23](app/models/user.py#L22-L23); [app/schemas/user_preferences.py:50-67](app/schemas/user_preferences.py#L50-L67) | `User.preferences` (PortableJSON) tem grupo `ai` = `AiPreferences`. Campos: `assistance_level`, `summary_length`, `show_suggestions_in_flow`, `show_auto_summaries`, `require_human_validation_before_advance`, `save_ai_readings_history`. **Nenhum campo de provider/modelo/API-key.** São knobs de comportamento, não de seleção de LLM. |
| 13 | Frontend — tela/aba de configuração de IA e campos expostos | **PARCIAL** | [frontend/src/pages/Settings/index.tsx:466-521](frontend/src/pages/Settings/index.tsx#L466-L521) | Existe aba "IA" (`AiTab`, `TabKey='ai'`). Expõe: seletor `assistance_level` (automatic/balanced/manual), `summary_length` (short/medium/detailed) e toggles (`show_suggestions_in_flow`, `show_auto_summaries`...). **Não há** seletor de provider/modelo (Claude/Gemini/GPT). |
| 14 | Endpoint backend que GRAVA preferência de provider/modelo | **PARCIAL** | [app/api/v1/auth.py:177-192](app/api/v1/auth.py#L177-L192) | `PATCH /auth/me/preferences` faz merge parcial em `profile/notifications/operational/ai` e grava `current_user.preferences`. Grava o grupo `ai`, mas como `AiPreferences` não tem campo de provider/modelo, **não existe** PATCH/PUT que persista escolha de provider/modelo de LLM. |
| 15 | Propagação: escolha do usuário chega à chamada do agente? | **FALTA** | [app/agents/base.py:263-273](app/agents/base.py#L263-L273); [app/core/ai_gateway.py:187](app/core/ai_gateway.py#L187) | `BaseAgent.call_llm` → `complete(prompt, system=..., **kwargs)`. O modelo vem de: (a) `kwargs['model']` hardcoded no agente (ex.: legislação escolhe Gemini Flash/Pro por tamanho de contexto) ou (b) lista global de fallback. **Não há** leitura de `User.preferences` para resolver modelo. Sem override por contexto-de-usuário. |
| 16 | Todos os providers/modelos referenciados no código | **EXISTE (constatação)** | [config.py:118-158](app/core/config.py#L118-L158); [ai_gateway.py:151](app/core/ai_gateway.py#L151) | Referenciados: OpenAI `gpt-4o-mini` (`AI_DEFAULT_MODEL`; também em [ai_summarizer.py:69](app/workers/ai_summarizer.py#L69)); Gemini `gemini/gemini-2.5-flash` (fallback + legal) e `gemini/gemini-2.5-pro` (legal long); Anthropic `claude-sonnet-4-20250514` (`CLAUDE_LEGAL_MODEL`) e `claude-haiku-4-5-20251001` (gateway). Embeddings: comentário cita Gemini `text-embedding-004` ([knowledge_catalog.py:6](app/models/knowledge_catalog.py#L6)) com `EMBEDDING_PROVIDER` openai\|gemini ([config.py:114-117](app/core/config.py#L114-L117)). **Nenhuma referência** a DeepSeek, Qwen ou GLM (grep sem matches, mesmo comentadas). |

---

## Frente D — Criptografia de segredos por usuário

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| 17 | Confirmar FALTA de Fernet/AES; onde estão segredos hoje | **FALTA** | grep `app/`; [requirements.txt:16-17](requirements.txt#L16-L17) | Confirmado: nenhum `cryptography.fernet`/`Fernet`/`AES`/`encrypt`/`decrypt` em `app/`. Segredos vivem **apenas em env vars / `settings`** (SMTP, MinIO, LLM keys, Resend, SECRET_KEY). `requirements.txt` tem `python-jose[cryptography]` e `passlib[bcrypt]` — uso restrito a JWT e hash de senha de usuário, não a cofre de segredos de terceiros. |
| 18 | Biblioteca de cofre/vault (HashiCorp/AWS Secrets Manager/doppler/sops) | **FALTA** | grep `app/` + `requirements.txt` | Nenhuma referência (`vault`, `secretsmanager`, `doppler`, `sops`): grep sem matches. `boto3` está presente mas usado para MinIO/S3, não para Secrets Manager. |
| 19 | Modelo com campo `encrypted` (mesmo não usado) | **FALTA** | grep `app/models` | Nenhum `EncryptedString`/`EncryptedField`/`_encrypted`. Type decorators portáveis em [app/models/types.py](app/models/types.py) cobrem `PortableJSON`/Geometry/Vector — nenhum cifrado. |
| 20 | Pré-voo: padrão arquitetural existente que Fernet+chave-mestra afetaria | **EXISTE (constatação)** | [app/models/user.py:23](app/models/user.py#L23); [app/models/client.py:42](app/models/client.py#L42) | Constatação factual: hoje os campos de "dado solto" são PortableJSON/Text **em texto plano** (`User.preferences`, `Client.extra_json`, `Client.notes`). Não há nenhuma coluna cifrada no schema atual; `SECRET_KEY` já existe em settings (uso atual: JWT, ref. [config.py:84](app/core/config.py#L84)). |

---

## O que ainda precisa existir para fechar cada frente

### Frente A — Resend Inbound
- **PARCIAL** config Resend: só envio (`API_KEY/AUDIENCE_ID/FROM_*`); **falta** o que for específico de inbound.
- **FALTA** endpoint/webhook de inbound do Resend (`email.received`); o `ResendClient` declara inbound fora de escopo.
- **FALTA** SDK `resend` no `requirements.txt` (hoje só `httpx` direto, cobrindo rotas outbound).
- **PARCIAL** docs: `INTEGRACOES_GOVTECH.md` descreve inbound como desenho futuro e afirma "não existe ainda".
- **FALTA** registro DNS/MX em `render.yaml` (ou terraform) para Resend Inbound.

### Frente B — Provider WhatsApp
- **FALTA** abstração de provider (`WhatsAppProvider`/`MessagingProvider`); `whatsapp` existe só como enum/string em vários pontos.
- **FALTA** cliente Evolution/Z-API/Twilio no `requirements.txt`.
- **FALTA** variáveis de config de provider (`EVOLUTION_*`/`ZAPI_*`/`WHATSAPP_*`).
- **PARCIAL** modelo de mensagem: `channel`+`external_id`+`external_msg_id` existem; **faltam** `provider`/`provider_account_id` para distinguir provider quando o tenant trocar.
- **FALTA** webhook genérico de WhatsApp; rotas de `threads.py` são todas manuais (usuário interno).

### Frente C — UI e persistência de configuração de LLM por consultor
- **PARCIAL** gateway: existe e é multi-provider, mas **global** (env + defaults); **falta** resolução por tenant/usuário (só orçamento é per-tenant).
- **PARCIAL** modelo de preferências: grupo `ai` existe em `User.preferences`, mas **falta** campo de provider/modelo/API-key (só knobs de comportamento).
- **PARCIAL** frontend: aba "IA" existe, mas **falta** seletor de provider/modelo.
- **PARCIAL** endpoint: `PATCH /auth/me/preferences` grava o grupo `ai`, mas **falta** campo de provider/modelo a ser gravado.
- **FALTA** propagação: `BaseAgent.call_llm`/`ai_gateway.complete` não leem preferência do usuário para escolher o modelo.
- **EXISTE** (constatação) inventário de modelos: gpt-4o-mini, gemini-2.5-flash/pro, claude-sonnet-4, claude-haiku-4-5; sem DeepSeek/Qwen/GLM.

### Frente D — Criptografia de segredos por usuário
- **FALTA** padrão de criptografia (Fernet/AES; nenhum `encrypt`/`decrypt` em `app/`); segredos só em env vars.
- **FALTA** biblioteca de cofre/vault referenciada.
- **FALTA** coluna/type cifrado no schema (sem `EncryptedString`/`EncryptedField`/`_encrypted`).
- **EXISTE** (constatação) pré-voo: campos de dado solto são texto plano (PortableJSON/Text); `SECRET_KEY` já existe em settings (uso atual: JWT). Nenhum padrão de coluna cifrada hoje.

---

*Auditoria gerada em modo read-only. Nenhuma alteração feita ao repositório ou banco além deste arquivo.*
