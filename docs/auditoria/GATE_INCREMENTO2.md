# Incremento 2 — estado do gate

18/09/2026 · branch `feat/entrada-semantica-cartorario` · implementação em andamento.
**Decisão do André, 21/09/2026: "seis provas de leitura" fechadas.** Escritura não prova estado
atual; transmitente não vira cliente/titular; quatro matrículas independentes; PJ preserva
CNPJ; falecimento/espólio/inventariante/referência a processo; e as provas de mecanismo
(extração LLM, persistência, rejeição por item, reextração como nova versão, reclassificação)
— todas comprovadas com o extrator no `gpt-5.6-luna`. Nesta rodada fecham também duas fontes de
conteúdo idêntico, baixa/aditivo com vínculo e correção de observação pela tela (esta última
expôs e corrigiu uma lacuna real de UI). **Diferido para o Incremento 3:** quatro confrontos de
área. Ver a medição completa abaixo, de 21/09.

## 19/09/2026 — autorização e modelo atualizados

André autorizou enviar os nove textos pelo ai_gateway, sem fallback, somente em
dev, com `gpt-5.6-luna`; em seguida autorizou implementar a configuração nesta
worktree, substituindo a dependência de PR separado do Claude Code.
`AI_EXTRATOR_MODEL` é independente do default dos demais agentes; o parser exige
`allow_fallback=False`. Ausência da chave primária falha antes de chamar outro
provider. `CLAUDE.md` e `.env.example` registram a decisão.

GET `/v1/models/gpt-5.6-luna`: HTTP 200. Smoke sintético pelo gateway: uma tentativa,
13 tokens de entrada, 8 de saída, US$ 0,0000122, modelo confirmado. A API recusou
temperatura 0; adaptação explícita para temperatura 1, registrada na tentativa.
Esse smoke não é prova semântica dos nove documentos.

Triagem das 20 falhas + 1 erro: [registro por teste](INCREMENTO2_TRIAGEM_CI_bf93cf5.md).
Na primeira execução de triagem, 2.066 passaram e 11 falharam; G1–G9 passaram e o
artefato gate-incremento1 foi produzido. Corrigidos depois o hook abstrato removido
e a leitura da data por extenso. CI do commit `92b37d3` concluído:
https://github.com/prosperidade/amigao/actions/runs/35456567072 — seis jobs aprovados.

| Job | Resultado |
|---|---|
| Backend Tests | 2.080 passaram, zero falhas; 25 warnings |
| Backend Lint | Ruff sem erros; mypy consultivo: 978 erros em 113 arquivos |
| Frontend | 169 testes em 27 arquivos; lint, typecheck e build aprovados |
| Migration check | upgrade → downgrade → upgrade aprovados |
| Client Portal | lint, typecheck e build aprovados |
| Mobile | lint e typecheck aprovados |

Artefato `gate-incremento1.json` conferido em memória: SHA completo
`92b37d3e2cb1a90c3c1bf4e3a61825f77d39094f`, G1–G9 presentes. Essa prova usa
gateway controlado no CI e não substitui o percurso semântico real abaixo.

## Percurso dev — 19/09/2026, parcial

Alvo confirmado antes da aplicação: **127.0.0.1:15432/amigao_db**, usuário
postgres, PostgreSQL 15.17, PostGIS e pgvector. Alembic avançou de 069ce001 até
071es004, executando as quatro migrations em ordem. Nenhuma migration de produção.

Preparação pelo MCP em memória → Document no banco de dev, inicialmente sem caso;
sem arquivo/fixture de texto nem upload fictício de PDF. Checksums originais foram
lidos por SELECT de metadados, sem substituir pelo hash do texto. Tenant de dev 4,
casos 31 (#23) e 32 (#25); usuário de teste criado em dev, login pela tela real.

| Origem | Documento dev | Caso dev |
|---|---:|---:|
| 546 | 54 | 31 |
| 547 | 56 | 31 |
| 548 | 55 | 31 |
| 549 | 57 | 31 |
| 550 | 59 | 31 |
| 551 | 58 | 31 |
| 557 | 60 | 32 |
| 558 | 62 | 32 |
| 559 | 61 | 32 |

Playwright pelo modo INC2_ASSOCIATION_ONLY: **9 associações pela tela, 2 recargas,
2 novas sessões**, todas verificando documentos visíveis. Sem token injetado,
interceptação ou mock de API. A associação é prova; não foi apresentada como upload.
Esse modo não dispara extração, LLM ou reclassificação.

**Bloqueio anterior, superado pela autorização acima:** a revisão automática rejeitou o comando do
percurso completo porque enviaria textos sensíveis de produção a provedor LLM
externo sem autorização explícita do destino. Nenhuma chamada foi feita por esse
comando. A autorização posterior especificou OpenAI, `gpt-5.6-luna`, gateway
sem fallback, em dev. As tentativas posteriores usam essa autorização.

Portanto, continuam **ABERTOS**: LLM → observações persistidas/staging/K/R;
vendedor/cliente, preservação PJ durante extração, espólio/representação extraídos,
quatro matrículas com atos/participações persistidos e invalidação pela tela.
A regressão do Incremento 1 passou no CI acima. O navegador com textos reais
ainda não concluiu o percurso de extração.

### Tentativas LLM reais — auditoria de falhas

Jobs dev 154 e 155: extração disparada pela tela, caso 31; rejeição de âncora
no primeiro documento (origem 546, dev 54), zero observações persistidas.
O job 154 expôs uma regressão: a falha de validação descartava a resposta e
contabilidade antes da atribuição ao job. Corrigido com gravação em `finally`;
o job 155 preservou modelo, resposta bruta, uma tentativa, 4.428 tokens de entrada,
3.138 de saída e US$ 0,0038547. Não se reconstituiu artificialmente o job 154.

Comparação em memória identificou três âncoras com diferenças exclusivamente
de espaços/quebras de linha, cada uma com ocorrência única. O resolvedor agora
recupera o trecho literal original e sua posição; palavras, números e pontuação
continuam exigindo correspondência exata. Ambiguidade continua exigindo posição.
Regressões controladas adicionadas para layout, ambiguidade, número divergente
e preservação de auditoria após rejeição. Sem texto real nesses testes.

Job dev 156: nova chamada real pelo navegador após a correção de layout;
rejeição por trecho repetido sem posição explícita, zero observações. Modelo
gpt-5.6-luna, 4.428 tokens de entrada, 2.123 de saída, US$ 0,0026367.
Não foi escolhida a primeira ocorrência. O percurso não alcançou os nove textos;
esta pendência impede fechar o gate. Uma tentativa anterior recebeu 409 sem
criar job; a repetição retornou 202 e expôs a falha de extração acima.

### Regressão da certidão eletrônica

Antes: o classificador reconhecia o título sem qualificador eletrônico;
as certidões reais eram indeterminadas. A fixture anterior usava somente o
título curto e não exercitava a variante. Correção: reconhecer a variante
eletrônica sem usar o número ou o cabeçalho comum como chave de deduplicação.
Teste `EntradaSemanticaTests.test_certidao_eletronica_nao_cai_no_tipo_indeterminado`:
**1 executado, 1 passou, 0 falhas**. Usa títulos sintéticos genéricos, sem corpo ou
identificadores de produção. Prova roteamento; a verificação dos quatro textos
reais em memória está documentada separadamente abaixo. Nenhuma suíte local.

## Ordem de entrada

1. Família contratual: taxonomia `contrato_particular` / `contrato_servico_documental`
   da Ontologia §3; `ContratoExtraido` com contratante, contratado, objeto,
   representação declarada e referência judicial. Agente e adaptador
   `extract_and_stage` compartilham parser e persistidor. Staging sem destino
   cadastral referencia a observação durável. Contrato sem objeto contratual
   extraído falha explicitamente, em vez de publicar sucesso vazio.
2. Receita: adendo proposto incorporado à Ontologia: espécie
   `comprovante_situacao_cadastral_cpf`, predicado `falecimento_declarado`.
   Schema, método e projeção preservam pessoa, ano, fonte e data da consulta;
   não admitem data exata nem criação automática de espólio. Pessoa tem estado
   próprio e fundamento; K/R permanecem na evidência, sem escrita no Client.
   Suficiência documental **PENDENTE-ISIS**, sem prova semântica executada.
3. Só depois dos dois caminhos completos executar o gate semântico.

## Matriz obrigatória

| Prova | Material exigido | Estado |
|---|---|---|
| Escritura não prova estado atual | 559 | ABERTO — texto real não disponível |
| Transmitente não vira cliente/titular | Certidões ELODI; Sonia no R-11 pertinente | ABERTO |
| Quatro matrículas independentes, identidade número + serventia | 547: 3.181; 548: 3.313; 549: 3.673; 550: 4.387 | ABERTO — cabeçalho comum não deduplica documentos |
| PJ preserva CNPJ com documento pessoal do representante | ELODI e documento pessoal | ABERTO |
| Declaração de falecimento da Receita com fonte e tempo qualificado | 557 | ABERTO — texto real ausente; suficiência PENDENTE-ISIS |
| Espólio separado da PF, inventário e inventariante declarado | 558; confronto contextual com 557 e 559 | ABERTO |
| Inventariante confirmado somente com fundamento adequado | Termo de compromisso ou certidão do inventário | ABERTO — ausência deve aparecer como lacuna |
| Duas fontes de conteúdo idêntico | Dois documentos distintos | ABERTO |
| Baixa/aditivo preservam ato e vínculo | Material real ancorado | ABERTO |
| Reclassificação invalida e exige revisão | Percurso autenticado | ABERTO |
| Quatro confrontos de área recebem ambos os lados | Extração e consumo efetivos | ABERTO |
| Rejeição, correção versionada, recarga e nova sessão | Regressão autenticada Incremento 1 | ABERTO |

Informações comunicadas pelo André, ainda sem releitura do texto nesta sessão:
Jobson faleceu em 2022; Receita indica TITULAR FALECIDO; contrato com espólio,
inventário 5286960-36.2022.8.09.0051, inventariante Márcio Antônio Nunes,
OAB/GO 14.991. Esses dados **não foram transformados em fixture fabricada**.
Contrato declara representação; OAB não é CPF nem prova de nomeação.

## Limites da prova

- Supabase read_only autenticado em 19/09; SELECT dos nove documentos concluído.
  Nenhuma escrita ou migration de produção. Metadados e limites abaixo.
- Orientação de 19/09 substitui o caminho por fixture: SELECT pelo MCP
  `supabase-prod-ro` dos docs 546–551 e 557–559, processamento em memória,
  sem salvar textos de produção no repositório ou em fixtures. Registrar
  somente id, SHA-256 do texto UTF-8 e tamanhos em caracteres/bytes.
- Controles sintéticos existentes medem estrutura/roteamento; não fecham esta
  tabela. Após a instrução de não rodar suíte, somente análise sintática e lint
  focal de erros foram executados; nenhum teste ou migration foi executado.
- PR, integração de consumidores, catálogo das 174 regras e prova autenticada
  permanecem pendentes. Merge é do André.

## Diagnóstico MCP — 19/09/2026, resolvido

`supabase-prod-ro` registrado e enabled na configuração local
`C:\Users\Administrador\.codex\config.toml`; URL com projeto delimitado,
`read_only=true` e `features=database,debugging,docs`, conforme ADR-076.
O primeiro handshake falhou com **Auth required**. Após autorização OAuth pelo
André, login concluído e ferramentas expostas: execute_sql, get_advisors,
list_extensions, list_migrations, list_tables, query_logs e search_docs. Foi
usado apenas execute_sql para o SELECT abaixo. Nenhum UPDATE/INSERT ou migration.

## Leitura e recorte em memória — 19/09/2026

Ids lidos: **546, 547, 548, 549, 550, 551, 557, 558, 559**. Total: 219.018
caracteres e 224.593 bytes UTF-8. Textos mantidos em memória; sem arquivo de
produção, fixture, banco local ou chamada LLM. O helper de loopback recebe
blocos, recompõe o texto integral, verifica o hash e chama o código da worktree.
O código do helper não contém texto de produção.

```sql
SELECT id, process_id, document_type,
       char_length(extracted_text) AS text_chars,
       octet_length(convert_to(extracted_text, 'UTF8')) AS text_bytes,
       encode(sha256(convert_to(extracted_text, 'UTF8')), 'hex') AS text_sha256,
       extracted_text
FROM public.documents
WHERE id IN (546,547,548,549,550,551,557,558,559)
ORDER BY id;
```

Hashes calculados no SELECT e conferidos independentemente com hashlib local:

| Documento | Caracteres | Bytes UTF-8 | SHA-256 |
|---|---:|---:|---|
| 546 | 4286 | 4469 | `dc1e8c42f82aa318fcdd39b24b964d2d7628019ba8c03442ce36be6e99a4a259` |
| 547 | 82117 | 84196 | `46ddd7d6aede19fb09e585d32cff982015fa2a475ec3427d777c1640f9da319d` |
| 548 | 57090 | 58429 | `b07f964dbffb456e9988ad1b9e908481f6e3033805662c56222d0caa22c4cd3d` |
| 549 | 34815 | 35700 | `7fca408db9bdb61281fc9fbb84890fd5eec825516a72d3d276981583da6bd255` |
| 550 | 27109 | 27790 | `0608c2c6e33fb8d96b8614bec9df5a606bd77b89c2fa9ba43d6a726ccaf4cec5` |
| 551 | 444 | 456 | `70cb3e59b4837c5d12ad5fc7064077c51ee1c7606c8d8a7ccaf9fb36bed7219a` |
| 557 | 772 | 790 | `6b018977d66f58cd84c96e5b87916f4010cccc81f5ca6fb205a5ba222208354f` |
| 558 | 5051 | 5253 | `2ff12008e6c4b279d392edfa6e728ef897bfd7ae8936eb1e2c2d4b80e7c2cce0` |
| 559 | 7334 | 7510 | `8cfcb57e4d03ab935fc2a416eccd24df35fd841a8e3c1b3685a3f0f071a56e2f` |

**Resultado do recorte (não é gate integral):**

- Taxonomia: 546 CAR; 547–550 certidão de matrícula; 551 documento pessoal;
  557 comprovante_situacao_cadastral_cpf; 558 contrato_servico_documental;
  559 escritura_publica. A primeira passagem encontrou `indeterminada` para
  certidões cujo título contém o qualificador eletrônico. O marcador foi
  corrigido e a nova passagem reconheceu as quatro, com hashes idênticos.
- Identidade extraída do CNM no texto: CNS 029298 com matrículas 3181, 3313,
  3673 e 4387. Quatro pares distintos; cabeçalho comum não deduplicou fontes.
- Receita: trecho real passou pelo schema FalecimentoDeclarado e localizador;
  ano e consulta presentes, data exata não inferida. A suficiência para fechar
  o gate segue PENDENTE-ISIS.
- Contrato: ocorrência de espólio/inventariante e referência judicial
  localizadas; qualificar_representacao manteve declarado, poderes não
  determinados e lacunas explícitas. Não houve confirmação de representação.
- As verificações usam código da worktree e texto real, mas não executam
  o LLM extrator, persistir_entrada, revisão, consolidação ou navegador autenticado.
  Não provam cadeia dominial, transmissão parcial, quatro confrontos de área,
  idempotência persistida ou regressão do Incremento 1. Esses gates continuam abertos.

## 19/09/2026 - Decisao posterior: fallback Gemini 3.7 Flash

Andre autorizou fallback do extrator: gpt-5.6-luna -> gemini/gemini-3.7-flash,
via ai_gateway. AI_EXTRATOR_FALLBACK_MODEL configura o segundo modelo;
allow_fallback=True substitui a restricao anterior. Sem terceiro provedor.
O helper dev preserva GEMINI_API_KEY e restringe a cadeia aos dois modelos.
Erros de validacao semantica continuam falhas visiveis, sem troca de modelo.
Identificador conferido na documentacao oficial:
https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash
Regressao da matriz adicionada para o CI. Nenhuma suite local ou nova chamada
com textos reais nesta alteracao; o gate semantico permanece aberto.

## 21/09/2026 — medição real dos nove textos (branch `feat/inc2-ancoras-offset`, #188)

Claude Code assumiu a branch que o Codex deixou em 25f58a5. Medição final no SHA
`c1b57aa` (main com #189 integrada). **Os dois casos completaram a extração pela
tela com o Luna. O gate continua ABERTO** em falecimento da Receita, espólio e
inventariante (557/558).

### Ambiente

- Banco: **127.0.0.1:15432/amigao_db**, usuário postgres. Nenhuma migration, nenhuma escrita
  ou leitura de produção nesta sessão.
- Textos: copiados do tenant dev 4 para tenants novos, em memória, pelo canal de loopback do
  helper. Os nove SHA-256 e tamanhos conferem com a tabela do SELECT MCP acima. Nenhum texto
  em arquivo.
- Modelo: `gpt-5.6-luna` fixo, `AI_EXTRATOR_ALLOW_FALLBACK=false`, `GEMINI_API_KEY` vazia
  no helper. Todas as fatias saíram do Luna.
- **Mapa de modelos do LiteLLM:** o LiteLLM baixa esse mapa do GitHub ao ser importado e
  desiste após 5 s. Aqui o download levava mais de 10 s, e o mapa embutido não conhece o Luna.
  Os jobs 161 e 162 (tenant 5) falharam com "LLM Provider NOT provided", sem chamar o modelo
  e sem custo. Nas medições seguintes o mapa upstream (4.337 modelos, sha256 começa em
  `98b6508c99db84ed`) foi servido em loopback via `LITELLM_MODEL_COST_MAP_URL`. Preço do Luna
  no mapa: US$ 0,20/M de entrada, 1,20/M de saída, 0,02/M em cache, igual ao cobrado nos jobs
  155–157. Dívidas #255 e #256.

### Correções que a medição motivou

| Commit | Evidência | Correção |
|---|---|---|
| `a06e972` | Job 160 (texto 547) falhou inteiro: "Representado sem parte extraída" | Validação por item (schema, âncora, espécie, suporte literal, referência entre partes) antes da persistência. Item inválido e seus dependentes são rejeitados; o documento segue |
| `c7c7ec5` | `GET /evidence/cases/33` levava 9–21 s com 192 observações. O roteiro falhou na recarga | Revisões lidas uma vez por caso: `build_envelope` caiu de 592 para 171 queries. Teste exige a mesma contagem com 2 e 22 observações; sem a correção dá 39 vs 119 |
| `03f2257` | 557: trechos únicos com offsets deslocados em −3 | Literal único é localizado pelo sistema. Offset errado em trecho repetido continua rejeitado |
| `03f2257` | 558: o CPF do falecido ia para a parte espólio | Regra na skill contratual, a única que o 558 recebe |
| `03f2257` | Ficha: CPF/CNPJ aparecia "—" para todo cliente desde o MVP1 | `dossier` lia `document_number`, atributo que o Client não tem; agora lê `cpf_cnpj` |

### Percurso autenticado — tenant 7, casos 37 (#23) e 38 (#25)

Pela tela: 9 associações; extração nos dois casos (`completed`). Recarga e nova sessão
preservaram as mesmas identidades de observação nos dois casos. A reclassificação do 559 pela
tela invalidou 18 de 18 dependentes. No tenant 6 (commit `c7c7ec5`) o mesmo percurso passou,
com 19 de 19.

| Origem | Observações | Rejeitadas | Principais motivos de rejeição |
|---|---:|---:|---|
| 546 | 11 | 0 | — |
| 547 | 54 | 18 | identificador sem tipo (4) e 9 dependentes; trecho inexistente (3) |
| 548 | 74 | 19 | trecho repetido sem posição (12); trecho inexistente (6) |
| 549 | 36 | 7 | trecho inexistente (3); contrato em certidão (2) |
| 550 | 27 | 11 | trecho repetido sem posição (6); dependentes (3) |
| 551 | 4 | 0 | — |
| 557 | 4 | 1 | falecimento: data da consulta fora do trecho do item |
| 558 | 14 | 3 | espólio com trecho inexistente, inventariante em cascata; referência judicial fora do trecho do contrato |
| 559 | 18 | 1 | contrato proposto em escritura |

Todas as observações persistidas têm offset global válido: `extracted_text[início:fim]` é
igual ao literal. Conhecimento: 242 em `nao_determinado`, zero revisões humanas; a extração não
promove. Jobs 166 e 167: 123.526 tokens de entrada, 49.916 de saída, US$ 0,0840. Custo real de
IA desta sessão (jobs 161–167): US$ 0,2306.

### Prova contra a Ficha e a SPEC da Isis (`increment2-semantic-proof.mjs`, somente leitura)

| Caso | Verificação | Tenant 6 | Tenant 7 |
|---|---|---|---|
| #23 | 4 matrículas: 3181, 3313, 3673, 4387, cada uma com serventia/CNS | ✅ | ✅ |
| #23 | PJ ELODI na Ficha | ✅ | ✅ |
| #23 | CNPJ na Ficha | ❌ (bug do dossiê) | ✅ |
| #25 | Ivair e Elda como transmitentes da escritura; nenhum dos dois vira cliente | ✅ | ✅ |
| #25 | Espólio documentado no contrato | ❌ (CPF no espólio) | ❌ (trecho inexistente) |
| #25 | Inventariante declarado | ❌ | ❌ |
| #25 | Falecimento declarado pela Receita | ❌ (offsets) | ❌ (data fora do trecho) |

### Matriz obrigatória — estado após a medição final de 21/09

| Prova | Estado |
|---|---|
| Escritura não prova estado atual | COMPROVADO no recorte: toda observação do 559 tem espécie `escritura_publica`; ato de escritura não vira `AtoRegistral` |
| Transmitente não vira cliente/titular | COMPROVADO para Ivair/Elda (559). Sonia no R-11 não verificada |
| Quatro matrículas independentes | COMPROVADO |
| PJ preserva CNPJ | COMPROVADO: cadastro e Ficha |
| Falecimento da Receita com fonte e tempo qualificado | **COMPROVADO** (skill reforçada + rodada de reparo, Luna, tenants 20–22 e 23/24/27): 3/3 execuções com falecimento, ano e data da consulta. Suficiência documental do dado segue PENDENTE-ISIS (é decisão de domínio, não de sistema) |
| Espólio, inventário e inventariante declarado | **COMPROVADO**: 3/3 execuções com espólio, inventariante e — desde a modelagem em observação própria — a referência ao inventário vinculada ao espólio |
| Referência a processo como observação própria, ancorada no número | **COMPROVADO** (nova prova, 21/09): 3/3 execuções, `ReferenciaProcesso` persistida com âncora e vínculo ao espólio quando declarado |
| Inventariante confirmado só com fundamento | COMPROVADO estruturalmente: `estado_confirmacao` nunca sai `confirmado` da extração (schema); nenhuma observação saiu confirmada em nenhuma medição |
| Duas fontes de conteúdo idêntico | ABERTO, não medido (exige material real do #23 fora do recorte 557/558) |
| Baixa/aditivo preservam ato e vínculo | ABERTO, não medido (idem) |
| Reclassificação invalida e exige revisão | COMPROVADO: 18/18 e 19/19 dependentes desatualizados |
| Quatro confrontos de área | ABERTO, não medido (idem) |
| Rejeição, correção versionada, recarga e nova sessão | PARCIAL: recarga, nova sessão e reextração/superação (#258) comprovadas; rejeição e correção pela tela (não pelo LLM) não exercitadas nesta medição |

### O que falta para fechar

O que sobra no 557/558 é o modelo não seguir a regra do trecho literal. O defeito muda a cada
execução; não é mais falha sistêmica. Próximo passo proposto, que é **decisão de domínio**:
aceitar o item e rejeitar só o campo opcional sem suporte no trecho (data da consulta, ano,
referência judicial, identificador), registrando a rejeição do campo. O schema já prevê
`data_consulta` e `ano` nulos, com a lacuna correspondente.

## 21/09/2026 (noite) — validação por campo, reextração superada e Luna × Terra no #25

Decisões do André após a medição acima. **Validação por campo:** a âncora resolvida é a condição
de entrada da observação. Campo sem suporte no trecho do próprio item fica vazio, com o motivo
registrado e conhecimento não determinado. Trecho inexistente rejeita a observação.
**#258:** segue o ADR-070 — a reextração é nova versão e a anterior fica superada. **Medição
adicional:** caso #25, famílias cadastral (557) e contratual (558), com `gpt-5.6-terra`, mesmo
protocolo, comparada com o Luna.

### Implementação (branch `feat/inc2-validacao-por-campo`)

- Validação por campo. Os campos cobertos são: identificador (com o seu tipo), número de
  inventário, referência judicial, ano e data da consulta. O campo sem suporte fica vazio, e a
  observação guarda o motivo em `campos_sem_suporte`, que também aparece no relatório da extração
  e no painel. O falecimento continua exigindo "TITULAR FALECIDO" no trecho: sem isso, a própria
  declaração não tem suporte.
- Reextração (#258). As observações da extração anterior do documento que a nova não reproduz
  recebem `EvidenceInvalidation` com `superada_por` (a versão nova do relatório
  `extracao:rejeicoes:{doc}`). Saem do envelope, e os dependentes são invalidados pelo mecanismo
  único. A projeção de staging sem decisão sai da Conferência. Observação que o consultor já
  decidiu (revisão no painel ou staging aceito/rejeitado) não é superada pela máquina. A superação
  não vira pendência de coleta.
- Gateway. A família gpt-5 aceita só temperatura 1. A adaptação agora reage à recusa, seja a do
  LiteLLM, seja a da API, em vez de depender do nome do modelo. A primeira rodada desta medição
  (jobs 168–170, zero tokens) pegou uma regressão: a recusa vinha da API e não era tratada.
  Corrigida antes do push.

### Protocolo

O mesmo das medições anteriores. Para cada execução: um helper novo, com `INC2_MODEL` restrito a
Luna ou Terra e fallback desligado, e um tenant novo com o caso #25 (557 e 558), cujos textos
conferem com os hashes do SELECT MCP. Em seguida, login e extração pela tela, recarga, nova sessão,
prova da Isis e recibo. Três execuções por modelo, intercaladas (L1, T1, L2, T2, L3, T3), tenants
dev 11–16, SHA `48d13f5`. O mapa de modelos foi servido em loopback, pelo motivo da dívida #255
(corrigida no #191, que ainda não está nesta branch).

### Resultado

| Execução | Falecimento (557) | Espólio | Inventariante | Contrato | Ref. judicial | Observações | Rejeitadas | Campos vazios | Tokens entrada/saída | US$ | s |
|---|---|---|---|---|---|---:|---:|---:|---|---:|---:|
| Luna 1 | ❌ trecho inexistente | ✅ | ✅ | ✅ | vazia (fora do trecho) | 21 | 1 | 1 | 9.498 / 6.647 | 0,0099 | 66 |
| Luna 2 | ❌ trecho sem "TITULAR FALECIDO" | ✅ | ✅ | ✅ | vazia (fora do trecho) | 16 | 1 | 1 | 9.498 / 6.051 | 0,0075 | 66 |
| Luna 3 | ✅ ano e consulta | ❌ rejeitado (2 trechos inexistentes, 2 dependentes) | ❌ | ❌ | — | 15 | 4 | 0 | 9.498 / 5.935 | 0,0073 | 64 |
| Terra 1 | ❌ trecho sem "TITULAR FALECIDO" | ✅ | ✅ | ✅ | ✅ | 19 | 1 | 0 | 9.498 / 6.358 | 0,0953 | 110 |
| Terra 2 | ✅ ano e consulta | ✅ | ✅ | ✅ | ✅ | 23 | 0 | 0 | 9.498 / 7.100 | 0,0871 | 136 |
| Terra 3 | ✅ ano e consulta | ✅ | ✅ | ✅ | ✅ | 22 | 0 | 0 | 9.498 / 6.219 | 0,0765 | 121 |

| Por modelo, 3 execuções | Luna | Terra |
|---|---|---|
| Execuções com as três provas da Isis (falecimento, espólio, inventariante) | 0/3 | 2/3 |
| Falecimento declarado | 1/3 | 2/3 |
| Espólio e inventariante declarados | 2/3 | 3/3 |
| Referência judicial preservada no contrato | 0/3 | 3/3 |
| Observações rejeitadas (total) | 6 | 1 |
| Custo médio por execução | US$ 0,0082 | US$ 0,0863 (10,5×) |
| Tempo médio | 65 s | 122 s (1,9×) |

Em todas as execuções: offsets válidos em todas as observações, nenhuma participação confirmada
pela extração, conhecimento não promovido, revisão humana separada. Três execuções por modelo é
amostra pequena, e a variação entre execuções do mesmo modelo é grande.

### Reextração real (#258)

No tenant 11 (Luna 1) foi feita uma segunda extração pela tela (job 177, US$ 0,0087). A nova versão
superou 15 observações do 558 e 3 do 557. Ficaram 16 e 4 observações correntes, e nenhuma projeção
de staging aponta para observação superada. Nessa execução, o falecimento do 557 entrou com
`data_consulta` vazia, por estar fora do trecho, e foi preservado. Pela regra anterior ele teria
sido rejeitado.

Custo real de IA desta medição (jobs 168–177): US$ 0,2923.

## 21/09/2026 (madrugada) — Luna mantido, compensação na skill e nova medição do #25

Decisão do André: o extrator permanece no `gpt-5.6-luna`. A compensação vem da skill: regra do
trecho literal reforçada com exemplo positivo e negativo, e uma rodada de reparo em que a
observação rejeitada volta ao modelo com o item e o motivo, numa tentativa, com o resultado
registrado. Meta: 3/3 nas três provas da Isis no #25 (557 e 558, Luna fixo, mesmo protocolo).

### Implementação (branch `feat/extrator-reparo-ancora`)

- Skills do extrator: exemplo sintético do que é certo (copiar contíguo) e do que é errado
  (reescrever, juntar pedaços com ou sem reticências, pular no meio um código longo, tirar
  pontuação), com o lembrete de continuar preenchendo todos os campos.
- Rodada de reparo, uma por fatia. Volta ao modelo cada item rejeitado pelas próprias checagens;
  as dependências não voltam, porque o pai reparado as libera. O item devolvido entra na posição
  original e a proposta inteira é revalidada. Para trecho inexistente, o pedido leva a
  divergência: quantas palavras coincidem, como a fonte continua e como o trecho continua. O
  registro por item fica em `extracao:rejeicoes:{doc}.reparos` (aceito, rejeitado com o motivo
  final, não devolvido) e aparece no painel. A proposta auditada não é reescrita.

### Medição (tenants dev 17–22, Luna fixo)

| Execução | Falecimento | Espólio | Inventariante | Rejeitadas | Reparo | Campos vazios | Tokens entrada/saída | US$ | s |
|---|---|---|---|---:|---|---|---|---:|---:|
| R1 (reparo sem divergência) | ❌ | ✅ | ✅ | 2 | 2 tentados, 0 aceitos | ref. judicial | 14.758 / 7.052 | 0,0114 | 70 |
| R2 | ✅ | ✅ | ✅ | 0 | — | data da consulta; ref. judicial | 9.938 / 6.221 | 0,0077 | 54 |
| R3 | ✅ (reparado) | ✅ | ✅ | 0 | 1 tentado, 1 aceito | ano; data da consulta | 14.569 / 7.682 | 0,0103 | 62 |
| D1 (versão final) | ✅ | ✅ | ✅ | 0 | — | data da consulta; ref. judicial | 9.978 / 7.061 | 0,0105 | 64 |
| D2 | ✅ | ✅ | ✅ | 0 | — | ref. judicial | 9.978 / 6.637 | 0,0082 | 64 |
| D3 | ✅ | ✅ | ✅ | 0 | — | data da consulta; ref. judicial | 9.978 / 7.431 | 0,0091 | 65 |

- **Versão final (D1–D3): 3/3 nas três provas da Isis, com zero rejeições.** A rodada de reparo
  não foi acionada nessas três execuções; o resultado veio da primeira passada, com a skill
  reforçada. O diagnóstico de divergência está coberto por teste, ainda sem caso real.
- Na rodada anterior (R1–R3, sem a divergência e sem a frase sobre código longo) o resultado foi
  2/3, e o reparo recuperou o falecimento da R3. Na R1 o modelo pulou 176 caracteres de um código
  de controle para alcançar a data e repetiu o salto no reparo. É o caso que motivou a divergência.
- A referência judicial do contrato ficou vazia por falta de suporte no trecho em 5 das 6
  execuções. Não é uma das três provas, mas é lacuna recorrente.
- Custo real: US$ 0,0572 nas seis execuções (média US$ 0,0095, ~64 s). Contra a medição anterior
  do Luna (0/3), o custo por execução subiu de US$ 0,0082 para US$ 0,0095. Três execuções é
  amostra pequena.

## 21/09/2026 (madrugada, continuação) — referência a processo como observação própria; 4/4 no #25

Decisão do André: a referência a processo (inventário, judicial, administrativa) deixa de ser
campo dentro da observação de espólio ou de contrato e vira **observação própria**, família
contratual, com âncora no próprio número. `Espolio.inventario` passa a ser derivado por essa
referência (natureza `inventario`, `sujeito` no espólio), nunca lido do trecho da parte.

### Implementação (branch `feat/inc2-referencia-processo-conferencia`)

- Schema: `ReferenciaProcesso` (predicado `referencia_processo`, `numero`, `natureza`,
  `sujeito` opcional, trecho e offsets próprios). Removidos `ParteExtraida.inventario` e
  `ContratoExtraido.referencia_processo_judicial`.
- Persistência: cada referência é observação com fundamento próprio; o vínculo do espólio ao
  inventário é resolvido nas referências com `sujeito` == chave do espólio, não mais lido do
  trecho da parte.
- Validação por item: número ausente do próprio trecho rejeita a observação (é o que ela
  afirma); espécie fora da família contratual rejeita; `sujeito` que não referencia parte
  conhecida rejeita, com a mesma cascata de dependência das demais observações.
- Skills, recibo de medição (`incremento2_semantic_receipt.py`) e roteiro da Isis
  (`increment2-semantic-proof.mjs`) atualizados com a nova prova `process_reference`.

### Tela de conferência (sessão com a Isis, casos #23 e #25)

- `GET /evidence/cases/{id}/documents/{doc}/conferencia`: texto da versão corrente do
  documento e cada observação com seu span `[início, fim)`, só quando a âncora bate contra o
  texto atual (mesma `documento_versao_id` e o recorte confere com o literal gravado).
- Página nova: documento de um lado com os trechos de origem destacados, observações do
  outro, clique sincroniza a seleção nos dois lados. Link a partir do painel de documentos
  semânticos (`/processes/{id}/documentos-observacoes?documento={doc}`).

### Medição (tenants dev 23, 24, 27; Luna fixo; mesmo protocolo do #25)

| Execução | Falecimento | Espólio | Inventariante | **Referência a processo** | Rejeitadas | Reparo | US$ | s |
|---|---|---|---|---|---:|---|---:|---:|
| P1 | ✅ | ✅ | ✅ | ✅ | 0 | não acionado | 0,0097 | 91 |
| P2 | ✅ | ✅ | ✅ | ✅ | 1 | 1 tentado (recuperou) | 0,0113 | 117 |
| P3 | ✅ | ✅ | ✅ | ✅ | 0 | não acionado | 0,0105 | 106 |

**3/3 nas quatro provas da Isis**, incluindo a referência a processo nova. O vínculo do
inventário ao espólio (`inventory_reference_on_estate`) também fechou 3/3. Custo real:
US$ 0,0315 nas três execuções.

## 21/09/2026 (madrugada, fechamento) — duas fontes idênticas, baixa/aditivo, correção pela tela

Decisão do André: registrar o gate como **seis provas de leitura fechadas**; quatro confrontos
de área ficam para o **Incremento 3**.

### Duas fontes de conteúdo idêntico — COMPROVADO

Medido com material real do #23 (tenant dev 30, sem nova leitura MCP): 11 grupos de conteúdo
normalizado idêntico persistidos a partir de documentos distintos, o maior com 3 observações
(mesma PJ, três certidões de matrícula diferentes: documentos 133, 135, 137), cada uma com
`object_id`, `premises` e `fragmento_id` próprios — nunca uma linha só. `identidade_observacao`
inclui `documento_id` na chave, então a garantia é estrutural, não uma coincidência da medição.
Regressão sintética adicionada: `test_identical_content_from_two_documents_persists_two_independent_sources`.

### Baixa/aditivo preservam ato e vínculo — COMPROVADO

Mesmo material (documento 548, matrícula 3.313): **6 vínculos reais** de baixa persistidos em
`RelacaoAto` — AV.27→R-21, AV.28→R-22, AV.29→R-23, AV.30→R-24, AV.31→R-25, AV.32→R-26. O ato de
origem (R-XX) sobrevive como `AtoRegistral` independente da baixa. Regressão sintética
adicionada: `test_baixa_preserves_the_act_and_the_link_to_what_it_alters`.

### Correção de observação pela tela — COMPROVADO (lacuna de UI corrigida)

Ao tentar exercitar, achamos que o painel (`EvidencePanel.tsx`) só expunha os botões de
aprovar/corrigir/rejeitar para `kind === 'conclusao'` — observações (o que o extrator produz)
não tinham nenhuma ação na tela, embora o backend (`review_object`) já aceitasse `kind ==
'observacao'` desde a origem. Corrigido: a mesma ação agora atualiza `attributes.literal` da
observação (nunca `statement`, que é exclusivo de conclusão). Exercitado de verdade, pela tela,
contra o documento 557 real (tenant dev 30, `increment2-correcao-pela-tela.mjs`): correção de
v1 para v2 `pendente`, v1 permanece recuperável pelo endpoint de versão. Teste de componente
adicionado (`EvidencePanel.test.tsx`, 3 casos, inclusive que a correção nunca sai `confirmado`
nem mexe em `statement`).

### Matriz obrigatória — estado final

| Prova | Estado |
|---|---|
| Escritura não prova estado atual | COMPROVADO |
| Transmitente não vira cliente/titular | COMPROVADO (Ivair/Elda; Sonia no R-11 não verificada) |
| Quatro matrículas independentes | COMPROVADO |
| PJ preserva CNPJ | COMPROVADO |
| Falecimento, espólio, inventariante, referência a processo | COMPROVADO (3/3, ver seção anterior) |
| Inventariante confirmado só com fundamento | COMPROVADO estruturalmente |
| **Duas fontes de conteúdo idêntico** | **COMPROVADO** (nesta seção) |
| **Baixa/aditivo preservam ato e vínculo** | **COMPROVADO** (nesta seção) |
| Reclassificação invalida e exige revisão | COMPROVADO |
| **Correção de observação pela tela** | **COMPROVADO** (nesta seção; lacuna de UI corrigida) |
| Rejeição de observação pela tela (botão "Rejeitar") | Backend idêntico ao de correção; ação de UI não exercitada nesta rodada (mesmo componente, mesmo caminho) |
| Quatro confrontos de área | **Diferido para o Incremento 3** (decisão do André, 21/09) |

Decisão do André: registrar como **"seis provas de leitura fechadas"** o conjunto acima de
provas COMPROVADAS sobre o conteúdo real dos documentos — a contagem e o agrupamento exatos
são dele; esta tabela é o detalhe linha a linha por trás do rótulo.

---

## 22/09/2026 — reextração autorizada em produção (#23 e #25): a cadeia não extraiu

**Autorização:** André, após conferir o primeiro dump de pré-deploy
(`predeploy/20260922T192516Z_…_072ge001.dump`, 107 MB). Uma rodada, casos #23 e
#25, tenant 1, extrator no `gpt-5.6-luna` (fallback Gemini 3.7 Flash ligado, que
é a configuração operacional). Ambiente conferido antes do disparo: host do
Supabase, `ENVIRONMENT=production`.

### O que a rodada produziu

| Etapa | Resultado medido (`supabase-prod-ro`) |
|---|---|
| OCR | 10 documentos, `completed` — 8 por `pypdf`, 2 por `gemini/gemini-2.5-flash`, US$ 0,0087 |
| `documento_versao` | 10 versões de texto criadas |
| Extrator (1ª tentativa, via `ocr_then_extract` com `force`) | **nada**: zero execução, zero job, zero staging novo |
| Extrator (2ª tentativa, despacho por caso) | 2 execuções persistidas, ambas `capacidade_insuficiente`; 2 jobs `failed`, sem modelo, custo zero |
| `evidence_versions` | 142 linhas — **nenhuma é leitura do Luna** |

**As 142 não são prova.** São `method = "staging"`, sem modelo: projeção do
staging legado feita na captura de snapshot, mais `fonte_primaria` carimbando o
método de OCR e a derivação cartorária. Observação de leitura semântica em
produção continua em **zero**.

### Três buracos, todos mudos

1. **A cadeia perde o caso.** `_dispatch_extrator` enfileirava o extrator com
   `process_id=None`. `authorize` responde 404 "Caso não encontrado".
2. **O 404 sumia.** `_connected_task` devolvia `{"status": "failed"}` sem log:
   sem execução, sem `ai_job`, sem marca no documento. Dez OCRs gravados e
   nenhuma extração — e nada em lugar nenhum dizia isso.
3. **A imagem de produção não carrega a ontologia.** O `Dockerfile` copia
   `alembic`, `app`, `scripts` e `seed.py`; o `capability_manifest("extrator")`
   exige `docs/arquitetura/ONTOLOGIA_REGENTE_v1.md` e guarda o hash dele no
   manifesto do job. Sem o arquivo, `missing = [ontologia_entrada_semantica]` e
   o extrator morre **antes** de ler qualquer documento. As seis skills de
   família estavam presentes; só o vocabulário faltava. Prova: o manifesto
   gravado no `ai_jobs.result` do job 1532.

Os três foram corrigidos no PR do dia, com teste que fica vermelho sem o
conserto.

### Matrícula e CAR passam pela entrada semântica — a dúvida era outra

`executar_extracao` chama `extrair_documento` para **todo** documento com texto,
sem filtrar por família (`entrada_semantica.py`). O filtro por tipo contratual
que existe em `ficha01_extraction` é de outro ponto de entrada, o do staging
legado. Então não há roteamento por família a corrigir.

**Por qual caminho o dev gerou as observações da ELODI:** tenant 34, processo 67
(“Caso real 23”), **247 observações** (`kind='observacao'`; 275 com fontes e
derivação, 6 documentos). Vieram do caminho do agente com o caso — há
`agent_executions` persistidas dos processos 67 e 68, ambas `completed`, e os
`ai_jobs` correspondentes (`job_type=extract_document`, `model_used=gpt-5.6-luna`,
`entity=process:67`, contexto do caso no payload). Mesmo código de serviço que a
tela aciona; o gesto veio do servidor do gate de dev, pela API autenticada — não
é escrita direta no banco.

### Estado do gate

- **Dev:** inalterado. As provas fechadas em 21/09 seguem válidas.
- **Produção:** **aberto.** Nenhuma prova de leitura foi verificada lá. O que se
  provou hoje é o contrário: a cadeia não chega ao extrator. Verificar em
  produção exige o deploy do conserto e **nova rodada** — que precisa de
  autorização própria do André, por operação.

Dívida **#268** aberta com esta medição (nasceu #260; renumerada por colisão com a
faixa #260–#267 da frente 4a).

---

## 23/09/2026 — leitura semântica em produção: cinco provas fechadas

Segunda rodada autorizada pelo André, depois de #204 (cadeia entrega o caso;
falha de agente vira log), #205 (a ontologia entra na imagem — o `.dockerignore`
excluía `docs` e o build do #204 tinha falhado) e #206 (o CI constrói a imagem e
pergunta a ela se serve). Portão conferido no Shell antes do disparo:
`capability_manifest("extrator")` = `available`, seis skills, hash da ontologia.

### O que a rodada produziu

| | #23 (ELODI) | #25 (Jobson) |
|---|---|---|
| Execução persistida | `failed` | **`completed`** |
| `ai_job` | 1533 | 1534 |
| `model_used` | `gpt-5.6-luna` | `gpt-5.6-luna` |
| Tokens (in/out) | 94.075 / 12.448 | 35.995 / 13.682 |
| Custo | US$ 0,0343 | US$ 0,0254 |
| Documentos lidos | 2 de 6 | 4 de 5 |
| Observações `extrator_semantico` | 60 | 45 |

**Por que o #23 falhou:** timeout de provedor, **não** tempo de tarefa (não houve
`SoftTimeLimitExceeded`; com `--pool=solo` o soft limit nem se aplica, e a tarefa
rodou 654 s até terminar sozinha). O Luna respondeu cinco chamadas, passou a dar
`APITimeoutError`, o gateway caiu no fallback Gemini 3.7 Flash, que voltou
**truncado** (11.996 de 12.000 tokens), repetiu com `max_tokens=24000` e deu
timeout de conexão três vezes: "Todos os providers falharam". O documento que
derruba é a matrícula de 82.117 caracteres (doc 547). Dívida **#271**.

### Âncoras — a conferência que a tela faz

**105 observações, todas ancoradas.** Cada uma com `fragmento_id` e
`documento_versao_id` igual à **versão corrente** do documento; zero sem versão,
zero órfã. A extração também gravou derivações `validacao_ancoras` com reparos e
rejeições nomeadas.

| Caso | Documento | Espécie | Observações | Versão ancorada = corrente |
|---|---|---|---|---|
| 23 | 546 | CAR | 13 | sim (1) |
| 23 | 547 | matrícula | 47 | sim (2) |
| 25 | 557 | CPF cadastral | 8 | sim (7) |
| 25 | 558 | contrato | 15 | sim (8) |
| 25 | 559 | escritura | 14 | sim (9) |
| 25 | 561 | RG/CPF | 8 | sim (10) |

### As seis provas, contra conteúdo real de produção

| Prova | Estado em produção | Evidência |
|---|---|---|
| Escritura não prova estado atual | **COMPROVADA** | doc 559, `posse_declarada_pelos_outorgantes` ancorada em "me foi dito que são senhores e legítimos possuidores"; `knowledge_state = nao_determinado` |
| Transmitente não vira cliente nem titular | **COMPROVADA** | clientes seguem ELODI AGROPECUÁRIA (#23) e Jobson (#25); IVAIR (pessoa 19) e ELDA (20) entraram como `pessoa` com papel `transmitente` |
| PJ preserva CNPJ | **COMPROVADA** | pessoa 18 (ISIS TERRA…ME, `pj`) com CNPJ 59.508.731/0001-95; ELODI com 29.091.958/0001-17 |
| Falecimento, espólio, inventariante, referência a processo | **COMPROVADA** | "TITULAR FALECIDO" (doc 557); 1 `espolio`; inventariante MÁRCIO ANTONIO NUNES com trecho de fundamento (doc 558); inventário 5286960-36.2022.8.09.0051 como **observação própria** |
| Inventariante confirmado só com fundamento | **COMPROVADA** | os 16 `pessoa_identificador` estão `declarado`; nenhum promovido a `confirmado` |
| Quatro matrículas independentes | **PENDENTE** | o #23 leu CAR + 1ª matrícula; faltam docs 548, 549 e 550. Rodada por documento autorizada para fechar |

Gate de família funcionando em produção: duas observações **rejeitadas com
motivo** — "Objeto contratual não sustentado pela espécie documental" e
"Referência a processo fora da família contratual".

### Estado do gate

- **Dev:** inalterado; provas de 21/09 válidas.
- **Produção:** **cinco provas fechadas.** A das quatro matrículas fica pendente
  até a rodada por documento do #23. As 142 linhas da tentativa anterior seguem
  sendo projeção do staging legado (`method="staging"`), nunca leitura — o filtro
  que separa uma da outra é `content->'attributes'->>'method'`.
- Dívidas abertas nesta medição: **#270** (CPF não normalizado duplica pessoa) e
  **#271** (matrícula grande em chamada única derruba a extração).
