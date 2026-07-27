# Ficha 08 — Base de Dados: Documentos Obrigatórios, Cruzamento de Campos e Prioridade em Divergência

> **Origem:** ficha de domínio da Isis — "Regente / Base de Dados — Documentos Obrigatórios,
> Cruzamento de Campos e Prioridade em Divergência", **V2**.
> **Versionada no repo em 2026-07-20** por `fix/fonte-unica-requisitos-documentais`.
> Conversão fiel do documento original (`.docx`, fora do repo). Sem dados pessoais.
>
> **V2** — revisado após simulação de fluxo do Extrator com documentos reais do caso
> Fazenda São Jorge (Lotes 01-B e 01-C) e complementado com campos registrais
> (Matrícula, Livro, Folha, Ficha, NIRF, Módulo Fiscal, Número do CCIR).
>
> **Escopo implementado neste PR:** seção 2 (a lista dos 6) e seção 7 (completude e
> validade). O restante está versionado aqui como especificação e registrado como
> dívida — ver "Estado de implementação" ao final.

Ficha de apoio para a **aba Conferência** — etapa de construção da base de dados do Regente.

---

## 1. Contexto

Esta ficha define, para a aba Conferência, quais documentos são obrigatórios para compor a
base de dados do Regente, quais campos entre eles devem ser cruzados para checar
consistência, e qual documento prevalece quando há divergência. Também separa o que é dado
do imóvel/matrícula do que é dado do proprietário, e mapeia o que precisa ser coletado além
dos documentos obrigatórios.

Esta versão foi revisada após uma série de simulações do fluxo do Extrator contra documentos
reais (Matrículas 4.698 e 6.776, CCIR, ITR/DIAC/DIAT, CNH, CAR/RAT, Memorial Descritivo e
Planta SIGEF). As simulações expuseram riscos de normalização que não apareciam ao olhar os
documentos isoladamente — a seção 8 documenta esses achados e as regras criadas para
blindar o Extrator contra eles.

---

## 2. Arquivos obrigatórios e seu papel na base

| Documento | Papel na base |
|---|---|
| **Matrícula** | Documento-mãe jurídico — domínio, cadeia dominial, ônus, averbações (RL, APP). Uma por lote/registro. |
| **CAR** (obrigatório) | Documento-mãe ambiental — RL, APP, área vetorizada, situação do cadastro. Dado único do imóvel: vive no Imóvel Hub, não se duplica por matrícula/card, mesmo quando o imóvel tem mais de uma matrícula contígua. |
| **CCIR** | Documento-mãe fiscal/cadastral rural — código INCRA, módulos fiscais. Um por matrícula/código INCRA. |
| **ITR (DIAC + DIAT)** | Declaração tributária — código INCRA, valor do imóvel (VTN), distribuição de área (RL/APP/vegetação declaradas). Um por matrícula/código INCRA. |
| **Documento de identidade do titular (RG/CNH)** | Fonte de verdade do titular único do caso — ver seção 3. |
| **Planta / Memorial descritivo (SIGEF)** | Documento-mãe técnico de perímetro — coordenadas, confrontações. Nem todo imóvel possui; ver regra de coordenadas na seção 5. |

> ⚑ **RAT não substitui o CAR** (decisão da Isis, 2026-07-20). O Relatório de
> Análise Técnica *só existe quando já foi feita uma análise do CAR* — é o parecer
> do órgão sobre o cadastro, não o cadastro. O sistema deve ler o RAT como **"não
> serve"** para o requisito CAR, mesmo quando ele traz o número do CAR no corpo.
>
> Implementado: `rat` fica fora do vocabulário do requisito `car` em
> `requisito_documental.py`, com teste travando (`test_vocabulario_tipo_fora_dos_seis`).
>
> **Adendo 2026-07-26 (Isis) — o RAT é fonte de CONTEXTO/HISTÓRICO.** Não basta
> não satisfazer o requisito: ele precisa *aparecer com o papel certo*. O RAT
> retrata a análise do órgão **numa data**, e essa foto pode já estar superada
> pela retificação seguinte — foi o que aconteceu no caso 15, onde o RAT de 2024
> descrevia um CAR que a retificação de 15/11/2024 mudou. Na tela e no
> diagnóstico ele se chama **"análise histórica do CAR"**, nunca "CAR".
> Implementado em `frontend/src/lib/labels/docLabels.ts` (`rat`) e travado por
> `tests/services/test_rat_nao_satisfaz_car.py` (vocabulário **e** equivalências —
> equivalência era a segunda porta pela qual ele poderia entrar).

> ⚑ **CAR é dado único do imóvel como um todo**, independente de quantas matrículas o
> compõem. Ele é anexado uma única vez no Imóvel Hub e referenciado por todos os
> cards/matrículas daquele imóvel — nunca duplicado ou re-solicitado.

---

## 3. Pré-requisitos de identificação (antes de qualquer cruzamento)

Estas três regras resolvem **quem é o titular** e **qual é o imóvel** antes de qualquer campo
ser comparado entre documentos. Sem elas, a tabela de campos-âncora da seção 4 gera falsos
positivos de divergência.

### 3.1 Titular único do caso

O sistema trabalha com um **único titular por caso**. O nome e CPF cadastrados manualmente
pelo consultor — sempre o primeiro dado inserido, antes do upload de qualquer documento —
devem ser idênticos ao nome e CPF do documento de identidade (RG/CNH) enviado como um dos
documentos obrigatórios.

Qualquer outro nome que apareça nos documentos (cônjuge, coobrigado em hipoteca, herdeiro) é
tratado como **parte relacionada**, nunca como cotitular — mesmo quando o texto do documento
usa "proprietários" no plural (regime de comunhão de bens).

Divergência de nome entre documentos (ex.: grafia diferente, nome de solteira) segue a mesma
regra da seção 5: o sistema alerta, o consultor decide manter ou corrigir.

### 3.2 Identificação do imóvel: chave composta comarca + matrícula

O número da matrícula sozinho **não é identificador único** — ele só é exclusivo dentro do
cartório que o emitiu. Um mesmo número pode existir em comarcas diferentes.

**Regra:** o identificador do imóvel na base é sempre **comarca/cartório + número da
matrícula** (ex.: `São João d'Aliança-GO :: 4.698`), nunca o número isolado.

Essa chave é extraída direto do cabeçalho da própria Matrícula (campo de Comarca/Distrito
Judiciário + número), nunca do documento de identidade do titular — o RG/CNH não tem relação
com a comarca do imóvel.

Não é necessário reconstruir cadeia de sucessão (matrícula antiga → matrícula nova). O
sistema usa sempre a matrícula atual do imóvel do cliente, que já vem corretamente
identificada no próprio documento anexado.

Essa regra vale apenas para a matrícula do imóvel do cliente. Matrículas de terceiros citadas
em confrontações (vizinhos) são texto descritivo — não entram em nenhuma lógica de
identificação ou validação.

### 3.3 CAR: vínculo por imóvel, não por matrícula

Como o CAR é um dado único do imóvel consolidado (seção 2), ele se vincula ao **Imóvel Hub** —
não a uma matrícula individual. Quando o imóvel tem mais de uma matrícula contígua, todos os
cards daquele imóvel compartilham a mesma referência de CAR, sem re-upload.

---

## 4. Tabela de campos-âncora (cruzamento)

Reúne os dados importantes da base do cliente: tanto os campos que aparecem em 2 ou mais
documentos e servem como ponto de verificação cruzada, quanto campos estruturais de fonte
única (ex.: Livro, Ficha, Número do CCIR) que não geram divergência a resolver, mas são
obrigatórios na base por identificar e localizar o registro do imóvel.

Revisada: campos removidos de "Todos" quando o documento de identidade (CNH/RG) não os possui;
campos novos adicionados a partir do mapeamento completo dos documentos reais.

| Campo | Documentos que cruzam | Consequência se divergir |
|---|---|---|
| Código INCRA/SNCR | CCIR × ITR × Matrícula × Memorial × CAR | Ação de retificação (ver prioridade, seção 5) |
| Área total (ha) | Matrícula × CCIR × CAR × Memorial | Ação de retificação — Memorial/SIGEF é referência prioritária |
| Denominação do imóvel | Matrícula × CCIR × ITR × CAR × Memorial × Planta | Alerta — variações Gleba/Lote são padrão esperado entre documentos jurídicos e fiscais, não necessariamente erro; consultor confirma |
| Proprietário + CPF (titular único) | Matrícula × CAR × ITR × CCIR × Documento de identidade | Documento de identidade é a fonte de verdade — ver seção 3.1 |
| Município | Matrícula × CCIR × ITR × CAR × Memorial | Divergência rara — checar erro de transcrição |
| Número da matrícula (identificador) | CCIR × Memorial × Planta (citam) × Matrícula (fonte) | Sempre resolvido via chave composta comarca+matrícula — ver seção 3.2 |
| Livro (Registro Geral) | Matrícula (registro anterior + cada averbação) × CCIR ("Livro ou Ficha") | Dado estrutural de localização do registro — Matrícula vence (cadeia jurídica); divergência no CCIR indica erro de transcrição |
| Folha (fls.) | Matrícula (cada registro/averbação cita "às fls.") | Campo só existe na Matrícula — sem par de cruzamento; usado para localizar o ato dentro do livro |
| Ficha | CCIR ("Livro ou Ficha") | Alterna com "Livro" conforme o sistema do cartório (digital = Ficha, físico = Livro); campo só existe no CCIR, sem par de cruzamento direto — equivalente funcional ao par Livro/Folha da Matrícula |
| NIRF / CIB | Matrícula ("NIRF n°…") × ITR ("Identificação CIB") | Mesmo identificador (cadastro do imóvel rural na Receita Federal) sob dois nomes diferentes — Matrícula e ITR devem trazer o mesmo número; divergência é sinal de vinculação CNIR desatualizada |
| Módulo Fiscal (ha) | CCIR (campo próprio) × Matrícula (quando o texto do CCIR aparece transcrito em alguma averbação) | CCIR vence; divergência indica CCIR desatualizado em relação ao módulo fiscal do município — campo usado em cálculos de classificação fundiária |
| Número do CCIR | CCIR (próprio) × Matrícula (citado em cláusulas de hipoteca) | CCIR vence — se a Matrícula citar número de CCIR diferente do vigente, é referência desatualizada (mesma lógica do número de matrícula, seção 3.2); campo obrigatório para rastreabilidade de qual emissão foi usada na Conferência |
| Coordenadas | Matrícula (memorial embutido) × Memorial/SIGEF × Planta × CAR | Memorial/SIGEF tem preferência; na ausência de Memorial, usa-se a Matrícula (ver seção 5) |
| Perímetro | Matrícula × Memorial × Planta | Mesma prioridade de Coordenadas — CAR não possui este campo (só área vetorizada) |
| Contiguidade de matrículas | CAR (fonte única) | Define a granularidade CAR-por-imóvel (Lei 8.629/93 art. 4º I; IN MMA 02/2014 art. 31–32) |
| RL Averbada (ha) | Matrícula × CAR × ITR | Matrícula vence — é o registro jurídico da averbação. Atenção: RL pode ter sido relocada de outra matrícula de origem — validar se a área averbada está fisicamente contida no perímetro do imóvel em análise |
| APP (ha) | CAR × ITR | CAR vence sobre ITR (ITR é autodeclarado, sujeito a simplificação) |
| Valor do imóvel | Cliente (declarado) × Matrícula (garantia) × ITR (VTN) | Não há "vencedor" — os três coexistem na base com rótulos distintos; uso depende do contexto (venda / garantia / fiscal) |
| Data de nascimento do titular | Documento de identidade × ITR | Documento de identidade vence — ITR é autodeclarado |
| Número do CAR | CAR (próprio) × ITR/DIAT (campo "Número de CAR") | Frequentemente em branco no ITR — ausência de dado, não divergência. Quando preenchido e diferente do CAR real, indica ITR desatualizado |
| Matrícula (nº, como valor de campo) | Matrícula (própria) × CCIR (campo "Matrícula ou Registro") × Memorial (campo "Matrícula do imóvel") × Planta | Diferente do uso como identificador (seção 3.2) — aqui é o dado registral que vai para a base. Matrícula é a fonte; demais documentos apenas citam |
| Livro | Matrícula (ex.: "Livro n°2-I", "Livro 1-B") × CCIR (campo "Livro ou Ficha") | Formatação pode variar (ex.: "2" vs. "2-I/J") — mesmo conceito registral; Matrícula vence |
| NIRF | Matrícula (citado no texto) × ITR (identificação do imóvel na Receita Federal) | Deve ser extraído diretamente do cabeçalho do ITR, não só "emprestado" de dentro do texto da Matrícula |
| Módulo Fiscal (ha) | CCIR (campo próprio) × Matrícula (citado no texto quando reproduz dados do CCIR apresentado em cartório) | CCIR vence — é o documento de origem deste dado (cadeia jurídica/fiscal, seção 5.1) |
| Número do CCIR | CCIR (campo próprio) × Matrícula (citado no texto) | CCIR vence — é o documento de origem deste dado |

> ⚑ Toda divergência identificada nesta tabela é **sempre mostrada ao consultor** — o sistema
> nunca resolve e sobrescreve em silêncio, mesmo quando a hierarquia da seção 5 indica um
> valor preferencial. A hierarquia sugere; o consultor ratifica ou abre retificação.

### 4.1 Campos registrais sem par de cruzamento

Campos que compõem a base de dados do cliente, mas que têm fonte única entre os documentos
obrigatórios — não há outro documento para confirmar ou divergir. Registrados como dado da
Matrícula, sem verificação cruzada possível hoje.

| Campo | Fonte única | Observação |
|---|---|---|
| Folha | Matrícula (ex.: "às fls.199eV°", "fls.78vº") | Referência interna do livro de registro do cartório. O CCIR não abre este campo separadamente. |
| Ficha | Matrícula | Não aparece como valor isolado nos documentos reais analisados — no CCIR, a coluna "Livro ou Ficha" está sempre preenchida com número de livro, nunca com ficha distinta. |

---

## 5. Prioridade em divergência

A hierarquia de confiança para arbitrar conflitos **não segue uma única escada** — os campos
se dividem em duas cadeias paralelas, uma jurídica e uma geométrica/técnica.

### 5.1 Cadeia jurídica/dominial

Rege titularidade, CPF, código INCRA, RL averbada, CPF do cônjuge, estado civil.

```
Matrícula  →  SNCR / CCIR  →  Cafir/CIB  →  ITR  →  CAR
```

### 5.2 Cadeia técnica/geométrica

Rege área, perímetro, coordenadas, confrontações.

```
Memorial/SIGEF  →  Matrícula (fallback, se não houver Memorial)  →  CAR
```

**Regra de coordenadas:** sistema escolhe o Memorial/SIGEF quando existente. Na ausência de
Memorial (caso real: Lote 01-B, sem dados SIGEF conforme o próprio CCIR declara), usa-se a
Matrícula.

Confrontações seguem a cadeia técnica, mas como frequentemente aparecem descritas dentro da
própria Matrícula, o sistema trata como alerta de revisão, não substituição automática.

### 5.3 Por que a divisão em duas cadeias

Nem todo campo é puramente jurídico ou puramente técnico. Área e perímetro nascem do mesmo
levantamento técnico (por isso seguem juntos na cadeia geométrica). Já RL averbada, mesmo
tendo componente de área, é um ato jurídico registrado em cartório — por isso segue a cadeia
jurídica. O Extrator deve aplicar a cadeia correspondente ao campo, não uma hierarquia
genérica única.

### 5.4 Regra geral

**CAR:** obrigatório para compor a base e insubstituível para revelar contiguidade de
matrículas — mas não arbitra contra a Matrícula em titularidade, código INCRA ou RL averbada.
Funciona como checagem de consistência do conjunto, não como árbitro de divergência
individual.

**ITR:** declaratório anual — reflete o que o contribuinte informou, não corrige os demais
cadastros.

> ⚑ **Regra de ouro:** o CAR não corrige matrícula, CCIR, ITR ou GEO — e o inverso também
> vale: se o CAR divergir da Matrícula em RL, código ou titularidade, é o **CAR** que precisa
> de retificação, não a Matrícula.

---

## 6. Dados que vão além dos arquivos obrigatórios

Separado por titularidade da informação — o que pertence ao proprietário (pessoa) vs. ao
imóvel/matrícula (bem).

### 6.1 Dados do Proprietário (pessoa física)

| Campo | Fonte |
|---|---|
| CPF do proprietário | Documento de identidade — fonte de verdade (ver seção 3.1); confere com Matrícula, CAR, ITR, CCIR |
| Telefone, e-mail, escolaridade | Entrevista / cadastro do consultor — sem fonte documental |
| Endereço de correspondência | Declarado pelo cliente — pode divergir do endereço do imóvel |

### 6.2 Dados do Imóvel / Matrícula

| Campo | Fonte |
|---|---|
| Valor do imóvel | Triplo: cliente (declarado) + Matrícula (garantia, quando informado) + ITR (VTN) — os três coexistem na base |
| Descrição de acesso | Autoria do próprio consultor — não é extraída de documento (o CCIR/CAR trazem só indicação geral de localização) |
| RL Averbada (ha) / APP (ha) | Matrícula (averbação) + CAR (declaração) + ITR (distribuição de área) — Matrícula vence em conflito |

**Situação Fundiária não é dado de base** — é produto interpretativo do Diagnóstico, que roda
depois da Legislação cruzando os dados brutos já consolidados. O mesmo vale para **Situação do
cadastro do CAR** (Ativo/Pendente/Cancelado): é status de acompanhamento, não campo de
cruzamento — fica registrado junto ao CAR, mas sua leitura/implicação é trabalho do
Diagnóstico.

### 6.3 Bloco de Distribuição de Área (origem: ITR/DIAT)

| Campo | Fonte | Observação |
|---|---|---|
| Área de Preservação Permanente | ITR | Cruza com APP do CAR |
| Área de Reserva Legal | ITR | Cruza com RL da Matrícula/CAR |
| Área Coberta por Florestas Nativas | ITR | Equivale ao "Remanescente de Vegetação Nativa" do CAR — nomenclatura diferente, mesmo conceito |
| RPPN, Área Tributável, Área Aproveitável, Grau de Utilização | ITR | Uso fiscal — sem par de cruzamento nos demais documentos |
| Nº do Recibo ADA/Ibama | ITR | Pode verificar contra a data de averbação de RL na matrícula |

### 6.4 Bloco de Atividade/Uso e Licenciamento — pendência em aberto

Tipologia de Atividade, Código CEMAM, Área do empreendimento, Receita Bruta Anual: nenhum dos
6 documentos obrigatórios cobre esse bloco. O próprio RAT do CAR real analisado lista "Licença
Ambiental e Autorização de Desmatamento" entre os documentos solicitados, reforçando que essa
é a fonte provável.

> ⚑ **Em aberto:** definir se a Licença Ambiental entra como **7º documento obrigatório**, ou
> se este bloco fica como informação complementar não-obrigatória, preenchida apenas quando há
> atividade licenciável.
>
> **Decisão de implementação (2026-07-20):** enquanto em aberto, a Licença Ambiental **NÃO**
> entra na lista de obrigatórios da fonte única. São 6, não 7.

### 6.5 Excluído por ora

Arquivo SHP/KML — exportação técnica derivada do próprio CAR; fora do escopo da base neste
momento.

---

## 7. Completude e validade de documentos

Um documento "presente" (anexado) **não é o mesmo** que um documento "completo". Estas regras
evitam que gaps fiquem escondidos atrás de um checklist marcado como satisfeito.

### 7.1 Sub-campos obrigatórios dentro do documento

**Caso real:** um ITR recebido só com a parte de identificação (DIAC), sem a parte de
distribuição de área/VTN (DIAT) — onde vivem RL, APP declarada e Valor do Imóvel. Marcar "ITR
anexado" nesse caso esconde a ausência real desses campos.

**Regra:** o requisito de documento obrigatório é decomposto em sub-campos. Se um sub-campo
essencial está ausente (ex.: DIAT dentro do ITR), o sistema gera **lacuna (gap) nos campos
específicos que dependem dele** — mesmo com o arquivo tecnicamente presente.

### 7.2 Georreferenciamento embutido supre a ausência de Memorial/SIGEF separado

**Caso real:** o CCIR do Lote 01-B declara oficialmente que o imóvel "não possui dados
geográficos cadastrados na base SIGEF/INCRA" — mas a própria Matrícula já contém
georreferenciamento certificado pelo INCRA (2010), com coordenadas por vértice completas.

**Regra:** o requisito de "Planta/Memorial SIGEF" é **satisfeito** quando a própria Matrícula
contém georreferenciamento certificado embutido no texto, mesmo sem um arquivo de
Memorial/SIGEF separado. O sistema **não deve travar o card** exigindo um documento que
oficialmente não existe para aquele imóvel.

### 7.3 Vencimento gera alerta, não bloqueio

Documentos com data de validade (CNH, CCIR quando há débito pendente, certidões negativas)
devem ser monitorados quanto ao vencimento.

**Regra:** documento vencido ou próximo do vencimento gera **alerta** na Conferência — mesma
categoria de gap, **não trava**. Não impede o avanço do card por si só; sinaliza para o
consultor solicitar reenvio.

O campo de vencimento só é avaliado **quando presente e preenchido** no documento — nem todo
CCIR tem data de vencimento (só ocorre quando há débito em aberto); não assumir prazo fixo
genérico.

---

## 8. Riscos de normalização identificados em simulação

Achados de simulações de fluxo do Extrator contra os documentos reais do caso Fazenda São
Jorge. Cada um já está refletido nas regras das seções anteriores — esta seção documenta o
porquê.

- **Sistemas de coordenadas incompatíveis:** Matrícula registra em UTM; Memorial/SIGEF
  registra em Lat/Long geodésica. Comparação direta sem conversão prévia sempre resulta em
  falso positivo de divergência. Resolvido pela regra de prioridade da seção 5.2
  (Memorial/SIGEF preferencial, conversão necessária antes de qualquer cruzamento).
- **Formatação de código de vértice:** mesma referência de vértice aparece como `CWQ-M-0087`
  na Matrícula e `CWQ-M-087` no Memorial (zero à esquerda inconsistente). Matching por string
  exata gera falso negativo. Requer normalização de formato antes da comparação.
- **Nomenclatura Gleba × Lote:** documentos da cadeia jurídica (Matrícula, CAR) usam "Gleba";
  documentos da cadeia fiscal (CCIR, ITR) usam "Lote", referindo-se ao mesmo imóvel. Tratado
  como alerta de revisão (seção 4), não como erro a corrigir automaticamente.
- **Sobreposição do CAR com Unidade de Conservação:** o próprio RAT do CAR, ao apontar essa
  pendência, solicita de volta "certidão de matrícula atualizada" e "certificado de
  georreferenciamento" — documentos que, no fluxo do Regente, já são obrigatórios e
  frequentemente já estão anexados à base. **Oportunidade de produto:** quando o CAR apontar
  esse tipo de pendência, a Conferência pode indicar automaticamente quais documentos já
  presentes na base servem de resposta, evitando que o consultor precise recolher algo que já
  tem.

---

## 9. Resumo para implementação

1. Os **6 documentos obrigatórios** (seção 2) devem ser upload obrigatório antes do card
   avançar da etapa correspondente — com as exceções de completude e validade descritas na
   seção 7.
2. A resolução de **titular único** (seção 3.1) e a **chave composta comarca+matrícula**
   (seção 3.2) rodam **antes** de qualquer cruzamento — são pré-requisitos, não parte da
   tabela de campos-âncora.
3. **CAR é dado único do Imóvel Hub** — nunca duplicado ou re-solicitado por card/matrícula
   (seção 3.3).
4. Os **campos-âncora** (seção 4) devem ser extraídos automaticamente pelo Extrator e
   comparados; divergência gera alerta ou gap, **nunca sobrescrita silenciosa**.
5. A prioridade de arbitragem segue **duas cadeias paralelas** — jurídica e geométrica
   (seção 5) — não uma hierarquia única genérica.
6. O consultor decide, para cada divergência: (a) qual valor vai para a base (segue a cadeia
   correspondente), ou (b) se vira ação de retificação na rota regulatória.
7. Situação Fundiária e Situação do cadastro do CAR são removidas da tabela de dados brutos e
   passam a ser output do Diagnóstico.
8. **Documento vencido = alerta, não trava; documento presente mas incompleto (sub-campo
   ausente) = gap nos campos dependentes, não checklist satisfeito.**

---

## Cascata de vinculação ITR → matrícula (spec da Isis, 2026-07-20)

> Esta seção **não estava na ficha original** — é a resposta da Isis à pergunta
> "como o ITR encontra a matrícula dele?", registrada aqui porque é regra de
> domínio e vale como spec (ver ADR-032).

Do sinal mais forte ao mais fraco:

1. **NIRF normalizado** — extrai o NIRF do cabeçalho do ITR e compara com o NIRF
   já registrado na Matrícula (aparece repetido de forma consistente ao longo dos
   registros/hipotecas). Match único → vincula automaticamente, alta confiança.
2. **Código INCRA normalizado, só se o match for único** — se o NIRF não estiver
   disponível ou não bater. Nenhuma ou 2+ matrículas → não autolinka.
3. **Corroboração (área + denominação)** como desempate — quando o INCRA sozinho
   não resolve (caso 909-8 × 371-0, duas famílias documentais concorrentes).
   Reforça a hipótese, **mas nunca autolinka sozinho**: vira sugestão de alta
   probabilidade.
4. **Vínculo manual do consultor** — o sistema apresenta o ITR como não vinculado,
   mostra os candidatos com os sinais a favor de cada um, e o consultor decide. A
   decisão fica registrada: é proveniência, útil inclusive se a divergência de
   INCRA virar caso de retificação formal.

> ⚑ **Pendente de domínio (não bloqueante):** confirmação de leitura da Isis sobre
> o vínculo ITR→matrícula por INCRA normalizado — §4 aplicado conforme esta
> cascata. Comportamento implementado é o conservador: os degraus 1 e 2 vinculam;
> 3 e 4 nunca decidem sozinhos.

## Estado de implementação (mantido pelo time técnico)

Esta seção **não faz parte da ficha da Isis** — registra o que já virou código.

| Seção | Estado | Onde |
|---|---|---|
| §2 — lista dos 6 obrigatórios | ✅ implementado | `app/services/requisito_documental.py` (`REQUISITOS_BASE`) |
| §6.4 — Licença Ambiental como 7º | ⏸️ em aberto (decisão da Isis) | não implementado por decisão explícita |
| §7.1 — sub-campos / presente ≠ completo | ✅ implementado | `SATISFEITO_PARCIAL` + `gaps` |
| §7.2 — georref embutido supre Memorial | ✅ implementado | equivalência `matricula` → `planta_memorial` |
| §7.3 — vencido = alerta, nunca trava | ✅ implementado | `alertas` (nunca muda o estado para ausente) |
| §3.1 — titular único | ❌ dívida **#73** | — |
| §3.2 — chave composta comarca+matrícula | ❌ dívida **#72** | — |
| §4 — **NIRF/CIB** (identidade) | ✅ implementado | `_FIELD_SPECS['matricula']` + cascata |
| §4 — Livro, Folha, Ficha, Módulo Fiscal, nº CCIR (completude) | ❌ dívida **#74** | — |
| §5.1 — hierarquia declarada no confronto de identidade | ✅ implementado | `confronto_identidade.py` |
| §8 — normalização de código antes de comparar | ✅ implementado | `norm_incra` (só dígitos) |
| §5 — duas cadeias de prioridade | ❌ dívida **#75** | — |
| §8 — normalização (UTM×geodésica, vértices, Gleba×Lote) | ❌ dívida **#76** | — |
| §8 — CAR aponta pendência → Conferência responde com doc já presente | 💡 oportunidade de produto (#77) | — |
