# Orçamento só do tenant — #284 (registro)

26/09/2026. Implementação do [ADR-081](../adr/081-proposta-so-nasce-do-orcamento-do-tenant.md) (aceito pelo André em 26/09).
Condição de entrada do Incremento 7 (André, 24/09). **Só dev**; produção intocada.

## 1. O que entrou

| Peça | Onde |
|---|---|
| Porta única da proposta de caso | `exigir_orcamento` em [proposal_generator.py](../../app/services/proposal_generator.py): rascunho, criação e renegociação. Sem Rota assinada → pede a assinatura; com ela, sem orçamento aprovado e atual → pede o orçamento |
| Saem | `PRICE_TABLE`, `DEFAULT_PRICE`, a distribuição da faixa, `_build_notes`; `OrcamentoAgent._estimate_by_rules` e o enriquecimento por LLM ([orcamento.py](../../app/agents/orcamento.py) fica só com o registro do passo) |
| Mirante | nome da demanda por rótulo próprio (`DEMANDA_ROTULO`), sem a tabela de preço |
| Propostas antigas | rascunho de caso sem orçamento não é enviado (422); enviada e aceita seguem; renegociar exige o orçamento |
| Tela | editor de proposta: sem orçamento, a recusa da API, criar bloqueado, itens e total travados, atalho para o Comercial do caso; com orçamento, itens travados ("do orçamento #N") e `orcamento_id` no corpo |

Testes: `tests/comercial/apoio.py` monta o orçamento aprovado pelos serviços reais; proposta
(s5a), caracterização, Mirante e smoke de tenant adaptados; novos: rota assinada sem orçamento
pede o orçamento, escopo nasce do orçamento, renegociação recusada sobre orçamento desatualizado e
aceita depois de regerar, proposta antiga sem orçamento só renegocia com Rota e orçamento, rascunho
antigo não é enviado, caso sem orçamento recusado no `POST /proposals`. Frontend:
`ProposalEditor.test.tsx` (2). Recorte `tests/api`, `tests/comercial`, `tests/motor_juridico`,
`tests/agents`: **789 verdes**; a única falha local (`test_download_artefato`) era o `.env` local com
`MINIO_SERVER` vazio — com o valor preenchido os 9 da suíte passam. Frontend: 34 arquivos, 202
testes. Suíte e lint completos no CI.

## 2. Percurso em dev, no navegador (#22, #23, #25)

API da worktree em `:8040`, Vite em `:5182`, banco `127.0.0.1:15432/amigao_db`, Chromium headless.
Roteiro: [scripts/provar_284.mjs](../../scripts/provar_284.mjs). Transcrição:
[provas/proposta_so_do_orcamento_284_dev_2026-09-26.json](provas/proposta_so_do_orcamento_284_dev_2026-09-26.json).
Rodada final no commit **46142bc** (rodapé "Painel 46142bc · API 46142bc · desenvolvimento").

| Caso | Resultado pela tela |
|---|---|
| **#22** (processo 69) — Rota assinada, nenhum passo cobrável, sem orçamento | "Gerar relatório e escopo" → 422 "não há escopo a especificar"; proposta nova → 422 "A proposta nasce do orçamento…", mensagem na tela, **Criar bloqueado**, itens travados; o atalho leva ao Comercial do caso |
| **#23** (65) | rascunho nasce do orçamento 22 (R$ 950), itens travados; **proposta 22** criada com `orcamento_id` 22 |
| **#25** (66) | rascunho do orçamento 23 (R$ 1.900); **proposta 23** criada; enviar → recusar → **nova versão 24** (v2), nascida do orçamento 23 |

Rodadas anteriores do mesmo roteiro (commits 64e9c73 e o ajuste do seletor) criaram as propostas
17–21 no dev; ficaram como estão.

## 3. Gate da Frente J reescrito para o caminho real

`tests/e2e/frente_j/gate_api.py` criava a proposta com itens no corpo. Agora, pela API:
diagnóstico → rascunho **recusado sem orçamento** → Rota gerada pelo **motor** (sem LLM) e assinada
— ciência dos alertas críticos, passo do motor sem norma no catálogo sai com motivo, um passo
cobrado declarado — → método padrão do tenant → relatório e escopo, escopo aprovado → orçamento
aprovado → rascunho lido do orçamento → proposta **sem itens no corpo** (itens e total conferidos
contra o orçamento) → enviada. A invalidação por documento novo passa a exigir também o orçamento
desatualizado. `setup_db.py` semeia o conjunto de regras do gate 4b (homologado e ativo pelo
superusuário do seed, só no banco descartável).

**Validado em 26/09** com o próprio `setup_db.py` num banco descartável (`amigao_e2e_284`, removido
depois) e a API da worktree apontada para ele: recusa sem Rota → Rota 1 assinada (5 passos: 4 sem
norma saíram com motivo, 1 cobrado) → orçamento 1 aprovado, R$ 1.000 → proposta 1 enviada → documento
novo (PDF sintético) → diagnóstico, Rota, orçamento e proposta desatualizados → aceite **422**. O
trecho de 6 documentos com extração real não foi refeito: exige os PDFs de texto de produção, que não
são versionados. A tentativa anterior, com a Rota pela IA, falhou em `capacidade_insuficiente`
(Legislação) — daí o motor; ela deixou no dev o cliente 65 e o processo 74 ("Gate 284 — caminho
real", tenant 33), sintéticos.

## 4. Propostas sem orçamento em produção

Lido em 26/09 pelo canal somente-leitura (`read_only=true`, ADR-076), só `SELECT`. Produção em
`076mc001` (tabela `orcamento` e coluna `proposals.orcamento_id` existem) e com **uma proposta** ao
todo:

| Proposta | Processo | Tenant | Estado | Valor | `orcamento_id` | Rota | Contratos | Orçamento aprovado no caso | Métodos do tenant |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 16 | 1 | **rascunho** (criada 05/08, nunca enviada; validade gravada até 04/09) | R$ 1.400 | nenhum | Rota 2, assinada | 0 | não | **0** |

**O que acontece com ela depois do merge:** fica como está (nada é apagado nem reprecificado), mas
**não pode ser enviada** — o envio devolve 422 pedindo a proposta a partir do orçamento. Para o caso
16 ter proposta: cadastrar métodos e preços do tenant (Configurações › Métodos e preços; hoje são
zero), gerar e aprovar relatório, escopo e orçamento da Rota 2 e criar a proposta nova, que nasce do
orçamento.

**Achado:** o tenant 1 de produção não tem nenhum método. Sem método padrão, o orçamento é recusado
("sem método padrão") — nenhum caso de produção gera proposta até a consultoria cadastrar os seus
preços. É a consequência esperada do ADR-081 (preço é do escritório), e precisa estar no roteiro de
implantação.

Consulta usada:

```sql
select p.id as proposta, p.process_id as processo, p.tenant_id, p.status, p.total_value, p.orcamento_id,
       p.rota_id, p.version_number, p.created_at::date as criada, p.sent_at::date as enviada,
       p.accepted_at::date as aceita, p.expires_at::date as expira,
       (select count(*) from contracts c where c.proposal_id = p.id) as contratos,
       exists (select 1 from rotas r where r.process_id = p.process_id and r.status = 'validada') as rota_assinada,
       exists (select 1 from orcamento o where o.process_id = p.process_id and o.estado_revisao = 'aprovada') as tem_orcamento_aprovado,
       (select count(*) from orcamento_metodo m where m.tenant_id = p.tenant_id) as metodos_do_tenant
from proposals p order by p.id;
```

**Canal:** o OAuth do `supabase-prod-ro` passou a ser recusado pelo servidor de autorização do
Supabase ("Resource must be a valid MCP endpoint": o recurso anunciado leva os parâmetros da URL, o
servidor de login só aceita a URL sem eles). O André configurou na máquina dele o servidor
`supabase-prod-ro-pat` — **mesma URL, com `read_only=true`**, autenticado por token pessoal no
cabeçalho, em escopo de usuário (o `.mcp.json` versionado ficou intacto). Como a sessão já estava
aberta, a leitura foi por uma chamada `claude -p` restrita a `mcp__supabase-prod-ro-pat__execute_sql`
(o contorno de 21/09), lendo o `tool_result` literal. Registrado no ADR-076.

**No dev** (análogo): 5 propostas, todas **aceitas e com contrato**, sem Rota assinada nem
orçamento (ids 1, 2, 3, 5 e 6, tenant 2, abril e maio). Pela regra do ADR-081 §4 elas **não mudam**:
seguem aceitas e o contrato continua saindo delas; só uma renegociação (nova versão) exigiria Rota
assinada e orçamento.

**O que acontece com cada estado em produção**, quando a lista vier:

| Estado da proposta sem orçamento | Depois do merge |
|---|---|
| rascunho (`draft`) | não é enviada; o consultor gera a proposta nova a partir do orçamento aprovado |
| enviada (`sent`) | segue: pode ser aceita ou recusada; recusada ou expirada, a nova versão exige o orçamento |
| aceita (`accepted`) | segue como está; contrato normal |
| recusada / expirada | fica no histórico; a nova versão exige Rota assinada e orçamento |

## 5. Em aberto

- **#292** — proposta avulsa (decisão do André, 26/09): permanece, rotulada e sem vínculo a caso;
  itens a partir do catálogo de métodos do tenant, valor editável. Frente pequena, depois do merge.
- Merge só com a autorização do André.
