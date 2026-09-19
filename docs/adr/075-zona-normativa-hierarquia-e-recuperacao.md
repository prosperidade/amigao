# ADR-075 — Zona normativa: hierarquia de fontes, coletânea como proveniência e recuperação que não relaxa

- **Data:** 18/09/2026
- **Estado:** aceita com as decisões do André de 18/09 (§Decisões do André). **Nenhuma ingestão,
  nenhuma reindexação, nenhum schema alterado.**
- **Frente:** B — zona normativa e RAG (`docs/zona-normativa-adr075`)
- **Base inspecionada:** `origin/main` @ `175ecfa`; banco dev `amigao_db` @ `127.0.0.1:15432` e
  produção (Supabase), ambos só por SELECT.
- **Relação:** detalha a zona normativa do [ADR-070 §12](070-modelo-de-dados-alvo.md#12-zona-normativa-autoridade-no-nível-do-documento)
  (que **não** refaz o modelo do caso); preserva o [ADR-040](040-espaco-vetorial-e-por-tenant-na-implantacao.md)
  (espaço vetorial travado); herda o [ADR-041](041-chunk-e-a-unidade-semantica-do-dominio.md)
  com a tese refutada; **emenda a decisão 6 do [ADR-038](038-corpus-dirigido-por-manifesto-curado.md)** (§3).
  Regras executáveis ficam no ADR-073.
- **Evidência e medições:** [ZONA_NORMATIVA_RAG.md](../arquitetura/ZONA_NORMATIVA_RAG.md).

> **Insumo.** [`ARQUITETURA_DADOS_RAG_REGENTE_v1.md`](../arquitetura/ARQUITETURA_DADOS_RAG_REGENTE_v1.md)
> chegou depois deste ADR escrito e está versionado sem edição. Confronto em
> [ZONA_NORMATIVA_RAG §8](../arquitetura/ZONA_NORMATIVA_RAG.md#8-confronto-com-o-insumo):
> onde divergem, **este ADR vence** — nasceu de medição — e a divergência fica registrada.

## Contexto (medido)

1. **Um só nível para tudo.** 32.161 chunks de 395 fontes (dev) sem nível de autoridade nem
   estado de validação. Norma federal, coletânea estadual e parecer são indistinguíveis. Na
   pergunta de defesa, a OJN 06/2009 (parecer da PFE-IBAMA) ocupou **6 das 8 vagas**
   ([ADR-041, adendo de 06/08](041-chunk-e-a-unidade-semantica-do-dominio.md#adendo-de-0608--a-requalificação-do-teto-fica-para-depois-de-propósito)),
   e o art. 18 do Decreto 6.514/2008 ficou na **posição 37**, similaridade 0,6687
   ([posfase4_defesa.json](../../ops/medicao_corpus_federal/posfase4_defesa.json)).
2. **Coletânea tratada como documento.** São **32 coletâneas** — as 29 `compendio_regente`
   (MS 8, MT 11, AC 10) e 3 de Goiás gravadas como `manual` —, **77,1% dos chunks**. A
   identidade gravada é o núcleo (`MT-NUC04-licenciamento`), não o ato: um "Art. 70" de
   coletânea não diz de que lei é. Medido: **só 2 das 32 têm sumário**; MS, MT e GO são
   **páginas impressas do navegador concatenadas** (4.249 páginas com cabeçalho de impressão e
   URL de origem); AC é markdown do portal LEGIS. Dentro delas há **177 a 368 atos
   distintos**; **17,3% do texto é repetição** (15,6% entre coletâneas, 1,7% com norma avulsa),
   e a Constituição de MT está inteira em duas delas.
3. **Só 19,3% dos chunks** têm nível derivável do que está gravado; 282 PDFs da SEMAD não têm
   linha de documento; `ingest_manifesto` grava toda norma como `lei` (#234).
4. **A busca relaxa até sobrar similaridade:** `legislacao.py:346–357` tira UF, depois
   demanda, depois as duas; `nao_identificado` vira sem filtro com `min_similarity=0.0`; toda
   exceção vira lista vazia (`:370–375`), inclusive a recusa do ADR-040.
5. **Mas esse caminho está parado.** Depois do ADR-069, `BaseAgent.run` não chama `execute()`;
   Legislação responde "capacidade insuficiente" e o envelope do ADR-069 **não usa RAG**. O
   único consumidor ativo da busca é `GET /api/v1/knowledge/search`; o único controle ativo
   de citação é o `persist_object` ([evidence.py:113–117](../../app/services/evidence.py#L113-L117)).
   **O contrato novo entra antes de a Legislação voltar — não depois.**
6. **Dev ≠ produção:** dev 32.161 chunks / 113 documentos; produção 28.891 chunks / 64
   documentos / 346 fontes, com as mesmas 29 coletâneas (#244).

## Decisão

### 1. Seis níveis de autoridade, no nível da fonte

| Nível | O que é | Citável em peça? |
|---|---|---|
| `norma` | Ato normativo com força própria (lei, decreto, resolução, IN, portaria) | Sim, se `validado` |
| `interpretacao` | Interpretação **oficial** de órgão (OJN, parecer normativo, nota de procuradoria, despacho em SEI) | Sim, se `validado`, **sempre ao lado da norma que interpreta** |
| `exigencia` | Requisito imposto por órgão para peça/rito (TR, checklist oficial, matriz IPE) | Sim, como exigência, se `validado` |
| `procedimento` | Como operar sistema/portal (roteiro SIGCAR por mensagem de erro, manual) | Não como fundamento jurídico; sim como orientação operacional |
| `precedente` | Decisão individual de órgão (indeferimento) com motivo | Não como regra geral; sim como alerta de risco no Radar |
| `radar` | Doutrina, bibliografia, material de apoio | **Nunca** |

O nível é da **fonte** (documento/ato) e o trecho herda por junção — não coluna de chunk
(ADR-070 §12: o reindex do ADR-041 zeraria, o ADR-040 duplicaria, e o UPDATE em massa
reescreveria o ivfflat). Classificação retroativa só onde o gravado basta; o resto nasce
`nao_determinado` e entra por reingestão.

### 2. Regra de conflito

1. **Elegibilidade antes de similaridade:** nível permitido para o uso, competência/esfera
   (ADR-034), vigência na data de referência e estado de validação filtram; a similaridade
   só ordena o que sobrou.
2. **Vigente antes de histórico, sem apagar a história** (ADR-037): norma histórica continua
   recuperável quando a data de referência pede, e sai marcada.
3. **Divergência material SUSPENDE a afirmação e abre revisão.** Duas fontes elegíveis que
   dizem coisas incompatíveis sobre o mesmo ponto não são desempatadas por quem "parece mais"
   com a pergunta: a afirmação dependente fica `conflitante` (estado K do ADR-069) e uma
   tarefa de revisão nasce com as duas versões. O mesmo vale para ressalva de interpretação
   (§5): referência errada suspende o que depende dela.

### 3. Interpretação não disputa vaga com a norma (emenda ao ADR-038 §6)

A decisão 6 do ADR-038 continua valendo **para curadoria**: interpretação oficial tem o
mesmo valor que o texto legal, e às vezes maior. **Na recuperação**, ela deixa de competir
pelas mesmas vagas: o resultado traz primeiro os dispositivos de `norma` elegíveis e **anexa**
a cada um as interpretações que o referem. Quem trouxe a OJN à frente do art. 18 foi a
competição por similaridade, não o valor dela. Uma fonte ocupa no máximo uma vaga por
dispositivo — acabam os seis "(parte N)" da mesma OJN.

### 4. Estados de validação e quem assina

`bruto → proposto → validado` (ADR-070), no nível da **versão da fonte**:

| Transição | Quem | Exige | Trilha |
|---|---|---|---|
| nasce `bruto` | ingestão | hash dos bytes, origem, nível ou `nao_determinado` | registro de ingestão |
| `bruto → proposto` | engenharia/curadoria | identidade (tipo, órgão, número, ano) conferida contra a fonte oficial; texto conferido por hash ou `validation_keyword` (ADR-038); vigência declarada ou "não sei" | evento com autor, data, URL oficial e hash |
| `proposto → validado` | **usuário com alçada `validar_fonte_normativa`** (Ontologia §10 — hoje a Ísis) | leitura da ficha da fonte | evento append-only com autor, data, versão, hash do texto e justificativa, numa **hash chain própria do catálogo global** (o catálogo não tem tenant) |

São só três estados (decisão do André). Conflito material **não** cria quarto estado na fonte:
suspende a **afirmação** que depende dela (§2) e abre tarefa de revisão; a fonte mantém o status.

Destino: **peça assinada só cita `validado`**; `proposto` aparece em ambiente interno com
selo; `bruto` serve de candidato de descoberta, sem selo de citável. `status_validacao` não
some da busca (ADR-037) nem da contagem de cobertura (ADR-036). Custo: coluna com default
constante no documento — sem reescrita ([MIGRACAO §7](../arquitetura/MIGRACAO_MODELO_DADOS.md#7-zona-normativa--o-que-muda-no-corpus-atual)).

Onde a Ísis assina: fila "Acervo normativo" no painel (Incremento 4), com validação em lote
**por coletânea desmembrada** — ela confere as fronteiras e as identidades de uma coletânea de
uma vez, não 300 cliques soltos.

### 5. Coletânea é proveniência, não unidade de ingestão

A coletânea continua existindo como **documento de origem** (o arquivo que a Ísis compilou,
com hash). Cada ato dentro dela vira `fonte_normativa` própria, com identidade canônica
normalizada (tipo + órgão + número + ano — nunca string crua) e
**proveniência**: "esta IN veio da Coletânea MT-NUC04, páginas 112–130, impressa de
`<URL>` em 10/05/2026". O mesmo ato em duas coletâneas é **uma** fonte com duas
proveniências; duas redações diferentes do mesmo ato são **versões**, não duplicatas.

Desmembramento determinístico por dois sinais medidos — cabeçalho de impressão (URL e
página) e cabeçalho formal do ato em contexto de abertura —, com revisão humana das
fronteiras por coletânea. LLM não decide fronteira; pode propor ementa/órgão onde faltar,
sempre `proposto`. Ato sem ano ou fronteira ambígua fica `nao_determinado` até a revisão.

### 6. Quatro naturezas com tabela própria

Cada uma é uma projeção tipada de uma `fonte_normativa` do seu nível; chunks só indexam:
- `exigencia_tr` + `exigencia_tr_item` (os 102 TRs): órgão, rito, peça governada, edição,
  itens obrigatórios/condicionais **com página/seção**.
- `precedente` + `precedente_motivo` (indeferimentos): órgão, processo, data, objeto, motivos
  com dispositivo invocado, alcance individual. **Privado do tenant por padrão.**
- `procedimento` + `procedimento_passo` (SIGCAR): sistema, versão, código e mensagem literal
  de erro, pré-condições, passos, resultado esperado.
- `interpretacao` + `interpretacao_ressalva` (SEI): órgão, espécie, número/processo, questão,
  conclusão, alcance, normas interpretadas por id e **ressalvas** — citação literal,
  referência resolvida, tipo de erro, verificação e efeito. O Parecer 84 cita "Decreto Federal
  9.710/2020", que é **decreto estadual de Goiás**: o literal fica, a ressalva aponta a
  referência correta e suspende a afirmação que dependa dela.

### 7. Recuperação: filtro obrigatório antes do ranking, vazio com razão

Ordem fixa: (1) **consulta por identidade** — se a pergunta ou a regra já traz norma e
dispositivo, busca-se por ID, sem similaridade; (2) **conjunto elegível** — nível permitido
para o uso, status conforme o destino, vigência na data de referência, competência/esfera,
objetivo canônico, tenant e espaço vetorial; (3) **ranking híbrido só dentro do elegível** —
`tsvector` (configuração `portuguese`) + pgvector, fusão por RRF; (4) **uma vaga por
dispositivo**, interpretação anexada à norma.

**Se o filtro esvazia, a resposta é vazia com a razão**: `contexto_insuficiente`,
`sem_fonte_elegivel`, `fora_da_cobertura`, `falha_de_busca` ou
`espaco_vetorial_incompativel`. **Nunca relaxa.** Busca exata sobre o elegível enquanto ele
couber (hoje ~32 mil trechos); ANN (`iterative_scan` do pgvector 0.8) só quando o elegível
passar de ~100 mil.

### 8. Citação por claim, verificada por ID antes de emitir

Cada afirmação carrega `[fonte_versao_id, dispositivo, localizador]`. O envelope entrega ao
modelo só as fontes elegíveis, com IDs; o modelo cita por ID. Antes de emitir: todo ID existe
no envelope, o dispositivo existe naquela versão, o status serve ao destino e a vigência vale
na data de referência — **pertencimento a conjunto, não semelhança**. Menção a norma em texto
livre sem ID é **citação órfã e bloqueia a saída**. O `citation_evaluator` deixa de ser
validador por regex e vira **detector de menção sem vínculo**.

### 9. Avaliação em CI

Conjunto versionado de 30–50 sondas com fonte e dispositivo-alvo conhecidos, controles
negativos e métricas fixas: **recall@5 ≥ 0,9**, **groundedness 100%**, **zero citação
órfã**, **controle negativo → vazio com a razão certa**. Alvo casado por ID de fonte +
dispositivo, nunca por regex no texto (o `art61a` "recuperado" de hoje é falso positivo).
Em todo PR: testes de contrato com vetores sintéticos. Qualidade de recuperação: corpus de
homologação + vetores das perguntas em cache (§9 do documento de desenho).

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Nível de autoridade como peso no score | Mistura escalas: um peso alto o bastante para o art. 18 vencer a OJN esconde a OJN quando ela é o que importa. Elegibilidade + vaga por nível resolve sem calibrar |
| Rebaixar interpretação | Contraria o ADR-038 §6 e o valor real da OJN para defesa |
| Manter coletânea como documento e marcar o ato no chunk | O chunk não sabe a fronteira do ato; identidade por trecho não sobrevive ao reindex (ADR-041) |
| LLM para cortar coletânea | Fronteira tem sinal determinístico medido; LLM cortaria sem trilha e com custo por página |
| Relaxar filtro com aviso | "Não encontrei com filtro, então busquei sem" é exatamente o defeito medido; o aviso não chega à peça |
| Validar citação depois de emitir | Hoje é assim (redator/diagnóstico marcam e seguem); citação inventada já saiu |
| Só busca vetorial | Número de norma, sigla e "art. 18" são tokens exatos que a similaridade dilui |
| Status de validação filtrando descoberta | Contra ADR-037 e ADR-036 (cobertura cairia a zero) |

## Consequências

- O Incremento 4 deixa de ser "acrescentar colunas": é **reingerir 80,7% do corpus** (32
  coletâneas + 5 manuais + 18 PDFs SEMAD ambíguos) com desmembramento e identidade.
- A Legislação só volta a rodar com este contrato; reativar o caminho legado reabre o defeito.
- Corpus resultante estimado: **258 a 449 documentos de legislação** (hoje 113), 540 a 731
  fontes (as 282 da SEMAD ganham linha) e ~27.900 chunks (−17,3% de texto repetido).
- A trava de citação ativa no `persist_object` tem lacunas hoje (#243).

## Decisões do André (18/09/2026)

| # | Decisão | Efeito |
|---|---|---|
| 1 | Emenda ao ADR-038 §6 **aprovada**: interpretação oficial anexada à norma que interpreta | §3 vale |
| 2 | Validar fonte normativa é **papel de curadoria, delegável**. A Ísis é a titular hoje; o papel aceita outros curadores por área (advogado ambiental entra sem mudar arquitetura). A trilha grava quem assinou | §4: alçada `validar_fonte_normativa` por área, não pessoa |
| 3 | `precedente` **privado da consultoria** por padrão; promoção a global é decisão do tenant, nunca automática | §6 |
| 4 | Avaliação da busca: **por PR que toque recuperação, corpus, chunking ou embedding + rodada noturna completa** | §9 |
| 5 | Reconstrução parte do **dev (113 documentos)** — **mas medir antes** por que produção tem 64: listar o que existe em um e não no outro. Se produção tiver documento que o dev não tem, a reconstrução perde material. **Reportar antes de qualquer reingestão** | **medido em 18/09:** a produção **não tem nenhum documento** que o dev não tenha; o dev tem **49 a mais, todos federais** (ids 102–210 — manifesto do ADR-038 e normativas de 06/08, incluindo Decreto 6.514/2008, Constituição Federal e OJN 06/2009); os 64 comuns batem por identidade (7 com texto levemente diferente, 50 com contagem de chunks diferente — fatiamentos de épocas diferentes); as 282 fontes SEMAD são idênticas. **Reconstruir a partir do dev não perde material.** [ZONA_NORMATIVA_RAG §0](../arquitetura/ZONA_NORMATIVA_RAG.md#0-estado-de-partida) |
| 6 | **Sondas verdes são condição para religar a Legislação.** Martelo batido | #242 fecha só com as sondas |

## Pendente com a Ísis

Vão **juntas**, no mesmo envio: **Q-ISIS-18** (tipologias SEMAD como `exigencia` ou
`procedimento`), **Q-ISIS-19** (as coletâneas têm índice ou lista dos atos? medido: só 2 das
32 têm sumário) e **Q-ISIS-04** (tolerância de reprodução da área do KMZ).

## Execução (sem decisão)

Parser de desmembramento em dry-run com relatório por coletânea · função única de identidade
normalizada · autoria das sondas com a Ísis validando os alvos · dívidas #242–#247.
