# ADR-018 — Rodar os agentes da etapa é uma ação separada de avançar o card

**Status:** aceito
**Data:** 2026-06-29
**Contexto:** Fase 0.2 — Movimentação do Card. Decisão de produto do André.

## Contexto

A Ficha 07 (§6) descreve o card percorrendo as 7 macroetapas: **rodar os agentes
de uma etapa produz a saída e deixa o card "pronto para avançar"; o consultor
confirma o avanço**. O diagnóstico #78 (`docs/trabalhos/diagnostico_movimentacao.md`)
mediu que o código fazia o **inverso**: `POST /processes/{id}/macroetapa` (avançar
o card) é que disparava, fire-and-forget, a chain de agentes da etapa de destino
(`processes.py:854`, dict `_MACROETAPA_CHAINS`). Ou seja, "avançar" causava
"rodar", quando deveria ser o contrário.

Além de invertido, isso acoplava duas decisões distintas (executar os agentes vs.
mover o caso de etapa) num único gatilho, e fazia a chain rodar **na etapa nova**
em vez de **na etapa atual**.

## Decisão

Separar os dois gatilhos:

1. **Rodar os agentes da etapa** — `POST /processes/{id}/macroetapa/run-agents`.
   Dispara, async, a chain da macroetapa **atual** (`MACROETAPA_AGENT_CHAIN`). Ao
   concluir com sucesso, o worker marca o checklist da etapa
   (`mark_stage_agents_done`) e o card fica `pronta_para_avancar`. Etapas sem
   chain (`coleta_documental`, `contrato_formalizacao`) são manuais
   (`dispatched=false`).

2. **Avançar a etapa** — `POST /processes/{id}/macroetapa`. Apenas move o card,
   após o gate de prontidão (`can_advance_macroetapa`). **Não** dispara mais
   nenhuma chain.

O avanço é sempre **confirmado pelo consultor** (Princípio 1: a IA propõe ao
rodar e marcar o checklist; o humano decide ao clicar "Avançar etapa"). Não há
avanço automático ao terminar os agentes.

> Exceção preservada: a assinatura de um `RegulatoryDiagnosis`
> (`regulatory.py`) continua auto-avançando a etapa de diagnóstico — esse é um
> ato humano explícito (assinar), não uma consequência de rodar agentes.

## Consequências

- **Positivas:** o fluxo bate com a Ficha 07; rodar é idempotente e observável
  (audit `stage_agents_dispatched`); o card só anda por decisão humana; a chain
  roda na etapa certa (a atual).
- **Custo:** quem antes contava com a chain disparando "de graça" ao avançar para
  `diagnostico_tecnico`/`caminho_regulatorio`/`orcamento_negociacao` agora precisa
  clicar "Rodar agentes da etapa" na etapa nova. É o comportamento desejado.
- **Reversão:** reintroduzir o disparo no avanço (não recomendado) reabriria a
  inversão.

## Alternativas descartadas

- **Avanço automático ao terminar os agentes:** descartado pelo André — viola
  "consultor decide e assina".
- **Manter o disparo no avanço (status quo):** é exatamente o que o #78 apontou
  como a inversão que trava o entendimento do fluxo.
