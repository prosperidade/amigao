# Seed de Dados — Desenvolvimento e Homologação
**Projeto:** Plataforma Ambiental SaaS  
**Versão:** 1.0  
**Data:** 26/03/2026

---

## 1. Objetivo

Definir o conjunto de dados mínimo para que qualquer desenvolvedor ou agente de IA consiga iniciar o sistema em ambiente de desenvolvimento com um cenário realista e testável, sem depender de dados de produção.

Sem seed padronizado, cada sessão começa do zero. Testes ficam inconsistentes. A homologação com a cliente fica difícil porque cada ambiente tem dados diferentes.

---

## 2. Princípios do seed

- **Realista:** usar dados que simulem o negócio real (município goiano, tipo de processo ambiental, área em hectares plausível)
- **Completo:** cobrir todos os status da máquina de estados para testar transições
- **Seguro:** sem dados reais de clientes ou propriedades
- **Idempotente:** rodar o seed duas vezes não duplica dados
- **Documentado:** cada item do seed tem um propósito explícito

---

## 2.1 Estado implementado hoje no repositório

O estado atual do checkout **não** usa uma pasta `seed/` modularizada. Hoje o seed implementado e suportado pela stack local e:

- `python seed.py` para execucao manual
- `python seed.py` no startup da `api` via Docker Compose

O comportamento implementado hoje:

- seed idempotente em arquivo unico `seed.py`
- tenant principal `Amigao Headquarters`
- 4 usuarios seed reais no banco local
- 3 clientes seed
- processos seed cobrindo todos os status da maquina atual
- tarefas encadeadas para o processo em `execucao`
- sincronizacao opcional de senhas quando `SEED_*_PASSWORD` estiver definido

Variaveis de ambiente relevantes no estado atual:

- `SEED_ADMIN_PASSWORD`
- `SEED_CONSULTANT_PASSWORD`
- `SEED_CLIENT_PASSWORD`
- `SEED_FIELD_PASSWORD`
- `SEED_RESET_PASSWORDS`

---

## 3. Estrutura do seed

### 3.1 Tenant principal (escritório fictício)

```python
TENANT_SEED = {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "Consultoria Ambiental Verde Cerrado",
    "legal_name": "Verde Cerrado Consultoria Ambiental Ltda",
    "document_number": "12.345.678/0001-90",
    "tenant_type": "consultoria",
    "plan": "professional",
    "status": "active",
    "primary_color": "#2D7A3A",
}
```

---

### 3.2 Usuários por perfil

| Perfil | Nome | E-mail | Senha (dev) | Propósito |
|--------|------|--------|-------------|-----------|
| admin | Administrador Global | admin@amigao.com | Seed@2026 | Testar configurações, observabilidade e RBAC |
| consultor | Consultor Demo | consultor@amigao.com | Seed@2026 | Testar fluxo principal interno |
| tecnico_campo | Tecnico de Campo Demo | campo@amigao.com | Seed@2026 | Testar tarefas e fluxo operacional |
| cliente_portal | Cliente Demo | cliente@amigao.com | Seed@2026 | Testar login e fluxos do portal do cliente |

> **Importante:** senhas do seed são apenas para desenvolvimento local. Nunca aplicar em staging ou produção.
>
> Na stack Docker local, a senha fica determinística quando `SEED_*_PASSWORD` estiver definido. O template `.env.example` atual usa `Seed@2026`.

---

### 3.3 Clientes

```
Cliente 1 — Agricultor PF
  Nome: José Alves Neto
  CPF: 000.000.001-91 (fictício)
  Cidade: Senador Canedo, GO
  Status: active
  Origem: whatsapp
  Propósito: testar fluxo principal com PF rural

Cliente 2 — Fazenda PJ
  Razão Social: Fazenda Boa Vista Agropecuária Ltda
  CNPJ: 00.000.002/0001-00 (fictício)
  Cidade: Goianésia, GO
  Status: active
  Origem: parceiro
  Propósito: testar fluxo com PJ e vínculo de imóvel

Cliente 3 — Cooperativa
  Razão Social: Cooperativa Agropecuária do Cerrado
  CNPJ: 00.000.003/0001-00 (fictício)
  Cidade: Rio Verde, GO
  Status: lead
  Origem: email
  Propósito: testar status lead e conversão
```

---

### 3.4 Imóveis rurais

```
Imóvel 1 — Fazenda Boa Vista
  Vinculado ao Cliente 2
  Município: Goianésia, GO
  Área: 850.00 ha
  CAR: GO-5208400-XXX0001 (fictício)
  Status CAR: ativo
  CCIR: 1234567890 (fictício)
  Bioma: Cerrado
  Geometria: polígono simples em área rural de Goiânesia
    (coordenadas EPSG:4674 — Sirgas 2000)
    POLYGON((-49.05 -15.32, -49.03 -15.32, -49.03 -15.30, -49.05 -15.30, -49.05 -15.32))
  has_embargo: false

Imóvel 2 — Sítio São João
  Vinculado ao Cliente 1
  Município: Senador Canedo, GO
  Área: 45.50 ha
  CAR: GO-5218805-XXX0002 (fictício)
  Status CAR: pendente_analise
  CCIR: 9876543210 (fictício)
  Bioma: Cerrado
  Geometria: polígono pequeno próximo a Goiânia
    POLYGON((-49.10 -16.72, -49.08 -16.72, -49.08 -16.70, -49.10 -16.70, -49.10 -16.72))
  has_embargo: true
  Propósito: testar fluxo de desembargo
```

---

### 3.5 Processos — um em cada status

| # | Tipo | Cliente | Status | Propósito do Teste |
|---|------|---------|--------|--------------------|
| P001 | Retificação CAR | Cliente 1 | `triagem` | Testar entrada e diagnóstico |
| P002 | Desembargo IBAMA | Cliente 1 | `diagnostico` | Testar Agente Extrator |
| P003 | Licença Ambiental | Cliente 2 | `planejamento` | Testar Agente Orquestrador |
| P004 | Outorga de Água | Cliente 2 | `execucao` | Testar execução de tarefas |
| P005 | Regularização Fundiária | Cliente 2 | `protocolo` | Testar protocolo e docs |
| P006 | CAR Novo | Cliente 3 | `aguardando_orgao` | Testar acompanhamento |
| P007 | PRAD | Cliente 1 | `pendencia_orgao` | Testar ciclo de pendência |
| P008 | Averbação RL | Cliente 2 | `concluido` | Testar processo encerrado |
| P009 | Licença Prévia | Cliente 3 | `cancelado` | Testar status cancelado |

---

### 3.6 Tarefas de exemplo (para P004 — em execução)

```
Tarefa 1: Coleta de documentos fundiários
  Status: concluida
  Responsável: consultor
  Origem: manual

Tarefa 2: Visita técnica ao imóvel
  Status: concluida
  Responsável: tecnico_campo
  Origem: ai (marcada)

Tarefa 3: Levantamento topográfico
  Status: aguardando
  Responsável: parceiro (Geo Topografia)
  Dependência: Tarefa 2
  Origem: manual

Tarefa 4: Elaboração do memorial descritivo
  Status: em_progresso
  Responsável: consultor
  Dependência: Tarefa 3
  Origem: ai (marcada)

Tarefa 5: Montagem do processo para protocolo
  Status: backlog
  Responsável: consultor
  Dependência: Tarefa 4
  Origem: rule
```

---

### 3.7 Documentos de exemplo

```
DOC-001: Matrícula do Imóvel
  Processo: P004
  Tipo: matricula
  OCR Status: processed
  Confiança: 0.91
  Arquivo: /seed/docs/matricula_exemplo.pdf (PDF de 3 páginas com texto real típico)

DOC-002: CCIR
  Processo: P004
  Tipo: ccir
  OCR Status: processed
  Confiança: 0.97

DOC-003: CAR (print borrado)
  Processo: P001
  Tipo: car_declaracao
  OCR Status: review_required
  Confiança: 0.54
  Propósito: testar fila de revisão OCR com baixa confiança

DOC-004: CPF do produtor
  Processo: P001
  Tipo: documento_pessoal
  OCR Status: processed
  Confiança: 0.99
```

---

### 3.8 Base regulatória mínima (para Agente Regulatório)

```
NORMA-001:
  Título: Código Florestal Brasileiro
  Tipo: lei_federal
  Código: Lei 12.651/2012
  Jurisdição: federal
  Status: active
  Chunks: 50 chunks aproximados (capítulos principais)

NORMA-002:
  Título: Resolução CONAMA 237/1997 — Licenciamento
  Tipo: resolucao
  Código: CONAMA 237/1997
  Jurisdição: federal
  Status: active
  Chunks: 20 chunks

NORMA-003:
  Título: Decreto 7.830/2012 — SICAR
  Tipo: decreto
  Código: Decreto 7.830/2012
  Jurisdição: federal
  Status: active
  Chunks: 15 chunks

PRECEDENTE-001:
  Título: Desembargo IBAMA em APP de rio intermitente
  Tipo: precedente
  Outcome: deferido em 60 dias
  Município: Inhumas, GO
  Tags: ["desembargo", "app", "rio_intermitente", "ibama"]
```

---

## 4. Arquivos e execução do seed

### Estrutura implementada hoje

```
seed.py                              # seed idempotente atual
docker-compose.yml                   # startup da api executa init_db + seed.py
.env.example                         # expõe SEED_*_PASSWORD para credenciais previsíveis
ops/provision_homologation_tenant.py # cria tenant controlado para homologações reais
```

### Comandos suportados hoje

```bash
# Seed manual no ambiente local
python seed.py

# Stack local com seed no startup da API
docker compose up --build
```

### Comandos operacionais úteis

```bash
# Provisionar tenant controlado para homologacao de fluxos reais
python ops/provision_homologation_tenant.py \
  --internal-email seu+interno@gmail.com \
  --portal-email seu+portal@gmail.com \
  --password Seed@2026
```

### Backlog estrutural

Continuam como evolucao desejada, mas **ainda nao implementada neste checkout**:

- modularizacao do seed em `seed/main.py`
- seeds especializados por dominio
- seed dedicado de base regulatoria
- seed de homologacao separado por ambiente

---

## 5. Seed de homologação com a cliente

O comando dedicado `python seed/main.py --env homologacao` **ainda nao existe** neste checkout.

Hoje, para homologacao controlada com a cliente, existem dois caminhos:

- usar o seed local padrao com credenciais deterministicas
- provisionar um tenant isolado de homologacao via `ops/provision_homologation_tenant.py`

Exemplo atual:

```bash
python ops/provision_homologation_tenant.py \
  --internal-email seu+interno@gmail.com \
  --portal-email seu+portal@gmail.com \
  --password Seed@2026
```

Esse tenant controlado deve usar:
- Dados mais próximos da realidade da cliente (municípios que ela atende, tipos de processo que ela lida)
- PDFs reais de documentos anonimizados (com permissão)
- Pelo menos 5 precedentes do escritório registrados
- Base regulatória com normas que ela usa no dia a dia

Quando existir um seed separado de homologacao, ele nao deve ir para o repositório Git. Deve ficar em pasta segura compartilhada apenas com o time.

---

## 6. Manutenção do seed

| Quando atualizar | O que atualizar |
|---|---|
| Nova entidade adicionada ao banco | Adicionar instância no seed correspondente |
| Nova tela implementada | Garantir que o seed cobre o cenário dessa tela |
| Nova máquina de estados | Garantir que há um processo em cada novo status |
| Antes de cada apresentação à cliente | Atualizar seed de homologação com dados mais reais |

---

*Documento criado em 26/03/2026 e atualizado em 29/03/2026. Responsável pela manutenção: Dev Lead.*
