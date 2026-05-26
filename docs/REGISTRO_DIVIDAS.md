# Registro de dívidas — Regente (consolidado pós-PROMPT_6 · 2026-05-26)

Reúne num lugar só as dívidas que estavam espalhadas por relatórios do agente, rodapés de skill,
memórias do desenvolvedor e análises de coordenação. Ordenadas por prioridade de desbloqueio.
Cada item: o que é, de onde veio, o que destrava, e o estado.

> **Convenção de governança:** este documento é VIVO (`docs/REGISTRO_DIVIDAS.md`) — atualizado ao
> fim de cada sprint. Itens fechados saem para a seção "Fechadas (histórico)" abaixo; não somem.
> Ver `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.

## P0 — fecham o pipeline ponta a ponta

*Nenhuma aberta nesta camada — as duas que estavam (#1 e #2) foram fechadas pelo PROMPT_4.
Pipeline ponta-a-ponta no nível de código: auditor cruza → diagnóstico consome → grava
versionado → consultor assina.*

## P1 — (esvaziada — todos os itens P1 já foram fechados)

*Os 3 itens que estavam aqui (#3 remodelagem do RegulatoryIssue, #4 mapeamento
4→3 do severity, #5 reconciliação dos 3 status) foram fechados nos PROMPTs 5
e 6. Ver tabela "Fechadas (histórico)" abaixo.*

## P2 — produto/domínio (precisam da sócia)

**6. Conjunto canônico de documentos esperados** (para `DOCUMENTO_AUSENTE`). A régua de
área não gera finding quando um lado é `None`; falta definir quais documentos são essenciais
por tipo de caso. Conecta com a planilha de checklist 1.2.1 da sócia. **Origem:** Onda C
(24/05).

**7. Marcador de aplicação de citação** (`confirmada`/`aplicacao_preliminar`/
`hipotese_a_confirmar`) no `EnquadramentoRegulatorioContent` do Legislação. Distinto da
validação de existência (o `citation_evaluator`, que não muda). **Origem:** P3.

**8. Tool determinística de cálculo de uso do solo** — função Python, não LLM. Fórmula por
**período × localização jurídica** (ver "Regime de compensação por supressão em GO" na
skill de Diagnóstico). Pós-contrato. **Origem:** skill de Diagnóstico (gabarito Romilton).

## P3 — robustez e higiene (sem urgência, sem risco externo)

**9. `except Exception` genérico no `pdf_generator.py:234`** devolve `{"error": str(e)}` sem
`status` — engole qualquer erro. O logo foi só o gatilho (resolvido na Onda A do PROMPT_3);
o tratamento de erro continua frágil. **Origem:** Onda A (24/05).

**10. Testes que dependem de storage externo sem mock.** O `test_pdf_generator` não era o
único caso latente provável. Varredura quando der folga. **Origem:** Onda A (24/05).

**11. Race no versionamento `MAX(version)+1`** — capturado por `UniqueConstraint`, mas
devolve 500 + retry manual. Tratar com retry server-side. Improvável para consultor único.
**Origem:** Onda B (24/05).

## Bloqueada por terceiros / coordenação (NÃO tocar sozinho)

**13. R1 — contratos externos.** Headers `X-Amigao-*` em `alerts.py`, `User-Agent` dos
crawlers. Risco de quebrar webhook receiver e allowlists de SEMAs. **Coordenar com os
consumidores antes.**

## Aguardando infraestrutura (D1 = `Property.geom`)

**14. Sobreposição e alertas geoespaciais** (🛰️ na skill do auditor): CAR deslocado,
polígono deslocado, sobreposição com terceiro, confrontantes, datum/fuso, RL × realidade,
APP, supressão, restrição territorial. O helper `grade_overlap_severity()` já está
preparado sem chamador; pluga direto quando o `geom` existir.

**15.** Alertas de consulta externa (🔌): embargo (IBAMA), auto de infração,
licença/outorga — aguardam integração.

## Backlog de produto (já versionado em ADR)

**16. Loop de aprendizado com material dos consultores** — ADR-010.

## Reveladas na revisão do PROMPT_6 (26/05) — novas dívidas

**17. Coerência entre os 3 status reconciliados.** A Opção A do
`RECONCILIACAO_STATUS_ALERTAS.md` foi implementada como **3 enums soltos**
— o `PATCH /properties/{prop}/issues/{id}` aceita qualquer combinação. A
"tabela-verdade do uso real" descrita no documento da proposta NÃO está
aplicada como constraint. Combinações contraditórias gravam sem erro
(ex.: `decisao=ignorar_justificado` + `status_achado=confirmada`;
`decisao=corrigir_antes` + `status_saneamento=saneado`). Não bloqueia
produção, mas a UI fica responsável por evitar essas combinações — frágil.
**Resolver:** seja regras de validação no schema Pydantic
(`@model_validator(mode='after')`), seja CHECK constraints no banco, seja
máquina de estados explícita. **Origem:** revisão do PROMPT_6 (26/05).

**18. Hash chain de `AuditLog` sem rotina de verificação.**
`app/services/audit_hash.py` tem **só escritores** (`compute_audit_hash`,
`get_last_hash_for_tenant`, `stamp_audit_hash`) — não existe função que
percorra a cadeia de um tenant e detecte se algum elo foi quebrado.
Hash chain sem verificador é cerimônia. **Resolver:** adicionar
`verify_audit_chain(db, tenant_id) -> list[BrokenLink]` que recomputa cada
hash em ordem e compara com o `hash_sha256` persistido; expor via endpoint
admin (read-only, auth restrita). **Origem:** revisão do PROMPT_6 (26/05).
**Nota:** dívida pré-existente (vem do A1); foi exposta porque a camada 2
do Princípio 1 reforça a ênfase na auditoria.

**19. Justificativa obrigatória para `ignorar_justificado` e `fora_escopo`.**
O nome do valor `ignorar_justificado` implica "com justificativa
preenchida", mas o `RegulatoryIssueUpdate` aceita `decisao_consultor=
ignorar_justificado` com `decisao_consultor_justificativa` vazio. Sem essa
exigência, o nome mente — vira cancela disfarçada. **Resolver:** validator
no `RegulatoryIssueUpdate` exigindo `justificativa not in (None, "")`
quando `decisao_consultor in {ignorar_justificado, fora_escopo}`.
**Origem:** revisão do PROMPT_6 (26/05).

---

## Fechadas (histórico — não revoga, só comprova fechamento)

| # | Item | Fechada em | Como |
|---|---|---|---|
| **1** | Diagnóstico não consome `chain_data["auditor_imovel"]` | 2026-05-25 (PROMPT_4 Onda A) | `_consume_auditor_findings()` em `app/agents/diagnostico.py` — findings viram `Divergencia` + `Risco` com `grau` 4-níveis preservado. Commit `f93b4b4`. |
| **2** | "Humano assina" — ciclo do Princípio 1 (camada 1) | 2026-05-25 (PROMPT_4 Onda B) | `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` grava `validated_by_user_id` + `validated_at` + AuditLog hash chain SHA-256. 409 ao revalidar. Commit `c74ff2e`. *(A camada 2 — 5 botões P4 — continua aberta, pós-PROMPT_5.)* |
| **3** | Remodelar `RegulatoryIssue` (família + codigo_alerta + 4 níveis) | 2026-05-25 (PROMPT_5 Onda A) | Enum `RegulatoryFamilia` (11 estável) + model `RegulatoryIssueCatalog` (PK = codigo_alerta string; catálogo evolutivo via INSERT, NÃO migration) + colunas `codigo_alerta`/`familia`/`muda_rota_regulatoria`/`muda_escopo_preco_prazo`/`documentos_cruzados` em `RegulatoryIssue`. `severity` passa para 4 níveis. Migration `c1b2d3e4f5a7` cria, popula 45 entradas seed (via `app/models/regulatory_catalog_seed.py`, fonte única) e migra dados antigos. `type` legado fica nullable (deprecated). |
| **4** | Mapeamento `grade` 4→`severity` 3 que colapsava alto+crítico | 2026-05-25 (PROMPT_5 Onda A) | `_GRADE_TO_SEVERITY` removido de `property_audit.py`. `AuditFinding.grade` e `RegulatoryIssue.severity` agora compartilham 4 níveis (`informativo`/`atencao`/`alto`/`critico`). Auditor emite codigos reais (📄) e grade direto; 🛰️/🔌 ficam no catálogo mas não emitidos até infra. Diagnóstico mapeia `familia` (11) → `RiscoCategoria` (7) via `_FAMILIA_TO_CATEGORIA` (substitui `_FINDING_TYPE_TO_CATEGORIA` do PROMPT_4). |
| **5** | Reconciliar `status_saneamento` × `status` do auditor × `decisao_consultor` (3 status circulantes) | 2026-05-26 (PROMPT_6 — Opção A do RECONCILIACAO_STATUS_ALERTAS) | 3 enums novos: `StatusAchado` (5 valores), `DecisaoConsultor` (os 5 botões P4), `StatusSaneamento` (5 valores). 5 colunas em `RegulatoryIssue`: `status_achado` (NOT NULL default `suspeita`), `decisao_consultor` (nullable), `decisao_consultor_justificativa`, `decisao_consultor_at`, `status_saneamento` (NOT NULL default `pendente`). PATCH `/properties/{prop}/issues/{id}` edita com AuditLog granular por campo. Gate no PATCH `/validate` rejeita 422 se houver crítica sem decisão (camada 2 do Princípio 1 fechada). Migration `d2c3e4f5a6b8`. |
| **Camada 2 P1** | 5 botões da P4 — decisão obrigatória por alerta crítico antes da assinatura | 2026-05-26 (PROMPT_6) | `decisao_consultor` enum com os 5 valores + gate no `PATCH /validate` retornando 422 com lista de pendentes. Frontend dos botões fica para rodada futura (UI consome `RegulatoryIssueOut` + PATCH). |
| **12** | `PROJECT_NAME='Amigão'` em `config.py:52` | 2026-05-23 (Fase 0) | Já estava `"Regente Ambiental"` quando a Fase 0 auditou. Commit `7877652` documentou. |

---

*Atualizar este registro ao fim de cada sprint. Itens fechados vão para a tabela acima,
não se apagam — comprova o trajeto e ajuda auditoria. Ver
`docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.*
