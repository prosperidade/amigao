# ADR-070 — Modelo de dados alvo: envelope epistêmico único + entidades de domínio tipadas

- **Data:** 17/09/2026
- **Estado:** proposta. Análise e desenho; **nenhuma migration escrita, nenhum schema alterado**.
- **Frente:** A — arquitetura de dados versionada (`docs/arquitetura-dados-adr070`)
- **Base inspecionada:** código em `b6df7e6` (pós-#172 e #173); rebaseado sobre `4def0cf`,
  que só acrescenta os docs do #175; banco dev
  `amigao_db` @ `127.0.0.1:15432`, alembic `c7e1a94d2f60`, somente leitura.
- **Complementa:** ADR-069 (contrato de evidência), ADR-062 a 068, ADR-036/037/038/040/041,
  rascunho ADR-042. **Nomes:** [Ontologia v1](../arquitetura/ONTOLOGIA_REGENTE_v1.md)
  (#175) decide os nomes; este ADR decide a **forma**.
- **Roteiro e evidências:** [MIGRACAO_MODELO_DADOS.md](../arquitetura/MIGRACAO_MODELO_DADOS.md).

> **Insumo ausente.** O pedido previa versionar `ARQUITETURA_DADOS_RAG_REGENTE_v1.md`
> como passo zero. O arquivo não foi entregue e não existe no disco (busca por nome e
> pelos termos distintivos). O alvo usado aqui é o
> [Plano v1.1 §6](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md#6-modelo-de-dados) e o
> [Mergulho §2.3–§2.4 e §5](../arquitetura/MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md#5-m4--modelo-de-dados-e-migração),
> que nomeiam as mesmas entidades e os mesmos sete grupos de migração. Quando o
> documento chegar, a reconciliação é um item de execução (ver fim).

> **Numeração.** O Plano §10.2 reservou 070 para "entrada semântica e cartorário". Este
> ADR ocupa 070 com o modelo de dados que o Incremento 2 executa; o comportamento do
> motor cartorário entra como adendo deste ou em número novo — decisão do André.
> Forma de geometria e de regras é fixada aqui; método de cálculo (071) e linguagem de
> regra (072) continuam nos ADRs reservados e podem emendar esta forma.

## Contexto (medido)

1. O #172 criou o envelope epistêmico: `evidence_versions` guarda fonte primária,
   observação, derivação e conclusão como `kind` + `content` JSONB, com identidade
   `(tenant, processo, object_id, version)` ([evidence.py:22–38](../../app/models/evidence.py#L22-L38)).
   Toda regra de conteúdo vive só no Pydantic/serviço
   ([schemas/evidence.py:82–126](../../app/schemas/evidence.py#L82-L126)). **O banco não tem
   nenhuma CHECK nem trigger do app** — só unicidade. Insert direto (script, SQL de
   correção em produção, agente futuro) passa sem validação.
2. Texto de OCR é **sobrescrito no lugar** (`extracted_text`, [ocr_tasks.py:363](../../app/workers/ocr_tasks.py#L363));
   âncoras apontam offset do texto *corrente* ([text_anchor.py:56–57](../../app/services/text_anchor.py#L56-L57)).
   `version_number` nunca sai de 1. Não há página.
3. Staging mistura três eixos numa linha mutável: comparação (`consistente`/`divergente_*`),
   revisão (`aceito`/`rejeitado`) e persistência (`consolidated_at`)
   ([extracted_field_staging.py:35–43](../../app/models/extracted_field_staging.py#L35-L43)).
4. Identidade de pessoa está em cinco lugares sem ligação (Client, ClientRepresentative,
   `ManualPessoa`, `Matricula.proprietarios`, `atributos.partes`). Ato registral e relação
   entre atos só existem em memória e em JSON de staging.
5. `Property.geom` (GEOMETRY, SRID 4674) nunca é gravada; nenhuma função `ST_*` é chamada
   em `app/`. Não há shapely/pyproj/fastkml na imagem.
6. Corpus: 32.161 chunks de 395 fontes (113 legislação + 282 PDFs SEMAD sem linha de
   documento). Nível de autoridade determinável dos campos gravados para **19,2% dos
   chunks**; os 29 compêndios (70,7% dos chunks) exigem re-derivação por ato.
7. Não existe catálogo de regras: `regulatory_issue_catalog` é vocabulário de saída, e
   `regulatory_issues` só grava o que disparou — `indeterminado` vira "não disparou".

## Decisão

### 1. Duas famílias, não uma tabela por substantivo

| Família | Onde vive | Critério de entrada |
|---|---|---|
| **Objetos epistêmicos do caso** — fonte primária, observação, derivação, conclusão | `evidence_versions` (ADR-069), **uma** identidade, **um** mecanismo de versão, revisão e invalidação | É uma afirmação sobre o caso que pode ser revista, invalidada e usada como premissa |
| **Entidades de domínio com identidade própria** — `documento_versao`, `fragmento`, `pessoa`, `espolio`, `participacao`, `serventia`, `ato_registral`, `relacao_ato`, `arquivo_geo`, `feicao`, `medicao`, `regra`/`regra_versao`, `conjunto_regras`, `avaliacao_regra`, `manifesto`, `fonte_normativa`/`dispositivo` | Tabelas tipadas | Existe fora de uma única conclusão, é referida por várias observações, precisa de FK/unicidade, ou tem ciclo de vida próprio |

Uma observação **aponta** para a entidade (ex.: observação "R.3 transmite a X" referencia
`ato_registral` e `pessoa`); a entidade não duplica a observação. Atributos variáveis
continuam em JSON tipado.

### 2. Colunas promovidas são GERADAS do conteúdo

Onde houver constraint, FK ou índice sobre um campo do `content`, ele vira coluna
`GENERATED ALWAYS AS (content->…) STORED`: `kind`, `knowledge_state`, `conclusion_class`,
`predicate`, `documento_versao_id`, `fragmento_id`, `consulta_object_id/version`,
`finalidade`, `rota_passo_id`. Uma escrita (o conteúdo), nenhuma divergência possível
entre coluna e JSON. A tabela é nova e pequena; a reescrita do `ADD COLUMN … STORED` é
irrelevante nela. **A confirmar no Incremento 2 com teste de migration:** FK sobre coluna
gerada (PostgreSQL aceita sem ações `ON UPDATE CASCADE/SET NULL`). Plano B: coluna comum
preenchida por trigger `BEFORE INSERT`.

### 3. Imutabilidade garantida pelo banco

Versões, revisões, arestas de premissa, medições e avaliações são **append-only**:
trigger `BEFORE UPDATE OR DELETE` rejeita. É o que torna um trigger de validação no
insert tão forte quanto uma constraint — a linha referida não muda depois. Consequência:
`EvidenceInvalidation.returned_at` hoje é atualizado no lugar
([api/v1/evidence.py:98–101](../../app/api/v1/evidence.py#L98-L101)); passa a evento
novo. Cursor e passos de execução continuam mutáveis (são estado de trabalho, não prova).

### 4. Dependência é relação, não lista JSON

`evidence_premissa(dependente_id, premissa_object_id, premissa_version, papel)` com FK
composta `(tenant_id, process_id, object_id, version)` → `evidence_versions`. É
**materializada por trigger** a partir de `content.premises` no mesmo insert: continua
havendo uma escrita canônica; a aresta é índice gerado pelo banco. Resolve o walk de
invalidação transitiva que hoje varre JSON em Python
([services/evidence.py:128–161](../../app/services/evidence.py#L128-L161)). Normas e regras
citadas ganham arestas próprias para os catálogos globais (`dispositivo`/`fonte_normativa_versao`,
`regra_versao`).

### 5. Tenant dentro da FK

Toda FK de contexto inclui `tenant_id` (e `process_id` quando o objeto é do caso): o
isolamento do Princípio 4 passa a valer também para referência, não só para query.
Catálogos globais usam `tenant_id` nulo; conteúdo de caso nunca vira global.

### 6. Documento: versão imutável e fragmento

`documents` continua a identidade do arquivo. `documento_versao` (documento, n, sha256
dos bytes, texto, sha256 do texto, páginas lidas/total, método/modelo/parâmetros de
leitura, origem — inclusive cópia de gêmeo com o id de origem) é imutável.
`fragmento` (versão, página, início, fim, trecho, hash) é o que a âncora referencia.
`extracted_text` vira projeção da versão corrente. Re-OCR cria versão; nunca apaga a
anterior nem desloca âncoras antigas.

### 7. Pessoa, espólio e participação

`pessoa` (natureza PF/PJ/indeterminada, nomes, aliases) + `pessoa_identificador` (tipo,
valor, fonte, estado; falta com motivo). `espolio` é entidade própria ligada à pessoa
falecida e ao inventário — não é papel, não é PJ. `participacao` liga **sujeito**
(pessoa **ou** espólio) a **contexto** (ato **ou** documento **ou** caso) com papel de
vocabulário versionado, fundamento (evidência), extensão/fração ou desconhecida,
intervalo e estados R/K. Arco exclusivo (`num_nonnulls(...) = 1`) em vez de associação
polimórfica, para que as FKs existam. `Client` permanece cadastro comercial e ganha
`pessoa_id`; `ClientRepresentative` vira projeção de participações de representação.

### 8. Ato registral e relação entre atos

`serventia` (CNS ou falta com motivo, especialidade, localidade). `matricula` ganha
`serventia_id`; identidade = serventia + número. `ato_registral` (matrícula, rótulo
literal R/AV, espécie registro|averbação|outra, natureza do vocabulário do ADR-065 **com
o literal preservado**, data do ato com precisão, ordem na fonte). Duas certidões que
mostram o mesmo ato produzem duas observações de **um** ato. `relacao_ato` (origem,
destino, tipo baixa|aditivo|retificação|cancelamento, fundamento) admite várias por
destino — nada sobrescreve `baixado_por`. Vigência continua **derivada** (ADR-066); se
materializada, é derivação versionada.

### 9. Geometria: arquivo, feição, medição

`arquivo_geo` 1:1 com `documento_versao` (formato, inventário de componentes, CRS de
origem declarado/inferido/desconhecido). `feicao` (arquivo, identificador interno,
tipo, geometria em 4674 + geometria original e SRID de origem, validade).
`medicao` (objeto = feição **ou** declaração documental, grandeza, valor, unidade,
método+versão, modelo de cálculo, resultado de validação), append-only.
`Property.geom` vira projeção de uma feição escolhida por decisão registrada. O método
de área e a tolerância são do ADR-071 e da Ísis (Q-ISIS-04).

### 10. Regras: identidade, versão, conjunto, avaliação

`regra` (id estável) · `regra_versao` imutável (eixo, objetivo, UF/alcance, competência,
predicados e condição em linguagem restrita validada, resultado, severidade **e**
certeza separadas, fonte normativa → `dispositivo`, origem arquivo/aba/linha/hash,
estado de domínio × estado de implementação) · `conjunto_regras` (versão publicada,
homologação, ativação por escopo; rollback = reativar a anterior) ·
`avaliacao_regra` append-only (execução, caso, regra_versao, estado ∈
`aplicavel_disparou | aplicavel_nao_disparou | nao_aplicavel | indeterminado | conflito
| erro_execucao`, entradas por referência, faltantes, trilha).
`regulatory_issue_catalog` fica como **vocabulário de códigos de saída**, referido por
`regra_versao.resultado`; nunca é a regra.

### 11. Execução e manifesto

`agent_executions` permanece, com o histórico de snapshots como relação
(`execucao_snapshot`: execução, snapshot, a partir de qual passo) em vez de sobrescrever
`snapshot_id` na retomada ([connected_agents.py:262](../../app/services/connected_agents.py#L262)).
`manifesto` é tabela **endereçada por conteúdo** (PK = hash do manifesto canônico):
skills com hash **incluindo front-matter**, prompt-base, parâmetros efetivos, conjunto
de regras e templates. AIJob e execução referenciam o hash.

### 12. Zona normativa: autoridade no nível do documento

`fonte_normativa` (uma linha por documento/ato **incluindo as 282 fontes SEMAD** que hoje
só existem como chunks) com `nivel_autoridade` ∈ `norma | interpretacao | exigencia |
procedimento | precedente | radar` e `status_validacao` (nasce `bruto`). O chunk herda
por junção, como a vigência já faz
([services/knowledge_catalog.py:351–355](../../app/services/knowledge_catalog.py#L351-L355)).
Por que documento e não chunk: o reindex do ADR-041 zera colunas de chunk, o ADR-040
multiplica chunks por provider, e um UPDATE em 32 mil chunks reescreve entradas do
índice ivfflat de 249 MB. **`status_validacao` qualifica, não filtra a descoberta**
(ADR-037: ausência de curadoria não apaga trecho; ADR-036 contaria cobertura
insuficiente em todas as esferas). Precedente é entidade própria (Ontologia §10).

### 13. Nomes

A ontologia decide o nome canônico; tabelas novas usam o termo canônico. Tabelas
existentes não são renomeadas por idioma. Coluna com semântica errada não recebe
`ALTER … RENAME`: nomes de coluna estão gravados como **dado** (`target_field`, chaves de
`field_sources`, `lineage.campos`, auditoria, mapas do frontend). O caminho é
expandir → projetar → contrair.

### 14. O que o banco garante e o que fica na aplicação

| Invariante | No banco | Na aplicação | Por quê |
|---|---|---|---|
| `ausencia_verificada_no_escopo` exige consulta | CHECK (estado × referência presente) + FK composta para a consulta no mesmo tenant e caso + trigger: referida é `fonte_primaria` de origem `consulta` | Adequação da consulta à pergunta; limites da base | Adequação é juízo; existência e tipo são fato |
| `risco` exige premissa `fato_documental` e justificativa | CHECK (justificativa não vazia) + constraint trigger DEFERRABLE: ≥1 aresta para conclusão `fato_documental` | Premissa **aprovada e atual** no consumo; suporte semântico | Aprovação muda no tempo e o radar deixa o risco nascer antes dela — é gate de consumo (ADR-069), não de escrita |
| `escopo_proposto` exige finalidade e passo aprovado | CHECK (finalidade não vazia) + FK `(tenant_id, rota_passo_id)` + trigger: passo `validado`, mesmo caso, não removido, no insert | Passo que deixa de ser válido depois gera invalidação, não bloqueio | `RotaPasso.status` e `deleted_at` são mutáveis; bloquear a edição da Rota seria pior que invalidar |

### 15. Migração

Expandir/contrair; **nenhum backfill inferido** (papel, página, trecho e data não
registrados não se adivinham); uma escrita canônica por vez; adaptador serve a UI legada.
Roteiro, ordem e janelas em [MIGRACAO_MODELO_DADOS.md](../arquitetura/MIGRACAO_MODELO_DADOS.md).

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Uma tabela por classe (observação, derivação, conclusão) | Triplica versão/revisão/invalidação que o ADR-069 acabou de entregar; premissa vira FK polimórfica entre três tabelas |
| Manter só JSONB validado por Pydantic (estado do #172) | Nenhuma das três invariantes sobrevive a um insert fora do serviço; premissa não tem FK; predicado/sujeito não indexam |
| Triplas genéricas (EAV/RDF) para todo o domínio | Perde tipo, unidade e constraint; contraria "schema antes de escala" |
| Associação polimórfica `(entity_type, entity_id)` | Sem FK; é o padrão de `AIJob.entity_type/entity_id` ([ai_job.py:54–55](../../app/models/ai_job.py#L54-L55)), que o banco não consegue verificar |
| Banco de grafo (Apache AGE) para cadeia de atos | Extensão não medida em produção; CTE recursiva sobre `relacao_ato` basta para o volume |
| Autoridade/validação no chunk | Zera no reindex (ADR-041), duplica por provider (ADR-040), reescreve o ivfflat |
| `status_validacao` filtrando a busca | Apaga material não curado (contra ADR-037) e zera a cobertura contada (ADR-036) |
| `ALTER TABLE RENAME` para alinhar à ontologia | O nome é dado persistido; renomear quebra staging, `field_sources`, auditoria e UI sem ganho semântico |
| Toda validação em trigger | Juízo semântico (suporte, adequação, aplicabilidade) não é expressável em SQL e seria falsa garantia |
| Área com `ST_Area(geometry)` em 4674 | Resultado em graus² — é exatamente o erro que o Plano §4.5 proíbe |

## Consequências

- Uma camada de proteção nova: correções por SQL direto em produção passam a esbarrar
  nas mesmas invariantes do serviço.
- O Incremento 2 ganha trabalho de fundação antes do motor cartorário (documento_versao,
  imutabilidade, arestas).
- Colunas legadas convivem como projeção por um período; contração exige janela.
- Testes que dependem de SQLite quebram com colunas geradas e triggers; a suíte já exige
  PostgreSQL (Testcontainers).

## O que exige decisão do André

1. **Insumo:** entregar `ARQUITETURA_DADOS_RAG_REGENTE_v1.md`. Se o §3/§5/§10 divergir
   deste ADR, qual prevalece.
2. **Numeração:** cartorário como adendo do 070 ou ADR novo.
3. **Premissa de risco:** só conclusão `fato_documental` conta, ou observação revisada
   também. Muda o caminho de escrita do diagnóstico.
4. **`status_validacao`:** valores (proposta: `bruto → conferido → homologado`, mais
   `suspenso`) e o que `bruto` pode fazer — candidato na descoberta sim; fonte citável
   de conclusão só a partir de qual estado.
5. **Regras:** catálogo global do produto, por consultoria, ou global com sobreposição por
   tenant.
6. **`has_embargo` legado:** anular os 11 falsos de dev (e os de produção) ou congelar a
   coluna e ler só o eixo novo.
7. **Retenção (#207):** RESTRICT indefinido ou política de expurgo com recibo.
8. **Janela de contração:** quando remover colunas legadas (irreversível).
9. **Tipologias SEMAD:** `exigencia` ou `procedimento` para as 223 fichas de tipologia —
   uma decisão para a classe inteira (com a Ísis).

## O que é execução (sem decisão)

Medir extensões/versões de produção · teste de FK sobre coluna gerada · versionar o
insumo quando chegar · inventário por consumidor antes de cada contração · dívidas
#233–#236.
