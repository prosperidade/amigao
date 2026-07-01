# ADR-021 — Rota Regulatória (E5): snapshot editável, demand_type-driven, reconciliação mediada por humano

- **Status:** Aceita
- **Data:** 2026-06-30
- **Validada por:** André (decisões travadas do sprint) · Ficha 07 §8.1 e §9 (Isis, autoridade de produto)
- **Relacionada a:** ADR-007 (StageOutputContent), ADR-016 (dedupe_key da Acao), ADR-017 (consolidação parcial), contrato de fontes #70, Princípio 1 (a IA propõe; o humano decide e assina), Princípio 2 (auditável), dívida #48 (constraint desde o commit 1), dívida #18 (hash chain)

## Contexto

A `LegislacaoAgent` (movimento E5) já produz `etapas` — os passos do caminho regulatório. O
diagnóstico read-only mostrou que esses passos eram **efêmeros**: viviam só dentro do JSON do
`AIJob` e do `chain_data` em memória, sem tabela, sem tela, perdidos ao recarregar. "A Rota é a
entrega de valor" — faltava materializá-la como entidade que o consultor opera e **assina**.

Três achados da medição condicionaram o desenho:

1. **Dual-emit.** `EnquadramentoRegulatorioContent` carrega dois shapes de `etapas` no mesmo
   dict: o TIPADO (`Etapa` com `sources`+`prazo_fonte`) e o BRUTO top-level (dict com
   `fonte_trecho`, que `legislacao.py:719-723` sobrescreve). O bruto quebra o schema strict.
2. **A cadeia está pela metade.** A legislação keia por `demand_type`, **não** pelos passivos
   do auditor. O elo `auditor → legislacao` não existe no código.
3. **Sem identidade estável.** O passo não tem chave própria; `ordem` é instável entre runs.

## Decisão

**Entidade `Rota` + `RotaPasso` como snapshot editável, materializado do que a legislação emite
hoje, reconciliado de forma aditiva e mediada por humano.**

- **Ler o TIPADO, nunca o bruto.** A materialização reconstrói `Etapa` tipada (`sources`+
  `prazo_fonte`), preferindo campos típados e mapeando `fonte_trecho` como o próprio agente faz.
  O que é persistido nunca é o shape bruto.
- **demand_type-driven.** Uma rota por `(tenant, process, demand_type)`. **Não** religamos a
  chain agora — persistimos o que a legislação já produz. Religar `auditor → legislacao` é
  follow-on nomeado (dívida #50).
- **Reconciliação NÃO-destrutiva** (padrão ADR-017): passo IA novo entra; passo que casa
  `dedupe_key` preserva ordem/edição/classificação do consultor; passo `manual` nunca é tocado;
  rota já validada + diff da IA vira `desatualizada` (não rebaixa o conteúdo assinado) e trava
  "Fechar rota" até o consultor aceitar o diff.
- **"Nenhum passo sem norma" enforça na VALIDAÇÃO, não na geração** (radar-não-cancela): passo
  sem fonte entra marcado (`estimativa_profissional`/`sem_fonte`); o consultor reconhece ao
  validar. A geração nunca recusa um passo por falta de norma.
- **Classificação obrigatória para validar** (Ficha §8.1): cada passo é `item_proposta`
  (faturável) ou `direcao` — `NULL` até o consultor decidir; validar exige a decisão.
- **`dedupe_key` é HIGIENE, não oráculo** (dívida #48): `sha1(rota_id | norma_ref | orgao |
  titulo)`, exclui `ordem` (instável) e matrícula (a rota é por imóvel). Constraint desde o
  commit 1, mas a reconciliação real é mediada pelo humano — a chave só evita duplicar o óbvio.
- **Fechar assina** (Princípio 2): "Fechar rota" só habilita com todos os passos validados e
  grava um `AuditLog` com **hash chain SHA-256** (primeiro uso real da cadeia — dívida #18).

## Consequências

**Positivas**
- A Rota deixa de ser efêmera: vira entidade consultável, versionada por reconciliação, assinada.
- Re-rodar a IA nunca destrói o trabalho do consultor (edição/ordem/classificação/manual).
- "IA propõe, humano decide e assina" fica materializado na tela (reordenar/classificar/validar/
  fechar) e no banco (hash chain no fechamento).
- Honestidade preservada: passo sem fonte aparece marcado, não escondido.

**Negativas / limites**
- A rota reflete `demand_type`, não os passivos — enquanto o elo `auditor → legislacao` não for
  religado (dívida #50), ela não é a somatória das Ações (Ficha §3.5).
- Reconciliação aditiva: refino de conteúdo da IA em passo de mesmo título não é auto-aplicado
  (o primeiro conteúdo materializado vale) — decisão consciente de "nunca sobrescrever".
- Sem documento formal da rota em Saídas ainda (dívida #49 — exige template novo no Redator).

## Alternativas descartadas

- **(a) Ler o `etapas` bruto top-level** — descartado: quebra o schema strict e perde
  `sources`/`prazo_fonte`. Reconstruímos o típado.
- **(b) Regenerar a rota do zero a cada run** — descartado: apagaria edição/ordem/classificação
  do consultor. O snapshot é editável e a reconciliação é aditiva.
- **(c) `@dnd-kit` para reordenar** — descartado: `framer-motion` (já instalado, já no chunk
  `ui`) tem `<Reorder>` suficiente para lista plana; evita dependência nova.
- **(d) Enforçar "nenhum passo sem norma" na geração** — descartado: bloquear passos do LLM é
  frágil; a validação humana é o ponto certo de reconhecimento (radar-não-cancela).
