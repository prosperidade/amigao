# Calibração da Matriz de Inconsistências — caso real #11 (Fazenda São Jorge)

> PR `fix/matriz-calibracao-caso-real`. Calibra a matriz determinística da Ficha 02
> (`app/services/inconsistency_matrix.py`) contra o **staging real de produção** do
> processo 11 (Leonardo Ribeiro — Fazenda São Jorge, Lotes 1B mat. 4698 e 1C mat. 6776).
> Data: 2026-06-06.

## 0. Origem

A matriz (PR #62) passava no teste **sintético** mas furou no caso real. O prompt
hipotetizou "sinônimos de `field_name` que não casam". A **medição** (abaixo) confirmou
isso só **parcialmente** — e revelou uma causa mais profunda: parte das fontes nunca
chegou ao staging (problema de Fase 2/OCR, upstream e fora do escopo deste PR).

## 1. Medição do staging real (passo "medir, não assumir")

Dump do Supabase de produção (`process_id = 11`). Achados:

- **Só `rat` e `sigef` viraram staging.** Nenhuma linha de `matricula`, `ccir`, `itr`
  ou `car`. As certidões (4698/6776), o CCIR e o ITR **não foram extraídos**.
- **Linhas triplicadas** (3 extrações sem dedup).
- **Área do RAT mal-parseada** em parte das linhas: `area_vetorizada_ha` = `1.0107113`
  (≈ 1 ha, separador de milhar comido) em vez de `1010,7113`. Em outras linhas, correta.
- **Nomes que a Fase 2 grava (medidos) já casam** com o que a matriz lia — para área
  (`area_georreferenciada_ha`, `area_declarada_ha`, `area_registrada_ha`, `area_ha`) e
  denominação (`denominacao`, `nome_imovel`). **Exceção:** `area_vetorizada_ha` (RAT) era
  ignorada. Logo, a hipótese "sinônimos não casam" era só parcial.
- **Pendências do RAT** vêm como `pendencias_rat` = lista de dicts com `categoria`,
  `detalhamento`, `recomendacao`, `atendimento`, `coordenadas`. As **categorias são
  genéricas** (`"Documentos"`, `"Unidades de Conservação"`, `"Inconsistência Adicional"`,
  `"Cobertura do solo"`); o conteúdo discriminante mora no **`detalhamento`**.
- **SIGEF** tem código (`029231.2.0006776-55`) e status (`ativo`) **reais**, mas só do
  Lote 01-C (mat. 6776). O Lote 1B (4698) não tem geo.

### Causa raiz de cada furo de produção

| Saiu (produção) | Causa raiz (do dump) | Camada |
|---|---|---|
| denominação **Consistente** | só o SIGEF trouxe denominação → 1 valor, nada a divergir | Fase 2 (fonte ausente) |
| área **não virou linha** | RAT ignorado + única área reconhecida (SIGEF 349,9) → `len(present) < 2` | **matriz (A)** |
| pendências **só Cobertura+Acesso** | casamento de tema só no `categoria` (genérico); UC/hidrografia no `detalhamento` | **matriz (C)** |
| SIGEF **Consistente** | regra olhava só área, não validava código/status; e era global (mascarava 1B sem geo) | **matriz (D)** |

## 2. Dicionário de sinônimos (construído da medição + `_FIELD_SPECS`)

Constantes em `inconsistency_matrix.py` — **não inventar nomes; adicionar quando a
medição revelar variação nova**:

- `_AREA_SYNONYMS` por `doc_type` (o mesmo nome muda de nível: `area_declarada_ha` é do
  imóvel no CAR e da matrícula no ITR) + `_AREA_LEVEL` (matrícula | imóvel).
- `_DENOM_SYNONYMS` = `denominacao`, `denominacao_imovel`, `nome_imovel`,
  `nome_imovel_rural`, `averbacao_denominacao`.
- `_INCRA_SYNONYMS` = `codigo_sncr_incra`, `codigo_incra`, `codigo_incra_sncr`.
- `_TEMA_KEYWORDS` (pendências do RAT → uc / supressao / hidrografia / cobertura / acesso /
  documentos), casados em **categoria + detalhamento** (não na recomendação — o texto-padrão
  do órgão repete "área antropizada após 22/07/2008", o que falsearia cobertura como supressão).

## 3. O que mudou na matriz (A/B/C/D + dedup)

- **(A) RAT na área.** `area_vetorizada_ha` agora entra como área de **nível imóvel**.
- **(B) Dois níveis.** `_collect_areas` separa área **por matrícula** (confronto entre
  fontes do mesmo `matricula_hint`) e **do imóvel** (CAR/RAT × soma das matrículas).
  Imóvel ≥ 1,5× a soma conhecida (`MISSING_MATRICULA_FACTOR`) ⇒ **ATENÇÃO de vínculo**
  (matrícula faltante), não falsa divergência. Duplicatas da mesma fonte → mantém o
  **maior** valor (recupera a área mal-parseada).
- **(C) Pendências por tema.** Casamento em categoria+detalhamento; **dedup por tema**
  (colapsa a triplicação); UC tenta nomear a unidade (`_extrai_uc`, best-effort — o RAT do
  #11 não nomeia, fica genérico); `documentos` agregam numa linha; `acesso` segue à parte.
- **(D) SIGEF real.** Exige `codigo_certificacao` + `status_certificacao` ativos para
  "consistente"; se o órgão pede o SIGEF (pendência geo no RAT) → **atenção**, não consistente.

Shape do resultado **inalterado** (`fontes/linhas/resumo/gap_d1`); `MatrixRow` e
`status_updates` preservados. `_to_float_br` (usado por `staging_consolidation`) intacto.

## 4. Matriz ANTES × DEPOIS (caso real #11)

| item | ANTES (produção) | DEPOIS (calibrado) |
|---|---|---|
| `area_total` | (sem linha) | **atenção** — soma 349,9 « 1010,7 do imóvel (RAT); "verificar matrícula(s) faltante(s)" |
| `tecnica:uc` | (ausente) | **crítico** — Sobreposição com Unidade(s) de Conservação |
| `tecnica:hidrografia` | (ausente) | **crítico** — nascentes/hidrografias não declaradas |
| `tecnica:cobertura` | crítico | **crítico** (mantido) |
| `acesso_imovel` | atenção | **atenção** (mantido) |
| `documentos_solicitados` | (ausente) | **atenção** — certidão, SIGEF etc. exigidos no RAT |
| `sigef_georreferenciamento` | consistente | **atenção** — cert. real existe, órgão pede apresentação |
| `denominacao_imovel` | consistente | **consistente** (1 fonte — gap honesto, ver §5) |

Validado em `tests/services/test_matriz_caso11_real.py` (fixture = shape real do dump).

## 5. Fora de escopo — follow-on de Fase 2/OCR

A **denominação com 3 variações** ("GLEBA 01 B" no CAR/RAT, "Shangri-lá" no CCIR,
"LOTE 01-C" na averbação) e a **área por matrícula completa** dependem de a extração
entregar certidão/CCIR/CAR — que **não chegaram ao staging** no #11. Isso é **Fase 2/OCR**,
upstream da matriz, e o prompt proíbe mexer ali. Registrar como issue separada:

- por que certidão/CCIR/ITR/CAR não viram `extracted_field_staging` (OCR `pending` /
  classificação de `document_type`);
- triplicação do staging (3 extrações sem dedup);
- `area_vetorizada_ha` mal-parseada (separador de milhar).

## 6. Skill do auditor — gatilho avaliado, sem mudança

O gatilho SKILL foi avaliado: a skill `auditor_imovel/analise_divergencias_documentais`
descreve a taxonomia de **findings LLM** (`AuditFinding`) e as regras de domínio da sócia.
Esta calibração mexe na **matriz determinística** (implementação), **não** nas regras
canônicas de domínio — e a config de agentes é congelada. **Skill não alterada.**
