# Triagem da Auditoria Codex — Fase 1 (somente leitura)

**Data:** 2026-08-10
**Branch:** `docs/triagem-auditoria-codex` · worktree `wt-triagem-auditoria`
**Insumo:** `auditoria_codex_regente.md` (idêntico ao `AuditoriaCodexRegente.docx`)
**Escopo triado:** AUD-04-01…09 · AUD-05.1…9 · AUD-10 itens 1…14 · RISCO ESTRUTURAL do AUD-01
**Nenhuma linha de código foi alterada. Nenhuma dívida foi aberta.**

---

## 0. Correção de premissa — ler antes das listas

A missão dizia: *"SHA auditado: 11ab1af. A main atual está ADIANTE (merges #141, #143,
#144 e o pulso da Sprint 2) — parte dos achados pode já estar fechada."*

**A main não está adiante. Ela está exatamente no SHA auditado.**

```
$ git rev-parse main          → 11ab1afcd133042f985918ff855fc029684b3fb0
$ git rev-parse origin/main   → 11ab1afcd133042f985918ff855fc029684b3fb0

$ git merge-base --is-ancestor d6e2681 11ab1af   (PR #141) → é ancestral
$ git merge-base --is-ancestor 9f20c30 11ab1af   (PR #143) → é ancestral
$ git merge-base --is-ancestor d401c88 11ab1af   (PR #144) → é ancestral
$ git merge-base --is-ancestor c7b65fa 11ab1af   (PR #142) → é ancestral
```

Os quatro merges citados **já estavam dentro** do snapshot auditado. A própria auditoria
declara isso em nove seções (`AUD-09`: *"Snapshot auditado:
11ab1afcd133042f985918ff855fc029684b3fb0 (HEAD)"*).

**Consequência para a Lista A.** Ela não pode ser *"fechado por merge posterior"* — não
houve merge posterior. Ela passa a ser: **achado que não reproduz no próprio SHA que a
auditoria diz ter lido.** Isso não desqualifica a auditoria; é o resultado esperado de uma
leitura estática de 500 arquivos Python. Mas muda a natureza do crédito: o mérito é do
fluxo que fechou o buraco **antes** da auditoria, e o registro serve para que a remediação
não reabra o que já está fechado.

**Uma nota de escopo.** A missão pedia "AUD-10 itens 1-11". O capítulo tem **14 itens**.
Os três excedentes (12 health, 13 métricas, 14 crawlers) foram triados junto — são da
mesma família e ficariam órfãos.

### Método

Cada achado foi cruzado, nesta ordem, contra:

1. `docs/REGISTRO_DIVIDAS.md` (2.274 linhas, lido integralmente)
2. `docs/adr/` (44 ADRs) + `MAQUINA_DE_ESTADOS.md`, `MULTITENANT_LGPD.md`,
   `ARQUITETURA_GERAL.md`, `GOVERNANCA_IA.md`
3. O código em `11ab1af` — arquivo e linha abertos, não inferidos

Toda classificação abaixo cita trecho e fonte. Onde a linha citada pela auditoria mudou de
posição, a linha real está anotada.

---

## A. JÁ RESOLVIDO — não reproduz no SHA auditado

**Dois achados.** É pouco, e é honesto que seja pouco: a auditoria rodou sobre o estado
atual, não sobre um snapshot velho.

### A1 · AUD-05.2 (segunda metade) — "a Conferência não tem estado gravado"

**O que a auditoria afirma:**

> *"Além disso, a Conferência não tem estado gravado; depois da consolidação, a linha
> permanece `aceito`. Evidência: `extracted_field_staging.py:101`."*

**Não reproduz.** A coluna existe, e existe exatamente para isso:

```python
# app/models/extracted_field_staging.py:112
consolidated_at = Column(DateTime(timezone=True), nullable=True)
```

Criada pela migration `c7a3f2b81d64` (*"Conferência: 'Aceito' deixa de ser igual a
'Gravado' — consolidated_at"*), entregue no **PR #141** (`d6e2681`, merge de
`audit/fluxo-validacoes-isis`) — que é ancestral de `11ab1af`. Carimbada em
`staging_consolidation.py:555,682` e limpa por qualquer nova decisão
(`:299,380,415,441,505,552`). Consumida na API em `processes.py:1445-1446`
(`r.gravado = r.consolidated_at is not None`). Coberta por
`tests/api/test_gravado_visivel.py` (216 linhas).

**Por que o auditor errou, e por que isso importa.** A linha 101 que ele cita cai **dentro
do comentário que explica a coluna**, onze linhas acima dela:

```python
# app/models/extracted_field_staging.py:100-103
# Por que uma coluna própria e não derivar de `field_sources` do destino:
# `field_sources` é por (entidade, COLUNA) e diz apenas "esta coluna foi
# validada por humano alguma vez". Ele não distingue a linha que pousou da
# linha que foi RECUSADA sobre uma coluna já consolidada …
```

Ele leu o parágrafo que justifica a solução e concluiu que a solução não existia. Vale
como calibragem de confiança para o resto do documento: **onde a auditoria afirma
ausência, conferir a vizinhança da linha citada.**

**Crédito ao fluxo:** PR #141 nasceu da auditoria de fluxo das validações da Isis de
06/08 — quatro dias antes deste documento.

### A2 · AUD-01 [RISCO ESTRUTURAL] — troca de provider de embedding

**O que a auditoria afirma:**

> *"Trocar o provider de embedding exige reindexação completa; caso contrário, a busca
> opera em espaços vetoriais incompatíveis."*

**A primeira metade é verdadeira e trivial; a segunda não reproduz mais.** A busca não
"opera em espaço incompatível" — ela **recusa**:

```python
# app/services/knowledge_catalog.py:467
raise EspacoVetorialIncompativel(
# app/services/embeddings.py:72
class EspacoVetorialIncompativel(EmbeddingError):
```

Fechado pela **ADR-040** + dívida **#114** (03/08, `fix/trava-espaco-vetorial`), com o
motivo escrito no registro: *"devolver vazio faria o agente dizer 'não encontrei
fundamentação' quando o problema é perguntar no idioma errado"*. O provider passou a ser
**explícito** com default de produto — ausência de chave vira falha ruidosa, não troca
silenciosa.

O risco residual real é outro e já tem número: **#303** (troca de provider não dispara
auditoria de premissas).

---

## B. JÁ DECIDIDO — a remediação segue a decisão, não a reabre

Sete achados que o material do projeto trata como **desenho**, não defeito. "Já decidido"
não é "ignorar": significa que qualquer conserto precisa passar pela decisão existente —
e, se for para mudá-la, muda-se o ADR primeiro.

### B1 · AUD-05.6 — "assinatura conclui mesmo sem arquivo assinado"

**Decisão explícita, ADR-030 §1** (`030-assinatura-manual-conclui-caso-comercial-oculta.md`):

> *"`POST /contracts/{id}/assinar` (sent→signed): registra a assinatura — `signed_at`
> (data informada), quem REGISTROU (`signed_registered_by_user_id`) e, **OPCIONAL, o
> upload do PDF já assinado** (`signed_pdf_storage_key`). Multipart; **sem arquivo é
> válido**."*

O código diz a mesma coisa em português (`app/api/v1/contracts.py:482-484`): *"Upload
OPCIONAL do PDF assinado (não-fatal: registra a assinatura mesmo se o storage falhar —
degrada com elegância)"*. E a própria auditoria cita o teste que **assegura** o
comportamento (`tests/api/test_signature_e2e_s5c.py:87-131`) — um teste que trava a
conduta é prova de intenção, não de descuido.

**Remediação coerente:** nenhuma. O MVP registra assinatura que aconteceu fora do sistema;
a assinatura eletrônica com validade jurídica é a dívida **#69**, nomeada no mesmo ADR.

### B2 · AUD-05.3 — "endpoint alternativo conclui o processo sem os gates da macroetapa"

**A leitura da casa está certa; a dívida que a missão apontou não é.**

A convivência dos dois eixos é decisão documentada em `MAQUINA_DE_ESTADOS.md` §1b:

> *"**Duas máquinas paralelas.** O processo tem **dois** eixos de estado, distintos e **não
> sincronizados**: `ProcessStatus` (seção 1, lifecycle legado de 11 estados, mudado
> manualmente por `PATCH /status`) e `Process.macroetapa` (as 7 etapas E1..E7 da Ficha
> 07)."*

E reafirmada na ADR-030 §2:

> *"O `ProcessStatus` operacional (lead→…→concluido) **NÃO é tocado**: é o eixo pós-contrato
> (MVP2), desacoplado da macroetapa **por design** — a conclusão da Ficha 07 vive no eixo
> da macroetapa, honestamente."*

**Correção à hipótese da missão.** A missão sugeriu cruzar com a **dívida #17**. Não é ela.
A #17 trata da coerência entre os status do `RegulatoryIssue`
(achado/saneamento/decisão) — substrato disjunto —, está **fechada** desde o PROMPT_8, e o
próprio registro tem nota de 03/07 dizendo que nem o selo de 3 estados a reabre
(`REGISTRO_DIVIDAS.md:59-63`). A dívida certa é a **#26** (unificação `Process.status` ×
`Process.macroetapa`, eixo 3 — ver Lista C).

**Correção à segunda hipótese da missão.** A frase *"dois motores complementam o domínio"*
(`ARQUITETURA_GERAL.md:157`) **não** se refere a estas duas máquinas — ela se refere a
`MacroetapaEngine` × `WorkflowEngine`, que é outro par. A cobertura documental correta para
o achado é `MAQUINA_DE_ESTADOS.md` §1b, citada acima.

**Onde a leitura da casa se confirma:** o princípio *radar-não-cancela* está escrito na
ADR-021 (*"'Nenhum passo sem norma' enforça na VALIDAÇÃO, não na geração"*) e a decisão da
Isis v02 (alerta crítico sinaliza sem impedir) segue valendo. O conserto é **coerência e
visibilidade entre as duas trilhas**, não cadeado no endpoint legado.

### B3 · AUD-04-08 — "ausência comprovável de RLS"

**Verificado:** a varredura confirma o fato. `grep -rniE "ROW LEVEL SECURITY|CREATE
POLICY|current_setting|SET ROLE" app/ alembic/` retorna **zero linhas**.

**Mas o fato é a decisão.** ADR-001 (Aceito, 2026-03-26):

> *"Isolamento é **lógico**, garantido por: […] 3. Toda query filtra explicitamente"*
> *"**Negativas:** Bug de query sem `WHERE tenant_id = X` vaza dados entre clientes —
> risco inegociável"*

A ADR **assume a negativa por escrito** e nomeia a mitigação prevista — que está declarada
como não feita na própria tabela de status de execução:

| Item | Estado |
|---|---|
| Lint automático que detecte query sem filtro | ❌ Pendente |

`MULTITENANT_LGPD.md:58` repete: *"Auditoria periódica dessa convenção está pendente — hoje
não há lint automático […]. Recomendação: adicionar regra customizada de `ruff` ou teste de
fumaça que faça `SELECT` cross-tenant."*

**Remediação coerente:** o **lint/teste de fumaça** que a ADR-001 já prometeu. Adotar RLS
seria reabrir a ADR-001 — decisão de arquitetura, não conserto de bug, e fora do que este
achado sustenta.

### B4 · AUD-05.2 (primeira metade) — "gate valida efeito de auditoria, não verdade da base"

O achado é verdadeiro **e está declarado no próprio código**, com a palavra "aceita":

```python
# app/services/macroetapa_engine.py:112-118  (docstring de has_consolidated)
Lacuna conhecida e aceita: `consolidate_process` só grava esse AuditLog
quando produz `writes`/`reconciliacoes`/`acoes_criadas`/`divergencias_devolvidas`
[…] este helper detecta "consolidação produziu efeito" e não "consolidação foi
chamada".
```

A auditoria **cita essa mesma frase** como evidência. Não há informação nova: o projeto
sabia, escreveu e seguiu. Fica em B com um alerta: se o gate um dia precisar significar
"a base está correta" e não "a consolidação produziu efeito", isso é mudança de contrato e
pede decisão — hoje não é defeito.

### B5 · AUD-01 [RISCO ESTRUTURAL] — Beat embarcado (`-B`) duplica agendadas ao escalar

Declarado no arquivo, com a condição e a saída nomeadas:

```yaml
# render.yaml:70-72
# -B: beat scheduler embarcado (DOU/DOE/vigia/acompanhamento/cleanup).
# IMPORTANTE: -B só é seguro com 1 instância. Ao escalar, migrar pra
# celery-redbeat ou serviço regente-beat dedicado (ver runbook).
dockerCommand: celery -A app.core.celery_app worker --pool=solo --loglevel=info -B
```

Decisão consciente de piloto, com gatilho escrito. Não é achado — é o comentário do arquivo
reproduzido.

### B6 · AUD-05 §4 — "`Document.extraction_status` é string livre; estados inválidos são possíveis"

`MAQUINA_DE_ESTADOS.md` §3, com o aviso em destaque:

> *"⚠️ **Decisão de design:** o Regente **não usa máquina de estados monolítica** para
> documento […] **Campo 2 — `extraction_status` (String livre).** […] Sem enum rígido —
> convenção textual usada pelo pipeline."*

Com os três motivos escritos (OCR e extração são pipelines independentes; validação é
decisão humana descentralizada; arquivamento é metadado). O mesmo documento decide
`AIJobStatus` em 4 estados e declara `cancelled` como *"não implementado (decisão: jobs IA
não cancelam, eles terminam ou falham)"* — que responde ao item *"`ContractStatus.cancelled`
existe mas não há fluxo"* da mesma seção da auditoria, por analogia de política.

### B7 · AUD-01 [RISCO ESTRUTURAL] — prompt persistido × fallback em código × skill externa

A "divergência entre três níveis" é a **hierarquia de resolução documentada** em
`GOVERNANCA_IA.md:135-139`:

> *"1. Procura `tenant_id = <tenant>` […] 2. Se não encontra, procura `tenant_id IS NULL`
> […] 3. Se não encontra, cai no **fallback hardcoded** no `.py` do agente (sempre existe
> um)."*

O risco real que sobra — um prompt do banco em prod divergir da melhoria feita no fallback
— já tem número: **#45**, com a nota operacional exata (*"se prod usa prompt do banco
(`extract_matricula`), a melhoria de prompt deste PR (fallback hardcoded) só vale onde não
há prompt no banco — conferir/atualizar o prompt do banco em prod"*).

---

## C. JÁ REGISTRADO — dívida numerada aberta, com o que a auditoria acrescenta

### C1 · AUD-05.3 (estrutural) → dívida **#26**

**#26 — Unificação `Process.status` × `Process.macroetapa` (eixo 3 — PR3-agressivo).**
*"Marco para destravar: quando alguma feature ou bug exigir resolver divergências entre os
dois eixos."*

**O que a auditoria ACRESCENTA:** o marco condicional da #26 acaba de ser atingido, e com
superfície nomeada. `app/api/v1/processes.py:448-487` (`update_process_status`) valida
**exatamente duas coisas** — `is_valid_transition` e `count_incomplete_tasks` — e nada mais:

```python
# app/api/v1/processes.py:466-473
if status_update.status not in [ProcessStatus.cancelado, ProcessStatus.arquivado,
                                ProcessStatus.triagem, ProcessStatus.lead]:
    incomplete_tasks = repo.count_incomplete_tasks(process.id)
```

Não consulta `macroetapa`, nem `Contract.signed_at`, nem `Process.closed_at`, nem
`RegulatoryDiagnosis.validated_at`. O estado alcançável que a auditoria nomeia
(`status=concluido` + `macroetapa != contrato_formalizacao` + `signed_at IS NULL`)
**reproduz**.

### C2 · AUD-05.8 → dívida **#11**

**#11 — Race no versionamento `MAX(version)+1`.** *"Capturado por `UniqueConstraint`, mas
devolve 500 + retry manual. […] Improvável para consultor único."* O código declara o mesmo
(`app/api/v1/regulatory.py:177-180`).

**O que a auditoria ACRESCENTA — e é maior que a #11.** A varredura que fiz para confirmar
devolve o número que generaliza o achado:

```
$ grep -rn "with_for_update\|FOR UPDATE" app/   →  zero ocorrências
```

**Não há lock de linha em nenhum fluxo do backend.** A #11 está escrita como um problema de
versionamento de diagnóstico; o que existe é a ausência sistemática de proteção concorrente
em **todas** as transições críticas — macroetapa, aceite de proposta, assinatura de
contrato, fechamento de rota. A #11 precisa ser **reescrita com o escopo real** (não é
dívida nova; é a mesma com a superfície medida).

### C3 · AUD-05.5 → dívida **#90(d)**

**#90(d) — Especificações pendentes da Ficha-do-chat:** *"**(d) versionamento** — o que se
versiona (diagnóstico, consolidação, ficha) e o que apenas se audita."*

**O que a auditoria ACRESCENTA:** o lugar concreto. Conferi as colunas de `StageOutput`
(`app/models/stage_output.py:32-77`) — são doze, e **nenhuma** é de vigência: não há
`supersedes`, `invalidated_at`, `version` nem `is_current`. `processes.py:1266` lista tudo
por data. A #90(d) é uma pergunta conceitual em aberto; a auditoria dá a ela um endereço
de implementação. Correlata da ADR-039, que resolveu o mesmo dilema no par
diagnóstico↔rota escolhendo **avisar, nunca regenerar** — o precedente para responder a
#90(d).

### C4 · AUD-05.1 → dívidas **#70** e **#71**

**#71 — Vínculo doc↔item gravado só de um lado.** *"`Document.checklist_item_id` é NULL em
100% dos 42 documentos do processo 15 […] o estado vive só no JSON do checklist."*

**O que a auditoria ACRESCENTA:** a consequência de **gate**, não só de leitura. As #70/#71
estão escritas como problema de visibilidade ("documentos invisíveis para a base"). O que a
auditoria mostra é que o mesmo buraco alimenta uma **decisão de avanço de etapa**:

```python
# app/services/checklist_engine.py:131  →  completion_pct
completion_pct = round((received + waived) / total * 100, 1)
# app/services/checklist_engine.py:168-179  →  mark_item_received
def mark_item_received(checklist, item_id, document_id: Optional[int] = None) -> bool:
```

`received` grava com `document_id=None` e entra no percentual; o percentual é insumo de
`can_advance_macroetapa`. **Checklist 100% pode significar só marcação manual** — e é isso
que o gate lê.

### C5 · AUD-05.7 → dívida **#68(a)**

**#68(a):** *"o `contract_generator.fill_contract_template` (template-fill genérico) e o
`scope_base` residual do `PRICE_TABLE` […] seguem no código para o caminho AVULSO (contrato
sem proposta) […] — aposentar tudo de vez quando o avulso migrar."*

**O que a auditoria ACRESCENTA:** a porta legada não é só "avulso". `POST /contracts`
aceita **`proposal_id`** e grava sem conferir o estado da proposta:

```python
# app/api/v1/contracts.py:176-184
contract = Contract(
    tenant_id=current_user.tenant_id,
    client_id=body.client_id,
    proposal_id=body.proposal_id,      # ← nenhuma checagem de status == accepted
    process_id=body.process_id,
```

Contra a ADR-029, que decide o oposto para `/contracts/gerar`: *"`status == accepted` (senão
422 honesto)"*. A #68(a) prevê aposentar o legado por **higiene**; a auditoria mostra que
ele é um **bypass de regra decidida**. Isso sobe a prioridade da #68(a) e muda seu motivo.

### C6 · AUD-10.6, AUD-10.13 → família **#123** / **#303**

**#123 — REGRA: silêncio não é evidência de ausência.** *"Artefato de medição registra o que
ACONTECEU, nunca o que foi solicitado."* / *"Nossos defeitos não são de dado ausente — são
de dado presente e não consultado."*

**O que a auditoria ACRESCENTA:** duas superfícies novas da mesma família, ambas em código
de produção (a #123 nasceu em instrumentos de medição):

```python
# app/core/metrics.py:352-354  e  375-376
    except Exception:
        return          # ← sem log. A métrica desaparece sem deixar rastro.
```

```python
# app/services/ai_job_persistence.py:79-83   →  return None após warning
# app/agents/base.py:444-445, 476-477        →  flush do AIJob absorvido
```

A #123 é uma **regra**, não uma dívida com escopo. Estes achados dizem onde a regra ainda
não foi aplicada — e a de `metrics.py` é a versão literal do `2>/dev/null` que a #123
autopsia.

---

## D. GENUINAMENTE NOVO — sem dívida, sem decisão, e reproduz na main

**Vinte e um achados.** A hipótese da missão se confirma: o grosso está no **AUD-04**
(multi-tenant na escrita) e no **AUD-10** (contratos de falha). Todas as linhas abaixo
foram **abertas e conferidas** em `11ab1af`; onde a auditoria errou a linha, a real está
anotada.

### D-MT · Multi-tenant na escrita — 9 achados

> **Divergência doc × código a corrigir junto.** `ARQUITETURA_GERAL.md:131` afirma
> *"Tentativa de manipular entidade de outro tenant retorna 403"* e `MULTITENANT_LGPD.md`
> §"Camada 4" afirma *"Quando o JWT diz `tenant_id = 5` e o body tenta criar entidade com
> `tenant_id = 7`, o serviço valida e rejeita com 403"*. **A Camada 4 valida o `tenant_id`
> da própria entidade — nunca as relações que ela aponta.** Os achados D1–D3 vivem
> exatamente nessa distinção, e a documentação hoje esconde a lacuna. Corrigir os dois
> documentos no mesmo PR da remediação.

| # | Achado | Severidade | Evidência revalidada |
|---|---|---|---|
| **D1** | Relações cross-tenant não validadas na criação | **Alta** | `processes.py:110-119`; `base.py:61`; `process.py:100-101` |
| **D2** | Contratos resolvem entidades relacionadas sem tenant | **Alta** | `contracts.py:117-119`, `158-186`, `507` |
| **D3** | `storage_key` controlável no cliente | **Alta** | `documents.py:198-199`; `intake.py:819-820` |
| **D4** | WebSocket não valida escopo do JWT | **Alta** | `websockets.py:126-152` |
| **D5** | Webhook WhatsApp deriva tenant por telefone global | **Alta** | `messaging.py:63-80`, `193-199` |
| **D6** | Corpus legislativo mutável por qualquer usuário interno | **Alta** | `legislation.py:32,66,87,113,147`; `legislation_alerts.py:78-88` |
| **D7** | Jobs assíncronos sem precheck de tenant | Média | `agents.py:172`; `ai.py:173`; `agent_tasks.py:202` |
| **D8** | Revogação de sessão inexistente | Média | `auth.py:246-254` |
| **D9** | `X-Tenant-Id` no contexto de observabilidade | Baixa | `middleware.py:38-50` |

**D1 · AUD-04-01 — relações cross-tenant na criação.** O endpoint repassa o body inteiro
menos o `tenant_id`:

```python
# app/api/v1/processes.py:110-119
repo = ProcessRepository(db, current_user.tenant_id)
process = repo.create(process_in.model_dump(exclude={"tenant_id"}))
```

e o repositório injeta apenas o tenant **da própria linha**:

```python
# app/repositories/base.py:61
obj = self.model(**data, tenant_id=self.tenant_id)
```

`client_id`, `property_id` e `responsible_user_id` chegam do payload sem conferência. O
schema não oferece segunda barreira — as FKs são simples, não compostas:

```python
# app/models/process.py:100-101
client_id   = Column(Integer, ForeignKey("clients.id",   ondelete="RESTRICT"), nullable=False, index=True)
property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True,  index=True)
```

**D2 · AUD-04-02 — contratos.** Três pontos, e o terceiro **escreve**:

```python
# app/api/v1/contracts.py:168     (create_contract)
proc = db.query(Process).filter(Process.id == body.process_id).first()
# app/api/v1/contracts.py:119     (_resolve_demand_type)
proc = db.query(Process).filter(Process.id == contract.process_id).first()
# app/api/v1/contracts.py:507     (assinar)  ← escrita cross-tenant
proc = db.query(Process).filter(Process.id == contract.process_id).first()
if proc and proc.closed_at is None:
    proc.closed_at = datetime.now(UTC)
```

A auditoria classificou o terceiro como *"pode fechar processo de outro tenant"*. Confirmado:
não é leitura vazada, é **`closed_at` gravado** num processo que o tenant corrente não
possui.

**D3 · AUD-04-04 — `storage_key`.** A chave enviada pelo cliente é persistida crua, nas duas
portas:

```python
# app/api/v1/documents.py:198-199        # app/api/v1/intake.py:819-820
storage_key=body.storage_key,           storage_key=body.storage_key,
s3_key=body.storage_key,                s3_key=body.storage_key,
```

Nenhuma checagem de que a chave foi emitida pelo backend, ou de que começa com
`tenant_{current_user.tenant_id}/` — prefixo que `storage.py:98` produz mas ninguém verifica
na volta. O download depois presigna a chave persistida.

**D4 · AUD-04-05 — WebSocket.** A busca é por id e só:

```python
# app/api/websockets.py:135-152
user = db.query(User).filter(User.id == user_id).first()
if not user:  await websocket.close(code=1008); return
tenant_id = user.tenant_id
client_id = token_data.client_id
if token_data.profile == "client_portal" and client_id is None:
    await websocket.close(code=1008); return
```

Não confere `user.is_active`, não compara `token_data.tenant_id` com `user.tenant_id`, e do
`client_id` verifica apenas a **presença** — nunca se pertence ao tenant. Token viaja em
query string. *(A auditoria diz "nenhuma validação de client"; é justo registrar que a
checagem de presença existe.)*

**D5 · AUD-04-06 — webhook WhatsApp.** A varredura é global e a primeira coincidência vence:

```python
# app/api/v1/messaging.py:74-80
candidates = db.query(Client).filter(Client.phone.isnot(None)).all()   # todos os tenants
for client in candidates:
    for phone in (client.phone, client.secondary_phone):
        if norm and norm[-8:] == tail:
            return client
# :193-199 — tenant_id = client.tenant_id
```

O docstring da função afirma a premissa que sustenta o desenho — *"o número identifica
unicamente o cliente"* — e **nenhuma constraint a garante**. Dois tenants com o mesmo
telefone (número corporativo, contador compartilhado, cliente que trocou de consultoria)
atribuem mensagem, mídia, thread e trilha ao tenant errado. É o único caminho da lista
alcançável **sem JWT**.

**D6 · AUD-04-03 — corpus legislativo.** Os cinco endpoints usam
`get_current_internal_user` e nenhum confere `is_superuser` (`legislation.py:32,66,87,113,147`).
O caso mais claro é o gatilho de monitoramento, que **se declara admin no docstring** e não
implementa:

```python
# app/api/v1/legislation_alerts.py:78-88
@router.post("/monitor/trigger")
def trigger_monitoring(..., current_user: User = Depends(get_current_internal_user), ...):
    """Dispara ciclo de monitoramento manualmente (admin)."""
```

Não é vazamento entre tenants — o corpus é global por decisão (ADR-001). É **ausência de
autorização administrativa sobre um bem compartilhado**: qualquer usuário interno de
qualquer tenant escreve na base que fundamenta as peças de todos. Pesa mais aqui do que
pesaria em outro produto, porque o corpus é o diferencial.

**D7 · AUD-04-07.** O enqueue não valida, e a task revalida pela metade:

```python
# app/workers/agent_tasks.py:202  — tenant_id está em escopo e não é usado
proc = db.query(Process).filter(Process.id == process_id).first()
```

**D8 · AUD-04-09.** `logout` só instrui o cliente (`auth.py:246-254`, docstring: *"poderia
ser estendido para invalidar o token em uma blacklist (Redis) no futuro"*). Troca de senha
também não invalida token emitido.

**D9.** `middleware.py:38-50` aceita `X-Tenant-Id` como fallback do contexto de
observabilidade. **Não autoriza nada** — mas contradiz `MULTITENANT_LGPD.md:43` (*"**Não há
header `X-Tenant-Id`** — anti-padrão"*) e o `CLAUDE.md`. Baixa severidade, correção de uma
linha ou de uma frase de documento; entra aqui só para não ficar órfã.

### D-CF · Contratos de falha — 12 achados

| # | Achado | Severidade | Evidência revalidada |
|---|---|---|---|
| **D10** | Upload confirmado sem prova do objeto; dispatch falho vira `success` | **Alta** | `documents.py:305-340` |
| **D11** | Chain parcial reportada como `status: success` | **Alta** | `agent_tasks.py:216` |
| **D12** | Extração nunca persistida — guard morto | **Alta** | `ai_tasks.py:175-183`; `document.py:89` |
| **D13** | JSON inválido vira extração "concluída" | **Alta** | `document_extractor.py:198-200` |
| **D14** | Falha de auditoria do AIJob absorvida | **Alta** | `ai_job_persistence.py:79-83`; `base.py:444,476` |
| **D15** | Fallback de regras sem proveniência | Média/Alta | `llm_classifier.py:172-174`; `ai_tasks.py:79-91` |
| **D16** | Confiança desconhecida aceita como válida | Média | `base.py:479-486`, `488-492` |
| **D17** | Soft delete ignorado na leitura e nos workers | Média/Alta | `dossier.py:175-181`; `processes.py:198-202`; `ocr_tasks.py:91-95` |
| **D18** | `/decisions/latest` não exclui `substituida` | Média | `decisions.py:134-144` |
| **D19** | `/health` verde falso | Média | `main.py:211-213` |
| **D20** | Métricas medem Celery, não resultado | Média | `celery_app.py:121-123` |
| **D21** | Crawler devolve parcial como completo | Média | `dou_crawler.py:57-68` |

**D10 · AUD-10.1+10.2.** A falha de enfileiramento é absorvida e o upload é contabilizado
como sucesso na mesma função:

```python
# app/api/v1/documents.py:319-320
except Exception as exc:
    logger.warning("Falha ao enfileirar OCR para document_id=%s: %s", db_doc.id, exc)
# … app/api/v1/documents.py:337
record_document_upload("client_portal" if ... else "internal", "success")
```

Nada verifica que o objeto existe no storage sob a chave confirmada. Documento fica
`ocr_status=pending` para sempre, sem estado que diga "o despacho falhou".

**D11 · AUD-10.3 — e o dado existe.** O retorno é incondicional:

```python
# app/workers/agent_tasks.py:216
return {"status": "success", "chain": chain_name, "steps": [...]}
```

**Dezenove linhas acima**, a mesma função já calcula o booleano que faltaria:

```python
# app/workers/agent_tasks.py:197
if process_id is not None and all(r.success for r in results):
```

`all(r.success ...)` é computado para decidir se marca o checklist da etapa — e **não é
consultado** para o status devolvido. É a #123 na letra (*"dado presente e não
consultado"*), agora em worker de produção.

> **Nota de decisão que NÃO cobre este achado.** A **ADR-011** decide que certos agentes
> não travam a chain (`NON_BLOCKING_REVIEW_AGENTS`, `NON_BLOCKING_FAILURE_BY_CHAIN`). Ela
> decide a **continuação** — nunca que o relatório final possa omitir a falha. Ao contrário:
> a ADR-011 exige que *"o erro/output fica registrado"*. O achado é sobre o **contrato de
> retorno**, e permanece novo.

**D12 · AUD-10.4 — o guard nunca dispara.** O caminho legado protege a escrita com um
`hasattr` sobre um atributo que **não existe no modelo**:

```python
# app/workers/ai_tasks.py:175-176 e 182-183
if hasattr(document, "extracted_fields") and fields:
    document.extracted_fields = fields
```

```
$ grep -n "extracted_text\|extracted_fields" app/models/document.py
89:    extracted_text = Column(Text, nullable=True)
102:        return bool((self.extracted_text or "").strip())
```

`Document` tem `extracted_text` e **não tem** `extracted_fields`. A condição é sempre falsa;
o `db.add(document)` da linha 183 nunca roda. Mesmo assim o job fecha `completed` e a task
devolve `{"status": "success", "fields_count": len(fields)}`. É o caso mais limpo da lista:
**a resposta afirma persistência que o código torna impossível.**

**D13 · AUD-10.5.** O erro de parser vira dicionário de dados e segue como resultado:

```python
# app/services/document_extractor.py:198-200
if parsed is None:
    logger.warning("document_extractor: falha no parse JSON para doc_type=%s", doc_type)
    parsed = {"_raw": response.content[:500], "_parse_error": True}
```

`persist_ai_job(result=parsed)` grava o job como concluído e o log seguinte reporta
`fields=%d` com `len(parsed)` — **dois** —, então uma falha de parse aparece como duas
"chaves extraídas".

**D14 · AUD-10.6.** Três absorções, todas com `logger.warning` e sequência normal:
`ai_job_persistence.py:79-83` (`return None`), `base.py:444-445` (`_complete_job`),
`base.py:476-477` (`_fail_job`). Consequência: um agente entrega resultado enquanto o
custo, os tokens, o modelo e o histórico não existem. **Fere o Princípio 2** ("tudo é
auditável") no ponto exato em que ele é vendido.

**D15 · AUD-10.10.** O classificador devolve regra estática sem qualquer marca de origem:

```python
# app/services/llm_classifier.py:170-174
except AIGatewayError as exc:
    logger.warning("llm_classifier: LLM falhou, usando regras. error=%s", exc.message)
...
return static_result, None
```

e a task fecha o job como se o LLM tivesse produzido, gravando no processo:

```python
# app/workers/ai_tasks.py:76-91
process.initial_diagnosis = result.initial_diagnosis
job.status = AIJobStatus.completed
job.result = {"demand_type": ..., "confidence": result.confidence, ...}
```

> **Por que isto NÃO é coberto por "radar não cancela".** O princípio manda **degradar com
> elegância e sinalizar** — nunca degradar em silêncio. `GOVERNANCA_IA.md:218` diz do
> citation evaluator: *"**Não bloqueia** o output — apenas **sinaliza**"*. Aqui não há
> sinalização: falta o "apenas sinaliza". O princípio da casa **condena** este achado em vez
> de absolvê-lo.

**D16 · AUD-10.11.** Valor externo entra como string e o gate compara por igualdade exata:

```python
# app/agents/base.py:479-482
if "confidence" in data:
    return str(data["confidence"])
# app/agents/base.py:488-492
def _needs_review(self, confidence: str, data) -> bool:
    if data.get("requires_review") is True: return True
    return confidence == "low"
```

`"LOW"`, `"0.2"`, `"baixa"` e `"certain"` não disparam revisão. O caminho do classificador
tem o mesmo buraco (`llm_classifier.py:134`, `confidence=parsed.get("confidence", "medium")`).

**D17 · AUD-10.8.** Três leituras sem `deleted_at IS NULL`, com a coluna existindo
(`document.py:94`):

```python
# app/services/dossier.py:176-181
.filter(Document.process_id == process_id, Document.tenant_id == tenant_id)
# app/api/v1/processes.py:198-202   (contagem do kanban)
.filter(Document.process_id.in_(process_ids))
# app/workers/ocr_tasks.py:91-95    (worker processa documento excluído)
.filter(Document.id == doc_id, Document.tenant_id == tenant_id)
```

**D18 · AUD-10.9.** A consulta filtra `deleted_at` mas não o status:

```python
# app/api/v1/decisions.py:137-144
.filter(ProcessDecision.process_id == process_id,
        ProcessDecision.tenant_id == current_user.tenant_id,
        ProcessDecision.deleted_at.is_(None))
.order_by(desc(ProcessDecision.created_at)).first()
```

`DecisionStatus.substituida` existe e não é excluída — a decisão substituída volta como
"última decisão" no drawer do Quadro.

**D19 · AUD-10.12.** `main.py:211-213` devolve `{"status": "ok", ...}` sem tocar em banco,
Redis, storage ou broker. Não há endpoint de readiness separado. O warm-up
(`main.py:55-73`) apenas loga e segue.

**D20 · AUD-10.13.** `celery_app.py:121-123` registra o estado do **broker**
(`record_celery_task(task.name, (state or "unknown").lower(), duration)`) — uma task que
devolve `{"status": "failed"}` sem levantar exceção entra como `SUCCESS`. E a persistência
da métrica engole tudo sem log (`metrics.py:352-354`, `375-376`) — ver C6.

**D21 · AUD-10.14.** Erro por termo sai do resultado e vira só log:

```python
# app/services/crawlers/dou_crawler.py:63-66
except Exception as exc:
    logger.warning("DOU search falhou para '%s': %s", term, exc)
    continue
```

`crawl()` devolve `list[CrawledDocument]` — não há como o chamador saber que a varredura foi
parcial.

### D-ROTA · 1 achado

**D22 · AUD-05.4 — edição humana de passo validado não invalida a rota.** A ADR-021 decide a
invalidação **pelo caminho da IA**:

> *"rota já validada + diff da IA vira `desatualizada` (não rebaixa o conteúdo assinado) e
> trava 'Fechar rota' até o consultor aceitar o diff"*

O caminho humano não tem regra, e o endpoint escreve qualquer campo sem tocar em
`Rota.status`:

```python
# app/api/v1/rotas.py:377-392
def editar_passo(...):
    passo = _get_passo_or_404(db, rota_id, passo_id, current_user.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(passo, field, value)
    db.commit()
```

Uma rota **fechada com hash chain** (ADR-021: *"'Fechar rota' […] grava um `AuditLog` com
hash chain SHA-256"*) continua `validada` depois que título, prazo, órgão ou classificação
mudaram. **Lacuna dentro de um desenho decidido**, não contra ele — e por isso a remediação
tem forma óbvia: aplicar ao caminho humano a mesma política já escrita para o caminho da IA.

> Vizinhança relevante: a **#305** (passo removido não tem tela) e a pergunta aberta com a
> Isis — *"rejeitar × remover"*. Se a conversa acontecer, esta decisão entra junto: o que uma
> edição do consultor faz com a assinatura da rota.

---

## E. Frentes de remediação propostas

Derivadas **só** da Lista D e do delta da Lista C. Ordem por dependência e por risco, não
por tamanho. **Nenhuma numeração de dívida foi atribuída** — isso é decisão do André.

### Frente 1 — Integridade de tenant na escrita  ·  `D1 D2 D3 D7` + delta `B3`

**Por que primeira.** É a única frente cujo dano é **irreversível e silencioso**: uma
relação cross-tenant gravada hoje continua torta depois de qualquer conserto de código, e
D2 já grava `closed_at` em processo alheio. Toda leitura posterior (dashboard, dossiê, PDF,
RAG) herda o erro — a auditoria chama isso de *"joins posteriores sem filtro tenant"*, e
eles são consequência, não causa.

**Conteúdo:** validador único de relação (`assert_relacao_do_tenant`) aplicado em processo,
imóvel, proposta e contrato; `storage_key` derivada no backend ou validada contra o prefixo
`tenant_{id}/`; precheck antes do `.delay()` e filtro de tenant na task; e o **lint/teste de
fumaça cross-tenant que a ADR-001 prometeu e nunca entregou** (B3 — não é frente própria,
é o instrumento que impede a Frente 1 de regredir).

**Dependência:** nenhuma. Começa hoje.

**Não fazer junto:** FK composta `(tenant_id, id)` no schema. Resolve de vez, exige
migration em todas as tabelas tenantizadas e é o AUD-02-003 — outro capítulo, outra rodada.
A validação na aplicação cobre a escrita nova; a constraint é o cinto que vem depois.

### Frente 2 — Portas sem dono  ·  `D4 D5 D6 D8`

**Por que separada da 1.** São caminhos de **entrada**, não de escrita interna: WebSocket,
webhook público, corpus global, sessão. Cada um tem um mecanismo próprio e nenhum
compartilha código com a Frente 1 — juntar faria um PR que ninguém revisa.

**Ordem interna sugerida:** D5 primeiro (único alcançável **sem JWT**), depois D6 (bem
compartilhado, e o gatilho de monitoramento já se declara admin no docstring — é uma linha),
depois D4, e D8 por último (revogação exige decidir se é blacklist Redis ou `token_version`
no usuário — é decisão, não conserto).

**Dependência:** independente da Frente 1.

### Frente 3 — Contrato de falha do pipeline documental  ·  `D10 D12 D13 D17`

**Por que aqui.** É a frente que a **Isis sente**: documento que sobe e não é lido, extração
que diz que gravou e não gravou, documento apagado que reaparece no dossiê. D12 é o item de
melhor retorno da triagem inteira — um `hasattr` sobre atributo inexistente, conserto de
minutos, e hoje ele torna um caminho de extração inteiro decorativo.

**Conteúdo:** verificar o objeto no storage antes de confirmar; estado explícito de despacho
falho (a coluna `ocr_error` do PR #69 já é o precedente); `_parse_error` derruba o job em vez
de virar dado; filtro de soft delete centralizado.

**Dependência:** D3 (`storage_key`) mora na Frente 1 e é vizinho de D10 — se as duas frentes
correrem juntas, combinar o ponto de contato antes.

### Frente 4 — Honestidade do resultado de IA  ·  `D11 D14 D15 D16` + delta `C6`

**Por que depois da 3.** Não muda comportamento visível; muda o que o sistema **afirma** ter
feito. Vale por si — é o Princípio 2 e o Princípio 11 no código de produção — mas não
desbloqueia ninguém amanhã.

**Conteúdo:** `status` da chain derivado de `all(r.success)` com `partial` como terceiro
valor (o booleano **já está calculado**, `agent_tasks.py:197`); falha de persistência de
AIJob deixa de ser best-effort; fallback carrega `fallback_source` e não fecha job como se
o provider tivesse respondido; `confidence` normalizada na entrada com valor desconhecido
caindo para revisão, nunca para "válido".

**Dependência:** nenhuma técnica. Conceitual: fecha a família da #123 dentro do runtime.

### Frente 5 — Observabilidade que não mente  ·  `D19 D20 D21` + `C6`

**Por que por último entre as de código.** Menor risco imediato, maior custo de descoberta —
é a frente que faz as outras quatro serem **verificáveis em produção**. Fazê-la antes das
outras seria instrumentar o que ainda vai mudar.

**Conteúdo:** `/health` (liveness) separado de `/ready` (banco, Redis, storage); métrica de
resultado funcional ao lado da de execução Celery; `except Exception: return` da
`metrics.py` ganha log; crawler devolve resultado explicitamente parcial.

### Frente 6 — Coerência entre as duas trilhas  ·  `C1 (#26)` + `D22` + `C5 (#68a)`

**Por que fora da fila técnica.** Esta frente **precisa de decisão de produto antes de
código**, e a decisão não é minha nem do André sozinho:

- **#26** — o marco condicional foi atingido (C1). Mas "unificar as duas máquinas" tem
  desde a versão barata (o endpoint legado passa a **avisar** quando diverge da macroetapa —
  radar não cancela) até o PR3 agressivo que o registro descreve. São produtos diferentes.
- **D22** — o que uma edição do consultor faz com a assinatura da rota entra na conversa
  *"rejeitar × remover"* que já está aberta com a Isis (#305). Decidir isolado seria escolher
  no lugar dela.
- **C5/#68(a)** — aposentar `POST /contracts` é trivial; decidir se o caminho **avulso**
  (contrato sem proposta) continua existindo é decisão comercial.

**Dependência:** as três esperam a Isis e o André. Nenhuma linha de código antes disso.

### Fora de frente — itens avulsos

- **D9** (`X-Tenant-Id`) — uma linha de código **ou** uma frase de documento. Carona em
  qualquer PR da Frente 1 ou 2.
- **D18** (`/decisions/latest`) — um `.filter()`. Carona na Frente 3 ou 5.
- **C2/#11** — não é frente: é **reescrever a dívida #11** com o escopo medido (zero
  `with_for_update` em todo o backend, não só no diagnóstico). Edição de registro, não PR.
- **B-list inteira** — nada a fazer. Se alguma delas incomodar, o caminho é **mudar o ADR**,
  não consertar o código.

### O que a triagem NÃO cobre

O escopo pedido deixou de fora, **por instrução**: AUD-02 (16 achados de banco/migrations —
inclui `AUD-02-003`, a FK composta que é o cinto da Frente 1, e `AUD-02-002`, um `downgrade`
que apaga tombstones), AUD-03, AUD-06 a AUD-09, AUD-11 a AUD-13. O AUD-14 se recusa a
concluir por falta de insumo e não tem achados próprios.

**Não foram lidos nem verificados.** Não estão nas quatro listas, e a ausência aqui não é
sinal de que estejam fechados.

---

*Fase 1 encerrada no relatório, conforme a missão. Atacar, e em que ordem, é decisão do
André.*
