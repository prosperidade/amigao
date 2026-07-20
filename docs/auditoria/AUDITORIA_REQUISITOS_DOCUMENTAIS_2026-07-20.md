# Auditoria — fonte única de requisitos documentais (2026-07-20)

> **Fase 1 (read-only) do PR `fix/fonte-unica-requisitos-documentais`.**
> Sintoma relatado: o sistema mostra "4 documentos pendentes" e acusa MATRÍCULA
> ausente num caso onde a certidão de inteiro teor **foi enviada**. Mesmo sintoma
> que o forense caso Isis corrigiu no emissor `MISSING_MATRICULA` — reapareceu
> em outra superfície.
>
> **Conclusão da auditoria: a hipótese do André está certa, e é pior do que
> "N lógicas".** Não existe nenhuma noção compartilhada de "requisito documental
> satisfeito" no código. Existem 8 lugares que respondem a essa pergunta, cada um
> com uma fonte da verdade diferente, e no caso real **três deles discordam entre
> si sobre a mesma matrícula, no mesmo processo, no mesmo instante**.

---

## 1. O caso concreto — processo 15 (prod, nada apagado)

**Processo 15** — "Defesa Administrativa / Auto de Infração"
**Property 12** — "Fazenda São Jorge – Lotes 1B (matrícula 4698) e 1C (matrícula 6776)"
Caso criado em 2026-07-20 13:19 UTC. 42 documentos anexados.

### 1.1 Os "4 documentos pendentes" — quem gera

A frase exata que aparece na tela é produzida em
`app/models/macroetapa.py:487`:

```python
blockers.append(f"{documents_pending_required} documento(s) obrigatório(s) pendente(s)")
```

O número vem de `missing_docs`, contado em `app/api/v1/processes.py:225-228`
(kanban) e **de novo, literalmente duplicado**, em `app/api/v1/processes.py:350-353`
(detalhe). Ambos varrem o JSON `ProcessChecklist.items` contando
`required=True AND status="pending"`.

Chega ao consultor por:
- `frontend/src/pages/Processes/QuadroProcessCard.tsx:77` — `card.missing_docs_count`
- `frontend/src/pages/Processes/WorkspaceRightPanel.tsx:217` — "Requisitos pendentes — veja as travas abaixo"
- `frontend/src/pages/Processes/ProcessChecklist.tsx:205` — "Docs obrigatórios pendentes"

### 1.2 Quais são os 4 — e a surpresa

Estado real do checklist do processo 15:

| item_id | label | doc_type | required | status | document_id |
|---|---|---|---|---|---|
| `auto_infracao` | Auto de Infração / Notificação | `auto_infracao` | sim | **pending** | — |
| `matricula` | Matrícula do Imóvel | `matricula` | sim | `received` | 317 |
| `car` | CAR | `car` | sim | **pending** | — |
| `fotos_area` | Fotos Atuais da Área | `foto` | sim | **pending** | — |
| `doc_proprietario` | Procuração / Documento do Proprietário | `doc_pessoal` | sim | **pending** | — |
| `laudo_anterior` | Laudo ou Relatório Anterior | `laudo` | não | pending | — |

**Os "4 pendentes" NÃO incluem matrícula** — ali ela está `received`.
A acusação de matrícula ausente vem de **outra superfície**, no mesmo processo.
O consultor lê as duas na mesma tela e entende como uma lista só. A confusão
do relato é, ela própria, o sintoma: **duas respostas para a mesma pergunta**.

### 1.3 O caminho exato da certidão de inteiro teor

| id | arquivo | document_type | ocr_status | texto | checklist_item_id |
|---|---|---|---|---|---|
| 317 | `Certidão Inteiro Teor Mat. 6.776 19-08-25.pdf` | `matricula` | done | 33.712 ch | **NULL** |
| 318 | `Certidão de Inteiro Teor Mat. 4698 Lote 1B.pdf` | `matricula` | done | 117.900 ch | **NULL** |

A classificação funcionou: `ficha01_extraction.py:130-137` mapeia "inteiro teor"
→ `matricula` corretamente (herança do caso #11).

O staging **também** funcionou — `extracted_field_staging` tem o número:

| document_id | field_name | valor | status |
|---|---|---|---|
| 317 | `numero_matricula` | `{"value": "6.776"}` | `pendente` |
| 318 | `numero_matricula` | `{"value": "4698"}` | `pendente` |
| 317 | `area_registrada_ha` | `349,9022 ha` | consistente |
| 318 | `area_registrada_ha` | `660,6561 ha` | consistente |

Mas a materialização **não** aconteceu:

```
properties.id = 12 → registry_number = NULL
                     matriculas do imóvel = 0   ← zero linhas
```

A consolidação (staging → `Matricula`) ainda não rodou; o staging está `pendente`.

### 1.4 A linha exata que falhou

`app/services/dossier.py:291-301`:

```python
tem_matricula = any(
    (m.numero_matricula or "").strip() for m in prop.matriculas_vigentes()
)
if not prop.registry_number and not tem_matricula:
    issues.append(Inconsistency(code="MISSING_MATRICULA", severity="error",
                                title="Matrícula do imóvel ausente", ...))
```

Com `matriculas = []` e `registry_number = None`, a condição é verdadeira →
**"Matrícula do imóvel ausente"**, severity `error`, com duas certidões de
inteiro teor anexadas, lidas por OCR e com o número já extraído no staging.

**A lógica não está errada — está respondendo outra pergunta.** Ela pergunta
"o *dado* matrícula está materializado?" e imprime a resposta como se fosse
"o *documento* matrícula existe?". São perguntas diferentes e o código as
colapsou numa string só. O forense curou a cegueira a `Matricula` materializada;
não curou a confusão entre **dado consolidado** e **documento presente**.

### 1.5 Por que o teste do forense não pegou

`tests/services/test_matricula_ausente_reconhece_doc.py:52,59` — **as duas
asserções passam `documents=[]`**:

```python
codigos = {i.code for i in validate_technical_consistency(process, prop, [], None)}
```

O teste `test_sem_matricula_e_sem_registry_number_acusa_ausente` afirma que
"sem `Matricula` → acusa ausente" é o comportamento **correto** — sem nunca
considerar que possa haver documento enviado. O caso do André cai exatamente
no buraco entre os dois testes: documento presente + dado não consolidado.

---

## 2. Mapa completo — todos os pontos que decidem "satisfeito / pendente / ausente"

| # | Local (file:linha) | Fonte da verdade | Lógica de matching | Teste |
|---|---|---|---|---|
| 1 | `services/checklist_engine.py:207` (`auto_link_document`) | `Document.document_type` | **igualdade exata de string** contra `item.doc_type` | nenhum |
| 2 | `services/checklist_engine.py:98-123` (`get_checklist_status`) | JSON `ProcessChecklist.items[].status` | lê estado congelado | nenhum |
| 3 | `api/v1/processes.py:225-228` (kanban) | JSON `items[]` | `required and status=="pending"` | `test_movimentacao_card.py` (parcial) |
| 4 | `api/v1/processes.py:350-353` (detalhe) | JSON `items[]` | **cópia literal de #3** | nenhum |
| 5 | `services/dossier.py:291-301` (`MISSING_MATRICULA`) | `Property.registry_number` + `matriculas_vigentes()` | dado materializado **vigente** | `test_matricula_ausente_reconhece_doc.py` (cego a documentos) |
| 6 | `services/dossier.py:380-390` (`CAR_NO_MATRICULA_DOC`) | `doc_types` (set) + `prop.matriculas` (**todas**) | `"matricula" not in doc_types` | idem |
| 7 | `services/dossier.py:396-407` (`MISSING_CCIR`) | `Matricula.codigo_incra_sncr` | campo derivado | `test_ccir_depreciado.py` |
| 8 | `models/macroetapa.py:485-489` (`list_macroetapa_blockers`) | recebe `missing_docs` de #3/#4 | propaga contagem alheia | `test_ramo_e2.py`, `test_macroetapa_gate.py` |

### 2.1 As divergências — o diagnóstico propriamente dito

**D1 — Três respostas para a mesma pergunta (o bug do André).**
No processo 15, sobre a mesma matrícula, no mesmo instante:
- #2/#3/#4 (checklist): **SATISFEITO** (`received`, doc 317)
- #5 (dossiê): **AUSENTE** (`MISSING_MATRICULA`, severity error)
- realidade: **RECEBIDO, EM PROCESSAMENTO** (staging `pendente` com o número extraído)

Nenhuma das duas respostas exibidas é verdadeira.

**D2 — Vigência inconsistente dentro do mesmo arquivo.**
`dossier.py:292` usa `prop.matriculas_vigentes()`; `dossier.py:381` usa
`prop.matriculas or []` (todas). `agents/diagnostico.py:315,448` também usa
todas. Uma matrícula histórica (#60/ADR-027) satisfaz um e não o outro.

**D3 — Vocabulário divergente entre documento e requisito.**
Não há mapa `doc_type → requisito`. Os vocabulários simplesmente não batem:

| documento tem | requisito espera | casa? |
|---|---|---|
| `cpf_cnpj` (doc 316) | `doc_pessoal` | **não** |
| `ccir` (docs 314, 315) | *nenhum item* | **não** |
| `matricula` | `matricula` | sim (por sorte de nomenclatura) |

O item `doc_proprietario` do processo 15 está pendente **com a CNH do
proprietário anexada** (doc 316, `CNH-e L.R.pdf`, OCR done). Segunda instância
do mesmo bug, na mesma tela, ainda não relatada.

**D4 — Vínculo é evento, não função do estado.**
`auto_link_document` só roda no upload (`documents.py:215`) e na migração de
draft (`intake.py:356`), usando o `document_type` **daquele instante**. A
classificação por conteúdo (`classify_doc_type`) roda depois, no OCR/extração,
e **nada reprocessa o vínculo**. Consequência medida: **36 dos 42 documentos
do processo 15 têm `document_type = NULL`** — o `elif body.document_type:` de
`documents.py:214` nem chega a chamar o matching. Esses 36 nunca serão
vinculados a requisito nenhum, por construção.

**D5 — Vínculo gravado só de um lado.**
`checklist_item_id` é **NULL em 100% dos 42 documentos**, inclusive no doc 317
que o checklist declara `received`. O estado vive só no JSON do checklist; o
documento não sabe que satisfaz um requisito. Qualquer consumidor que parta do
documento (não do checklist) enxerga o requisito como não atendido.

**D6 — Lógica duplicada por cópia.**
#3 e #4 são o mesmo loop de 4 linhas, copiado. Divergem no dia em que alguém
corrigir um só — que é precisamente como esta classe nasceu.

---

## 3. Por que a cura do forense não bastou

O forense caso Isis corrigiu **um emissor** (`MISSING_MATRICULA`, #5) para
enxergar **uma fonte a mais** (`Matricula` materializada além de
`registry_number`). Foi uma correção correta e insuficiente pela mesma razão
que qualquer correção pontual seria: o sistema não tem onde guardar a resposta
certa. Cada superfície nova reimplementa a pergunta, e cada reimplementação
nasce com um recorte diferente do que conta como "satisfeito".

Enquanto "requisito documental satisfeito" for uma expressão booleana escrita
inline em 8 lugares, o próximo consumidor será o nono. A Fase 2 não corrige o
nono — cria o lugar onde a resposta mora e move os oito para lá.

---

## 4. O que a Fase 2 vai fazer

1. `services/requisito_documental.py` — `requisito_documental_status(processo,
   requisito)` com 3 estados: `AUSENTE` · `RECEBIDO_EM_PROCESSAMENTO` ·
   `SATISFEITO`, e mapa `doc_type → requisito` centralizado (fecha D1, D3).
2. Os 8 consumidores do mapa migram para ela (fecha D2, D6).
3. Semântica honesta na tela: com documento visível, nunca "ausente" —
   "recebido, em processamento" ou "recebido como `<tipo>` — confirme se
   atende `<requisito>`" (P12 aplicado a requisitos).
4. Matrícula histórica satisfaz **presença** documental sem contar na soma
   (não confundir vigência com presença — ADR-027/#60).
5. Testes: o caso real do André (317/318 → nunca "ausente") + 1 por consumidor
   migrado.

### Fora do escopo deste PR (dívidas novas)

- **#70** — reprocessar o vínculo doc↔requisito quando a classificação por
  conteúdo altera `document_type` depois do upload (D4). Os 36 documentos
  `NULL` do processo 15 precisam de um backfill; a fonte única os lê pelo
  conteúdo/staging, mas o `document_type` persistido segue nulo.
- **#71** — gravar `Document.checklist_item_id` no mesmo commit que marca o
  item como recebido, tornando o vínculo bidirecional (D5).

*(S5-C reservou #69 em `feat/s5c-assinatura-saidas`, ainda não mergeado —
por isso esta auditoria começa em #70.)*
