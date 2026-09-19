# Incremento 2 — estado do gate

18/09/2026 · branch `feat/entrada-semantica-cartorario` · implementação em andamento.
**Gate aberto. Associação autenticada comprovada; extração LLM e persistência semântica ainda não comprovadas.**

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
