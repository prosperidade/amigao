# ADR-068 — Estado único por serviço; invalidação por aviso

**Data:** 10/09/2026
**Status:** Aceita
**Frente:** H — estado único e invalidação transitiva (`feat/estado-unico-invalidacao`)
**Insumo:** `docs/auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md` §5/§6
(DOC-001, STATE-001, REV-001), `AUDITORIA_INDEPENDENTE_FASE1_2026-09.md` bloco E,
`AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md` bloco C, `docs/adr/039-rota-nasce-do-
diagnostico-fundamentado.md` (item 6 — precedente de "avisa, nunca regenera"),
`docs/adr/067-decisao-como-unidade-da-conferencia.md` ("Fora do escopo": DOC-001/
STATE-001/REV-001 ficam para esta frente), `docs/adr/011-agentes-nao-bloqueantes-
chain.md`
**Dívidas fechadas:** DOC-001, STATE-001, REV-001 — com fronteiras declaradas abaixo
**Dívida aberta:** nenhuma nova nesta frente (uma nota de escopo, ver "Fora desta
frente")

---

## Contexto

Três problemas medidos, cada um em auditoria própria:

**STATE-001.** `AUDITORIA_INDEPENDENTE_FASE1_2026-09.md` bloco E lista seis
lugares que respondem "quanto falta neste processo?" com contas
independentes: checklist (`checklist_engine.py`), barra da macroetapa
(`MacroetapaSidePanel.tsx`), staging preparado (`ConsolidacaoPanel.tsx`),
`consolidated_at` por linha (`processes.py`), resultado da última consolidação
(`campos_gravados`, `staging_consolidation.py`) e o `checklist_summary` do
dossiê (`dossier.py`). Medido em código: o dossiê **reimplementava** a mesma
conta do checklist, com o MESMO bug — `docs/auditoria/TRIAGEM_AUDITORIA_
CODEX.md` (achado sobre `mark_item_received`): um item marcado "recebido" com
`document_id=None` entra no percentual igual a um item com documento de
verdade. Checklist 100% podia significar só marcação manual.

**DOC-001.** O documento tem três sinais parciais e sem relação entre si —
`ocr_status` (enum do pipeline de leitura), `extraction_status` (string livre,
hoje só carrega o motivo de "não processado, revisar" —
`app/agents/extrator.py:382`) e `review_required` (flag solta). Nenhum
responde "em que pé está este documento" (recebido → lido → classificado →
extraído → conferido), e nenhuma mudança de estado tinha autor registrado.

**REV-001.** Medido duas vezes: a Isis subiu documento novo na E5 e o
diagnóstico re-rodado não o enxergou (validação de 02/08); e antes disso, "a
IA atualizou e apagou toda a rota" (validação 30/07, o precedente que motivou
o ADR-039). Documento novo ou decisão alterada na Conferência não avisam
diagnóstico, rota ou proposta que dependem daquele estado.

## Decisão

### 1. STATE-001 — uma função de serviço por indicador, nunca duas contas da mesma pergunta

`app/services/process_indicators.py` cria `progresso_conferencia(db, tenant_id,
process_id) → {decisoes_total, decididas, gravadas, pendentes}`, construída
sobre `reconciliation_decisions.build_decisions` (ADR-067) — que já expõe
`Decisao.estado ∈ {pendente, decidida, gravada}` sem coluna nova. `sem_
agrupamento` entra na conta (Ficha 07: "nada some sem dizer").

**Não são seis números que devam bater sempre** — é a conclusão medida da
auditoria Astra (bloco C), adotada aqui como princípio de desenho: família de
cálculo responde pergunta própria.

| Pergunta | Fonte canônica | Trata igual a...? |
|---|---|---|
| Quantos documentos entraram? | `checklist_engine.get_checklist_status` (já era única — só faltava consertar o bug e parar de duplicar) | dossiê (`dossier.py`), `/processes/{id}/checklist`, `/processes/{id}/progresso` |
| Quanto da Conferência (decisões) está resolvido? | `process_indicators.progresso_conferencia` (NOVA) | dossiê, `/processes/{id}/progresso`, `ConsolidacaoPanel.tsx` (banner) |
| Quantas ações desta etapa estão feitas? | `macroetapa_engine.calculate_completion_pct` | mede ATIVIDADE de etapa — legitimamente outro número, mantido |
| Resultado da ÚLTIMA consolidação | `campos_gravados` (`staging_consolidation.py`) | delta de UMA chamada, não total corrente — rotulado como tal, não confundido com `progresso_conferencia.gravadas` |

**Correção do bug:** `checklist_engine.get_checklist_status` ganha
`received_without_document`; o `completion_pct` deixa de contar "recebido sem
documento" como concluído (`concluidos = received - received_without_document
+ waived`). Não muda o `status` do item na tela — só o que entra no
percentual. `dossier.py` para de duplicar a fórmula e passa a chamar
`get_checklist_status`.

**Novo endpoint** `GET /processes/{id}/progresso` — a resposta única,
nomeada por pergunta (`checklist_documental` + `conferencia`), consumida por
`ConsolidacaoPanel.tsx` (banner) e disponível para qualquer tela futura.

### 2. DOC-001 — estado do documento como PROJEÇÃO, não coluna nova

Medido antes de decidir: os três sinais que já existem (`ocr_status`,
`extraction_status`, `review_required`) respondem perguntas parciais e
sobrepostas, mas nenhum sozinho é "o estado". Duas saídas foram avaliadas —
**(a)** consolidar os três num enum novo (migration, campo substituído) ou
**(b)** expor uma projeção pura sobre os sinais que já existem. Escolhida
**(b)**: mesma filosofia do STATE-001 (derivar, nunca manter estado à parte
para divergir depois) e zero migration de schema para o próprio enum.

`app/services/document_lifecycle.py`:

- `DocumentLifecycleStatus`: `recebido → lido → classificado → extraido →
  conferido` — escada; cada degrau implica os anteriores.
- `derive_document_status(db, document)` — leitura pura: `lido` = texto extraído
  ou `ocr_status ∈ {done, not_required}`; `classificado` = `document_type`
  preenchido e ≠ "outro"; `extraido` = existe `ExtractedFieldStaging` para o
  documento; `conferido` = toda linha de staging do documento saiu de
  `pendente` (`aceito`/`rejeitado`).
- `registrar_transicao_se_mudou(db, document, user_id=None)` — grava a
  transição (quando muda) no `AuditLog` **já existente**
  (`entity_type="document"`, a mesma tabela que `DocumentRepository.add_audit`
  usa para `action="uploaded"`), com hash chain (`stamp_audit_hash`) — nenhuma
  tabela nova. `old_value`/`new_value` guardam de→para; `user_id=None` marca
  gatilho automático (pipeline), preenchido só quando a mudança nasce de um
  gesto humano.

Baseline `recebido` não grava uma segunda entrada: o próprio
`action="uploaded"` do upload (com autor) já a implica.

**Pontos de gatilho** (automáticos, sem tocar a UI):
`document_classification.aplicar_classificacao` (classificado),
`ficha01_extraction.extract_and_stage` (extraído),
`ocr_tasks.emit_leitura_event` via `Session.object_session(doc)` — evita
alterar as ~14 chamadas do helper (lido), e
`staging_consolidation.consolidate_process`, ao final, para todo `document_id`
tocado pela consolidação (conferido — só a consolidação pode fazer TODAS as
linhas pendentes de um documento saírem de pendente na mesma passagem).

**Correção pós-review (mesma frente):** o bloco DOC-001 em `consolidate_
process` roda DEPOIS do `db.commit()` que grava de verdade — uma exceção ali
(sem guarda) propagaria para o endpoint e seria reportada como "nada foi
gravado" quando na verdade JÁ TINHA gravado (o handler de erro do endpoint
registra até uma falha de consolidação permanente no audit_log — inverteria a
garantia que aquele handler existe para dar, achado do code review). Corrigido
com `try/except Exception` largo ao redor do bloco inteiro, com `logger.
warning` — mesmo padrão que `emit_leitura_event` já usa para o gatilho de
`ocr_tasks.py`. Seguro porque `registrar_transicao_se_mudou` é idempotente
(recalcula do zero a cada chamada): uma transição perdida por essa falha se
autocorrige na próxima consolidação ou no próximo gatilho que tocar o mesmo
documento.

### 3. REV-001 — dependência pelos carimbos que já existem, não por snapshot novo

Medido antes de escrever: a proposta original pedia gravar, em cada artefato
(diagnóstico/rota/proposta), a lista de `document_id`/decisões consideradas na
geração. Descartada depois de medir que os carimbos que **já existem**
bastam: `RegulatoryDiagnosis.created_at`/`validated_at`, `Rota.created_at`/
`validated_at`, `Proposal.created_at`/`accepted_at`. Comparar
`Document.created_at`/`extracted_at` e `ExtractedFieldStaging.updated_at` do
MESMO `process_id` contra esse carimbo produz o mesmo aviso observável, sem
tabela nova, sem coluna nova, sem lista de IDs para manter sincronizada.

**Revisão pós-review desta mesma frente:** a primeira versão comparava só
`created_at`/`decided_at` e tinha três falsos negativos medidos por revisão de
código — (1) documento que chega antes do corte mas só fica LEGÍVEL depois
(`extracted_at`, gravado quando o OCR/transcrição termina, não no upload) —
o incidente literal que abriu esta frente; (2) "reabrir" uma decisão zera
`decided_at`, apagando o próprio sinal de mudança; (3) a consolidação carimba
`consolidated_at` sem nunca tocar `decided_at`. Trocar `created_at` sozinho
por `created_at`/`extracted_at` (documento) e `decided_at` sozinho por
`updated_at` (staging — toca em qualquer UPDATE da linha) fecha as três, sem
schema novo: `updated_at` fica `NULL` em linha nunca atualizada (sem
`server_default`), então staging recém-inserido e ainda pendente não soa
alarme sozinho — a chegada em si já é coberta pelo documento de origem.

`app/services/artifact_staleness.py` — só lê, nunca escreve:

- `checar_desatualizacao(db, tenant_id, process_id, cutoff)` — o aviso mais
  antigo entre "documento novo depois de `cutoff`" e "decisão da Conferência
  alterada depois de `cutoff`".
- `desatualizacao_diagnostico`/`desatualizacao_rota`/`desatualizacao_proposta`
  — `cutoff = validado/aceito, senão criado`. O corte usa a validação humana
  quando existe (o critério de aceite da spec é literal: "após diagnóstico
  **validado**").

Exposto em leitura: `RegulatoryDiagnosisOut.aviso_desatualizado`,
`RotaOut.aviso_desatualizado` (ao lado do `aviso_fundamento` do ADR-039 — a
mesma garantia, outro sinal: um olha proveniência achado→passo, o outro olha
documento/decisão), e no corpo de `GET /proposals/{id}`. Nenhum escreve
status, nenhum regenera. `RotaTab.tsx` e `DiagnosisAssinatura.tsx` renderizam
o aviso quando presente.

**Fronteira declarada:** o corte é POR PROCESSO, não por proveniência fina —
um processo com duas frentes de trabalho independentes pode gerar aviso "de
mais" (falso positivo informativo). Preferimos o alarme ao silêncio (mesmo
princípio do "radar não cancela", `app/skills/auditor_imovel`); refinar por
proveniência granular (qual documento efetivamente alimentou qual artefato) é
follow-on nomeado, não feito agora. Falso negativo residual e conhecido,
NÃO coberto pela correção acima: dois gravadores concorrentes tocando a mesma
linha no mesmo instante — este módulo lê timestamp, não é lock; correção
exigiria mecanismo de concorrência à parte, fora do escopo de um aviso
informativo.

## Fora desta frente (registrado, não esquecido)

- **Dívida #26** (unificação `ProcessStatus` × `Macroetapa`) — não é esta
  frente; STATE-001 aqui trata de INDICADORES de progresso, não das duas
  máquinas de estado do processo.
- **Retrocesso automático de etapa** (spec §11, "todo documento novo volta à
  E3") — o Astra classificou como decisão de PRODUTO nova, não conserto.
  REV-001 entrega o aviso; regredir etapa sozinho não foi implementado e
  exige validação da Isis.
- **ROUTE-001** — P2, permanece para depois.
- **Proveniência fina da invalidação** (por documento/decisão específica, não
  por processo inteiro) — ver fronteira declarada acima.

## Consequências

**Ganhos.** Uma pergunta, uma função — o dossiê e o endpoint de progresso
respondem com o mesmo número porque chamam a mesma função. O documento ganha
uma linha do tempo auditável sem tabela nova. Diagnóstico, rota e proposta
avisam quando o chão debaixo deles mudou, sem nunca destruir trabalho humano.

**Custos, ditos por inteiro.**

- O aviso de REV-001 é por processo, não por proveniência — pode soar mesmo
  quando o documento novo é irrelevante para aquele artefato específico.
  Declarado acima, não escondido.
- `progresso_conferencia` reusa `build_decisions`, recomputado a cada leitura
  — mesmo custo que `DecisoesPanel.tsx` já paga; sem cache novo.
- DOC-001 não está wireado em 100% dos caminhos de mutação (ex.: reclassificação
  manual pelo consultor, se existir endpoint próprio, não foi auditada nesta
  frente) — o gate cobre a sequência automática completa; caminhos manuais
  adicionais que mudem `document_type`/staging devem chamar
  `registrar_transicao_se_mudou` também, e ficam como checklist para revisão
  de código, não dívida numerada (a função é idempotente e segura de chamar
  a mais).

## Alternativas descartadas

**DOC-001 como enum consolidado com migration** (substituir os 3 campos por
um só). Descartada por ora: mudaria contrato de leitura em vários lugares
(`ocr_status`/`extraction_status` são lidos em telas e filtros existentes) sem
ganho adicional sobre a projeção — a projeção já responde a pergunta que
faltava sem quebrar nada.

**REV-001 com tabela de snapshot de dependências** (`document_ids`/
`decisao_refs` gravados por artefato). Descartada: os carimbos que já existem
(`created_at`/`validated_at`/`accepted_at`) produzem o mesmo aviso observável
com zero schema novo. Reconsiderar se a fronteira "por processo" (não por
proveniência) se mostrar barulhenta demais na prática.

**STATE-001 forçando os seis números a um só valor.** Descartada — mediria a
coisa errada e escondera decisões de UX válidas (macroetapa mede atividade,
não documento). O correto é nomear cada pergunta, não fundir as respostas.
