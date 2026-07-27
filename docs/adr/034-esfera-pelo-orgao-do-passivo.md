# ADR-034 — A esfera vem do órgão do passivo, nunca da UF do imóvel

- **Status:** aceita
- **Data:** 2026-07-26
- **Branch:** `fix/validacao-26-07`
- **Decisão de domínio:** Isis (sócia ambientalista), pós-teste do caso 15
- **Correlata:** ADR-033 (a fundamentação que esta ADR escopa)

## Contexto

A busca de fundamentação (`LegislacaoAgent._load_rag_chunks`) escolhia o recorte
do corpus pela **UF do imóvel** (`Property.state`). É uma heurística que parece
inofensiva e não é.

O caso 15 tem, na mesma fazenda em Goiás:

| passivo | órgão | esfera |
|---|---|---|
| Auto de infração 484341/D e peças correlatas (docs 337, 340, 344, 351) | IBAMA | **federal** |
| Notificação GO-NOT-2024-001985 | SEMAD/GO | **estadual** |

Buscando por UF = GO, o corpus estadual de Goiás domina o resultado e a defesa do
auto **federal** sai fundamentada em norma **estadual**. O texto fica plausível —
cita norma real, do estado certo, sobre o tema certo — e está errado no que mais
importa: a competência.

Essa é a classe de erro mais cara do produto, porque não parece erro. Um
consultor com pressa não distingue "norma correta" de "norma da esfera errada"
numa leitura rápida.

## Decisão

**1. A esfera de um passivo é derivada do ÓRGÃO que o emitiu.**
`app/services/esfera.py:esfera_do_orgao()` mapeia órgão → `federal` / `estadual`
/ `municipal`. O órgão **nomeado sempre vence a pista geográfica**: "IBAMA-GO" e
"Superintendência do IBAMA em Goiás" são federais, apesar do "GO" no nome.

**2. Não saber é uma resposta.** Sem órgão reconhecível, `esfera_do_orgao()`
devolve `None` e o sistema **não escolhe uma esfera por padrão**. Chutar
"estadual porque o imóvel é em GO" é exatamente o que esta ADR proíbe.

**3. Um caso tem N passivos com N esferas.**
`app/services/passivos_esfera.py` varre os documentos de fiscalização
(`auto_infracao`, `certidao_embargo`) e o relato do intake, e devolve cada
passivo com órgão, esfera e **fonte**. A fundamentação roda **uma varredura de
corpus por esfera presente**, dividindo a cota de trechos entre elas — o caso com
dois passivos precisa de fundamentação dos dois, não do dobro de trechos de um.

**4. A esfera do domínio mapeia para as jurisdições do corpus.** `federal`
abrange `jurisdiction in ('federal', 'nacional')` — resoluções CONAMA e afins são
de alcance nacional, não estaduais. `knowledge_catalog.search(jurisdiction=...)`
passou a aceitar lista para isso.

**5. Fonte obrigatória, com peso declarado.** Passivo lido de documento carrega
`SourceRef(tipo="documento", confianca="alta")`; passivo lido do relato do
cliente carrega `SourceRef(tipo="atendimento", confianca="baixa")` e aparece na
tela como *"relato do cliente — não conferido em documento"*. Foi exatamente o
rótulo que faltou na GO-NOT-2024-001985: o dado estava certo e vinha do relato,
mas a tela o exibia com o mesmo peso de um dado extraído de documento — o que
tornou "certo" indistinguível de "inventado" (ver ADR-035).

## Consequências

- A UF continua sendo usada — mas só para escopar a busca **estadual**, que é
  onde ela de fato significa alguma coisa.
- Caso sem passivo com órgão identificável cai no caminho anterior (por UF): o
  comportamento novo é aditivo, não substitui o antigo às cegas.
- Cobertura: `tests/services/test_esfera_por_orgao.py`, incluindo o caso real de
  dois passivos com duas esferas e os controles negativos de sigla curta
  (`ima` dentro de "estimativa", `ana` dentro de "Paraná").

## Alternativas descartadas

- **Perguntar a esfera ao LLM.** Devolveria o problema ao lugar onde ele nasceu;
  a esfera é determinística a partir do órgão.
- **Cadastrar todos os órgãos estaduais.** Frágil: uma UF esquecida vira
  classificação errada silenciosa. Há uma lista nomeada **mais** um padrão
  genérico (`SEMA-XX`), e o desconhecido devolve `None`.
