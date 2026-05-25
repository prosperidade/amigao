# ADR-011 — Agentes não-bloqueantes na chain (`NON_BLOCKING_REVIEW_AGENTS`)

- **Status:** Aceita
- **Data:** 2026-05-24
- **Implementada em:** Onda B, commit `6b25602` (`feat/onda-bc-pipeline-ativacao`)
- **Relacionada a:** ADR-006 (skills procedurais), ADR-007 (StageOutputContent), Princípio 1 ("IA propõe; humano decide e assina")

## Contexto

O `AuditorImovelAgent` entrou na chain `extrator → auditor_imovel → legislacao → diagnostico`.
Como todo agente cujo output exige conferência humana, ele marca `requires_review=True`
(Princípio 1). O comportamento padrão de um output que exige review é **bloquear** o avanço até
a validação humana.

Aplicado ao auditor, esse padrão quebra o pipeline: o auditor produz **divergências documentais
que são insumo do Diagnóstico** (consumidas via `chain_data`). Se ele bloqueasse a chain
aguardando o consultor validar cada finding, o Diagnóstico — e tudo a jusante — nunca rodaria em
batch. O consultor receberia uma chain parada no primeiro movimento, sem nada para revisar de
fato, porque o produto que ele valida (o diagnóstico) depende justamente do passo bloqueado.

A tensão: **preservar o Princípio 1** (o output do auditor precisa de conferência humana) **sem
travar um pipeline** cujo valor só aparece ao final, quando o consultor vê o diagnóstico
completo com as divergências já incorporadas.

## Decisão

Criar a categoria `NON_BLOCKING_REVIEW_AGENTS = frozenset({"auditor_imovel"})` no orchestrator.

Um agente nessa lista:
- **continua marcando `requires_review=True`** — a UI exibe o badge, o output fica registrado para conferência, o Princípio 1 permanece intacto;
- **não trava o pipeline em batch** — a chain segue para os próximos agentes, que consomem o output via `chain_data`.

**Critério de entrada na lista:** o agente cujo output é **insumo** (`chain_data`) para outro
agente, e **não produto final** entregue diretamente ao consultor. O auditor qualifica: suas
divergências alimentam o Diagnóstico; o produto final que o consultor valida é o diagnóstico, não
o finding isolado.

## Consequências

**Positivas**
- O pipeline roda ponta a ponta; o consultor recebe o diagnóstico já com as divergências incorporadas e valida o conjunto, não fragmentos soltos.
- Separação explícita e versionada entre **agentes-insumo** e **agentes-produto** — um conceito de arquitetura que estava implícito e agora é regra.
- O Princípio 1 é preservado: nada do auditor é tratado como verdade definitiva; tudo nasce `requires_review=True`.

**Trade-offs / a ter em mente**
- Agentes a jusante (Diagnóstico) consomem findings **ainda não validados** pelo consultor. Isso é aceitável e coerente com o diagnóstico **preliminar** (triagem, H3 da skill de Diagnóstico — confiança baixa/média, hipóteses sinalizadas), mas exige que o preliminar use linguagem de cautela (P3) e que o consultor valide o conjunto ao final.
- A lista é um ponto de decisão sensível: incluir nela um agente que é **produto final** faria o consultor perder a janela de validação antes do downstream. O critério ("insumo, não produto") deve ser respeitado a cada novo agente.

## Alternativas consideradas

1. **Auditor bloqueia a chain** (padrão de review). Rejeitada: o Diagnóstico nunca rodaria em batch; o pipeline pararia no primeiro movimento.
2. **Auditor não marca `requires_review`.** Rejeitada: feriria o Princípio 1 — o output do auditor passaria como definitivo sem conferência humana.
3. **`NON_BLOCKING_REVIEW_AGENTS` (escolhida):** marca review (preserva Princípio 1) sem travar (preserva o pipeline). Captura a distinção real entre insumo e produto.

## Notas

- A reconciliação dos três conjuntos de status de um alerta (`status_saneamento` × `status` do auditor × `decisao_consultor`) é dívida aberta (ver Registro de dívidas, item 5) e deve considerar este ADR ao definir quando um finding de agente não-bloqueante é "resolvido".
- Quando o consumo de `chain_data["auditor_imovel"]` pelo Diagnóstico for implementado (Registro de dívidas, item 1), confirmar que findings `grade=critico` disparam o mecanismo de decisão obrigatória do consultor (P4) no produto final, mesmo tendo sido gerados por um agente não-bloqueante.
