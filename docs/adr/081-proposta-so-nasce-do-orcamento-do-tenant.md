# ADR-081 — A proposta de um caso só nasce do orçamento do tenant

- **Data:** 26/09/2026
- **Estado:** aceito (André, 26/09/2026, PR #220).
- **Emenda:** [ADR-074](074-metodos-e-fechamento-comercial.md) §7 e o caminho legado do
  [ADR-028](028-proposta-nasce-da-rota.md) (faixa da `PRICE_TABLE`).
- **Plano:** [Plano Diretor v1.1](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md), condição de entrada
  do Incremento 7 (André, 24/09): "orçamento só do tenant (dívida #284)"; decisão travada **6** (o
  Orçamento não é segunda fonte de escopo; a Rota validada manda).

## Contexto

O ADR-074 fez a proposta nascer do orçamento aprovado **quando ele existe** e deixou dois
orçamentos de código para o caso sem orçamento, como legado declarado até a tela do orçamento
existir (#282):

1. `PRICE_TABLE` em `proposal_generator` — faixa por demanda × complexidade, distribuída igualmente
   entre os itens da Rota ("default grosseiro", ADR-028);
2. `OrcamentoAgent._estimate_by_rules` — faixas fixas por demanda, enriquecidas por LLM. Desde o
   ADR-074 o passo `orcamento` da cadeia já era desviado para o cálculo determinístico
   (`comercial/cadeia.py`); a estimativa por regras não era mais chamada por nenhum caminho.

Com as telas de orçamento e de métodos e preços na `main` (#218, #219), os dois saem.

## Decisão

1. **Porta única.** `exigir_orcamento` (em `proposal_generator`) é a única entrada da proposta de um
   caso — rascunho (`GET /proposals/generate-draft`), criação (`POST /proposals`) e renegociação
   (`POST /proposals/{id}/nova-versao`). Devolve o orçamento mais novo, aprovado e atual, ou recusa
   (422) com o próximo passo:
   - sem Rota assinada: "feche (assine) a Rota Regulatória" (decisão 6 — a Rota manda, antes de
     qualquer conversa sobre preço);
   - com Rota assinada e sem orçamento aprovado e atual: "gere e aprove o relatório, o escopo e o
     orçamento" (ou o motivo exato: não aprovado, desatualizado com os motivos, versão errada).
2. **Itens e total vêm do orçamento**, nunca do corpo da requisição (já valia desde o ADR-074 §7
   para o caso com orçamento; passa a valer para todo caso).
3. **Saem** a `PRICE_TABLE`, o `DEFAULT_PRICE`, a distribuição da faixa e o
   `OrcamentoAgent._estimate_by_rules` com os prompts `orcamento_system`/`orcamento_user`. A classe
   `OrcamentoAgent` fica só para o registro do passo e o tipo do job; `execute` recusa. O documento
   Mirante, que lia a `PRICE_TABLE` só para o nome da demanda, ganha o rótulo próprio.
4. **Propostas que já existem não mudam.** Não se recalcula, não se apaga, não se reprecifica:
   - **rascunho** de caso sem orçamento (precificado pela tabela antiga) **não é enviado** — 422
     pedindo a proposta nova a partir do orçamento;
   - **enviada** segue o ciclo (aceitar, recusar): já está com o cliente;
   - **aceita** segue como está, e o contrato continua saindo dela;
   - **renegociar** qualquer uma delas (nova versão de recusada ou expirada) exige o orçamento
     aprovado e atual — a versão nova nunca copia os itens da tabela antiga.
5. **Proposta avulsa** (sem processo) fica fora desta decisão: segue com os itens do corpo. Se ela
   deve existir é pergunta de produto (dívida #292).

## Consequências

- O caso da Rota de coleta (#22 de dev: Rota assinada sem passo cobrável) não tem proposta: o
  Redator recusa o escopo ("não há escopo a especificar") e a proposta recusa por falta de
  orçamento — é o comportamento certo, e a tela diz os dois motivos.
- Testes que criavam proposta de caso com itens no corpo passam a montar o orçamento pelo caminho
  real (`tests/comercial/apoio.py`).
- O gate da Frente J (`tests/e2e/frente_j/gate_api.py`, manual) criava proposta com itens no
  corpo; foi reescrito para o caminho real (Rota do motor assinada → orçamento aprovado → proposta),
  e o `setup_db.py` semeia o conjunto de regras no banco descartável.
- Em produção, as propostas sem `orcamento_id` ficam como estão (item 4). A lista é levantada pelo
  canal somente-leitura antes do merge (registro da frente).
