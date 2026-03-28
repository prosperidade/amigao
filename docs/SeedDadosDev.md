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
| admin | Admin Sistema | admin@seed.dev | Seed@2026 | Testar configurações e RBAC |
| gestor | Ana Ferreira | gestor@seed.dev | Seed@2026 | Testar visão gerencial |
| consultor | Carlos Mendes | consultor@seed.dev | Seed@2026 | Testar fluxo principal |
| tecnico_campo | João Silva | campo@seed.dev | Seed@2026 | Testar app mobile e sync |
| parceiro | Geo Topografia | parceiro@seed.dev | Seed@2026 | Testar escopo isolado |
| cliente_portal | Maria Donos | cliente@seed.dev | Seed@2026 | Testar portal do cliente |

> **Importante:** senhas do seed são apenas para desenvolvimento local. Nunca aplicar em staging ou produção.

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

## 4. Arquivos do seed

### Estrutura de diretórios

```
seed/
├── main.py               # executa todos os seeds na ordem correta
├── 00_tenant.py          # tenant e settings
├── 01_users.py           # usuários por perfil
├── 02_clients.py         # clientes fictícios
├── 03_properties.py      # imóveis com geometria PostGIS
├── 04_processes.py       # processos em cada status
├── 05_tasks.py           # tarefas do processo P004
├── 06_documents.py       # documentos de exemplo
├── 07_regulatory_base.py # base regulatória mínima
├── docs/
│   ├── matricula_exemplo.pdf
│   ├── ccir_exemplo.pdf
│   └── car_baixa_qualidade.pdf  # para testar OCR com baixa confiança
└── geometries/
    ├── fazenda_boa_vista.geojson
    └── sitio_sao_joao.geojson
```

### Comando de execução

```bash
# Limpar e recriar seed (desenvolvimento)
python seed/main.py --reset

# Apenas adicionar se não existir (idempotente)
python seed/main.py

# Seed específico
python seed/main.py --only regulatory_base
```

---

## 5. Seed de homologação com a cliente

Antes de apresentar o sistema para a sócia consultora, usar um seed diferente:

```bash
python seed/main.py --env homologacao
```

Esse seed usa:
- Dados mais próximos da realidade da cliente (municípios que ela atende, tipos de processo que ela lida)
- PDFs reais de documentos anonimizados (com permissão)
- Pelo menos 5 precedentes do escritório registrados
- Base regulatória com normas que ela usa no dia a dia

**Esse seed não vai para o repositório Git.** Fica em pasta segura compartilhada apenas com o time.

---

## 6. Manutenção do seed

| Quando atualizar | O que atualizar |
|---|---|
| Nova entidade adicionada ao banco | Adicionar instância no seed correspondente |
| Nova tela implementada | Garantir que o seed cobre o cenário dessa tela |
| Nova máquina de estados | Garantir que há um processo em cada novo status |
| Antes de cada apresentação à cliente | Atualizar seed de homologação com dados mais reais |

---

*Documento criado em 26/03/2026. Responsável pela manutenção: Dev Lead.*
