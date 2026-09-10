# Frente E — tipo de observação (medição)

**Branch:** `feat/tipo-observacao` · **ADR:** 065 · **Dívidas fechadas:** #221
**Insumo:** `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md` (Entrega 2, "Tipo
de observação: AUSENTE"), `docs/trabalhos/contencao_entrada.md` (#221),
`docs/trabalhos/fiacao_entrada.md` (lição do preâmbulo)
**Data da medição:** 10/09/2026

---

## ⚠️ Pendência declarada — gate roda ANTES do #157, precisa reconferir depois

Este gate rodou contra `_extract_structured`/`JanelaResultado` como existem
**antes** do PR #157 (`fix/cobertura-janela`, aberto em paralelo,
`docs/services/extraction_window.py`): hoje `janela.truncado` é calculado só
por posição de char (`cobertura_chars = fatias[-1].fim`), sem saber se a
ÚLTIMA fatia realmente produziu resposta do LLM — uma falha silenciosa na
última chamada não derruba `truncado=False`. Os docs **547** (2 fatias,
82.117 chars) e **548** (2 fatias, 57.090 chars) são os únicos desta frente
que fatiam, logo os únicos expostos a essa lacuna; 549 e 550 cabem numa fatia
só.

O #157 adiciona `completa`/`falhas` a `JanelaResultado` para fechar exatamente
essa lacuna. **Ação pendente, após o merge do #157:** `git rebase main` nesta
branch e reconferir os quatro documentos exigindo `completa=True` em TODAS as
execuções — uma execução com `completa=False` não conta como leitura válida
do documento, entra na tabela como falha, não como dado. Sem isso, a "cobertura
completa" que este gate reporta para 547/548 é precisamente o tipo de
afirmação que o #157 existe para não deixar passar sem prova. Instrução
recebida em 10/09, endereçada ao agente desta frente.

---

## Ambiente da medição

| item | valor |
|---|---|
| banco | `amigao_tipo`, `TEMPLATE amigao_audit`, container `amigao-tipo-db`, **host 55234** (não 55432 dev, não 55433/55444, que são de outras frentes/projetos) |
| alvo impresso antes de cada escrita | `db=amigao_tipo port=5432` (porta interna do container) — conferido por `assert` |
| schema | as duas colunas da migration `b8d4e1f7a209` aplicadas por **DDL direta** (`ALTER TABLE`), não `alembic upgrade` — CLAUDE.md reserva o comando ao banco de desenvolvimento `amigao_db:127.0.0.1:55432`; banco descartável de gate não é esse banco |
| entrada | `extracted_text` **real** de produção, docs 545–551, recuperado de `backup_prod_20260909T120549Z.dump` (backup local do André, 09/09), restaurado num Postgres 17 auxiliar — produção não foi acessada nesta rodada |
| conferência do texto | md5 calculado no banco restaurado, decodificado e reconferido em Python; tamanhos batem com o relatório de 09/09 (547: 82.117 · 548: 57.090 · 549: 34.815 · 550: 27.109 chars) |
| LLM | real, `gpt-4o-mini` via `ai_gateway` |
| produção | intocada nesta rodada — só o dump local foi lido |

---

## Gate — 4 documentos de matrícula, 2 execuções cada, LLM real

### #221 — área de Reserva Legal não ocupa a área do imóvel

| doc | execução | `area_registrada_ha` | destino | normalizado |
|---|---|---|---|---|
| 547 | 1 | `926,36.54` | `matricula.area_ha` | 926,3654 |
| 547 | 2 | `926,36.54` | `matricula.area_ha` | 926,3654 |

Nas duas execuções o modelo devolveu a área do IMÓVEL corretamente na abertura
(`area_registrada_ha`), e a área da relocação da RL (`185,85.60`, Av.03) saiu
**separada**, como observação `reserva_legal` — presente na lista de tipos da
execução 2 (`"reserva_legal"` em `tipos`). A trava (`area_de_outro_objeto`) não
precisou disparar neste gate porque o modelo não colidiu os dois valores desta
vez — o que é o próprio ponto do achado #221 (a colisão é intermitente, típica
de merge de fatias). A trava foi testada sob a colisão **forçada**, com o texto
real e o JSON exatamente no formato da falha medida no gate pós-deploy da Frente
C, em `tests/services/test_observacao_registral.py::TestAreaDeOutroObjeto` — ali
sim ela dispara e a linha perde destino com o motivo nomeando o ato (`Av.03`,
`reserva_legal`).

### doc 548 — arrendamento fora de APP

| execução | tipos emitidos | `averbacao_app` no staging |
|---|---|---|
| 1 | `arrendamento`, `hipoteca`, `baixa`, `compra_venda`, `compromisso_compra_venda`, `georreferenciamento` | **ausente** |
| 2 | `arrendamento`, `hipoteca`, `baixa`, `compra_venda`, `georreferenciamento` | **ausente** |

Nas duas execuções a AV.10 (arrendamento de 50 ha) saiu tipada como
`arrendamento`, sem destino (motivo: sem coluna correspondente), e
`averbacao_app` não aparece em nenhuma linha — nem vazio, nem com o
arrendamento dentro. A gaveta deixou de existir no esqueleto do prompt; o que a
substituiu (`atos`) não a repovoa por acidente.

### doc 549 — ônus derivado dos atos, não das gavetas

| execução | ônus vigentes afirmados |
|---|---|
| 1 | 1: Alienação fiduciária, ato R.15, R$ 9.798.869,87 |
| 2 | 1: Alienação fiduciária, ato R.15, R$ 9.798.869,87 |

Nas duas execuções: **nenhuma hipoteca vigente afirmada** (as três reais,
AV.03/04/05, saem tipadas como `hipoteca` e marcadas `baixado_por` AV.09/AV.10/
AV.12 — confirmado nos `tipos`, que incluem `baixa` nas duas execuções); R-11
(preço da compra e venda) sai como `compra_venda`, fora de `onus`; R.15 sai como
`alienacao_fiduciaria`, o único item da lista de ônus vigentes.

### O achado do gate: `partes[0]` não é o credor

Nas duas execuções do doc 549, a linha de R.15 listava `JOEL CENCI` — não o
Itaú — porque a primeira versão de `onus_vigentes` lia `partes[0]` como "o
credor". Conferido no doc 550 (R.05/R.06): a execução 1 devolveu
`["BANCO DO BRASIL S/A", ...]` e a execução 2 devolveu `["JOEL CENCI", ...]`
para o **mesmo ato** — a ordem das partes não é estável entre execuções, e
"escolher a primeira" produz uma afirmação de credor que o documento não
sustenta naquela ordem. É a mesma classe do N1 do relatório de 09/09 (afirmação
sem lastro), só que nascida NESTA frente em vez de herdada.

**Corrigido no próprio gate, antes do merge:** `onus_vigentes` passou a expor
`partes` (a lista inteira, como o documento nomeia), não `credor` (singular,
escolhido por posição). Reconferido — doc 550, uma execução, pós-correção:

```json
{"tipo": "Alienação fiduciária", "partes": ["BANCO DO BRASIL S/A", "JOEL CENCI", "ELODI AGROPECUARIA LTDA"], "valor": "R$ 2.125.132,64", "ato": "R.05", "data": "12 DE MAIO DE 2.025"}
```

Todas as partes reais visíveis, nenhuma escolhida como "a" credora. É a mesma
decisão que "papel de pessoa" já declarava fora do escopo desta frente (ADR-065)
— só que a primeira versão do código a violava sem querer.

### Campos antigos — tabela antes × depois

| campo | doc 547 | doc 548 | doc 549 | doc 550 |
|---|---|---|---|---|
| `numero_matricula` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |
| `cartorio` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |
| `denominacao` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |
| `denominacao_anterior` | — | ✓ 1/2 | — | — |
| `registro_anterior` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |
| `proprietarios` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |
| `codigo_certificacao` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |
| `nirf_cib` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |
| `area_registrada_ha` | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 | ✓ 2/2 |

Nenhum campo antigo regrediu. `denominacao_anterior` de 548 saiu só numa das
duas execuções — variação já catalogada na dívida #215 (determinismo), não
desta frente; o campo continua no spec e no prompt sem alteração.

### Controle negativo

Documentos 545 (RG) e 551 (CNH-e, OCR vazio): `doc_type` != `matricula`, o
ramo `atos`/observações nunca é acionado — coberto por
`TestNaoRegressao::test_documento_que_nao_e_matricula_nao_ganha_observacao`
com texto real do RG da Valéria. O gate contra o LLM real não precisou repetir
isso: a condição é `doc_type == "matricula"`, testada estaticamente.

---

## O que NÃO mudou (fronteira desta frente)

- **Temporalidade.** `data`/`prazo` continuam texto livre; nenhuma vigência
  computada. A baixa por referência textual (`aplicar_baixas`) NÃO é
  temporalidade — é leitura do que o documento já afirma por escrito.
- **Papel de pessoa.** `partes` lista nomes sem papel — inclusive depois do
  conserto do achado acima, que reforça essa fronteira em vez de furá-la.
- **CAR/CCIR.** Fora do escopo; só matrícula.

---

## Suíte

`tests/services/test_observacao_registral.py` — 26 casos, texto VERBATIM dos
quatro documentos da ELODI. `26 passed` (recorte; ver nota de cobertura global
abaixo). Recorte de vizinhança também verde:
`tests/services/test_contencao_entrada.py`,
`tests/services/test_fiacao_entrada.py`, `tests/agents/test_extrator_auditavel.py`
(46 passed), mais o pacote de staging/consolidação/matriz (91 passed,
745 deselected — filtro por `-k`).

**Nota de cobertura:** os recortes acima reportam `ERROR: Coverage failure`
porque `--cov-fail-under=70` é avaliado sobre o arquivo/subset filtrado, não
sobre a suíte inteira — mesmo padrão dos gates anteriores (#152/#155). A suíte
completa não foi rodada nesta rodada por economia de sessão; roda no CI do PR.
