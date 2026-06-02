# EXTRATOR — sister file

> Documento vivo do agente `extrator`. Toda afirmação aqui é verificável no
> código (referências `arquivo:linha`). Criado em 2026-05-30 a partir do código
> real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Extrai campos estruturados de documentos (matrícula, CAR, CCIR, CPF/CNPJ, etc.)
via OCR + LLM. Alimenta a **coleta documental** (macroetapa 3) e o enriquecimento
da base do cliente/imóvel no intake. É agente de **apoio** — não emite peça
formal, não decide; entrega dados extraídos com proveniência.

Registrado como `"extrator"` / `ExtratorAgent`, `job_type="extract_document"`
(`app/agents/extrator.py`).

## 2. Estado de implementação

- **Implementado.** `execute()` chama `extract_document_fields()` (OCR + LLM) e
  retorna `extracted_fields`, `doc_type`, `fields_count`, e `skipped` quando não
  há documento no contexto.
- **Proveniência por campo (PR Intake backend, #26):** `Client.field_sources` e
  `Property.field_sources` (JSONB, `PortableJSON`) registram a origem de cada
  campo — `"raw"` / `"ai_extracted"` / `"human_validated"`. Permite à UI exibir
  badge "extraído pela IA" e ao consultor validar manualmente.
- **Preview lateral:** `GET /api/v1/intake/drafts/{draft_id}/extracted-fields`
  (`app/api/v1/intake.py`) expõe os campos extraídos com `value`, `confidence`,
  `source_document_id` e a flag `diverges_from_manual`.
- **Reconciliação:** `POST /api/v1/intake/drafts/{draft_id}/reconcile` grava a
  decisão do consultor (origem `manual`|`extracted`) em
  `form_data["field_sources"]` e cria `AuditLog` (`action="reconciled"`).
- **Pipeline OCR:** disparado por `app/workers/ocr_tasks.py:ocr_then_extract`
  (cache SHA-256, budget guard). Ver `docs/arquitetura/PIPELINE_OCR.md`.

## 3. Skills

Sem skill procedural formal dedicada em `app/skills/extrator/` no momento. O
comportamento vive em `extract_document_fields()` + prompts em
`app/services/document_extractor.py` (com fallback hardcoded; o prompt real pode
vir do banco via `prompt_service`). O `ExtratorAgent.execute()` chama o serviço
direto — **não** passa por `_compose_system_with_skills`. Transformar esse prompt
numa skill procedural é dívida registrada (#45, `REGISTRO_DIVIDAS`). (Skills
existentes hoje: `diagnostico/situacao_ambiental_imovel_rural` e
`auditor_imovel/analise_divergencias_documentais`.)

**Janela de texto (`EXTRACTOR_MAX_CHARS`, default 30.000):** o extrator considera
os primeiros `settings.EXTRACTOR_MAX_CHARS` chars do `extracted_text`. Era 3.000
hardcoded (`document_extractor.py:183`) — truncava escrituras/matrículas reais
(15-25k chars): a capa (certidão CNIB) trazia só nome+CPF e os campos do imóvel
(área/matrícula/município), que ficam depois do char 3.000, vinham `None`. Fix
2026-06-02 (`fix/extrator-truncamento`): janela elevada/configurável + prompt da
matrícula avisa que o doc tem várias seções e que os campos podem estar em
qualquer parte. Provado no doc 118 (escritura Romilton, 20.817 chars): área
58,7654 / município Uirapuru / UF GO / denominação / comarca / cartório passaram
de `None` a preenchidos.

## 4. Tools que usa

- **OCR pipeline** (`ocr_then_extract`) — extração de texto de PDFs.
- **LiteLLM gateway** (`ai_gateway.complete`) — extração estruturada via LLM.
- **AIJob** — persiste cada chamada (tokens, custo, `result.extracted_fields`).

## 5. Inputs aceitos

Por `ctx.metadata`: `document_id`, `text`, `doc_type`. Quando nenhum documento é
fornecido, retorna `skipped` (não é erro). Quatro caminhos de disparo:
1. Via `/agents` (execução manual por agente).
2. Via processo (`POST /api/v1/processes/{id}/extract`).
3. Via chain `enquadramento_regulatorio` (`["extrator", "legislacao"]`) e
   `diagnostico_completo` (`["extrator", "auditor_imovel", "legislacao", "diagnostico"]`).
4. **Via IntakeDraft:** no wizard, o extrator é disparado em cada `Document`
   anexado; os campos alimentam o `PreviewPanel` lateral da UI.

## 6. Outputs

`dict` com `extracted_fields`, `doc_type`, `fields_count`, `skipped`. No intake,
a estrutura por campo segue o schema `ExtractedField`
(`app/schemas/intake.py`): `{value, confidence, source_document_id}`. Os campos
extraídos previstos no `ExtractedFields`: `nirf`, `ccir_numero`, `sigef_numero`,
`car_numero`, `municipio`, `uf`, `coordenadas_centroide`, `area_total_ha`,
`titular_matricula`, `area_app`, `area_rl`, `area_consolidada`.

`requires_review=False` — o extrator não emite peça formal; a revisão humana
acontece na reconciliação do wizard.

## 7. Knowledge essencial

- Tipos documentais: matrícula, CAR, CCIR, NIRF, SIGEF, CPF/CNPJ, comprovante,
  contrato societário, KML/SIGEF.
- Distinção área documental × área gráfica (campos em `Property`:
  `area_documental_ha`, `area_grafica_ha`).
- Não inventa valor: campo ausente fica vazio; a régua de divergência (auditor)
  não dispara quando um lado é `None`.

## 8. Conversation patterns

Não conversacional. Roda como task (síncrona via API ou async via Celery na
chain). Reentrante: reprocessar o mesmo documento sobrescreve o `AIJob` mais
recente daquele `document_id`.

## 9. Cross-agente

- Alimenta `auditor_imovel` (que cruza `extracted_data` com CAR/matrícula) e
  `diagnostico` na chain `diagnostico_completo`.
- **Reconciliação (espírito ADR-012):** a decisão entre valor manual e extraído
  é registrada no draft/processo — contextual, não perene no imóvel.

## 10. Dívidas técnicas próprias

- **#9** — `except Exception` genérico no `pdf_generator.py` (tratamento de erro
  frágil; o extrator depende do pipeline OCR).
- **#10** — testes que dependem de storage externo sem mock.
- OCR de PDFs escaneados específicos pendente (ex.: **#28**, Errata SEMAD).

## 11. Próximas frentes

- PR 2.1 (mensagens externas WhatsApp/email) pode trazer anexos que entram no
  pipeline — sem impacto estrutural aqui.
- Auditoria de leitura de campo sensível não afeta o extrator (ele não lê
  segredos).

## 12. Validação Isis

- Pipeline OCR validado em caso real (Romilton, 2026-05-08).
- **Pendente:** wizard com `PreviewPanel` + reconciliação testado pela Isis
  fim-a-fim em dados reais.
