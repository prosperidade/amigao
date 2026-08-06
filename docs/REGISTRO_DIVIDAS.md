# Registro de dívidas — Regente (consolidado pós-PROMPT_11 · 2026-05-26)

Reúne num lugar só as dívidas que estavam espalhadas por relatórios do agente, rodapés de skill,
memórias do desenvolvedor e análises de coordenação. Ordenadas por prioridade de desbloqueio.
Cada item: o que é, de onde veio, o que destrava, e o estado.

> **Convenção de governança:** este documento é VIVO (`docs/REGISTRO_DIVIDAS.md`) — atualizado ao
> fim de cada sprint. Itens fechados saem para a seção "Fechadas (histórico)" abaixo; não somem.
> Ver `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.

> **PRÓXIMO NÚMERO LIVRE: 91.** (#85 a #90 abertas pela remediação de 26/07,
> `fix/validacao-26-07`: vigia de revogação, editor de rota do consultor,
> `SourceRef.pagina`, área gravada em coluna de status, linguagem técnica na UI
> fora das telas da Isis, e as 4 specs da Ficha-do-chat. Ver bloco próprio.)
> (histórico do contador abaixo — **PRÓXIMO NÚMERO LIVRE: 80** era o valor antes.) (#79 aberta pela identidade da matrícula,
> `fix/consolidacao-lineage-decisoes`, 2026-07-20 — degrau 3 da cascata da Isis;
> ver abaixo. A #74 teve a FATIA NIRF fechada na mesma rodada.) (#78 aberta pela dívida #70,
> `fix/70-classificacao-persistida`, 2026-07-20 — extração dos documentos sem
> staging, medida e orçada, aguardando decisão; ver abaixo.) (#70 a #77 abertas pela fonte única de requisitos
> documentais, `fix/fonte-unica-requisitos-documentais`, 2026-07-20 — ver bloco
> próprio abaixo.)
> (#69 aberta pelo S5-C, `feat/s5c-assinatura-saidas` —
> assinatura eletrônica externa (gov.br/Clicksign); ver entrada abaixo.)
> (#68 aberta pelo S5-B, `feat/s5b-proposta-contrato-mirante` —
> follow-ons da consolidação da peça Mirante; ver entrada abaixo.)
> (#67 aberta pelo S5-A, `feat/s5a-rota-proposta-estados` —
> proposta/contrato multi-bloco/multi-titular; ver entrada abaixo.)
> (#66 aberta pelo forense caso Isis, `fix/forense-caso-isis`,
> 2026-07-18 — drift de mapa macroetapa→chain; ver abaixo. O forense também atualizou #60
> com o critério de domínio da Isis e #64 com mitigação parcial de backend.)
> Todo PR que abrir dívida nova incrementa este número
> (mata a classe de colisão que já aconteceu 2x — #21 e #44, ver nota na entrada 44a/44b
> abaixo). #59/#60 (PR #98) já mergeados; #61 usado na Fase 1 (ver abaixo). #62 aberta
> pela Fase 2 (`feat/fase2-reset-tool`, ver abaixo). #63/#64 abertas pelo Sprint 6
> (`feat/sprint6-limpeza-abas`, abas do workspace — ver abaixo). #65 aberta pela
> linguagem de consultor (`fix/dashboard-linguagem-consultor` — ver abaixo).
> Fase 1 (`feat/fase1-classificador-n1n2`) fecha #48 e #59; **#60 FECHADA** pela cadeia
> de fichas/vigência (`feat/60-vigencia-cadeia-matriculas`, ADR-027, 2026-07-18); #61 aberta.

## P0 — fecham o pipeline ponta a ponta

*Nenhuma aberta nesta camada — as duas que estavam (#1 e #2) foram fechadas pelo PROMPT_4.
Pipeline ponta-a-ponta no nível de código: auditor cruza → diagnóstico consome → grava
versionado → consultor assina.*

## P1 — (esvaziada após PROMPT_7)

*A re-modelagem do ADR-012 (dívida #20) foi implementada nesta rodada. Ver
tabela "Fechadas (histórico)" abaixo.*

## P2 — (esvaziada após PROMPT_8)

*A coerência entre os status (dívida #17) foi implementada nesta rodada
via 2 regras: helper `assert_status_coerente` sobre estado resultante no
PATCH `/issues` + bloqueio do PUT `/decision` quando achado em `suspeita`
(`assert_decisao_permitida`). Sem máquina de estados completa — barrou só
o absurdo óbvio. Ver tabela "Fechadas" abaixo.*

> **Nota de reconciliação (03/07/2026, Sprint 3 do selo — ADR-022):** o selo de 3 estados
> NÃO reabre a #17 — substrato disjunto. A #17 trata da coerência entre status do
> `RegulatoryIssue` (achado/saneamento/decisão); o selo vive no `field_sources` das
> entidades cadastrais (Client/Property/Matricula) e não circula por aqueles enums.
> A #17 permanece fechada como estava no PROMPT_8.

## P2 — produto/domínio (precisam da sócia)

**6. Conjunto canônico de documentos esperados** (para `DOCUMENTO_AUSENTE`). A régua de
área não gera finding quando um lado é `None`; falta definir quais documentos são essenciais
por tipo de caso. Conecta com a planilha de checklist 1.2.1 da sócia. **Origem:** Onda C
(24/05).

**7. Marcador de aplicação de citação** (`confirmada`/`aplicacao_preliminar`/
`hipotese_a_confirmar`) no `EnquadramentoRegulatorioContent` do Legislação. Distinto da
validação de existência (o `citation_evaluator`, que não muda). **Origem:** P3.

**8. Tool determinística de cálculo de uso do solo** — função Python, não LLM. Fórmula por
**período × localização jurídica** (ver "Regime de compensação por supressão em GO" na
skill de Diagnóstico). Pós-contrato. **Origem:** skill de Diagnóstico (gabarito Romilton).

**29. Critério do "Valor Estratégico — nível Baixo" não definido.** Na triagem do intake,
o eixo `valor_estrategico` tem 3 níveis (alto/médio/baixo). Para o nível **baixo**, a Isis
respondeu "não sei responder" — é label sem régua escrita; hoje o consultor decide livre.
Validar o critério na tela quando a Isis testar o wizard. **Proibido** implementar critério
agora (decisão pendente da sócia). **Origem:** PR intake campos derivados (30/05).

**36. Validade e alerta proativo de credenciais de portal.** O prompt de UI citava `valid_until`
e badge de vencimento, mas o contrato real em `CredentialCreate`/`CredentialResponse` não tem esse
campo; a UI do Cliente Hub foi implementada sem inventá-lo. Se a operação precisar controlar
expiração de senhas/procurações/acessos de portal, modelar `valid_until` no backend, expor na API e
criar alerta proativo (cron/Vigia ou dashboard). **Origem:** UI das credenciais no Cliente Hub
(31/05), divergência entre prompt e schema real.

**54. Criar WorkflowTemplate para demand_types sem cobertura.** *(Renumerada de #21 em
03/07/2026 — o número colidia com a dívida #21 "pares de status semanticamente incoerentes"
da revisão do PROMPT_6, abaixo.)* Auditoria de cobertura
em `docs/arquivo/auditorias/2026-05-28_cobertura_templates.md` aponta ausência de
template ativo para: `prad`, `sobreposicao`, `supressao`, `due_diligence`,
`arrendamento`, `condicionantes_antigas`, `misto`, `nao_identificado`. **Origem:**
Eixo 2 workflow por tipo (29/05). **Nota:** a rodada atual proibiu criar templates;
ficou apenas o erro explícito e o relatório. **Confirmada por rodada real
(2026-05-30, `fix/pr2.2-fechar-testes`):** script rodou contra o banco dev ativo e
reproduziu exatamente esses 8 gaps de template. Adicionalmente, mediu os gaps de base
regulatória (`LegislationDocument` com 0 documentos): `exigencia_bancaria`,
`sobreposicao`, `supressao`, `due_diligence`, `arrendamento`, `condicionantes_antigas`,
`misto`, `nao_identificado` — os 8 sem template (exceto `prad`, que tem 2 docs) + `exigencia_bancaria`.

## Reveladas pela fonte única de requisitos documentais (20/07)

*Abertas por `fix/fonte-unica-requisitos-documentais` (ADR-031). A auditoria que
as revelou está em `docs/auditoria/AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md`;
as regras de domínio, na Ficha 08 (`docs/fichas/FICHA_08_BASE_DADOS_CONFERENCIA.md`).*

**70. Vínculo doc↔requisito é evento no upload, nunca reprocessado.** → **FATIA ESTRUTURAL FECHADA** por `fix/70-classificacao-persistida` (20/07): o extrator passa a persistir o tipo classificado (só onde é NULL) e a re-disparar o vínculo, e `scripts/backfill_document_type.py` repara o retroativo com custo zero de IA. **FATIA DE DADOS TAMBÉM FECHADA** (20/07, ~18h50): backfill executado em prod pelo rito — **28 documentos** classificados (19 `auto_infracao`, 2 `itr`, 2 `rat`, 2 `sigef`, 1 `ccir`, 1 `planta_topografica`, 1 `certidao_embargo`), 8 preservados em NULL por não terem tipo específico, doc 355 (`outro`) intocado. O item `auto_infracao` do checklist foi marcado como recebido e **persistiu** — prova em produção do fix de `flag_modified`. Requisitos do caso 15 depois: Matrícula, CCIR, ITR e Planta/Memorial satisfeitos; pendência real de coleta caiu de 4 para **1** (só o CAR). Descrição original abaixo.  `auto_link_document`
roda uma vez, com o `document_type` do instante do upload. A classificação por conteúdo
(`classify_doc_type`) roda depois, no OCR/extração, e nada repara o vínculo. Medido no
processo 15: **36 dos 42 documentos têm `document_type = NULL`** — o `elif body.document_type:`
de `documents.py` nem chega a chamar o matching, e esses 36 nunca serão vinculados a
requisito nenhum. A fonte única (ADR-031) lê o tipo persistido, então herda a cegueira.
**Fix:** ao concluir a extração, reclassificar e re-vincular; backfill dos NULL existentes.
**Impacto:** alto — é o que mantém o processo 15 com documentos invisíveis para a base.

**71. Vínculo doc↔item gravado só de um lado.** `Document.checklist_item_id` é **NULL em
100% dos 42 documentos** do processo 15, inclusive no doc 317 que o checklist declara
`received` — o estado vive só no JSON do checklist. Qualquer consumidor que parta do
documento enxerga o requisito como não atendido. **Fix:** gravar `checklist_item_id` no
mesmo commit que marca o item recebido (bidirecional).

**72. Ficha 08 §3.2 — chave composta comarca + matrícula.** O número da matrícula sozinho
não é identificador único (só é exclusivo dentro do cartório emissor). A base usa o número
isolado. **Fix:** identificador `comarca/cartório :: número`. **Precede** qualquer cruzamento.

**73. Ficha 08 §3.1 — titular único do caso.** Um único titular por caso; nome/CPF do
cadastro devem bater com o documento de identidade, e qualquer outro nome (cônjuge,
coobrigado, herdeiro) é *parte relacionada*, nunca cotitular — mesmo com "proprietários"
no plural. Não implementado. **Fix:** resolver titular antes do cruzamento.

**74. Ficha 08 §4 — campos-âncora registrais novos.** **FATIA NIRF FECHADA** (20/07, ADR-032): `nirf_cib` entrou no `_FIELD_SPECS` da certidão + prompt + materialização, porque é INFRAESTRUTURA DE IDENTIDADE — o degrau 1 da cascata da Isis compara o NIRF do ITR contra o da matrícula, e o campo nascia sempre NULL, deixando o degrau mais forte morto e a cascata começando silenciosamente no degrau 2. **Seguem abertos** Livro, Folha, Ficha, Módulo Fiscal e nº do CCIR (completude, não identidade). **Somado à lista:** `vtn` — foi ACEITO no caso 15 e não existe coluna em `matriculas`; hoje aparece em `ignorados` na Conferência (não some mais calado), mas continua sem destino.  Livro, Folha, Ficha, NIRF/CIB,
Módulo Fiscal e Número do CCIR entram na base como campos próprios (alguns sem par de
cruzamento, §4.1). O extrator hoje não os emite. **Fix:** ampliar `_FIELD_SPECS`.

**75. Ficha 08 §5 — duas cadeias de prioridade, não uma.** A arbitragem de divergência
segue cadeia **jurídica** (Matrícula → SNCR/CCIR → Cafir/CIB → ITR → CAR) para
titularidade/INCRA/RL averbada, e cadeia **técnica** (Memorial/SIGEF → Matrícula → CAR)
para área/perímetro/coordenadas. O código usa hierarquia genérica única. **Fix:** aplicar
a cadeia correspondente ao campo.

**76. Ficha 08 §8 — normalização antes do cruzamento.** Três falsos positivos medidos em
simulação: coordenadas UTM (Matrícula) × geodésicas (SIGEF) comparadas sem conversão;
código de vértice `CWQ-M-0087` × `CWQ-M-087` (zero à esquerda); Gleba × Lote entre cadeia
jurídica e fiscal. **Fix:** normalizar antes de comparar (o terceiro já é alerta, não erro).

**77. Oportunidade de produto (Ficha 08 §8).** Quando o RAT do CAR aponta pendência e
solicita "certidão de matrícula atualizada" / "certificado de georreferenciamento", esses
documentos frequentemente **já estão na base**. A Conferência poderia responder com o que
já tem, em vez de o consultor recoletar. Não é dívida — é feature nomeada pela Isis.

**Vitest local: 9 workers falham com `ERR_REQUIRE_ESM`.** `@asamuzakjp/css-color` (CJS,
dependência transitiva do jsdom) faz `require()` de `@csstools/css-calc`, que virou
ESM-only. Os 79 testes que rodam passam; 9 arquivos não chegam a iniciar. **Verificado
idêntico na `main`** — não introduzido por este PR — e o CI **não roda vitest** (só ESLint,
tsc e build), por isso está verde. **Fix proposto:** `server.deps.inline:
['@asamuzakjp/css-color']` no `vitest.config`, ou `overrides` fixando `@csstools/css-calc`
numa versão CJS. Provável origem do `frontend/package-lock.json` que aparece modificado
sem diff de conteúdo no repo local.

## Reveladas pela dívida #70 (20/07)

**78. Extração de campos dos documentos sem staging — medida, não executada.**
Depois do backfill de tipo, 32 documentos do processo 15 seguem sem staging; 21
deles seriam extraíveis (9 caem em `outro`, sem tipo específico → sem spec de
campos). Volume medido: **~39,4k tokens de input** de texto já salvo — 141.875
chars só dos 19 autos de infração, 13.136 do RAT, 2.458 do CCIR. Em
`gemini-2.5-flash` isso é ordem de **centavos de dólar**, coerente com os
$0,085/caso do pipeline OCR. **Não rodado por decisão:** o prompt do #70 pediu
medir e orçar para o André decidir. **Fix:** disparar `extract_and_stage` nos
documentos com tipo e sem staging, em lote, com teto de custo.

**Achado: mutação de JSON não persistia no checklist — CORRIGIDO neste PR.**
`ProcessChecklist.items` é `Column(JSON)` sem `MutableList`. Os quatro helpers do
`checklist_engine` faziam `items = list(...)` → mutavam os dicts (compartilhados
com o atributo) → reatribuíam; no instante da atribuição "antigo" já era igual a
"novo", o objeto nunca ficava dirty e o flush não emitia UPDATE. **Marcar item de
checklist não persistia** em checklist já gravado — isto é, em todo upload
posterior e em toda marcação manual do consultor. Só não aparecia no fluxo do
intake, onde o INSERT grava o estado final. `macroetapa_engine.py:418-434` já
tinha curado exatamente isto no campo `actions` com `flag_modified`; os quatro
pontos de `items` ficaram sem o remédio. Corrigido com `_persistir_items`
(cópia dos dicts + `flag_modified`) e travado por testes que expiram a sessão e
releem do banco — o que o consultor vê depois do F5.

## Staging órfão — CORRIGIDO (20/07)

**Achado durante a verificação do backfill do #70.** 46 linhas de
`extracted_field_staging` do caso 15, em 7 documentos, com `process_id` NULL: campos
lidos, gravados no banco e **invisíveis** para a Conferência, a matriz e a fonte única
— todas filtram por processo.

**Causa raiz** (`extrator.py:172`): `process_id=(doc.process_id if doc is not None else
ctx.process_id)` testava a EXISTÊNCIA do documento, não o VALOR do campo. Documento
carregado ainda no rascunho (`process_id` NULL) passava None, e o fallback para o
contexto ficava inalcançável.

**Evidência (timeline do caso 15, mesmo rascunho 58):** extrações de 13:30:12 a
13:31:52 (docs 314-321) nasceram órfãs; as de 13:32:07 em diante (322, 324, 329) não.
Entre os dois momentos, o rascunho virou caso. Mesma rota, mesmo agente — só mudou se
o commit do caso já tinha acontecido. A hipótese inicial (re-disparo do fix #70) foi
**refutada pelos timestamps**: o backfill rodou 5h depois e nem chama `extract_and_stage`.

**Fix em duas camadas:** (1) `extrator.py` resolve `doc.process_id or ctx.process_id`;
(2) a migração draft→processo em `intake.py` passa a **adotar o staging** dos documentos
migrados — antes ela levava os documentos e esquecia o que já tinha sido lido deles.
A camada 2 é a cura na nascente.

**Reparo das 46 existentes** (`scripts/reparar_staging_orfao.py`, dry-run default):
decisão híbrida do André — 44 redundantes APAGADAS, 2 exclusivas ADOTADAS. As duas
exclusivas são `averbacao_rl` do doc 317 (a Reserva Legal averbada da matrícula 6.776)
e `municipio` do doc 320; apagá-las perderia leitura única. A adoção **não toca
`field_value`** — o bug dict→text do #81 nasceu de reserializar exatamente
`averbacao_app`/`averbacao_rl`, e há teste guardando isso.

**Carona:** o dry-run do backfill dizia "seriam gravados: 0" quando gravaria 28 —
`gravados` filtra pelo que foi escrito e zera no dry-run. Corrigido com `a_gravar`,
agora fonte única do relatório e da frase de confirmação.

## Identidade da matrícula (20/07) — o que ficou

**79. Degrau 3 da cascata de vinculação — corroboração por área + denominação.**
Spec pronta: resposta da Isis de 20/07. Quando NIRF e INCRA não resolvem, usar
área total e denominação do ITR contra cada matrícula candidata; se um candidato
bate nos dois (mesmo com grafia diferente — "Lote 01-C" × "Sao Jorge Lote 01-C"),
**vira sugestão de alta probabilidade — NUNCA autolink**. A Isis foi explícita, e
há comentário no código travando isso: quando este degrau for implementado, o
teste obrigatório é `nunca_autolinka`. Junto vem a tela rica de candidatos com os
sinais a favor de cada um. Enquanto não existem, o caso ambíguo cai no degrau 4
manual, que resolve. **Origem:** ADR-032.

**Perguntas de domínio em aberto com a Isis** (não bloqueantes, comportamento
conservador implementado): confirmação de leitura do vínculo ITR→matrícula por
INCRA normalizado (§4 aplicado). RAT×CAR já foi respondida em 20/07 (o RAT não
substitui o CAR) e está anotada na Ficha 08.

## Escalar em coluna de lista (21/07) — reveladas pela varredura de classe

Origem: o crash do `diagnostico` em produção (`'str' object has no attribute
'get'`). Corrigido em `fix/escalar-em-coluna-lista`; a varredura de classe que
acompanhou o fix achou o que segue.

**80. Reparo do dado já gravado em produção.** As 2 matrículas do caso 15 (ids
29 e 30) têm `proprietarios = "Leonardo Ribeiro"` — string nua em coluna de
lista, com `field_sources.proprietarios = human_validated`. O fix de LEITURA já
as tolera, então não há urgência nem risco; mas o dado segue torto e a
normalização (`[{"nome": ...}]`) deve rodar **pelo rito** (dry-run → aval →
execute). Não vai junto do bugfix de propósito: misturar correção de código com
migração de dado esconde qual dos dois quebrou se algo quebrar.

**81. A fonte BEM-FORMADA de `proprietarios` é descartada.** O prompt do
doc_type `matricula` já extrai `"proprietarios": [{"nome","cpf"}]` no shape
certo (`ficha01_extraction.py`), mas **não existe `_FieldSpec` roteando o
campo** — só os escalares `ccir.detentor` e `sigef.proprietario` alimentam a
coluna. Consequência: 100% dos valores vindos do pipeline nascem malformados e
dependem do embrulho de compatibilidade. Ligar o spec exige entrar em
`_LIST_COLLAPSE_FIELDS` (senão vira N linhas de staging por proprietário).
**Não entrou no PR do fix por razão operacional:** ligá-lo muda o que a extração
produz, e a Isis estava decidindo o staging do caso 15 no mesmo dia — linhas
novas apareceriam no meio da re-decisão. Sequenciar depois do teste.

**82. Tipar as colunas JSON em vez de tapar buraco a buraco.** Um
`TypeDecorator` derivado de `PortableJSON` (`PortableJSONList` /
`PortableJSONDict`) validando em `process_bind_param` mataria a classe inteira
nas ~20 colunas `default=list`/`default=dict`, em vez de depender de guard por
call-site. Toca todos os modelos e rebate em muitos testes (sem migration — é só
Python). Estimativa 3-5 dias. É a correção estrutural do arquétipo.

**83. Guards ausentes em colunas JSON que falham ALTO.** A varredura mapeou ~25
call-sites que iteram/indexam coluna JSON sem checar tipo:
`MacroetapaChecklist.actions` (5 pontos de leitura em API/dashboard),
`Proposal.scope_items`/`payment_installments` (proposta e contrato),
`ChecklistTemplate.items`, `WorkflowTemplate.steps`, `Etapa.sources`,
`AIJob.result` (`intake.py` e `intake_enrichment.py` não têm o `isinstance` que
`diagnostico.py` tem), `User.preferences`, `StageOutput.content_data`. Todos
falham alto (500 visível), nenhum corrompe dado em silêncio — por isso ficam
para o #82 em vez de virarem 25 `isinstance` avulsos.

**84. `KnowledgeDoc.extra_metadata.demand_types` compara escalar contra array.**
`knowledge_catalog.py` usa `CAST(... AS jsonb) @>` sobre `demand_types`; se o
valor tiver sido gravado como string em vez de lista, o `@>` nunca casa e a
busca volta **silenciosamente vazia**. Mesma família do #83, mas silencioso —
merece guard próprio quando alguém encostar no módulo. O irmão desta classe
(`legislation_monitor`, onde `in` sobre string virava match de SUBSTRING) já foi
corrigido junto do fix.

---

### Abertas pela remediação de 2026-07-26 (`fix/validacao-26-07`)

**85. Vigia normativo de revogação — 3 degraus.** Hoje o sistema afirma *"vigência
conferida em DD/MM/AAAA"* (ADR-035, item 12) — que é honesto e insuficiente. O
degrau (a) foi entregue: a data da última verificação do corpus aparece ao lado de
cada norma. Faltam: **(b)** *detecção* — job que reconsulta a fonte oficial e marca
`LegislationDocument.revoked_at` quando a norma cai; **(c)** *propagação* — alerta
no caso que citou a norma revogada, para a consultora saber que uma fundamentação
já usada mudou de status. Sem (b) e (c), "conferida em 12/2024" pode significar
"revogada em 03/2025 e ninguém viu". **O que destrava:** confiabilidade da
biblioteca qualificada ao longo do tempo — que é o produto inteiro da ADR-033.

**86. Editor de rota do consultor.** Consequência direta da ADR-033: se o agente
não propõe mais rota, a consultora precisa de onde **construir a dela**. Hoje a
`Rota`/`RotaPasso` (E5) só nasce por caminho automático; falta a tela de compor,
ordenar e anotar passos à mão, com fonte por passo (`origem_manual_nota` já existe
no model). **O que destrava:** fecha o ciclo que a ADR-033 abriu — sem isso a
decisão de sombrear a rota tira uma muleta sem entregar a ferramenta. **Prioridade:
alta** — é a próxima fase da fila oficial.

**87. `SourceRef.pagina` não é populada pelos extratores.** O contrato de UI já
aceita página (`FonteChip` renderiza "p. N" quando existe) e a ADR-035 exige
"documento de origem + página". Os extratores ainda não devolvem o número da
página do trecho lido — então hoje o clique abre o documento, mas no início, não
no ponto. **O que destrava:** conferência de fonte em documento longo (auto de
infração de 40 páginas) deixa de ser uma caça ao trecho.

**88. `rl_declarada_ha` grava ÁREA na coluna de STATUS (`Property.rl_status`).**
Medido em prod no processo 15: `properties.rl_status = "250,2094"` — um número de
hectares numa coluna que descreve situação ("averbada"). Vem do mapeamento
`ficha01_extraction._FIELD_SPECS['car']: rl_declarada_ha → imovel.rl_status`, somado
à entrada de `rl_status` na allowlist da consolidação. O Hub exibe "Reserva Legal:
250,2094". **Fix correto:** coluna `Property.rl_area_ha` (migration aditiva) +
remapeamento, mantendo `rl_status` para situação. **Não foi feito aqui** por ser
mudança de modelo com efeito no Hub e no dossiê — escopo próprio. **Dado sujo em
prod:** 1 linha (property 12), a corrigir junto do fix.

**89. Linguagem técnica na UI — telas fora do escopo da Isis (item 14c).** A
varredura de 26/07 catalogou termos internos renderizados crus. O que a Isis opera
(workspace, Conferência, diagnóstico) foi corrigido em `fix/validacao-26-07`; o
restante fica para PR próprio de linguagem, com esta tabela como spec:

| tela | termo exposto | tradução proposta | esforço |
|---|---|---|---|
| `ProcessDossier.tsx:398` | `{doc.document_type}` cru (`auto_infracao`) | `docTypeLabel()` | S |
| `ProcessDossier.tsx:457` | `{p.status}` da proposta, cru | dicionário de status comercial | S |
| `PropertyHub.tsx:709` | `{iss.tipo}` da issue, cru | `FAMILIA_LABEL` / rótulo de alerta | S |
| `PropertyHub.tsx:1122` | `{ev.entity_type}` (`process`, `document`) | dicionário de entidade | S |
| `DashboardRegente.tsx:359` | `{a.severity}` cru | `SEVERITY_LABEL` (já existe) | S |
| `ProcessChecklist.tsx` | `status` `pending`/`received`/`waived` em lógica e rótulo | dicionário de checklist | M |
| `MacroetapaStepper.tsx` | `step.status === 'completed'` refletido em texto | rótulos de etapa | M |
| `AgentsPage`/`AIPanel` | nomes internos de agente e `job.status` inglês | `AGENT_LABELS` (existe) + status PT | M |
| global | `failed`/`running`/`queued` em toasts e badges | "falhou — tentar novamente" etc. | M |

**Já existia e foi reusado (não refazer):** `fieldLabels.ts` (campos),
`activityLabels.ts` + `AGENT_LABELS` de `@/types/agent` (eventos e agentes),
`regulatory/labels.ts` (severidade/família), `quadro-types.ts` (demanda/macroetapa).
Adicionado agora: `lib/labels/docLabels.ts` (tipo de documento, tipo de fonte,
origem do dado) com teste de guarda.

**90. Especificações pendentes da Ficha-do-chat (análise futura).** Quatro
conceitos nomeados mas ainda sem spec fechada: **(a) readiness gate** — o que
significa um caso estar "pronto" para avançar, além dos gates atuais por
macroetapa; **(b) classificação de achados** — taxonomia estável do que o auditor
encontra, separando "divergência", "lacuna" e "risco"; **(c) evidência com força**
— graduar o peso de uma fonte (documento oficial > relato > inferência), que hoje
existe só como `confianca` solta em `SourceRef`; **(d) versionamento** — o que se
versiona (diagnóstico, consolidação, ficha) e o que apenas se audita. **O que
destrava:** os quatro decidem juntos como o sistema fala sobre certeza.

**91. A exceção de "Gravar na base" (30/07) não foi reconstituída.** A auditoria
de produção prova que o clique falhou e não completou (toda a sessão da Isis está
na trilha; a linha `consolidar` de 30/07 não existe). O **replay** da
`consolidate_process` contra o staging real do caso 15 — 34 aceitos, 7
`divergente_transcricao`, `proprietarios` como string nua do legado #80, base no
estado pós-26/07 — **não levanta exceção**: a causa é ambiente (fila, timeout de
plataforma, estado de sessão) e não se reconstitui sem o log da aplicação, fora
de alcance nesta rodada. `registrar_falha_consolidacao` + o `logger.exception` no
endpoint existem para que a PRÓXIMA ocorrência seja diagnosticável em um minuto.
**Marco para fechar:** primeira linha `consolidar_falhou` em produção — ler o
`erro_tipo`/`erro` e corrigir a causa raiz. **Origem:** validação Isis 30/07.

**92. Classificação documental grossa: o dossiê inteiro vira `auto_infracao`.**
No caso 15, **19 documentos** são tipados `auto_infracao` — mas o conjunto tem
ofício, notificação, julgamento, PRAD, resposta técnica, requerimento REFIZ,
relatório de vistoria, termo de embargo e pedido de prorrogação. Consequências
medidas: `_stage_ficha01` roda `extract_auto_infracao_fato` em todos, cada peça
produz um "fato de auto" e o consultor vê 5 autos onde existem 2 (o mesmo auto
484341 apareceu 3 vezes porque `orgao_autuante` variou entre "IBAMA", "IBAMA-GO"
e "IBAMA/MMA - SUP. ESTADUAL", quebrando o dedupe de `_chave_auto`). A rodada de
30/07 tratou o SINTOMA (a fonte agora nomeia o arquivo real e marca confiança);
a causa é de classificação. **O que destrava:** subtipos de peça de fiscalização
(`auto_infracao` vs `oficio` vs `notificacao` vs `prad` vs `termo_embargo`) em
`classify_doc_type`, e canonicalização da sigla do órgão antes do dedupe.
**Origem:** validação Isis 30/07.

**93. `.docx` nunca é lido — fica em `ocr_status=pending` para sempre.** O
documento 360 do caso 15
(`relatorio_ampliado_defesa_car_fazenda_sao_jorge.docx`) foi anexado em 30/07 às
19:55 e continua sem `extracted_text`: o pipeline de OCR trata PDF e imagem, e o
`.docx` entra na fila e não sai. Até a rodada de 30/07 isso era **silencioso**;
agora ele aparece no contexto do diagnóstico marcado `sem_leitura`, então o furo
é visível — mas o conteúdo continua fora. **O que destrava:** extrator de texto
para `.docx`/`.odt` (biblioteca local, sem custo de IA) no `ocr_pdf`/`ocr_tasks`,
ou recusa explícita no upload. **Origem:** validação Isis 30/07.

**94. A primeira regeneração de rota pós-#4 pode reordenar passos legados.** A
`dedupe_key` do `RotaPasso` deixou de incluir `norma_ref` (era ela que duplicava
a rota a cada execução). Passos gravados antes disso carregam chave legada e são
casados por um índice de compatibilidade `(orgao, titulo)` — o que impede a
duplicação, mas **não regrava** a `dedupe_key` antiga. Efeito: a linha continua
correta e estável, e a chave persistida fica dessincronizada da fórmula atual.
**O que destrava:** script idempotente que recalcula `dedupe_key` dos passos
`origem=ia` (custo zero de IA, mesmo padrão do `backfill_document_type.py`).
Baixo impacto — em produção há 1 rota com 11 passos. **Origem:** item 4 da
validação Isis 30/07.

### Abertas pelo corpus federal — pacote A (31/07, `feat/corpus-federal-defesa`)

**95. Corpus antigo com mojibake (`U+FFFD`).** O planalto.gov.br responde
`Content-Type: text/html` **sem charset**; o httpx assume utf-8 sobre bytes
ISO-8859-1. Os diplomas federais ingeridos em abril entraram com todo acento
corrompido — o corpus guarda `"Art. 3� O �rg�o ... aplicar� as seguintes
san��es"` no lugar de `"Art. 3º O órgão ... aplicará as seguintes sanções"`.
Passou três meses despercebido porque **texto corrompido não levanta exceção**:
só degrada a citação e o embedding, em silêncio. **Corrigido para ingestões
novas** (`scripts/ingest_legislation.py:_decodificar`, com canário
`verificar_mojibake` que recusa acima de 0,05%); os documentos **já gravados não
foram reprocessados**. **O que destrava:** reingerir os 7 federais de origem
Planalto (ids 16–25) com o mesmo script — custo de embedding desprezível.
**Origem:** ADR-037.

**96. Espaço não-quebrável em 998 chunks do corpus antigo.** O Planalto separa
"Art." do número com `U+00A0`. O texto *parece* `"Art. 18."` e não casa com
`"Art. 18."` em busca nenhuma — nem na nossa (`chunk_text LIKE '%Art. 18.%'`
devolvia 0 linhas para um artigo que estava lá), nem no Ctrl+F de quem lê a peça
pronta. `sanitize_text` passou a normalizar; o já gravado, não. Fecha junto com
a #95 (mesma reingestão). **Origem:** ADR-037.

**97. Proveniência não tem campo próprio no modelo.** Auditoria de 31/07: **54
dos 64 documentos (97,3% do texto do corpus) não têm URL** — só `file_path`
apontando para PDF de disco ou `.md` compilado, e nenhum campo diz se a fonte é
oficial. Os compêndios estaduais (`MT-NUC01`, 3,0 M chars) não registram quem os
compilou nem de que fonte. O pacote A grava `fonte_origem`/`fonte_oficial`/
`fonte_url` em `extra_metadata`, mas isso é convenção, não contrato. **O que
destrava:** colunas `fonte_origem TEXT`, `fonte_oficial BOOLEAN NOT NULL DEFAULT
false` e `fonte_conferida_em DATE` em `legislation_documents`, com backfill a
partir de `url`/`file_path` e `fonte_oficial=false` para tudo que veio de disco.
Enquanto não existir, o selo do ADR-035 não distingue "fonte oficial" de "PDF que
estava numa pasta". **Origem:** item 0 da medição de 31/07.

**98. IN IBAMA 10/2012 ingerida de fonte não-oficial.** O portal do IBAMA
responde 403 a cliente não-browser e o DOU não resolveu para esta norma.
Ingerida do LegisWeb, marcada `fonte_oficial: false`, com `validation_keyword`
como guarda — necessária: o mirror óbvio (`legisweb id=245167`) servia uma
**resolução da SEFAZ-AM**, e a guarda pegou. **Pedido à Isis:** PDF oficial da
IN 10/2012; ao chegar, reingerir e o metadado vira oficial. **Origem:** ADR-037.

**99. Pacotes B e C do corpus federal — não executar sem decisão.** **B (núcleo
federal ausente):** ICMBio, ANA, CONAMA de fauna/hídrico/UC, Lei 11.428 (Mata
Atlântica) — ~12 documentos, ~540 chunks, ~US$ 0,003. **C (rito IBAMA
completo):** INs de embargo, PRAD, CTF, conversão de multa — ~10 documentos,
~540 chunks, ~US$ 0,003. O custo de embedding é irrelevante nos dois; o custo
real é **curadoria humana** da lista de URLs e conferência de vigência.
**Origem:** medição de 31/07.

**Encaixe com a #85 (vigia de revogação).** O pacote A entrega a metade de baixo
do #85: o lugar onde a revogação passa a morar (`vigencia_fim` +
`sucessora_id`/`sucessora_ref`), o rótulo que ela produz no dado e o recorte
temporal na busca (`search(vigente_em=...)`). Falta ao #85 só o **gatilho** —
quem descobre a revogação e escreve nesses campos; nenhuma modelagem nova é
necessária. **Uma consequência de projeto a não esquecer:** como o rótulo é
gravado no `title` do chunk **na indexação**, marcar uma norma como revogada
exige **reindexar** seus chunks — o UPDATE na tabela sozinho não muda o que
chega ao modelo. O vigia precisa disparar `index_legislation_document` para o
documento que acabou de marcar.

### Saneamento do corpus (01/08, `fix/saneamento-corpus`)

**#95 — mojibake: FECHADA para os 7 federais, ABERTA para 3 do Acre.**
`scripts/sanear_corpus.py --mojibake` rebaixou da URL de origem, conferiu que
saiu limpo e reindexou: Lei 12.651/2012, Lei 9.605/1998, Lei 9.985/2000, Lei
6.938/1981, LC 140/2011, Decreto 7.830/2012 e Decreto 8.235/2014 — de ~4% de
U+FFFD para **0%**, 433 chunks refeitos, 0 embedding nulo. O `UPDATE` é no mesmo
`id` (não supersede), o que preserva quem aponta para o documento via
`sucessora_id`. Restam **41 chunks** em 3 documentos do Acre (`AC-N10` 0,51%,
`AC-N04` 0,044%, `AC-N05` 0,012%): vieram de `.md` em disco, não têm URL, e rede
não resolve — entram no pedido à Isis junto do #98. Nota: os dois últimos estão
**abaixo do limiar do canário** (0,05%), então nem um reprocesso automático os
pegaria; precisam do arquivo original.

**#96 — invisíveis: dry-run pronto, execução aguardando aval.** 651 chunks em 25
documentos com `U+00A0`/`U+200B`/`U+FEFF`. Remediação por `UPDATE` **in-place**,
sem reembedar: o caractere é semanticamente invisível, então o vetor não muda de
forma relevante e o que se recupera é a busca **literal** — `chunk_text LIKE
'%Art. 18.%'` devolvia ZERO para um artigo que estava no corpus. **Custo de
embedding: US$ 0,00.** O `content_hash` é recalculado no mesmo passo (sem isso, a
próxima reindexação não reconheceria o texto e duplicaria tudo). Rodar com
`--invisiveis --executar`.

**#97 — proveniência: FECHADA.** Migration `b5c92fa4d7e1` com `fonte_origem`,
`fonte_oficial` (NOT NULL DEFAULT **false** — o que ninguém conferiu não se
apresenta como oficial) e `fonte_conferida_em`. Backfill medido: **54 documentos**
de disco → oficial por curadoria da Isis, com data 01/08/2026; **18** com URL de
domínio oficial → oficial deduzido, sem data; **1** (LegisWeb) → não-oficial. A
regra vive em `app/services/proveniencia.py`, testável, e a migration a espelha.
A proveniência viaja no `SearchResult` e chega à citação localizada de
`lookup_enquadramento` — o único ponto do fluxo em que o chunk é conhecido; daí
em diante só há o texto livre do modelo. UI: `FonteChip` mostra "fonte oficial —
X" em cinza e "fonte não conferida — X" em âmbar. Oficial **não** virou selo
verde de destaque: transformar o normal em troféu treina o olho a ignorá-lo.

**#98 — pedido à Isis (ampliado).** (a) PDF oficial da IN IBAMA 10/2012; (b) os
`.md` originais do Acre (`AC-N04`, `AC-N05`, `AC-N10`), para fechar a #95.

**100. A fresta do guard de identidade — FECHADA nesta rodada.** O guard do
ADR-036 usava `_digitos()`, que concatenava os dígitos de `identifier + title +
chunk_text` numa string única e fazia busca de **substring**. Para o trecho
`Decreto 6.514/2008 · "Art. 18. O descumprimento..."` isso dava `6514200818`, e
**"65142"**, **"142"** e **"18"** — nenhum deles norma daquele trecho — eram
confirmados. Fresta mais estreita que o bug original do ADR-036, e da mesma
família: fonte falsa com aparência de rigor, em peça assinada. Corrigido com
comparação por **token** de número (`_numeros_de_norma`), que além disso rejeita
número precedido de `Art.`/`§`/`inciso` — dispositivo nunca identifica a norma
que o contém — e tolera `U+00A0` como separador de milhar. 11 testes; a
regressão do ADR-036 (compêndio do MT confirmando lei federal) segue rejeitando.
**Origem:** sonda do saneamento, 31/07.

**101. Integridade dos compêndios agregados — MEDIDA, não resolvida.** Origem
oficial (confirmada pelo André em 01/08) **não garante integridade**: o compêndio
pode ter perdido artigo, ementa ou vigência **na compilação**. Sinal medido
(normas distintas citadas × articulados presentes, via `Art. 1º`):

| compêndio | normas citadas | com articulado |
|---|---:|---:|
| MS-NUC04-licenciamento | 62 | 36 |
| AC-N05-hidrico | 35 | 15 |
| Portaria SEMAD-GO 501/2024 | 53 | 39 |
| MT-NUC01-constitucional | 101 | 151 |
| MT-NUC08-biomas | 178 | 197 |

Os MT vêm com mais articulados que normas citadas (compilação farta); MS-NUC04 e
AC-N05 vêm ao contrário. **O sinal é FRACO e não prova truncamento**: compêndio
cita norma correlata sem reproduzi-la o tempo todo, e isso é legítimo. Para virar
prova seria preciso confrontar o índice declarado de cada compêndio com o que tem
articulado. **Nada foi reingerido e nada é afirmado além do número.**
**Origem:** item de integridade do saneamento, 01/08.

### Abertas pela validação da Isis de 02/08 (`fix/validacao-02-08`)

**102. A Rota da E5 não lê o diagnóstico técnico nem as ações da E4.** ✅ **FECHADA em 03/08** (`feat/rota-do-diagnostico`, ADR-038) — ver o fecho no fim desta entrada. Pergunta
literal da consultora: *"a rota traçada na E5 se direciona pelas ações definidas
na E4?"* **Não** — e nem pelo diagnóstico. Medido: `materialize_rota`
(`app/services/rota_materializer.py:480`) monta um `AgentContext` **sem
`chain_data`** (`:258-264`) e a `LegislacaoAgent` consome apenas `demand_type`,
campos do imóvel, o texto livre `process.initial_diagnosis`, o corpus (RAG) e os
órgãos derivados de documentos de fiscalização (`_bloco_passivos_esfera`).
`Acao` e `RegulatoryIssue`/`RegulatoryDiagnosis` têm **zero ocorrências** no
caminho da rota. Pior: `initial_diagnosis` é escrito **só no intake**
(`app/api/v1/intake.py:85,242,457`) e a coluna se declara "pré-diagnóstico por
regras" (`app/models/process.py:132`) — o `DiagnosticoAgent` lê e nunca escreve
de volta. Ou seja, a rota enxerga o palpite do minuto 1 do caso, congelado, e
tudo que foi construído da E2 à E4 passa ao largo. **Diverge da própria Ficha
07** §8.1 ("desenhada pela Legislação a partir do **diagnóstico fundamentado**")
e §5 (E4 "Ações: refinadas e finais" → E5 "a aba Ações assume a forma de rota").
**O que destrava:** alimentar a `LegislacaoAgent` com diagnóstico fundamentado +
ações da E4, e dar ao `RotaPasso` a origem (`derivado_de_acao_id`) para a rota
ser rastreável até o passivo. **Muda desenho — exige ADR e decisão do André
antes de implementar.** Reportado sem implementar, por instrução. **Origem:**
item 0 da validação de 02/08.

**103. ✅ FECHADA em 03/08** (`feat/transcricao-audio` · ADR-060 · ver faixa
200-299 abaixo). **Não existe transcrição de áudio em lugar nenhum do sistema.** A validação
de 02/08 pedia áudio na E2; ao medir, descobriu-se que o pipeline que se supunha
existir na E1 também não existe. `IntakeDraft.audio_url` é gravado e **não é
lido por serviço algum**; a menção a Whisper em `app/schemas/intake.py:101` é
comentário, não código. O commit `feat(áudio)` desta rodada igualou as duas
portas de **upload** — o arquivo chega, fica anexado ao caso e visível. Mas
"gravar/transcrever áudio" continua sendo trabalho manual do consultor. **O que
destrava:** um worker de transcrição (Whisper via `ai_gateway`) que persista o
texto em `Document.extracted_text`, e daí o extrator já flui. **Origem:** item 4
da validação de 02/08.

**104. ✅ FECHADA em 03/08** — a leitura em produção foi executada; a hipótese se
confirmou e apareceu uma segunda causa (dívida #200). Detalhe na faixa 200-299
abaixo. **#91 não pôde ser fechada — falta a leitura em produção.** O relato
("aceitei matrícula, CCIR e ITR e só NIRF/CCIR/INCRA pousaram") foi atacado pela
causa provável mais forte encontrada no código: `divergencias_devolvidas` voltava
na resposta e **nunca era renderizada** (corrigido nesta rodada). Mas isso é
hipótese medida em código, **não** confirmação do caso dela. Esta sessão não tem
MCP do Supabase nem credenciais de produção. **O que destrava** — rodar em prod,
com o `process_id` do caso dela:

```sql
SELECT created_at, action, details
FROM audit_logs
WHERE entity_type = 'process' AND entity_id = <PROCESS_ID>
  AND action IN ('consolidar', 'consolidar_falhou')
ORDER BY created_at DESC;
```

`consolidar_falhou` (do #126) traz `erro_tipo`/`erro`; `consolidar` traz
`ignorados`, `divergencias_devolvidas` e `writes` — juntos dizem exatamente por
qual dos três caminhos cada aceite saiu. **Origem:** item 2 da validação de
02/08.

**105. Suíte do frontend acusa 10 erros de worker (não relacionados ao código).**
`npx vitest run` reporta `Test Files 11 passed / Tests 86 passed / Errors 10`.
Causa raiz: `@asamuzakjp/css-color` (CJS, dependência transitiva do jsdom) faz
`require()` de `@csstools/css-calc`, que é ESM puro — `ERR_REQUIRE_ESM` na
partida de alguns workers. **Verificado idêntico na `main`** (mesma contagem),
portanto não é regressão desta rodada. Os testes passam porque o pool recria o
worker. **O que destrava:** fixar `@csstools/css-calc` numa versão CJS via
`overrides` no `package.json`, ou migrar o pool do vitest para `threads`.
**Origem:** medição de 02/08.

### Abertas pelo ingestor curado — Bloco 0 + núcleo 06 (03/08, `feat/ingestor-curado-nucleo06`)

**106. Avaliar a versão COMPILADA como camada adicional do corpus.** A planilha
da Isis aponta as versões *compiladas* de Decreto 6.514/2008, Lei 12.651/2012 e
Lei 6.938/1981; o corpus tem as **anotadas**. Decisão de 03/08: manter as
anotadas — são elas que trazem `"Redação dada pelo Decreto nº 12.189, de 2024"`
inline, e é isso que sustenta *tempus regit actum* (ADR-037). A compilada
responde melhor "o que vale hoje" e polui menos o chunk; ter as duas dobraria o
texto dessas três normas. **O que destrava:** decisão da Isis sobre se o ganho
compensa a duplicação. Enquanto isso a escolha está **codificada no manifesto** —
as três dão `skip` por hash idêntico a cada rodada, o que torna a decisão
verificável em vez de comentada. **Origem:** ADR-038.

**107. DILUIÇÃO POR DOCUMENTO GIGANTE — a norma-mãe compete consigo mesma.**
Classe nova de falha, nomeada em 03/08. A CF entrou íntegra: 495 chunks, **72% de
todo o núcleo 06**. O art. 225 é recuperável quando a consulta o **nomeia**
(similaridade 0,69), mas uma paráfrase do próprio texto dele — *"todos têm
direito ao meio ambiente ecologicamente equilibrado"* — traz o **art. 205**
(educação) à frente. Não é defeito de ingestão: é um documento de 495 artigos
onde cada dispositivo disputa com os outros 494, e o dispositivo que importa
afoga. Vale para toda norma-mãe extensa (CF, Código Florestal, Decreto 6.514).

**Hipótese a testar quando atacarmos:** enriquecer o chunk com a identificação do
artigo no `title` — mesmo princípio do rótulo de vigência do ADR-037, **metadado
no chunk vale mais que reranking depois**. O rótulo histórico já provou que
informação gravada no dado chega a todo consumidor sem que nenhum deles precise
saber que ela existe; a identificação de dispositivo tende a se comportar igual.
Parente também da regra de identidade do ADR-036, aplicada *dentro* de um mesmo
documento. **Não implementado nesta rodada** — a hipótese fica registrada para
não se perder.

**108. Frente própria: os 165 alertas da curadoria.** A aba `Alertas_Regente` da
planilha traz 165 linhas de "gatilho → ação sugerida". **Isso não é corpus, é
spec de motor de diagnóstico** — e o Auditor já tem ~40 alertas implementados.
**O que destrava:** comparar os 165 com os 40 atuais, mapear sobreposição e
lacuna, implementar em ondas. Não misturar com corpus: são coisas diferentes que
só parecem próximas por virem na mesma planilha. **Origem:** entrega do mapa
normativo, 02/08.

**109. Referências operacionais são o embrião do "onde protocolar".** As 10
linhas `referencia_operacional` do núcleo 06 (FAQ do auto, consulta de áreas
embargadas, obter certidão de embargo, REGULARIZE/PGFN, impedimentos do Manual de
Crédito Rural) são exatamente o que o **editor de rota do consultor** (#86)
precisa consumir: onde se protocola, onde se consulta, onde se obtém. Hoje estão
versionadas no manifesto e não são exibidas em lugar nenhum. **O que destrava:**
o editor de rota ler o manifesto por bloco. **Origem:** ADR-038.

**#98 — pedido à Isis, ampliado.** Agora com quatro itens, todos com a mesma
causa nos dois últimos: (a) PDF oficial da IN IBAMA 10/2012; (b) os `.md`
originais do Acre (`AC-N04`, `AC-N05`, `AC-N10`); (c) PDF oficial da **IN IBAMA
21/2023**; (d) PDF oficial da **Portaria IBAMA 15/2026**. O portal do IBAMA
responde 403 a cliente não-browser. Retorno completo em
`docs/trabalhos/retorno_curadoria_isis_2026-08-03.md`.

> **✅ FECHAMENTO DA #102 (03/08, `feat/rota-do-diagnostico` · ADR-039).** O
> insumo da rota passou a ser o diagnóstico ASSINADO + as ações triadas
> (`tipo_triagem ∈ {tarefa, escopo}`), via `app/services/rota_contexto.py`.
> O filtro de quais achados dirigem a rota reusa `muda_rota_regulatoria`, que já
> existia no catálogo e na `RegulatoryIssue` e **ninguém lia** — hierarquia
> decisão humana > override do caso > default do catálogo. `RotaPasso` ganhou
> `origem_issue_id`/`origem_acao_id` (SET NULL), fechando a corrente
> achado → ação → passo → item da proposta. `initial_diagnosis` foi rebaixado a
> "relato do cliente — não conferido". Sem diagnóstico assinado, a geração é
> bloqueada com 409 e frase acionável. Diagnóstico que anda depois da rota
> **avisa**, nunca regenera.

### Abertas pela rota fundamentada (03/08, `feat/rota-do-diagnostico`)

**110. Proveniência do passo depende do LLM declarar `origem_refs`.** O prompt
lista os achados/ações com rótulos (`ACHADO-<id>`, `ACAO-<id>`) e exige que cada
etapa devolva de quais nasceu. Referência que não casa com o que existe no caso
é **descartada com log** (nunca inventada), mas referência OMITIDA produz passo
sem proveniência — silenciosamente. Hoje não há métrica de quantos passos saem
sem origem. **O que destrava:** contar `passos_sem_origem` no log de
`rota_materialized` e, se a taxa for alta, considerar um segundo passe
determinístico que case passo↔achado por similaridade de título (com o consultor
confirmando). **Origem:** ADR-039, seção "Consequências".

**111. Achado que dirige a rota pode ficar sem passo.** O prompt pede que cada
achado seja endereçado; pedido não é garantia. O aviso de reconciliação
(`fundamento_mudou_desde_a_rota`) pega o caso, mas só DEPOIS de a rota existir e
só na leitura da aba — não há verificação no momento da geração. **O que
destrava:** ao materializar, comparar os achados que dirigem contra os
endereçados e devolver a diferença no `RotaMaterializeOut`, como o
`orgaos_corrigidos` já faz. **Origem:** ADR-039, seção "Consequências".

**112. Rotas legadas nunca terão proveniência.** Passos gerados antes da ADR-039
nasceram de um contexto sem achados nem ações; backfill seria inventar origem.
Ficam NULL — e por isso o aviso de reconciliação se cala quando NENHUM passo da
rota tem origem (senão todo caso antigo acusaria "desatualizada" para sempre).
Efeito colateral aceito: uma rota legada que de fato ficou para trás não avisa.
**O que destrava:** regenerar a rota desses casos quando o consultor passar por
eles — a versão anterior fica guardada (#126). **Origem:** ADR-039.

### Aberta pelo fix do recall vetorial (03/08, `fix/rag-ivfflat-probes`)

**113. Reavaliar `lists`/`probes` do índice vetorial — GATILHO: quando os chunks
DOBRAREM.** `probes=10` é o remédio para o índice de **hoje**:
`ix_knowledge_catalog_embedding_cosine`, IVFFlat com `lists=100`, sobre ~31 mil
chunks. Os dois parâmetros são acoplados — `probes` só faz sentido em relação a
`lists`, e `lists` só faz sentido em relação ao número de vetores. Crescer o
corpus sem revisitar os dois traz de volta o mesmo modo de falha.

**Gatilho objetivo, para não virar "revisar um dia":** quando
`select count(*) from knowledge_catalog` passar de **~62 mil** (o dobro de agora),
reavaliar `lists` e `probes` **juntos**, medindo recall com a mesma régua usada
em 03/08 — comparar o top-k devolvido pela busca com o top-k exato obtido por
varredura sem índice.

**Alternativa a avaliar nessa hora: trocar IVFFlat por HNSW.** O HNSW não tem
este modo de falha: não existe `probes` para esquecer de ajustar, o recall é
consistentemente melhor e a latência é comparável na nossa escala. O custo da
troca é uma reindexação — que **não gasta API**, porque não é reembedding; os
vetores já estão gravados. Leva minutos.

**Por que adiar não acumula juros:** o `probes=10` já elimina a perda medida, e a
migração para HNSW não fica mais cara por esperar. O risco de adiar é só um:
esquecer. Por isso o gatilho está escrito aqui em número, não em intenção.

**Origem:** medição do bloco 2, 03/08 — o defeito apareceu disfarçado de
regressão de corpus.

**114. ✅ FECHADA em 03/08** (`fix/trava-espaco-vetorial` · ADR-040).
**Provider de embedding escolhido por presença de chave era risco vivo.**
`_select_provider()` decidia: se há `OPENAI_API_KEY`, OpenAI; senão, Gemini —
então chave ausente, cota estourada ou deploy sem a variável trocaria o espaço
vetorial da CONSULTA contra um índice do outro provedor. A busca não falharia:
devolveria trechos com similaridade de aparência normal, **todos ruído**. Pior
que o `probes=1` da #113 — lá eram vizinhos subótimos do MESMO espaço.

**Medido antes de concluir:** corpus homogêneo, 31.298 chunks, todos
`text-embedding-3-small` 768d. **A mistura nunca aconteceu** — a trava é
prevenção, não reparo.

**Como ficou:** (a) provider EXPLÍCITO com default do produto, e ausência da
chave configurada vira falha ruidosa em vez de troca; (b) a busca **mira** um
espaço (`embedding_model`) e **recusa** com `EspacoVetorialIncompativel` quando
o corpus está povoado em outro — devolver vazio faria o agente dizer "não
encontrei fundamentação" quando o problema é perguntar no idioma errado;
(c) a escrita declara o espaço (`index_text(embedding_model=...)`), capacidade
para o white-label sem ligar segundo índice; (d) 8 testes, incluindo o controle
de que falta de chave NÃO troca de provider e a distinção entre vazio legítimo e
espaço trocado. **A escolha é por tenant, na implantação — não seletor de
runtime (ADR-040).**

**115. O interpretativo federal é INALCANÇÁVEL por robô — e é onde mora o
ganho.** Das 10 URLs de material interpretativo dos núcleos 02 e 03, **zero**
baixam como texto de norma: `car.gov.br` fecha a conexão TLS (IN MMA 02/2014); o
portal do INCRA devolve HTML numa URL terminada em `.pdf` (IN 77/2013); o Manual
de Georreferenciamento é **página de notícia** e ainda responde 401; a Receita
tem certificado que não valida (IN RFB 2.203/2024); o IBAMA responde 403 (IN
21/2014); três INs do IBAMA linkam **posts de notícia** em vez do ato; e o BCB
devolve *"Essa pagina depende do javascript"* (Res. CMN 5.193/2024).

No núcleo 06 o material apontava para o Planalto, que serve HTML puro. Aqui ele
mora em **portais de agência**. **O que destrava:** a pasta de INs que a Isis vai
enviar — que por isso entra **antes** dos blocos 3–5. **Origem:** sondagem do
bloco 2.

**116. Links do Sisconama por `id=` não são confiáveis — não usar.** Conferidos
três, todos serviram outro ato: `id=594` (pedido CONAMA 411/2009) devolve **Moção
102/2009**; `id=586` (pedido 406/2009) devolve **Resolução 412/2009**; `id=452`
(pedido 369/2006) não contém "369". Já havia registro do mesmo em abril
(`id=745`, `id=489`). A `validation_keyword` pegou os três. A 369/2006 está no
corpus desde abril por um espelho da CETESB, justamente porque o Sisconama
falhou. **O que destrava:** a Isis fornecer identificador estável ou espelho de
órgão. **Origem:** sondagem do bloco 2.

**117. O chunker atribui material não articulado ao último artigo visto.**
*(Título anterior: "O chunker perde a fronteira do artigo em PDF de compêndio" —
trocado em 04/08 porque a causa que ele nomeava foi refutada.)*

> **⛔ CAUSA ORIGINAL REFUTADA em 04/08.** A hipótese registrada era que "o `Art.`
> seguinte frequentemente não começa em início de linha, e a fatia engole o resto
> do documento até o próximo match válido" — e a prescrição era consertar o
> regex. **Medido no caso exato:** a fatia do `Art. 51.` do MT-NUC01 tem
> **1.045.121 chars** e **12.768 linhas**, e contém **1** cabeçalho de artigo em
> início de linha (o próprio, na posição 0). Testadas todas as variantes —
> `Art N` sem ponto, `Artigo N`, `ART. N`, `Art. Nº`: **0 ocorrências**. Em
> qualquer posição da linha: **15 ocorrências, todas citações inline**
> (*"art. 225, caput, da CF/88"*, *"Pelo art. 54 da lei nº 9.605/98"*). `CAPÍTULO`:
> 1. `SEÇÃO`: 0.
>
> **Não há fronteira perdida — não há fronteira.** Nenhum regex melhor corrige,
> porque não existe o que casar. Amostrado, aquele 1 MB é sumário paginado
> (*"Zona 2.1.14. Áreas que Requerem Manejo Específico....187"*), rodapé de
> captura web repetido (*"leisestaduais.com.br/… 77/238"*) e listas de diretrizes
> (*"146. Implementar programas de pesquisa…"*): **anexo de plano territorial**,
> não texto articulado.

**CAUSA REAL.** `_split_by_pattern` assume que o documento é articulado do início
ao fim: tudo entre um cabeçalho e o próximo pertence àquele cabeçalho. **A
premissa é falsa.** Quando o texto deixa de ser articulado, todo o rabo
não-normativo é atribuído ao último cabeçalho visto. É defeito de **modelo**, não
de expressão regular.

O padrão dominante confirma: das 54 fatias absorvedoras do corpus, **31 começam
com o artigo de vigência** (*"Esta Lei entra em vigor na data de sua
publicação"*) — que é sempre uma frase, e é o **último** artigo da norma. No
compêndio, o que vem depois dele é o anexo ou a norma seguinte. Há ainda o
cabeçalho **falso** vindo de referência inline que calhou de abrir linha
(*"Art. 10 desta Resolução (Juntar cópia do arquivo…"*).

**O QUE PERMANECE VÁLIDO — e é a parte grave.** Os 374 pedaços carregam todos o
`section` `"Art. 51. (parte N)"`: sumário de zoneamento **etiquetado como artigo
de lei**. Metadado **ativamente errado**, não apenas ausente. Rótulo mentiroso é
pior que ausência de rótulo — **passa na conferência**, mesma lógica da #121.

**✅ FASE 1 (04/08, `feat/chunking-estrutural`).** Guarda de sanidade: fatia que
realmente começa em cabeçalho de artigo e passa de `LIMITE_ARTIGO_TOKENS`
(8.000) **não é artigo**, não herda o rótulo, cai em janela deslizante sob
`"[trecho nao articulado]"` e **loga** — estratégia declarada, nunca silêncio.
Limiar justificado por medição (p50=129, p90=499, p95=737, p99=2.144,
p99,9=23.483, max=261.280 sobre 24.577 fatias; maior artigo confirmadamente
genuíno ~6.289 tokens). Medido antes/depois: **30.104 chunks antes e depois**
(nada se perde), **−3.380 rótulos de artigo falsos**, **+3.380 rótulos honestos**,
**371 artigos grandes legítimos intocados**. Sem reindexação — vale na próxima
passada de índice.

*Registro histórico da entrada original:* O corte
estrutural usa `^\s*Art\.\s*\d+` em MULTILINE. Em PDF de compêndio o "Art."
seguinte frequentemente **não começa em início de linha**, e a fatia engole o
resto do documento até o próximo match válido. Medido: `Art. 51.` do MT-NUC01
virou **374 pedaços somando 298.580 tokens** — não é artigo grande, é o documento
inteiro sob um rótulo só.

**A consequência é pior que o corte:** os 374 pedaços carregam todos o `section`
`"Art. 51. (parte N)"`. Um trecho de outra norma está **etiquetado como Art. 51**
— metadado ativamente errado, não apenas ausente. E é esse campo que a #107
propõe usar como âncora.

Números: **5.442 chunks (17,4%)** têm marca `(parte N)`, dos quais **5.117 são
estaduais**. No federal, de HTML limpo, o quadro é sadio: mediana 138 tokens,
p95 800, máximo 1.498.

**Atenção ao medir:** os 17,4% misturam artigo genuinamente grande cortado por
tamanho (legítimo — `Art. 61-A` do Código Florestal, 4.644 tokens) com fronteira
perdida engolindo o documento (defeito). **Separar os dois antes de qualquer
experimento de chunking**; medir sobre a mistura mediria o defeito, não a
estratégia. **Origem:** levantamento de 03/08.

> **✅ FASE 2 (04/08, `feat/chunking-estrutural` · ADR-041).** Teto próprio para
> artigo: `MAX_ARTIGO_TOKENS = 7000`, cobrindo inteiros os três medidos (4.644 /
> 5.578 / 6.289). Vale **só para artigo** — capítulo, seção e prelúdio seguem em
> `MAX_TOKENS`, porque para eles 7.000 tokens num chunk é diluição, não
> dispositivo inteiro. Corte por tamanho continua como último recurso e passou a
> **logar**. Medido: chunks de artigo partidos por tamanho **4.935 → 67**;
> mediana **172 → 163**; p90/p95 **inalterados em 800**; máximo 1.498 → 6.963.
> Base declarada nos artefatos (`legislation_documents`, 30.104 — não os 31.298
> do catálogo inteiro). Sem reindexação.
>
> **⚠️ RESULTADO DA FASE 4 (05/08): o ganho de recuperação NÃO existe — houve
> PERDA.** Medido depois da reindexação única, no caso escolhido para provar a
> tese: o **art. 61-A** passou de `partido_em 7` para `0` (entrou inteiro, como a
> dívida pedia) e **caiu da posição 2 para a 29**, similaridade **0,7764 →
> 0,6601**. O fragmento focado casava melhor com a pergunta que o artigo
> completo — o mecanismo de diluição que a ADR-041 descreve, agora medido contra
> nós.
>
> Escala: **490 chunks** são artigos inteiros acima de 1.500 tokens, **1,60% do
> corpus** (p50 2.304, p90 4.302). É cauda; mas o 61-A (2.837 e 2.641 tokens)
> está no miolo dela — a regressão é típica da faixa, não um extremo.
>
> **A dívida permanece justificada por OUTRO motivo, declarado:** o consultor
> recebia o dispositivo em cacos — o 61-A chegava em quatro pedaços no top-8 — e
> peça se escreve sobre artigo inteiro. **Benefício de ENTREGA, com custo medido
> de RECUPERAÇÃO.** Nada foi revertido; a requalificação do teto é decisão
> separada, fora da fase que produziu o número.
>
> **Efeito colateral medido:** dos 362 chunks de artigo acima de 1.500 tokens,
> **81 são absorvedores de vigência abaixo do limiar de 8.000** — viraram blobs
> únicos. Menos rótulo falso, mais diluição. O sinal que os pega é semântico (o
> artigo de vigência tem p50=273, p75=519 tokens), não de tamanho; pertence à
> #126.

**118. `MAX_TOKENS=1500` é escolha nossa, não limite do modelo.** O
`text-embedding-3-small` aceita **8.191 tokens**; nosso teto é 1.500. Os artigos
que se partem por tamanho no federal caberiam folgados: `Art. 19` da Lei 6.938
(6.289), `Art. 100` da Constituição (5.578), `Art. 61-A` do Código Florestal
(4.644). **Consequência para o experimento de embedding:** "janela maior do
provedor X" resolveria gargalo que não temos — nem a janela atual está sendo
usada. **Origem:** levantamento de 03/08.

> **✅ FASE 3 (04/08, `feat/chunking-estrutural` · ADR-041 · migration
> `b7e3f1a90c24`).** Medido sobre os 102 documentos, 28.971 chunks:
>
> | | antes | depois |
> |---|---:|---:|
> | com hierarquia | 12 de 3.192 federais | **26.938 (93,0%)** |
> | com dispositivo em campo próprio | 0 | **24.584 (84,9%)** |
> | referências como dado | 0 | **2.235** |
>
> `dispositivo_origem` distingue **lido** (24.523) de **herdado** (61) — campo
> preenchido por herança tem de ser distinguível de campo lido do texto, ou
> repetimos a #121/#123. Das 2.235 referências, **547 têm norma-alvo declarada**
> e **1.688 não** — e as não declaradas ficam gravadas assim, nunca supondo "é a
> norma atual" nem descartadas em silêncio. Alvo só é aceito quando a norma
> **segue o artigo diretamente**: sem essa âncora, *"art. 8 aplica-se conforme
> resolução CONAMA 369"* ligava o art. 8 a uma resolução que é outra referência.
>
> **Escopo declarado:** o gatilho são as três fórmulas que esta dívida mediu.
> Menção solta (*"o prazo do art. 225"*) não entra — o campo `referencias` **não
> é exaustivo**, e há teste dizendo isso. Alargar o gatilho traria falso positivo
> junto.
>
> **Extração sim, navegação não:** nada resolve, segue ou expande referência.
> Colunas nascem NULL; preenchem na reindexação única da Fase 4.

**119. A estrutura determinística da norma é jogada fora.** Três coisas que o
texto entrega de graça e o corpus não guarda: **(a) hierarquia** — o chunker usa
o padrão mais granular que corta e, ao cortar por artigo, descarta capítulo e
título; medido, só **12 chunks de 3.192 federais** têm rótulo hierárquico;
**(b) referências cruzadas explícitas** — 329 chunks federais com *"na forma do
art."* (27), *"nos termos do art."* (64), *"previsto/disposto no art."* (238),
arestas de grafo viradas texto corrido; **(c) identidade do dispositivo** — 93,1%
dos chunks federais mencionam um artigo, e o número não está em campo
consultável. **É dado, não inferência** — e pode ser solução mais elegante que
trocar de provedor. Parente da #107. **Origem:** levantamento de 03/08.

**120. 245 chunks sem `identifier` — trecho que não sabe dizer de que norma
veio.** Todos estaduais de GO, espalhados por **51 documentos** distintos. Um
chunk sem identidade pode ser recuperado e usado na fundamentação, mas não pode
ser **citado nem conferido** — o consultor recebe o conteúdo sem a fonte. Fere o
Princípio 11 ("nenhuma afirmação sem fonte") no ponto exato em que ele foi
escrito para valer. Também é invisível para a família de métricas que recorta por
`identifier` (o guard da identidade da norma, o alvo do medidor, a cobertura
nominal): elas não erram nesses chunks, elas **não os enxergam**. **Origem:**
levantamento do baseline do chunking, 04/08.

**121. O mesmo texto normativo gravado sob identidades diferentes.**
**⚠️ O achado mais grave do levantamento de 04/08 — acima do chunking.**

Chunking ruim devolve trecho ruim, e trecho ruim se **vê**. Atribuição errada
devolve o trecho **certo** com a fonte **errada**, e isso não se vê: a peça sai
coerente, bem fundamentada, citando a portaria no lugar da lei. É o Princípio 11
("nenhuma afirmação sem fonte") ferido na raiz — a afirmação *tem* fonte, e a
fonte está errada, que é pior que não ter, porque passa na conferência.

**Impacto:** risco de citação com fonte errada em **peça assinada**.

Medido:
**4.821 grupos** de chunks com texto idêntico (normalizando caixa e pontuação)
distribuídos entre identificadores **diferentes**, somando **9.890 chunks
redundantes** — e não é só cabeçalho: **2.013 grupos têm ≥200 tokens**. Exemplo
conferido: um trecho de 524 tokens sobre termo de compromisso ambiental aparece
igual em `IN SEMAD-GO 01/2024`, `Lei GO 18.102/2013` e `Portaria SEMAD-GO
501/2024`.

**Exemplar colado** (trecho de 524 tokens, termo de compromisso ambiental,
idêntico nos três):

```
identifier                  | tokens | início
IN SEMAD-GO 01/2024         |    524 | a Lei nº 20.961, de 13-01-2021. § 5º O termo de
Lei GO 18.102/2013          |    524 | compromisso ambiental poderá conter cláusulas
Portaria SEMAD-GO 501/2024  |    524 | relativas às demais sanções aplica...
```

**HIPÓTESE DE CAUSA — não confirmada.** Coletâneas e portarias que transcrevem
outras normas seriam ingeridas com o `identifier` **delas**, e o texto
reproduzido herdaria essa identidade. É a explicação que o formato dos casos
sugere; **precisa ser confirmada ou refutada com evidência antes de virar
premissa de conserto**. Investigar depois do baseline.

O dedup atual não pega: `content_hash` tem **zero** colisões no corpus, porque as
cópias diferem em ligaduras tipográficas (#122), espaçamento e pontuação. Hash
exato sobre texto de PDF é dedup que **parece** funcionar. Parente da #107 e da
#119. **Origem:** levantamento do baseline do chunking, 04/08.

**122. Ligaduras tipográficas atrapalham comparação literal e busca por termo.**
*(Título anterior: "…não normalizadas na extração de texto" — reescrito em 05/08
junto com a causa, que foi refutada por medição.)*

> **⛔ CAUSA ORIGINAL REFUTADA em 05/08 — e o defeito é do tipo que esta própria
> dívida descreve.** Estava escrito aqui que a ligadura **"já mascarou uma
> duplicação inteira"**: que o `content_hash` reportava zero colisões enquanto
> 9.890 chunks estavam duplicados porque `ﬁns` ≠ `fins`.
>
> **Isso era INFERÊNCIA APRESENTADA COMO MEDIÇÃO.** Nunca foi medido; foi
> deduzido de dois fatos verdadeiros (há ligaduras; o `content_hash` não
> colidia) e escrito com a autoridade de um número. Medido agora:
>
> | grupos de texto idêntico entre normas diferentes | |
> |---|---:|
> | antes da normalização | **4.530** |
> | depois da normalização | 4.529 |
>
> **Não emergiu nada — caiu 1.** As duplicatas já eram byte-idênticas.
>
> **Causa real da invisibilidade:** `_hash_chunk` inclui `source_ref`. Dois
> documentos diferentes **nunca colidem**, com ou sem ligadura. A duplicação é
> invisível ao `content_hash` **por desenho do hash**, não por Unicode.
>
> Cruzar com **#123** ("artefato registra o que ACONTECEU, nunca o que foi
> solicitado"): o mesmo erro, cometido **dentro do documento que o descreve**. É
> a lição mais transferível do dia — a regra não protege quem a escreveu.

**ESCOPO REMANESCENTE — defeito real, menor e de outra natureza.** **19 de 102
documentos**, **8.974 ocorrências**, **2.507 chunks** (8,7%) de `ﬁ`, `ﬂ` e parentes
(U+FB00…U+FB06). Vem do PDF: a fonte usa o glifo composto e o extrator o copia.
Atrapalha **comparação literal e busca por termo** — quem procura `fins` não
acha o que está gravado como `ﬁns`, nem no nosso match de citação nem no Ctrl+F
de quem lê. **Não** atrapalha dedupe, pelo motivo acima.

**O conserto é normalização na ENTRADA, e é CIRÚRGICA — só ligaduras.** NFKC foi
a primeira escolha e **medir antes de escrever no corpus a derrubou**: ele trata
`º` (U+00BA) como equivalente de compatibilidade de `o` e converte —
`"Lei nº 12.651"` → `"Lei no 12.651"`, `"art. 5º, §1º"` → `"art. 5o, §1o"`.
Mudaria **18.362 chunks (63%)**, quase todos por causa do `º`, e **quebraria toda
busca por dispositivo**: a normalização feita para consertar comparação
destruiria a comparação que sustenta o produto. A troca preserva `º`, `ª` e `§`.

**Garantia estrutural que apareceu na conferência:** como o `content_hash` inclui
`source_ref`, a reindexação **não deduplica por acidente**. A instrução de não
deduplicar está garantida pela **estrutura do hash**, não pela disciplina de quem
executa — e garantia estrutural vale mais que instrução.

**Origem:** levantamento do baseline do chunking, 04/08; causa corrigida na Fase
4, 05/08.

**123. REGRA: silêncio não é evidência de ausência.** Nenhum instrumento de
medição ou vigilância pode descartar `stderr` (`2>/dev/null`) nem tratar
resultado vazio como "o estado ainda não foi atingido". **Vazio e erro são
estados distintos de "não bateu"** e precisam ser distinguíveis no log. Todo
vigia/poller precisa de **prova de vida**: falhar alto na primeira consulta que
não devolve linha bem-formada, em vez de seguir em loop parecendo paciente.

**Autópsia (exemplar, 04/08).** O vigia que esperava o corpus chegar a
31.298/102 foi escrito assim:

```bash
until [ "$(docker exec ... psql -tAc 'select (select count(*) ...) || "/" || ...' 2>/dev/null)" = "31298/102" ]
```

Três defeitos compostos: em SQL, `"/"` é **identificador**, não literal — o banco
respondia `ERROR: column "/" does not exist`; o `2>/dev/null` engolia o erro; e a
comparação passava a testar string **vazia** contra `31298/102`. O vigia **nunca
poderia disparar, em nenhum estado do banco**. Pior: o silêncio dele era
indistinguível de "ainda não chegou", e o revert do corpus já tinha entrado havia
tempo enquanto o loop parecia estar trabalhando.

**REGRA DERIVADA — artefato de medição registra o que ACONTECEU, nunca o que foi
solicitado.** Sempre que "pedido ≠ realizado" for possível — fallback de
provider, retry, degradação, cache — o artefato grava **os dois lados e o
booleano de igualdade**.

**Segundo exemplar (mesmo dia, mesma família).** A primeira rodada completa deste
baseline gravou `modelo: gemini/gemini-2.5-flash` nos cinco json. Em uma delas
(`defesa`) houve **2 timeouts** nesse modelo e o gateway acionou o **fallback** —
outro modelo respondeu. O medidor gravava `settings.GEMINI_LEGAL_MODEL`, colhido
**antes** da chamada: o modelo *pedido*. O json afirmava um modelo que não rodou.

Isso quebraria em silêncio a condição que sustenta o experimento desde o pacote A
("mesma pergunta, mesmo modelo"). O que denunciou não foi o campo — foi o perfil
dos números: 1.602 tokens de saída e US$ 0,0054 contra 4.808–6.466 e
US$ 0,0129–0,0164 das outras quatro.

**O padrão do dia:** `model_used` existia e ninguém lia; `embedding_model`
existia desde a Sprint U e ninguém lia. **Nossos defeitos não são de dado
ausente — são de dado presente e não consultado.**

`AIResponse` **já expunha** `model_used`; faltava alguém lê-lo — igual à
`embedding_model` da #114. O medidor passou a gravar `modelo_efetivo`,
`modelo_efetivo_igual_ao_pedido`, `provider_efetivo`, `duracao_ms` e
`finish_reason`. Como `AIResponse` **não** expõe nº de tentativas nem motivo do
fallback, esse sinal é capturado de quem o tem — os próprios avisos do gateway —
e gravado em `gateway.tentativas_transitorias` / `gateway.fallbacks_acionados`:
timeout recorrente num modelo é sinal operacional e não pode morrer no terminal.

**TERCEIRO EXEMPLAR — o instrumento de aceite tinha o defeito que a fase
combatia (05/08).** A métrica que julgaria o sucesso da remediação dizia que o
art. 61-A continuava `recuperado` depois da reindexação. **Estava errada.**

Ela procurava o texto `"art. 61-A"` **no corpo do chunk** — e os chunks do art.
61-**B** *mencionam* o 61-A. A métrica capturava **menção**, não **identidade**,
e por isso deu positivo para um artigo que havia **saído do top-8**.

É literalmente a #121 (o mesmo texto sob identidade errada) cometida pelo
medidor. Toda a Fase 3 existiu para separar identidade de menção — e o
instrumento de aceite continuava misturando as duas.

Corrigido usando o campo `dispositivo`, que a Fase 3 criou exatamente para isso.
Com a identidade correta, o número real apareceu: **posição 2 → 29, similaridade
0,7764 → 0,6601**. Sem a correção, a fase teria sido reportada como sucesso.

**Família.** Mesmo mecanismo da #117 (fronteira perdida em silêncio), do
`probes=1` (#113), do fallback de provider por presença de chave (#114) e do
`content_hash` mascarado por ligadura (#121/#122). **O sistema não falha:
responde errado, calado.** A defesa é sempre a mesma — conferir por um segundo
caminho e fazer o instrumento **recusar** em vez de responder quando não pode
responder direito. **Origem:** autópsia do vigia do baseline, 04/08.

**124. Tentativas e motivo do fallback só existem como texto de log.**
`AIResponse` expõe `content`, `model_used`, `provider`, `tokens_in/out`,
`cost_usd`, `duration_ms` e `finish_reason` — **não** expõe quantas tentativas
houve nem por que o fallback foi acionado. Esse dado existe apenas na frase do
aviso que o gateway escreve no log.

**Raspar log é frágil pelo motivo da #123:** mudou a frase do aviso, o consumidor
**cala** — não quebra, não avisa, apenas passa a contar zero. Silêncio outra vez,
mesma família.

**Telemetria de fallback não é instrumento de laboratório.** Timeout recorrente
num provider é **sinal operacional** e deveria ser visível em produção, não só
num baseline. Hoje, um provider degradando sustentadamente aparece como latência
e custo estranhos, sem nome.

**O que fazer:** promover `tentativas` e `motivo_do_fallback` a campos
estruturados de `AIResponse` em `app/core/ai_gateway.py`, e expor a contagem como
métrica. **Fora do escopo do PR do chunking** (é código de produção): registrado,
não executado. O baseline usa um handler no logger — solução certa para capturar
sem tocar em produção, e que esta dívida torna desnecessária quando for feita.
**Evidência operacional já colhida.** Com a captura ligada, o baseline mediu:
`gemini-2.5-flash` deu **2 timeouts e caiu para `gpt-4.1-mini`** na pergunta
`defesa` — **nas duas rodadas seguidas**, não por acaso. É justamente a pergunta
de **maior contexto**. Ou seja: o provider degrada de forma reprodutível na maior
entrada, e hoje isso só aparece se alguém estiver lendo o terminal na hora.
**Origem:** re-run do baseline do chunking, 04/08 (#123).

**125. `gemini-2.5-flash` degrada de forma reprodutível na maior entrada.**
Medido no baseline do chunking: na pergunta `defesa` — a de **maior contexto** —
o modelo deu **2 timeouts** e o gateway caiu para `gpt-4.1-mini`. **Nas duas
rodadas**, não uma vez. As outras quatro perguntas, de contexto menor, passaram
(duas com 1 tentativa transitória, duas limpas).

Não é ruído de laboratório: é **sinal operacional de produção**. O agente de
legislação usa esse modelo e monta contexto RAG do mesmo tamanho — em produção
isso aparece como latência alta, custo estranho e resposta de outro modelo, sem
nome e sem alarme. Ninguém está olhando o terminal lá.

Relação com a #124: enquanto tentativas e motivo do fallback não forem campos
estruturados, essa degradação não é observável fora de uma medição manual.

**Decisão: não mexer no timeout do gateway agora** (código de produção, fora do
PR do chunking). Registrado, não executado. **Origem:** baseline do chunking,
04/08.

**126. O corpus contém documentos NÃO ARTICULADOS tratados como norma
articulada.** Plano de manejo, plano territorial, anexo, formulário, coletânea,
manual, parecer doutrinário e captura de página web entram pelo **mesmo caminho**
de uma lei. O chunker então procura `Art. N` num texto que não tem artigos — e o
que ele encontra são citações inline e cabeçalhos falsos.

Exemplos medidos em 04/08: `MT-NUC01` (1 MB de sumário paginado + rodapé de
captura + listas de diretrizes), `Plano de Manejo EE Pouso Alto` (228.152 tokens
de prelúdio começando em *"GOIÂNIA, QUINTA-FEIRA, 23 DE JUNHO DE 2016 — DIÁRIO
OFICIAL"*), `Manual SFB SICAR 2023`, `OJN 06/2009 PFE-IBAMA` (prosa numerada por
parágrafo: *"102. José dos Santos Carvalho Filho apresenta…"*).

**É questão de CLASSIFICAÇÃO na entrada, anterior ao chunking.** Um documento
não articulado não deveria sequer tentar o corte por artigo; deveria declarar o
que é e receber a estratégia adequada. A guarda da #117 trata o **sintoma** com
honestidade — impede a etiqueta falsa — mas não decide o que o documento é.

**Provável parentesco com a #121:** a coletânea que empresta a própria identidade
ao texto que transcreve é a mesma família — documento cuja natureza (compilação,
plano, manual) não é declarada e por isso é tratada como se fosse a norma.

**HIPÓTESE REFORÇADA pela Fase 4 (05/08) — registrada, sem abrir frente.** Na
pergunta da `defesa`, o art. 18 do Decreto 6.514 continuou fora do top-8 mesmo
depois de toda a remediação. A causa ficou **visível**: a **OJN 06/2009
PFE-IBAMA** — um parecer doutrinário — ocupa **6 das 8 vagas**. O problema ali
nunca foi chunking.

Isso sugere que o corpus precisa distinguir **NORMA de INTERPRETAÇÃO na
RECUPERAÇÃO**, não só no rótulo: material interpretativo é semanticamente mais
próximo de uma pergunta em linguagem natural do que o texto seco do dispositivo,
e por isso ganha a disputa por similaridade — justamente quando o consultor
precisa da norma. **Hipótese, não conclusão.**

Registrado, **não resolvido agora**. **Origem:** Fase 1 da remediação do
chunking, 04/08.

**127. Metadado do chunk de legislação é preenchido em dois lugares.**
`index_legislation_document()` e `scripts/reindexar_chunking.py:_inserir_preparado()`
montam **o mesmo** conjunto de metadados — `source_ref`, título, `tenant_id`,
`scope`, `uf`, `agency`, `identifier`, `effective_date` e o `extra_metadata` com
`demand_types`, `keywords`, `vigencia_inicio/fim`, `sucessora_ref` e `historica`.

A duplicação foi **necessária** em 05/08: a rota original embarca e insere na
mesma chamada, e a reindexação da Fase 4 precisou separar as duas coisas
(embedding fora de transação, escrita dentro). Não havia como reusar sem
reescrever a original no meio de uma passada de escrita.

**Mas duplicação diverge com o tempo, e o candidato óbvio já está apontado:** o
rótulo de vigência do ADR-037 (`titulo_com_vigencia`) é exatamente o detalhe que
alguém atualiza num lugar só. Ele viaja **no dado** justamente para não depender
de ninguém lembrar — e passaria a depender de alguém lembrar de dois lugares.

**Conserto:** extrair o preenchimento de metadado para uma função única,
consumida pelas duas rotas. **Não fazer agora.** **Origem:** Fase 4 da
remediação do chunking, 05/08.

**PRÓXIMO LIVRE: 128.**

---

## Faixa 300-399 — infraestrutura do repositório

> Faixa própria pelo mesmo motivo das outras: dois agentes lendo "próximo livre"
> ao mesmo tempo colidem. **Próximo livre nesta faixa: 304.**

**303. Troca de provider não dispara auditoria de premissas.** Trocar o provider
de embedding altera **tokenização, limites duros, dimensionalidade e custo** — e
**nada no processo obriga a reconferir o que dependia do provider anterior**.

Não é descuido individual. É **ausência de gatilho**: cada uma das premissas
abaixo foi escrita corretamente, com evidência, na época em que valia. Todas
sobreviveram intactas à migração Gemini → OpenAI da Sprint W, e nenhuma foi
reconferida — até serem descobertas por acidente, **três no mesmo dia**.

| premissa | escrita quando | como foi descoberta |
|---|---|---|
| régua de token `len//4`, *"confirmado contra Gemini tokenizer"* | Sprint 0 | reindexação abortou: `maximum input length is 8192 tokens`. Erro real de 1,22× na mediana, **2,44× no máximo** |
| `embedding_model` gravado em toda linha | Sprint U | levantamento da #114 — a coluna existia, **ninguém lia**; a busca não filtrava por espaço vetorial |
| `model_used` exposto no `AIResponse` | — | baseline gravava o modelo **pedido** como se fosse o realizado (#123); o campo com o modelo real já estava ali |

**O padrão comum:** o dado existia e ninguém foi olhar. As três só apareceram
porque algo quebrou alto — a régua porque a API recusou, as outras duas porque
alguém foi medir por outro motivo. Nenhuma teria aparecido sozinha.

**Proposta — registrada, NÃO implementada:**

1. **Checklist obrigatório de troca de provider**, cobrindo no mínimo:
   tokenização e contagem, limites duros de entrada, dimensionalidade do vetor,
   tabela de preço, nomes de modelo persistidos, e **reindexação necessária ou
   não**.
2. **Comentário de calibração no código**: toda constante calibrada contra um
   provider específico declara **qual provider e quando** — como
   `# calibrado contra cl100k_base (OpenAI), 05/08`. Sem isso, a constante
   parece universal e sobrevive à troca sem que ninguém desconfie.

**Origem:** três achados independentes na Fase 4 da remediação do chunking,
05/08. Correlatas: #114, #123, #124, ADR-040, ADR-041 (adendo).

**302. 🔴 ABERTA — dev com grafo de alembic inconsistente (duas frentes
paralelas).** O `alembic_version` do `amigao_db` está em **`b4e1d70c9a35`**,
revisão que vive na branch **`feat/audio-conversao-e-diarizacao`** (commit
`ce4f1a8`) e **não está na main**. Qualquer branch que não a contenha não
consegue nem resolver o `current`:

```
ERROR  Can't locate revision identified by 'b4e1d70c9a35'
FAILED: Can't locate revision identified by 'b4e1d70c9a35'
```

Consequência concreta: a migration `b7e3f1a90c24` (#119, estrutura da norma como
dado) **não pôde ser aplicada por alembic**, e a reindexação da Fase 4 falhou com
`UndefinedColumn: column "dispositivo" does not exist`.

**Contorno aplicado em 05/08 (opção C):** o DDL de `b7e3f1a90c24` foi executado
**à mão** no dev, numa transação única, com `alembic_version` **intocado**.
Conferido coluna a coluna contra a migration — tipos, nullability e os dois
índices batem; as quatro colunas nasceram NULL em 31.298 linhas.

**Descartado: `alembic stamp`.** Apontar o banco para o head que a nossa branch
conhece **mentiria sobre o estado do banco** — as tabelas da outra frente
continuariam existindo com o alembic declarando que não foram aplicadas. É a
família #123 (registrar o pretendido como se fosse o realizado), e o preço se
paga meses depois, quando alguém confia no `alembic_version`.

**O conserto real é o merge da branch de áudio.** Enquanto ele não acontece, dev
e prod divergem no registro de migrations — não no schema, que está conferido.
**Esta dívida NÃO fecha com o contorno; fecha quando a branch entrar na main e o
`upgrade head` rodar limpo.**

**Origem:** Fase 4 da remediação do chunking, 05/08.

**301. 110 MB de blobs mortos no histórico do git — ~80% do `.git`.** O
repositório tem **137 MB** em `.git`, dos quais **110 MB são 8 blobs acima de
1 MB** que ninguém usa:

| arquivo | tamanho | entrou | saiu |
|---|---:|---|---|
| `frontend.zip` | **43,4 MB** | `1bbac39` *"atualização do sistema"* | `66b6b9b` |
| 7 PDFs `docs/base_regulatoria/SEMAD/Manuais/` | **66,6 MB** | `ed1801f` | `6d7eab9` |

**Não é hipótese de dano — já cobrou.** O commit `6d7eab9` diz o que aconteceu:
*"remove corpus SEMAD do git — quebrava clone do Render no Linux"*. O deploy
falhava no `git clone`, antes do build.

**NOTA OBRIGATÓRIA: remover do working tree NÃO remove do histórico.** Os dois
arquivos já não existem no working tree e os 110 MB continuam lá — todo clone
ainda os baixa. A limpeza exige **reescrita de histórico** (`git filter-repo` ou
equivalente), que é **janela própria, com o repo parado e coordenada com quem
tiver clone**: reescrever troca os hashes de todos os commits, e quem tiver
branch local fica órfão. **Decisão do André, não se faz no meio de uma fase.**

**Prevenção já feita** (commit `66bddb7`, não é reescrita): `*.dump`, `*.sql.gz`
e `*.zip` no `.gitignore`. A lacuna quase pegou de novo — o backup de 109 MB da
Fase 4 apareceria como untracked porque `*.dump` não estava listado.

**Origem:** levantamento pedido na Fase 4 da remediação do chunking, 05/08.

---

## Faixa 200-299 — transcrição de áudio (`feat/transcricao-audio`, 03/08)

> **Convenção nova de numeração.** Esta frente numera dívidas na faixa
> **200-299** e ADRs a partir de **060**. Motivo: dois agentes escrevendo no mesmo
> `REGISTRO_DIVIDAS.md` leem o "próximo número livre" ao mesmo tempo, e "próximo
> livre" resolve conflito **sequencial**, não **simultâneo** — colidimos duas
> vezes em dois dias (ver a nota de renumeração no topo da ADR-039). Faixa por
> frente resolve sem coordenação. **Próximo livre nesta faixa: 207.**

> **✅ FECHADAS na 2ª rodada (03/08, `feat/audio-conversao-e-diarizacao`):**
> **#200** (todo `ignorados` diz o motivo; `modulos_fiscais` ganhou destino) e
> **#201** (o sistema converte o áudio sozinho; a consultora nunca ouve falar de
> bitrate). **#205** foi absorvida pela **#206**, que é o problema real por trás
> dela. **#203 segue desligada — agora por decisão técnica medida, não por falta
> de resposta da Isis** (ver a entrada revista abaixo).

> **✅ FECHAMENTO DA #103 (03/08, `feat/transcricao-audio` · ADR-060).** O sistema
> passou a ouvir. Áudio virou "documento cuja leitura é a transcrição": Whisper
> via `ai_gateway.transcribe()` (LiteLLM, modelo por env, BYOK respeitado), texto
> em `Document.extracted_text` — e daí herdando de graça a entrada no diagnóstico,
> a fonte clicável, a busca, o cache SHA-256, o budget guard e o `AIJob`. Estado
> visível na tela nos três valores: transcrevendo / pronta (com o texto a um
> clique) / falhou **com o motivo escrito**, mais botão de tentar de novo. Ao
> medir apareceu um terceiro furo além dos dois previstos na dívida: a porta de
> upload do caso recusava `.m4a`/`.mp3` com **400** porque `ALLOWED_EXTENSIONS`
> nunca ganhou as extensões de áudio — o seletor "🎙️ Áudio de reunião/ligação"
> estava na tela e não funcionava. Corrigido junto.

> **✅ FECHAMENTO DA #104 (03/08).** A leitura em produção foi executada nesta
> sessão (Management API do Supabase, `SELECT` no `audit_logs` do processo 16). A
> hipótese atacada pela #91 se **confirmou**, e havia uma segunda causa junto —
> ver #200. Detalhe da medição: no lote de 02/08 15:19 a consolidação gravou
> **zero** campos; 3 voltaram como divergência devolvida e 3 saíram em
> `ignorados`. Nenhum `consolidar_falhou` em todo o histórico do caso — o
> caminho do 500 não era o vetor.

**200. ✅ FECHADA em 03/08** (`feat/audio-conversao-e-diarizacao`). Todo
`ignorados` passou a carregar motivo, vindo de uma **fonte única**
(`motivo_sem_destino`) que o selo durável e o pós-consolidação agora compartilham
— antes o selo explicava e o `ignorados` não, e a mesma pergunta tinha duas
respostas de qualidade diferente. A função distingue quatro situações que pediam
ações opostas e recebiam a mesma string: **recusa declarada** (decisão, com o
porquê), **sem coluna na base** (campo a pedir), **coluna existe mas a
consolidação não grava** (mapeamento a ajustar) e **sem campo de destino**.
Decisão sobre os três campos órfãos do caso 16: `modulos_fiscais` ganhou
**destino** (coluna em `properties`, allowlist, Hub e selo — é atributo do
imóvel, decide porte e portanto exceção do Código Florestal); `rat_protocolo` e
`rat_data_emissao` ganharam **recusa declarada** — metadado que identifica o
DOCUMENTO, não o imóvel, e dois RATs de datas diferentes são dois documentos.
Também saiu do vocabulário da tela o "valor incoercível/implausível", que não é
português de consultora. Texto original abaixo. — **`ignorados` mostra o campo
descartado, mas não o motivo.** Medido no
processo 16 em produção (a leitura que fechou a #104). Os três campos que saíram
em `ignorados` — `imovel.rat_protocolo`, `imovel.modulos_fiscais`,
`imovel.regulatory_issues` — caem em `staging_consolidation.py:718`, o **único**
`ignorados.append` que grava só o identificador, sem sufixo de motivo (os outros
quatro explicam: "sem coluna na base", "valor incoercível", etc.). A tela mostra
`imovel.rat_protocolo` e o consultor não tem como saber que aquilo significa
*"este campo não tem destino na base"*. Pior: `rat_protocolo`, `rat_data_emissao`
e `modulos_fiscais` são campos que a extração produz de verdade e a base não tem
onde guardar. **O que destrava:** (a) sufixo de motivo nessa linha, como as
outras quatro já têm; (b) decidir se esses campos ganham coluna ou se a extração
deve parar de emiti-los. **Origem:** leitura de produção de 03/08 (#104).

**201. ✅ FECHADA em 03/08** (`feat/audio-conversao-e-diarizacao`) — **na
conversão, não na segmentação**. `ffmpeg` entrou na imagem e o sistema comprime
sozinho (mp3 mono 64 kbps / 16 kHz, que é o patamar em que o próprio Whisper
reamostra internamente — a perda é nenhuma na prática). A consultora **nunca ouve
falar de bitrate**: só é avisada se, mesmo comprimida, a gravação não couber, e aí
a instrução é em **horas** ("divida em partes de até uma hora"), unidade que ela
tem como avaliar. Ganho colateral: formatos que o provedor recusava (`.amr` de
gravador antigo, `.wma`) passam a ser convertidos e transcritos — recusa virou
entrega. **Segmentação em pedaços de 25 MB NÃO foi implementada**, por decisão:
é específica do Whisper e viraria trabalho jogado fora se a medição do #206
apontar outro provedor. Texto original abaixo. — **Áudio acima de 25 MB não é
transcrito.** O provedor recusa arquivos
maiores; uma reunião de 30 min em WAV, ou em MP3 de bitrate alto, passa disso. A
task falha com motivo acionável ("divida a gravação ou reenvie em mono, 64 kbps")
em vez de silêncio — mas o consultor não deveria precisar saber o que é bitrate.
**O que destrava:** segmentar o áudio no worker (ffmpeg/pydub) e concatenar as
transcrições, mesmo padrão da rasterização por página no OCR multipágina. Custa
adicionar `ffmpeg` à imagem Docker (Dockerfile + build do Render), que é mudança
de infra e ficou fora desta frente. **Origem:** ADR-060.

**202. Consultor BYOK sem chave OpenAI fica sem transcrição.** Dos quatro
providers suportados, só a OpenAI expõe endpoint de transcrição. Quem configurou
só Gemini/Anthropic/DeepSeek em Configurações > IA recebe erro explícito
("Transcrição de áudio exige chave OpenAI") — honesto, e ainda assim uma função a
menos para ele. **O que destrava:** rota alternativa via Gemini, que aceita áudio
como entrada multimodal em `generateContent` e cobra por tokens de áudio (~32
tokens/segundo) em vez de por minuto. Exige segunda implementação no gateway, com
contrato de custo diferente. **Origem:** ADR-060.

**203. Resumo estruturado BLOQUEADO por decisão técnica — não por falta de
resposta da Isis.** *(Revisto em 03/08 com evidência medida. A entrada anterior
tratava isto como pendência de produto; é impedimento técnico.)*

O resumo promete responder **"o que o CLIENTE prometeu enviar"**. Medição de
03/08, com duas vozes distintas passadas pelo caminho de produção: o `whisper-1`
**não faz diarização**. Os `segments` do `verbose_json` trazem
`id/start/end/text/tokens/avg_logprob/compression_ratio/no_speech_prob/temperature`
e **não trazem `speaker`**. A saída é bloco corrido, sem quebra na troca de turno:

> "…e protocolar a defesa administrativa até o dia 15. **Certo. E eu te mando o
> recibo do CAR** e a matrícula do lote 1B até sexta-feira."

Ali, no meio da linha, a voz muda — e nada no texto diz isso. A primeira promessa
é da consultora, a segunda é do cliente. **Num bloco sem atribuição, "o que o
cliente prometeu" é inderivável**, e o LLM vai preencher com o palpite mais
plausível.

**Por que resumo com dono errado é PIOR que resumo nenhum:** a promessa vira
compromisso no caso. Atribuída ao consultor, nasce **Ação interna**; atribuída ao
cliente, nasce **pendência dele**, com cobrança e prazo. Trocar os dois cria
tarefa para quem não assumiu e some com a cobrança de quem assumiu — e, diferente
do silêncio de hoje, isso **parece informação**, então ninguém confere.

**Cuidado ao ler a medição:** os cortes de segmento caíram perto das trocas de
turno, mas só porque o áudio de teste foi montado concatenando clipes de voz
única com corte seco. Em reunião real (sobreposição, sem pausa) o corte é
prosódico. **Segmento não é proxy de falante** — não construir em cima disso.

**O que destrava:** a #206. Enquanto ela não fechar,
`AUDIO_TRANSCRICAO_RESUMO_ENABLED` fica `false`, e a resposta da Isis sobre o
formato do resumo (decisão 3a) não é o que falta. **Origem:** ADR-060; medição de
03/08.

**204. Visibilidade "material interno" só afeta o portal do cliente.** Decisão 3b
implementada no default conservador: `Document.is_internal` esconde o documento da
listagem do portal, e nada mais. O portal está congelado (ADR-009), então na
prática a marcação hoje é sobretudo um **rótulo** para o consultor. **O que
destrava:** definir com a Isis se "interno" deve também sair do dossiê gerado e
das peças entregues ao cliente — e, se sim, aplicar em `dossier.py` e nos
geradores de proposta/contrato. **Origem:** ADR-060.

**205. Transcrição não é cronometrada por falante nem por trecho.** *(Absorvida
pela #206 em 03/08 — o timestamp sozinho não resolve o problema real, que é
atribuição. Fica registrada porque a parte de "achar onde foi dito" continua
valendo mesmo que a atribuição venha de outro caminho.)* O texto sai corrido, sem
marcas de tempo e sem separação de quem falou. Para achar "onde ele disse isso"
numa reunião de 30 min, o consultor lê tudo. O Whisper devolve `segments` com
timestamps no `verbose_json` — hoje descartados. **O que destrava:** persistir os
segmentos e usá-los para ancorar a citação do diagnóstico num minuto do áudio,
fechando a fonte clicável até o ponto da fala. **Origem:** ADR-060.

**206. ATRIBUIÇÃO DE FALANTE — a medição Gemini × Whisper, com áudio real.**
Bloqueia a #203 (ver acima). Aberta em 03/08 com a medição **pronta e não
executada**: falta o insumo.

**Por que não foi medida nesta rodada.** A medição exige **áudio real de reunião
da Isis**, e não há nenhum no ambiente — o único arquivo de áudio no repositório
é um `.wav` de health-check do litellm. Medir com áudio sintético seria pior que
não medir: na montagem por concatenação de clipes de voz única, o corte de
segmento cai na troca de turno **por artefato**, e a conclusão sairia
otimista. Em reunião real há sobreposição, muletas ("é... então..."), ruído de
fundo e duas pessoas falando ao mesmo tempo — que é exatamente onde a atribuição
quebra. **Parado, por instrução, até o áudio dela chegar.**

**Protocolo já definido, para rodar assim que houver o arquivo** — duas dimensões,
não uma:

1. **Atribuição** — Gemini 2.5 (áudio nativo, já é provider nosso, já está atrás
   do LiteLLM) recebe a gravação e é *pedido* a marcar quem falou. Medir: quantas
   trocas de turno ele acerta, e o que faz nas sobreposições.
2. **Fidelidade de termo técnico** — `auto de infração`, número de auto/processo,
   nome de norma, número de matrícula, CCIR, NIRF. **Não adianta ganhar atribuição
   e perder o vocabulário**: o Whisper só acertou "auto de infração" depois do
   `VOCABULARIO_DOMINIO` no prompt (antes saía "**alto** de infração"), e um
   provedor novo começa sem esse ajuste. Comparar lado a lado, mesmo áudio.
3. **Custo e latência dos dois lados.** A conta estimada inverte a favor do
   Gemini — áudio ≈32 tokens/s ⇒ 30 min ≈ 57,6k tokens ≈ **US$ 0,058** no Flash,
   contra **US$ 0,18** do Whisper —, mas estimativa não é medição (foi
   exatamente assim que o "alto de infração" passou despercebido).

**Declaração honesta, obrigatória se o Gemini vencer:** é **LLM ouvindo e
atribuindo**, não diarização por impressão vocal. Erro de atribuição é erro de
modelo, não de assinatura de voz — e por isso tem de chegar à tela como
**"atribuição sugerida"**, nunca como fato. Um rótulo "Cliente:" que o consultor
leia como certeza é a #203 de volta, só que com aparência de resolvida.

**Origem:** medição de 03/08; absorve a #205.

## P3 — robustez e higiene (sem urgência, sem risco externo)

**46. Tipagem mypy do backend (~495 erros) é advisory, não enforçada.** O job
`backend-lint` do CI nunca rodou mypy de fato (morria antes, em `ruff: command not
found` — corrigido em `fix/backend-lint`, 03/06). Com o ruff verde, o mypy passou a
rodar e acusou **~495 erros em 77 arquivos**, sobretudo `Column[int]` vs `int` do
SQLAlchemy (acesso a atributos ORM em runtime). Como corrigi-los é refactor de
tipagem em massa (mexe em assinaturas/lógica), o passo mypy ficou **`continue-on-error:
true`** (advisory): roda e reporta, mas não derruba o check. **Fix incremental:**
anotar tipos / usar `Mapped[...]` do SQLAlchemy 2.0 por módulo, baixando o número aos
poucos; quando zerar, remover o `continue-on-error`. **Sem urgência.** **Origem:**
`fix/backend-lint` (03/06).

**9. `except Exception` genérico no `pdf_generator.py:234`** devolve `{"error": str(e)}` sem
`status` — engole qualquer erro. O logo foi só o gatilho (resolvido na Onda A do PROMPT_3);
o tratamento de erro continua frágil. **Origem:** Onda A (24/05).

**10. Testes que dependem de storage externo sem mock.** O `test_pdf_generator` não era o
único caso latente provável. Varredura quando der folga. **Origem:** Onda A (24/05).

**11. Race no versionamento `MAX(version)+1`** — capturado por `UniqueConstraint`, mas
devolve 500 + retry manual. Tratar com retry server-side. Improvável para consultor único.
**Origem:** Onda B (24/05).

**48. UNIQUE constraint de idempotência em `regulatory_issues` (3º caso do padrão "dedupe sem
constraint").** Hoje a não-duplicação de achados é só **app-level** (`auditor_imovel._persist_issues`
consulta + `by_key`); `pg_constraint` em `regulatory_issues` tem só PK + 4 FKs, nenhuma UNIQUE. Foi
a causa-raiz das 11 linhas `VERIFICACAO_ESPACIAL_PENDENTE` (caso 13). O ADR-020 removeu **aquele**
emissor (virou nota derivada), mas os OUTROS códigos (área, GEO, RL) seguem sem cinto de segurança
no banco — uma regressão no guard ou uma corrida volta a duplicar. **Fix futuro (PR próprio):**
índice UNIQUE parcial sobre chave estável `(tenant_id, property_id, codigo_alerta, tema, subject_ref)`
para `resolved_at IS NULL` — exige (a) desenhar `subject_ref`/chave estável (hoje o desempate usa
`descricao`, que varia com texto livre) e (b) **varredura table-wide** de duplicatas pré-existentes
antes de criar o índice (senão a migration falha). Mesmo padrão recorrente do staging (#81) e ações
(Ficha 07). **Origem:** diagnóstico dos alertas espaciais (30/06, ADR-020).
**✅ FECHADA (06/07, `feat/fase1-classificador-n1n2`, N1 item 6):** colunas `tema`/`subject_ref`
adicionadas a `RegulatoryIssue`; `_persist_issues` do `auditor_imovel` agora as popula
(`subject_ref` = documentos cruzados, join `|`); índice `uq_regulatory_issues_chave_estavel_aberta`
(UNIQUE parcial `WHERE resolved_at IS NULL`) criado via migration `b094ae9bee3d`. Varredura
table-wide rodada em prod ANTES da migration (`GROUP BY tenant_id, property_id, codigo_alerta
HAVING count(*) > 1` sobre linhas abertas) — **vazia**, prod estava limpo. NULL em `tema`/
`subject_ref` não colide entre si (semântica Postgres de UNIQUE com NULL distinto) — linhas
legadas não quebram. Testes em `tests/models/test_regulatory.py::TestRegulatoryIssueChaveEstavelUniqueParcial`.

**45. Extrator de campos sem skill procedural.** O `ExtratorAgent.execute()` chama
`extract_document_fields()` direto — **não** passa por `_compose_system_with_skills`. O
prompt de extração vive hardcoded em `document_extractor.py` (com fallback; pode vir do
banco via `prompt_service`), fora do padrão de skills (`.md` versionado) que o diagnóstico
e o auditor já seguem. O fix de truncamento (`fix/extrator-truncamento`, 02/06) melhorou o
prompt da matrícula inline, mas o ideal é migrar para skill procedural — versionável,
revisável pela sócia, por `doc_type`. **Sem urgência.** **Origem:** `fix/extrator-truncamento`
(02/06). Nota: se prod usa prompt do banco (`extract_matricula`), a melhoria de prompt deste
PR (fallback hardcoded) só vale onde não há prompt no banco — conferir/atualizar o prompt do
banco em prod se existir.

**44a. OCR Gemini multipágina é sequencial (1 call/página) e sensível a 503.** *(Desambiguado
de "#44" em 2026-07-06 — o número estava duplicado com a dívida abaixo, "chain não propaga
uf"; ambas viraram 44a/44b em vez de renumerar uma delas, pois 9 arquivos fora deste
registro já citam "#44" e renumerar quebraria essas referências. Convenção daqui pra
frente: colisão de número vira sufixo `a`/`b` no registro, sem tocar citações externas.)*
O fix de
`fix/ocr-multipagina` resolveu a leitura só-da-1ª-página rasterizando e transcrevendo página a
página, mas isso é serial: ~10s e ~$0.002-0.01 por página (doc de 6 págs ≈ 90s, $0.02). Sob 503
sustentado do Gemini ("high demand") uma página pode cair mesmo com os 3 retries → texto parcial
(degrada com elegância, não derruba o doc). Se virar gargalo: paralelizar as chamadas de página
e/ou cachear por página. **Sem urgência** — docs típicos ≤ alguns págs cabem no `soft_time_limit`
de 300s. **Origem:** `fix/ocr-multipagina` (02/06). Correlato: imagem do worker **dev** local
estava defasada (sem `pypdfium2`/`tenacity` que já estão no `requirements.txt` → prod OK); rebuild
local quando for mexer em deps de OCR.

**28. OCR do PDF SEMAD pendente.** A ingestão do corpus SEMAD (PR #24) indexou 282/283 PDFs;
`ON_01_2021_SEMAD - Errata.pdf` é escaneado e ficou de fora (sem camada de texto). Rodar pelo
pipeline OCR existente (`docs/arquitetura/PIPELINE_OCR.md`) e reingerir o único documento.
Baixo impacto (1 errata). **Origem:** corpus SEMAD (30/05).

**31. Histórico do git carrega 254 MB de corpus SEMAD removido.** A PR #31 tirou
`docs/base_regulatoria/` do HEAD (destravou o `git clone` do Render — ver `TROUBLESHOOTING`
categoria 8), mas os blobs seguem no histórico, então todo `git clone` ainda baixa ~254 MB.
Enxugar exige reescrita de histórico (`git filter-repo` + `push --force`) — **invasivo**:
reescreve SHAs e quebra os worktrees/branches ativos de outros trabalhos. Fazer em janela
dedicada, combinada com o Andre, com todos os worktrees fechados. **Origem:** fix deploy
Render (30/05).

**34. Duas trilhas de orçamento paralelas e desalinhadas.** O agente `orcamento`
(`_estimate_by_rules`, 3 tipos — `app/agents/orcamento.py`) e o serviço determinístico
`app/services/proposal_generator.py` (`PRICE_TABLE`, ~8 tipos, prazos distintos) têm tabelas de
preço **diferentes**. O endpoint `GET /api/v1/proposals/generate-draft` usa o **serviço**
(`app/api/v1/proposals.py:114`), não o agente — então o valor que o consultor vê pode divergir
conforme o caminho (chain `gerar_proposta` via agente × endpoint via serviço). Unificar numa fonte
única de preço (eleger serviço ou agente, migrar a outra para consumi-la). **Não urgente** (consultor
único, valores são rascunho que ele revisa e assina). **Origem:** verificação dos sister files
(31/05, quitação #32) — ver `docs/agentes/ORCAMENTO_AGENTE.md` seção 10.

**35. Implementar ZAPIProvider quando demandar.** A PR 2.1 (WhatsApp inbound a caso aberto) deixou
o contrato `WhatsAppProvider` + `EvolutionProvider` (real, httpx) e o `ZAPIProvider` em **stub**
(`app/services/messaging/zapi_provider.py` — `NotImplementedError`). Se/quando o consultor precisar
de Z-API (ex.: produção hospedada paga em vez de Evolution self-hosted), implementar `send_message`
+ `parse_inbound_webhook` e plugar via `WHATSAPP_PROVIDER=zapi` (config já pronta). **No mesmo balaio:**
**e-mail inbound (Resend) ficou adiado** na PR 2.1 — só os placeholders de config existem; retomar
quando o Resend Inbound for habilitado no domínio/plano (MX + webhook secret). **Origem:** PR 2.1 (31/05).

**37. Reintegrar o Evolution ao compose/boot quando o canal WhatsApp for reativado.** Em
2026-06-01 (decisão do André) o serviço `evolution` e o profile `whatsapp` saíram do
`docker-compose.yml` para destravar `docker compose up -d` (o `${EVOLUTION_API_KEY:?...}` da
definição do serviço abortava o boot do core inteiro, mesmo com a Evolution dormente). O código
do provider (`app/services/messaging/`) e o webhook (`/api/v1/messaging/whatsapp/webhook`)
**permanecem** — só foram desacoplados; o webhook responde **503 "WhatsApp não configurado"**
sem `EVOLUTION_API_URL`/`KEY`. **O que destrava:** ao reativar o WhatsApp, repor o serviço
`evolution` no compose (definição antiga no git — PR 2.1, #38) e preencher as envs no `.env`.
**Como reativar:** ver `docs/operacao/RUNBOOK_OPS.md` (seção WhatsApp/Evolution). **Origem:**
PR ops/evolution-opcional-no-boot (01/06).

**38. ✅ FECHADA (01/06, `fix/chain-legislacao-timeout`). Falha de um agente abortava a chain inteira
(legislacao matava o diagnóstico).** `app/agents/orchestrator.py` agora tem exceção escopada por
chain: em `diagnostico_completo`, `legislacao` é insumo intermediário e fica não-bloqueante tanto para
`requires_review=True` quanto para falha/timeout. A falha é preservada em
`ctx.chain_data["legislacao"]` e a chain continua para `diagnostico`; em chains onde `legislacao` é o
produto final, o comportamento permanece bloqueante. **Revalidado rodando:** com timeout Gemini
(`litellm.Timeout`, AIJob 134, ~33,6s), a chain continuou e `diagnostico` rodou (AIJob 135), entregando
3 itens em `passivos_identificados`; em execução sem timeout, `legislacao.requires_review=True` também
não parou a chain e `diagnostico` rodou (AIJob 139). Auditoria:
`docs/arquivo/auditorias/2026-06-01_chain_legislacao.md`.

**39. Robustez da `legislacao` (timeout/parsing).** A `legislacao` falha intermitentemente: AIJob 115
por `json_parse` ("não foi possível extrair JSON da resposta LLM"), AIJob 124 por `litellm.Timeout`
("Connection timed out after None seconds" — timeout aparentemente sem limite). Endurecer: timeout
explícito por chamada, parsing tolerante de JSON + retry, e/ou fallback de provider mais robusto.
**Origem:** mergulho fluxo agêntico (01/06).

**44b. A chain não propaga `uf` ao `ctx.metadata` do diagnóstico (skill base só casa com `uf` presente).** *(Desambiguado de "#44" em 2026-07-06 — ver nota completa na 44a acima.)*
Descoberto ao fechar a #40: a skill `diagnostico/situacao_ambiental_imovel_rural` tem
`applies_to: {uf: [GO, MS, MT]}`, então `matches_context` só a injeta no system prompt quando
`ctx.metadata["uf"]` existe e está na lista. Provado rodando: com `uf="MS"` a skill é injetada
(prompt 45 → 55.504 chars); **sem** `uf` o bloco `<!-- skills:start -->` não aparece. Hoje o `uf`
só chega se o **caller** da chain o coloca em `body.metadata` (`app/api/v1/agents.py` →
`run_agent_chain` → `AgentContext(metadata=metadata or {})`); nada deriva `uf` do imóvel/processo
automaticamente, e o `DiagnosticoAgent` não auto-enriquece o metadata. Logo, na chain
`diagnostico_completo` disparada sem `uf` explícito, o diagnóstico roda **sem** a skill base.
**O que destrava:** a chain (ou o agente) derivar `uf` do imóvel/processo e injetar no
`ctx.metadata` antes do diagnóstico. **Toca orquestração/propagação de contexto na chain → ligada à
#38** (mesmo PR de chains sensíveis, com aval do André). **NÃO resolvido no PR #40** (escopo de lá era
só validar os SKILL.md). **Origem:** validação E2E do PR #40 (01/06).
**✅ FECHADA (06/07, `fix/fase0-gap-ficha07`, item 7 do gap-analysis Ficha 07):** `_build_context`
(`app/api/v1/agents.py`) deriva `uf` do `Property.state` do processo quando o caller não passa o
metadado explicitamente (callers que já setam `uf` não são sobrescritos). Testado com UF=AC (corpus
Acre). Ver `tests/api/test_agents_uf_propagation.py`.

**41. `create-case` não auto-dispara a chain de diagnóstico.** Ao finalizar o caso, só o
`atendimento` roda; o consultor precisa acionar diagnóstico/legislação manualmente. Decisão de
produto/custo: auto-rodar `diagnostico_completo` ao criar o caso (custo de LLM por caso) ou manter
manual com um botão claro? **Decisão pendente do André.** **Origem:** mergulho fluxo agêntico (01/06).

**42. Bucket MinIO não garantido na geração de URL presigned.** `_ensure_bucket_exists`
(`app/services/storage.py`) só roda em put/get server-side, não ao gerar a URL presigned. Em ambiente
novo, o PUT do consultor direto no MinIO dá **404 NoSuchBucket** (visto no mergulho). Prod já tem o
bucket (latente), mas o intake quebra em qualquer MinIO recém-criado. Garantir o bucket na geração da
presigned URL (ou no startup). **Origem:** mergulho fluxo agêntico (01/06).
> **Nota (01/06):** distinta do bug de **region R2 + SignatureDoesNotMatch** (o GET não lia o
> objeto), fechado em `fix/storage-r2-region-redis` — ver
> `docs/trabalhos/storage_r2_redis.md` e a tabela "Fechadas". A #42 (bucket presigned ausente)
> **segue aberta**.

**43. Error Boundary único na raiz apaga o app inteiro.** `frontend/src/App.tsx:33` envolve toda a
aplicação em um único `<ErrorBoundary>`. Qualquer crash de render (ex.: componente lê `undefined`
quando uma query falhou) **apaga a aplicação inteira** ("Algo deu errado"), incluindo a navegação.
O `QueryClient` não usa `throwOnError`, então o gatilho é render-time, não a query em si. Adicionar
boundaries por rota/seção (degrade local em vez de nuke global). O **gatilho exato** ("Algo deu
errado" pós-IA/criar-caso) **não foi reproduzido** (precisa de navegador/devtools) → repro pendente.
**Origem:** mergulho fluxo agêntico (01/06).

## P3 — Rota Regulatória E5 (Sprint 2 · follow-ons nomeados)

Abertos deliberadamente ao entregar a Rota (ADR-021). O snapshot editável já existe; estes
estendem, não corrigem.

**49. Documento da Rota em Saídas.** Gerar a peça formal da rota (para o dossiê/Saídas). O
`RedatorAgent` **não tem template "rota"** — exige template novo + `requires_review=True`.
Hoje a rota vive só como entidade/tela, sem documento. **Origem:** Rota E5 (Sprint 2).

**50. Religar `auditor → legislacao` (a "cadeia pela metade").** Hoje a `LegislacaoAgent` keia
por `demand_type`, não pelos passivos do auditor — a Rota não é a somatória das Ações (Ficha
§3.5). Alimentar os findings do auditor na legislação para que a rota derive dos passivos.
Medido no diagnóstico read-only (TASK 7). **Origem:** Rota E5 (Sprint 2).

**51. Gatilho "Ação mudou em Ações → desatualiza a rota".** Quando uma Ação vinculada muda,
marcar a rota `desatualizada`. Depende do link rota↔ações (hoje inexistente). **Origem:**
Rota E5 (Sprint 2).

**52. Auto-RAG de fundamento ao adicionar passo manual** (Ficha §8.1 "REPROCESSE"). Ao criar
um passo manual, buscar a norma que o sustenta no RAG. MVP: o consultor digita o fundamento/
origem em `origem_manual_nota`. **Origem:** Rota E5 (Sprint 2).

**53. Aprendizado real da Legislação a partir das reordenações.** O MVP só CAPTURA o sinal
(persiste a ordem do consultor). Fechar o loop de feedback-ao-modelo (reordenação vira sinal
de treino/ajuste do prompt) é follow-on. **Origem:** Rota E5 (Sprint 2).

**55. Grupos de contiguidade por matrícula (follow-on ① do Sprint 4).** O MVP registra a
declaração no nível do imóvel (`Property.matriculas_contiguas` tri-state, ADR-023). Quando um
imóvel tiver N grupos, modelar `grupo_contiguidade` na `Matricula` + soma derivada POR GRUPO
(consumidores da soma teriam que virar group-aware: dossiê, Hub, prompts, matriz, auditor).
O corte MVP contorna: não-contíguo = separar em outra Property (re-home já existe).
**Origem:** Sprint 4 (Ficha 07 §9).

**56. N CARs / CAR por grupo (follow-on ② do Sprint 4).** `Property.car_code` é 1 slot
(String). Dois grupos não-contíguos = dois CARs legais; hoje o 2º não é representável e o
passivo determinístico "CAR nao cadastrado" (`diagnostico.py`) dá falso-negativo com 1 CAR
presente. Depende do #55 OU da separação em Properties (caminho MVP). **Origem:** Sprint 4.

**57. Split-wizard / UI de mover matrícula (follow-on ③ do Sprint 4).** O re-home existe
como API (`PATCH /properties/{pid}/matriculas/{mid}`, auditado) e o aviso de não-contiguidade
orienta a separação — mas não há botão na UI. Wizard: escolher matrículas → criar/escolher
imóvel destino → mover em lote (processos/docs continuam no imóvel de origem; avaliar o que
migra junto). **Origem:** Sprint 4 (TASK 0a).

**58. Corpus legislativo do Acre incompleto — N7 sem conteúdo.** A ingestão do corpus AC
(`scripts/ingest_legislacao_acre.py`, 11 docs, 4.658 chunks) pulou `ACRE_N11.md`
(byte-idêntico a N10 por SHA-256, sem perda) e `ACRE_LEG_RURAL.md` (compilação dos N#,
sem conteúdo exclusivo) — **exceto** o N7 (~28KB), cujo único conteúdo exclusivo não
veio no export da pasta `Legislacoes Regente` e a André confirmou que **não vai vir**
(não vale reprocessar/perguntar de novo). RAG de legislação AC roda sem o N7 — se
algum caso futuro precisar do fundamento normativo especificamente do N7, vai faltar
no `knowledge_catalog` até que outra fonte apareça. **Marco para revisitar:** se a
sócia trouxer o conteúdo do N7 por outro canal (novo export, PDF avulso). **Origem:**
Sprint corpus Acre (2026-07-04), fechado sem N7 em 2026-07-06.

**61. Corpus legislativo do Acre NUNCA rodou contra produção (distinta da #58).**
Confirmado no item 0 da Fase 1 (06/07): `SELECT uf, count(*) FROM knowledge_catalog`
em prod (`diquycxxkfrjhxtrcmzb`) tem 24.233 linhas — GO/MS/MT/Federal, **zero** com
`uf='AC'`. O commit `ef76da0` (PR #95) já dizia "Executado em dev" — mesmo padrão
recorrente da dívida #47 (corpus SEMAD/estadual ausente em prod). Runbook + script
de reindex síncrono prontos em `docs/trabalhos/corpus_acre_prod.md` e
`scripts/reindex_legislation_by_uf.py` (PR #102) — falta só rodar com credenciais de
prod. **Origem:** item 0 da Fase 1 (gap-analysis Ficha 07, 06/07).

**59. Tipos próprios para planta/memorial/auto-de-infração no classificador de
documentos.** O classificador rule-based do `extrator` não distingue planta/memorial
descritivo de CCIR — quando o conteúdo cita internamente um código INCRA/SNCR ou termos
de CCIR, a heurística rotula como `source_doc_type='ccir'`. Isso faz o documento "colher"
campos (SNCR, área) e disputar o mesmo `matricula_hint` de um CCIR real vizinho, gerando
matrícula espúria quando consolidado (mecanismo documentado em
`docs/operacao/TROUBLESHOOTING.md`, categoria 2). O guard fantasma e o fix de bucket do
Sprint 4 (ADR-023) mitigam o **dano** (nada grava sem divergência acusada), não a
**causa**. **Caso real:** caso 13 (Property 10), docs 228/230 lidos como `ccir` sendo
plantas. **Origem:** verificação pós-merge #94–#97 (2026-07-06), residual de severidade
rebaixada citado em ADR-023.
**✅ FECHADA (06/07, `feat/fase1-classificador-n1n2`, N1 item 1):** classificador ganhou
4 tipos novos (`planta_topografica`, `memorial_descritivo`, `auto_infracao`,
`certidao_embargo`) com precedência ANTES de `ccir`/`sigef` — a menção fraca de "CCIR"
na legenda de uma planta não sequestra mais a classificação (fixture do shape real do
doc 228, `tests/agents/test_extrator_ficha01_staging.py`). `auto_infracao` reusa o tipo
já existente no pipeline legado (`document_extractor.py`), não duplicado. Planta/memorial
não têm `_FIELD_SPECS` (não alimentam staging cadastral) nem entram no allowlist de
criação de `Matricula` (guard já existia, Sprint 4). Item 3 (mesma rodada): o
`skipped_reason` que já existia e nunca era lido agora vira nota visível em
`Document.extraction_status` ("recebido, não processado — revisar").

**60. Conceito `registro_anterior` na `Matricula` (linhagem de matrícula). — FECHADA
(PR #60-cadeia, 2026-07-18, ADR-027).** Implementada além do conceito inicial: a
linhagem virou VIGÊNCIA. `Matricula.vigencia` (`vigente`/`historica`) + `superseded_by_id`
(cadeia navegável) + `registro_anterior`/`denominacao_anterior` extraídos com fonte.
Detecção por 3 sinais PROPÕE, consultor confirma em 1 clique na Conferência (substitui as
12 rejeições), reversível em Dados. Histórica sai da soma e das lacunas, permanece como
linhagem. Caso da Isis validado (processo 14): 4698+6776 = 1.010,5583 (não em dobro).
Detalhe abaixo (mantido para histórico da origem).


imóvel rural muda de número de matrícula por reabertura/desmembramento cartorial, o
sistema hoje não modela a linhagem — cada matrícula é um registro independente sem
referência à anterior. Evidência real: caso 13, linhagem 2609→2923→4698 (mesma área,
números diferentes ao longo do tempo); um CCIR de 2024 ainda cita a ficha antiga (2923),
o que confundiu o extrator/consolidação. **O que destrava:** campo
`Matricula.registro_anterior` (auto-referência nullable) para o consultor documentar a
cadeia manualmente quando souber, sem exigir que o sistema infira automaticamente.
**Sem urgência** — mitigação atual é o consultor validar o SNCR/área manualmente (selo
de oficialização, ADR-022). **Origem:** verificação pós-merge #94–#97 (2026-07-06),
diagnóstico da remediação do caso 13.
> **Critério de domínio da Isis (registrado no forense do teste dela, 2026-07-18 — NÃO
> implementado aqui):** a matrícula **vigente é a da ÚLTIMA averbação**; a ficha anterior
> (mesma terra, número/proprietário antigos) NÃO deve compor a soma de área do imóvel.
> Evidência viva: processo 14 (Fazenda São Jorge) — a matrícula **4655** (Fazenda
> Shangri-lá, proprietário antigo) é a ficha anterior da **6776** (Lote 01-C vigente,
> mesma área 349,9022 ha); ambas materializadas somaram a área em dobro. Idem lote 1B:
> CCIR **2923** ↔ matrícula **4698**. Quando #60 for implementada, `registro_anterior`
> (ou equivalente) deve marcar a ficha anterior como fora-da-soma automaticamente. Até
> lá, a mitigação nova (fix forense: desativar matrícula na Conferência) permite ao
> consultor **rejeitar** a ficha anterior e tirá-la da soma manualmente.

**62. Fallback `_rules_based_diagnosis` fica cego ao passivo do auto de infração.** A Fase 1
(N2, item 10) fez o `DiagnosticoAgent` carregar os fatos do auto de infração
(`_load_auto_infracao_fatos`) e transformá-los em `Afirmacao` determinística
(`_build_afirmacoes_auto_infracao`) — **mas só no caminho com LLM**. Causa raiz medida em
`app/agents/diagnostico.py`: os autos são carregados em `run()` (linha ~175) e guardados em
`process_data["process"]["autos_infracao"]`; quando `settings.ai_configured` é falso, `run()`
retorna `self._rules_based_diagnosis(process_data)` (linha ~181), e esse método (linha ~679)
monta passivos/ações a partir de campos cadastrais e dos findings do auditor, **mas nunca lê
`process_data["process"]["autos_infracao"]` nem chama `_build_afirmacoes_auto_infracao`**. Efeito:
no modo degradado (IA indisponível), um imóvel com auto de infração real (ex.: caso 13, doc 240
IBAMA nº 484341) não gera Afirmação nem passivo do auto — o diagnóstico de fallback silencia o
passivo mais grave, violando "degradar com elegância, nunca ficar cego" (Princípio do radar).
**Fix proposto (pequeno e seguro):** em `_rules_based_diagnosis`, ler
`autos = process_data.get("process", {}).get("autos_infracao", [])` e passar
`afirmacoes=self._build_afirmacoes_auto_infracao(autos)` para `_build_payload` (que já aceita
`afirmacoes=`, linha ~966), espelhando o path com LLM; opcionalmente somar um passivo
determinístico por auto. **O que destrava:** paridade de honestidade entre os dois caminhos do
diagnóstico. **Origem:** Fase 2 (`feat/fase2-reset-tool`, 2026-07-12) — gap declarado na Fase 1,
registrado como carona da ferramenta de reset.

**63. Fusão Tarefas→Ações no workspace (pós-MVP).** O Sprint 6 ocultou a aba **Tarefas** do
detalhe do caso (flag `isTabVisible`, ver ADR-024), mas **não fundiu** `Task` em `Acao`. As
duas entidades são deliberadamente distintas (`app/models/acao.py:20-26`): a fusão seria 1:N,
não 1:1, e perderia o grafo de dependências + o kanban operacional das `Task`. Por ora `Task`
segue viva por baixo (só a superfície some). **O que destrava:** se algum dia o consultor
precisar operar tarefas genéricas dentro do caso sem sair para outra superfície, decidir
conscientemente se elas viram Ações, ganham aba própria de volta, ou migram para outro lugar —
com o desenho do grafo preservado. **Origem:** Sprint 6 (`feat/sprint6-limpeza-abas`, 2026-07-13).

**64. Aba IA do workspace não dispara a cadeia de agentes.** A aba **IA** (`ai`) do detalhe do
caso (`AIPanel`) estava quebrada — não aciona a cadeia de agentes da etapa. O Sprint 6 a
**ocultou** (flag `isTabVisible=false`, ADR-024), o que resolve a dor imediata (tela morta na
frente do consultor) mas **não conserta** o disparo. **O que destrava:** religar o flag depois
de fazer o painel efetivamente orquestrar a cadeia (ou redirecionar o "Rodar agentes" para o
mesmo caminho do `WorkspaceRightPanel`, que já dispara). Enquanto não consertar, manter oculta.
**Origem:** Sprint 6 (`feat/sprint6-limpeza-abas`, 2026-07-13).
> **Mitigação parcial (forense caso Isis, 2026-07-18, `fix/forense-caso-isis`):** o
> `WorkspaceRightPanel` já dispara, mas a chain `intake` FALHAVA silenciosamente porque o
> endpoint `POST /macroetapa/run-agents` passava só `{macroetapa}` e o agente `atendimento`
> exige `metadata['description']` ("Campo 'description' obrigatorio…" — 3× no processo 14).
> O fix passa a derivar a descrição do processo e, sem descrição, retorna mensagem honesta
> (`dispatched=False`) em vez de disparar pra falha invisível. **Falta** a superfície de
> resultado (aba IA religada / surface no workspace) — parte frontend desta dívida.

**65. Humanizador da timeline do workspace não traduz eventos de agente.** Achado da varredura
de linguagem (ADR-025). `frontend/src/pages/Processes/historicoEventos.ts::describeEvento` cobre
`staging_decidir`, `consolidar`, `status_changed`, etc., mas **não** tem ramo para
`agent.{nome}.{status}` — esses caem em `descreverGenerico`, que faz `humanizar(action)` →
"Agent vigia completed" (semi-técnico) e pode expor escalares do payload não listados em
`META_OCULTO`. Baixa urgência hoje: é a aba **Histórico**, oculta no Sprint 6 (ADR-024). **O que
destrava:** se a aba for religada, o Histórico do caso volta a mostrar linguagem de máquina em
eventos de agente. **Fix proposto (S):** adicionar ramo `agent.*` em `describeEvento` reusando
`agentLabel`/`translateActivity` de `lib/activityLabels.ts` (fonte única criada neste PR).
**Origem:** varredura da linguagem de consultor (`fix/dashboard-linguagem-consultor`, 2026-07-13).

**66. Dois mapas macroetapa→chain divergentes (drift).** Achado do forense caso Isis
(2026-07-18). Existem DOIS mapas de macroetapa para nome de chain: `MACROETAPA_AGENT_CHAIN`
(`app/models/macroetapa.py:233`, usado pelo botão "Rodar agentes" em `run_stage_agents`) e
`MACROETAPA_CHAINS` (`app/agents/orchestrator.py:92`, não usado pelo botão). Eles DIVERGEM
em `caminho_regulatorio`: o primeiro mapeia para `"analise_regulatoria"`, o segundo para
`"enquadramento_regulatorio"`. Não foi a causa do bug da Isis (a etapa dela era
`entrada_demanda`), mas é uma fonte latente de comportamento inconsistente conforme quem lê
o mapa. **O que destrava:** unificar numa fonte única (ou documentar por que são dois) e
testar que ambos os nomes de chain existem no registry `CHAINS`. **Origem:** forense caso
Isis (`fix/forense-caso-isis`, 2026-07-18).
**✅ FECHADA (30/07, `fix/polimento-validacao-30-07`):** `MACROETAPA_CHAINS` deixou de ser
escrito à mão e passou a ser **derivado** de `MACROETAPA_AGENT_CHAIN` (fonte única), com a
chave em `str` para não obrigar quem consome o orquestrador a importar o enum.
`tests/agents/test_chain_fonte_unica.py` trava as três garantias: os dois mapas dizem a
mesma coisa, toda `Macroetapa` tem entrada, e todo nome de chain apontado existe no
registry `CHAINS` (etapa manual — `coleta_documental`/`contrato_formalizacao` — segue
`None` por projeto). O que a #66 previa como "fonte latente de comportamento
inconsistente" apareceu de fato na validação de 30/07: o botão "Rodar agentes da etapa"
falhou na E4 e a mesma cadeia rodou pela seção de Agentes. A divergência de mapa era
metade; a outra metade é o TRANSPORTE (fila do Celery × execução dentro da requisição),
que continua sendo duas coisas de propósito — mas o 503 mudo do botão virou mensagem que
diz o que houve e qual a saída, e grava `stage_agents_dispatch_falhou` na trilha.

## Bloqueada por terceiros / coordenação (NÃO tocar sozinho)

**13. R1 — contratos externos.** Headers `X-Amigao-*` em `alerts.py`, `User-Agent` dos
crawlers. Risco de quebrar webhook receiver e allowlists de SEMAs. **Coordenar com os
consumidores antes.**

## Aguardando infraestrutura (D1 = `Property.geom`)

**14. Sobreposição e alertas geoespaciais** (🛰️ na skill do auditor): CAR deslocado,
polígono deslocado, sobreposição com terceiro, confrontantes, datum/fuso, RL × realidade,
APP, supressão, restrição territorial. O helper `grade_overlap_severity()` já está
preparado sem chamador; pluga direto quando o `geom` existir.

**15.** Alertas de consulta externa (🔌): embargo (IBAMA), auto de infração,
licença/outorga — aguardam integração.

**27. Aplicar `EncryptedString` em colunas reais.** A infraestrutura de cripto de
segredos (Fernet + `EncryptedString` + `CREDENTIAL_ENCRYPTION_KEY`) foi entregue pela
Frente D ([ADR-014](adr/014-cripto-segredos-usuario.md)), mas **nenhuma coluna real a usa
ainda**. Plugar quando a **PR 2.3** (`Credential` — logins de portal por cliente) e a
**PR LLM** (`User.preferences.ai.api_key` — chave de IA do consultor, white label)
entrarem. **Origem:** Frente D (28/05). **Parcialmente fechada (30/05, PR LLM):** a chave de
IA do consultor já é gravada criptografada — mas em `User.preferences['ai']['api_key_encrypted']`
(JSONB), via `encrypt_str`/`decrypt_str` no service (NÃO `EncryptedString`, que é só p/ coluna
String). Resta a **PR 2.3** (`Credential` — aí sim usa `EncryptedString` em coluna real).
**✅ FECHADA (30/05, PR 2.3):** o modelo `Credential` (tabela `credentials`) usa `EncryptedString`
na coluna `password_encrypted` — primeiro uso real do type decorator em coluna de tabela. Cofre de
logins de portais por cliente (SEMA/IBAMA/SICAR/INCRA/banco). Ver tabela "Fechadas" abaixo.

**30. Auditoria de uso de IA por usuário/tenant (white label).** Com o consultor trazendo a
própria chave, falta rastrear gasto/tokens consumidos POR chave de consultor (hoje os limites de
custo — horário/mensal — são por tenant, e o cost cap por job não distingue chave do sistema vs
do consultor). Útil para billing/transparência quando o white label escalar. **Origem:** PR LLM (30/05).

**32. Sister files dos 7 agentes restantes.** A PR de quitação documental (30/05) criou
`docs/agentes/` com `ECOSSISTEMA_AGENTICO.md` + sister files de `extrator`, `legislacao` e
`atendimento` (+ `MEMORIA_CHAT.md`). Faltam os sister files de `diagnostico`, `auditor_imovel`,
`orcamento`, `financeiro`, `redator`, `acompanhamento`, `vigia`, `marketing` — adiados por não
haver material absorvido fresco que justifique criar agora. Criar em round documental dedicado ou
quando a feature do agente evoluir. **Origem:** quitação documental (30/05). **Nota:** isto encerra
o deferimento histórico dos "docs de agente" (que nunca foi dívida numerada — vivia nos pulsos do
`progressoIA`); os 4 docs centrais estão feitos, os 8 restantes ficam aqui como dívida residual menor.
**✅ FECHADA (31/05, `docs/sister-files-agentes`):** criados os 8 sister files restantes
(`diagnostico`, `auditor_imovel`, `orcamento`, `financeiro`, `redator`, `acompanhamento`, `vigia`,
`marketing`), todos verificados contra o código real (referências `arquivo:linha`). Os 11 agentes
agora têm sister file. A rodada também corrigiu uma alegação errada do mestre — `diagnostico`
estava documentado como `requires_review`="não", mas o código força `True` (`diagnostico.py:448`).
Achados de divergência docstring×código de cada agente ficaram registrados na seção 10 do
respectivo sister file (não elevados aqui — não destravam pipeline).

**33. Auditoria de USO server-side de segredo decifrado.** Apurado em
`docs/arquivo/auditorias/2026-05-30_auditoria_leitura_sensivel.md`: o `AuditLog` audita
escrita (create/update/delete/reconciled) mas NÃO audita o uso server-side de segredo decifrado —
a `api_key` de LLM do consultor é decifrada em `BaseAgent` a cada chamada sem registro; a senha de
portal (`Credential`) é decifrada no load do ORM mas hoje **não tem consumidor** (não vaza). Quando
a senha ganhar consumidor real (login automatizado / endpoint de revelação) ou ao querer rastrear
uso da `api_key`, adicionar `AuditLog` no ato de uso. Conecta com **#30** (uso de IA por chave) e
**#18** (verificação da hash chain). NÃO implementar agora — PR própria. **Origem:** auditoria de
leitura sensível (30/05).
**🟡 PARCIALMENTE FECHADA (31/05, `feat/divida-33-audit-uso-api-key`):** a parte com uso real — a
`api_key` de LLM do consultor — passou a ser auditada. `BaseAgent.call_llm` emite `AuditLog`
`action="ai_key_used"` (hash chain) **uma vez por execução** quando a chave própria do consultor é
usada, com a chave **sempre mascarada** (`…últimos4`; plaintext nunca persistido/logado);
best-effort (falha de auditoria não derruba o agente). Helper `emit_ai_key_use_event`
(`app/agents/events.py`); 5 testes em `tests/agents/test_base_agent_ai_key_audit.py`. **Resta** (sem
uso real hoje, por isso adiado): auditar a senha de portal (`Credential`) — só quando ganhar
consumidor (login automatizado / endpoint de revelação). Conexão com **#30**/**#18** mantida.

## Reveladas em fix/llm-consistencia (07/06)

**47. Corpus de legislação (RAG) AUSENTE no banco de produção.**
Medido no Supabase prod (`diquycxxkfrjhxtrcmzb`, 07/06): `knowledge_catalog` e
`legislation_documents` têm **0 linhas**. O agente legislação roda, mas com
`tokens_in≈572/694` (só query+system, zero trechos) e declara "ausência de
trechos legislativos hiper-relevantes" — exatamente o sintoma reportado. **Causa
estrutural (dado ausente), não bug de busca:** o corpus (~23k chunks GO+Federal)
foi ingerido em dev/local (Sprint W 14/05, SEMAD 20/05) mas o Supabase prod foi
criado em 19/05 e nunca recebeu os dados. O código de `knowledge_catalog.search`
está correto. **Resolver (ops, PR/runbook próprio):** rodar
`scripts/ingest_federais_canonicos.py`, `ingest_legislacao_estadual.py`,
`ingest_corpus_semad.py` (e afins) contra o `DATABASE_URL` de prod com
`OPENAI_API_KEY` (text-embedding-3-small 768d). ⚠️ A maioria dos PDFs-fonte foi
removida do git (deploy Render) — recuperar a fonte antes. **Marco:** alta
prioridade — sem o corpus, o diferencial regulatório/RAG está morto em prod.
**Observabilidade já adicionada** em `fix/llm-consistencia`: log `legislacao.rag
0 trechos …` quando a busca volta vazia. **Origem:** Item 4 da PR
`fix/llm-consistencia` (07/06). Doc: `docs/trabalhos/llm_consistencia.md`.
> **Atualização 2026-07-13:** a premissa "0 linhas" ficou desatualizada — prod já
> tinha 24.233 chunks (MT/GO/MS/Federal). O último gap conhecido era a fatia **Acre**
> (0 linhas `uf='AC'`), agora **ingerida em prod** (28.891 chunks totais, +4.658;
> ver `docs/trabalhos/corpus_acre_prod.md`). #47 permanece aberta como guarda-chuva de
> cobertura das demais UFs (meta 27 UFs), mas os corpora hoje presentes em dev estão
> todos em prod.

## Backlog de produto (já versionado em ADR)

**16. Loop de aprendizado com material dos consultores** — ADR-010.

## Reveladas na revisão do PROMPT_6 (26/05)

*Régua de prioridade aplicada após classificação do Andre.*

### P3 — com marco condicional

**21. Pares de status semanticamente incoerentes fora das 2 regras do PROMPT_8.**
As 2 regras de `regulatory_coherence.py` foram desenhadas como "barrar o
absurdo óbvio" — escopo fechado, não máquina de estados completa. Sobram
pares teoricamente incoerentes que o sistema aceita por desenho:
`status_achado=resolvida` com `status_saneamento=pendente` (achado já
sanado mas saneamento ainda pendente); `descartada+pendente`,
`ignorada+pendente` e variações com `nao_aplicavel`/`descartado` no
saneamento sobre achados terminais. **Dimensionamento:** consultor não é
adversário (P2 da rodada, agora P3 do que sobrou) — não cria isso de
propósito; UI dos 5 botões pode até prevenir naturalmente pelo fluxo de
clique. **Marco para revisitar:** apenas se aparecer dado real bagunçando
o estado (ex.: import legado, regressão de UI deixando registros em
combinações fantasmas). Aí valeria considerar máquina de estados completa
ou regras adicionais. **Origem:** revisão pós-PROMPT_8 (26/05 — Andre
notou ao revisar o escopo).

**22. Workaround `--experimental-require-module` no runner do Vitest.**
Os primeiros testes de componente do frontend (PROMPT_9) usam jsdom 27,
que puxa `@asamuzakjp/css-color` (CJS) que `require()` `@csstools/css-calc`
(ESM). Node 22.11 só aceita isso com a flag experimental
`--experimental-require-module`. Como `poolOptions.execArgv` do Vitest não
propaga aos workers Tinypool, o workaround é o runner
`frontend/scripts/run-vitest.mjs` que injeta a flag via `NODE_OPTIONS`.
**Marco para remover:** quando o jsdom corrigir a dep CJS/ESM upstream
**ou** quando o projeto subir pra Node 22.12+ (que ativou `require(esm)`
por default). Sem urgência — o runner é local, isolado e cross-platform.
**Origem:** PROMPT_9 (26/05).

**26. Unificação `Process.status` × `Process.macroetapa` (eixo 3 — PR3-agressivo).**
Hoje o sistema mantém duas máquinas de estado paralelas: o enum legado
`ProcessStatus` (em `app/models/process.py`) e o novo enum `Macroetapa`
(em `app/models/macroetapa.py`), conectados pelo dicionário fixo
`STATUS_TO_MACROETAPA`. Card do kanban lê `macroetapa`; outras telas e
endpoints legados ainda olham `status`; cada update precisa decidir qual
fonte respeitar. **Por que continua aberta:** o fix
`fix/diagnostico-propaga-estado` (PR atual) foi deliberadamente
conservador — só propaga o estado da assinatura para a `macroetapa` e
adiciona um gate em `can_advance_macroetapa`. A unificação propriamente
dita (eleger uma fonte única, migrar dados, ajustar as 4 tabelas
denormalizadas que carregam o status, podar `STATUS_TO_MACROETAPA`)
ficou para um PR3 agressivo, isolado, com migration própria. **Marco
para destravar:** quando alguma feature ou bug exigir resolver
divergências entre os dois eixos (e.g. relatório que mistura `status` e
`macroetapa`, regra de negócio que conflita por causa do mapeamento
fixo). **Origem:** PR `fix/diagnostico-propaga-estado` (2026-05-28).

**18. Hash chain de `AuditLog` sem rotina de verificação.**
`app/services/audit_hash.py` tem **só escritores** (`compute_audit_hash`,
`get_last_hash_for_tenant`, `stamp_audit_hash`) — não existe função que
percorra a cadeia de um tenant e detecte se algum elo foi quebrado.
Hash chain sem verificador é cerimônia. **Marco:** implementar **antes do
primeiro uso jurídico da trilha** (auditoria de órgão, disputa com banco,
contestação de decisão do consultor). Até lá, **não vender** "auditabilidade
garantida" como se o verificador existisse. **Resolver:** adicionar
`verify_audit_chain(db, tenant_id) -> list[BrokenLink]` que recomputa cada
hash em ordem e compara com o `hash_sha256` persistido; expor via endpoint
admin (read-only, auth restrita). **Origem:** revisão do PROMPT_6 (26/05).
**Nota:** dívida pré-existente (vem do A1).
**✅ FECHADA (31/05, `feat/divida-18-verify-audit-chain`):** `app/services/audit_hash.py` ganhou
`verify_audit_chain(db, tenant_id) -> list[BrokenLink]` (+ helper puro `_verify_chain`) que percorre
a cadeia carimbada do tenant em ordem de `id` e faz duas checagens ortogonais por registro:
integridade do **conteúdo** (recomputa `hash_sha256`) e do **elo** (`hash_previous` aponta para o
anterior). Exposto em `GET /api/v1/admin/audit/verify-chain` (`app/api/v1/audit.py`), read-only,
**superusuário**, tenant do JWT. 10 testes (`tests/services/test_audit_hash.py` +
`tests/api/test_audit.py`): cadeia válida, conteúdo adulterado, linha removida (elo quebrado),
isolamento por tenant, 403 para não-superuser. Agora a auditabilidade tem verificador — deixa de ser
cerimônia.

---

**67. Proposta/contrato multi-bloco e multi-titular.** O S5-A gera a proposta a
partir da(s) Rota(s) validada(s) do processo, mas o caso real da Mirante às vezes
tem BLOCOS de serviço distintos (imóveis/matrículas diferentes) e/ou mais de um
titular no mesmo instrumento. Hoje: quando há mais de uma Rota validada, o S5-A
agrega os passos numa proposta só e soma as faixas (o `rota_id` no nível da
proposta fica nulo; a rastreabilidade fina permanece em `scope_items[].rota_passo_id`).
O CONTRATO (S5-B) trata bloco único do processo corrente. **O que destrava:**
modelar blocos de serviço (imóvel+matrículas por bloco) e contratante multi-titular
na proposta e no contrato. **Origem:** S5-A (2026-07-18), decisão registrada na
missão ("multi-bloco/multi-titular = dívida pós-MVP, registrar"). Ver ADR-028.

**68. Follow-ons da consolidação da peça Mirante (S5-B).** A geração de proposta/
contrato virou determinística e canônica (`app/services/mirante_documents.py`,
ADR-029), mas a consolidação com o legado ficou pela metade e há arestas nomeadas:
**(a)** o `contract_generator.fill_contract_template` (template-fill genérico) e o
`scope_base` residual do `PRICE_TABLE` (`proposal_generator.py`, já morto desde o
S5-A) seguem no código para o caminho AVULSO (contrato sem proposta) e os paths
`proposta`/`contrato` do `RedatorAgent` continuam como caminho paralelo — aposentar
tudo de vez quando o avulso migrar (conecta com #34, duas trilhas de orçamento, e
#49, RedatorAgent sem template de peça). **(b)** A seção 4 da proposta (entregáveis)
reusa a descrição do passo — falta um campo `entregavel` explícito por `RotaPasso`
para o produto de cada etapa. **(c)** Não há UI neste PR para editar o perfil emissor
do tenant (`tenant.settings["issuer"]`) nem as parcelas estruturadas
(`proposals.payment_installments`) — hoje via API/seed; o consultor precisa da tela.
**(d)** A migration `f1a7c2d9e4b6` (tenant.settings + proposals.payment_installments)
é aditiva e precisa rodar em prod no deploy. **Origem:** S5-B (2026-07-19). Ver ADR-029.

**69. Assinatura eletrônica externa do contrato (gov.br / Clicksign / DocuSign).** O
S5-C fechou a Ficha 07 com assinatura MANUAL (MVP): o consultor registra "assinado em
<data>" com upload opcional do PDF já assinado (`app/api/v1/contracts.py:/assinar`,
ADR-030). Falta a integração externa que colhe a assinatura DENTRO do fluxo — envio ao
signatário, coleta da assinatura eletrônica com validade jurídica (ICP-Brasil/gov.br),
webhook de retorno marcando `signed_at` automaticamente. **O que destrava:** provider de
assinatura plugável (mesmo padrão do `WhatsAppProvider`/#35), estado `awaiting_signature`
entre `sent` e `signed`, e webhook. **Correlato:** a migration `c3e9b1d7f4a2`
(`signed_registered_by_user_id` + `signed_pdf_storage_key` em `contracts`) é aditiva e
precisa rodar em prod no deploy; e o `Process.closed_at` marca o fecho da Ficha, mas
`ProcessStatus.concluido` (eixo operacional pós-contrato/MVP2) não é setado
automaticamente por decisão consciente (eixos desacoplados). **Origem:** S5-C
(2026-07-19). Ver ADR-030.

## Fechadas (histórico — não revoga, só comprova fechamento)

| # | Item | Fechada em | Como |
|---|---|---|---|
| **1** | Diagnóstico não consome `chain_data["auditor_imovel"]` | 2026-05-25 (PROMPT_4 Onda A) | `_consume_auditor_findings()` em `app/agents/diagnostico.py` — findings viram `Divergencia` + `Risco` com `grau` 4-níveis preservado. Commit `f93b4b4`. |
| **2** | "Humano assina" — ciclo do Princípio 1 (camada 1) | 2026-05-25 (PROMPT_4 Onda B) | `PATCH /api/v1/processes/{id}/diagnoses/{version}/validate` grava `validated_by_user_id` + `validated_at` + AuditLog hash chain SHA-256. 409 ao revalidar. Commit `c74ff2e`. *(A camada 2 — 5 botões P4 — continua aberta, pós-PROMPT_5.)* |
| **3** | Remodelar `RegulatoryIssue` (família + codigo_alerta + 4 níveis) | 2026-05-25 (PROMPT_5 Onda A) | Enum `RegulatoryFamilia` (11 estável) + model `RegulatoryIssueCatalog` (PK = codigo_alerta string; catálogo evolutivo via INSERT, NÃO migration) + colunas `codigo_alerta`/`familia`/`muda_rota_regulatoria`/`muda_escopo_preco_prazo`/`documentos_cruzados` em `RegulatoryIssue`. `severity` passa para 4 níveis. Migration `c1b2d3e4f5a7` cria, popula 45 entradas seed (via `app/models/regulatory_catalog_seed.py`, fonte única) e migra dados antigos. `type` legado fica nullable (deprecated). |
| **4** | Mapeamento `grade` 4→`severity` 3 que colapsava alto+crítico | 2026-05-25 (PROMPT_5 Onda A) | `_GRADE_TO_SEVERITY` removido de `property_audit.py`. `AuditFinding.grade` e `RegulatoryIssue.severity` agora compartilham 4 níveis (`informativo`/`atencao`/`alto`/`critico`). Auditor emite codigos reais (📄) e grade direto; 🛰️/🔌 ficam no catálogo mas não emitidos até infra. Diagnóstico mapeia `familia` (11) → `RiscoCategoria` (7) via `_FAMILIA_TO_CATEGORIA` (substitui `_FINDING_TYPE_TO_CATEGORIA` do PROMPT_4). |
| **5** | Reconciliar `status_saneamento` × `status` do auditor × `decisao_consultor` (3 status circulantes) | 2026-05-26 (PROMPT_6 — Opção A do RECONCILIACAO_STATUS_ALERTAS) | 3 enums novos: `StatusAchado` (5 valores), `DecisaoConsultor` (os 5 botões P4), `StatusSaneamento` (5 valores). 5 colunas em `RegulatoryIssue`: `status_achado` (NOT NULL default `suspeita`), `decisao_consultor` (nullable), `decisao_consultor_justificativa`, `decisao_consultor_at`, `status_saneamento` (NOT NULL default `pendente`). PATCH `/properties/{prop}/issues/{id}` edita com AuditLog granular por campo. Gate no PATCH `/validate` rejeita 422 se houver crítica sem decisão (camada 2 do Princípio 1 fechada). Migration `d2c3e4f5a6b8`. |
| **Camada 2 P1** | 5 botões da P4 — decisão obrigatória por alerta crítico antes da assinatura | 2026-05-26 (PROMPT_6) | `decisao_consultor` enum com os 5 valores + gate no `PATCH /validate` retornando 422 com lista de pendentes. Frontend dos botões fica para rodada futura (UI consome `RegulatoryIssueOut` + PATCH). |
| **19** | Justificativa obrigatória para `ignorar_justificado` e `fora_escopo` (camada 2 completa) | 2026-05-26 (revisão pós-PROMPT_6) | `@model_validator` no `RegulatoryIssueUpdate` rejeita 422 quando `decisao_consultor in {ignorar_justificado, fora_escopo}` no body sem `justificativa` preenchida (str_strip cuida de strings só-espaços). Aplica APENAS quando `decisao_consultor` está no body — PATCH parcial que só toca outros campos não força re-confirmação. 5 testes em `TestUpdatePropertyIssueJustificativaObrigatoria`. PROMPT_7 migrou o validator para `ProcessIssueDecisionCreate` (mesma regra, schema novo). |
| **20** | Re-modelar `decisao_consultor` como entidade contextual ao processo (ADR-012) | 2026-05-26 (PROMPT_7) | Nova entidade `ProcessIssueDecision` (FK composta `(process_id, issue_id)` unique). Campos `decisao`/`justificativa`/`decided_at`/`decided_by_user_id` (renomeados em relação ao PROMPT_6; `decided_by_user_id` é novo). Migration `e3d4f5g6a7b8` cria tabela e dropa as 3 colunas do `RegulatoryIssue` (drop sem backfill — sem dados em prod). Endpoints novos: `GET` e `PUT /api/v1/processes/{pid}/issues/{iid}/decision` com upsert + AuditLog granular por campo (hash chain SHA-256). Gate `PATCH /validate` cruza issues críticas × `ProcessIssueDecision` deste processo. Validator de justificativa obrigatória migrou para o schema novo. Cada processo recomeça do zero (titularidade torta pesa diferente para venda e para crédito). `TestProcessIssueDecision` (11 testes novos) + `test_decisao_de_outro_processo_nao_libera_gate` confirma comportamento contextual. |
| **17** | Coerência entre os status reconciliados | 2026-05-26 (PROMPT_8) | Helper puro `app/services/regulatory_coherence.py` com 2 regras semânticas (escopo fechado, sem máquina de estados completa). **Regra A — perenes:** `assert_status_coerente(status_achado, status_saneamento)` exige `status_achado in {confirmada, resolvida}` quando `status_saneamento in {em_validacao, saneado}`. Aplicada (i) no `@model_validator` do `RegulatoryIssueUpdate` (fast-fail quando os 2 status vêm juntos no body) e (ii) no endpoint `PATCH /properties/.../issues/{id}` sobre o estado **resultante** (fonte da verdade — cobre PATCH parcial). **Regra B — cross-entidade:** `assert_decisao_permitida(status_achado)` rejeita `PUT /processes/.../decision` quando `status_achado == suspeita`. Mensagens de erro acionáveis: a primeira cita `confirmada`/`resolvida`, a segunda diz "Confirme ou descarte o achado antes de decidir". Sem migration (validação, não modelagem). `TestCoerenciaStatusPerene` (7 testes) + `TestDecisaoBloqueadaSeAchadoSuspeita` (3 testes). Suite 635/635 verde. |
| **23** | Gate camada 2 cobrando decisão em achado terminal (trap revelado pós-PROMPT_9) | 2026-05-26 (PROMPT_10, corrigido por PROMPT_11) | Gate de `PATCH /diagnoses/{version}/validate` filtra `status_achado in {suspeita, confirmada, ignorada}` — só `descartada` ("não é divergência real") e `resolvida` ("corrigida no mundo") são excluídas, pois nelas não há o que decidir. **PROMPT_11 corrigiu a versão original do #10**, que excluía `ignorada` por erro de simetria: `ignorada` significa "achado REAL posto de lado" e setá-la via `PATCH /issues` não exige justificativa — excluí-la abriria atalho pra silenciar crítico real sem registro, recriando a porta que o #19 fechou. Quem quer ignorar registra `decisao=ignorar_justificado` (com justificativa, #19); a Regra B permite porque `ignorada` ≠ `suspeita`. `suspeita` permanece pra forçar adjudicação antes de assinar (não é deadlock). `resolved_at IS NULL` mantido como critério ortogonal. Testes no `TestValidateDiagnosisGateCamada2`: `descartada`/`resolvida` liberam; `suspeita`/`confirmada`/`ignorada` continuam exigindo (422). Sem migration, sem ADR. **Follow-on aberto:** badge "N pendentes" do `DiagnosisAssinatura` (PROMPT_9) precisa espelhar a mesma exclusão (`descartada`/`resolvida`) pra não super-contar. |
| **12** | `PROJECT_NAME='Amigão'` em `config.py:52` | 2026-05-23 (Fase 0) | Já estava `"Regente Ambiental"` quando a Fase 0 auditou. Commit `7877652` documentou. |
| **24** | Upload de documento não casava com item do checklist + UI de exclusão sem cascata (ciclo de teste travado) | 2026-05-28 (`fix/upload-checklist-binding`) | (i) `DocumentConfirmRequest` ganhou `checklist_item_id?: str`; `confirm_upload` persiste a coluna e chama `auto_link_document` quando o `document_type` casa com um item pendente. (ii) `ProcessChecklist.handleReceived` passa `item.document_id` no PATCH. (iii) `DocumentsTab` renderiza `Object.entries(AIJob.result)` em `<dl>` (antes era só badge sem dado). (iv) Cascade delete service `app/services/cascade_delete.py` + endpoints `GET /{clients,properties}/{id}/delete-preview` + `DELETE` com cascata em ordem segura (RESTRICT-friendly) + `AuditLog cascade_deleted` com hash chain SHA-256 (LGPD); nunca toca doc de outro cliente. (v) Modais de confirmação em Clients/Properties listam contagens exatas antes de confirmar. Suite 186 testes verde, tsc verde. Sem migration. |
| **Sintoma "card discorda do diagnóstico assinado"** | Card lia só `completion_pct` enquanto `RegulatoryDiagnosis.validated_at` ficava em outro bloco; nem `can_advance_macroetapa` cobrava assinatura | 2026-05-28 (`fix/diagnostico-propaga-estado`) | `compute_macroetapa_state` e `can_advance_macroetapa` ganharam kwargs `current_macroetapa` + `diagnosis_validated` — etapa de diagnóstico vira `aguardando_validacao` enquanto não houver assinatura, e o gate de saída cobra o `validated_at`. `PATCH /processes/{id}/diagnoses/{version}/validate` chama `advance_macroetapa` automaticamente quando o gate passa (mesmo critério do botão manual: docs obrigatórios + checklist 100% + agora assinatura). Conservador: NÃO toca `Process.status` nem consolida as 2 chains — isso é o **eixo 3** (dívida nova **#26**, abaixo). Kanban (`processes.py`) consulta uma única vez o set de `process_id` com `RegulatoryDiagnosis.validated_at IS NOT NULL` para evitar N+1. 4 testes unitários (`tests/models/test_macroetapa_gate.py`) + 3 de API (`TestValidateAdvancesMacroetapa`). |
| **25** | Extrator no-op silencioso + sem caminho de extração por processo | 2026-05-28 (`fix/extrator-por-processo`) | Novo `POST /api/v1/processes/{id}/extract` enfileira `workers.run_agent(extrator)` para docs com `extracted_text` cacheado e `workers.ocr_then_extract` (chain OCR→extrator) para docs sem texto, com `force=true` opcional pra re-OCR. `AuditLog(action="extractor_dispatched")` rastreia o disparo. Mensagens do `ExtratorAgent` ganharam orientação acionável (apontam pro endpoint novo) — tanto o `reason` do skipped sem args quanto o `ValueError` quando `document_id` existe mas `extracted_text` é NULL. UI: card do `extrator` no `/agents` agora mostra "Rodar no processo #N" (disabled sem ID); Step 4 do `IntakeWizard` trava avanço se há docs sem leitura disparada; `DraftDocumentUploader` ganha botão 🗑 por linha (habilitado pra `ocr_status` em `{null, pending}`). Sem migration. 3 testes novos em `tests/api/test_processes.py` + 1 em `tests/agents/test_extrator_cache.py`. Suite verde (9 do processes / 4 do extrator). **Marco condicional:** o `_dispatch_extrator` em `app/workers/ocr_tasks.py` ainda passa `process_id=None` ao `run_agent` — `AIJob` resultante perde o link com o processo no caminho da chain OCR. Fora do escopo deste PR; abrir nova dívida se isso passar a doer. |
| **Eixo 2 workflow/RAG** | Silent failure de workflow sem template + RAG sem filtro estruturado por tipo | 2026-05-29 | `knowledge_catalog.search(demand_type=...)` filtra via `LegislationDocument.demand_types`; `LegislacaoAgent` usa o filtro; `apply_workflow_template` levanta `TemplateNotFoundError`; API retorna 422 acionável; enum `DemandType` expandido com 5 valores. |
| **Frente D** | Cripto de segredos por usuário (white label LLM + credenciais de portal) | 2026-05-28 (ADR-014) | Padrão Fernet (AES-128-CBC + HMAC-SHA256): módulo `app/core/encryption.py` (`get_fernet`/`encrypt_str`/`decrypt_str` com MultiFernet pra rotação), type decorator `EncryptedString` em `app/models/types.py`, `CREDENTIAL_ENCRYPTION_KEY` obrigatória (falha no startup, sem fallback), `tools/gen_encryption_key.py`. 8 testes verdes. **Nenhuma coluna real alterada** — aplicação fica pra dívida #27 (PR 2.3 + PR LLM). |
| **40** | Dois `SKILL.md` inválidos silenciosamente ignorados (skills não injetadas) | 2026-06-01 (`fix/skills-frontmatter-40`) | Corrigido **só o front-matter** dos 2 arquivos (corpo de domínio intacto). `diagnostico/situacao_ambiental_imovel_rural/SKILL.md`: adicionado `agent: diagnostico`, `name` ganhou prefixo `diagnostico/`, `applies_to` virou mapping `{uf: [GO, MS, MT]}`, `version` em string. `auditor_imovel/analise_divergencias_documentais/SKILL.md`: `name` ganhou prefixo, `applies_to` (era string) virou `{doc_types: []}` (não restringe), a string descritiva e o campo `movimento` viraram `description`. **Provado rodando** (container api): `discover_skills()` lista as 2 **sem warning** de `SkillParseError`, `load_skill()` retorna `SkillContent` para ambas, e `DiagnosticoAgent._compose_system_with_skills()` com `ctx.metadata={"uf":"MS"}` injeta o corpo da skill (55 KB) entre `<!-- skills:start -->`/`<!-- skills:end -->`. Controle negativo: sem `uf` não injeta → virou dívida **#44** (ligada à #38). Auditor segue determinístico (`prompt_slugs=[]`, sem LLM) — skill entra no catálogo mas não é injetada. 26 testes de skills verdes. Docx Word duplicados movidos de `docs/skills/` para `docs/_archive/skills-fontes-word/`. |
| **27** | Aplicar `EncryptedString` em colunas reais | 2026-05-30 (PR LLM + PR 2.3) | **PR LLM:** chave de IA do consultor cifrada em `User.preferences['ai']['api_key_encrypted']` (JSONB, via `encrypt_str`). **PR 2.3:** modelo `Credential` (tabela `credentials`) com `password_encrypted` usando o type decorator `EncryptedString` — **primeiro uso real em coluna de tabela**. Cofre de logins de portais por cliente (SEMA/IBAMA/SICAR/INCRA/banco), CRUD tenant-scoped, AuditLog hash chain, senha nunca em plaintext na API (verificado por SQL nos testes). Migration `c0d1e2f3a4b5` também **reunificou 2 heads do Alembic** (PROMPT_7 `e3d4f5g6a7b8` + PR 2.2 `e6f7a8b9c0d1`, ambas de `d2c3e4f5a6b8`) que quebravam `alembic upgrade head`. |
| **Gap `seen_this_run` em `generate_acoes_from_divergencias`** | Colisão de `dedupe_key` intra-run (separador ingênuo no sha1: `hint="a\|b", field="c"` ≡ `hint="a", field="b\|c"`) adicionava 2 `Acao` com a mesma chave no MESMO flush → `uq_acoes_tenant_dedupe` estourava e derrubava a consolidação inteira | 2026-07-03 (Sprint 3 — selo, ADR-022) | Guard `seen_this_run` no loop (mesmo padrão do `generate_acoes_from_diagnosis`); regressão coberta em `tests/services/test_acao_generator_divergencias.py` (colisão intra-run → 1 ação, sem IntegrityError; idempotência entre runs preservada). Gap medido no diagnóstico read-only do sprint; régua "o sprint toca o arquivo" aplicada. |
| **Storage R2 + Redis SSL + download silencioso** | OCR não lia o doc ("no_bytes" sem causa) + evento realtime quebrado em prod | 2026-06-01 (`fix/storage-r2-region-redis`) | **Causa raiz (provada no Render Shell):** clients boto3 com `region_name="us-east-1"` hardcoded — R2 exige `region="auto"`, senão o scope SigV4 não bate no GET server-side → `SignatureDoesNotMatch` (o upload presigned tolerava → arquivo subia mas nunca era lido). **Agravante:** `download_bytes` engolia **todo** `ClientError` e retornava `b""`, mascarando o `SignatureDoesNotMatch` como `no_bytes` genérico por semanas. **Fix:** `S3_REGION` (default `"auto"`, configurável) nos 2 clients; `download_bytes` retorna `b""` só para NoSuchKey/404 e re-levanta `StorageDownloadError(code)` com log ERROR para o resto; `ocr_then_extract` registra `storage_error:<code>` (não `no_bytes`). **+Redis:** `redis_url_safe` normaliza `ssl_cert_reqs` (env trazia `CERT_REQUIRED`, redis-py espera `required`) → evento realtime publica; Celery seta `broker_use_ssl` só em `rediss://`. **+Endpoint:** `_with_scheme` respeita `MINIO_SECURE` (https sem scheme na env). Provado rodando local: round-trip MinIO com `region=auto` (sem regressão), `SignatureDoesNotMatch` agora levanta, repro+fix do CERT do Redis, 20 testes verdes. E2E contra R2 real: snippet pronto pro Render Shell. **Lição:** nunca capturar exceção de I/O e retornar vazio — distinguir "ausente" (NoSuchKey → `b""`) de "falhou" (re-levanta com o código). Doc: `docs/trabalhos/storage_r2_redis.md`. **NÃO fecha #42** (bucket presigned — bug distinto). |

---

*Atualizar este registro ao fim de cada sprint. Itens fechados vão para a tabela acima,
não se apagam — comprova o trajeto e ajuda auditoria. Ver
`docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.*
