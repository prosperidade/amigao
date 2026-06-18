# Histórico de eventos do caso — humanizar + fonte

> A tela "Histórico de eventos do caso" (rodapé de `/processes/{id}`) mostrava
> **JSON cru** ao consultor. Esta correção transforma cada evento em uma frase
> em PT-BR e liga o evento ao **documento de origem** do dado decidido.

- **Branch:** `fix/historico-eventos-humanizado`
- **Escopo restrito:** APENAS o histórico de eventos. Nenhuma outra tela.

## Antes × depois (process 13 real)

**Antes** — o `details` do AuditLog ia cru pra tela:

```json
{"field_id": 401, "acao": "aceitar", "status": "aceito",
 "target_entity": "matricula", "target_field": "geo_certificacao_codigo",
 "matricula_hint": "4655", "fonte": null, "irmaos_rejeitados": [],
 "staging_origin_ai_job_id": 87}
```

**Depois** — frase humana, com ícone/cor por tipo e o documento de origem:

| Evento (cru) | Frase renderizada |
|---|---|
| `staging_decidir` aceitar `geo_certificacao_codigo` hint 4655 | **Código de certificação SIGEF da matrícula 4655 aceito.** |
| `staging_decidir` rejeitar `denominacao_imovel` hint 2923 | **Denominação do imóvel da matrícula 2923 rejeitada.** |
| `staging_decidir` escolher_fonte `denominacao_imovel` hint 6776 | **Denominação do imóvel da matrícula 6776: escolhida uma fonte entre as divergentes.** |
| `staging_aceitar_consistentes` count 6 | **6 campos consistentes aceitos de uma vez.** |
| `consolidar` 7 gravados / 2 matrículas | **7 campos gravados na base do imóvel.** · _2 matrículas criadas_ |
| `notification_process_status_changed` `{old,new}` | **Status do caso: Lead → Triagem** |

Zero JSON, zero `target_field`/`field_id`/`ai_job_id`, zero `[object Object]`.

## Item 1 — Humanizar

- Novo módulo **`frontend/src/pages/Processes/historicoEventos.ts`** (`describeEvento`):
  converte cada `AuditLog` numa frase PT-BR. Cobre todos os tipos presentes no
  caso real (`staging_decidir` × aceitar/rejeitar/escolher_fonte/editar,
  `staging_aceitar_consistentes`, `consolidar`, `status_changed`,
  `macroetapa_changed`, `notification_process_status_changed`, `created`,
  `demand_type_classified`, `ai_summary_generated`) + um **fallback genérico
  seguro** que nunca imprime JSON cru.
- Rótulos de campo vêm do **módulo central** `lib/labels/fieldLabels.ts`
  (`labelFor`), **estendido** com os `target_field` de destino do staging
  (Cliente/Imóvel/Matrícula) — ex.: `geo_certificacao_codigo → "Código de
  certificação SIGEF"`, `denominacao_imovel → "Denominação do imóvel"`. Vira
  base para humanizar outras telas depois (fora deste PR).
- Concordância de gênero do particípio (`aceito/aceita`, `rejeitado/rejeitada`)
  via um conjunto de campos femininos no módulo do histórico.
- Ícone + cor por tipo de ação, reusando o padrão de tons da severidade
  (emerald positivo, red negativo, violet escolha, indigo status, slate neutro).
- `TimelineTab.tsx` reescrito para renderizar as frases (sem mais
  `log.details ?? log.action`).

## Item 2 — Fonte (causa medida + tratamento)

**Causa medida (no código).** O `fonte: null` vinha de
`app/services/staging_consolidation.py::decide_field`, que grava no audit o
parâmetro `body.fonte` — a fonte **opcional** do `escolher_fonte`. Para
`aceitar`/`rejeitar`/lote esse parâmetro nunca é passado → sempre `null`. Ou
seja, `fonte` no audit é a *fonte da decisão* (que é do humano), não a fonte do
dado — exibi-la como "fonte: null" é enganoso.

**A fonte real existe e estava ignorada.** `ExtractedFieldStaging` tem
**`document_id`** — o documento de onde o campo foi extraído. Esse é o vínculo
de rastreabilidade verdadeiro.

**Tratamento.** O endpoint `GET /processes/{id}/timeline`
(`_enrich_timeline_origin`) resolve, no **read-time**, `field_id →
ExtractedFieldStaging.document_id → Document.original_file_name` e entrega
`origin_document` em cada evento de decisão. Read-time (não reescrita do audit)
para que eventos **já gravados** (process 13) também ganhem a origem. A UI
mostra **"Origem do dado: <documento>"** e **nunca** exibe "fonte: null". Quando
não há documento resolvível, o campo é omitido — não se inventa fonte.

## Arquivos

- Backend: `app/schemas/audit_log.py` (+`origin_document`),
  `app/api/v1/processes.py` (`_enrich_timeline_origin` + endpoint).
- Frontend: `lib/labels/fieldLabels.ts` (estendido), `historicoEventos.ts`
  (novo), `TimelineTab.tsx` (reescrito).
- Testes: `tests/api/test_processes.py` (enriquecimento da origem),
  `frontend/.../historicoEventos.test.ts` (11 casos — zero JSON/termo técnico).

## Validação

- `historicoEventos.test.ts`: 11 casos com os shapes reais do process 13;
  assert de ausência de termos técnicos (`target_field`, `field_id`, `fonte:`,
  `{`, `[object Object]`, snake_case) em toda saída.
- Backend: `test_timeline_enriches_staging_decision_with_origin_document` +
  regressão do timeline.
- `npm test` 64 verdes; `tsc --noEmit` + `npm run build` verdes.
