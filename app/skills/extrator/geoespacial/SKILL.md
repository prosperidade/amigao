---
name: extrator/geoespacial
agent: extrator
version: 1.1.0
description: Método geoespacial da entrada semântica ADR-071
applies_to: {}
---
## Contrato de evidência — ADR-069
Extraia uma única coleção de observações. Preserve trecho literal exato e a ocorrência do documento. Não deduplique duas fontes por hash. Não preencha papel, data, fração, identidade ou página ausente. Declarado não é confirmado. Preview e staging são projeções, nunca fontes novas. Liste limites e trechos ilegíveis. Não devolva proprietarios como lista de nome/CPF. Use partes, participacoes, atos e observacoes conforme EntradaExtraida.

## Método
Identifique formato, nome e ocorrência do arquivo. Não invente polígono, CRS, coordenadas ou área a partir de nome/menção textual. Registre que a capacidade geométrica é externa a este incremento (ADR-072); arquivo recebido não significa geometria processada. Não apresente área escrita em documento como cálculo geométrico.

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

Exemplo (sintetico). Texto da fonte, com quebra de linha:
    SITUACAO: TITULAR FALECIDO
    Ano do obito: 2021
Certo: trecho "SITUACAO: TITULAR FALECIDO\nAno do obito: 2021" (copia exata
e contigua; no JSON a quebra de linha vira \n), ou so "TITULAR FALECIDO" se o item nao
informa o ano.
Errado, e rejeitado: "Situacao: titular falecido em 2021" (reescrito: caixa,
palavras e ordem mudaram); "TITULAR FALECIDO ... 2021" (reticencias juntando
pedacos); "SITUACAO TITULAR FALECIDO" (pontuacao removida); texto que nao esta
na fonte. Regra: selecione e copie; nunca redija o trecho. Isto vale para todos
os itens; continue preenchendo todos os campos do schema.
