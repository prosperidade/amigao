# ADR-071 — Entrada semântica e motor cartorário

**Estado: proposta em implementação, sem homologação ou merge.** 18/09/2026.
Autoridades: Plano Diretor v1.1 §8, ADR-070, MIGRACAO_MODELO_DADOS e
ONTOLOGIA_REGENTE_v1. O glossário decide nomes; lacunas não autorizam criar
predicado pelo prompt.

## Decisão em implementação

Fonte versionada → observação ancorada → projeções de staging/preview.
Pessoas, espólios e participações mantêm fundamento e contexto. Extração declara;
não confirma por iniciativa do modelo. Contrato conserva contratante, contratado,
objeto, representação e referência judicial mesmo sem coluna cadastral.

`contrato_servico_documental` é a espécie da Ontologia §3. O adendo proposto de
18/09 nomeia `comprovante_situacao_cadastral_cpf` e `falecimento_declarado`.
Schema e método cadastral preservam ano, sujeito, fonte e data da consulta;
não inferem data exata, sucessão ou espólio. Pessoa guarda estado próprio com
fundamento versionado, K/R independentes; não se grava esse estado no Client.
Suficiência da Receita para fechar o gate permanece PENDENTE-ISIS.
Inventariante declarado no contrato não tem poderes presumidos; confirmação exige
revisão de termo de compromisso ou certidão do inventário, com alcance e tempo.

O motor é determinístico. Agrupa por número de matrícula **e** serventia e resolve
rótulos dentro do documento/contexto. Cabeçalho comum não une quatro matrículas.
Ausência de baixa não produz titularidade atual nem vigência incondicionada.
Cobertura, data de referência, cadeia e frações insuficientes permanecem lacunas.

## Migration e limites

Rascunhos `071es001`–`071es004`, após `069ce001`, seguem os blocos 1–4 do roteiro:
fundação imutável/manifesto/snapshot, versão documental/fragmentos, premissas,
pessoas/espólio/atos/participações. Não constituem autorização de aplicação.
Tabelas e referências novas são aditivas; generated columns, índices/constraints,
triggers de imutabilidade e validação de linhas existentes exigem planejar janela
e levantar inconsistências antes da aplicação. Não sanear legado nesta frente.
O bloco 0 de inventário de produção e demais passos do roteiro continuam exigidos.

As 174 regras da planilha inventariada no #175 são insumo, não 174 regras já
implementadas. O catálogo executável e sua homologação estão pendentes. Geometria,
motor jurídico, demais skills e saneamento de legado ficam nos incrementos próprios.

Condição de conclusão: [gate autenticado](../auditoria/GATE_INCREMENTO2.md), com
texto real, todos os itens e regressão do Incremento 1. Implementação parcial,
controle sintético e sintaxe válida não substituem esse gate.
