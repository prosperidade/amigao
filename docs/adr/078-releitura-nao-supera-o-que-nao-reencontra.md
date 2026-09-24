# ADR-078 — A releitura não supera o que não reencontra

**Status:** proposto · **Data:** 23/09/2026 · **Dívida:** #281 · **Altera:** ADR-070 (superação por nova extração)

## Contexto

Pelo ADR-070, uma nova extração do documento é uma nova versão, e a leitura
anterior é superada: toda observação que a nova leitura não produziu de novo era
invalidada (`superar`), saía do envelope e levava junto os dependentes.

Isso pressupõe que duas leituras do mesmo texto produzem o mesmo conjunto de
observações. Não produzem. O Luna só aceita temperatura 1, e a medição do
ADR-077 mostrou o CAR da ELODI indo de **20 para 5 observações** entre duas
leituras do mesmo texto. Com a superação automática, cada releitura apaga do
caso o que a leitura anterior viu e esta não viu — **perda de evidência por
variância do modelo**, sem ninguém decidir.

Há ainda um segundo efeito: a identidade da observação inclui as chaves que o
modelo inventa para ligar parte e participação (`"elodi"` numa leitura, `"p1"`
na outra). O mesmo fato, lido de novo, ganha identidade nova — e para a regra
antiga isso era "não reproduzida".

## Decisão

Decisão do André, 23/09/2026.

1. **Reencontrada** é o mesmo fato na nova leitura: mesmo tipo, mesmo
   discriminante (identificador da parte, rótulo do ato, papel, número do
   processo), trecho sobreposto na mesma versão do texto — ou o mesmo literal,
   quando a versão mudou — e, para observação, **mesmo predicado ou mesmo valor
   lido**. As chaves que o modelo inventa não entram. (Calibrado pela medição
   abaixo: exigir o predicado deixava de fora o rótulo trocado; dispensá-lo
   fundia fatos distintos da mesma frase.)
2. **Reencontrada é superada automaticamente** pela nova. O relatório da extração
   registra com qual observação ela foi reencontrada e se o **valor lido mudou**
   (`valor_diferente`). Com o valor igual, a superação não perde nada — o fato
   está na nova; sem ela, o mesmo fato ficaria em dobro, porque a identidade muda
   com a chave do modelo.
3. **Não reencontrada não é superada.** Continua corrente — no envelope, na
   qualificação do caso, com seus dependentes —, marcada **"não reencontrada na
   última leitura"** no relatório (`nao_reencontradas`) e na tela de conferência,
   e o documento pede revisão. **O consultor decide.** Decisão gravada tira a
   marca, e observação decidida nunca é superada pela máquina (como já era).
4. Observação que uma leitura posterior reencontrar deixa de estar marcada e
   passa pela regra 2.

## Medição (dev, 23/09)

Três leituras independentes do CAR e das quatro matrículas da ELODI (#23), por
modelo, **sem gravar** — `scripts/medir_releitura.py` usa `ler_documento`
(fatiar, chamar, ancorar, validar) e compara os itens validados por documento.

### A variância é grande, e metade dela é rótulo

| Critério de "mesmo fato" | gpt-5.6-luna: nas 3 / união | só em 1 leitura | gpt-6-luna: nas 3 / união | só em 1 leitura |
|---|---|---|---|---|
| mesmo predicado + trecho | 368 / 1.223 = 0,301 | 55% | 224 / 791 = 0,283 | 51% |
| só coleção + trecho | 453 / 780 = 0,581 | 26% | 300 / 539 = 0,557 | 24% |
| **predicado OU valor + trecho (regra adotada)** | **429 / 1.078 = 0,398** | **41%** | **248 / 725 = 0,342** | **41%** |

- Exigir o mesmo predicado conta como "sumido" o mesmo trecho com o mesmo valor
  e outro nome de predicado (`area_imovel` × `area_total_ha`).
- Dispensar o predicado funde fatos distintos da mesma frase: no gpt-5.6-luna,
  **292 de 485** pares de observação casados só pelo trecho tinham predicado **e**
  valor diferentes.
- Com a regra adotada, **~41% dos fatos aparecem em só uma de três leituras**, nos
  dois modelos. Isso não é rótulo: o modelo lê subconjuntos diferentes do mesmo
  texto.

### O que a regra põe na tela

Por releitura (cada leitura contra cada outra), a fração da leitura anterior que
a nova **não** reencontra — o que antes era superado em silêncio e agora fica
marcado para o consultor:

| Modelo | Marcadas por releitura (média) | CAR | 3.313 | 3.181 | 3.673 | 4.387 |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | **222 de 732 (30%)** | 8 de 15 | 52 de 204 | 80 de 242 | 34 de 136 | 48 de 135 |
| gpt-6-luna | **158 de 493 (32%)** | 2 de 6 | 48 de 147 | 39 de 145 | 26 de 94 | 43 de 101 |

## Comparação de modelos (dado, não decisão)

`gpt-6-luna` registrado na tabela local do LiteLLM (entrada copiada do mapa
oficial: US$ 0,10 / 0,50 por milhão, `openai`) **só para esta medição**. O padrão
do extrator segue `gpt-5.6-luna`; trocar é decisão do André.

| | gpt-5.6-luna | gpt-6-luna |
|---|---|---|
| Itens por leitura (CAR + 4 matrículas) | 738 · 741 · 717 | 485 · 493 · 500 |
| Estabilidade (nas 3 / união, regra adotada) | 0,398 | 0,342 |
| Custo de 3 leituras | US$ 0,9951 | **US$ 0,3424** |
| Tempo de 3 leituras (soma) | 7.582 s | 6.130 s |
| Fallback · truncadas | 0 · 0 | 0 · 0 |
| Timeouts transitórios (todas as rodadas) | 5, resolvidos na nova tentativa | 0 |
| #23 gravado: observações · chamadas · custo · tempo | 754 · 92 · US$ 0,3169 · 3.337 s | 462 · 71 · US$ 0,1006 · 2.504 s |
| #25 gravado: observações · chamadas · custo | 46 · 5 · US$ 0,0206 | 32 · 4 · US$ 0,0072 |
| **Seis provas de leitura** (tenant limpo, `scripts/provas_leitura.py`) | **6 de 6** | **6 de 6** |

O gpt-6-luna lê ~35% menos itens pelo mesmo texto, custa um terço e não teve
timeout; as seis provas passam nos dois. Menos itens não é, por si, pior nem
melhor: sem gabarito do documento, a medição diz quanto cada modelo lê e quão
estável é, não quanto acerta. O gpt-6-luna recusa `max_tokens` e exige
`max_completion_tokens`; o gateway passou a aprender essa recusa como já
aprendia a de temperatura.

## Consequências

- Uma releitura nunca diminui a evidência do caso sozinha. O que ela deixa de
  ver aparece para decisão.
- O caso acumula observações não reencontradas até o consultor decidir — **cerca
  de 30% da leitura anterior a cada releitura**, medido. É o custo explícito de
  não perder evidência por variância; uma decisão em lote na tela reduziria esse
  custo e fica como proposta.
- A superação passa a dizer **por que** aconteceu: reencontrada, com valor igual
  ou diferente.
