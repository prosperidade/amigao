# Auditoria de fluxo — validações da Isis (30/07 e 02/08)

**Fase 1 — READ-ONLY.** Nenhuma linha de código alterada. Worktree
`wt-auditoria-fluxo`, branch `audit/fluxo-validacoes-isis`.
Medição feita contra **produção** (Supabase `diquycxxkfrjhxtrcmzb`, SELECT apenas)
no caso real: **processo 16** — "Fazenda São Jorge – Lotes 1B (matrícula 4698) e
1C (matrícula 6776)", cliente Leonardo Ribeiro, imóvel 13. O processo 17 (lotes
01A/02-AA/02-AC, imóvel 14) entrou como controle.

O caso da sessão de **30/07 não existe mais no banco** (`processes` só tem 16 e
17; a `rotas.id=2` prova que houve uma rota 1 apagada). Tudo que se afirma sobre
30/07 vem do código, do git e do `REGISTRO_DIVIDAS`; tudo sobre 02/08 vem da
trilha de auditoria real.

---

## Sumário executivo

**A hipótese central do briefing — "A e B são a mesma doença: a consolidação não
promove para `Property`" — está PARCIALMENTE CERTA, e a parte certa não é a que
parecia.**

1. **A consolidação gravou muito mais do que três campos.** Em 02/08 ela
   escreveu 16 campos em 4 matrículas (cartório, denominação, área, averbação de
   APP e de RL, proprietários, registro anterior, NIRF, CCIR, INCRA, ônus,
   livro/folha). Está tudo no banco agora. A frase "gravou apenas NIRF, CCIR,
   INCRA" descreve **a tela**, não o banco.

2. **Os três campos que ela viu são exatamente os três que a tela do caso
   renderiza.** O dossiê expõe 7 campos da matrícula
   ([dossier.py:113-126](app/services/dossier.py#L113-L126)) e a UI desenha 4 deles
   ([ProcessDossier.tsx:242-245](frontend/src/pages/Processes/ProcessDossier.tsx#L242-L245)):
   SIGEF, INCRA/SNCR, NIRF, Nº CCIR. Em produção o SIGEF é `NULL`. **Sobram
   exatamente INCRA/SNCR, NIRF e CCIR.** Não é falha seletiva de gravação — é uma
   janela de três buracos numa parede cheia.

3. **A promoção para `Property` de fato não existe** — e isso é verdade e é
   grave. `properties.ccir`, `.nirf`, `.registry_number`, `.total_area_ha` estão
   **NULL** no imóvel 13 mesmo depois de sete consolidações. O que a Isis chamou
   de "os dados não aparecem no imóvel" era literal.

4. **A correção de B foi feita no mesmo dia 02/08 e está no ar — mas só metade
   dela.** O commit `290cf3c` ensinou o **Hub do Imóvel** a derivar das
   matrículas (`agregar_das_matriculas`). O **dossiê do Caso** continua lendo as
   colunas cruas ([dossier.py:99-101](app/services/dossier.py#L99-L101)). Ou seja:
   hoje o imóvel mostra e **o caso não** — o bug trocou de tela.

5. **O erro de 30/07 é irreproduzível e assim deve ser reportado.** Não existe
   **nenhuma** linha `consolidar_falhou` em toda a base. O mecanismo que a
   gravaria só nasceu em **31/07**, um dia depois do erro.

**A doença comum a A e B tem nome, e não é a consolidação:** *o sistema grava
certo e não sabe mostrar o que gravou*. Três telas leem a mesma base por três
caminhos diferentes (colunas cruas · derivação · subconjunto fixo), e nenhuma
delas confirma ao consultor que a gravação aconteceu.

---

## 1. Caminho completo do dado — do clique à tabela

| # | Camada | Arquivo:linha | O que faz |
|---|---|---|---|
| 1 | Botão | [ConsolidacaoPanel.tsx:388-400](frontend/src/pages/Processes/ConsolidacaoPanel.tsx#L388-L400) | "Gravar na base" (rodapé sticky). Desabilitado se `consolidaveis === 0` |
| 2 | Mutation | [ConsolidacaoPanel.tsx:160-189](frontend/src/pages/Processes/ConsolidacaoPanel.tsx#L160-L189) | `POST /processes/{id}/consolidar`; toast âmbar se houve `ignorados`/`divergencias_devolvidas` |
| 3 | Endpoint | [processes.py:1668-1712](app/api/v1/processes.py#L1668-L1712) | `consolidate_process_endpoint`. `try/except` → `registrar_falha_consolidacao` + HTTP 500 com frase de consultora |
| 4 | Serviço | [staging_consolidation.py:448](app/services/staging_consolidation.py#L448) | `consolidate_process` — carrega `ExtractedFieldStaging` com `status=aceito` |
| 5 | Agrupamento | [staging_consolidation.py:486-513](app/services/staging_consolidation.py#L486-L513) | Chave de destino `(entidade, [hint], campo)`. `decided_value is None` → `ignorados` ("achado") |
| 6 | Destino | [staging_consolidation.py:551-587](app/services/staging_consolidation.py#L551-L587) | Resolve `Client` / `Property` / `Matricula` (+ guard fantasma, + cascata de âncora do ITR) |
| 7 | Guard de conflito | [staging_consolidation.py:605-621](app/services/staging_consolidation.py#L605-L621) | 2 valores distintos no mesmo destino → devolve a `divergente_transcricao` e **limpa a decisão** |
| 8 | Escrita | [staging_consolidation.py:711-795](app/services/staging_consolidation.py#L711-L795) | Allowlist → coerção → reconciliação → `setattr` + `field_sources[col] = "human_validated"` |
| 9 | Tabelas | `clients` · `properties` · `matriculas` | — |
| 10 | Trilha | [staging_consolidation.py:675-689](app/services/staging_consolidation.py#L675-L689) | `AuditLog action='consolidar'` com `writes`, `ignorados`, `reconciliacoes`, `divergencias_devolvidas` |

**Onde o dado pousa:** `matriculas` (o grosso), `properties` (allowlist estreita),
`clients`.
**Onde ele para:** cinco portas de saída — `ignorados`, `divergencias_devolvidas`,
`reconciliacoes`, achado sem valor, e guard fantasma. Todas as cinco voltam na
resposta HTTP e vão para o `AuditLog`; **nenhuma delas muda o status da linha na
Conferência.**

### A porta que não está no mapa: a Conferência não tem estado "gravado"

`ExtractedFieldStagingOut`
([extracted_field_staging.py:15-46](app/schemas/extracted_field_staging.py#L15-L46))
tem `pendente · consistente · divergente_* · aceito · rejeitado`. **Não existe
`gravado`.** Depois de consolidar com sucesso, a linha continua "Aceito" — visualmente
idêntica a uma linha aceita que nunca pousou. Do lugar onde a consultora está
sentada, o clique não tem consequência observável.

---

## 2. Por que esses três — NIRF, CCIR e INCRA/SNCR

**Resposta: porque são os únicos três campos registrais que a tela do caso
desenha.** Não têm nada em comum de mapeamento, tipo de documento ou destino.

O dossiê monta a matrícula com 7 campos
([dossier.py:113-126](app/services/dossier.py#L113-L126)):
`numero_matricula`, `geo_certificacao_codigo`, `geo_certificacao_status`,
`codigo_incra_sncr`, `nirf_cib`, `numero_ccir`, `area_ha`.
A UI renderiza 4 como linha selável
([ProcessDossier.tsx:242-245](frontend/src/pages/Processes/ProcessDossier.tsx#L242-L245)):
**Nº SIGEF · INCRA/SNCR · NIRF · Nº CCIR**.

Estado real da matrícula 33 (nº 6776) em produção:

| Campo | Valor no banco | Aparece na tela do caso? |
|---|---|---|
| `codigo_incra_sncr` | `951.048.549.371-0` | **sim** |
| `nirf_cib` | `6.907.469-0` | **sim** |
| `numero_ccir` | `65077345244` | **sim** |
| `geo_certificacao_codigo` | `NULL` | linha vazia |
| `cartorio` | `Serviço de Registro Públicos … São João d'Aliança-GO` | **não existe na tela** |
| `denominacao_imovel` | `Fazenda SÃO JORGE LOTE 01-C` | **não** |
| `averbacao_app` | `area: 186,1647 · referencia: matrícula n° 4.655` | **não** |
| `averbacao_rl` | `area: 186,1647 · referencia: AV.02-M.4.655` | **não** |
| `proprietarios` | `[{"nome": "Leonardo Ribeiro"}]` | **não** |
| `registro_anterior` | `4.655` | **não** |
| `registro_livro_folha_ficha` | `NULL` (a 35 tem `2-H`) | **não** |

`field_sources` da matrícula 33 tem **11 campos** carimbados `human_validated`.
A tela mostra 3.

**A trilha de auditoria de 02/08 (processo 16), na ordem:**

| Hora | `campos_gravados` | O que entrou |
|---|---|---|
| 15:09:58 | 2 | `area_ha` das matrículas 33 e 34 (+2 matrículas criadas) |
| 15:12:54 | **13** | cartório, denominação, registro anterior, averbação APP/RL, NIRF, CCIR, INCRA, proprietários |
| 15:13:02 | 0 | (idempotente) |
| 15:15:15 | 1 | `imovel.car_status = "Pendente"` |
| 15:19:08 | 0 | 3 devolvidas + 3 ignoradas + 3 ações |

**16 campos gravados numa sessão.** A frase "gravou apenas NIRF, CCIR, INCRA" é
uma leitura fiel de uma tela infiel.

### O que realmente NÃO pousou (e por quê) — o lote das 15:19

| Campo | Saída | Motivo real |
|---|---|---|
| `matricula.nirf_cib` | devolvido | dois valores (`6.442.022-1` × `9.153.765-7`) de 2 ITRs, sem `matricula_hint` |
| `matricula.vtn` | devolvido | **`vtn` não existe em nenhum modelo** — ver achado abaixo |
| `imovel.rat_data_emissao` | devolvido | `24/11/2024` × `28/07/2026` (dois RATs) |
| `imovel.rat_protocolo` | ignorado | recusa declarada (metadado do documento) — corrigido em 03/08 (#200) |
| `imovel.modulos_fiscais` | ignorado | sem coluna à época — ganhou coluna em 03/08 (#200) |
| `imovel.regulatory_issues` | ignorado | recusa declarada |

**Achado novo — o guard de conflito roda antes da allowlist.** `vtn` não está em
`_MATRICULA_FIELDS` ([staging_consolidation.py:75-82](app/services/staging_consolidation.py#L75-L82))
nem existe como coluna em `matriculas`. Mas o guard de conflito
([:610-621](app/services/staging_consolidation.py#L610-L621)) executa **antes** de
`_write_entity` ([:626](app/services/staging_consolidation.py#L626)), que é quem
consulta a allowlist. Resultado medido: a ação **id 49 "Resolver divergência de
vtn"** foi criada em produção para um campo que **jamais poderia ser gravado**.
O sistema cobrou da consultora trabalho impossível. Ordem invertida, correção
barata.

**O ITR não gravou nada.** Nas 7 consolidações, zero `writes` com `fonte: "itr"`.
As linhas de ITR chegam sem `matricula_hint` (o ITR identifica por NIRF/INCRA,
não por número de matrícula) e dependem da cascata de âncora
([:563](app/services/staging_consolidation.py#L563)) — que aqui não resolveu, porque
os dois ITRs discordam do NIRF. Isso casa exatamente com a frase dela: *"aceitei
matrícula, ccir, itr"* — e o ITR foi o único que de fato não entrou.

---

## 3. O erro relatado ao gravar — **não reproduzido, e digo por quê**

```sql
SELECT id, action FROM audit_logs WHERE action ILIKE '%falh%' OR action ILIKE '%erro%';
-- []  (zero linhas em toda a base)
```

- **Não existe nenhum `consolidar_falhou` em produção.** Nem no caso 16, nem em
  lugar nenhum.
- O mecanismo que grava essa linha — `registrar_falha_consolidacao`
  ([staging_consolidation.py:958](app/services/staging_consolidation.py#L958)) — entrou
  no commit **`8c255fd`, de 31/07**. O erro dela é de **30/07**. O instrumento
  nasceu um dia depois do evento.
- Em **02/08 não houve erro nenhum**: as 7 consolidações do caso 16/17
  completaram e gravaram trilha. O relato de 02/08 (*"não foram para a base"*) é
  sobre **visibilidade**, não sobre exceção.
- **Não invento causa.** Isto confirma a dívida **#91**, que já registra o
  replay contra o staging real do caso 15 sem levantar exceção e conclui
  "causa é ambiente". O marco de fechamento continua válido: **a primeira linha
  `consolidar_falhou` que aparecer em produção.**

Uma observação de método que vale registrar: o toast vermelho de 30/07 pode não
ter sido um erro de verdade. O commit `8c255fd` também corrigiu um `toast.error`
disparado **no caminho de sucesso** quando havia `ignorados`
([ConsolidacaoPanel.tsx:170-186](frontend/src/pages/Processes/ConsolidacaoPanel.tsx#L170-L186),
comentário "RESSALVA NÃO É ERRO (validação 30/07)"). É plausível que "deu erro
quando mandei gravar na base" tenha sido esse vermelho numa gravação que
funcionou. **Plausível, não provado** — sem o log da aplicação de 30/07 não dá
para fechar.

---

## 4. Modelo de dados matrícula × imóvel

**Existe promoção matrícula → `Property`? NÃO. Nunca existiu, e é por decisão.**

- `_IMOVEL_FIELDS` ([staging_consolidation.py:62-72](app/services/staging_consolidation.py#L62-L72))
  não contém `registry_number`, `ccir`, `nirf` nem `total_area_ha`.
- `total_area_ha` está em `_IMOVEL_RECUSA_DECLARADA`
  ([:1057-1062](app/services/staging_consolidation.py#L1057-L1062)): a área do imóvel é
  **derivada** de `Property.area_total_matriculas()`
  ([property.py:109-118](app/models/property.py#L109-L118)).
- `Property.ccir` está **depreciado** por ambiguidade
  ([dossier.py:442-445](app/services/dossier.py#L442-L445)).

Medido no imóvel 13 depois de sete consolidações:

```
registry_number = NULL   ccir = NULL   nirf = NULL   total_area_ha = NULL
field_sources   = {car_code, car_status, municipality, matriculas_contiguas,
                   rl_status: "derived_matricula"}
```

A única "promoção" real que existe é a **ponte RL** — se alguma matrícula tem
`averbacao_rl`, o imóvel recebe `rl_status = "averbada"` marcado
`derived_matricula` ([:652-658](app/services/staging_consolidation.py#L652-L658)). É
exatamente o padrão certo, aplicado a **um** campo.

**A regra de domínio dela (02/08) virou código no mesmo dia.**
`Property.agregar_das_matriculas` ([property.py:120-153](app/models/property.py#L120-L153)):
valor único quando as matrículas concordam, `"349,9022 | 660,6561"` quando
divergem, `None` quando ninguém tem — **nunca escolher uma nem fabricar um
número**. Está certo e está no ar.

### O furo que sobrou — a derivação foi ensinada a uma tela só

| Tela | Como lê matrícula/CCIR/NIRF/área | Estado hoje |
|---|---|---|
| **Hub do Imóvel** | `agregar_das_matriculas` ([properties.py:514,532-537](app/api/v1/properties.py#L514)) | ✅ mostra |
| **Dossiê do Caso** | colunas cruas `prop.registry_number/.ccir/.nirf/.total_area_ha` ([dossier.py:99-104](app/services/dossier.py#L99-L104)) | ❌ mostra `—` |

Ou seja: **hoje, no caso 16, o painel "Imóvel Rural" da aba Dados exibe
Matrícula `—`, CCIR `—`, NIRF `—`, Área `—`** — com quatro matrículas
consolidadas e 16 campos gravados. O defeito que ela relatou no imóvel foi
corrigido no imóvel e permaneceu no caso.

**Sobre a granularidade `matriculas_contiguas`:** não é esta dívida. Ela existe,
está implementada (tri-state + soma anotada, ADR-023) e no imóvel 13
`matriculas_contiguas = true`, `human_validated`. Os follow-ons abertos são
**#55/#56/#57** (grupos de contiguidade, N CARs, split-wizard) — outro problema.

---

## 5. A pergunta dela, respondida

> *"Assim quando o caso finalizar, a base de dados some?"*

**Não. Os dados consolidados sobrevivem ao caso.** Com evidência de esquema:

```
matriculas.property_id      → properties   ON DELETE CASCADE
processes.property_id       → properties   ON DELETE SET NULL
(não existe FK de matriculas para processes)
```

`Matricula` é filha de `Property`, não de `Process`
([matricula.py:43-45](app/models/matricula.py#L43-L45)). Concluir um caso é mudança de
`status`/`macroetapa` — não apaga nada. Mesmo o **hard delete** do processo não
toca matrícula nem imóvel.

**Mas há um "porém" que precisa ser dito, e é achado de produto:**

```
extracted_field_staging.process_id → processes  ON DELETE CASCADE
documents.process_id               → processes  ON DELETE CASCADE
```

**O valor sobrevive; a prova morre com o caso.** Apagado o processo, some o
staging (de qual documento veio cada campo) e somem os documentos. Restam o
`field_sources` (que diz *o tipo* da fonte) e o `lineage` da matrícula
([matricula.py:97-105](app/models/matricula.py#L97-L105)) — que aponta `staging_id` e
`document_id` que **já não existem mais**. Para um sistema cujo Princípio 2 é
"tudo é auditável" e cujo Princípio 11 é "nenhuma afirmação sem fonte", isto é um
buraco real: o dado permanece afirmando algo cuja fonte foi apagada.

**Portanto a resposta honesta para a Isis é:** *"o dado fica; hoje ele fica
invisível na tela do caso, e se o caso for apagado ele fica órfão de fonte."* As
três partes precisam ser ditas juntas.

---

## 6. Inventário dos outros sete achados

Legenda: **B**=bug de código · **D**=bug de dado · **S**=semântica de domínio ·
**U**=UX.

### 6.1 — Auto de infração com número errado ("fala 492262, abre 492263") · **D + S**
**Dívida aberta: #92** (30/07) e **#59**.
Medido: **26 documentos** do caso 16/17 estão tipados `auto_infracao` — mas o
conjunto é `Ofício 005-2008`, `Notificação IBAMA`, `Julgamento 067-2012`, `PRAD`,
`Termos de embargo`, `requerimento REFIZ`, `Relatório Vistoria`, `Solicitação de
Prorrogação`. Cada peça roda `extract_auto_infracao_fato`
([auto_infracao_extraction.py:98](app/services/auto_infracao_extraction.py#L98)) e
produz "um fato de auto"; o dedupe `_chave_auto` quebra quando o órgão varia de
grafia. O número exibido descola do documento aberto porque **o rótulo vem do
fato extraído e o link vem do documento**, e há N documentos por auto.
**Superfície:** `classify_doc_type` (subtipos de peça de fiscalização) +
canonicalização de sigla de órgão antes do dedupe. **Não é bug do consolidador.**

### 6.2 — Rota manda defender na SEMAD auto que é do IBAMA · **S — JÁ CORRIGIDO (31/07)**
`aplicar_esfera_do_caso` ([rota_materializer.py:190-222](app/services/rota_materializer.py#L190-L222))
implementa a ADR-034 na rota: órgão de esfera que o caso não tem é **removido**
(vira nulo), o passo permanece, e o que foi tirado sobe em `orgaos_corrigidos`.
O docstring cita o caso 15 nominalmente. **Verificado em produção:** o único
passo da rota 2 tem `orgao = NULL` — o guard agiu.
**Ressalva não fechada:** `rotas.orgao_competente` do caso 16 ainda diz
`"IBAMA (esfera federal) e ... SEMAD (esfera estadual)"`. O guard só corrige
órgão **reconhecível** por `esfera_do_orgao`, e uma string composta com dois
órgãos não é reconhecida. **Item a levar para a Fase 2.**

### 6.3 — E5 não fecha (três queixas distintas) · **B + U — 2 de 3 corrigidas**
- *"atualizar da IA apagou toda a rota"* → **corrigido (31/07)**. A `dedupe_key`
  incluía `norma_ref`, que vem do LLM não-determinístico: a mesma etapa gerava
  chaves diferentes e a rota duplicava; ela limpava na mão. Hoje a chave é
  `(rota, órgão, título)` ([rota_materializer.py:238-260](app/services/rota_materializer.py#L238-L260))
  e existe `preservar_versao` ([:326](app/services/rota_materializer.py#L326)) que
  fotografa **antes** de a IA rodar. Follow-on registrado: **#94**.
- *"travada mesmo com itens marcados"* → **corrigido (31/07)**. O gate da E5 não
  é o checklist: é `has_rota_validada`
  ([macroetapa_engine.py:142-156](app/services/macroetapa_engine.py#L142-L156)), que exige
  `RotaStatus.validada` (todos os passos validados **e** classificados).
  `descrever_pendencia_rota` passou a devolver a frase com o número exato do que
  falta ([processes.py:848-854](app/api/v1/processes.py#L848-L854)). Em produção a rota 2
  está `validada` desde 05/08 — o gate abriu.
- *"gerar rota não deu em nada"* → **NÃO fechado.** A rota 2 tem **um único
  passo** ("Inscrição e atualização do CAR"), num caso com dois autos do IBAMA,
  embargo e PRAD. Isto é a dívida **#102/ADR-038** (a rota nascia cega ao
  diagnóstico e às ações da E4), fechada em 03/08 por `feat/rota-do-diagnostico`
  — **mas a rota do caso 16 foi gerada em 02/08, antes do fix, e nunca foi
  regerada.** Verificação pendente: regerar e contar os passos.

### 6.4 — LegislacaoAgent traz a norma inteira, não artigo/parágrafo · **B — ⚠ TERRITÓRIO PROIBIDO**
O prompt **pede** o artigo ([legislacao.py:907,934](app/agents/legislacao.py#L907)) e o
formatador usa `c.identifier` + `c.chunk_text`
([legislacao.py:484-497](app/agents/legislacao.py#L484-L497)). A granularidade da citação
é, portanto, **a granularidade do chunk** — o agente não pode citar mais fino do
que o corpus foi cortado.
**A causa está em `app/services/chunking.py`, arquivo proibido nesta frente.**
**Relato e paro.** Dívidas já abertas que cobrem exatamente isto:
**#117** (chunker atribui material não articulado ao último artigo visto),
**#119** (a estrutura determinística da norma é jogada fora),
**#120** (245 chunks sem `identifier` — trecho que não sabe de que norma é),
**#126**, **#127**. Está na frente do outro agente (`wt-normativas-federais`).
Recomendo tratar 6.4 como **consequência** dessa frente, não como item próprio.

### 6.5 — "Passivo" atrelado a ato — vocabulário errado · **S**
**Sem dívida aberta.** O modelo está conceitualmente correto e a UI não.
`Acao.vinculo_passivo` ([acao.py:158-162](app/models/acao.py#L158-L162)) é
**referência ao passivo de origem**, explicitamente sem FK, e a decisão de
16/06 (ADR-016) diz "concluir uma ação NÃO resolve o passivo". A modelagem
respeita o domínio dela.
O que vaza é o **nome**: `vinculo_passivo` chega ao frontend como campo do card
da Ação ([types.ts:24,38](frontend/src/lib/acoes/types.ts#L24)), e ali ele lê como *"o
passivo desta ação"* — invertendo a direção. Na leitura dela, passivo é **o que
gera** embargo/multa/pendência; a ação é resposta ao passivo, não portadora
dele. **Superfície:** rótulo na UI (ex.: "Responde ao passivo:") e o dicionário
`fieldLabels.ts`. Custo baixo, ganho de precisão alto. **É item de vocabulário,
não de modelo — não mexer no schema.**

### 6.6 — Checklists de E1 e E2 trocados · **B — JÁ CORRIGIDO (02/08) E VERIFICADO EM PROD**
Commit `c597eda` (02/08) + migration `b4c8d1e6a293`. Conferido no banco: o
processo 16 tem `ed_01…ed_08` (cadastro, canal, imóvel, ligação/roteiro, áudio,
demanda, mínimo essencial, agentes do intake) e `dp_01…dp_07` (Conferência,
divergências, **"Gravar na base (Consolidação)"**, diagnóstico, objetivo,
remediação, lacunas). **Alinhado à Ficha 07 §5/§7. Fechado.**

### 6.7 — Áudio só pode subir no ato do registro · **U — JÁ CORRIGIDO (02/08 + 03/08)**
`DocumentUploadZone.tsx:26-31` acrescentou `audio_entrevista` ("🎙️ Áudio de
reunião/ligação") à aba **Documentos**, que é a boca de entrada de todas as
etapas — com o comentário citando a validação de 02/08. Em 03/08 a dívida **#103**
(ADR-060) fechou o resto: o áudio passou a ser **transcrito** (`ai_gateway.transcribe`
→ `Document.extracted_text`), com os três estados na tela
([DocumentsTab.tsx:241-270](frontend/src/pages/Processes/DocumentsTab.tsx#L241-L270)) e
`ALLOWED_EXTENSIONS` corrigido. **Fechado — vale só confirmar com ela.**

---

## 7. Notas de governança

**Colisão de faixa de dívidas.** O briefing reserva **200-299** para esta frente.
Essa faixa **já está em uso** pela frente de áudio
([REGISTRO_DIVIDAS.md:1328-1335](docs/REGISTRO_DIVIDAS.md#L1328-L1335)), com #200-#206
gravados e a nota *"próximo livre nesta faixa: 207"*. Vou numerar a partir de
**207**, salvo instrução em contrário. Registro porque a convenção de faixa
existe justamente para evitar colisão entre agentes simultâneos.

**Arquivos proibidos.** Nenhum foi lido para modificação. O único achado que
aponta para lá (6.4, granularidade da citação) foi **relatado e interrompido**,
com as dívidas correspondentes nomeadas.

**Trabalho já feito por sessões anteriores.** As dívidas **#104** e **#200**
(03/08) já haviam medido o processo 16 em produção e concluído "zero campos no
lote das 15:19; nenhum `consolidar_falhou`". Esta auditoria **confirma** essa
medição e **acrescenta** o que faltava: os outros seis lotes da mesma sessão
gravaram 16 campos, e a pergunta "por que só três" tem resposta na camada de
exibição, não na de gravação.

---

## Proposta de Fase 2 (para decisão do André — nada implementado)

Ordem por razão de valor/custo, não por gravidade:

1. **A Conferência confirma a gravação.** Estado `gravado` na linha do staging
   (ou selo derivado de `field_sources`) para que "Aceito" e "Gravado" deixem de
   ser a mesma coisa na tela. É a causa-raiz comum de A e B.
2. **O dossiê do Caso deriva das matrículas** — aplicar `agregar_das_matriculas`
   em [dossier.py:99-104](app/services/dossier.py#L99-L104), fechando a metade que
   `290cf3c` deixou aberta.
3. **A tela da matrícula mostra o que foi gravado** — expandir
   [dossier.py:113-126](app/services/dossier.py#L113-L126) e a UI para cartório,
   denominação, livro/folha, averbações, proprietários. É a correção literal do
   "gravou apenas três".
4. **Guard de conflito depois da allowlist** — campo sem destino nunca vira Ação
   (o caso `vtn`).
5. **Órgão composto na rota** — `esfera_do_orgao` reconhecer strings com mais de
   um órgão (6.2).
6. **Regerar a rota do caso 16** e medir se a ADR-038 resolve "gerar rota não deu
   em nada" (6.3).
7. **Vocabulário do passivo** na UI (6.5).
8. **Preservar a fonte quando o caso é apagado** — decisão de produto: ou o
   processo não faz hard delete, ou `lineage` guarda o suficiente para
   sobreviver. Ver §5.

**Não recomendo abrir 6.4 nesta frente** — é da frente do corpus.

---

*Fase 1 encerrada. Nada foi alterado. Aguardando leitura do André.*
