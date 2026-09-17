# Contraprova das avaliações do Regente Ambiental

Data: 17/09/2026. Repositório: prosperidade/amigao.
Base conferida: `d2a3de0070a456acb9095d063164135ae26cbe06`, main com PR #170.
Branch de correção: `fix/contraprova-jobson-20260917`.

## Resultado

A segunda avaliação tem fundamento técnico. Reproduzi seis classes de problema com entradas sintéticas no código atual e preparei correções. Isso não equivale a reproduzir o caso real #25 nem a liberar o MVP. A primeira remediação existe, mas não resolve todas as exigências da segunda avaliação.

A API pública respondeu `GET /health` com HTTP 200 e `{"status":"ok","version":"0.1.0","service":"api"}` nesta sessão. O serviço está acessível; esse retorno não identifica o commit publicado, não testa o worker e não comprova a qualidade do fluxo.

**Não houve alteração de banco, merge ou deploy.** A branch não tem migration. O lançamento continua bloqueado por funções e validações descritas abaixo.

## Insumos e alcance da prova

Foram lidos integralmente os textos e tabelas dos dois DOCX anexados: especificação inicial v0.1 e segunda verificação Jobson de 17/09. As figuras não foram usadas para alegar reprodução independente. Também foram conferidos CLAUDE.md, código atual, documentação das remediações, ADR-011, ADR-007, governança de IA e testes relacionados.

Os PDFs originais e o KMZ do caso Jobson não foram fornecidos nesta sessão. Não houve acesso autenticado ao caso #25, ao corpus normativo ou ao banco de produção. Assim, corrupção do e-mail concreto, classificação dos documentos concretos, precisão do OCR e mistura dos cartões normativos permanecem **observações da avaliação**, não execuções reproduzidas aqui.

As referências de linha abaixo apontam à main `d2a3de0`, salvo indicação de arquivo novo ou alteração desta branch. Não se deve comparar seus números com o antigo commit `4a96b5d`.

## Contraprovas executadas

O mesmo arquivo novo `tests/services/test_contraprova_jobson.py` foi executado numa worktree isolada da main original e na branch corrigida. Sem banco e sem chamadas a modelos reais; colaboradores de agente são simulados quando necessário.

| Prova | Main original | Branch corrigida | Alcance |
|---|---|---|---|
| SIGEF ausente em contexto CAR | Crítico; destino diagnóstico e orçamento | Atenção; verificar aplicabilidade; destino alertas | AUD-002; contenção parcial de DIAG-003/004 |
| Denominação com uma fonte | Consistente | Fonte única, aguardando confronto | AUD-005 |
| Matriz com pendência e findings vazios | Resumo declara zero divergências | Resumo conta os pontos da própria matriz | AUD-001 |
| E-mails `a@`, `a@@example.com`, `a b@example.com` | Aceitos no schema do intake | Rejeitados antes da persistência | ENTR-001, validação apenas |
| Objetivo CAR com classificação pendente | Legislação recebe `nao_identificado` | Pesquisa usa `car`, sem promover classificação oficial | ENTR-004 / LEG-001, parcial |

**Antes: 8 falhas e 6 aprovações nos 14 testes novos. Depois: 14 aprovações.** Três das oito falhas são variações de e-mail. Os controles preservam e-mail válido, classificação oficial já definida e confronto entre duas fontes.

A seleção final com matriz, caso São Jorge, observações registrais e infraestrutura de skills teve **112 testes aprovados**. Um teste de tela confirma que até um resultado histórico com resumo contraditório é apresentado a partir das linhas da matriz. O build real `tsc -b && vite build`, Ruff nos arquivos alterados e `git diff --check` passaram.

Uma tentativa mais ampla teve **27 erros de preparação** nos testes de reconciliação que exigem Docker/PostgreSQL, ausente neste ambiente. Não são 27 defeitos comprovados do produto e não foram convertidos em testes aprovados. As três falhas adicionais daquela primeira execução foram resolvidas: dois patches incorretos no teste novo e uma expectativa antiga de consistência por fonte única. A suíte completa e o percurso autenticado não estão certificados por essa seleção.

## Primeira avaliação versus remediação atual

| Requisito | Contraprova da main atual | Situação e próxima solução |
|---|---|---|
| SAVE-001 | `staging_consolidation.py:659` implementa consolidação; `:1421` registra falha. A Frente L declara limite do replay em `docs/trabalhos/pos_reteste_l.md:305`. | Existe implementação; falta comprovar upload → decisão → gravação → nova sessão com os casos reais. Não repetir a conclusão antiga de função ausente. |
| DATA-001 | `schemas/client.py:61` expõe razão social; `api/v1/intake.py:157` transmite nome, documento e e-mail ao Client. | Remediado estruturalmente; leitura de banco/tela ainda necessária para aceitar o caso. |
| ENT-001 | `models/client.py:89`, `models/client_representative.py:47` e `staging_consolidation.py:1485` separam representante de PJ. | A ausência de entidade da auditoria antiga foi superada. Testar também documento pessoal sem vínculo previamente definido. |
| ENT-002 | Índice único normalizado em `models/client.py:75`; busca por tenant em `services/identity.py:55`; guard no intake `api/v1/intake.py:140`. | Proteção existe. Confirmar migration aplicada e situação dos duplicados antigos; não fundir dados automaticamente. |
| DIAG-001 | O classificador inicial já distingue rótulo declarado de conclusão (`intake_classifier.py:15`, `:56`, `:404`). O diagnóstico posterior ainda transforma findings em riscos (`agents/diagnostico.py:1421`). | Correção inicial não fecha a exigência ampliada do segundo relatório. Exigir evidência/aplicabilidade por conclusão. |
| OCR-001 | `area_registral.py:94` e `inconsistency_matrix.py:257` tratam a notação hectares/ares/centiares. | `926,36.54` não deve ser chamado automaticamente de erro de OCR. A normalização existe; falta OCR dos originais nesta sessão. |
| OCR-002 | `observacao_registral.py:318` estrutura atributos de atos; `staging_consolidation.py:379` contém decisão/edição. | Parcial. Não extrapolar cobertura de atos de matrícula para escritura e todos os documentos. |
| HIST-001 | `observacao_registral.py:442`, `:587` e `:712` aplicam alterações, vigência e adquirentes. | Temporalidade existe para atos estruturados. Falta demonstrar domínio semântico na escritura real de Jobson. |
| REC-001 | `reconciliation_decisions.py:958` agrupa evidências por chave natural. | Função existente. Não foi repetida a prova com banco ou os documentos reais nesta sessão. |
| DATA-002 | `reconciliation_decisions.py:853` calcula área total; `:903` trata RL. | Não é ausência total de modelo. KMZ continua sem parser; fonte gráfica não pode ser inventada. |
| CONF-001 | `reconciliation_decisions.py:245` e `:958` sustentam decisões agrupadas. | A segunda avaliação declara explicitamente que a nova Conferência não foi retestada. Aceite permanece aberto. |
| CONF-002 / DOC-001 | `document_lifecycle.py:46` distingue vários estados positivos/negativos, mas não declaração de não posse. | Parcial. Adicionar declaração com autor/justificativa, separada de dispensa; preservar estados existentes. |
| STATE-001 | `process_indicators.py:83` unifica progresso da conferência; `MacroetapaSidePanel.tsx:363` ainda apresenta checklist de etapa. | Unificação parcial não comprova coerência de todas as superfícies. A retirada do checklist no MVP é uma decisão de interface; não deve remover gates de evidência do backend. |
| REV-001 | `artifact_staleness.py:178` detecta desatualização; `api/v1/proposals.py:428` impede aceite de proposta desatualizada. | Não está ausente. Aviso/bloqueio não equivalem ao retorno automático à E3 pedido pela spec. Formalizar a diferença e testar nova evidência. |
| ROUTE-001 | Dependência explícita do diagnóstico e das fontes; nova avaliação já registra evidência negativa parcial. | Continua sem aceite integral. Não liberar rota/proposta como aprovadas apenas porque a cadeia executou. |

A v0.1 tem inconsistência editorial: a matriz resume CONF-002 como reclassificação e a seção detalhada como estados documentais; também há DOC-001 na matriz. Esta contraprova considera ambos os sentidos sem apagar IDs. ROUTE-001 era próximo recorte, mas integra a promessa de MVP até contrato.

## Segunda avaliação e soluções

### Entrada e contexto

**ENTR-001:** confirmado que a validação de e-mail aceitava apenas presença de `@` (`schemas/intake.py:57`). Corrigido para validação sintática real sem consulta de entrega e preservando o valor válido, exceto espaços externos já removidos antes. Isso não prova nem explica sozinho a corrupção específica observada em Jobson; comparar payload, banco e resposta continua necessário.

**ENTR-002:** o canal é gravado em `Client.source_channel` (`api/v1/intake.py:164`) e convertido para `Process.intake_source` (`:237`). Valor não reconhecido vira `None` silenciosamente. Não foi demonstrado que o canal usado por Jobson era inválido. Solução: contrato tipado, rejeição de valor desconhecido e teste de recarga com o canal efetivamente escolhido.

**ENTR-003:** o CPF é transmitido na criação (`api/v1/intake.py:162`), mas o contexto geral do diagnóstico (`agents/diagnostico.py:355–405`) não inclui um bloco geral de pessoas. A leitura de cliente em `:574` pertence ao percurso de fatos de autos, não a todos os casos. Solução: contexto único de pessoas, papéis e documentos consumido por todos os agentes, sem inferir propriedade a partir do simples cadastro do contratante.

**ENTR-004:** `demand_type=nao_identificado` é intencional (`api/v1/intake.py:227`); `process_type` guarda a sugestão. A legislação só usava o primeiro (`agents/legislacao.py:117`) e retirava o filtro ao encontrar a sentinela (`:316`). A branch usa o objetivo disponível para pesquisa e acrescenta o relato à consulta. Não altera a classificação oficial e não garante a qualidade de todo o ranking.

### Leitura, papéis e geometria

**READ-001 a READ-006 / AUD-004:** há uma lacuna concreta: o prompt de matrícula começa com “matricula/escritura” (`services/document_extractor.py:32`), enquanto `ficha01_extraction.py:234` preserva qualquer tipo específico recebido. Isso permite tratamento compartilhado indevido, mas o caminho exato da escritura de Jobson depende do payload e do original. Solução: tipo próprio de escritura, campos de comprador/vendedor/data do ato e proibição de promover esse conteúdo a certidão atualizada. RG deve permanecer identificador da pessoa, não “registro” genérico. Ausência de extração deve ser explícita por campo central.

Não criar essa distinção só no rótulo da tela: classificação, schema de extração, staging, consolidação, conferência e contexto precisam consumir o mesmo significado. READ-003/004/005/006 não foram fechados pelo PR.

**ENT-INV-001 / READ-007:** `inventariante` já aparece no vocabulário (`models/client_representative.py:37`), mas isso não fornece por si só espólio, falecimento, termo judicial e validade. O relatório está correto quanto à limitação operacional; seria incorreto dizer que nem a palavra/papel existe no modelo. Solução incremental: ampliar o vínculo já existente com fundamento e vigência, sem transformar o inventariante em proprietário.

**AUD-003:** `services/geo_files.py:12` declara que só detecta e roteia KML/KMZ; não calcula geometria. Solução: parser com limites de arquivo e validação de polígono/CRS, área geodésica ou projeção adequada, método registrado e comparação determinística. Os ~2,7250 ha são controle do documento recebido, não área recalculada aqui. Com números arredondados 2,7250 − 2,6893 resulta 357 m²; 356,8 m² pode vir das coordenadas não arredondadas. O aceite precisa usar o KMZ, não exigir igualdade artificial com valores arredondados.

### Auditoria e diagnóstico

**AUD-001:** confirmado e corrigido. `agents/auditor_imovel.py:100` contava findings; a matriz era outro conjunto. `AgentResultRenderer.tsx:375` ainda exibia ausência de divergência quando esse primeiro conjunto estava vazio. Agora resumo e número de pontos da matriz derivam das mesmas linhas; achados das outras regras permanecem explicitamente separados, sem soma que duplicaria ocorrências.

**AUD-002:** confirmado e contido. `inconsistency_matrix.py:955` convertia ausência de certificação em crítico e `_destino` (`:164`) encaminhava para orçamento. Agora pede aplicabilidade e não encaminha automaticamente a serviço. Isso não é implementação de todas as regras jurídicas do SIGEF.

**AUD-005:** confirmado e corrigido para denominação. Uma fonte deixa de ganhar selo de confronto consistente; tampouco vira falsa divergência no emissor de findings. **AUD-006/007:** ainda exigem classes de fato/lacuna/risco e leitura da cadeia dominial/RL. **AUD-008:** falta revisão completa por item. **AUD-009:** a tela passa a identificar regras determinísticas; versão específica de regras continua pendente.

**DIAG-001 a DIAG-009:** a crítica central é sustentada pelo código. `_consume_auditor_findings` (`agents/diagnostico.py:1421`) converte grau em risco; `evidencia` é texto opcional (`schemas/stage_output.py:225`). Uma string com nome de agente não comprova fonte primária. A branch contém uma origem de risco indevido, mas não estabelece o gate completo.

Solução: conservar evidência primária estruturada, espécie do achado e aplicabilidade; impedir promoção a risco/serviço sem os campos exigidos. “Não localizado nos documentos” não pode virar prova de ausência de embargo. Testar negativos sem documento, documento de terceiro, documento histórico e fonte divergente; testar positivo com evidência suficiente para não bloquear conclusões legítimas. Falecimento/RL/KMZ precisam entrar antes pelo contexto. Aprovação humana final já existente não deve ser confundida com aprovação por conclusão.

### Fundamentação normativa

**LEG-001:** corrigida parcialmente a perda do objetivo. **LEG-002:** os fallbacks da busca (`agents/legislacao.py:351`) relaxam demanda/UF; recuperar um trecho não prova pertinência. Solução: candidatos ampliados não entram como fundamento até comprovar tema, competência, território, vigência e ligação factual.

**LEG-003/004/005:** o modelo emite a lista normativa e o resultado conserva metadados dos chunks separadamente (`agents/legislacao.py:252`); a existência desses metadados não demonstra ligação íntegra de cada cartão/conclusão. A mistura concreta relatada não foi reproduzida sem corpus e resultado do job. Solução: identificar cada citação por chunk/dispositivo e montar título, número, órgão, trecho e URL na aplicação a partir desse registro; rejeitar associações que não correspondam à fonte. Exigir fato → norma → consequência e declarar insuficiência.

**LEG-006/007:** revisão por fundamento e apresentação precisam ser completadas. Não se trata de reescrever o texto jurídico para parecer melhor. A validade atual das normas listadas pela avaliação não foi objeto de parecer jurídico nesta contraprova; devem ser conferidas nas fontes oficiais durante curadoria do corpus.

### Revisão e estados

**REVIEW-001 / AUD-008 / LEG-006 / DIAG-009:** o ADR-011 deliberadamente deixa insumos não revisados seguirem (`agents/orchestrator.py:52`, `:56`, `:168`, `:187`). O pedido novo é diferente da decisão antiga. Solução: atualizar explicitamente a decisão arquitetural e implementar revisão por item com autor, versão, justificativa, correção e rejeição; somente a versão permitida pode seguir. Não basta remover uma exceção do orquestrador: sem persistência e retomada, isso paralisa a cadeia sem dar ao consultor um caminho utilizável.

**STATE-001 / DOC-001 / CONF-001/002 / REV-001:** manter os mecanismos existentes, completar estados e executar a Conferência real antes de declarar reprovação ou aceite. O segundo relatório a deixou para a próxima fase. Não atribuir às remediações recentes uma falha que só foi observada na leitura anterior à nova Conferência.

## Sistema agêntico e skills após a observação do André

O diagnóstico de sistema inacabado está correto, com uma distinção verificável: arquivos de skill, carregamento e execução são três coisas diferentes.

| Componente | Skill de domínio no repositório | Comportamento verificado |
|---|---|---|
| Diagnóstico | `situacao_ambiental_imovel_rural`, v1.1.0 | Exige `metadata.uf` GO/MS/MT; é injetada por `BaseAgent.call_llm`. |
| Auditoria | `analise_divergencias_documentais`, v1.2.0 | Há especificação, mas o agente é determinístico e não chama `call_llm`; o texto não executa as regras por si. |
| Extrator | Apenas `_template` | Não aplica ao caso CAR. O extrator delega chamadas a serviços, fora da injeção automática de `BaseAgent.call_llm`. |
| Legislação | Nenhuma skill própria descoberta | Tem prompts e RAG; não equivale a agente sem instrução, mas falta a camada procedural específica. |
| Redator | Apenas `_template` | Não aplica ao caso CAR. Falta skill de domínio, embora existam prompts. |
| Orçamento | Nenhuma skill própria descoberta | Não extrapolar qualidade de execução para maturidade do conteúdo. |

Inventário executado pelo registry com contexto `uf=GO, demand_type=car, doc_type=car`: só Auditoria e Diagnóstico deram match. Fontes: `app/skills/`, `app/skills/_registry.py:232`, `app/agents/base.py:294`, `app/agents/extrator.py:209`, `app/services/document_extractor.py:201` e `app/agents/auditor_imovel.py:54`.

**Contraprova adicional:** a API síncrona deriva UF (`app/api/v1/agents.py:44–80`), mas os endpoints assíncronos passam os metadados recebidos (`:197`, `:227`) e os workers os usam diretamente (`app/workers/agent_tasks.py:109`, `:186`). Com metadados vazios, o Diagnóstico podia rodar sem sua skill mesmo tendo imóvel GO. Reproduzido com o agente real e colaboradores simulados; o teste falha na main original. A branch deriva a UF do imóvel já carregado antes de selecionar a skill, sem sobrescrever UF explícita nem inventar uma quando o imóvel não a informa.

A correção torna a skill disponível nesse caminho; não prova que ela foi omitida no job original #25 e não prova qualidade jurídica das respostas. O texto da skill de diagnóstico já orienta registrar lacuna e não afirmar certeza sem verificação externa (`SKILL.md:41`); portanto, completar skills é necessário, mas o contrato de evidência também precisa ser aplicado por código.

Concordância com Fable: informação achatada e insumos não verificados podem amplificar erros; KMZ e resumo não são resolvidos por prompt. Ressalvas: não é comprovado que falta de skill explique LEG-001 a 005 quase integralmente; já há revisão de diagnóstico/artefatos, embora não o gate por conclusão solicitado; skill excelente não torna o sistema necessariamente pior, mas fluência não fornece evidência.

O Docker ligado pelo André no Windows foi considerado. Nova conferência neste runtime não encontrou executável Docker nem `/var/run/docker.sock`. Não há ligação automática ao Docker Desktop remoto; não solicitar exposição pública do daemon. O caminho é CI do projeto ou execução local no repositório do Windows.

## Ordem para liberar o MVP

| Ordem | Entrega | Evidência de saída | Esforço relativo |
|---|---|---|---|
| 1 | Revisar e integrar as contenções deste PR | CI e regressões novas; nenhuma migration necessária | Pequeno |
| 2 | Contexto de entrada, semântica de documento/pessoa e carregamento das skills | Jobson, PF simples, PJ+representante e espólio preservam dados após recarga | Médio a grande |
| 3 | Geometria e confronto de fontes | KMZ real calculado; fontes e tolerância explícitas; nenhuma ausência vira obrigação | Médio |
| 4 | Skills procedurais, citações íntegras e diagnóstico rastreável | Positivos e negativos com documento/trecho/dispositivo; conclusão sem suporte barrada | Grande |
| 5 | Revisão persistida e consumo somente da versão permitida | Corrigir/rejeitar, recarregar, retomar cadeia e comprovar que a rejeitada não alimenta proposta | Grande |
| 6 | Conferência → base → diagnóstico → rota → proposta → contrato | Percurso autenticado completo nos três casos, nova sessão e nova evidência | Médio após as anteriores |

As ordens 2 e 3 podem avançar sem reescrever a arquitetura. A ordem 5 deve definir o contrato de revisão antes de concluir o consumo da ordem 4. Esforço relativo não é promessa de dias: falta executar os documentos e medir o corpus.

## Bloqueios de acesso e aceite

1. Falta cópia dos cinco arquivos originais de Jobson ou acesso autenticado ao ambiente de homologação que contém o caso #25, com os resultados dos jobs. Os dois relatórios não substituem esses arquivos.
2. Este ambiente não dispõe do Docker/banco de desenvolvimento autorizado pelo CLAUDE.md. A CI existente tem PostgreSQL; o PR permite verificar essa parte sem apontar para produção.
3. Não há acesso de operação a Render/Netlify/Supabase/R2 nesta sessão. A consulta pública de saúde não supre esses acessos nem permite conferir a versão implantada.
4. O CLAUDE.md exige autorização explícita para merge na main; a main aciona deploy automático em `render.yaml:35`. O PR é entregável revisável, não autorização implícita para publicar uma versão ainda sem aceite.

**Decisão recomendada:** manter o ambiente para validação. Não liberar o MVP para decisão de risco, rota ou contratação com base nesta contraprova parcial. Não houve aceite dos P0 ainda abertos, nem recomendação de reconstrução total do sistema.
