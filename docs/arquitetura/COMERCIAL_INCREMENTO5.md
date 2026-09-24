# Fechamento comercial — Incremento 5 (registro)

23/09/2026. Implementação do [ADR-074](../adr/074-metodos-e-fechamento-comercial.md). **Só dev**;
produção intocada (nenhuma leitura nem escrita nesta frente).

## 1. O que entrou

| Peça | Onde |
|---|---|
| Migration `076mc001` | `orcamento_metodo` (versionada por tenant e código), `redacao_comercial` (relatório preliminar e especificação de escopo, versionados), `orcamento` + `orcamento_item`, `orcamento_escolha` (escolha do consultor por passo), `rota_passos.remocao_motivo`, `proposals.orcamento_id`. FK com índice em todas |
| Cadeia | `gerar_proposta = [redator, orcamento]`; `orcamento` depende do `redator`, resolvido quando o escopo mais novo está aprovado e atual. Passos determinísticos no agendador do ADR-069 ([cadeia.py](../../app/services/comercial/cadeia.py)); rodar de novo reaproveita o que continua atual |
| Evidência por ID | [evidencia.py](../../app/services/comercial/evidencia.py) — onze tipos, cada ID conferido no banco, no tenant e no caso; afirmação sem evidência resolvida recusa a geração |
| Redator | [redator.py](../../app/services/comercial/redator.py) — relatório (situação, achados, alertas, lacunas, caminho) e escopo (incluído, orientações, fora, premissas) |
| Orçamento | [orcamento.py](../../app/services/comercial/orcamento.py) — um item por passo validado `item_proposta`; método: consultor → regra → padrão; `Decimal`; revisão |
| Atualidade | [base.py](../../app/services/comercial/base.py) — base gravada × base atual ⇒ `vigente`/`desatualizado`/`superada` com motivos; soma o aviso de documento novo do ADR-068 |
| Skills | `redator/relatorio_preliminar_escopo` e `orcamento/orcamento_da_rota` (1.0.0), no manifesto como `deterministic_contract`; fora da cadeia comercial o Redator segue `capacidade_insuficiente` (peça definitiva sem método) |
| API | `POST/GET /processes/{id}/comercial/redacao`, `POST .../redacao/{id}/revisar`, `POST/GET .../comercial/orcamento`, `PATCH .../orcamento/passos/{passo}` (gera versão), `POST .../orcamento/{id}/revisar`; `GET/POST /comercial/metodos` |
| Proposta | `generate-draft` e `POST /proposals` nascem do orçamento aprovado e atual quando ele existe; itens/total do corpo ignorados; editar itens/total → 422; aceite bloqueado se o orçamento de origem ficar desatualizado ou superado |

Testes: `tests/comercial/` (17). Recortes de regressão: cadeia, motor, skills, Rota, proposta,
contrato, staleness, tenant_guard, agentes (309). Suíte e lint completos no CI.

## 2. Percurso autenticado em dev

API da worktree em `127.0.0.1:8040`, banco `127.0.0.1:15432/amigao_db` em `076mc001`. Script
versionado: [scripts/provar_incremento5_comercial.py](../../scripts/provar_incremento5_comercial.py).
Transcrição: [provas/inc5_percurso_dev_2026-09-23.json](provas/inc5_percurso_dev_2026-09-23.json).

**Escritas diretas no banco de dev (declaradas):** senha aleatória nos usuários 38 (consultor de
gate, tenant 33) e 37 (tenant 34, isolamento); e a conclusão **sintética** 4092 do diagnóstico no
#25, gravada por `persist_object` com texto "PROVA INC5" — mede roteamento, não semântica (ver
achado 1). Preços são de prova (hora técnica R$ 250 × 8 h padrão; CCIR R$ 900 fixo para
REG-FUN-002; inscrição no CAR R$ 1.800 fixo para REG-BR-CAR-001).

| Etapa | Resultado |
|---|---|
| **#25** (66) pela cadeia | `gerar_proposta`: redator `completed`, orçamento `awaiting_review` (espera o escopo). Escopo aprovado → retomada → orçamento v1 **R$ 2.700** (CAR 1.800 + CCIR 900, os dois por regra) → aprovado → retomada → cadeia **`completed`** |
| **#23** (65) pela API | Relatório (12 afirmações) e escopo (6), **zero sem evidência**; 17 referências a documento e 34 a fonte primária das quatro matrículas e do CAR. Orçamento **R$ 900** (CCIR); "Mapear os componentes" fora como orientação (direção); dois passos removidos na 4b fora com o motivo. Rascunho de proposta do orçamento: 1 item, R$ 900, com `orcamento_item_id` e `rota_passo_id` |
| Recarga e nova sessão | mesmos IDs, estados e totais nos dois casos |
| **Remoção com motivo** (#25) | `DELETE` do passo 6 (CCIR) com motivo. O orçamento v1 **continua aprovado** e sai **desatualizado**, com o motivo do passo; Rota segue `validada`; macroetapa intacta (`entrada_demanda`). Orçar sobre o escopo antigo → **422** nomeando o motivo. Escopo v2 → orçamento v2 **R$ 1.800**, CCIR em "fora" com o motivo |
| Diagnóstico em revisão | Conclusão 4092 em revisão: o orçamento aprovado ficou desatualizado ("o diagnóstico mudou") **sem retroceder nada**; o novo saiu com a ressalva `diagnostico_em_revisao` citando a 4092 e não foi bloqueado |
| Correção e v3 (#25) | Achado 2 corrigido; relatório e escopo v3; orçamento v2 marcou "escopo mudou (v2 → v3)"; orçamento v3 **R$ 1.800** aprovado; proposta do orçamento v3 |
| Isolamento | usuário do tenant 34: **404** em orçamento e redação; lista de métodos vazia |
| Estado final | 8 redações (4 superadas, preservadas), 4 orçamentos (2 superados), 4 aprovações de orçamento e 4 de escopo na trilha de auditoria com hash |

## 3. Achados

1. **O diagnóstico real não produz conclusão pelo contrato 069.** Rodado pelo gateway no #25
   (`gpt-5.6-luna`, 61.222 tokens de entrada, 2.279 de saída, US$ 0,015, job 201), devolveu o
   schema **legado** do diagnóstico (`situacao_geral`, …) em vez de `{"objects": [...]}`, e o passo
   falhou com o erro cru `'objects'`. O prompt-base legado vence a instrução do contrato. É a
   "reconciliação semântica" do diagnóstico que o Plano põe no Incremento 5 e que esta frente não
   fez. Dívida **#284**.
2. **Qual execução do motor o relatório lê.** A primeira versão lia a execução que gerou os passos
   (#4 no #25) e escreveu "alerta crítico **sem ciência**" — falso: a ciência está na execução #5,
   a que o `fechar` exige. Corrigido (ADR-074 §2), com teste de regressão. O relatório v2 errado
   (id 5) ficou superado e preservado.
3. **O script da prova caiu depois de um `DELETE` 204** (erro próprio de argumento). A retomada
   declarou o passo já removido em vez de repetir o gesto; o JSON registra as três execuções.
4. **Relatório esquemático.** Frases de modelo ("Não consta CCIR nos autos."), não prosa de
   consultor. É o esperado de um Redator determinístico; a prosa por LLM sobre afirmações fixas é
   a dívida **#282**.

## 4. O que esta frente não fez (do Incremento 5 do Plano)

- Diagnóstico por afirmação com premissas e a reconciliação da skill do diagnóstico (DIAG-001 a
  009) — ver achado 1.
- Redator com checklist de TR e peça técnica definitiva (pós-contratação).
- Relatório da Fazenda Paraíso (INS-008) como referência de qualidade.
- Tela: relatório, escopo, orçamento e métodos só por API (**#281**).
- Validação da Ísis do método de orçamento e do texto das afirmações.
