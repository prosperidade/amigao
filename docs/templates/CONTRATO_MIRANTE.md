# Template de Contrato — Padrão Mirante

> **Origem:** destilado dos contratos reais da Mirante Ambiental.
> **LGPD:** este template contém **ZERO dado pessoal real**. Todos os exemplos
> abaixo são **fictícios**. Os originais (com CPF/RG/conta bancária) **nunca**
> entram no repositório.
>
> **Como nasce:** o contrato é gerado **a partir de uma proposta ACEITA**
> (S5-B). A Cláusula 1ª espelha o escopo aceito; a Cláusula 2ª espelha os
> valores. Bloco único do processo corrente — cenário multi-bloco /
> multi-titular é a **dívida #67** (já registrada).
>
> **Validações de consistência (geração bloqueada em caso de violação):**
> 1. Soma das parcelas (Cláusula 2ª) == total do bloco (Cláusula 1ª).
> 2. Valores da Cláusula 2ª == tabela de valores por serviço da Cláusula 1ª.
> 3. Matrículas citadas existem e são **VIGENTES** no caso.
>
> **Placeholder não resolvido = geração bloqueada** (nunca sai `[12]` no
> documento final).
>
> **Cláusulas 3ª a 8ª = boilerplate parametrizado** (foro, prazo, % multa,
> bônus/malus). O bônus/malus ±20% é **OPCIONAL** e vem **desligado por
> padrão** (`condicoes.bonus_malus.ativo = false`).

---

## Convenção de placeholders

| Placeholder | Origem | Exemplo fictício |
|---|---|---|
| `{{tenant.razao_social}}` | Tenant | Mirante Consultoria Ambiental Ltda. |
| `{{tenant.cnpj}}` | Tenant | 00.000.000/0001-00 |
| `{{tenant.endereco}}` | Tenant | Rua Exemplo, 000 — Município/UF |
| `{{tenant.banco.*}}` | Tenant | ver Cláusula 2ª |
| `{{tenant.responsavel_tecnico.*}}` | Tenant | ver assinaturas |
| `{{contratante.nome}}` | Property Hub | Cliente Exemplo |
| `{{contratante.qualificacao}}` | Property Hub | brasileiro, produtor rural, portador dos documentos arquivados no caso |
| `{{contratante.endereco}}` | Property Hub | Fazenda Exemplo, Município/UF |
| `{{bloco.imovel.nome}}` | Proposta aceita | Fazenda Exemplo |
| `{{bloco.matriculas}}` | Property Hub (vigentes) | 0.000, 0.001 |
| `{{bloco.servicos}}` | Escopo aceito (Rota) | ver Cláusula 1ª |
| `{{bloco.total}}` | Precificação | R$ 00.000,00 |
| `{{parcelas}}` | Precificação | ver Cláusula 2ª |
| `{{condicoes.foro}}` | Condições do tenant | Comarca de Exemplo/UF |
| `{{condicoes.prazo_execucao}}` | Condições | 00 dias |
| `{{condicoes.vigencia}}` | Condições | até o cumprimento do objeto |
| `{{condicoes.multa_percentual}}` | Condições | 10% |
| `{{condicoes.bonus_malus}}` | Condições (opcional, default off) | ver Cláusula 6ª |

---

# CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CONSULTORIA AMBIENTAL

Pelo presente instrumento particular, de um lado:

**CONTRATADA:** {{tenant.razao_social}}, inscrita no CNPJ sob o nº
{{tenant.cnpj}}, com sede em {{tenant.endereco}}, doravante denominada
**CONTRATADA**;

e de outro lado:

**CONTRATANTE:** {{contratante.nome}}, {{contratante.qualificacao}},
residente e domiciliado em {{contratante.endereco}}, doravante denominado
**CONTRATANTE**;

têm entre si, justo e contratado, o presente Contrato, que se regerá pelas
cláusulas e condições seguintes:

---

## CLÁUSULA 1ª — DO OBJETO

O presente contrato tem por objeto a prestação, pela CONTRATADA, dos
serviços de consultoria ambiental adiante especificados, referentes ao(s)
imóvel(is) e matrícula(s) abaixo:

{{#each blocos}}
### Bloco: {{this.imovel.nome}}

Imóvel: **{{this.imovel.nome}}** — Matrícula(s): **{{this.matriculas}}**

Serviços:

{{#each this.servicos}}
{{this.numero}}. {{this.descricao}}
{{/each}}

| # | Serviço | Valor |
|---|---|---|
{{#each this.servicos}}
| {{this.numero}} | {{this.descricao}} | {{this.valor_formatado}} |
{{/each}}
| | **Total do bloco** | **{{this.total_formatado}}** |

{{/each}}

> *Exemplo fictício (bloco único, 2 serviços):*
>
> ### Bloco: Fazenda Exemplo
> Imóvel: **Fazenda Exemplo** — Matrícula(s): **0.000**
>
> 1. Diagnóstico ambiental do imóvel.
> 2. Regularização do Cadastro Ambiental Rural (CAR).
>
> | # | Serviço | Valor |
> |---|---|---|
> | 1 | Diagnóstico ambiental do imóvel. | R$ 00.000,00 |
> | 2 | Regularização do CAR. | R$ 00.000,00 |
> | | **Total do bloco** | **R$ 00.000,00** |

---

## CLÁUSULA 2ª — DO VALOR E DA FORMA DE PAGAMENTO

O valor total dos serviços é de **{{contrato.total_formatado}}**, a ser pago
da seguinte forma:

{{#each blocos}}
**{{this.imovel.nome}}** — total do bloco **{{this.total_formatado}}**:

| Parcela | Vencimento | Valor |
|---|---|---|
{{#each this.parcelas}}
| {{this.numero}} | {{this.vencimento}} | {{this.valor_formatado}} |
{{/each}}

{{/each}}

Os pagamentos serão realizados por meio de depósito ou transferência para a
conta da CONTRATADA:

- Banco: {{tenant.banco.nome}}
- Agência: {{tenant.banco.agencia}}
- Conta: {{tenant.banco.conta}}
- Titular: {{tenant.banco.titular}}
- Chave PIX: {{tenant.banco.pix}}

> *Exemplo fictício:*
>
> **Fazenda Exemplo** — total do bloco **R$ 00.000,00**:
>
> | Parcela | Vencimento | Valor |
> |---|---|---|
> | 1 | Na assinatura | R$ 00.000,00 |
> | 2 | Na entrega | R$ 00.000,00 |
>
> - Banco: Banco Exemplo (000)
> - Agência: 0000
> - Conta: 00000-0
> - Titular: Mirante Consultoria Ambiental Ltda.
> - Chave PIX: 00.000.000/0001-00

---

## CLÁUSULA 3ª — DAS OBRIGAÇÕES DO CONTRATANTE

O CONTRATANTE obriga-se a:

a) Fornecer à CONTRATADA todos os documentos, informações e acessos
necessários à execução dos serviços;
b) Efetuar os pagamentos nas condições e prazos estabelecidos na Cláusula 2ª;
c) Comunicar à CONTRATADA quaisquer alterações relevantes na situação do
imóvel durante a vigência deste contrato;
d) Arcar com taxas, emolumentos e custas de órgãos públicos e cartórios,
salvo quando expressamente previsto em contrário na Cláusula 1ª.

---

## CLÁUSULA 4ª — DAS OBRIGAÇÕES DA CONTRATADA

A CONTRATADA obriga-se a:

a) Executar os serviços com zelo técnico e observância da legislação
ambiental aplicável;
b) Manter o CONTRATANTE informado sobre o andamento dos trabalhos;
c) Guardar sigilo sobre as informações a que tiver acesso em razão deste
contrato;
d) Entregar os produtos descritos na Cláusula 1ª nos prazos acordados,
ressalvadas as hipóteses de atraso imputáveis a terceiros ou ao CONTRATANTE.

---

## CLÁUSULA 5ª — DA RESCISÃO

O presente contrato poderá ser rescindido:

a) Por acordo entre as partes, a qualquer tempo;
b) Por inadimplemento de qualquer das partes, mediante notificação prévia de
{{condicoes.rescisao_notificacao_dias}} dias;
c) Na hipótese de rescisão por culpa do CONTRATANTE, será devida à CONTRATADA
a remuneração proporcional aos serviços executados, acrescida de multa de
{{condicoes.multa_percentual}} sobre o saldo remanescente.

> *Exemplo fictício:* notificação prévia de 30 dias; multa de 10%.

---

## CLÁUSULA 6ª — DA VIGÊNCIA E DO PRAZO

O presente contrato vigora a partir da data de sua assinatura e permanece em
vigor {{condicoes.vigencia}}. O prazo estimado de execução dos serviços é de
{{condicoes.prazo_execucao}}, contado a partir do recebimento da primeira
parcela e da documentação necessária.

{{#if condicoes.bonus_malus.ativo}}
**Cláusula de desempenho (bônus/malus):** Cumprido o objeto em prazo inferior
ao estimado, o CONTRATANTE poderá conceder bônus de até
{{condicoes.bonus_malus.percentual}} sobre o valor do contrato. Havendo atraso
imputável exclusivamente à CONTRATADA, aplicar-se-á redução (malus) de até
{{condicoes.bonus_malus.percentual}} sobre o valor do contrato.
{{/if}}

> *Nota:* a cláusula de bônus/malus (±20%) é **opcional** e vem **desligada
> por padrão**. Só aparece no documento quando o consultor a ativa.

---

## CLÁUSULA 7ª — DAS DISPOSIÇÕES GERAIS

a) Este contrato representa o acordo integral entre as partes, substituindo
quaisquer entendimentos anteriores;
b) Alterações somente terão validade se formalizadas por escrito e assinadas
por ambas as partes;
c) A tolerância de qualquer das partes quanto ao descumprimento de cláusula
não implica novação nem renúncia de direitos;
d) As partes reconhecem a validade da assinatura eletrônica para todos os
fins deste contrato.

---

## CLÁUSULA 8ª — DO FORO

Fica eleito o foro da {{condicoes.foro}} para dirimir quaisquer controvérsias
oriundas deste contrato, com renúncia a qualquer outro, por mais privilegiado
que seja.

E, por estarem assim justos e contratados, firmam o presente instrumento.

{{contrato.local_data}}

<br>

_______________________________________________
**CONTRATADA** — {{tenant.razao_social}}
{{tenant.responsavel_tecnico.nome}} — {{tenant.responsavel_tecnico.titulo}}
{{tenant.responsavel_tecnico.crea}}

<br>

_______________________________________________
**CONTRATANTE** — {{contratante.nome}}

<br>

**Testemunhas:**

1. _______________________________  Nome: {{testemunha.1.nome}}

2. _______________________________  Nome: {{testemunha.2.nome}}

> *Exemplo fictício:* Local e data: Município Exemplo/UF, 00 de mês de 0000.
> Testemunhas: Testemunha Um Exemplo; Testemunha Dois Exemplo.
