# Ficha 01 / FASE 4 — Decisão do consultor + Consolidação (fecho do ciclo)

**Branch:** `feat/ficha01-fase4-decisao-consolidacao` (base `main`, requer Fases 1-3)
**Data:** 2026-06-05
**Espec:** Ficha 01 §8
**Relacionada a:** ADR-015, Fases 1 (#60), 2 (#61), 3 (#62)

Fecha o ciclo da Ficha 01: o CONSULTOR decide campo a campo (ou em lote) sobre o
staging e a CONSOLIDAÇÃO **determinística** grava na base real. Princípio:
"agentes propõem (staging), consultor decide (Alertas), sistema grava (base)".
Nada é gravado sem decisão explícita — **sem LLM** em ponto algum.

## Backend

**Decisão por campo** — `POST /processes/{id}/staging-fields/{field_id}/decidir`
`{acao, valor?, fonte?}`:
- `aceitar` — usa o valor da fonte. **Gate:** proibido em `divergente_transcricao`
  (→ 422; exige escolha ativa). `divergente_fundo` é aceito como ACHADO (issue/
  escopo já roteado pela matriz) sem gravação automática de valor.
- `escolher_fonte` — aceita este campo e **rejeita os irmãos** (mesmo
  target_field/matrícula) das outras fontes.
- `editar` — grava `valor` (obrigatório → 422 se ausente) como override manual.
- `rejeitar` — descarta (fora da consolidação).
Marca `status`, `decided_value`, `decided_by_user_id`, `decided_at`. Auditável.

**Lote** — `POST /processes/{id}/staging-fields/aceitar-consistentes`: aceita
TODOS os `consistente`. Divergentes nunca entram (gate por campo).

**Consolidação** — `POST /processes/{id}/consolidar` (serviço
`app/services/staging_consolidation.py`, determinístico, idempotente):
- pega `status=aceito` (com `decided_value` ou valor único) e grava:
  `cliente`→`Client`, `imovel`→`Property`, `matricula`→**upsert** `Matricula` por
  `matricula_hint` (cria se não existir; atualiza se existir).
- **allowlist** de colunas por entidade + alias (`document`→`cpf_cnpj`); campos
  sem coluna correspondente são ignorados (reportados em `ignorados`).
- **`Property.total_area_ha` NÃO é sobrescrito** (área = derivada,
  `area_total_matriculas()`). `field_sources[col]="human_validated"`.
- Auditoria (`AuditLog`) de cada gravação: staging_id, ai_job_id, decided_by.

## Frontend

`ConsolidacaoPanel` (estende a aba **Alertas**, fluxo de issues inalterado): lista
agrupada por entidade (Cliente / Imóvel / Matrícula N), cada campo com nome
humanizado (`labelFor`), valor por fonte, status colorido e ações **Aceitar ·
Escolher fonte · Editar · Rejeitar**; banner "Aceitar todos os consistentes (N)";
botão "Consolidar na base" (desabilita enquanto há divergências de transcrição
pendentes) + resumo pós-consolidação. Rótulos PT-BR, sem `[object Object]`.

## Validação real (ciclo completo, caso São Jorge — rodando)

Staging semeado no processo 30 (property 11, client 21) e marcado pela Fase 3
(auditor): áreas `consistente`; denominações + CAR `divergente_transcricao`.

1. `aceitar-consistentes` → **2 aceitos** (áreas das matrículas).
2. **GATE** `aceitar` no CAR divergente (total_area_ha) → **HTTP 422**.
3. `escolher_fonte` na denominação 4.698 → aceito ("Fazenda São Jorge"), irmão rejeitado.
4. `aceitar` os pendentes (cartório, RL, car_code, nome do cliente).
5. **`consolidar`** → `campos_gravados=7`, `matriculas_criadas=2`,
   `cliente_atualizado=true`, `imovel_atualizado=true`,
   **`area_total_matriculas=1010.5583`**.

Base real conferida:
- `Matricula 4.698` (area_ha 660,6561 · cartório CRI Uirapuru · denominação
  "Fazenda São Jorge" · averbação RL "132,00 ha averbada") e `6.776` (349,9022).
- `Property.car_code` gravado; **`total_area_ha` = 250 (pré-existente, NÃO
  sobrescrito)**. `Client.full_name` = "Luiz Augusto da Silva".
- **Idempotência:** re-consolidar → `matriculas_criadas=0`,
  `matriculas_atualizadas=2`, contagem segue **2** (sem duplicação).
- **Auditoria:** `consolidar` ×2, `staging_decidir` ×5, `staging_aceitar_consistentes` ×1.

## Testes

`tests/api/test_fase4_consolidacao.py` — 3 testes (TestClient):
- ciclo completo (lote → gate 422 → escolher_fonte → consolidar → matrículas na
  base + soma → idempotência);
- `editar` (422 sem valor; grava `decided_value`; consolida com override);
- `rejeitar` não grava.

## Governança

`FLUXOS_E2E.md` ganhou o fluxo staging → decisão → consolidação. Sem ADR novo (o
desenho segue as Fichas; o catálogo `MatrixSituacao`/`ExtractedFieldStatus` já
existia).

## Não nesta fase (PROIBIDO — respeitado)

Gravar sem decisão do consultor; LLM na decisão/consolidação; sobrescrever
`Property.total_area_ha`; quebrar o fluxo de alertas/issues do auditor.

## Arquivos

- `app/services/staging_consolidation.py` (novo)
- `app/api/v1/processes.py` (3 endpoints)
- `app/schemas/extracted_field_staging.py` (schemas de decisão/consolidação)
- `frontend/src/pages/Processes/ConsolidacaoPanel.tsx` (novo) + `AlertasTab.tsx`
- `tests/api/test_fase4_consolidacao.py`
- Governança: `FLUXOS_E2E.md`, ESTADO_ATUAL, MEMORIA_CHAT.
