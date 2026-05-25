# Progresso 8 — Fechar o pipeline: Diagnóstico consome o auditor + assinatura humana

Padrao deste arquivo:

- linguagem executiva e de historico de execucao
- foco em resultado, decisao, validacao, risco e pendencia
- evitar instrucoes operacionais detalhadas; isso pertence aos runbooks

## Projeto: Regente Ambiental
## Referencias: `PROMPT_4_fechar_pipeline.md` (efêmero, descartado pós-rodada) + `REGISTRO_DIVIDAS.md` (dívidas #1, #2, #12)

---

## Objetivo da rodada

Fechar os **2 elos abertos** que sobraram da Onda B+C (`progresso7`): (1) o Diagnóstico
não lia os findings do auditor; (2) o consultor não tinha endpoint para **assinar** o
diagnóstico. Esta rodada fecha os dois, mantendo escopo limitado à **camada 1** do
Princípio 1 (o consultor assina o diagnóstico como um todo). A **camada 2** (5 botões da
P4 — decisão por alerta crítico) **NÃO** entra: depende da remodelagem do `RegulatoryIssue`
que aguarda a sócia validar a skill `auditor_imovel/analise_divergencias_documentais`.

---

## Estado pre-rodada

- `main` em `cc553cd` (progresso7 + Fase 2 + Ondas A/B/C, pushado em 24/05).
- Suite 562/562 verdes.
- PR `chore/reduce-redis-polling` (Upstash) mergeado durante a rodada (PR #2 → `bc98c93`).
- Worktree dedicado: `feat/prompt4-fechar-pipeline` em `impl-prompt4`, baseado em `main`.

---

## Sprints executados (PROMPT_4 — 25/05)

### Onda A — DiagnosticoAgent consome `chain_data["auditor_imovel"]`

**Commit** `f93b4b4` — 4 arquivos, +671/-8 linhas.

3 mudanças cirúrgicas:

1. **`app/services/property_audit.py`** — todos os `AuditFinding` agora carregam `grade`
   explicitamente. `geo_incra_ausente` → `GRADE_CRITICO`; `rl_divergente` → calculado
   pela mesma régua de 4 faixas do `area_divergente`; `verificacao_espacial_pendente` →
   `GRADE_INFORMATIVO`. (`area_divergente` já preenchia desde Onda C.)
2. **`app/agents/auditor_imovel.py`** — `findings_raw` no payload passa a emitir `grade`.
   Antes omitia — o consumidor não conseguia preservar 4 níveis sem isso.
3. **`app/agents/diagnostico.py`** — novo `_consume_auditor_findings()` que lê
   `chain_data["auditor_imovel"]["findings_raw"]` e produz `Divergencia` (matriz de
   cruzamento) + `Risco` com `grau` preservado.
   - Mapeamento explícito `_GRADE_TO_GRAU` (4→4): `critico` → `critico_impeditivo_potencial`
     (NÃO colapsa em "alto" — dívida #4 endereçada).
   - Mapeamento `_FINDING_TYPE_TO_CATEGORIA`: area→cadastral_sistemico, rl→ambiental,
     geo→fundiario, espacial→geoespacial.
   - `_derive_nivel_risco_geral()` calcula `NivelRiscoGeral` (4 níveis) pelo "pior" grau.
   - Riscos do auditor vêm **antes** do risco do LLM no array (primeiro movimento).
   - Path rules-based também consome (auditor é fonte independente do LLM).
   - 15 testes novos em `tests/agents/test_diagnostico_consume_auditor.py`.

### Onda B — Assinatura humana do `RegulatoryDiagnosis` (camada 1 do Princípio 1)

**Commit** `c74ff2e` — 2 arquivos, +260/-8 linhas.

- `PATCH /api/v1/processes/{process_id}/diagnoses/{version}/validate` em
  `app/api/v1/regulatory.py`.
- Grava `validated_by_user_id = current_user.id` + `validated_at = now(UTC)`
  (campos **já existiam** no model desde a migration A1 `a8e1d4c7f3b6`).
- `AuditLog(entity_type="regulatory_diagnosis", action="validated")` com hash chain
  SHA-256 via `stamp_audit_hash` (Princípio 2 — quem assinou, quando, qual versão).
- **409 Conflict** ao revalidar (idempotência explícita: evita sobrescrita silenciosa
  do assinante original).
- 8 testes novos em `TestValidateDiagnosis` (auth, 404 processo/versão, gravação,
  AuditLog com hash 64-hex, conflito, tenant isolation, versões independentes).

### Item rápido (`PROJECT_NAME`) — JÁ RESOLVIDO

`PROJECT_NAME = "Regente Ambiental"` já estava em `app/core/config.py:52` desde a Fase 0
(commit `7877652`). Confirmado por grep. Nada a fazer — anotado.

---

## Resumo numerico

| Dimensao | Quantidade |
|----------|------------|
| Worktrees isolados criados nesta rodada | 1 (`impl-prompt4`) |
| Commits novos | 2 (`f93b4b4`, `c74ff2e`) |
| Testes novos | +23 (15 consume_auditor + 8 TestValidateDiagnosis) |
| Suite total | **585 passed, 0 failed** (vs 562 em main) |
| Endpoints novos | 1 (`PATCH /processes/{id}/diagnoses/{version}/validate`) |
| Migrations novas | 0 (campos já existiam) |

---

## Decisoes arquiteturais

### `_GRADE_TO_GRAU` (4 → 4) preserva alto vs. crítico

O `RegulatoryIssue` ainda usa `severity` de 3 níveis (info/warning/critical) — a
remodelagem para 4 níveis é a próxima rodada (PROMPT_5). Enquanto isso, o **payload do
Diagnóstico** (JSONB livre) carrega o `grau` de 4 níveis no `Risco.grau`, preservando a
distinção que a sócia afiou: só `critico_impeditivo_potencial` dispara o mecanismo de
decisão obrigatória do consultor (camada 2, sprint posterior).

### Categoria inferida por `finding.type` — mínimo, refinará depois

Mapeamento simples: area→`cadastral_sistemico`, rl→`ambiental`, geo→`fundiario`,
espacial→`geoespacial`. É suficiente para a próxima sprint começar com dado real; a
remodelagem do `RegulatoryIssue` (família + codigo_alerta) afina a inferência.

### Não duplicação: auditor é fonte única do cruzamento

O `DiagnosticoAgent` **não calcula** divergência de área por conta própria. Mesmo que o
LLM "alucine" texto sobre divergência (`situacao_geral`), isso passa pelos campos de
texto livre — não vira `Divergencia` automática. Teste explícito em `TestSemDuplicacao`.

### `Risco.evidencia` recebe JSON serializado determinístico

`json.dumps(evidencia_dict, sort_keys=True)` — preserva o detalhe do cruzamento
(Princípio 2) e fica auditável sem perder informação. `sort_keys` garante string
determinística (mesma evidência sempre vira a mesma string).

### 409 Conflict ao revalidar (não 200 idempotente)

Decisão consciente: revalidar é conflito, não no-op silencioso. Se outro consultor já
assinou, o segundo recebe 409 com o `validated_at` original. Se a sprint seguinte quiser
permitir "revalidação" (raro), exigir endpoint distinto (`/revalidate`) com flag
explícita.

### `PropertyMock` para mockar `@property` em pydantic Settings

`patch("app.core.config.Settings.ai_configured", new_callable=PropertyMock,
return_value=False)`. Pydantic blinda atributos; patch direto em `.ai_configured` dá
`AttributeError`. Padrão registrado em
[`memory/project_prompt4_fechar_pipeline_2026-05-25.md`](../../../../.claude/projects/...)
para reuso.

---

## Principais arquivos criados/modificados

### Backend
- `app/services/property_audit.py` — todos `AuditFinding` carregam `grade` (geo→crítico, rl→régua, espacial→informativo)
- `app/agents/auditor_imovel.py` — `findings_raw` no payload inclui `grade`
- `app/agents/diagnostico.py` — `_consume_auditor_findings()` + `_derive_nivel_risco_geral()` + mapeamentos `_GRADE_TO_GRAU` (4→4) e `_FINDING_TYPE_TO_CATEGORIA`
- `app/api/v1/regulatory.py` — endpoint `PATCH /validate` + AuditLog hash chain

### Testes (2 arquivos)
- `tests/agents/test_diagnostico_consume_auditor.py` (novo) — 15 testes
- `tests/api/test_regulatory.py` — adicionado `TestValidateDiagnosis` (8 testes)

---

## Dividas e pendencias

### Fechadas nesta rodada

- **#1** — Diagnóstico consome `chain_data["auditor_imovel"]` (Onda A).
- **#2** — Assinatura humana do `RegulatoryDiagnosis` (Onda B, camada 1 do Princípio 1).
- **#4 (parcial)** — alto vs. crítico preservados ponta a ponta no nível do **payload**.
  A persistência em `RegulatoryIssue` ainda colapsa via `_GRADE_TO_SEVERITY` (será removida
  no PROMPT_5 quando `RegulatoryIssue.severity` virar 4 níveis).
- **#12** — `PROJECT_NAME` (já estava fechada desde Fase 0; confirmado).

### Em aberto (cobertas pelo PROMPT_5)

- **#3** — Remodelar `RegulatoryIssue`: `familia` (enum estável ~11) +
  `codigo_alerta` (catálogo evolutivo, NÃO enum) + campos novos + `severity` 4 níveis.
- **#4 (completo)** — sai o `_GRADE_TO_SEVERITY` que colapsa alto+crítico.
- **#5 (proposta, não implementação)** — reconciliar `status_saneamento` × `status` do
  auditor × `decisao_consultor` (5 ações P4).

### Em aberto (pós-PROMPT_5)

- **Camada 2 do Princípio 1** (5 botões P4) — depende da reconciliação de status (#5).
- **Conjunto canônico de documentos esperados** (`DOCUMENTO_AUSENTE`) — dívida #6.
- **Marcador de aplicação de citação** no Legislação — dívida #7.
- **Tool determinística de uso do solo** — dívida #8.
- **`except Exception` genérico em `pdf_generator.py:234`** — dívida #9.
- **Varredura de testes sem mock de storage externo** — dívida #10.
- **Race no `MAX(version)+1`** (retry server-side opcional) — dívida #11.
- **R1 polish dos 8 contratos externos** (headers `X-Amigao-*` + crawlers User-Agent) —
  dívida #13.
- **Alertas geoespaciais** (depende de `Property.geom` — D1) — dívidas #14 e #15.
- **Loop de aprendizado com material dos consultores** — ADR-010, dívida #16.
- **`feat/ocr-automatico` remoto fantasma** — Andre decide apagar via `git push origin
  --delete`.

---

## Estado da base apos esta rodada

- `main` em `cc553cd` (não mergeado ainda; PR `feat/prompt4-fechar-pipeline` aberto).
- 11 agentes registrados ativos (10 antigos + `auditor_imovel`).
- 4 dependências da skill diagnóstico **vivas** (A2 + A3 + A4 + K3).
- **Pipeline ponta-a-ponta no nível de código** finalizado:
  `extrator → auditor_imovel → legislacao → diagnostico → POST /diagnoses (versionado +
  gate Pydantic) → PATCH /validate (consultor assina + AuditLog hash chain)`.
- UI do consultor-assina depende do frontend consumir o `PATCH` novo (escopo de outra
  rodada).
- Suite **585/585 verde**, 0 falhas.

---

## Aprendizados (memoria de feedback do Andre)

| Memoria | Resumo da regra |
|---|---|
| [[prompt4-fechar-pipeline-2026-05-25]] | Estado pos-PROMPT_4: o que mudou, decisões 409-vs-200 e `PropertyMock`, dívidas fechadas/abertas. |

(Nada surpreendente fora do registro acima — o PROMPT_4 era nítido em escopo. As decisões
mais interessantes foram técnicas de teste e a postura idempotência-vs-conflito.)
