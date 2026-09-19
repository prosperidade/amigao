# Incremento 0 — inventário dos insumos, padrões e decisões pendentes

**Data:** 17/09/2026. **Base:** `b6df7e64830361e52c84d6276c92549419d77f72`. Worktree `wt-cobertura-mvp`, branch `docs/cobertura-e-ontologia`. Escopo documental; sem ingestão, importação de regra, schema, banco, provider ou deploy. Não há nova numeração de dívida; eventuais dívidas de produto pertencem à faixa 200–299.

**Resultado da inspeção:** INS-001/002/003 abertos: 325 ocorrências v01 (320 IDs textuais), 289 v03 e 174 cartorárias. Protocolo 98 e controle 99 transcritos literalmente. As três divergências foram verificadas contra os arquivos: vocabulário heterogêneo confirmado; coluna de tipo deslocada não reproduzida; CAR v03 tem um exemplo, não três regras. **Inventário integral permanece aberto nos demais insumos e decisões.**

Entregas complementares: [ontologia](ONTOLOGIA_REGENTE_v1.md) e [matriz de cobertura](COBERTURA_MVP_v1.md). A v1.1 é a referência de execução; o [ADR-042:5](../adr/ADR-042-motor-de-regras-deterministico-RASCUNHO.md#L5) continua rascunho histórico, não autorização de importação.

## 1. Proveniência, disponibilidade e método

Revisão após fornecimento do André: originais lidos em `D:\RegenteLandpage`, sem alteração. ZIP aberto em memória; membros XLSX do RAR lidos por `7z x -so`, sem extração permanente. Leitura de células por openpyxl com `data_only=False`; nenhum workbook foi salvo. Cache temporário de análise fora do repositório, sem substituir o acervo. Os hashes abaixo identificam exatamente os bytes examinados.

**Decisão do André: acervo permanente em R2, hash no catálogo, nunca Git ou pasta local como fonte definitiva.** Pendência de infraestrutura: provisionamento/configuração do armazenamento, política de acesso, chave e versão do objeto, SHA-256 dos bytes originais (distinto do hash do chunk), catálogo/manifesto de origem, verificação de integridade, retenção e recuperação. Nada foi enviado ao R2 nesta revisão. Precedente conferido: `6d7eab9`, “fix(repo): remove corpus SEMAD do git — quebrava clone do Render no Linux”. O Git recebe somente documentação derivada, inclusive a transcrição expressamente solicitada.

| Insumo | Estado atual | Limite |
|---|---|---|
| INS-001 | Oito matrizes do RAR abertas integralmente | 325 linhas de regra; identidade/versionamento e homologação ainda precisam das decisões indicadas abaixo. |
| INS-002 | Oito matrizes do ZIP v03 abertas; abas 98/99 comparadas célula a célula | 289 linhas de regra; CAR contém um exemplo, não três regras. |
| INS-003 | Cartorária aberta, oito abas | 174 IDs em duas representações; não somar abas como regras novas. |
| INS-004 | `MANUAIS_SEMAD.rar` aberto para a cobertura: sete TRs relacionados na seção 3.2 de COBERTURA_MVP; leitura integral do pacote não concluída | Origem/página e requisitos dos TRs selecionados registrados; contagem/deduplicação integral continuam tarefas de engenharia. |
| INS-006/007 | Nomes de arquivos SEI/SIGCAR localizados no diretório fornecido | Conteúdo ainda não auditado nesta revisão, priorizada em INS-002/003/001. Não tratar como inexistentes ou já lidos. |
| Três documentos externos | Não identificados inequivocamente | Os oito padrões foram confrontados com o código, não com o texto integral externo. |

A solicitação do caminho INS-001 foi atendida. Não há pedido pendente desses três originais. O caminho do pacote INS-004 foi solicitado individualmente; na sequência foi localizado `MANUAIS_SEMAD.rar`, candidato à próxima inspeção. Não inventar conteúdo dos itens ainda não auditados.


| Original | Bytes | SHA-256 |
|---|---|---|
| BASES DA REGULARIZAÇÃO.rar | 1037434 | 1f3dc4fd5faca89986ce62dca771e6ecb1fa57399908886afa5a84827dcc8c42 |
| Pacote_Matrizes_Regente_v03_2026-08-05.zip | 997826 | 750e25d382a4ba22e567586c7a126198e20945a29ab0df6e0f302a852eed54e2 |
| Matriz_Normativa_Cartoraria_Regente_FED_GO_MG_SP_MT_v1.xlsx | 85015 | 47f1a70cb15b6f06edcaf4ad81e716fc761d3f8ffd6a819d39e445deb6f0c1b9 |


## 2. Protocolo de conflito — transcrição literal prioritária da v03


Fonte representativa: `Matriz_Regulatoria_CAR_Federal_GO_SP_MG_MT_v03_2026-08-05.xlsx`, SHA-256 `c8019ec2cd7df2691d1770ff2d9f3d660520417dadb2ff69e592932a4fc4244a`. As oito matrizes têm conteúdo de células **idêntico** nas abas 98 e 99 (incluindo posições e vazios). Comparação de valores, não de estilos. A seguir, texto da autora, **sem homologação jurídica independente**; links e comandos são transcritos, não resultados de consultas atuais. Escapes HTML apenas preservam a renderização do texto.

### 2.1 `98_Conflitos_Regras!A1:J20`

> 98 — PROTOCOLO DE CONFLITO ENTRE REGRAS FEDERAIS E ESTADUAIS

> Regra oficial: não existe prevalência automática da regra federal, da regra estadual ou da norma mais restritiva. A resolução começa pela competência constitucional e pela hierarquia do ato.

| Linha Excel | Ordem | Tipo de conflito | Pergunta de resolução | Regra oficial | Resultado aplicável | Ação do Regente | Severidade | Exige decisão profissional | Fonte principal | Observações |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 1 | Hierarquia constitucional | Alguma regra contraria a Constituição? | A Constituição prevalece sobre leis, decretos, resoluções, instruções e manuais de qualquer esfera. | Desconsiderar a interpretação incompatível e registrar o fundamento constitucional. | Emitir alerta crítico, apresentar o conflito e exigir fundamentação do consultor. | Crítica | Sim | https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm | Não existe autonomia estadual para contrariar a Constituição. |
| 6 | 2 | Competência privativa ou exclusiva | A matéria foi reservada constitucionalmente à União? | Quando a Constituição atribui competência privativa ou exclusiva à União, a regra federal ou nacional válida disciplina a matéria; o Estado somente atua nos limites autorizados pela própria Constituição ou por lei complementar. | Aplicar a regra federal/nacional e separar a execução administrativa estadual permitida. | Classificar a competência antes de comparar o conteúdo das regras. | Crítica | Sim | https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm | Exemplo: legislação sobre águas é privativa da União, embora os Estados administrem águas de seu domínio dentro do sistema nacional. |
| 7 | 3 | Competência concorrente | A matéria está no art. 24 da Constituição, como proteção ambiental? | A União estabelece normas gerais; os Estados suplementam para atender peculiaridades regionais. As duas regras podem ser aplicáveis simultaneamente. | Aplicar a norma geral federal e a complementação estadual compatível. | Não escolher automaticamente uma esfera; montar a composição normativa. | Crítica | Sim | https://portal.stf.jus.br/constituicao-supremo/artigo.asp?abrirArtigo=24&abrirBase=CF | A relação é de coordenação constitucional, não de superioridade genérica da lei federal. |
| 8 | 4 | Contradição com norma geral | A regra estadual reduz, afasta ou contradiz requisito mínimo de norma geral federal? | A competência suplementar não autoriza o Estado a esvaziar ou contrariar a norma geral nacional. | Não aplicar a regra estadual no ponto incompatível; preservar as demais disposições válidas. | Emitir alerta crítico e encaminhar para validação jurídica. | Crítica | Sim | https://portal.stf.jus.br/constituicao-supremo/artigo.asp?abrirArtigo=24&abrirBase=CF | A incompatibilidade pode ser parcial, sem invalidar todo o diploma estadual. |
| 9 | 5 | Proteção estadual adicional | A regra estadual é mais protetiva e continua harmônica com a norma geral federal? | Uma norma estadual mais protetiva pode ser válida quando suplementa a disciplina nacional, atende peculiaridade regional e não invade competência privativa. | Aplicar cumulativamente; o resultado operacional poderá ser o requisito estadual mais exigente. | Registrar que a aplicação decorre de compatibilidade e competência, não da fórmula automática 'a mais restritiva vence'. | Alta | Condicional | https://portal.stf.jus.br/constituicao-supremo/artigo.asp?abrirArtigo=24&abrirBase=CF | O STF admite, em linha de princípio, proteção estadual adicional, mas examina competência, finalidade e harmonia com as normas gerais. |
| 10 | 6 | Ausência de norma geral federal | Não existe norma geral federal sobre a matéria concorrente? | O Estado pode exercer competência legislativa plena para atender suas peculiaridades enquanto faltar norma geral federal. | Aplicar a regra estadual válida. | Marcar a regra como exercício estadual pleno e monitorar norma federal superveniente. | Alta | Condicional | https://portal.stf.jus.br/constituicao-supremo/artigo.asp?abrirArtigo=24&abrirBase=CF | A competência estadual plena decorre do art. 24, §3º. |
| 11 | 7 | Norma federal superveniente | Surgiu norma geral federal depois da regra estadual? | A norma federal superveniente suspende a eficácia da regra estadual apenas no que for contrário; não ocorre revogação total automática. | Comparar dispositivo por dispositivo e manter a parte estadual compatível. | Emitir alerta crítico sobre conflito temporal e exigir análise comparativa. | Crítica | Sim | https://portal.stf.jus.br/constituicao-supremo/artigo.asp?abrirArtigo=24&abrirBase=CF | Aplicação do art. 24, §4º, da Constituição. |
| 12 | 8 | Competência administrativa comum | O conflito é sobre quem licencia, autoriza, aprova supressão ou executa a ação administrativa? | A Lei Complementar nº 140/2011 distribui as atribuições administrativas entre União, Estados e Municípios. Deve ser identificado o ente originariamente competente, eventual delegação e atuação supletiva. | Aplicar o procedimento e o sistema do ente competente. | Executar primeiro a regra de roteamento institucional. | Crítica | Sim | https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp140.htm | Competência administrativa não se resolve pela regra ambiental material mais rigorosa. |
| 13 | 9 | Fiscalização concorrente | Dois entes fiscalizaram ou autuaram o mesmo fato? | Todos os entes mantêm atribuição comum de fiscalização, mas a LC nº 140/2011 prevê prevalência do auto do órgão que detenha a atribuição de licenciar ou autorizar, sem eliminar a necessidade de analisar fatos, objetos e competências. | Priorizar o auto da autoridade licenciadora/autorizadora no conflito previsto em lei e investigar duplicidade. | Emitir alerta crítico de possível sobreposição ou bis in idem. | Crítica | Sim | https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp140.htm | Não interpretar como superioridade automática de auto federal ou estadual. |
| 14 | 10 | Hierarquia interna dos atos | A divergência ocorre entre lei, decreto, resolução, instrução normativa, portaria, manual ou FAQ? | O ato inferior deve respeitar o superior: Constituição; lei complementar/lei conforme competência; decreto regulamentar; resolução, instrução e portaria; manual, guia e FAQ. | Aplicar o ato superior e usar o inferior apenas para operacionalização compatível. | Classificar a natureza jurídica de cada fonte antes da comparação. | Crítica | Condicional | https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm | A posição na lista não elimina a análise de competência e da função específica do ato. |
| 15 | 11 | Especialidade | As duas normas são válidas, da mesma esfera de competência e tratam o caso em níveis diferentes de especificidade? | A norma especial rege o objeto específico, enquanto a norma geral continua aplicável de forma subsidiária e nos pontos não afastados. | Aplicar a norma especial compatível e conservar a norma geral no restante. | Mostrar ao consultor quais dispositivos são gerais e quais são especiais. | Alta | Condicional | Critério jurídico de especialidade — exigir fonte normativa específica do caso | Especialidade não salva norma editada por ente incompetente nem ato inferior contrário à lei. |
| 16 | 12 | Temporalidade | As normas válidas têm a mesma hierarquia, competência e objeto, mas foram editadas em datas diferentes? | A norma posterior pode prevalecer no ponto incompatível, observadas regras de transição, direito intertemporal, especialidade e vigência. | Aplicar a regra vigente na data do fato, do ato ou do procedimento, conforme o tema. | Construir linha do tempo normativa e não usar apenas a data de publicação mais recente. | Alta | Sim | Lei de Introdução às Normas do Direito Brasileiro e atos de vigência específicos | Em matéria sancionadora e processual, a temporalidade exige tratamento próprio. |
| 17 | 13 | Cumulação compatível | As regras federal e estadual tratam aspectos diferentes e podem ser cumpridas juntas? | Não há conflito verdadeiro. As obrigações devem ser aplicadas cumulativamente. | Gerar um checklist integrado sem escolher vencedor. | Classificar como regras complementares. | Alta | Não | Constituição Federal e Lei Complementar nº 140/2011 | Exemplo: regra federal de proteção material e procedimento estadual de protocolo. |
| 18 | 14 | Conflito aparente de terminologia | As bases usam nomes ou status diferentes para o mesmo objeto? | A divergência terminológica deve ser resolvida pelo conceito jurídico, ato constitutivo e autoridade da informação, e não pelo nome do campo. | Mapear sinônimos, preservar o termo original e adotar um termo padronizado no Regente. | Emitir alerta de harmonização, sem criar conflito jurídico inexistente. | Média | Condicional | Dicionário de entidades e atos de cada matriz | Exemplos: cadastrado, protocolado, autorizado, vigente e regularizado não são equivalentes. |
| 19 | 15 | Conflito não resolvido | Os critérios anteriores não permitem definir uma aplicação segura? | O Regente não deve eleger automaticamente uma regra vencedora. | Exibir as duas regras, seus dispositivos, competência, data, especialidade, impactos e limitações. | Emitir alerta crítico; exigir decisão fundamentada do consultor e revisão jurídica quando o efeito for material. | Crítica | Sim | Governança Regente | A conclusão deve ser registrada como interpretação profissional, não como resultado automático do sistema. |
| 20 | 16 | Princípio da maior proteção | É possível usar simplesmente 'a norma mais protetiva vence'? | Não como regra geral. A maior proteção é argumento relevante, mas depende de competência constitucional, harmonia com normas gerais, proporcionalidade, finalidade e validade do ato. | Usar como critério complementar, nunca como primeiro ou único critério. | Emitir alerta quando o sistema tentar escolher apenas pelo grau de restrição. | Crítica | Sim | https://portal.stf.jus.br/constituicao-supremo/artigo.asp?abrirArtigo=24&abrirBase=CF | Uma norma estadual mais restritiva pode ser válida; outra pode ser inconstitucional por invadir competência ou contrariar norma geral. |

### 2.2 Aplicação por tema — `A23:F32`

> Aplicação por tema das matrizes

| Linha Excel | Tema da matriz | Regra federal/nacional | Regra estadual | Critério principal | Resultado padrão do Regente | Exemplo de conflito a evitar |
|---|---|---|---|---|---|---|
| 26 | CAR e florestas | Código Florestal e normas gerais nacionais | Procedimentos, cadastros e complementações estaduais | Competência concorrente + norma geral + suplementação | Aplicar o mínimo nacional e a complementação estadual compatível | Estado redefinir conceito federal ou reduzir proteção mínima. |
| 27 | Outorga e recursos hídricos | Critérios nacionais e legislação federal sobre águas | Gestão e outorga das águas de domínio estadual | Domínio do corpo hídrico + competência constitucional + sistema nacional | Roteamento pelo domínio e aplicação do procedimento do órgão competente | Escolher regra federal apenas porque a ANA é federal. |
| 28 | Licenciamento ambiental | Normas gerais nacionais e LC 140 | Tipologias e procedimentos estaduais válidos | Competência administrativa + compatibilidade com normas gerais | Aplicar o rito do ente competente sem reduzir requisito nacional obrigatório | Estado simplificar procedimento de forma incompatível com norma nacional. |
| 29 | Unidades de conservação | SNUC e regras nacionais | SEUC, ato de criação e plano estadual | Norma geral + ato específico da unidade + órgão gestor | Aplicar cumulativamente e priorizar o ato/plano específico válido | Tratar APA estadual como menos relevante que regra federal genérica. |
| 30 | Embargos e sanções | Decreto federal apenas no âmbito competente; normas gerais e LC 140 | Lei e processo sancionador estadual | Competência do órgão + fato + objeto + art. 17 da LC 140 | Separar autos e priorizar o da autoridade licenciadora/autorizadora quando a hipótese legal ocorrer | Concluir que todo auto federal prevalece sobre estadual. |
| 31 | Cavidades, TI e arqueologia | Regimes federais específicos e competências da União | Normas estaduais complementares de licenciamento e proteção | Competência federal específica + complementação ambiental estadual | Cumular exigências compatíveis e consultar o órgão federal competente | Norma estadual dispensar manifestação federal exigida. |
| 32 | Dados geoespaciais e manuais | Metodologia ou base federal | Metodologia ou base estadual | Autoridade da fonte + escala + finalidade + ato jurídico relacionado | Não existe prevalência pela esfera; escolher a fonte adequada ao objeto e declarar divergências | Usar layer federal generalizado para invalidar limite estadual oficial mais preciso. |

### 2.3 Controle cumulativo — `99_Controle_Versao!A1:H5`

> CONTROLE CUMULATIVO DE VERSÃO — REGENTE

| Linha Excel | Versão | Data | Escopo | Correção aplicada | Comportamento oficial | Responsável pela decisão | Status | Observação |
|---|---|---|---|---|---|---|---|---|
| 4 | v02 | 2026-08-05 00:00:00 | Todas as abas | Conversão de restrições internas do Regente em alertas críticos, sem interrupção automática do fluxo. | O alerta não impede avanço, conclusão, protocolo ou mudança de status; exige ciência, justificativa e registro. | Consultor responsável pelo caso | Aplicado | Termos que descrevem restrições jurídicas ou operacionais externas reais foram preservados como fatos. |
| 5 | v03 | 2026-08-05 00:00:00 | Todas as matrizes | Inclusão do protocolo de conflito entre regras federais, estaduais e atos de diferentes níveis. | Sem vencedor automático por esfera ou maior restrição. Resolver por competência, hierarquia, norma geral/suplementar, especialidade, temporalidade e objeto. | Consultor responsável; revisão jurídica nos conflitos materiais. | Aplicado | Criada a aba 98_Conflitos_Regras com matriz decisória e exemplos por tema. |

### 2.4 Conflito de governança a resolver, sem alterar a transcrição

`99!E4` afirma que alerta não impede avanço, conclusão, protocolo ou status. O plano v1.1 e o padrão 8 exigem suspensão do **uso de claim/regra afetado por conflito material**, preservando a decisão fundamentada humana. Essas duas coisas não são equivalentes: uma autorização de avançar o fluxo não publica uma conclusão sem lastro. Além disso, `98!F19` exige revisão jurídica em efeito material e a cartorária conserva comandos de bloqueio. **Referência de execução já definida: v1.1.** Preservar a tensão documental, implementar a suspensão do uso afetado e a trilha de decisão sem reescrever o original nem liberar consumo automático. Não pedir novamente que a Ísis confirme o contrato já aprovado; uma eventual exceção precisa de caso concreto e fonte.

## 3. INS-003 — matriz cartorária


Arquivo `Matriz_Normativa_Cartoraria_Regente_FED_GO_MG_SP_MT_v1.xlsx`, 85015 bytes, SHA-256 `47f1a70cb15b6f06edcaf4ad81e716fc761d3f8ffd6a819d39e445deb6f0c1b9`. Data-base declarada em `00_Leia-me!B3`: 05/08/2026. `B2` diz “1.0 – baseline implementável”; isso é rótulo da autora, não comprovação de executor, fonte vigente ou implantação.

| Aba | Linhas não vazias (incluem cabeçalhos) | Colunas físicas | Registros de domínio |
|---|---|---|---|
| 00_Leia-me | 18 | 2 | metadados/painel/listas |
| 01_Matriz_Normativa | 175 | 26 | 174 regras |
| 02_Regras_Regente | 175 | 13 | 174 projeções dos mesmos IDs |
| 03_Documentos_Rurais | 37 | 10 | 36 documentos/classes |
| 04_Dicionario_Campos | 51 | 7 | 50 campos |
| 05_Fontes_Controle | 39 | 9 | 38 fontes |
| 06_Dashboard | 16 | 8 | metadados/painel/listas |
| _Listas | 6 | 4 | metadados/painel/listas |

### 3.1 Colunas literais das abas de dados

| Aba | Cabeçalhos na ordem original |
|---|---|
| 01_Matriz_Normativa | 1: ID_Regra; 2: Jurisdição; 3: UF; 4: Nível_Hierárquico; 5: Norma; 6: Dispositivo; 7: Tema; 8: Especialidade; 9: Documento_Entrada; 10: Ato_Pretendido; 11: Princípio_Registral; 12: Regra_Operacional; 13: Requisito_ou_Validação; 14: Exceção_ou_Ressalva; 15: Evidência_a_Extrair; 16: Condição_Lógica; 17: Ação_do_Regente; 18: Saída_Controlada; 19: Bloqueia_Automação; 20: Revisão_Humana; 21: Risco; 22: Status_Normativo; 23: Vigência_ou_Referência; 24: Data_Base; 25: Fonte_Oficial_URL; 26: Observações_de_Implementação |
| 02_Regras_Regente | 1: Rule_ID; 2: Prioridade; 3: Jurisdição; 4: Trigger_Documental; 5: IF_Condição; 6: THEN_Ação; 7: ELSE_Conduta; 8: Saída_Controlada; 9: Bloqueio; 10: Revisão_Humana; 11: Risco; 12: Fundamento; 13: Fonte_Oficial_URL |
| 03_Documentos_Rurais | 1: Classe; 2: Documento; 3: Especialidade_ou_Órgão; 4: Função_Jurídica; 5: Prova_Domínio; 6: Fonte_de_Verdade_para; 7: Campos_Críticos; 8: Conflitos_Comuns; 9: Comando_Regente; 10: Risco |
| 04_Dicionario_Campos | 1: Grupo; 2: Campo; 3: Tipo; 4: Obrigatório_Quando; 5: Regra_de_Validação; 6: Saída_ou_Uso; 7: Sensibilidade |
| 05_Fontes_Controle | 1: ID_Fonte; 2: Jurisdição; 3: Fonte; 4: Objeto; 5: URL_Oficial; 6: Versão_ou_Atualização_Identificada; 7: Frequência_de_Verificação; 8: Risco_de_Desatualização; 9: Ação_de_Monitoramento |
| _Listas | 1: Risco; 2: Status; 3: SimNãoCond; 4: Jurisdição |

Leia-me: pares A/B de metadados. Dashboard: indicadores em A4:F4, comparação por jurisdição em A8:G8 e controle de fontes em A16:D16; fórmulas de painel não são condições executáveis de regra.

### 3.2 Quantidade, UF, finalidade e relação com as 325

| UF literal (`01!C2:C175`) | Regras |
|---|---|
| FED | 83 |
| GO | 22 |
| MG | 27 |
| SP | 24 |
| MT | 18 |

Total: **174 IDs únicos**, presentes uma vez em cada uma das abas 01 e 02. FED=83 reúne 61 Federal, 7 Federal/CNJ e 15 “Federal – regra de interpretação”; GO=22, MG=27, SP=24, MT=18. Não extrapolar isso para outras UFs. As 174 condições `02!E2:E175` são texto iniciado por SE, não DSL tipada validada. **0 executáveis prontas; 174 condições em texto.** IF/THEN/ELSE melhora a estrutura editorial, mas não define sozinho predicados, campos, nulidade ou vigência.

Ato pretendido é o eixo de finalidade **literal da cartorária**, não o `DemandType` do produto. Contagem completa de `01!J2:J175`: Identificar competência e autoridade: 1; Qualificação institucional: 7; Qualquer: 3; Registro/averbação: 1; Diligência: 6; Registrar: 10; Averbar: 1; Registrar/averbar: 4; Abrir/analisar: 1; Registrar/retificar: 2; Parcelar/remembrar/transferir: 2; Qualificar: 1; Sanear/impugnar: 1; Controlar prioridade: 1; Retificar: 5; Cancelar/revisar: 1; Reconhecer usucapião: 1; Adjudicar: 1; Unificar: 1; Averbar/cancelar: 6; Alienação/constituição de direito real: 1; Transferência: 3; Identificar proprietário: 2; Alienar/onerar: 5; Transferência causa mortis: 1; Lavratura/registro/consulta: 4; Qualificação nacional: 1; Validação: 1; Averbação/cancelamento: 1; Rastreabilidade: 1; Interoperabilidade: 1; Tratamento de dados: 1; Autenticidade: 1; Alienar/prometê-lo/hipotecar/arrendar/desmembrar: 1; Parcelar/desmembrar: 1; Ato registral rural: 1; Parcelamento/remembramento/transferência: 1; Adquirir/arrendar: 1; Aquisição/arrendamento: 4; Ato sobre imóvel rural: 1; Aquisição/regularização: 1; Ratificar registro: 1; Diagnóstico ambiental/dominial: 1; Analisar/averbar restrição: 1; Constituir/cancelar garantia: 1; Registrar título/garantia: 1; Registrar garantia: 3; Constituir/executar: 1; Explorar imóvel: 1; Registrar/analisar: 1; Transferir/regularizar: 1; Identificar titular: 1; Identificar parcela: 1; Reconstruir situação: 1; Interpretar vigência: 1; Alienar/onerar/parcelar: 2; Diagnóstico: 2; Saneamento: 3; Pré-qualificação: 1; Lavrar alienação/oneração: 3; Lavrar escritura: 2; Desmembrar/alienar parcela: 1; Alienar fração: 1; Lavrar título: 2; Constituir/cancelar afetação: 1; Usucapião extrajudicial: 3; Validar: 4; Aplicar norma estadual: 4; Parcelar/unificar: 2; Registrar/transferir: 2; Transferir: 3; Protocolar/acompanhar: 4; Calcular custo: 4; Qualificação: 2; Alienar: 1; Sanear: 1; Registrar aquisição judicial: 1; Registrar aquisição: 2; Desmembrar/remembrar: 2; Averbar geo/abrir matrícula: 1; Receber/protocolar: 1; Parcelar/alienar parcela: 1; Averbar informação: 1; Averbar RL: 2; Averbar número CAR: 1; Impugnar exigência: 1; Lavrar ato: 1; Alienar/parcelar: 1; Registrar/impugnar: 1; Averbar geo/transferir: 1; Registrar para conservação: 1; Registrar contrato: 1; Atualizar motor: 1.

Os 174 IDs cartorários não coincidem com os IDs das 325 linhas v01. Portanto são **499 ocorrências de regra, com namespace de matriz**, não 499 regras independentes já deduplicadas/homologadas. As abas 01/02 não entram duas vezes. Há sobreposição semântica comprovável que impede concluir independência a partir de IDs distintos:

| Tema | Cartorária (linha = posição do ID na aba 01) | Matriz v01 relacionada | Relação / limite |
|---|---|---|---|
| CAR não prova domínio | FED-059, `01!A60` | M01 REG-BR-CAR-002, linha 6; M02 REG-FUN-001, linha 5 | Mesmo limite probatório; conciliar fundamento, escopo e saída, não executar alertas duplicados. |
| Certificação não reconhece domínio | FED-072, `01!A73` | M02 REG-FUN-001/006, linhas 5/10 | Complementa certificação e confronto com certidão; não fundir automaticamente condições distintas. |
| Atos cancelados permanecem históricos | FED-077, `01!A78`; FED-031, `01!A32` | M02 REG-FUN-005/025, linhas 9/29 | História e atualidade se relacionam, mas cancelamento registral não é cancelamento SIGEF. |
| Sucessão/representação | FED-037, `01!A38` | M02 tema Titularidade, REG-FUN-008, linha 12 | Cartorária acrescenta ato/título; divergência de titular não supre cadeia sucessória. |

Relação integral regra-a-regra: **trabalho de mapeamento da engenharia**, iniciado pelas correspondências acima e pelas famílias na cobertura. Só devolver à Ísis ambiguidade específica não resolvida pelas fontes, depois de apresentar regras/células confrontadas. Contagem não comprova validade jurídica das referências. `00_Leia-me!B7` limita a matriz à pré-qualificação e exclui substituição de registrador, Corregedoria, parecer ou consulta à versão oficial vigente. A referência hierárquica em B8 não pode sobrepor silenciosamente o protocolo detalhado da aba 98.

## 4. INS-001/002 — oito matrizes completas e divergências

### 4.1 Identidade dos membros e totais


| Pacote/matriz | Membro XLSX | Bytes | SHA-256 |
|---|---|---|---|
| v01/M1 | BASES DA REGULARIZAÇÃO\1.Matriz_Regulatoria_CAR_Preenchida_Federal_GO_SP_MG_MT.xlsx | 129588 | 0f78db470ace9f7043c629cfda1c673361dadec1c88ec7295b3af302237f90a9 |
| v01/M2 | BASES DA REGULARIZAÇÃO\2.Matriz_Fundiaria_Cadastral_Federal_GO_SP_MG_MT_Preenchida (1).xlsx | 112744 | 0892c44232f373da794064298ec2283bc3edf9be040b05f8a6a52d0764b6a7c0 |
| v01/M3 | BASES DA REGULARIZAÇÃO\3.Matriz_Uso_Cobertura_Solo_Desmatamento_Imagens_Federal_GO_SP_MG_MT_Preenchida.xlsx | 91129 | 7fed8ee23ef656e47f743b86bd8b7fa27c38845b8a847d8631c0914ef955bace |
| v01/M4 | BASES DA REGULARIZAÇÃO\4.Matriz_Geoambiental_Hidrografia_Recursos_Hidricos_Federal_GO_SP_MG_MT_Preenchida.xlsx | 121989 | 44f3729a66070dfcc3154c492363c2701c64175b2dc2f1537b2eb0ad055b84d7 |
| v01/M5 | BASES DA REGULARIZAÇÃO\5.Matriz_Outorga_Seguranca_Barragens_Federal_GO_SP_MG_MT_Preenchida.xlsx | 136732 | a1133b3c7ba4ec65c475be242a4905711d9e5c7b81d87a5f362efefac56c89f3 |
| v01/M6 | BASES DA REGULARIZAÇÃO\6.Matriz_Relevo_Solos_Geologia_Vegetacao_Federal_GO_SP_MG_MT_Preenchida.xlsx | 162590 | eb41e7223b8489cf23306a055252fa4eadb923fb3f2e1998438aec5ea5680e93 |
| v01/M7 | BASES DA REGULARIZAÇÃO\7.Matriz_Embargos_Autuacoes_Sancoes_Federal_GO_SP_MG_MT_Preenchida.xlsx | 179712 | 14bb632a46b822e2f830f708e521567cb9e18b49933fc3ac68e3c3e25b31fe4f |
| v01/M8 | BASES DA REGULARIZAÇÃO\8.Matriz_Areas_Protegidas_Cavidades_Territorios_Especiais_Federal_GO_SP_MG_MT_Preenchida.xlsx | 176683 | 973c82fae2f9d7c4ef0bc8b4873964fca81fc36196b1fd157c1d46c2373630a3 |
| v03 | Matriz_Areas_Protegidas_Cavidades_Territorios_Especiais_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 186041 | a1798b022c88997c8a7e518e9db43ba0fa8c0caff60f756a4b62fca2ccee0eea |
| v03 | Matriz_Embargos_Autuacoes_Sancoes_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 188879 | 6f6da32306d658505d2f53596aa9e480937c40d09c20351b052b5a247fd21609 |
| v03 | Matriz_Fundiaria_Cadastral_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 121966 | 903232f96d74dc63860f134540ae6c9ec0b920ae8779c3bda000a37cd464e470 |
| v03 | Matriz_Geoambiental_Hidrografia_Recursos_Hidricos_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 131378 | c8a65c290584a05d2d41609cec8baebe07807e0966c1368d2f942b906c7b423f |
| v03 | Matriz_Outorga_Seguranca_Barragens_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 146297 | 75dbdd5e6575d16f5675311985c300ee4724be151dcb01a6fa99e43f5de5e28d |
| v03 | Matriz_Regulatoria_CAR_Federal_GO_SP_MG_MT_v03_2026-08-05.xlsx | 77811 | c8019ec2cd7df2691d1770ff2d9f3d660520417dadb2ff69e592932a4fc4244a |
| v03 | Matriz_Relevo_Solos_Geologia_Vegetacao_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 152609 | ea1432170f66af9d7ddf1f45f7c301786eec055fc28d78bac113f9ecd87260ae |
| v03 | Matriz_Uso_Cobertura_Solo_Desmatamento_Imagens_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 100375 | 33da045dea3feb7388e43fe6680a0f1ab9e3f027aee1263f75c730b46b035d41 |

**v01: 159 abas, 4.318 linhas não vazias somadas entre todas as abas**, incluindo títulos, cabeçalhos e registros de vários tipos. As 325 regras são somente as linhas com ID das oito abas de regras, não `max_row`, linhas estilizadas ou tamanho do arquivo. **v03: 175 abas, 4.393 linhas não vazias**, incluindo as 16 abas 98/99 acrescentadas. As dimensões físicas somam 14.215 linhas no v01 e 14.502 no v03. O número histórico **14.056 se reproduz numericamente por 14.215 − 159 (uma linha por aba)**, mas inclui vazios/formatação e não representa 14.056 registros de conteúdo. As cópias CAR/fundiária antes lidas em `curadoria_isis` têm hashes idênticos aos membros M01/M02 do RAR; a identidade agora está estabelecida, sem declarar qual edição a autora pretende publicar.

| Matriz | Aba de regras | Regras | BR | Federal | Todas | GO | MG | SP | MT |
|---|---|---|---|---|---|---|---|---|---|
| M01 | 06_Regras_Negocio | 37 | 10 | 0 | 0 | 7 | 9 | 5 | 6 |
| M02 | 12_Regras_Regente | 28 | 19 | 0 | 0 | 2 | 2 | 2 | 3 |
| M03 | 13_Regras_Regente | 32 | 0 | 0 | 20 | 3 | 3 | 3 | 3 |
| M04 | 15_Regras_Regente | 42 | 0 | 0 | 27 | 4 | 3 | 4 | 4 |
| M05 | 19_Regras_Regente | 47 | 0 | 1 | 33 | 3 | 4 | 3 | 3 |
| M06 | 18_Regras_Regente | 46 | 0 | 0 | 37 | 2 | 1 | 2 | 4 |
| M07 | 22_Regras_Regente | 48 | 0 | 2 | 38 | 2 | 2 | 2 | 2 |
| M08 | 25_Regras_Regente | 45 | 0 | 0 | 43 | 1 | 0 | 0 | 1 |
| TOTAL |  | 325 | 29 | 3 | 198 | 24 | 24 | 21 | 26 |

**BR, Federal e Todas são valores originais diferentes; não foram convertidos nem multiplicados por UF.** “Todas” não certifica cobertura nacional. Seleção de território/órgão/objetivo e vigência ainda exige curadoria.

**325 ocorrências, 320 IDs textuais distintos.** Colisões abaixo; a chave de origem deve incluir matriz e versão, além do ID. Não sobrescrever por `rule_id` isolado.

| ID repetido | Localizadores |
|---|---|
| REG-GOV-001 | M05/19_Regras_Regente!A50; M07/22_Regras_Regente!A50; M08/25_Regras_Regente!A46 |
| REG-GOV-002 | M05/19_Regras_Regente!A51; M07/22_Regras_Regente!A51; M08/25_Regras_Regente!A47 |
| REG-GOV-003 | M07/22_Regras_Regente!A52; M08/25_Regras_Regente!A48 |

### 4.2 Colunas e divergência de vocabulário

| Matriz / aba | Cabeçalhos, na ordem original |
|---|---|
| M01 / 06_Regras_Negocio | 1: ID da regra; 2: UF; 3: Tema; 4: Descrição da regra; 5: Tipo de regra; 6: Entrada necessária; 7: Condição lógica; 8: Resultado esperado; 9: Mensagem ao consultor; 10: Fonte normativa; 11: Dispositivo; 12: Grau de confiança; 13: Exige decisão profissional; 14: Pode ser automatizada; 15: Status de implementação; 16: Responsável pela validação; 17: Última revisão; 18: Observações |
| M02 / 12_Regras_Regente | 1: ID da regra; 2: UF; 3: Tema; 4: Entradas necessárias; 5: Condição lógica; 6: Resultado/ação do sistema; 7: Severidade; 8: Mensagem ao consultor; 9: Fonte normativa/operacional; 10: Automatização; 11: Exige decisão profissional?; 12: Status; 13: Critério de aceite |
| M03 / 13_Regras_Regente | 1: ID regra; 2: UF; 3: Tema; 4: Entrada necessária; 5: Condição lógica; 6: Ação do Regente; 7: Severidade; 8: Mensagem ao consultor; 9: Fonte; 10: Automatizável; 11: Decisão profissional; 12: Status |
| M04 / 15_Regras_Regente | 1: ID regra; 2: UF; 3: Tema; 4: Entrada necessária; 5: Condição lógica; 6: Ação do Regente; 7: Severidade; 8: Mensagem ao consultor; 9: Fonte; 10: Automatizável; 11: Decisão profissional; 12: Status |
| M05 / 19_Regras_Regente | 1: ID regra; 2: UF; 3: Eixo; 4: Tema; 5: Entrada necessária; 6: Condição lógica; 7: Ação do Regente; 8: Severidade; 9: Mensagem ao consultor; 10: Fonte; 11: Automatizável; 12: Decisão profissional; 13: Status |
| M06 / 18_Regras_Regente | 1: ID regra; 2: UF; 3: Eixo; 4: Tema; 5: Entrada necessária; 6: Condição lógica; 7: Ação do Regente; 8: Severidade; 9: Mensagem ao consultor; 10: Fonte; 11: Automatizável; 12: Decisão profissional; 13: Status |
| M07 / 22_Regras_Regente | 1: ID regra; 2: UF; 3: Tema; 4: Entrada necessária; 5: Condição lógica; 6: Ação do Regente; 7: Severidade; 8: Mensagem ao consultor; 9: Fonte; 10: Automatizável; 11: Advogado; 12: Técnico ambiental; 13: Status |
| M08 / 25_Regras_Regente | 1: ID regra; 2: UF; 3: Tema; 4: Entrada necessária; 5: Condição lógica; 6: Ação do Regente; 7: Severidade; 8: Mensagem ao consultor; 9: Fonte; 10: Automatizável; 11: Advogado; 12: RT/Especialista; 13: Status |

Mapeamento proposto, sem importação: `ID da regra`/`ID regra` → identificador de origem; `Resultado esperado`/`Resultado/ação do sistema`/`Ação do Regente` precisam separar efeito esperado de comando; `Pode ser automatizada`/`Automatização`/`Automatizável` são avaliações autorais, não flags de regra publicada. `Grau de confiança` de M01 **não é** `Severidade` de M02–08. M05/M06 têm **Eixo e Tema simultaneamente**, então não são sinônimos. `Exige decisão profissional`, sua variante com “?”, `Decisão profissional`, `Advogado`, `Técnico ambiental` e `RT/Especialista` não podem ser achatados num único booleano que apague profissão/competência.

**“Tipo de regra” com condição: não reproduzido nestes bytes.** Varredura de células/cabeçalhos nas 16 matrizes e cartorária encontrou o cabeçalho somente em M01 v01/v03, E4. Em v01 E5:E41 há 37 rótulos de tipo; em v03 E5 há “Alerta”. `Interseção > 0.` aparece em M02 E15/E25, mas E4 diz **Condição lógica**, portanto está na coluna declarada. A condição ocupa E nas matrizes sem Eixo e F nas matrizes M05/M06; um leitor posicional baseado na CAR confundiria esses campos. Isso é explicação possível do relato, **não causa comprovada**. Pedir à Ísis arquivo/hash/aba/célula do caso alegado antes de corrigir dados ou declarar o defeito resolvido.

### 4.3 Executável versus prosa

Critério desta inspeção: executável pronta exige expressão em linguagem restrita reconhecida, operandos tipados e ligados ao contexto, tratamento de ausências/unidades, ação definida e versão/fonte aplicável. Texto que parece comparação ou rótulo “Sim” em Automatizável não atende sozinho. Não foi executada nem publicada nenhuma regra.


| Matriz | Condições preenchidas | Executáveis prontas | Texto/prosa ou expressão informal | Automatização declarada pela autora |
|---|---|---|---|---|
| M01 | 37 | 0 | 37 | Sim: 21; Parcialmente: 15; Não: 1 |
| M02 | 28 | 0 | 28 | Sim: 22; Parcialmente: 6 |
| M03 | 32 | 0 | 32 | Sim: 27; Parcial: 5 |
| M04 | 42 | 0 | 42 | Sim: 38; Parcial: 4 |
| M05 | 47 | 0 | 47 | Sim: 37; Parcial: 10 |
| M06 | 46 | 0 | 46 | Sim: 37; Parcial: 9 |
| M07 | 48 | 0 | 48 | Sim: 35; Parcial: 13 |
| M08 | 45 | 0 | 45 | Sim: 32; Parcial: 13 |

**Total v01: 325 preenchidas, 0 executáveis prontas, 325 textuais (incluem pseudocondições com operadores).** Por exemplo M01 G15 `UF = GO`; M02 E15 `Interseção > 0.`; M04 E29 `Vazão >1 L/s`. São candidatas à formalização, não código. Não se presume que as 325 exijam julgamento subjetivo: algumas comparações podem ser convertidas após vinculação de campo/unidade/ausência/tempo. As abas de regras v01 não contêm fórmulas Excel; ausência de fórmula é observação auxiliar, não o critério de executabilidade.

### 4.4 Contagem por objetivo e tema, sem inventar taxonomia

**Não existe coluna Objetivo nem associação com os 16 `DemandType` nas oito abas de regras. Portanto 325/325 linhas permanecem sem vínculo explícito ao objetivo canônico.** Não registrar zero regras aplicáveis nem chamar o Tema de objetivo aprovado. A tabela seguinte entrega a contagem integral por matriz × agrupador autoral × UF, que pode fundamentar a decisão da Ísis. Usa Eixo onde existe (M05/M06), Tema nas demais. A soma é 325; não é contagem de cobertura MVP homologada.

| Matriz | Agrupador | Valor literal | Regras | UF literal: quantidade |
|---|---|---|---|---|
| M01 | Tema | Obrigatoriedade do CAR | 1 | BR: 1 |
| M01 | Tema | Natureza do CAR | 1 | BR: 1 |
| M01 | Tema | Elegibilidade ao PRA | 1 | BR: 1 |
| M01 | Tema | Prazo de adesão ao PRA | 1 | BR: 1 |
| M01 | Tema | Versão do cadastro | 1 | BR: 1 |
| M01 | Tema | Duplicidade | 1 | BR: 1 |
| M01 | Tema | Unidade cadastral | 1 | BR: 1 |
| M01 | Tema | Status oficial | 1 | BR: 1 |
| M01 | Tema | Notificação | 1 | BR: 1 |
| M01 | Tema | Responsabilidade técnica | 1 | BR: 1 |
| M01 | Tema | Sistema competente | 3 | GO: 1; SP: 1; MG: 1 |
| M01 | Tema | Migração | 1 | GO: 1 |
| M01 | Tema | Camadas obrigatórias | 1 | GO: 1 |
| M01 | Tema | Vinculação do proprietário | 1 | GO: 1 |
| M01 | Tema | Prioridade de análise | 1 | GO: 1 |
| M01 | Tema | Cancelamento | 2 | GO: 1; SP: 1 |
| M01 | Tema | Compensação de RL | 1 | GO: 1 |
| M01 | Tema | Pós-validação/PRA | 1 | SP: 1 |
| M01 | Tema | Resposta a pendência | 1 | SP: 1 |
| M01 | Tema | Responsável técnico | 1 | SP: 1 |
| M01 | Tema | CAR 2.0 | 1 | MG: 1 |
| M01 | Tema | Norma procedimental vigente | 1 | MG: 1 |
| M01 | Tema | Prazo de resposta | 1 | MG: 1 |
| M01 | Tema | Bloqueio de retificação durante análise | 1 | MG: 1 |
| M01 | Tema | Alteração de titularidade | 1 | MG: 1 |
| M01 | Tema | Reabertura após validação | 1 | MG: 1 |
| M01 | Tema | Tolerâncias de área e sobreposição | 1 | MG: 1 |
| M01 | Tema | Cancelamento irreversível no sistema | 1 | MG: 1 |
| M01 | Tema | Abrangência do CAR Digital | 1 | MT: 1 |
| M01 | Tema | Discordância geográfica | 1 | MT: 1 |
| M01 | Tema | Análise manual | 1 | MT: 1 |
| M01 | Tema | Complementação | 1 | MT: 1 |
| M01 | Tema | PRA no fluxo digital | 1 | MT: 1 |
| M01 | Tema | Taxas | 1 | MT: 1 |
| M02 | Tema | Autoridade da fonte | 1 | BR: 1 |
| M02 | Tema | CCIR | 1 | BR: 1 |
| M02 | Tema | SNCR | 1 | BR: 1 |
| M02 | Tema | CNIR | 1 | BR: 1 |
| M02 | Tema | SIGEF | 2 | BR: 2 |
| M02 | Tema | Área | 1 | BR: 1 |
| M02 | Tema | Titularidade | 1 | BR: 1 |
| M02 | Tema | Geometria | 1 | BR: 1 |
| M02 | Tema | Vértices | 1 | BR: 1 |
| M02 | Tema | Assentamento | 1 | BR: 1 |
| M02 | Tema | Beneficiário | 1 | BR: 1 |
| M02 | Tema | Cláusula resolutiva | 1 | BR: 1 |
| M02 | Tema | Terra pública | 1 | BR: 1 |
| M02 | Tema | Terra devoluta | 1 | BR: 1 |
| M02 | Tema | Regularização estadual | 1 | GO: 1 |
| M02 | Tema | Georreferenciamento estadual | 1 | GO: 1 |
| M02 | Tema | Área ITESP | 1 | SP: 1 |
| M02 | Tema | Lei 11.600/2003 | 1 | SP: 1 |
| M02 | Tema | Competência | 1 | MG: 1 |
| M02 | Tema | Terra arrecadada | 1 | MG: 1 |
| M02 | Tema | Modalidade INTERMAT | 1 | MT: 1 |
| M02 | Tema | Acervo AtoM | 1 | MT: 1 |
| M02 | Tema | INTERGEO × SIGEF | 1 | MT: 1 |
| M02 | Tema | Temporalidade | 1 | BR: 1 |
| M02 | Tema | Rastreabilidade | 1 | BR: 1 |
| M02 | Tema | Grau de certeza | 1 | BR: 1 |
| M02 | Tema | Fonte ausente | 1 | BR: 1 |
| M03 | Tema | Rastreabilidade | 1 | Todas: 1 |
| M03 | Tema | Imagem | 1 | Todas: 1 |
| M03 | Tema | Nuvem | 1 | Todas: 1 |
| M03 | Tema | Escala | 1 | Todas: 1 |
| M03 | Tema | MapBiomas | 1 | Todas: 1 |
| M03 | Tema | Alerta | 2 | Todas: 2 |
| M03 | Tema | Legalidade | 1 | Todas: 1 |
| M03 | Tema | Autorização | 1 | Todas: 1 |
| M03 | Tema | Autoria | 1 | Todas: 1 |
| M03 | Tema | Área consolidada | 2 | Todas: 2 |
| M03 | Tema | Regeneração | 2 | Todas: 2 |
| M03 | Tema | Fogo | 3 | Todas: 3 |
| M03 | Tema | Árvores isoladas | 1 | GO: 1 |
| M03 | Tema | DAI | 1 | GO: 1 |
| M03 | Tema | Competência | 1 | GO: 1 |
| M03 | Tema | Inventário | 1 | SP: 1 |
| M03 | Tema | Painel Verde | 1 | SP: 1 |
| M03 | Tema | Cerrado | 1 | SP: 1 |
| M03 | Tema | IDE | 1 | MG: 1 |
| M03 | Tema | Intervenção | 1 | MG: 1 |
| M03 | Tema | Estágio sucessional | 1 | MG: 1 |
| M03 | Tema | PMCV | 1 | MT: 1 |
| M03 | Tema | Uso consolidado | 1 | MT: 1 |
| M03 | Tema | Histórico | 1 | MT: 1 |
| M03 | Tema | Versão | 1 | Todas: 1 |
| M03 | Tema | Ausência de resultado | 1 | Todas: 1 |
| M03 | Tema | Conclusão | 1 | Todas: 1 |
| M04 | Tema | Hidrografia | 1 | Todas: 1 |
| M04 | Tema | Drenagem modelada | 1 | Todas: 1 |
| M04 | Tema | Nascente | 1 | Todas: 1 |
| M04 | Tema | Perenidade | 1 | Todas: 1 |
| M04 | Tema | APP | 1 | Todas: 1 |
| M04 | Tema | Escala | 1 | Todas: 1 |
| M04 | Tema | Domínio | 3 | Todas: 3 |
| M04 | Tema | Status | 3 | Todas: 3 |
| M04 | Tema | Validade | 1 | Todas: 1 |
| M04 | Tema | Ponto de uso | 1 | Todas: 1 |
| M04 | Tema | Vazão | 1 | Todas: 1 |
| M04 | Tema | Finalidade | 1 | Todas: 1 |
| M04 | Tema | Poço | 2 | Todas: 2 |
| M04 | Tema | Barragem | 2 | Todas: 2 |
| M04 | Tema | Disponibilidade | 1 | Todas: 1 |
| M04 | Tema | Qualidade | 1 | Todas: 1 |
| M04 | Tema | Somatório | 1 | Todas: 1 |
| M04 | Tema | Unidades | 1 | Todas: 1 |
| M04 | Tema | Uso insignificante | 3 | GO: 1; SP: 2 |
| M04 | Tema | Barramento insignificante | 1 | GO: 1 |
| M04 | Tema | Norma | 1 | GO: 1 |
| M04 | Tema | Sistema | 1 | GO: 1 |
| M04 | Tema | Armazenamento | 1 | SP: 1 |
| M04 | Tema | DVI | 1 | SP: 1 |
| M04 | Tema | Uso superficial | 2 | MG: 1; MT: 1 |
| M04 | Tema | Poço tubular | 1 | MG: 1 |
| M04 | Tema | Área de restrição | 1 | MG: 1 |
| M04 | Tema | Uso subterrâneo | 1 | MT: 1 |
| M04 | Tema | Bacia crítica | 1 | MT: 1 |
| M04 | Tema | Divisão hidrográfica | 1 | MT: 1 |
| M04 | Tema | Contradição | 1 | Todas: 1 |
| M04 | Tema | Rastreabilidade | 1 | Todas: 1 |
| M04 | Tema | Campo | 1 | Todas: 1 |
| M05 | Eixo | Outorga | 26 | Todas: 16; Federal: 1; GO: 2; SP: 2; MG: 3; MT: 2 |
| M05 | Eixo | Barragens | 19 | Todas: 15; GO: 1; SP: 1; MG: 1; MT: 1 |
| M05 | Eixo | Governança | 2 | Todas: 2 |
| M06 | Eixo | Relevo | 9 | Todas: 9 |
| M06 | Eixo | Solos | 6 | Todas: 6 |
| M06 | Eixo | Solos/vegetação | 1 | GO: 1 |
| M06 | Eixo | Geologia | 8 | Todas: 8 |
| M06 | Eixo | Vegetação | 16 | Todas: 8; GO: 1; SP: 2; MG: 1; MT: 4 |
| M06 | Eixo | Integrado | 6 | Todas: 6 |
| M07 | Tema | Autuação | 1 | Todas: 1 |
| M07 | Tema | Consulta | 1 | Todas: 1 |
| M07 | Tema | Processo | 1 | Todas: 1 |
| M07 | Tema | Norma temporal | 1 | Todas: 1 |
| M07 | Tema | Sujeito | 1 | Todas: 1 |
| M07 | Tema | Autoria | 1 | Todas: 1 |
| M07 | Tema | Descrição | 1 | Todas: 1 |
| M07 | Tema | Materialidade | 1 | Todas: 1 |
| M07 | Tema | Geometria | 1 | Todas: 1 |
| M07 | Tema | Área | 1 | Todas: 1 |
| M07 | Tema | Duplicidade | 1 | Todas: 1 |
| M07 | Tema | Intimação | 1 | Todas: 1 |
| M07 | Tema | Prazo | 1 | Todas: 1 |
| M07 | Tema | Defesa | 1 | Todas: 1 |
| M07 | Tema | Recurso | 1 | Todas: 1 |
| M07 | Tema | Definitividade | 1 | Todas: 1 |
| M07 | Tema | Trânsito | 1 | Todas: 1 |
| M07 | Tema | Prescrição | 2 | Todas: 2 |
| M07 | Tema | Nulidade | 1 | Todas: 1 |
| M07 | Tema | Conciliação | 1 | Todas: 1 |
| M07 | Tema | Solução legal | 1 | Federal: 1 |
| M07 | Tema | Autocomposição | 1 | GO: 1 |
| M07 | Tema | Atendimento Ambiental | 1 | SP: 1 |
| M07 | Tema | Competência CETESB | 1 | SP: 1 |
| M07 | Tema | Taxa de expediente | 1 | MG: 1 |
| M07 | Tema | Temporalidade | 1 | MT: 1 |
| M07 | Tema | Embargo | 5 | Todas: 5 |
| M07 | Tema | Descumprimento | 1 | Todas: 1 |
| M07 | Tema | Embargo rural | 1 | Federal: 1 |
| M07 | Tema | Embargo e TCACM | 1 | GO: 1 |
| M07 | Tema | Base geográfica | 1 | MT: 1 |
| M07 | Tema | Multa | 1 | Todas: 1 |
| M07 | Tema | Cálculo | 1 | Todas: 1 |
| M07 | Tema | Pagamento | 2 | Todas: 1; MG: 1 |
| M07 | Tema | Parcelamento | 1 | Todas: 1 |
| M07 | Tema | PRAD | 1 | Todas: 1 |
| M07 | Tema | Execução | 1 | Todas: 1 |
| M07 | Tema | Regularização | 1 | Todas: 1 |
| M07 | Tema | Reparação | 1 | Todas: 1 |
| M07 | Tema | Rastreabilidade | 1 | Todas: 1 |
| M07 | Tema | Contradição | 1 | Todas: 1 |
| M07 | Tema | Dados pessoais | 1 | Todas: 1 |
| M08 | Tema | UC proposta | 1 | Todas: 1 |
| M08 | Tema | CNUC | 1 | Todas: 1 |
| M08 | Tema | Limite | 1 | Todas: 1 |
| M08 | Tema | Geometria aproximada | 1 | Todas: 1 |
| M08 | Tema | Plano de manejo | 1 | Todas: 1 |
| M08 | Tema | Revisão parcial | 1 | Todas: 1 |
| M08 | Tema | Zona de amortecimento | 1 | Todas: 1 |
| M08 | Tema | APA | 1 | Todas: 1 |
| M08 | Tema | Proteção integral | 1 | Todas: 1 |
| M08 | Tema | Consulta gestor | 1 | Todas: 1 |
| M08 | Tema | Manifestação condicionada | 1 | Todas: 1 |
| M08 | Tema | Licenciamento | 1 | Todas: 1 |
| M08 | Tema | RPPN proposta | 1 | Todas: 1 |
| M08 | Tema | RPPN criada | 1 | Todas: 1 |
| M08 | Tema | Plano RPPN | 1 | Todas: 1 |
| M08 | Tema | RPDS/PNC | 1 | GO: 1 |
| M08 | Tema | RPPN MT | 1 | MT: 1 |
| M08 | Tema | CANIE negativo | 1 | Todas: 1 |
| M08 | Tema | Potencial espeleológico | 1 | Todas: 1 |
| M08 | Tema | Distância a cavidade | 1 | Todas: 1 |
| M08 | Tema | Entrada de caverna | 1 | Todas: 1 |
| M08 | Tema | Prospecção | 1 | Todas: 1 |
| M08 | Tema | Relevância | 1 | Todas: 1 |
| M08 | Tema | Regime jurídico | 1 | Todas: 1 |
| M08 | Tema | Fase TI | 1 | Todas: 1 |
| M08 | Tema | TI em estudo | 1 | Todas: 1 |
| M08 | Tema | Aldeia | 1 | Todas: 1 |
| M08 | Tema | Impacto | 1 | Todas: 1 |
| M08 | Tema | Consulta Funai | 1 | Todas: 1 |
| M08 | Tema | Certificação quilombola | 1 | Todas: 1 |
| M08 | Tema | RTID | 1 | Todas: 1 |
| M08 | Tema | Titulação parcial | 1 | Todas: 1 |
| M08 | Tema | Consulta comunitária | 1 | Todas: 1 |
| M08 | Tema | SICG/CNSA negativo | 1 | Todas: 1 |
| M08 | Tema | Ficha FCSA | 1 | Todas: 1 |
| M08 | Tema | Pesquisa arqueológica | 1 | Todas: 1 |
| M08 | Tema | Achado fortuito | 1 | Todas: 1 |
| M08 | Tema | Manifestação Iphan | 1 | Todas: 1 |
| M08 | Tema | Área prioritária | 1 | Todas: 1 |
| M08 | Tema | Reserva da Biosfera | 1 | Todas: 1 |
| M08 | Tema | Ramsar | 1 | Todas: 1 |
| M08 | Tema | Rastreabilidade | 1 | Todas: 1 |
| M08 | Tema | Contradição | 1 | Todas: 1 |
| M08 | Tema | Distância | 1 | Todas: 1 |
| M08 | Tema | Múltiplos regimes | 1 | Todas: 1 |

### 4.5 Comparação v03 e CAR: 37 versus um exemplo, não três

| Matriz v03 | Aba | Linhas com ID |
|---|---|---|
| Matriz_Areas_Protegidas_Cavidades_Territorios_Especiais_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 25_Regras_Regente | 45 |
| Matriz_Embargos_Autuacoes_Sancoes_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 22_Regras_Regente | 48 |
| Matriz_Fundiaria_Cadastral_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 12_Regras_Regente | 28 |
| Matriz_Geoambiental_Hidrografia_Recursos_Hidricos_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 15_Regras_Regente | 42 |
| Matriz_Outorga_Seguranca_Barragens_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 19_Regras_Regente | 47 |
| Matriz_Regulatoria_CAR_Federal_GO_SP_MG_MT_v03_2026-08-05.xlsx | 06_Regras_Negocio | 1 |
| Matriz_Relevo_Solos_Geologia_Vegetacao_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 18_Regras_Regente | 46 |
| Matriz_Uso_Cobertura_Solo_Desmatamento_Imagens_Federal_GO_SP_MG_MT_Preenchida_v03_2026-08-05.xlsx | 13_Regras_Regente | 32 |

Nas sete matrizes não CAR, os conjuntos de IDs são preservados (288 ocorrências). Na CAR v03, `06_Regras_Negocio` tem **quatro linhas não vazias**: 1=título, 2=descrição, 4=cabeçalho, 5=um exemplo. A contagem “três regras” não se reproduz; não contar título/descrição/cabeçalho como regra. Total do ZIP: **289 ocorrências**, versus 325 no RAR.

O único ID CAR v03 é `REG-BR-CAR-001`, **reutilizado com outro conteúdo**: no v01, D5 trata obrigatoriedade do CAR e G5 é “Imóvel classificado como rural e CAR não localizado”; no v03, D5 começa “Exemplo estrutural: identificar múltiplos cadastros potencialmente relacionados ao mesmo imóvel.” e G5 é “Mais de um cadastro relacionado ao imóvel”. J5/K5 (fonte/dispositivo) estão vazios; R5 diz “Exemplo metodológico; não considerar regra validada até vincular fonte e procedimento.” Não interpretar igualdade de ID como identidade semântica. Os outros 36 IDs CAR v01 estão ausentes; isso **não comprova revogação nem substituição deliberada**. O tema duplicidade aproxima o exemplo de `REG-BR-CAR-006` v01, sem estabelecer linhagem autorizada.

O diretório também contém CAR v05; não foi promovida a versão vigente nem substituiu o ZIP v03 expressamente solicitado. **Engenharia antes de perguntar:** abrir e comparar a v05/controle de versão disponível; só depois apresentar à autora uma lacuna concreta de linhagem/publicação que os arquivos não resolvam. O nome com `(1)` da fundiária não decide versão: os 28 IDs existem também na v03, mas o controle 99 declara mudanças de comportamento.

### 4.6 Reprodutibilidade e fronteira

Para repetir: verificar SHA-256 dos três originais; enumerar XLSX do RAR/ZIP sem salvar sobre originais; abrir com `data_only=False`; nas oito matrizes contar apenas A5:Amax não vazio nas abas de regras identificadas acima; na cartorária contar IDs de A2:A175 e comparar o conjunto da aba 02; agrupar pela coluna UF de cada cabeçalho, preservando rótulos. Para o protocolo, comparar as matrizes completas de valores das abas 98/99 e transcrever A4:J20, A25:F32 e A3:H5 com localizadores. A contagem de regras não depende de filtros de visibilidade, dimensões formatadas ou cálculos do dashboard. Nenhuma ingestão foi feita.


## 5. TRs e manuais — INS-004

**Inventário integral não concluído; leitura focal realizada.** `MANUAIS_SEMAD.rar` foi aberto em memória para qualificar os produtos da cobertura. Os sete TRs de recuperação inicial/conclusiva, plantio compensatório, memorial de mineração, flora, controle de cheias e PCA específico de cemitério estão identificados por nome original/página na [cobertura, seção 3.2](COBERTURA_MVP_v1.md#32-templates-e-trs-especificar-o-serviço-sem-antecipar-execução). Os 224 arquivos/102 TRs/450 MB continuam sendo volume descrito no [plano:486](PLANO_DIRETOR_REGENTE_v1.1.md#L486), não contagem integral nova. O inventário SEMAD de maio não foi transplantado como leitura deste pacote.

- **Peça governada, órgão e itens exigidos:** determinados para os sete TRs referenciados na cobertura; restante do pacote ainda não concluído. Um roteiro de plantio selecionado retornou texto com glifos/códigos ilegíveis; falha de leitura técnica, não falta de resposta da Ísis.
- **Duplicados nomeados:** não determinados; nomes parecidos não bastam, e hash igual identifica bytes iguais, não necessariamente duas versões juridicamente equivalentes.
- **PDF de 41 MB, nome:** não identificado. Nos arquivos soltos da pasta local `legislacao/`, o maior encontrado tem 28.431.063 bytes; isso não identifica o arquivo do pacote ausente.

Ficha obrigatória por item a produzir quando disponível: caminho/nome original; hash/tamanho/páginas; espécie (TR/manual/formulário); título interno; órgão; UF/rito; peça/atividade governada; edição/data; itens obrigatórios **com página/seção**; condicionais; anexos; fonte oficial; qualidade de leitura/cobertura; relação com outros itens. Duplicata exata por hash, versão por comparação de conteúdo e quase duplicata por revisão, nunca por nome apenas. PDF grande será inventariado localmente por texto/páginas; falha ou cobertura parcial ficará explícita, sem OCR pago automático.

Destino proposto: checklist de peça e método do Redator versionados por órgão/rito; texto de consulta é apoio. Não transformar obrigação do TR em chunk sem estrutura nem considerar enum `prad` prova de conformidade.

## 6. SEI — INS-006 e erro material

**Confirmado em fonte oficial:** o [Decreto numerado 9.710/2020](https://legisla.casacivil.go.gov.br/pesquisa_legislacao/103356/decreto-9710) é ato do **Governador do Estado de Goiás**, não decreto federal. Consulta em 17/09/2026. A esfera dessa referência está comprovada; a localização de sua ocorrência no Parecer 84 ainda não está.

| Citação a conferir | Origem da informação nesta sessão | Marca / ação |
|---|---|---|
| “Decreto Federal 9.710/2020” atribuído ao Parecer 84 | Pedido e [plano:488](PLANO_DIRETOR_REGENTE_v1.1.md#L488); Parecer original não lido | **ERRO DE ESFERA SE CONFIRMADA A TRANSCRIÇÃO**. Preservar literal do parecer, vincular observação de erro e referência estadual verificada. Não emendar o original. |
| Demais normas/dispositivos citados no Parecer 84 e nos outros arquivos do SEI | `PROCESSO SEI.rar` localizado em RegenteLandpage; conteúdo ainda não auditado nesta revisão | **NÃO INVENTARIADOS**; não há lista fictícia de citações. |

Antes da ingestão: abrir parecer e localizar todas as citações por página/trecho; comparar número, ano, espécie, esfera, dispositivo e versão; separar citação literal de referência resolvida; marcar divergências materiais e suspender uso automático do claim dependente até revisão. Não concluir sobre o mérito do parecer apenas pelo erro material. CNH e demais PII do pacote não irão para o repositório; análise usa referências mínimas, com acesso contextual da consultoria.

## 7. SIGCAR — INS-007

| Item descrito | Natureza / destino | O que falta comprovar antes de ingerir |
|---|---|---|
| IN 23/2025 | **Norma** → catálogo normativo/corpus, com órgão, espécie, número, ano, publicação, vigência e versão | Arquivo oficial exato, texto/alterações, hash e escopo. “IN 23/2025” sem órgão não é chave suficiente. |
| Seis roteiros por mensagem de erro | **Procedimento** → índice por sistema/versão, mensagem literal/código de erro, contexto, pré-condições, passos e resultado esperado | Nomes dos seis arquivos, mensagens, páginas, tela/versão, limites e data. Pacotes de roteiros localizados em RegenteLandpage, ainda não abertos nesta revisão. |
| Demais arquivos do pacote de 21 | Natureza ainda não inventariada | Classificação por conteúdo, duplicatas, vínculos e cobertura de leitura; não forçar todos em norma ou roteiro. |

Busca por erro retorna roteiro compatível com versão/contexto; ausência retorna não localizado com razão. O roteiro não substitui a IN para fundamentação jurídica, e a IN não vira receita de interface. Uma atualização de portal deve versionar procedimento sem alterar retroativamente a norma citada.

## 8. Oito padrões externos contra o código atual

Os três documentos externos não foram lidos. A análise abaixo aplica **os padrões fornecidos no pedido**, sem afirmar fidelidade integral ao outro projeto. **Não incorporar família/workspace como fronteira de tenant**: consultoria permanece a unidade de isolamento, [evidence.py:22](../../app/services/evidence.py#L22).

Custo: estimativa preliminar em dias de engenharia de uma pessoa, incluindo testes focados, **não orçamento/compromisso**; exclui espera por insumos, curadoria de centenas de regras, homologação da Ísis e integrações pagas. Faixas se sobrepõem e não devem ser somadas. Dependências externas tornam o prazo de calendário indeterminado.

| Padrão | Já existe — evidência atual | Falta / avaliação | Custo preliminar e incremento | Aceite necessário |
|---|---|---|---|---|
| 1. Estados que não fingem valor | Seis K e validação em [evidence.py:76](../../app/schemas/evidence.py#L76); status de revisão separado. | Estender às identidades/cadastros/entradas; `Property.has_embargo` ainda default falso, [property.py:32](../../app/models/property.py#L32). `declined` é recusa no atendimento, não sétimo K nem `nao_aplicavel`. | 3–6 dias; incremento 2, com auditoria dos consumidores. | Falta não vira zero/falso; recusa, desconhecido e não aplicável sobrevivem a persistência e contexto. |
| 2. Declarado × confirmado | Staging conserva valor extraído e decisão; atributos literal/normalizado separados em [evidence.py:57](../../app/schemas/evidence.py#L57). | `normalized` não significa confirmado; `aceito` valida decisão sobre versão, não transforma declaração em fato extrínseco. Falta estado/lastro de confirmação uniforme nos cadastros e APIs. | 4–8 dias; incremento 2. | Declaração CAR permanece declaração após aceite; consulta independente pode confirmar predicado sem apagar o literal. |
| 3. Relação, papel e efeito jurídico separados | Representantes em [client_representative.py:47](../../app/models/client_representative.py#L47); adquirentes/transmitentes em [observacao_registral.py:321](../../app/services/observacao_registral.py#L321). | Pessoa independente, participação, espólio, poderes e eficácia; `titular_atual` não basta para adjudicar cadeia completa. Ontologia deste incremento fornece o mapa. | 10–20 dias; incremento 2, depende INS-003/Q-06/10. | Contratante, vendedor, adquirente, inventariante e titular não se confundem; relação não inventa efeito. |
| 4. Regras executáveis separadas de textos recuperáveis | Catálogo de texto/embeddings em [knowledge_catalog.py:303](../../app/services/knowledge_catalog.py#L303); contrato aceita referências versionadas em [evidence.py:93](../../app/schemas/evidence.py#L93); ADR-042 propõe separação. | Catálogo de regras, DSL restrita, predicados, estados indeterminado/conflito, publicação/rollback e testes. Nenhum texto de planilha ativado; tabela `RegulatoryIssueCatalog` não é o motor jurídico. | 15–30 dias para infraestrutura e uma cobertura delimitada; incremento 4. Curadoria das 325 depende da escolha de cobertura e formalização, não incluída nesta faixa. | Mesmas entradas/versionamento reproduzem resultado; regra sem conceito/fonte não publica; RAG não decide o disparo. |
| 5. Citação por claim, localizador e versão | `Afirmacao.fontes`, evidência/versão em [stage_output.py:175](../../app/schemas/stage_output.py#L175); `SourceRef` tem página/hash em linha 138; conclusões têm premissas em [evidence.py:99](../../app/schemas/evidence.py#L99). | Cobertura de todos os claims de peças, localizador obrigatório ou falta explícita; versões documentais/corpus completas; ligação precisa a dispositivo, não só norma encontrada no texto. Evaluator atual [citation_evaluator.py:303](../../app/services/citation_evaluator.py#L303) não substitui prova semântica. | 5–10 dias; incrementos 2/4/5. | Cada claim recupera fonte exata e versão; claim sem lastro não ganha citação por proximidade textual. |
| 6. Busca híbrida com filtro obrigatório antes do ranking | `knowledge_catalog.search` monta `WHERE` antes do `ORDER BY` vetorial, [knowledge_catalog.py:347](../../app/services/knowledge_catalog.py#L347). Mantém tenant/global e modelo de embedding. | Não é busca híbrida lexical+vetorial; filtros de aplicabilidade opcionais; fallback do agente retira UF/demanda. Corrigir conjunto elegível obrigatório, razão de vazio e ranking só dentro dele. Detalhe abaixo. | 8–15 dias; incremento 4; avaliação de corpus pode ampliar esforço. | Filtro nunca relaxa; norma relevante por similaridade mas inelegível não aparece; vazio traz razão; sentinela não libera pesquisa geral. |
| 7. Exclusão como workflow auditável | Soft-delete com auditoria em [documents.py:539](../../app/api/v1/documents.py#L539); hard-delete auditado em [cascade_delete.py:130](../../app/services/cascade_delete.py#L130); RESTRICT e versões no Incremento 1. | Orquestração durável/idempotente por índices, caches, objetos e filas; conciliar retenção de prova e eliminação autorizada. Soft-delete sozinho não confirma expurgo. [Dívida #207](../REGISTRO_DIVIDAS.md#L2171) continua relevante. | 10–20 dias; preparar ao modelar retenção no incremento 2, concluir conforme publicação controlada. | Inventário de dependências, bloqueio/retencão justificados, recibos por destino, retries e prova de que tarefa antiga não ressuscita dados. |
| 8. Divergência material abre review_task e suspende claim/regra | Invalidação preserva revisão, [evidence.py:138](../../app/services/evidence.py#L138); gate em linha 270; conflito de UF explicitado no envelope. | Não há workflow geral de tarefa de revisão normativa/material nem suspensão versionada de regra. Ranking vetorial não é adjudicação. Criar tarefa com versões conflitantes, decisão/motivo e reavaliação dos dependentes. | 7–14 dias; base no incremento 2, regras no 4. | Conflito material bloqueia uso do claim/regra afetado; resolução humana preserva alternativas e reavalia dependentes; não suspende todo o catálogo indiscriminadamente. |

### 8.1 RAG: defeito confirmado e alcance real

Em [legislacao.py:312](../../app/agents/legislacao.py#L312), `nao_identificado` e outras sentinelas viram `demand_filter=None`. Em [legislacao.py:334](../../app/agents/legislacao.py#L334), `min_similarity=0.0`. Em [legislacao.py:346](../../app/agents/legislacao.py#L346), a sequência pode retirar UF e demanda até ambas ausentes. **Os filtros de tenant, tipo legislation e espaço de embedding permanecem**; o defeito é perder o escopo obrigatório de aplicabilidade, não um bypass de tenant provado por essas linhas.

**Mudança de contexto desde o pedido:** esse é o caminho legado de `LegislacaoAgent`. Na main inspecionada, [BaseAgent.run:134](../../app/agents/base.py#L134) encaminha para execução conectada; [connected_agents.py:152](../../app/services/connected_agents.py#L152) verifica manifesto antes do provider; [agent_capabilities.py:22](../../app/services/agent_capabilities.py#L22) retorna falta de método-base para Legislação. Logo o fallback não está demonstrado como percurso ativo do Incremento 1. **Continua dívida de código a resolver antes de reativar esse método, não correção já feita.**

Contrato proposto para o incremento 4:

1. Autorizar consultoria/caso e resolver objetivo, território, competência, ato, data de referência e famílias de fontes. Distinguir restrição obrigatória de preferência de ranking.
2. Sem dados mínimos, retornar `contexto_insuficiente`; sem fonte elegível, `sem_fonte_elegivel`; verificação operacional falha retorna `falha_de_busca`. Nunca um array vazio sem razão nem relaxamento implícito.
3. Aplicar predicados obrigatórios **antes** de ambos os rankings, lexical e vetorial, e também na recuperação por chave. A fonte nacional/federal pode ser elegível para GO por política explícita, não por remoção da UF. Vigência desconhecida não vira vigente automaticamente.
4. Combinar rankings apenas sobre candidatos elegíveis; registrar filtros, versões, scores e método. Chave normativa declarada pela regra tem resolução exata; similaridade não substitui norma ausente.
5. Materialidade de conflito abre tarefa de revisão e suspende uso dos claims/regras afetados. Ranking não determina qual fonte juridicamente prevalece.

Nada disso foi implementado neste PR documental.

## Perguntas para a Ísis

Registro consolidado, revisto após procurar nas Fichas 07/08, spec v0.1, manifesto, BASE_REGULATORIA, enum/classificador, filtros, casos reais e TRs. **Pergunta já respondida foi retirada da fila humana.** `PENDENTE-ISIS` só permanece com lacuna específica e evidência da busca; leitura, formalização, implementação e teste são tarefas de engenharia. IDs preservados para rastrear a correção da revisão anterior, não números de dívida 200–299.

| ID / estado | Resposta encontrada ou pergunta residual exata | Busca / evidência e encaminhamento |
|---|---|---|
| Q-ISIS-01 — RESPONDIDA | Jobson: novo CAR, GO, relatório preliminar + escopo; certidão atual ausente é lacuna. | [Plano:523](PLANO_DIRETOR_REGENTE_v1.1.md#L523) e [plano:831](PLANO_DIRETOR_REGENTE_v1.1.md#L831). Não pedir reconfirmação. |
| Q-ISIS-02 — RESPONDIDA | MVP1 termina no contrato; rota Federal+GO. Catálogo tem 16 demandas, CAR é entrada prioritária. | [Spec:75](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md#L75), [spec:103](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md#L103), [process.py:32](../../app/models/process.py#L32), [manifesto:54](../manifesto/01-VISAO_PRODUTO.md#L54). Corpus e matrizes mais amplos não mudam o recorte. |
| Q-ISIS-03 — ENGENHARIA | Objetivos/misto/não identificado já têm roteiros; famílias de regras por objetivo estão na cobertura. Falta formalizar vínculos versionados e predicados por regra, não descobrir o catálogo com a Ísis. | [intake_classifier.py:73](../../app/services/intake_classifier.py#L73), linhas 404/432 para triagem, seção 4 deste inventário e [cobertura](COBERTURA_MVP_v1.md#4-matriz-preenchida-por-objetivo). Só abrir pergunta posterior com regra/célula ambígua concreta. |
| Q-ISIS-04 — PENDENTE-ISIS / COV-P01 | Qual erro máximo em m²/ha será aceito ao reproduzir a área do KMZ de Jobson a partir das coordenadas completas e método registrado? | Procurados plano:356/603, mergulho:363, `property_audit.py:157` e ocorrências de KMZ/tolerância em docs/app/tests. Resultado ≈2,7250 ha, referência documental 2,6893 ha e denominador estão respondidos; não consta tolerância de reprodução. O limiar de divergência de 1% não a substitui. [Busca documentada](COBERTURA_MVP_v1.md#6-registro-da-busca-antes-de-qualquer-pendência). |
| Q-ISIS-05 — RESPONDIDA | Rota/Proposta/Contrato; relatório preliminar+escopo na prova Jobson; TRs especificam serviços técnicos pós-contrato. | [Ficha 07:74](../fichas/FICHA_07_WORKSPACE_REGENCIA.md#L74), [spec:79](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md#L79), [redator:50](../../app/agents/redator.py#L50), sete TRs originais na cobertura §3.2. Não pedir lista genérica de peças. |
| Q-ISIS-06 — RESPONDIDA / ENGENHARIA | Pessoa principal, representante PJ e inventariante já estão definidos; implementar sem confundir parte, papel e efeito. | [Spec:85](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md#L85), [Ficha 08:77](../fichas/FICHA_08_BASE_DADOS_CONFERENCIA.md#L77), cartorária FED-037 e ontologia. Requisito específico de um ato deve ser resolvido na regra/fonte antes de perguntar. |
| Q-ISIS-07 — RESPONDIDA | Preservar Eixo e Tema distintos (coexistem em M05/M06), confiança separada de severidade e tipo separado de ação. | Cabeçalhos e valores literais das oito abas em §4.2; [spec:124](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md#L124) já separa dimensões do achado. Não há autorização para achatar escalas. |
| Q-ISIS-08 — ENGENHARIA ANTES DE PERGUNTAR | Reconciliar o exemplo CAR v03 com v01 e examinar a v05 já localizada antes de perguntar qual edição vale. Não ativar o exemplo sem fonte nem revogar IDs ausentes. | v01/v03 abertos, hash e diff em §4.5; v05 ainda não comparada. A lacuna de leitura disponível não será devolvida à autora como escolha cega de arquivo. |
| Q-ISIS-09 — PENDENTE-ISIS, localização específica | Qual arquivo/hash/aba/célula mostra texto de condição sob o cabeçalho “Tipo de regra”? | Procuradas as 16 matrizes v01/v03 e cartorária: só CAR E4 tem esse cabeçalho, com rótulos em E5:E41/v03 E5; M02 E15 está corretamente sob Condição lógica. §4.2 registra método e resultado. Não corrigir dados por hipótese nem pedir reexplicação da taxonomia. |
| Q-ISIS-10 — ENGENHARIA | Completar correspondências e detectar duplicação semântica regra-a-regra antes de pedir revisão de uma ambiguidade específica. | INS-003 aberta; colunas A/J/P/Q/S/T e exemplos FED-059/072/077/037 em §3; famílias vinculadas na cobertura. A existência de trabalho de mapeamento não torna o escopo pendente. |
| Q-ISIS-11 — REFERÊNCIA DE EXECUÇÃO DEFINIDA | A v1.1 rege execução: avanço de fluxo não publica claim/regra sem lastro; revisão humana é preservada. A tensão do texto 99 permanece registrada, sem reabrir a aprovação da v1.1. | §2.4 preserva 99!E4 e 98!F19; [plano:550](PLANO_DIRETOR_REGENTE_v1.1.md#L550), [spec:398](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md#L398). Exceção futura só exige pergunta se o caso concreto não for resolvido pelo contrato. |
| Q-ISIS-12 — ENGENHARIA ANTES DE PERGUNTAR | Abrir o SEI disponível e localizar a citação/página e os efeitos do erro antes de formular pergunta de mérito. | `PROCESSO SEI.rar` localizado, ainda não auditado; esfera do decreto já conferida em §6. Não pedir à Ísis para inventariar o arquivo no lugar da engenharia. |
| Q-ISIS-13 — RESPONDIDA | Fonte inelegível não entra; vazio tem razão; filtro não relaxa; conflito material suspende o uso do claim/regra afetado e abre revisão. | Pedido do Incremento 0, padrão 8 e contrato proposto em §8.1; [spec:306](../auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md#L306), protocolo 98, ordem 15. Implementar e apresentar divergência concreta se surgir, não perguntar se a regra já fixada deve valer. |
| Q-ISIS-14 — ENGENHARIA ANTES DE PERGUNTAR | Versionamento/preservação e revisão humana estão fixados; detalhar publicação/catálogo R2 e examinar controles de fonte antes de pedir decisão sobre ferramenta/cadência. | Controle 99 transcrito; INS-003 `05_Fontes_Controle` tem frequência e ação de monitoramento; decisão do André determina R2. Não tratar escolha técnica de importador como bloqueio da cobertura. |
| Q-ISIS-15 — ENGENHARIA | Continuar leitura/deduplicação do pacote de TRs; itens já lidos estão ligados ao serviço na cobertura. Não pedir “quais TRs” sem completar a inspeção. | Sete originais/páginas qualificados na cobertura §3.2; um roteiro com falha de extração; inventário integral pendente em §5. |
| Q-ISIS-16 — ENGENHARIA ANTES DE PERGUNTAR | Abrir normas e roteiros SIGCAR disponíveis, extrair órgão/versão/mensagem/código e só então apontar lacuna concreta. | Pacotes localizados, ainda não auditados; §7. Não transferir à Ísis a leitura dos originais já fornecidos. |
| Q-ISIS-19 — PENDENTE-ISIS | As coletâneas têm índice, ou você tem a lista dos atos que compilou em cada uma (tipo, número, ano)? | Medido: só 2 das 32 coletâneas têm sumário no início; os atos dentro delas ficam entre 177 e 368 conforme o critério. A lista encurta a revisão de fronteiras do desmembramento. [ADR-075](../adr/075-zona-normativa-hierarquia-e-recuperacao.md#pendente-com-a-ísis); [ZONA_NORMATIVA_RAG §3](ZONA_NORMATIVA_RAG.md#3-desmembramento-das-coletâneas). |
| Q-ISIS-18 — PENDENTE-ISIS, vai junto com Q-ISIS-04 | As 223 fichas de tipologia SEMAD (A1.x, Y1.x…) são `exigencia` ou `procedimento` como nível de autoridade? Uma resposta para a classe inteira, não por ficha. | Medido no corpus: 191 tipologias gravadas como `norma_procedural` e 28 como `matriz_ipe`; só o nome do arquivo as separa das 6 matrizes IPE verdadeiras. [ADR-070 §Pendente com a Ísis](../adr/070-modelo-de-dados-alvo.md#pendente-com-a-ísis); [MIGRACAO §7](MIGRACAO_MODELO_DADOS.md#7-zona-normativa--o-que-muda-no-corpus-atual). Decisão do André: não decidir sem ela. |
| Q-ISIS-17 — FUTURO, NÃO BLOQUEIA MVP | Consumidor advogado ambiental confirmado; ontologia prevê papel, autoridade, peça e precedente. O desenho deve apresentar permissões concretas para revisão futura, sem pedir novamente objetivos amplos. | Decisão do André e [ontologia §10](ONTOLOGIA_REGENTE_v1.md#10-decisão-do-andré--consumidor-jurídico-futuro-e-acervo-permanente). Nenhuma implementação agora. |

## 9. Estado de entrega e parada

| Bloco | Estado desta revisão |
|---|---|
| A — Ontologia | Vocabulário mínimo e mapa de colisões, acrescidos de papéis de usuário, autoridade, tipos de peça e precedente para o consumidor jurídico futuro; homologação de domínio pendente. |
| B — Cobertura | 16 demandas + Jobson preenchidas com fontes por célula. MVP até contrato, Federal+GO, formatos e três casos respondidos pelas fontes. Tolerância de reprodução KMZ permanece específica; execução/homologação técnica não foram realizadas. |
| C — Insumos | INS-001/002/003 abertos: 325 linhas v01, 289 v03, 174 cartorárias; abas 98/99 transcritas. **Integral ainda aberto** em TRs, SEI, SIGCAR e decisões de domínio. Não se afirma leitura dos pacotes restantes. |
| D — Padrões | Oito padrões avaliados contra main, com lacunas, custo e aceite; comparação literal com os três documentos externos aguarda recebimento. |

O PR é documental e deve permanecer **rascunho enquanto o inventário solicitado não puder ser completado**. Não fechar o Incremento 0 nem aprovar cobertura por CI verde. Parar no PR, sem merge e sem implementar os incrementos seguintes. A homologação externa herdada em [#174](https://github.com/prosperidade/amigao/issues/174) continua no Incremento 7.
