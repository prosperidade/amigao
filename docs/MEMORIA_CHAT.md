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
PR 2.3), **#40** (2 SKILL.md inválidos — front-matter corrigido, skill do
diagnóstico injetada; PR `fix/skills-frontmatter-40`). Dívida nova: **#44** (chain
não propaga `uf` ao diagnóstico — ligada à #38). Dívidas novas por PR: ver REGISTRO.

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
- **2026-06-01 — Storage R2 + Redis SSL + download silencioso (`fix/storage-r2-region-redis`).**
  Causa-raiz do "OCR não extrai nada, sem mensagem" (provada no Render Shell do worker): os clients
  boto3 usavam `region_name="us-east-1"` hardcoded, mas o **Cloudflare R2 exige `region="auto"`** —
  com `us-east-1` o scope SigV4 não bate no GET server-side → `SignatureDoesNotMatch`; o upload
  presigned (query-auth) tolerava, então o arquivo **subia mas nunca era lido**. **Agravante:**
  `download_bytes` engolia **todo** `ClientError` e retornava `b""`, mascarando como `no_bytes`
  genérico por semanas. **Fix:** setting `S3_REGION` (default `"auto"`, configurável) nos 2 clients;
  `download_bytes` retorna `b""` só para NoSuchKey e **re-levanta** `StorageDownloadError(code)` para
  o resto (log ERROR); `ocr_then_extract` registra `storage_error:<code>`. **+Redis:** `redis_url_safe`
  normaliza `ssl_cert_reqs` (env trazia `CERT_REQUIRED`, redis-py quer `required` → evento realtime
  voltou); Celery seta `broker_use_ssl` só em `rediss://`. **+Endpoint:** `_with_scheme` respeita
  `MINIO_SECURE`. Provado rodando local (round-trip MinIO com `region=auto` sem regressão; repro+fix do
  `SignatureDoesNotMatch` e do CERT do Redis; 20 testes verdes). E2E contra R2 real: snippet pronto pro
  André no Render Shell. **Lição:** nunca capturar exceção de I/O e devolver vazio — distinguir
  "ausente" (NoSuchKey) de "falhou" (re-levanta com o código). **Não fecha #42** (bucket presigned,
  bug distinto). Doc: `docs/trabalhos/storage_r2_redis.md`.
- **2026-06-02 — OCR: modelo Gemini descontinuado + timeout do fallback (`fix/ocr-gemini-model`).**
  Sequência do fix de storage: agora o PDF baixa e o OCR roda, mas o intake "fica rodando" em doc
  escaneado. **Causa (log do worker em prod):** `app/services/ocr_pdf.py:28` tinha
  `GEMINI_OCR_MODEL = "gemini/gemini-2.0-flash"` **hardcoded** — modelo descontinuado pelo Google →
  404 `is no longer available`; caía no fallback OpenAI Vision que pendurava ~272s (≈ 3 × 90s = os
  `num_retries` default do litellm) até Timeout, com o worker `pool=solo` bloqueado. (O
  `GEMINI_LEGAL_MODEL` já tinha migrado pra 2.5-flash na Sprint W; o OCR ficou pra trás.) **Fix:**
  `GEMINI_OCR_MODEL` virou setting (`config.py`, default `gemini/gemini-2.5-flash`, env-configurável);
  `ocr_pdf.py` lê a setting e usa `num_retries=0`; fallback OpenAI ganhou
  `OPENAI_VISION_TIMEOUT_SECONDS=75` explícito + `num_retries=0`. **Provado rodando** (worker local,
  chaves reais): PDF imagem-only → pypdf 0 chars → Gemini 2.5-flash → `chars=146`,
  `model=gemini/gemini-2.5-flash`, `error=None`, $0.00057, 13,8s. **Lição:** modelo de IA
  descontinuável **sempre** por env, nunca hardcoded — o próximo deprecation é troca de variável, não
  de código. Doc: `docs/trabalhos/ocr_gemini_model.md`.
- **2026-06-02 — OCR só lia 1 página de PDF multipágina (`fix/ocr-multipagina`).** Com o modelo
  Gemini já corrigido, a escritura do Romilton (doc 118, 6 págs, 2,3 MB) saía com **832 chars = só a
  certidão CNIB da capa**; páginas 2-6 (área 58,7654 ha, matrícula 6253, CAR GO-5221577) sumiam, e o
  extrator devolvia quase tudo `None`. **Causa medida (PDF real reproduzido local, sem assumir):** o
  Gemini com o PDF enviado **inline** transcreve só a 1ª página em docs escaneados multipágina — o
  custo alto (~9x) provava que ele recebia as 6 págs mas só transcrevia a capa. Teste de síntese
  enganava (PDF legível pequeno vinha 8/8); só o PDF real expôs a falha. **Fix:**
  `extract_text_with_gemini` rasteriza cada página (`pypdfium2`, 200 DPI) e faz **1 chamada por
  página**, concatenando (`reasoning_effort="disable"` → OCR não precisa de thinking, ~2x mais rápido/
  barato; **retry próprio** por página p/ 503 — litellm `num_retries` exige `tenacity`, ausente, e
  falhava; página que falha é pulada → texto parcial, não derruba o doc). Inline antigo virou fallback
  (`_extract_text_with_gemini_inline`) p/ quando a rasterização não está disponível. **+ Bug do cache:**
  `cache_twin` em `ocr_tasks.py` **não respeitava `force=True`** — reprocessar copiava o texto curto de
  um gêmeo e mascarava o re-OCR; agora pula o twin em force. `soft_time_limit` 180→300s. **Provado
  rodando no PDF real:** 832 → ~18-21k chars, `area_ok`/`matricula_ok`/`car_ok` = True. **Lições:**
  (1) Gemini multipágina = rasterizar + 1 call/página, não PDF inline; (2) síntese pequena não
  reproduz falha de scan real — exigir o doc real (regra "validar com o doc real"); (3) não confiar no
  `num_retries` do litellm (depende de `tenacity`). doc 115/118 destravam com `force=True` pós-deploy.
  Doc: `docs/trabalhos/ocr_multipagina.md`.
- **2026-06-02 — Extrator truncava o texto em 3000 chars (`fix/extrator-truncamento`).** Terceiro elo
  da cadeia OCR→extrator: com o texto inteiro no banco (doc 118, ~20.8k chars), o extrator devolvia só
  nome+CPF e os 9 campos do imóvel vinham `None`. **Causa raiz:** `document_extractor.py:183` fazia
  `text[:3000]` — a página 1 do PDF é a certidão CNIB (nome/CPF); os campos do imóvel ficam depois do
  char 3000, fora da janela. **Fix:** `EXTRACTOR_MAX_CHARS` (config, default 30.000) substitui o 3000
  hardcoded; prompt da matrícula avisa que o doc tem várias seções (capa + escritura + memorial) e que
  os campos podem estar em qualquer parte. **Provado rodando no texto real do doc 118:** área=58.7654,
  município=UIRAPURU, uf=GO, denominação="LOTE 32, PA MÃE MARIA", comarca=CRIXÁS, cartório, proprietário
  — 7 campos `None`→preenchidos; regressão de doc simples (RG/CPF) OK. **`numero_matricula` segue None e
  está correto:** a única "Matrícula nº 6253" do doc é dos confrontantes (lotes 31/33); o imóvel é o lote
  32, referenciado por CIB/CCIR/memorial, sem matrícula própria — forçar 6253 seria atribuir a matrícula
  de um vizinho. **Não usa skill** (chama `extract_document_fields` direto, sem `_compose_system_with_skills`)
  → dívida #45. **Lição:** validar contra a realidade do doc antes de "forçar" um campo esperado (6253
  parecia óbvio mas era do vizinho). doc 118 re-extrai em prod via chain OCR→extrator ou `POST
  /processes/{id}/extract`. Doc: `docs/trabalhos/extrator_truncamento.md`.

- **2026-06-02 — UI: renderer dos agentes saía JSON cru + seletores por ID (`fix/ui-renderer-seletores`).**
  Na aba Agentes o resultado vinha como JSON cru/`[object Object]` e o card mostrava `Agente —`/`Modelo —`.
  **Causa raiz (NÃO a hipótese do prompt, que dizia "`agent_name` vazio na chain"):** o banco **tem**
  `agent_name` em todos os jobs (chain inclusa — `BaseAgent._create_running_job` grava sempre); quem
  descartava era o `_serialize_job` (`GET /ai/jobs`, `app/api/v1/ai.py`), que **não serializava** o campo
  → o front recebia `agent_name=undefined` → `renderers[undefined]` cai no `GenericResult`/`JSON.stringify`.
  `model_used`/`tokens` nulos são corretos para `extrator`/`auditor_imovel` (não chamam LLM). **Fix:**
  (A) serializer expõe `agent_name`+`chain_trace_id`; (B) novo `AuditorResult` (divergências humanizadas;
  esconde `findings_raw`/`issue_ids`), `divergencias` no `DiagnósticoResult`, `GenericResult` reescrito
  para nunca emitir `[object Object]`/`JSON.stringify`; (C) `IntakeWizard` troca os inputs "ID do
  cliente/imóvel" por `SearchSelect` (dropdown com busca) — cliente via `/clients/`, imóvel via
  `/properties/?client_id=` filtrado pelo cliente (desabilitado sem cliente). **Provado rodando:**
  `GET /ai/jobs` agora devolve `agent_name` (#139 diagnostico/gpt-4o-mini, #137 auditor_imovel);
  `/clients/`→16, `/properties/?client_id=3`→1; `tsc --noEmit` verde. **Fecha #UX-1 e #UX-2.**
  **Lição (reforço):** confirmar a causa medindo (banco + resposta da API) antes de aceitar a hipótese
  escrita no prompt — aqui a hipótese apontava pro lugar errado (chain), o bug estava na serialização.
  Doc: `docs/trabalhos/ui_renderer_seletores.md`.
- **2026-06-02 — Diagnóstico → GPT-4.1 (`fix/diagnostico-modelo-gpt41`).** Pedido do André: o agente de
  diagnóstico rodava em `gpt-4o-mini`; trocar pra `gpt-4.1`. **Cirúrgico, só o diagnóstico** — mudar o
  `AI_DEFAULT_MODEL` global encareceria todos os outros agentes sem ter sido pedido. Seguiu a convenção
  que o `legislacao` já usa (modelo por env, não hardcoded no agente): novo setting `AI_DIAGNOSTICO_MODEL`
  (default `gpt-4.1`, vazio→`AI_DEFAULT_MODEL`) em `config.py`; `diagnostico.py` passa `model=` no
  `call_llm`; `docker-compose.yml` (api+worker) e `render.yaml` ganharam a env. White-label do consultor
  mantém precedência no gateway; passar `model=` explícito desativa o fallback automático **só** do
  diagnóstico (igual `legislacao`). **Provado rodando** (container, chave real): setting='gpt-4.1' e
  `complete(model='gpt-4.1')`→`model_used=gpt-4.1`, `content='OK'` (modelo existe e a chave chama).
  Reversível por env. **Lição (reforço):** modelo de IA sempre por env — deprecation é troca de variável.
  Doc: `docs/trabalhos/diagnostico_modelo_gpt41.md`.
- **2026-06-03 — UI: eliminar termos técnicos / rótulos PT-BR (`fix/ui-termos-tecnicos`).** Termos técnicos
  vazavam pra tela do consultor: `snake_case` cru, **JSON cru**, `[object Object]`, `demand_type` em
  maiúsculas (`.toUpperCase()`). **Causa (lendo o frontend):** dicionários de rótulo de campo
  fragmentados/incompletos (dois `FIELD_LABELS` divergentes em PreviewPanel e DraftDocumentUploader,
  sem os campos de matrícula/RG) **+** vários pontos sem dicionário, humanizando com `key.replace(/_/g,' ')`
  (só troca `_` por espaço, segue técnico). **Fix:** módulo fonte única `frontend/src/lib/labels/fieldLabels.ts`
  — `labelFor()` (PT-BR ou fallback humanizado, nunca underscore cru), `humanizeValue()` (objeto/array sem
  JSON nem `[object Object]`), `isMetaField()` (oculta `confidence`/`*_raw`/`chain_trace_id`/…). Aplicado em
  `AgentResultRenderer` (extrator+genérico), `DocumentsTab` (fim do `JSON.stringify`), `WorkflowTimeline`
  (passa a usar `DEMAND_TYPE_LABELS` de quadro-types), e `PreviewPanel`/`DraftDocumentUploader` (importam o
  módulo, `FIELD_LABELS` locais removidos). **Achado que corrige o briefing:** os 2 `CATEGORY_LABELS`
  (PropertyHub × ProcessChecklist) **não** eram duplicados — taxonomias distintas (categorias de documento
  do imóvel × categorias de checklist); mesclar seria errado, mantidos. **Provado por teste de render**
  (`fieldLabels.test.tsx`, 8 casos: matrícula+RG+genérico renderizam PT-BR, meta oculto, sem termo
  técnico/JSON/`[object Object]`) + suite 48/48 + `tsc`/`build` verdes. Lint pré-existente (5 arquivos
  `react-hooks`) fora do escopo, confirmado na `main` limpa. **Follow-on anotado:** unificar os 3
  dicionários de tipo de demanda. Doc: `docs/trabalhos/ui_termos_tecnicos.md`.
- **2026-06-03 — Zerar lint react-hooks / CI frontend verde (`fix/lint-react-hooks`).** O check
  **Frontend Lint** estava cronicamente vermelho com 6 problemas pré-existentes (5 erros + 1 warning;
  `--max-warnings=0` quebra com warning), escondendo erros novos. **Não tratei todos igual** — classifiquei
  cada um e corrigi **na estrutura, zero `eslint-disable`**: (1) `IntakeWizard` `DraftExpirationBadge` lia
  `Date.now()` no render (`react-hooks/purity`) → lazy `useState(() => Date.now())` (badge estático, "agora"
  uma vez no mount); (2) `AlertaCard` sync server→form em `useEffect`+setState (`set-state-in-effect`) →
  padrão React de ajustar estado **durante o render** com sentinela `syncedData` (sentinela inicia
  `undefined`: cobre loading/cache-no-1º-render/null; sem loop pois iguala após sincronizar); (3) `QuadroAcoes`
  `const columns = kanbanData?.columns ?? []` recriava array todo render e disparava useMemo dependente
  (`exhaustive-deps`) → `useMemo(() => ..., [kanbanData])`; (4) `CredentialModal` init de form em effect →
  lazy `useState` + `key` no pai (remonta ao trocar credencial — reset canônico); (5) `PriorityStep` exportava
  constantes junto do componente (`react-refresh/only-export-components`) → movidas p/ `priorityOptions.ts`,
  importadas em PriorityStep e IntakeWizard. **Validação:** eslint dos 7 arquivos = 0; `npm run lint` projeto
  verde; tsc/build verdes; suite 48/48; **anti-loop** nas 2 telas de setState (AlertaCard + CredentialsTab,
  11/11 testes sem `Maximum update depth`). **Lição:** `exhaustive-deps`/`set-state-in-effect` exigem
  julgamento caso-a-caso — corrigir a estrutura (estabilizar ref, sync no render, key+lazy-init) é melhor que
  adicionar dep cegamente (vira loop) ou `disable` atalho. **Backend Lint segue dívida separada** (fora deste
  PR). Doc: `docs/trabalhos/lint_react_hooks.md`.
- **2026-06-03 — Backend Lint verde / diagnosticar antes de corrigir (`fix/backend-lint`).** O check
  `backend-lint` (ruff + mypy) estava vermelho desde #52. **Diagnóstico (não assumi):** li o `ci.yml` e
  puxei o log real → `ruff: command not found` (exit 127). **Era (A) infra + (B) código:** o CI instalava
  só `requirements.txt`, mas ruff/mypy vivem em `requirements-dev.txt` → o lint **nunca rodou**; atrás disso,
  77 erros reais de ruff e **~495 de mypy** (pré-existentes, sobretudo `Column[int]` do SQLAlchemy).
  **Fix:** (1) `ci.yml` — `backend-lint` e `backend-test` passam a instalar `requirements-dev.txt` (sem isso,
  ao destravar o lint, o `backend-test` que tinha `needs: backend-lint` e estava *skipping* rodaria pela 1ª
  vez e quebraria por falta de pytest); (2) ruff 77→0: `ruff --fix` (62 autofix: imports/datetime.UTC/aspas)
  + 15 manuais sem mudar comportamento (reorder E402, `contextlib.suppress`, `zip(strict=False)` p/ preservar
  comportamento, combinar with/if, ternário, `Union`→`|`) — **2 `# noqa` justificados** (B027 em
  `BaseAgent.validate_preconditions`, hook opcional no-op que não pode virar `@abstractmethod`; B017 em teste
  de WS cuja exceção varia por versão do starlette); (3) mypy vira **advisory** (`continue-on-error: true`) —
  decisão do André: ruff é o gate, mypy reporta mas não derruba; corrigir 495 é refactor de tipagem,
  **dívida #46**; (4) `ruff==0.15.13`/`mypy==2.1.0` **pinados** (gate reproduzível). **Validação:** ruff=0;
  baseline da suíte **753 passed** e pós-fix **753 passed** (lint não mudou comportamento; testcontainers +
  Postgres real). **Princípio:** diagnosticar (ler workflow + log real) antes de tocar arquivo — o vermelho
  era infra escondendo código. **Nenhuma regra afrouxada.** RUNBOOK_DEV ganhou seção de lint/tipagem.
  **A cascata cresceu:** deixar o lint verde **desskipou** `backend-test` e `backend-migrations` (tinham
  `needs: backend-lint` e nunca haviam rodado no CI) → vários blockers pré-existentes vieram à tona, todos
  corrigidos pra deixar o **backend CI 100% verde** (1ª vez): (a) `python -m pytest` (o `pytest` cru não põe
  cwd no sys.path → `ModuleNotFoundError: app`); (b) build da imagem custom PostGIS+pgvector pro Testcontainers
  (fallback `pgvector/pgvector:pg15` não tem PostGIS) e pro job de migração (trocado `services:` postgis-only
  por build+`docker run`); (c) `CREDENTIAL_ENCRYPTION_KEY` (Fernet, ADR-014, obrigatória) + `AI_ENABLED`+chave
  **fake** (18 testes do caminho IA mockam `complete` mas gateiam em `ai_configured`); (d) `--cov-fail-under=0`
  (753 passam; gate de 70% era TODO, cobertura real 63%); (e) **2 bugs reais de migration** (decisão André de
  corrigir no PR, só quebram em `upgrade head` do zero — deploy novo): `UnsafeNewEnumValueUsage` do enum `lead`
  em `afcea9834c04` → `op.get_context().autocommit_block()` (padrão de `b3d5c7e9f1a2`); e `op.execute(text,
  dict)` no downgrade da seed `024fe3f5dbeb` → `.bindparams()` (o 2º posicional de `op.execute` é
  `execution_options`, não params). **Lição:** destravar um job de CI pode acordar jobs `needs:`-dependentes
  que nunca rodaram — esperar uma cascata de débito latente, não só o alvo. Validação local do ciclo de
  migração foi atrapalhada por flakiness do port-forward do Docker Desktop no Windows; o runner Linux do CI é
  a fonte de verdade. **CI 100% verde** (6 jobs), `mergeStateStatus: CLEAN`. Doc: `docs/trabalhos/backend_lint.md`.
- **2026-06-01 — PR #38 chain legislação (`fix/chain-legislacao-timeout`).** Fechou a dívida #38:
  `diagnostico_completo` não morre mais se `legislacao` falhar ou pedir revisão. Medido rodando:
  RAG local ~4,5s, contexto por metadados ~0,5s, timeout real na chamada Gemini
  (`gemini/gemini-2.5-flash`, `litellm.Timeout`, ~33s). Em `diagnostico_completo`, `legislacao`
  virou não-bloqueante por chain para `requires_review=True` e falha; o erro fica em
  `chain_data["legislacao"]` e `diagnostico` roda com contexto parcial. Revalidação: com timeout,
  `diagnostico` rodou depois e entregou 3 passivos (AIJob 135); sem timeout, mas com
  `legislacao.requires_review=True`, também rodou e entregou 3 passivos (AIJob 139). #39 continua
  aberta para robustez própria da legislação.
- **2026-06-01 — Front-matter dos 2 SKILL.md (`fix/skills-frontmatter-40`), dívida #40 FECHADA.**
  Os 2 únicos SKILL.md formais tinham front-matter inválido e `discover_skills` os **ignorava
  silenciosamente** (só WARNING) → agentes rodando sem a skill. Corrigido **só o front-matter** (corpo
  intacto): diagnóstico ganhou `agent:` + `name` com prefixo + `applies_to: {uf: [GO, MS, MT]}`;
  auditor ganhou `name` com prefixo + `applies_to: {doc_types: []}` + string→`description`. **Provado
  rodando** (container api): `discover_skills()` sem warning, `load_skill()` OK, e
  `DiagnosticoAgent._compose_system_with_skills()` com `ctx.metadata={"uf":"MS"}` injeta o corpo
  (~55 KB) entre `<!-- skills:start -->`/`<!-- skills:end -->`; controle negativo sem `uf` não injeta.
  26 testes de skills verdes. **Gap novo: dívida #44** (a chain não propaga `uf` ao diagnóstico —
  ligada à #38; não resolvida aqui). Docx Word duplicados movidos para `docs/_archive/skills-fontes-word/`.

- **2026-06-03 — Diagnóstico enxerga o insumo persistido (`fix/diagnostico-insumo`).** O diagnóstico
  rodava com `tokens_in≈358` e saía genérico quando chamado avulso (aba Agentes) ou com extrator falho
  na rodada — `extracted_fields` vinha **só** de `chain_data["extrator"]` e `legal_context` **só** de
  `chain_data["legislacao"]`, ambos efêmeros. Os dados persistem: campos no `AIJob.result` do extrator
  (dois shapes — `ExtratorAgent.result.extracted_fields` e `document_extractor` save_job com campos no
  topo) e o enquadramento no `AIJob.result` da legislação (`agent_name="legislacao"`). Fix em
  `app/agents/diagnostico.py`: `_load_persisted_extraction` (mescla o job mais recente de cada doc),
  `_load_persisted_legislacao` e `_property_from_extracted` (enriquece o `property` do prompt **sem
  gravar na Property**). `chain_data` segue prioritário — fallback só dispara quando
  `_has_extracted_fields(chain)` é falso. Só campos estruturados pequenos (**nunca** `extracted_text`
  bruto). Modelo: nenhuma mudança de código — o agente já passa `model=gpt-4.1`; caso #8 saiu
  `gpt-4o-mini` por ser **pré-deploy** do PR #53, confirmado agora rodando. UI
  (`AgentResultRenderer.tsx`): `formatLegislacao` formata os itens objeto `{identificador, titulo, ...}`
  (antes saíam `[object Object]`) tipo "Lei nº 12.651/2012 — Código Florestal, art. 17". **Provado
  rodando** (processo 30, container real, gpt-4.1): `tokens_in` **359→3491**, `model_used=gpt-4.1`,
  output cita "Fazenda Boa Vista"/Auto de Infração (não genérico); via chain o `FRESCO_CHAIN` prevalece
  (sem regressão); `_property_from_extracted` monta município/UF/área sem gravar. 44 testes de
  diagnóstico verdes, tsc+build verdes. Doc: `docs/trabalhos/diagnostico_insumo.md`.
- **2026-06-04 — Teste Isis rodada 1 (`fix/teste-isis-rodada1`).** Primeiro teste de caso real (caso
  #10 "Fazenda São Jorge"), 6 defeitos. Contexto-chave: a Isis testou em produção **sem o PR #57**
  (mergeado no início desta sessão) — por isso metade some com o merge. **A** (500 repetido em
  `GET /properties/{id}/issues`): reproduzido inserindo issue com `documentos_cruzados` = lista de
  **objetos** → `ResponseValidationError` (`list[str]` no schema) derruba a lista inteira. Fix em duas
  pontas: `field_validator` em `RegulatoryIssueOut` (conserta linhas legadas na leitura, **sem
  migration**) + `@validates` em `RegulatoryIssue` (normaliza na escrita). **B** (`[object Object]` no
  extrator): `ExtratorResult` fazia `String(value)` em campo-objeto (`confidence`-mapa no shape flat;
  `{value,confidence}` no shape aninhado do caso #10); fix `extratorFieldValue` desempacota `.value` e
  usa `humanizeValue`. **D** (`litellm.Timeout ... None seconds` na legislação): a legislação passa
  `model=` explícito → `complete()` monta 1 só modelo, **sem fallback nem retry**; fix retry só para
  erros **transitórios** (`AI_MAX_RETRIES=2` + backoff exponencial curto) e timeout defensivo
  (`AI_TIMEOUT_SECONDS or 30.0`). Settings com default → compose intacto. **C** (legislação
  `[object Object]`) e **F** (diagnóstico `tokens_in=636`): confirmados **resolvidos pelo #57** —
  `formatLegislacao` cobre o shape real `{identificador,titulo,relevancia}` e o fallback
  `_load_persisted_extraction` não filtra por `doc_type` (cobre `"outros"`); ambos travados com testes
  de regressão (histórico de tokens do processo 30: id 135=637 pré-#57 → id 142=3491 pós). **E**
  (alertas sem cor): sintoma **downstream de A** — `AlertasTab` em `error` renderiza só a caixa de
  falha, então os `AlertaCard` (com `SEVERITY_CLS`, classes estáticas não-purgadas) nunca aparecem;
  fix A restaura o render colorido. Suites: **backend 760**, **frontend 51**, build/tsc/eslint/ruff
  verdes; mypy dos arquivos alterados limpo. Doc: `docs/trabalhos/teste_isis_rodada1.md`.
- **2026-06-05 — Ficha 01 / FASE 4: Decisão + Consolidação, fecho do ciclo (`feat/ficha01-fase4-decisao-consolidacao`).**
  Fecha a Ficha 01 §8: o CONSULTOR decide o staging e a consolidação **determinística (sem LLM)** grava
  na base real. "Agentes propõem (staging), consultor decide (Alertas), sistema grava (base)". Backend:
  `POST /processes/{id}/staging-fields/{fid}/decidir` (`aceitar`/`escolher_fonte`/`editar`/`rejeitar`)
  — **gate**: aceitar um `divergente_transcricao` direto → **422** (exige escolha ativa);
  `divergente_fundo` é aceito como ACHADO sem valor; `escolher_fonte` rejeita os irmãos (mesmo
  target/matrícula); `editar` exige `valor`. `POST .../aceitar-consistentes` (lote dos consistente).
  `POST /processes/{id}/consolidar` (`app/services/staging_consolidation.py`, idempotente): aceito →
  `Client`/`Property`/`Matricula` com **upsert por `matricula_hint`** (cria/atualiza), allowlist de
  colunas + alias (`document`→`cpf_cnpj`), `field_sources[col]="human_validated"`, auditoria por
  gravação (`AuditLog`). **NÃO sobrescreve `Property.total_area_ha`** — área = derivada
  (`area_total_matriculas()`). Frontend: `ConsolidacaoPanel` estende a aba **Alertas** (grupos por
  entidade Cliente/Imóvel/Matrícula, valor por fonte, ações por campo, banner "aceitar consistentes",
  botão "consolidar na base" + resumo) — o fluxo de `RegulatoryIssue` segue intacto. **Validação real
  rodando (ciclo completo, caso São Jorge, processo 30/property 11/client 21):** auditor (Fase 3)
  marcou áreas `consistente` + denominações/CAR `divergente_transcricao`; aceitar-consistentes (2) →
  gate aceitar divergente **422** → escolher_fonte denominação 4.698 (rejeita irmã) → aceitar pendentes
  → **consolidar: 7 campos, 2 matrículas criadas** (4.698: area 660,6561/cartório CRI Uirapuru/denom
  "Fazenda São Jorge"/RL "132,00 ha"; 6.776: 349,9022), Client.full_name + Property.car_code gravados,
  **`area_total_matriculas`=1.010,5583**, **`total_area_ha`=250 NÃO sobrescrito**; **idempotência**
  (re-consolidar: 0 criadas, 2 atualizadas, contagem segue 2); audit `consolidar`×2/`staging_decidir`×5/
  `aceitar_consistentes`×1. **Ciclo da Ficha 01 fechado (Fases 1→4).** Testes
  `tests/api/test_fase4_consolidacao.py` (3: ciclo+gate+idempotência, editar, rejeitar). Suite verde;
  ruff/tsc/build/eslint limpos. `FLUXOS_E2E.md` ganhou o Fluxo 8 (staging→decisão→consolidação); sem ADR
  novo (desenho segue as Fichas). Doc: `docs/trabalhos/ficha01_fase4.md`.
- **2026-06-05 — Ficha 02 / FASE 3: Auditor → Matriz de Inconsistências (`feat/ficha02-fase3-matriz-inconsistencias`).**
  A saída canônica do `auditor_imovel` virou a MATRIZ (Ficha 02): confronto multi-fonte
  **DETERMINÍSTICO** (sem LLM — auditor segue determinístico) lendo o staging da Fase 2. Novo
  `app/services/inconsistency_matrix.py`: colunas dinâmicas por fonte (cada matrícula via
  `matricula_hint` + ccir/itr/car/rat/sigef), linhas canônicas (`area_total`, `denominacao_imovel`,
  `codigo_incra_sncr`, `sigef_georreferenciamento`, `car_presenca_consistencia`, `acesso_imovel`) +
  linhas técnicas das `pendencias_rat` (`profundidade="tecnica"`, gap D1 — só registram, sem
  confronto espacial). Âncora = SIGEF; taxonomia Ficha 02 §4 (enum `MatrixSituacao`:
  critico/inconsistente/divergente±subtipo transcricao|fundo/atencao) + destino. Área: ≤0,5% ⇒
  consistente; não-nulo ⇒ divergente (fundo se geo ausente/0, senão transcrição). Efeitos: (1) marca
  o staging das linhas confrontadas (`consistente`/`divergente_transcricao`/`divergente_fundo`;
  aceito/rejeitado é do consultor, Fase 4); (2) `matriz_inconsistencias` persiste no `result` do AIJob
  do auditor — **campo NOVO**, shape antigo intacto (`content`/`divergencias`/`issue_ids`/
  `findings_raw`/`geom_present`/`method`); (3) diagnóstico ganhou `_load_persisted_auditor` (mesmo
  padrão do atendimento) — sem chain, recupera o AIJob e injeta a matriz no contexto do prompt (sem
  tocar prompt-template); (4) UI `AuditorResult` ganhou a tabela da matriz (item×situação×ação, cores
  por situação, flag "técnica — aguarda geo"). Fase 2 ajustada (aditivo): matrícula `denominacao`, ITR
  `numero_car` (alimentam denominação × confronto e car_presença). Skill
  `auditor_imovel/analise_divergencias_documentais` → **v1.2.0** (nota da matriz; a `situacao` é eixo
  distinto do `grade` da "Régua de área", que segue valendo p/ o `RegulatoryIssue`). **Validação real
  rodando (matriz da Isis Ficha 02 §7, caso São Jorge, staging semeado no processo 30):** area_total
  divergente/transcricao "ajustar/justificar **0,153 ha**" (soma matrículas 1.010,5583 vs CAR
  1.010,7113); denominacao divergente (Fazenda São Jorge × Shangri-lá Parte 2 × São Jorge);
  codigo_incra atencao; sigef **critico** (ausente); car_presenca **inconsistente** (ITR sem CAR);
  acesso atencao; 3 técnicas **critico** (APA/supressões/hidrografia). Staging marcado (matrículas
  consistente; CAR/ITR/denominação divergente_transcricao); diagnóstico re-rodado (job 152) citou a
  matriz. Suite completa verde; ruff/tsc/build limpos. **Legislação/normas:** a matriz é cruzamento
  documental puro — NÃO consulta o RAG de legislação (isso é do `legislacao`/diagnóstico); nada a subir
  por conta desta fase. **NÃO nesta fase:** tela de decisão/consolidação (Fase 4), LLM no auditor,
  confronto espacial real (gap D1). Doc: `docs/trabalhos/ficha02_fase3.md`.
- **2026-06-04 — Teste Isis rodada 2 (`fix/teste-isis-rodada2`).** Segunda leva (orquestração +
  contexto entre agentes), 5 achados. Reprodução no análogo local **processo 30 / propriedade 11 /
  tenant 2** (a base prod-like com usuários Isis não roda local; o 30 é o único caso com pipeline
  completo). **Causa-raiz única de B+C:** `validate_preconditions()` levanta `ValueError` **antes** de
  `_create_running_job()` em `BaseAgent.run()` → nenhum AIJob é criado (execução some do histórico = B)
  e `run_agent` faz `self.retry()` de um erro **determinístico** (retry storm + UI presa em "Execução
  agendada" sobre um histórico que nunca ganha linha = C). Fix: job criado **antes** das pré-condições,
  validação movida pra **dentro do `try`** (falha → job `failed` + `AgentResult(success=False)`, sem
  propagar); cost-cap segue antes do job (hard limit intacto); `run_agent` ganhou `except ValueError`
  que **não** faz retry (commit do job `failed` + retorno `status=failed`). Provado: auditor sem
  processo → job 146 `failed` em **0.79s sem retry** (antes: `retry in 30s` em loop). **A** (`AgentsPage.tsx`):
  só o card do Extrator reagia ao "ID do Processo" (botão process-aware); os demais traziam "Executar"
  sempre habilitado, solto do caso. Fix: todo agente executável habilita/rotula com processo válido
  ("Rodar no processo #X"); rodar avulso segue pelo seletor abaixo. **E** (atendimento não chega ao
  diagnóstico): o `atendimento` **não** roda na chain `diagnostico_completo` (é create-case), então o
  relato inicial do consultor — inclusive o que só existe na fala e não em doc (ex.: **embargo sem
  documento**) — nunca chegava. Fix em `diagnostico.py` **sem tocar prompt-template** (proibido): inclui
  narrativa do processo (`description`/`initial_summary`/`intake_notes`) no placeholder `{process_data}`
  + novo `_load_persisted_atendimento()` injeta o AIJob do atendimento como `relato_demanda_consultor`,
  **SEMPRE** (fonte adicional; extrator/legislação seguem prioritários). Provado no processo 30: diag
  passou de **"Não há embargo vigente"** (job 145) para **"relato verbal de embargo… sem documentação
  comprobatória"** + ações de confirmar o embargo (job 147). **D** confirmado resolvido pela rodada 1
  (kanban 200/20 cards; `/properties/11/issues` 200/5). Suites: `tests/agents/` 183, suite completa
  verde, tsc + build verdes. Doc: `docs/trabalhos/teste_isis_rodada2.md`.
- **2026-06-05 — Ficha 01 / FASE 2: extração estruturada → staging (`feat/ficha01-fase2-extracao-estruturada`).**
  O Extrator passou a **preencher** `ExtractedFieldStaging` (a Fase 1 só criou a tabela). Extração
  ESTRUTURADA por tipo de documento (Ficha 01 §5.1-5.7), **adicional** ao fluxo atual: 1 chamada LLM
  dedicada por doc, reusando o texto do OCR; o `AIJob.extracted_fields` (que UI e diagnóstico leem)
  **continua igual** — `extract_document_fields` intocado. Novo `app/services/ficha01_extraction.py`:
  (1) `classify_doc_type(text, current)` rule-based por conteúdo reconhece os 8 canônicos
  (`rg_cpf, endereco, car, ccir, matricula, itr, sigef, rat` + `outro`); respeita tipo específico já
  atribuído, só `outro`/None dispara heurística; ordem importa (rat antes de car). (2) `_FIELD_SPECS` +
  `_STAGING_PROMPTS` por tipo; `build_staging_fields` mapeia o JSON → linhas (escalares com
  `{value[,unidade]}` + listas especiais: `car.matriculas[]` → `matricula_listada` por item com
  `matricula_hint`; `rat.pendencias[]` → `pendencias_rat` JSON). (3) `extract_and_stage` persiste com
  `status=pendente`, `created_by_agent="extrator"`, `ai_job_id`. `ExtratorAgent._stage_ficha01` chama
  nos 2 caminhos (doc único + processo); `base.py` agora expõe `self._current_job` p/ o `ai_job_id`.
  **Decisão de nomenclatura `rat` (Ficha 02 §8):** RELATÓRIO DE ANÁLISE TÉCNICA do CAR (emitido pelo
  órgão); "Retificação" é ATO, não documento → sem doc_type. As pendências do RAT são o insumo central
  do Diagnóstico/Matriz (Fase 3). **Validação real rodando** (equivalentes São Jorge, docs inseridos
  como `outro` → classificados certo): Recibo CAR → `car`, 9 linhas (nº CAR, área 1010,5583, **2
  `matricula_listada` hints 4.698/6.776**); RAT → `rat`, 7 linhas (protocolo GO-RAT-2025-000123,
  situação Pendente, **`pendencias_rat` estruturado**); certidão → `matricula`, 6 linhas (hint 4.698).
  22 linhas `pendente`/`extrator`/`ai_job_id`; `extracted_fields` (AIJob 148) dict plano intacto.
  Test-safety: `test_extrator_cache` ganhou fixture autouse que stuba o staging (mesma disciplina do
  mock de `extract_document_fields`) — o `.env` local tem `AI_ENABLED=true`+chave real, então sem o
  stub o staging dispararia LLM real em teste. **Custo/dívida:** +1 chamada LLM por doc; unificar as
  duas extrações fica como otimização futura. Suite verde + ruff limpo. **NÃO nesta fase:**
  reconciliação multi-fonte do auditor (3), tela de Alertas/consolidação (4), gravar base real.
  Doc: `docs/trabalhos/ficha01_fase2.md`.
- **2026-06-04 — Ficha 01 / FASE 1: Matrícula + staging (`feat/ficha01-fase1-matricula-staging`).**
  A Ficha 01 (Dicionário de Extração do Intake, espec **fechada** pela dupla fundadora) redefine a
  fundação do intake. Esta FASE 1 instala **só o schema** — extrator/auditor/intake NÃO mudam (fases
  2-4). Decisões de modelagem (já tomadas pela dupla, implementadas, não rediscutidas): (1) **1 Imóvel
  (`Property`) : N Matrículas** contíguas sob o mesmo CAR — CAR/município/nome ficam no imóvel; nº
  matrícula, cartório/registro, INCRA/SNCR, NIRF/CIB, geo (SIGEF), área e averbações ficam na
  `Matricula`; **área do imóvel = SOMA das áreas das matrículas** (derivada, via
  `Property.area_total_matriculas()`). (2) **Staging** (`ExtractedFieldStaging`): extrator/auditor
  escrevem campos extraídos lá, NUNCA na base; a base só grava na confirmação do consultor (fase 4) —
  "agentes propõem (staging), consultor decide (Alertas), sistema grava (base)". (3) Campo **extraído**
  (carrega `confidence` + `status` de validação) ≠ **derivado** (carrega rastreabilidade
  `created_by_agent`/`ai_job_id`). Entregue: 2 models + enum `extractedfieldstatus` (6 valores),
  `Property.matriculas` (1:N) + `area_total_matriculas()` (`total_area_ha` legado mantido), migration
  `a1f2c3d4e5f6` provada up→down→up limpa, repos tenant-scoped, endpoints `GET`/`POST
  /properties/{id}/matriculas` + `GET /processes/{id}/staging-fields` (filtro status, 422/404/401),
  10 testes (incl. caso real: matrículas 4.698=660,6561 + 6.776=349,9022 → **1.010,5583 ha**). ADR-015
  (entidade Matrícula + staging, referenciando a Ficha 01 como espec) + MODELO_DE_DADOS atualizados.
  Suite completa verde + ruff limpo. **NÃO neste PR:** fase 2 (extrator escreve no staging + migração
  de dados `Property`→`Matricula`), fase 3 (reconciliação multi-fonte do auditor), fase 4 (tela de
  Alertas/consolidação). Doc: `docs/trabalhos/ficha01_fase1.md`.
- **2026-06-05 — Intake: roteamento geoespacial + card lateral (`fix/intake-geo-routing`).** Dois
  sintomas de produção, ambos com causa-raiz medida e fix provado. (1) **`.kml` caía no OCR de PDF**:
  `import_draft_documents` enfileirava `ocr_then_extract` para TODOS os docs do draft sem guard, então
  geometria (KML/KMZ/SHP/GeoJSON/GPX) batia na cascata `pypdf`(0 chars)→Gemini(`400 Unsupported MIME
  type: application/octet-stream`)→`rasterization_failed`. Fix **só ROTEIA** (geometria real é o gap
  D1): novo `app/services/geo_files.py` (`is_geospatial` por extensão **ou** MIME + `zip_contains_shapefile`
  pra `.zip`); no `/import` e `/confirm-upload` o geo entra `ocr_status=not_required` +
  `document_type=geoespacial` SEM dispatch (resposta agrega `docs_skipped_geo`); guard no worker
  (extensão/MIME antes do download; `.zip`-com-shapefile depois) com falha LIMPA; guard no orquestrador
  (`ocr_pdf` sem assinatura `%PDF` → `not_a_pdf`, sem cascata de providers). (2) **Card do intake não
  atualizava** ao job concluir (preso em "Aguardando" → consultor achava que falhou): o polling de
  `DraftDocumentUploader` só ligava com doc em `processing`, mas o `/import` marca `pending` → o
  intervalo nunca iniciava. Fix: flag `awaitingOcr` + polling enquanto houver doc não-terminal
  (`pending`/`processing`), parando em `done`/`failed`/`not_required`; pill "Armazenado" + mensagem
  honesta pro geo. **Aprendizado de ferramenta:** rodar vitest via `npm test` (não `npx vitest`) — o
  flag Node de `require(esm)` p/ jsdom vive no script npm; com `npx` direto todos os testes jsdom
  abortam com `ERR_REQUIRE_ESM`. **Validação:** backend venv+Testcontainers (30 testes novos; regressão
  workers/services/intake 190 passed; ruff limpo); frontend `tsc`/`build` limpos, `npm test` 53 passed,
  eslint limpo. NÃO validado ao vivo: E2E browser→MinIO→Celery (prova por integração+unit). Doc:
  `docs/trabalhos/intake_geo_routing.md`. **NÃO neste PR:** parser KML/SHP, `Property.geom`, PostGIS
  (gap D1 — dívidas #14/#15).
