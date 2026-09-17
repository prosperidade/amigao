# PR #171 frente ao Incremento 1 do plano v1.1

Conferência em 17/09/2026. Referência de execução: [plano diretor, §8](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md#8-os-oito-incrementos).
O [mergulho](../arquitetura/MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md) sustenta a análise; não substitui o plano.

## Base e autoria

- Main local e remota conferidas: `d2a3de0070a456acb9095d063164135ae26cbe06`.
- Worktree: `wt-contrato-evidencia`; branch: `feat/contrato-evidencia`.
- Documentos recebidos versionados isoladamente em `9e02b98`, sem edição de conteúdo.
- PR [#171](https://github.com/prosperidade/amigao/pull/171): aberto, rascunho, não integrado no momento da consulta.
- Único commit: `e30a8dd7296743d8ef545ce64962d957c9fd0a12`, autor `prosperidade <96192657+prosperidade@users.noreply.github.com>`.
- Diff: 12 arquivos, 360 inserções, 24 remoções. Nenhuma migration.
- O commit original permanece recuperável pela branch `fix/contraprova-jobson-20260917` e pela referência do PR. Não houve cherry-pick nem merge.

## Destino das alterações

As linhas abaixo são decisões de triagem, não alegações de transporte já executado.

| Alteração do #171 | Validade perante o plano | Destino |
|---|---|---|
| `auditor_imovel.py`: contar resumo pela matriz | Válida como contenção de contradição visual; não resolve contrato, revisão ou #220 | Reaproveitar o princípio na projeção canônica. Preservar contagem de achados e distinguir achado de divergência; não chamar ausência de achados de regularidade |
| `auditor_imovel.py`: não emitir divergência registral por fonte única | Válida, mas contar chaves de um dict não demonstra independência das fontes | Reaproveitar com identidade das fontes, sem declarar o confronto completo do Incremento 3 |
| `inconsistency_matrix.py`: denominação com fonte única vira atenção | Válida; observação isolada não é concordância nem divergência | Reaproveitar contenção e testes pertinentes. Não promover duas chaves do mesmo documento a duas fontes independentes |
| `inconsistency_matrix.py`: SIGEF ausente deixa de ser crítico e de ir ao orçamento | Válida; falta de evidência não demonstra obrigação nem serviço | Reaproveitar a contenção. A frase “nos documentos revisados” não pode permanecer sem material/cobertura recuperáveis; sem isso, usar `nao_determinado` |
| `diagnostico.py`: completar `metadata.uf` dentro do agente | Substituída pelo construtor único. Mantém precedência do payload e não trata conflitos | Não transportar. UF precisa de origem autorizada, normalização e conflito explícito. Não ativar a skill contraditória por este remendo |
| `legislacao.py`: fallback de demanda para `process_type` e objetivo inicial na query | Intenção válida: preservar objetivo sem promover classificação | Reimplementar no contexto único com origem e estatuto de relato; não manter enriquecimento exclusivo de uma porta |
| `intake.py`: validação sintática real de e-mail, sem consulta de entrega | Correção válida e independente, não resolve a cadeia decisória | Preservar no histórico para entrega própria de entrada. Não incluí-la incidentalmente no contrato; não alegar que explica a corrupção concreta de Jobson |
| `AgentResultRenderer.tsx`: resumo e aviso derivados da matriz, inclusive no legado | Válida como projeção de apresentação | Reaproveitar na adaptação da UI; histórico não recebe aprovação nem proveniência por essa projeção |
| Teste de tela do resumo histórico | Válido para apresentação | Reutilizar quando a projeção for transportada; não conta como gate autenticado de revisão/retomada |
| Alterações em `test_auditor_matriz`, `test_inconsistency_matrix`, `test_matriz_caso11_real` | Intenção válida: ausência/fonte única não provam risco/concordância | Adaptar somente junto à mudança correspondente e à semântica do contrato |
| `test_contraprova_jobson.py`: 14 casos sintéticos | Parte útil, parte incompatível | Manter controles de ausência e fonte única. Substituir teste que exige preservar UF do payload. Os testes com `MagicMock` não provam autenticação, persistência ou retomada |
| `CONTRAPROVA_JOBSON_2026-09-17.md` | Evidência histórica útil, planejamento anterior superado | Preservar por referência ao commit original. Não adotar sua ordem de liberação, nem seu relato de Docker ausente como fato do runtime atual |

Nenhuma dessas alterações estava incorporada à main conferida: o PR continua baseado exatamente em `d2a3de0`, com seu único commit fora da main. “Válida” nesta tabela não significa implementada nem suficiente para fechar o incremento.

## CI: causa confirmada e limites

[Run do PR 35230611165](https://github.com/prosperidade/amigao/actions/runs/35230611165), job de PostgreSQL `105233939040`: **1 failed, 2046 passed**, em 439,46 s.

Única falha: `tests/agents/test_auditor_imovel.py::TestExecuteSemLLM::test_payload_inclui_contagem_e_descricao`. A asserção esperava a palavra `divergência`; o resumo novo contém `Matriz documental: 0 item(ns), 0 ponto(s) para revisão. Achados das regras de auditoria: 2. Ausência de achados não comprova regularidade.`

[Run da main 34735852305](https://github.com/prosperidade/amigao/actions/runs/34735852305), SHA `d2a3de0070a456acb9095d063164135ae26cbe06`: seis jobs concluídos com sucesso — backend lint, backend PostgreSQL, migrations, frontend, portal e mobile.

Classificação: incompatibilidade de expectativa textual introduzida pelo PR, evidenciada pelo diff e pela CI verde da base. Não é falha de preparação do PostgreSQL. O teste precisa verificar o comportamento pretendido — contagens, descrição e ausência de afirmação de regularidade — e não apenas trocar a palavra para obter verde. Esta consulta não equivale a reexecução local da suíte.

## Decisão

Não integrar o PR integralmente. Seu fechamento sem merge não apaga o commit nem autoriza abandono das contenções identificadas. O transporte seletivo precisa citar a autoria acima e provar o novo comportamento.

O Incremento 1 inclui, desde a fundação, invalidação por versão de premissa sem apagar aprovação; nova avaliação do auditor sem sobrescrever aceite; retenção recuperável; compatibilização semântica das duas skills reais; transações e retomada concorrentes. O #171 não entrega essas garantias.

ADR-069 está livre no checkout conferido. A faixa de dívidas 200–299 já contém números até 230; o registro declara 231 como próximo livre. Não reservar 200 nem reutilizar os números existentes.

## Fechamento executado

Após esta triagem, o PR #171 foi fechado sem merge conforme instrução do André. A consulta posterior confirmou `state=CLOSED`, `mergedAt=null` e o mesmo head `e30a8dd7296743d8ef545ce64962d957c9fd0a12`. A branch original foi preservada. Nenhuma contenção foi transportada nesta etapa documental.

O push da branch documental foi bloqueado pela revisão automática de aprovação por exigir autorização explícita para publicar os documentos internos no remoto. Os commits são locais até essa autorização. Nenhum código, migration ou banco foi alterado nesta etapa.
