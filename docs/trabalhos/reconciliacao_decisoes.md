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

### Resultado — medido em 11/09/2026 (Frente J, `fix/fechamento-contrato-spec`)

**Fonte:** Supabase MCP, só leitura (`SELECT`), projeto `diquycxxkfrjhxtrcmzb`,
tabela `extracted_field_staging`, `process_id = 23` — as 116 linhas inteiras
(sem a chave `ancora` de `field_value`, que é só rastro de posição no texto)
alimentadas em `build_decisions` **localmente**, com o código desta branch
(`reconciliation_decisions.py` de `fix/fechamento-contrato-spec` — a mesma
função pura que `GET /processes/23/staging-decisions` chama em produção).
Nada escrito, nada clicado, nada consolidado.

**Antes × depois da rodada 1 (re-extração de 546-550, texto cacheado):**

| | antes (10/09) | depois (11/09) |
|---|---|---|
| linhas de staging | 42 | **116** (42 de 08/09 intactas + 74 novas de 11/09) |
| com `tipo_observacao` | 0 | **57** (hipoteca 20 · baixa 11 · compra_venda 6 · alienação fiduciária 4 · georreferenciamento 3 · arrendamento 3 · aditivo 3 · não classificado 3 · reserva legal 2 · compromisso 2) |
| com `vigencia` derivada | 0 | 29 (vigente 17 · baixado 8 · expirado 2 · retificado 2) |
| aceitas pela Isis (08/09) | 28 | **28 — as mesmas, por id, status intacto** |
| gravadas (`consolidated_at`) | 0 | 0 |
| decisões | 11 | **21** |
| `sem_agrupamento` | 27 | **66** |
| soma | 42 | 50 (cobertas por decisão) + 66 = **116, nenhuma linha perdida** |

**Por documento:** 546 (CAR) 12 · 547 (M3.181) 27 · 548 (M3.313) 33 ·
549 (M3.673) 28 · 550 (M4.387) 16 · 551 (CNH-e) 0 — o doc 551 continua sem
linha (dívida #223, OCR vazio; agora `lifecycle_status = erro_leitura`, não
mais "lido").

**O que a rodada 1 fez aparecer, como a Frente I previa:**

- **RL como decisão, por matrícula** — `matricula:3181:reserva_legal`
  (185,856 ha, AV.03 da 3.181 — o exemplo literal do #221/ADR-065, que na
  extração antiga estava preso em `averbacao_app`) e `matricula:3673:reserva_legal`
  (492,9252 ha, AV.02). E a decisão do IMÓVEL `imovel:23:reserva_legal_total`:
  CAR declara 437,7632 ha × soma das matrículas — **divergem, crítico** (fonte
  única registral). Antes: uma evidência só, "fonte única", sem confronto.
- **Gravames como decisão, por matrícula** — 4 decisões (3181: 4 atos;
  3313: 11; 3673: 4; 4387: 5), cada ato com a vigência derivada
  (`R.06: baixado; R-10: retificado; …`; `AV.03/04/05: baixado; R.15: vigente`
  na 3.673 — zero hipotecas vigentes, como o texto do doc 549 afirma).
- **Titularidade por matrícula** (PR #165, cadeia real) — 4 decisões:
  3181 → ELODI (R-09), 3673 → ELODI (R-13), 4387 → ELODI (R-01); **3313 →
  "IZAURA DE FATIMA PEGO (ato R-11)"**. Este último é a ELODI pelo R-20 do doc
  548 (ADR-065 cita R-11 e R-20 como compra e venda desta matrícula): a
  extração desta rodada só nomeou `adquirentes` no R-11 — o R-20 saiu sem os
  dois lados distinguidos. Não é regra errada: é a não-determinação da entrada
  (`CONFIRMACAO_ENTRADA_2026-09-09.md`) — registrado para a Isis conferir na
  tela e decidir (item 5 desta frente: o tipo/valor é editável na decisão).
- **`composicao` ×4 continuam pendentes** — e agora com 2–3 evidências cada
  (CAR + certidão [+ nova linha da re-extração]). Nenhuma foi consolidada
  ainda; quando a certidão antiga (aceita) for gravada e a nova ficar
  pendente, o estado será `parcialmente_gravada` (item 2), não "gravada".
- **`sem_agrupamento` = 66**: 25 observações tipadas sem chave natural
  (georreferenciamento, arrendamento, baixa, aditivo, compromisso, não
  classificado — eventos/observações que a Frente G deliberadamente não
  agrupa), 7 `nirf_cib`, 5 `cartorio`, 5 `denominacao`, 4 `registro_anterior`,
  4 `codigo_certificacao`, 4 `onus` (a linha agregada de gravames vigentes por
  matrícula — coluna `onus_gravames`), 4 `proprietarios`, 2 `averbacao_app`
  (extração antiga, 08/09), e 1 de cada: município, UF, `app_declarada_ha`,
  `denominacao_anterior`, `modulos_fiscais`, `registro_livro_folha`. Todos
  visíveis na Conferência campo a campo; nenhum some.

### Decisões (21) — `build_decisions` sobre as 116 linhas reais, código de `fix/fechamento-contrato-spec`

| # | chave | label | evidências (staging_id · doc · campo/ato · valor normalizado · vigência · tipo · status) | concordância | nível | estado | valor proposto |
|---|---|---|---|---|---|---|---|
| 1 | `imovel:23:area_total` | Área total do imóvel | 1552 · car · total_area_ha · 2180.8267 · — · — · aceito<br>1593 · car · area_documental_ha · 2180.3923 · — · — · pendente<br>calc · calculado · soma_matriculas · 2180.3923 · — · — · calculado | concordam | informativo (0.02%) | pendente | 2180.8267 |
| 2 | `imovel:23:car` | CAR (número/status) | 1551 · car · car_code · GO-5200605-82E5.AE14.076B.4637.9900.9C9D · — · — · aceito · **fonte autoritativa** | fonte_unica | — | decidida | GO-5200605-82E5.AE14.076B.4637.9900.9C9D.EC86.D700 |
| 3 | `imovel:23:reserva_legal_total` | Reserva Legal do imóvel | 1556 · car · rl_status · 437.7632 · — · — · aceito<br>calc · calculado · soma_matriculas · 678.7812 · — · — · calculado | divergem | critico (35.51%) | decidida | 437.7632 |
| 4 | `matricula:3181:area` | Área — matrícula 3181 | 1563 · matricula · area_ha · 926.3654 · — · — · aceito · **fonte autoritativa** | fonte_unica | — | decidida | 926.3654 |
| 5 | `matricula:3181:composicao` | Matrícula 3181 integra o imóvel | 1557 · car · numero_matricula · {"data": "01/10/2013", "numero": "3181", · — · — · pendente<br>1561 · matricula · numero_matricula · 3181 · — · — · aceito · **fonte autoritativa** | concordam | — | pendente | 3181 |
| 6 | `matricula:3181:gravames` | Gravames vigentes — matrícula 3181 | 1606 · matricula · R.06 · baixado · baixado · hipoteca · pendente · **fonte autoritativa**<br>1609 · matricula · R-10 · retificado · retificado · hipoteca · pendente · **fonte autoritativa**<br>1611 · matricula · R-12 · retificado · retificado · hipoteca · pendente · **fonte autoritativa**<br>1615 · matricula · R-16 · vigente · vigente · alienacao_fiduciaria · pendente · **fonte autoritativa** | concordam | — | pendente | R.06: baixado; R-10: retificado; R-12: retificado; R-16: vigente |
| 7 | `matricula:3181:reserva_legal` | Reserva Legal — matrícula 3181 | 1603 · matricula · averbacao_rl · 185.856 · vigente · reserva_legal · pendente · **fonte autoritativa** | fonte_unica | — | pendente | 185.856 |
| 8 | `matricula:3181:titularidade` | Titularidade | 1602 · matricula · R-02 · ALEXANDRE AUGUSTO CLEMENTE (adquirente) · — · compra_venda · pendente · **fonte autoritativa**<br>1602 · matricula · R-02 · VERA LÚCIA BRAUN GALVÃO (transmitente) · — · compra_venda · pendente · **fonte autoritativa**<br>1608 · matricula · R-09 · ELODI AGROPECUÁRIA (adquirente) · — · compra_venda · pendente · **fonte autoritativa**<br>1608 · matricula · R-09 · ALEXANDRE AUGUSTO CLEMENTE (transmitente · — · compra_venda · pendente · **fonte autoritativa** | concordam | — | pendente | ELODI AGROPECUÁRIA (ato R-09) |
| 9 | `matricula:3313:area` | Área — matrícula 3313 | 1568 · matricula · area_ha · 725.4663 · — · — · aceito · **fonte autoritativa** | fonte_unica | — | decidida | 725.4663 |
| 10 | `matricula:3313:composicao` | Matrícula 3313 integra o imóvel | 1559 · car · numero_matricula · {"data": "23/01/2014", "numero": "3.313" · — · — · pendente<br>1566 · matricula · numero_matricula · 3.313 · — · — · aceito · **fonte autoritativa** | concordam | — | pendente | 3.313 |
| 11 | `matricula:3313:gravames` | Gravames vigentes — matrícula 3313 | 1620 · matricula · AV.02 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1621 · matricula · AV.03 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1622 · matricula · AV.04 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1623 · matricula · AV.05 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1624 · matricula · AV.06 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1625 · matricula · AV.07 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1626 · matricula · AV.08 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1630 · matricula · R-23 · baixado · baixado · hipoteca · pendente · **fonte autoritativa**<br>1631 · matricula · R-24 · baixado · baixado · hipoteca · pendente · **fonte autoritativa**<br>1632 · matricula · R-25 · baixado · baixado · hipoteca · pendente · **fonte autoritativa**<br>1633 · matricula · R-26 · baixado · baixado · hipoteca · pendente · **fonte autoritativa** | concordam | — | pendente | AV.02: vigente; AV.03: vigente; AV.04: vigente; AV.05: vigente; AV.06: |
| 12 | `matricula:3313:titularidade` | Titularidade | 1629 · matricula · R-11 · IZAURA DE FATIMA PEGO (adquirente) · — · compra_venda · pendente · **fonte autoritativa**<br>1629 · matricula · R-11 · SONIA INÊS GONDIM (transmitente) · — · compra_venda · pendente · **fonte autoritativa** | concordam | — | pendente | IZAURA DE FATIMA PEGO (ato R-11) |
| 13 | `matricula:3673:area` | Área — matrícula 3673 | 1578 · matricula · area_ha · 212.3553 · — · — · aceito · **fonte autoritativa** | fonte_unica | — | decidida | 212.3553 |
| 14 | `matricula:3673:composicao` | Matrícula 3673 integra o imóvel | 1560 · car · numero_matricula · {"data": "10/02/2016", "numero": "3.673" · — · — · pendente<br>1576 · matricula · numero_matricula · 3673 · — · — · aceito · **fonte autoritativa**<br>1640 · matricula · numero_matricula · 3.673 · — · — · pendente · **fonte autoritativa** | concordam | — | pendente | 3673 |
| 15 | `matricula:3673:gravames` | Gravames vigentes — matrícula 3673 | 1646 · matricula · AV.03 · baixado · baixado · hipoteca · pendente · **fonte autoritativa**<br>1647 · matricula · AV.04 · baixado · baixado · hipoteca · pendente · **fonte autoritativa**<br>1648 · matricula · AV.05 · baixado · baixado · hipoteca · pendente · **fonte autoritativa**<br>1658 · matricula · R.15 · vigente · vigente · alienacao_fiduciaria · pendente · **fonte autoritativa** | concordam | — | pendente | AV.03: baixado; AV.04: baixado; AV.05: baixado; R.15: vigente |
| 16 | `matricula:3673:reserva_legal` | Reserva Legal — matrícula 3673 | 1645 · matricula · averbacao_rl · 492.9252 · vigente · reserva_legal · pendente · **fonte autoritativa** | fonte_unica | — | pendente | 492.9252 |
| 17 | `matricula:3673:titularidade` | Titularidade | 1654 · matricula · R-11 · ALEXANDRE AUGUSTO CLEMENTE (adquirente) · — · compra_venda · pendente · **fonte autoritativa**<br>1654 · matricula · R-11 · KARINA SANTAROSA CLEMENTE (adquirente) · — · compra_venda · pendente · **fonte autoritativa**<br>1654 · matricula · R-11 · Nascente Agro-industrial Ltda (transmite · — · compra_venda · pendente · **fonte autoritativa**<br>1656 · matricula · R-13 · ELODI AGROPECUÁRIA (adquirente) · — · compra_venda · pendente · **fonte autoritativa**<br>1656 · matricula · R-13 · ALEXANDRE AUGUSTO CLEMENTE (transmitente · — · compra_venda · pendente · **fonte autoritativa**<br>1656 · matricula · R-13 · KARINA SANTAROSA CLEMENTE (transmitente) · — · compra_venda · pendente · **fonte autoritativa** | concordam | — | pendente | ELODI AGROPECUÁRIA (ato R-13) |
| 18 | `matricula:4387:area` | Área — matrícula 4387 | 1587 · matricula · area_ha · 316.2053 · — · — · aceito · **fonte autoritativa** | fonte_unica | — | decidida | 316.2053 |
| 19 | `matricula:4387:composicao` | Matrícula 4387 integra o imóvel | 1558 · car · numero_matricula · {"data": "22/04/2020", "numero": "4.387" · — · — · pendente<br>1585 · matricula · numero_matricula · 4387 · — · — · aceito · **fonte autoritativa**<br>1659 · matricula · numero_matricula · 4.387 · — · — · pendente · **fonte autoritativa** | concordam | — | pendente | 4387 |
| 20 | `matricula:4387:gravames` | Gravames vigentes — matrícula 4387 | 1662 · matricula · R-02 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1663 · matricula · R-03 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1664 · matricula · R-04 · vigente · vigente · hipoteca · pendente · **fonte autoritativa**<br>1665 · matricula · R.05 · vigente · vigente · alienacao_fiduciaria · pendente · **fonte autoritativa**<br>1666 · matricula · R.06 · vigente · vigente · alienacao_fiduciaria · pendente · **fonte autoritativa** | concordam | — | pendente | R-02: vigente; R-03: vigente; R-04: vigente; R.05: vigente; R.06: vige |
| 21 | `matricula:4387:titularidade` | Titularidade | 1661 · matricula · R-01 · ELODI AGROPECUÁRIA (adquirente) · — · compra_venda · pendente · **fonte autoritativa**<br>1661 · matricula · R-01 · Nascente Agro-industrial Ltda (transmite · — · compra_venda · pendente · **fonte autoritativa** | concordam | — | pendente | ELODI AGROPECUÁRIA (ato R-01) |

`staging_ids` cobertos pelas decisões: **50** — 1551, 1552, 1556, 1557, 1558, 1559, 1560, 1561, 1563, 1566, 1568, 1576, 1578, 1585, 1587, 1593, 1602, 1603, 1606, 1608, 1609, 1611, 1615, 1620, 1621, 1622, 1623, 1624, 1625, 1626, 1629, 1630, 1631, 1632, 1633, 1640, 1645, 1646, 1647, 1648, 1654, 1656, 1658, 1659, 1661, 1662, 1663, 1664, 1665, 1666

### Sem agrupamento (66) — visíveis, decididas campo a campo

| staging_id | doc | source_doc_type | field_name | target | matricula_hint | tipo_observacao | valor (resumo) | status | motivo |
|---|---|---|---|---|---|---|---|---|---|
| 1553 | 546 | car | municipio | imovel.municipality | — | — | Alto Paraíso de Goiás | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1554 | 546 | car | uf | imovel.state | — | — | Goiás | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1555 | 546 | car | app_declarada_ha | imovel.app_area_ha | — | — | 90,4225 | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1562 | 547 | matricula | cartorio | matricula.cartorio | 3181 | — | Registro de Imóveis de Alto Paraíso de Goiás | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1564 | 547 | matricula | denominacao | matricula.denominacao_imovel | 3181 | — | UMA GLEBA DE TERRAS | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1565 | 547 | matricula | nirf_cib | matricula.nirf_cib | 3181 | — | 050.041.396.737-1 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1567 | 548 | matricula | cartorio | matricula.cartorio | 3313 | — | Registro de Imóveis de Alto Paraíso de Goiás | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1569 | 548 | matricula | denominacao | matricula.denominacao_imovel | 3313 | — | FAZENDA NOVO HORIZONTE II | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1570 | 548 | matricula | denominacao_anterior | matricula.denominacao_anterior | 3313 | — | FAZENDA OLHOS D`ÁGUA | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1571 | 548 | matricula | registro_anterior | matricula.registro_anterior | 3313 | — | 1908 | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1572 | 548 | matricula | averbacao_app | matricula.averbacao_app | 3313 | — | {"area": "50", "referencia": "Averba-se para constar o  | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1573 | 548 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 3313 | — | 281310000060-08 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1574 | 548 | matricula | nirf_cib | matricula.nirf_cib | 3313 | — | 4.078.154-2 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1575 | 548 | matricula | onus | matricula.onus_gravames | 3313 | — | [{"tipo": "Hipoteca", "valor": "R$ 1.200.000,00", "cred | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1577 | 549 | matricula | cartorio | matricula.cartorio | 3673 | — | Registro de Imóveis de Alto Paraíso de Goiás | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1579 | 549 | matricula | denominacao | matricula.denominacao_imovel | 3673 | — | Fazenda "POSSE OU PORCOS - GLEBA 4" | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1580 | 549 | matricula | registro_anterior | matricula.registro_anterior | 3673 | — | 3.669 | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1581 | 549 | matricula | averbacao_app | matricula.averbacao_app | 3673 | — | {"area": "42,8070", "referencia": "Reserva Legal"} | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1582 | 549 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 3673 | — | ed59189a-9c02-4322-bc6a-9e2906de3105 | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1583 | 549 | matricula | nirf_cib | matricula.nirf_cib | 3673 | — | 6.442.022-1 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1584 | 549 | matricula | onus | matricula.onus_gravames | 3673 | — | [{"tipo": "Hipoteca", "valor": "R$ 657.000,00", "credor | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1586 | 550 | matricula | cartorio | matricula.cartorio | 4387 | — | Registro de Imóveis de Alto Paraíso de Goiás | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1588 | 550 | matricula | denominacao | matricula.denominacao_imovel | 4387 | — | UMA GLEBA DE TERRAS, situada na Fazenda "POSSE OU PORCO | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1589 | 550 | matricula | registro_anterior | matricula.registro_anterior | 4387 | — | 3.672 | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1590 | 550 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 4387 | — | 295d1b3b-993c-4ac1-bfbe-d567d1cfd0a7 | aceito | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1591 | 550 | matricula | nirf_cib | matricula.nirf_cib | 4387 | — | 9.475.495-0 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1592 | 550 | matricula | onus | matricula.onus_gravames | 4387 | — | [{"tipo": "Hipoteca de 1º Grau", "valor": "R$ 2.123.994 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1594 | 546 | car | modulos_fiscais | imovel.modulos_fiscais | — | — | 31,1547 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1595 | 547 | matricula | registro_livro_folha | matricula.registro_livro_folha_ficha | 3181 | — | 2-D, ás fls. vº941 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1596 | 547 | matricula | cartorio | matricula.cartorio | 3181 | — | Registro de Imóveis, Titulos e Documentos, das Pessoas  | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1597 | 547 | matricula | registro_anterior | matricula.registro_anterior | 3181 | — | 1039 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1598 | 547 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 3181 | — | 281308000084-73 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1599 | 547 | matricula | nirf_cib | matricula.nirf_cib | 3181 | — | 2.974.457-1 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1600 | 547 | matricula | proprietarios | matricula.proprietarios | 3181 | — | [{"cpf": null, "nome": null}, {"cpf": "088.957.081-72", | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1601 | 547 | matricula | observacao | —.— | 3181 | georreferenciamento | AV-01 · Georreferenciamento · 15/08/2013 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1604 | 547 | matricula | observacao | —.— | 3181 | arrendamento | AV.04 · Arrendamento · 200ha ha · 16/10/2012 a 16/10/20 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1605 | 547 | matricula | observacao | —.— | 3181 | arrendamento | AV.05 · Arrendamento · 100,00ha ha · R$ 20,17 · 17/06/2 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1607 | 547 | matricula | observacao | —.— | 3181 | baixa | AV.08 · Baixa · 18 de junho de 2018 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1610 | 547 | matricula | observacao | —.— | 3181 | aditivo | AV.11 · Aditivo · 21 de setembro de 2018 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1612 | 547 | matricula | observacao | —.— | 3181 | aditivo | AV.13 · Aditivo · 17 de setembro de 2019 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1613 | 547 | matricula | observacao | —.— | 3181 | aditivo | AV.14 · Aditivo · 02 de julho de 2020 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1614 | 547 | matricula | observacao | —.— | 3181 | baixa | AV.15 · Baixa · 25 de fevereiro de 2021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1616 | 547 | matricula | onus | matricula.onus_gravames | 3181 | — | [{"ato": "R-10", "tipo": "Hipoteca", "partes": ["BANCO  | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1617 | 548 | matricula | nirf_cib | matricula.nirf_cib | 3313 | — | 000.027.341.088-0 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1618 | 548 | matricula | proprietarios | matricula.proprietarios | 3313 | — | [{"cpf": "283.621.361-20", "nome": "SONIA INÊS GONDIM"} | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1619 | 548 | matricula | observacao | —.— | 3313 | georreferenciamento | AV.01 · Georreferenciamento · data não especificada | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1627 | 548 | matricula | observacao | —.— | 3313 | compromisso_compra_venda | AV.09 · Compromisso de compra e venda · 04/09/2008 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1628 | 548 | matricula | observacao | —.— | 3313 | arrendamento | AV.10 · Arrendamento · 50 hectares ha · 15 anos · 30 de | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1634 | 548 | matricula | observacao | —.— | 3313 | baixa | AV.27 · Baixa · 23 DE DEZEMBRO DE 2.021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1635 | 548 | matricula | observacao | —.— | 3313 | baixa | AV.28 · Baixa · 23 DE DEZEMBRO DE 2.021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1636 | 548 | matricula | observacao | —.— | 3313 | baixa | AV.29 · Baixa · 23 DE DEZEMBRO DE 2.021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1637 | 548 | matricula | observacao | —.— | 3313 | baixa | AV.30 · Baixa · 23 DE DEZEMBRO DE 2.021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1638 | 548 | matricula | observacao | —.— | 3313 | baixa | AV.31 · Baixa · 23 DE DEZEMBRO DE 2.021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1639 | 548 | matricula | observacao | —.— | 3313 | baixa | AV.32 · Baixa · 23 DE DEZEMBRO DE 2.021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1641 | 549 | matricula | denominacao | matricula.denominacao_imovel | 3673 | — | UMA GLEBA DE TERRAS, situada na Fazenda "POSSE OU PORCO | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1642 | 549 | matricula | nirf_cib | matricula.nirf_cib | 3673 | — | 6.816.752-0 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1643 | 549 | matricula | proprietarios | matricula.proprietarios | 3673 | — | [{"cpf": "25.078.411/0001-20", "nome": "Nascente Agro-i | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1644 | 549 | matricula | observacao | —.— | 3673 | georreferenciamento | AV.01 · Georreferenciamento · 10 DE FEVEREIRO DE 2016 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1649 | 549 | matricula | observacao | —.— | 3673 | compromisso_compra_venda | AV.06 · Compromisso de compra e venda · 212,6931 ha · 1 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1650 | 549 | matricula | observacao | —.— | 3673 | nao_classificado | AV.07 · Ato não classificado · 13 DE FEVEREIRO DE 2013 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1651 | 549 | matricula | observacao | —.— | 3673 | nao_classificado | AV.08 · Ato não classificado · 26 DE AGOSTO DE 2016 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1652 | 549 | matricula | observacao | —.— | 3673 | baixa | AV.09 · Baixa · 16 DE MARÇO DE 2017 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1653 | 549 | matricula | observacao | —.— | 3673 | baixa | AV.10 · Baixa · 16 DE MARÇO DE 2017 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1655 | 549 | matricula | observacao | —.— | 3673 | baixa | AV.12 · Baixa · 21 DE AGOSTO DE 2019 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1657 | 549 | matricula | observacao | —.— | 3673 | nao_classificado | AV.14 · Ato não classificado · 25 DE FEVEREIRO DE 2021 | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |
| 1660 | 550 | matricula | proprietarios | matricula.proprietarios | 4387 | — | [{"cpf": "25.078.411/0001-20", "nome": "Nascente Agro-i | pendente | tipo sem chave natural mapeada nesta frente — decide-se camp |

### As 116 linhas, por id

| id | doc | tipo doc | field_name | target | hint | tipo_observacao | status | decidida em | gravada | criada em | decisão |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1551 | 546 | car | numero_car | imovel.car_code | — | — | aceito | 2026-09-08 | não | 2026-09-08 | imovel:23:car |
| 1552 | 546 | car | area_declarada_ha | imovel.total_area_ha | — | — | aceito | 2026-09-08 | não | 2026-09-08 | imovel:23:area_total |
| 1553 | 546 | car | municipio | imovel.municipality | — | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1554 | 546 | car | uf | imovel.state | — | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1555 | 546 | car | app_declarada_ha | imovel.app_area_ha | — | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1556 | 546 | car | rl_declarada_ha | imovel.rl_status | — | — | aceito | 2026-09-08 | não | 2026-09-08 | imovel:23:reserva_legal_total |
| 1557 | 546 | car | matricula_listada | matricula.numero_matricula | 3181 | — | pendente | — | não | 2026-09-08 | matricula:3181:composicao |
| 1558 | 546 | car | matricula_listada | matricula.numero_matricula | 4387 | — | pendente | — | não | 2026-09-08 | matricula:4387:composicao |
| 1559 | 546 | car | matricula_listada | matricula.numero_matricula | 3313 | — | pendente | — | não | 2026-09-08 | matricula:3313:composicao |
| 1560 | 546 | car | matricula_listada | matricula.numero_matricula | 3673 | — | pendente | — | não | 2026-09-08 | matricula:3673:composicao |
| 1561 | 547 | matricula | numero_matricula | matricula.numero_matricula | 3181 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:3181:composicao |
| 1562 | 547 | matricula | cartorio | matricula.cartorio | 3181 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1563 | 547 | matricula | area_registrada_ha | matricula.area_ha | 3181 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:3181:area |
| 1564 | 547 | matricula | denominacao | matricula.denominacao_imovel | 3181 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1565 | 547 | matricula | nirf_cib | matricula.nirf_cib | 3181 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1566 | 548 | matricula | numero_matricula | matricula.numero_matricula | 3313 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:3313:composicao |
| 1567 | 548 | matricula | cartorio | matricula.cartorio | 3313 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1568 | 548 | matricula | area_registrada_ha | matricula.area_ha | 3313 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:3313:area |
| 1569 | 548 | matricula | denominacao | matricula.denominacao_imovel | 3313 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1570 | 548 | matricula | denominacao_anterior | matricula.denominacao_anterior | 3313 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1571 | 548 | matricula | registro_anterior | matricula.registro_anterior | 3313 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1572 | 548 | matricula | averbacao_app | matricula.averbacao_app | 3313 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1573 | 548 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 3313 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1574 | 548 | matricula | nirf_cib | matricula.nirf_cib | 3313 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1575 | 548 | matricula | onus | matricula.onus_gravames | 3313 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1576 | 549 | matricula | numero_matricula | matricula.numero_matricula | 3673 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:3673:composicao |
| 1577 | 549 | matricula | cartorio | matricula.cartorio | 3673 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1578 | 549 | matricula | area_registrada_ha | matricula.area_ha | 3673 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:3673:area |
| 1579 | 549 | matricula | denominacao | matricula.denominacao_imovel | 3673 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1580 | 549 | matricula | registro_anterior | matricula.registro_anterior | 3673 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1581 | 549 | matricula | averbacao_app | matricula.averbacao_app | 3673 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1582 | 549 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 3673 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1583 | 549 | matricula | nirf_cib | matricula.nirf_cib | 3673 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1584 | 549 | matricula | onus | matricula.onus_gravames | 3673 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1585 | 550 | matricula | numero_matricula | matricula.numero_matricula | 4387 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:4387:composicao |
| 1586 | 550 | matricula | cartorio | matricula.cartorio | 4387 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1587 | 550 | matricula | area_registrada_ha | matricula.area_ha | 4387 | — | aceito | 2026-09-08 | não | 2026-09-08 | matricula:4387:area |
| 1588 | 550 | matricula | denominacao | matricula.denominacao_imovel | 4387 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1589 | 550 | matricula | registro_anterior | matricula.registro_anterior | 4387 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1590 | 550 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 4387 | — | aceito | 2026-09-08 | não | 2026-09-08 | sem agrupamento |
| 1591 | 550 | matricula | nirf_cib | matricula.nirf_cib | 4387 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1592 | 550 | matricula | onus | matricula.onus_gravames | 4387 | — | pendente | — | não | 2026-09-08 | sem agrupamento |
| 1593 | 546 | car | area_documental_ha | imovel.area_documental_ha | — | — | pendente | — | não | 2026-09-11 | imovel:23:area_total |
| 1594 | 546 | car | modulos_fiscais | imovel.modulos_fiscais | — | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1595 | 547 | matricula | registro_livro_folha | matricula.registro_livro_folha_ficha | 3181 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1596 | 547 | matricula | cartorio | matricula.cartorio | 3181 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1597 | 547 | matricula | registro_anterior | matricula.registro_anterior | 3181 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1598 | 547 | matricula | codigo_certificacao | matricula.geo_certificacao_codigo | 3181 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1599 | 547 | matricula | nirf_cib | matricula.nirf_cib | 3181 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1600 | 547 | matricula | proprietarios | matricula.proprietarios | 3181 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1601 | 547 | matricula | observacao | —.— | 3181 | georreferenciamento | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1602 | 547 | matricula | observacao | —.— | 3181 | compra_venda | pendente | — | não | 2026-09-11 | matricula:3181:titularidade |
| 1603 | 547 | matricula | averbacao_rl | matricula.averbacao_rl | 3181 | reserva_legal | pendente | — | não | 2026-09-11 | matricula:3181:reserva_legal |
| 1604 | 547 | matricula | observacao | —.— | 3181 | arrendamento | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1605 | 547 | matricula | observacao | —.— | 3181 | arrendamento | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1606 | 547 | matricula | observacao | —.— | 3181 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3181:gravames |
| 1607 | 547 | matricula | observacao | —.— | 3181 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1608 | 547 | matricula | observacao | —.— | 3181 | compra_venda | pendente | — | não | 2026-09-11 | matricula:3181:titularidade |
| 1609 | 547 | matricula | observacao | —.— | 3181 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3181:gravames |
| 1610 | 547 | matricula | observacao | —.— | 3181 | aditivo | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1611 | 547 | matricula | observacao | —.— | 3181 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3181:gravames |
| 1612 | 547 | matricula | observacao | —.— | 3181 | aditivo | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1613 | 547 | matricula | observacao | —.— | 3181 | aditivo | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1614 | 547 | matricula | observacao | —.— | 3181 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1615 | 547 | matricula | observacao | —.— | 3181 | alienacao_fiduciaria | pendente | — | não | 2026-09-11 | matricula:3181:gravames |
| 1616 | 547 | matricula | onus | matricula.onus_gravames | 3181 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1617 | 548 | matricula | nirf_cib | matricula.nirf_cib | 3313 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1618 | 548 | matricula | proprietarios | matricula.proprietarios | 3313 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1619 | 548 | matricula | observacao | —.— | 3313 | georreferenciamento | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1620 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1621 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1622 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1623 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1624 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1625 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1626 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1627 | 548 | matricula | observacao | —.— | 3313 | compromisso_compra_venda | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1628 | 548 | matricula | observacao | —.— | 3313 | arrendamento | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1629 | 548 | matricula | observacao | —.— | 3313 | compra_venda | pendente | — | não | 2026-09-11 | matricula:3313:titularidade |
| 1630 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1631 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1632 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1633 | 548 | matricula | observacao | —.— | 3313 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3313:gravames |
| 1634 | 548 | matricula | observacao | —.— | 3313 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1635 | 548 | matricula | observacao | —.— | 3313 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1636 | 548 | matricula | observacao | —.— | 3313 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1637 | 548 | matricula | observacao | —.— | 3313 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1638 | 548 | matricula | observacao | —.— | 3313 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1639 | 548 | matricula | observacao | —.— | 3313 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1640 | 549 | matricula | numero_matricula | matricula.numero_matricula | 3673 | — | pendente | — | não | 2026-09-11 | matricula:3673:composicao |
| 1641 | 549 | matricula | denominacao | matricula.denominacao_imovel | 3673 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1642 | 549 | matricula | nirf_cib | matricula.nirf_cib | 3673 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1643 | 549 | matricula | proprietarios | matricula.proprietarios | 3673 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1644 | 549 | matricula | observacao | —.— | 3673 | georreferenciamento | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1645 | 549 | matricula | averbacao_rl | matricula.averbacao_rl | 3673 | reserva_legal | pendente | — | não | 2026-09-11 | matricula:3673:reserva_legal |
| 1646 | 549 | matricula | observacao | —.— | 3673 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3673:gravames |
| 1647 | 549 | matricula | observacao | —.— | 3673 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3673:gravames |
| 1648 | 549 | matricula | observacao | —.— | 3673 | hipoteca | pendente | — | não | 2026-09-11 | matricula:3673:gravames |
| 1649 | 549 | matricula | observacao | —.— | 3673 | compromisso_compra_venda | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1650 | 549 | matricula | observacao | —.— | 3673 | nao_classificado | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1651 | 549 | matricula | observacao | —.— | 3673 | nao_classificado | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1652 | 549 | matricula | observacao | —.— | 3673 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1653 | 549 | matricula | observacao | —.— | 3673 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1654 | 549 | matricula | observacao | —.— | 3673 | compra_venda | pendente | — | não | 2026-09-11 | matricula:3673:titularidade |
| 1655 | 549 | matricula | observacao | —.— | 3673 | baixa | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1656 | 549 | matricula | observacao | —.— | 3673 | compra_venda | pendente | — | não | 2026-09-11 | matricula:3673:titularidade |
| 1657 | 549 | matricula | observacao | —.— | 3673 | nao_classificado | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1658 | 549 | matricula | observacao | —.— | 3673 | alienacao_fiduciaria | pendente | — | não | 2026-09-11 | matricula:3673:gravames |
| 1659 | 550 | matricula | numero_matricula | matricula.numero_matricula | 4387 | — | pendente | — | não | 2026-09-11 | matricula:4387:composicao |
| 1660 | 550 | matricula | proprietarios | matricula.proprietarios | 4387 | — | pendente | — | não | 2026-09-11 | sem agrupamento |
| 1661 | 550 | matricula | observacao | —.— | 4387 | compra_venda | pendente | — | não | 2026-09-11 | matricula:4387:titularidade |
| 1662 | 550 | matricula | observacao | —.— | 4387 | hipoteca | pendente | — | não | 2026-09-11 | matricula:4387:gravames |
| 1663 | 550 | matricula | observacao | —.— | 4387 | hipoteca | pendente | — | não | 2026-09-11 | matricula:4387:gravames |
| 1664 | 550 | matricula | observacao | —.— | 4387 | hipoteca | pendente | — | não | 2026-09-11 | matricula:4387:gravames |
| 1665 | 550 | matricula | observacao | —.— | 4387 | alienacao_fiduciaria | pendente | — | não | 2026-09-11 | matricula:4387:gravames |
| 1666 | 550 | matricula | observacao | —.— | 4387 | alienacao_fiduciaria | pendente | — | não | 2026-09-11 | matricula:4387:gravames |

### Rodada 2 (11/09/2026) — tentativa de OCR forçado do doc 551, BLOQUEADA

Escopo autorizado: só o doc 551 (dívida #223). Passo 1 executado; passos 2-6
não executados — bloqueio de credencial, não de dado ou de decisão.

**1. Backup do doc 551** (Supabase MCP, read-only, projeto `diquycxxkfrjhxtrcmzb`):

| campo | valor |
|---|---|
| `id` / `process_id` / `client_id` / `property_id` | 551 / 23 / 20 / 18 |
| `original_file_name` | `CNH-e.pdf.pdf` |
| `storage_key` | `tenant_1/process_23/993ec255-0659-4318-bb5e-f5b87b7b2844.pdf` |
| `file_size_bytes` / `checksum_sha256` | 284319 / `35f2e7e6f5ab30c799226d88ac92ccdb518149466e4a4c5fba231bdf9ae180e2` |
| `document_type` / `document_category` | `doc_pessoal` / `societarios` |
| `ocr_status` / `confidence_score` | `done` / 0.95 |
| `extraction_status` (antes) | "recebido, não processado (doc_pessoal) — revisar: OCR não extraiu texto legível deste documento (provável PDF de imagem) — reprocessar o OCR; sem texto não há o que extrair" |
| `extracted_text` (444 chars, íntegro) | "QR-CODE\nDocumento assinado com certificado digital em conformidade com a Medida Provisória nº 2200-2/2001. Sua validade poderá ser confirmada por meio do programa Assinador Serpro. As orientações para instalar o Assinador Serpro e realizar a validação do documento digital estão disponíveis em: https://www.serpro.gov.br/assinador-digital. REPÚBLICA FEDERATIVA DO BRASIL MINISTÉRIO DOS TRANSPORTES SECRETARIA NACIONAL DE TRÂNSITO - SENATRAN" |
| `extracted_at` / `updated_at` | 2026-09-08 00:55:33 UTC / 2026-09-11 04:01:20 UTC |

Confere com o medido na pré-condição (#223) — nada mudou desde 11/09 cedo.

**2. HEAD no R2 — não executado.** Esta sessão não tem as credenciais de
storage de produção: o `.env` local aponta para MinIO dev (`localhost:9000`),
e `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`/`MINIO_SERVER` de produção são
`sync: false` no `render.yaml` — só existem no dashboard do Render, nunca no
repo. Evidência indireta de que o objeto existia: o próprio `ocr_status='done'`
de 08/09 prova que `download_bytes(storage_key)` funcionou naquela data (284319
bytes, checksum gravado). Não foi reverificado hoje.

**3-6. Disparo do `force=True`, leitura do resultado, re-extração, correção
da `extraction_status` — não executados.** A rota que o painel usa
(`POST /api/v1/documents/551/reprocess-ocr`, `app/api/v1/documents.py:447-514`)
exige `Depends(get_current_internal_user)` — um JWT de usuário interno de
produção. Esta sessão não tem login de produção (as credenciais seed do
`CLAUDE.md` são só do banco dev; não há token de serviço/API-key alternativa
no código — conferido em `app/api/deps.py` e afins). Sem esse token não há
como chamar o endpoint nem, portanto, disparar `ocr_then_extract` real.

**O que falta para fechar, literalmente um clique:** André abre o processo
#23 no painel → aba de documentos → `CNH-e.pdf.pdf` (doc 551) → "Reprocessar
OCR". A rota já embute `force=True` (não pede parâmetro) e, em sucesso,
encadeia sozinha o extrator (`ocr_tasks.py:366-367`) — não precisa disparar os
dois passos à mão. Alternativa equivalente: André roda, com o Bearer token da
própria sessão do painel,
`curl -X POST https://api.regenteambiental.com.br/api/v1/documents/551/reprocess-ocr -H "Authorization: Bearer <token>"`.
Depois disso, os passos 4-6 (ler `extracted_text` novo, conferir staging,
`extraction_status`) ficam prontos para rodar nesta mesma sessão ou na
próxima — a leitura pós-fato é só `SELECT`, doutrina já usada nesta e nas
frentes anteriores.

**Dívida #223 permanece aberta** (não fechada por esta tentativa) —
atualização em `docs/REGISTRO_DIVIDAS.md`.

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
