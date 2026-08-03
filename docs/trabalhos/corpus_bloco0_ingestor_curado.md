# Bloco 0 + Bloco 1 — ingestor curado e núcleo 06

**Branch:** `feat/ingestor-curado-nucleo06` · **Data:** 2026-08-03 · **ADR:** 038

> O PR #129 mergeou durante esta rodada. As dívidas foram para
> `docs/REGISTRO_DIVIDAS.md` como **#106 a #109** — renumeradas, porque o #129
> consumiu 102–105. Este documento é o registro do trabalho.

---

## O que foi entregue

**Bloco 0** — o corpus deixa de ser dirigido por lista no código e passa a ser
dirigido por **manifesto CSV versionado**. Três peças:

| arquivo | papel |
|---|---|
| `app/services/manifesto_corpus.py` | schema + validação (falha no carregamento, antes de baixar) |
| `scripts/extrair_manifesto.py` | planilha da Isis → CSV rascunho (agrupa por URL) |
| `scripts/ingest_manifesto.py` | executa o manifesto, com as 8 garantias |

**Bloco 1** — núcleo 06 (Infrações, Embargos e Responsabilização):
**5 normas ingeridas, 686 chunks, US$ 0,0048.** Federal+nacional: 1.600 → 2.288.

---

## Dívidas abertas

**106. Avaliar a versão COMPILADA como camada adicional do corpus.** A planilha
da Isis aponta as versões compiladas de Decreto 6.514/2008, Lei 12.651/2012 e Lei
6.938/1981; o corpus tem as **anotadas**. A decisão de 03/08 foi manter as
anotadas — são elas que trazem `"Redação dada pelo Decreto nº 12.189, de 2024"`
inline, e é isso que sustenta *tempus regit actum* (ADR-037). A compilada
responde melhor "o que vale hoje" e polui menos o chunk. Ter as duas dobraria o
texto dessas três normas. **O que destrava:** decisão da Isis sobre se o ganho de
clareza compensa a duplicação. Enquanto isso, a escolha está codificada no
manifesto (as três dão `skip` por hash idêntico a cada rodada).

**107. A Constituição compete consigo mesma na busca.** A CF entrou íntegra (495
chunks — 72% de todo o bloco 06). O art. 225 é recuperável **quando a consulta o
nomeia** (similaridade 0,69), mas uma paráfrase do próprio texto do artigo
("todos têm direito ao meio ambiente ecologicamente equilibrado") traz o **art.
205** (educação) à frente dele. Não é defeito da ingestão: é um documento de 495
artigos onde cada um disputa com os outros 494. **O que destrava:** filtro ou
reforço por dispositivo quando a citação nomeia artigo — parente da regra de
identidade do ADR-036, agora aplicada dentro de um mesmo documento. Medido em
03/08, não corrigido aqui.

**108. Frente própria: os 165 alertas da curadoria.** A aba `Alertas_Regente` da
planilha traz 165 linhas de "gatilho → ação sugerida". **Isso não é corpus, é
spec de motor de diagnóstico** — e o Auditor já tem ~40 alertas implementados.
**O que destrava:** comparar os 165 com os 40 atuais, mapear sobreposição e
lacuna, e implementar em ondas. Não fazer junto com corpus: são coisas
diferentes que só parecem próximas por virem na mesma planilha.

**109. Referências operacionais são o embrião do "onde protocolar".** As 10
linhas `referencia_operacional` do núcleo 06 (FAQ do auto, consulta de áreas
embargadas, obter certidão de embargo, REGULARIZE/PGFN, impedimentos do MCR) são
exatamente o que o **editor de rota do consultor** (dívida #86) precisa consumir:
onde se protocola, onde se consulta, onde se obtém. Hoje estão versionadas no
manifesto e não são exibidas em lugar nenhum. **O que destrava:** o editor de
rota ler o manifesto por bloco.

**#98 — pedido à Isis (ampliado de novo).** Agora com quatro itens:
(a) PDF oficial da IN IBAMA 10/2012; (b) os `.md` originais do Acre (`AC-N04`,
`AC-N05`, `AC-N10`); (c) PDF oficial da **IN IBAMA 21/2023**; (d) PDF oficial da
**Portaria IBAMA 15/2026**. Os itens (c) e (d) têm a mesma causa dos anteriores:
o portal do IBAMA responde 403 a cliente não-browser.

---

## Retorno de curadoria para a Isis

Está em `docs/trabalhos/retorno_curadoria_isis_2026-08-03.md`, escrito em
português simples para o André repassar.

---

## Blocos seguintes (registrados, não feitos)

| bloco | escopo | observação |
|---|---|---|
| 2 | núcleos 02 (Territorial/Cadastro) e 03 (Florestal/CAR/PRA) | 32 + 37 linhas na planilha |
| 3 | núcleos 01, 04, 05 | 23 + 42 + 44 |
| 4 | núcleos 07 a 12 | 45+48+46+49+20+46 |
| 5 | estadual — 27 UFs | planilha `ECOSSISTEMA_NORMATIVO_..._MAPEAMENTO_ESTADUAL.xlsx` |

**Expectativa calibrada pelo bloco 1:** das 43 linhas do núcleo 06 saíram **3
normas novas de texto sancionador** (mais a CF e uma histórica). A matriz é
analítica e o corpus já cobre boa parte do canônico federal — o valor dos
próximos blocos provavelmente também não será volume. Melhor saber agora do que
descobrir no bloco 5.

**Critério de curadoria para os próximos (ADR-038, item 6):** priorizar material
**interpretativo** — OJNs, pareceres normativos, notas técnicas de procuradoria,
INs de rito — sobre o canônico já coberto. A medição do bloco 1 mostrou por quê:
a OJN 06/2009 da PFE-IBAMA ocupou 4 das 8 vagas de recuperação, à frente do
próprio Decreto 6.514/2008. O decreto diz o que a lei determina; a OJN diz como o
órgão a aplica — e é ela que vincula quem vai julgar o recurso.
