# Ficha 01 / FASE 1 — entidade Matrícula + staging (fundação)

**Branch:** `feat/ficha01-fase1-matricula-staging` (base `main` @ 798257a)
**Data:** 2026-06-04
**Espec:** Ficha 01 — Dicionário de Extração do Intake (FECHADA pela dupla fundadora)
**ADR:** ADR-015

Esta FASE 1 instala **só o schema**. Comportamento de extrator/auditor/intake
NÃO muda (fases 2-4). Princípio: "agentes propõem (staging), consultor decide
(Alertas), sistema grava (base)".

## Decisões da Ficha → schema implementado

### 1. Entidade `Matricula` (`matriculas`) — 1 Imóvel : N Matrículas
CAR/município/nome ficam no `Property`; o que é da matrícula fica aqui (seções
5.4-5.7 da Ficha):

| Campo | Tipo | Nota |
|---|---|---|
| `property_id` (FK CASCADE), `tenant_id` (FK RESTRICT) | int | filha do imóvel |
| `numero_matricula` | str (index) | |
| `cartorio`, `registro_livro_folha_ficha` | str | |
| `codigo_incra_sncr`, `nirf_cib` | str | cadastros rurais |
| `area_ha` | float | área decidida/consolidada da matrícula |
| `denominacao_imovel` | str | |
| `geo_certificacao_codigo`, `geo_certificacao_status` | str | SIGEF |
| `averbacao_app`, `averbacao_rl`, `onus_gravames` | text | texto livre nesta fase |
| `proprietarios` | JSON | `[{nome, cpf}]` — cruzamento c/ Cliente é da fase 3 |
| `created_at`/`updated_at` | ts | |

Índices: `(tenant_id, property_id)` composto + `numero_matricula`.

### 2. Tabela `ExtractedFieldStaging` (`extracted_field_staging`)
Campos extraídos em staging — agentes propõem, consultor decide.

- `tenant_id` (RESTRICT), `process_id` (CASCADE, nullable), `document_id` (SET NULL)
- `source_doc_type` (rg_cpf/endereco/car/ccir/matricula/itr/sigef/outro)
- `field_name`, `field_value` (JSON: valor + unidade), `confidence` (high/medium/low)
- `target_entity` (cliente/imovel/matricula), `target_field`, `matricula_hint`
- `status` — **enum `extractedfieldstatus`**: pendente | consistente |
  divergente_transcricao | divergente_fundo | aceito | rejeitado
- `decided_value`, `decided_by_user_id` (SET NULL), `decided_at` — decisão (fase 4)
- `created_by_agent` (extrator/auditor), `ai_job_id` (SET NULL) — rastreabilidade
- Índice composto `(tenant_id, process_id, status)`.

### 3. `Property` — relationship + soma derivada
- `matriculas` (1:N, `cascade="all, delete-orphan"`, `passive_deletes=True`).
- `area_total_matriculas()` → SOMA de `area_ha` (None=0), arredondada a 4 casas.
- `total_area_ha` **mantido** (compatibilidade) — transição completa é fase posterior.

### Campo extraído ≠ derivado
Extraído carrega confiança + status de validação (`ExtractedFieldStaging`);
derivado carrega rastreabilidade (`created_by_agent` + `ai_job_id`).

## Migration

`alembic/versions/a1f2c3d4e5f6_ficha01_fase1_matricula_staging.py`
(down_revision `pr21_wa_provider`). Cria o enum `extractedfieldstatus`
explicitamente (`checkfirst`) + as 2 tabelas + índices. Downgrade dropa as
tabelas e o enum. Padrões do CI respeitados (enum novo criado/dropado
explicitamente; sem `ALTER TYPE ADD VALUE`).

## Validação (rodando)

- **Migration up→down→up limpos** no Postgres de dev:
  - upgrade: tabelas `matriculas` + `extracted_field_staging` criadas, enum com 6 valores;
  - downgrade -1: ambas as tabelas somem, enum sai do catálogo (`count=0`);
  - upgrade: recriadas; `alembic current` = `a1f2c3d4e5f6 (head)`.
- **Soma derivada (caso real da Ficha):** matrículas **4.698** (660,6561 ha) +
  **6.776** (349,9022 ha) → `area_total_matriculas()` = **1.010,5583** (ORM e via API).
- **Endpoints respondendo** (tenant 2, imóvel 11):
  - `GET /properties/11/matriculas` → 200 `[]` → após 2 POSTs → 200 com 2 itens;
  - `POST /properties/11/matriculas` → 201 (`property_id`/`tenant_id` do path+JWT);
  - `GET /processes/30/staging-fields` → 200; `?status=pendente` → 200;
    `?status=xpto` → **422**; processo/imóvel inexistente → **404**; sem auth → **401**.
- **Testes:** `tests/api/test_matricula_staging.py` — 10 testes (model+soma, repos
  com escopo por tenant, endpoints incl. seed das 2 matrículas reais e a soma).
- **Suite completa** verde; **ruff** limpo nos arquivos tocados.

## Status

FASE 1 concluída — só schema. Nada do comportamento atual regrediu. Próximas
fases (NÃO neste PR): fase 2 (extrator escreve no staging + migração de dados),
fase 3 (reconciliação multi-fonte do auditor), fase 4 (tela de Alertas/consolidação).

## Arquivos

- `app/models/matricula.py`, `app/models/extracted_field_staging.py` (novos)
- `app/models/property.py` (relationship + `area_total_matriculas()`)
- `app/models/__init__.py` (registro)
- `app/repositories/matricula_repo.py`, `app/repositories/staging_repo.py` (+ `__init__`)
- `app/schemas/matricula.py`, `app/schemas/extracted_field_staging.py`
- `app/api/v1/properties.py` (GET/POST matrículas), `app/api/v1/processes.py` (GET staging-fields)
- `alembic/versions/a1f2c3d4e5f6_ficha01_fase1_matricula_staging.py`
- `tests/api/test_matricula_staging.py`
- Governança: ADR-015, `MODELO_DE_DADOS.md`, `ESTADO_ATUAL.md`, `MEMORIA_CHAT.md`
