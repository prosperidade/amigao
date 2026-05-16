# ADR-004 · Regente Ambiental como nome do produto; Amigão como codinome técnico

**Status:** Aceito
**Data:** 2026-05-15
**Decisores:** sócia + tecnologia
**Substitui:** decisão informal anterior que mantinha os dois nomes em paralelo sem hierarquia explícita

---

## Contexto

Desde o início do projeto, dois nomes coexistiram:

- **Amigão do Meio Ambiente** — nome usado no repositório (`Amigao_do_Meio_Ambiente`), em `PROJECT_NAME` da configuração, em e-mails transacionais (`@amigao.com`), em métricas Prometheus (`amigao_*`), em bucket MinIO (`amigao-docs`), em banco de dados (`amigao_db`) e em diversos pontos do código.
- **Regente Ambiental** — nome usado na landing pública (`regenteambiental.com.br`), em e-mails da waitlist (`contato@regenteambiental.com.br`), no design visual recente da sócia, e em diversos documentos das últimas semanas (Sprint Waitlist, RELATORIO_WAITLIST, MUDANCAS_REGENTE).

A coexistência sem decisão formal gerou:

1. Confusão de marca em material externo (parceiros, investidores potenciais, sócia).
2. Inconsistência em pontos de contato (e-mail de waitlist é Regente, e-mail transacional é Amigão).
3. Dificuldade de onboarding (quem chega no projeto não entende a relação entre os dois nomes).
4. Pergunta em aberto registrada no relatório de Fase 0 da Sprint Waitlist (divergência #4).

A decisão precisava ser tomada antes da reescrita da documentação para que a documentação nova fosse coerente.

## Decisão

**Regente Ambiental** é o nome do produto. Aparece em toda comunicação visível ao usuário, ao mercado, a parceiros, a órgãos públicos e em material institucional.

**Amigão do Meio Ambiente** torna-se codinome técnico interno. Permanece em identificadores de infraestrutura que existem há mais tempo e cuja renomeação tem custo desproporcional ao ganho.

A distinção é equivalente à de muitas empresas que mantêm codinomes internos diferentes do nome comercial. O Regente não tem dois produtos; tem dois nomes em camadas diferentes do sistema, com propósitos distintos.

## O que muda imediatamente

| Camada | Ação |
|---|---|
| Branding visível (login, header, e-mails, PDFs gerados) | Renomear para Regente Ambiental |
| Configuração lógica (`PROJECT_NAME`, `EMAILS_FROM_NAME`, User-Agent dos crawlers) | Renomear para Regente Ambiental |
| Repositório GitHub | Renomear de `Amigao_do_Meio_Ambiente` para `regente-ambiental` |
| Documentação nova | Toda escrita já usa Regente Ambiental |
| `.env.example` | Atualizar valores default de branding |

Detalhes operacionais dessa migração ficam em [`../manifesto/02-IDENTIDADE.md`](../manifesto/02-IDENTIDADE.md).

## O que NÃO muda agora

| Identificador | Por quê mantemos |
|---|---|
| `POSTGRES_DB=amigao_db` | Renomear implica migração de dados em produção. Sem ganho para o usuário. |
| `BUCKET_NAME = "amigao-docs"` (MinIO) | Implica copiar todos os documentos armazenados. Risco operacional alto. |
| `REALTIME_EVENTS_CHANNEL = "amigao_events"` (Redis) | Rolling deploy ficaria dessincronizado temporariamente. |
| Métricas Prometheus `amigao_*` (13 métricas) | Quebra dashboards Grafana e alertas pré-configurados. |
| `ops/prometheus-alerts.yml` | Mesmo motivo das métricas. |

Esses identificadores podem migrar em sprint futura dedicada, com plano próprio. Não há urgência.

## Consequências

**Positivas:**
- Comunicação externa coerente e clara
- Onboarding de nova pessoa no projeto fica óbvio
- Material institucional para reunião SEMAD-GO e similares pode ser produzido sem ambiguidade
- Encerra pergunta em aberto da Sprint Waitlist (divergência #4)

**Negativas:**
- Convivência com codinome técnico "amigao" em infraestrutura por tempo indeterminado pode confundir quem mexe em métricas/banco sem ler este ADR
- Necessidade de manter este ADR vinculado a `02-IDENTIDADE.md` para que qualquer leitor entenda a coexistência

**Mitigação da negativa:** o documento [`../manifesto/02-IDENTIDADE.md`](../manifesto/02-IDENTIDADE.md) explica a relação entre os dois nomes em primeiro plano. Comentários estratégicos no `app/core/config.py` e no `.env.example` apontam para este ADR.

## Alternativas consideradas

**Alternativa A — Manter Amigão como nome principal e Regente como submarca.**
Rejeitada. A marca pública já está vinculada ao domínio `regenteambiental.com.br` e ao discurso recente da sócia. Voltar para Amigão exigiria refazer landing, material institucional e narrativa.

**Alternativa B — Renomear tudo (incluindo banco, bucket, métricas) numa única migração grande.**
Rejeitada. Custo alto, risco operacional alto, ganho zero para usuário final. A renomeação visível resolve 100% da confusão externa; a renomeação técnica pode esperar momento adequado.

**Alternativa C — Manter os dois nomes em paralelo sem decisão hierárquica.**
Rejeitada. Foi o estado anterior, e gerou os problemas que motivam este ADR.

## Status de execução

| Item | Estado |
|---|---|
| Decisão tomada e registrada | ✅ 2026-05-15 |
| Patch de renomeação visível preparado | Pendente |
| Repo GitHub renomeado | Pendente |
| Documentação nova consistente | ✅ em curso (Onda 3) |
| ADR público | ✅ este documento |
