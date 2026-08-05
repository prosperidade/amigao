# Baseline da remediação do chunking (04/08)

Estado do corpus **antes** de qualquer mudança no chunker. É contra estes números
que a remediação (#117, #118, #119) será medida, e só contra eles: baseline e
pós-remediação **só se comparam sobre fingerprints iguais**.

## Fingerprint exigido

| campo | valor |
|---|---|
| `total_chunks` | **31.298** |
| `legislation_documents` | **102** |
| espaço vetorial | `text-embedding-3-small`, 768d, provider `openai` |
| `ivfflat.probes` | 10 |

O portão é **igualdade exata**, não piso. Piso protege contra banco *parcial*;
não vê corpus *poluído*. Em 04/08 o corpus chegou a 31.718/113 por uma ingestão
de outro agente (depois revertida) — um piso teria deixado a medição correr e
produzido um baseline incomparável, e o defeito só apareceria semanas depois, na
comparação que deveria provar o ganho.

Cada json grava `fingerprint_inicio` e `fingerprint_fim`; divergência entre os
dois invalida a rodada e o arquivo não é escrito.

### O portão pegaria o caso sozinho

Registro de validação, não crédito ao observador: no dia da medição o vigia que
eu escrevi para esperar o corpus limpo estava quebrado e **nunca poderia
disparar** (#123). Se eu tivesse rodado a medição completa confiando nele, o
portão de igualdade a teria recusado por conta própria, com a divergência
impressa. O instrumento estava certo; o observador é que não estava. Foi
verificado nos dois sentidos antes de valer: recusa a medição completa fora do
estado, e libera o dry-run só-leitura com aviso.

## As 5 perguntas

Escolhidas pelo **estado atual do alvo**, não por conveniência: três devem
melhorar, uma **não pode piorar**, uma é de outra esfera.

| chave | esfera | alvo | por que está aqui |
|---|---|---|---|
| `defesa` | federal | Decreto 6.514/2008, art. 18 | série histórica (desde o pacote A) |
| `car` | federal | *sem alvo* | série histórica (desde o bloco 2) |
| `art61a` | federal | Lei 12.651/2012, art. 61-A | hoje **partido em pedaços** |
| `art71` | federal | Lei 9.605/1998, art. 71 | **controle negativo** — hoje íntegro |
| `compensacao_rl_go` | **estadual GO** | conjunto de 7 normas | única estadual; tema espalhado |

`art71` existe porque um experimento só com casos que devem melhorar **não
detecta regressão**. Se a remediação quebrar o que já estava certo, é aqui que
aparece.

`car` fica **sem alvo, com a razão gravada**: a norma procedural do CAR (IN MMA
2/2014) não está ingerida. Um alvo aqui mediria ausência de corpus e a debitaria
do chunking — atribuiria a causa errada. Campo no json:
`reavaliar_apos="ingestao_normativas_federais"`.

## O conjunto de GO — 7 identificadores

Compensação de Reserva Legal em GO não tem "a norma": o tema está espalhado. O
alvo é o conjunto, e cada item vem do identificador **real** gravado no catálogo:

```
Coletânea Regularização Ambiental GO 2024
IN SEMAD 3/2025
Coletânea Licenciamento GO 2020+
Lei GO 21.231/2022
IN SEMAD-GO 01/2024
Portaria SEMAD-GO 501/2024
7841 - Y1.2
```

**Aceite:** ≥1 chunk de qualquer norma do conjunto no top-8.

**Uma oitava linha foi excluída, e a razão fica no json** (`alvo.excluidos`): o
chunk 25771 tem `identifier` nulo e é o *"Termo de Referência — Compensação
Ambiental por Doação de Imóvel em Unidade de Conservação"*. Trata de **compensação
ambiental do SNUC** — instituto diferente de compensação de Reserva Legal; casou
apenas por compartilhar a palavra "compensação". Mantê-la afrouxaria o aceite,
que poderia "passar" devolvendo documento de outro tema.

## Duas métricas, que não se misturam

**Estrutural (offline).** Conta sobre o chunker rodado no texto: em quantos
pedaços um dispositivo vira, tamanho da maior fatia, distribuição. Não depende do
índice — por isso é medível **a cada fase**.

**Recuperação (só depois da reindexação).** O que a busca devolve, com que
similaridade, quais dispositivos entram e saem do top-8. O índice só muda na
reindexação única da Fase 4; medir recuperação antes disso seria medir o índice
velho e chamar de resultado.

## Classificação do alvo

Três estados, porque dois deles produzem o **mesmo sintoma** (o agente não cita a
norma) com causas opostas:

- `recuperado`
- `falha_de_recuperacao` — existe no corpus e ficou de fora do top-k. Resolve-se
  em chunking/índice. O json grava **onde ficou**: posição no ranking e
  similaridade.
- `ausencia_de_corpus` — não está lá. Resolve-se ingerindo.

Sem essa separação, ausência de corpus leva a culpa de falha de recuperação — ou
o contrário.

## Os números (04/08, corpus 31.298/102, probes=10)

### Recuperação — top-8 por pergunta

| pergunta | fragmentos no top-8 | identificadores | alvo | situação |
|---|---:|---:|---|---|
| `defesa` | **5 / 8** | 4 | Decreto 6.514/2008, art. 18 | **`falha_de_recuperacao`** |
| `car` | 0 / 8 | 3 | — | sem alvo (norma não ingerida) |
| `art61a` | **4 / 8** | 3 | Lei 12.651/2012, art. 61-A | `recuperado`, **como fragmento** |
| `art71` | 0 / 8 | 4 | Lei 9.605/1998, art. 71 | `recuperado`, **íntegro** |
| `compensacao_rl_go` | 0 / 8 | 4 | conjunto de 7 normas | aceite **atendido** |

### O que a remediação precisa reverter

**`defesa` — o art. 18 do Decreto 6.514/2008 existe e não é recuperado.**
2 chunks no corpus; o que carrega o dispositivo fica na **posição 32**, com
similaridade **0,6686**, fora do top-8. Não é ausência de corpus: é falha de
recuperação, e é o número que a Fase 4 tem de mover.

**`art61a` — o artigo está partido em 7 pedaços.** É recuperado, mas **como
fragmento**: 4 dos 8 trechos do top-8 são pedaço de dispositivo. O consultor
recebe o art. 61-A em cacos.

**`art71` — controle negativo, hoje íntegro.** 1 chunk, 0 pedaços, recuperado
inteiro, 0 fragmentos no top-8. **Se isto piorar, a remediação regrediu.**

**`compensacao_rl_go` — o conjunto responde.** 2.409 chunks no corpus casam a
união; 5 dos 8 do top-8 são do conjunto: IN SEMAD 3/2025 (#1, 0,7313), Coletânea
Licenciamento GO 2020+ (#2 0,7282, #5 0,7276, #7 0,7098) e Coletânea
Regularização GO 2024 (#8, 0,6998). Zero fragmentos — o problema aqui não é
corte, é **dispersão entre coletâneas** (#121).

### Proveniência da fundamentação — uma ressalva que fica no dado

| pergunta | modelo efetivo | = pedido | tentativas | fallback | `finish_reason` |
|---|---|:--:|--:|--:|---|
| `defesa` | **`gpt-4.1-mini`** | **não** | 2 | **1** | stop |
| `car` | `gemini/gemini-2.5-flash` | sim | 0 | 0 | stop |
| `art61a` | `gemini/gemini-2.5-flash` | sim | 1 | 0 | stop |
| `art71` | `gemini/gemini-2.5-flash` | sim | 0 | 0 | stop |
| `compensacao_rl_go` | `gemini/gemini-2.5-flash` | sim | 1 | 0 | stop |

Nenhuma resposta truncada (`finish_reason=stop` nas cinco).

**A `defesa` foi respondida por outro modelo, e isso é reprodutível:** duas
rodadas seguidas, dois timeouts do `gemini-2.5-flash` em cada, fallback para
`gpt-4.1-mini` nas duas. É também a pergunta de **maior contexto** — a que mais
carrega trechos recuperados.

Consequência para o experimento: a camada de **fundamentação** da `defesa` não
satisfaz a condição "mesmo modelo" e **não entra** na comparação modelo-a-modelo
do antes/depois. As métricas de **recuperação** dela valem integralmente — busca
vetorial não passa pelo LLM.

O timeout reprodutível no maior contexto é sinal operacional, não ruído de
laboratório: ver #124.

## Previsões registradas ANTES de remediar

Previsão feita depois do resultado não é previsão. Estas ficam gravadas no
commit do baseline para poderem ser conferidas — e para poderem estar erradas.

**1. A Fase 1 NÃO deve mover `compensacao_rl_go`.** Aquela pergunta tem **zero
fragmentos** no top-8: o problema dela não é corte de dispositivo (#117), é
**dispersão entre coletâneas** (#121). Se a Fase 1 mover essa pergunta, **não é
para comemorar** — é sinal de que entendemos errado uma das duas dívidas, e a
investigação vem antes de qualquer festejo.

**2. `art71` é controle negativo, e reprova a fase sozinho.** Hoje: íntegro
(1 chunk, 0 pedaços), recuperado inteiro, 0 fragmentos no top-8. O aceite da
Fase 1 **inclui obrigatoriamente** que ele continue íntegro e continue
recuperado. **Regressão nele reprova a fase, mesmo com ganho em todas as
outras.**

**3. Os dois alvos a bater.** O art. 18 do Decreto 6.514/2008 sai da **posição
32 (0,6686)** e entra no top-8. O art. 61-A do Código Florestal deixa de vir em
cacos — hoje **partido em 7**.

## Achados do levantamento (não entram na remediação em curso)

Medidos ao construir este baseline, registrados em `docs/REGISTRO_DIVIDAS.md`:

- **#120** — 245 chunks sem `identifier`, em 51 documentos de GO. Recuperável,
  mas não citável nem conferível.
- **#121** — o mesmo texto normativo sob identidades diferentes: 4.821 grupos,
  9.890 chunks redundantes, 2.013 grupos com ≥200 tokens. **O mais grave do
  dia**: devolve o trecho certo com a fonte errada, e isso passa na conferência.
- **#122** — ligaduras tipográficas (`ﬁ`/`ﬂ`) em 2.091 chunks. **Entra na mesma
  passada da reindexação da Fase 4** — se o texto vai ser reescrito de qualquer
  forma, é aqui que a troca sai de graça.

  > **Correção de 05/08 — a frase original desta linha foi REFUTADA por
  > medição.** Estava escrito *"mascarou a #121 inteira do dedup por
  > `content_hash`"*, e daí se concluía que reindexar sem normalizar produziria um
  > antes/depois contaminado. Medido: **4.530 grupos de texto idêntico antes da
  > normalização, 4.529 depois** — as duplicatas já eram byte-idênticas. O que as
  > esconde é o **desenho do hash** (`_hash_chunk` inclui `source_ref`, então
  > documentos diferentes nunca colidem), não a ligadura.
  >
  > A afirmação era **inferência apresentada como medição** — o defeito que a
  > #123 descreve, cometido no documento que a registra. O escopo real da #122 é
  > menor e de outra natureza: atrapalha **comparação literal e busca por termo**
  > (quem procura `fins` não acha `ﬁns`), não dedupe. Também mudou o **como**:
  > NFKC foi descartado por converter `º`→`o` em 18.362 chunks; a troca é
  > cirúrgica, só ligaduras. Detalhe em `docs/REGISTRO_DIVIDAS.md` #122.
  >
  > Consequência para esta Fase 4: como o `content_hash` inclui `source_ref`, a
  > reindexação **não deduplica por acidente** — garantia estrutural, não
  > disciplina de quem executa. A #121 continua aberta e intocada.
- **#123** — regra: silêncio não é evidência de ausência.

---

## Anotação de 05/08 — o que a Fase 4 mudou neste documento

Este arquivo **não foi reescrito**: baseline é artefato do que aconteceu,
incluindo o que foi refutado depois (#123). O que segue é anotação.

**O fingerprint de partida acima (31.298 / 102) vale para o baseline.** Depois da
reindexação da Fase 4 ele muda, e a previsão foi declarada **antes** de executar,
a partir do dry-run:

| | baseline (2e78917) | previsto pós-Fase 4 |
|---|---:|---:|
| chunks de legislação | 30.104 | **28.971** |
| outras fontes (SEMAD etc.) | 1.194 | 1.194 |
| **total `knowledge_catalog`** | **31.298** | **30.165** |
| `legislation_documents` | 102 | 102 |

O portão do medidor foi atualizado para 30.165 **antes** da execução. Bater
confirma a previsão; não bater é **achado** — reportar e parar, nunca ajustar a
constante para caber no observado. Preencher com o resultado faria o portão
deixar de medir e passar a refletir.

**Custo:** o dry-run estimou **US$ 0,1852** (9.259.633 tokens a US$ 0,020/1M),
contra os ~US$ 0,58 previstos na abertura da frente. A estimativa antiga fica
registrada como divergência **sem procedência conhecida** — não foi investigada.
