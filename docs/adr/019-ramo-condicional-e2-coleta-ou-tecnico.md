# ADR-019 — Ramo condicional na saída da E2: coleta (E3) ou diagnóstico técnico (E4)

**Status:** aceito
**Data:** 2026-06-29
**Contexto:** Sprint 1 — Ficha 07, máquina de etapas. Decisão de produto do André.

## Contexto

A Ficha 07 descreve um **ramo** na saída da E2 (Diagnóstico Preliminar): terminada
a E2 (diagnóstico preliminar gerado + base consolidada), **se há documento
essencial pendente** o caso vai para a Coleta Documental (E3) para coletá-lo;
**senão** pula a coleta e vai direto para o Diagnóstico Técnico (E4).

A máquina de macroetapas era **estritamente linear** (`MACROETAPA_TRANSITIONS`,
cada etapa com um único sucessor; `next_macroetapa = nexts[0]`). Não havia
sucessor condicional. Além disso, o gate tratava "documento obrigatório pendente"
como **blocker** em **todas** as etapas — o que, na E2, **travaria** justamente o
caso que precisa ir à coleta para resolver a pendência (contradição direta com o
ramo).

O sinal "documento essencial pendente" **já existe** e é canônico: itens do
`ProcessChecklist` com `required=True` em `status="pending"` (definidos por
`ChecklistTemplate` por `demand_type`, gerados no intake). É o mesmo `missing_docs`
contado no kanban, no detalhe e no gate. **Não foi preciso inventar conjunto de
essenciais nem mudar o `DiagnosticoAgent`** (config de agentes congelada).

## Decisão

1. **Dois destinos válidos na E2.** `MACROETAPA_TRANSITIONS[diagnostico_preliminar]`
   passa a `[coleta_documental, diagnostico_tecnico]` (coleta em 1º — default/legado
   para `nexts[0]`). Ambas as transições são válidas → a E4 é alcançável **direto**
   da E2.

2. **Destino recomendado resolvido por função pura.**
   `resolve_next_macroetapa(current, has_essential_pending)`: na E2 retorna
   `coleta_documental` se há essencial pendente, senão `diagnostico_tecnico`;
   nas demais etapas, o sucessor linear. `_compute_can_advance` usa-a para o
   campo `next_macroetapa` (com `has_essential_pending = missing_docs > 0`).

3. **Doc essencial pendente ROTEIA, não trava, na E2.** `list_macroetapa_blockers`
   ganha `current_macroetapa`: em `diagnostico_preliminar` o documento pendente
   **não** vira blocker (ele decide o destino); nas outras etapas (notadamente a
   própria `coleta_documental`) continua blocker. O gate da E2 segue exigindo
   checklist 100% + diagnóstico assinado (regra recém-corrigida, **preservada**).

4. **Entrada da E4 é CONDIÇÃO, não "E3 anterior".** O gate/estado da E4 só
   inspecionam o próprio checklist — nunca exigiram "E3 concluída". Nada a mudar
   no gate da E4; apenas tornar a transição válida (item 1).

5. **A E3 pulada é `skipped`, não `completed`.** `get_macroetapa_status` marca a
   coleta como `skipped` quando ficou para trás com checklist intocado (0%) — o
   stepper não mente (Princípio: "o badge não mente"). Novo valor `skipped` no
   tipo do front, com estilo próprio (tracejado, "· pulada").

O avanço continua **confirmado pelo consultor** (Princípio 1 / ADR-018): o ramo
decide só o **destino**, não automatiza o avanço.

## Consequências

- **Positivas:** o fluxo bate com a Ficha 07; a coleta é pulada quando não agrega;
  a E2 deixa de ser travada por pendência que ela mesma encaminha; reuso do sinal
  `missing_docs` já existente (sem nova regra de negócio); ramo testado nos dois
  caminhos + auditado (`macroetapa_changed`).
- **Custo:** a E2 agora tem dois destinos — qualquer caller que assumia sucessor
  único deve usar `resolve_next_macroetapa`/`next_macroetapa` (já ajustado).
- **Reversão:** voltar a `[coleta_documental]` e remover o ramo reintroduz a
  linearidade (não recomendado — reabre o gap da Ficha 07).

## Alternativas descartadas

- **Emitir uma nova lista de essenciais no `DiagnosticoAgent`:** desnecessário — o
  `ProcessChecklist` (required+pending) já é o sinal canônico; mexer no prompt do
  agente violaria o congelamento de config de agentes.
- **Bloquear a E2 quando houver doc pendente:** é o status quo que contradiz o
  ramo (impediria o caminho da coleta).
- **Forçar o destino no `POST /macroetapa` (recusar E4 quando há pendente):**
  descartado — sobre-restringe o consultor; ambas as transições são legítimas e
  o destino recomendado já é sinalizado por `next_macroetapa`.
