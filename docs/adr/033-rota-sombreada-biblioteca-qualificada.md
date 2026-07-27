# ADR-033 — Rota regulatória sombreada; a Análise Legal vira biblioteca qualificada

- **Status:** aceita
- **Data:** 2026-07-26
- **Branch:** `fix/validacao-26-07`
- **Decisão de domínio:** Isis (sócia ambientalista), pós-teste do caso 15
- **Contexto de domínio:** Ficha 07 §5 (caminho regulatório), ADR-021, ADR-028

## Contexto

A Análise Legal (`agent_legislacao`) vinha entregando, junto com a fundamentação,
uma **rota**: etapas numeradas, órgão por etapa, prazo estimado por etapa e
recomendações de conduta. A saída tem aparência de resposta pronta.

No caso 15 essa saída foi medida (`ai_jobs` 964, 971, 981, 992). O que ela
produziu, entre outras coisas:

- etapas com `prazo_estimado_dias` cuja fonte declarada era, literalmente,
  `"estimativa profissional — sem fonte normativa nos autos"`;
- sequência de protocolo (defesa → documentos → protocolização) montada sem
  saber o estado real do processo administrativo no órgão;
- órgão competente afirmado (`SEMAD-GO`) num caso que tem **também** passivo
  federal do IBAMA — ver ADR-034.

Nada disso é defeito de prompt. É consequência de pedir ao modelo uma coisa que
**não está nos autos nem na norma**: a ordem prática de andar com o caso depende
do histórico com o órgão, da mesa do analista, do que já foi protocolado e do que
a consultora sabe por telefone. Rota é conhecimento de ofício, não de corpus.

O risco não é simétrico. Fundamentação errada é corrigida na leitura — a
consultora reconhece a norma. Rota errada é seguida: perde-se prazo, protocola-se
no órgão errado, contesta-se o que não cabia. E uma rota plausível convida mais à
obediência do que uma rota obviamente ruim.

## Decisão

**1. No piloto, a Análise Legal não propõe rota.** Ela vira **biblioteca
qualificada**: localiza as normas aplicáveis e as apresenta **ao pé da letra**,
com fonte, alcance declarado (esfera/UF) e a data em que a vigência foi
conferida. Rótulo fixo na tela: *"fundamentação localizada — a rota é decisão do
consultor"*.

**2. Sombreada, não desligada.** O agente continua rodando e o output continua
persistido **inteiro** em `AIJob.result`. O que muda é o que a API **serve**:
`app/services/rota_shadow.py:apply_shadow()` remove os campos prescritivos
(`caminho_regulatorio`, `etapas`, `prazos_estimados`, `prazos_legais`,
`recomendacoes`, `documentos_necessarios`) na leitura de `/ai/jobs`.

Três consequências, todas desejadas:
- a decisão é **reversível** por flag, sem redeploy nem perda de histórico;
- o material fica **avaliável** (dá para medir, depois, se a rota gerada bateria
  com a rota que a consultora construiu);
- a rota **não pode vazar** para a tela por descuido de um componente — o dado não
  chega ao navegador. Filtrar no renderer seria uma promessa, não uma garantia.

**3. Flag por tenant.** `settings.ROTA_REGULATORIA_MODE` (default `shadow`),
sobrescrevível em `tenants.settings['rota_regulatoria_mode']`. Falha ao ler a
configuração cai no default conservador — na dúvida, sombra.

**4. `Rota`/`RotaPasso` (E5) são OUTRA entidade e não são tocadas.** A Rota da
macroetapa E5 (ADR-021, ADR-028) é o **serviço contratado**: construída pela
consultora, base do escopo da proposta, com máquina de estados própria. O que
esta ADR sombreia é a **sugestão de caminho** que o agente emitia dentro do
enquadramento regulatório. Objetos diferentes que a linguagem do projeto infeliz
mente aproximou. Nenhum endpoint, model ou gate da Rota-E5 muda aqui.

## Consequências

- A Análise Legal passa a responder "o que a norma diz", não "o que fazer".
- `EnquadramentoRegulatorioContent` continua com os campos prescritivos: o schema
  não muda, só a serving layer. Reativar é trocar uma string.
- Consumidores internos (o `DiagnosticoAgent` lê `chain_data["legislacao"]`) não
  são afetados — a sombra é da API, não do pipeline.
- Cobertura: `tests/services/test_rota_shadow.py` trava as duas pontas (o que sai
  filtrado **e** o que permanece no banco).

## Alternativas descartadas

- **Desligar o agente.** Perderia a fundamentação, que é o que ele faz bem, e
  perderia o material de avaliação.
- **Manter a rota com aviso "confira antes de usar".** É o que já existia, na
  prática, via `requires_review`. O caso 15 mostrou que aviso genérico não
  compete com a autoridade visual de uma lista numerada com prazos.
- **Filtrar só no frontend.** Uma tela nova, um renderer novo, e a rota volta.
