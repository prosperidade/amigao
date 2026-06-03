# Trabalho — UI: eliminar termos técnicos (rótulos PT-BR)

> Arquivo único de trabalho. Problema → causa → o que centralizou → telas
> varridas → validação → status.
> Branch: `fix/ui-termos-tecnicos` (base `main`). Data: 2026-06-03.
> Escopo: só camada de apresentação/rótulos. Backend/OCR/chain/storage intactos.

## Problema

Termos técnicos de programação/domínio vazavam para a tela do consultor:

- chaves `snake_case` cruas (`area_hectares`, `proprietario_nome`);
- **JSON cru** quando o valor era objeto/array (`DocumentsTab` fazia
  `JSON.stringify(v)`);
- `demand_type` cru em maiúsculas (`Aplicar trilha CAR` via `.toUpperCase()`);
- campos meta/internos (`confidence`, `*_raw`, `chain_trace_id`…) exibidos como
  se fossem informação útil.

## Causa (verificada lendo o frontend real)

Dois problemas combinados:

1. **Dicionários de rótulos fragmentados e incompletos.** Existiam ao menos
   dois `FIELD_LABELS` independentes e divergentes
   (`components/IntakeWizard/PreviewPanel.tsx` e
   `pages/Intake/DraftDocumentUploader.tsx`), cada um cobrindo um subconjunto
   diferente de campos. Faltavam os campos de matrícula e de RG/CPF.
2. **Vários pontos sem dicionário nenhum**, humanizando com
   `key.replace(/_/g, ' ')` — que só troca `_` por espaço e deixa o termo ainda
   técnico (`area_hectares` → `area hectares`).

### Achado que corrige o briefing (não confiar, verificar)

- O briefing supunha **`CATEGORY_LABELS` duplicado** entre `PropertyHub` e
  `ProcessChecklist`. **Não é duplicação:** são taxonomias diferentes —
  `PropertyHub` mapeia *categorias de documento do imóvel*
  (`fundiarios`, `ambientais`, `fiscais_rurais`, …) e `ProcessChecklist` mapeia
  *categorias de checklist* (`ambiental`, `fundiario`, `pessoal`, …). Cada um é
  usado em um único lugar. **Mesclar seria errado** — mantidos separados.
- O briefing supunha `DEMAND_TYPE_LABELS` em `lib/regulatory/labels.ts`. O real:
  o canônico vive em `pages/Processes/quadro-types.ts` (usado por Quadro,
  MacroetapaSidePanel, DashboardOperacional). `WorkflowTimeline` passou a
  importá-lo. (Há ainda `DEMAND_LABELS` em `ProcessDetailTypes.ts` e um local em
  `Dashboard/index.tsx`, ambos já PT-BR e funcionais — **fragmentação anotada
  como follow-on**, não mexida para não alterar saída visível com/sem emoji.)

## O que centralizou

Novo módulo **fonte única de rótulos de CAMPO**:
`frontend/src/lib/labels/fieldLabels.ts`

- `FIELD_LABELS` — merge de PreviewPanel + DraftDocumentUploader **+** campos de
  matrícula (`area_hectares`, `proprietario_nome`, `numero_matricula`,
  `comarca`, `cartorio`, `denominacao_imovel`, `descricao_limites`, …) e de
  RG/CPF (`nome_social`, `data_nascimento`, `orgao_expedidor`,
  `local_emissao`, `naturalidade`, `validade`, …).
- `labelFor(field)` — rótulo PT-BR ou **fallback humanizado** (capitaliza +
  troca `_`), **nunca** o termo cru com underscore.
- `humanizeValue(value)` — escalar→string, array de escalares→`"a, b, c"`,
  array de objetos→`"N itens"`, objeto→`"Rótulo: valor · Rótulo: valor"`.
  **Nunca** produz JSON cru nem `[object Object]`.
- `isMetaField(key)` — oculta `confidence`, sufixo `_raw`, prefixo `_`
  (`_parse_error`), `geom_present`, `codigo_alerta`, `issue_ids`,
  `chain_trace_id`, `findings_raw`, `method`, `metadata`.

`PreviewPanel` e `DraftDocumentUploader` tiveram seus `FIELD_LABELS` locais
**removidos** e passaram a importar do módulo único.

## Pontos que vazavam — corrigidos

| Arquivo | Antes | Depois |
|---|---|---|
| `AgentResultRenderer.tsx` (ExtratorResult) | `key.replace(/_/g,' ')`, sem filtro meta | `labelFor()` + `isMetaField()` |
| `AgentResultRenderer.tsx` (GenericResult, 3×) | `key.replace(/_/g,' ')`, `GENERIC_HIDDEN_KEYS` local | `labelFor()` + `isMetaField()` central |
| `DocumentsTab.tsx` | `JSON.stringify(v)` + `key.replace(/_/g,' ')` + `capitalize` | `humanizeValue()` + `labelFor()` + filtro meta |
| `WorkflowTimeline.tsx` (3×) | `Tipo: {demand_type}`, `demand_type.toUpperCase()` | `DEMAND_TYPE_LABELS[…]` |
| `DraftDocumentUploader.tsx` | `FIELD_LABELS[field] ?? field`, `String(value)` | `labelFor()` + `humanizeValue()` |

## Telas varridas (pages/ + components/)

Varredura por `key.replace(/_/g,' ')`, `JSON.stringify` em render, `.toUpperCase()`
de campo de domínio e render de objeto cru.

| Área | Status |
|---|---|
| Intake (IntakeWizard, DraftDocumentUploader, PreviewPanel, DiagnosisPanel) | **corrigida** (uploader + preview) / limpa |
| Processos — DocumentsTab | **corrigida** |
| Processos — WorkflowTimeline | **corrigida** |
| Processos — Checklist, Quadro, Macroetapa, Tasks, Alertas, Decisions, Saidas, Timeline, Messages, Dossier, Header, Commercial, LeituraIA | limpas (já usavam dicionário) |
| Componentes — AgentResultRenderer | **corrigida** |
| Propriedades (PropertyHub, index) | limpas (CATEGORY_LABELS próprio, correto) |
| Clientes (ClientHub, index, CredentialsTab) | limpas (`toLowerCase` só em busca/input) |
| AI/Agentes (AgentsPage, AIPanel) | limpas (usam AGENT_LABELS) |
| Dashboard (index, Regente, Operacional) | limpas (`toUpperCase` só em input de UF) |
| Settings, Proposals, Contracts, Auth | limpas |

Usos remanescentes de `.toUpperCase()`/`JSON.stringify` confirmados **legítimos**:
inicial de avatar, normalização de input de UF, e `JSON.stringify` como
*dependency key* (não renderizado).

## Validação

- **Teste de render real** (`fieldLabels.test.tsx`, 8 casos, jsdom): extrator de
  **matrícula** e **RG** renderizam todos os campos com rótulo PT-BR; valores
  corretos; meta ocultos; sem `[object Object]`, sem JSON cru, sem `snake_case`.
  `GenericResult` (diagnóstico/auditor sem renderer dedicado) idem.
- **Suite frontend:** 9 arquivos, **48/48 verdes** (sem regressão em
  `DraftDocumentUploader.test.tsx`).
- `npx tsc --noEmit` **verde**. `npm run build` **verde** (1913 módulos).
- `npm run lint`: meus arquivos **limpos**. Restam 5 erros/warnings
  **pré-existentes** (`AlertaCard.tsx`, `QuadroAcoes.tsx`, `IntakeWizard.tsx`,
  `CredentialModal.tsx`, `PriorityStep.tsx` — regras `react-hooks`),
  confirmados na `main` limpa (stash) e **fora do escopo** deste trabalho.

## Status

**Concluído.** Módulo único de rótulos de campo criado; `FIELD_LABELS`
fragmentados eliminados; nenhum termo técnico, JSON cru ou `[object Object]`
visível nas telas varridas; campos meta ocultos. tsc + build + testes verdes.

### Follow-on (anotado, fora de escopo)

- Unificar os três dicionários de tipo de demanda (`DEMAND_TYPE_LABELS` em
  quadro-types, `DEMAND_LABELS` em ProcessDetailTypes, local em Dashboard) numa
  fonte só — exige decidir o padrão com/sem emoji (muda saída visível).
- Lint pré-existente `react-hooks` em 5 arquivos.
