---
name: extrator/cadastral
agent: extrator
version: 1.1.0
description: Método cadastral da entrada semântica ADR-071
applies_to: {}
---
## Contrato de evidência — ADR-069
Extraia uma única coleção de observações. Preserve trecho literal exato e a ocorrência do documento. Não deduplique duas fontes por hash. Não preencha papel, data, fração, identidade ou página ausente. Declarado não é confirmado. Preview e staging são projeções, nunca fontes novas. Liste limites e trechos ilegíveis. Não devolva proprietarios como lista de nome/CPF. Use partes, participacoes, atos e observacoes conforme EntradaExtraida.

## Método
O adendo proposto da Ontologia v1 nomeia `comprovante_situacao_cadastral_cpf` (Receita) e `falecimento_declarado`. Para TITULAR FALECIDO, preencha `falecimentos_declarados[]`: sujeito é a chave da pessoa física em partes[], fonte é receita_federal, ano somente quando escrito junto à declaração, data exata sempre nula, data_consulta somente quando explícita. Preserve trecho literal abrangendo os valores e posição quando repetido. Ano da consulta não é ano de falecimento. Não completar a data pelo inventário ou pelo relógio. Ano não localizado fica nulo e sua falta permanece visível.

O estado próprio da pessoa é falecimento_declarado; K e R continuam independentes na evidência, sem confirmação pelo extrator. Não é campo do Client. Não criar espólio, inventário, sucessão ou representação a partir da Receita: cada um exige fundamento próprio. É proibido retornar apenas partes[] e perder a declaração. Suficiência da Receita para fechar o gate: PENDENTE-ISIS, inclusive eventual exigência de certidão de óbito.

Separe CAR, CCIR, ITR, SIGEF, RAT e peça do órgão. CAR/CCIR/ITR não provam domínio. Extraia car_area_ha, ccir_area_ha e itr_area_ha com unidade, objeto e trecho. Área de reserva legal não é área total. Nome de detentor não vira proprietário. Preserve o ato de consulta negativa mesmo sem destino cadastral; consulta exige identificadores, fonte, data e resposta para sustentar ausência. SIGEF documental não substitui cálculo de geometria. RAT é análise com escopo e data, não situação registral.

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
