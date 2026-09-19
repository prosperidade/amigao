# ARQUITETURA DE DADOS, CONHECIMENTO E RAG — REGENTE AMBIENTAL

**Versão 1.0 · 17/09/2026**

Documento de arquitetura. Define o modelo de dados, o banco de conhecimento
normativo, a recuperação e as regras de proveniência que sustentam a cadeia
decisória descrita no Plano Diretor v1.1.

**Deriva de:** Plano Diretor v1.1 (§3 contratos, §6 modelo, §7 acervo) · mergulho
estrutural de 17/09 · spec v0.1 e segunda validação da Ísis · lições medidas das
Frentes C-L (ADRs 062-069).
**Incorpora padrões externos**, creditados onde aparecem: documentos 08/09/10 de
arquitetura patrimonial e documentos 07/07a do Farol (corpus tributário).

---

## 1. PRINCÍPIOS

Sete regras que o schema e a recuperação implementam. Não são aspiração — cada
uma corresponde a um defeito medido neste sistema.

| # | Princípio | Defeito que ele corrige |
|---|---|---|
| 1 | **Uma saída de agente não é evidência primária** | Circuito de autoconfirmação: leitura achatada → auditoria contraditória → diagnóstico transformando ausência em risco alto |
| 2 | **Desconhecimento e falha nunca viram ausência ou regularidade** | "Não há embargo registrado" sem consulta a órgão (DIAG-005); `has_embargo=False` lido como ausência verificada |
| 3 | **Cálculo e regra são determinísticos; julgamento é LLM; decisão é humana** | Auditor sem LLM está certo; geometria inexistente; recuperação por similaridade chamada de relevância jurídica |
| 4 | **Toda afirmação aponta para premissas recuperáveis, por id** | NIRF `6.442.022-1` gravado com confiança alta em três processos — era o exemplo escrito no prompt |
| 5 | **Nova versão nunca sobrescreve** *(Farol 07a §3.6)* | Norma ingerida substitui a anterior; impossível reconstruir o que se afirmou em agosto |
| 6 | **Autoridade da fonte é campo, não suposição** *(Farol 07a §4)* | Parecer doutrinário (OJN 06/2009) ocupando 6 das 8 vagas na busca da defesa |
| 7 | **Declarado e confirmado são campos distintos** *(doc 08 §7)* | Escritura tratada como certidão de matrícula; "último nome encontrado" como titular atual |

**Regra de ouro, adaptada do Farol:** a LLM nunca calcula área, nunca decide
vigência e nunca afirma ausência. Números vêm do serviço geoespacial; vigência vem
da regra temporal; ausência exige registro de consulta. Resposta sobre "quanto" ou
"desde quando" sem lastro determinístico é **bug de severidade máxima**.

---

## 2. AS QUATRO ZONAS DE DADOS

O sistema separa quatro zonas com regras de acesso, versionamento e retenção
próprias. Misturá-las é a origem de metade dos defeitos.

| Zona | O que guarda | Compartilhamento | Versionamento |
|---|---|---|---|
| **Normativa** | Normas, dispositivos, interpretações oficiais, procedimentos de órgão | **Global**, entre tenants | Por versão da norma; nunca sobrescreve |
| **Regras** | As regras executáveis derivadas do método (325 + cartorárias) | Global, com ativação por escopo | Por conjunto publicado e homologado |
| **Caso** | Documentos, evidências, observações, conclusões, decisões | **Por tenant**, isolado | Por versão de documento e de conclusão |
| **Operacional** | Execuções, custos, manifestos, telemetria | Por tenant, agregável | Imutável |

**Fronteiras duras:**
- Dado de caso **nunca** entra no corpus normativo nem em embedding global.
  *(doc 09: "dados de famílias nunca entram no corpus normativo")*
- Corpus normativo é **leitura** para o tenant; escrita exige papel administrativo
  (hoje qualquer usuário interno escreve — dívida D6 da auditoria Codex).
- Regra é **conteúdo versionado no banco**, não código e não chunk.

---

## 3. ZONA DE CASO — O MODELO DE EVIDÊNCIA

### 3.1 Os quatro objetos

Substituem o dict que hoje trafega entre agentes. Cada um com identidade e versão.

```
fonte_primaria     documento original ou registro de consulta identificável
observacao         o que a fonte declara, com âncora no texto
derivacao          cálculo ou regra, com entradas referenciadas e versão do método
conclusao          interpretação sustentada por observações, derivações e normas
```

**Um AIJob nunca é fonte primária.** O tipo `auditor` deixa de ser aceito como
origem de evidência.

### 3.2 Entidades

```sql
-- DOCUMENTO E VERSÃO -------------------------------------------------
documento              (id, tenant, caso, especie, emissor, data_emissao,
                        storage_key, hash_original, classificacao_original,
                        classificacao_revisada, revisor, motivo_reclassificacao)
documento_versao       (id, documento, versao, hash_texto, paginas, metodo_ocr,
                        cobertura_chars, completa, falhas jsonb, extraido_em)
fragmento              (id, documento_versao, pagina, posicao_inicio, posicao_fim,
                        trecho)

-- EVIDÊNCIA -----------------------------------------------------------
observacao             (id, versao, tenant, caso, documento_versao, fragmento,
                        predicado, valor_literal, valor_normalizado, unidade,
                        sujeito_ref, objeto_ref, papel,
                        data_documento, data_ato, eficacia_inicio, eficacia_fim,
                        metodo, cobertura, ancora_ok, certeza,
                        estado_conhecimento, estado_revisao, linhagem jsonb)

derivacao              (id, versao, tenant, caso, tipo, metodo, metodo_versao,
                        entradas jsonb,        -- ids de observações/derivações
                        resultado jsonb, unidade, tolerancia, executado_em)

conclusao              (id, versao, tenant, caso, classe, texto,
                        premissas jsonb,       -- ids, nunca texto
                        normas jsonb,          -- id + versão + dispositivo
                        regras jsonb,          -- id + versão do conjunto
                        aplicabilidade, justificativa_aplicabilidade,
                        certeza, impacto, urgencia, fundamento_temporal,
                        limites, estado_revisao, estado_atualidade,
                        autor_agente, substituiu_versao)

revisao                (id, alvo_tipo, alvo_id, alvo_versao, acao, autor,
                        justificativa, premissas_no_momento jsonb, decidido_em)
```

**`classe` da conclusão** é enum fechado: `fato_documental` · `divergencia` ·
`lacuna` · `hipotese` · `risco` · `orientacao` · `escopo_proposto`.

**Regras duras no schema:**
- `risco` exige pelo menos uma premissa da classe `fato_documental` **e**
  `justificativa_aplicabilidade` não nula;
- `escopo_proposto` exige `finalidade` e referência a passo de rota aprovado;
- `lacuna` nunca satisfaz o requisito de premissa de `risco`.

### 3.3 Estados de conhecimento

Enum obrigatório em `observacao` e em toda conclusão que afirme ausência:

| Estado | Requisito de gravação |
|---|---|
| `nao_determinado` | — |
| `nao_localizado_no_material` | escopo e cobertura declarados |
| `ausencia_verificada_no_escopo` | **consulta_ref obrigatória**: órgão, identificadores, data, resposta preservada |
| `nao_aplicavel` | avaliação de aplicabilidade registrada |
| `conflitante` | ids das fontes incompatíveis |
| `falha_de_verificacao` | erro preservado |

**Constraint:** `ausencia_verificada_no_escopo` sem `consulta_ref` é rejeitada pelo
banco. Isso mata DIAG-005 na camada de dados, não na de prompt.

### 3.4 Pessoas, papéis e participação

*(padrão do doc 08 §7: "relação, parentesco declarado e efeito jurídico são campos
distintos")*

```sql
parte           (id, tenant, tipo_pessoa, nome, documento_normalizado,
                 documentos jsonb, aliases jsonb)
participacao    (id, parte, papel, contexto_tipo, contexto_id,
                 fundamento_observacao, intervalo_inicio, intervalo_fim,
                 estado_confirmacao)
```

**`papel`** é enum: `adquirente` · `transmitente` · `conjuge` · `representante` ·
`procurador` · `inventariante` · `espolio` · `confrontante` · `credor` · `devedor` ·
`arrendatario` · `titular_declarado`.

**`estado_confirmacao`**: `declarado` (a escritura diz) × `confirmado` (a certidão
comprova). A mesma pessoa é compradora num ato e vendedora em outro; `proprietarios`
como `{nome, cpf}` deixa de existir.

**Espólio** é parte representada com vínculo ao falecido — não substitui CPF, não
vira PJ. Inventariante exige documento, alcance e validade.

### 3.5 Atos registrais e temporalidade

```sql
ato_registral   (id, documento_versao, matricula_ref, serventia,
                 referencia_interna, tipo, data_ato, texto_fragmento)
relacao_ato     (id, ato_origem, ato_destino, tipo, fundamento_textual)
```

`referencia_interna` (`AV.10`) **sozinha não identifica** — documento + matrícula +
serventia delimitam o ato. `tipo` de relação: `baixa` · `aditivo` · `retificacao` ·
`cancelamento`.

Vigência é **derivada**, nunca extraída: regra sobre o grafo de relações + datas +
tipo, com a data de referência da análise. Ausência de baixa **não** produz
`vigente`; produz `vigente_segundo_o_material`.

### 3.6 Geometria

*(hoje inexistente: `Property.geom` nunca gravado, KMZ guardado sem abrir, sem
ST_Area, sem shapely)*

```sql
arquivo_geo     (id, documento, formato, hash, crs_origem, feicoes_detectadas)
feicao          (id, arquivo_geo, tipo, identificador_interno, geom geometry)
medicao         (id, origem_tipo, origem_id, valor, unidade, metodo,
                 crs_calculo, versao_metodo, calculado_em)
```

`origem_tipo`: `feicao_calculada` · `declaracao_textual` · `registro`.
**"Área do texto do CAR", "área calculada do KMZ" e "área registral" são medições
diferentes mesmo quando coincidem.** Cálculo em CRS métrico; área em graus não é
hectare. PostGIS já está no stack.

Comparação publica: valores originais, delta absoluto, percentual **com
denominador declarado** e tolerância com método. *(A Ísis usa a área documental
como denominador; o comparador atual usa o maior valor — os dois precisam ser
identificados.)*

---

## 4. ZONA NORMATIVA — O BANCO DE CONHECIMENTO

### 4.1 O problema atual

32.161 chunks, 113 documentos, **todos no mesmo nível de autoridade**. Norma
federal ingerida com rigor, coletânea estadual, parecer doutrinário — nada os
distingue. Consequência medida: a OJN 06/2009, um parecer, ocupa 6 das 8 vagas na
busca de defesa do art. 18 do Decreto 6.514, e a norma central fica fora.

### 4.2 Hierarquia de fontes

*(padrão do doc 09 §4, adaptado ao domínio ambiental)*

| Nível | O que é | Pode ser citado em peça? |
|---|---|---|
| 1 | **Norma** — lei, decreto, resolução, IN, portaria | Sim |
| 2 | **Interpretação oficial** — parecer em processo, resposta a consulta, nota técnica de órgão | Sim, identificada como interpretação |
| 3 | **Exigência** — TR, manual, checklist de órgão | Sim, como exigência procedimental |
| 4 | **Procedimento** — roteiro operacional de sistema (SIGCAR) | Não; orienta o consultor |
| 5 | **Precedente** — decisão do órgão em caso concreto (indeferimento) | Como referência, nunca como norma |
| 6 | **Radar** — doutrina, artigo, compilação de terceiro | **Nunca.** Descoberta apenas |

**Regra de conflito** *(doc 09 §4.1)*: autoridade e competência antes de
similaridade · texto vigente antes de histórico, sem apagar a história · ato
superior não resolve automaticamente detalhe local · **divergência material abre
tarefa de revisão e SUSPENDE a afirmação** — não escolhe a mais parecida.

### 4.3 Estados de validação

*(padrão do Farol 07a §4 — a ponte com a Ísis)*

| Estado | Significa | Onde pode aparecer |
|---|---|---|
| `bruto` | Ingerido, sem leitura humana | Backend apenas |
| `proposto` | Fonte conferida, proveniência completa, contraditório feito | Ambiente interno, com selo visível |
| `validado` | Assinado pela Ísis (quem, quando, decisão) | **Peça e resposta ao cliente** |

**Regra de produto: peça assinada só cita material `validado`.** Enquanto a
validação não acontece, o corpus cresce em `bruto/proposto` — nenhuma hora
perdida, nenhuma promessa indevida. Isso resolve o problema estrutural de ter 32
mil chunks sem ninguém ter conferido nenhum.

### 4.4 Esquema

```sql
norma           (id, tipo, identificador, orgao, esfera, uf,
                 data_publicacao, vigencia_inicio, vigencia_fim,
                 url_fonte, hash_documento, storage_path,
                 nivel_autoridade, status_validacao, versao, substitui_versao)

dispositivo     (id, norma, caminho, texto, ordem)
                 -- caminho: "Lei 12.651/2012, art. 61-A, §4º"

norma_chunk     (id, norma, dispositivo, texto, embedding vector(768),
                 tokens, hierarquia jsonb, referencias jsonb,
                 status_validacao, cobertura)

validacao_norma (id, alvo_tipo, alvo_id, validador, decisao, nota, data)
```

**Nova versão cria registro novo.** `substitui_versao` preserva a cadeia; qualquer
afirmação histórica é reconstruível contra a versão vigente à época.

### 4.5 As outras naturezas

Nem tudo que a Ísis trouxe é norma. Quatro tabelas próprias, porque destino
diferente:

```sql
exigencia_tr    (id, orgao, tipo_peca, uf, versao, itens jsonb, storage_path)
                 -- os 102 TRs do IPE: o que a peça precisa conter

precedente      (id, orgao, tipo_decisao, data, resultado,
                 motivos jsonb, natureza, caso_ref, storage_path)
                 -- indeferimentos com motivo declarado

procedimento    (id, sistema, mensagem_erro, causa, passos jsonb, versao)
                 -- roteiros SIGCAR, indexados por mensagem de erro

interpretacao   (id, orgao, processo_ref, pergunta, resposta,
                 dispositivos_citados jsonb, data, ressalvas)
                 -- consulta SEI e pareceres
```

**`interpretacao` tem campo `ressalvas`** por um motivo concreto: o Parecer 84/2026
cita "Decreto Federal 9.710/2020" quando o 9.710/2020 é estadual de Goiás. Erro
material do órgão não vira verdade do sistema — a ressalva viaja com a
interpretação.

---

## 5. ZONA DE REGRAS — O MOTOR DETERMINÍSTICO

*(padrão convergente: doc 09 "regras executáveis separadas dos textos
recuperáveis" · Farol "a LLM nunca calcula" · ADR-042)*

As 325 regras das matrizes **não viram 325 trechos de prompt nem 325 `if`**.

```sql
regra            (id, versao, eixo, objetivos jsonb, uf, alcance_territorial,
                  competencia, orgao, vigencia_inicio, vigencia_fim,
                  predicados jsonb,      -- entradas tipadas exigidas
                  condicao jsonb,        -- linguagem restrita, não código
                  resultado, mensagem, consequencias jsonb,
                  severidade, certeza, exige_decisao_profissional,
                  norma_ref, norma_versao, dispositivo,
                  origem jsonb,          -- planilha, aba, linha, hash
                  autor, homologador, homologado_em,
                  exemplos jsonb)        -- positivo, negativo, incompleto,
                                         -- conflitante, fronteira

conjunto_regras  (id, versao, publicado_em, homologador, escopo jsonb, ativo)

avaliacao_regra  (id, regra, regra_versao, conjunto_versao, caso,
                  estado, entradas_usadas jsonb, entradas_faltantes jsonb,
                  trilha jsonb, avaliado_em)
```

**Linguagem de condição restrita.** Operadores conhecidos, predicados tipados.
Nunca Python ou SQL arbitrário importado de planilha. Regra que exige conceito não
representado na ontologia é **recusada na publicação, com motivo**. Nenhum LLM
traduz e ativa regra sem conferência humana.

**Estados de avaliação:** `aplicavel_disparou` · `aplicavel_nao_disparou` ·
`nao_aplicavel` · `indeterminado` · `conflito` · `erro_execucao`.

**Valor desconhecido é desconhecido, nunca falso.** O relatório lista também as
regras não avaliadas e as entradas faltantes. **"Zero regras disparadas" significa
isso — não regularidade.**

**Aplicabilidade precede consequência.** A seleção considera objetivo, território,
competência, ato e datas. Regra federal pode integrar caso estadual; a UF do imóvel
não decide sozinha o órgão competente (ADR-034).

**Conflito de esferas** (protocolo da Ísis, v03) vira tabela de decisão homologada:
Constituição → competência privativa da União → competência concorrente do art. 24
→ contradição com norma geral. Proibido "federal sempre ganha" ou "mais restritiva
ganha". Indeterminado retorna `conflito` para decisão profissional.

**Motor cartorário** usa a mesma infraestrutura, com eixo próprio: espécie
documental, grafo de atos, vigência, cadeia dominial, participações. Insumo: a
matriz cartorária (INS-003).

---

## 6. RECUPERAÇÃO — COMO O AGENTE ACHA A NORMA

### 6.1 O defeito atual

`legislacao.py:346-356`: o filtro começa por UF + demand_type + esfera e **relaxa
em cascata** — tira a UF, depois o demand_type, até sobrar só similaridade.
`nao_identificado` vira "sem filtro" com `min_similarity=0.0`. Resultado medido no
caso Jobson: consulta sobre novo CAR retornou licenciamento, fiscalização e TFAGO.

### 6.2 O padrão correto

*(doc 09: "busca híbrida com filtros obrigatórios ANTES do ranking")*

```
1. FILTRO OBRIGATÓRIO (elimina, não pondera)
   · vigência na data de referência do caso
   · status_validacao conforme o destino (peça = só `validado`)
   · nivel_autoridade ≤ o permitido para o uso
   · competência e esfera compatíveis com o caso
   · objetivo canônico do atendimento

2. BUSCA HÍBRIDA no que sobrou
   · full-text em português (tsvector) + vetorial (pgvector)
   · fusão por RRF

3. SE NÃO SOBROU NADA
   → retorna VAZIO com a razão do filtro que esvaziou
   → NUNCA relaxa o filtro silenciosamente
```

**A diferença entre "não achei" e "achei outra coisa parecida" é a diferença entre
um sistema que o consultor pode assinar e um que ele não pode.**

### 6.3 Citação por claim

*(padrão do Farol 07a §6 e doc 09)*

Toda afirmação normativa carrega **norma + versão + dispositivo + localizador**.
Não é "esta resposta veio deste documento" — é "esta afirmação veio deste
dispositivo, nesta versão, nesta posição".

**Checagem anti-invenção, antes de emitir:** toda citação precisa existir no corpus
**por id**, não por semelhança de texto. Citação órfã é bug de severidade máxima e
bloqueia a saída. *(É o que mata a classe do NIRF que veio do exemplo do prompt: o
valor não existia no documento, e nada verificava.)*

### 6.4 Espaço vetorial travado

Mantido da ADR-040, com as lições das Frentes C-F:
`text-embedding-3-small`, 768 dimensões, chave da casa. Provider divergente ⇒
falha alta, **nunca fallback silencioso**. Troca de modelo exige re-embedding total
e registro em ADR.

### 6.5 Chunking — o que já sabemos

Patrimônio medido, não hipótese:
- unidade é o **dispositivo**, com caminho completo;
- documento não-articulado (plano, anexo, coletânea) herdava rótulo falso de artigo
  — guarda de sanidade corrige;
- **"artigo inteiro = melhor recuperação" foi REFUTADO por medição** (art. 61-A:
  posição 2→29 quando juntado). A decisão vale por *entrega* — o consultor recebia
  em cacos — com custo de recuperação declarado;
- NFKC destrói texto jurídico (`art. 5º` → `art. 5o`): normalizar **só ligaduras**;
- contagem de token por tiktoken real; teto de artigo 7.000, teto duro da API 8.192
  com guarda antes de embarcar;
- IVFFlat `probes=10`.

### 6.6 Avaliação da recuperação

*(padrão do Farol 07a §8)*

Hoje a ingestão usa três buscas de fumaça improvisadas. O alvo:

| Instrumento | Meta |
|---|---|
| 30-50 perguntas-sonda com dispositivo-alvo conhecido | recall@5 ≥ 0,9 |
| Groundedness | 100% — toda afirmação citada |
| Citação órfã | zero, por verificação de id |
| Controle negativo | perguntas cujo alvo **não** está no corpus retornam vazio com razão |

Roda em CI. As sondas nascem `proposto` e a Ísis valida — mesmo padrão do corpus.

---

## 7. ZONA OPERACIONAL — EXECUÇÃO AUDITÁVEL

```sql
execucao         (id, caso, snapshot jsonb, passos_previstos jsonb,
                  passos_concluidos jsonb, passos_pendentes jsonb,
                  passos_falhos jsonb, cursor, chave_idempotencia)

manifesto        (id, execucao, agente, skills_aplicadas jsonb,
                  skills_esperadas_ausentes jsonb, motivo_ausencia,
                  prompt_base, prompt_versao, system_hash, user_hash,
                  parametros jsonb, modelo, provider, tentativas,
                  resposta_bruta, custo, tokens_in, tokens_out)
```

**Hoje o AIJob não grava o prompt de sistema montado** — não há como saber depois
que skill entrou numa execução. Foi por isso que o caso #25 rodou sem a skill do
diagnóstico e ninguém percebeu.

**Skill obrigatória indisponível ⇒ estado visível de CAPACIDADE INSUFICIENTE**,
nunca omissão silenciosa.

---

## 8. RETENÇÃO, EXCLUSÃO E LGPD

*(padrão do doc 08 §1 e doc 10 §9: "exclusão é workflow auditável, incluindo
índices, caches, objetos e suboperadores"; "TTL por campo/objeto, não somente por
tabela")*

**O problema atual (#207):** `documents` e `extracted_field_staging` são CASCADE no
processo. Apagar um caso mata a prova — a matrícula continua afirmando um valor
cujo lineage aponta para ids que não existem mais. Em um sistema cujo princípio é
"tudo é auditável", isso é buraco estrutural.

**O alvo:**
- exclusão de caso é **workflow**, não DELETE: marca, propaga a índices, caches,
  objetos no R2 e filas, e registra;
- evidência que sustenta conclusão emitida tem **retenção própria**, independente do
  caso;
- `legal hold` para caso com peça protocolada;
- object keys aleatórias, sem nome de usuário *(doc 08 §4.1 — o Regente já faz:
  `tenant_1/process_23/uuid.pdf`)*;
- identificadores públicos não codificam tenant, UF nem significado.

---

## 9. SEGURANÇA — O QUE SE INCORPORA

*(doc 10, apenas o aplicável)*

| Controle | Estado no Regente |
|---|---|
| Isolamento por tenant na escrita | ✅ Frente 1 (#147): 404 nunca 403, validador único de relação |
| FK composta `(tenant_id, id)` | ❌ dívida #128 — o cinto que torna a validação à prova de regressão |
| RLS | ❌ ADR-001 assume a negativa; o lint prometido foi entregue no #147 |
| Corpus normativo com escrita administrativa | ❌ qualquer usuário interno escreve (D6 da auditoria Codex) |
| Hash chain de auditoria | ⚠️ existe, com 10 elos quebrados por race — dívida #217 |
| Backup gerenciado | ❌ **produção sem backup**: `backups: []`, PITR desligado |
| Segredo em log | ✅ zero tolerância mantida |

**Zero tolerância** *(doc 10 §2.1)*: vazamento cross-tenant · segredo em log ·
fonte normativa adulterada · execução arbitrária a partir de regra importada.

---

## 10. MIGRAÇÃO

| Grupo | Como migra | O que não volta |
|---|---|---|
| Documentos e extrações | Adicionar versão e fragmento; converter staging em observação preservando ids | Página, papel, trecho e data nunca registrados. Reextração onde necessário |
| Pessoas e atos | Participações a partir de vínculos comprovados; menções indeterminadas vão para revisão | Vendedor, titular atual e representante **não se inferem** de `proprietarios` |
| Conclusões antigas | Importar como legado, com cobertura explícita | `completed` **não** vira aprovado |
| `has_embargo=False` | Separar declaração, consulta e desconhecimento | Falso legado não vira ausência verificada |
| Corpus | Classificar por nível de autoridade e estado de validação | Nada vira `validado` sem assinatura |
| Regras | Inventariar ids, publicar versionado após homologação | Equivalência por nome parecido |
| Geometria | Ingerir originais, criar feições e medições | Número de área não reconstrói polígono |

**Um adaptador serve a UI legada durante a transição. Nunca duas escritas canônicas
concorrentes.**

---

## 11. O QUE ESTE DOCUMENTO NÃO RESOLVE

- **Correção jurídica das 325 regras.** O desenho define como recebê-las, executá-las
  e verificá-las; a correção é homologação da Ísis.
- **Cobertura por UF.** Presença de regra não prova cobertura operacional.
- **Determinismo do LLM.** Versionar entrada, modelo e saída torna auditável, não
  determinístico.
- **Qualquer documento, qualquer situação.** Nenhum schema finito cobre tudo. O
  contrato garante resposta íntegra para o não coberto: preservar material, declarar
  limite, permitir decisão. **"Não sei" rastreável é comportamento funcional;
  regularidade inventada não é.**

---

## ANEXO — ORIGEM DOS PADRÕES INCORPORADOS

| Padrão | Origem | Onde aparece aqui |
|---|---|---|
| Estados que não fingem valor | doc 08 §6.1 | §3.3 |
| Declarado × confirmado | doc 08 §7.1 | §3.4 |
| Relação, papel e efeito jurídico distintos | doc 08 §7.1 | §3.4 |
| Object keys aleatórias, id sem significado | doc 08 §4.1 | §8 |
| Exclusão como workflow que propaga | doc 08 §1.1 / doc 10 §9 | §8 |
| Hierarquia de fontes e conflito | doc 09 §4 | §4.2 |
| Regras executáveis separadas dos textos | doc 09 §1.1 | §5 |
| Divergência suspende claim | doc 09 §4.1 | §4.2 |
| Corpus normativo isolado do dado do cliente | doc 09 §1.1 | §2 |
| Três estados de validação | Farol 07a §4 | §4.3 |
| Nova versão nunca sobrescreve | Farol 07a §3.6 | §4.4 |
| Filtros obrigatórios antes do ranking | Farol 07a §6 / doc 09 | §6.2 |
| Citação por claim com localizador e versão | Farol 07a §6 | §6.3 |
| Anti-invenção por id, não por semelhança | Farol 07a §6 | §6.3 |
| Perguntas-sonda com dispositivo-alvo e gate | Farol 07a §8 | §6.6 |
| A LLM nunca calcula | Farol 07 | §1 |
| Zero tolerância | doc 10 §2.1 | §9 |

**O que o Regente já fazia melhor e permanece:** chunking por dispositivo medido e
refutado com evidência (Frentes C-F) · espaço vetorial travado com falha alta
(ADR-040) · âncora de valor no texto (#152) · observação tipada e vigência derivada
(ADR-065/066) · reconciliação por chave natural (ADR-067).

**O que foi recusado:** família/workspace como fronteira de tenant — aqui o tenant é
a consultoria, e trocar reabriria o que a Frente 1 fechou · banco de posições e
golden set de cálculo — pertencem ao domínio tributário, onde o motor calcula
imposto.

---

*Arquitetura de dados, conhecimento e RAG v1.0 — 17/09/2026. Implementa o Plano
Diretor v1.1. O vocabulário canônico vem da Ontologia (incremento 0); onde os dois
divergirem, a ontologia decide o nome e este documento decide a forma.*
