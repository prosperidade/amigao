# Retorno de curadoria — núcleo 06 (03/08/2026)

Isis, três achados da primeira rodada de ingestão do seu mapa normativo. Nada
grave, e dois deles o sistema pegou sozinho — o que é justamente o que a gente
queria que ele fizesse.

---

## 1. A Constituição: o link da planilha entrega texto incompleto

**O que aconteceu.** A linha da Constituição aponta para
`planalto.gov.br/ccivil_03/constituicao/constituicao.htm`. Esse endereço não
devolve a Constituição inteira: o texto **para no art. 24, §4º**. Como a sua
linha cita justamente o **art. 225, §3º** (a tríplice responsabilização), o
artigo mais importante para o nosso tema ficaria de fora.

**O que o sistema fez.** Recusou a ingestão. Cada linha do mapa tem uma
"palavra-chave de conferência" — a sua era `art. 225` —, e o sistema confere se
ela aparece no texto baixado antes de aceitar. Não apareceu, não entrou.

**O que fizemos.** Trocamos pelo endereço da versão consolidada,
`constituicaocompilado.htm`, que traz o texto completo (686 mil caracteres,
com o art. 225). Já está no sistema.

**O que pedimos.** Corrigir o link na planilha, para a próxima extração já sair
certa.

---

## 2. O Decreto 9.760/2019 está revogado, e a planilha não diz

**O que aconteceu.** A linha está marcada como "Fonte oficial validada" — e está
mesmo, o link é oficial e funciona. Só que o próprio texto do Planalto termina
com: *"(Revogado pelo Decreto nº 11.080, de 2022)"*.

Ele criava os núcleos de conciliação ambiental. Não vale mais.

**O que fizemos.** Ingerimos assim mesmo, **marcado como norma histórica** —
porque um auto de 2007 (como o do caso 15) pode precisar dela, já que vale a
norma da época do fato. Todo trecho dela que o sistema recuperar vem com um aviso
colado: *"NORMA HISTÓRICA — revogada em 24/05/2022, sucedida pelo Decreto
11.080/2022. Aplicável a fatos anteriores; NÃO citar como norma vigente."*

Fomos ao Decreto 11.080 para confirmar a data exata (24 de maio de 2022) em vez
de deduzir.

---

## 3. Sugestão de método: uma coluna de vigência na planilha

Este é o pedido de verdade, e vem dos dois casos acima.

Hoje a planilha tem **"Status da fonte"**, que responde *"o link funciona e é
oficial?"*. É uma pergunta ótima e não é a mesma que *"a norma ainda vale?"*. O
Decreto 9.760/2019 é "fonte validada" **e** norma revogada ao mesmo tempo — as
duas coisas são verdadeiras e a planilha só tem espaço para uma.

Sugerimos acrescentar três colunas:

| coluna | o que preencher |
|---|---|
| **Vigência — início** | quando a norma passou a valer |
| **Vigência — fim** | em branco se ainda vale; a data se foi revogada |
| **Sucedida por** | qual norma tomou o lugar dela |

Isso importa porque o sistema já sabe usar essa informação: norma revogada entra
no acervo (a defesa precisa dela) mas **nunca** é apresentada como direito
vigente. Hoje, quem descobre a revogação é quem lê o texto na hora da ingestão —
ou seja, por acaso. Com as colunas, a informação vem da sua curadoria, que é
onde ela deve estar.

---

## 4. Duas normas que não conseguimos baixar

**IN IBAMA 21/2023** (conversão de multa em serviços) e **Portaria IBAMA 15/2026**
(Solução Legal). O portal do IBAMA bloqueia acesso automatizado — devolve erro
403 para qualquer programa que não seja um navegador de pessoa.

É o mesmo problema que já tivemos com a **IN IBAMA 10/2012**.

**O que pedimos.** Se você conseguir abrir essas três no navegador e salvar em
PDF, a gente ingere na hora. Não há pressa nem risco: elas estão registradas como
pendência e o sistema sabe que não as tem — ele não vai fingir que sabe.

---

## Resumo do que entrou

Das 43 linhas do núcleo 06, o sistema identificou 26 endereços distintos (a mesma
norma aparece em várias linhas do seu mapa, cada uma por um ângulo — o Decreto
6.514/2008 sozinho está em 7). Dessas 26:

- **9 normas** já estavam no acervo desde junho e julho;
- **5 entraram agora**: Constituição, Orientação Jurídica Normativa 06/2009 da
  procuradoria do IBAMA, IN ICMBio 9/2023, Decreto 8.539/2015 e o Decreto
  9.760/2019 (histórico);
- **2 ficaram pendentes** por causa do bloqueio do IBAMA;
- **10 são páginas de serviço** (consulta de áreas embargadas, obter certidão,
  FAQ, parcelamento da PGFN). Essas ficaram registradas mas **fora do acervo de
  fundamentação** — elas dizem *onde fazer*, não *o que a lei diz*, e misturá-las
  com lei atrapalharia a busca. Elas vão ser muito úteis noutro lugar: são
  exatamente o "onde protocolar / onde consultar" que o editor de rota vai usar.

Efeito medido na mesma pergunta de sempre (a defesa do auto 484341/D): a
Orientação Jurídica Normativa da procuradoria do IBAMA passou a aparecer entre os
trechos mais relevantes, ocupando 4 das 8 vagas. É interpretação vinculante sobre
o rito sancionador — exatamente o tipo de material que faltava.

---

# Segunda rodada — núcleos 02 e 03 (Territorial/Cadastro e Florestal/CAR/PRA)

Isis, esta rodada tem um recado principal e ele é sobre **onde vale a pena
investir o seu tempo de curadoria**.

## O achado que muda a prioridade

Separamos o seu mapa em dois grupos antes de ingerir:

- **Canônico** — as leis e decretos: "o que a lei exige"
- **Interpretativo** — INs, manuais, notas técnicas: "como se faz na prática"

Ingerimos 25 documentos canônicos novos e medimos o efeito numa pergunta de
procedimento: *"quais são os requisitos e o procedimento para retificação do CAR
de um imóvel rural em Goiás?"*.

**O resultado foi zero.** Os mesmos 8 trechos antes e depois, idênticos. Nenhum
dos 25 documentos novos entrou na resposta.

Não é que eles sejam inúteis — a Lei 10.267/2001, o Decreto 4.449/2002 e a Lei
6.015/1973 são a espinha fundiária que faltava, e vão responder perguntas de
georreferenciamento e registro que ainda não fizemos. Mas **pergunta de
procedimento só melhora com material de procedimento**.

## E o material de procedimento é justamente o que não conseguimos baixar

Das 10 fontes interpretativas do seu mapa nesses dois núcleos, **nenhuma** entrega
o texto da norma:

| norma | o que o link entrega |
|---|---|
| IN MMA 02/2014 (SICAR) | o site `car.gov.br` derruba a conexão |
| IN INCRA 77/2013 | o endereço termina em `.pdf` mas devolve uma página |
| Manual de Georreferenciamento | página de **notícia** sobre o manual, e pede senha |
| IN RFB 2.203/2024 | certificado de segurança da Receita não é aceito |
| IN IBAMA 21/2014 (Sinaflor) | portal bloqueia acesso automatizado |
| IN IBAMA 16/2022, 11/2025, 14/2024 | páginas de **notícia**, não o ato |
| Res. CMN 5.193/2024 | página do Banco Central exige JavaScript |
| Res. CONAMA 411/2009 | o link do Sisconama entrega **outra resolução** |

**Por isso a sua pasta de INs tem prioridade sobre os próximos blocos.** Ela vale
mais que todo o restante do mapa canônico — e é a única forma de alcançar esse
material.

## Sobre os links do CONAMA (Sisconama)

Conferimos três links do tipo `sisconama...id=NNN` e **os três entregaram ato
diferente do pedido**:

| você pediu | o link entregou |
|---|---|
| Resolução 411/2009 | Moção nº 102/2009 |
| Resolução 406/2009 | Resolução nº 412/2009 |
| Resolução 369/2006 | um texto sem o número 369 |

Já tínhamos visto isso em abril com outros dois. **Sugestão: não usar links do
Sisconama por número de id** — eles parecem apontar para um arquivo e apontam
para outro. Onde precisar de resolução do CONAMA, um espelho de órgão estadual
(a CETESB, por exemplo) tem servido melhor. A 369/2006 já está no nosso acervo
por esse caminho, desde abril.

## O que entrou

25 documentos: 12 do núcleo territorial (Lei 10.267/2001, Decreto 4.449/2002,
Lei 6.015/1973, Lei 5.868/1972, as resoluções do IBGE sobre SIRGAS2000, entre
outros) e 14 do florestal (Lei 11.428/2006 da Mata Atlântica e seu decreto, as
alterações do PRA pelas Leis 13.887/2019 e 14.595/2023, o decreto da CRA, a
Política de Pagamento por Serviços Ambientais).

Outros 15 links do seu mapa são **sistemas e portais** — SIGEF, acervo fundiário
do INCRA, malhas do IBGE, CNUC, WebAmbiente, consulta do SICAR. Ficaram
registrados, mas **fora do acervo de fundamentação**: eles dizem *onde fazer*,
não *o que a lei diz*. Vão ser usados noutro lugar — são o "onde protocolar,
onde consultar" que o editor de rota do consultor vai precisar.
