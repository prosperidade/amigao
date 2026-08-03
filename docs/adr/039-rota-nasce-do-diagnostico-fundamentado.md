# ADR-039 — A rota nasce do diagnóstico fundamentado e das ações validadas

- **Status:** aceita
- **Data:** 2026-08-03
- **Contexto:** validação da Isis de 02/08 (item 0) · dívida #102
- **Substitui:** nada. **Corrige:** a implementação da E5, que divergia da Ficha 07.

> **Nota de numeração.** Esta ADR nasceu como 038 e virou 039 no merge: o
> PR #131 (corpus dirigido por manifesto curado) chegou à `main` primeiro e
> ficou com o 038. Dois agentes escrevendo no mesmo repositório leram o
> "próximo livre" ao mesmo tempo. Quem chega depois renumera — ADR é
> referência citável e não pode ter dois donos.

---

## O problema

A consultora perguntou, olhando a tela:

> *"A rota traçada na E5 se direciona pelas ações definidas na E4?"*

A resposta medida foi **não** — e pior do que a pergunta supunha.

`materialize_rota` montava o contexto do agente **sem `chain_data`**
(`rota_materializer.py:258-264`), e a `LegislacaoAgent` consumia apenas:
`demand_type`, campos do imóvel, o corpus (RAG), os órgãos derivados de
documentos de fiscalização, e o texto livre `process.initial_diagnosis`.

`Acao` e `RegulatoryDiagnosis`/`RegulatoryIssue` tinham **zero ocorrências** no
caminho da rota.

E `initial_diagnosis` não é o diagnóstico do caso: é escrito **só no intake**
(`app/api/v1/intake.py:85,242,457`) e a própria coluna se declara
*"pré-diagnóstico por regras"* (`app/models/process.py:132`). O `DiagnosticoAgent`
lê esse campo e nunca escreve de volta.

**Consequência:** a rota — que a Ficha 07 chama de "a entrega de valor" — era
desenhada a partir do que o **cliente contou no minuto 1**, não do que o
**sistema apurou**. Tudo que a consultora construiu da E2 à E4 (achados
confirmados, divergências reconciliadas, ações refinadas) passava ao largo.

## A Ficha 07 já mandava o contrário

- **§8.1:** *"Desenhada pela Legislação a partir do **diagnóstico fundamentado** +
  a base legal consolidada (que mapeia a ordem)."*
- **§5:** E4 *"Ações: refinadas e finais"* → E5 *"a aba Ações assume a forma de
  rota"* — é a mesma aba se transformando.

Não houve mudança de requisito. **A implementação divergiu do desenho** e ninguém
percebeu porque o resultado era plausível: uma rota genérica da demanda parece
uma rota.

## A decisão

### 1. O insumo da rota passa a ser o diagnóstico fundamentado + as ações triadas

`app/services/rota_contexto.py` monta o contexto e o materializer o injeta no
prompt. Entram:

- a **versão assinada** mais recente do `RegulatoryDiagnosis`, com as
  `afirmacoes` e suas fontes (contrato #70);
- os **achados que dirigem a rota** (ver filtro abaixo);
- as **ações triadas** — `tipo_triagem ∈ {tarefa, escopo}`. Ficam de fora
  `pendente` (a IA propôs e ninguém olhou) e `dispensada` (o consultor disse não).

### 2. `muda_rota_regulatoria` é o filtro — porque o domínio já o tinha

O campo existe desde o PROMPT_5, no catálogo (default por código de alerta,
curadoria da Isis) e na `RegulatoryIssue` (override do caso). O
`AuditorImovelAgent` **escreve** o campo. E **ninguém o lia para decidir nada**.

Inventar heurística nova para "quais achados mudam a rota" seria reimplementar,
com critério pior, uma decisão de domínio já tomada. A hierarquia, da mais forte
para a mais fraca:

| # | Camada | Por quê vence |
|---|---|---|
| 1 | `ProcessIssueDecision` ∈ {`fora_escopo`, `ignorar_justificado`} | Declaração humana explícita sobre ESTE caso — Princípio 1 |
| 2 | `RegulatoryIssue.muda_rota_regulatoria` | Override sobre AQUELE achado naquele imóvel |
| 3 | `RegulatoryIssueCatalog.muda_rota_regulatoria` | Default do código de alerta |

Achado que **não** dirige a rota **não some**: entra como *contexto secundário*,
nomeado, para o agente não perder o quadro do caso. Só não vira passo.

Achado com código fora do catálogo entra como contexto, também nomeado — não dá
para afirmar que dirige a rota, e o silêncio seria pior que a dúvida declarada.

### 3. Proveniência: a corrente fecha

`RotaPasso` ganha `origem_issue_id` e `origem_acao_id`, ambos `SET NULL`,
espelhando `ProposalScopeItem.rota_passo_id` do S5-A. A corrente inteira passa a
ter FK em cada elo:

```
RegulatoryIssue → Acao → RotaPasso → ProposalScopeItem
```

O modelo declara a origem de cada passo em `origem_refs` (rótulos `ACHADO-<id>`
/ `ACAO-<id>` que o próprio prompt listou). Na materialização, **só referência
que casa com achado/ação REAIS deste caso é aceita**; o resto é descartado com
log. Passo sem origem é honesto; passo com origem inventada corromperia a
corrente inteira.

`NULL` é legítimo e frequente: passo manual do consultor, passo de rito, ou passo
anterior a esta ADR.

### 4. `initial_diagnosis` é rebaixado, não removido

Continua entrando no prompt — mas rotulado, em texto:

> *RELATO DO CLIENTE — NÃO CONFERIDO (pré-diagnóstico automático do intake,
> anterior a qualquer apuração). Use no máximo para entender a intenção; NUNCA
> como fundamento de passo, prazo ou norma.*

Ele ainda carrega a intenção do empreendedor, que é informação real. O que muda é
o **estatuto**: contexto, nunca fundamento.

### 5. Guard: sem diagnóstico assinado, não há rota

`DiagnosticoNaoFundamentado` bloqueia a geração e vira **409** com a frase inteira
na tela — distinguindo os dois "nãos", porque o próximo movimento é diferente:

- *não existe diagnóstico* → "rode os agentes do Diagnóstico Técnico e assine";
- *existe mas não assinado* → "assine-o na Visão geral" (Princípio 1: a rota é
  peça formal, não pode nascer de leitura não validada).

Não é 502: seria mandar o consultor procurar defeito onde só falta um passo dele.

### 6. Reconciliação: sinaliza, nunca regenera

Achado que passa a dirigir a rota **depois** de ela ter sido traçada (documento
novo, decisão nova, override novo) **não regenera nada e não apaga nada**.
`fundamento_mudou_desde_a_rota` devolve uma frase e a tela mostra *"a rota pode
estar desatualizada — regenerar?"*. Quem decide é quem assina.

Regenerar sozinha apagaria classificação, ordem e passos manuais por causa de um
evento que o consultor talvez nem tenha visto — e o versionamento (#126) protege
o trabalho, mas proteger não é desculpa para destruir.

Guarda-corpo contra alarme falso: se **nenhum** passo da rota tem proveniência,
ela é anterior a esta ADR e o aviso não dispara. Do contrário todo caso legado
acusaria "desatualizada" para sempre — o tipo de alarme que se aprende a ignorar.

## Consequências

**Ganhos.** A rota passa a responder "de onde veio este passo?" com FK, não com
prosa. O consultor deixa de receber roteiro genérico da demanda. E a decisão de
domínio da Isis (`muda_rota_regulatoria`) finalmente é lida por alguém.

**Custos, ditos por inteiro.**

- **A E5 fica mais dura.** Casos sem diagnóstico assinado que antes geravam rota
  agora são bloqueados. É o ponto — mas é atrito novo, e vai aparecer.
- **Depende do LLM declarar a origem.** Ele pode omitir `origem_refs`; nesse caso
  o passo nasce sem proveniência em vez de errado. Preferimos o buraco à mentira.
- **Passos legados ficam sem origem para sempre.** Backfill seria inventar
  proveniência — exatamente o que a coluna existe para impedir.
- **Um achado pode ficar sem passo.** O prompt pede que cada achado que dirige a
  rota seja endereçado, mas pedido não é garantia. Por isso existe o aviso de
  reconciliação, que é justamente quem pega esse caso.

## Alternativas descartadas

**Heurística própria de "o que muda a rota"** (por severidade, por família).
Descartada: reimplementaria com critério pior uma decisão de domínio já curada.

**Bloquear também sem ações triadas.** Descartada: um caso pode legitimamente ter
achados e nenhuma ação triada, e a rota ainda é devida. O diagnóstico assinado é
o piso; as ações são enriquecimento.

**Regenerar a rota automaticamente quando o diagnóstico muda.** Descartada — ver
item 6. Contraria "a IA propõe; o humano decide e assina".

**Tabela de junção `rota_passo_origem` (N:N).** Descartada por ora: dois FKs
resolvem o caso real (um passo nasce de um achado e/ou de uma ação) sem uma
tabela a mais. Se aparecer passo com múltiplos achados, promove-se então.
