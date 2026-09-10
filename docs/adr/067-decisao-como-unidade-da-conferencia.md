# ADR-067 — Decisão como unidade da Conferência

**Data:** 10/09/2026
**Status:** Aceita
**Frente:** G — reconciliação e Conferência por decisões (`feat/reconciliacao-decisoes`)
**Insumo:** `docs/auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md` §3,
§5, §6 (REC-001, CONF-001), `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md`
("Decisão agrupada" — INSUFICIENTE), `docs/adr/062-fonte-unica-registral.md`,
`docs/adr/065-observacao-registral-tipada.md`, `docs/adr/066-temporalidade-de-ato-derivada-por-regra.md`
(item "Fora do escopo": REC-001/CONF-001 dependem da vigência — esta frente),
`docs/adr/012-decisao-consultor-contextual-ao-processo.md`,
`AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md` bloco B
**Dívidas fechadas:** REC-001, CONF-001 — com fronteiras declaradas abaixo
(aceite em bloco de várias decisões, DOC-001/STATE-001, invalidação
transitiva ficam fora)
**Dívida aberta:** nenhuma nova nesta frente

---

## Contexto

Medido na ELODI (caso #23): 42 linhas de staging para 8 fatos do domínio que a
spec Isis nomeia (titularidade, composição de matrículas, área por matrícula,
área total, RL, gravames, CAR, representante). O sintoma mais concreto
(`CONFIRMACAO_ENTRADA_2026-09-09.md`, linha "Decisão agrupada — INSUFICIENTE"):
a matrícula 3.181 aparecia em DUAS linhas — `matricula_listada` do CAR e
`numero_matricula` da certidão, mesmo hint, destinos diferentes, duas decisões
cobradas da consultora por um fato só. A própria confirmação já apontava a
saída: "o hint já é a chave natural de agrupamento; falta a decisão que
consome as duas."

A Conferência (`ConsolidacaoPanel.tsx`) agrupa por ENTIDADE (Cliente / Imóvel /
Matrícula N), não por FATO — dentro de cada grupo, cada linha de
`ExtractedFieldStaging` é uma decisão independente. É a granularidade certa
para "onde este valor pousa" (a pergunta que a Ficha 01 resolve) e a
granularidade errada para "o que a consultora precisa confirmar" (a pergunta
da Conferência).

## Decisão

### A chave natural, não uma entidade nova

Medido antes de escrever código (Astra, bloco B): `ProcessDecision` é log de
governança por macroetapa (`decision_type`, `basis` com documentos/stage_outputs/
ai_readings) — sem chave natural, sem noção de "mesmo fato em duas fontes".
`ProcessIssueDecision` é a decisão do consultor sobre um ACHADO regulatório
(`RegulatoryIssue`, 5 botões `DecisaoConsultor`) — contextual ao processo
(ADR-012), mas sobre outra NATUREZA de fato: um achado já é uma conclusão do
auditor, não um dado cadastral em disputa entre documentos. Nenhuma das duas
serve de base; estender qualquer uma delas para caber aqui seria forçar uma
entidade a significar duas coisas.

A decisão desta frente **não é uma linha nova na base**. É uma função pura,
`app/services/reconciliation_decisions.py:build_decisions`, que agrupa
`ExtractedFieldStaging` (já existente, já com `tipo_observacao`/`atributos`
das Frentes E/F) por **chave natural**: `(entidade, identificador, aspecto)` —
ex. `("matricula", "3181", "composicao")`, `("imovel", "23", "reserva_legal")`.
Recomputável a qualquer leitura; nenhum estado a sincronizar, nenhuma migration.
"Gravada" continua sendo a mesma leitura de `consolidated_at` que a tela já
mostra por campo ("Aceito" ≠ "Gravado", validação 30/07/02-08) — só agregada
por grupo, não uma coluna nova.

### Regras de chave, por tipo de fato (não por documento)

| Aspecto | Chave | Evidências |
|---|---|---|
| `composicao` | `(matricula, hint, composicao)` | qualquer linha declarando `numero_matricula`/`matricula_listada` com este hint — CAR, certidão, CCIR, ITR, SIGEF |
| `area` | `(matricula, hint, area)` | área de NÍVEL matrícula (mesmos sinônimos de `inconsistency_matrix._AREA_SYNONYMS`) |
| `area_total` | `(imovel, process_id, area_total)` | CAR gráfica + CAR documental + soma calculada das decisões `area` (injetada depois de montar o grupo — não é uma fonte, é o resultado das outras decisões) |
| `reserva_legal` | `(imovel, process_id, reserva_legal)` | observação tipada `reserva_legal` (qualquer matrícula) × `rl_declarada_ha` do CAR |
| `gravames` | `(matricula, hint, gravames)` | toda observação tipada em `TIPOS_GRAVAME` desta matrícula — uma decisão por matrícula, não por ato |
| `titularidade` | `(cliente, process_id, titularidade)` | linhas de cliente (`full_name`/`document`) |
| `identificacao` | `(representante, document_id, identificacao)` | linhas de representante, uma por documento pessoal (CNH) |
| `car` | `(imovel, process_id, car)` | `numero_car`/`status_car` |

Contagem: na ELODI (4 matrículas), isto produz **mais de 8 decisões**
(`composicao`×4 + `area`×4 + `area_total` + `reserva_legal` + `gravames`×4 +
`titularidade` + `car` + `identificacao`) — a spec nomeia 8 FATOS na narrativa
do caso, mas "composição de matrículas (4)" já indica 4 decisões, uma por
matrícula (é exatamente o que fecha REC-001: "matrícula 3.181, UMA decisão").
Registrado aqui, não forçado: o número certo é o que a chave natural produz,
não 8 por definição. Ver a tabela medida no PR.

### Concordância/divergência por REGRA, nunca LLM

`aspecto` numérico (`area`, `area_total`, `reserva_legal`) compara por
`parse_area_ha` + a régua de 4 níveis já validada pela sócia
(`property_audit.grade_area_divergence`: ≤1% informativo, 1-5% atenção, 5-10%
alto, >10% crítico) — a MESMA régua da skill do auditor, não uma nova. Os
demais aspectos comparam por texto normalizado (`inconsistency_matrix.
norm_compare`). `composicao` e `gravames` não comparam VALOR — a chave já
garante que é o mesmo fato (ou a evidência é uma síntese de atos, não um
número em disputa): múltiplas fontes corroborando é "concordam" por definição.

Fonte autoritativa por ADR-062 — não uma regra nova: registral (matrícula)
para `composicao`/`area`/`reserva_legal`/`gravames`/`titularidade`; ambiental
(CAR) para `car`; `area_total` não tem fonte única (é soma calculada) e
`identificacao` não compete (é a própria CNH da pessoa).

### Estado da decisão, gravação

`decidir_decisao_agrupada` (`staging_consolidation.py`) aplica `decide_field`
a cada linha do grupo ainda pendente — a mesma função, o mesmo gate de
`divergente_transcricao`/`escolher_fonte`/sibling-rejection que o campo a
campo já usa. Só a evidência marcada `fonte_autoritativa` (ADR-062) resolve
uma divergência sem escolha explícita; sem fonte única marcada, a decisão
exige o mesmo gesto manual de hoje. "Decidida" (todas as linhas saíram de
pendente) e "gravada" (`consolidated_at` presente) continuam DISTINTOS — o
clique em "Gravar na base" não muda; decidir por decisão só poupa o clique
repetido, 42 → ~N.

### Tela: decisões, com "sem agrupamento" sempre visível

`ConferenciaTab` passa a renderizar decisões (evidências expansíveis por
fonte, recolhidas quando concordam). Linha sem regra de chave (`sem_
agrupamento`) continua na lista campo a campo existente — nunca escondida.
Escolha DELIBERADA: a lista antiga não foi removida, só deixou de repetir o
que uma decisão já cobre. Campo já coberto por `ConsolidacaoPanel.test.tsx`
(GATE existente, `cartorio`/`rat_protocolo`) não casa com nenhuma chave desta
frente — continua passando sem alteração, prova de que a mudança é aditiva.

## Fora do escopo desta frente (registrado, não esquecido)

- **Aceite em bloco de várias decisões** (spec §11) — decidir uma por vez já
  reduz 42 → ~N cliques; múltiplas de uma vez é frente própria.
- **DOC-001/STATE-001** (fonte única de contagem) — depende de a decisão
  existir; próxima frente.
- **REV-001** (invalidação transitiva) — depende de estado.
- **Aceite em bloco por matrícula inteira** (todas as decisões daquela
  matrícula de uma vez) — mesma razão do primeiro item.

## Gate

`tests/services/test_reconciliation_decisions.py` — fixtures com os trechos
VERBATIM já vetados nas Frentes E/F/fiação (`tests/services/
test_observacao_registral.py`, `test_fiacao_entrada.py`: docs 546/547/549 da
ELODI, extracted_text real de produção lido via MCP read-only nas frentes
anteriores). Pull fresco de produção nesta sessão foi bloqueado pelo
classificador de auto-modo (`execute_sql` recusado); os valores usados são os
já medidos e citados nesta própria spec/ADR-066 (492,9252 × 437,7632; 926,3654;
3.181; 3.673; R.15) — não inventados, mas não re-verificados nesta rodada.
Tabela campo × antes × depois (regressão das Frentes C-F) e a lista completa
de decisões da ELODI/Valéria: `docs/trabalhos/reconciliacao_decisoes.md`.
