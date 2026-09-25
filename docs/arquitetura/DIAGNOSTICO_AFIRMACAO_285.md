# Diagnóstico por afirmação — #285 (registro)

24/09/2026. Implementação do [ADR-080](../adr/080-diagnostico-por-afirmacao.md), empilhada sobre o
Incremento 5 ([ADR-074](../adr/074-metodos-e-fechamento-comercial.md), PR #211). **Só dev**;
produção intocada.

## 1. O que entrou

| Peça | Onde |
|---|---|
| Prompt-base do contrato | [diagnostico_contrato.py](../../app/services/diagnostico_contrato.py) `PROMPT_BASE` (080.3, hash `8f53a2ff…`), gravado no job com origem `contrato_080`; o `diagnostico_system` legado não vai mais no pedido |
| Schema da afirmação | `AfirmacaoDiagnostico`: texto, classe, premissas, `certainty`/`impact`/`urgency`, aplicabilidade, conhecimento, normas, regras, limites. Espécie, origem e identidade são do servidor; `kind` diferente de `conclusao` é erro nomeado |
| Regras de admissão | `recusas`: D1 premissa · D2 certeza (alta exige documento conferido) · D3 risco/fato/serviço exigem premissa documental · D4 impacto no risco · D5 aplicabilidade no serviço · D6 urgência alta só em risco aplicável. D7 (ausência verificada) é do schema |
| Execução | [connected_agents.py](../../app/services/connected_agents.py): teto por chamada do próprio agente; resposta sem JSON ganha **uma** nova chamada (as duas no job); custo e tokens pagos ficam no job mesmo se uma chamada seguinte falhar |
| Contrato | `EvidenceAttributes` ganha `impact` e `urgency` (opcionais) |
| Skill | `diagnostico/situacao_ambiental_imovel_rural` 1.4.0: "Formato da afirmação" no lugar do schema `DiagnosticoPreliminarContent`; versão exigida por agente |

Testes: `tests/services/test_diagnostico_contrato.py` (20). Fixtures de provedor controlado (G1 do
gate do Inc. 1, execução, cadeia) passam a declarar `certainty`.

## 2. Percurso em dev com o modelo real

API da worktree em `127.0.0.1:8040`, banco `127.0.0.1:15432/amigao_db`. Script versionado:
[scripts/provar_285_diagnostico.py](../../scripts/provar_285_diagnostico.py). Registro:
[provas/inc5_285_diagnostico_dev_2026-09-24.json](provas/inc5_285_diagnostico_dev_2026-09-24.json).
Nenhuma conclusão foi escrita no banco pelo agente: todas vieram do modelo pela API.

**Sem sintético:** a conclusão sintética 4092 da prova do Inc. 5 foi **rejeitada** pela API com
justificativa; nada foi apagado.

| Job | Caso | Prompt | Resultado |
|---|---|---|---|
| 201 | #25 | legado | schema `situacao_geral` — o defeito de partida |
| 208 | #23 | 080.1 | barrado no teto global por chamada (US$ 0,1192 > 0,10); custo pago não ficou no job (corrigido) |
| 209, 210 | #23, #25 | 080.1 | classe no campo `kind` a partir do 4º item |
| 211 | #23 | 080.2 | JSON inválido (faltou `]` em `limits`) — origem da nova chamada por sintaxe |
| 212 | #25 | 080.2 | **7 afirmações admitidas** (rejeitadas depois para refazer no código final) |
| 213 | #23 | 080.2 | classe em `kind` de novo — origem do schema estreito |
| **214** | **#23** | **080.3** | **9 afirmações admitidas**, 286.533 tokens de entrada, US$ 0,1187 |
| **215** | **#25** | **080.3** | **10 afirmações admitidas**, 61.023 tokens, US$ 0,0122 |

Os jobs gravaram o rótulo `079.x` (ver renumeração no ADR); texto e hash são os mesmos.

**Resultado final (código do PR):** 19 afirmações em revisão — #23: 2 fatos documentais, 2
divergências (área gráfica × comprobatória do CAR; Reserva Legal do CAR × matrículas 3.181 e 3.673),
1 risco (`atencao`, urgência média, aplicável), 2 lacunas, 2 orientações; #25: 3 fatos, 1
divergência (comprador na escritura × detentor no CCIR), 1 risco (`alto`, urgência alta, aplicável),
3 lacunas, 2 orientações. **57 premissas, 57 resolvidas** no banco pelo id e versão. 13 com certeza
alta, 6 média.

**Orçamento:** nos dois casos o orçamento aprovado ficou **desatualizado** ("o diagnóstico mudou"),
sem retroceder etapa nem Rota; escopo e orçamento regerados trazem a ressalva
`diagnostico_em_revisao` citando as 9 e as 10 conclusões por ID; o rascunho de proposta sai do
orçamento. Nova sessão lê o mesmo estado.

**Custo total em dev:** cerca de US$ 0,44 (0,32 nos jobs + 0,12 pagos no job 208, barrado).

## 3. Revisão independente (antes do CI)

Um achado importante e quatro menores, todos corrigidos com teste: custo pago que sumia do job
quando a chamada seguinte falhava; tokens de uma chamada só; `attributes` com referências não
conferidas (`coverage.material`); observação legada não revisada contando como documental; cerca
```` ```json ```` gerando duas chamadas pagas pelo mesmo erro.

## 4. O que fica em aberto

- **DIAG-002 a DIAG-009** não estão no repositório (segundo DOCX da Ísis); a correspondência com as
  regras D1–D7 é declarada só para DIAG-001 e DIAG-005. Dívida **#288**.
- Vocabulário de `urgency` provisório (PENDENTE-ISIS), dentro da #288.
- A tela não mostra as dimensões (certeza, impacto, urgência) na revisão da afirmação — mesma frente
  de tela das #278/#282.
