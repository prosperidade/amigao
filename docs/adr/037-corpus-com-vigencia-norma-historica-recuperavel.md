# ADR-037 — O corpus tem eixo do tempo; a norma revogada é citável, nunca como vigente

- **Status:** aceita
- **Data:** 2026-07-31
- **Branch:** `feat/corpus-federal-defesa`
- **Decisão de domínio:** André, a partir da medição do corpus federal de 31/07
- **Correlatas:** ADR-034 (esfera pelo órgão — dá o escopo), ADR-036 (identidade da
  norma e cobertura declarada — mede a lacuna que esta ADR preenche), ADR-035
  (fonte clicável obrigatória)

## Contexto

A medição de 31/07 mostrou 785 chunks federais contra 26.505 estaduais e provou
que a causa **não** era falha de ingestão: `chars/chunk` era praticamente igual
nas duas esferas (federal 1.118, estadual 954–1.484), 64/64 documentos
`indexed`, zero embedding nulo. O corpus federal era pequeno porque
`scripts/ingest_federais_canonicos.py` é uma **lista curada fixa de 10 diplomas**
digitada à mão em 23/04/2026. Ele tinha exatamente o tamanho da lista.

O que a lista cobria era o direito **material** (o que é APP, o que é reserva
legal). O que faltava era o direito **sancionador e processual** — que é a
matéria de uma defesa de auto de infração. O Decreto 6.514/2008 era citado por
102 chunks e não tinha uma linha de texto próprio no corpus.

E aí apareceu o problema que esta ADR existe para resolver. O caso 15 é um auto
do IBAMA de **2007**, e seu enquadramento invoca:

| norma citada no auto | situação hoje |
|---|---|
| Decreto 3.179/1999, art. 25 c/c art. 2º | revogado pelo Decreto 6.514/2008 |
| Lei 4.771/1965, art. 2º, "c" | revogada pela Lei 12.651/2012 |
| Lei 9.605/1998, arts. 70 e 72 | vigente |
| Decreto 6.514/2008, art. 18, §1º (certidão de embargo) | vigente |
| MPV 780/2017, art. 2º (adesão ao REFIZ) | convertida na Lei 13.494/2017 |

Metade da defesa se faz com norma **revogada**, porque é a que valia no fato
(*tempus regit actum*). Deixá-la fora do corpus não protege ninguém: obriga o
consultor a procurar fora do sistema exatamente na hora mais delicada.
Ingeri-la sem marcação é pior ainda — o sistema passa a apresentar norma morta
como direito vigente, que é a classe de erro mais cara do produto, porque não
parece erro.

`legislation_documents` não tinha como responder "esta norma valia na data do
fato?". Havia `effective_date` (início) e `revoked_at` — mas `revoked_at` já tem
outro dono: é o carimbo de quando **nós** superamos aquele *registro* ao inserir
uma versão nova do arquivo. Reaproveitá-la confundiria "trocamos o arquivo" com
"o legislador revogou".

## Decisão

**1. O corpus ganha eixo do tempo.** `vigencia_inicio`, `vigencia_fim`,
`sucessora_id` (FK) e `sucessora_ref` (texto). `vigencia_fim IS NULL` significa
vigente. Documento anterior à coluna, com tudo NULL, é tratado como vigente —
ausência de curadoria não pode apagar trecho da busca de um dia para o outro.

**2. A norma revogada ENTRA, marcada.** Quatro dos nove diplomas do pacote A são
históricos e foram ingeridos de propósito, com a janela de vigência declarada e
a sucessora apontada.

**3. O rótulo viaja no DADO, não no prompt.** Esta é a regra que generaliza para
além deste caso, e a razão dela é simples:

> Aviso que mora no prompt de um agente protege **um agente**.
> Aviso que mora no dado protege **o dado**.

O rótulo de norma histórica é gravado no `title` do chunk no momento da
indexação (`app/services/vigencia.py`). O `LegislacaoAgent` já monta o cabeçalho
de cada trecho a partir do `title` — então o aviso chega ao modelo **sem uma
linha de diff no agente**, e chega igual para o diagnóstico, para a consolidação
e para qualquer agente que ainda não existe. O texto gravado é:

> `[NORMA HISTÓRICA — revogada em 22/07/2008, sucedida por Decreto 6.514/2008.`
> `Aplicável a fatos anteriores a 22/07/2008 (tempus regit actum); NÃO citar`
> `como norma vigente]`

Medido: com o rótulo no dado, a resposta do modelo passou a escrever *"Decreto
3.179/1999, art. 2º (norma histórica, revogada em 22/07/2008, sucedida pelo
Decreto 6.514/2008)"* sem nenhuma instrução específica sobre vigência no prompt.

**4. `search(vigente_em=data)` recorta pelo tempo.** Com a data do fato, só vêm
normas que valiam nela. **Sem** o parâmetro, vem tudo — e o histórico vem
rotulado. O default é trazer avisado, não esconder: esconder devolveria o
consultor à busca manual.

**5. Sucessora fora do corpus se nomeia.** `sucessora_id` é FK para quando a
sucessora está no corpus; `sucessora_ref` guarda o nome quando não está. A IN
IBAMA 10/2012 foi revogada pela IN Conjunta MMA/IBAMA/ICMBio 02/2020, que não é
do pacote A — sem o campo de texto, a única saída seria uma FK nula e a
informação sumiria em silêncio.

**6. Proveniência é declarada, e "não sei" é um valor.** Todo documento novo
grava `fonte_origem`, `fonte_oficial` e `fonte_url` em `extra_metadata`. A
proveniência é **derivada da URL**, não digitada entrada a entrada, para que não
exista documento novo sem origem: fonte não reconhecida cai no rótulo explícito
`"origem não identificada — conferir antes de citar"`, nunca em branco. Oito dos
nove diplomas do pacote A vêm de fonte oficial (Planalto e DOU); a IN IBAMA
10/2012 vem do LegisWeb, marcada `fonte_oficial: false`, com o PDF oficial na
lista de pedidos à Isis.

## Consequências

- Corpus federal+nacional: 785 → 1.600 chunks. Custo de embedding: US$ 0,0030.
- O texto que entra passa a ser **conferido**: canário de mojibake recusa
  ingestão acima de 0,05% de caracteres de substituição, e o saneador normaliza
  espaço não-quebrável. Os dois defeitos foram encontrados nesta sprint e
  estavam no corpus desde abril (ver "O que a sprint revelou").
- `revoked_at` fica com o significado que sempre teve. Nada foi reinterpretado.
- Cobertura: `tests/services/test_vigencia_norma_historica.py` (10 testes),
  incluindo os três casos temporais e o controle de que o rótulo **não vaza**
  para norma vigente e não se duplica ao reindexar.

## O que a sprint revelou (e não estava no plano)

**Mojibake desde abril.** O planalto.gov.br responde `Content-Type: text/html`
sem `charset`; o httpx assume utf-8; os bytes são ISO-8859-1. Todo acento virou
`U+FFFD`: o corpus guardava *"Art. 3º O órgão ... aplicará as seguintes
sanções"* como `"Art. 3� O �rg�o ... aplicar� as seguintes san��es"`. Passou
três meses despercebido porque **texto corrompido não levanta exceção** — só
degrada a citação e o embedding, calado. Corrigido em
`scripts/ingest_legislation.py:_decodificar` (header → `<meta charset>` → utf-8
→ ISO-8859-1) com canário `verificar_mojibake`.

**Espaço não-quebrável.** O Planalto separa "Art." do número com `U+00A0`. O
texto *parece* `"Art. 18."` e não casa com `"Art. 18."` em busca nenhuma — nem na
nossa, nem no Ctrl+F de quem lê a peça pronta. 998 chunks do corpus antigo têm o
caractere. `sanitize_text` passou a normalizá-lo.

Ambos afetam o corpus já ingerido, que não foi reprocessado aqui — vira dívida
nomeada (ver `docs/trabalhos/corpus_federal_pacote_a.md`).

## Alternativas descartadas

- **Não ingerir norma revogada.** Foi a primeira ideia e é a errada: a defesa do
  caso 15 é feita de norma revogada. Sem ela no corpus, o sistema fica mudo
  justamente no caso que motivou a sprint.
- **Filtrar a histórica por padrão.** Transformaria o default em "o corpus mente
  por omissão". Trazer avisado é mais seguro que esconder — e o `vigente_em`
  existe para quem quer o recorte estrito.
- **Instruir o agente no prompt a checar vigência.** Protege um agente e deixa
  todos os outros descobertos, além de gastar a atenção do modelo com uma
  verificação que o dado já pode carregar resolvida.
- **Reaproveitar `revoked_at` como fim de vigência.** Sobrecarregaria uma coluna
  que já significa outra coisa, e a confusão apareceria como norma "revogada"
  toda vez que trocássemos o arquivo-fonte.
