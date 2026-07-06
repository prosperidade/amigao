# Registro de dívidas — Regente (consolidado pós-PROMPT_11 · 2026-05-26)

Reúne num lugar só as dívidas que estavam espalhadas por relatórios do agente, rodapés de skill,
memórias do desenvolvedor e análises de coordenação. Ordenadas por prioridade de desbloqueio.
Cada item: o que é, de onde veio, o que destrava, e o estado.

> **Convenção de governança:** este documento é VIVO (`docs/REGISTRO_DIVIDAS.md`) — atualizado ao
> fim de cada sprint. Itens fechados saem para a seção "Fechadas (histórico)" abaixo; não somem.
> Ver `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md` para a regra.

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

**44. OCR Gemini multipágina é sequencial (1 call/página) e sensível a 503.** O fix de
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

**44. A chain não propaga `uf` ao `ctx.metadata` do diagnóstico (skill base só casa com `uf` presente).**
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
