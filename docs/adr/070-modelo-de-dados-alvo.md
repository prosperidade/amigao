# ADR-070 — Modelo de dados alvo: envelope epistêmico único + entidades de domínio tipadas

- **Data:** 17/09/2026
- **Estado:** aceita no merge do #176 (18/09/2026). Emendada com as decisões do André de
  17/09 e com as provas de execução (§Decisões do André, §Execução). **Nenhuma migration
  escrita, nenhum schema alterado.**
- **Frente:** A — arquitetura de dados versionada (`docs/arquitetura-dados-adr070`)
- **Base inspecionada:** código em `b6df7e6` (pós-#172 e #173); rebaseado sobre `4def0cf`,
  que só acrescenta os docs do #175; banco dev
  `amigao_db` @ `127.0.0.1:15432`, alembic `c7e1a94d2f60`, somente leitura.
- **Complementa:** ADR-069 (contrato de evidência), ADR-062 a 068, ADR-036/037/038/040/041,
  rascunho ADR-042. **Nomes:** [Ontologia v1](../arquitetura/ONTOLOGIA_REGENTE_v1.md)
  (#175) decide os nomes; este ADR decide a **forma**.
- **Roteiro e evidências:** [MIGRACAO_MODELO_DADOS.md](../arquitetura/MIGRACAO_MODELO_DADOS.md).

> **Insumo.** `ARQUITETURA_DADOS_RAG_REGENTE_v1.md` não estava no disco quando este ADR
> foi escrito; o alvo veio do
> [Plano v1.1 §6](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md#6-modelo-de-dados) e do
> [Mergulho §2.3–§2.4 e §5](../arquitetura/MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md#5-m4--modelo-de-dados-e-migração).
> **Decisão do André:** o insumo entra em `docs/arquitetura/` quando entregue; **se divergir,
> este ADR vence** — ele nasceu do confronto com o schema real.

> **Numeração (decisão do André).** 070 = modelo de dados · **071 = motor cartorário** ·
> **072 = geometria** (e auditor). Por deslocamento, motor jurídico passa a 073 e métodos/
> comercial a 074 ([Plano §10.2](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md#102-numeração-e-artefatos)).
> A forma de geometria e de regras é fixada aqui; método de cálculo (072) e linguagem de
> regra (073) podem emendá-la.

## Contexto (medido)

1. **O banco não tem NENHUMA CHECK nem trigger do app — em dev e em produção.** Medido:
   zero `CheckConstraint`/`CREATE TRIGGER` em todo `alembic/versions`; produção (Supabase,
   18/09) com **0 CHECK e 0 trigger** no schema `public`; dev só com a CHECK e o trigger que
   o próprio PostGIS instala. O envelope do #172 (`evidence_versions`: `kind` + `content`
   JSONB, [evidence.py:22–38](../../app/models/evidence.py#L22-L38)) valida conteúdo só no
   Pydantic/serviço ([schemas/evidence.py:82–126](../../app/schemas/evidence.py#L82-L126)).
   **Toda regra de conteúdo é contornável por SQL direto** — script de saneamento, correção
   manual em produção (já usada no wipe dos casos 8/13), backfill, agente novo. Este é o
   argumento das constraints do §14, não um detalhe.
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
6. **A zona normativa exige REINGESTÃO, não classificação retroativa.** Corpus: 32.161
   chunks de 395 fontes (113 legislação + 282 PDFs SEMAD sem linha de documento). Só
   **19,2% dos chunks** têm nível de autoridade derivável do que está gravado. **70,7%**
   (22.725 chunks) vêm de **29 compêndios** cuja identidade é o núcleo temático, não o ato:
   cada chunk precisa de nova identificação de ato — reingestão com fatiamento por ato.
   Isso muda o tamanho do trabalho do Incremento 4: não é uma coluna nova preenchida por
   regra, é refazer a entrada de 80,8% do corpus.
7. Não existe catálogo de regras: `regulatory_issue_catalog` é vocabulário de saída, e
   `regulatory_issues` só grava o que disparou — `indeterminado` vira "não disparou".
8. **Produção ≠ dev (medido 18/09, leitura read-only):** PostgreSQL **17.6** (dev e CI rodam
   15); PostGIS **3.3.7 no schema `extensions`** (dev: 3.3.4 em `public`); `vector` 0.8.0;
   `pgcrypto` presente; alembic em `069ce001` (o Incremento 1 está aplicado em produção,
   não em dev); `properties.geom` = `extensions.geometry(Geometry,4674)`, 0 preenchidas.
   O papel `postgres` tem `search_path = "$user", public, extensions`, por isso `ST_*`
   resolve hoje; funções e triggers novas fixam `search_path` explicitamente.

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
`GENERATED ALWAYS AS (content->…) STORED`: `knowledge_state`, `conclusion_class`,
`predicate`, `documento_versao_id`, `fragmento_id`, `consulta_object_id/version`,
`finalidade`, `rota_passo_id`. `kind` já é coluna comum em produção; ganha
`CHECK (kind = content->>'kind')`. Uma escrita (o conteúdo), nenhuma divergência possível
entre coluna e JSON. A tabela é nova e pequena; a reescrita do `ADD COLUMN … STORED` é
irrelevante nela.

**Provado (18/09, PostgreSQL 15.4 e 17.6, 23/23 casos):** FK composta sobre colunas
geradas funciona, inclusive `DEFERRABLE`, e barra referência a outro caso e a outra
consultoria. Duas restrições do PostgreSQL entram como regra de desenho:
- FK sobre coluna gerada não aceita `ON UPDATE CASCADE` (erro `42601`) — irrelevante aqui,
  porque as linhas são imutáveis;
- **trigger `BEFORE` não enxerga coluna gerada** (erro `42P17` no `WHEN`; a coluna ainda não
  foi calculada nessa fase). Toda validação que lê coluna gerada é **constraint trigger
  `AFTER`**. Script e saída: [provas/adr070_prova_constraints.sql](../arquitetura/provas/adr070_prova_constraints.sql),
  [MIGRACAO §2](../arquitetura/MIGRACAO_MODELO_DADOS.md#2-as-três-constraints-no-postgresql).

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
de área e a tolerância são do ADR-072 e da Ísis (Q-ISIS-04).

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

**Escopo (decisão do André): global com camada por consultoria.** `regra.tenant_id` nulo =
base do produto, vale para todos; não nulo = camada daquela consultoria. O conjunto ativo de
um caso é *base publicada + camada do tenant*, e a avaliação grava as duas versões. **Regra
de tenant não vaza:** um conjunto só pode incluir regra com `tenant_id` nulo ou igual ao seu
(FK composta + constraint trigger), e toda leitura filtra por esse par. Se a camada pode
desativar ou sobrepor regra da base não foi decidido — fica para o ADR-073.

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
procedimento | precedente | radar` e `status_validacao` ∈ **`bruto → proposto → validado`**
(decisão do André): nasce `bruto`; **só `validado` é citável em peça**; `proposto` aparece em
ambiente interno com selo; `bruto` é candidato de descoberta, sem selo de citável. Os 29
compêndios entram por **reingestão** fatiada por ato (Contexto, item 6), não por UPDATE. O chunk herda
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
| `risco` exige premissa de fato e justificativa | CHECK (justificativa não vazia) + constraint trigger DEFERRABLE: ≥1 aresta para **conclusão `fato_documental`** ou para **observação** | No consumo: a conclusão tem de estar **aprovada**, ou a observação **revisada e aceita**; suporte semântico | Dois caminhos (decisão do André). Aprovação/aceite mudam no tempo e o radar deixa o risco nascer antes deles — é gate de consumo (ADR-069), não de escrita. Aceite legado do staging só conta se tiver autor e data gravados, importado como evento de revisão da observação |
| `escopo_proposto` exige finalidade e passo aprovado | CHECK (finalidade não vazia) + FK `(tenant_id, rota_passo_id)` + trigger: passo `validado`, mesmo caso, não removido, no insert | Passo que deixa de ser válido depois gera invalidação, não bloqueio | `RotaPasso.status` e `deleted_at` são mutáveis; bloquear a edição da Rota seria pior que invalidar |

### 15. Migração

Expandir/contrair; **nenhum backfill inferido** (papel, página, trecho e data não
registrados não se adivinham); uma escrita canônica por vez; adaptador serve a UI legada.
**Colunas legadas saem no Incremento 6, com inventário de leitores
([INVENTARIO_LEITORES_LEGADO.md](../arquitetura/INVENTARIO_LEITORES_LEGADO.md)); nunca no
mesmo passo que cria as novas** (decisão do André).

### 16. `has_embargo` congelada

A coluna fica como está: **não se anulam os valores legados** — anular apagaria a distinção,
ainda recuperável caso a caso, entre default e marcação. Linha nova nasce `NULL`, e
`NULL` = `nao_determinado`. A coluna **deixa de ser lida**; embargo passa a ser observação ou
consulta com fonte. Nenhum DDL: no banco a coluna já é nula e sem default; o `False` vinha do
ORM e dos schemas.

### 17. Retenção: expurgo com recibo (#207)

RESTRICT indefinido trava a operação; RESTRICT continua só como proteção contra apagamento
acidental. Eliminar prova é um fluxo explícito que grava **`recibo_expurgo`** append-only —
**o quê** (tipo, id, versão), **quando**, **quem**, **hash** do conteúdo eliminado e a base
da decisão —, entra na hash chain do tenant, invalida os dependentes com motivo
"prova expurgada" e só então apaga. Nenhum valor continua afirmado como comprovado depois
de sua prova sair.
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

## Decisões do André (17/09/2026)

| # | Decisão | Efeito neste ADR |
|---|---|---|
| 1 | Insumo entra em `docs/arquitetura/`; se divergir, **o ADR-070 vence** | Nota de insumo |
| 2 | Cartorário = ADR-071; geometria = ADR-072; 070 fica com o modelo | Nota de numeração; Plano §10.2 ajustado |
| 3 | Premissa de risco: conclusão `fato_documental` **aprovada** ou observação **revisada e aceita** | §14 com os dois caminhos; prova, casos 6 e 7 |
| 4 | `status_validacao`: `bruto → proposto → validado`; citável em peça só `validado`; `proposto` interno com selo | §12 |
| 5 | Regras: global com camada por consultoria; regra de tenant não vaza | §10 |
| 6 | `has_embargo`: congelar; `NULL` = `nao_determinado`; coluna deixa de ser lida; não anular | §16 |
| 7 | #207: expurgo com recibo (o quê, quando, quem, hash) | §17 |
| 8 | Colunas legadas saem no Incremento 6, com inventário de leitores; nunca junto da criação das novas | §15 |
| 9 | 223 fichas de tipologia SEMAD: **pergunta para a Ísis**, junto com a tolerância do KMZ | Pendente com a Ísis |

## Pendente com a Ísis

- **Q-ISIS-18:** as 223 fichas de tipologia SEMAD são `exigencia` ou `procedimento`? Uma
  resposta para a classe inteira. Vai junto com **Q-ISIS-04** (tolerância de reprodução da
  área do KMZ de Jobson). Não se decide sem ela.

## Execução (18/09/2026)

| Item | Resultado |
|---|---|
| #236 — extensões de produção | **Medido e fechado.** PostgreSQL 17.6; PostGIS 3.3.7 em `extensions`; `vector` 0.8.0; `pgcrypto` 1.3; `pg_stat_statements`, `uuid-ossp`, `supabase_vault`; `postgis_topology` disponível e não instalado; alembic `069ce001`; 0 CHECK e 0 trigger em `public`. Leitura por SELECT via API de gestão em modo read-only. A divergência de versão com dev/CI vira #237 |
| FK sobre coluna gerada | **Provado**, 23/23 casos em 15.4 e 17.6; duas restrições registradas no §2 |
| Inventário de leitores das colunas legadas | [INVENTARIO_LEITORES_LEGADO.md](../arquitetura/INVENTARIO_LEITORES_LEGADO.md): 28 colunas/estruturas, leitores por lógica, API, consulta e tela. Achados #238–#241; `Document.size` sem leitor; `properties.regulatory_issues` e `geom` sem escritor |
| Versionar o insumo | Aguarda entrega do André |
