# ADR-073 — Motor jurídico: regra como dado, avaliação em três valores, fundamento por ID

- **Data:** 23/09/2026
- **Estado:** proposta (Incremento 4b). Decisões marcadas **[André]** pedem aceite no PR.
- **Incorpora:** [ADR-042 (rascunho)](ADR-042-motor-de-regras-deterministico-RASCUNHO.md), aceito
  **dentro deste ADR** com as correções do Mergulho, como manda o
  [Plano Diretor v1.1](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md) (linhas 631–637 e 831–835).
- **Detalha:** [ADR-070 §10](070-modelo-de-dados-alvo.md) (tabelas de regra, já decididas) e a
  linguagem de regra que o ADR-070 delegou a este ADR.
- **Consome:** [ADR-075](075-zona-normativa-hierarquia-e-recuperacao.md) (fundamento por
  `fonte_versao_id` + `dispositivo`) e o catálogo da 4a.
- **Emenda proposta:** [ADR-039](039-rota-nasce-do-diagnostico-fundamentado.md), no guarda da Rota
  (§8) **[André]**.

## Contexto (medido em 22–23/09)

1. **A Rota hoje não ganha passos.** `materialize_rota` chama a `LegislacaoAgent`
   ([rota_materializer.py:293](../../app/services/rota_materializer.py)), que desde o ADR-069 cai em
   `capacidade_insuficiente`. O materializador levanta `RuntimeError` e o endpoint responde 502. Os
   testes não pegam isso porque fazem mock do agente. O lugar do motor está vago.
2. **Quando havia passos, o fundamento era texto livre.** `fonte_trecho` do LLM virava
   `SourceRef(tipo="legislacao", descricao=<texto>)` sem ID ([rota_materializer.py:93–114]). Nem
   `validar_passo` nem `fechar_rota` conferem norma ([rotas.py:473–564]).
3. **As matrizes da Ísis são autoria, não execução.** O conjunto vigente é v03 (matrizes 2–8) + v05
   (CAR), **325 regras**. A própria Ísis declarou a CAR v03 inválida (aba 99 da v05). O recorte
   Federal + GO tem **254**.
   - Condições são **prosa**: 318 distintas em 325; só cerca de 23 têm comparador.
   - **Só as 37 regras da CAR** ligam fonte por chave e dispositivo (`NOR-FED-001` + "Art. 29").
     As outras 288 citam a fonte em texto livre, e 207 delas não citam ato identificável.
   - Desde a v02, **nenhuma regra bloqueia**: "Bloquear/Impedir" virou "alerta crítico", que exige
     ciência, justificativa e registro, mas não impede avanço.
4. **Os três casos do gate** (produção, tenant 1, só leitura):

   | Caso | Imóvel | Fatos disponíveis |
   |---|---|---|
   | #22 Valéria | Chácara Avalon, Gleba 05 (GO) | 2 documentos pessoais (CNH com OCR falho, RG); **nenhum documento do imóvel**; 0 observações |
   | #23 ELODI | Faz. Retiro dos Olhos d'Água, Glebas 03/04 e Novo Horizonte II (GO) | 4 matrículas, CAR, 1.217 observações (atos registrais, hipoteca, arrendamento, CNIB, dados do CAR) |
   | #25 Jobson | Faz. Abóbora ou Serradinho (GO), novo CAR | escritura, contrato, documento pessoal, KMZ; 72 observações (falecimento declarado, inventário, CCIR/INCRA declarados); **sem CAR** |

5. **O catálogo normativo resolve parte das fontes das regras.**
   - Presentes: Lei 12.651/2012, Decretos 7.830/2012 e 8.235/2014, IN MMA 2/2014, Lei 14.595/2023,
     Leis GO 18.104/2013 e 21.231/2022, IN SEMAD 3/2025 e 9/2024, Leis 6.015/1973 e 5.868/1972.
   - **Ausentes:** IN SEMAD 22/2025 (a do roteamento ao SIGCAR), IN SEMAD 18/2021 e 12/2025,
     Decreto GO 10.470/2024.
   - Todas as presentes estão `bruto`, com vigência não determinada.

## Decisão

### 1. Regra é dado versionado, não código nem prompt

As tabelas são as do ADR-070 §10, criadas agora:

- **`regra`:** identidade estável. Chave de origem `matriz:versao:id`, porque há IDs que colidem
  entre matrizes (REG-GOV-001/002/003).
- **`regra_versao`:** imutável. Guarda aplicabilidade, condição em linguagem restrita, consequência,
  fundamento, severidade, decisão profissional por papel e origem (arquivo, sha256, aba, linha).
- **`conjunto_regras`** e **`conjunto_regras_item`:** o que está publicado e ativo. Rollback é
  reativar o conjunto anterior.
- **`avaliacao_regra`:** append-only, uma linha por regra avaliada numa execução, com entradas por
  referência e faltantes.

A planilha é a fonte de **autoria**. A tradução formal de cada regra é feita pela engenharia,
versionada no repositório (`app/services/motor_juridico/regras/*.yaml`) e importada com origem e
hash. **Nenhum LLM traduz nem ativa regra.**

### 2. Linguagem restrita e lógica de três valores

A condição é uma árvore JSON com um vocabulário fechado:

- **Combinadores:** `todos` (e), `algum` (ou), `nao`.
- **Folha:** `{"fato": <nome>, "op": <eq|ne|in|gt|ge|lt|le|existe|verdadeiro>, "valor": …}`.

**Fato desconhecido é desconhecido, nunca falso.** A avaliação é de Kleene:

- `todos` é falso se algum filho é falso; verdadeiro se todos são verdadeiros; desconhecido nos demais casos.
- `algum` é o dual.
- `nao` inverte e preserva o desconhecido.

**Validação na publicação.** Fato fora do vocabulário, operador desconhecido ou tipo incompatível
**recusa a regra na publicação, com motivo**, em vez de ela virar `erro_execucao` no caso. Regra
cujo texto a engenharia não consegue formalizar fica `nao_formalizavel`, com motivo, e não
publica.

### 3. Fatos: vocabulário fechado, com origem e estado

O motor não lê texto. Lê um **retrato de fatos** montado de forma determinística a partir do caso:
documentos por classe, observações do extrator (ADR-069/070), declarações do caso e cadastro do
imóvel. Cada fato carrega:

- `valor`;
- `estado` (`determinado` ou `desconhecido`);
- `origem` (ids de documento, observação ou declaração);
- `revisao` (`revisada` ou `nao_revisada`).

Vocabulário do gate:

| Fato | Tipo | Como se determina |
|---|---|---|
| `caso.uf` | texto | UF do imóvel do caso |
| `imovel.natureza` | `rural`/desconhecido | demanda de CAR declarada na abertura ou CAR no dossiê. O CAR só existe para imóvel rural. Nos demais casos, **desconhecido** |
| `car.no_dossie` | booleano | documento de classe `car` ou observação de protocolo/registro do CAR |
| `dominio.matriculas_no_dossie` | inteiro | documentos de classe `matricula` |
| `ccir.no_dossie` | booleano | documento de classe `ccir` |
| `titular.falecimento_declarado` | booleano/desconhecido | observação `falecimento_declarado`. **Ausência da observação é desconhecido, não "vivo"** |

Fatos "do dossiê" (`*_no_dossie`) afirmam o que **consta nos autos**, não o que existe no mundo.
É isso que a regra REG-BR-CAR-001 pede: "Não confundir ausência de acesso com ausência de cadastro".

### 4. Seis estados de avaliação, aplicabilidade antes da condição

| Estado | Quando |
|---|---|
| `nao_aplicavel` | a aplicabilidade (UF, esfera, objetivo) exclui o caso; a condição nem é avaliada |
| `aplicavel_disparou` | condição verdadeira |
| `aplicavel_nao_disparou` | condição falsa |
| `indeterminado` | condição desconhecida. Grava os fatos **faltantes** |
| `conflito` | reservado para a tabela de conflito de esferas (§9); fora do gate |
| `erro_execucao` | exceção na avaliação; nunca silenciosa |

"Zero regras disparadas" aparece como isso, **não como regularidade**. O relatório lista as
avaliadas, as não aplicáveis e os faltantes.

### 5. Consequência: três tipos, nenhum bloqueio

Segue a v02 da Ísis, em que restrição interna vira alerta crítico:

- **`passo_rota`:** propõe um passo da Rota (título, descrição, órgão, fase).
- **`coleta`:** propõe um passo de coleta de documento ou informação.
- **`alerta_critico`:** exige ciência com justificativa. Não impede avanço, conclusão nem protocolo.
  **A Rota não fecha** enquanto houver alerta crítico da execução corrente sem ciência registrada.

**Indeterminado vira coleta.** Quando uma regra aplicável fica `indeterminada`, cada fato faltante
vira um passo de coleta ("Confirmar: natureza do imóvel"), com o fundamento da regra que precisa
dele. É assim que um caso sem documentos do imóvel (o #22) chega a uma Rota fundamentada: uma Rota
de coleta, e não uma Rota vazia ou inventada.

### 6. Fundamento por ID, resolvido na avaliação, nunca por semelhança

A regra declara `fonte` (identidade canônica do ADR-075, `tipo|ente|orgao|numero|ano`) + `artigo`
(+ `paragrafo`). A tradução da chave da planilha (`NOR-FED-001`) para identidade é **tabela curada
no YAML da regra**, não derivação. O mapeamento automático errou o órgão de todas as IN da SEMAD
(`semadgosemad`).

Na avaliação, o motor resolve **por identidade**, com a política `interno` do ADR-075: versão
`validado` ou `proposto`, não bloqueada, vigente ou de vigência não determinada (marcada). O
dispositivo tem de existir **naquela versão**. O resultado é um de dois:

- **resolvido:** `(fonte_versao_id, dispositivo_id, caminho)`, gravado na avaliação e no passo;
- **não resolvido,** com a razão: `fonte_ausente`, `versao_nao_elegivel` (ex.: todas `bruto`) ou
  `dispositivo_ausente`.

**Norma ausente não ganha substituta por semelhança.** Passo com fundamento não resolvido é
proposto com essa marca e **não pode ser validado** (§7). O consultor remove com motivo, ou a
curadoria traz a fonte.

**Por que a política `interno` e não `peca`.** A Rota é artefato interno e comercial (escopo da
proposta), não peça assinada. Quando o conteúdo da Rota entrar numa peça, vale a política `peca`
(só `validado`). Consequência: **`bruto` não serve de fundamento de passo**; a curadoria precisa ao
menos propor a fonte (ADR-075 §4).

Quando a planilha não traz artigo (ex.: "Dados do imóvel", "Orientações INCRA"), o dispositivo
**proposto pela engenharia** entra com `origem_dispositivo = proposta_engenharia` e depende da
homologação da Ísis (§10).

### 7. Integração com a Rota

- **Serviço novo:** `gerar_rota_pelo_motor(process_id)`. Avalia o conjunto ativo e converte
  `passo_rota` e `coleta` em `Etapa`. Depois **reusa** `_upsert_rota`/`_reconcile_passos`, com
  reconciliação aditiva, lápides, versões, guarda de esfera e `desatualizada`. Nada disso muda.
- **Colunas novas em `rota_passos`:** `origem = 'motor'` (valor novo do enum), `origem_avaliacao_id`
  → `avaliacao_regra`, `fundamento_fonte_versao_id` → `fonte_normativa_versao` e
  `fundamento_dispositivo_id` → `dispositivo`. `norma_ref` e `sources` continuam como **exibição**,
  derivados do `caminho`; a tela atual mostra "com fonte" sem mudar.
- **`validar_passo` de passo `motor`:** exige fundamento resolvido e **verificado de novo** por
  `citacao.verificar(destino="interno")` no momento da validação. A fonte pode ter mudado de estado
  entre a geração e a validação. Passos manuais seguem como hoje (`origem_manual_nota`).
- **`fechar_rota`:** mais uma pré-condição, a ciência de todo alerta crítico da execução corrente.

### 8. Guarda da Rota: avaliação do motor no lugar do diagnóstico assinado **[André]**

O ADR-039 exige diagnóstico assinado para gerar Rota, porque a Rota tem de nascer de fundamento
revisado. **Proposta:** a Rota **gerada pelo motor** dispensa o diagnóstico assinado. Nela, cada
passo carrega regra homologada, fatos com origem e norma por ID, e o consultor valida passo a passo
e dá ciência dos alertas. Isso é mais fundamentado do que o diagnóstico por LLM. O caminho da
`LegislacaoAgent` (quando voltar) mantém o guarda do ADR-039.

### 9. Conflito de esferas

O protocolo de 16 degraus da aba 98 vira **tabela de decisão homologada**. **Fora do gate.**

- Nenhuma regra do gate declara conflito.
- O estado `conflito` fica reservado.
- Vale o A4 do ADR-075: sem regra homologada de conflito, a afirmação fica `conflitante` com
  tarefa de revisão.
- Proibido o atalho "federal sempre ganha" ou "mais restritiva ganha" (aba 98, regra-mãe).

### 10. Ciclo de vida e alçada

- **Estados da `regra_versao`:** `rascunho → homologada`, ou `nao_formalizavel`, com motivo.
- **Publicação:** é do **`conjunto_regras`** (`rascunho → publicado → ativo`; um ativo por
  escopo).
- **Homologar regra** é um papel novo de curadoria, **`homologar_regra`**, por área, na mesma tabela
  `papel_curadoria` do A2. A Ísis é a titular hoje. Superusuário concede, mas não homologa.
- **Só avalia regra homologada de conjunto ativo.** A tradução formal das regras do gate nasce
  `rascunho` e depende da Ísis (**Q-ISIS-22**).

### 11. Camada do tenant **[André]**

O ADR-070 delegou a este ADR decidir se a camada do tenant pode desativar ou sobrepor regra da
base. **Proposta:** **não pode.** O tenant só **acrescenta** regras próprias (`tenant_id`
preenchido), que nunca vazam para outro tenant. Divergência entre regra do tenant e da base é
`conflito` registrado, não sobreposição silenciosa. Motivo: sobreposição por tenant apagaria a
trilha de por que um passo sumiu.

### 12. Parâmetros provisórios declarados

- **Q-ISIS-18** (ficha de tipologia = `exigencia`): nenhuma regra do gate cita ficha. Quando citar,
  vale o parâmetro da 4a.
- **Q-ISIS-19** (índice das coletâneas): o motor só resolve fundamento em fonte com **identidade
  determinada**. Ato que está em segmento `nao_determinado` de coletânea não serve de fundamento até
  a revisão. A IN SEMAD 22/2025 pode estar num deles; a lista da Ísis encurtaria a busca.

### 13. Gate do Incremento 4b

As regras necessárias para **#22, #23 e #25 (Federal + GO)** chegarem a uma **Rota validada com
fundamento por ID**, provadas em dev com percurso autenticado. O catálogo integral das 325 fica fora
do gate e entra **por família**, com importador recorrente.

**Recorte do gate** (tradução formal em `regras/gate_4b.yaml`, origem na CAR v05 e na Fundiária v03):

| Regra | Condição formal (resumo) | Consequência | Fundamento |
|---|---|---|---|
| REG-BR-CAR-001 | `imovel.natureza = rural` e não `car.no_dossie` | `passo_rota`: verificar inscrição e inscrever no CAR | Lei 12.651/2012, art. 29 (matriz) |
| REG-BR-CAR-002 | `car.no_dossie` e `dominio.matriculas_no_dossie = 0` | `alerta_critico` + `coleta` da matrícula | Lei 12.651/2012, art. 29 (matriz) |
| REG-BR-CAR-007 | `dominio.matriculas_no_dossie ≥ 2` | `coleta`: mapear componentes do imóvel | IN MMA 2/2014, art. 2º (proposto; matriz diz "Dados do imóvel") |
| REG-FUN-002 | `imovel.natureza = rural` e não `ccir.no_dossie` | `passo_rota`: emitir/regularizar o CCIR | Lei 5.868/1972, art. 2º (proposto; matriz diz "Orientações INCRA") |
| REG-FUN-012 | `titular.falecimento_declarado` | `alerta_critico` (possível sucessão: classificar cessão, sucessão ou ocupação) + `coleta` da prova da sucessão | Código Civil, art. 1.784 (proposto; matriz diz "Regras de titulação") — **ausente do catálogo** (prova do caminho "norma ausente") |
| REG-GO-CAR-001 | `caso.uf = GO` e `imovel.natureza = rural` | `passo_rota`: operar o CAR no SIGCAR (SEMAD-GO) | IN SEMAD 22/2025 — **ausente do catálogo** |

**Formalização parcial, declarada.** Quatro das seis traduções cobrem só um ramo do texto da
matriz, e o YAML diz qual: REG-BR-CAR-002 ("usuário tenta concluir titularidade apenas pelo CAR")
vira "há CAR e nenhuma matrícula nos autos", o retrato que torna essa conclusão possível;
REG-FUN-002 cobre o CCIR **ausente**, não o vencido nem a taxa não quitada (fatos fora do
vocabulário do gate); REG-FUN-012 ("pessoa na posse não corresponde ao titular") dispara pelo
**falecimento declarado do titular**, um gatilho suficiente de sucessão, e não pelos demais;
REG-GO-CAR-001 ("UF = GO") acrescenta imóvel rural, porque o CAR só existe para ele. A
homologação da Ísis (Q-ISIS-22) decide se cada recorte serve.

**Prova:** positivo, negativo, desconhecido, não aplicável e norma ausente. Regras aplicadas aos três
casos em dev, com percurso autenticado até a Rota fechada com fundamento por ID em todo passo
validado.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Regras como `if` Python | O próprio Plano Diretor proíbe; sem trilha nem homologação por versão |
| Regras como trechos no prompt / RAG | Similaridade não decide aplicabilidade; ADR-042 já descartou |
| LLM traduzindo prosa em condição automaticamente | Tradução sem conferência humana ativaria regra errada com cara de certa |
| Desconhecido tratado como falso | Faria "sem CAR no dossiê" virar "imóvel sem CAR" e ausência de óbito virar "titular vivo" |
| Fundamento por similaridade quando a fonte falta | "Norma ausente não ganha substituta" (Plano, ADR-075) |
| Política `peca` para fundamento de passo | A Rota não é peça assinada; exigiria validação da Ísis de toda fonte antes de qualquer Rota existir |
| Alerta crítico bloqueando | Contraria a v02 da Ísis |

## Consequências

- O motor ocupa o lugar vago da Rota **sem depender da Legislação**, que segue desligada até as
  sondas da 4a ficarem verdes.
- Toda Rota do motor exige curadoria mínima das fontes citadas (`proposto`) e homologação das regras.
  **Sem Ísis, nada disso roda em produção.** Em dev, as duas coisas são feitas como prova, com nota
  dizendo isso.
- O importador recorrente das 325 e a tabela de conflito de esferas são as próximas famílias, não
  o gate.
