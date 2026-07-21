# ADR-032 — Identidade da matrícula: confronto antes da decisão e cascata de vinculação

- **Status:** aceita
- **Data:** 2026-07-20
- **Branch:** `fix/consolidacao-lineage-decisoes`
- **Domínio:** Ficha 08 §4 (campos-âncora), §5.1 (cadeia jurídica), §8 (normalização)
- **Spec de domínio:** resposta da Isis de 20/07 (cascata de vinculação) + investigação do caso 15

## Contexto

O caso 15 materializou a matrícula **2923** onde deveria ser **4698**, e perdeu em
silêncio dois campos que o consultor tinha aceitado (NIRF e VTN). A investigação
(read-only, com timeline reconstituída) mostrou que **nada disso foi bug de
cálculo** — foi ausência de conceito em três pontos:

**1. A identidade nunca foi confrontada.** O CCIR do Lote 1B declara `matricula_hint
= 2923` (número registral defasado); a certidão do mesmo lote declara `4698`. A
Conferência apresentou os campos **documento a documento**, nunca lado a lado. O
consultor aceitou os campos do CCIR (14:44) e rejeitou os da certidão, e a
consolidação (14:46) fez exatamente o que foi mandado. A hipótese inicial de que
"staging rejeitado contribuiu" foi **refutada**: `staging_consolidation.py:405`
filtra `status == aceito`, e o dado bate.

**2. O aceite podia não ter destino — e ninguém era avisado.** Duas classes
distintas, que uma verificação de schema não separa:
- `vtn` foi aceito e **não existe coluna** para ele;
- `nirf_cib` foi aceito, **a coluna existe**, e mesmo assim não gravou — porque as
  linhas do ITR nascem sem `matricula_hint` (o ITR não declara número de matrícula;
  identifica o imóvel por NIRF/CIB e código INCRA, Ficha 08 §4). Tinha destino,
  faltava **dono**.

**3. O registro não tinha certidão de nascimento.** Responder "de onde veio esse
2923?" exigiu cruzar timestamps de decisão com `matricula_hint` na mão.

## Decisão

**1. Confronto de identidade abre a Conferência.** Quando dois ou mais documentos
declaram números de matrícula divergentes, isso é a primeira coisa da tela: os
números lado a lado, a fonte de cada um, e a hierarquia da §5.1 **declarada em
texto** pelo backend. A tela não reimplementa a regra — mesmo padrão do guard-rail
do avanço (ADR-031 mostrou o custo de duplicar redação entre superfícies).

**2. Linha rejeitada continua no confronto.** Deliberado: no caso 15 o número
correto estava justamente na linha rejeitada. Esconder o rejeitado esconderia a
evidência de que a decisão precisa ser revista.

**3. A proposta de cadeia nasce da leitura do staging, não da decisão.** Se algum
documento declara `registro_anterior` apontando para o número concorrente, o
sistema propõe a linhagem antes de qualquer decisão campo a campo. No caso 15 esse
sinal existia e foi **destruído pela rejeição** — a rejeição matava justamente o
sinal que teria evitado a rejeição errada.

**4. Vinculação ITR→matrícula segue a cascata da Isis**, do sinal mais forte ao
mais fraco:

| Degrau | Sinal | Autolink? |
|---|---|---|
| 1 | NIRF normalizado, match único | **sim** |
| 2 | Código INCRA normalizado, match único | **sim** |
| 3 | Corroboração (área + denominação) | **nunca** — sugestão de alta probabilidade |
| 4 | Escolha do consultor entre os candidatos | manual, vira proveniência |

INCRA ambíguo (2+ matrículas) ou divergente entre documentos do lote **não**
vincula: vira pendência + proposta de 1 clique.

**5. Todo aceite ou vira dado, ou aparece.** A varredura classifica `sem_coluna`
× `sem_dono` e a Conferência exibe. Aceite perdido em silêncio, nunca mais.

**6. Todo registro nasce com lineage** — qual staging, qual decisão, de quem, quando.

**7. Reabrir decisão existe.** Correção de dado errado é **re-decisão humana na tela
consertada**, não `UPDATE` em produção.

## Consequências

**Boas:**
- A decisão mais cara do domínio (identidade jurídica do imóvel) deixa de ser
  tomada por acidente, campo a campo, sem que o consultor saiba que a está tomando.
- O caso 15 vira o teste de aceite da própria cura: a Isis reabre 314/318, vê o
  confronto 2923×4698 com a hierarquia à vista, decide certo, e a cadeia grava 4698
  como vigente e 2923 como histórica.

**Custos e limites:**
- O degrau 3 (corroboração ranqueada) e a tela rica de "sinais a favor" ficam como
  dívida, com a cascata da Isis como spec. Enquanto não existem, o caso ambíguo cai
  no degrau 4 manual, que resolve.
- A extração de NIRF na certidão entrou como **fatia da #74** por ser
  infraestrutura de identidade: sem ela o degrau 1 é letra morta e a cascata começa
  silenciosamente no degrau 2. Os outros 5 campos registrais (Livro, Folha, Ficha,
  Módulo Fiscal, nº CCIR) seguem como dívida — são completude, não identidade.
- `lineage` é aditiva e nullable: registros anteriores ficam sem certidão de
  nascimento, e isso é honesto — não dá para inventar origem retroativamente.

## Alternativa descartada

**Corrigir a matrícula 29 em produção por SQL.** Rejeitada: consertaria o sintoma e
deixaria a tela cega que produziu o erro. A correção pelas mãos de quem errou, na
tela consertada, é o que prova a cura — e é o único caminho que gera proveniência
da re-decisão.

## Referências

- Ficha 08 §4, §5.1, §8 · resposta da Isis de 20/07 (cascata)
- ADR-031 (fonte única de requisitos) — a mesma classe: redação duplicada diverge
- ADR-027 / dívida #60 (vigência da cadeia de fichas)
- Auditoria: `docs/auditoria/AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md`
