# ADR-009 · Frentes mobile e portal cliente congeladas até validação do painel consultor

**Status:** Aceito
**Data:** 2026-05-15
**Decisores:** sócia + tecnologia
**Relacionado:** [`004-regente-vs-amigao.md`](./004-regente-vs-amigao.md), [`../manifesto/04-ROADMAP.md`](../manifesto/04-ROADMAP.md)

---

## Contexto

O Regente Ambiental tem três frentes de software documentadas como parte do produto:

- **Painel do consultor** (`frontend/`) — React 18 + Vite + TypeScript. Frente ativa, foco do MVP.
- **Portal do cliente** (`client-portal/`) — Next.js 16 (App Router) + TypeScript. Existe no repositório, declarado em `docker-compose.yml`, parcialmente desenvolvido em sprints anteriores.
- **App de campo** (`mobile/`) — Expo + React Native + SQLite offline. Existe no repositório, parcialmente desenvolvido.

Documentação fundacional do projeto (26/03/2026) descrevia as três frentes como pilares simultâneos. Auditorias subsequentes (`auditoria3implemantation.md`, 03/04) registraram maturidade desigual: painel ~75%, portal cliente ~70%, mobile ~30%.

A partir da Sprint Regente (17/04 em diante), o esforço se concentrou no painel do consultor — sócia como primeira usuária, fluxo do consultor sendo o que prova ou não prova o produto. Portal cliente e mobile **deixaram de receber commits**, mas continuaram presentes no repositório, no docker-compose, e em documentos antigos como se estivessem em andamento.

Essa ambiguidade gerou:

1. Confusão sobre o estado real do produto em conversas com investidores/parceiros.
2. Documentação que descreve três frentes ativas quando uma está ativa.
3. Esforço periódico de manutenção (atualização de dependências, build) em código que não está sendo desenvolvido.
4. Risco de drift técnico — código parado por meses tende a apodrecer.

## Decisão

**Portal do cliente (`client-portal/`) e app mobile (`mobile/`) ficam formalmente congelados até validação do painel do consultor.**

Congelado significa, especificamente:

- **Código permanece no repositório.** Não é deletado. Não vira `_archive/`.
- **Build não é mantido em CI.** Não há expectativa de que `npm run build` funcione a cada commit. Quando descongelarmos, faremos a atualização de dependências necessária.
- **Não recebe commits funcionais.** Apenas mudanças triviais (correção de typo, atualização de README local, etc.) podem entrar.
- **Não é apresentado em pitch ou demo como "em andamento".** É apresentado como "frente do produto, atualmente em pausa estratégica para foco no painel consultor".
- **Documentação reconhece o estado** — tanto no manifesto quanto no `ESTADO_ATUAL.md` quanto neste ADR.

O critério de descongelamento é binário: **o painel do consultor está validado em produção com a sócia rodando casos reais sem suporte técnico.** Quando isso for verdade, este ADR é revisado e uma das duas frentes (não as duas) é descongelada primeiro.

## Ordem provável de descongelamento

Quando o critério de validação for atingido:

1. **Portal do cliente primeiro.** Razão: clientes da sócia já demandam acompanhamento; portal é o ponto de contato mais direto com receita expandida (cliente acompanha, aprova proposta, assina contrato).
2. **App mobile depois.** Razão: depende de portal cliente operacional para fazer sentido (cliente final acompanha pelo portal; equipe técnica usa app para coleta). Mobile sem portal é capacidade técnica sem aplicação imediata.

A ordem pode mudar se a primeira reunião com a SEMAD-GO ou com banco/cooperativa indicar necessidade prioritária inversa.

## Consequências

**Positivas:**
- Foco operacional claro — equipe de desenvolvimento não se divide entre 3 frentes simultâneas
- Comunicação externa coerente — pitch, deck, conversa com parceiro mencionam o estado real sem confusão
- Documentação clara para qualquer pessoa nova no projeto
- Eliminação do risco de manter código semi-pronto que apodrece sem ser usado

**Negativas:**
- Dependências do `client-portal/` e do `mobile/` ficarão desatualizadas durante o congelamento. Ao descongelar, será necessário esforço de atualização (provavelmente 1-2 semanas dedicadas a cada).
- Cliente potencial que quiser ver "tudo pronto" precisa entender a estratégia de fases.
- Repositório fica com pastas "frias" — quem clona o repo precisa saber o que está vivo e o que está congelado.

**Mitigação da negativa:** README da raiz e `docs/manifesto/02-IDENTIDADE.md` declaram explicitamente o estado de cada frente. Comentário no `docker-compose.yml` (próximo ao serviço `client-portal`) também aponta para este ADR.

## Status no docker-compose

O serviço `client-portal` continua declarado em `docker-compose.yml` para preservação histórica e facilidade de descongelamento futuro, mas:

- Não há expectativa de que esteja funcional em qualquer momento durante o congelamento.
- Em ambientes de homologação/produção, o serviço pode ser comentado ou removido do `compose.override.yml` sem prejuízo.
- App mobile (`mobile/`) não tem serviço em docker-compose por natureza (mobile não roda em container).

## Alternativas consideradas

**Alternativa A — Manter as três frentes em desenvolvimento paralelo.**
Rejeitada. Equipe pequena, contexto de validação inicial, três frentes em paralelo dilui foco e atrasa a única que pode validar o produto.

**Alternativa B — Arquivar definitivamente portal e mobile (mover para `_archive/`).**
Rejeitada. As duas frentes são parte da visão de longo prazo do produto. Arquivar manda sinal de "produto reduzido", não de "produto faseado".

**Alternativa C — Manter sem decisão formal (estado anterior).**
Rejeitada. É o que motivou este ADR.

## Revisão

Este ADR deve ser revisitado quando o painel consultor for validado em produção com a sócia. Marco de validação: 1 caso real conduzido do início ao fim por consultor que não seja a sócia, sem intervenção técnica.

Estimativa atual de marco: **Janela 2 do roadmap (3-6 meses)**.
