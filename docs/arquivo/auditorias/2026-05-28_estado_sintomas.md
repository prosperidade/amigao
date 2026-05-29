# Auditoria de estado dos sintomas — 2026-05-28

Branch verificada: `feat/dashboard-redesign-v2`

## Sintoma 1 — Extrator no-op / sem caminho por processo

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| 1 | `app/agents/extrator.py` com metadata vazia ainda retorna `{"skipped": True}` em vez de operar sobre o processo? | PRESENTE | `app/agents/extrator.py:32`, `app/agents/extrator.py:36`, `app/agents/extrator.py:43` | `execute()` lê apenas `metadata["text"]`, `metadata["doc_type"]` e `metadata["document_id"]`; sem `document_id` e sem `text`, retorna `skipped: True`. |
| 2 | Existe endpoint `POST /processes/{id}/extract` ou equivalente que extraia todos os documentos de um processo? | PRESENTE | `app/api/v1/processes.py:51`, `app/api/v1/processes.py:789`, `app/api/v1/agents.py:61`, `app/api/v1/agents.py:147` | Rotas de `processes.py` não incluem endpoint de extração por processo; `agents.py` expõe execução genérica de agente (`/run`, `/run-async`), não endpoint dedicado que percorra todos os documentos do processo. |
| 3 | `extrator.py` ainda faz `raise ValueError` quando `Document.extracted_text` está vazio? | PRESENTE | `app/agents/extrator.py:58`, `app/agents/extrator.py:60`, `app/agents/extrator.py:62`, `app/agents/extrator.py:63` | Com `document_id` e sem `text` em metadata, o agente lê `doc.extracted_text`; se vazio, levanta `ValueError`. |

## Sintoma 2 — Upload desacoplado do checklist

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| 4 | `app/api/v1/documents.py` `confirm_upload` atribui `checklist_item_id` ao `Document` criado? | PRESENTE | `app/schemas/document.py:21`, `app/schemas/document.py:28`, `app/schemas/document.py:29`, `app/api/v1/documents.py:167`, `app/api/v1/documents.py:184` | `DocumentConfirmRequest` não declara `checklist_item_id`; o `Document(...)` criado em `confirm_upload` não recebe `checklist_item_id`. |
| 5 | `auto_link_document` tem algum caller no `app/`? | PRESENTE | `app/services/checklist_engine.py:194` | Busca por `auto_link_document(` em `app/` encontrou apenas a definição da função. |
| 6 | `frontend ProcessChecklist.tsx` — o toggle "Recebido" envia `document_id`? | PRESENTE | `frontend/src/pages/Processes/ProcessChecklist.tsx:109`, `frontend/src/pages/Processes/ProcessChecklist.tsx:111`, `frontend/src/pages/Processes/ProcessChecklist.tsx:122`, `frontend/src/pages/Processes/ProcessChecklist.tsx:123`, `frontend/src/pages/Processes/ProcessChecklist.tsx:304` | `handleReceived` envia apenas `item_id` e `action: "received"`; não envia `document_id`. |
| 7 | `frontend DocumentsTab.tsx` — mostra só badge "Campos extraídos" ou exibe os campos extraídos? | PRESENTE | `frontend/src/pages/Processes/DocumentsTab.tsx:48`, `frontend/src/pages/Processes/DocumentsTab.tsx:57`, `frontend/src/pages/Processes/DocumentsTab.tsx:108`, `frontend/src/pages/Processes/DocumentsTab.tsx:110` | A tela monta `extractedDocIds` a partir de jobs e renderiza somente o badge "Campos extraidos"; não renderiza os campos extraídos. |
| 8 | Endpoint `DELETE` de cliente e `DELETE` de imóvel existem e estão ligados a botão no frontend? Funcionam com cascata? | PARCIAL | `app/api/v1/clients.py:91`, `app/api/v1/clients.py:99`, `frontend/src/pages/Clients/index.tsx:207`, `app/api/v1/properties.py:46`, `app/api/v1/properties.py:84`, `frontend/src/pages/Properties/index.tsx:6`, `app/repositories/base.py:73`, `app/repositories/base.py:75`, `app/models/process.py:96`, `app/models/property.py:16` | Cliente tem endpoint `DELETE`, mas o botão de lixeira não tem `onClick`/`api.delete`; imóvel não tem endpoint `DELETE` nas rotas lidas. O delete base usa `db.delete`; FKs de `process.client_id` e `property.client_id` usam `ondelete="RESTRICT"`. |

## Sintoma 3 — Estado não propaga

| # | O que checa | Status | Onde no código | Observação factual |
|---|---|---|---|---|
| 9 | O endpoint que valida/assina o diagnóstico chama `advance_macroetapa`? | PRESENTE | `app/api/v1/regulatory.py:198`, `app/api/v1/regulatory.py:287`, `app/api/v1/regulatory.py:308`, `app/api/v1/processes.py:789`, `app/api/v1/processes.py:812`, `app/api/v1/processes.py:814` | `PATCH /processes/{process_id}/diagnoses/{version}/validate` grava `validated_at` e faz commit; não chama `advance_macroetapa`. O endpoint de validar artefato também apenas grava `validated_at` e faz commit. |
| 10 | `can_advance_macroetapa` exige existir `RegulatoryDiagnosis.validated_at` nas saídas de etapa de diagnóstico? | PRESENTE | `app/models/macroetapa.py:415`, `app/models/macroetapa.py:422`, `app/models/macroetapa.py:427`, `app/models/macroetapa.py:429` | A função avalia blockers de checklist/documentos e `completion_pct`; não consulta `RegulatoryDiagnosis` nem `validated_at`. |
| 11 | `compute_macroetapa_state` considera `RegulatoryDiagnosis`, ou só `MacroetapaChecklist.completion_pct`? | PRESENTE | `app/models/macroetapa.py:356`, `app/models/macroetapa.py:372`, `app/models/macroetapa.py:381`, `app/models/macroetapa.py:382` | O estado é derivado de `checklist.actions`, `has_blockers`, `is_current` e `checklist.completion_pct`; não há referência a `RegulatoryDiagnosis`. |

## Resumo

Sintoma 1: PRESENTE

Sintoma 2: PRESENTE

Sintoma 3: PRESENTE
