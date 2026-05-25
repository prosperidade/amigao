# ADR-010 · Loop de aprendizado com material dos consultores

**Status:** Proposto
**Data:** 2026-05-22
**Decisores:** fundador + sócia + tecnologia
**Relacionado:** [`./001-multitenant.md`](./001-multitenant.md), [`./005-pgvector-rag.md`](./005-pgvector-rag.md), [`./006-skills-procedurais.md`](./006-skills-procedurais.md), [`./007-stage-output-content.md`](./007-stage-output-content.md)

---

## Contexto

O ativo mais valioso do Regente não é o modelo nem o código — é o **conhecimento tácito dos consultores ambientais**. Esse conhecimento aparece em três lugares: no método (capturado nas skills, ADR-006), nas normas (capturadas no `knowledge_catalog`, ADR-005) e, sobretudo, nos **materiais que os consultores produzem caso a caso**: ofícios protocolados, diagnósticos validados, pareceres técnicos, respostas de órgão, gabaritos de cada estado.

Hoje esse terceiro acervo se perde. Cada caso resolvido vira um arquivo num diretório e morre ali. O conhecimento que distingue um ofício que retorna com exigência de um que protocola sem retorno — exatamente o problema que o ADR-006 identificou — está nesses materiais, mas não realimenta o sistema.

Dois fatos tornam isso urgente:

1. **Escala nacional (27 estados).** O conteúdo regulatório carregado hoje é GO. Cada estado novo tem legislação, procedimentos e ofícios próprios. Ingestão manual de 27 corpora não escala. Mas o produto vai rodar com consultores validando em campo em vários estados — e esses consultores geram material regulatório real de cada UF como subproduto natural do trabalho.

2. **O moat é de dados, não de modelo.** O modelo é commodity (qualquer concorrente acessa o mesmo LLM). O que ninguém tem é o acervo de como casos reais de regularização ambiental rural foram resolvidos, por estado, com o resultado de cada rota. Quanto mais o Regente é usado por consultores, mais esse acervo cresce — se houver um loop que o capture.

Sem esse loop, a expansão depende de trabalho manual e o produto não fica mais inteligente com o uso. Com ele, o uso alimenta o sistema e cada consultor que valida torna o Regente melhor para os próximos.

## Decisão

Criar um **loop estruturado de captura → curadoria → ingestão → recuperação** do material gerado pelos consultores, realimentando o `knowledge_catalog` (e, quando couber, as skills) por UF e tipo de peça.

Fluxo:

1. **Captura** — o material que o consultor já produz no fluxo normal (diagnóstico validado, ofício, parecer, resposta de órgão recebida, norma estadual que ele citou) é interceptado pelo sistema, sem pedir trabalho extra. O consultor produz; o sistema observa.
2. **Curadoria** — antes de virar conhecimento citável, o material passa por aprovação humana. Estado: `rascunho → em_curadoria → aprovado → publicado` (ou `rejeitado`). Só material `publicado` é recuperável pelos agentes e citável pelo `citation_evaluator`.
3. **Ingestão** — material aprovado entra no `knowledge_catalog` com `source_type` e `doc_type` próprios (ofício, gabarito de diagnóstico, resposta de órgão, norma estadual) e `uf`, gerando embeddings via o gateway (ADR-002).
4. **Recuperação** — os agentes recuperam esse acervo por similaridade na UF do caso, do mesmo modo que recuperam normas. O consultor que abre um caso em TO se beneficia do material que outro consultor validou em TO.

Adicionalmente, **logger de fonte de consulta externa**: quando o consultor registra "consultei MapBiomas / PRODES / sistema X" (H3 da skill de diagnóstico), o sistema grava a fonte, para aprender as fontes preferidas por região — sinal que a própria sócia apontou como ponto de aprendizagem do Regente.

## Por que esse caminho (vs. alternativas)

**Por que não fine-tuning do modelo com o material:**
- Caro e lento; cada novo lote exige retreino
- Não rastreável — não dá para saber de qual material veio uma afirmação (mata a citação rastreável do ADR-007)
- Não permite curadoria fina nem remoção de um item ruim depois de absorvido
- Mistura conhecimento de tenants diferentes dentro dos pesos — risco LGPD irreversível

**Por que não RAG sem curadoria (ingerir tudo automaticamente):**
- Propaga erro. O material dos consultores tem erros reais — vimos um cálculo de compensação aritmeticamente inconsistente sobreviver de uma versão de diagnóstico para outra. Ingerir sem curadoria é elevar o erro a "fonte citável".
- Risco LGPD: material cru contém CPF, matrícula, nome de cliente
- Qualidade variável entre consultores; sem filtro, a média puxa para baixo

**Por que não manter ingestão só manual (status quo):**
- Não escala para 27 estados
- O produto não fica mais inteligente com o uso — desperdiça o moat

**Por que captura no fluxo natural (e não um "envie seu material aqui"):**
- Fricção mata contribuição. O consultor não vai parar para "doar conhecimento"
- Ele já produz o material como parte do trabalho; o sistema captura o que já existe

## Distinção crítica: três tipos de conhecimento

Estende a distinção Skills vs Knowledge do ADR-006 com um terceiro tipo, que é o que este loop principalmente alimenta:

| Tipo | O que é | Exemplo | Onde mora | Como se valida |
|---|---|---|---|---|
| **Normativo** | Fato regulatório objetivo | Texto da IN SEMAD 3/2025 | `knowledge_catalog` | Fonte oficial |
| **Procedural** | Como o agente trabalha | "Em ofício SEMAD-GO, cite Art. 26 da Lei 18.104" | Skills (ADR-006) | Especialista escreve |
| **Exemplar** | Caso real resolvido, por imitação | Ofício protocolado que retornou deferido em MT | `knowledge_catalog` (`source_type` próprio) | **Curadoria do consultor** |

O loop alimenta principalmente o **exemplar** (gabaritos, ofícios, respostas de órgão) e enriquece o **normativo** (quando o consultor traz uma norma estadual ainda não indexada). O **procedural** continua vindo de skills escritas pela especialista — mas o loop pode revelar quando uma skill nova é necessária (padrão recorrente nos exemplares de uma UF).

## A questão LGPD / multi-tenant (decisão estruturante)

Materiais reais contêm dados de clientes (CPF, matrícula, nome, localização). Transformar isso em conhecimento global cruzaria a fronteira de tenant do ADR-001 e violaria LGPD. A regra:

**Separar o PADRÃO do DADO.** O que vira conhecimento global é *como se faz* (a estrutura do ofício, o fundamento usado, a rota que funcionou, o texto da norma estadual). O que NÃO atravessa tenant é *de quem* (CPF, matrícula, nome, polígono específico). Material exemplar é **des-identificado** antes de virar conhecimento global; o dado do caso permanece tenant-scoped.

Decisão sobre escopo do conhecimento exemplar fica em aberto (ver pontos abertos): conhecimento normativo (norma de um estado) é inerentemente global; conhecimento exemplar des-identificado *pode* ser global, mas há um argumento de que parte dele é vantagem competitiva do consultor que o gerou e deveria permanecer no tenant dele.

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Curadoria é gargalo (quem cura não dá conta) | Começar com curadoria centralizada (sócia) só de GO; medir volume antes de distribuir. Curadoria assistida por IA (sugerir aprovação) depois |
| Propagação de erro por curadoria falha | `citation_evaluator` continua validando contra fonte; material exemplar entra com peso menor que norma oficial; rastreabilidade permite remover item ruim |
| Vazamento de dado entre tenants | Des-identificação obrigatória antes de globalizar; dado do caso é tenant-scoped por padrão (ADR-001) |
| Consultor não quer contribuir (moat dele) | Captura no fluxo sem fricção; decisão de escopo (global vs tenant) respeitada; valor de volta (ele usa o acervo dos outros) |
| Qualidade variável entre consultores | Curadoria filtra; sinal de "material que gerou bom resultado" (ofício deferido) pesa mais que material sem desfecho conhecido |

## Pontos abertos (decidir com a sócia)

- **Quem cura, e com que critério de aprovação?** Início provável: sócia, só GO.
- **Conhecimento exemplar é global (des-identificado) ou tenant-scoped?** Trade-off entre força do acervo coletivo e vantagem competitiva individual do consultor.
- **Material exemplar vira só RAG, ou pode promover a skill nova?** Quando um padrão se repete numa UF, vale escrever skill — quem detecta o padrão?
- **Que sinal de "desfecho" capturamos?** Ofício deferido/indeferido, exigência atendida, crédito liberado — para pesar material que funcionou acima de material apenas plausível.
- **Incentivo explícito ao consultor** para validar/contribuir, se a captura passiva não bastar.

## Status de execução

| Item | Estado |
|---|---|
| Decisão arquitetural (este ADR) | Proposto — aguarda fechamento com a sócia |
| `doc_type` estendido (oficio, gabarito_diagnostico, resposta_orgao, norma_estadual) | ❌ A fazer |
| Estado de curadoria (`rascunho→curadoria→aprovado→publicado`) | ❌ A fazer |
| Pipeline de des-identificação de material exemplar | ❌ A fazer — pré-requisito para conhecimento global |
| Captura no fluxo (interceptar diagnóstico validado, ofício, resposta de órgão) | ❌ A fazer |
| Logger de fonte de consulta externa | ❌ A fazer (também listado na skill de diagnóstico) |
| Ingestão de material aprovado no `knowledge_catalog` | Reusa pipeline do ADR-005 |
| Curadoria assistida por IA | ❌ Futuro |

## Relação com outros ADRs

- [`./001-multitenant.md`](./001-multitenant.md) — a fronteira de tenant define o que pode virar conhecimento global; des-identificação é pré-requisito
- [`./005-pgvector-rag.md`](./005-pgvector-rag.md) — material aprovado entra no mesmo `knowledge_catalog`, com `source_type` próprio
- [`./006-skills-procedurais.md`](./006-skills-procedurais.md) — o loop pode revelar quando uma skill nova é necessária; conhecimento exemplar ≠ procedural
- [`./007-stage-output-content.md`](./007-stage-output-content.md) — citação rastreável depende de o conhecimento ter fonte identificável (mata fine-tuning como alternativa)
