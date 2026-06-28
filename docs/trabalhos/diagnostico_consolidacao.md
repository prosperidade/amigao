# Diagnóstico — por que a Consolidação não grava a base

> **PR de diagnóstico.** Nenhum código de produção foi alterado. Só medição,
> leitura e queries read-only (Supabase prod `diquycxxkfrjhxtrcmzb`).
> Data: 2026-06-28 · Caso medido: **process 13** (Fazenda São Jorge, Leonardo
> Ribeiro, `property_id=10`, tenant 1) — o caso que a sócia testou.

---

## VEREDITO (uma frase)

**A consolidação NUNCA executou** — o botão "Consolidar na base" fica
**desabilitado** enquanto existir ≥1 campo `divergente_transcricao`, e o caso
tem **1** não resolvido (campo 452, denominação da matrícula 4698); logo o
staging aceito nunca chega à base e Matrícula/Área/RL/APP seguem "—". **O furo
é de GRAVAÇÃO (gate de UI bloqueando o disparo), não de leitura.**

Prova dura: `SELECT count(*) FROM audit_logs WHERE action='consolidar'` = **0**
em todo o banco; `SELECT count(*) FROM matriculas` = **0**; nenhuma `properties`
com `field_sources` preenchido. O #73 (Hub deriva das matrículas) está correto
no `main`, mas não tem o que ler porque a escrita nunca aconteceu.

---

## Mapa do fluxo real (com o ponto de quebra marcado)

```
  staging (aceito)            BOTÃO              endpoint            base            Hub
 ┌───────────────┐      ┌──────────────┐    ┌────────────┐    ┌──────────┐    ┌──────────┐
 │ 27 linhas     │      │ "Consolidar  │    │ POST .../  │    │ Property │    │ /properties│
 │ status=aceito │─────▶│  na base"    │───▶│ consolidar │───▶│ Matricula│───▶│ /hub-summary│
 │ (process 13)  │      │              │    │            │    │          │    │            │
 └───────────────┘      └──────┬───────┘    └────────────┘    └──────────┘    └──────────┘
                               │
                       ╳╳╳ QUEBRA AQUI ╳╳╳
        disabled = (pendentesObrig > 0)   ← 1 campo divergente_transcricao
        ConsolidacaoPanel.tsx:201          (campo 452, matrícula 4698)
        → clique não dispara nada → endpoint nunca é chamado
        → base nunca recebe escrita → Hub deriva de Matricula vazia → "—"
```

O staging tem munição (27 aceitos, destinos válidos). O endpoint e o serviço de
gravação estão corretos e plugados. **Tudo trava no gate de UI antes do disparo.**

---

## Respostas com evidência

### 1. Caminho do botão (componente → endpoint → serviço)

- **Componente:** `frontend/src/pages/Processes/ConsolidacaoPanel.tsx`, renderizado
  dentro da aba Alertas (`AlertasTab.tsx:39`). O botão rotulado **"Consolidar na
  base"** (`ConsolidacaoPanel.tsx:206`) é o que a sócia chama de "Confirmar e
  gravar na base" — é o **único** botão de gravação na base no frontend (grep por
  `gravar|consolidar|Confirmar` confirma; os demais `validate` são de
  diagnóstico/artefato/ação, fluxos distintos).
- **Chamada:** `consolidate.mutate()` → `api.post('/processes/${processId}/consolidar', {})`
  (`ConsolidacaoPanel.tsx:90`).
- **Endpoint:** `POST /processes/{id}/consolidar` →
  `app/api/v1/processes.py:1146` → chama
  `staging_consolidation.consolidate_process()`.
- **Está plugado? SIM.** O caminho existe e está correto ponta a ponta.
- **Porém o botão está GATED:**
  `disabled={consolidate.isPending || pendentesObrig > 0}` (`ConsolidacaoPanel.tsx:201`),
  onde `pendentesObrig = fields.filter(f => f.status === 'divergente_transcricao').length`
  (`:96`). Com ≥1 divergente de transcrição, o botão fica desabilitado/cinza e o
  clique **não dispara a mutation**.

### 2. O que o endpoint /consolidar faz hoje

`consolidate_process()` (`app/services/staging_consolidation.py:282`), determinístico
e idempotente:

1. Carrega o `Process`, o `Client` (via `process.client_id`) e o `Property`
   (via `process.property_id`).
2. Lê **somente** `ExtractedFieldStaging` com `status='aceito'` (`:295-304`).
   `pendente`/`rejeitado`/`divergente_*` são ignorados.
3. Agrupa por destino `(entity, [matricula_hint], target_field)`; descarta
   `decided_value IS NULL` (achados de divergente_fundo) e valores nulos (`:320-334`).
4. Faz **upsert idempotente de `Matricula`** por `matricula_hint` (`_upsert_matricula`,
   `:476`) e grava campo a campo em `Client` / `Property` / `Matricula` via
   `_write_entity` (`:408`), respeitando allowlists (`_CLIENTE_FIELDS`,
   `_IMOVEL_FIELDS`, `_MATRICULA_FIELDS`) e marcando `field_sources[col]="human_validated"`.
5. **NÃO grava `Property.total_area_ha`** (área é derivada da soma das matrículas —
   `_IMOVEL_FIELDS` não inclui `total_area_ha`).
6. Grava `AuditLog action='consolidar'` **apenas se houve `writes` ou
   `reconciliacoes`** (`:386-392`).

O serviço está correto. O problema não está aqui — ele simplesmente **nunca é
chamado** para o process 13.

### 3. Estado do staging no caso real (process 13)

```
status                  | count
------------------------+------
aceito                  |  27
pendente                |  51
rejeitado               |   6
divergente_transcricao  |   1   ← bloqueia o botão
```

Os 27 aceitos têm destinos **válidos e consolidáveis**, ex.:
`imovel.car_code`, `imovel.car_status`, `imovel.area_grafica_ha`,
`imovel.municipality`; `matricula.area_ha` / `denominacao_imovel` /
`codigo_incra_sncr` / `averbacao_app` para os hints **2923, 4655, 4698, 6776**.
**Há munição de sobra para consolidar.**

O único `divergente_transcricao` é o **campo 452**:
`source_doc_type=matricula`, `target_entity=matricula`,
`target_field=denominacao_imovel`, `matricula_hint=4698`,
`field_value={"value":"FAZENDA SÃO JORGE – GLEBA 01 B"}`. Nunca foi decidido
(não há `staging_decidir` para field 452 no audit) → o gate nunca foi liberado.

### 4. A base depois da tentativa

- **`properties` id=10:** `registry_number=null`, `total_area_ha=null`,
  `app_area_ha=null`, `rl_status=null`, `area_grafica_ha=null`,
  `field_sources={}` (vazio). Só tem `car_code`/`municipality`/`state`, que vêm
  do **intake**, não da consolidação.
- **`matriculas` where property_id=10:** **0 linhas.**
- **Global:** `count(matriculas)=0` no banco inteiro; nenhuma `property` com
  `field_sources` preenchido.

→ **A base está vazia do lado da gravação.** Não é leitura do Hub — não há o que
ler. O furo está **antes** da escrita.

### 5. De onde o Hub LÊ cada campo (cruzado com (4))

`get_property_hub_summary()` (`app/api/v1/properties.py:281`), header montado em `:389-425`:

| Campo Hub        | Lê de                                                   | Consolidação grava aí? |
|------------------|---------------------------------------------------------|------------------------|
| **Matrícula**    | `prop.registry_number` **OU** `"; ".join` dos `numero_matricula` das `Matricula` (`:394-396`) | via `Matricula` (upsert) |
| **Área total**   | `prop.total_area_ha` **OU** `prop.area_total_matriculas()` = soma das matrículas (`:397-398`, `property.py:65`) | via `Matricula.area_ha` |
| **RL (rl_status)** | `prop.rl_status` (`:418`) | **NÃO** — ver gap 2 abaixo |
| **APP (app_area_ha)** | `prop.app_area_ha` (`:419`) | sim em tese (`_IMOVEL_FIELDS`), mas **sem staging-alvo** — ver gap 2 |

A derivação do #73 (Matrícula/Área a partir de `Matricula`) está **correta no
`main`** e alinhada com onde a consolidação grava. Como há **0 matrículas**, ela
deriva vazio → "—". Confirma: o Hub está certo; falta a escrita a montante.

### 6. Deploy — o #73 está em produção?

- `#73` mergeado no `main` (commit `9c3fe77`, sob o HEAD atual `f25648f`). É código
  Python puro de leitura (derivação no Hub) — **sem migration** associada.
- A tabela `matriculas` **existe** em prod (as queries rodaram). A infra de
  consolidação está deployada.
- **Deploy NÃO é a causa raiz.** A prova independe da versão: mesmo o código
  *anterior* ao #73 criaria linhas em `Matricula` ao consolidar, e há **0**
  matrículas em todo o banco. Logo a consolidação nunca rodou — qualquer que seja
  a versão no ar. (O #73 corrige a *leitura*; o que falta é o *disparo da escrita*.)

### 7. Divergências bloqueiam a gravação dos consistentes?

**Indiretamente, sim — e esse é o ponto.** No backend, `consolidate_process`
ignora corretamente os divergentes (só lê `status='aceito'`); um divergente não
impediria a gravação dos aceitos **se o endpoint fosse chamado**. Mas a **UI** usa
um gate de tudo-ou-nada: 1 `divergente_transcricao` em qualquer campo desabilita o
botão inteiro (`disabled = pendentesObrig > 0`, `ConsolidacaoPanel.tsx:201`). Ou
seja, **1 divergência de transcrição de um único campo de matrícula impede a
consolidação dos outros 27 campos já aceitos.** É o bloqueio efetivo.

---

## Gaps secundários (não são a causa raiz, mas o fix deve considerar)

- **Gap 1 — Gate de UI tudo-ou-nada.** Resolver o campo 452 (escolher_fonte /
  editar) libera o botão e a consolidação deve popular Matrícula + Área. Esse é o
  desbloqueio imediato do caso. A decisão de design (gate global vs. consolidar só
  os aceitos deixando o divergente pendente) é tua a desenhar.
- **Gap 2 — RL e APP no Hub continuarão "—" mesmo após consolidar.**
  - `rl_status` **não está** em `_IMOVEL_FIELDS` (`staging_consolidation.py:56`) e
    não há staging-alvo `imovel.rl_status`. A info de RL no caso vive como
    `matricula.averbacao_rl`. O Hub lê `prop.rl_status` → fica "—".
  - `app_area_ha` está em `_IMOVEL_FIELDS`, mas **não há** linha de staging
    aceita com alvo `imovel.app_area_ha`; a info de APP do caso é
    `matricula.averbacao_app` (hint 6776). O Hub lê `prop.app_area_ha` → fica "—".
  - Ou seja, há um **descasamento de mapeamento**: APP/RL chegam no nível de
    **matrícula**, mas o Hub os exibe no nível de **imóvel**. Mesmo com a
    consolidação rodando, esses dois campos não sobem sem ponte matrícula→imóvel
    (ou leitura do Hub a partir da matrícula).
- **Obs — `imovel.modulos_fiscais`** (campo 442, aceito) não existe como coluna em
  `_IMOVEL_FIELDS`/`Property` → cairá em `ignorados` na consolidação (inofensivo,
  mas não persiste).

---

## Como reproduzir as medições (read-only)

```sql
-- consolidação nunca rodou
SELECT count(*) FROM audit_logs WHERE action='consolidar';            -- 0
-- base vazia
SELECT count(*) FROM matriculas;                                      -- 0
SELECT registry_number, total_area_ha, field_sources FROM properties WHERE id=10;
-- staging do caso
SELECT status, count(*) FROM extracted_field_staging WHERE process_id=13 GROUP BY status;
-- o divergente que trava o botão
SELECT id, target_field, matricula_hint, field_value
FROM extracted_field_staging WHERE process_id=13 AND status='divergente_transcricao';
```
