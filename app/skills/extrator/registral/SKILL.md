---
name: extrator/registral
agent: extrator
version: 1.1.0
description: Método registral da entrada semântica ADR-071
applies_to: {}
---
## Contrato de evidência — ADR-069
Extraia uma única coleção de observações. Preserve trecho literal exato e a ocorrência do documento. Não deduplique duas fontes por hash. Não preencha papel, data, fração, identidade ou página ausente. Declarado não é confirmado. Preview e staging são projeções, nunca fontes novas. Liste limites e trechos ilegíveis. Não devolva proprietarios como lista de nome/CPF. Use partes, participacoes, atos e observacoes conforme EntradaExtraida.

## Método
Leia identidade do documento antes de interpretar atos. Separe certidão de matrícula e escritura pública. Escritura sustenta declarações e negócio, não registro ou titularidade atual. Identifique serventia, matrícula e rótulo literal de cada ato; não reúna AV.10 de inscrições distintas. Extraia transmitente e adquirente por expressão explícita. Preserve todas as baixas, cancelamentos, retificações e aditivos com referência expressa ao destino; nunca derive baixa de menção ao pagamento. Data do ato, emissão e eficácia são distintas. Não escolha maior ordem como prova de cadeia completa. Fração ausente permanece desconhecida. Preserve a qualificação documental de Sonia como transmitente do R-11.

Um cartório emite certidões de matrículas distintas com o mesmo cabeçalho. Esse cabeçalho não identifica o conteúdo. Separe áreas, atos, titulares e cadeia de cada número de matrícula. Na ELODI, os documentos 547, 548, 549 e 550 correspondem respectivamente às matrículas 3.181, 3.313, 3.673 e 4.387: os quatro são fontes distintas. Use esses números somente se confirmados no texto recebido; a orientação não é dado extraído.

## Ocorrencia documental e offsets

Cada item inclui trecho literal e posicao_inicio/posicao_fim: offsets globais
no extracted_text, caracteres Unicode, base zero e fim exclusivo. Nao estime
posicoes. Se o literal for unico, ambos podem ser nulos para localizacao
exata pelo sistema. Se repetido, amplie o contexto ate identificar uma unica
ocorrencia ou informe offsets exatos. Item ambiguo e rejeitado com motivo;
outros itens independentes continuam. Preserve as referencias entre partes,
representacao e atos; uma identidade rejeitada nao fundamenta participacao.
Identificador, inventario, referencia judicial, ano e data de consulta
informados precisam constar do trecho do proprio item; sem isso o campo
fica vazio, com motivo, e a observacao segue. Trecho que nao existe no texto
rejeita a observacao. Amplie o trecho em vez de omitir o valor.
