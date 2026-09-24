# Gate do Incremento 1 — nove provas no mesmo percurso autenticado

Referência: [Plano Diretor v1.1, §8](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md).
Este relatório responde aos **nove itens** enumerados na revisão pré-merge.
**Execução local: G1–G9 aprovados no mesmo teste, em 17/09/2026 às 20:13:40 UTC.**
A validação remota do SHA publicado deve ser conferida no #172; a execução
anterior de 2.046 testes não atesta este cenário novo.

## Separação dos PRs e correção da alegação anterior

O #172 originalmente reunia documentos e implementação. Nenhum deles havia sido
mergeado. A separação preserva o histórico, sem force-push:

- [#173 — somente documentos](https://github.com/prosperidade/amigao/pull/173),
  base `main`, branch `docs/plano-diretor-v1-1`, contém `9e02b98`, `a4a2633` e
  `a42a1cd`: mergulho, plano, triagem e índices. Pode entrar independentemente do código.
- [#172 — Incremento 1](https://github.com/prosperidade/amigao/pull/172), base
  temporária `docs/plano-diretor-v1-1`, contém apenas o diff de implementação e
  sua documentação. Depois da integração do #173, sua base deve voltar à `main`;
  em caso de squash do documental, ajustar a ancestralidade antes de integrar código.
- Nenhum merge foi executado nesta separação. O #171 continua fechado sem merge.

Os 2.046 testes verdes em `4cdb76b` **não eram prova do gate conjunto**:
os itens estavam distribuídos entre testes de API/serviço e navegador. Essa
alegação foi corrigida, e o #172 voltou a rascunho durante a revisão.

O cenário unificado encontrou **defeito real em G1**: a recomendação rejeitada
continuava no prompt do diagnóstico dentro de `derivacao.attributes.normalized.acao_recomendada`.
A asserção de exclusão do texto foi mantida. A correção em
`app/services/connected_agents.py`, método de projeção `069.2`, deixa dados do
confronto na derivação e move recomendação/classificação/destino para a conclusão
revisável. O gate exige a ausência do texto no envelope inteiro recebido pelo
gateway, não apenas sua retirada da lista `conclusions`.

## Unidade de prova

Há um único item pytest:
[`test_incremento1_gate_nove_provas_no_mesmo_percurso`](../../tests/e2e/test_evidence_browser.py#L34).
Ele cria um caso em PostgreSQL real, inicia a aplicação HTTP e executa
[`increment1-unified-gate.mjs`](../../frontend/scripts/increment1-unified-gate.mjs)
uma vez. As nove fases usam **o mesmo caso**, sem reiniciar o fixture entre elas.
O novo contexto de navegador faz novo login; não recebe token injetado.

Ao terminar todas as asserções de navegador, entrada efetiva do diagnóstico e
persistência, o teste grava `artifacts/gate-incremento1.json`. A CI o publica como
artefato `gate-incremento1`, com SHA do head, recibo das operações, identificadores,
versões, manifesto e limites. A ausência desse artefato reprova sua etapa de publicação.

## As nove provas

### G1 — rejeição impede consumo pelo diagnóstico

O auditor determinístico real produz avaliações. Uma conclusão de denominação é
rejeitada **pela UI**; outra é aprovada pelo endpoint autenticado como controle
positivo. A cadeia `gerar_proposta` chama o diagnóstico real até a fronteira do LLM.
No **prompt efetivamente entregue ao gateway**, o teste verifica que o texto
rejeitado não aparece, que seu ID não está nas conclusões autorizadas nem nas
premissas destas, e que as conclusões aprovadas do auditor estão presentes.
Não é uma prova vacuosa de contexto vazio, nem só inspeção do estado da revisão.

Evidência: [gestos G1](../../frontend/scripts/increment1-unified-gate.mjs#L89) e
[entrada efetiva](../../tests/e2e/test_evidence_browser.py#L123).

### G2 — correção versiona e conserva a anterior

A UI corrige a conclusão proposta pelo diagnóstico. A resposta exige versão 2,
pendente. A rota autenticada de versões recupera a versão 1, e o objeto completo
é comparado ao original. A consulta PostgreSQL confirma exatamente as versões
1 e 2, com o conteúdo original íntegro.

Evidência: [G2](../../frontend/scripts/increment1-unified-gate.mjs#L104).

### G3 — recarga e nova sessão mantêm decisões

O teste faz `page.reload()`, encerra o primeiro contexto do navegador, abre outro
e faz login pela UI novamente. Confere visualmente a rejeição anterior, a correção
pendente e a versão antiga ao abrir o histórico; a consulta autenticada confirma
os estados `rejeitar`, `corrigir` e a versão 2 ainda sem aprovação. Só então o
consultor aprova a versão 2 pela UI.

Evidência: [G3](../../frontend/scripts/increment1-unified-gate.mjs#L113).

### G4 — retomar não duplica efeito nem recomeça a cadeia

É a cadeia de produção `gerar_proposta`, não uma cadeia inventada pelo teste.
Antes da revisão: diagnóstico concluído, cursor 1, redator aguardando revisão,
sem job. Duas retomadas autenticadas conservam o mesmo primeiro passo, job,
outputs e cursor. O redator passa a ser tentado: isso prova que a retomada saiu
da dependência revisada sem reiniciar o diagnóstico. PostgreSQL confirma **um só
job do diagnóstico nessa cadeia e somente suas duas versões**, sem nova chamada
ao provider por retomada.

**Limite explícito:** o redator não tem método-base disponível. Cada tentativa
manual registra um job de capacidade insuficiente, sem objeto de evidência.
A cadeia permanece incompleta; o teste não declara proposta concluída, broker
remoto ou garantia de custo externo exactly-once.

Evidência: [G4](../../frontend/scripts/increment1-unified-gate.mjs#L131) e
[efeitos persistidos](../../tests/e2e/test_evidence_browser.py#L140).

**Reescrita do G4 (24/09/2026, PR #211, ADR-074).** A cadeia `gerar_proposta` deixou de rodar
o diagnóstico (ruptura 4) e passou a ser `[redator, orcamento]`, a partir da Rota validada. O G4
continua provando a retomada de uma cadeia de produção **real e parcial**, agora a nova:

- o diagnóstico roda como execução própria (`chain_name: diagnostico`), fonte do G1/G2;
- `gerar_proposta` sem Rota validada: redator `failed` com "Rota validada ausente", orçamento
  `awaiting_review` sem job, cursor 0;
- duas retomadas autenticadas: cada uma registra **nova tentativa** do redator (3 jobs, todos com
  o motivo, zero objetos de evidência); o orçamento nunca roda; cursor inalterado;
- a execução do diagnóstico, retomada depois da aprovação da versão 2, fica `completed` com o
  mesmo passo e o mesmo job — **um só job do diagnóstico**, nenhuma chamada nova ao provider (4
  no total, como antes).

Mudou a contagem de jobs do percurso (9 → 10) e o limite explícito: o redator agora tem método
(pré-contratação), e a tentativa falha pela Rota ausente, não por capacidade insuficiente. As nove
provas continuam verdes no CI (run 35948833019) e localmente com navegador.

### G5 — portas síncrona e assíncrona recebem o mesmo contexto e skill

No mesmo caso revisado, chama `/agents/run` e `/agents/run-async` com diagnóstico.
Ambos percorrem aplicação, autorização e worker reais; `task.delay` não é substituído.
As duas respostas controladas são vazias para não alterar as premissas entre portas.
O teste compara **envelopes completos e system prompts compostos** recebidos pelo
gateway, depois compara os `AIJob.input_payload` persistidos. Exige uma skill
real `diagnostico/situacao_ambiental_imovel_rural`, versão `1.3.0`, conteúdo no
system prompt e hash correspondente no manifesto. O artefato registra os dois
jobs, nome/versão/hash da skill, hash do contexto e do system prompt.

Evidência: [G5 HTTP](../../frontend/scripts/increment1-unified-gate.mjs#L148) e
[comparação efetiva e persistida](../../tests/e2e/test_evidence_browser.py#L133).

### G6 — skill obrigatória ausente gera capacidade insuficiente visível

Uma injeção de falha remove **somente a skill obrigatória do diagnóstico**, por
uma execução. O consultor clica Executar na UI; a tela deve mostrar
`diagnostico: CAPACIDADE INSUFICIENTE`. O manifesto persistido precisa identificar
a skill faltante e `ausente_ou_invalida`, sem skill aplicada, sem resposta bruta
e sem chamada adicional ao provider. Não é apenas o caso do extrator sem método.

Evidência: [G6](../../frontend/scripts/increment1-unified-gate.mjs#L153) e
[manifesto de falha](../../tests/e2e/test_evidence_browser.py#L160).

### G7 — ausência sem registro de verificação é recusada

Com a skill real novamente disponível, o provider controlado devolve uma conclusão
`ausencia_verificada_no_escopo` com premissa documental, mas **sem verification**.
A chamada autenticada termina `failed`; o job guarda a resposta bruta e o erro
de validação. O teste exige zero objetos persistidos para esse job. Não basta
esconder a conclusão na UI ou aceitar a resposta e marcar revisão pendente.

Evidência: [G7](../../frontend/scripts/increment1-unified-gate.mjs#L160) e
[recusa no contrato](../../tests/e2e/test_evidence_browser.py#L164).

### G8 — premissa corrigida invalida dependente sem apagar aprovação

O teste identifica a **versão vigente da observação efetivamente citada** pelo
diagnóstico e a corrige pelo endpoint autenticado. A conclusão versão 2, antes
aprovada, passa a `stale=true` e sai das conclusões do envelope. O registro de
aprovação inteiro (autor, instante, motivo e premissas) e seu histórico são
comparados antes/depois. PostgreSQL confirma que a mesma versão ainda tem sua
aprovação original com as versões antigas das premissas.

Evidência: [G8](../../frontend/scripts/increment1-unified-gate.mjs#L165) e
[aprovação persistida](../../tests/e2e/test_evidence_browser.py#L168).

### G9 — reexecutar auditor cria avaliação nova sem substituir aceite (#220)

O staging começa **pendente** no fixture. O aceite/edição para 11 é realizado no
percurso via HTTP autenticado, com autor e data preenchidos pelo servidor.
O auditor roda antes e depois da correção da premissa. O teste exige IDs distintos
para as novas avaliações; compara status, valor decidido, autor e instante do
aceite anterior, que permanecem idênticos. Também verifica a preservação do
histórico de aprovação da conclusão dependente. O comparador e a persistência do
auditor são reais, sem provider controlado nesse caminho.

Evidência: [G9](../../frontend/scripts/increment1-unified-gate.mjs#L181) e
[staging persistido](../../tests/e2e/test_evidence_browser.py#L174).

## Fronteiras da prova

- **Reais:** login, tokens emitidos pela aplicação, autorização, servidor HTTP,
  build da UI, navegador, contratos Pydantic, PostgreSQL com commits, snapshots,
  revisões, manifesto, retomada e auditor determinístico.
- **LLM controlado:** quatro respostas na fronteira `app.core.ai_gateway.complete`:
  uma hipótese vinculada às premissas autorizadas, duas respostas vazias para
  equivalência de portas e uma ausência inválida. Não testa provider externo,
  escolha de modelo, qualidade técnica do diagnóstico ou validade jurídica.
- **Celery eager:** executa o corpo real da task no processo do teste, usando
  transporte em memória; não comprova Redis/broker remoto, serialização entre
  máquinas, perda de worker ou entrega da fila em produção.
- **Injeção adicional explícita:** indisponibilidade da skill de diagnóstico em
  uma chamada, para exercitar G6. As outras chamadas carregam os arquivos reais.
- **DOM versus HTTP:** login, rejeição, correção de conclusão, recarga, nova
  sessão, histórico, aprovação e capacidade insuficiente são verificados na UI.
  Aceite de staging, disparo de cadeia/auditor, retomada, comparação das portas,
  recusa de ausência e correção de premissa usam HTTP autenticado no mesmo
  navegador/caso. Não são apresentados como cliques que o teste não executou.
- Documentos e valores são sintéticos. Não é aceite dos originais Jobson/ELODI,
  homologação da sócia, prova do broker ou declaração de MVP completo.

## Resultado reproduzível

Recibo da execução local (caso sintético 1, 22 chamadas HTTP autenticadas
adicionais aos gestos DOM):

| Prova | Resultado observado |
|---|---|
| G1 | Avaliação rejeitada `assessment:29f0f4c6339f4605bcddb7fc8657a5ec` ausente do contexto efetivo; outras avaliações aprovadas presentes. |
| G2 | `conclusion:34ce2ab915424d70b4bb2bb365f5922c`: versões 1 e 2; conteúdo completo da 1 recuperado. |
| G3 | Rejeição e correção visíveis após reload e novo login; versão 2 inicialmente pendente. |
| G4 | Job do diagnóstico `2` antes e depois das duas retomadas; cursor `1`; próximas tentativas de redator registradas sem novos objetos. |
| G5 | Jobs `5` (síncrono) e `6` (assíncrono) com entradas persistidas iguais e skill real `1.3.0`. |
| G6 | Skill obrigatória do diagnóstico removida uma vez; capacidade insuficiente do diagnóstico visível na tela e no manifesto. |
| G7 | Job `8` recusado com `Ausência verificada exige consulta e resposta preservadas`; zero objetos persistidos. |
| G8 | Premissa `staging:1` corrigida de versão 2 para 3; conclusão versão 2 desatualizada, aprovação e histórico iguais aos anteriores. |
| G9 | Novos IDs de avaliação; aceite `aceito`, valor `11`, autor `1`, instante `2026-09-17T20:13:07.212958Z` idênticos antes/depois. |

Manifesto comparado nessa execução:

```text
skill = diagnostico/situacao_ambiental_imovel_rural
version = 1.3.0
skill_hash = 51d0fd5396f7faf5e751fc418097db17faf8d2667b50297eced5666870598483
context_hash = 690da066034f9d1cd56a3b59c4b6cc08c3c8e94a9b8622af3d7d07a083ec7a8b
system_hash = 414da79ef6eda7a1b0c01a233a3be42910aeeca44af6a0f69240fe941a9f94b1
```

IDs e hash de contexto mudam em outra execução descartável; a igualdade é exigida
entre as duas portas **dentro da mesma execução**, não entre fixtures diferentes.

Construir o frontend e instalar Chromium conforme [TESTING](../operacao/TESTING.md).
Com o ambiente de teste descartável configurado:

```powershell
$env:EVIDENCE_BROWSER_GATE='1'
python -m pytest tests/e2e/test_evidence_browser.py::test_incremento1_gate_nove_provas_no_mesmo_percurso -q --no-cov
```

O resultado específico deste teste e o artefato das nove fases são o gate.
A contagem global da suíte é regressão adicional, não substituto dessas provas.
