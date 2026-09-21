---
name: extrator/contratual
agent: extrator
version: 1.1.0
description: Método contratual da entrada semântica ADR-071
applies_to: {}
---
## Contrato de evidência — ADR-069
Extraia uma única coleção de observações. Preserve trecho literal exato e a ocorrência do documento. Não deduplique duas fontes por hash. Não preencha papel, data, fração, identidade ou página ausente. Declarado não é confirmado. Preview e staging são projeções, nunca fontes novas. Liste limites e trechos ilegíveis. Não devolva proprietarios como lista de nome/CPF. Use partes, participacoes, atos e observacoes conforme EntradaExtraida.

## Método
Dê à espécie o nome da Ontologia §3: `contrato_particular` ou `contrato_servico_documental`. Preencha `contratos[]` no schema EntradaExtraida: `contratante[]` e `contratado[]` referenciam chaves de `partes[]`; `objeto` preserva o serviço/negócio expresso; `representacao_declarada[]` preserva representante ou inventariante, representado, alcance e datas somente quando escritos; `referencia_processo_judicial[]` conserva o número literal. Cada contrato e representação exige trecho exato e posição quando houver repetição. Campos não localizados ficam nulos ou listas vazias, nunca preenchidos pelo cadastro do cliente. Contratante, contratado e representante são contextos distintos; não promover nenhum deles a cliente ou titular.

O staging recebe uma projeção dessas observações, inclusive sem target_entity/target_field. A observação com fonte versionada é a autoridade. Não devolver apenas campos genéricos que omitam o contrato por falta de coluna cadastral.

Diferencie contrato particular sobre imóvel e contrato de serviço da consultoria. Preserve partes e papéis expressos, objeto, condições e aditivos. Contrato não comprova registro nem titularidade atual. Não extraia denominação do imóvel a partir do nome do serviço. Aditivo sem vínculo explícito permanece observação com lacuna; não emende o primeiro contrato disponível. Assinatura, declaração e vigência não são a mesma coisa.

Contrato com ESPÓLIO não pode ser descartado por não preencher cadastro. Preserve a parte espólio, o vínculo nominal ao falecido, o número de inventário e a pessoa indicada como inventariante. Preserve OAB como identificador profissional próprio, nunca como CPF nem como prova de nomeação. A menção ao inventariante é participação declarada mesmo sem termo de nomeação: registre as lacunas de documento, alcance e validade. Não complete essas lacunas pela data do contrato. A escritura anexada ao inventário continua escritura; sua origem não a transforma em certidão nem prova sucessão concluída.

`confirmado` não pode sair deste método. Para inventariante, a confirmação depende de revisão com termo de compromisso ou certidão do inventário; a falta desse documento é lacuna visível.

## Ocorrencia documental e offsets

Cada item inclui trecho literal e posicao_inicio/posicao_fim: offsets globais
no extracted_text, caracteres Unicode, base zero e fim exclusivo. Nao estime
posicoes. Se o literal for unico, ambos podem ser nulos para localizacao
exata pelo sistema. Se repetido, amplie o contexto ate identificar uma unica
ocorrencia ou informe offsets exatos. Item ambiguo e rejeitado com motivo;
outros itens independentes continuam. Preserve as referencias entre partes,
representacao e atos; uma identidade rejeitada nao fundamenta participacao.
Identificador, inventario, referencia judicial, ano e data de consulta
informados precisam constar do trecho do proprio item; sem isso o item e
rejeitado. Amplie o trecho em vez de omitir o valor.
