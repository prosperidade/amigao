---
name: extrator/cartorario
agent: extrator
version: 1.0.0
description: Método cartorario da entrada semântica ADR-071
applies_to: {}
---
## Contrato de evidência — ADR-069
Extraia uma única coleção de observações. Preserve trecho literal exato e a ocorrência do documento. Não deduplique duas fontes por hash. Não preencha papel, data, fração, identidade ou página ausente. Declarado não é confirmado. Preview e staging são projeções, nunca fontes novas. Liste limites e trechos ilegíveis. Não devolva proprietarios como lista de nome/CPF. Use partes, participacoes, atos e observacoes conforme EntradaExtraida.

## Método
Método determinístico, sem LLM. Qualifique suporte pela espécie. Resolva relações apenas por identidade completa e referência explícita; ambiguidades geram lacuna. Situação é calculada na data de referência e limitada ao material. Ausência de baixa nunca prova vigência externa. Transmissão parcial mantém saldo e exige fração e direito identificados; sucessão exige representação e fundamento. Sem cobertura e continuidade comprovadas, titularidade é não determinada. As 174 condições textuais do INS-003 são insumo, não 174 regras executáveis homologadas. Registre regras não avaliáveis e versão/hash do método.
