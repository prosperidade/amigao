# Progresso 10 — Camada 2 do Princípio 1: reconciliação dos 3 status + 5 botões P4

Padrao deste arquivo:

- linguagem executiva e de historico de execucao
- foco em resultado, decisao, validacao, risco e pendencia
- evitar instrucoes operacionais detalhadas; isso pertence aos runbooks

## Projeto: Regente Ambiental
## Referencias: proposta `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md` (Opção A) + skill `auditor_imovel/analise_divergencias_documentais` v1.1.0 + PROMPT_4 PATCH `/validate` (camada 1 do Princípio 1) + `REGISTRO_DIVIDAS.md` (#5)

---

## Objetivo da rodada

Implementar a **Opção A** da reconciliação de status (proposta na Onda C do
PROMPT_5) e materializar a **camada 2 do Princípio 1**: o consultor decide
alerta por alerta sobre cada `RegulatoryIssue` crítico (os 5 botões da P4)
antes que o `PATCH /validate` aceite a assinatura do diagnóstico.

Fecha a dívida **#5**. A rodada foi disparada pela aprovação do Andre da
Opção A (3 campos ortogonais) — **não havia arquivo `PROMPT_6_*.md`** na raiz;
o escopo veio do RECONCILIACAO_STATUS_ALERTAS.md + confirmação interativa.

---

## Estado pre-rodada

- `main` em `3c8ac8f` — PROMPT_5 (taxonomia rica) + PROMPT_4 (PATCH `/validate`)
  + governanca documental mergeados.
- Suite 591/591 verdes.
- Skill auditor v1.1.0 já no repo (governanca).
- `RegulatoryIssue` com taxonomia rica (codigo_alerta + familia + 4 níveis severity).

---

## Sprints executados (PROMPT_6 — 26/05)

### Onda A1 — modelo + migration

**Enums novos** em `app/models/regulatory.py`:
- `StatusAchado` (5 valores: suspeita/confirmada/descartada/resolvida/ignorada).
- `DecisaoConsultor` (5 valores — **os 5 botões da P4**: corrigir_antes / seguir_com_ressalva / solicitar_doc / fora_escopo / ignorar_justificado).
- `StatusSaneamento` (5 valores: pendente/em_validacao/saneado/descartado/nao_aplicavel).

**5 colunas novas** em `RegulatoryIssue`:
- `status_achado` (Enum NOT NULL default `suspeita`).
- `decisao_consultor` (Enum nullable — obrigatório só para severity=critico).
- `decisao_consultor_justificativa` (String nullable — texto livre).
- `decisao_consultor_at` (DateTime nullable — gravado automaticamente quando
  decisao é setada/alterada).
- `status_saneamento` (Enum NOT NULL default `pendente`).

**Migration `d2c3e4f5a6b8_prompt6_camada2_principio1.py`:**
- 3 enums Postgres + 5 colunas + 2 índices (`ix_regulatory_issues_decisao_consultor`,
  `ix_regulatory_issues_status_achado`).
- Aditiva pura — registros existentes ganham defaults explícitos.
- Downgrade limpo (drop colunas + drop tipos).

### Onda A2 — auditor

Confirmação: o `auditor_imovel._persist_issues` **não** passa explicitamente
`status_achado` nem `status_saneamento` ao gravar `RegulatoryIssue`. Os
defaults do model (`suspeita` e `pendente`) cobrem. **Nenhuma mudança de
código** necessária no auditor — o default explícito do SQLAlchemy aplica.

### Onda B — endpoint PATCH /issues

`PATCH /api/v1/properties/{property_id}/issues/{issue_id}` em
`app/api/v1/regulatory.py`:

- Body parcial (`RegulatoryIssueUpdate` com `extra="forbid"`): 4 campos
  opcionais (`status_achado`, `decisao_consultor`,
  `decisao_consultor_justificativa`, `status_saneamento`).
- **AuditLog separado por campo alterado** — granularidade Princípio 2.
  `old_value`/`new_value` populados. Hash chain SHA-256 via `stamp_audit_hash`.
- **No-op por campo:** PATCH com mesmo valor não gera AuditLog (só mudança
  efetiva é evento auditável).
- **`decisao_consultor_at` gerenciado pelo servidor** — gravado automaticamente
  quando `decisao_consultor` muda (NULL→valor, valor→outro valor, ou
  valor→NULL). Body NÃO aceita override do timestamp.
- Tenant isolation: PATCH em issue de outro tenant retorna 404.

### Onda D — gate no PATCH /validate

No `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` (PROMPT_4),
**antes** de gravar `validated_*`:

```python
pendentes = (
    db.query(RegulatoryIssue)
    .filter(
        RegulatoryIssue.tenant_id == current_user.tenant_id,
        RegulatoryIssue.property_id == process.property_id,
        RegulatoryIssue.severity == RegulatoryIssueSeverity.critico,
        RegulatoryIssue.decisao_consultor.is_(None),
        RegulatoryIssue.resolved_at.is_(None),
    )
    .all()
)
if pendentes:
    raise HTTPException(422, detail={
        "message": "N alerta(s) crítico(s) sem decisão...",
        "alertas_pendentes": [{id, codigo_alerta, familia, severity}, ...]
    })
```

- **422** com lista completa de alertas pendentes (frontend mostra cada um
  para decisão).
- Alertas críticos RESOLVIDOS (`resolved_at != NULL`) **não bloqueiam** — já
  sanados no mundo.
- Alertas não-críticos (informativo/atenção/alto) **não bloqueiam** — gate
  é só para crítico (a sócia afiou essa distinção de propósito).
- Quando o gate rejeita, **nada é gravado**: `validated_at` continua None,
  nenhum `AuditLog("validated")` é criado.

---

## Testes

`tests/api/test_regulatory.py` ganhou 18 testes novos:

**`TestUpdatePropertyIssue` (11):**
- 401 sem auth
- 404 quando issue não existe
- 404 quando issue pertence a outra property
- body vazio = no-op + zero AuditLogs
- mudar `status_achado` → AuditLog `status_achado_changed` com old/new
- setar `decisao_consultor` (NULL → valor) → grava `decisao_consultor_at`
  + 2 AuditLogs (decisão + justificativa)
- mudar `decisao_consultor` (valor → outro valor) → atualiza timestamp
- múltiplos campos no mesmo PATCH → múltiplos AuditLogs distintos com hash
- mesmo valor (no-op por campo) NÃO gera AuditLog
- valor inválido (fora do enum) → 422
- extra field no body → 422 (`extra="forbid"`)
- tenant isolation: PATCH em issue de outro tenant → 404

**`TestValidateDiagnosisGateCamada2` (6):**
- 422 com 1 crítica sem decisão
- 422 lista TODAS as críticas pendentes
- 200 quando todas as críticas têm decisão
- 200 quando a crítica está RESOLVIDA (resolved_at != NULL)
- 200 sem issues críticas (alto/atencao não bloqueiam)
- 422 não grava `validated_at` nem AuditLog

Subset rodado: 18/18 verdes em ~94s. Suite completa rodando em background.

---

## Decisoes arquiteturais

### Opção A da reconciliação (3 campos ortogonais)

Os 3 campos medem dimensões diferentes do mesmo alerta:
1. **`status_achado`** — natureza do indício (responde "é real?")
2. **`decisao_consultor`** — ação escolhida (responde "o que faço?") — só
   obrigatória para crítico.
3. **`status_saneamento`** — progresso no mundo (responde "foi resolvido?")

Não há derivação automática — cada um é editável. Auditoria explícita por
campo. Trade-off: 3 colunas para preencher; ganho: cada faceta tem seu
AuditLog próprio.

### `decisao_consultor_at` gerenciado pelo servidor

Body do PATCH não aceita override do timestamp. Server grava em qualquer
mudança de `decisao_consultor` (inclusive NULL → valor e valor → NULL).
Evita timestamps mentirosos.

### Gate só para `critico` (não alto)

A sócia distinguiu alto vs. crítico de propósito (dívida #4 resolvida no
PROMPT_5). **Só crítico dispara decisão obrigatória.** Alto fica como
sinalização forte para o consultor, mas sem bloquear assinatura.

### Issue crítica RESOLVIDA não bloqueia

`resolved_at != NULL` significa que a divergência foi sanada no mundo —
não faz sentido exigir decisão sobre algo já resolvido. Gate respeita.

### AuditLog granular por campo (não payload único)

Cada campo alterado gera um `AuditLog` próprio com `old_value`/`new_value`.
Princípio 2: filtrar histórico por campo específico fica trivial. Hash
chain SHA-256 garante integridade da cadeia.

---

## Principais arquivos criados/modificados

### Backend
- `app/models/regulatory.py` — 3 enums + 5 colunas em RegulatoryIssue
- `app/models/__init__.py` — re-exports
- `app/schemas/regulatory.py` — `RegulatoryIssueOut` com 3 status + `RegulatoryIssueUpdate` (novo)
- `app/api/v1/regulatory.py` — PATCH `/issues/{id}` + gate no PATCH `/validate`

### Migration
- `alembic/versions/d2c3e4f5a6b8_prompt6_camada2_principio1.py` (**novo**)

### Testes
- `tests/api/test_regulatory.py` — `TestUpdatePropertyIssue` (11) + `TestValidateDiagnosisGateCamada2` (6)

---

## Dividas e pendencias

### Fechadas nesta rodada

- **#5** — Reconciliação dos 3 status. Opção A implementada + 5 botões P4
  como `DecisaoConsultor` enum + gate no `PATCH /validate`.
- **Camada 2 do Princípio 1** (5 botões P4) — implementada ponta a ponta
  no backend.

### Em aberto

- **UI dos 5 botões** — frontend consome `RegulatoryIssueOut` + PATCH; cada
  card de alerta crítico mostra os 5 radios + textarea de justificativa.
  Botão "Assinar diagnóstico" só habilita quando todas as críticas têm
  decisão.
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

- `feat/prompt6-camada2-principio1` aguardando PR.
- Princípio 1 fechado em **2 camadas**:
  - Camada 1 (PROMPT_4): consultor assina o diagnóstico como um todo.
  - Camada 2 (PROMPT_6): consultor decide alerta por alerta antes da
    assinatura — sem decisão, gate rejeita.
- 3 status reconciliados (Opção A) editáveis via PATCH com AuditLog
  granular.
- Frontend pendente (Onda C original do RECONCILIACAO_STATUS_ALERTAS).

Relacionado: [[prompt5-remodelar-regulatory-issue-2026-05-25]], [[prompt4-fechar-pipeline-2026-05-25]].
