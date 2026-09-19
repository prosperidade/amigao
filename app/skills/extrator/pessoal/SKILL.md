---
name: extrator/pessoal
agent: extrator
version: 1.0.0
description: Método pessoal da entrada semântica ADR-071
applies_to: {}
---
## Contrato de evidência — ADR-069
Extraia uma única coleção de observações. Preserve trecho literal exato e a ocorrência do documento. Não deduplique duas fontes por hash. Não preencha papel, data, fração, identidade ou página ausente. Declarado não é confirmado. Preview e staging são projeções, nunca fontes novas. Liste limites e trechos ilegíveis. Não devolva proprietarios como lista de nome/CPF. Use partes, participacoes, atos e observacoes conforme EntradaExtraida.

## Método
Preserve PF/PJ e os identificadores literais. CPF de representante nunca substitui CNPJ de ELODI ou de outra PJ. Papel e vínculo dependem de texto explícito; nome igual não autoriza fusão. Espólio referencia pessoa falecida e inventário, sem CPF/CNPJ próprio. Inventariante e representante exigem documento de poderes, alcance e intervalo; desconhecimento de validade produz lacuna, não poderes ilimitados. Documento pessoal isolado só identifica a pessoa. Nunca transforme vendedor em cliente.

No comprovante da Receita, preserve literalmente “TITULAR FALECIDO” como situação declarada na fonte. PF descreve a natureza da pessoa, não significa pessoa viva. Não invente data de óbito a partir da emissão ou consulta. Se o ano constar sem dia e mês, registre o literal e a precisão disponível em observação própria. Não substitua o CPF do falecido por identificador do espólio ou do inventariante.
