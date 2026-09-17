# Incremento 0 — inventário dos insumos, padrões e decisões pendentes

**Data:** 17/09/2026. **Base:** `b6df7e64830361e52c84d6276c92549419d77f72`. Worktree `wt-cobertura-mvp`, branch `docs/cobertura-e-ontologia`. Escopo documental; sem ingestão, importação de regra, schema, banco, provider ou deploy. Não há nova numeração de dívida; eventuais dívidas de produto pertencem à faixa 200–299.

**Resultado da inspeção:** duas planilhas originais localizadas e abertas, 65 regras contadas; demais pacotes não disponibilizados/localizados no escopo abaixo. **Inventário integral dos insumos permanece aberto.** Os totais 325 regras, 159 abas, 14.056 linhas e 224 arquivos são referências históricas do plano, não contagem independente desta sessão. O próprio [mergulho:28](MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md#L28) declarou não ter aberto os originais.

Entregas complementares: [ontologia](ONTOLOGIA_REGENTE_v1.md) e [matriz de cobertura](COBERTURA_MVP_v1.md). A v1.1 é a referência de execução; o [ADR-042:5](../adr/ADR-042-motor-de-regras-deterministico-RASCUNHO.md#L5) continua rascunho histórico, não autorização de importação.

## 1. Proveniência, disponibilidade e método

Inspecionados arquivos versionados de `docs/`, `data/`, `app/` e nomes de arquivos locais em `curadoria_isis/`, `legislacao/`, `data/` e `Legislações Regente/` no checkout principal deste mesmo projeto. Não houve varredura de outros projetos. A pasta de curadoria também contém materiais de outro assunto, que não foram abertos. Nenhum original, PII ou arquivo pesado foi adicionado ao Git.

As duas planilhas foram lidas com `openpyxl`, `read_only=True`, sem `save`, uma passagem de valores e outra de fórmulas. Hash SHA-256 dos bytes, abas e linhas com primeira célula iniciada por `REG-` identificam a contagem reproduzível. Cabeçalhos estão na linha 4; títulos/legendas/linhas vazias não são regras. “Linhas não vazias” abaixo inclui cabeçalho e notas; não equivale a registros de domínio. Avisos de extensões de formatação do leitor não resultam em alteração do original porque não houve gravação.

| Insumo | Disponibilidade nesta sessão | O que está comprovado / o que falta |
|---|---|---|
| INS-001/002, matrizes | **Parcial:** CAR e fundiária/cadastral locais, sem marca v01/v03 no nome | Abertas e contadas; não é possível atribuir a edição apenas por aparência. Faltam pacote completo, restantes seis matrizes e v03 para comparação. |
| INS-003, cartorária | **Não localizado** | Não confundir com a fundiária/cadastral de 112.744 bytes. O plano descreve outra matriz de ~85 KB. Abas, colunas, regras e cobertura ainda desconhecidas. |
| INS-004, TRs/manuais | **Pacote de 224 não localizado** | Relatórios antigos de outro corpus SEMAD existem; não são substituto da leitura dos 224 itens do pedido. Conteúdo, duplicados e PDF de 41 MB não confirmados. |
| Protocolo de esferas, aba v03 | **Não localizado** | As duas planilhas abertas não têm aba de protocolo de conflitos. Transcrição literal bloqueada pela falta do original. |
| INS-006, SEI/ Parecer 84 | **Não localizado** | Natureza estadual do Decreto GO 9.710/2020 confirmada em fonte oficial; ocorrência/posição da citação no Parecer ainda não verificada. |
| INS-007, SIGCAR | **Não localizado** | Destinos norma/procedimento definidos; nomes, erros, páginas e integridade dos 21 arquivos/157 páginas não recontados. |
| Três documentos externos: dados/banco, RAG, segurança | **Não disponibilizados nesta sessão** | Avaliam-se os oito padrões literalmente enumerados no pedido contra o código local. Não se atribuem detalhes ou conformidade a documentos não lidos. |

**Solicitação de insumo ao André, um por vez:** pedido do caminho local do **INS-001, pacote original completo das matrizes**, enviado durante a execução e pendente de resposta. As duas cópias encontradas não eliminam a necessidade do restante do pacote. Depois desse recebimento, a fila é INS-002/v03 → INS-003 → INS-004 → INS-006 → INS-007 → documentos externos. Esta fila registra dependências, não afirma que os arquivos foram solicitados ou recebidos. Não substituir falta de arquivo por conteúdo imaginado.

## 2. Matrizes abertas — contagem real e vocabulário

### 2.1 Identidade dos arquivos

| Chave | Arquivo em `curadoria_isis/` do checkout principal | Bytes | SHA-256 | Abas / linhas não vazias totais |
|---|---|---:|---|---|
| M-CAR | `Matriz_Regulatoria_CAR_Preenchida_Federal_GO_SP_MG_MT.xlsx` | 129588 | `0f78db470ace9f7043c629cfda1c673361dadec1c88ec7295b3af302237f90a9` | 11 / 296 |
| M-FUN | `Matriz_Fundiaria_Cadastral_Federal_GO_SP_MG_MT_Preenchida (1).xlsx` | 112744 | `0892c44232f373da794064298ec2283bc3edf9be040b05f8a6a52d0764b6a7c0` | 15 / 372 |

O sufixo `(1)` **não é versão**. Q-ISIS-08 pede identificação da edição corrente e sua precedência. As contagens não são extrapoladas para o pacote de oito matrizes.

### 2.2 Abas e abrangência observada

| M-CAR: aba | Linhas não vazias | Colunas observadas |
|---|---:|---:|
| 00_Leia-me | 25 | 8 |
| 01_Bases_Sistemas | 18 | 26 |
| 02_Fontes_Normativas | 33 | 24 |
| 03_Base_x_Fonte | 33 | 19 |
| 04_Etapas_Processo | 26 | 18 |
| 05_Comparativo_UFs | 25 | 9 |
| 06_Regras_Negocio | 40 | 18 |
| 07_Docs_Geometrias | 38 | 18 |
| 08_Manuais_Instrucoes | 26 | 17 |
| 09_Historico_Atualizacoes | 17 | 15 |
| 10_Pendencias_Pesquisa | 15 | 16 |

| M-FUN: aba | Linhas não vazias | Colunas observadas |
|---|---:|---:|
| 01_Bases_Sistemas | 27 | 24 |
| 02_Catalogo_Normas | 38 | 19 |
| 03_Manuais_Instrucoes | 22 | 15 |
| 04_Base_Norma_Proced | 27 | 15 |
| 05_Etapas_Diligencia | 31 | 15 |
| 06_Dicionario_IDs | 23 | 16 |
| 07_Campos_por_Base | 28 | 12 |
| 08_Autoridade_Informacao | 20 | 10 |
| 09_Cruzamentos | 25 | 14 |
| 10_Comparativo_UFs | 21 | 7 |
| 11_Documentos_Evidencias | 25 | 13 |
| 12_Regras_Regente | 31 | 13 |
| 13_Historico_Atualizacoes | 15 | 11 |
| 14_Pendencias_Pesquisa | 17 | 13 |
| 00_LEIA_ME | 22 | 8 |

“Colunas observadas” é a largura física retornada pelo leitor, não número de conceitos canônicos. Células formatadas além do conteúdo fazem algumas abas chegarem a 250/500 linhas físicas; esse número não foi usado como total de regras.

### 2.3 Dicionário exato das colunas de regras

M-CAR, `06_Regras_Negocio!A4:R4`:

| Coluna | Nome original | Interpretação proposta / impedimento |
|---|---|---|
| A | ID da regra | Identidade de autoria; preservar, sem igualar versões. |
| B | UF | Escopo territorial declarado; `BR` não é UF nem determina competência. |
| C | Tema | Assunto; não confundir com objetivo, eixo ou ação. |
| D | Descrição da regra | Texto de autoria, não expressão executável. |
| E | Tipo de regra | Natureza de comportamento pretendido; não severidade. |
| F | Entrada necessária | Predicados a formalizar, com unidade, objeto e K. |
| G | Condição lógica | Todas preenchidas, mas texto; precisa tradução tipada/homologada. |
| H | Resultado esperado | Consequência permitida, separada de disparo/aplicabilidade. |
| I | Mensagem ao consultor | Apresentação; não define o comportamento do motor. |
| J | Fonte normativa | Chave ou texto; não pressupor FK válida em todas as linhas. |
| K | Dispositivo | Localização normativa, às vezes descrição de fluxo/governança. |
| L | Grau de confiança | Certeza atribuída pela autoria, não gravidade. |
| M | Exige decisão profissional | Governança da decisão. |
| N | Pode ser automatizada | Intenção de automação, não implementação comprovada. |
| O | Status de implementação | Valor da planilha, separado do estado técnico de publicação. |
| P | Responsável pela validação | Autoria/validação declaradas; não aceite técnico do software. |
| Q | Última revisão | Data da revisão da autoria, não vigência normativa. |
| R | Observações | Ressalvas/limites a preservar, sem converter em operador. |

M-FUN, `12_Regras_Regente!A4:M4`:

| Coluna | Nome original | Correspondência proposta / diferença |
|---|---|---|
| A | ID da regra | Identidade de autoria. |
| B | UF | Escopo, mesma cautela para `BR`. |
| C | Tema | Assunto; não há campo objetivo. |
| D | Entradas necessárias | Corresponde funcionalmente a entrada, plural não muda natureza. |
| E | Condição lógica | Texto de condição; **não é coluna Tipo de regra**. |
| F | Resultado/ação do sistema | Mistura resultado e ação: preservar e decompor com aprovação. |
| G | Severidade | Impacto/gravidade, **não sinônimo de confiança**. |
| H | Mensagem ao consultor | Texto de apresentação. |
| I | Fonte normativa/operacional | Mistura lei, manual, matriz e orientação; precisa natureza e referência resolvida. |
| J | Automatização | Intenção; valores Sim/Parcialmente. |
| K | Exige decisão profissional? | Inclui Sim/jurídica e Sim/RT: não converter para booleano perdendo papel. |
| L | Status | `Mapeada` nas 28 linhas, não `executável`. |
| M | Critério de aceite | Texto para derivar testes, não teste executado. |

Matrizes 3–8 não foram abertas; os nomes **Eixo/Ação do Regente/Severidade** para 5–8 vêm do [ADR-042:111](../adr/ADR-042-motor-de-regras-deterministico-RASCUNHO.md#L111). Sem equivalência confirmada pela autora:

- Tema/eixo podem estar em níveis diferentes de classificação; propor `eixo` + `tema`, não descartar um.
- Tipo de regra classifica o comportamento; ação especifica consequência; ambos diferem de condição.
- Confiança/certeza e severidade/impacto são eixos independentes. Não converter Alto→Alta como se fossem o mesmo atributo.
- Automatização e decisão profissional coexistem: uma regra pode automatizar uma detecção e exigir decisão humana sobre consequência.

**Campo deslocado:** nesta M-CAR, E5:E41 contém 13 rótulos de tipos/composições, nenhum texto como “Interseção > 0”. Em M-FUN não há coluna `Tipo de regra`; E contém corretamente condição conforme seu cabeçalho. O problema histórico nas outras matrizes **não foi refutado nem confirmado** por essas duas cópias. Não aplicar correção de deslocamento por posição global.

### 2.4 Contagens por regra, UF e objetivo

| Matriz / aba / linhas de regras | BR | GO | SP | MG | MT | Total / IDs distintos |
|---|---:|---:|---:|---:|---:|---:|
| M-CAR / 06_Regras_Negocio / 5–41 | 10 | 7 | 5 | 9 | 6 | 37 / 37 |
| M-FUN / 12_Regras_Regente / 5–32 | 19 | 2 | 2 | 2 | 3 | 28 / 28 |
| **Subtotal inspecionado** | **29** | **9** | **7** | **11** | **9** | **65 / 65** |

`BR` é contado literalmente, sem replicar a regra em cada UF. MS, AC e demais UFs não têm linhas territoriais próprias nessas duas abas; isso não resolve a aplicabilidade de regras nacionais.

**Por objetivo:** não existe coluna `objetivo` nas duas abas. Há 37 regras no tema amplo CAR/PRA e 28 fundiárias/cadastrais, mas isso **não permite afirmar 37 regras de novo CAR nem 28 de regularização fundiária**. M-CAR inclui retificação, cancelamento, PRA, prazo, compensação e governança; M-FUN inclui identidade, cadastro, competência e prova. A incidência por `DemandType` exige mapa muitos-para-muitos homologado (Q-ISIS-03). Contagem exata por objetivo: **não determinada**, não zero.

| Qualidade da autoria | M-CAR | M-FUN | Interpretação |
|---|---:|---:|---|
| Condições preenchidas | 37 | 28 | Presença de texto, não executabilidade. |
| Condições formais executáveis publicadas, tipadas e testadas demonstradas | 0 | 0 | Não há DSL/vinculação de predicados/versão publicada nas planilhas nem motor jurídico implantado por este trabalho. |
| Condições textuais a formalizar | 37 | 28 | Incluem fórmulas verbais e expressões curtas como `Interseção > 0.`; sem unidade/objeto/camada/semântica de desconhecido, não são execução segura. |
| Fórmulas Excel nas células das linhas de regra | 0 | 0 | Contagem com `data_only=False`; ausência de fórmula não é o único critério acima. |
| Automação declarada Sim / Parcialmente / Não | 21 / 15 / 1 | 22 / 6 / 0 | Não equivale a 43 regras implementadas. |
| Decisão profissional | Não 24; Sim 13 | Não 8; Sim 14; Sim/jurídica 5; Sim/RT 1 | Preservar qualificação profissional. |

Exemplos rastreáveis de impedimentos antes de ingerir:

| Célula/ID | Observação | Destino técnico antes de ativar |
|---|---|---|
| M-CAR `G6`, REG-BR-CAR-002 | Tentativa de concluir titularidade só pelo CAR é condição em linguagem natural. | Predicado de fonte/claim/papel e teste que bloqueia a conclusão, sem bloquear acesso ao documento. |
| M-CAR `J9:K9`, REG-BR-CAR-005 | Fonte descrita como boa prática e dispositivo como rastreabilidade. | Classificar como regra de governança, sem inventar lei ou chave normativa. |
| M-CAR `G17`, REG-GO-CAR-003 | Condição é envio de projeto; a descrição D17 contém exigências de camadas. | Não traduzir só a célula G perdendo requisitos em D/F/R. Método geoespacial e manual original necessários. |
| M-FUN `E9`, REG-FUN-005 | Situação cancelada parece simples, mas exige parcela, fonte e tempo consultados. | Predicado tipado de situação SIGEF, com desconhecido distinto de não cancelado. |
| M-FUN `E15`, REG-FUN-011 | `Interseção > 0.` | Exigir geometrias, camada/versionamento, CRS, unidade e comportamento em erro antes de aceitar a condição. |
| M-FUN `E31`, REG-FUN-027 | Divergência entre fontes de autoridades distintas. | Abrir revisão e suspender claim dependente; não resolver por maioria ou similaridade. |

**CAR v03 com 3 versus 37:** confirmado apenas o denominador desta cópia local, 37. Não há arquivo v03 inspecionado nem diff por ID; “3” permanece referência do plano. Proibido concluir que houve remoção deliberada de 34 regras ou que a v03 substitui a cópia completa sem resposta da autora.

### 2.5 Reprodutibilidade mínima, sem ingestão

Executar na worktree documental; o código abaixo apenas lê os originais do checkout principal. Não salva planilha nem usa banco:

```python
from pathlib import Path
from collections import Counter
from hashlib import sha256
from openpyxl import load_workbook

for path in sorted(Path('../curadoria_isis').glob('Matriz*.xlsx')):
    print(path.name, path.stat().st_size, sha256(path.read_bytes()).hexdigest())
    workbook = load_workbook(path, read_only=True, data_only=False)
    for sheet in workbook:
        rows = list(sheet.iter_rows(values_only=True))
        rules = [(i, row) for i, row in enumerate(rows, 1)
                 if row and str(row[0]).startswith('REG-')]
        print(sheet.title, sum(any(v is not None for v in r) for r in rows),
              len(rules), dict(Counter(r[1] for _, r in rules)))
    workbook.close()
```

## 3. Matriz cartorária — INS-003

**Bloqueado por arquivo não disponível.** Não há base para preencher abas, colunas, quantidade de regras, cobertura por UF ou sobreposição com as 325. `Matriz_Fundiaria_Cadastral...` não foi renomeada como cartorária para fechar este item artificialmente.

Ao receber: hash/versão → inventário de abas/cabeçalhos e IDs → contagem por UF/ato/objetivo → predicados de pessoa/papel, matrícula/serventia, título/registro, representação e tempo → referências normativas → correspondência por ID e conteúdo com INS-001/002. Coincidência de palavras não prova duplicação de regra; registrar equivalente, complementar, conflitante ou sem relação, com decisão da Ísis. Relação esperada de arquitetura: cartorário qualifica atos/direitos; jurídico avalia aplicabilidade/consequências. Isso ainda não é relação medida entre os arquivos.

## 4. Protocolo de conflito de esferas — aba da v03

**Transcrição literal: não realizada; original ausente.** Não se apresenta a síntese do plano como se fosse a tabela da autora. O [plano:325](PLANO_DIRETOR_REGENTE_v1.1.md#L325) menciona Constituição, competência privativa da União, competência concorrente e contradição com norma geral; faltam as linhas, condições, exceções, saídas e referências exatas da aba.

Contrato de recebimento: preservar título/aba/células, cabeçalhos, ordem e redação integral; separar transcrição de interpretação técnica; marcar células vazias como vazias; não corrigir texto do original silenciosamente. Tradução para tabela executável só depois de homologar casos de conflito/indeterminação. **Não adotar “federal sempre vence” ou “mais restritiva vence”.**

## 5. TRs e manuais — INS-004

**Não concluído por falta do pacote.** Os 224 arquivos/102 TRs/450 MB são volume descrito no [plano:486](PLANO_DIRETOR_REGENTE_v1.1.md#L486). O [inventário SEMAD de maio](../relatorios/corpus_semad_2026-05-20_inventario_preliminar.md) trata outro levantamento; nomes exemplificados ali não foram transplantados para esta lista.

- **Peça governada, órgão e itens exigidos por cada arquivo:** não determinados nesta sessão.
- **Duplicados nomeados:** não determinados; nomes parecidos não bastam, e hash igual identifica bytes iguais, não necessariamente duas versões juridicamente equivalentes.
- **PDF de 41 MB, nome:** não identificado. Nos arquivos soltos da pasta local `legislacao/`, o maior encontrado tem 28.431.063 bytes; isso não identifica o arquivo do pacote ausente.

Ficha obrigatória por item a produzir quando disponível: caminho/nome original; hash/tamanho/páginas; espécie (TR/manual/formulário); título interno; órgão; UF/rito; peça/atividade governada; edição/data; itens obrigatórios **com página/seção**; condicionais; anexos; fonte oficial; qualidade de leitura/cobertura; relação com outros itens. Duplicata exata por hash, versão por comparação de conteúdo e quase duplicata por revisão, nunca por nome apenas. PDF grande será inventariado localmente por texto/páginas; falha ou cobertura parcial ficará explícita, sem OCR pago automático.

Destino proposto: checklist de peça e método do Redator versionados por órgão/rito; texto de consulta é apoio. Não transformar obrigação do TR em chunk sem estrutura nem considerar enum `prad` prova de conformidade.

## 6. SEI — INS-006 e erro material

**Confirmado em fonte oficial:** o [Decreto numerado 9.710/2020](https://legisla.casacivil.go.gov.br/pesquisa_legislacao/103356/decreto-9710) é ato do **Governador do Estado de Goiás**, não decreto federal. Consulta em 17/09/2026. A esfera dessa referência está comprovada; a localização de sua ocorrência no Parecer 84 ainda não está.

| Citação a conferir | Origem da informação nesta sessão | Marca / ação |
|---|---|---|
| “Decreto Federal 9.710/2020” atribuído ao Parecer 84 | Pedido e [plano:488](PLANO_DIRETOR_REGENTE_v1.1.md#L488); Parecer original não lido | **ERRO DE ESFERA SE CONFIRMADA A TRANSCRIÇÃO**. Preservar literal do parecer, vincular observação de erro e referência estadual verificada. Não emendar o original. |
| Demais normas/dispositivos citados no Parecer 84 e nos outros arquivos do SEI | Originais não disponíveis | **NÃO INVENTARIADOS**; não há lista fictícia de citações. |

Antes da ingestão: abrir parecer e localizar todas as citações por página/trecho; comparar número, ano, espécie, esfera, dispositivo e versão; separar citação literal de referência resolvida; marcar divergências materiais e suspender uso automático do claim dependente até revisão. Não concluir sobre o mérito do parecer apenas pelo erro material. CNH e demais PII do pacote não irão para o repositório; análise usa referências mínimas, com acesso contextual da consultoria.

## 7. SIGCAR — INS-007

| Item descrito | Natureza / destino | O que falta comprovar antes de ingerir |
|---|---|---|
| IN 23/2025 | **Norma** → catálogo normativo/corpus, com órgão, espécie, número, ano, publicação, vigência e versão | Arquivo oficial exato, texto/alterações, hash e escopo. “IN 23/2025” sem órgão não é chave suficiente. |
| Seis roteiros por mensagem de erro | **Procedimento** → índice por sistema/versão, mensagem literal/código de erro, contexto, pré-condições, passos e resultado esperado | Nomes dos seis arquivos, mensagens, páginas, tela/versão, limites e data. Não extraídos de pacote ausente. |
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
| 4. Regras executáveis separadas de textos recuperáveis | Catálogo de texto/embeddings em [knowledge_catalog.py:303](../../app/services/knowledge_catalog.py#L303); contrato aceita referências versionadas em [evidence.py:93](../../app/schemas/evidence.py#L93); ADR-042 propõe separação. | Catálogo de regras, DSL restrita, predicados, estados indeterminado/conflito, publicação/rollback e testes. Nenhum texto de planilha ativado; tabela `RegulatoryIssueCatalog` não é o motor jurídico. | 15–30 dias para infraestrutura e uma cobertura delimitada; incremento 4. Curadoria das 325 não estimável sem originais. | Mesmas entradas/versionamento reproduzem resultado; regra sem conceito/fonte não publica; RAG não decide o disparo. |
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

Bloco consolidado. **Nenhuma pergunta foi respondida por inferência.** `PENDENTE-ISIS` representa decisão de domínio; falta de arquivo é responsabilidade de fornecimento do André e está separada na seção 1. IDs Q-ISIS não são números de dívida da faixa 200–299.

| ID / estado | Pergunta exata | Por que bloqueia / entrega afetada |
|---|---|---|
| Q-ISIS-01 — PENDENTE-ISIS | Para Jobson #25, confirma que a finalidade é **novo CAR** e a primeira entrega se limita a **relatório preliminar + escopo**, sem promessa de protocolo/conclusão dominial? Quais conclusões são permitidas com escritura, CCIR, ITR e KMZ, e quais exigem certidão atual? | Fecha limites da linha obrigatória e evita transformar lacuna em serviço ou título. Cobertura/ontologia. |
| Q-ISIS-02 — PENDENTE-ISIS | Quais pares **objetivo × UF × órgão/rito** entram no primeiro lançamento, além da linha Jobson/GO, e quais ficam expressamente não cobertos? | Enum/corpus não define compromisso do produto. Matriz de cobertura. |
| Q-ISIS-03 — PENDENTE-ISIS | Para cada linha aprovada, quais IDs/versões de regras são necessários e suficientes, com vínculo explícito a um ou mais objetivos? Qual tratamento deseja para objetivo não identificado ou misto? | Não há coluna objetivo nas duas abas abertas; bloqueia contagem por objetivo e seleção de método. |
| Q-ISIS-04 — PENDENTE-ISIS | Quais consultas/camadas, versões/datas, CRS, tolerâncias e denominador percentual devem compor o aceite de Jobson e das demais linhas espaciais? Qual resultado esperado do KMZ original? | Sem referência não se homologa cálculo, sobreposição ou diferença tolerável. Incremento 3. |
| Q-ISIS-05 — PENDENTE-ISIS | Para cada objetivo coberto, qual espécie de entrega, destinatário, TR/edição, itens obrigatórios, assinatura e critério de suficiência do relatório preliminar? | Template nominal não comprova peça correta. Redator/escopo, incremento 5. |
| Q-ISIS-06 — PENDENTE-ISIS | Confirma separar pessoa, participação, papel e efeito jurídico conforme a ontologia, inclusive espólio como sujeito contextual distinto de PF/PJ e inventariante como representante? Quais provas mínimas de poderes, fração e atualidade devem ser exigidas por ato? | Bloqueia semântica de representação/titularidade e a migração sem perda. Incremento 2. |
| Q-ISIS-07 — PENDENTE-ISIS | Tema e Eixo são níveis distintos ou equivalentes? Tipo de regra e Ação do Regente são campos distintos? Confirma manter **Confiança** separada de **Severidade**, e qual escala/definição vale para cada uma? | Evita unificação destrutiva das matrizes. Motor jurídico/importador. |
| Q-ISIS-08 — PENDENTE-ISIS | Qual arquivo/hash é a versão corrente da matriz 2, hoje encontrada com sufixo `(1)`? A CAR v03 com três regras é recorte, complemento ou substituição da cópia com 37, e qual destino de cada ID anterior? | Bloqueia versionamento e reconciliação; não permite apagar/revogar regras por ausência na nova planilha. |
| Q-ISIS-09 — PENDENTE-ISIS | Nas matrizes em que “Tipo de regra” contém condição, houve deslocamento de coluna ou uso deliberado? Para cada linha afetada, qual o valor correto e qual célula original deve ser preservada? “Bloqueio” suspende qual ação, admitindo qual decisão profissional? | Bloqueia importação e consequências do motor; as duas cópias lidas não resolvem o conjunto. |
| Q-ISIS-10 — PENDENTE-ISIS | Na matriz cartorária, quais regras cobrem título versus registro, completude da certidão, transmissão, sucessão, representação, baixa e aditivo por UF, e quais IDs correspondem ou complementam as 325 regras regulatórias? | A matriz não foi disponibilizada; bloqueia o método cartorário e seu aceite. |
| Q-ISIS-11 — PENDENTE-ISIS | Confirma a tabela integral de conflito de esferas da v03, incluindo pressupostos, exceções, referências e a saída para informação insuficiente/conflito sem solução automática? | Sem a tabela não há precedência executável; proíbe atalho federal/mais restritiva. Incremento 4. |
| Q-ISIS-12 — PENDENTE-ISIS | Ao conferir o Parecer 84 original, a expressão “Decreto Federal 9.710/2020” pretende referir-se ao decreto estadual goiano? O erro é só identificação da esfera ou afeta a conclusão? Que outras citações requerem ressalva? | Identidade estadual verificada externamente; texto/página/mérito do parecer não. Suspende claim afetado até revisão. |
| Q-ISIS-13 — PENDENTE-ISIS | Qual critério torna uma divergência material e quais claims/regras ficam suspensos até decisão? Confirma que ausência de fonte elegível deve retornar vazio com razão, sem relaxar filtros de aplicabilidade? | Define suspensão, revisão e comportamento de recuperação. Padrões 6/8, incremento 4. |
| Q-ISIS-14 — PENDENTE-ISIS | Qual o ciclo de revisão das matrizes, quem homologa/publica e como a versão anterior é preservada? A atualização continuará por planilha reimportada ou haverá edição controlada? | Bloqueia governança de publicação/rollback e custo de manutenção. |
| Q-ISIS-15 — PENDENTE-ISIS | Quais TRs do pacote de 224 correspondem à cobertura escolhida e, em documentos semelhantes, qual edição deve governar cada peça? Confirma os itens obrigatórios e condicionais por órgão? | Bloqueia inventário semântico final e checklist; nenhuma deduplicação/precedência por nome. |
| Q-ISIS-16 — PENDENTE-ISIS | Para os roteiros SIGCAR, qual versão do sistema e mensagem/código exato identifica cada procedimento, e quais passos exigem juízo profissional? Qual órgão/edição identifica inequivocamente a IN 23/2025 do pacote? | Evita tratar procedimento como norma ou usar roteiro de tela/versão incompatível. |

## 9. Estado de entrega e parada

| Bloco | Estado desta revisão |
|---|---|
| A — Ontologia | Proposta completa do vocabulário mínimo, fontes/limites, atributos/relações/estados e mapa de colisões com código; homologação de domínio pendente. |
| B — Cobertura | 16 demandas catalogadas + linha Jobson, UFs/formatos/templates qualificados; lançamento não escolhido pela engenharia. |
| C — Insumos | **Parcial e bloqueado nos originais faltantes**. 65 regras contadas nas duas cópias; nenhuma transcrição inventada da v03, nenhum TR/parecer fingido lido. |
| D — Padrões | Oito padrões avaliados contra main, com lacunas, custo e aceite; comparação literal com os três documentos externos aguarda recebimento. |

O PR é documental e deve permanecer **rascunho enquanto o inventário solicitado não puder ser completado**. Não fechar o Incremento 0 nem aprovar cobertura por CI verde. Parar no PR, sem merge e sem implementar os incrementos seguintes. A homologação externa herdada em [#174](https://github.com/prosperidade/amigao/issues/174) continua no Incremento 7.
