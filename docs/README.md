# Documentação · Regente Ambiental

Esta pasta tem 5 camadas. Cada documento tem propósito único — se você encontrar conteúdo duplicado, é bug. Reporta.

## Estrutura

```
docs/
├── README.md              ← você está aqui
│
├── manifesto/             Por que existimos
│   ├── 01-VISAO_PRODUTO.md
│   ├── 02-IDENTIDADE.md
│   ├── 03-PRINCIPIOS.md
│   └── 04-ROADMAP.md
│
├── arquitetura/           Como o sistema é construído
│   ├── ARQUITETURA_GERAL.md
│   ├── MODELO_DE_DADOS.md
│   ├── API_v1.md
│   ├── GOVERNANCA_IA.md
│   ├── FLUXOS_E2E.md
│   ├── MULTITENANT_LGPD.md
│   ├── OBSERVABILIDADE.md
│   ├── WHITELABEL.md
│   ├── INTEGRACOES_GOVTECH.md
│   ├── PIPELINE_OCR.md
│   └── BASE_REGULATORIA.md
│
├── operacao/              Como fazer
│   ├── RUNBOOK_DEV.md
│   ├── RUNBOOK_OPS.md
│   ├── TROUBLESHOOTING.md
│   ├── SEED_DADOS.md
│   └── TESTING.md
│
├── estado/                Onde estamos hoje (vivo)
│   ├── ESTADO_ATUAL.md
│   ├── BACKLOG.md
│   ├── AUDITORIA_ATUAL.md
│   ├── progressoIA.md
│   └── PROGRESSO_WAITLIST.md
│
├── sprints/               Sprints em curso
│
├── adr/                   Decisões arquiteturais (imutáveis)
│   ├── 001-multitenant.md
│   ├── 002-multi-llm-gateway.md
│   ├── 003-mempalace-REVOKED.md
│   ├── 004-regente-vs-amigao.md
│   ├── 005-pgvector-rag.md
│   ├── 006-skills-procedurais.md
│   ├── 007-stage-output-content.md
│   ├── 008-resend-vs-smtp.md
│   └── 009-mobile-clientportal-congelados.md
│
└── _archive/              Histórico congelado
```

## Por onde começar

| Você é... | Leia nesta ordem |
|---|---|
| Pessoa nova no projeto | `manifesto/01-VISAO_PRODUTO.md` → `manifesto/02-IDENTIDADE.md` → `manifesto/03-PRINCIPIOS.md` → `arquitetura/ARQUITETURA_GERAL.md` |
| Dev que vai mexer no código | `CLAUDE.md` (raiz) → `arquitetura/ARQUITETURA_GERAL.md` → `arquitetura/MODELO_DE_DADOS.md` → `operacao/RUNBOOK_DEV.md` → `operacao/TESTING.md` |
| Ops que vai operar produção | `operacao/RUNBOOK_OPS.md` → `arquitetura/OBSERVABILIDADE.md` → `operacao/TROUBLESHOOTING.md` |
| Estrategista / comercial | `manifesto/` (toda) → `estado/ESTADO_ATUAL.md` |
| Investidor / parceiro | `manifesto/01-VISAO_PRODUTO.md` → `manifesto/04-ROADMAP.md` → `estado/ESTADO_ATUAL.md` |

## Regras de manutenção

- **Manifesto** muda raramente. Cada alteração precisa de discussão.
- **Arquitetura** muda quando o desenho técnico muda. Atualizar junto com a sprint.
- **Operação** muda quando o procedimento muda. Atualização contínua.
- **Estado** muda toda sprint. `ESTADO_ATUAL.md` é regenerado a cada release.
- **ADR** é imutável. Decisões novas viram novos ADRs com números sequenciais. Decisões revogadas ganham sufixo `-REVOKED.md` no nome e banner no topo.
- **Sprints** ativas ficam em `sprints/`. Ao fechar, movem para `_archive/sprints-fechadas/`.
