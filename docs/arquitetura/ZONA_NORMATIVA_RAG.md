# Zona normativa e RAG — medições e desenho

**Documento:** Arquitetura · base do Incremento 4
**Decisões:** [ADR-075](../adr/075-zona-normativa-hierarquia-e-recuperacao.md) · modelo do caso no
[ADR-070](../adr/070-modelo-de-dados-alvo.md) (não refeito aqui)
**Base:** `origin/main` @ `175ecfa`; banco dev `amigao_db` (alembic `c7e1a94d2f60`) e produção
(Supabase), só SELECT. **Nenhuma ingestão, reindexação ou schema alterado.**
**Execução (Incremento 4a, 22/09):** [ZONA_NORMATIVA_INCREMENTO4A.md](ZONA_NORMATIVA_INCREMENTO4A.md).
**Medições reproduzíveis:** [provas/adr075_medir_coletaneas.py](provas/adr075_medir_coletaneas.py)
e [saída](provas/adr075_medicao_coletaneas.txt).

> O insumo [`ARQUITETURA_DADOS_RAG_REGENTE_v1.md`](ARQUITETURA_DADOS_RAG_REGENTE_v1.md) chegou depois
> deste desenho; o confronto está no [§8](#8-confronto-com-o-insumo). Onde divergem, vale o ADR-075
> (nasceu de medição) e a divergência fica anotada.

---

## 0. Estado de partida

| | Dev | Produção |
|---|---|---|
| Chunks | 32.161 | 28.891 |
| Fontes (`source_ref` distintos) | 395 | 346 |
| Documentos de legislação | 113 | 64 |
| Coletâneas (`compendio_regente`) | 29 | 29 |
| Espaço vetorial | 100% `text-embedding-3-small` 768d | idem |

**Dev × produção (decisão 5 do ADR-075, medido em 18/09).** Comparação por identidade
(identificador normalizado) e por hash do texto:

| | Resultado |
|---|---|
| Só em produção | **0 documentos** — reconstruir a partir do dev não perde material |
| Só no dev | **49 documentos, todos federais** (ids 102–210): manifesto curado do ADR-038 e normativas de 06/08 — 33 leis, 9 IN, 3 decretos, 3 resoluções, 1 portaria, 2.709 chunks. Inclui **Decreto 6.514/2008**, **Constituição Federal** e **OJN 06/2009**: a produção nem tem o alvo da busca de defesa |
| Comuns (64) | batem por identidade; **7 com hash diferente = os 7 federais do reparo de charset da #95** (Lei 12.651/2012, 9.605/1998, 9.985/2000, 6.938/1981, LC 140/2011, Decretos 7.830/2012 e 8.235/2014): o dev rebaixou do Planalto com o charset certo (~4% de `U+FFFD` → 0%); a produção guarda a ingestão de abril, **com o mojibake** — **confirmado em 21/09 pelo `supabase-prod-ro`: 3,7% a 4,7% de `U+FFFD` nos ids 16–22** (issue #185). A **Lei 9.605/1998** tem +284 caracteres no dev que o charset não explica — provável mudança da página do Planalto, **não verificado**; 50 com contagem de chunks diferente (a reindexação da fase 4 do ADR-041 rodou só no dev) |
| Fontes SEMAD | 282 × 282, mesmas referências e mesma contagem |

Leitura de produção feita por SELECT em modo somente-leitura, antes da regra do ADR-076; as
próximas passam pelo MCP `supabase-prod-ro`.

**Quem consome a busca hoje:**

| Consumidor | Estado | Filtros |
|---|---|---|
| `LegislacaoAgent._load_rag_chunks` ([legislacao.py:290–375](../../app/agents/legislacao.py#L290-L375)) | **parado** — ADR-069 não chama `execute()`; Legislação responde "capacidade insuficiente" ([agent_capabilities.py:21–23](../../app/services/agent_capabilities.py#L21-L23)) | cascata que relaxa |
| `auto_infracao_extraction.lookup_enquadramento` | parado (só dentro de `execute()` do diagnóstico) | `min_similarity=0.55` + identidade por número |
| `GET /api/v1/knowledge/search` ([knowledge.py:34–86](../../app/api/v1/knowledge.py#L34-L86)) | **ativo**, sem consumidor no frontend | os que o chamador passar |
| Envelope do ADR-069 ([connected_agents.py:176–206](../../app/services/connected_agents.py#L176-L206)) | ativo | **não usa RAG** |

Conclusão: a recuperação normativa **não está servindo peça hoje**. O contrato novo pode
entrar inteiro antes de a Legislação voltar.

---

## 1. Hierarquia de fontes contra o corpus atual

### 1.1 As 395 fontes (dev)

| Balde | Fontes | Chunks | Como |
|---|---:|---:|---|
| **Classificável pelo que está gravado** | **340** | **6.200 (19,3%)** | `norma` 74 (espécie); `interpretacao` 1 (OJN 06/2009, pelo identificador — está gravada como `lei`, #234); `radar` 1 (bibliografia CPI/PUC-Rio); `exigencia` 33 (6 matrizes IPE + 27 TR/gabarito, pelo nome do arquivo); **223 fichas de tipologia** (`exigencia` ou `procedimento` — Q-ISIS-18); `procedimento` 8 |
| **Exige releitura** | 23 | 1.155 (3,6%) | 5 manuais (Manual SICAR, Matriz IPÊ, listas ATIV-INEX 308p e 7p, Plano de Manejo — 1.038 chunks); 18 PDFs SEMAD diversos (117) |
| **Coletânea** | 32 | 24.806 (77,1%) | 29 `compendio_regente` + 3 coletâneas de Goiás gravadas como `manual` (ids 12, 13, 15); desmembrar (§3) |

Entre os **113 documentos de legislação**: 76 classificáveis (74 `norma`, 1 `interpretacao`,
1 `radar`), 5 manuais para reler, 32 coletâneas. `precedente`: **zero** no corpus (INS-005 não
ingerido). O `source_type` gravado não basta sozinho: 28 dos 36 `matriz_ipe` são fichas de
tipologia; só o nome do arquivo separa.

### 1.2 Regra de conflito (ADR-075 §2–§3)

| Situação | Hoje | Alvo |
|---|---|---|
| Norma e interpretação disputam a mesma pergunta | similaridade decide; OJN 6 de 8 vagas, art. 18 na 37ª | norma elegível primeiro; interpretação **anexada** ao dispositivo que refere |
| Mesma norma em coletânea e avulsa | duas entradas, mesma similaridade: na compensação de RL em GO, **7 das 8 vagas** são pares (Lei GO 18.104 arts. 25/26/29 e IN SEMAD 3/2025 art. 1º, cada um também dentro de coletânea — [posfase4_compensacao_rl_go.json](../../ops/medicao_corpus_federal/posfase4_compensacao_rl_go.json)) | uma fonte, duas proveniências; uma vaga |
| Norma histórica | recuperável, marcada (ADR-037) | idem, filtrada pela data de referência |
| Duas fontes incompatíveis | a mais parecida vence | afirmação `conflitante` + tarefa de revisão |

---

## 2. Estados de validação

**Custo:** `ADD COLUMN status_validacao … DEFAULT 'bruto'` em `legislation_documents` (ou na
`fonte_normativa` nova) é só metadado (PostgreSQL 11+), precedente no próprio banco
(`fonte_oficial`, `atthasmissing = t`). **O nome não pode ser `status`**: essa coluna já é o
estado de processamento (pending → indexed).

**Ponte com a Ísis:**

| Onde | O que ela vê | O que grava |
|---|---|---|
| Fila "Acervo normativo" (Incremento 4) | ficha da fonte: identidade, órgão, vigência, URL oficial, trecho de abertura, proveniências | `proposto → validado` ou devolução com motivo |
| Validação em lote por coletânea desmembrada | lista dos atos que saíram da coletânea, com fronteira (páginas) e identidade | aceita o lote ou marca os atos com problema |

Cada gesto é evento append-only (autor, data, versão da fonte, hash do texto, justificativa)
na hash chain. Alçada `validar_fonte_normativa` (Ontologia §10: autoridade do usuário é eixo
separado da autoridade da fonte).

---

## 3. Desmembramento das coletâneas

### 3.1 O que as coletâneas são (medido)

| | MS (8) | MT (11) | AC (10) | GO (3) |
|---|---|---|---|---|
| Origem | PDF por núcleo, **páginas impressas do navegador** | idem | markdown exportado do portal LEGIS | PDF da pasta da sócia, impresso |
| Sinal de página | `10/05/2026, 17:04 13977-1.pdf` + URL de origem + `n/m` | idem (sefaz.mt, legisweb, leis.org…) | `LEGIS :: Portal da Legislação` | idem MS/MT |
| Sumário/índice no início | 1 (MS-NUC05) | 0 | 0 | 1 |

Totais: 28,2 milhões de caracteres; **4.249 páginas** com cabeçalho de impressão; **429 URLs
de origem** (soma por coletânea; inclui variantes truncadas da mesma URL).

### 3.2 Quantas normas há dentro

| Critério | Atos distintos | Observação |
|---|---:|---|
| **Estrito** — cabeçalho formal (`TIPO Nº n, DE … DE aaaa`) com abertura de documento nos 400 caracteres anteriores (`ESTADO DE…`, `ASSEMBLEIA LEGISLATIVA`, `Compilado`, página `1/n`) | **177** (MS 39, MT 39, AC 56, GO 43) | **38 atos em mais de uma coletânea**; 22 sem ano |
| **Largo** — todo cabeçalho formal em maiúsculas | **368** | já sem as 217 linhas `EMENDA CONSTITUCIONAL` da Constituição de MT compilada, que aparece **inteira em MT-NUC01 e MT-NUC08**; 75 sem ano |

Por tipo (estrito): 79 decretos, 65 leis, 12 portarias, 12 resoluções, 7 leis complementares,
1 IN, 1 parecer. O número real fica entre 177 e 368: o estrito perde cabeçalho sem contexto
de abertura (a maior região sem fronteira tem 1,43 milhão de caracteres); o largo conta
cabeçalho citado em maiúsculas.

**Repetição:** **17,3% do texto** das 32 coletâneas é removível — **15,6%** se repete entre
coletâneas (MT-NUC08 75%, MT-NUC05 74%, AC-N06 52%, MS-NUC05 40%) e **1,7%** repete norma
avulsa já no corpus (ex.: Lei GO 18.104/2013 e IN SEMAD 3/2025 dentro das coletâneas de GO —
na busca de compensação de RL, 7 das 8 vagas são pares duplicados). Três coletâneas trazem
cabeçalho de norma **federal** (MS-NUC04: 2, MT-NUC12: 1).

### 3.3 Corpus resultante (muda a conta)

| | Hoje (dev) | Depois do desmembramento |
|---|---:|---:|
| Documentos de legislação | 113 | **258 a 449** (81 avulsos + 177…368 atos) |
| Fontes | 395 | **540 a 731** (282 SEMAD ganham linha) |
| Chunks | 32.161 | **~27.900** (−17,3% do texto das coletâneas por deduplicação; o re-fatiamento por artigo do ADR-041 mexe pouco no total) |

### 3.4 Como separar

```
coletânea (arquivo, hash)                          ← documento de origem, não fonte citável
  └─ fronteiras candidatas
       sinal 1: cabeçalho de impressão (URL + página n/m) → troca de URL = troca de documento
       sinal 2: cabeçalho formal do ato em contexto de abertura
  └─ identidade proposta: tipo + órgão + número + ano, normalizada
       (função única; nunca string crua — mesma regra do dedupe de identificador)
  └─ agrupamento por identidade
       mesmo texto em várias coletâneas → 1 fonte, N proveniências
       texto diferente do mesmo ato       → versões (compilada × original), não duplicata
  └─ revisão humana das fronteiras por coletânea (dry-run com relatório)
  └─ fonte_normativa (bruto) → conferência contra URL oficial (proposto) → Ísis (validado)
```

`proveniencia(fonte_versao_id, documento_origem_id, pagina_inicio, pagina_fim, url_impressa,
impresso_em, trecho_hash)`. O Acre não tem cabeçalho de página: só o sinal 2, com revisão mais
pesada. LLM **não** decide fronteira; pode propor ementa ou órgão faltante, sempre `proposto`.

**Custo de reconhecimento:** fronteira e identidade saem de regex e dos cabeçalhos de impressão
já no texto — sem OCR nem chamada paga. O custo real é a revisão humana: 177 a 368 fichas, com
a lista de atos da Ísis (Q-ISIS-19) encurtando a conferência. Ato sem ano (22 a 75) e regiões
sem fronteira ficam `nao_determinado` até a revisão.

---

## 4. As quatro naturezas

Todas pendem de `fonte_normativa` (identidade, nível, status, versão, hash, proveniência).
Chunk indexa; a tabela tipada responde.

```
exigencia_tr        (fonte_versao_id, orgao, uf, rito, tipo_licenca, peca_governada,
                     edicao, qualidade_leitura)
exigencia_tr_item   (exigencia_tr_id, ordem, texto_literal, obrigatoriedade
                     [obrigatorio|condicional], condicao, pagina, secao, anexo)

precedente          (fonte_versao_id, tenant_id NOT NULL, orgao, instancia, processo,
                     tipo_decisao, data, objeto, resultado, situacao_consultada, alcance)
precedente_motivo   (precedente_id, motivo_literal, dispositivo_invocado → dispositivo,
                     exigencia_invocada → exigencia_tr_item, pagina)

procedimento        (fonte_versao_id, sistema, versao_sistema, codigo_erro,
                     mensagem_literal, mensagem_normalizada, contexto_tela,
                     precondicoes, resultado_esperado, data_referencia)
procedimento_passo  (procedimento_id, ordem, acao, pagina)

interpretacao       (fonte_versao_id, orgao, especie [ojn|parecer|despacho|nota_tecnica],
                     numero, processo_sei, data, questao, conclusao, alcance)
interpretacao_norma (interpretacao_id, fonte_normativa_id, dispositivo)
interpretacao_ressalva
                    (interpretacao_id, citacao_literal, pagina, trecho_hash,
                     referencia_resolvida → fonte_normativa, tipo_erro
                     [esfera|numero|ano|vigencia|inexistente], verificado_por,
                     verificado_em, fonte_verificacao_url, efeito [suspende|anota])
```

Exemplo que o desenho precisa aguentar — Parecer 84 (SEI 202600017013170): literal "Decreto
Federal 9.710/2020" → `referencia_resolvida` = Decreto 9.710/2020 **de Goiás**
([legisla.casacivil.go.gov.br](https://legisla.casacivil.go.gov.br/pesquisa_legislacao/103356/decreto-9710)),
`tipo_erro = esfera`, `efeito = suspende`. O literal do órgão não é emendado. `procedimento` é
achado por código ou mensagem literal (índice exato + `tsvector`); ausência devolve "não
localizado" com razão. `precedente` é privado do tenant: indeferimento de cliente não vira
corpus global.

---

## 5. Recuperação

### 5.1 O que muda

| Hoje | Alvo |
|---|---|
| Cascata remove UF, depois demanda, depois as duas ([legislacao.py:346–357](../../app/agents/legislacao.py#L346-L357)) | conjunto elegível fixo; **vazio com razão** |
| `nao_identificado` → sem filtro, `min_similarity=0.0` ([:316–334](../../app/agents/legislacao.py#L316-L334)) | objetivo não resolvido → `contexto_insuficiente` |
| demanda e UF embutidas no texto da pergunta ([:307–310](../../app/agents/legislacao.py#L307-L310)) | escopo só em filtro; o texto é a pergunta |
| `except Exception: return []` engole a recusa do ADR-040 ([:370–375](../../app/agents/legislacao.py#L370-L375)) | `falha_de_busca` / `espaco_vetorial_incompativel` sobem |
| `min_similarity` aplicado **depois** do `LIMIT` ([knowledge_catalog.py:479–481](../../app/services/knowledge_catalog.py#L479-L481)) | limiar por uso, dentro do elegível |
| ivfflat + filtros pode devolver menos que `limit` | busca exata sobre o elegível |
| `vigente_em` existe e ninguém passa | data de referência obrigatória |
| sem deduplicação; não devolve `dispositivo` | uma vaga por dispositivo; devolve fonte, versão, dispositivo, nível, status |
| só vetor; zero `tsvector` no repositório | híbrida com RRF |
| `rota_shadow` carimba `confianca: alta` e lê chunk sem tenant | confiança é dado do resultado; predicado de tenant (#245) |

### 5.2 Consulta alvo (esboço)

```sql
WITH elegivel AS (
  SELECT t.id, t.fonte_versao_id, t.dispositivo, t.embedding, t.tsv, f.nivel_autoridade
  FROM trecho_normativo t
  JOIN fonte_normativa_versao v ON v.id = t.fonte_versao_id
  JOIN fonte_normativa f        ON f.id = v.fonte_id
  WHERE f.nivel_autoridade   = ANY(:niveis_do_uso)
    AND v.status_validacao   = ANY(:status_do_destino)      -- peça: {validado}
    AND (v.vigencia_inicio IS NULL OR v.vigencia_inicio <= :data_ref)
    AND (v.vigencia_fim    IS NULL OR v.vigencia_fim    >= :data_ref)
    AND f.esfera = ANY(:esferas)                           -- ADR-034
    AND (f.uf IS NULL OR f.uf = :uf)
    AND :objetivo = ANY(f.objetivos)
    AND t.embedding_model = :modelo                        -- ADR-040
    AND (t.tenant_id IS NULL OR t.tenant_id = :tenant)
),
vet AS (SELECT id, row_number() OVER (ORDER BY embedding <=> :q) AS r
        FROM elegivel ORDER BY embedding <=> :q LIMIT 50),
lex AS (SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, :tsq) DESC) AS r
        FROM elegivel WHERE tsv @@ :tsq ORDER BY ts_rank_cd(tsv, :tsq) DESC LIMIT 50)
SELECT id, sum(1.0 / (60 + r)) AS rrf
FROM (SELECT * FROM vet UNION ALL SELECT * FROM lex) u
GROUP BY id ORDER BY rrf DESC;
-- depois: uma vaga por (fonte, dispositivo); interpretação anexada à norma que refere.
-- COUNT(*) FROM elegivel = 0 → vazio com a razão do filtro que esvaziou.
```

Vigência desconhecida **não** vira vigente: vai marcada e só entra onde o uso aceita "vigência
não determinada". `tsvector` com a configuração `portuguese` (existe no dev); `unaccent` está
disponível e **não instalado** em produção. Antes do ranking, a **consulta por identidade**:
se a pergunta ou a regra (ADR-073) traz norma e dispositivo, busca-se o dispositivo por ID.

### 5.3 Contrato de retorno

```
{ trechos: [...], interpretacoes_anexadas: {dispositivo: [...]},
  vazio: null | {razao: contexto_insuficiente|sem_fonte_elegivel|fora_da_cobertura|
                        falha_de_busca|espaco_vetorial_incompativel,
                 filtro_que_esvaziou, filtros_aplicados},
  filtros_aplicados, modelo, metodo: "identidade"|"hibrido_rrf" }
```

---

## 6. Citação por claim e anti-invenção

### 6.1 O que existe

| Mecanismo | Quando | O que faz | Lacuna |
|---|---|---|---|
| `persist_object` ([evidence.py:113–117](../../app/services/evidence.py#L113-L117)) — **ativo** | antes de gravar conclusão | extrai citações do `statement` por regex e exige que estejam nas normas-premissa | **forma não reconhecida passa sem checar** (LC 140/2011, "Res. CONAMA 237/1997", "Lei GO 18.104/2013", norma sem ano); cada texto de norma só indexa a **primeira** citação ([citation_evaluator.py:296–299](../../app/services/citation_evaluator.py#L296-L299)) → rejeição falsa de quem cita a segunda; dispositivo nunca conferido ("art. 999 da Lei 12.651/2012" passa); "art. 61-A" não é capturado (#243) |
| Redator e Diagnóstico (legado) | depois do LLM | marcam e seguem | parados; não bloqueiam |
| `lookup_enquadramento` (legado) | enquadramento de auto | número como token | conferência de ano é inócua; parado |
| Premissa só de fonte primária do caso | ADR-069 | norma citada tem de ser documento do caso | o corpus não é premissa possível hoje |

### 6.2 O que falta para validar antes

1. O envelope entrega as fontes elegíveis **com IDs** (`fonte_versao_id`, dispositivos).
2. O schema de saída exige, por afirmação, `citacoes[{fonte_versao_id, dispositivo, localizador}]`.
3. Verificação determinística **antes de emitir**: ID ∈ envelope; dispositivo existe naquela
   versão; status serve ao destino; vigência vale na data de referência.
4. Detector de menção sem vínculo (o `citation_evaluator`, com padrões corrigidos) varre o texto:
   **menção a norma sem ID é citação órfã e bloqueia a saída**.
5. Ressalva de interpretação suspende a afirmação que se apoia na referência errada.

---

## 7. Avaliação da recuperação

### 7.1 O que existe

- **As três buscas de fumaça** ("intervenção em APP utilidade pública", "impedimento crédito
  rural embargo ambiental", "DOF transporte produto florestal nativo") estão só em relatório —
  **não há script**, não rodam em CI, conferência a olho do top-5.
- `scripts/medir_defesa_federal.py`: 5 perguntas, alvo por **regex no texto do chunk** — o
  `art61a` sai "recuperado" com top-8 sem o art. 61-A (falso positivo). A trava de impressão
  digital espera 31.744 chunks / 102 documentos; o dev tem 32.161 / 113 — **a medição completa
  recusa rodar** (#246).
- Testes de busca em CI usam vetor constante `[0.1]*768`: provam montagem de filtro, **não
  qualidade**. `test_auto_infracao_extraction.py:77–84` chama embedding real sem mock (401
  engolido no CI; chamada paga com chave local).

### 7.2 Conjunto de sondas

`tests/recuperacao/sondas.yaml`, versionado, 30–50 itens:

```yaml
- id: fed-6514-art18
  pergunta: "descumprimento de embargo, qual a sanção"
  contexto: {objetivo: defesa_auto, esfera: [federal], uf: GO, data_ref: 2026-09-18, uso: peca}
  alvo: [{fonte: "DECRETO|UNIAO|6514|2008", dispositivo: "18"}]
  anexos_esperados: [{fonte: "OJN|PFE-IBAMA|6|2009"}]
- id: neg-uf-sem-corpus
  pergunta: "..."
  contexto: {objetivo: car, esfera: [estadual], uf: RR, uso: peca}
  vazio_esperado: sem_fonte_elegivel
```

| Grupo | Sondas | Para quê |
|---|---:|---|
| Norma federal com dispositivo | 10 | art. 18 do 6.514 (hoje na 37ª), 61-A do Código Florestal, art. 71 da Lei 9.605 |
| Norma estadual pós-desmembramento (MS, MT, AC, GO) | 12 | prova que o ato saiu da coletânea com identidade |
| Interpretação anexada, sem deslocar a norma | 4 | OJN 06/2009 anexada ao art. 18 |
| Exigência (TR) e procedimento (SIGCAR por mensagem) | 6 | tabelas tipadas |
| Vigência (norma revogada × data de referência) | 4 | ADR-037 |
| **Controle negativo** (fora do corpus, UF sem corpus, objetivo não resolvido, dispositivo inexistente) | 8 | vazio com a razão certa |

**Métricas e portão:** recall@5 ≥ 0,9 nas positivas (alvo por ID de fonte + dispositivo);
groundedness 100% (toda citação resolve para trecho recuperado e elegível; amostra humana para
suporte semântico); **zero citação órfã**; controle negativo 100% vazio com a razão esperada.
A Ísis valida os alvos antes da sonda valer.

**Onde roda (decisão do André, 18/09):**

| Camada | O quê | Quando |
|---|---|---|
| Contrato | filtro antes do ranking, nunca relaxa, vazio com razão, uma vaga por dispositivo, citação por ID bloqueia órfã | todo PR, vetores sintéticos, sem API |
| Qualidade | recall@5, groundedness, controle negativo | **PR que toque recuperação, corpus, chunking ou embedding** + **rodada noturna completa**; corpus de homologação restaurado de snapshot + vetores das perguntas em cache |

As sondas nascem `proposto` e o curador valida o alvo (mesmo ciclo do corpus).

---

## 8. Confronto com o insumo

[`ARQUITETURA_DADOS_RAG_REGENTE_v1.md`](ARQUITETURA_DADOS_RAG_REGENTE_v1.md) (§4–§6) × ADR-075.
Onde divergem, o ADR vence — nasceu de medição —; a divergência fica registrada, não apagada.

### 8.1 Converge

- Seis níveis (norma · interpretação oficial · exigência · procedimento · precedente · radar);
  radar nunca citável.
- Conflito: autoridade e competência antes de similaridade; vigente antes de histórico sem
  apagar; divergência material **suspende a afirmação** e abre revisão.
- `bruto → proposto → validado`; peça assinada só cita `validado`; `proposto` interno com selo.
- Nova versão nunca sobrescreve (`substitui_versao`).
- Filtro obrigatório antes do ranking; vazio com a razão; **nunca relaxa**; híbrida tsvector +
  pgvector com RRF.
- Citação por claim (norma + versão + dispositivo + localizador), verificada **por id** antes de
  emitir; órfã bloqueia.
- As quatro naturezas com tabela própria; `interpretacao.ressalvas` com o Parecer 84.
- Espaço vetorial travado (ADR-040); lições de chunking do ADR-041, com a tese refutada.
- Sondas 30–50, recall@5 ≥ 0,9, groundedness 100%, zero órfã, controle negativo.

### 8.2 O documento tem e o ADR não — incorporar

**Incorporado em 19/09:** os cinco itens aprovados pelo André estão no
[Adendo do ADR-075](../adr/075-zona-normativa-hierarquia-e-recuperacao.md#adendo-de-19092026--cinco-itens-incorporados-do-insumo)
(A1 a A5).

| Item do documento | Incorporação |
|---|---|
| Tabela `validacao_norma` (alvo, validador, decisão, nota, data) | é a tabela do evento append-only do §4 do ADR |
| `dispositivo` com **caminho completo** (`Lei 12.651/2012, art. 61-A, §4º`) e ordem | entra no esquema; é a chave que a citação por id usa |
| Corpus é **leitura** para o tenant; escrita só com papel administrativo (D6 do Codex) | vale com a decisão 2: escrita e validação por papel de curadoria |
| Dado de caso **nunca** entra no corpus nem em embedding global | fronteira dura; o `precedente` privado é o caso concreto dela |
| "Ato superior não resolve automaticamente detalhe local" na regra de conflito | entra no §2 do ADR |
| `hash_documento` + `storage_path` na norma (original no R2) | proveniência guarda hash e objeto do original, não só do texto |
| Zero tolerância a "fonte normativa adulterada" | conferência periódica do hash contra o original |
| Caso Jobson: consulta de novo CAR devolveu licenciamento, fiscalização e TFAGO | evidência adicional do defeito da cascata (afirmação do documento, não medida nesta frente) |

### 8.3 O ADR tem e o documento não — o que a medição achou

- **32 coletâneas**, não "113 documentos": 29 compêndios + 3 de GO gravadas como `manual`, 77,1%
  dos chunks; são **páginas impressas do navegador** — desmembramento determinístico, coletânea
  como **proveniência**; 177 a 368 atos dentro; só 2 com sumário.
- **17,3% do texto é repetição** (15,6% entre coletâneas, 1,7% com norma avulsa); 7 das 8 vagas
  de GO eram pares duplicados; uma fonte ocupa uma vaga por dispositivo.
- **Dev ≠ produção**: 32.161 / 113 × 28.891 / 64.
- **A Legislação já está desligada** desde o ADR-069; só `GET /knowledge/search` consulta o corpus;
  o contrato entra antes de religar, e sondas verdes são condição (decisão 6).
- **A trava de citação ativa tem lacunas** (#243): o que a regex não reconhece passa; a segunda
  norma de uma fonte é recusada. Correção em PR próprio.
- O `citation_evaluator` **não consulta o banco**; `min_similarity` real é 0,0; as buscas de fumaça
  não têm script; a medição existente recusa o corpus atual.
- Busca **exata** sobre o elegível (ivfflat + filtro devolve menos que o pedido, #247);
  `unaccent` não instalado em produção.

### 8.4 Divergências — o ADR vence

| # | Documento | ADR-075 | Por quê |
|---|---|---|---|
| D1 | `status_validacao` também em `norma_chunk` | só na versão da fonte; o trecho herda | reindex (ADR-041) zeraria; provider (ADR-040) duplicaria; UPDATE reescreve o ivfflat |
| D2 | Migração do corpus = "classificar por nível e estado" (§10) | **reingestão** de 80,7% (32 coletâneas + 5 manuais + 18 SEMAD) | só 19,3% é classificável pelo gravado |
| D3 | OJN 06/2009 chamada de "parecer doutrinário" (§1, princípio 6) | **interpretação oficial** (nível 2), anexada à norma | é da PFE-IBAMA, vincula os procuradores (ADR-038 §6); o defeito era disputar vaga |
| D4 | `validado` = "assinado pela Ísis" | papel de curadoria delegável; a trilha grava quem | decisão 2 |
| D5 | "Roda em CI" | por PR que toque recuperação/corpus/chunking/embedding + noturna | decisão 4 |
| D6 | `nivel_autoridade ≤ o permitido para o uso` (ordem numérica) | conjunto de níveis permitido por uso; interpretação anexada | ordem única esconderia a OJN quando ela é o que importa |
| D7 | `precedente` na zona normativa, "global entre tenants" (§2) | privado da consultoria; promoção é decisão do tenant | decisão 3 |
| D8 | Coletânea como `norma` (esquema sem proveniência) | coletânea é **documento de origem**; cada ato é fonte com proveniência | medição do §3 |

### 8.5 Fora da zona normativa (anotado, não tratado aqui)

- §3 do documento propõe tabelas separadas para observação, derivação e conclusão; o ADR-070
  escolheu envelope único — **o ADR-070 vence** (decisão do André de 17/09).
- §3.2 exige premissa só `fato_documental` para risco; decisão do André: `fato_documental`
  aprovada **ou** observação revisada e aceita (ADR-070 §14). `lacuna` não satisfaz — converge.
- §3.4 trata `espolio` como papel; Ontologia e ADR-070 §7: espólio é entidade, não papel.
- §8 traz **legal hold** para caso com peça protocolada — **incorporado ao ADR-070 §17 em 19/09**.
- §9 afirma **produção sem backup** (`backups: []`, PITR desligado). **Confirmado pelo André;
  decisão já tomada** — não é reaberto aqui.
