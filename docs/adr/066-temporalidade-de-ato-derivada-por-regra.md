# ADR-066 — Temporalidade de ato derivada por regra

**Data:** 10/09/2026
**Status:** Aceita
**Frente:** F — temporalidade de ato (`feat/temporalidade-ato`)
**Insumo:** `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md` (HIST-001: "o
staging não tem data, número do ato, partes nem vigência"), `docs/adr/065-observacao-registral-tipada.md`
(Frente E — tipo de observação, "Fora do escopo": temporalidade é a frente
seguinte), `docs/REGISTRO_DIVIDAS.md` #218 (RL do CAR em `rl_status` — contexto,
não fechada por esta frente)
**Dívidas fechadas:** HIST-001 — parcial, com fronteira declarada abaixo
(reconciliação entre documentos e a tela continuam fora)
**Dívida aberta:** nenhuma nova nesta frente

---

## Contexto

A Frente E (ADR-065) resolveu **o quê** cada ato é — tipo, não gaveta. O que
sobrou, medido no próprio ADR-065 ("Fora do escopo"):

> `data` e `prazo` ficam como TEXTO, do jeito que o documento escreve. Não
> existe vigência, cancelamento nem "qual titular é o atual" fora da baixa por
> referência textual — que resolve o caso mais grave de HIST-001 (gravame
> baixado afirmado como vigente) sem resolver o requisito inteiro (consultar
> "o que vale hoje" por data).

Medido de novo, agora com o texto completo do doc 549 (matrícula 3.673,
Supabase, tabela `documents`, id 549 — o mesmo texto das frentes C/D/E):

- **AV.03/04/05** são três hipotecas do Banco do Brasil, cada uma com data
  própria (15/04/2008, 03/04/2009, 15/09/2011). **AV.09/AV.10/AV.12** são as
  baixas — cada uma cita, por escrito, qual hipoteca baixa ("constante da
  AV.03", "constante da AV.04", "constante da AV.05 acima ... ficando assim, o
  imóvel livre de hipoteca"). A Frente E já produz as seis como observações
  tipadas e já marca `baixado_por` nas três primeiras. O que **não** existia:
  um estado consultável — "quantas hipotecas vigentes tem esta matrícula
  agora?" exigia reler seis linhas de staging e refazer o casamento à mão.
- **AV.10 do doc 548** (matrícula 3.313): arrendamento de 50ha, prazo "15 anos
  com inicio no dia 01/01/2013 a 01/01/2028". Hoje o prazo é texto solto.
  "Há arrendamento vigente em 2026?" — sem resposta sem ler a string.
- **AV.02 do doc 549** é a averbação de Reserva Legal vigente (492,9252ha, em
  conjunto com as matrículas 1.224/1.225). O CAR (fora desta matrícula) diz
  437,7632 — divergência real, mas de OUTRO documento (RL do CAR, dívida
  #218 — fora desta frente). Dentro desta matrícula, a própria **AV.01**
  (georreferenciamento) cita "área de reserva legal de 42,8070ha" — um número
  de RL dentro de um ato que **não é** reserva legal. É a mesma classe do
  #221 (forma certa, tipo errado), agora precisando que a leitura de "RL
  vigente" respeite o TIPO do ato, não s a presença do número.
- **Titularidade** (Frente D, PR #155): a matrícula 3.673 lista 4 titulares na
  cadeia (`proprietarios`) sem saber qual é o ATUAL. Medido no próprio texto:
  **R-11** (18/03/2019) transfere de Nascente Agro-industrial Ltda para
  Alexandre Augusto Clemente + Karina Santarosa Clemente; **R-13**
  (10/12/2019) transfere destes para ELODI AGROPECUÁRIA. R-11/R-13 já são
  observações tipadas `compra_venda` — só faltava ler quem adquire e quem
  transmite em cada uma.

## Decisão

### Três campos estruturados, extraídos com âncora — dois novos, um já existia

Cada observação tipada (Frente E) já carregava `ato` (o rótulo do próprio
ato — "AV.02", "R-11"). Esta frente completa o trio:

- **`ato`** — já existia (Frente E). Já cumpre o papel de "a referência deste
  ato"; não foi duplicado sob outro nome.
- **`data_ato`** (novo nome; era `data`) — a data DESTE ato, como escrita.
- **`altera_ato`** (novo nome; era `ato_referenciado`) — o rótulo do ato que
  este BAIXA, cancela, rescinde, quita, adita ou retifica.

O rename de `data`→`data_ato` e `ato_referenciado`→`altera_ato` é
deliberado, não cosmético: o par (`data_ato`, `altera_ato`) é o que
`derivar_vigencia` (abaixo) lê para produzir `vigencia` — nomeá-los pelo papel
que exercem no grafo de temporalidade é o que torna a leitura do módulo
honesta sobre o que mudou. `ato_referenciado` já cobria semanticamente
"adita" desde a Frente E (o prompt antigo já dizia "quando o ato BAIXA,
cancela, rescinde, quita **ou adita** outro ato") — só o código nunca lia essa
combinação: `aplicar_baixas` (agora `aplicar_alteracoes`) ignorava toda
observação que não fosse `TIPO_BAIXA`. Esta frente fecha esse gap junto com o
rename, e não como frentes separadas, porque são o mesmo grafo.

**`adquirentes`/`transmitentes`** — novos, só em atos `compra_venda`. Só
preenchidos quando o próprio texto distingue os dois lados ("foi adquirido
por X ... por compra feita a Y"). Sem essa distinção, o campo fica vazio —
nunca inferido por posição.

### Campo DERIVADO: `vigencia`, nunca extraído pelo LLM

`observacao_registral.derivar_vigencia(observacoes, data_referencia=None)`
preenche `atributos["vigencia"]` por REGRA, em quatro passos, nesta ordem:

1. **Alterado** — outra observação desta matrícula cita esta em `altera_ato`
   (via `aplicar_alteracoes`, o mesmo grafo que já existia como
   `aplicar_baixas` na Frente E, generalizado para `aditivo`). `baixa` ⇒
   `baixado`; `aditivo` ⇒ `retificado`. Retificação AMENDA, não cancela — um
   gravame retificado continua contando em `onus_vigentes` (a coluna
   `onus_gravames` não muda de comportamento).
2. **Prazo com termo final** — só para `arrendamento`/`usufruto`
   (`_TIPOS_COM_TERMO`). A ÚLTIMA data dentro de `prazo` ("01/01/2013 a
   **01/01/2028**") é o termo; termo < `data_referencia` ⇒ `expirado`, senão
   `vigente`. Gravame **não** entra aqui: "vencimento" de uma CRH (cédula
   rural hipotecária) não baixa a hipoteca por si — só a averbação de baixa
   faz isso (medido no próprio doc 549: a AV.03 vence em 01/12/2016 e só é
   baixada em 16/03/2017, por ato próprio). Tratar vencimento como expiração
   inventaria um estado que o registro não afirma.
3. **Ato de origem com data** (`data_ato` presente, sem alteração encontrada)
   ⇒ `vigente`.
4. **Nenhuma das anteriores** ⇒ `indeterminado`. **Nunca `vigente` por
   default** — silêncio não é vigência, a mesma régua do achado `partes[0]`
   do ADR-065 (o sistema só afirma o que o documento sustenta).

Só tipos em `TIPOS_COM_VIGENCIA` (`TIPOS_GRAVAME | TIPOS_AREA_PARCIAL` — reuso
direto do conjunto que a Frente E já definia para "objeto com vida própria
dentro do imóvel") recebem o campo. `compra_venda`, `baixa`, `aditivo`,
`georreferenciamento` são EVENTOS, não estados — `vigencia` neles ficaria
`None`, não um valor arbitrário.

**Achado do gate contra o doc 548 real (não do fragmento de teste da Frente
E): `aplicar_alteracoes` só marca `baixado_por`/`retificado_por` quando o
ALVO também está em `TIPOS_COM_VIGENCIA`.** A AV.14 do doc 549 — "para
constar a QUITAÇÃO da dívida mencionada no R-13 acima" — é tipada `baixa`
(sinônimo "quitação") e cita `R-13` (`compra_venda`) em `altera_ato`,
corretamente: o texto está certo, o PREÇO da venda foi pago. Sem a trava, o
código marcava `R-13.baixado_por = "AV.14"`, e `resumo()` (sem filtro de
tipo) mostrava **"R-13 · Compra e venda · ... · baixado por AV.14"** — uma
frase que um consultor lendo a Conferência interpretaria como "a venda foi
desfeita", quando o documento diz o oposto (a dívida do preço foi quitada,
a venda permanece). `compra_venda` nunca teve `vigencia` computada (não está
em `TIPOS_COM_VIGENCIA`), então o dano ficava só no atributo bruto e no
resumo textual — mas ficava. Testado em
`TestQuitacaoDeDividaNaoBaixaACompraEVenda`, com o trecho real do doc 549.

**`data_referencia` é parâmetro, não `date.today()` embutido.** A regra
compara o termo final "com a data de referência do CASO, não com hoje"
(medido: o mesmo prazo pode estar vigente ou expirado dependendo de QUANDO se
pergunta). Hoje não existe um conceito de "data de referência do caso" no
sistema — construir um é fora do escopo desta frente. `derivar_vigencia`
aceita a data de fora; a chamada em tempo de extração
(`ficha01_extraction._linhas_de_observacoes`) usa `date.today()` como
default honesto ("vigente hoje, no momento em que o documento foi lido") — os
FATOS (`data_ato`, `altera_ato`) ficam salvos, então uma consulta futura com a
data do caso não precisa reextrair nada, só rederivar.

### `rl_vigente` reaproveita `ultimo_por_destino`, não duplica

RL é uma COLUNA (`matricula.averbacao_rl`), não uma lista — "qual observação
grava a coluna" e "qual é a RL vigente" são a mesma pergunta para este tipo
(ao contrário dos gravames, que são lista e por isso têm `onus_vigentes`
próprio desde a Frente E). `rl_vigente(observacoes)` é
`ultimo_por_destino(observacoes).get(("matricula", "averbacao_rl"))` — sem
lógica nova. O caso do AV.01 (RL do CAR dentro do georreferenciamento) já é
resolvido pelo TIPO: `destino_de` só considera `TIPO_RESERVA_LEGAL`, e AV.01 é
`georreferenciamento` — nunca entra na disputa pela coluna, não importa que
número ele cite.

### Titularidade: derivada de `compra_venda`, não do campo `proprietarios`

`proprietarios` (o campo legado, cadeia solta sem papel nem ato) **não foi
tocado**. A fonte com ato + data + papel é `atos` — especificamente as
observações `compra_venda`, que já são o registro formal de cada
transferência. `cadeia_titularidade(observacoes)` lista uma linha por
(pessoa, papel, ato); `titular_atual(observacoes)` é o(s) `adquirentes` do
ato `compra_venda` de maior `ordem`.

**"Sem ato posterior que o transfira" é automático para o último ato** — por
definição não há nenhum depois dele nesta matrícula. Não há verificação
cruzada entre `adquirentes` de um ato e `transmitentes` do próximo (cada ato
fala por si, mesma régua do ADR-065 para `partes`) — na prática eles
concordam (medido no doc 549: os adquirentes de R-11 são exatamente os
transmitentes de R-13), mas isso é o documento sendo consistente, não uma
invariante que o código impõe.

**Por que não modelar `papel_no_ato` genérico** (comprador/vendedor/credor/
devedor para QUALQUER tipo de ato, não só `compra_venda`): o pedido desta
frente é "adquirente/transmitente" — o par que TRANSFERE titularidade
registral. Generalizar para representante, procurador, cônjuge (o achado do
`partes[0]`, já registrado como fora do escopo desde o ADR-065) é outro
conceito — ENT/papel, frente própria. `partes` (a lista sem papel, usada por
`hipoteca`/`alienacao_fiduciaria`/`arrendamento`/`servidao`/`usufruto`)
continua exatamente como a Frente E deixou.

### O cuidado medido no texto real: referência de arquivamento ≠ alteração

Quase toda averbação do doc 549 abre com uma referência de ARQUIVAMENTO para
OUTRA matrícula — *"AV.02 MAT. 3.673 -(Averbação referente a Av.09 Mat. 2007 e
Av. 04 Mat. 3.669)-"*. Isso não é alteração: é a matrícula ANTERIOR do mesmo
ato, numa certidão diferente (a cadeia dominial, fora desta frente — só
matrícula, ver "Fora do escopo" no ADR-065). Um `altera_ato` lido sem essa
distinção faria a AV.02 (Reserva Legal) parecer alterada pela AV.09 de uma
matrícula que nem está neste documento.

Duas defesas, uma no prompt e uma estrutural no código:

1. O prompt (`ficha01_extraction._STAGING_PROMPTS["matricula"]`) agora avisa
   explicitamente: "não confundir com a referência de arquivamento que abre
   muitas averbações ... `altera_ato` é só quando o TEXTO DO ATO (não o
   cabeçalho) diz que ele baixa/cancela/adita/retifica algo".
2. Estrutural, por construção: `aplicar_alteracoes` só lê a referência a
   partir de observações `baixa`/`aditivo` — nunca a partir de uma
   `hipoteca`/`reserva_legal`/etc. Mesmo que o modelo copie o cabeçalho de
   arquivamento para dentro de `descricao` de uma hipoteca, ele nunca é
   escaneado, porque hipoteca não é fonte de alteração — só alvo. Testado em
   `TestReferenciaDeArquivamentoNaoEAlteracao`.

## Fora do escopo desta frente (registrado, não esquecido)

- **Reconciliação entre documentos** (REC-001 — comparar RL do CAR ×
  matrícula, área do CAR × soma de matrículas por vigência). Depende desta
  frente (precisa saber "o que vale hoje" antes de comparar).
- **Tela por decisões** (CONF-001). Depende da reconciliação.
- **Papel de pessoa como conceito geral** (representante, procurador,
  cônjuge) além de adquirente/transmitente — ENT/papel, frente própria.
- **CAR e CCIR.** Só matrícula nesta frente, como nas anteriores.
- **`data_referencia` do caso como conceito persistido.** `derivar_vigencia`
  aceita o parâmetro; não existe hoje um campo de "data de referência do
  caso" para alimentá-lo automaticamente fora do `date.today()` da extração.
- **Dívida #218** (RL do CAR em `imovel.rl_status`) — contexto lido, não
  fechada aqui: é modelo (coluna nova), não temporalidade.

## Gate

Medido em duas camadas, como as frentes anteriores:

1. **Unitário, determinístico** — `tests/services/test_observacao_registral.py`,
   62 casos (26 da Frente E + 36 novos), com trechos VERBATIM do
   `extracted_text` real de produção (Supabase, projeto "Regente Ambiental",
   tabela `documents`, ids 547–550 — lido via MCP read-only, mesma fonte das
   frentes C/D/E). Cobre: as três hipotecas do doc 549 baixadas por
   AV.09/10/12 (`vigencia=baixado`, zero vigentes); a alienação R.15 sem baixa
   (`vigencia=vigente`); o arrendamento do doc 548 (`vigente`/`expirado`
   conforme `data_referencia`); o aditivo retificando sem baixar
   (`retificado`, ônus continua vigente); a RL do doc 549 (AV.02 vigente,
   42,8070ha do georreferenciamento NÃO promovido); a titularidade real
   (ELODI atual, 3 titulares anteriores, cada um com o ato que o inscreveu);
   o teste negativo de "vigente nunca por silêncio"; e a defesa contra a
   referência de arquivamento.
2. **LLM real, medição registrada em** `docs/trabalhos/temporalidade_ato.md`
   — mesmo padrão de banco descartável das frentes anteriores (Frente E:
   `amigao_tipo`, host 55234; Frente C: `amigao_entrada`, host 55433).

Números completos: `docs/trabalhos/temporalidade_ato.md`.

## Testes

`tests/services/test_observacao_registral.py` — classes novas:
`TestVigenciaGravames`, `TestVigenciaArrendamento`, `TestVigenciaIndeterminado`,
`TestAditivoRetifica`, `TestReferenciaDeArquivamentoNaoEAlteracao`,
`TestRlVigente`, `TestTitularidade`, `TestAtributosTemporaisNaLinhaDeStaging`
— mais o rename das chaves antigas (`data`→`data_ato`,
`ato_referenciado`→`altera_ato`, `aplicar_baixas`→`aplicar_alteracoes`) nas
classes da Frente E, que continuam verdes.


---

## Adendo — Frente J (11/09/2026): a vigência derivada é CONSULTADA, e a data é do caso

**Insumo:** `docs/auditoria/REAUDITORIA_CODEX_11-09.md`, itens 4 e 7.
**Branch:** `fix/fechamento-contrato-spec`.

Dois pontos deste ADR ficaram pela metade, ambos nas seções "`rl_vigente`
reaproveita `ultimo_por_destino`" e "`data_referencia` é parâmetro":

1. **`rl_vigente` não olhava `vigencia`.** "Vigente" era a última RL do
   papel, mesmo baixada por averbação posterior — a regra derivada existia e
   não era consultada. Corrigido: `rl_vigente` exclui `baixado`/`retificado`/
   `expirado` e devolve a mais recente entre as que restam (ou `None`).
   `ultimo_por_destino` (quem grava a coluna) deixa de promover ato
   `baixado` — a RL baixada não grava `matricula.averbacao_rl`. Retificado
   **continua** gravando a coluna (aditivo amenda, não cancela — a regra do
   passo 1 acima), mas não é afirmado como "vigente" sem olhar o aditivo.
   Fronteira declarada: as duas funções agora respondem perguntas
   diferentes ("quem grava" × "o que vale"), e o docstring de cada uma diz
   qual.
2. **`date.today()` como default.** "Não existe data de referência do caso"
   não era verdade: `Process.opened_at` existe (com `created_at` como
   fallback). `ficha01_extraction.data_referencia_do_processo` a lê e
   `extract_and_stage` a passa a `derivar_vigencia`. Sem referência
   explícita, prazo com termo final fica `indeterminado` — nunca `vigente`
   pelo passo 3 ("tem `data_ato`"), que só vale para ato sem termo (gravame
   com data continua `vigente`). Os fatos ficam salvos; quem consultar com
   outra data rederiva sem reextrair.

**Titularidade** (mesma frente, adendo do ADR-065): `cadeia_titularidade`/
`titular_atual` leem `TIPOS_TRANSFERENCIA_TITULARIDADE`, não só
`compra_venda`.

**Testes:** `tests/services/test_observacao_registral.py::TestFrenteJVigenciaEDestino`
(RL baixada não grava a coluna e não é vigente; todas baixadas ⇒ nenhuma;
retificada mantém a coluna sem ser promovida; termo sem data de referência ⇒
indeterminado, com data ⇒ vigente/expirado; gravame com data sem referência
continua vigente; espólio → formal de partilha → herdeiro na cadeia) e
`test_reconciliation_decisions.py::test_data_de_abertura_do_caso_alimenta_a_vigencia`.
