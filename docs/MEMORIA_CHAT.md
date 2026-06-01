# Memória de projeto — Regente Ambiental

> Memória de continuidade entre chats/sessões. Versionada no repo a partir de
> 2026-05-30 (antes vivia só em rascunhos de chat). Tudo aqui foi conferido
> contra o código, o git log e os docs versionados. Onde algo é decisão de
> produto ou regra processual (não código), está marcado como tal.

## 1. Projeto

SaaS multi-tenant de consultoria ambiental brasileira ("Regente Ambiental";
codinome técnico `amigao`). Potencializa o consultor, não substitui. Três
audiências: consultorias (pagam), órgãos públicos (validam), bancos/cooperativas
(distribuem). Stack: FastAPI + Pydantic v2 + SQLAlchemy 2 + Postgres/PostGIS/
pgvector + Redis + MinIO + Celery; frontend React+Vite (consultor, ativo);
client-portal Next.js e mobile Expo **congelados** (ADR-009). IA via LiteLLM
multi-provider.

## 2. Divisão de trabalho

- **André** — programador/coordenador. Roda comandos locais, valida, decide
  escopo, faz merge.
- **Isis** — sócia ambientalista (domínio). Valida skills e fluxos contra a
  prática real. Várias validações estão **pendentes** (ver dívidas e sister files).
- **Claude (assistente)** — implementa por PR, sob as Regras Comuns abaixo.

## 3. Método

Trabalho por **PRs pequenos e coesos**, cada um: pre-flight → implementação →
testes verdes → governança documental no mesmo commit → push → PR → merge (só
com OK do André) → **apagar branch local+remota** (manter repo só com `main`).
Backend é verificável (testes); frontend valida por `tsc --noEmit` + validação
da Isis pendente.

## 4. Estrutura de docs

5 camadas (`docs/manifesto/`, `docs/arquitetura/`, `docs/operacao/`,
`docs/estado/`, `docs/adr/`) + `docs/REGISTRO_DIVIDAS.md` + `docs/agentes/`
(sister files, criados 2026-05-30). Regra em
`docs/arquitetura/GOVERNANCA_DOCUMENTAL.md`. Pulso (`ESTADO_ATUAL`,
`progressoIA`, `REGISTRO_DIVIDAS`, índice) atualiza TODA rodada; docs de
estrutura por gatilho.

## 5. Regras de governança

- Documento VIVO é fonte de verdade; EFÊMERO (prompt, relatório, chat) só pode
  ser descartado depois que o durável foi capturado num vivo.
- ADRs imutáveis após aceitas (cai → marca `REVOKED`, não some).
- **Não documentar ficção:** feature não construída não entra como existente.
- Não renumerar dívidas existentes.

## 6. Regras Comuns para Agentes (v2026-05-30) — processuais

Pre-flight (pwd/branch/status limpo; abortar se uncommitted não-relacionado;
criar branch dedicada). Migration → confirmar 1 head no Alembic. Nunca tocar
fora do escopo; saída sempre no repo. Post-work: status limpo, add escopo,
commit, push, governança no mesmo commit, confirmar via git log, reportar.
Nunca: branch base com mudanças soltas, uncommitted após "pronto", misturar PRs.
Congelados (ADR-009): client-portal, mobile. (Regras processuais — independem do
estado do código.)

## 7. Roadmap

✅ Mergeado: Eixo 1 · PR 2.2 (#26) · Frente D (ADR-014) · Intake backend (#26) ·
Intake frontend (#27) · PR LLM (#28) · PR 2.3 credenciais (#29) · fix compose
(#30) · remoção corpus do git (#31) · governança Render (#32) · esta PR (docs
sistema agêntico).
⏭ Pendente: **PR 2.1** (WhatsApp/email externos; depende de Resend Inbound +
URL/key Evolution) · **EIXO 3** (unificação `Process.status` × `macroetapa`,
dívida #26) · validações da Isis · sister files restantes.

## 8. Dívidas (numeração REAL — `docs/REGISTRO_DIVIDAS.md`)

Abertas relevantes: **#14** (geoespacial aguarda `geom`), **#15** (alertas de
consulta externa IBAMA), **#16** (loop de aprendizado, ADR-010), **#18** (hash
chain sem rotina de verificação), **#21** (templates por demand_type / pares de
status — colisão de número pré-existente, não renumerar), **#26** (eixo 3),
**#28** (OCR Errata SEMAD), **#29** (critério Valor Estratégico "Baixo"),
**#30** (auditoria de uso de IA por chave), **#31** (git history carrega 254MB
de corpus removido). Fechadas recentes: **#27** (EncryptedString em coluna real,
PR 2.3). Dívidas novas desta PR: ver REGISTRO.

## 9. Lições codificadas

- Verificar contra o código antes de afirmar (a doc anterior tinha alegações
  fabricadas: `credential_service.py`, `GET /secret`, `login_password`,
  numeração de dívida errada — nada disso existe/era verdade).
- Diff de EOL (LF↔CRLF) parece mudança de conteúdo no `git status` mas não é —
  conferir o conteúdo commitado antes de "abrir PR de fix".
- 2 heads do Alembic quebram `alembic upgrade head` silenciosamente (resolvido
  na PR 2.3 via migration de merge `c0d1e2f3a4b5`).
- Princípio "vermelho-canário": checar o consumidor antes de ajustar um teste.

## 10. Decisões fechadas (produto — não código)

- **White label:** consultor traz a própria chave de LLM (André, 28/05).
- **Caso só nasce por mão do consultor.**
- **E-mail obrigatório** no contato; **Sintoma/Dor** não viram campo (interpretação
  do consultor); **"Possui arquivo do CAR"** não vira campo (Isis, 28/05).
- **Triagem 2 eixos** independentes (urgência + valor estratégico).
- **Reconciliação Opção A** (modal na divergência).

## 11. Preferências do André

- Repo enxuto: apagar branch local+remota após merge (manter só `main`).
- Confirmação explícita antes de commit/push/merge e de comandos destrutivos
  (configurado em `.claude/settings.json`).
- Não documentar ficção; sinalizar divergências em vez de "consertar" no escuro.

## 12. Cadência

Pulso documental a cada PR. Branch limpa pós-merge. Validações da Isis em lote
quando ela testar a UI.

## 13. Próximo passo

PR 2.1 depende de credenciais/URLs externas (Resend Inbound, Evolution) que o
André precisa fornecer/decidir. Alternativas sem dependência externa: sister
files restantes (round documental), follow-ups de UI (credenciais no Client Hub).

## 14. Documentos externos (em mãos do André, fora do repo)

Rascunhos de chat (`MEMORIA_CHAT v5`, `ECOSSISTEMA_AGENTICO v1`,
`EXTRATOR_AGENTE v1`) serviram de inspiração estrutural; **continham alegações
fabricadas/desatualizadas** e NÃO foram copiados — esta versão e os sister files
em `docs/agentes/` são a fonte de verdade verificada.

## 15. Eventos significativos

- **2026-05-31 — PR 2.1 (WhatsApp inbound) mergeado (#38).** Canal WhatsApp via Evolution, dormente
  até credenciais; e-mail inbound adiado (dívida #35). Atualiza o "próximo passo" da seção 13.
- **2026-05-31 — Correção dos 2 críticos da Isis (`fix/intake-uploads-criticos-isis`).** Persistência:
  `/intake/create-case` aceita `draft_id` e migra os docs do rascunho para o processo (antes ficavam
  órfãos — invisíveis na aba Documentos). Upload em massa: `DraftDocumentUploader` com pool de 4, retry
  com backoff, botão remover sempre visível e feedback por item; visual alinhado ao design system.
  Origem: auditoria `2026-05-31_uploads_isis.md`. Validações finais da Isis na UI ainda pendentes.
- **2026-06-01 — Evolution fora do boot (`ops/evolution-opcional-no-boot`).** **Decisão do André:**
  tirar o Evolution do compose/boot AGORA para o sistema subir e ser validável E2E; o canal WhatsApp
  volta DEPOIS, quando o core estiver de pé. Motivo: a definição do serviço `evolution` exigia
  `EVOLUTION_API_KEY` (`${EVOLUTION_API_KEY:?...}`) e o Compose interpola o arquivo inteiro no `up`,
  abortando o boot do core mesmo com a Evolution dormente. O serviço `evolution` + profile `whatsapp`
  saíram do `docker-compose.yml`; o **código do provider e o webhook permanecem** — só desacoplados —
  e o webhook responde 503 "WhatsApp não configurado" sem as envs. Validado: `docker compose up -d`
  do core sobe healthy + `/health` 200. Dívida #37 (reintegrar Evolution); reativação no RUNBOOK_OPS.
- **2026-06-01 — Mergulho fluxo agêntico (`fix/mergulho-fluxo-agentico`).** Diagnóstico por EXECUÇÃO
  (não leitura) do fluxo intake→agentes, sistema rodando (AI_ENABLED=true). **Veredito:** funciona em
  pedaços — OCR+extrator+atendimento entregam (caso reproduzido: matrícula → 12 campos); o que trava
  a entrega do diagnóstico é (a) `create-case` dispara só `atendimento` (chain de diagnóstico não
  auto-roda), (b) na chain o `extrator` pulava sem `document_id`, (c) a `legislacao` é bloqueante e
  flaky e ao falhar **aborta a chain antes do `diagnostico`** (0 diagnoses gravados). **3 P0
  corrigidos e revalidados rodando:** (1) CORS mascarava 500 — handler global reanexa CORS+request_id
  (o "threads CORS" de prod é 500 mascarado, não config); (2) WS path — rota também sob `/api/v1`
  (prod batia em `/api/v1/ws`→403); (3) extrator resolve os docs do processo quando recebe só
  `process_id`. **Viraram dívida:** #38 chain aborta na legislacao (ALTA), #39 robustez legislacao,
  #40 SKILL.md inválidos, #41 auto-trigger pós-case (decisão produto), #42 bucket MinIO presigned,
  #43 Error Boundary global. **Infra p/ André:** Cloudflare WebSockets=ON +
  `VITE_WS_URL=wss://api.regenteambiental.com.br`. Doc:
  `docs/arquivo/auditorias/2026-06-01_mergulho_fluxo_agentico.md`.
- **2026-06-01 — PR #38 chain legislação (`fix/chain-legislacao-timeout`).** Fechou a dívida #38:
  `diagnostico_completo` não morre mais se `legislacao` falhar ou pedir revisão. Medido rodando:
  RAG local ~4,5s, contexto por metadados ~0,5s, timeout real na chamada Gemini
  (`gemini/gemini-2.5-flash`, `litellm.Timeout`, ~33s). Em `diagnostico_completo`, `legislacao`
  virou não-bloqueante por chain para `requires_review=True` e falha; o erro fica em
  `chain_data["legislacao"]` e `diagnostico` roda com contexto parcial. Revalidação: com timeout,
  `diagnostico` rodou depois e entregou 3 passivos (AIJob 135); sem timeout, mas com
  `legislacao.requires_review=True`, também rodou e entregou 3 passivos (AIJob 139). #39 continua
  aberta para robustez própria da legislação.
