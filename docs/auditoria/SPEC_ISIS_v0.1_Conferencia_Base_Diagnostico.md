<!-- Versionado em docs/auditoria/ como insumo da auditoria de generalidade (Fase 2).
Fonte: 01_REGENTE_IA_Especificacao_Conferencia_Base_Diagnostico_v0_1.docx, autoria Isis Terra.
Convertido de .docx sem alteração de conteúdo. Autoridade de produto: decisões confirmadas
por Isis prevalecem. Não editar este arquivo; nova versão da spec = novo arquivo. -->

**REGENTE IA**

**ESPECIFICAÇÃO FUNCIONAL E HISTÓRICO\
DE VALIDAÇÃO DO MVP1**

Entrada • OCR • Base cadastral • Conferência • Diagnóstico

Casos de teste: Valéria Ruiz / Avalon Gleba 05\
e ELODI Agropecuária Ltda.

**Versão 0.1 \| Setembro de 2026**

Situação: baseline técnico para correção antes da validação dos Agentes IA

# Controle do documento

| **Campo** | **Definição** |
|----|----|
| Finalidade | Orientar o desenvolvimento, registrar decisões de produto e preservar as evidências dos testes do MVP1. |
| Público principal | Equipe de desenvolvimento do Regente (produto, backend, frontend e agentes). |
| Autoridade de produto | Decisões confirmadas por Ísis prevalecem sobre recomendações e hipóteses. |
| Documento relacionado | 00 — REGENTE IA — Documento Mestre do MVP1. Este arquivo o complementa com especificações e evidências operacionais. |
| Escopo desta versão | Entrada do caso, documentos, OCR, base cadastral, Conferência e pré-condições do diagnóstico. |
| Fora do escopo desta versão | Redesenho completo dos Agentes IA e programação detalhada da rota regulatória. Esses temas serão tratados após estabilização da base. |
| Estados usados | Confirmado; evidência de teste; defeito; regra funcional; recomendação; pendente; fora do MVP1. |

## Histórico de versões

| **Versão** | **Período** | **Resumo** | **Situação** |
|----|----|----|----|
| 0.1 | Setembro de 2026 | Consolidação dos testes Valéria e ELODI; definição da função da Conferência; requisitos de base, OCR, reconciliação e diagnóstico. | Baseline para revisão do DEV |
| Próxima | Após retorno técnico | Registro de solução proposta, estimativa, responsável, entrega, reteste e decisão de aceite. | A criar no mesmo documento |

## Como manter este arquivo

- Não apagar observações anteriores. Mudanças de regra devem ser registradas como nova versão.

- Para cada alteração do sistema, preencher: ID do requisito, solução adotada, responsável, versão entregue, resultado do reteste e situação.

- Separar sempre defeito observado, decisão de produto, hipótese técnica e evolução futura.

- Não transformar um dado específico de um caso em regra geral sem aprovação de produto.

# 1. Síntese executiva

**Conclusão principal.** Os dois testes mostraram que o gargalo anterior aos Agentes IA não está apenas no OCR. O problema central é a ausência de uma camada confiável de normalização, reconciliação e consolidação entre a leitura documental e a base do caso. A tela atual de Conferência entrega ao consultor fragmentos para validação e o obriga a reconstruir o significado dos documentos, comparar fontes e escolher categorias — trabalho que deveria ser preparado pelo sistema.

**Implicação.** Se os Agentes IA forem avaliados sobre uma base vazia, inconsistente, mal classificada ou não gravada, suas saídas não permitirão distinguir erro do agente de erro na camada documental. Portanto, o próximo gate não é “melhorar o prompt”; é garantir que o caso possua dados consolidados, evidências rastreáveis e achados corretamente classificados.

| **Pergunta** | **Resposta consolidada** |
|----|----|
| O que a Conferência deve validar? | Decisões consolidadas e exceções relevantes; não dezenas de fragmentos brutos do OCR. |
| O que entra na base? | Dados canônicos necessários à identificação do cliente, do imóvel e dos documentos, preservando a origem e as observações divergentes. |
| O que vai ao diagnóstico? | Divergências, lacunas, riscos, hipóteses, situações atuais relevantes, possíveis desatualizações e erros não resolvidos. |
| Quem decide? | A IA prepara e sugere; o consultor confirma ou corrige; o sistema registra a decisão e sua evidência. |
| Quando testar os Agentes IA? | Depois de corrigir as falhas P0 de gravação/persistência e de impedir diagnósticos sem base factual suficiente. |

## 1.1 Resultado esperado desta rodada

1\. O DEV compreende o comportamento atual e as evidências que o demonstram.

2\. Cada alteração possui identificação, prioridade e critério de aceite.

3\. Os casos Valéria e ELODI tornam-se casos de regressão permanentes do MVP1.

4\. A etapa de Agentes IA começa somente com uma base minimamente confiável.

# 2. Baseline de produto já confirmado

**Promessa do MVP1:** transformar uma demanda ambiental rural bruta em um caso diagnosticado, com caminho regulatório definido, proposta/orçamento estruturado e contrato formalizado — pronto para entrar em execução.

**Definition of Done:** o consultor recebe uma demanda desorganizada e chega, usando o Regente, a um contrato coerente com o diagnóstico e com a rota regulatória validada, sem reconstruir manualmente o caso fora da plataforma.

**Limite:** o MVP1 termina no contrato. Execução técnica, protocolos e acompanhamento posterior ficam fora desse recorte.

## 2.1 Regras estruturais confirmadas

| **Tema** | **Regra do MVP1** |
|----|----|
| Pessoa principal | Cada imóvel possui um único CPF ou CNPJ principal já registrado. O contratante do caso deve ser essa mesma pessoa. |
| Pessoa jurídica | Quando o cliente for CNPJ, o representante pessoa física pode ser vinculado como representante; não deve ser tratado como titular do imóvel. |
| Falecimento | Quando aplicável, a referência processual é o inventariante. |
| Coproprietários | O MVP1 não cadastra os demais coproprietários como pessoas vinculadas. |
| Imóvel | Unidade territorial permanente; pode conter várias matrículas confrontantes e com a mesma composição de titulares, mesmo com percentuais distintos. |
| Limite territorial | Matrícula não confrontante forma outro imóvel, outro caso e outros processos. |
| Caso | Demanda comercial específica ligada a um cliente, um imóvel e uma contratação. Nova contratação gera novo caso. |
| Frentes | Um caso pode conter várias frentes regulatórias. |
| Nova evidência | Documento técnico novo após a etapa 4 força revisão e retorno à etapa 3, preservando versões anteriores. |
| Proposta | Mudança relevante após envio gera nova versão numerada; a versão anterior fica desatualizada. |

## 2.2 Fronteira entre base, diagnóstico e rota

| **Camada** | **Responsabilidade** |
|----|----|
| Base cadastral | Guardar entidades e dados operacionais consolidados: pessoa principal, imóvel, matrículas, identificadores e valores necessários ao trabalho, sempre com proveniência. |
| Evidência/observação | Preservar o que cada documento declarou, inclusive período, página, trecho e confiança da extração. |
| Achado diagnóstico | Explicar o que a comparação das evidências revela: consistência, divergência, lacuna, possível desatualização, risco, oportunidade, condicionante ou contexto. |
| Rota regulatória | Aplicar normas vigentes aos fatos diagnosticados. Pode ser condicional; não pode ser inventada nem baseada em citações decorativas. No MVP1: normas federais e do Estado de Goiás. |

# 3. Arquitetura funcional esperada

**Fluxo lógico mínimo:** Documento → OCR/extração → normalização e classificação → reconciliação entre fontes → proposta de consolidação → validação humana → base canônica + achados → diagnóstico.

**Comportamento atual observado:** Documento → OCR → lista extensa de campos → consultor reconstrói o significado → tentativa de gravação. Essa sequência transfere para o usuário a análise complexa que o produto deveria preparar.

## 3.1 Modelo de informação recomendado

| **Objeto** | **Pergunta que responde** | **Conteúdo mínimo** |
|----|----|----|
| Documento | Qual arquivo foi recebido? | Tipo documental, emissor, data/período, partes, vínculo com cliente/imóvel, versão. |
| Observação | O que o documento declarou? | Campo, valor bruto, valor normalizado, unidade, página/trecho, documento-fonte, confiança. |
| Dado canônico | Qual valor operacional o sistema utilizará? | Valor vigente/proposto, regra de escolha, evidências, decisão humana, versão. |
| Achado | O que a comparação significa? | Classificação, frente regulatória, evidências, impacto, estado e conclusão. |
| Decisão | O que o consultor confirmou? | Opção escolhida, justificativa, autor, momento e versão. |
| Ação/rota | O que deve acontecer? | Providência, condição, responsável, dependência e fundamento normativo quando aplicável. |

## 3.2 Classificação do diagnóstico

**Antes da conclusão existe um achado.** Cada achado deve ser descrito em dimensões independentes, evitando misturar certeza, relação e impacto em um único rótulo.

| **Dimensão** | **Valores adotados** | **Uso** |
|----|----|----|
| Certeza | Fato confirmado; indicação; hipótese; não determinado | Quanto a evidência sustenta a conclusão. |
| Relação | Consistente; divergente; lacuna; possível desatualização; relação não comprovada | Como as fontes se relacionam. |
| Impacto | Risco; oportunidade/benefício; condicionante; dependência; bloqueio; contexto | Qual consequência existe para diagnóstico, rota, escopo ou contratação. |

## 3.3 Nova função da Conferência

**Definição funcional:** a Conferência é uma mesa de decisões consolidadas. Ela deve mostrar ao consultor o resultado preparado pelo sistema, as fontes que o sustentam, as divergências e o impacto da decisão — e permitir confirmar, corrigir ou classificar a exceção.

| **O sistema prepara** | **O consultor decide** |
|----|----|
| Normalização de números, nomes e identificadores | Confirma ou corrige decisão relevante |
| Agrupamento de evidências que tratam do mesmo atributo | Resolve exceção quando a evidência não é suficiente |
| Cronologia: atual, histórico, cancelado ou vigência incerta | Indica conhecimento técnico adicional quando necessário |
| Comparação entre matrícula, CAR, CCIR, ITR, SIGEF e outros | Valida o efeito no diagnóstico e na contratação |
| Proposta de valor canônico e justificativa | Registra a decisão final com responsabilidade |

## 3.4 Blocos mínimos de decisão

- Composição territorial do imóvel e matrículas integrantes.

- Áreas documentais, gráficas e soma das matrículas.

- CAR: identificação, área, APP, Reserva Legal e situação documental.

- Titularidade atual e representante, quando pessoa jurídica.

- Cadastros rurais: INCRA/SNCR, CCIR, NIRF/CIB, ITR e respectivos períodos.

- Georreferenciamento e SIGEF: certificação, código e estado.

- Reserva Legal, APP e demais registros ambientais nas matrículas.

- Ônus, arrendamentos, averbações, cancelamentos e documentos ausentes.

# 4. Evidências dos casos de teste

**Método:** cadastro e upload executados no sistema atual; observação das telas de entrada, documentos, Conferência e dados. Os resultados abaixo não são opinião sobre o caso ambiental: são evidências do comportamento do produto.

## 4.1 Caso 01 — Valéria Ruiz / Avalon Gleba 05

| **Item** | **Registro** |
|----|----|
| Finalidade | Primeiro teste do fluxo de cadastro, checklist documental e execução da cadeia de diagnóstico. |
| Município correto | Pirenópolis/GO. Qualquer valor diferente deve ser corrigido e tratado como erro de dado ou inferência. |
| Interação identificada | Para o checklist avançar, foi necessário marcar documentos como “Recebido”. A ação e seu efeito precisam estar claros para o usuário. |
| Execução pretendida | Agentes IA → Executar cadeia → selecionar o contexto do caso → Diagnóstico Completo. |
| Limite da evidência | Esta versão não atribui ao caso conclusões técnicas não verificadas nos documentos ou em resultado registrado. |

**Lição do caso:** dados básicos incorretos ou estados documentais mal compreendidos contaminam o diagnóstico. O sistema deve distinguir dado cadastral informado, dado extraído e dado inferido, preservando quem confirmou cada valor.

## 4.2 Caso 02 — ELODI Agropecuária Ltda.

| **Campo** | **Valor usado no teste** |
|----|----|
| Pessoa principal | ELODI Agropecuária Ltda. — CNPJ 29.091.958/0001-17 |
| Representante | Joel Cenci — documento pessoal utilizado apenas como representação/identificação |
| Imóvel | Fazenda Retiro dos Olhos d’Água, Posse ou Porcos — Glebas 03 e 04 e Novo Horizonte II |
| Município | Alto Paraíso de Goiás/GO |
| CAR | GO-5200605-82E5.AE14.076B.4637.9900.9C9D.EC86.D700 |
| Matrículas | 3.181, 3.313, 3.673 e 4.387 |
| Documentos enviados | CAR, quatro certidões de matrícula e CNH do representante |
| Não apresentados nesta rodada | CCIR e ITR |
| Objeto do teste | Verificar consistência territorial/documental e lacunas antes de qualquer rota regulatória. |

### 4.2.1 Dados extraídos corretamente

| **Fonte**       | **Dado**                       | **Valor**     |
|-----------------|--------------------------------|---------------|
| CAR             | APP                            | 90,4225 ha    |
| CAR             | Reserva Legal                  | 437,7632 ha   |
| CAR             | Área gráfica                   | 2.180,8267 ha |
| CAR             | Área documental                | 2.180,3923 ha |
| Matrícula 3.181 | Área                           | 926,3654 ha   |
| Matrícula 3.313 | Área                           | 725,4663 ha   |
| Matrícula 3.673 | Área                           | 212,3553 ha   |
| Matrícula 4.387 | Área                           | 316,2053 ha   |
| Cálculo         | Soma das matrículas            | 2.180,3923 ha |
| Cálculo         | Diferença gráfica − documental | 0,4344 ha     |

**Regra derivada:** a base não pode guardar apenas “uma área total”. Deve preservar, no mínimo, área gráfica do CAR, área documental do CAR, áreas das matrículas, soma calculada, unidade e diferença. A interpretação canônica precisa coexistir com as observações por fonte.

### 4.2.2 Erros e ambiguidades de extração/classificação

| **Documento** | **Leitura atual** | **Leitura esperada** |
|----|----|----|
| Matrícula 3.313 | Arrendamento de 50 ha, com vigência 2013–2028, classificado como averbação de APP. | Classificar como arrendamento; registrar área e vigência; indicar situação atual segundo a data de referência. |
| Matrícula 3.673 | Reserva Legal de 42,8070 ha classificada como averbação de APP. | Classificar como Reserva Legal e preservar a averbação/documento-fonte. |
| Matrícula 3.181 | Código 050.041.396.737-1 classificado como NIRF/CIB. | Classificar conforme o texto-fonte: identificador INCRA/SNCR; não converter para NIRF/CIB sem evidência. |
| Matrícula 3.313 | Código 281310000060-08 classificado como SIGEF. | Registrar como certificação INCRA conforme a certidão; associar a SIGEF somente quando a fonte comprovar. |
| Matrículas | “2 itens” ou “5 itens” de ônus/averbações. | Extrair os eventos relevantes, tipo, data, estado atual e relação com o imóvel; não reduzir a contagem genérica. |
| Quatro matrículas | Titularidade atual não consolidada. | Extrair titular atual, título aquisitivo e eventos posteriores que alterem a titularidade. |

### 4.2.3 Problemas de entidade, estado e persistência

| **Evidência** | **Impacto** |
|----|----|
| O sistema permitiu cadastros duplicados para o mesmo CNPJ, com variações do nome Joel/ELODI. | Fragmenta histórico, imóveis, casos e contatos; impede identidade única da pessoa principal. |
| A aba de dados mostrou CNPJ vazio e aviso de razão social não preenchida, apesar do preenchimento no cadastro. | Indica falha de persistência, vínculo ou leitura da entidade pessoa jurídica. |
| A CNH do representante apareceu como “não classificado” e como documento de identidade do titular. | Confunde representação com titularidade e pode levar o agente a assumir pessoa física como proprietário. |
| Foram apresentados 42 campos para validação, muitos duplicados ou de baixa inteligibilidade. | Aumenta carga cognitiva e delega ao consultor a reconciliação dos documentos. |
| Foram preparados 28 campos; 14 permaneceram pendentes. | A interface permite progresso parcial, mas não organiza o trabalho por decisão ou impacto. |
| O comando “Gravar na base” foi acionado duas vezes e não concluiu a gravação nem exibiu erro. | Defeito crítico: nenhuma matrícula foi consolidada, a área permaneceu 0 ha e 28 campos continuaram aguardando gravação. |
| Antes de rodar os Agentes IA surgiu diagnóstico “Demanda Mista / Múltiplos Passivos”. | Conclusão sem base documental suficiente; o sistema deve impedir ou marcar explicitamente como hipótese não sustentada. |
| Contagens e estados do checklist/sidebar ficaram incompatíveis em diferentes momentos. | O usuário não consegue saber se o caso está pronto, pendente ou processando. |

**Nota de rastreabilidade:** a indicação “Dispensado: Não possui” para CCIR foi marcada manualmente pela usuária. Ela não deve ser registrada como decisão automática do sistema.

# 5. Matriz consolidada de lacunas

| **ID** | **Tipo** | **Prioridade** | **Lacuna** | **Risco** |
|----|----|----|----|----|
| SAVE-001 | Defeito | P0 | Gravação da Conferência falha silenciosamente | Base vazia; agentes sem contexto |
| DATA-001 | Defeito | P0 | CNPJ/razão social preenchidos não aparecem na base | Entidade PJ incorreta |
| DIAG-001 | Defeito/regra | P0 | Diagnóstico de passivos sem evidência suficiente | Risco técnico e comercial |
| ENT-001 | Regra/defeito | P0 | Representante confundido com titular | Titularidade incorreta |
| ENT-002 | Regra ausente | P0 | Duplicidade por mesmo CPF/CNPJ | Histórico fragmentado |
| OCR-001 | Defeito | P1 | Números brasileiros malformados | Áreas e cálculos errados |
| OCR-002 | Defeito | P1 | Evento/código classificado em categoria errada | Diagnóstico contaminado |
| HIST-001 | Regra ausente | P1 | Sem estado temporal atual/histórico/cancelado | Ônus e direitos mal interpretados |
| REC-001 | Função ausente | P1 | Evidências duplicadas não são reconciliadas | Consultor compara manualmente |
| CONF-001 | UX/arquitetura | P1 | Conferência por fragmentos, não por decisões | Carga cognitiva elevada |
| CONF-002 | Função ausente | P1 | Usuário altera valor, mas não categoria | Erro sem forma de correção |
| DATA-002 | Modelo ausente | P1 | Uma área total não representa as fontes | Perda de informação |
| DOC-001 | Regra/UX | P1 | Recebido, não apresentado, inexistente e dispensado não são claros | Checklist ambíguo |
| STATE-001 | Defeito | P1 | Estados e contagens contraditórios | Gate não confiável |
| REV-001 | Regra | P1 | Nova evidência precisa disparar revisão/versionamento | Histórico inconsistente |
| ROUTE-001 | Próxima fase | P2 | Rota precisa nascer de normas federais e de Goiás | Proposta de valor incompleta |

# 6. Requisitos funcionais para o DEV

**SAVE-001 — Gravação transacional da consolidação**

**Classificação:** Defeito \| Prioridade: P0

**Problema observado:** O clique em “Gravar na base” não produziu resultado visível nem persistiu os 28 campos preparados.

**Regra funcional:** A gravação deve ser atômica ou registrar claramente sucesso parcial. O backend deve devolver resultado por entidade/campo; o frontend deve mostrar sucesso ou erro acionável e impedir clique repetido durante processamento.

**Critério de aceite:** Dado um conjunto válido de decisões confirmadas, quando o usuário gravar, então as matrículas e dados canônicos aparecerão na aba Dados, a área será recalculada e os itens mudarão de estado. Em falha, nenhum dado deve ser apresentado como salvo e uma mensagem deve identificar a causa e permitir nova tentativa.

**Observação:** Registrar log técnico com case_id, user_id, batch_id, quantidade enviada, quantidade persistida, erro e timestamp.

**DATA-001 — Persistência da pessoa jurídica**

**Classificação:** Defeito \| Prioridade: P0

**Problema observado:** O CNPJ e a razão social informados no cadastro não apareceram corretamente na base do caso.

**Regra funcional:** Pessoa principal deve ser uma entidade única identificada por CPF ou CNPJ. O caso e o imóvel referenciam essa entidade; campos não podem ser duplicados em estruturas divergentes sem sincronização.

**Critério de aceite:** Ao abrir o caso da ELODI após cadastro, CNPJ e razão social devem aparecer exatamente como registrados em todas as telas que consomem a pessoa principal.

**ENT-001 — Separação entre titular/contratante e representante**

**Classificação:** Regra funcional \| Prioridade: P0

**Problema observado:** A CNH de Joel foi tratada como documento do titular, embora o cliente principal seja a pessoa jurídica ELODI.

**Regra funcional:** O CNPJ é pessoa principal, titular/contratante no escopo do caso. Joel deve ter papel “representante da pessoa jurídica”. Seu documento comprova representação/identidade, não titularidade do imóvel.

**Critério de aceite:** Ao carregar o caso, o sistema deve mostrar ELODI como pessoa principal e Joel em bloco separado de representante. Agentes e relatórios devem receber esses papéis explicitamente.

**ENT-002 — Prevenção e resolução de duplicidade por documento**

**Classificação:** Regra funcional \| Prioridade: P0

**Problema observado:** O mesmo CNPJ pôde ser cadastrado várias vezes com nomes diferentes.

**Regra funcional:** CPF/CNPJ normalizado deve ter unicidade no tenant. Antes de criar, o sistema procura correspondência exata e oferece reutilização do cadastro existente; divergência de nome vira atualização controlada, não nova pessoa.

**Critério de aceite:** Dado o CNPJ 29.091.958/0001-17 já existente, uma nova tentativa de cadastro deve bloquear duplicação e direcionar para selecionar/atualizar a entidade existente.

**Observação:** Não executar fusão automática dos registros históricos sem plano de migração e auditoria.

**DIAG-001 — Bloqueio de conclusão sem evidência**

**Classificação:** Regra funcional \| Prioridade: P0

**Problema observado:** O sistema apresentou “Múltiplos Passivos” antes da execução dos agentes e sem documento de passivo na rodada.

**Regra funcional:** Toda conclusão precisa apontar evidências. Sem base suficiente, o estado permitido é hipótese, não determinado ou lacuna; nunca fato afirmado.

**Critério de aceite:** Quando nenhuma evidência sustentar passivo, o diagnóstico não poderá afirmar passivo. Se houver indicação indireta, deverá mostrar classificação de certeza, fonte e justificativa.

**OCR-001 — Normalização de números e unidades**

**Classificação:** Defeito \| Prioridade: P1

**Problema observado:** Valores como 926,36.54 e 725,46.63 exigiram correção manual.

**Regra funcional:** O extrator deve preservar o valor bruto e produzir valor normalizado numérico usando contexto, unidade, valor por extenso e consistência interna.

**Critério de aceite:** As áreas das matrículas 3.181 e 3.313 devem ser propostas como 926,3654 ha e 725,4663 ha, com o texto original disponível para auditoria e nível de confiança.

**OCR-002 — Taxonomia e reclassificação de campos/eventos**

**Classificação:** Defeito + função ausente \| Prioridade: P1

**Problema observado:** Arrendamento, Reserva Legal e códigos INCRA foram classificados em categorias incorretas; a interface permitia editar somente o valor.

**Regra funcional:** Cada observação deve ter tipo editável, valor, unidade, temporalidade e proveniência. O usuário autorizado deve reclassificar sem perder o valor bruto e a sugestão original.

**Critério de aceite:** Na matrícula 3.313, o arrendamento deve ser classificável como arrendamento; na 3.673, a área deve ser classificável como Reserva Legal; as alterações devem persistir e alimentar a reconciliação.

**HIST-001 — Leitura temporal dos atos registrais**

**Classificação:** Regra funcional \| Prioridade: P1

**Problema observado:** A listagem genérica de averbações/ônus não distingue situação atual, histórica ou cancelada.

**Regra funcional:** O sistema deve extrair eventos com data, ato, partes, objeto, vigência e relação com eventos posteriores; indicar atual, histórico, cancelado ou indeterminado.

**Critério de aceite:** Um arrendamento com termo de 2028 deve ser mostrado como vigente se a data de referência estiver dentro do período, sem ser confundido com APP. Um cancelamento posterior deve alterar o estado, preservando o histórico.

**REC-001 — Reconciliação de evidências antes da Conferência**

**Classificação:** Nova função \| Prioridade: P1

**Problema observado:** O mesmo número de matrícula apareceu em campos separados por ter sido encontrado no CAR e na certidão.

**Regra funcional:** Observações equivalentes devem ser agrupadas como evidências corroborantes de uma mesma decisão. Divergências permanecem lado a lado com explicação.

**Critério de aceite:** O consultor verá uma decisão “Matrícula 3.181 integra o imóvel” com as fontes CAR e certidão, em vez de dois campos independentes para validar.

**DATA-002 — Modelo de áreas por fonte**

**Classificação:** Modelo de dados \| Prioridade: P1

**Problema observado:** A interface sugere uma única área total e informa que a área do CAR não entra na base.

**Regra funcional:** Armazenar observações de área por tipo e fonte; calcular somas e diferenças; registrar separadamente o valor canônico usado para cada finalidade.

**Critério de aceite:** O caso ELODI deve exibir área gráfica CAR 2.180,8267 ha, documental CAR 2.180,3923 ha, soma das matrículas 2.180,3923 ha e diferença 0,4344 ha, sem sobrescrever nenhuma origem.

**CONF-001 — Conferência orientada por blocos de decisão**

**Classificação:** Arquitetura/UX \| Prioridade: P1

**Problema observado:** Foram exibidos 42 campos, exigindo leitura de todos os documentos para compreender o que confirmar.

**Regra funcional:** A tela deve agrupar informações nas oito decisões mínimas e priorizar divergências, baixa confiança e alto impacto. Evidências concordantes ficam recolhidas, mas acessíveis.

**Critério de aceite:** O usuário pode concluir cada bloco com uma decisão e visualizar claramente: proposta do sistema, fontes, divergências, impacto, pendências e ação disponível.

**CONF-002 — Estados de decisão claros**

**Classificação:** Regra/UX \| Prioridade: P1

**Problema observado:** Os estados de campos e documentos não permitiram distinguir ausência, inexistência, dispensa ou pendência.

**Regra funcional:** Usar estados distintos para documento: apresentado/recebido; processando; lido; erro de leitura; não apresentado; declarado inexistente; dispensado por decisão; substituído; desatualizado. Toda alteração manual registra autor.

**Critério de aceite:** CCIR e ITR não enviados devem aparecer como “não apresentados” até decisão explícita. “Declarado inexistente” ou “dispensado” só ocorre por ação registrada do consultor.

**STATE-001 — Consistência dos estados derivados**

**Classificação:** Defeito \| Prioridade: P1

**Problema observado:** Checklist, barra lateral, progresso e base exibiram contagens incompatíveis.

**Regra funcional:** Definir uma máquina de estados única por documento e por bloco de decisão. Indicadores devem ser derivados da mesma fonte, não mantidos independentemente.

**Critério de aceite:** Após cada evento, todas as telas devem refletir o mesmo estado e contagem. Reteste deve incluir atualização de página e nova sessão.

**REV-001 — Revisão automática por nova evidência técnica**

**Classificação:** Regra funcional \| Prioridade: P1

**Problema observado:** Hoje a chegada tardia de documento pode exigir reconstrução manual do caso.

**Regra funcional:** Documento técnico novo após a etapa 4 retorna o caso à etapa 3, preserva versões anteriores e marca diagnóstico, rota e proposta posterior como desatualizados até nova validação.

**Critério de aceite:** Ao anexar nova matrícula após diagnóstico validado, o caso muda para etapa 3, cria nova revisão, preserva a anterior e impede aceite da proposta desatualizada.

**ROUTE-001 — Fundamentação normativa da rota**

**Classificação:** Direção da próxima fase \| Prioridade: P2

**Problema observado:** A rota regulatória é a principal entrega, mas sua avaliação depende de diagnóstico confiável.

**Regra funcional:** Cada decisão da rota deve ligar condição factual, norma vigente, consequência, órgão, ação, dependências, alternativas e validação humana. Escopo inicial: normas federais e do Estado de Goiás.

**Critério de aceite:** Uma rota não pode ser aprovada sem fonte normativa identificável ou declaração explícita de insuficiência. Este requisito será detalhado após o gate atual.

# 7. Roteiro de reteste e critérios de saída

## 7.1 Reteste mínimo — ELODI

1\. Localizar ou reutilizar a pessoa jurídica pelo CNPJ, sem criar duplicidade.

2\. Confirmar ELODI como pessoa principal/contratante e Joel apenas como representante.

3\. Criar ou abrir o imóvel e vincular as quatro matrículas confrontantes.

4\. Enviar CAR, quatro matrículas e documento do representante; manter CCIR e ITR como não apresentados.

5\. Confirmar que o OCR preserva valores brutos e propõe os valores normalizados esperados.

6\. Confirmar que arrendamento, Reserva Legal e identificadores rurais são corretamente classificados ou reclassificáveis.

7\. Conferir o caso por blocos de decisão, não por 42 fragmentos independentes.

8\. Gravar a consolidação e verificar persistência após atualização da página e nova sessão.

9\. Confirmar áreas por fonte, soma e diferença na aba Dados.

10\. Confirmar que nenhum passivo é afirmado sem evidência e que os agentes recebem apenas dados validados/qualificados.

## 7.2 Reteste mínimo — Valéria

1\. Confirmar município Pirenópolis/GO e rastrear se o valor foi informado, extraído ou corrigido.

2\. Validar que o checklist distingue documento recebido de documento dispensado ou não apresentado.

3\. Concluir a consolidação mínima antes de executar Diagnóstico Completo.

4\. Executar a cadeia no contexto do caso correto e verificar que toda conclusão aponta as evidências efetivamente vinculadas ao caso.

## 7.3 Gate para avançar aos Agentes IA

| **Condição** | **Obrigatória?** | **Evidência de aceite** |
|----|----|----|
| Gravação da Conferência funciona e persiste | Sim — P0 | Dados presentes após recarga/nova sessão; log de sucesso. |
| CPF/CNPJ e papéis estão corretos | Sim — P0 | Pessoa principal e representante separados. |
| Não há conclusão factual sem evidência | Sim — P0 | Diagnóstico inicial não inventa passivo ou rota. |
| Áreas e matrículas chegam estruturadas ao contexto | Sim | Payload ou tela demonstra valores, fontes e estado de validação. |
| Erros de classificação podem ser corrigidos | Sim | Categoria editada persiste e é consumida pelo diagnóstico. |
| Estados do caso são coerentes | Sim | Checklist, progresso e dados mostram a mesma situação. |

**Decisão de gate:** os Agentes IA podem ser auditados quando todos os itens P0 estiverem aprovados no reteste e existir um contexto estruturado minimamente confiável. Itens P1 podem ser entregues por incrementos, desde que não contaminem o resultado do agente.

# 8. Contrato mínimo de contexto para os Agentes IA

**Objetivo:** permitir que o DEV comprove o que os agentes efetivamente recebem. Não é uma definição final de API, mas o conteúdo semântico mínimo esperado.

| **Bloco** | **Conteúdo mínimo** |
|----|----|
| case | ID, etapa/revisão, objeto da demanda, imóvel vinculado e pessoa principal. |
| people | Pessoa principal/contratante; representante quando aplicável; papéis explícitos. |
| property | Município/UF, denominação, matrículas integrantes, critério de composição territorial. |
| documents | Tipo, estado, versão, data/período, vínculo, arquivo-fonte e resultado de processamento. |
| observations | Valor bruto, valor normalizado, unidade, tipo, documento/página, confiança e temporalidade. |
| canonical_data | Valores confirmados ou propostos, decisão, justificativa, fonte e versão. |
| findings | Certeza, relação, impacto, frente regulatória, evidências e estado de validação. |
| gaps | Documento/dado ausente, consequência e se bloqueia ou não o avanço. |
| instructions | Limites da tarefa: não inventar fatos, declarar insuficiência, respeitar território normativo federal + Goiás. |

# 9. Plano de implementação sugerido

| **Ordem** | **Entrega** | **IDs** | **Resultado esperado** |
|----|----|----|----|
| 1 | Correção de persistência e entidade | SAVE-001, DATA-001, ENT-001, ENT-002 | Caso confiável e reutilizável; base efetivamente gravada. |
| 2 | Proteção do diagnóstico | DIAG-001 | Nenhuma conclusão sem evidência rastreável. |
| 3 | Normalização e classificação | OCR-001, OCR-002, HIST-001 | Observações estruturadas antes da decisão humana. |
| 4 | Reconciliação e modelo de áreas | REC-001, DATA-002 | Base canônica preserva fontes e divergências. |
| 5 | Redesenho incremental da Conferência | CONF-001, CONF-002, DOC-001, STATE-001 | Consultor valida decisões e exceções. |
| 6 | Revisão/versionamento | REV-001 | Nova evidência não apaga história nem mantém saídas obsoletas. |
| 7 | Auditoria dos Agentes IA | Contrato de contexto + casos de regressão | Separar erro de dado, agente, prompt e norma. |
| 8 | Especificação programável da rota | ROUTE-001 | Decisões regulatórias normativamente fundamentadas. |

# 10. Registro de desenvolvimento

**Instrução ao DEV:** não substituir esta tabela. Adicionar novas linhas a cada entrega/reteste para preservar a memória do produto.

| **Período** | **Evento/evidência** | **Decisão ou requisito** | **Situação** |
|----|----|----|----|
| Setembro de 2026 | Teste Valéria: necessidade de marcar documentos como recebidos; município correto é Pirenópolis. | Rastrear origem/validação do dado e tornar estado documental inequívoco. | Registrado |
| Setembro de 2026 | Teste ELODI: cadastro PJ, quatro matrículas, CAR e representante. | Pessoa principal CNPJ; representante separado; um imóvel com múltiplas matrículas. | Regra confirmada |
| Setembro de 2026 | OCR gerou 42 campos e exigiu análise manual complexa. | Conferência deve operar por decisões consolidadas e exceções. | Especificado |
| Setembro de 2026 | 28 campos preparados; gravação não ocorreu e não houve erro visível. | SAVE-001 — correção P0 e observabilidade. | Aberto |
| Setembro de 2026 | Diagnóstico de múltiplos passivos apareceu sem evidência suficiente. | DIAG-001 — impedir afirmação sem evidência. | Aberto |
| A preencher pelo DEV | Solução implementada / versão / PR / migração. | Relacionar aos IDs deste documento. | Pendente |
| A preencher no reteste | Resultado de cada caso de regressão. | Aprovado, reprovado ou aprovado com ressalva. | Pendente |

# 11. Decisões ainda pendentes

- Hierarquia específica de fontes por classe de dado — não existe uma fonte universal para todos os atributos.

- Quais decisões não ambíguas podem ser aprovadas em lote e quais exigem confirmação individual.

- Modelo técnico de versionamento da base canônica, diagnósticos, rotas e propostas.

- Estrutura final das frentes regulatórias e regras programáveis da rota.

- Localização, formato, curadoria e atualização da base normativa atualmente consumida pelos agentes.

- Plano de tratamento/migração dos registros duplicados já existentes.

# 12. Próximo passo após esta consolidação

1\. Revisão técnica pelo DEV, com resposta por ID: causa, solução proposta, impacto de dados, esforço, dependências e ordem de entrega.

2\. Correção e reteste dos itens P0 nos casos Valéria e ELODI.

3\. Inspeção do contexto real enviado aos agentes, antes da execução da cadeia.

4\. Execução comparada dos Agentes IA e classificação de cada falha por camada: entrada, OCR, consolidação, agente, norma ou interface.

5\. Somente depois, detalhamento da estrutura programável do diagnóstico e da rota regulatória.

# Anexo A — Base esperada no caso ELODI após consolidação

| **Objeto** | **Valor/estado esperado** | **Observação** |
|----|----|----|
| Pessoa principal | ELODI Agropecuária Ltda. — CNPJ 29.091.958/0001-17 | Titular/contratante do caso. |
| Representante | Joel Cenci | Papel de representante; documento pessoal não prova titularidade. |
| Município/UF | Alto Paraíso de Goiás/GO | Vinculado ao imóvel. |
| Matrícula 3.181 | 926,3654 ha | Integra o imóvel; fonte e título atual devem permanecer rastreáveis. |
| Matrícula 3.313 | 725,4663 ha | Integra o imóvel; contém arrendamento de 50 ha com vigência registrada. |
| Matrícula 3.673 | 212,3553 ha | Integra o imóvel; RL de 42,8070 ha deve ser classificada corretamente. |
| Matrícula 4.387 | 316,2053 ha | Integra o imóvel; manter certificações e registros anteriores por categoria correta. |
| Soma das matrículas | 2.180,3923 ha | Valor calculado; não substitui observações de outras fontes. |
| CAR — área documental | 2.180,3923 ha | Corrobora a soma das matrículas. |
| CAR — área gráfica | 2.180,8267 ha | Preservar como observação distinta. |
| Diferença | 0,4344 ha | Achado de comparação; requer interpretação, não sobrescrita. |
| CCIR/ITR | Não apresentados | Não marcar automaticamente como inexistentes ou dispensados. |
| Passivos | Não determinado nesta rodada | Não afirmar sem evidência. |

# Anexo B — Modelo de resposta do DEV

| **ID** | **Causa técnica** | **Solução proposta** | **Dados/migração** | **Estimativa** | **Versão** | **Reteste** | **Situação** |
|----|----|----|----|----|----|----|----|
| SAVE-001 |  |  |  |  |  |  |  |
| DATA-001 |  |  |  |  |  |  |  |
| ENT-001 |  |  |  |  |  |  |  |
| ENT-002 |  |  |  |  |  |  |  |
| DIAG-001 |  |  |  |  |  |  |  |

*Fim da versão 0.1 — manter histórico e acrescentar decisões futuras por versão.*
