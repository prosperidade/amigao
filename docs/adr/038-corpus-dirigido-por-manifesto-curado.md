# ADR-038 — O corpus é dirigido por manifesto curado e versionado

- **Status:** aceita
- **Data:** 2026-08-03
- **Branch:** `feat/ingestor-curado-nucleo06`
- **Decisão de domínio:** André, a partir da entrega do mapa normativo da Isis
- **Correlatas:** ADR-036 (identidade e cobertura), ADR-037 (vigência e o rótulo
  no dado), ADR-034 (esfera pelo órgão)

## Contexto

O que entrava no corpus era uma **lista fixa escrita à mão** dentro de
`scripts/ingest_federais_canonicos.py`. A medição de 31/07 mostrou o preço disso:
o corpus federal tinha exatamente o tamanho da lista que alguém digitou em
23/04 — 785 chunks contra 26.505 estaduais — e ninguém sabia que era esse o
limite. Parecia falha de ingestão; era escopo, invisível porque não estava
declarado em lugar nenhum.

Agora a Isis entregou o mapa normativo completo: 435 normas federais com URL e
status por linha, mais o mapeamento das 27 UFs. Continuar por lista digitada
seria transformar curadoria de especialista em trabalho de digitação, com o erro
de cópia junto.

Ao ler a planilha do núcleo 06, apareceu a segunda razão, mais forte. A matriz da
Isis é **analítica**: a mesma norma ocupa várias linhas, examinada por ângulos
diferentes. 43 linhas apontam para 26 URLs; o Decreto 6.514/2008 sozinho ocupa 7
(embargo, apreensão, suspensão, reincidência…). E das 26 URLs, só 16 são texto
normativo — as outras são páginas de serviço do gov.br: FAQ do auto de infração,
"obter certidão de embargo", consulta de áreas embargadas, parcelamento da PGFN.

Ingerir linha a linha baixaria o mesmo decreto sete vezes. Ingerir tudo poria
página de FAQ competindo com lei na busca vetorial — a mesma física que o
ADR-036 descreveu, agora com o agravante de virar fonte de peça assinada.

## Decisão

**1. A fonte de verdade do corpus é um manifesto CSV versionado**, em
`data/corpus_manifesto/`, extraído da planilha por
`scripts/extrair_manifesto.py`. A planilha fica **fora** do repo
(`curadoria_isis/` no `.gitignore` — 18 MB de binário). Rodar o extrator com a
planilha atualizada e ler o **diff do CSV** passa a ser a forma de auditar o que
a curadoria mudou.

**2. O manifesto distingue `norma` de `referencia_operacional`.** Só `norma`
entra no corpus vetorial. A página de serviço fica versionada e exibível ao
consultor — é onde ele protocola, consulta ou obtém documento — mas **não é
fundamentação** e não disputa espaço na busca por similaridade.

**3. O ingestor só executa o que a curadoria validou.** Linha com status
diferente de "Fonte oficial validada" não entra. Não localizado, em tramitação,
portal fora do ar: fica no manifesto, declarado, fora do corpus.

**4. Oito garantias, e cada uma é um bug que já pagamos:**

| # | garantia | o bug de origem |
|---|---|---|
| a | idempotência por `content_hash` | reingestão cega duplicando corpus |
| b | charset real + canário que **recusa** acima de 0,05% U+FFFD | mojibake do Planalto, 3 meses invisível (#95) |
| c | `U+00A0`/`U+200B`/`U+FEFF` normalizados na ingestão | `"Art. 18."` não casava com `"Art. 18."` (#96) |
| d | `validation_keyword` **obrigatória**, conferida no texto | LegisWeb serviu resolução da SEFAZ-AM no lugar da IN IBAMA 10/2012 |
| e | proveniência gravada | 97,3% do corpus sem origem declarada (#97) |
| f | vigência com rótulo **no dado** | norma revogada apresentada como vigente (ADR-037) |
| g | relatório por linha, **falha não aborta o lote** | 403 de um portal derrubando 25 linhas boas |
| h | dry-run por padrão | gravar antes de ver |

**5. `observacao_curadoria` é canal de volta.** O que a ingestão descobre e a
curadoria precisa saber — revogação não sinalizada, URL truncada, portal que
responde 403 — fica no manifesto, versionado, e sai no relatório. Não é
comentário de código: é recado para a especialista.

**6. Material INTERPRETATIVO vale tanto quanto o texto legal.** Critério de
curadoria firmado em 03/08, a partir do que a primeira medição mostrou: a
**Orientação Jurídica Normativa 06/2009 da PFE-IBAMA** passou a ocupar 4 das 8
vagas de trecho recuperado na pergunta de defesa — à frente do próprio Decreto
6.514/2008.

Faz sentido, e é a diferença que interessa ao consultor: o decreto diz o que a
lei determina; a OJN diz **como o órgão a aplica**, e é vinculante para os
procuradores que vão julgar o recurso. Citar a lei sem saber a interpretação do
órgão é entregar metade da defesa.

Portanto, na curadoria dos blocos seguintes: OJNs, pareceres normativos, notas
técnicas de procuradoria e instruções normativas de rito entram com a **mesma
prioridade** do texto legal canônico — e, onde o canônico já está coberto (que é
a regra, medida no bloco 1), com prioridade **maior**.

## Consequências

O primeiro uso já se pagou duas vezes, e as duas com o mesmo mecanismo — a
`validation_keyword`:

- **A Constituição da planilha vinha truncada.** A URL entrega texto que para no
  art. 24, §4º; a linha da curadoria invoca o **art. 225, §3º**, que não está
  lá. Baixa, tem 60 mil caracteres, parece certa. Com a keyword `art. 225` o
  ingestor recusou, e a versão íntegra (`constituicaocompilado.htm`, 686.756
  chars) entrou no lugar. Sem a guarda, entraria uma Constituição sem o artigo
  ambiental — e **texto truncado não levanta exceção**, mesma física do mojibake.
- **A guarda também pega curadoria descuidada.** A LC 140/2011 reprovou porque a
  keyword escrita foi `140/2011` e o Planalto grafa "LEI COMPLEMENTAR Nº 140, DE
  8 DE DEZEMBRO DE 2011". Erro de quem curou, não da fonte — e igualmente barrado.

Outros efeitos:

- **A decisão de curadoria fica codificada, não comentada.** A escolha de manter
  a versão **anotada** das três normas que a planilha aponta como compiladas
  virou URL no manifesto: elas dão `skip` por hash idêntico a cada rodada. É
  decisão verificável, não um comentário que alguém esquece.
- **Norma revogada entra marcada.** O Decreto 9.760/2019 está na planilha como
  "Fonte oficial validada" sem nenhum sinal de revogação; o texto do Planalto diz
  *"(Revogado pelo Decreto nº 11.080, de 2022)"*. Entrou com `vigencia_fim` e
  sucessora — data conferida na fonte, não suposta.
- Cobertura: `tests/services/test_ingestor_manifesto.py` (20 testes), com os
  casos reais deste bloco como fixture.

## Alternativas descartadas

- **Manter a lista no código.** É o que produziu o corpus de tamanho invisível.
  Curadoria em código-fonte não é auditável por quem cura.
- **Ler a planilha direto na ingestão.** Tiraria o binário do repo e o diff
  junto: não haveria como ver o que mudou entre duas rodadas, nem revisar a
  curadoria em PR. O CSV intermediário é o artefato revisável.
- **Ingerir uma linha por linha da matriz.** Baixaria o Decreto 6.514/2008 sete
  vezes e poria FAQ como fundamentação.
- **Deixar a keyword opcional.** Foi a tentação — ela dá trabalho de preencher.
  As duas capturas do primeiro uso responderam.
