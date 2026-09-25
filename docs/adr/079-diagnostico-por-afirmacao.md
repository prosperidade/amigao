# ADR-079 — Diagnóstico por afirmação no contrato de evidência

- **Data:** 24/09/2026
- **Estado:** proposta (Incremento 5, dívida #285). Decisões marcadas **[André]** pedem aceite no PR.
- **Plano:** [Plano Diretor v1.1 — Incremento 5](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md)
  ("diagnóstico por afirmação com premissas · risco, urgência e serviço têm premissas e
  aplicabilidade · lacuna não vira passivo"), §4.2 (skill do diagnóstico: "reconciliar
  semanticamente") e §6.2 (`conclusao`: premissas, aplicabilidade, certeza, impacto, urgência).
- **Consome:** [ADR-069](069-contrato-contexto-revisao.md) (envelope, `EvidenceObject`, revisão),
  [ADR-074](074-metodos-e-fechamento-comercial.md) (diagnóstico em revisão vira ressalva do orçamento).

## Contexto (medido em 23–24/09)

1. **O diagnóstico real não produz conclusão pelo contrato.** No #25 de dev (job 201,
   `gpt-5.6-luna`, 61.222 tokens, US$ 0,015) a resposta veio no schema legado (`situacao_geral`,
   `passivos_identificados`…) e o passo falhou com o erro cru `'objects'` (KeyError).
2. **Causa:** o `run_step` do ADR-069 manda, **antes** da instrução do contrato, o prompt-base
   legado `diagnostico_system` (fallback de código, sem versão no banco), que termina em
   "Retorne APENAS JSON válido com: situacao_geral…". O modelo obedeceu a primeira ordem. A skill
   (1.3.0) ainda descreve `DiagnosticoPreliminarContent` como "o que você produz".
3. **O contrato aceita afirmação sem premissa.** `EvidenceObject` exige premissa só para `risco`;
   uma `hipotese` ou `fato_documental` sem premissa passa. Não há certeza nem impacto nem urgência
   como dimensões; o método da Ísis fala em grau de risco (4 níveis) e confiança, e o Plano em
   "risco separado de certeza e urgência".
4. **DIAG-002 a DIAG-009 não estão versionados no repositório.** Só a DIAG-001 tem texto
   ([SPEC v0.1](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md), "toda conclusão
   precisa apontar evidências; sem base suficiente, hipótese, não determinado ou lacuna"). A
   DIAG-005 aparece citada ("não há embargo registrado" sem consulta). As demais estão no segundo
   DOCX da Ísis, fora do repo; o [Mergulho §8.4](../arquitetura/MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md)
   resume o grupo: "conclusões com premissas, lacunas explícitas e dimensões independentes de
   risco/certeza/urgência; nenhuma ausência não verificada, obrigação ou risco promovido sem suporte".

## Decisão

### 1. Prompt-base do contrato, não o legado

No contrato 069, o diagnóstico recebe um prompt-base próprio, versionado em código
(`app/services/diagnostico_contrato.py`, `CONTRATO_VERSAO = "079.3"`), gravado no job com hash e
origem `contrato_079`. O `diagnostico_system` legado **não é enviado**. O pedido termina no schema
de `EvidenceObject`, como antes. O teto por chamada é o do agente
(`AI_MAX_COST_PER_JOB_USD_DIAGNOSTICO`), como no agente legado — o caminho do contrato tinha
perdido o repasse e o #23 foi barrado no teto global (US$ 0,1192 > 0,10).

**Sintaxe (transporte), não conteúdo:** resposta que não é JSON ganha **uma** nova chamada; as
duas ficam no job (`resposta_sem_sintaxe`) e o custo do job é o pago nas duas. Regras de admissão
(§3) nunca ganham nova chamada. Medido no #23 de dev: um `]` faltando em `limits`.

A 079.2 acrescenta um exemplo de item e a regra de forma "`kind` é sempre `conclusao`": na 079.1
o modelo pôs a classe em `kind` do 4º item em diante (#25, job 210).

**079.3 — o modelo não escolhe espécie nem identidade.** A regra de forma não bastou: no #23
(286 mil tokens de envelope) a classe voltou a `kind`. O diagnóstico passa a receber o schema
`AfirmacaoDiagnostico` — só o que ele decide (texto, classe, premissas, dimensões, aplicabilidade,
conhecimento, limites) — e o servidor monta a `conclusao` com espécie, origem e identidade, que já
atribuía. `kind` diferente de `conclusao` na resposta é erro nomeado, nunca corrigido.

Resposta sem a chave `objects` falha com motivo nomeado ("resposta
fora do contrato: faltou `objects`; veio `situacao_geral`, …"), não com `KeyError`.

### 2. Afirmação = conclusão com três dimensões independentes

Cada afirmação é um `EvidenceObject` `conclusao`, com `statement`, `conclusion_class` e premissas
por ID e versão **do envelope**. Três dimensões em `attributes`, independentes:

| Dimensão | Valores | Quando |
|---|---|---|
| `certainty` | `alta` · `media` · `baixa` | toda afirmação |
| `impact` | `informativo` · `atencao` · `alto` · `critico_impeditivo_potencial` (os 4 níveis do método) | toda afirmação de `risco` |
| `urgency` | `alta` · `media` · `baixa` | opcional; **[André]** vocabulário provisório, PENDENTE-ISIS |

`impact` e `urgency` entram em `EvidenceAttributes` como campos opcionais (nenhum dado antigo muda).

### 3. Regras de admissão (determinísticas, no servidor)

A afirmação que viola uma regra é **recusada**, e a execução falha com a lista (`regra: afirmação —
motivo`); nada é gravado. Mesmo comportamento do G7 do Incremento 1 (ausência sem verificação).

| Regra | Conteúdo | Origem |
|---|---|---|
| D1 | Toda afirmação tem ao menos uma premissa, e toda premissa está no envelope autorizado | DIAG-001 |
| D2 | `certainty` obrigatória; `alta` exige premissa **documental** (fonte primária ou observação) | DIAG-001; skill ("confiança alta exige documento") |
| D3 | `risco`, `fato_documental` e `escopo_proposto` exigem premissa documental: derivação de inventário, declaração ou outra conclusão sozinhas não sustentam | "lacuna não vira passivo"; skill ("ausência de informação isolada é lacuna") |
| D4 | `risco` exige `impact`, aplicabilidade `aplicavel` e razão (a última já no schema) | Plano: "risco tem premissas e aplicabilidade" |
| D5 | `escopo_proposto` (serviço) exige aplicabilidade `aplicavel` e razão | Plano: "serviço tem premissas e aplicabilidade" |
| D6 | `urgency` `alta` só em `risco` aplicável | Plano: "urgência tem premissas e aplicabilidade" |
| D7 | Ausência verificada exige consulta e resposta preservadas (já no schema) | DIAG-005 |

**[André]** Sem o texto de DIAG-002 a DIAG-009, a correspondência exata não é declarada: as regras
acima cobrem o resumo do Mergulho e os dois critérios com texto. Quando o segundo DOCX entrar no
repositório, cada DIAG ganha linha nesta tabela ou regra nova.

### 4. Skill 1.4.0

A seção "O que você produz — schema `DiagnosticoPreliminarContent`" sai e dá lugar a "Formato da
afirmação — ADR-079": a mesma taxonomia da Ísis (4 níveis de risco, 7 categorias, confiança)
mapeada para `impact`, `certainty` e `conclusion_class`. As 24 heurísticas ficam como estão.

### 5. O que não muda

Revisão humana por afirmação (ADR-069), gate de contexto, retomada, custo por job
(`AI_MAX_COST_PER_JOB_USD_DIAGNOSTICO`) e cadeia de modelos (Luna → Gemini 3.7 Flash → Sonnet 5).
O diagnóstico continua fora da cadeia comercial; em revisão, vira ressalva do orçamento (ADR-074).

## Alternativas descartadas

- **Reparo automático (segunda chamada com os erros).** Útil, mas muda o G7 do Incremento 1 e o
  custo; fica para decisão se a taxa de recusa medida justificar.
- **Aceitar as afirmações válidas e descartar as inválidas.** Diagnóstico parcial sem aviso é o
  defeito que a DIAG-001 descreve; a recusa inteira com motivo é auditável e barata de refazer.
- **Manter o prompt legado e reforçar a instrução do contrato.** Duas ordens de formato no mesmo
  pedido é a causa medida.

## Consequências

- O diagnóstico real entra em revisão pelo contrato, afirmação por afirmação, com premissa por ID.
- Afirmação sem suporte documental não vira risco nem fato — vira lacuna ou hipótese, ou é recusada.
- Testes com provedor controlado passam a declarar `certainty`.
- O legado `DiagnosticoAgent.execute` (fora do contrato) não é tocado.

## Validação

- `tests/services/test_diagnostico_contrato.py` — D1 a D7, resposta sem `objects`, prompt-base.
- Percurso em dev, #23 e #25, com o modelo real: [provas/inc5_285_diagnostico_dev_2026-09-24.json](../arquitetura/provas/inc5_285_diagnostico_dev_2026-09-24.json).
