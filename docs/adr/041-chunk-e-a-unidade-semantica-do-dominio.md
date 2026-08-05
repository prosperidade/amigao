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

## Regra que a Fase 4 provou na prática

**Operação que substitui corpus é transação única — nunca delete-then-insert
commitado em etapas.**

Em 05/08 a reindexação abortou no primeiro documento (`UndefinedColumn:
dispositivo`, dívida #302). O `DELETE` de **30.104 chunks** e os `INSERT`s
estavam na mesma transação: a exceção subiu, a sessão fechou sem commit, e o
corpus voltou intacto — 31.298 / 102 / max id 188, conferido.

Escrito da forma "natural" — apagar, commitar, depois inserir — aquele mesmo erro
teria destruído o corpus, e a recuperação dependeria do backup. O backup existia
e estava verificado (114.408.164 bytes, 47 tabelas), **e não precisou ser usado**.

Backup é a última linha, não a primeira. A primeira é a transação.

## Alternativas descartadas

- **Subir `MAX_TOKENS` para todos.** Resolveria o corte de artigo e criaria
  diluição em capítulo, seção e prelúdio.
- **Manter 1.500 e aceitar o corte.** É a situação que a #118 registra: 4.935
  chunks de artigo partido, e o dispositivo específico — o que a peça cita —
  espalhado entre pedaços.
- **Escolher o teto pelo limite de contexto do modelo.** Mede a infraestrutura,
  não o domínio. O artigo não fica maior nem menor porque trocamos de provider.

---

## Adendo de 05/08 — a régua estava errada, não a direção

O corpo acima permanece: **o alvo do teto é do DOMÍNIO** — o artigo é a unidade
semântica, e é isso que decide o que deve caber inteiro. Isso não muda.

O que faltava é que existe uma **segunda restrição, da INFRAESTRUTURA, e ela não
se argumenta**: a API de embedding recusa qualquer entrada acima de **8.192
tokens**. Acima dela não há embedding, e sem embedding não há chunk. As duas
restrições valem ao mesmo tempo e não se substituem — o domínio diz o que
*deveria* caber; a API diz o que *pode*.

A Fase 4 descobriu isso do jeito difícil: a reindexação abortou com
`Invalid 'input[55]': maximum input length is 8192 tokens`.

### A premissa refutada

O chunker contava tokens por `len(texto) // 4`, e o docstring dizia que a
heurística estava *"confirmada contra Gemini tokenizer no Sprint 0"*.

**Era verdade — para o tokenizador do Gemini.** Trocamos o provider de embedding
para OpenAI na Sprint W, e a premissa **nunca foi reconferida**. Medida contra
`cl100k_base` (o tokenizador de quem de fato embarca), sobre todo o corpus:

| razão token real / estimado | |
|---|---:|
| mediana | **1,22×** |
| p90 | **1,50×** |
| p99 | **1,79×** |
| máximo | **2,44×** |

Seis chunks estouravam o teto; o maior tinha **9.947 tokens reais contra 5.915
estimados** (1,68×). Cinco dos seis eram absorvedores de vigência — a #118/#126
cobrando por outra via, e mais um argumento de que a **classificação de entrada**
é o conserto real, não heurística de rótulo.

**Família #123:** premissa que sobreviveu à troca de provider sem ser
reconferida. É a mesma história de `embedding_model` (existia desde a Sprint U,
ninguém lia) e de `model_used` (existia no `AIResponse`, ninguém lia). **O dado
existia; ninguém foi olhar.**

### O que mudou

- `contar_tokens()` usa **tiktoken/cl100k_base**. `MAX_ARTIGO_TOKENS = 7000`
  passa a ser em tokens **reais**, seguro contra os 8.192.
- A janela deslizante corta **por token**, não por caractere: cortar por char
  com uma razão chutada foi exatamente o defeito.
- **Guarda dura antes de embarcar:** nenhum chunk vai para a API sem conferência
  de tokens reais. Estourou, falha alto **dizendo qual chunk** — nunca trunca em
  silêncio. Truncar calado embarcaria meio dispositivo como se fosse inteiro, e o
  vetor representaria um texto que ninguém escreveu.

**Descartado:** baixar o teto estimado para ~4.500 (8.192 ÷ 1,79). Compensaria
régua torta cortando artigo legítimo, e ainda deixaria a cauda de 2,44×
descoberta.

**A Fase 2 é ajustada, não invalidada.** Depois da troca: maior chunk do corpus
**6.871 tokens reais**, zero acima do teto da API.

---

## Adendo de 05/08 (2) — "artigo inteiro = melhor recuperação" está REFUTADO

A aposta central da Fase 2 era que juntar o dispositivo melhoraria a
recuperação. **Medido depois da reindexação única, o contrário aconteceu.**

**Art. 61-A do Código Florestal**, o caso escolhido para provar a tese:

| | baseline (2e78917) | pós-Fase 4 |
|---|---|---|
| `partido_em_pedacos` | 7 | **0** |
| posição no ranking | **#2** | **#29** |
| similaridade | **0,7764** | **0,6601** |

O artigo passou a entrar inteiro — exatamente o que a #118 pedia — e **caiu 27
posições**. Os dois chunks do 61-A hoje têm 2.837 e 2.641 tokens.

**O mecanismo é o que esta própria ADR descreve, agora medido contra nós:** um
vetor de 2.837 tokens representa **tudo vagamente**. O fragmento focado casava
melhor com a pergunta do que o artigo completo. Escrevemos isso como argumento
para não deixar o chunk crescer, e não aplicamos a nós mesmos quando o chunk que
crescia era o artigo.

**Escala da troca:** **490 chunks** são artigos inteiros acima de 1.500 tokens —
**1,60% do corpus** (p50 2.304, p90 4.302, máx 6.871). É **cauda, não sintoma
sistemático**. Mas o 61-A está no miolo dessa faixa: a regressão é **típica da
faixa**, não um extremo dela.

### A #118 continua justificada — por OUTRO motivo, declarado

Não pelo ganho de recuperação, que **não existe**. Pelo que o consultor recebe:
antes, o art. 61-A chegava em **quatro cacos** no top-8, e a metade que ficava de
fora podia ser a que continha a condição. Peça se escreve sobre **artigo
inteiro**.

**É benefício de ENTREGA, com custo medido de RECUPERAÇÃO.** Os dois são reais e
não se cancelam. Registrado sem suavizar: a fase entregou estrutura correta e
**piorou** a recuperação no caso que escolhemos para prová-la.

**Nada foi revertido.** A requalificação do teto — se e como — exige decidir o
que vale mais para a peça assinada, e isso não se decide dentro da fase que
produziu o número.
