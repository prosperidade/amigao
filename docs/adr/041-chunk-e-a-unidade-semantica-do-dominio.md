# ADR-041 — O chunk é a unidade semântica do domínio, não uma janela de tokens

- **Status:** aceita
- **Data:** 2026-08-04
- **Branch:** `feat/chunking-estrutural`
- **Decisão de domínio:** André, na remediação do chunking
- **Correlatas:** dívidas #117 (material não articulado), #118 (teto), #119
  (estrutura da norma como dado), #121 (atribuição), #122 (ligaduras),
  #126 (documentos não articulados); ADR-034 (esfera pelo órgão), ADR-036
  (identidade da norma)

## Contexto

O chunker cortava por marcador estrutural e, quando a fatia passava de
`MAX_TOKENS = 1500`, caía em janela deslizante. Aquele 1.500 nunca foi limite de
modelo — **foi escolha nossa**, e ela partia artigo ao meio.

**Medido em 04/08** sobre 24.577 fatias de artigo em 102 documentos
(`legislation_documents`; equivale a `knowledge_catalog WHERE
source_type='legislation'`, 30.104 chunks — **não** ao catálogo inteiro, que tem
31.298):

| percentil | tokens |
|---|---:|
| p50 | 129 |
| p90 | 499 |
| p95 | 737 |
| p99 | 2.144 |
| p99,9 | 23.483 |
| máximo | 261.280 |

**4.935 chunks** eram pedaço de artigo cortado por tamanho.

## O problema com os dois extremos

**Chunk grande demais dilui.** O vetor de um trecho longo é um ponto que
representa **tudo vagamente** — e perde justamente o dispositivo específico, que
é o que a peça cita. Uma busca por *"prazo de defesa do auto de infração"* não
encontra o artigo que trata disso se ele estiver dissolvido em 7.000 tokens de
matéria variada.

**Chunk pequeno demais parte o dispositivo.** O consultor recebe metade do
art. 61-A, e a metade que ficou de fora é a que continha a condição.

## Decisão

**O tamanho certo é a unidade semântica do domínio: o artigo.**

Não é um número escolhido por conveniência de infraestrutura — é o recorte que o
próprio direito usa. A peça cita artigo, o auto de infração enquadra artigo, a
defesa rebate artigo. O corpus deveria guardar artigo.

**1. Teto próprio para artigo.** `MAX_ARTIGO_TOKENS = 7000`. Precisam caber
inteiros, medidos: **4.644** (art. 61-A do Código Florestal), **5.578** (art. 100
da CF) e **6.289** (art. 19 da Lei 6.938). O valor cobre os três com folga e fica
abaixo do limiar da guarda de sanidade (8.000).

**2. O teto ampliado vale SÓ para artigo.** Capítulo, seção e prelúdio seguem em
`MAX_TOKENS = 1500`. Para eles, 7.000 tokens num chunk só não é "dispositivo
inteiro" — é exatamente a diluição descrita acima. Subir o teto de todo mundo
resolveria o corte de artigo criando dissolução em toda parte.

**3. Teto é limite, não alvo.** Chunk pequeno continua pequeno: a mediana caiu de
172 para **163** tokens, e p90/p95 permanecem em 800. O que mudou foi o extremo,
não o corpo da distribuição.

**4. Corte por tamanho continua existindo, como ÚLTIMO recurso, e deixa rastro.**
Quando um artigo ainda assim excede o teto, ele é cortado — e isso é **logado**.
Sem o log, um dispositivo partido ao meio some do radar: a busca devolve meio
artigo e ninguém fica sabendo que houve corte.

**5. A ordem das fases não é conveniência — é pré-requisito de correção.** A
guarda de sanidade (#117) tinha de vir **antes** do teto (#118): subir o teto com
fatias absorvedoras ainda rotuladas como artigo transformaria cada absorvedor num
único blob gigante com etiqueta falsa, piorando dilução e recuperabilidade ao
mesmo tempo. Medir depois de remediar mede o remédio; remediar fora de ordem
produz número que não se sabe do que é.

## Resultado medido

| métrica | antes | Fase 1 (guarda) | Fase 2 (teto) |
|---|---:|---:|---:|
| chunks totais | 30.104 | 30.104 | 28.971 |
| com rótulo de artigo | 28.960 | 25.580 | 24.454 |
| com rótulo honesto | 0 | 3.380 | 3.380 |
| **de artigo PARTIDO por tamanho** | **4.935** | 1.555 | **67** |
| p50 / p90 / p95 do chunk | 172 / 800 / 800 | 172 / 800 / 800 | **163 / 800 / 800** |
| máximo | 1.498 | 1.498 | 6.963 |

## Consequências

- Vale na **próxima passada de índice**. Nenhuma reindexação foi feita nestas
  fases: haverá **uma só**, no fim, junto com a normalização Unicode (#122) —
  reindexar sobre texto não normalizado mediria o pós-remediação com as ligaduras
  ainda mascarando comparação de string.
- O controle negativo do baseline continua valendo: o art. 71 da Lei 9.605 é
  íntegro (180 tokens) e tem de continuar íntegro e recuperado. Regressão nele
  reprova a fase, mesmo com ganho nas outras.
- **Efeito colateral medido e não resolvido:** dos 362 chunks de artigo acima de
  1.500 tokens, **81 são absorvedores de vigência abaixo do limiar de 8.000**
  (247.408 tokens somados) — agora blobs únicos em vez de vários pedaços. Menos
  rótulos mentirosos, porém mais diluição naquele material. O sinal que os pegaria
  é semântico, não de tamanho (o artigo de vigência tem p50 = 273 e p75 = 519
  tokens), e pertence à família da #126 — classificação na entrada.

## Alternativas descartadas

- **Subir `MAX_TOKENS` para todos.** Resolveria o corte de artigo e criaria
  diluição em capítulo, seção e prelúdio.
- **Manter 1.500 e aceitar o corte.** É a situação que a #118 registra: 4.935
  chunks de artigo partido, e o dispositivo específico — o que a peça cita —
  espalhado entre pedaços.
- **Escolher o teto pelo limite de contexto do modelo.** Mede a infraestrutura,
  não o domínio. O artigo não fica maior nem menor porque trocamos de provider.
