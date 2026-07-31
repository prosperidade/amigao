# Ficha 07 — Workspace do Caso, Regência e Movimentação do Card

> Regente · peça única do workspace — as 6 abas, a grade Etapas × Abas × IAs, a movimentação do card, as travas e as telas das etapas finais (rota, orçamento, contrato)
>
> Fonte única do workspace. Substitui as antigas fichas de Ações, Dados e Fluxo/Gates. Status: validada com a Ísis em 5 simulações de ponta a ponta (entrada → contrato). Pronta para o André (Luis) implementar. Referência cruzada: Ficha 05 (Consolidação), Ficha 06 (esquema cliente/imóvel), Backlog de Ideias e Funcionalidades Futuras.

Convertido fielmente a partir de `Ficha_07_Workspace_Regencia_e_Movimentacao.docx` (anexado por André em 2026-07-06). Este arquivo é a versão canônica versionada — a autoridade de produto é o conteúdo abaixo, não o docx original.

## 0. Como ler esta ficha

O caso vive em um workspace de 6 abas, percorre 7 etapas e é trabalhado por um time de IAs (agentes). Esta ficha responde: o que é cada aba e qual seu prompt (seção 3), quem trabalha em cada etapa e em que ordem (seções 4 e 5), o que move o card (seção 6), o que trava o avanço (seção 7), como são as telas das etapas finais (seção 8), as regras de negócio (seção 9) e o que o backend precisa construir (seção 10).

Bússola: o Regente é a direção que o consultor precisa e a segurança de que ele pode relaxar, porque nada vai se perder. O cliente do Regente é o consultor (B2B).

## 1. Princípios que regem o workspace

- Agentes propõem, consultor decide, sistema grava. Nenhuma automação fecha sozinha o que é decisão (rota, proposta, contrato).
- Toda automação permite input/edição manual. O sistema sugere; o consultor corrige.
- Nenhuma afirmação sem fonte. Rastreabilidade é o antídoto contra alucinação.
- A lei gera as ações — e qualifica os passivos. Nenhum passivo sem lei: a existência de um passivo é uma conclusão legal, não só um fato observado.
- A rota é a entrega de valor. O Caminho Regulatório é o momento em que a Legislação lê o diagnóstico e diz o que as normas determinam. Sem a rota, o Regente não entrega sua proposta de valor — ela não é uma formalidade, é o produto.
- Desacoplamento. As partes falam por camadas intermediárias (staging, entidade Alerta), nunca ponto a ponto.

## 2. Elementos fixos (não pertencem a nenhuma aba)

- **Cabeçalho do imóvel** — nome, matrículas, cliente, CAR, município, área, saúde. Presente em todas as etapas.
- **Painel da etapa** (à direita) — Estado · Travas · Lacunas · Agentes (principal + secundários) + botão "Rodar agentes". Moldura fixa, conteúdo muda por etapa.

## 3. As 6 abas — definição, conteúdo e prompt

Ordem do fluxo de trabalho: Visão geral · Documentos · Conferência · Dados · Ações · Saídas.

### 3.1 Visão geral — a capa do caso (vitrine de leitura)

Primeira leitura ao abrir o caso. Contém: resumo Situação & Intenção + diagnóstico do agente (síntese, passivos com fonte, ações de remediação com artigo de lei e botão "→ Ações"). É output gerado após a consolidação (não existe na E1). No MVP, o diagnóstico vive aqui como leitura viva e NÃO vira documento em Saídas.

**PROMPT (agente Diagnóstico):** "Com a base consolidada, gere a leitura do caso: (1) RESUMO SITUAÇÃO & INTENÇÃO — o que o empreendedor quer, lido do campo de intenção (Entrada) ou da transcrição do áudio; mais a situação ambiental em uma frase. (2) SÍNTESE DIAGNÓSTICA. (3) PASSIVOS E DIVERGÊNCIAS — cada item com FONTE. (4) AÇÕES DE REMEDIAÇÃO — cada uma com ARTIGO DE LEI e ligação para Ações. (5) DOCUMENTOS ESSENCIAIS PENDENTES para o aprofundamento técnico (lista que decide o ramo E3/E4). REGRAS: nenhuma afirmação sem fonte; um passivo só é passivo se a lei o qualifica; não inventar — se faltar dado, declarar lacuna."

### 3.2 Documentos — a boca de entrada

Upload acontece aqui e dispara o Extrator. Três camadas: (a) Mínimo essencial — TRAVA (certidão de matrícula, documento do proprietário, comprovante de endereço, CAR, KML só se não vier pela matrícula); (b) Documentos do caso classificados pelo Extrator (inclui ÁUDIO transcrito); (c) Sugeridos — LACUNAS, puxados da biblioteca conforme intenção/passivos.

**PROMPT (Extrator + checklist):** "Ao receber upload (incluindo ÁUDIO, que deve ser transcrito), classifique o TIPO conforme a biblioteca de 13 categorias; vincule à matrícula/imóvel; extraia campos para o staging (→ Conferência). Permita correção manual. Mantenha o checklist em três camadas: MÍNIMO ESSENCIAL (trava — sem ele não há diagnóstico), DOCUMENTOS DO CASO recebidos, SUGERIDOS (lacunas). Documento faltante gera pendência em Ações."

### 3.3 Conferência — onde o que foi lido vira base

Campos por categoria; consistentes pré-marcados ("Aceitar todos"); divergentes com escolha ativa. "Gravar na base" aciona a Consolidação. Campos gravados permanecem como histórico. Divergência = 3 caminhos: escolher valor · digitar manual · criar ação.

**PROMPT (Conferência; divergências da Auditoria):** "Apresente os campos lidos AGRUPADOS pelas categorias do imóvel. Marque CONSISTENTE ou DIVERGENTE. Consistentes pré-marcados ('Aceitar todos'). Para cada DIVERGÊNCIA, ofereça TRÊS caminhos: escolher um valor (com fonte), digitar manual, ou CRIAR AÇÃO. Apresentação NEUTRA (não sugerir âncora). Ao gravar, acionar a Consolidação. Campos permanecem como histórico. Documento novo conflitante volta como alerta de reconciliação — não sobrescreve."

### 3.4 Dados — a bancada de trabalho

Base consolidada exposta para operar sistemas externos. Campos-chave operacionais destacados e copiáveis (nº SIGEF, CAR, INCRA, NIRF). Três estados do dado: **VALIDADO · CORRETO**, **PENDENTE DE OFICIALIZAÇÃO** (verdade técnica ainda não oficializada → gera ação na proposta), **NÃO VALIDADO**. Áreas reconciliadas (documental × gráfica × total).

**PROMPT (Dados — leitura da base):** "Exiba a base como bancada. DESTAQUE e torne COPIÁVEIS os campos-chave (nº SIGEF, CAR, INCRA/SNCR, NIRF). Agrupe os demais por categoria. Cada campo com FONTE e SELO em três estados: VALIDADO; CORRETO, PENDENTE DE OFICIALIZAÇÃO (gera ação 'atualização de arquivos oficiais'); NÃO VALIDADO. Reconcilie as áreas (documental × gráfica × total)."

Pós-MVP (camada do cliente): logins/senhas das plataformas — criptografados, acesso restrito, registro de acesso.

### 3.5 Ações — o catálogo do que se vende (ferramenta do consultor)

Convergência de quatro fontes: diagnóstico/remediação, divergência da Conferência, documento faltante, dado pendente. No MVP, foco nas ações que geram proposta. A aba Ações é ferramenta do consultor, não do cliente dele. A rota é a somatória das ações. Preço só no Orçamento.

**PROMPT (Ações):** "Reúna as ações que geram PROPOSTA. Para cada uma: SERVIÇO + DESCRIÇÃO/ESCOPO (texto que vai à proposta) + FUNDAMENTO TRIPLO (norma/artigo + regra de sistema federal/estadual + impacto no crédito) + ORIGEM visível + STATUS. Triagem: 'custo meu para entender o caso (interna) ou serviço que o cliente compra (proposta)?'. O consultor edita, adiciona, remove. PREÇO não entra aqui."

### 3.6 Saídas — a mesa de trabalho dos entregáveis (sensível à etapa)

Esta aba é sensível à etapa: ela mostra e deixa trabalhar o entregável da etapa atual, acumulando os das etapas anteriores.

- E1 a E4: vazia — não há entregável ainda (o diagnóstico não vira saída no MVP). Mostra aviso: "os entregáveis aparecem a partir do Caminho Regulatório."
- E5: a Rota.
- E6: Rota + Proposta (a proposta é a mesa de trabalho aqui).
- E7: Rota + Proposta + Contrato — e é aqui, em Saídas, que o consultor faz as edições finais (inclusive a tradução serviço→produto) antes de emitir o arquivo.

Três entregáveis no MVP: Rota, Proposta, Contrato. Cada um com estado (gerado / em revisão / a gerar) e versões (v1, v2…). O contrato fica em Saídas (não retorna a Documentos).

**PROMPT (Saídas — Redator materializa):** "Mantenha a estante de entregáveis, sensível à etapa: vazia em E1–E4; Rota em E5; Rota+Proposta em E6; Rota+Proposta+Contrato em E7. Os entregáveis são gerados pelos agentes e revisados pelo consultor. Em E7, traduza os serviços em PRODUTOS (entregáveis na linguagem do cliente) e permita ao consultor editar antes de emitir. Cada item tem estado e versões. O diagnóstico NÃO é entregável no MVP (vive na Visão geral)."

## 4. A regência — grade Etapas × Abas × IAs

Cada etapa tem uma IA principal (lidera, nomeia a etapa) e uma ordem de execução. "Principal" ≠ "primeira a rodar".

| # | Etapa | Abas que enchem | IA principal | Ordem de execução |
| --- | --- | --- | --- | --- |
| 1 | Entrada da Demanda | Documentos · Dados | Atendimento | Atendimento → (Extrator, se entram docs) |
| 2 | Diagnóstico Preliminar | Conferência · Dados · Visão geral · Ações | Diagnóstico | Extrator → Auditoria → (Diagnóstico ⇄ Legislação) |
| 3 | Coleta Documental | Documentos · Conferência · Dados · Ações | Auditoria | Extrator → Auditoria → (Diagnóstico ⇄ Legislação, condicional) ‖ Monitoramento |
| 4 | Diagnóstico Técnico | Conferência · Dados · Ações · Visão geral | Diagnóstico | Auditoria (aprofunda) → (Diagnóstico ⇄ Legislação) |
| 5 | Caminho Regulatório | Ações · Saídas | Legislação | Legislação (desenha/fecha a rota) → Redator |
| 6 | Orçamento e Negociação | Saídas | Orçamento | Orçamento → Análise Financeira → Redator |
| 7 | Contrato e Formalização | Saídas | Redator | Redator → Análise Financeira |

Diagnóstico ⇄ Legislação são ACOPLADOS (E2 e E4): operação conjunta, não duas chamadas independentes — o passivo só existe porque a lei o qualifica. Legislação tem 2 modos: acoplada ao Diagnóstico (E2, E3-condicional, E4) para qualificar passivos e gerar ações; sozinha (E5) para desenhar e fechar a rota. Transversal: Monitoramento (prazos/validade — gera sempre lacunas, nunca travas). Fora do MVP: Marketing (lead/GTM), Acompanhamento (execução pós-contrato).

## 5. O que cada aba recebe em cada etapa

- **E1 Entrada** — Documentos: primeiros uploads + checklist; Dados: cadastro básico. Visão geral ainda não tem output; Saídas vazia.
- **E2 Diag. Preliminar** — Conferência: campos do intake (protagonista); Dados: base consolidada; Visão geral: nasce o diagnóstico preliminar; Ações: remediação + divergências + pendências. Saídas vazia.
- **E3 Coleta** — Documentos: docs novos; Conferência: campos novos (conflito vira reconciliação); Dados: base atualizada; Ações: atualizadas (cadeia re-roda condicional). Saídas vazia.
- **E4 Diag. Técnico** — Visão geral: atualiza; Conferência: aberta (campos técnicos); Dados: base aprofundada; Ações: refinadas e finais. Saídas vazia.
- **E5 Caminho Regulatório** — Ações: rota fechada; Saídas: Rota.
- **E6 Orçamento** — Saídas: Proposta (mesa de trabalho) + Rota.
- **E7 Contrato** — Saídas: Contrato + Proposta + Rota (edições finais aqui).

## 6. Movimentação do card no Kanban (gatilhos de transição)

Princípio: o card não se move por arraste — move-se por evento. Rodar os agentes de uma etapa produz a saída e avança o card. Card move = gatilho dispara E gate livre (seção 7). Sem essa lógica construída, o card trava na E1.

| Transição | Gatilho (evento) | Efeito |
| --- | --- | --- |
| E1 → E2 | Consultor roda os agentes do intake | Visão geral nasce; diagnóstico preliminar; Conferência preenchida |
| E2 → E3 | Há documentos essenciais a coletar | Abre a Coleta |
| E3 → E4 | Docs novos + agentes → diagnóstico atualizado | Visão/Conferência/Ações/Dados atualizam; Conferência aberta na E4 |
| E2 → E4 (sem coleta) | Não há documentos essenciais pendentes | Mais uma rodada → diagnóstico técnico; pula a E3 |
| E4 → E5 | Diagnóstico técnico confirmado | Legislação desenha a rota |
| E5 → E6 | Rota fechada (validada passo a passo) | Orçamento precifica; proposta |
| E6 → E7 | Proposta aceita | Redator gera o contrato |

A rota (E5) é sempre obrigatória — é a entrega de valor.

## 7. Critérios de saída por etapa (travas) — reconciliados com a movimentação

Trava = torna a próxima etapa impossível (bloqueia). Lacuna = avisa, não bloqueia. O Monitoramento gera sempre lacunas, nunca travas.

| Saída de | Condição de saída (trava) | Destino |
| --- | --- | --- |
| E1 | mínimo essencial recebido + agentes do intake rodados | E2 |
| E2 | diagnóstico gerado + base consolidada (Consolidação rodou) | E3 se há documento essencial pendente; senão E4 |
| E3 | os documentos essenciais pendentes apontados chegaram | E4 |
| E4 | passivos confirmados e quantificados | E5 |
| E5 | rota desenhada e validada passo a passo (todos os passos) | E6 |
| E6 | proposta gerada e aceita pelo cliente | E7 |
| E7 | contrato assinado | — (marco final) |

Entrada da E4 é uma condição ("há documento essencial pendente?"), não "E3 concluída" — o desvio E2→E4 não trava. Saída da E2: condição ≠ destino — a condição de saída é uma só; o destino (E3/E4) é que ramifica.

Dependência crítica: a trava da E2 exige a Consolidação (Ficha 05). Enquanto ela não existir, nenhum caso passa da E2. É o pré-requisito para ligar os gates.

## 8. Telas das etapas finais

### 8.1 E5 — Caminho Regulatório (a rota)

Na E5, a aba Ações assume a forma de rota: sequência ordenada do estado atual ao objetivo. Desenhada pela Legislação a partir do diagnóstico fundamentado + a base legal consolidada (que mapeia a ordem). Lista plana, numerada. Cada passo: nome + fundamento legal + marcação "→ proposta" (faturável) ou "direção" (não faturável). O consultor pode: arrastar para reordenar (cada reordenação ensina a Legislação), editar cada passo, validar passo a passo, e adicionar pontos que o sistema não trouxe. A rota só fecha quando todos os passos estão validados. A rota é mais rica que a proposta. Ao fechar, gera o Documento da Rota em Saídas.

**PROMPT (Legislação — desenha a rota):** "A partir do diagnóstico fundamentado e da base legal consolidada, monte o CAMINHO REGULATÓRIO como SEQUÊNCIA ORDENADA do estado atual ao objetivo. Derive a ORDEM da base legal (pré-requisitos — ex.: CAR antes da DAI; regularizar antes de licenciar). Para cada passo: nome + FUNDAMENTO (artigo/norma/regra de sistema) + marcação ITEM DE PROPOSTA (faturável) ou DIREÇÃO (não faturável). Lista plana numerada. PERMITA: reordenar por arrasto (aprende a ordem), editar, validar passo a passo, adicionar passos. Ao adicionar um ponto, REPROCESSE: confronte com a base; se houver fundamento, incorpore; se NÃO houver, pergunte ao consultor de onde veio a informação (insumo de aprendizado). A rota só fecha quando todos os passos forem validados. Se uma ação mudar em Ações, marque a rota DESATUALIZADA e trave o fechamento até reprocessar."

### 8.2 E6 — Orçamento e proposta

Cada serviço (da rota) com descrição editável (o texto que vai ao cliente) e valor único digitado pelo consultor. Total somado. Prazo e pagamento da proposta inteira (não por ação). Validade da proposta (campo — aparece em todas as propostas reais da Mirante). O sistema guarda os valores para formar um banco de referência. Gera a proposta (simples, comercial; diagnóstico não é anexo no MVP). Aceite manual; recusa → arquiva (caso inativo, reativável) ou renegocia (nova versão).

**PROMPT (Orçamento + Redator — proposta):** "Liste os serviços da rota marcados como faturáveis. Para cada um: descrição editável (texto ao cliente) + valor único (consultor digita). Some o total. Capture PRAZO, PAGAMENTO e VALIDADE da proposta inteira. Gere a PROPOSTA — simples, comercial, objetiva. Guarde os valores no banco de referência. O consultor marca aceita (→ contrato) ou renegocia (nova versão). Recusa → caso inativo no hub, reativável."

### 8.3 E7 — Contrato (layout de 13 blocos, baseado nos contratos reais da Mirante)

O Redator monta o arquivo por encaixe: preenche os blocos variáveis da base/Ações/Orçamento e cola os blocos de texto-modelo fixo. No MVP, bloco único (objeto em blocos por matrícula → backlog).

| # | Bloco | Origem |
| --- | --- | --- |
| 1 | Cabeçalho (título, nº/ano, identificação) | fixo |
| 2 | Partes (cliente + sócios; Mirante) | da base |
| 3 | Responsável técnico / ART | condicional (se há serviço que exige ART) |
| 4 | Imóvel e matrículas | da base |
| 5 | Objeto (finalidade do caso) | da intenção |
| 6 | Escopo — serviços (o que o consultor faz) | das Ações |
| 7 | Produtos — entregáveis (o que o cliente recebe) | tradução serviço→produto, editável em Saídas/E7 |
| 8 | Valor, prazo e pagamento | do Orçamento |
| 9 | Obrigações do contratante (inclui: arca com taxas, ARTs, estudos do órgão) | fixo |
| 10 | Obrigações da contratada (executar, sigilo, ART, informar impedimentos) | fixo |
| 11 | Limites do escopo (custos fora do contrato) | fixo |
| 12 | Cláusulas padrão (rescisão, vigência, confidencialidade, foro) | fixo |
| 13 | Assinaturas (contratante, contratada, RT se houver, 2 testemunhas) | fixo |

Estados do contrato: gerado → aguardando retorno do cliente → concluído (assinado). Assinatura manual/externa no MVP. Caso concluído vira "concluído" no hub do imóvel (pronto para futura execução).

> **✅ ENTREGUE (S5-A · S5-B · S5-C — 2026-07):** E5→E7 fechados ponta a ponta.
> A **proposta nasce da Rota** validada (S5-A, ADR-028); o **contrato nasce da
> proposta ACEITA** nos moldes reais da Mirante, determinístico, com 3 validações
> de consistência (S5-B, ADR-029); a **assinatura MANUAL** (rascunho → enviado →
> assinado, com upload opcional do PDF) fecha o gate E7 e CONCLUI o caso, e as
> **Saídas convergem** proposta/minuta/contrato com download (S5-C, ADR-030). A
> **Comercial** foi ocultada (convergiu em Saídas + /proposals). Teste de integração
> **E1→E7 completo** cobrindo a Ficha inteira. **Falta no MVP: NADA.** Fora do MVP:
> assinatura eletrônica externa (gov.br/Clicksign — dívida #69), multi-bloco/
> multi-titular (#67), tradução serviço→produto editável e contrato de 13 blocos
> ricos (backlog).

**PROMPT (Redator — contrato):** "Monte o contrato por encaixe (bloco único no MVP). Preencha os blocos variáveis: PARTES (base), IMÓVEL E MATRÍCULAS (base), OBJETO (intenção), ESCOPO/SERVIÇOS (Ações), VALOR/PRAZO/PAGAMENTO (Orçamento). TRADUZA os serviços em PRODUTOS (entregáveis na linguagem do cliente) e deixe o consultor editar em Saídas antes de emitir. Inclua o RESPONSÁVEL TÉCNICO/ART só se o escopo tiver peça que o exija. Cole os blocos de TEXTO-MODELO FIXO (cabeçalho, obrigações de cada parte, limites do escopo com custos fora do contrato, cláusulas padrão, assinaturas). Gere a partir da proposta ACEITA E VIGENTE — se a proposta mudou, regenere antes. Estado: gerado → aguardando retorno do cliente → concluído."

## 9. Regras de negócio consolidadas

- **Consolidação é pré-condição dos gates.** Função determinística (não-agente): upsert versionado, chave única por campo, idempotente. Nenhum gate de "base consolidada" abre sem ela.
- **Diagnóstico emite a lista de essenciais faltantes** (mecanismo derivado). Cada passivo "puxa" o documento técnico que falta para quantificá-lo. Lista vazia → E4; com itens → E3. (Tabela curada passivo→documento: backlog.)
- **Travas de desatualização.** Rota desatualizada trava "Fechar rota" até re-rodar a Legislação. Contrato só gera da proposta aceita e vigente — se a proposta mudou, regenera antes.
- **Divergência de área.** Preenche pela fonte de maior prioridade (SIGEF primeiro — o CAR segue o GEO do SIGEF). A retificação vira ação de proposta automática (divergência exige retificação, que tem custo).
- **"Correto, pendente de oficialização" → ação automática.** Ao receber o selo, o sistema cria sozinho a ação "atualização de arquivos oficiais" em Ações (marcada como proposta); o consultor edita/remove.
- **Granularidade (fundamentada na norma).** O passivo é geoespacial (prende-se à área dentro da matrícula). Ações de cartório (retificar, georref) → por matrícula (unitariedade matricial). CAR e rota → por imóvel (grupo de matrículas contíguas do mesmo titular = um imóvel rural, um CAR; Lei 8.629/93 art. 4º I; Estatuto da Terra art. 46 §3º; IN MMA 02/2014 art. 31–32). Matrículas não contíguas → tratadas separadamente. O sistema precisa do campo "matrículas contíguas?".
- **Aprendizado na rota.** Reordenar (arrasto) e adicionar pontos ensinam a Legislação; ao adicionar ponto sem fundamento na base, o agente pergunta ao consultor a origem (ex.: orientação verbal da secretaria).
- **Diagnóstico não tem saída no MVP.** Vive na Visão geral como leitura viva.
- **Tradução serviço→produto** acontece na geração do contrato (E7), em Saídas, feita pelo agente e editável pelo consultor — não é campo da aba Ações.
- **Estados do caso (cauda).** Proposta: gerada → aceita / recusada (→ inativo, reativável) / renegociada. Contrato: gerado → aguardando retorno do cliente → concluído.

## 10. Requisitos para o backend (André / Luis)

- Consolidação (Ficha 05) — item zero; sem ela o card trava na E2.
- Movimentação do card (gatilhos da seção 6) — sem ela o card trava na E1.
- Diagnóstico + Legislação acoplados (E2/E4) — operação conjunta.
- Diagnóstico emite a lista de documentos essenciais pendentes — insumo do ramo E3/E4.
- Travas de desatualização — rota (trava fechamento) e proposta (regenera contrato).
- Reconciliação — documento novo conflitante volta como alerta, não sobrescreve.
- Granularidade matrícula × imóvel — campo "contíguas?"; passivo geoespacial; cartório por matrícula; CAR/rota por imóvel.
- Segurança da camada do cliente (quando desenvolvida) — credenciais criptografadas, acesso restrito, registro de acesso.

## 11. Decisões registradas e pendências

- **Backlog** (artefato próprio): tabela curada passivo→documento; base de conhecimento por situação de fato; camada do cliente; comunicação com o cliente; laudo; execução pós-contrato; captura multicanal; Marketing; + contrato em blocos por matrícula; opções de pagamento na proposta; extrato da rota para o produtor rural.
- **Usuário / Organização (Bloco 0) não iniciado** — no MVP, responsável único.
- **Fora do MVP:** execução regulatória (pós-contrato), captura multicanal, Marketing, Acompanhamento.

## 12. Rodada de fechamento — validação da Isis de 30/07/2026

`fix/polimento-validacao-30-07`. Última rodada de polimento sobre a Ficha 07: 12
achados da consultora percorrendo o caso 15 (Fazenda São Jorge) de ponta a ponta.
O que cada um mudou na Ficha, em uma linha:

| # | Achado dela | O que mudou aqui |
|---|---|---|
| 1 | "Gravar na base deu erro" | Clique que falha grava `consolidar_falhou` na trilha e devolve frase de consultora. Ressalva deixou de ser alarme vermelho. |
| 2 | "Diz auto 492262, abre 492263" / "abre pedido de prorrogação" | §1 *nenhuma afirmação sem fonte* ganha precisão: a fonte é rotulada com o NOME DO ARQUIVO e todo o dossiê é alcançável; doc que não carrega o número entra com confiança baixa. |
| 3 | Rota mandou "defender auto na SEMAD" para auto do IBAMA | §9 — a esfera do passivo (ADR-034) passa a reger a ROTA, não só a busca de corpus. Guard determinístico remove órgão de esfera que o caso não tem. |
| 4 | "Atualizar da IA apagou toda a rota" | §8/§9 — regeneração cria versão (`rota_versoes`), com aviso prévio conferido no servidor. A `dedupe_key` deixou de depender da norma (instável entre execuções). |
| 5 | Gate E5→E6 travado sem dizer o quê | §7 — o blocker passa a contar o que falta ("N sem classificação; M não validados") e apontar a maçaneta. |
| 6 | Botão "rodar agentes" da E4 falhou; a seção de agentes funcionou | §2 — os dois mapas macroetapa→chain viram um só (dívida #66). A diferença restante (fila × execução na hora) está dita na mensagem de erro. |
| 7 | Dois relatórios subidos na E4 não entraram no diagnóstico | §5 — o contexto do diagnóstico passa a levar TRECHO de cada documento do caso, mais recente primeiro, com fonte citável. **Era o gargalo do fluxo real.** |
| 8 | "Passivo gerou o auto; pendência é o que resta" | §0 — a tela e a prosa dos agentes falam **pendência**. O termo interno segue no código. |
| 9 | Biblioteca cita a norma inteira | A fonte cita o **dispositivo** (`Art. 70`) onde o chunk o carrega. A biblioteca da Análise Legal já o renderizava; o buraco era a afirmação do diagnóstico. |
| 10 | "Declare quando não tiver base do órgão" | §1 — cobertura insuficiente é DECLARADA ("base em atualização") em vez de fundamentada com o que há de outra esfera. Sugestão dela, adotada. |
| 11 | "Com seta abre, sem seta não" | Fonte que nomeia documento vira link; id inexistente não vira seta. |
| 12 | E3 pulada aparece vazia | §4 — a Coleta Documental declara-se **estação opcional**, com o caminho do upload à mão. |

**O que esta rodada não fechou** (dívidas nomeadas no REGISTRO): a exceção exata
do item 1 não foi reconstituível — o replay da consolidação contra o staging real
do caso 15 não levanta, e o log da aplicação está fora de alcance; a trilha nova
existe para que a próxima ocorrência seja diagnosticável. Classificação
documental grossa (19 peças de dossiê tipadas `auto_infracao`) e OCR de `.docx`
seguem abertos.

---

Fim da Ficha 07. Peça única do workspace. Referência: Ficha 05 (Consolidação), Ficha 06 (esquema cliente/imóvel), Backlog de Ideias e Funcionalidades Futuras, Mapa-Mestre de Arquitetura.
