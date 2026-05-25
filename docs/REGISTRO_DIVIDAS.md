# Registro de dívidas — Regente (consolidado pós-PROMPT_4 · 2026-05-25)

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

## P1 — remodelagem que três dívidas compartilham

**3. Remodelar o `RegulatoryIssue`.** (**PROMPT_5 — próxima rodada**)
Hoje: `type` (enum curto que cai em "outro" para a maioria dos findings) + `severity` de 3
níveis. A taxonomia da sócia (40 alertas) e a régua de risco pedem outra forma:
- `familia` — enum estável (~11: identificação, titularidade, área, geoespacial, geo_incra,
  car, ambiental, fiscal, restrição_risco, licenciamento, validade_documental)
- `codigo_alerta` — **catálogo evolutivo, não enum** (cresce sem migration)
- campos novos: `muda_rota_regulatoria`, `muda_escopo_preco_prazo`, `documentos_cruzados`
- `severity`/`grade` com **4 níveis** (informativo/atenção/alto/crítico), não 3

**Origem:** ponto #5 dos sensíveis + taxonomia da sócia (P2). **Estado:** spec pronta na skill
do auditor; **PROMPT_5 implementa.**

**4. Mapeamento 4→3 níveis (`grade` → `severity`) colapsa alto e crítico.** (**parcial**)
O `AuditFinding.grade` preserva os 4 níveis, mas `_GRADE_TO_SEVERITY` projeta para os 3 do
`RegulatoryIssueSeverity`. A sócia afiou alto-vs-crítico de propósito: **só crítico dispara
o mecanismo de decisão obrigatória do consultor (5 ações, P4).**

- **Endereçada parcialmente pelo PROMPT_4 (Onda A):** o **payload** do Diagnóstico preserva
  os 4 níveis em `Risco.grau` (`critico` vira `critico_impeditivo_potencial`, NÃO colapsa).
  Camada 2 do Princípio 1 ainda não foi implementada, mas o sinal certo já circula.
- **Pendência:** a **persistência** em `RegulatoryIssue.severity` continua de 3 níveis.
  `_GRADE_TO_SEVERITY` sai junto com a Onda A do **PROMPT_5** (severity vira 4 níveis).

**5. Reconciliar os três conjuntos de status de um alerta.** (**PROMPT_5 — propõe, não
implementa**)
Circulam: `status_saneamento` (skill diagnóstico: pendente/em_validacao/saneado/descartado/
nao_aplicavel) × `status` do auditor (suspeita/confirmada/descartada/resolvida/ignorada) ×
`decisao_consultor` (P4: corrigir_antes/seguir_com_ressalva/solicitar_doc/fora_escopo/
ignorar_justificado). Descrevem coisas diferentes (estado do saneamento × estado do achado ×
ação escolhida) mas precisam de modelagem única antes do campo de decisão entrar em produção.

**Origem:** P4 + skill diagnóstico. **Estado:** PROMPT_5 Onda C **propõe** a reconciliação;
implementação fica para a rodada seguinte (junto com a camada 2 do Princípio 1).

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

---

## Fechadas (histórico — não revoga, só comprova fechamento)

| # | Item | Fechada em | Como |
|---|---|---|---|
| **1** | Diagnóstico não consome `chain_data["auditor_imovel"]` | 2026-05-25 (PROMPT_4 Onda A) | `_consume_auditor_findings()` em `app/agents/diagnostico.py` — findings viram `Divergencia` + `Risco` com `grau` 4-níveis preservado. Commit `f93b4b4`. |
| **2** | "Humano assina" — ciclo do Princípio 1 (camada 1) | 2026-05-25 (PROMPT_4 Onda B) | `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` grava `validated_by_user_id` + `validated_at` + AuditLog hash chain SHA-256. 409 ao revalidar. Commit `c74ff2e`. *(A camada 2 — 5 botões P4 — continua aberta, pós-PROMPT_5.)* |
| **12** | `PROJECT_NAME='Amigão'` em `config.py:52` | 2026-05-23 (Fase 0) | Já estava `"Regente Ambiental"` quando a Fase 0 auditou. Commit `7877652` documentou. |

---

*Atualizar este registro ao fim de cada sprint. Itens fechados vão para a tabela acima,
não se apagam — comprova o trajeto e ajuda auditoria. Ver
`docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.*
