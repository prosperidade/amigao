# PLANO DIRETOR — REGENTE AMBIENTAL

**Versão 1.1 · 17/09/2026 · Documento único de planejamento**

Este documento **centraliza o planejamento e referencia os ADRs** — não os revoga.
Substitui o planejamento disperso em prompts e relatórios.
É o caminho completo: o que existe, o que está quebrado, o que se constrói, em
que ordem, com que prova, e o que entra no banco de dados.

**Base:** main `d2a3de0` · mergulho estrutural de 17/09 · spec v0.1 e segunda
validação da Ísis · cinco auditorias independentes · catálogo de insumos.

---

## SUMÁRIO

1. O que o sistema é e onde ele quebrou
2. Arquitetura-alvo — visão única
3. Os quatro contratos que fecham a arquitetura
4. Os seis agentes e os dois motores
5. Máquina de estados determinística
6. Modelo de dados
7. O acervo: documentos que entram no banco
8. Os oito incrementos — ordem, escopo, prova
9. Remediações e dívidas
10. Governança de execução
11. Matriz de aceite final

---

## 1. O QUE O SISTEMA É E ONDE ELE QUEBROU

### 1.1 O produto

SaaS para consultorias ambientais brasileiras. O consultor sobe documentos de um
imóvel rural, o sistema lê, confronta, fundamenta, diagnostica, define a rota de
regularização, redige as peças e precifica o serviço. **A IA propõe; o humano
decide e assina.** O radar não cancela: o sistema não impede o consultor de
seguir, impede-o de fingir que não viu.

### 1.2 O diagnóstico, sem rodeios

O sistema tem serviços de domínio corretos e **não tem uma cadeia decisória com
contrato comum de evidência**. Onze agentes registrados, quatro chamam LLM no
caminho previsto. Quatro skills: duas são esqueleto de 17 linhas; das duas reais,
a do auditor não entra (o agente não usa LLM) e a do diagnóstico exige `uf` que
nenhuma porta da tela envia.

Cinco rupturas estruturais, todas confirmadas em código:

| # | Ruptura | Consequência |
|---|---|---|
| 1 | A chain passa o **dict inteiro** do agente anterior | Sem fonte, sem tempo, sem distinção entre fato e opinião |
| 2 | O auditor procura campos no primeiro nível; o extrator entrega dentro de `extracted_fields` | 3 dos 4 confrontos de área nunca recebem os dois lados |
| 3 | O extrator produz **duas extrações**: preview achatado (primeiro valor vence) e staging rico | Duas verdades; a segunda fonte some por ordem de documento |
| 4 | `gerar_proposta = [diagnostico, orcamento]`, diagnóstico sempre `requires_review=True`, `stop_on_review=True` | **O orçamento nunca é alcançado.** A cadeia comercial está quebrada por construção |
| 5 | Não existe leitura de polígono. `Property.geom` nunca gravado, KMZ guardado sem abrir | Um sistema de regularização ambiental que não processa geometria |

E o efeito que a Ísis nomeou na segunda validação: **as saídas dos agentes viram
fonte umas das outras** — circuito de autoconfirmação. Leitura achatada → auditoria
contraditória → legislação sem contexto → diagnóstico transformando ausência em
risco alto, urgência e recomendação comercial.

### 1.3 Por que seis meses não produziram MVP

Cada frente foi rigorosa dentro do escopo, e o escopo sempre veio do último
relato. Corrigimos gravação, tipo, vigência, reconciliação, estado — tudo medido,
tudo com gate. A auditoria de agosto já documentava a circulação entre agentes e
suas exceções; **o que nunca foi fechado foram os contratos entre camadas**, e
nenhum aceite exigiu o percurso real. Isso muda a partir deste documento: o
critério de aceite passa a vir da spec e do percurso autenticado, não do escopo do
prompt.

### 1.4 O que se preserva

Não é reconstrução. O patrimônio é grande e fica:

observações registrais tipadas (ADR-065) · vigência derivada por regra (ADR-066) ·
âncora de valor no texto (#152) · reconciliação agrupada e mesa de decisões
(ADR-067) · consolidação humana com `consolidated_at` · fonte única registral
(ADR-062) · identidade PF/PJ e representante (ADR-063) · estado único e
invalidação (ADR-068) · diagnósticos versionados · decisões por processo (ADR-012) ·
Rota · proposta e contrato determinísticos (ADR-028/029) · catálogo normativo com
proveniência · corpus de 32 mil chunks · multi-tenant fechado · auditoria com hash
chain.

---

## 2. ARQUITETURA-ALVO — VISÃO ÚNICA

```
                    ┌──────────────────────────────────────┐
                    │   REPOSITÓRIO DE EVIDÊNCIAS          │
                    │   fonte · observação · derivação ·   │
                    │   conclusão · revisão · linhagem     │
                    └──────────────────────────────────────┘
                         ▲         ▲         ▲         ▲
                         │         │         │         │
   documento ──► EXTRATOR ──► AUDITOR ──► LEGISLAÇÃO ──► DIAGNÓSTICO
                    │            ▲            ▲              │
                    │            │            │              ▼
              ┌─────▼─────┐  ┌───┴────┐  ┌────┴─────┐      ROTA
              │ GEOESPA-  │  │ MOTOR  │  │  MOTOR   │    (validada
              │  CIAL     │  │CARTORÁ-│  │ JURÍDICO │   pelo humano)
              │(determin.)│  │  RIO   │  │(325 regras)     │
              └───────────┘  └────────┘  └──────────┘      ▼
                                                        REDATOR
                                                     (peça técnica)
                                                           │
                                                           ▼
                                                       ORÇAMENTO
                                                           │
                                                           ▼
                                              PROPOSTA → CONTRATO
                                              (geradores determinísticos)
```

**As setas significam acesso à próxima versão autorizada, não repasse de dict.**
Documentos e observações primárias permanecem acessíveis a cada etapa — a cadeia
não depende da interpretação do anterior como única janela para a fonte.

**Entre cada seta existe um gate de revisão** — na montagem do contexto seguinte,
não no fim do agente anterior.

### 2.1 Princípios de arquitetura

1. **Uma saída de agente não é evidência primária.** (regra da Ísis, literal)
2. **Desconhecimento e falha nunca viram ausência ou regularidade.**
3. **Cálculo e regra são determinísticos; julgamento é LLM; decisão é humana.**
4. **Toda conclusão aponta para premissas recuperáveis.**
5. **Reexecução não desfaz decisão humana nem duplica efeito.**
6. **Resumo e lista derivam da mesma coleção tipada.**
7. **Escopo e preço não nascem de risco não comprovado.**

---

## 3. OS QUATRO CONTRATOS QUE FECHAM A ARQUITETURA

### 3.1 Contrato de evidência

Quatro objetos lógicos, com identidade e versão próprias:

| Objeto | O que é | O que não pode |
|---|---|---|
| **Fonte primária** | Documento original ou registro de consulta identificável | Um AIJob ser apresentado como documento comprobatório |
| **Observação** | O que a fonte declara, extraído com âncora | Virar fato sem premissas adicionais |
| **Derivação determinística** | Cálculo ou regra com entradas referenciadas e versão do método | Apagar as entradas ou fingir fonte independente |
| **Conclusão** | Interpretação sustentada por observações, derivações e normas | Ser promovida a fato por ter vindo de outro agente |

**Campos mínimos de observação:** identidade (id, versão, tenant, caso, objeto,
tipo de origem) · documento (versão, hash do original e do texto, classificação
revisável, emissor, data) · localização (página, trecho, posição, feição; ou
"desconhecida" explícita) · significado (predicado tipado, valor literal,
normalizado, unidade, sujeito, objeto) · pessoa e papel · tempo (data do
documento, do ato, eficácia, referência da análise, vigência derivada) ·
qualidade (método, cobertura, âncora, certeza, revisão) · linhagem.

**Campos mínimos de conclusão:** id, versão, classe (`fato_documental`,
`divergencia`, `lacuna`, `hipotese`, `risco`, `orientacao`, `escopo_proposto`),
texto, premissas por id, normas e regras por versão, aplicabilidade e
justificativa, certeza, impacto, urgência com fundamento temporal, limites,
revisão, autor, dependências, versão substituída.

**Regras duras:** risco exige fato e teste de aplicabilidade. Serviço proposto
exige finalidade e decisão de escopo. Lacuna justifica atividade de verificação,
não comprova irregularidade.

### 3.2 Contrato de conhecimento

| Estado | Requisito | Redação |
|---|---|---|
| `nao_determinado` | dados insuficientes ou conflito não resolvido | "A titularidade atual não foi determinada pelos documentos disponíveis." |
| `nao_localizado_no_material` | escopo e cobertura declarados | "Não foi localizada referência a embargo nestes documentos." |
| `ausencia_verificada_no_escopo` | consulta feita, identificadores, data, resposta preservada | "A consulta X, em Y, para Z, não retornou registro." |
| `nao_aplicavel` | aplicabilidade avaliada, ou decisão profissional com fundamento | "Não se aplica ao ato avaliado, pelas condições registradas." |
| `conflitante` | fontes ou regras incompatíveis | "Há duas declarações incompatíveis; requer decisão." |
| `falha_de_verificacao` | consulta, storage, OCR ou cálculo falhou | "A verificação não foi concluída por erro de leitura." |

Estados de **atendimento ao requisito** são outra dimensão: não apresentado,
declarou não possuir, dispensado, aguardando obtenção. Nenhum prova inexistência
do fato.

### 3.3 Contrato de execução (envelope)

Substitui o dict acumulado. Carrega: caso, tenant, objetivo canônico, data de
referência · snapshot dos documentos e observações autorizadas · derivações
reproduzíveis · conclusões aprovadas · lacunas e falhas explícitas · manifesto de
skills, regras e templates aplicados · tarefas não avaliáveis.

O agente acrescenta observações e conclusões identificadas. **Não devolve um novo
"estado verdadeiro do caso".**

### 3.4 Contrato de revisão

Revisa-se **a conclusão e sua versão**, não o job. Aprovar, corrigir, rejeitar,
marcar não aplicável — persistindo autor, justificativa, versão e premissas.
Corrigir cria nova versão; rejeitar não apaga observação nem documento.

**O gate fica na montagem do contexto seguinte.** Só conclusão aprovada e válida
entra como premissa. Observações e documentos continuam disponíveis com sua
qualificação. Execução posterior não pode recuperar "o último job completed" e
contornar a decisão.

**Revisão não transforma falsidade em verdade.** O consultor pode assumir uma
hipótese com ressalva; o sistema conserva esse estatuto. Não pode aprovar
"ausência verificada" sem registro de verificação, nem converter escritura em
certidão atual por aceite.

---

## 4. OS SEIS AGENTES E OS DOIS MOTORES

### 4.1 Responsabilidades

"Agente" é responsabilidade do fluxo, não obrigação de chamar LLM.

| Agente | Decide | Recebe | Produz | LLM? |
|---|---|---|---|---|
| **Extrator** | Propor classificação e observações; declarar ilegibilidade | Original, texto versionado, taxonomia, sujeitos candidatos, objetivo | Observações com âncora, papel, data, unidade, cobertura | Sim, por tipo documental |
| **Auditor** | Comparar fontes, executar confrontos, classificar fato/concordância/divergência/lacuna | Observações revisadas, objetos identificados, resultado cartorário e geométrico | Cálculos, pares comparados, regra e versão, lacunas, conclusões propostas | **Não.** Núcleo determinístico |
| **Legislação** | Selecionar fundamentos aplicáveis e explicar fato→norma→consequência | Objetivo canônico, UF/competência/datas, fatos autorizados, avaliação dos motores, corpus | Fundamentos por id de norma/dispositivo/versão; aplicabilidade, conflito ou insuficiência | Sim, sobre resultado do motor |
| **Diagnóstico** | Sintetizar situação, hipóteses, lacunas, riscos sustentados, próximos passos | Evidências e conclusões permitidas, avaliações jurídicas, limites de cobertura | Conclusões revisáveis com premissas; risco separado de certeza e urgência | Sim |
| **Redator** | Elaborar peça técnica e descrição de escopo fundamentado | Diagnóstico e rota aprovados, evidências citáveis, TR versionado | Rascunho com afirmações ligadas a fontes + checklist de atendimento ao TR | Sim |
| **Orçamento** | Propor esforço, preço e condições para escopo validado | Rota e itens aprovados, especificação do Redator, tabela comercial versionada | Itens com origem, quantidade, cálculo, faixa, premissas | Assistente; totais determinísticos |

**Correção de rota confirmada pelo mergulho:** o Redator **não** gera contrato. A
peça comercial oficial nasce de `proposal_generator` e `mirante_documents`, depois
do preço e do aceite (ADR-028/029). O Orçamento **não** é segunda fonte de escopo —
a Rota validada é a autoridade comercial; o agente sugere, o serviço calcula e
persiste.

**O Redator produz coisas diferentes antes e depois da contratação** — e a
distinção evita executar o serviço antes de vendê-lo:

| Momento | O que o Redator produz | Alimenta |
|---|---|---|
| **Antes da contratação** | Relatório preliminar e **especificação do escopo** — o que será feito, com que fundamento, o que está fora | Orçamento e proposta |
| **Depois da contratação** | **Peça técnica definitiva** (laudo, memorial, requerimento, resposta a notificação), quando faz parte do serviço contratado | Entrega ao cliente e ao órgão |

O relatório preliminar cita evidências e declara lacunas; não é o produto
contratado. O checklist de TR aplica-se à peça definitiva.

### 4.2 Skills — o que cada uma é

| Agente | Skill de domínio | Estado hoje | Ação |
|---|---|---|---|
| Extrator | Como reconhecer documentos e atos, preservar ambiguidade, separar pessoas e áreas — **por tipo documental** | `_template` de 18 linhas | **Escrever.** Uma por família: registral, CAR/cadastral, pessoal, geoespacial, contratual |
| Auditor | Método de confronto vira **regra verificável**, não prompt | 228+66 linhas escritas, não ligadas (agente sem LLM) | **Traduzir em regras.** Não adicionar LLM para o arquivo "rodar" |
| Legislação | Ordem de pesquisa, competência, exceções, limites, tratamento de fonte | Não existe | **Escrever.** Consome o motor jurídico |
| Diagnóstico | Raciocínio da Ísis, ordem de perguntas, distinções, forma de explicar | 890 linhas, GO/MS/MT, **nunca carregada pela tela** | **Reconciliar semanticamente.** A H1 classifica "não sei se há GEO" como risco alto — contradiz a segunda validação. Normas concretas vão para o catálogo de regras; o método fica na skill |
| Redator | Método da peça e revisão + TR por tipo de peça e órgão | `_template` de 17 linhas | **Escrever.** Alimentada pelos 102 TRs |
| Orçamento | Dimensionar trabalho, explicitar exclusões | Não existe | **Escrever.** Totais permanecem determinísticos |

**Regra de carregamento (corrige a causa raiz do caso #25):** skill-base
obrigatória por responsabilidade; extensões por documento, objetivo, UF e estágio.
A seleção retorna **manifesto** — skills aplicadas, versões, anexos, skills
esperadas ausentes e motivo. Método obrigatório indisponível gera **capacidade
insuficiente visível**, nunca omissão silenciosa. UF desconhecida permite método
geral de coleta, jamais conclusão estadual disfarçada de cobertura nacional.

### 4.3 Motor cartorário

**Serviço determinístico de qualificação documental e estado registral segundo as
evidências disponíveis.** Não lê documentos por LLM nem garante realidade externa
por ausência de evento no material recebido.

**Entradas:** documentos classificados e revisados · identidade de serventia e
matrícula · atos com referência interna · pessoas e papéis · datas · alterações e
cancelamentos expressos · cobertura e data da certidão · objetivo e data de
referência · regras cartorárias homologadas.

**Operações:**

1. **Determinar o que cada espécie sustenta.** Escritura registra declarações e
   negócio; não recebe a autoridade da certidão atualizada. Contrato comercial não
   vira ato registral.
2. **Construir o grafo de atos** por referência explícita e identidade registral
   completa. `AV.10` sozinho não identifica; documento + matrícula + serventia
   delimitam o ato.
3. **Derivar situação** na data de referência: baixado, alterado, expirado,
   vigente-segundo-o-material, indeterminado — mantendo o evento e sua prova.
4. **Propor cadeia dominial e participações**, incluindo transmissão parcial,
   representação e sucessão. Nunca "último nome encontrado" como titular atual.
5. **Declarar o que falta:** certidão adequada, trecho legível, vínculo de
   aditivo, documento de representação, ato intermediário, fração ou objeto.

**Reuso:** `aplicar_alteracoes`, `derivar_vigencia`, `cadeia_titularidade`,
`titular_atual`, observações tipadas, linhagem de matrículas.
**Limites a corrigir:** vigência marcada por mera presença de `data_ato`;
`rl_vigente` não exclui indeterminado; `titular_atual` escolhe maior ordem entre
transferências sem provar completude da cadeia.

**Insumo:** matriz cartorária da Ísis (INS-003).

### 4.4 Motor jurídico

**Avaliador de regras versionadas, com aplicabilidade explícita e trilha
completa.** As 325 regras não viram 325 trechos de prompt nem 325 `if`.

**Cada regra declara:** identidade estável, versão, eixo, objetivo(s) · UF e
alcance territorial · competência e órgão · vigência e data de revisão ·
predicados de entrada tipados (existência, valor, unidade, papel, tempo, classe
documental, qualidade mínima da fonte, estado de revisão exigido) · condição
formal executável · resultado, mensagem, consequências permitidas · severidade
separada de certeza · necessidade de decisão profissional · fonte normativa por
chave **mais versão e dispositivo** · origem (planilha, aba, linha, hash) ·
autoria e homologação · exemplos positivos, negativos, incompletos, conflitantes
e de fronteira.

**Runtime:** linguagem restrita de condições e operadores conhecidos. Nunca
Python ou SQL arbitrário importado. Regra que exige conceito não representado é
recusada na publicação, com motivo. Nenhum LLM traduz e ativa regra sem
conferência humana.

**Estados de avaliação:** `aplicavel_disparou` · `aplicavel_nao_disparou` ·
`nao_aplicavel` · `indeterminado` · `conflito` · `erro_execucao`.
**Valor desconhecido é desconhecido, nunca falso.** O relatório lista também as
regras não avaliadas e as entradas faltantes. **"Zero regras disparadas" significa
isso, não regularidade.**

**Aplicabilidade precede consequência.** A seleção considera objetivo, território,
competência, ato e datas. Regra federal pode integrar caso estadual; UF do imóvel
não decide sozinha o órgão competente (ADR-034).

**Conflito de esferas:** o protocolo da Ísis (Constituição → competência privativa
da União → competência concorrente do art. 24 → contradição com norma geral) vira
**tabela de decisão homologada**, com pressupostos e referências. Proibido o
atalho "federal sempre ganha" ou "mais restritiva ganha". Indeterminado retorna
conflito para decisão profissional.

**Insumo:** as 325 regras (INS-001/002) + o protocolo da v03.

### 4.5 Serviço geoespacial

Determinístico, chamado pelo Extrator e pelo Auditor. **Hoje não existe.**

1. Receber arquivo como evidência, guardar hash e versão; inspecionar com limites
   de tamanho e descompressão. **KMZ exige abrir o KML interno** — não enviar
   bytes para o LLM adivinhar área.
2. Extrair feições, separar polígono de ponto e linha. Múltiplas feições sem
   vínculo claro ⇒ seleção pelo consultor. Preservar anéis, vazios e
   multipolígonos; não unir imóveis distintos.
3. Validar coordenadas, CRS, geometria e objeto. Correção gera derivação
   registrada, não troca silenciosa do original.
4. **Calcular área em método métrico adequado**, registrando CRS de origem,
   transformação, método, unidade e versão. Área em graus não é hectare. Usar
   PostGIS (já no stack).
5. Associar medição à feição, fonte, data e objeto. "Área do texto do CAR", "área
   calculada do KMZ" e "área registral" são coisas diferentes mesmo quando
   coincidem.
6. **Comparar objetos compatíveis** publicando áreas originais, delta absoluto,
   percentual **com denominador declarado** e tolerância com método.
7. Overlays com camadas identificadas, data e cobertura. Sem camada ⇒ **"não
   verificado"**, jamais "sem sobreposição".

**Caso de prova:** o KMZ de Jobson. 2,7250 ha calculado × 2,6893 ha documental =
~357 m², 1,33%. Declarar tolerância e denominador — o comparador atual usa o maior
valor como base; a Ísis usa a área documental. Os dois precisam ser identificados.

---

## 5. MÁQUINA DE ESTADOS DETERMINÍSTICA

### 5.1 Os cinco eixos de estado

O sistema hoje mistura eixos. O alvo separa, e cada tela nomeia qual mostra:

Um documento inexistente não pode ter estado de processamento. Por isso as
dimensões são independentes e combináveis, não uma lista única:

| Eixo | Estados | Quem decide |
|---|---|---|
| **Caso (macroetapa)** | E1 entrada · E2 base · E3 coleta · E4 diagnóstico · E5 rota · E6 proposta · E7 execução | Gate por etapa + consultor |
| **Documento** (o arquivo que existe) | recebido · processando · processado · falha_de_leitura · substituído | Sistema |
| **Requisito documental** (o que o caso precisa) | pendente · apresentado · declarou_não_possuir · dispensado · aguardando_obtenção | Consultor |
| **Observação** | proposta · revisada · aceita · rejeitada · corrigida · superseded | Consultor |
| **Conclusão — revisão** | proposta · aprovada · corrigida · rejeitada · não_aplicável | Consultor |
| **Conclusão — atualidade** | vigente · desatualizada | Sistema, por dependência |
| **Execução (chain)** | previsto · em_execução · concluído · pendente_de_revisão · falho | Sistema |

**Revisão e atualidade são eixos separados.** Uma conclusão aprovada que fica
desatualizada **conserva o registro da aprovação** — a atualidade muda, a decisão
humana não se perde. `retomado` é evento de execução, não estado: depois dele a
execução volta a executar ou a aguardar.

**Invariante:** resumo e lista derivam da mesma coleção tipada. Um percentual
único não representa sete perguntas diferentes.

### 5.2 Transições que são regra, não opinião

| Transição | Condição determinística |
|---|---|
| Documento → `lido` | Texto legível pelo mesmo critério do extrator. `ocr_status=done` com 444 chars de boilerplate **não é lido** |
| Observação → `aceita` | Decisão humana registrada com autor e data |
| Conclusão → `aprovada` | Decisão humana + premissas recuperáveis + (se risco) teste de aplicabilidade satisfeito |
| Conclusão → `desatualizada` | Dependência mudou de versão (documento novo, observação corrigida, regra republicada) |
| Caso E2 → E3 | Base consolidada com fonte única registral respeitada |
| Caso E4 → E5 | Diagnóstico aprovado, com lacunas declaradas |
| Caso E5 → E6 | Rota validada passo a passo |
| Caso E6 → E7 | Proposta aceita e contrato assinado |
| Proposta → `aceita` | **Bloqueado** se qualquer fundamento estiver desatualizado |

### 5.3 Evidência nova — decisão travada

Documento novo **não retrocede etapa automaticamente**. Ele:
1. marca como desatualizado tudo que dependia da versão anterior;
2. abre **pendência de coleta dependente**, visível;
3. oferece ao consultor o **gesto explícito** de voltar à etapa.

ADR-068 permanece; ganha o botão. Razão: retrocesso automático destrói trabalho
humano, e radar não cancela.

---

## 6. MODELO DE DADOS

### 6.1 O que existe e o que muda

| Dimensão | Hoje | Alvo |
|---|---|---|
| Documento | storage key, checksum, tipo, versão, origem, texto. CASCADE no processo | **Versão e fragmento como entidades.** Extração vinculada à versão exata, com página e posição. Retenção que não deixe dado "comprovado" órfão (#207) |
| Observação | `ExtractedFieldStaging`: documento, campo, valor, destino, tipo, atributos, decisão, `consolidated_at` | **Observação durável e independente de destino cadastral.** Um aditivo, uma baixa, uma consulta negativa importam sem preencher coluna. Staging vira projeção de "o que pode ser consolidado" |
| Afirmação | `Afirmacao`: schema de conteúdo com texto, categoria, fontes | **Conclusão identificável e versionada**, com revisão, premissas por id e dependências |
| Pessoa | `Client` (cadastro) + `ClientRepresentative` (CPF, papel, documento-fonte) + `proprietarios` JSON sem papel | **Identidade separada de participação.** A mesma pessoa é compradora num ato, vendedora em outro, representante no caso. Cada vínculo com documento, fundamento, objeto e intervalo |
| Espólio | Não existe | **Parte representada com vínculo ao falecido.** Não substitui CPF, não vira PJ. Inventariante exige documento, alcance e validade |
| Ato e temporalidade | Atributos + derivações + linhagem de matrícula | Referências **resolvíveis entre documentos e matrículas**; autoridade e completude da fonte |
| Geometria | Coluna `geom` SRID 4674 existe; upload só é reconhecido | **Arquivo geoespacial + feição + medição** como entidades, com CRS, método, versão. `Property.geom` vira projeção escolhida |
| Áreas | documental, gráfica, APP, RL numérica | **Medição por fonte, objeto e finalidade** antes de escolher o canônico |
| Regras | Catálogo de alertas + regras Python | **Regra + conjunto publicado + avaliação**, versionados, com origem nas matrizes |
| Revisão | Diagnóstico versionado, validação de artefato, `ProcessDecision`, `ProcessIssueDecision` | **Revisão de conclusão e de observação**, com dependências |
| Execução | AIJob com resultado, custo, modelo | **Snapshot, passos previstos/concluídos/pendentes/falhos, cursor, chave idempotente, manifesto de skills** |

### 6.2 Entidades novas

```
documento_versao      (documento, versão, hash, texto, páginas, ocr_meta)
fragmento             (documento_versao, página, posição, trecho)
observacao            (id, versão, fonte, predicado, valor, unidade, sujeito,
                       objeto, papel, tempo, âncora, qualidade, linhagem, estado)
parte                 (identidade de pessoa/organização, documentos, aliases)
participacao          (parte, papel, caso|documento|ato, fundamento, intervalo)
ato_registral         (documento, matrícula, serventia, referência, tipo, data)
relacao_ato           (ato_origem, ato_destino, tipo: baixa|aditivo|retificação)
arquivo_geo           (documento, formato, hash, crs_origem)
feicao                (arquivo_geo, tipo, geometria, identificador interno)
medicao               (feicao|declaração, valor, unidade, método, crs, versão)
regra                 (id, versão, eixo, objetivo, uf, competência, predicados,
                       condição, resultado, fonte_normativa, dispositivo, origem)
conjunto_regras       (versão publicada, homologação, ativação por escopo)
avaliacao_regra       (regra, versão, caso, estado, entradas, faltantes, trilha)
conclusao             (id, versão, classe, texto, premissas[], normas[], regras[],
                       aplicabilidade, certeza, impacto, urgência, limites, estado)
revisao               (conclusao|observacao, versão, ação, autor, justificativa)
execucao              (caso, snapshot, passos, cursor, chave, manifesto)
```

**Não é uma tabela por substantivo.** JSON tipado continua adequado para atributos
variáveis; relações que precisam de integridade, revisão, busca e versionamento é
que saem do texto livre.

### 6.3 Migração

| Grupo | Como migra | O que não volta |
|---|---|---|
| Documentos e extrações | Adicionar versões e referências; converter staging em observações preservando ids legados | Página, papel, trecho e data nunca registrados. Reextração dos originais onde necessário |
| Pessoas e atos | Criar participações a partir de vínculos comprovados; menções indeterminadas ficam para revisão | Vendedor, titular atual e representante não se inferem de `proprietarios` |
| Conclusões antigas | Importar como legado, com cobertura explícita | `completed` **não** vira aprovado |
| `has_embargo=False` | Separar declaração, consulta e desconhecimento | Falsos legados não viram "ausência verificada" |
| Valores cadastrais | Projeções canônicas ligadas à decisão e à evidência | Identidade corrompida exige escolha humana |
| Regras | Inventariar ids, publicar versionado após homologação | Não afirmar equivalência por nome parecido |
| Geometria | Ingerir originais, criar versões e medições | Número de área não reconstrói polígono |

**Um adaptador serve a UI legada durante a transição. Nunca duas escritas
canônicas concorrentes.**

---

## 7. O ACERVO: DOCUMENTOS QUE ENTRAM NO BANCO

Nove insumos catalogados, **nenhum ingerido**. Sete naturezas, sete destinos.

| INS | O que é | Volume | Natureza | Destino | Incremento |
|---|---|---|---|---|---|
| 001/002 | Matrizes regulatórias v01 e v03 | 8 matrizes, 159 abas, 14.056 linhas, **325 regras** com condição lógica, resultado, fonte e dispositivo | Regra | **Motor jurídico** — tabela versionada | 4 |
| 003 | Matriz cartorária FED/GO/MG/SP/MT | 85 KB | Regra | **Motor cartorário** | 2 |
| 004 | Manuais e **102 TRs do IPE/SEMAD** | 224 arquivos, 450 MB | Exigência | **Skill do Redator** + checklist de peça por órgão | 5 |
| 005 | Indeferimentos lotes 1B/1C | 2 pareceres com motivo declarado | Decisão do órgão | **Base de precedentes** — alimenta o Radar | 5 |
| 006 | Processo SEI 202600017013170 | 9 arquivos, consulta + 2 pareceres + 3 despachos | Interpretação oficial | **Catálogo normativo**, tipo próprio ⚠ *erro material a confirmar: cita "Decreto Federal 9.710/2020" que é estadual* | 4 |
| 007 | Pacote SIGCAR | 21 arquivos, 157 pág, **6 roteiros por mensagem de erro** + IN 23/2025 | Procedimento + norma | **Indexado por erro** (novo tipo) + IN 23 no corpus | 4 |
| 008 | Relatório Fazenda Paraíso | 12 tabelas, 16 pendências | Método / gabarito de saída | **Referência de qualidade do diagnóstico** | 5 |
| 009 | Auditoria Codex + as 5 auditorias | — | Auditoria | Já versionado | — |

**Regras de manuseio (valem sempre):** nada de original pesado no git (R2 é o
storage) · PII nunca no repo (INS-006 tem CNH de terceiro) · hash na chegada ·
**erro material do órgão não vira verdade do sistema** · natureza antes de destino.

### 7.1 Trabalho de análise pendente por insumo

| Insumo | O que falta antes de ingerir |
|---|---|
| Matrizes | Vocabulário canônico entre matrizes (a 1 usa Tema/Tipo/Confiança; as 5-8 usam Eixo/Ação/Severidade) · coluna "Tipo de regra" deslocada em parte das linhas · confirmar versão corrente da matriz 2 · a CAR v03 veio com 3 regras contra 37 |
| Matriz cartorária | Inventário completo — nunca foi feito |
| TRs | Inventariados por contagem, não por conteúdo · duplicados · um PDF de 41 MB |
| SEI | Confirmar o erro material do Parecer 84 com a Ísis |
| SIGCAR | Separar a IN 23/2025 (norma, vai para o corpus) do resto (procedimento) |

---

## 8. OS OITO INCREMENTOS

Cada um atravessa o sistema e entrega algo conectado. Nenhum é "metade de
arquitetura". Os seis agentes compartilham o contrato desde o primeiro.

### INCREMENTO 0 — Cobertura do MVP e preparação dos insumos
**Roda em paralelo à fundação; não bloqueia o incremento 1.**

Inventariar as 325 regras não é torná-las operacionais no lançamento. O mesmo
vale para os 102 TRs. Antes de construir, definir **o que o primeiro produto
cobre**:

| Objetivo | UF | Documentos e formatos | Regras necessárias | Consultas e camadas | Peça entregue | Teste de aceite |
|---|---|---|---|---|---|---|
| Novo CAR | GO | certidão, escritura, CCIR, ITR, KMZ | (a definir com a Ísis) | (a definir) | relatório preliminar + escopo | Jobson #25 |
| … | … | … | … | … | … | … |

Tudo necessário à cobertura escolhida entra no MVP. O restante fica **identificado
como não coberto** — a arquitetura suporta, o lançamento não depende.

**Também neste incremento:** inventário e análise dos insumos (§7.1) — vocabulário
canônico das matrizes, coluna deslocada, matriz cartorária nunca inventariada, TRs
por conteúdo, erro material do Parecer SEI 84. Não esperar o incremento 4 para
descobrir que uma matriz está incompleta.

**Participação da Ísis:** confirma exemplos, resultados esperados e cobertura.
**Prova:** matriz de cobertura preenchida, com responsável por linha.
**Esforço:** pequeno-médio, mas é pré-condição de escopo.

### INCREMENTO 1 — Contrato, contexto e revisão
**Entrega:** construtor de contexto único (servidor) usado por tela, API síncrona,
worker e retomada · os quatro objetos do contrato de evidência · estados de
conhecimento · envelope de execução substituindo o dict · revisão por conclusão e
versão · gate na montagem do contexto seguinte · manifesto de execução no AIJob ·
retomada persistida com snapshot e idempotência · política de seis agentes ativos
(congelar os outros cinco em UI, API, worker **e scheduler**).

**Também no 1, porque nascem com o contrato e não depois dele:**
· conclusão aprovada **vinculada às versões das premissas**;
· premissa alterada torna a conclusão dependente **desatualizada**, sem apagar a
  aprovação;
· **avaliação automática nunca sobrescreve decisão humana** (a dívida #220 — hoje
  o auditor aplica status direto no staging, `auditor_imovel.py:164-171`);
· evidência recuperável conforme política de retenção declarada.
Sem isso, "conclusão aprovada e válida" do gate não tem como ser verdade.

**Método de domínio neste incremento:** compatibilizar as duas skills reais com o
contrato e corrigir as contradições conhecidas — a H1 da skill do diagnóstico
classifica "não sei se há GEO" como risco alto, o que contradiz a segunda
validação. Não religar as 890 linhas sem revisão semântica.

**Prova:** no percurso autenticado, no mesmo teste — rejeitar conclusão impede seu
consumo; corrigir cria versão e a anterior é recuperável; recarga e nova sessão
mantêm a decisão; retomar não duplica; porta síncrona e assíncrona produzem o
mesmo contexto (provar com a skill do diagnóstico carregando pelos dois e o
manifesto registrando qual entrou); skill obrigatória ausente ⇒ capacidade
insuficiente visível; conclusão que afirma ausência sem registro de verificação é
recusada; **premissa corrigida desatualiza a conclusão dependente e preserva o
registro da aprovação anterior**; **auditor reexecutado gera nova avaliação e não
substitui aceite**.

**Critérios que deve atender:** REVIEW-001 · base de DIAG-002 e DIAG-005 · #220 ·
#215 (versionamento de entrada/modelo/saída) · #217 · #227 · #229 · causa raiz do
caso #25. **ADR-069.** Esforço: grande.

### INCREMENTO 2 — Entrada semântica e motor cartorário
**Entrega:** taxonomia documental real (certidão de matrícula, escritura, contrato
particular, contrato de serviço, documento pessoal, documento de representação,
CAR, CCIR, ITR, SIGEF, peça de órgão, arquivo geoespacial) com tipo original,
proposto, revisado, responsável e motivo · pessoas e papéis · participação ·
espólio e inventariante · atos e temporalidade qualificada · observação durável ·
**fim do preview achatado como segunda verdade** · motor cartorário.

**Prova:** escritura não prova estado atual · vendedor não vira cliente nem
titular · PJ preserva CNPJ · espólio e representação têm fundamento · dois
documentos iguais preservam duas fontes · baixa e aditivo mantêm ato e vínculo ·
reclassificar tipo invalida extrações dependentes e pede revisão.

**Método de domínio neste incremento:** skill do Extrator por família documental
(registral, cadastral/CAR, pessoal, geoespacial, contratual) + método cartorário.
Capacidade não sai sem seu método.
**Participação da Ísis:** valida amostras já verificadas tecnicamente — papéis,
atos e o que cada espécie documental sustenta.

**Critérios que deve atender:** READ-001 a 007 · AUD-004 · ENT-INV-001 · #211 ·
#212 · #216 · #223 · #224 · #226.
**ADR-070 (modelo de dados) + ADR-071 (cartorário).** Esforço: grande. **Depende:** matriz cartorária (incremento 0).

### INCREMENTO 3 — Geometria e Auditor unificado
**Entrega:** ingestão KMZ/KML/shapefile · feições e medições · cálculo em CRS
métrico · comparação com denominador declarado · overlays com camada identificada ·
Auditor com fonte única para resumo e matriz · confrontos com identidade de objeto ·
avaliação não sobrescreve revisão humana.

**Prova:** KMZ real de Jobson reproduz a área dentro da tolerância acordada ·
denominador aparece · erro geométrico vira falha, não silêncio · falta de camada
vira "não verificado" · cabeçalho e linhas coincidem após recarga · rodar o Auditor
depois do aceite gera nova avaliação, não substitui decisão.

**Método de domínio neste incremento:** os critérios de confronto da skill do
Auditor (228+66 linhas) traduzidos em **regras verificáveis**, não em prompt.
**Participação da Ísis:** homologa tolerâncias, denominador do percentual e o que
é fato, divergência, lacuna e risco.

**Critérios que deve atender:** AUD-001 a 003 · AUD-005 a 007 · DATA-002 · #208 ·
#219 · #225 · #228 · #230.
**ADR-072.** Esforço: médio-grande.

### INCREMENTO 4 — Motor jurídico, matrizes e fontes
**Entrega:** importador recorrente das matrizes · linguagem restrita de condições ·
regras versionadas com homologação, publicação, ativação e rollback · protocolo de
competência e conflito como tabela de decisão · fontes por chave + versão +
dispositivo · avaliação com estado `indeterminado` · Legislação consumindo o motor ·
filtro por objetivo canônico sem relaxamento silencioso.

**Prova:** inventariar os 325 ids — todos com destino e status justificado · para
cada objetivo e UF suportados, cada regra necessária é executável ou explicitamente
de decisão profissional · positivo, negativo, faltante, conflito e fronteira passam ·
norma ausente não ganha substituta por similaridade · "zero regras disparadas"
aparece como isso, não como regularidade.

**Método de domínio neste incremento:** skill da Legislação — ordem de pesquisa,
competência, exceções, limites, tratamento de fonte — conectada ao motor.
**Participação da Ísis:** homologa as regras da cobertura escolhida e a tabela de
conflito de esferas. Regra não homologada não publica.

**Critérios que deve atender:** LEG-001 a 007 · DIAG-003 · ADR-042 aceito com as
correções do mergulho.
**ADR-073.** Esforço: grande. **Depende:** matrizes + protocolo (incremento 0).

### INCREMENTO 5 — Métodos dos seis e fechamento comercial
**Entrega:** skills reconciliadas e escritas (extrator por família documental,
legislação, diagnóstico revisado, redator com TR, orçamento) · diagnóstico por
afirmação com premissas · Redator com checklist de TR · Orçamento integrado à Rota
e à precificação oficial · `gerar_proposta` desbloqueado com retomada.

**Prova:** risco, urgência e serviço têm premissas e aplicabilidade · lacuna não
vira passivo · peça atende o TR item a item · orçamento usa escopo aprovado ·
`gerar_proposta` não reabre diagnóstico escondido nem trava sem retomada · o
relatório da Fazenda Paraíso (INS-008) serve de referência de qualidade.

**Participação da Ísis:** valida o método do diagnóstico e o atendimento ao TR
por tipo de peça.

**Critérios que deve atender:** DIAG-001 a 009 · ROUTE-001 · o bloqueio comercial
do `gerar_proposta`.
**ADR-074.** Esforço: grande. **Depende:** TRs (incremento 0).

### INCREMENTO 6 — Migração de dados
> **Redefinido em 22/09/2026 (André).** O schema **não** é trabalho deste
> incremento: produção migra sozinha no deploy (`preDeployCommand` do
> `regente-api` — dump do schema `public` no R2 e depois `alembic upgrade head`;
> confirmado em 22/09 pelo `supabase-prod-ro`: produção em `072ge001`, com as
> tabelas dos incrementos 1 a 3 presentes e vazias). O que resta é **dado**: o
> que já está em produção precisa chegar ao modelo novo sem fabricar evidência.

**Entrega — três frentes de dado:**

| Frente | O que é | Tamanho medido em produção (22/09) | Regra |
|---|---|---|---|
| **Corpus** | Reconstruir o corpus normativo de produção a partir do dev: texto corrompido dos ids 16–22 (issue #185, 3,7%–4,7% de `U+FFFD`), 49 documentos federais que só o dev tem (#244), estrutura da norma e proveniência (ADR-075) | 64 normas · 28.891 chunks | Reconstrução a partir do dev, conferida por impressão digital antes e depois; nada reingerido às cegas |
| **Extrações antigas** | Staging legado (`extracted_field_staging`) → observações do modelo novo, ou reextração dos originais onde a observação não se sustenta (página, trecho e data nunca registrados não se reconstroem — §6.3) | 342 linhas em 5 processos | Converter o comprovável, preservando ids legados; o resto é reextraído com o Luna, nunca inferido |
| **Checksums** | Hash sha256 dos bytes originais de cada documento de caso (#259) e de cada fonte normativa (ADR-075 A5) | 72 documentos, 1 sem hash | Recalcular a partir do objeto no storage **só** quando o objeto é comprovadamente o recebido; senão marcar "hash de origem desconhecido" — nunca inventar |

Continuam aqui, porque também são dado e não schema: obsolescência por
dependência de versão · saneamento assistido de identidade (#209, #210) ·
retenção que preserva prova (#207). A **contração** das colunas legadas
([inventário de leitores](INVENTARIO_LEITORES_LEGADO.md)) roda depois das três
frentes — a migration que remove a coluna sai no deploy como qualquer outra; o
trabalho do incremento é zerar os leitores e migrar o dado antes.

**Prova:** corpus de produção com a mesma impressão digital do dev, zero
`U+FFFD` nos ids 16–22 · cada linha de staging legado tem destino declarado
(convertida, reextraída ou marcada) · todo documento tem hash ou marca de
origem desconhecida · documento novo desatualiza o que depende dele · versões
anteriores preservadas · artefato comercial não fecha sobre fundamento superado
· fontes acessíveis após arquivamento · **nenhum backfill inferido** · dump de
pré-deploy conferido antes de cada escrita em produção.
**Esforço:** médio-grande.

### INCREMENTO 7 — Aceite E2E e homologação
**Entrega:** percurso autenticado completo em ambiente de homologação, com os
casos originais.

**Prova:** Jobson, ELODI, Valéria e perfis de borda · rejeição e correção em cada
etapa · falha, retry e concorrência · nenhuma evidência estrangeira ao tenant ·
proposta desatualizada não aceita · os cinco eixos de estado coerentes após nova
sessão.

**Condição de entrada (André, 23/09/2026) — a tela conhece o motor jurídico
(dívida #278).** O Incremento 4b provou o motor por API; o percurso do Incremento
7 é pela tela. Antes dele, o painel precisa: gerar a Rota pelo motor, mostrar o
relatório da execução (avaliadas, não aplicáveis, indeterminadas com os fatos
faltantes, fundamento por ID ou a razão de não ter), registrar ciência de alerta
crítico com justificativa e pedir motivo ao remover passo do motor — hoje o botão
de remover recebe 400 num passo de origem `motor`.

**Condição de entrada (André, 24/09/2026) — orçamento só do tenant (dívida #284).** Antes do
Incremento 7 saem os dois orçamentos legados de código — `OrcamentoAgent._estimate_by_rules` e a
distribuição da `PRICE_TABLE` em `proposal_generator` —, e toda proposta nasce do orçamento derivado
da Rota com métodos e preços do tenant (ADR-074). Depende da tela do orçamento (#282).
*(26/09: #282 fechada no #219; #284 implementada no ADR-081 — ver
[ORCAMENTO_SO_DO_TENANT_284.md](ORCAMENTO_SO_DO_TENANT_284.md).)*
**Esforço:** médio. **Não é opcional.**

### INCREMENTO 8 — Aceite da Ísis e publicação controlada
**Homologação aprovada e produção verificada são marcos diferentes.**

**Parte A — aceite integral.** A Ísis valida **domínio**, não caça bug. O roteiro
de reteste da segunda validação (§11 dela) é o guia. Ela chega tendo validado
amostras nos incrementos 2 a 5, então não descobre aqui uma interpretação errada
do próprio método.

**Parte B — publicação.** Preparada durante os incrementos anteriores:

| Item | O que precisa estar definido |
|---|---|
| Versão | Commit exato aprovado, com a trilha de provas anexada |
| Migrations | Compatibilidade entre API e worker durante o deploy; ordem e reversibilidade |
| Reversão | Procedimento de recuperação testado, não descrito |
| Verificação pós-publicação | Percurso mínimo executado em produção, com resultado colado |
| Monitoramento | Falhas, filas, custo de IA, e o que dispara alerta |
| Atendimento ao piloto | Quem responde, em quanto tempo, por qual canal |
| Backup | Dump do schema `public` no R2 antes de toda migration (pré-deploy, retenção 30 dias / mínimo 10). **Falta:** restore ensaiado e backup agendado independente de deploy |

**Prova:** a versão aceita está no ar, verificada, com reversão ensaiada.

### 8.1 Condição de avanço por incremento

| Ordem | Entrega principal | Condição para avançar |
|---|---|---|
| 0 | Cobertura do MVP, insumos inventariados, casos e resultados esperados | Escopo verificável, responsável por linha |
| 1 | Contrato, contexto, revisão, retomada, invalidação | Decisão humana preservada em todas as portas |
| 2 | Entrada semântica, método do Extrator, motor cartorário | Pessoas, papéis, atos e fontes corretos nos casos reais |
| 3 | Geometria e Auditor unificado | Medições reproduzíveis e confrontos coerentes |
| 4 | Motor jurídico e método da Legislação | Regras e fundamentos homologados para a cobertura escolhida |
| 5 | Diagnóstico, redação e fechamento comercial | Percurso chega a proposta sem inventar escopo |
| 6 | Migração de dados: corpus, extrações antigas, checksums (schema migra no deploy) | Dados antigos tratados sem fabricar evidência |
| 7 | Homologação técnica integral e auditoria independente | Percurso completo aprovado, com falha e concorrência · **entra só com a tela do motor jurídico (#278) e sem a tabela de preços de código (#284)** |
| 8 | Aceite da Ísis e publicação controlada | Versão aceita e funcionamento publicado verificado |

**Sobre prazo:** isto é uma sequência com esforço relativo, não um cronograma.
Faltam responsáveis, disponibilidade dos insumos e tempo de validação. O
incremento 1 será estimado por tarefas e sua execução calibra os seguintes. Não
inventar datas agora.

### 8.2 Por que esta ordem

O gate precisa conhecer identidade e versão antes de proteger conclusões. Os
motores precisam de fatos tipados antes de aplicar regras. A skill precisa receber
fatos confiáveis antes de sintetizar. A proposta precisa de escopo aprovado antes
de precificar. **Construir skill primeiro sobre o dict atual melhora o texto e não
resolve nada.**

---

## 9. REMEDIAÇÕES E DÍVIDAS

### 9.1 O que o redesenho absorve

Absorvida = a implementação elimina a causa e prova isso. **Nenhuma fecha por
decreto.**

| Dívida | Onde morre | Incremento |
|---|---|---|
| #207 prova morre com o caso | Evidência durável + retenção coerente | 1 e 6 |
| #208 rótulo fora da API | Resultado canônico com código, classe e rótulo do mesmo catálogo | 3 |
| #211 representante duplicado por ordem de campo | Separação pessoa/participação | 2 |
| #214 `initial_diagnosis` sugere conclusão | Contrato de relato e objetivo | 1 |
| #216 acentos no classificador | Porta documental única com regressões por tipo | 2 |
| #219 área gráfica do CAR | Medição por fonte e finalidade | 3 |
| #220 auditor sobrescreve aceite | Separação avaliação/revisão — **P0 para religar a cadeia** | 3 |
| #224 identidade PJ fora do staging | Pessoa/participação + comparação com cadastro | 2 |
| #225 APP sem decisão agrupada | Mesa de decisões por objeto e finalidade | 3 |
| #226 aditivo sem vínculo | Grafo de atos + revisão | 2 |
| #230 dict bruto na Conferência | Projeção de apresentação | 3 |

### 9.2 O que permanece e exige trabalho próprio

| Dívida | Por quê | Quando |
|---|---|---|
| #209 CPF em PJ legado | Correção assistida com fonte; nunca backfill inferido | 6 |
| #210 duplicados históricos | Identidade e relações com decisão humana | 6 |
| #212 representação sem edição na UI | Entrega obrigatória de interface | 2 |
| #213 títulos antigos afirmam passivo | Renomeação assistida | 6 |
| #215 variação da extração | Versionar entrada/modelo/saída, ancorar, medir repetibilidade. **Determinismo de regra não corrige observação errada** | 1 e 2 |
| #217 hash chain concorrente | **Agrava com mais eventos.** Escrita serializada + verificação da cadeia | 1 |
| #223 CNH-e sem conteúdo | Reexecutar OCR do original; contrato expõe insuficiência sem criar representante fictício | 2 |
| #227 rollback neutralizado nos testes | **Gate técnico.** Transações reais, falha entre revisão e retomada, worker repetido | 1 |
| #228 bucket inexistente vira arquivo ausente | Separar indisponibilidade de ausência — necessário para OCR e geometria confiáveis | 3 |
| #229 exceções e sessão abortada (11 pontos) | Dono da transação, savepoints, falhas tipadas. **`knowledge_catalog.search` é o pior: erro de banco vira RAG com zero trecho** | 1 |

### 9.3 As que agravam se o redesenho for apressado

**#207, #210, #217, #220, #227, #229.** Mais referências sem retenção, migração de
identidade sem decisão, mais concorrência, reavaliação apagando aceite, transações
não exercitadas. Tratar cada uma **dentro** do incremento que a toca, nunca depois.

### 9.4 Correções de desenho que entram junto

| Item | Ação | Incremento |
|---|---|---|
| `_call_claude` fora do gateway | Migrar para o gateway único (ADR-002) | 4 |
| Prompts em banco + fallback em código | Resolução versionada e auditada; fallback identificado | 1 |
| Preview do extrator | Vira projeção da observação, perde autoridade | 2 |
| `requires_review` como badge | Mantém sinalização; a autorização de consumo vira revisão versionada | 1 |
| Orçamento com tabela própria | Unificar com `proposal_generator` | 5 |
| Skills-placeholder anunciadas como capacidade | Sair do catálogo de capacidades habilitadas | 1 |
| `grade_overlap_severity` órfão | Reaproveitar no fluxo espacial homologado, ou remover | 3 |

---

## 10. GOVERNANÇA DE EXECUÇÃO

### 10.1 Regras que mudam a partir daqui

1. **O critério de aceite vem da spec da Ísis, não do prompt.** Onde ela diz
   "impedir", o teste prova que foi impedido — não que existe aviso.
2. **Quem implementa testa; o aceite independente é outra revisão.** O
   implementador continua responsável por provar o próprio trabalho — e o aceite
   nunca é dele. Base concreta: na Frente J, sete itens implementados e não
   validados; a revisão seguinte achou 15 problemas, três que quebrariam produção.
3. **Nenhum incremento fecha sem percurso autenticado.** Gate de staging não é
   ponta a ponta. Fixture construída do código confirma o código; fixture do dado
   real acha o bug.
4. **Toda frente que muda extração lista os casos em produção com extração
   antiga.** O #23 ficou desatualizado sem ninguém notar.
5. **Afirmação sem instrumento não fica.** Varredura descrita e não versionada não
   é varredura.
6. **Replay de dado fabricado mede roteamento, nunca semântica.**
7. **Auditoria independente ao fim de cada incremento**, com a régua rigorosa:
   FECHADO só com critério integral, caso real, autenticado, com recarga e nova
   sessão.

### 10.2 Numeração e artefatos

Dívidas: corpus 100-199 · produto 200-299 · infra 300-399. Próximo livre: 231.
ADRs deste plano: **069** (contrato) · **070** (modelo de dados) · **071** (motor
cartorário) · **072** (geometria e auditor) · **073** (motor jurídico) · **074**
(métodos e comercial). ADR-042 é aceito dentro do 073, com as correções do mergulho.
*Renumerado em 17/09 por decisão do André (070 modelo, 071 cartorário, 072 geometria);
073/074 por deslocamento. Ver [ADR-070](../adr/070-modelo-de-dados-alvo.md).*

Cada incremento produz: ADR · atualização do MODELO_DE_DADOS · relatório com a
prova colada · pulso (ESTADO_ATUAL, progressoIA, REGISTRO_DIVIDAS, index).

### 10.3 Disciplina de agente

Worktree própria por frente · branch nomeada · `git branch --show-current && pwd`
antes de commit · merge só do André · CI da main conferido job a job · suíte
completa no CI, não no agente · comando de lint igual ao do CI.

---

## 11. MATRIZ DE ACEITE FINAL

O MVP está pronto quando estes casos atravessam o sistema inteiro, autenticado,
com recarga e nova sessão:

| Caso | O que precisa ser demonstrado |
|---|---|
| **Jobson (#25)** | E-mail, canal, CPF e objetivo persistem · escritura mantém tipo e data · vendedor, comprador, falecido e inventariante separados · matrícula 2.972 e RL AV.10 visíveis · **KMZ calculado e confrontado** · ausência de certidão atual vira lacuna · nenhum embargo, SIGEF ou serviço obrigatório afirmado sem prova e aplicabilidade |
| **ELODI (#23)** | CNPJ preservado · representante correto · quatro matrículas e linhagem · números registrais normalizados · RL, APP, arrendamento e ônus separados · gravação e recarga comprovam destino e origem de cada valor |
| **Valéria (#22)** | Cadastro humano distinto de extração · documento pessoal sem leitura não recebe estado de leitura completa · município não se infere de local de emissão |
| PF/PJ, 1/N matrículas | Mesma cadeia e contrato · fonte cadastral não cria matrícula contra a regra registral · nenhuma evidência órfã some |
| Duas fontes iguais/divergentes | Preservar fontes; não votar por quantidade · tempo e objeto delimitam confronto · fonte única não é concordância |
| Regra positiva/negativa/desconhecida/não aplicável | Resultado e justificativa distintos · desconhecido não produz conclusão de ausência |
| Documento novo após aceite | Dependências desatualizadas · versões preservadas · artefato comercial não fecha sobre fundamento superado |
| Falha e concorrência | Storage, corpus e OCR indisponíveis ficam visíveis · retomada idempotente · rollback exercitado de verdade |

---

## ANEXO A — DECISÕES TRAVADAS

1. **Seis agentes conectados.** Os outros cinco congelados em UI, API, worker e
   scheduler. Código preservado.
2. **Seis agentes ≠ seis LLMs.** O Auditor permanece determinístico.
3. **Dois motores determinísticos** — cartorário e jurídico — como módulos de
   domínio com runtime e trilha compartilhados. Não são agentes.
4. **A cadeia trafega evidências, não resultados.**
5. **O Redator não gera contrato.** Peça comercial nasce dos geradores
   determinísticos, depois do preço e do aceite.
6. **O Orçamento não é segunda fonte de escopo.** A Rota validada manda.
7. **Evidência nova não retrocede etapa automaticamente** — marca desatualizado,
   abre pendência de coleta e oferece o gesto ao consultor.
8. **A Ísis valida domínio ao longo do caminho, e faz o aceite integral no
   incremento 8.** No 0 confirma cobertura, exemplos e resultados esperados; nos
   2 a 5 valida amostras já verificadas tecnicamente; no 8 aceita o conjunto. Ela
   não caça defeito de software — mas não se constrói a interpretação do método
   dela sem consultá-la.
9. **O objetivo imediato é o MVP; o objetivo real é o sistema inteiro.** Nada de
   meia arquitetura que precise ser refeita. A **cobertura** do primeiro
   lançamento é recortada (incremento 0); a **arquitetura** não.
10. **O Redator entrega relatório preliminar e especificação de escopo antes da
    contratação; peça técnica definitiva só depois.** Não se executa o serviço
    para vendê-lo.

## ANEXO B — O QUE ESTE PLANO NÃO RESOLVE SOZINHO

- **Conteúdo jurídico das 325 regras.** O desenho define como recebê-las,
  executá-las e verificá-las; a correção jurídica é homologação da Ísis.
- **Cobertura por UF.** Presença de regra não prova cobertura operacional. Exige
  matriz real de capacidade por objetivo, UF e fonte.
- **Qualquer documento, qualquer situação.** Nenhum conjunto finito de schemas
  resolve tudo. O contrato garante resposta íntegra para o não coberto: preservar
  material, declarar limite, permitir decisão. **"Não sei" rastreável é
  comportamento funcional; regularidade inventada não é.**
- **Determinismo do LLM.** Versionar entrada, modelo e saída torna auditável, não
  determinístico.

---

*Plano diretor v1.1 — 17/09/2026. Incorpora a revisão independente do mergulho
estrutural. Centraliza o planejamento e referencia os ADRs. Qualquer mudança de
rumo altera este documento, não um prompt solto.*
