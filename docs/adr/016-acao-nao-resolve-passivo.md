# ADR-016 — Concluir uma ação NÃO resolve o passivo de origem

- **Status:** Aceita
- **Data:** 2026-06-18
- **Validada por:** Isis (sócia, validadora de domínio) — decisões 16/06
- **Relacionada a:** Ficha 07 (Aba Ações + Quadro de Ações global), ADR-012 (decisão contextual), contrato de fontes #70 (PR #70), Princípio 1 (a IA propõe; o humano decide)

## Contexto

A Ficha 07 introduz a entidade `Acao` — a camada onde o **diagnóstico vira trabalho**. Cada passivo
levantado no diagnóstico/auditor (com fonte — contrato #70) pode virar uma ação que o consultor
**tria** (tarefa interna · escopo de venda · dispensada). Cada ação carrega um `vinculo_passivo` que
aponta para o passivo/linha de origem (rastreabilidade).

Surge a pergunta: **concluir uma ação resolve o passivo correspondente?** Por exemplo, marcar
"Solicitar retificação de área no CAR" como `concluida` deveria mudar o `status_saneamento` do
`RegulatoryIssue` de área para `saneado`?

## Decisão

**Não.** Concluir uma ação é "trabalho interno feito" — nunca "passivo resolvido".

No diagnóstico **nada se resolve**. Um passivo só é efetivamente sanado depois da **contratação** e
da **regularização real** no mundo (cartório, órgão, CAR retificado) — fluxo pós-MVP. A ação
**referencia** o passivo de origem para rastreabilidade, mas:

- `vinculo_passivo` é um **JSON solto, sem FK** para `RegulatoryIssue`. Não existe nenhum caminho de
  escrita de `Acao` → `RegulatoryIssue`/achado.
- Concluir, triar ou mover uma ação **jamais** toca `status_achado`, `status_saneamento` ou
  `resolved_at` do passivo.
- O saneamento real do passivo continua sendo decisão humana explícita no próprio `RegulatoryIssue`
  (`PATCH /properties/{id}/issues/{id}`), independente da ação.

Isso é coerente com o ADR-012: o **fato** do passivo é perene no imóvel; a **ação** é trabalho
contextual ao processo. São camadas separadas (Princípio 3 — Cadastro / Diagnóstico / Coleta /
Trabalho não se misturam).

## Consequências

**Positivas**
- Impede que "fechar uma tarefa" minta sobre a realidade regulatória do imóvel — o passivo só some
  quando foi de fato corrigido no mundo.
- Mantém a auditabilidade honesta (Princípio 2): a conclusão da ação gera AuditLog próprio, mas não
  contamina o histórico do achado.
- Simplifica a modelagem: `Acao` não precisa conhecer a máquina de estados do `RegulatoryIssue`.

**Negativas / limites**
- O consultor que sanar um passivo de fato precisa de **dois gestos**: concluir a ação E atualizar o
  status do alerta. Aceito no MVP — são informações diferentes (trabalho feito × fato corrigido).
- A ponte "ação concluída sugere revisar o passivo" pode ser adicionada como *dica de UI* no futuro,
  sem nunca virar escrita automática.

## Alternativas descartadas

- **(a) Concluir a ação marca o passivo como saneado** — descartada: confunde trabalho interno com
  saneamento real; abriria porta para "passivo resolvido" sem regularização, ferindo a honestidade
  do diagnóstico.
- **(b) FK rígida `Acao.issue_id`** — descartada: nem todo passivo de origem é um `RegulatoryIssue`
  (riscos/afirmações do diagnóstico não têm id estável); o vínculo solto cobre todos os casos sem
  acoplar.
