---
name: extrator/geoespacial
agent: extrator
version: 1.0.0
description: Método geoespacial da entrada semântica ADR-071
applies_to: {}
---
## Contrato de evidência — ADR-069
Extraia uma única coleção de observações. Preserve trecho literal exato e a ocorrência do documento. Não deduplique duas fontes por hash. Não preencha papel, data, fração, identidade ou página ausente. Declarado não é confirmado. Preview e staging são projeções, nunca fontes novas. Liste limites e trechos ilegíveis. Não devolva proprietarios como lista de nome/CPF. Use partes, participacoes, atos e observacoes conforme EntradaExtraida.

## Método
Identifique formato, nome e ocorrência do arquivo. Não invente polígono, CRS, coordenadas ou área a partir de nome/menção textual. Registre que a capacidade geométrica é externa a este incremento (ADR-072); arquivo recebido não significa geometria processada. Não apresente área escrita em documento como cálculo geométrico.
