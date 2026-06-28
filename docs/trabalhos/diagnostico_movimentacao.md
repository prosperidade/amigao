# Diagnóstico — movimentação do card e o encaixe Etapas × Abas × Agentes

> **PR de diagnóstico.** Nenhum código de produção alterado. Só medição, leitura e
> queries read-only (Supabase prod `diquycxxkfrjhxtrcmzb`). Data: 2026-06-28.
> Caso medido: os 2 processos reais do tenant 1 (#13 São Jorge, #8 Romilton).
>
> Nota: o working tree tinha WIP de outra branch (`staging_consolidation.py`,
> `acao_generator.py`) — **não tocado**; este PR commita só este relatório.

---

## VEREDITO (uma frase)

A máquina de 7 etapas **já existe** (enum `Macroetapa` + transições + gate +
mapa agente→etapa), separada do `ProcessStatus` legado; o card não anda porque
**falta o gatilho** (nada liga "rodar agente/terminar chain" a mexer no
checklist ou na macroetapa) **e o checklist nunca é inicializado no intake** —
sem checklist o gate de avanço trava em `False` e nem o avanço manual funciona.
**Não falta estado novo; falta o elo de transição + a inicialização do
checklist.**

---

## Mapa do fluxo real (com o ponto de quebra)

```
 INTAKE                  CARD (coluna = process.macroetapa)              AGENTES
 ┌─────────────┐         ┌──────────────────────────────┐        ┌──────────────┐
 │ cria Process│         │ Quadro /processes/kanban      │        │ run_agent_   │
 │ macroetapa= │────────▶│ agrupa por macroetapa          │        │ chain (worker)│
 │ entrada_dem.│         │ E1│E2│E3│E4│E5│E6│E7           │        └──────┬───────┘
 │ SEM checklist│        └───────────┬──────────────────┘               │
 └─────────────┘                     │                                   │ NÃO mexe
        ╳ FURO 1                      │ avança só por:                    │ em macroetapa
   checklist nunca                    │  (a) POST /macroetapa (humano)    │ nem no checklist
   inicializado                       │      ── gate exige checklist 100% │ (fire-and-forget)
   → gate sempre False                │  (b) auto: assinar diagnóstico    ▼
                                      │      (só nas 2 etapas de diag.)   produz AIJob/StageOutput
                                      │                                   mas o card fica parado
                                      ▼
                        avançar (a) DISPARA a chain  ←── INVERSÃO vs Ficha 07
                        (card move → roda agente),        (Ficha 07: roda agente → card move)
```

Medido: **0 checklists**, **0 avanços de macroetapa**, **0 diagnósticos** — os 2
processos estão congelados em `entrada_demanda`.

---

## A. MÁQUINA DE ESTADOS ATUAL

**Achado central: existem DUAS máquinas paralelas e não sincronizadas.**

### A.1 — Os dois campos

| Campo | Tipo | Transições | Quem move | Usado por |
|---|---|---|---|---|
| `Process.status` | `ProcessStatus` (11 estados) | `VALID_TRANSITIONS` (`process.py:74`) | **humano** via `PATCH /processes/{id}/status` (`processes.py:396`) | filtro do kanban, dossiê, PDFs, resumo IA |
| `Process.macroetapa` | `String`→`Macroetapa` (7 etapas) | `MACROETAPA_TRANSITIONS` (`macroetapa.py:67`) | `advance_macroetapa` (`macroetapa_engine.py:191`) | **coluna do card no kanban** |

`ProcessStatus` (`app/models/process.py:10-22`): `lead, triagem, diagnostico,
planejamento, execucao, protocolo, aguardando_orgao, pendencia_orgao, concluido,
arquivado, cancelado`. `VALID_TRANSITIONS` em `process.py:74-86` (lead→triagem→
diagnostico→planejamento→execucao→protocolo→aguardando_orgao→…).

`Macroetapa` (`app/models/macroetapa.py:31-39`): `entrada_demanda,
diagnostico_preliminar, coleta_documental, diagnostico_tecnico,
caminho_regulatorio, orcamento_negociacao, contrato_formalizacao`. Transição
estritamente linear (`macroetapa.py:67-75`), cada uma só vai para a seguinte.

> A premissa do prompt ("as 7 etapas mapeiam ao `ProcessStatus`") é **REFUTADA**:
> as 7 etapas têm enum/campo **próprios** (`Macroetapa`), distintos do
> `ProcessStatus`. Há um bridge lossy `STATUS_TO_MACROETAPA` (`macroetapa.py:92`),
> mas os dois campos evoluem por caminhos separados e **nunca se sincronizam**:
> `advance_macroetapa` não toca `status`; `PATCH /status` não toca `macroetapa`.

### A.2 — Como uma transição acontece hoje

- **`macroetapa` (o card):** muda só em `advance_macroetapa` (`macroetapa_engine.py:191`).
  Dois chamadores, **ambos não-agênticos**:
  1. **Humano:** `POST /processes/{id}/macroetapa` (`processes.py:803-879`), com
     guard `_compute_can_advance` (409 se o gate falhar).
  2. **Auto (único gatilho automático):** ao **assinar um diagnóstico**
     (`regulatory.py:408-418`) — *só* se a etapa atual ∈
     `{diagnostico_preliminar, diagnostico_tecnico}` e o gate passar.
- **`status` (legado):** muda só por ação humana em `PATCH /processes/{id}/status`
  (`processes.py:380-396`), validado por `is_valid_transition`.
- **Nenhum worker/agente** escreve `process.macroetapa` nem `process.status`:
  `grep` em `app/workers/agent_tasks.py` por `macroetapa|advance|toggle_action` →
  só uma *leitura* de filtro (`agent_tasks.py:338`), nenhuma escrita.

### A.3 — Estado real no banco (prod, read-only)

```sql
SELECT status, macroetapa, count(*) FROM processes WHERE deleted_at IS NULL
GROUP BY status, macroetapa;
-- → [{status: triagem, macroetapa: entrada_demanda, n: 2}]

SELECT count(*) FROM audit_logs WHERE action='macroetapa_changed';  -- 0
SELECT count(*) FROM regulatory_diagnoses;                          -- 0
SELECT count(*) FROM regulatory_diagnoses WHERE validated_at IS NOT NULL; -- 0
SELECT count(*) FROM macroetapa_checklists;                         -- 0
```

**Os 2 processos estão parados em `entrada_demanda` / `triagem`. Nenhum avançou
jamais** (`macroetapa_changed = 0`). **Confirma "o card não sai do lugar".**

---

## B. ENCAIXE 7 ETAPAS (Ficha 07) × ESTADOS ATUAIS

As 7 etapas E1..E7 mapeiam **1:1** ao enum `Macroetapa` (o código já implementa
exatamente as 7). O descasamento é com o `ProcessStatus`, não com a Ficha 07.

| Ficha 07 | `Macroetapa` (campo do card) | `ProcessStatus` equivalente (bridge `STATUS_TO_MACROETAPA`) | Encaixe |
|---|---|---|---|
| E1 Entrada | `entrada_demanda` | `lead`, `triagem` | etapa **1:1**; status agrega 2 |
| E2 Diag. Preliminar | `diagnostico_preliminar` | `diagnostico` | etapa **1:1** |
| E3 Coleta | `coleta_documental` | — (sem status) | etapa **1:1**; **sem** status próprio |
| E4 Diag. Técnico | `diagnostico_tecnico` | — (sem status) | etapa **1:1**; **sem** status próprio |
| E5 Rota | `caminho_regulatorio` | `planejamento` | etapa **1:1** |
| E6 Orçamento | `orcamento_negociacao` | — (sem status) | etapa **1:1**; **sem** status próprio |
| E7 Contrato | `contrato_formalizacao` | — (sem status) | etapa **1:1**; **sem** status próprio |

### Gaps (B.5)
- **Etapas sem estado próprio:** nenhuma — todas as 7 têm valor `Macroetapa`
  dedicado. (Ao nível do *card*, não há gap de modelo.)
- **`ProcessStatus` que sobra** (não estão na Ficha 07 — lifecycle pós-MVP):
  `lead`, `execucao`, `protocolo`, `aguardando_orgao`, `pendencia_orgao`,
  `concluido`, `arquivado`, `cancelado`. O bridge mapeia esses 5 pós-contrato
  para `None` (`macroetapa.py:97-103`).
- **Dessincronia:** as duas máquinas não se falam — risco de o `status` dizer
  "diagnostico" enquanto o card está em `entrada_demanda` (exatamente o estado
  atual dos 2 processos: `status=triagem` mas é o card que manda na coluna).

---

## C. GRADE ETAPAS × ABAS × AGENTES

### C.6 — Agentes têm noção de "a que etapa pertencem"? **Sim, como metadado.**

`app/models/macroetapa.py` declara o vínculo agente↔etapa:
- `MACROETAPA_AGENTS` (`:208-237`) — `{primary:[...], secondary:[...]}` por etapa.
  Ex.: `diagnostico_preliminar → primary:[agent_atendimento, agent_diagnostico],
  secondary:[agent_legislacao, agent_extrator]`.
- `MACROETAPA_AGENT_CHAIN` (`:194-202`) — 1 chain por etapa
  (`entrada_demanda→intake`, `diagnostico_preliminar/tecnico→diagnostico_completo`,
  `caminho_regulatorio→analise_regulatoria`, `orcamento_negociacao→gerar_proposta`).

Mas é **descritivo**: aparece só na resposta de `get_macroetapa_status`
(`macroetapa_engine.py:279-291`, campos `primary_agents`/`secondary_agents`/
`agent_chain`) para a UI desenhar a grade. **Não governa execução** — o agente
não sabe "sou da etapa X"; ele roda quando a chain é disparada.

### C.7 — Existe "regência" (quem lidera qual etapa) ou só chain linear?

A **orquestração real é a chain linear** (`app/agents/orchestrator.py:23-40`):

```
CHAINS = {
  "intake": ["atendimento"],
  "diagnostico_completo": ["extrator", "auditor_imovel", "legislacao", "diagnostico"],
  "gerar_proposta": ["diagnostico", "orcamento"],
  "analise_regulatoria": ["legislacao"],
  "enquadramento_regulatorio": ["extrator", "legislacao"],
  ...
}
```

A "regência por etapa" da Ficha 07 (E2 = Extrator→Auditoria→(Diag⇄Legislação))
existe **só** como os dois dicts-metadado acima (`MACROETAPA_AGENTS` +
`MACROETAPA_AGENT_CHAIN`). A ordem de execução de fato é a lista linear da chain;
não há ⇄ (ida-e-volta Diag⇄Legislação) — é sequencial, com `legislacao`
não-bloqueante dentro de `diagnostico_completo` (`agent_tasks.py:59-64`).

---

## D. GATILHOS DE MOVIMENTAÇÃO E TRAVAS

### D.8 — "Terminar um agente/chain" muda o status do processo? **Não.**

- O worker `run_agent_chain` (`app/workers/agent_tasks.py`) **não** chama
  `advance_macroetapa` nem `toggle_action` nem escreve `process.status`/
  `macroetapa` (grep = 0 escritas). Rodar a chain produz `AIJob`/`StageOutput`,
  mas **não mexe no card**.
- **A relação é INVERTIDA face à Ficha 07.** A Ficha 07 diz "rodar os agentes de
  uma etapa avança o card". No código é o oposto: **avançar o card (manual)
  DISPARA a chain** — `processes.py:854-877` enfileira
  `{diagnostico_tecnico→diagnostico_completo, caminho_regulatorio→
  enquadramento_regulatorio, orcamento_negociacao→gerar_proposta}` *depois* de
  `advance_macroetapa`.
- Único elo automático na direção "evento→card": **assinar o diagnóstico**
  auto-avança a etapa (`regulatory.py:408-418`) — e só nas 2 etapas de
  diagnóstico. Como há **0 diagnósticos** no banco, nunca disparou.

### D.9 — Travas de pré-condição para avançar? **Sim, e é onde trava.**

`can_advance_macroetapa` (`app/models/macroetapa.py:433-459`), via
`_compute_can_advance` (`processes.py:665-784`), exige para avançar:
1. **Checklist existe** — `checklist is None → (False, ["Etapa não iniciada (sem
   checklist)"])` (`macroetapa.py:453`).
2. **Checklist 100%** — `require_complete=True` por default
   (`processes.py:669`); `completion_pct < 1.0` → blocker (`macroetapa.py:455`).
3. **Sem documentos obrigatórios pendentes** (`ProcessChecklist`, `:455-456`).
4. **Diagnóstico assinado** ao sair das etapas de diagnóstico (`:457-458`).

**O FURO está na trava 1.** O intake cria o processo **sem inicializar o
checklist**: `intake.py:223-241` seta `macroetapa=entrada_demanda` mas **não**
chama `initialize_macroetapa_checklists`. Esse init só existe no endpoint
explícito `POST /macroetapa/initialize` (`processes.py:882-895`), que aparenta
nunca ser chamado (banco: **0 `macroetapa_checklists`** para 2 processos). Logo
`can_advance` é **sempre `False`** → o botão "Avançar" fica permanentemente
travado, mesmo manualmente.

E mesmo que o checklist existisse: **nenhum agente marca ação como concluída**
(`toggle_action` só é chamado pelo endpoint manual `processes.py:929`), então o
`completion_pct` ficaria em 0 até o consultor tiquetar as 5–8 ações à mão.

---

## VEREDITO — o que falta para o card andar

Não é estado novo (a máquina de 7 etapas existe e é 1:1 com a Ficha 07). Faltam
**duas coisas encadeadas**, ambas medidas:

1. **Inicialização do checklist no nascimento do caso** — sem ela o gate trava em
   `False` e o card não anda nem por clique manual. (0 checklists / 2 processos.)
2. **O gatilho evento→card** — o elo "rodar/terminar os agentes de uma etapa →
   marcar checklist / avançar macroetapa". Hoje a direção é inversa (avançar
   dispara a chain) e o único auto-avanço (assinar diagnóstico) cobre só 2 das 7
   etapas e nunca rodou (0 diagnósticos).

O **vínculo agente→etapa já existe** como metadado (`MACROETAPA_AGENTS` /
`MACROETAPA_AGENT_CHAIN`); o que não existe é a **fiação** desse metadado à
movimentação. (O plano da Fase 0.2 sai daqui — este relatório não propõe
implementação.)

---

## Apêndice — queries de medição (read-only, reproduzíveis)

```sql
SELECT status, macroetapa, count(*) FROM processes WHERE deleted_at IS NULL
  GROUP BY status, macroetapa;                                      -- triagem/entrada_demanda: 2
SELECT count(*) FROM processes;                                    -- 2
SELECT count(*) FROM audit_logs WHERE action='macroetapa_changed'; -- 0
SELECT count(*) FROM regulatory_diagnoses;                         -- 0
SELECT count(*) FROM regulatory_diagnoses WHERE validated_at IS NOT NULL; -- 0
SELECT count(*) FROM macroetapa_checklists;                        -- 0
SELECT count(*) FROM macroetapa_checklists WHERE completion_pct >= 100; -- 0
```
