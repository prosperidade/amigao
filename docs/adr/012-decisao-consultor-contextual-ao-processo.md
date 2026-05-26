# ADR-012 — A decisão do consultor sobre uma divergência é contextual ao processo, não perene no imóvel

- **Status:** Aceita
- **Data:** 2026-05-26
- **Validada por:** Isis (sócia, validadora de domínio)
- **Relacionada a:** PROMPT_6 (camada 2 do Princípio 1), dívida #5/#17 (reconciliação de status), ADR-011

## Contexto

A `RegulatoryIssue` (o fato de uma divergência — ex.: titularidade da matrícula ≠ CCIR) mora na
`Property`, porque é um fato do imóvel que atravessa o tempo. O PROMPT_6 implementou a camada 2 do
Princípio 1 colocando a **decisão do consultor** (os 5 botões da P4 + justificativa + timestamp)
como **campo da `RegulatoryIssue`** — ou seja, perene no imóvel.

Isso levantou a questão: quando o mesmo imóvel volta meses depois para um trabalho diferente
(primeiro uma venda, depois um financiamento), a decisão tomada antes vale automaticamente? O peso
de uma mesma divergência muda conforme o que se quer fazer — titularidade torta pesa diferente para
vender e para dar como garantia ao banco.

## Decisão

A sócia validou a opção **(b): cada trabalho recomeça.** Cada processo faz o consultor olhar e
decidir do zero, porque o peso da divergência muda com o contexto.

Consequência de modelagem:
- **O fato da divergência é perene** → permanece na `RegulatoryIssue` (Property): detecção
  automática, área, evidência, documentos cruzados, e o saneamento *real* (se a titularidade foi
  de fato corrigida no cartório, isso muda o fato e vale para todos).
- **A decisão do consultor é contextual** → sai da `RegulatoryIssue` e passa a ser uma entidade
  por **(issue × processo)** (ex.: `ProcessIssueDecision`): os 5 botões (`DecisaoConsultor`), a
  justificativa, o timestamp e a avaliação daquele trabalho. Cada processo começa sem decisão
  herdada; o consultor decide de novo.

## Consequências

**Positivas**
- Respeita o peso contextual da divergência — a decisão de "aceitar o risco" não vaza de um trabalho de venda para um de crédito.
- **Simplifica o gate da camada 2:** ele passa a verificar sempre as decisões *daquele processo*, sem precisar checar validade temporal de uma decisão antiga.
- **Ajuda a resolver a #17** (coerência dos 3 status): separar o que é perene (fato, saneamento real → Property) do que é contextual (avaliação, decisão → Processo) clarifica quais status convivem e onde.

**Trade-off**
- **Re-modelagem do que o PROMPT_6 fez:** os campos de decisão (`decisao_consultor`, `justificativa`, `decisao_consultor_at`) saem da `RegulatoryIssue` para a nova entidade por processo; o `PATCH /properties/.../issues/{id}` e o gate `/validate` ajustam para operar sobre a decisão-por-processo. Os 3 enums e o conceito dos 5 botões se aproveitam — muda *onde* a decisão mora.
- **A UI dos botões depende disto** — a rodada de frontend só começa depois da re-modelagem.

## Alternativas consideradas

1. **(a) Decisão perene no imóvel** (o que o PROMPT_6 fez). Rejeitada pela sócia: faz uma decisão tomada para um contexto (venda) liberar automaticamente outro (crédito), onde a mesma divergência pesa mais.
2. **(c) Guardada com aviso** ("decidido no trabalho X em tal data — ainda vale?"). Considerada, mas a sócia preferiu (b): recomeçar do zero é mais simples e seguro do que herdar uma decisão e arriscar que o consultor confirme no automático.
3. **(b) Recomeça por trabalho (escolhida).**

## Notas

- Encadeia direto na próxima rodada de implementação (re-modelagem antes da UI). Quando executada, dispara `MODELO_DE_DADOS` e `API_v1` (cadência documental).
- O `StatusSaneamento` precisa ser examinado na re-modelagem: o saneamento *real* (fato corrigido) é perene; a avaliação de saneamento *naquele trabalho* pode ser contextual. Detalhar ao implementar.
