# Progresso 9 — Remodelar `RegulatoryIssue`: taxonomia rica + severity 4 níveis

Padrao deste arquivo:

- linguagem executiva e de historico de execucao
- foco em resultado, decisao, validacao, risco e pendencia
- evitar instrucoes operacionais detalhadas; isso pertence aos runbooks

## Projeto: Regente Ambiental
## Referencias: `PROMPT_5_remodelar_regulatory_issue.md` (efêmero — descartado pós-rodada) + skill `auditor_imovel/analise_divergencias_documentais` v1.1.0 (validada pela sócia) + `REGISTRO_DIVIDAS.md` (#3, #4, #5)

---

## Objetivo da rodada

Tirar o `RegulatoryIssue` da forma genérica (enum `type` de 5 valores, com
maioria caindo em `outro`; `severity` de 3 níveis colapsando alto+crítico) e
levar para a forma **rica** que a sócia desenhou: `familia` (enum estável ~11) +
`codigo_alerta` (catálogo evolutivo de 40+ códigos, NÃO enum) + campos
`muda_rota_regulatoria` / `muda_escopo_preco_prazo` / `documentos_cruzados` +
`severity` de 4 níveis (`informativo`/`atencao`/`alto`/`critico`).

Fecha as dívidas **#3** (remodelagem) e **#4** (mapeamento 4→3 que colapsava
alto e crítico). **Endereça #5** com proposta documentada (Onda C — não
implementa). Atualiza o auditor para emitir códigos reais (📄 documental); os
🛰️ (geoespacial) e 🔌 (consulta externa) entram no **catálogo** mas **não são
emitidos** até a infra existir.

---

## Estado pre-rodada

- `main` em `4e1d961` — PR PROMPT_4 (fechar-pipeline) + PR governanca + PR
  Upstash mergeados.
- Suite 585/585 verdes (pós-PROMPT_4 + governanca).
- `feat/ocr-automatico` ainda fantasma em origin (Andre decide).
- Skill `auditor_imovel/analise_divergencias_documentais` v1.1.0 já no repo
  (vinda da governanca documental).

---

## Sprints executados (PROMPT_5 — 25/05)

### Onda A — Remodelar o `RegulatoryIssue`

**Modelo (`app/models/regulatory.py`):**

- 3 enums novos: `RegulatoryFamilia` (11 valores estáveis),
  `RegulatoryIssueSeverity` (4 níveis — **substitui** o de 3 antigo),
  `RegulatoryAlertFactibilidade` (`documental`/`geoespacial`/`consulta_externa`,
  espelha 📄/🛰️/🔌 da skill).
- 1 model novo: `RegulatoryIssueCatalog` (PK = `codigo_alerta` string;
  factibilidade, severity_base, muda_rota_regulatoria, muda_escopo_preco_prazo,
  documentos_cruzados_default). **Catálogo evolutivo:** adicionar código
  novo é INSERT, não migration de schema.
- `RegulatoryIssue` ganha 5 colunas (`codigo_alerta` FK no catálogo,
  `familia`, `muda_rota_regulatoria`, `muda_escopo_preco_prazo`,
  `documentos_cruzados`). `severity` passa de 3 para 4 níveis. `type` legado
  fica nullable (retrocompat com registros antigos; deprecated).
- Seed em `app/models/regulatory_catalog_seed.py` — fonte única de 45
  entradas (40 da skill + 2 extensões naturais + OUTRO_GENERICO +
  VERIFICACAO_ESPACIAL_PENDENTE). Importado pela migration E pelo conftest
  (testes que usam `create_all`).

**Migration (`c1b2d3e4f5a7_prompt5_remodelar_regulatory_issue.py`):**

1. Cria 3 enums Postgres (`regulatory_familia`, `regulatory_factibilidade`,
   `regulatory_severity_v2`).
2. Cria tabela `regulatory_issue_catalog`.
3. `bulk_insert` do seed (via `seed_rows_as_dicts()` do módulo único).
4. Adiciona colunas em `regulatory_issues`. FK + 2 índices.
5. Migra dados: `severity` 3→4 (`info`→`informativo`,
   `warning`→`atencao`, `critical`→`alto`). `type` antigo → `codigo_alerta`
   + `familia` via `_TYPE_TO_CATALOG` (mapeamento best-effort).
6. Drop coluna `severity` antiga; rename `severity_new` → `severity`. Drop
   enum antigo `regulatory_issue_severity` (3 níveis).
7. `type` vira nullable (deprecated).

Downgrade reverso (best-effort — colapsa 4→3 perdendo distinção
alto-vs-crítico).

**`property_audit.py`:**

- `AuditFinding` reescrito: campos `codigo_alerta` (str) + `familia` (str)
  + `grade` (str, 4 níveis) + `muda_rota_regulatoria` + `muda_escopo_preco_prazo`
  + `documentos_cruzados`. **Saíram** `type` (genérico) e `severity` (3 níveis).
- `audit_property()` emite codigos reais por par: `AREA_MATRICULA_X_CAR`,
  `AREA_MATRICULA_X_CCIR`, `AREA_MATRICULA_X_ITR`, `AREA_CAR_X_CCIR`,
  `GEO_AUSENTE`, `RL_MATRICULA_DIVERGENTE_RL_CAR`, `VERIFICACAO_ESPACIAL_PENDENTE`.
- Removidos `_FINDING_TO_ISSUE_TYPE` e `finding_to_issue_type`
  (sem mapeamento intermediário — codigo_alerta vai direto para `RegulatoryIssue`).
- `_GRADE_TO_SEVERITY` (mapeamento 4→3) **saiu** — `grade` é o único eixo.

**`auditor_imovel.py`:**

- `_persist_issues` grava `codigo_alerta` + `familia` + `severity` (4 níveis,
  igual ao grade) + `muda_rota_regulatoria` + `muda_escopo_preco_prazo` +
  `documentos_cruzados`. `type` legado fica None em registros novos.
- Payload `findings_raw` passa de `type`/`severity` para
  `codigo_alerta`/`familia`/`grade` (taxonomia rica).
- `content` sumariza por grade (crítico/alto/atenção), não por severity.

**`diagnostico.py`:**

- `_FINDING_TYPE_TO_CATEGORIA` (PROMPT_4, 4→4) substituído por
  `_FAMILIA_TO_CATEGORIA` (PROMPT_5, 11→7). Mapeamento mais granular sem
  perder semântica.
- `_consume_auditor_findings` lê `codigo_alerta` + `familia` do payload do
  auditor (era `type` no PROMPT_4).

**Schemas (`app/schemas/regulatory.py`):**

- `RegulatoryIssueOut` ganha `codigo_alerta`, `familia`, `muda_*`,
  `documentos_cruzados`. `type` continua exposto mas nullable.

**Testes (todos verdes):**

- `tests/services/test_property_audit.py` — 52 testes, ajustados para
  `f.codigo_alerta` / `f.familia` / `f.grade`.
- `tests/agents/test_auditor_imovel.py` — 8 testes, payload com taxonomia rica.
- `tests/agents/test_diagnostico_consume_auditor.py` — 15 testes, builder
  `_finding` aceita `codigo_alerta`/`familia` (com retrocompat via `type_`
  alias).
- `tests/models/test_regulatory.py` — **20 testes**, +7 do
  `TestRegulatoryIssueCatalog` (seed inicial, factibilidade, severity 4,
  família correta por código, catálogo aceita código novo sem DDL).
- `tests/api/test_regulatory.py` — 37 testes, severity values atualizados.

### Onda B — Auditor emite a taxonomia rica

Atendida junto da Onda A (não houve separação útil — quando o
`AuditFinding` virou rico, o `_persist_issues` virou junto). Códigos
emitidos cobrem os **factíveis agora (📄)**:

| Cenário do auditor | `codigo_alerta` emitido | `familia` |
|---|---|---|
| Matrícula × CAR (área) | `AREA_MATRICULA_X_CAR` | `area` |
| Matrícula × CCIR (área) | `AREA_MATRICULA_X_CCIR` | `area` |
| Matrícula × ITR (área) | `AREA_MATRICULA_X_ITR` | `area` |
| CAR × CCIR (área) | `AREA_CAR_X_CCIR` | `area` |
| GEO INCRA ausente na matrícula | `GEO_AUSENTE` | `geo_incra` |
| RL averbada × declarada | `RL_MATRICULA_DIVERGENTE_RL_CAR` | `ambiental` |
| Sem `Property.geom` | `VERIFICACAO_ESPACIAL_PENDENTE` | `geoespacial` |

Os 🛰️ (CAR_LOCALIZACAO_DIVERGENTE_REALIDADE, GEO_SOBREPOSICAO_TERCEIRO,
APP_OMITIDA, etc.) e 🔌 (EMBARGO_NAO_INFORMADO, AUTO_INFRACAO_PASSIVO,
LICENCA_OUTORGA_AUSENTE_VENCIDA) **estão no catálogo** (vocabulário
canônico) mas **não são emitidos** até a infra existir (D1 para 🛰️,
integrações externas para 🔌). Conforme regra explícita do PROMPT_5.

### Onda C — Reconciliação dos 3 status (PROPOSTA)

`docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md` — proposta com 3 opções
de modelagem (A: três campos ortogonais; B: campo único com state machine;
C: dois campos + saneamento derivado). Recomendação técnica: **Opção A**.
Razões: preserva vocabulário da sócia (3 dimensões reais), compatível com
desenho atual (3 PRs incrementais), auditoria simples (1 AuditLog por
campo), migração trivial. **NÃO implementada — aguarda decisão do Andre +
validação da sócia.**

---

## Resumo numerico

| Dimensao | Quantidade |
|----------|------------|
| Worktree isolado | 1 (`impl-prompt5`) |
| Commits novos | a definir no final do push |
| Migrations novas | 1 (`c1b2d3e4f5a7`) |
| Códigos no catálogo | 45 entradas iniciais (40 da skill + 2 extensões + OUTRO_GENERICO + VERIFICACAO_ESPACIAL_PENDENTE + …) |
| Enums Postgres novos | 3 (`regulatory_familia`, `regulatory_factibilidade`, `regulatory_severity_v2`) |
| Enums Postgres dropados | 1 (`regulatory_issue_severity` — 3 níveis antigo) |
| Testes alterados | 4 arquivos (test_property_audit, test_auditor_imovel, test_diagnostico_consume_auditor, test_regulatory model+API) |
| Testes novos no `TestRegulatoryIssueCatalog` | 7 (seed básico, total ≥40, factibilidade, severity 4, família por código, documentos_cruzados_default lista, evolutivo aceita INSERT) |

---

## Decisoes arquiteturais

### Catálogo evolutivo (não enum)

`codigo_alerta` é `String(80)` FK em `regulatory_issue_catalog` (PK natural
= o próprio código). Adicionar código novo é `INSERT` — sem migration de
schema. Único source-of-truth do seed é
`app/models/regulatory_catalog_seed.py` (importado pela migration E pelo
conftest). Garante que o catálogo cresce no tempo do produto (cada novo
caso de divergência identificado pela sócia / consultores) sem ciclo de
deploy.

### 11 famílias estáveis (enum)

Famílias mudam raramente (acréscimo de família é decisão arquitetural,
não operacional) — logo enum é adequado. As 11 espelham diretamente a
skill auditor v1.1.0.

### Severity 4 níveis (não 3)

Foi a dívida #4. A sócia distinguiu **alto** de **crítico** de propósito:
**só `critico` dispara o mecanismo de decisão obrigatória do consultor**
(camada 2 do Princípio 1 — 5 botões da P4). Mantendo 3 níveis,
`alto+crítico` colapsava em `critical` e perdia o gatilho. Agora os 4
níveis vivem ponta a ponta: do `AuditFinding.grade` (auditor)
→ `RegulatoryIssue.severity` (persistência) → `Risco.grau` (payload do
Diagnóstico).

### `type` legado fica nullable, não dropado

Decisão consciente para preservar leitura de registros antigos sem perder
dados. Novos registros têm `type=None` + `codigo_alerta` preenchido. A
migration de dados converteu os 5 valores antigos para 5 códigos novos
best-effort (`area_divergente` → `AREA_MATRICULA_X_CAR`, etc.). Dropar
`type` em sprint posterior depois de zero queries usando ele.

### `_GRADE_TO_SEVERITY` removido

Mapa 4→3 que colapsava alto+crítico saiu junto do severity 3-níveis.
`AuditFinding.grade` e `RegulatoryIssue.severity` agora são o mesmo eixo
(4 níveis com nomes idênticos). Diagnóstico continua mapeando para
`Risco.grau` via `_GRADE_TO_GRAU` (4→4 com renomeação de `critico` →
`critico_impeditivo_potencial` no schema Pydantic da skill diagnostico —
preservado).

### Onda C foi só proposta

PROMPT_5 explicitamente proibiu implementar a reconciliação de status.
Razão: depende de validação da sócia + decisão do Andre sobre a obrigação
de `decisao_consultor` em alertas críticos. Documento de proposta é Opção
A (3 campos ortogonais).

---

## Principais arquivos criados/modificados

### Backend

- `app/models/regulatory.py` — enums novos + `RegulatoryIssueCatalog` + RegulatoryIssue extendido
- `app/models/regulatory_catalog_seed.py` (**novo**) — fonte única do seed do catálogo
- `app/models/__init__.py` — re-export
- `app/schemas/regulatory.py` — `RegulatoryIssueOut` com taxonomia rica
- `app/services/property_audit.py` — AuditFinding rico; codigo_alerta por par
- `app/agents/auditor_imovel.py` — persiste taxonomia rica; payload novo
- `app/agents/diagnostico.py` — consumo lê `familia`/`codigo_alerta`

### Migration

- `alembic/versions/c1b2d3e4f5a7_prompt5_remodelar_regulatory_issue.py` (**novo**)

### Documentação

- `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md` (**novo**) — Onda C proposta

### Testes

- `tests/conftest.py` — seed do catálogo no `db_engine` fixture (one-shot por session)
- `tests/services/test_property_audit.py` — 52 testes ajustados
- `tests/agents/test_auditor_imovel.py` — 8 testes ajustados
- `tests/agents/test_diagnostico_consume_auditor.py` — 15 testes ajustados (builder `_finding` com retrocompat)
- `tests/models/test_regulatory.py` — 20 testes (+ 7 novos do catalog)
- `tests/api/test_regulatory.py` — 37 testes (severity values trocados)

---

## Dividas e pendencias

### Fechadas nesta rodada

- **#3** — Remodelagem do `RegulatoryIssue` (família + codigo_alerta +
  campos novos + 4 níveis em severity). Fechada inteira.
- **#4** — Mapeamento 4→3 que colapsava alto e crítico. `_GRADE_TO_SEVERITY`
  removido; severity é 4 níveis em persistência. Fechada inteira.

### Endereçadas (proposta, não implementação)

- **#5** — Reconciliação dos 3 status. Proposta em
  `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md`; aguarda decisão.

### Em aberto

- **Camada 2 do Princípio 1** (5 botões P4) — depende de #5 aprovada.
- **Conjunto canônico de documentos esperados** (`DOCUMENTO_AUSENTE`) — #6.
- **Marcador de aplicação de citação** no Legislação — #7.
- **Tool determinística de uso do solo** — #8.
- **`except Exception` genérico em `pdf_generator.py:234`** — #9.
- **Varredura de testes sem mock de storage externo** — #10.
- **Race no `MAX(version)+1`** — #11 (retry server-side opcional).
- **R1 polish dos 8 contratos externos** — #13.
- **Alertas geoespaciais** (depende de `Property.geom` — D1) — #14, #15.
- **Loop de aprendizado com consultores** — ADR-010, #16.
- **`feat/ocr-automatico` fantasma remoto** — Andre decide.

---

## Estado da base apos esta rodada

- `feat/prompt5-remodelar-regulatory-issue` aguardando merge (PR a abrir).
- 11 agentes registrados; `auditor_imovel` ativo na chain com **taxonomia
  rica** (codigos reais 📄).
- `regulatory_issue_catalog` com 45 códigos canônicos (40 da skill + extensões).
- `RegulatoryIssue.severity` em 4 níveis ponta a ponta.
- Pipeline ponta a ponta: `extrator → auditor_imovel → legislacao →
  diagnostico → POST /diagnoses (versionado + gate Pydantic) → PATCH
  /validate (consultor assina + AuditLog)`.

---

## Aprendizados (memoria de feedback do Andre — a salvar)

Nada surpreendente além do que o PROMPT_5 já antecipava: catálogo
evolutivo via INSERT é a abordagem certa quando a taxonomia cresce no
tempo do produto; severity 4 níveis preserva a granularidade que a sócia
afiou; manter `type` nullable é menos invasivo que dropar.

Relacionado: [[prompt4-fechar-pipeline-2026-05-25]],
[[pos-fase2-ondas-abc-2026-05-24]], [[phase2-skill-diagnostico-2026-05-23]].
