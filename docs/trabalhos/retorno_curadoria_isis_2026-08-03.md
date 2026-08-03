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
