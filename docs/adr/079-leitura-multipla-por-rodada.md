# ADR-079 — Leitura múltipla por rodada

**Status:** aceito (André, 24/09/2026: N = 2) · **Data:** 24/09/2026 · **Estende:** ADR-078 (releitura não supera o que não reencontra) · **Dívida relacionada:** #286

## Contexto

O ADR-078 mediu a variância do extrator: com o Luna em temperatura 1, **~41% dos
fatos aparecem em só uma de três leituras** do mesmo texto, nos dois modelos
testados. O modelo não erra o mesmo fato de jeitos diferentes: ele **lê
subconjuntos diferentes** do mesmo documento. A resposta do ADR-078 foi não
perder evidência entre leituras — o que a releitura não reencontra fica corrente
e marcado para o consultor. O preço medido: ~30% da leitura anterior vai para a
tela a cada releitura.

Se uma leitura só vê parte do que o modelo consegue ver, ler mais de uma vez e
publicar a união cobre mais do documento, e as rodadas seguintes passam a
comparar uniões — mais estáveis que leituras soltas.

## Decisão

Proposta ao André, 24/09/2026 (pedido: "2–3 leituras, união com dedupe do
ADR-078, 'não reencontrada' só entre rodadas").

1. **Rodada.** Uma extração do documento passa a ser uma rodada de **N leituras**
   completas (fatiar, chamar, ancorar, validar, reparar — ADR-077 inteiro em cada
   uma). N vem de `AI_EXTRATOR_LEITURAS_POR_RODADA` (1 a 3). **N = 2 por decisão
   do André (24/09)**, sobre a medição abaixo: custo e tempo dobram. O modelo segue
   `gpt-5.6-luna`.
2. **União com o dedupe do ADR-078.** Dois itens de leituras diferentes são o
   mesmo fato pela mesma regra do reencontro: mesmo tipo e discriminante, trechos
   sobrepostos e, para observação, mesmo predicado **ou** mesmo valor lido
   (`app/services/leitura_multipla.py`). Dois itens da **mesma** leitura nunca se
   fundem — a leitura já os distinguiu.
3. **O que só uma leitura viu entra.** Cada item publicado leva
   `leituras_na_rodada` (`{"viram": k, "de": N}`), mostrado na tela de
   conferência ("vista em 1 de 3 leituras da rodada"). É apoio, não valor: não
   entra na comparação de valor do reencontro.
4. **Valor divergente dentro da rodada.** Quando leituras casam o mesmo fato com
   valores diferentes, publica-se o da leitura mais antiga e a divergência vai ao
   relatório da extração (`rodada.valor_divergente`). A máquina não escolhe o
   valor "certo".
5. **Referências entre itens.** As chaves que o modelo inventa (`parte_chave`,
   `sujeito`...) ganham o prefixo da leitura (`l2:`); parte fundida numa de
   leitura anterior passa a ser referida pela chave do representante.
6. **"Não reencontrada" só entre rodadas.** Dentro da rodada nada é marcado. O
   ADR-078 vale entre a rodada nova e a anterior: o que a união nova não
   reencontra da anterior fica corrente e marcado.
7. **Leitura que falha não derruba a rodada.** Vai ao relatório
   (`rodada.falhas`) e a rodada publica a união das que concluíram; sem nenhuma,
   o erro sobe. O teto acumulado por job (#272) vale para a rodada inteira.
8. **O caso inteiro não é lido num job só.** Execução do extrator sem
   `document_id` (`/agents/run`, cadeias `diagnostico_completo` e
   `enquadramento_regulatorio`) abre um passo do extrator por documento com texto —
   job e teto próprios, como a fila da #279. O teto por job **não muda** (André,
   24/09).

O relatório da extração (`extracao:rejeicoes:<doc>`, `method_version` 071.5)
ganha `rodada`: leituras pedidas e concluídas, itens por leitura, união, em
todas, só em uma, divergências e falhas.

## Medição (dev, 24/09)

Seis leituras independentes, por modelo, do CAR e das quatro matrículas da
ELODI (#23), sem gravar: as três do ADR-078 e mais três, mesmo código.
`scripts/medir_rodada.py` monta as rodadas como combinações dessas leituras
(k = 1: 6 rodadas; k = 2: 15; k = 3: 20) e usa a regra do produto
(`leitura_multipla.mesmo_fato`). Nenhuma chamada nova para montar as rodadas.

**Sem gabarito, a cobertura é relativa**: a referência é tudo o que o modelo viu
nas seis leituras agrupadas (gpt-5.6-luna: 1.390 fatos; gpt-6-luna: 912) e o
subconjunto visto por pelo menos duas delas (900; 600), menos sujeito a leitura
espúria. A referência de um modelo não é a do outro: as colunas não comparam
acerto entre modelos.

### Cobertura, custo e tempo por rodada (caso ELODI: CAR + 4 matrículas)

| Modelo | Leituras por rodada | Itens publicados | Cobertura (tudo o que o modelo viu) | Cobertura (visto por 2+ leituras) | Custo por rodada do caso | Tempo sequencial do caso | Maior documento, sequencial |
|---|---|---|---|---|---|---|---|
| gpt-5.6-luna | 1 | 731 | 0,526 | 0,721 | US$ 0,33 | 2.510 s | 887 s |
| gpt-5.6-luna | 2 | 960 | 0,687 | 0,879 | US$ 0,66 | 5.020 s | 1.773 s |
| gpt-5.6-luna | 3 | 1.108 | 0,793 | **0,952** | US$ 0,99 | 7.529 s | 2.660 s |
| gpt-6-luna | 1 | 497 | 0,545 | 0,736 | US$ 0,11 | 2.035 s | 765 s |
| gpt-6-luna | 2 | 649 | 0,710 | 0,894 | US$ 0,21 | 4.070 s | 1.530 s |
| gpt-6-luna | 3 | 745 | 0,815 | **0,960** | US$ 0,32 | 6.105 s | 2.295 s |

- **Uma leitura vê cerca de metade do que o modelo consegue ver**, e perde ~27%
  até do que duas leituras concordam. Com 2 leituras, ~88% do que é visto por
  2+; com 3, ~95%. Nessa coluna, a 2ª leitura acrescenta ~0,16 e a 3ª, ~0,07.
- Custo e tempo são lineares em N. O tempo é o da soma das leituras (nesta
  medição elas correram em processos paralelos; no produto, em sequência).
- O gpt-6-luna com 3 leituras publica o mesmo volume que o gpt-5.6-luna com 1
  (745 × 731 itens) pelo mesmo custo (US$ 0,32 × 0,33) — **mesmo volume não é
  mesma cobertura nem mesmo acerto**; só o gabarito responde isso.

### O que vai para a tela entre rodadas

Rodadas com leituras disjuntas, uma depois da outra: a fração da união da
rodada anterior que a nova **não** reencontra (regra 6 → ADR-078):

| Modelo | k = 1 | k = 2 | k = 3 | Não reencontradas por releitura do caso (k = 1 → 3) |
|---|---|---|---|---|
| gpt-5.6-luna | 30,6% | 26,2% | 24,4% | 224 → 251 → 270 |
| gpt-6-luna | 30,0% | 25,3% | 24,0%¹ | 149 → 164 → 147¹ |

¹ sem a matrícula 3.673 (duas leituras falharam; ver abaixo, sobram 4 e não há
duas rodadas disjuntas de 3).

**A fração cai, o volume não.** A união cresce mais do que a marca encolhe; a
tela não fica mais leve só por ler mais vezes. Mas a marca se concentra no
apoio:

| Apoio do item na rodada anterior | não reencontrado (k = 2) | não reencontrado (k = 3) |
|---|---|---|
| visto por 1 leitura | 47,5% (5.6) · 46,2% (6) | 50,7% (5.6) · 50,6% (6) |
| visto por 2+ leituras | **7,2%** (5.6) · **7,3%** (6) | **6,8%** (5.6) · **6,7%** (6) |

Um fato que duas leituras viram quase sempre volta (93%); o que uma só viu some
em metade das rodadas seguintes. O apoio `k de N` separa, na tela, a marca que
merece atenção (o fato firme que sumiu) da que é a variância de sempre — é o
critério natural para a decisão em lote da #286 — confirmado pelo André (24/09):
a não reencontrada vista por 2+ leituras fica mantida; a vista por uma só vai
para a decisão em lote.

### Falhas

- gpt-6-luna: **2 de 30** leituras de documento falharam, as duas na matrícula
  3.673: uma fatia devolveu JSON inválido (`Invalid \escape`, `Invalid control
  character`) e a leitura inteira do documento caiu (dívida #287). Com N = 1 isso
  é extração falha; numa rodada, a leitura sai e a rodada publica as outras. O
  custo dessas leituras falhas não foi contado (as chamadas feitas antes da falha
  se perdem com a exceção).
- gpt-5.6-luna: 0 de 30. Nos dois: 0 fallback, 0 truncada.

### Teto de custo

O teto por job do extrator é US$ 0,75 (#272). Por documento (a fila lê um por
tarefa, #279), a matrícula mais cara custa ~US$ 0,12 por leitura no 5.6: N = 3 ≈
US$ 0,39, dentro. **A extração do caso inteiro num job só** (sem `document_id`)
custa US$ 0,99 com N = 3 no 5.6 e seria recusada no meio pelo teto. Decisão do
André: teto inalterado, o caso inteiro passa a ser um passo por documento
(regra 8).

## Consequências

- A cobertura de uma extração deixa de ser a sorte de uma leitura.
- Custo e tempo por documento multiplicam por N. O tempo é sequencial nesta
  versão (as leituras não correm em paralelo: a sessão de banco é uma só).
- O apoio por item (`k de N`) é o primeiro sinal de confiança da leitura que o
  consultor vê. Não é acerto: sem gabarito, um fato visto por uma leitura só pode
  ser o que as outras perderam ou uma leitura espúria.
- A dívida #287 (JSON inválido derruba a leitura do documento) pesa menos numa
  rodada — a leitura falha sai —, mas continua sendo dívida com N = 1.
- O gabarito da Ísis (matrícula 3.181 e CAR do #23) transforma esta medição de
  cobertura relativa em acerto: quanto da união é certo, quanto do certo a
  união contém.
