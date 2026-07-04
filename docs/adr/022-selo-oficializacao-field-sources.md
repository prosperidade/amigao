# ADR-022 — Selo de 3 estados = vocabulário de `field_sources`; automatismo com dedupe por destino; selo perene, gatilho contextual

- **Status:** Aceita
- **Data:** 2026-07-03
- **Validada por:** André (decisões travadas do Sprint 3) · Ficha 07 §3.4 e §9 (Isis, autoridade de produto)
- **Relacionada a:** ADR-016 (dedupe_key da Acao), ADR-017 (consolidação parcial), CAM2IH-007 (field_sources original), contrato de fontes #70, Princípio 1 (a IA propõe; o humano decide), Princípio 2 (auditável)

## Contexto

A Ficha 07 §3.4 define **três estados do dado**: VALIDADO · CORRETO, PENDENTE DE
OFICIALIZAÇÃO · NÃO VALIDADO. O §9 exige o automatismo: ao receber o selo do meio, o sistema
cria sozinho a ação "atualização de arquivos oficiais" (proposta; o consultor edita/remove).

O sistema já tinha uma infra de proveniência por campo — `field_sources` em `Client` e
`Property` (`raw | ai_extracted | human_validated | derived_matricula`) — mas a `Matricula`
não tinha a coluna, e a consolidação usava o fallback `old is not None` para decidir se um
campo já estava consolidado (qualquer valor não-nulo = consolidado, sem registrar por quê).

## Decisão

**O selo É o vocabulário de `field_sources` — não um enum de banco novo.**

- `VALIDADO` = `human_validated` (já existia).
- `CORRETO, PENDENTE DE OFICIALIZAÇÃO` = `pendente_oficializacao` (valor novo no vocabulário).
  Rótulo da UI sempre COMPLETO — nunca abreviar para "Pendente".
- `NÃO VALIDADO` = `raw | ai_extracted | derived_matricula | ausente` — **default por
  construção**: rebaixar um campo para "não validado" REMOVE a marca (não inventamos uma
  origem que não conhecemos mais).

**Selo perene, gatilho contextual.** O selo vive no `field_sources` da ENTIDADE
(Client/Property/Matricula) — sobrevive a processos. Mas o automatismo só dispara no
`POST /processes/{pid}/field-selo` (contexto de processo, com IDOR guard: a entidade precisa
pertencer ao tenant E estar ligada ao processo, senão 404). O `validate-fields` do Hub aceita
gravar o selo mas NUNCA cria ação — mesma razão do ADR-012: a decisão que gera trabalho é
contextual ao caso.

**Automatismo com dedupe por DESTINO, nunca por valor/estado.**
`dedupe_key = p{pid}:ofic:{sha1(entity|entity_id|field)[:24]}` — 1 ação POR CAMPO, título
"Atualização de arquivos oficiais — {rótulo do campo}". Consequências deliberadas:

- Oscilação `pendente → validado → pendente` não duplica (mesma chave).
- Ação **dispensada não recria** — a linha dispensada segura a chave; o sistema não desfaz
  triagem humana.
- Selo que volta a `VALIDADO` **não remove** a ação — o consultor dispensa/conclui.
- Guard `seen_this_run` desde o commit 1 + `uq_acoes_tenant_dedupe` como rede.

**Matricula ganha `field_sources` e a consolidação aposenta o fallback `old is not None`.**
A migration faz backfill (coluna não-nula da allowlist → `human_validated`, fiel: todo valor
de matrícula chegava por staging aceito ou cadastro manual). `_upsert_matricula` e o cadastro
manual carimbam proveniência na escrita. `pendente_oficializacao` também conta como
"já consolidado" na reconciliação — doc novo divergente de verdade técnica selada vira
reconciliação, não sobrescrita silenciosa.

**Selo NUNCA trava avanço.** Gate de macroetapa intocado — o selo sinaliza e gera trabalho,
não bloqueia.

Tudo auditado: `AuditLog action="field_selo"` com hash chain SHA-256.

## Consequências

**Positivas**
- Zero enum/tabela nova para o selo: reusa a infra de proveniência existente, badges do Hub
  continuam funcionando; o dossiê expõe campos-chave da matrícula (SIGEF, INCRA/SNCR,
  NIRF/CIB) e a reconciliação de áreas (documental × gráfica × total derivada).
- O caminho selo→ação materializa o §9 da Ficha sem tirar o consultor do comando (ação nasce
  `pendente` na triagem; Princípio 1).
- O fallback ambíguo da consolidação morre — proveniência explícita nas 3 entidades.

**Negativas / limites**
- `field_sources` é um só slot por campo: selar sobrescreve a origem anterior (`ai_extracted`
  se perde ao validar). Aceito — o AuditLog guarda o histórico (`anterior` no details).
- O backfill assume `human_validated` para dado legado de matrícula — fiel hoje, mas é uma
  afirmação retroativa registrada aqui.
- Rebaixar para "não validado" apaga a marca; não há como voltar ao `ai_extracted` original
  sem consultar o audit.

## Alternativas descartadas

- **(a) Enum de banco / coluna `selo` própria** — descartado: duplicaria a semântica de
  `field_sources` e exigiria migration + sync entre dois campos por entidade.
- **(b) Dedupe por valor do selo** (chave incluindo estado) — descartado: oscilar o selo
  duplicaria a ação e reabriria triagem já dispensada.
- **(c) Hub também dispara o automatismo** — descartado: ação é trabalho do CASO; o Hub não
  sabe a qual processo atribuir (e criaria ação em processo errado ou nenhum).
- **(d) Remover a ação quando o selo volta a VALIDADO** — descartado: sistema não desfaz
  trabalho/triagem do consultor (mesmo princípio da não-recriação).
