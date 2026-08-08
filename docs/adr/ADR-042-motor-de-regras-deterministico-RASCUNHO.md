# ADR-042 · Motor de regras determinístico ao lado do RAG

**Status:** RASCUNHO — não aceito. Aguarda respostas da Isis (4 pendências marcadas).
**Data:** 2026-08-05
**Decisores:** André (final), Isis Terra (autoria do domínio), tecnologia
**Faixa de numeração:** produto (200–299) para dívidas derivadas; corpus (100–199) para o que tocar `knowledge_catalog`.

---

## Contexto

Em 05/08/2026 a Isis entregou o pacote **BASES DA REGULARIZAÇÃO**: 8 matrizes, 159 abas, 14.056 linhas, cobrindo Federal + GO + SP + MG + MT em oito eixos (CAR/PRA; fundiário-cadastral; uso e cobertura do solo e desmatamento; hidrografia e recursos hídricos; outorga e segurança de barragens; relevo, solos, geologia e vegetação; embargos, autuações e sanções; áreas protegidas, cavidades e territórios especiais).

Dentro delas, **325 regras de negócio**, todas com condição lógica e resultado esperado preenchidos (zero incompletas — medido). Exemplar fiel, da matriz 1:

```
ID:                        REG-BR-CAR-002
UF:                        BR
Tema:                      Natureza do CAR
Descrição:                 O CAR não constitui título de propriedade ou posse.
Tipo de regra:             Alerta
Entrada necessária:        CAR; documentos dominiais
Condição lógica:           Usuário tenta concluir titularidade apenas pelo CAR
Resultado esperado:        Bloquear conclusão dominial
Mensagem ao consultor:     O CAR é declaratório ambiental e não comprova domínio ou posse.
Fonte normativa:           NOR-FED-001
Dispositivo:               Art. 29
Grau de confiança:         Alto
Exige decisão profissional: Não
Pode ser automatizada:     Sim
Status de implementação:   Validada
```

Distribuição por jurisdição: 198 valem para todas as UFs; BR 29, MT 26, GO 24, MG 24, SP 21, Federal 3.

Três propriedades desse material são decisivas e não estavam disponíveis antes:

1. **A regra não está em lei nenhuma.** A lei diz o que vale; a regra diz o que fazer quando o caso bate. É o método da consultoria destilado — o ativo que nenhum concorrente pode baixar de portal público.
2. **`Pode ser automatizada` e `Exige decisão profissional` vêm classificados regra a regra**, pela autora do domínio. O Princípio 1 ("a IA propõe; o humano decide e assina") deixa de ser política geral aplicada por julgamento e passa a ser atributo do dado.
3. **A proveniência é relacional, não textual.** `Fonte normativa` é chave (`NOR-FED-001` → aba `02_Fontes_Normativas`) e `Dispositivo` é campo separado (`Art. 29`). É exatamente o vínculo cuja ausência produziu a dívida **#121** (mesmo texto sob três identidades) e casa com o campo `dispositivo` criado no `knowledge_catalog` pela Fase 3 do chunking (#119).

## Decisão

**Um motor de regras determinístico, executado ao lado do RAG e nunca dentro dele.**

Os dois motores respondem perguntas diferentes e têm naturezas incompatíveis:

| | RAG + LLM | Motor de regras |
|---|---|---|
| Pergunta | "o que a norma diz sobre X?" | "este caso viola alguma regra?" |
| Natureza | probabilístico | determinístico |
| Saída | texto interpretado | disparou / não disparou |
| Verificação | citation evaluator, pós-fato | reprodução exata, sempre |
| Custo | tokens por consulta | zero |
| Falha típica | alucina, cita fonte errada | não dispara (visível no teste) |

O motor decide; o RAG fundamenta. Quando uma regra dispara, o texto normativo que a sustenta vem do corpus **pelo `dispositivo` já declarado na regra** — recuperação por chave, não por similaridade. É a fusão dos dois ativos sem misturar as naturezas.

### Fonte de autoria × fonte de execução

**A planilha é a fonte de autoria. Não é a fonte de execução.**

A Isis escreve nas matrizes — é onde o método vive e onde ela trabalha bem. Mas o sistema executa a partir de tabela versionada no banco, populada por importação que registra origem (arquivo + hash), versão e data.

Razão registrada, aprendida na série #114/#121/#122/#123: nossos defeitos não são de dado ausente, são de **dado presente e não consultado**. Regra viva apenas em planilha na máquina de alguém é a mesma família — verdade que o sistema não consulta.

### O que entra e o que não entra

- Regra sem `Fonte normativa` **não entra**. Princípio 11 por construção.
- Regra com `Exige decisão profissional = Sim` **nunca conclui sozinha** — propõe e para, conforme ADR-011 (NON_BLOCKING_REVIEW_AGENTS).
- Regra com `Pode ser automatizada = Parcialmente` entra como proposta com campos faltantes explicitados, nunca como veredito.
- `Status de implementação` é do domínio (Isis validou), não da engenharia. Um segundo campo, próprio do sistema, registra se a regra está implementada em código.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Ingerir as regras como chunks no RAG | Perde o determinismo. A regra viraria trecho a ser interpretado — exatamente o que ela existe para evitar. E competiria por recall com a legislação. |
| Codificar as regras em Python (`if/else` no serviço) | Só o desenvolvedor consegue mudar uma regra da Isis. Acopla o método ao ciclo de deploy e mata a autonomia da autora do domínio. |
| Colocar as regras no prompt dos agentes | Volta a ser probabilístico: o LLM pode ignorar, reinterpretar ou aplicar parcialmente. E 325 regras não cabem em contexto. |
| Motor de regras de terceiros (Drools, etc.) | Peso operacional desproporcional. As condições são simples; o valor está no conteúdo, não no engine. |

## Consequências

**Positivas**
- Diferencial defensável: 325 condições lógicas com jurisdição e fonte, que não existem em fonte pública.
- Auditoria trivial: regra disparada é reproduzível byte a byte, sem custo de token.
- Cobertura de 5 UFs de uma vez — SP e MG entram no produto pelas regras antes de entrarem pelo corpus.
- Testável: cada regra vira caso de teste; o motor tem cobertura mensurável, coisa que RAG não tem.

**Negativas**
- Manutenção do vocabulário: as matrizes não usam as mesmas colunas (ver PENDENTE-1). Unificação tem custo e risco de perda de nuance.
- Risco de regra desatualizada silenciosa — norma muda, regra não. Exige data de revisão visível e ciclo declarado (ver PENDENTE-4).
- Conflito entre regras precisa de resolução declarada, não emergente (ver PENDENTE-3).

**Mitigações**
- Toda regra carrega `Última revisão`; regra sem revisão dentro do ciclo aparece como envelhecida, não como inválida.
- Motor registra em audit trail toda avaliação: regra, entrada, resultado, versão da regra.

## Relação com outros ADRs

- **ADR-011** — regra com decisão profissional segue o padrão não-bloqueante.
- **ADR-041** (chunking) — o campo `dispositivo` criado na Fase 3 é a chave de ligação regra → texto normativo.
- **ADR-005** (pgvector/RAG) — este ADR não altera o RAG; declara o que **não** deve ir para ele.
- **#121** — a proveniência relacional das matrizes é insumo para resolver a atribuição no corpus.

---

## PENDENTE — aguarda resposta da Isis

**PENDENTE-1 · Vocabulário canônico.** A matriz 1 usa `Tema / Tipo de regra / Grau de confiança`; as matrizes 5–8 usam `Eixo / Ação do Regente / Severidade`. São sinônimos ou conceitos distintos? Qual conjunto vira o oficial? *Bloqueia o schema da tabela.*

**PENDENTE-2 · Campo `Tipo de regra` deslocado.** Em parte significativa das linhas, esse campo contém o texto da condição ("Interseção > 0", "Multa em aberto") em vez do tipo (Validação/Alerta/Bloqueio/Checklist/Roteamento). Deslocamento de coluna no preenchimento, ou uso deliberado com outro sentido? *Bloqueia a importação — importar sem resolver gravaria dado errado com cara de dado certo (família #121).*

**PENDENTE-3 · Semântica de severidade e conflito.** (a) "Bloqueio" impede o card de avançar de etapa, ou marca e o consultor decide? (b) Quando regra federal e estadual divergem no mesmo caso, quem vence — há hierarquia geral ou depende do tema? *Bloqueia o comportamento do motor.*

**PENDENTE-4 · Ciclo de atualização.** Frequência real de mudança e via de edição: planilha reimportada ou tela no Regente? *Decide se a importação é one-shot ou recorrente, e se há editor no roadmap.*

**PENDENTE-5 · Versão da matriz 2.** O arquivo veio como `..._Preenchida (1).xlsx`. Confirmar que é a versão corrente.

---

## Sequenciamento

Esta frente **não abre agora**. Ordem acordada: fechar Ficha 7 (validação da Isis) → concluir Fase 4 da remediação do chunking → então este ADR é fechado com as respostas e vira plano de implementação.

Nada nas matrizes foi ingerido, importado ou escrito em qualquer banco. O pacote está inventariado apenas.
