# Fiação da entrada — o dado chega e não pousa

**Data:** 09/09/2026 · **Branch:** `fix/fiacao-entrada` · **Base:** `ed2c327` (main, com #152/ADR-064)
**Insumo:** `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md`, Entrega 2 — as linhas
**INSUFICIENTE (material existe, ligação falta)**. As linhas **AUSENTE** ficam para a frente seguinte.
**Sem ADR:** é fiação, não decisão. Nenhum modelo novo, nenhuma migration.

---

## O que a frente ligou

Quatro dados que a extração **já produzia** (ou que o texto já trazia) e que morriam
antes de chegar a colunas **que já existiam e estavam NULL**.

| # | dado | onde morria | agora vai para |
|---|---|---|---|
| 1 | cadeia de titulares | JSON trazia os 4; `_FIELD_SPECS["matricula"]` não tinha a entrada → **0 linhas** | `matricula.proprietarios` |
| 2 | averbação de Reserva Legal | a gaveta existia; o prompt dizia `"averbacao_rl"/"averbacao_app"` na MESMA linha, sem distinguir | `matricula.averbacao_rl` |
| 3 | módulos fiscais | `"Módulos Fiscais: 31,1547"` no texto do CAR, coluna no banco, **o prompt não pedia** | `imovel.modulos_fiscais` |
| 4 | área documental do CAR | recibo declara DUAS áreas; o esqueleto tinha **um** slot | `imovel.area_documental_ha` |

**Regra da fiação (herdada do #152):** todo campo novo passa pela âncora — valor sem
trecho no texto não ganha destino. Nada do que o #152 fechou foi reaberto.

### Por que `proprietarios` é UMA linha, não quatro

Os quatro titulares são da **mesma** matrícula e disputariam a **mesma** coluna.
Quatro linhas fariam a primeira gravar e as outras três virarem **reconciliação
falsa** (`field_sources` já marcado + `_values_differ`). É a diferença para
`car.matriculas`, onde cada item tem `matricula_hint` próprio e, portanto, linha de
destino própria. A âncora composta do #152 preserva o rastro **por titular**: 4 nomes
+ 4 CPFs = 8 folhas, todas conferidas contra o texto.

---

## Gate — banco descartável `amigao_fiacao`, texto real, LLM real

`127.0.0.1:55433/amigao_fiacao`, criado por `TEMPLATE amigao_entrada` para **não
colidir** com o gate do #152, que roda no `amigao_entrada`. Alvo impresso e afirmado
por `assert` antes de qualquer escrita (`db=amigao_fiacao port=55433`); guarda extra
contra a porta 55432 (dev). Produção não acessada. Migration head `99fb989b546c` —
inalterada, a frente não tem migration.

ANTES = `main` (`ed2c327`) · DEPOIS = `fix/fiacao-entrada`. Mesmo script, mesmo banco,
staging truncado entre as execuções.

| doc | tipo | linhas antes | linhas depois | o que entrou |
|---|---|---|---|---|
| 545 | doc_pessoal | 0 | **0** | controle negativo — nenhuma linha nova |
| 546 | car | 10 | **12** | `area_documental_ha` · `modulos_fiscais` |
| 549 | matricula | 8 | **10** | `proprietarios` · `averbacao_rl` |
| 550 | matricula | 8 | **8** | `proprietarios` entrou; `codigo_certificacao` piscou (#215) |
| 551 | doc_pessoal | 0 | **0** | controle negativo — nenhuma linha nova |

### As linhas novas, com valor e âncora

| doc | campo | valor gravado | conf | destino | âncora |
|---|---|---|---|---|---|
| 546 | `area_documental_ha` | `"2180.3923"` | high | `imovel.area_documental_ha` | char **2.679**, dígitos |
| 546 | `modulos_fiscais` | `"31,1547"` | high | `imovel.modulos_fiscais` | char **405**, dígitos |
| 549 | `proprietarios` | 4 titulares (Nascente, Alexandre, Karina, ELODI) | high | `matricula.proprietarios` | composto, **8/8** folhas |
| 549 | `averbacao_rl` | `{"area": "492,9252", "referencia": "AV.02"}` | high | `matricula.averbacao_rl` | composto, **2/2** folhas |
| 550 | `proprietarios` | 5 titulares | high | `matricula.proprietarios` | composto, **10/10** folhas |

**A AV.02 é o resultado mais duro da frente.** A confirmação de 09/09 registrou:
*"a averbação registral de RL é a AV.02, de 492,9252 ha em conjunto com as matrículas
1.224 e 1.225. Nenhuma das duas execuções capturou a AV.02"*. Com a gaveta separada no
prompt, ela sai — com área e número do ato, ambos ancorados no texto.

**Nenhuma linha existente foi alterada.** Em 546 e 549 o conjunto de campos anteriores
é subconjunto exato do posterior (`SUMIRAM: []`). Cobertura de janela em todos: 1 fatia,
100% do texto (4.286 / 29.854 / 27.109 chars).

---

## Uma regressão que a frente produziu, mediu e consertou

A primeira versão do prompt do CAR abria com `Instruções de completude:` seguido de
bullets **só para os três campos que a frente mexia**. Efeito medido, 3 execuções de
cada lado, doc 546:

| campo | main | 1ª versão da fiação |
|---|---|---|
| `app_declarada_ha` = `90,4225` | **3/3** | **0/3** |
| `rl_declarada_ha` = `437,7632` | **3/3** | **0/3** |

O modelo leu a lista de instruções como **a lista de campos que importam** e parou de
preencher dois campos antigos do próprio esqueleto — que não foram tocados por nenhuma
linha do diff. Conserto: preâmbulo dizendo que os bullets esclarecem apenas os campos
ambíguos e que **todos** os campos do JSON continuam valendo, mais um bullet curto para
cada um dos dois. Depois do conserto: **3/3** dos oito campos, incluindo os dois novos.

**A lição, que vale para a frente seguinte:** num prompt-esqueleto, acrescentar
instrução para alguns campos **apaga** os demais se não houver preâmbulo dizendo o
contrário. Não é risco teórico — aconteceu, em 3 de 3 execuções, e só apareceu porque o
gate compara campo a campo contra o `antes`, e não só o total de linhas.

---

## O que NÃO entrou, e por quê

**#218 — a área de RL do CAR entra em campo de STATUS.** `rl_declarada_ha` →
`imovel.rl_status`, uma `Column(String)` cujo domínio é `averbada | proposta | pendente
| cancelada`, recebendo `437,7632`. `Property` tem `app_area_ha` para a APP e **não tem
par para a RL**. Fiação liga a coluna que existe; aqui não existe. Criar `rl_area_ha` é
migration + backfill + decidir o destino dos `rl_status` legados que hoje guardam número.

**#219 — a área GRÁFICA do CAR continua sem chegar a `area_grafica_ha`.** Ela segue em
`total_area_ha`, como sempre; `area_grafica_ha` só é preenchida pelo RAT. Pedir a mesma
área duas vezes ao modelo criaria duas linhas com o mesmo valor e destinos diferentes —
a classe do **REC-001**, que esta frente não tem mandato para criar.

**Nada de tipo de observação nem de temporalidade.** `onus` continua sem data, número de
ato e cancelamento; `averbacao_app`/`averbacao_rl` continuam sem vigência. São as linhas
**AUSENTE** da Entrega 2, e continuam sendo a frente seguinte.

**#215 mordeu de novo, e num campo escalar.** Doc 550, `codigo_certificacao` — intocado
pelo diff — presente em 3/3 antes e 2/3 depois. Registrado como medição adicional na
própria #215. É a razão pela qual este gate compara **presença de campo e destino**,
nunca valor exato entre execuções.

---

## Fronteira declarada

- **Docs 544, 547 e 548 não foram medidos:** o `extracted_text` deles não existe nesta
  máquina (só em produção, sem credencial aqui). O 547 é justamente o de 82k chars, o
  único que exercita **duas fatias** com os campos novos.
- **O doc 549 aqui tem 29.854 chars; em produção tem 34.815.** A cópia local é menor.
  Os trechos que a frente mede (AV.02, os quatro titulares, o NIRF) foram **conferidos
  como presentes** antes de rodar, mas o documento não é byte a byte o de produção.
- **Nada foi consolidado.** O gate mede staging; `consolidate_process` não foi chamado.
  O caminho staging → coluna já estava coberto por `_IMOVEL_FIELDS`/`_MATRICULA_FIELDS`
  (ambos já continham os quatro destinos) e por `fit_json_container`, que já tinha
  `LIST_ITEM_KEY["proprietarios"]`.

## Aceite pós-deploy

1. Reprocessar o doc **547** (82k, duas fatias) e conferir que `proprietarios` chega
   mesclado das duas fatias sem repetir titular.
2. Conferir no processo 23 que `imovel.area_documental_ha` e `imovel.modulos_fiscais`
   ficam preenchidos após "Gravar na base", e que `total_area_ha` **não muda**.
3. Conferir que `averbacao_app` deixou de receber o arrendamento do doc **548**
   (AV.10, 50 ha para terceiro) — é o caso que o item 2 endereça e que esta máquina
   não pôde medir.

## Testes

`tests/services/test_fiacao_entrada.py` — 10 casos com trechos VERBATIM dos docs 546 e
549. Recorte executado: **155 testes verdes** (`test_contencao_entrada`, `test_ficha01_*`,
`test_fase2_validators_dedup`, `test_fiacao_entrada`, `test_extrator_*`,
`test_consolidacao_integrada`, `test_auditor_matriz`, `test_fase4_consolidacao`,
`test_matricula_chain_vigencia`, `test_matriz_perfis_identidade`, `test_vtn_nao_vira_acao`,
`test_classificacao_identidade_2607`, `test_inconsistency_matrix`, `test_matriz_caso12_real`).
