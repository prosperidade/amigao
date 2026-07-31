# ADR-036 — A norma se confere por identidade; a lacuna de cobertura se declara

- **Status:** aceita
- **Data:** 2026-07-30
- **Branch:** `fix/polimento-validacao-30-07`
- **Decisão de domínio:** Isis (sócia ambientalista), validação do caso 15
- **Correlatas:** ADR-034 (esfera pelo órgão do passivo — é ela que dá o escopo),
  ADR-035 (fonte clicável obrigatória), ADR-033 (biblioteca qualificada)

## Contexto

`lookup_enquadramento` cruzava o enquadramento legal do auto de infração contra o
`knowledge_catalog` por similaridade vetorial (`min_similarity=0.55`), sem
recorte de esfera e sem conferir se o trecho recuperado **era** a norma citada.
Quando havia um hit, a citação era marcada `localizada: True` e virava fonte
clicável no diagnóstico.

Medido no corpus de produção, no caso 15 (autos **federais** do IBAMA sobre
fazenda em Goiás):

| citação no auto | chunk "localizado" | o que o chunk é |
|---|---|---|
| `Art. 70 da Lei 9.605/98` | 4838 | *MT — Compêndio Regente NUC04: Núcleo de Licenciamento Ambiental*, seção "Art. 70.", jurisdição **estadual**, UF **MT** |
| `IN IBAMA nº 14/2009` | 19532 | resolução de **MS** — trecho sobre comércio de iscas vivas |

O primeiro casou pela string `"Art. 70."`. O segundo, por vizinhança semântica.
Nenhum dos dois é a norma citada, e ambos foram apresentados ao consultor como
fundamentação confirmada, com link.

A física do erro está no corpus, não no acaso:

| jurisdição | chunks |
|---|---|
| estadual (MT, AC, MS, GO) | 26.505 |
| federal + nacional | 785 (IBAMA: 106) |

Num corpus com essa proporção, busca vetorial sem escopo **sempre** vai afogar a
esfera minoritária. Não é um caso ruim: é o comportamento esperado do mecanismo.

## Decisão

Três regras, nesta ordem.

**1. Escopo antes da busca.** Havendo esfera derivada do órgão autuante
(ADR-034), a busca de fundamentação é restrita às jurisdições daquela esfera —
`federal` abrange `federal` e `nacional`. Sem esfera identificável, a busca segue
ampla, como antes: não inventar esfera continua valendo.

**2. Identidade, não parecença.** Similaridade responde *"parece com"*; a
afirmação `localizada` promete *"é"*. Um chunk só confirma uma citação se o
**número da norma** aparecer em `identifier`, `title` ou no texto do próprio
trecho (comparação por dígitos — `9.605` e `9605` são a mesma lei). Sem isso, não
está localizada.

**3. Cobertura insuficiente é uma resposta, não uma falha.** Quando a esfera
exigida tem base rasa no corpus (limiar atual: 500 chunks), a citação não achada
deixa de ser reportada como *"não localizada no corpus"* — que sugere ao
consultor que a norma não existe — e passa a declarar:

> cobertura normativa insuficiente para **[órgão]** — base em atualização

acompanhada de um alerta **interno** (`cobertura_normativa_insuficiente`), porque
a ação corretiva é nossa (ingerir corpus), não dele. Com base farta, "não
localizada" continua significando o que sempre significou: a norma não está lá.

## Consequências

- Menos fundamentação exibida, e toda ela verificável. É o resultado desejado:
  a citação errada não era uma fonte a menos, era uma fonte **falsa** — e acerto
  sem fonte é indistinguível de alucinação (ADR-035), mas fonte errada é pior
  que ausência de fonte, porque convida o consultor a confiar.
- A cobertura do corpus vira métrica de produto observável em log, não uma
  suposição. A dívida #47 (corpus federal ausente/raso em produção) ganha um
  sinal que aponta para si mesma toda vez que dói.
- O limiar de 500 chunks é uma calibração, não uma verdade: ajustável quando a
  ingestão federal crescer.
- Onde o chunk carrega `section`, a fonte passa a citar o **dispositivo**
  ("Lei 9.605/98, Art. 70") em vez da norma inteira — o metadado já existia e
  morria no caminho. Item 9 da validação de 30/07.

## Alternativas descartadas

- **Subir o `min_similarity`.** Não separa as duas coisas: o compêndio do MT tem
  similaridade alta *porque* contém literalmente "Art. 70." O problema não é
  fraqueza do match, é ausência de verificação de identidade.
- **Fundamentar com o que se tem, avisando "aproximado".** Foi o que a Isis
  recusou, e com razão: texto plausível e errado é a classe de falha mais cara
  aqui, porque sobrevive a uma revisão apressada.
- **Bloquear o diagnóstico sem fundamentação.** Contraria "radar não cancela":
  a análise segue, com a lacuna dita.
