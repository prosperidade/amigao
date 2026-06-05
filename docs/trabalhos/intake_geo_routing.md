# Trabalho — Intake: roteamento de arquivos geoespaciais + card lateral

**Branch:** `fix/intake-geo-routing` (base `main`)
**Data:** 2026-06-05
**Origem:** dois sintomas observados em produção (hoje)

Corrige dois defeitos independentes do intake, ambos provados antes e depois.

---

## Sintoma 1 — `.kml` caía no OCR de PDF e estourava cascata de erros

**O que acontecia:** upload de `.kml` pelo intake era despachado para o pipeline
de OCR de PDF (`ocr_then_extract`). O arquivo não é PDF, então a cascata
estourava na cara do consultor:
- `pypdf` devolvia 0 chars;
- Gemini recusava com `400 Unsupported MIME type: application/octet-stream`;
- o fallback de rasterização (`rasterization_failed`).

**Causa raiz (medida):** `import_draft_documents`
([app/api/v1/intake.py](../../app/api/v1/intake.py)) enfileirava `ocr_then_extract`
para **todos** os docs do draft, sem guard por tipo. KML/KMZ/SHP/GeoJSON/GPX são
**geometria**, não documento — o OCR nunca deveria recebê-los.

**Fix (só ROTEIA + comunica honesto — não processa geometria):**
- Novo módulo [app/services/geo_files.py](../../app/services/geo_files.py):
  `is_geospatial(filename, mime)` (extensão **ou** MIME) e
  `zip_contains_shapefile(bytes)` (inspeciona nomes internos do `.zip`).
  Extensões: `kml, kmz, shp, shx, dbf, prj, geojson, gpx`.
- **Roteamento** no `/import`: doc geoespacial fica `ocr_status=not_required`,
  `document_type="geoespacial"`, **não** dispara OCR. Resposta agrega
  `docs_skipped_geo`.
- **Guard no `/confirm-upload`** ([documents.py](../../app/api/v1/documents.py)):
  geo entra como `not_required` sem dispatch.
- **Guard no worker** ([ocr_tasks.py](../../app/workers/ocr_tasks.py)): falha
  LIMPA por extensão/MIME (antes do download) e por conteúdo (`.zip` com
  shapefile, após o download) — sem cascata de providers.
- **Guard no orquestrador** ([ocr_pdf.py](../../app/services/ocr_pdf.py)): se os
  bytes não têm assinatura `%PDF`, retorna `error="not_a_pdf:..."` antes de
  qualquer provider. Robustez geral: qualquer não-PDF falha limpo.

**Fora de escopo (gap D1, frente própria):** parser de KML/shape,
`Property.geom`, overlay PostGIS. Este PR só impede o erro e armazena o arquivo
honestamente. O consumo real desbloqueia as dívidas #14/#15.

## Sintoma 2 — card do intake não atualizava quando o job concluía

**O que acontecia:** subir PDF válido, o job concluía (visível no histórico de
agentes), mas o card de documentos do intake ficava preso em "Aguardando" — o
consultor achava que tinha falhado.

**Causa raiz (medida):** o polling de
[DraftDocumentUploader.tsx](../../frontend/src/pages/Intake/DraftDocumentUploader.tsx)
só ligava enquanto algum doc estivesse em `processing`. Mas o `/import` marca os
docs como `pending` (fila do worker), não `processing`. No instante em que o
efeito rodava, nenhum doc estava `processing` → o intervalo nunca iniciava → a
lista nunca refazia o fetch quando o worker movia `pending → processing → done`.
(A coluna lateral `PreviewPanel` faz polling perpétuo e tem shape correto — o
elo quebrado era o status/sugestões do uploader.)

**Fix:** flag `awaitingOcr` ligada ao disparar a leitura IA (quando
`docs_queued > 0`); o polling roda enquanto houver doc em estado **não-terminal**
(`pending`/`processing`), parando só quando tudo é `done`/`failed`/`not_required`.
Status `not_required` ganha pill "Armazenado" + mensagem honesta
("🗺️ Geometria armazenada — processamento em breve").

---

## Validação (real)

- **Backend** (venv + Testcontainers Postgres):
  - `tests/services/test_geo_files.py` (23), `tests/services/test_ocr_pdf_guard.py`
    (5) — detecção + guard não-PDF.
  - `tests/api/test_intake_geo_routing.py` (2) — `.kml` roteado para fora do OCR
    (`docs_skipped_geo=1`, dispatch só do PDF); draft só-geo não enfileira nada.
  - Regressão: `tests/workers tests/services tests/api/test_intake.py` → **190 passed**.
  - `ruff check` dos arquivos tocados: limpo.
- **Frontend:** `tsc --noEmit` limpo; `vite build` ok; `npm test` → **53 passed**
  (inclui regressão de polling pós-import e pill geoespacial). `eslint` limpo.
  > Nota: rodar vitest via `npm test` (não `npx vitest`) — o flag Node de
  > `require(esm)` para jsdom vive no script npm (ver `vitest.config.ts`).

**O que NÃO foi validado ao vivo:** o fluxo E2E real (browser → MinIO → worker
Celery) não foi exercitado nesta máquina; a prova é por testes de integração
(endpoint real + Postgres real) e unitários, mais `tsc/build`.

## Dívida registrada

- **D1 (geo)** — consumo real de KML/SHP: parser → `Property.geom` → overlay
  PostGIS. Destrava alertas geoespaciais (dívidas #14/#15). Frente própria.
