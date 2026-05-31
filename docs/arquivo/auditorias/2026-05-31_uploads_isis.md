# Auditoria — 2 Críticos da Isis: Upload em massa + Persistência inconsistente

> Data: 2026-05-31
> Branch: `audit/isis-uploads-criticos` (base `main`)
> Modo: read-only. Nenhuma mudança em código de aplicação.
> Escopo: mapear a causa raiz dos 2 achados CRÍTICOS reportados pela Isis em 2026-05-31.
> Achados de teste da Isis:
> - **#1** — Upload de ~40 docs falhou em massa; "marcava todos enviados e depois falhou"; "sem opção de deletar"; segunda tentativa leu alguns e outros não; "apenas um arquivo foi enviado".
> - **#2** — "Mostrou que um arquivo foi enviado, mas ao abrir o caso o arquivo não estava lá"; re-anexou; workspace continuou com alertas de falta de documentos, sem intake nem confrontação.

---

## Contexto: qual componente a Isis usou

A tela de upload em massa do cadastro é o **Step 4 (Documentos)** do `IntakeWizard`, que renderiza
`DraftDocumentUploader` (`frontend/src/pages/Intake/IntakeWizard.tsx:5,699`). Esse é o **único** componente
de upload com seleção múltipla (`<input multiple>`). Os outros dois componentes de upload
(`DocumentUploadZone`, usado na aba Documentos do processo; e `DocumentUpload`) sobem **um arquivo por vez**
(`DocumentUploadZone.tsx:114` → `doUpload(files[0])`), logo não são o caminho dos "40 docs de uma vez".

Ponto estrutural que atravessa os dois críticos: no Step 4 os documentos são anexados a um
**rascunho (`intake_draft`)**, não ao processo. O `Document` nasce com `intake_draft_id` preenchido e
`process_id = NULL` (`intake.py:704-721`). A ligação do doc ao processo só aconteceria na migração do
endpoint `/commit` — que, como mostrado na Frente 2, **o wizard nunca chama**.

---

## Frente 1 — Fluxo de upload no frontend (#1)

Arquivo: `frontend/src/pages/Intake/DraftDocumentUploader.tsx`.

| # | O que checa | Achado factual | Onde no código |
|---|---|---|---|
| 1 | Componente usado no Step 4 | `DraftDocumentUploader` (multi-arquivo). Único uploader com `multiple`. | `IntakeWizard.tsx:699`; `DraftDocumentUploader.tsx:284-290` |
| 2 | Seleção múltipla | `<input type="file" multiple>`. Sem drag&drop neste componente. | `DraftDocumentUploader.tsx:287` |
| 3 | Estratégia de upload | **SEQUENCIAL** — `for (const file of Array.from(files)) { await … }`. Não há `Promise.all`. Um arquivo por vez, em série. | `DraftDocumentUploader.tsx:142-201` |
| 4 | Limite de concorrência | N/A — é sequencial (concorrência efetiva = 1). | `:142` |
| 5 | Limite de tamanho/quantidade | **Nenhum** limite de tamanho ou de quantidade no componente. Aceita os 40 de uma vez. | `:130-210` (ausência) |
| 6 | Timeout por etapa | PUT ao storage: **45s** (`PUT_TIMEOUT_MS`, AbortController). Presign + confirm (axios): **20s** (`BACKEND_TIMEOUT_MS`). | `:136-139,152,156,188` |
| 7 | Retry | **Nenhum** retry em nenhuma das 3 etapas. Falha → entra em `failures[]`. | `:142-201` (ausência) |
| 8 | Fluxo de 1 upload | (a) `POST /intake/drafts/{id}/upload-url` → (b) `PUT` direto ao storage (fora do axios) → (c) `POST /intake/drafts/{id}/documents` (confirm). | `:145-189` |
| 9 | Quando a UI marca "Enviado" | **Não é otimista.** A lista `docs` vem de `refresh()` = `GET /intake/drafts/{id}/documents` (banco). O badge deriva de `ocr_status`. `refresh()` só roda **ao fim** do loop inteiro (`:204`). | `:91-99,204; badge :249-254` |
| 10 | Estados visuais do item | 4 badges por `ocr_status`: `null/pending`→**"Enviado"**; `processing`→"Em leitura"; `done`→"Lido"; `failed`→**"Falhou"**. | `:249-254` |
| 11 | Transição "Enviado"→"Falhou" | Não existe transição reversa **no upload**. O badge "Falhou" aparece quando `ocr_status` vira `failed` — o que só acontece **depois** do botão "🤖 Ler documentos com IA" (`/import`) disparar o pipeline OCR, que pode falhar (ver Frente 2, item 12). | `badge :252`; import `:212-225` |
| 12 | Tratamento de erro na UI | Erros de PUT e de confirm são capturados, acumulados em `failures[]` e exibidos como **uma string única inline** (caixa vermelha no topo), separados por `·`. Sem toast. Sem retry. | `:165-200,205-207,258-262` |
| 13 | Botão de deletar | **Existe**, mas só renderiza quando `canDelete(ocr_status)` = `ocr_status ∈ {null, 'pending'}`. Para `processing/done/failed` o botão **some** (`canRemove` falso). | `:231-247,299,311-321` |
| 14 | "Sem opção de deletar" (Isis) | Confirmado pelo design: um doc que **falhou no OCR** (`ocr_status='failed'`, badge "Falhou") tem `canDelete=false` → **sem botão de excluir**. O comentário do código manda remover "pela aba Documentos do processo" — mas o doc do rascunho **nunca tem `process_id`** (Frente 2), então também não aparece lá. Beco sem saída. | `:228-230,247,311` |
| 15 | Refresh/polling pós-"Enviado" | Há polling de 5s **apenas enquanto** algum doc está em `processing` (`:117-128`). Em `pending`/`failed` não há polling — o badge "Falhou" persiste até a próxima ação. | `:117-128` |
| 16 | Áudio da entrevista | Caminho separado (`handleAudioUpload`) também presign+PUT ao draft; não passa pelo loop dos 40. | `IntakeWizard.tsx:347-372` |

---

## Frente 2 — Persistência no backend (#2)

Arquivos: `app/api/v1/intake.py`, `app/api/v1/documents.py`, `app/models/document.py`,
`app/repositories/document_repo.py`, `app/workers/ocr_tasks.py`.

| # | O que checa | Achado factual | Onde no código |
|---|---|---|---|
| 7 | Presign do draft | `POST /intake/drafts/{id}/upload-url`. **Não cria Document.** Só gera URL + `storage_key` com `uuid.uuid4()` **por chamada** (chave única a cada presign — re-upload do mesmo arquivo **não colide**). Bloqueia se draft já `card_criado` (409). | `intake.py:642-670`; `storage.py:109-130` |
| 8 | Confirm do draft | `POST /intake/drafts/{id}/documents`. **Cria** `Document` com `intake_draft_id`, `process_id=NULL`, `ocr_status=pending`, `source=intake`. Commit imediato. **Não dispara OCR/extrator aqui.** | `intake.py:673-733` |
| 9 | Modelo Document | NOT NULL: `tenant_id, original_file_name, filename, content_type, storage_key`. `storage_key` é **UNIQUE**. `process_id` é **nullable** (doc pode existir só preso ao draft). `ocr_status` default `pending`. | `document.py:36-63` |
| 10 | Constraint que bloqueia INSERT | `storage_key UNIQUE NOT NULL`. Como o presign usa uuid novo por chamada, re-upload **não** dispara colisão — esse não é o gatilho do "some uns, outros não". | `document.py:49`; `storage.py:119` |
| 11 | Disparo de OCR no draft | Só no endpoint **`/import`** (`POST /intake/drafts/{id}/import`), que enfileira `ocr_then_extract.delay(...)` por doc. Reseta para `pending` e o worker move para `processing`→`done/failed`. | `intake.py:775-839` |
| 12 | OCR vira `failed` (transição reversa) | `ocr_then_extract` seta `ocr_status=failed` em vários caminhos: sem bytes no storage (`:94`), **budget mensal de IA estourado** (`:157`, retorna `budget_exceeded`), extração falha (`:229`) e exaustão de retries (`:261-267`, `max_retries=2`). Qualquer um flippa o badge "Enviado"→"Falhou". | `ocr_tasks.py:86-94,155-170,224-267` |
| 13 | Lista de docs de UM caso | `GET /documents?process_id=X` → `list_scoped` filtra `Document.process_id == X` **e** `deleted_at IS NULL`. **Não há fallback por `intake_draft_id`.** Doc órfão de draft (`process_id=NULL`) **nunca** aparece no caso. | `documents.py:83-110`; `document_repo.py:24-66` |
| 14 | Migração draft→processo (`/commit`) | `POST /intake/drafts/{id}/commit` migra docs via bulk UPDATE (`process_id/client_id/property_id`), enriquece e marca draft `card_criado`. **Mas:** `grep` por `/commit` em `frontend/src` → **0 ocorrências**. O wizard **não chama** esse endpoint. | `intake.py:930-1012`; frontend: ausência |
| 15 | Finalização real do wizard | `handleSubmit` → `POST /intake/create-case` (`IntakeWizard.tsx:287`). `buildPayload()` **não inclui `draft_id`** (`:218-262`). `create_case` **não referencia draft nenhum** — cria Cliente/Imóvel/Processo/checklist do zero. Resultado: docs do draft **ficam órfãos** (`process_id` permanece NULL). | `IntakeWizard.tsx:265-297,218-262`; `intake.py:95-224` |
| 16 | Auto-link doc↔checklist | `auto_link_document`/`mark_item_received` rodam **só** no fluxo de processo (`/documents/confirm-upload`, `documents.py:200-220`). O confirm de **draft** não faz auto-link. Logo, mesmo se o doc existisse, não marcaria item do checklist do caso novo. | `documents.py:200-220`; `intake.py:704-723` (sem auto-link) |
| 17 | Workspace "falta de documentos" | O checklist do caso é gerado por `create_case` com todos os itens pendentes. Como nenhum doc do draft é migrado nem auto-linkado, **todos os itens seguem "faltando"** → alertas persistem. "Sem intake nem confrontação" = nenhum extrator/auditor rodou contra docs do processo, porque o processo tem **zero** documentos. | `intake.py:95-224` (gera checklist); itens 13-16 acima |

---

## Frente 3 — Correlação entre #1 e #2

| # | Cenário Isis | Reconstrução factual | Onde no código |
|---|---|---|---|
| 18 | "Marcava enviado depois falhou" + "apenas 1 enviado" | O loop é sequencial com timeouts de 20s (backend) / 45s (PUT) e **sem retry**. Com backend lento (cold start Render) ou storage instável, os `POST` de presign/confirm estouram `ECONNABORTED` e caem em `failures[]`. Ao fim, `refresh()` mostra só os confirms que persistiram ("Enviado") e a caixa vermelha lista o resto. "Apenas 1 enviado" = 1 confirm sobreviveu. **Segundo gatilho**: se ela clicou "Ler com IA", o budget guard / falha de OCR flippa os badges "Enviado"→"Falhou" em lote. | `DraftDocumentUploader.tsx:142-207`; `ocr_tasks.py:155-170` |
| 19 | "Segunda tentativa: leu alguns, outros não" | Re-upload gera `storage_key` novo (uuid) por arquivo — sem colisão de unique. Mas o loop sequencial sem retry sob backend instável volta a ter sucesso parcial. Resultado não-determinístico, dependente da latência do backend/storage no momento. | `storage.py:119`; loop `:142-201` |
| 20 | "Enviou mas sumiu ao abrir o caso" | A listagem do caso vem **do banco** (`Document.process_id==X`), não de cache local do front. Como o wizard finaliza por `create-case` (não `commit`), os docs do draft ficam com `process_id=NULL` e **nunca** entram nessa query. O que a Isis viu "enviado" era o estado **do rascunho** (`/intake/drafts/{id}/documents`), tela diferente da do caso. | `document_repo.py:24-66`; `IntakeWizard.tsx:287`; `intake.py:972-987` (migração só no commit, não chamado) |

---

## A. Causa raiz hipotética do #1 (upload em massa)

O `DraftDocumentUploader` sobe os arquivos em **série** (`for … await`), sem retry e sem limite de
tamanho/quantidade, com timeouts de 20s (chamadas ao backend) e 45s (PUT ao storage). Para ~40 documentos
isso é uma cadeia longa e frágil: basta o backend estar lento (cold start do Render, contenção no
`head_bucket`/MinIO) para que vários `POST /upload-url` ou `POST /documents` estourem `ECONNABORTED`,
caindo em `failures[]` sem nenhuma nova tentativa. Como o badge "Enviado" deriva do que o `refresh()` lê do
banco ao **fim** do loop, o usuário vê só os poucos confirms que sobreviveram ("apenas um arquivo foi
enviado") e uma caixa vermelha concatenando dezenas de mensagens de erro.

A percepção de "marcava todos enviados e **depois** apareciam como falhou" tem um segundo mecanismo
plausível e independente: os docs que **persistiram** com `ocr_status=pending` mostram badge "Enviado"; ao
acionar "🤖 Ler documentos com IA" (`/import`), o pipeline `ocr_then_extract` pode falhar em lote — por
**budget mensal de IA estourado** (`ocr_tasks.py:157`, comum com 40 docs de uma vez), por arquivo sem bytes
no storage, ou por exaustão de retries — virando `ocr_status=failed` e flippando o badge para "Falhou". A
isso soma-se a queixa de "sem opção de deletar": o botão de excluir só existe para `null`/`pending`; assim
que o doc entra em `processing/done/failed`, o botão desaparece, e o caminho alternativo indicado pelo
código ("remover pela aba Documentos do processo") não funciona porque esses docs nunca têm `process_id`.

## B. Causa raiz hipotética do #2 (persistência inconsistente)

O wizard finaliza o cadastro chamando `POST /intake/create-case` (`IntakeWizard.tsx:287`), e
`buildPayload()` não envia `draft_id`. O `create_case` cria Cliente/Imóvel/Processo/checklist do zero e
**não tem qualquer referência ao rascunho**. A única rotina que migra os documentos do rascunho para o
processo (bulk UPDATE setando `process_id`) está no endpoint `POST /intake/drafts/{id}/commit`
(`intake.py:972-987`) — e esse endpoint **não é chamado por nenhum ponto do frontend** (`grep` por
`/commit` em `frontend/src` → 0). Resultado: os `Document` anexados no Step 4 permanecem com
`process_id=NULL` e `intake_draft_id` preenchido.

Quando a Isis abre "o caso", a aba de documentos consulta `GET /documents?process_id=X`, cujo
`list_scoped` filtra estritamente por `Document.process_id == X` (sem fallback por `intake_draft_id`). Os
docs do rascunho são invisíveis ali — daí "enviei mas não está lá". Pela mesma razão, o checklist do caso
novo nasce inteiro como "faltando" (nada foi auto-linkado, pois `auto_link_document` só roda no
`/documents/confirm-upload` do fluxo de processo, não no confirm de draft), e não há "intake nem
confrontação" porque não há **nenhum** documento sob o processo para o extrator/auditor processar. O
re-anexar dela provavelmente também ocorreu na tela do rascunho (ou gerou novos órfãos), sem nunca cruzar a
fronteira draft→processo.

## C. Correlação entre os dois

São **dois bugs distintos** que se **compõem** para produzir a mesma sensação de "enviei e sumiu", não o
mesmo bug visto de dois ângulos.

- **#1** é uma **fragilidade de transporte/UX no upload** (série sem retry + timeouts + budget de OCR):
  determina **quantos** documentos chegam a virar `Document` e em que badge param.
- **#2** é um **buraco de fluxo na finalização** (wizard usa `create-case` em vez de `commit`):
  determina que **mesmo os documentos que persistiram com sucesso** nunca alcançam o processo.

A interação é multiplicativa: o #1 reduz quantos docs persistem e ainda flippa badges para "Falhou"; o #2
garante que, dos que sobreviveram, **nenhum** aparece no caso nem alimenta checklist/diagnóstico. Mesmo que
o #1 fosse 100% resolvido (todos os 40 confirmados), o #2 sozinho ainda faria todos sumirem ao abrir o
caso. E mesmo que o #2 fosse resolvido (migração no finalize), o #1 ainda faria a maioria falhar no envio.
São independentes na causa e somam-se no sintoma.

## D. Perguntas em aberto (não decidíveis só pelo código)

1. **A Isis chegou a clicar "🤖 Ler documentos com IA" (`/import`)?** Isso decide se os badges "Falhou" que
   ela viu vieram de falha de **upload** (item 18) ou de falha de **OCR/budget** (item 12). Precisa do
   relato dela ou de logs.
2. **O backend estava em cold start / sob latência alta no momento?** A hipótese de timeouts em série
   depende disso — exige logs do Render/API (ocorrências de `ECONNABORTED`, tempos de resposta de
   `/upload-url` e `/documents`).
3. **O budget mensal de IA do tenant estava esgotado?** Determina se `ocr_then_extract` retornou
   `budget_exceeded` em lote (`ocr_tasks.py:157`). Precisa do estado real de `check_tenant_monthly_budget`
   no dia.
4. **Houve falha de CORS/credencial no PUT ao storage?** O componente sinaliza isso como mensagem genérica;
   distinguir CORS de timeout de rede exige reproduzir com devtools/network abertos (memória do projeto já
   alerta que "CORS error pode mascarar 4xx").
5. **Quantos `Document` órfãos de draft existem hoje no banco?** Uma contagem de
   `Document WHERE process_id IS NULL AND intake_draft_id IS NOT NULL` quantificaria o impacto real do #2 —
   não verificável neste worktree (read-only, sem dados).
