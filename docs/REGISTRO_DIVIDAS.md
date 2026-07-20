# Registro de dívidas — Regente (consolidado pós-PROMPT_11 · 2026-05-26)

Reúne num lugar só as dívidas que estavam espalhadas por relatórios do agente, rodapés de skill,
memórias do desenvolvedor e análises de coordenação. Ordenadas por prioridade de desbloqueio.
Cada item: o que é, de onde veio, o que destrava, e o estado.

> **Convenção de governança:** este documento é VIVO (`docs/REGISTRO_DIVIDAS.md`) — atualizado ao
> fim de cada sprint. Itens fechados saem para a seção "Fechadas (histórico)" abaixo; não somem.
> Ver `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.

> **PRÓXIMO NÚMERO LIVRE: 79.** (#78 aberta pela dívida #70,
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

**74. Ficha 08 §4 — campos-âncora registrais novos.** Livro, Folha, Ficha, NIRF/CIB,
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
