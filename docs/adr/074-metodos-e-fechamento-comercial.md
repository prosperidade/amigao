# ADR-074 — Métodos e fechamento comercial: a cadeia comercial nasce da Rota validada

- **Data:** 23/09/2026
- **Estado:** proposta (Incremento 5). Decisões marcadas **[André]** pedem aceite no PR.
- **Plano:** [Plano Diretor v1.1 — Incremento 5](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md),
  §4.1 (Redator e Orçamento), §5.2 (transições), §9.4 ("orçamento com tabela própria") e as
  decisões travadas **5** (o Redator não gera contrato) e **6** (o Orçamento não é segunda fonte de
  escopo; a Rota validada manda).
- **Consome:** [ADR-073](073-motor-juridico-deterministico.md) (passo do motor com avaliação e
  fundamento por ID), [ADR-061](061-remocao-de-passo-da-rota-e-lembrada.md) (remoção lembrada),
  [ADR-068](068-estado-unico-invalidacao-por-aviso.md) (invalidação por aviso),
  [ADR-069](069-contrato-contexto-revisao.md) (execução persistida e retomada).
- **Emenda:** [ADR-028](028-proposta-nasce-da-rota.md) — a proposta passa a nascer do **orçamento
  aprovado** quando ele existe; a distribuição da `PRICE_TABLE` fica só como caminho legado.

## Contexto (medido em 23/09, main `211798a`)

1. **Ruptura 4 continua aberta, com outra forma.** `CHAINS["gerar_proposta"]` é
   `["diagnostico", "redator", "orcamento"]` ([connected_agents.py:29](../../app/services/connected_agents.py)).
   O primeiro passo **roda o diagnóstico de novo**; toda conclusão nasce em revisão, e
   `DEPENDENCIES` faz `redator` e `orcamento` esperarem essa revisão. Aprovada a revisão, `redator`
   e `orcamento` caem em `capacidade_insuficiente`, porque não têm método-base
   ([agent_capabilities.py](../../app/services/agent_capabilities.py)). O orçamento nunca é
   alcançado — agora por dois motivos em vez de um.
2. **O diagnóstico não é premissa do orçamento.** O Plano (§4.1) põe na entrada do Orçamento "Rota
   e itens aprovados, especificação do Redator, tabela comercial versionada". Diagnóstico entra
   na Rota; a Rota validada é a autoridade comercial (decisão 6). Nos casos de dev do Incremento
   4b (#23 = processo 65, #25 = 66), a Rota foi validada **pelo motor, sem diagnóstico** (ADR-073
   §8) — pedir um diagnóstico aprovado para orçar seria exigir de novo o que o motor dispensou.
3. **O orçamento tem duas tabelas de preço e nenhuma é do tenant.** `OrcamentoAgent._estimate_by_rules`
   ([orcamento.py](../../app/agents/orcamento.py)) e `PRICE_TABLE` ([proposal_generator.py](../../app/services/proposal_generator.py))
   são constantes de código; a segunda distribui a faixa **igualmente** entre os itens
   (ADR-028, "default grosseiro"). Consultoria diferente, preço igual.
4. **O motivo da remoção de um passo só existe no texto da auditoria.** `remover_passo` exige
   motivo para passo do motor, mas grava-o apenas em `audit_logs.details`
   ([rotas.py:399–437](../../app/api/v1/rotas.py)). Nenhum consumidor consegue dizer "este item
   saiu do orçamento porque…".
5. **Não existe redação pré-contratação.** O Redator tem `_template` de 17 linhas e sete
   templates de peça ([redator.py:50](../../app/agents/redator.py)); nenhum relatório preliminar
   nem especificação de escopo, e nada que ligue afirmação a evidência por ID.

## Decisão

### 1. A cadeia comercial parte da Rota validada (ruptura 4)

`gerar_proposta = ["redator", "orcamento"]`. O diagnóstico **sai** da cadeia comercial: ele é
entrada da Rota, não do orçamento. Dependências:

| Passo | Depende de | Resolvido quando |
|---|---|---|
| `redator` | Rota validada do processo | gerou relatório preliminar + especificação de escopo |
| `orcamento` | `redator` | a especificação de escopo **vigente e atual** está **aprovada** pelo consultor |

- Sem Rota validada, o `redator` falha com motivo nomeado ("Rota validada ausente") e a
  **retomada** o reexecuta quando a Rota fechar. Não trava sem retomada.
- **Diagnóstico em revisão não impede o orçamento.** Vira **ressalva registrada** no artefato
  (quantas conclusões do diagnóstico estão em revisão, e a versão legada do diagnóstico e se está
  validada) — o consultor vê, o sistema não finge que não viu, e não bloqueia.
- Rodar a cadeia de novo **reaproveita** relatório, escopo e orçamento que continuam atuais — não
  cria versão nova nem supera uma aprovação à toa.
- Nenhum passo da cadeia comercial chama LLM nesta versão; os dois são serviços determinísticos
  executados pelo mesmo agendador persistido do ADR-069 (execução, snapshot, cursor, retomada).

### 2. Redator pré-contratação: relatório preliminar e especificação de escopo

Dois artefatos por geração, ambos **montados da Rota validada e da última execução do motor**.
**Sem contrato** (decisão 5): a peça comercial oficial continua nascendo de `proposal_generator` e
`mirante_documents` depois do preço e do aceite; a peça técnica definitiva e o checklist de TR são
pós-contratação (decisão 10) e ficam fora deste ADR.

**Afirmação** é a unidade: `{id, secao, texto, evidencias: [{tipo, id, rotulo}]}`.

- **Toda afirmação tem ao menos uma evidência por ID, resolvida no banco e no tenant.** Tipos:
  `dispositivo` e `fonte_versao` (catálogo global ou do tenant), `observacao`, `fonte_primaria` e
  `conclusao` (`evidence_versions` do caso), `documento`, `avaliacao_regra`, `execucao_motor`,
  `ciencia_alerta`, `rota` e `rota_passo` (lápide inclusive).
- **Fundamento é por ID, nunca por semelhança.** Passo validado com `fundamento_dispositivo_id`
  cita o dispositivo e a versão da fonte. Passo validado sem fundamento por ID (manual, ou da IA
  com `SourceRef` textual) **não vira afirmação de obrigação legal**: entra no escopo como decisão
  do consultor ("sem fundamento normativo por ID; passo validado pelo consultor", evidência = o
  passo) e aparece também em *Lacunas*.
- **Fato "não consta nos autos" é fato sobre os autos** (ADR-073 §3): a evidência é a avaliação
  que o leu, com o retrato de fatos da execução — nunca "não existe".
- **Indeterminado vira lacuna**, com a avaliação que o declarou e os fatos faltantes.
- Afirmação que não passa na verificação **não é emitida**; a geração falha com a lista dos IDs
  não resolvidos. O validador é o mesmo que a redação por LLM terá de satisfazer quando entrar
  (dívida #282): ela poderá reescrever `texto`, nunca `evidencias`.

**Qual execução do motor.** Situação, achados, alertas e lacunas vêm da **execução mais recente**
do caso — a mesma que o `fechar` da Rota exige com ciência. A execução que gerou os passos pode ser
anterior; cada passo continua citando a própria avaliação. (Medido no #25 de dev: passos da execução
4, ciência do alerta na 5. Lendo a 4, o relatório dizia "sem ciência" — falso.)

Seções do **relatório preliminar**: situação dos autos (fatos do motor com origem), achados
(regras disparadas com fundamento), alertas críticos e ciência, lacunas, caminho validado.
Seções da **especificação de escopo**: o que será feito (passos `item_proposta` validados),
orientações não cobradas (passos `direcao`), **fora do escopo** (passos removidos, com o motivo
registrado), premissas (Rota validada, execução do motor, conclusões do diagnóstico em revisão).
Os limites da peça (não é a peça técnica definitiva, não é contrato) vão em `limites`, texto fixo
que não se apresenta como afirmação sobre o caso.

### 3. Versão, revisão e atualidade (redação e orçamento)

- Cada geração é **versão nova**; a anterior do mesmo tipo fica `superada`, preservada.
- Revisão humana: `aprovar` ou `rejeitar`, com autor, data e justificativa. Só se aprova a versão
  vigente **e atual**.
- Cada artefato grava a **base** de que dependeu: Rota (id, validação, passos vivos com status,
  classificação e fundamento), diagnóstico (versão legada + conclusões do agente e suas
  revisões), e — no orçamento — a versão do escopo e as versões dos métodos usados.
- **Atualidade é leitura**, como no ADR-068: a base gravada é comparada à atual e o artefato sai
  `vigente` ou `desatualizado`, com os motivos ("passo 6 removido: <motivo>", "diagnóstico
  mudou", "preço do método X mudou"). **Não retrocede etapa, não regenera sozinho, não apaga a
  aprovação** — revisão e atualidade são eixos separados (Plano §5.1).
- Proposta a partir de orçamento desatualizado → **422**. Aceitar proposta cujo orçamento ficou
  desatualizado → bloqueado pela mesma porta de `desatualizacao_proposta` (Plano §5.2).

### 4. Orçamento derivado da Rota

- **Um item por passo vivo, validado e `item_proposta`** da Rota validada. O item aponta o passo
  (`rota_passo_id`, FK) e carrega, como foto, o título e o fundamento do passo.
- **Passo removido some do orçamento** e aparece em *fora do orçamento* com o motivo; passo
  `direcao` não é cobrado. Nada entra no orçamento sem passo de origem.
- **Método do item, em ordem:** escolha do consultor para aquele passo (preservada na próxima
  versão) → método do tenant mapeado à regra que originou o passo (`rule_id`) → método padrão do
  tenant. Sem método padrão, a geração recusa com mensagem honesta (422); nunca usa preço de
  código.
- **Cálculo determinístico** em `Decimal`: `quantidade × valor_unitario`, arredondado a centavos;
  total = soma dos itens. O texto do cálculo acompanha cada item ("8 h × R$ 250,00"). O consultor
  muda método e quantidade; **nunca digita total**.
- **[André]** Unidades nesta versão: `hora`, `fixo`, `unidade`. **Hectare fica fora** até a medição canônica
  do Incremento 3 escolher a área por finalidade (Plano §6.1) — preço por área sobre número
  cadastral seria preço sobre fato não decidido.

### 5. Métodos e preços por tenant

Tabela `orcamento_metodo`, versionada por `(tenant, codigo, versao)`: nome, unidade, valor
unitário, quantidade padrão, `rule_ids` a que se aplica, `padrao`. **Mudar preço cria versão**; a
anterior fica e o item guarda a foto do valor usado — orçamento antigo não muda de preço por baixo.
Permissão: usuário interno do tenant. Sem semente automática: o tenant cadastra os seus.

### 6. A remoção lembrada guarda o motivo

`rota_passos.remocao_motivo` recebe o motivo informado em `DELETE /rotas/{id}/passos/{id}`; a
restauração o limpa. Lápides antigas sem a coluna leem o motivo da trilha de auditoria (fonte
registrada, não inferência); sem registro, o texto é "motivo não registrado".

### 7. Proposta nasce do orçamento aprovado (emenda ao ADR-028)

**[André]** `generate_proposal_from_rota` e `POST /proposals`: se o processo tem orçamento, a
proposta **só** nasce do orçamento
vigente, aprovado e atual — itens, preços e total dele, com `orcamento_id` na proposta e
`orcamento_item_id` + `rota_passo_id` em cada item; itens e total vindos no corpo são ignorados e
editar itens ou total dessa proposta é 422 (muda-se o orçamento). Orçamento existente mas não
aprovado ou desatualizado → 422 com o motivo. Sem orçamento, o caminho do ADR-028 (faixa da `PRICE_TABLE`)
permanece **como legado declarado**, até a tela do orçamento existir (dívida #281).

## Alternativas descartadas

- **Manter o diagnóstico na cadeia e só tirar o `stop_on_review`.** O ADR-069 já tornou o gate
  inviolável por flag (o teste `test_review_gate_cannot_be_bypassed…` prova isso); e rodar o
  diagnóstico de novo para orçar gera conclusões novas a cada clique.
- **Redator por LLM já neste incremento.** A exigência é evidência por ID em cada afirmação; a
  estrutura e os IDs são determinísticos de qualquer forma. LLM entra só para a prosa, sobre
  afirmações fixas (dívida #282), depois de o validador existir — que é o que este ADR entrega.
- **Congelar o orçamento na etapa (retroceder a E5 quando a Rota muda).** Destrói trabalho humano
  por evento que o consultor talvez nem tenha visto (ADR-039, ADR-068, decisão 7).
- **Preço por hectare com a área do cadastro.** Ver §4.

## Consequências

**Positivas.** O orçamento é alcançável; cada real do total aponta um passo validado e o fundamento
dele; tirar um passo muda o orçamento de forma visível e explicada; preço é do tenant e
versionado; a proposta deixa de dividir faixa por igual quando há orçamento.

**Custos e riscos.**
- A tela não conhece relatório, escopo nem orçamento; o percurso é por API (dívida **#281**,
  irmã da #278).
- A redação é esquemática, não prosa de consultor (dívida **#282**, com o checklist de TR da
  peça definitiva).
- O legado `OrcamentoAgent._estimate_by_rules` e a `PRICE_TABLE` continuam no código para o
  caminho sem orçamento; saem quando a #281 fechar (dívida **#283**).
- Afirmações do relatório cobrem o que o motor e a Rota sabem; o que não está no retrato de fatos
  (ADR-073 §3) não aparece — é limite declarado na própria peça, não omissão.

## Validação

- `tests/comercial/test_comercial_contrato.py` — cadeia sem diagnóstico, diagnóstico em revisão
  como ressalva, afirmação sem evidência recusada, orçamento por passo, remoção com motivo,
  preço por tenant e versão, atualidade sem retrocesso, proposta do orçamento, isolamento.
- `test_alerta_com_ciencia_na_execucao_mais_recente_aparece_como_ciente` — regressão do achado
  do percurso em dev.
- `tests/agents/test_orchestrator_chain.py` — reescrito para a cadeia nova; o gate de revisão
  continua provado na `diagnostico_completo`.
- Percurso autenticado em dev com #23 e #25:
  [provas/inc5_percurso_dev_2026-09-23.json](../arquitetura/provas/inc5_percurso_dev_2026-09-23.json).
