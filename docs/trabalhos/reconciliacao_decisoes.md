# Frente G — reconciliação e Conferência por decisões (medição)

**Branch:** `feat/reconciliacao-decisoes` · **ADR:** 067 · **Dívidas fechadas:** REC-001, CONF-001
**Insumo:** `docs/auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md` §3/§5/§6,
`docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md`
**Data da medição:** 10/09/2026 · **Mergeada em main:** PR #160, `3391402` (10/09/2026 21:21 -03)

---

## ACEITE REAL EM PRODUÇÃO — caso #23, pós-deploy (10/09/2026)

Autorização de merge do André: "pode mergear 160", seguida de pedido explícito
de aceite contra o caso real (não fixture). Medido **só leitura** — nada
consolidado, nada clicado, nenhuma escrita em produção.

### Deploy confirmado

- `GET https://api.regenteambiental.com.br/health` → `200 {"status":"ok",...}`.
- **Prova comportamental de que o código novo está no ar** (Render não expõe
  SHA no `/health`): rota nova sem auth → `401 {"detail":"Not authenticated"}`
  (a rota EXISTE, o gate é de autenticação); rota inexistente de propósito
  (`.../this-route-does-not-exist`) → `404 {"detail":"Not Found"}`. A
  diferença de corpo/código entre as duas provou o deploy de `POST/GET
  /processes/{id}/staging-decisions` sem precisar de token de produção.

### Dados reais (Supabase MCP, read-only — mesma doutrina das frentes C-F: "produção só recebeu SELECT")

`select count(*) from extracted_field_staging where process_id = 23` → **42**
(confirma o número citado em toda a documentação da frente). Todas as 42
linhas foram lidas (`SELECT`, nenhuma escrita) e alimentadas em
`build_decisions` **localmente**, com o código de `main` pós-merge — mesma
função pura que o endpoint em produção chama, resultado idêntico ao que a
Conferência real mostraria.

**Resultado: 11 decisões + 27 em `sem_agrupamento` — soma 15 + 27 = 42, nenhuma linha perdida.**

| decisão | evidências | estado | concordância |
|---|---|---|---|
| `matricula:3181:composicao` — **Matrícula 3181 integra o imóvel** | CAR (`matricula_listada`, pendente) + certidão (`numero_matricula`, **aceito**) | pendente | concordam |
| `matricula:3313:composicao` | CAR (pendente) + certidão (aceito) | pendente | concordam |
| `matricula:3673:composicao` | CAR (pendente) + certidão (aceito) | pendente | concordam |
| `matricula:4387:composicao` | CAR (pendente) + certidão (aceito) | pendente | concordam |
| `matricula:3181:area` | certidão, 926,3654 ha | **decidida** | fonte_unica |
| `matricula:3313:area` | certidão, 725,4663 ha | **decidida** | fonte_unica |
| `matricula:3673:area` | certidão, 212,3553 ha | **decidida** | fonte_unica |
| `matricula:4387:area` | certidão, 316,2053 ha | **decidida** | fonte_unica |
| `imovel:23:area_total` | CAR (2.180,8267 ha) + soma calculada das 4 matrículas (2.180,3923 ha) | **decidida** | concordam (0,02%, informativo) |
| `imovel:23:reserva_legal` | só CAR (437,7632 ha) | **decidida** | fonte_unica |
| `imovel:23:car` | número + status | **decidida** | fonte_unica |

### O caso central (REC-001) confere

Matrícula 3.181: **uma decisão**, não duas linhas — exatamente o sintoma
original (`CONFIRMACAO_ENTRADA_2026-09-09.md`) fechado contra o dado real.

### O que NÃO apareceu como a Frente G descrevia — registrado, não escondido

Contra o **caso real** (não a fixture), três pontos do pedido de aceite não se
confirmaram, e a causa-raiz é a mesma nos três: **as 42 linhas do processo #23
nunca foram re-extraídas desde as Frentes E/F (ADR-065/066)** —
`tipo_observacao`/`atributos` estão `null` em TODAS as 42 linhas. A extração
que está no banco é anterior ao vocabulário tipado.

1. **RL não veio com divergência crítica.** A decisão `reserva_legal` tem
   **uma evidência só** (CAR, 437,7632 ha) — `fonte_unica`, sem confronto. O
   lado da matrícula (a RL de 42,8070 ha da 3.673, o próprio exemplo do bug
   #221/ADR-065 "RL virou `averbacao_app`") está preso no campo antigo
   `averbacao_app` (staging 1581), sem `tipo_observacao=reserva_legal` — a
   regra de chave desta frente não o alcança. Confirmado em
   `sem_agrupamento`: `staging_id=1581 field_name=averbacao_app`.
2. **Gravames não formaram decisão nenhuma.** As três linhas `onus` (1575,
   1584, 1592) são arrays JSON brutos (`[{"tipo":"Hipoteca",...}]`), não
   observações tipadas — caem em `sem_agrupamento` pelo mesmo motivo.
3. **Titularidade e representante não existem entre as 42 linhas.** Não há
   nenhuma linha `target_entity=cliente` nem `representante` no staging do
   processo #23 — o CNPJ/nome da ELODI e o representante Joel não estão
   (mais, ou nunca estiveram) neste conjunto de 42. Nenhuma decisão desses
   dois aspectos existe para o caso real.

**Isto não é falha da regra de agrupamento — é a extração do #23 estar
desatualizada em relação às Frentes E/F.** Uma re-extração dos documentos
546-550 (fora do escopo desta frente e desta verificação, que é só leitura)
alimentaria `tipo_observacao`/`atributos`, e as decisões de RL/gravames
passariam a existir com a mesma mecânica já provada em fixture (ver seção
acima). Registrado para o André decidir se/quando vale reprocessar o #23.

### O estado da decisão sobrevive ao agrupamento — parcialmente confirmado

7 das 11 decisões (`area`×4, `area_total`, `reserva_legal`, `car`) mostram
`estado=decidida`, refletindo os campos que a Isis já aceitou — nenhuma
aceitação anterior regrediu a pendente. **As 4 decisões de `composicao`
(incluindo a 3.181) ficam `pendente`**, não porque o aceite da Isis sumiu —
a evidência da certidão continua com `status=aceito`, visível — mas porque a
OUTRA evidência do grupo (a confirmação do CAR, `matricula_listada`) nunca
foi decidida individualmente na tela antiga (campo que a UI de campo-a-campo
nunca dava destaque de decisão própria). Uma decisão só fica `decidida`
quando TODAS as evidências que a compõem saíram de pendente — é o
comportamento pretendido do ADR-067, não uma regressão do estado da Isis; e é
exatamente o tipo de coisa que a Conferência por decisões torna visível pela
primeira vez (a confirmação do CAR sobre a 3.181 nunca tinha sido
explicitamente revisada).

**Payload bruto** (as 42 linhas lidas via MCP + a saída completa de
`build_decisions`) arquivado nesta sessão, não commitado (dado de produção).

---

## FRENTE I — RE-EXTRAÇÃO DO CASO REAL (11/09/2026)

Objetivo: fechar REC-001/CONF-001 ponta a ponta contra o #23 real — os dois
gaps medidos acima (RL/gravames sem `tipo_observacao` porque o dado nunca foi
re-extraído desde as Frentes E/F) tinham causa raiz conhecida; esta frente
testa a hipótese.

### Pré-condição (medida antes de tocar em produção)

- **Escopo de documentos confirmado**: 546-551 pertencem TODOS ao
  processo #23 (`select process_id from documents where id between 546 and
  551` → 23 nos seis). Docs 544/545 são de Valéria (#22) — descartada uma
  referência cruzada equivocada de um gate anterior que cobria os dois casos
  juntos.
- **INSERT-only confirmado por leitura de código**, não por confiança —
  `app/services/ficha01_extraction.py:1449` (`extract_and_stage`): a única
  mutação é `db_session.add(ExtractedFieldStaging(...))`; nenhum `.update()`/
  `.delete()`; `status`/`decided_value`/`consolidated_at` de linha existente
  nunca são tocados.
- **Bug achado e fechado ANTES de re-extrair** (PR #162): a chave `gravames`
  exigia `target_entity=="matricula"`, mas `observacao_registral.
  DESTINO_POR_TIPO` só mapeia `reserva_legal`/`app` — gravame nunca tem
  destino individual, então nunca carrega `target_entity="matricula"`. Sem
  este fix, a decisão de gravames NUNCA apareceria, dado real ou não. Fixado,
  medido, 18/18 verde, mergeado antes da re-extração.
- **Backup** (read-only, Supabase MCP): `documents` (546-551, 6 linhas) e
  `extracted_field_staging` (processo 23, 42 linhas) com o payload completo;
  `audit_logs` (41 linhas, ids 2056-2109, sessão da Isis em 08/09, hash chain
  íntegra). Arquivos locais, não commitados (dado de produção).

### Escopo fechado para a rodada 1 (decisão do André, 11/09)

- Re-extração de **546-550** (texto CACHEADO, uma execução — sem re-OCR, sem
  `force=True`) disparada pelo painel (Agentes IA → campo "ID do Processo" →
  23 → card do agente Extrator → "Rodar no processo #23"), medida por
  `SELECT` antes/depois.
- **Aceite**: RL como decisão (AV.02 vigente × CAR 437,7632, fonte =
  matrícula), gravames como decisão (0 hipotecas vigentes na 3.673, R.15
  vigente). Composição e áreas por matrícula continuam. 28 linhas aceitas
  intactas por id.
- **Representante e titularidade ficam FORA desta rodada** — fronteira
  declarada, duas dívidas abertas (`docs/REGISTRO_DIVIDAS.md` #223 e #224):
  (a) doc 551 (CNH-e) tem OCR vazio — texto cacheado é só boilerplate de
  assinatura digital, sem nome/CPF; corrigir exige `force=True` (rodada 2,
  autorização separada, custo/risco maiores — chamada Vision real); (b)
  titularidade do cliente PJ não é dado de staging hoje — vem direto do
  `Client`, e `_FIELD_SPECS["car"]` não extrai razão social/CNPJ de
  documento nenhum; decidir com a Isis se vira campo extraído (CAR/CCIR) ou
  se a Conferência passa a ler o cadastro direto.

### Resultado — a preencher após o André disparar a extração no painel

_(seção completada na próxima atualização deste documento, com antes×depois
de linhas de staging, contagem de `tipo_observacao`/vigência/âncora, as 28
aceitas conferidas por id, a lista completa de `build_decisions` pós-
re-extração, e o SHA no ar no momento da medição.)_

---

## Ambiente da medição

| item | valor |
|---|---|
| banco | Testcontainers descartável (mesmo padrão do resto da suíte) — `build_decisions` é pura (não toca o banco); `decidir_decisao_agrupada`/`consolidate_process` escrevem via ORM na sessão de teste |
| entrada | fixture com os valores REAIS já vetados nas Frentes E/F/fiação (`tests/services/test_observacao_registral.py`, `test_fiacao_entrada.py` — docs 546/547/549 da ELODI, extracted_text real de produção) e no próprio ADR-066 (492,9252 × 437,7632 de RL) — não reinventados |
| LLM | nenhum. `build_decisions`/`decidir_decisao_agrupada` são deterministas (mesma doutrina de `staging_consolidation`/`inconsistency_matrix`) |
| produção | **não acessada nesta rodada.** `mcp__Supabase__execute_sql` foi recusado pelo classificador de auto-modo desta sessão (as frentes anteriores usaram o mesmo MCP read-only com sucesso — registrado como limitação da sessão, não da abordagem) |

Script: `tests/services/test_reconciliation_decisions.py` — 14 casos, fixture
única (`_elodi`) reutilizada por todos. Duas execuções de `consolidate_process`
(mesma convenção das frentes anteriores) em `TestDecidirDecisaoAgrupada::
test_estado_evolui_pendente_decidida_gravada`.

---

## A lista completa de decisões da ELODI (fixture, 16 linhas de staging)

`build_decisions` sobre a fixture produziu **10 decisões**, zero linhas em
`sem_agrupamento` — todas as 16 linhas desta fixture foram desenhadas para
casar com uma das 8 regras de chave do ADR-067 (a fixture é um recorte da
ELODI real, não o dump completo de 42 linhas; o caminho `sem_agrupamento` está
coberto por `TestRegressaoFrentesAnteriores` e `TestValeriaPF`, abaixo):

| chave | label | evidências | concordância | nível | estado |
|---|---|---|---|---|---|
| `matricula:3181:composicao` | Matrícula 3181 integra o imóvel | CAR (`matricula_listada`) + certidão (`numero_matricula`) | concordam | — | pendente |
| `matricula:3673:composicao` | Matrícula 3673 integra o imóvel | certidão | fonte_unica | — | pendente |
| `matricula:3313:composicao` | Matrícula 3313 integra o imóvel | certidão | fonte_unica | — | pendente |
| `matricula:3009:composicao` | Matrícula 3009 integra o imóvel | certidão | fonte_unica | — | pendente |
| `matricula:3181:area` | Área — matrícula 3181 | certidão (926,3654 ha) | fonte_unica | — | pendente |
| `imovel:*:reserva_legal` | Reserva Legal | matrícula AV.02 (492,9252 ha, **vigente**, autoritativa) × CAR (437,7632 ha) | **divergem** | **crítico** (11,19%) | pendente |
| `matricula:3673:gravames` | Gravames vigentes — matrícula 3673 | AV.03 (baixado) + R.15 (vigente) | concordam¹ | — | pendente |
| `cliente:*:titularidade` | Titularidade | nome "ELODI AGROPECUARIA" + CNPJ (campos distintos, 1 fonte cada) | fonte_unica | — | pendente |
| `representante:*:identificacao` | Representante | nome "Joel" + CPF (campos distintos, 1 fonte cada) | fonte_unica | — | pendente |
| `imovel:*:car` | CAR (número/status) | número + status (campos distintos, 1 fonte cada) | fonte_unica | — | pendente |

¹ `gravames` nunca compara "valor único" — é síntese dos atos
(`valor_proposto = "AV.03: baixado; R.15: vigente"`); concordância aqui
significa "mais de uma evidência reunida", não "os dois atos dizem a mesma
coisa".

**Contagem diferente de 8, registrada (não forçada):** a fixture soma **10
decisões** para 4 matrículas — "composição de matrículas (4)" já são 4
decisões, uma por matrícula (é exatamente o REC-001: "matrícula 3.181, UMA
decisão", não uma decisão agregada para as 4: `composicao`×4). Some `area`
(1, só 3181 tinha área na fixture), `reserva_legal` (1), `gravames` (1),
`titularidade` (1), `identificacao` (1) e `car` (1) = 4+1+1+1+1+1+1 = 10. A
ELODI real (com área/gravame em TODAS as 4 matrículas, mais `area_total` do
CAR) produziria mais — a tabela do ADR-067 já registra essa divergência de
contagem contra o "8" da narrativa da spec. `area_total` não aparece nesta
fixture: exige evidência do CAR (`area_declarada_ha`/`area_documental_ha`),
que não foi incluída neste recorte — `_injetar_area_total` só monta a decisão
quando ela existe.

**Nenhuma linha perdida:** 16 linhas de staging → 10 decisões cobrindo os 16
`staging_ids` (composicao 2+1+1+1, área 1, RL 2, gravames 2, titularidade 2,
identificação 2, CAR 2 — soma 16) + 0 em `sem_agrupamento`.

### O caso central (REC-001)

Matrícula 3.181: **UMA decisão**, evidência do CAR (`matricula_listada`,
`{"numero": "3181"}`) e da certidão (`numero_matricula`, `"3.181"`) — não duas
linhas a validar separadamente. É o sintoma exato de
`CONFIRMACAO_ENTRADA_2026-09-09.md`.

### Reserva Legal — divergência crítica (fonte = matrícula)

AV.02 (matrícula 3.673, vigente, 492,9252 ha) × RL declarada do CAR (437,7632
ha): diferença de 55,162 ha sobre 492,9252 ha = **11,19%** → `crítico` (régua
>10%). Fonte autoritativa marcada é a **matrícula** (ADR-062: RL averbada é
registral), não o CAR — `valor_proposto = 492.9252`.

### Gravames — matrícula 3.673

AV.03 (hipoteca) → `baixado`; R.15 (alienação fiduciária, Itaú) → `vigente`.
**Zero hipotecas vigentes**, R.15 vigente — uma decisão só, não duas linhas de
ato.

---

## Valéria (#22, PF) — 3 linhas → decisões coerentes com PF

`TestValeriaPF::test_tres_linhas_pf`: nome + CPF + data de nascimento (CNH).
Resultado: **1 decisão** (`titularidade`, 2 evidências: nome + CPF) + **1**
linha em `sem_agrupamento` (`data_nascimento` — sem chave natural nesta
frente, visível, não some). 2 evidências + 1 sem_agrupamento = as 3 linhas,
nenhuma perdida.

---

## Regressão das Frentes C-F (tabela campo × antes × depois)

`TestRegressaoFrentesAnteriores::test_campos_sem_regra_de_chave_aparecem_visiveis`
— campo que a Frente G não modela vira `sem_agrupamento`, com motivo, nunca
escondido; nenhum comportamento das frentes anteriores muda.

| campo (frente que o fechou) | antes (Frente G) | depois (Frente G) |
|---|---|---|
| `cartorio` (matrícula, pré-existente) | linha na Conferência campo a campo | continua igual — `sem_agrupamento`, motivo "tipo sem chave natural mapeada" |
| `modulos_fiscais` (Frente D, fiação) | idem | idem |
| `numero_ccir` (ADR-062 item 7, cadastral) | idem | idem |
| `app_area_ha`/`app_declarada_ha` (Ficha 01) | idem | idem |

`ConsolidacaoPanel.test.tsx` (GATE existente da Frente "Aceito ≠ Gravado",
fixture `cartorio`/`rat_protocolo`) passa **sem alteração** — os dois campos
da fixture não casam com nenhuma chave desta frente, prova de que a mudança é
aditiva (ver ADR-067).

---

## Teste de UI (vitest)

`DecisoesPanel.test.tsx` — 6 casos: agrupa CAR+certidão numa decisão só;
evidências concordantes vêm recolhidas (CONF-001) e expandem ao clique;
divergência vem expandida por padrão com o nível visível; **o gesto** —
decidir grava as linhas agrupadas, e uma montagem nova do componente (mesmo
padrão de "recarregar") lê o mesmo estado do servidor, não um flag otimista
que evaporaria; estado `gravada` mostra "Gravado na base" (mesmo selo da
Frente "Aceito ≠ Gravado"); sem decisões, o painel não renderiza nada (o bloco
`sem_agrupamento` continua na tela antiga do `ConsolidacaoPanel`).

`ConsolidacaoPanel.test.tsx` (3 casos) e o restante de `src/pages/Processes/`
(68 testes, 13 arquivos) passam sem alteração.

---

## Backend — suíte executada

`tests/services/test_reconciliation_decisions.py` (14), `tests/api/
test_staging_decisions.py` (4), mais regressão em `test_consolidacao_integrada.py`,
`test_matriz_perfis_identidade.py`, `test_observacao_registral.py`,
`test_fiacao_entrada.py`, `test_contencao_entrada.py`, `test_fase4_consolidacao.py`,
`test_matricula_staging.py`, `test_gravado_visivel.py`, `test_reabrir_e_vinculo.py`
— 158 testes, 0 falhas. Suíte completa não rodada nesta sessão (economia de
sessão) — os módulos tocados (`app/services/staging_consolidation.py`,
`app/api/v1/processes.py`, novo `app/services/reconciliation_decisions.py`)
estão cobertos; PR abre para o CI completar o resto.
