# Consolidação real — por que a ELODI gravou UM campo (Frente K, 12/09/2026)

`docs/trabalhos/fechamento_contrato/consolidacao.json` registrou, no gate da
Frente J: **1 campo gravado, 1 matrícula criada, `area_total = 0.0`, 2
ignorados** — sobre 115 linhas de staging, 51 delas dentro de decisões. SAVE-001
é requisito original da spec da Isis e reprovou ali pela primeira vez medido de
verdade.

Esta frente **investigou antes de corrigir**, e a investigação achou mais do que
o enunciado supunha.

---

## Ambiente da medição

| item | valor |
|---|---|
| banco | `amigao_e2e_frente_k` — descartável, `tests/e2e/frente_j/setup_db.py` (recusa nome fora de `amigao_e2e`; schema por `create_all`) |
| API / worker | `uvicorn` :8010 + `celery --pool=solo`, Redis DB 6 (índice próprio) |
| entrada | os mesmos 6 PDFs da ELODI, gerados do `extracted_text` **real de produção** dos docs 546–551 |
| LLM | real (`gpt-4o-mini` via `ai_gateway`) |
| produção | **não tocada** |

> **A contagem de linhas varia entre extrações**, porque a extração é LLM: a
> Frente J mediu 115 linhas, a primeira rodada desta frente 113, a segunda 118.
> O que NÃO varia — e é o que está sob teste — é o desfecho de cada linha.

Roteiro: `tests/e2e/frente_j/setup_db.py` para o banco; a rodada de medição
sobe os 6 documentos, extrai, decide e consolida duas vezes (A: as **mesmas 3
decisões** do gate da J; B: a consultora decidindo **tudo**).

---

## PARTE 1 — por que a consolidação gravou um campo

### Passo 1 — reproduzir o achado, sem consertar nada

Rodada **A**, código de `main`, as mesmas 3 decisões do gate da J:

```
campos_gravados        = 1        (imovel.car_code)
matriculas_criadas     = 1
area_total_matriculas  = 0.0
ignorados              = 2
desfecho das 113 linhas: 1 gravou · 4 aceito e não gravou · 108 não foi chamada
```

Idêntico ao `consolidacao.json` da J, inclusive nos dois textos de `ignorados`.
O achado é reprodutível.

### Passo 2 — as 51 linhas em decisões

A primeira camada da resposta é aritmética e sem mistério: **o gate da J decidiu
3 das 20 decisões**. As outras 17 nunca foram aceitas, e linha em `pendente` não
entra na consolidação — 108 das 113 linhas caem em *"não foi chamada"*.

Mas isso só empurra a pergunta: e se a consultora decidir TUDO, como faz no
trabalho real? Rodada **B**, ainda no código de `main`, com as 20 decisões e as
63 linhas soltas aceitas (113 linhas em `aceito`, zero falhas ao aceitar):

```
POST /processes/1/consolidar → 500 {"detail":"Internal Server Error"}
campos gravados: 0
```

**O caminho que gravaria muitos campos estava quebrado.** O gate da J não podia
vê-lo: com 3 decisões, a linha que derruba a consolidação nem chegava a ser
aceita.

### Passo 3 — os cinco defeitos, na ordem em que aparecem

#### 1. Um valor que não cabe na coluna derrubava a consolidação inteira

```
sqlalchemy.exc.DataError: (psycopg2.errors.StringDataRightTruncation)
value too long for type character varying(2)
[SQL: UPDATE properties SET state=%(state)s, ... ]
[parameters: {'state': 'Goiás', 'rl_status': '437,7632', 'app_area_ha': 90.4225,
              'area_documental_ha': 2180.3923, 'modulos_fiscais': 31.1547, ...}]
```

O CAR escreve `"Goiás"`; `properties.state` é `String(2)` (UF). No flush, o
`DataError` levou junto **todos os outros campos do mesmo UPDATE** e o resto da
passagem. Uma linha ruim cancelava 112 boas — o oposto do "radar não cancela o
voo".

**Conserto:** `_coerce_uf` (tabela fechada das 27 UFs, mesma dobra de acento do
resto do sistema) traduz `"Goiás" → "GO"`; e a porta da escrita passou a
perguntar se o valor **cabe fisicamente** na coluna antes de entregá-lo ao
banco — se não cabe, é recusa de UMA linha, com motivo em português, nunca a
queda da consolidação. O guard é geral (qualquer `String(n)`), não um remendo
para `state`.

#### 2. O socorro morria antes de socorrer

O endpoint tem, desde 30/07, um bloco de resgate escrito exatamente para isto:
registra a falha em auditoria (transação própria) e devolve uma frase que diz o
que houve. Ele não funcionou:

```python
except Exception as exc:
    registrar_falha_consolidacao(db, tenant_id=current_user.tenant_id, ...)
```

`current_user` é objeto ORM. Ler `.tenant_id` dispara lazy-load numa sessão cuja
transação o `DataError` já havia abortado → `PendingRollbackError` **dentro do
`except`**. Sem linha de auditoria, sem frase: a consultora recebia
`"Internal Server Error"`.

**Conserto:** `tenant_id` e `user_id` saem do ORM **antes** do `try`. Rede de
segurança não pode depender do que acabou de cair.

#### 3. A área de Reserva Legal pousava na coluna de estado

`rl_status` tem vocabulário `averbada | proposta | pendente | cancelada`. O
`_FieldSpec` do CAR mandava `rl_declarada_ha` — um número em hectares — para
essa coluna. O Hub exibia **"Reserva Legal: 437,7632"** onde deveria estar o
estado, e a ponte matrícula→imóvel (que escreve `'averbada'`) disputava a mesma
coluna com um número.

**Conserto:** coluna própria `properties.rl_area_ha` (migration
`c7e1a94d2f60`, aditiva), exposta no Hub ao lado do estado. Área é número,
status é estado.

#### 4. A decisão que a consultora toma não continha a linha que grava

Este é o defeito de fundo — o que faz "aceitei e não gravou" acontecer sem erro
nenhum. Medido nas 21 decisões do staging real de produção do caso #23:

| decisão | membros | membros COM destino gravável |
|---|---:|---:|
| `matricula:3181:gravames` | 4 | **0** |
| `matricula:3313:gravames` | 11 | **0** |
| `matricula:3673:gravames` | 4 | **0** |
| `matricula:4387:gravames` | 5 | **0** |
| `matricula:*:titularidade` (4 decisões) | 6 | **0** |
| as outras 13 decisões | — | ≥1 |

Gravame não tem coluna individual (ADR-065/066) — quem escreve
`matricula.onus_gravames` é a linha **agregada** (`field_name="onus"`), e ela
caía em `sem_agrupamento`. Idem `proprietarios` × decisão de titularidade. Ou
seja: **8 das 21 decisões podiam ser aceitas para sempre sem escrever nada**,
enquanto a coluna de que elas tratavam esperava um segundo clique numa linha
solta que a tela não liga ao mesmo fato.

**Conserto:** a linha que grava entra na decisão que fala do mesmo fato
(`_chave_de`). A linha agregada aparece como evidência legível — *"ônus vigentes
(o que vai para a base): 1 vigente(s): Alienação fiduciária (R-06)"* — e a linha
`proprietarios` aparece como *"proprietários (como o documento lista)"*,
explicitamente **não** autoritativa (é a lista bruta de todo mundo citado em
qualquer ato — foi ela que já exibiu uma transmitente como proprietária).
Membro que grava e não aparece seria escrita silenciosa.

Consequência de régua: `_estado_de` passou a perguntar pelos membros que
**podem** pousar. Sem isso, as 8 decisões gravariam de verdade e ficariam
"Parcialmente gravada" para sempre, porque as observações de ato que as
acompanham nunca recebem carimbo. E sem portador nenhum (matrícula cujos
gravames estão todos baixados) o estado é "Decidida" — "gravada" sem nada
gravado seria a mentira ao contrário.

> A primeira versão dessa régua perguntava "tem `target_field`?", e a suíte
> existente a reprovou: `test_estado_misto_e_parcialmente_gravada` mostrou que
> `matricula_listada` — o CAR citando a matrícula — **não** tem `target_field`
> e mesmo assim recebe carimbo, porque o que ela leva à base é a confirmação do
> vínculo. A régua correta é a declaração que a própria extração já grava na
> linha (`sem_destino`), não a ausência de coluna. Teste vermelho de terceiro
> apontando imprecisão de conserto novo é o sistema funcionando.

#### 5. O CAR acusava ausência de matrícula que a certidão criava na mesma passagem

```
"matricula.numero_matricula: o CAR cita a matrícula 3181, que não está
 cadastrada — a certidão de matrícula é a única fonte que cria o registro
 (cadastre-a manualmente ou anexe a certidão)"
```

A certidão da 3.181 estava no processo e criou a matrícula **na mesma
consolidação**. O julgamento "esta matrícula existe?" rodava ANTES do laço que
cria. A mensagem mandava a consultora cadastrar à mão o que o sistema acabara de
cadastrar sozinho.

**Conserto:** o julgamento roda depois dos grupos. A ordem era o defeito.

### `area_total = 0.0` — o sintoma próprio

`Property.area_total_matriculas()` soma `area_ha` das matrículas vigentes. A
matrícula nascia do `_upsert` só com o número; `area_ha` só entra quando a
decisão `area` é aceita — e ela não fora. A soma de zeros é zero: a conta estava
certa, faltava o dado. Com tudo decidido e os consertos acima:

```
matrícula 3181  926,3654
matrícula 3313  725,4663
matrícula 3673  212,3553
matrícula 4387  316,2053
                ─────────
soma            2180,3923  ==  area_total_matriculas = 2180,3923
```

### O razão das linhas — depois

Rodada B, agora com os consertos (`razao_linha_a_linha.json`, 118 linhas):

| desfecho | linhas |
|---|---:|
| **gravou** | 37 |
| **reafirmou** (o valor já estava na base) | 12 |
| **aceito, não gravou** — com motivo declarado | 69 |
| sem motivo declarado | **0** |

Os 69, por motivo:

| motivo | linhas |
|---|---:|
| observação sem coluna correspondente no cadastro — registrada como observação do documento | 40 |
| gravame — entra na base pela linha de ônus da matrícula, que reúne os não baixados | 27 |
| gravame — entra na reconciliação pela matrícula | 1 |
| a área total do imóvel é calculada pela soma das matrículas — aceite a área em cada matrícula | 1 |

Os 37 gravados, por destino:

```
4x matricula.cartorio          4x matricula.area_ha        4x matricula.denominacao_imovel
4x matricula.registro_anterior 4x matricula.nirf_cib       4x matricula.geo_certificacao_codigo
4x matricula.proprietarios     3x matricula.onus_gravames  1x matricula.denominacao_anterior
1x matricula.averbacao_rl      1x imovel.app_area_ha       1x imovel.rl_area_ha
1x imovel.area_documental_ha   1x imovel.modulos_fiscais
```

Estado das 20 decisões depois de gravar: **19 "Gravado na base"**, 1
"Parcialmente gravada" — `imovel:area_total`, e corretamente: metade dela
(`area_documental_ha`) pousa, e a outra metade (a área total declarada pelo CAR)
é derivada da soma das matrículas, por projeto. Nenhuma decisão fica em
"Decidida — aguardando gravação".

Segunda consolidação seguida: `200`, `campos_gravados = 0`, área inalterada —
idempotente.

| | antes | depois |
|---|---|---|
| 3 decisões (o gate da J) | 1 campo | 2 campos |
| todas as decisões | **500, 0 campos** | **37 campos** |
| `area_total` | 0,0 | 2180,3923 = soma das 4 matrículas |
| linhas sem desfecho declarado | — | 0 |

---

## PARTE 2 — gate de navegador único

`frontend/e2e/frente-k.spec.ts`: **um teste, uma sessão**, sem estado
pré-produzido pela API.

```
login → o caso começa vazio → "Gerar Checklist" (a APLICAÇÃO cria, não o seed)
      → os 6 documentos entram pelo input real, um a um, com o tipo escolhido
      → extração real → Conferência → RECLASSIFICAR uma evidência tipada
      → aceitar todas as decisões pelo cartão → "Gravar na base"
      → os seis números LIDOS DO DOM → F5 → logout/login → mesmos números
      → avançar de etapa até onde a tela permite → Rota → documento novo
```

**Os seis números vêm do DOM**, com âncoras estáveis
(`checklist-resumo`, `conferencia-progresso`, `decisoes-total`,
`conferencia-rodape`, `doc-lifecycle`, `decisao-estado`). Um deles **não existia
na tela**: quantas linhas de staging o caso tem — o rodapé dizia quantas iam
gravar e quantas já estavam, nunca de quantas se falava. Achado registrado e
corrigido na tela (*"De N linha(s) lida(s): …"*), não contornado no teste.

A prova da reclassificação também é da tela, não do estado local do componente:
o teste recarrega a página, reabre o cartão, reseleciona a evidência e relê o
tipo — que agora vem do servidor.

O único HTTP do teste é sincronização (esperar a extração terminar, ler a
macroetapa corrente); nenhum dos seis números passa por `fetch`.

### O resultado: `1 passed (8,7 min)`

Um teste, uma sessão, do caso vazio à base gravada. Registro completo em
`frente_k_percurso.json`; prints em `prints/`.

```
checklist criado PELA TELA : "0 de 7 documentos recebidos"
                    depois : "3 de 7 documentos recebidos"   (o auto-link achou 3)
extração                   : 113 linhas · 20 decisões
reclassificação            : staging 27, hipoteca → alienacao_fiduciaria
                             (relido do SERVIDOR depois de um F5)
rodapé antes de gravar     : "De 113 linha(s) lida(s): 57 campo(s) serão gravados."
rodapé depois              : "... 57 campo(s) serão gravados · 24 já na base."
decisões depois de gravar  : 19 "Gravado na base" · 1 "Parcialmente gravada"
                             nenhuma em "Decidida — aguardando gravação"
```

**Os seis números, lidos do DOM, nos três instantes** — `base`, após F5 e em
sessão nova: **idênticos, comparação de objeto**.

| pergunta | o que a tela diz |
|---|---|
| quantos documentos entraram (checklist) | `3 de 7 documentos recebidos` |
| quanto da Conferência está resolvido | `Conferência: 19/76 decisão(ões) decidida(s) · 19 gravada(s) na base · 57 pendente(s).` |
| quantas decisões a Conferência agrupa | `DECISÕES (20)` |
| quantas linhas de staging existem | `De 113 linha(s) lida(s): 57 campo(s) serão gravados · 24 já na base.` |
| estado de cada documento (DOC-001) | `Erro de leitura · Extraído × 5` |
| estado de cada decisão | `Gravado na base × 19 · Parcialmente gravada` |

E a base, conferida direto no Postgres depois do percurso: as 4 matrículas com
área somando **2180,3923**, `rl_area_ha = 437,7632` (número na coluna de
número) e `rl_status = 'averbada'` (estado na coluna de estado).

### O que o gate de navegador achou (que a camada de payload não achava)

1. **Esperar o OCR não é esperar a extração.** A primeira versão liberava a
   Conferência quando `ocr_status` saía de `processing` — mas o OCR (pypdf)
   leva segundos e a extração (LLM) leva minutos, em tarefa separada. A lista
   de decisões CRESCIA no meio do teste (17 → 19 cartões pendentes entre um
   clique e a verificação seguinte). O critério passou a ser o mesmo do gate da
   J: cada documento com texto tem de ter staging ou um `extraction_status`
   dizendo por que não tem.

2. **Aceitar uma decisão de 15 membros leva 19,4 s.** Medido nesta pilha, na
   decisão de gravames da matrícula 3.313 (`decidir_decisao_agrupada` chama
   `decide_field` por membro, e cada chamada recomputa as decisões inteiras
   para localizar a chave). Não é defeito de correção — é o tempo que a
   consultora espera olhando o botão. Fica registrado como dívida de
   desempenho; nesta frente só mudou o teste, que acusava "decisão que não
   fecha" onde havia espera.

3. **`allInnerTexts()` não espera.** A primeira comparação F5 acusou diferença
   que não existia: `""` antes, os 6 selos de documento depois. Ler do DOM
   custa esperar o DOM — a leitura passou a exigir os 6 selos antes de
   comparar. É o mesmo erro que um `fetch` esconde: o payload sempre chega
   inteiro, a tela não.

4. **O checklist criado pela tela nascia vazio no banco do gate.** "Gerar
   Checklist" produzia *"0 de 0 documentos recebidos"* — um checklist que não
   diz nada, apresentado como se dissesse. Causa: os `checklist_templates` são
   semeados por **migration** (`a1b2c3d4e5f6_sprint1_intake`), e o banco
   descartável usa `create_all`. Não é defeito de produção; era o gate medindo
   uma tela que não é a de lá. O `setup_db.py` passou a semear o template do
   `car`, como já fazia com o catálogo regulatório, e o número virou
   *"0 de 7"* → *"3 de 7"* depois dos uploads (o auto-link achou três).
   Fica registrado o que a medição encostou e não consertou: sem template,
   `_generate_checklist` devolve lista vazia em silêncio — dizer "não há
   template para esta demanda" seria melhor do que uma barra de 0%.

5. **Um caso sem macroetapa era um beco sem saída na tela.** Processo criado
   fora do intake nasce com `macroetapa` NULA. O painel dizia
   *"Etapa não iniciada (sem checklist)"*, não havia botão de avançar (não há
   próxima etapa a partir do nada) e **nenhum gesto da interface iniciava a
   etapa** — a tela nomeava o problema e não oferecia a saída. Pior: o
   backfill lazy que existe exatamente para curar caso legado
   (`ensure_macroetapa_checklists`, "Fase 0.2 … self-healing") **recusava
   justamente esse caso**, com um `return False` na primeira linha.
   Corrigido: sem macroetapa, o caso passa a nascer na `entrada_demanda` — o
   mesmo default que `POST /macroetapa/initialize` já aplicava.

### A Rota: o que foi provado e o que não

A Frente J registrou `"aviso_rota": "sem rota no processo"` — a invalidação da
rota nunca foi exercida porque não havia rota. Este gate mediu **por que** não
havia: a Rota só é oferecida na macroetapa **E5** (`caminho_regulatorio`), e
chegar lá pela tela exige fechar E1→E4 — assinar diagnóstico, completar o
output mínimo de cada etapa. Isso é trabalho de consultoria, não gesto de
teste; simular as quatro etapas para alcançar a Rota seria fabricar exatamente
o estado que este gate existe para não fabricar.

O que esta frente entregou nessa direção: **o degrau invisível saiu do
caminho** (item 3 acima). O teste vai até onde a tela leva, registra a etapa
alcançada e as travas que a tela mostra, e — quando a Rota não é alcançável —
declara isso como `não provado` na anotação do próprio teste, em vez de passar
verde por omissão.

## Regressão

| gate | resultado |
|---|---|
| suíte backend (`pytest tests/ -q`) | **1996 passed**, 0 failed — 32 min, cobertura 76,69% |
| `ruff check app/ tests/` | verde |
| `npm run build` (`tsc -b` + vite) | verde |
| testes de frontend (`vitest`) | **26 arquivos, 167 testes** — com `NODE_OPTIONS=--experimental-require-module` (ver abaixo) |
| `tsc -p tsconfig.e2e.json` | verde |
| **gate de navegador único** (`frente-k.spec.ts`) | **1 passed (8,7 min)** |

> **`vitest` sem a flag mente de verde.** No Node 22.11 o `require()` de ES
> Module ainda não é suportado, e a cadeia jsdom → `@asamuzakjp/css-color` →
> `@csstools/css-calc` derruba **14 workers na largada** — entre eles os de
> `ConsolidacaoPanel`, `DecisoesPanel`, `DocumentsTab` e `fieldLabels`,
> exatamente os componentes que esta frente tocou. O resumo sai "12 passed" e
> os 14 arquivos que não rodaram ficam escondidos em "Errors". Registrado no
> `CLAUDE.md`.

## O que ficou de FORA (registrado, não feito)

1. **REV-001 literal — retrocesso à E3.** Decisão de produto pendente da Isis; a
   ADR-068 já a declara fora de escopo.
2. **`declarado_inexistente` (DOC-001).** Exige gesto de consultora sobre o
   requisito (checklist), não derivação a partir do documento.
3. **OCR dos PDFs originais.** A entrada foi reconstruída do `extracted_text` de
   produção; medir o OCR real exige os arquivos do R2 — dívida própria.
4. **A invalidação da ROTA.** Ver "A Rota" acima: exige levar o caso até a E5
   pela tela, o que é o percurso de outra frente.

## Dívidas que esta frente encontrou e não fechou

* **`ignorados` agrupa linhas sem destino numa mensagem só.** As 67 linhas de
  observação sem `target_field` formam UM grupo (chave `("", None)`) e produzem
  uma única entrada em `ignorados`. Não há perda de informação para a
  consultora — cada linha carrega o seu motivo no `field_value`, e a tela o
  mostra —, mas a resposta da consolidação sub-relata.
* **O auditor ainda não vê `rl_area_ha`.** Ele recebe `rl_status` no contexto
  (`auditor_imovel`), que agora é sempre um estado limpo — antes podia chegar
  como "437,7632". Passar também a área exigiria mexer no prompt do agente, e
  a configuração dos agentes existentes está congelada; a divergência RL
  declarada × soma das matrículas continua sendo calculada pela matriz de
  inconsistências, sem depender disto.
* **O banco de desenvolvimento não chega ao head do alembic.** `alembic upgrade
  head` em `amigao_db` para na migration ENT-002, que recusa aplicar-se porque
  há cadastros duplicados por CPF/CNPJ normalizado no banco de dev (tenant 2:
  documento `09876543212` com 5 cadastros, `12345678900` com 2). É dado de teste
  acumulado, não defeito do código; a migration desta frente
  (`c7e1a94d2f60`) foi validada por SQL offline
  (`alembic upgrade b8d4e1f7a209:c7e1a94d2f60 --sql`) e pelo `create_all` do
  banco descartável. Saída: rodar `scripts/relatorio_duplicados_documento.py`,
  escolher o cadastro canônico e limpar o dev.
