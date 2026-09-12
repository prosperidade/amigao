# Reauditoria Codex — 11/09/2026 (os sete itens + o gate que faltava)

**SHA auditado:** `335e9e5` (main após #167) · **Data:** 11/09/2026 ·
**Autor da leitura:** Codex (auditor externo) · **Versionado por:** Frente J
(`fix/fechamento-contrato-spec`), como passo zero.

> **Nota de proveniência.** O relatório original do Codex não chegou ao repo
> como arquivo (não existe em `docs/`, no Desktop nem em Downloads do
> André). O que está abaixo é a **transcrição do escopo tal como o André o
> passou à Frente J** — os sete itens, na ordem de gravidade do Codex, com as
> referências de arquivo/linha que ele citou — mais a confirmação de cada
> item contra o código de `335e9e5`, feita nesta frente antes de corrigir.
> Onde o Codex citou linha, a linha foi aberta (±20 linhas, regra da
> triagem de 10/08: achado que afirma ausência exige ver a vizinhança).
> Se o `.docx`/`.md` original aparecer, ele entra ao lado deste arquivo
> como fonte bruta — este não é editado (regra da pasta: auditoria é
> fotografia de um SHA).

---

## O que o Codex olhou

Os contratos que as Frentes C–I (ADRs 064–068) **declararam** fechados,
lidos contra o que o código de `335e9e5` **faz** — e, sobretudo, contra o
único caso real com dado suficiente para exercitar todos eles: o **#23
(ELODI)**, reextraído em 11/09 (116 linhas de staging, 57 tipadas, 28
aceitas pela Isis em 08/09, 0 gravadas).

Conclusão em uma frase: **cada um dos sete itens é um contrato da spec que
existe pela metade** — a peça está lá, a fronteira que a spec exige não. E
nenhum dos sete tinha sido atravessado ponta a ponta num ambiente
autenticado (tela → decisão → consolidação → recarga → nova sessão).

## Os sete itens, na ordem de gravidade do Codex

### 1. Invalidação NÃO enxerga a reextração cacheada — `artifact_staleness.py:120-151`

**Achado.** `_decisao_alterada_apos` filtra só `ExtractedFieldStaging.
updated_at > cutoff`. Linha de staging **nova** nasce com `updated_at IS
NULL` (sem `server_default`; só `onupdate`). No caminho do #23 — reextração
com texto cacheado, `force=False` — o documento já existia,
`Document.extracted_at` **não muda** (o OCR não roda), e as 74 linhas novas
entram com `created_at` de 11/09 e `updated_at` nulo. Resultado: diagnóstico
validado em 08/09 continua sem aviso depois de 74 evidências novas.

**Confirmado no código** (`335e9e5`): o docstring da Frente H até registra o
raciocínio ("staging recém-inserido e ainda pendente não soa alarme por si
só; a chegada em si já é coberta por `_documento_novo_apos`") — a premissa
é falsa para reextração: `_documento_novo_apos` olha `created_at`/
`extracted_at` do **documento**, e nenhum dos dois muda.

**O que a spec exige (REV-001):** documento novo **ou evidência nova**
depois do diagnóstico validado ⇒ marcado desatualizado.

### 2. `_estado_de` esconde evidência nova sob "gravada" — `reconciliation_decisions.py:406-413`

**Achado.** `if any(r.consolidated_at is not None ...): return "gravada"`.
Decisão com uma evidência antiga já gravada (certidão, 08/09) e uma nova
pendente (CAR, 11/09) aparece **"Gravado na base"** — a consultora não vê
que há algo a decidir. No #23 pós-reextração, as 4 decisões `composicao`
estão exatamente neste estado.

**Confirmado no código.** `any(...)` na primeira condição.

**O que a spec exige (CONF-001/STATE-001):** "gravada" só quando **todos**
os membros consolidaram; misto é um estado próprio, visível.

### 3. Aceite de proposta desatualizada é AVISO, não bloqueio — `proposals.py:accept_proposal`

**Achado.** `GET /proposals/{id}` traz `aviso_desatualizado` (ADR-068), mas
`POST /proposals/{id}/accept` não o consulta: aceita uma proposta cujo
processo ganhou documento novo depois dela. A ADR-068 entregou o aviso e
declarou o item fechado.

**Confirmado no código.** `accept_proposal` checa só `_effective_status`.

**O que a spec exige:** bloqueio. Recusar com 422 honesto e a razão; e a
ADR-068 corrigida (aditivo, não reescrita).

### 4. `rl_vigente()` ignora a vigência que a Frente F derivou — `observacao_registral.py:rl_vigente`

**Achado.** `rl_vigente = ultimo_por_destino(...).get(("matricula",
"averbacao_rl"))` — a RL "vigente" é a **última do papel**, mesmo quando a
própria certidão a declara baixada/retificada por averbação posterior. A
Frente F derivou `vigencia` por regra e a Frente F mesma não a consulta
aqui.

**Confirmado no código.** Docstring assume "as duas concordam na prática".

**O que a spec exige (HIST-001):** RL com `baixado`/`retificado` não é
promovida; volta `None` ou o ato anterior válido.

### 5. Tipo de observação NÃO é editável na decisão — CONF-002 pela metade

**Achado.** `StagingDecisionRequest.acao ∈ {aceitar, escolher_fonte, editar,
rejeitar, criar_acao, reabrir}` — não existe ação que corrija **o tipo**
(`tipo_observacao`) que o modelo sugeriu. O padrão medido no ADR-065 ("o
modelo acerta o valor e erra o tipo") só tem saída pela reextração. E o
cartão agrupado (`DecisaoRequest.acao ∈ {aceitar, reabrir}`) não oferece
escolher fonte nem editar para divergência sem fonte autoritativa.

**Confirmado no código** (`schemas/extracted_field_staging.py`,
`schemas/reconciliation.py`, `DecisoesPanel.tsx`).

**O que a spec exige (CONF-002):** tipo decidido pelo consultor, original
preservado (`atributos["tipo_sugerido"]`), reconciliação consome o tipo
**decidido**; ações de escolher fonte / editar no cartão agrupado.

### 6. `document_lifecycle`: "lido" ≠ legível; estados negativos ausentes — `document_lifecycle.py:_tem_leitura`

**Achado.** `lido = texto extraído OU ocr_status ∈ {done, not_required}`.
O doc 551 do #23 (CNH-e) está `done` com 444 chars de boilerplate de
assinatura digital — a projeção diz "lido"; a `extraction_status` do mesmo
documento diz "OCR não extraiu texto legível". Duas respostas para a mesma
pergunta. E o enum só tem os 5 degraus positivos: a spec (DOC-001) nomeia
também erro de leitura, não apresentado, dispensado, substituído,
desatualizado. A projeção não chega ao `DocumentResponse`.

**Confirmado no código.**

**O que a spec exige:** um critério só de legibilidade (o mesmo que produz
a mensagem de `extraction_status`); estados negativos no vocabulário;
projeção exposta na API.

### 7. Titularidade não conhece sucessão — `observacao_registral.py:TIPOS`, `cadeia_titularidade`

**Achado.** `titular_atual`/`cadeia_titularidade` só leem `compra_venda`.
Sucessão, inventário, adjudicação e formal de partilha — os atos que
transferem domínio **causa mortis** — não estão no vocabulário nem no
prompt. O caso de 3.000 ha (espólio) da Isis não tem titular. E
`derivar_vigencia` usa `date.today()` quando ninguém passa data: a data de
referência do caso existe (`Process.opened_at`) e não alimenta a regra.

**Confirmado no código** (`TIPO_COMPRA_VENDA` único em
`cadeia_titularidade`; `ref = data_referencia or date.today()`).

**O que a spec exige (HIST-001/ENT):** vocabulário de sucessão;
`titular_atual` reconhece transferência por sucessão; a data do caso
alimenta a vigência.

## O gate que nunca foi feito

Nenhuma das Frentes C–I atravessou o fluxo num **ambiente autenticado**
(login real, frontend real, API real, banco real). Os gates foram unitários
(pytest/vitest) e medições de extração com LLM em banco descartável — cada
peça provada sozinha, nunca a sequência. O Codex exige, como condição de
merge da Frente J:

- subir os 6 docs da ELODI → extrair → abrir Conferência → ver decisões →
  decidir 3 (uma com edição de tipo) → consolidar → recarregar →
  logout/login → as mesmas decisões, mesmos estados, mesmos números nas
  seis telas;
- subir documento novo → diagnóstico/rota/proposta marcados desatualizados;
  tentar aceitar a proposta → recusado;
- colar a sequência inteira com prints ou payloads;
- regressão: os gates de C–H continuam verdes.

E, na saída, o **relatório de reconciliação do #23 versionado completo** —
as 116 linhas e as 66 sem agrupamento listadas (a seção "Resultado — a
preencher" de `docs/trabalhos/reconciliacao_decisoes.md` estava vazia, e o
Codex não pôde classificar o que não existia no repo).

## O que esta reauditoria NÃO afirma

- Não mede a extração (LLM) — os sete itens são de regra, estado e
  contrato, todos determinísticos.
- Não reabre REC-001/CONF-001 (Frente G): a chave natural está certa; o
  que falta é o que o consultor pode FAZER sobre a decisão (item 5) e o que
  o estado agregado ESCONDE (item 2).
- Não numera dívida nova: cada item é um contrato já declarado fechado
  pela metade. O fechamento é adendo aos ADRs 065–068, não ADR nova.

---

**Onde foi parar:** `docs/trabalhos/fechamento_contrato.md` (o fechamento,
item a item, com o gate E2E e o relatório do #23), adendos em
`docs/adr/065`–`068`.
