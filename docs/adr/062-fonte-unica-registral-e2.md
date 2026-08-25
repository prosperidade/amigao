# ADR-062 — Fonte única registral na consolidação (E2)

- **Status:** Aceita
- **Data:** 2026-08-25
- **Validada por:** Isis (sócia, validadora de domínio)
- **Branch:** `audit/consolidacao-fonte-unica`
- **Relacionada a:** ADR-017 (consolidação parcial — ponto 1 superado por
  este ADR), ADR-012 (decisão contextual ao processo), ADR-023
  (matrículas contíguas / integridade multi-documento), ADR-032 (identidade
  da matrícula e cascata de vinculação), dívida #75 (reescrita como
  superada), Ficha 08 §5 (marcada superada)

## Contexto

Hoje matrícula, CCIR, SIGEF, ITR e CAR competem, em pé de igualdade, pela
escrita dos mesmos campos de `target_entity=matricula` na consolidação
(`app/services/staging_consolidation.py:consolidate_process`). O agrupamento
é por DESTINO — `(entidade, matrícula_hint, campo)` — sem filtro por
`source_doc_type`; quem vence é decidido por `_pick_winner` (edição do
consultor > confiança > menor id, com uma âncora extra para SIGEF em `area_ha`
e `denominacao_imovel`).

Quando duas fontes ACEITAS discordam do mesmo destino, `_group_conflict_values`
devolve as duas para `divergente_transcricao` — nenhuma grava — e a
divergência vira uma `Acao` (`generate_acoes_from_divergencias`, ADR-017
opção b). O sintoma relatado pela Isis: o fluxo trava campo a campo,
repetidamente, porque o sistema trata documentos de natureza jurídica
diferente como concorrentes simétricos por um mesmo dado registral — quando a
matrícula é, por definição no direito registral brasileiro, o único
instrumento que declara com força de fé pública titularidade, área e
descrição do imóvel.

O inventário real de `app/services/ficha01_extraction.py:_FIELD_SPECS` mostra
o tamanho da concorrência: `matricula.area_ha` e `matricula.denominacao_imovel`
têm até 4 fontes (matrícula, CCIR, ITR, SIGEF); `codigo_incra_sncr` tem CCIR e
ITR; `nirf_cib` tem matrícula e ITR; `proprietarios` tem CCIR e SIGEF.

A investigação read-only (FASE 1 deste mesmo trabalho) também achou que a
Ficha 08 §5 já documentava uma hierarquia de arbitragem — mas em **duas
cadeias paralelas** (jurídica: Matrícula → SNCR/CCIR → Cafir/CIB → ITR → CAR;
técnica: Memorial/SIGEF → Matrícula → CAR), nunca implementada em código
(dívida #75). Este ADR não implementa as duas cadeias — substitui a pergunta
"qual documento vence, campo a campo" por uma resposta mais simples: para
dado registral, só a matrícula escreve; ponto.

## Decisão

**1. Campos de `target_entity=matricula` que descrevem o registro jurídico do
imóvel — área, denominação, titular (`proprietarios`), código INCRA/SNCR,
NIRF, RL averbada, geo_certificação — só são escritos por
`source_doc_type='matricula'`.** CCIR, SIGEF, ITR e CAR nunca escrevem esses
campos na consolidação, mesmo sozinhos (sem conflito com outra fonte): a
matrícula é a fonte, não apenas a vencedora de disputa. A única exceção é a
**edição explícita do consultor** (`decided_value` diferente do valor
extraído) — decisão humana sempre grava, de qualquer fonte, porque é decisão,
não competição de fonte (Princípio 1).

Divergência entre a matrícula e qualquer uma dessas fontes deixa de ser
resolvida (ou travada) na consolidação — vira **achado do diagnóstico**.

**2. Campos de `target_entity=imovel` que a matrícula não fornece — `car_code`,
`car_status`, `app_area_ha`, `municipality` — continuam vindo de CAR/ITR/RAT
como hoje.** Não é exceção à regra 1: é natureza diferente. Esses são dados
**ambientais/declaratórios** (o CAR é o cadastro ambiental; a matrícula não
fala sobre APP, situação do CAR ou código de inscrição). A concorrência que já
existia entre CAR × ITR × RAT nesses campos (ex.: `car_code` vindo de três
fontes) **não muda** — continua arbitrada por `_pick_winner` + o guard de
conflito de sempre, e uma divergência entre elas continua virando achado do
jeito que já virava.

**3. Só a certidão de matrícula cria o registro `Matricula`.** CCIR, ITR e CAR
citando uma matrícula que ainda não existe na base não a materializam mais
(endurecimento do guard fantasma da Sprint 4, que já vetava só `sigef`) — a
citação vira achado ("documento cita matrícula não cadastrada"), nunca
criação silenciosa. Isso inclui a lista de matrículas do CAR
(`matricula_listada`, Ficha 08 §4) — o CAR confirma/atualiza uma matrícula que
já existe, mas não a cria mais.

**4. O achado nasce do canal que já existe ponta a ponta — a matriz de
inconsistências —, não de `generate_acoes_from_divergencias`.**
`inconsistency_matrix.build_matrix` já compara matrícula × CCIR × SIGEF × ITR
× CAR por campo (`denominacao_imovel`, `codigo_incra_sncr` já calculados; área
e RL já tinham emissor próprio em `property_audit.audit_property`). O que
faltava era o redirecionamento para persistência: `auditor_imovel.
_registral_findings_from_matriz` traduz as linhas não-consistentes desses
itens em `AuditFinding` e as persiste pelo MESMO `_persist_issues` que já
grava os achados determinísticos de área/RL — sem duplicar a comparação, só
mudando o destino de "Ação de consolidação" para "achado do diagnóstico".
`generate_acoes_from_divergencias` (`app/services/acao_generator.py`) ganha a
exclusão correspondente — `denominacao_imovel`/`codigo_incra_sncr` de
`matricula` não viram mais `Acao` ali, registrado em log estruturado
(`divergencias_redirecionadas_para_matriz`) para não desaparecer em silêncio
do rastro operacional. Titular (`proprietarios`) e NIRF ainda não têm
comparação na matriz (dívida #73 cobre titular; NIRF fica como follow-on) —
**continuam virando `Acao`** normalmente (não foram excluídos de
`acao_generator.py`) até ganharem emissor de achado próprio; excluí-los agora
apagaria trabalho de verdade sem substituto.

**5. O achado é modelado pelo encaixe do ADR-012: fato perene do imóvel →
`RegulatoryIssue`; decisão do consultor → contextual ao processo.** Reusa o
catálogo evolutivo (`regulatory_issue_catalog`) e o mecanismo de idempotência
já existente em `AuditorImovelAgent._persist_issues` (dedupe por property +
codigo_alerta + tema + descrição, entre não-resolvidos). Nenhuma peça nova de
UI/gate — a mesma camada 2 do Princípio 1 que já atende
`AREA_MATRICULA_X_CAR` etc. atende os dois códigos novos/religados
automaticamente.

**6. PR #143 (guard sem-destino, `_sem_destino`/`motivo_sem_destino`) é
ortogonal — mantido sem alteração de comportamento.** Ele resolve "este campo
tem onde pousar", este ADR resolve "esta fonte pode escrever aqui". A ordem
de precedência no filtro de fonte única aplica primeiro `motivo_sem_destino`
(um campo sem coluna — ex.: `vtn` — continua com o motivo antigo, não vira
"fonte errada") e só then a recusa por fonte.

## Consequências

**Boas**

- O sintoma original (fluxo trava, campo a campo, quando as fontes divergem)
  desaparece para os 7 campos do item 1: a matrícula grava direto, sem
  disputar. `_group_conflict_values`/`divergencias_devolvidas` seguem existindo
  só para o caso residual real (duas certidões de matrícula — re-upload,
  retificação — discordando entre si), que é jurídico de verdade, não ruído
  de fonte.
- O achado passa a existir **antes** da decisão do consultor (a matriz roda a
  cada E2/E4, sobre todo o staging — aceito ou não), mais cedo que o modelo
  anterior (que só via divergência entre linhas já ACEITAS).
- Fecha uma classe inteira do histórico de bugs de "fonte errada corrompendo a
  matrícula" (caso 13 — CCIR frankenstein por menor id; caso 15 — CCIR
  sobrescrevendo `proprietarios` com string nua) por construção, não por
  correção pontual: essas fontes nem chegam mais a `_write_entity` para esses
  campos.

**Custos e limites**

- **`matricula.numero_ccir` E `matricula.codigo_incra_sncr` ficam
  estruturalmente sem fonte que os escreva pela consolidação automática.**
  Por `_FIELD_SPECS` (`app/services/ficha01_extraction.py`), nenhum doc-type
  `matricula` tem `_FieldSpec` para `numero_ccir` (só `ccir` tem) nem para
  `codigo_incra_sncr`/`codigo_sncr_incra` (só `ccir` e `itr` têm — a certidão
  de matrícula não é hoje lida para código INCRA/SNCR). Aplicando a regra 1
  sem exceção, os dois campos nunca mais são gravados automaticamente, mesmo
  sem qualquer conflito — o único caminho que resta é a edição explícita do
  consultor (medido em `tests/api/test_gravado_visivel.py`, que dependia de
  ambos pousarem via CCIR). Isto é reportado aqui porque contraria a
  expectativa de uso (os dois campos existiam e eram preenchidos antes); a
  decisão foi aplicar a regra tal como dada, sem abrir exceção por conta
  própria, e registrar a consequência para revisão de produto. Duas saídas
  possíveis para quem revisar: (a) aceitar que são campos de edição manual
  daqui em diante, ou (b) estender o prompt/schema de extração do doc-type
  `matricula` para também ler INCRA/SNCR e nº do CCIR do próprio texto da
  certidão (quando citados), fechando a lacuna pela fonte certa.
- Titular (`proprietarios`) e NIRF (`nirf_cib`) estão na lista do item 1, mas
  não têm comparação na matriz de inconsistências hoje — o redirect do item 4
  só cobre denominação e código INCRA/SNCR. Título e NIRF perdem a escrita
  automática de fonte não-matrícula (regra 1 vale já) mas ainda não geram
  achado quando divergem (só ficam em `ignorados`, texto efêmero da rodada de
  consolidação) — é lacuna aberta, não comportamento pretendido.
- `IDENT_NOME_IMOVEL_DIVERGENTE` e `TIT_PROP_MATRICULA_X_CAR`/
  `TIT_PROP_MATRICULA_X_CCIR` já existiam no catálogo (seed original,
  PROMPT_5 Onda A) sem nenhum emissor — código morto até este PR ligar o
  primeiro. `IDENT_CODIGO_INCRA_SNCR_DIVERGENTE` é novo (migration
  `e4f6a8c2b1d9`). Os dois de titularidade seguem sem emissor (aguardam a
  comparação de titular, dívida #73).
- A régua de severidade do achado redirecionado (`atencao`, fixa) é mais
  simples que a régua de área/RL (4 faixas, calibrada em produção) — não
  houve dado de produção para calibrar denominação/INCRA-SNCR ainda; ajustar
  quando houver medição real.

## Supersede

- **ADR-017, ponto 1** (consolidação parcial: divergente vira Ação) —
  superado NO PONTO DA CONCORRÊNCIA SIMÉTRICA para os 7 campos registrais do
  item 1. `_group_conflict_values` → `divergente_transcricao` continua vivo e
  correto para o que sobrou: certidão×certidão em `matricula` (a devolução
  aparece em `divergencias_devolvidas`, como sempre), e a concorrência
  não-registral (CAR×ITR×RAT) em `imovel`. O que muda é o PASSO SEGUINTE
  (`generate_acoes_from_divergencias`): para `denominacao_imovel` e
  `codigo_incra_sncr` especificamente, a exclusão do item 4 é por CAMPO, não
  por fonte — mesmo um conflito certidão×certidão nesses dois campos não vira
  mais `Acao` (o achado já nasce da matriz, e ela não distingue se as fontes
  em conflito eram a mesma ou não). Para os outros 5 campos do item 1 (sem
  emissor de achado ligado ainda), certidão×certidão continua virando `Acao`
  normalmente. O ponto 2 do ADR-017 (ponte RL matrícula→imóvel) não é
  afetado.
- **Dívida #75** ("Ficha 08 §5 — duas cadeias de prioridade, não uma") —
  reescrita como superada em `docs/REGISTRO_DIVIDAS.md`: as duas cadeias não
  serão implementadas; a arbitragem por hierarquia de documentos deixou de
  ser o modelo.
- **Ficha 08 §5** — recebe nota apontando este ADR como a regra vigente para
  os 7 campos do item 1 (a ficha permanece como registro histórico da
  investigação de domínio que a originou).

## Alternativas descartadas

- **Implementar as duas cadeias de prioridade da Ficha 08 §5** (dívida #75
  original). Rejeitada pela Isis: mais uma hierarquia condicional por campo é
  exatamente a complexidade que produz o travamento — cada exceção é mais uma
  decisão que o sistema tenta automatizar e erra.
- **Manter CCIR/ITR/CAR como criadores de matrícula "só quando a matrícula
  ainda não tem número".** Descartada: foi o vetor real do caso 13 (certidão
  de embargo mal-classificada como `sigef` materializou uma "matrícula"
  fantasma) — o guard fantasma da Sprint 4 já apontava nessa direção; este
  ADR só termina de fechar a porta.
- **Deixar `numero_ccir` como exceção silenciosa à regra 1** (permitir CCIR
  escrever só esse campo). Descartada por decisão própria: a regra foi dada
  "sem exceção de campo"; abrir uma exceção não pedida seria reinterpretar a
  decisão, não implementá-la. A consequência fica registrada acima para
  revisão de produto, não corrigida por conta própria.

## Referências

- `app/services/staging_consolidation.py` — filtro de fonte única
  (`consolidate_process`, `flag_sem_casa`), guard fantasma
  (`_MATRICULA_CREATOR_DOC_TYPES`)
- `app/services/inconsistency_matrix.py:build_matrix` — matriz já existente,
  fonte do redirect
- `app/agents/auditor_imovel.py:_registral_findings_from_matriz` — o redirect
- `app/models/regulatory_catalog_seed.py`,
  `alembic/versions/e4f6a8c2b1d9_*.py` — catálogo
- Ficha 08 §4/§5 (`docs/fichas/FICHA_08_BASE_DADOS_CONFERENCIA.md`)
- Relatório da FASE 1 (read-only) deste mesmo trabalho — mapeamento completo
  arquivo:linha do caminho de escrita antes desta mudança
