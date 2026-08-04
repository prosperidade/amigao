# ADR-040 — O espaço vetorial é escolhido por tenant, na implantação

- **Status:** aceita
- **Data:** 2026-08-03
- **Branch:** `fix/trava-espaco-vetorial`
- **Decisão de domínio:** André, ao preparar o experimento de embeddings
- **Correlatas:** ADR-036 (identidade da norma), dívida #113 (recall do IVFFlat),
  dívida #114 (esta)

## Contexto

`app/services/embeddings.py:_select_provider()` decidia o provedor de embedding
**por presença de chave**: havendo `OPENAI_API_KEY`, OpenAI; senão, Gemini.

Isso é um fallback, e parece resiliência. Não é.

Embeddings de provedores diferentes **não são intercambiáveis** — são espaços
vetoriais distintos. Uma consulta embarcada pelo Gemini, comparada contra um
índice construído pela OpenAI, não produz erro: produz **oito trechos com
similaridades de aparência perfeitamente normal e conteúdo aleatório**. O agente
recebe fundamentação inventada e não tem como saber. A consultora assina.

É pior que o defeito do `probes=1` (dívida #113): lá, os vizinhos devolvidos eram
subótimos, mas do mesmo espaço — erravam por pouco. Aqui seriam distâncias entre
coisas incomparáveis.

E o gatilho é banal: chave que expirou, cota estourada, deploy sem a variável.

**Medido antes de decidir (03/08):** o corpus está homogêneo — 31.298 chunks,
todos `text-embedding-3-small` a 768 dimensões, de 14/05 a 03/08. Uma única
linha no `group by embedding_model`. **A mistura nunca aconteceu.** Esta ADR é
prevenção, não reparo.

## Decisão

**1. O provedor é explícito, nunca inferido.** `EMBEDDING_PROVIDER` decide.
Sem configuração, assume o default do produto (`openai` — o que construiu o
corpus). A ausência da **chave** do provider configurado é **falha ruidosa** no
momento de usá-la, não troca de provider.

**2. A busca mira um espaço e recusa os outros.** `search()` filtra por
`embedding_model` e, se o corpus estiver povoado **em outro espaço**, levanta
`EspacoVetorialIncompativel` com log de erro — dizendo em que espaço o corpus
está e o que ajustar. Devolver lista vazia seria a falha silenciosa que esta ADR
existe para impedir: o agente diria *"não encontrei fundamentação"* quando o
problema é estar perguntando no idioma errado.

Corpus **vazio** não é incompatibilidade — é estado legítimo de ambiente novo, e
devolve vazio normalmente. A recusa só dispara quando **há** vetores e nenhum é
do espaço consultado.

**3. A escrita declara o espaço.** `index_text(embedding_model=...)` diz em que
espaço aquele texto está sendo gravado. Omitido, usa o configurado.

**4. A escolha é POR TENANT, definida na IMPLANTAÇÃO — não é seletor de
runtime.** Esta é a parte que se decide agora para não ser decidida errado
depois, sob pressão de um cliente.

Corpus compartilhado com dois provedores significa **dois índices** — os mesmos
chunks, embarcados duas vezes, ocupando espaço duas vezes e custando reindexação
a cada mudança de corpus. Não é uma opção que se liga por requisição; é uma
decisão de arquitetura de implantação.

**O segundo índice só é ligado quando houver cliente que exija.** Até lá, a
capacidade existe (a busca e a escrita aceitam o parâmetro) e permanece
desligada. Construir a capacidade é barato; mantê-la ativa sem demanda é caro e
duplica a superfície de erro.

## Consequências

- Um deploy sem `OPENAI_API_KEY` passa a **falhar alto** em vez de silenciosamente
  responder com ruído. É a troca certa: indisponibilidade honesta vale mais que
  disponibilidade mentirosa.
- O experimento de provedores (Google × OpenAI) já nasce com a trava: ele **exige**
  dois índices e comparação lado a lado, e agora isso é a única forma possível de
  fazê-lo — não há como misturar por acidente.
- `knowledge_catalog.embedding_model` deixa de ser só auditoria e passa a ser
  **chave de recorte**. A coluna já existia e já guardava o dado desde a Sprint U;
  faltava alguém lê-la.
- Cobertura: `tests/services/test_trava_espaco_vetorial.py` (8 testes), incluindo
  o controle de que ausência de chave **não** troca de provider, e a distinção
  entre "vazio legítimo" e "espaço trocado".

## Alternativas descartadas

- **Manter o fallback e avisar em log.** Log que ninguém lê não impede peça
  assinada com fundamentação inventada. O sistema tem de recusar.
- **Converter vetores entre espaços.** Não existe conversão fiel; a proximidade
  em um espaço não implica proximidade no outro.
- **Seletor de provedor por requisição.** Faria o corpus precisar de todos os
  índices, sempre, para atender qualquer requisição — o custo de manter N índices
  quentes sem demanda que os justifique.
