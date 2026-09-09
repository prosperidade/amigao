<!-- Versionado em docs/auditoria/. Auditoria de generalidade, Fase 2: matriz de perfis EXECUTADA.
Agente: Claude Code. SHA: 4a96b5d (main com #148). Escrita apenas em banco descartável amigao_audit
(127.0.0.1:55433). Produção intocada. Spec v0.1 commitada isoladamente em 130d715 na branch de auditoria.
Fronteira: perfis com staging já formado — não mede upload, OCR, classificação, extração nem tela. -->

# Fase 2 — Matriz de perfis executada

## Estado das pré-condições

- `HEAD`: `4a96b5d3e9e3e976f5ee4a3f8a85f8c735f0d948` (#148).
- Spec commitada isoladamente: `130d715 docs(auditoria): spec Isis v0.1 — insumo da matriz de perfis.`
- Os 15 IDs foram conferidos.
- Migration head do banco descartável: `amigao_audit | e4f6a8c2b1d9`
- Extensões confirmadas por `SELECT`: `postgis`, `vector`.
- Banco usado exclusivamente: `127.0.0.1:55433/amigao_audit`.
- Supabase/produção não foi acessado.
- Container descartável permanece ativo e saudável.
- Nenhuma linha de produção foi alterada.

A consolidação foi executada diretamente em `consolidate_process`, que é o serviço chamado pelo endpoint `POST /{process_id}/consolidar`, conforme `app/api/v1/processes.py:1699-1720`.

## Resultado da matriz

| Perfil | Preparados | Persistidos | Ignorados | Divergências | Matrículas antes → depois | Veredito |
|---|---:|---:|---:|---:|---:|---|
| P1 PF, 1 matrícula existente | 1 | 1 | 0 | 0 | 1 → 1 | SIM |
| P2 PF, 2 matrículas existentes | 2 | 2 | 0 | 0 | 2 → 2 | SIM |
| P3 PJ + CNH de representante | 3 | 3 | 0 | 0 | 1 → 1 | NÃO — entidade errada |
| P4 PJ sem matrícula, documento matrícula | 2 | 2 | 0 | 0 | 0 → 1 | SIM |
| P4 adicional, somente CCIR/CAR | 2 | 0 | 2 | 0 | 0 → 0 | Guard correto |
| P5 PF, 4 matrículas | 4 | 4 | 0 | 0 | 4 → 4 | SIM |
| P6 PJ, CNPJ duplicado no tenant | 1 | 1 | 0 | 0 | 4 → 4 | NÃO — duplicidade |
| P7, 28 campos | 28 | 28 | 0 | 0 | 4 → 4 | SIM |

### `consolidated_at`

- P1: staging `1` carimbado.
- P2: staging `2–3` carimbados.
- P3: staging `4–6` carimbados.
- P4 documento matrícula: staging `42–43` carimbados.
- P4 CCIR/CAR: staging `7–8` permaneceram `NULL`.
- P5: staging `9–12` carimbados.
- P6: staging `13` carimbado.
- P7: staging `14–41` — todos os 28 — carimbados.

O `consolidated_at` cobre todas as linhas efetivamente processadas nos perfis testados. Ele não garante que o dado esteja semanticamente correto.

## P3 — CNH do representante

Entrada preparada:

- `cliente.full_name = Joel Cenci`
- `cliente.document = 12345678909`
- fonte: `rg_cpf`

Resultado persistido:

```text
full_name  = Joel Cenci
legal_name = P3-PJ-representante
cpf_cnpj   = 12345678909
```

A CNH do representante virou dado do `Client` principal. O cliente PJ deixou de ter o CNPJ original `33000000000100`.

Evidência estrutural:

- `app/services/ficha01_extraction.py:269-273` mapeia `rg_cpf` para `cliente`.
- `app/services/staging_consolidation.py` usa a allowlist de cliente e alias `document -> cpf_cnpj`.
- O modelo não possui entidade/papel de representante, `app/models/client.py:30-42`.

**P3: NÃO.** A gravação ocorreu, mas a identidade persistida ficou incorreta.

## P4 — criação e guard ADR-062

Com documento `matricula` e nenhuma matrícula prévia:

```text
preparados: 2
persistidos: 2
matriculas_criadas: 1
matriculas_total: 1
ignorados: []
```

Com apenas CCIR/CAR:

```text
preparados: 2
persistidos: 0
ignorados: 2
matriculas_criadas: 0
matriculas_total: 0
```

Isso confirma o comportamento do #148:

- `_MATRICULA_CREATOR_DOC_TYPES = {"matricula"}`, `app/services/staging_consolidation.py:84-91`;
- a criação depende de `allow_create`, `:590-597`;
- CCIR/CAR não criam matrícula sem registro prévio;
- as linhas ficam visíveis em `ignorados`.

## P6 — CNPJ duplicado

Para o CNPJ `66000000000100`, o SELECT final retornou:

```text
audit-P6-PJ-CNPJ | 2 clientes
```

Não existe unicidade por CPF/CNPJ no modelo:

- `app/models/client.py:33`: `cpf_cnpj = Column(String, index=True)`;
- não há `UniqueConstraint` para `tenant_id + cpf_cnpj`;
- criação direta em `app/api/v1/clients.py:50-62`.

**P6: NÃO.** A consolidação não cria a duplicidade, mas o sistema permite que ela exista no mesmo tenant.

## P7 — SAVE-001 com 28 campos

Resultado:

```text
preparados: 28
persistidos: 28
ignorados: 0
divergencias: 0
```

Todos os 28 registros receberam `consolidated_at`.

**SAVE-001 passou neste perfil controlado.** Isso prova que a função consegue persistir 28 campos quando:

- os destinos existem;
- as quatro matrículas já existem;
- os campos estão aceitos;
- não há conflito entre fontes;
- o staging já está corretamente estruturado.

Não prova ELODI completo, porque não inclui o problema de identidade PJ/representante nem a carga documental real.

## DIAG-001 — payload e tela

Chamando o classificador com `process_type="misto"` e sem documento:

```json
{
  "demand_type": "misto",
  "demand_label": "Demanda Mista / Múltiplos Passivos",
  "confidence": "high",
  "initial_diagnosis": "O caso apresenta múltiplos passivos ou combina diferentes trilhas regulatórias. É necessário priorizar as demandas pela urgência e dependências entre elas.",
  "required_documents": [
    {"label": "Matrícula do Imóvel", "required": true},
    {"label": "CCIR", "required": true},
    {"label": "CAR (se houver)", "required": false},
    {"label": "Documentos do Proprietário", "required": true}
  ],
  "urgency_flag": null,
  "relevant_agencies": ["SEMA", "IBAMA", "INCRA"]
}
```

Origem:

- `app/services/intake_classifier.py:370-390`: rótulo e texto pré-definidos;
- `app/services/intake_classifier.py:446-507`: `process_type="misto"` força o tipo e retorna `confidence="high"`;
- `frontend/src/pages/Intake/DiagnosisPanel.tsx:60-86`: apresenta "Tipo identificado", o rótulo e "Diagnóstico inicial".

A tela apresenta:

```text
Tipo identificado
Demanda Mista / Múltiplos Passivos
Confiança alta

Diagnóstico inicial
O caso apresenta múltiplos passivos...
```

**DIAG-001 confirmado:** é apresentado como classificação/diagnóstico inicial com confiança alta, embora não dependa de agente executado nem de documento de passivo. O texto é um rótulo e uma afirmação de diagnóstico preliminar, não uma conclusão documentada.

## Resposta final por perfil

- P1: **SIM**
- P2: **SIM**
- P3: **NÃO**
- P4: **SIM** para documento matrícula; CCIR/CAR obedecem o guard
- P5: **SIM**
- P6: **NÃO**
- P7: **SIM**

Resultado: **5 de 7 perfis passaram; 2 falharam semanticamente: P3 e P6.**

## Resposta à pergunta central

**Não, o sistema ainda não funciona para qualquer caso.**

A consolidação funciona para perfis cadastrais simples e staging já bem formado. Ela falha como sistema geral porque:

1. não separa PJ de representante;
2. permite duplicidade de CNPJ no tenant;
3. carimba `consolidated_at` mesmo quando a gravação semântica está errada;
4. só cria matrícula por documento do tipo `matricula`;
5. apresenta "Múltiplos Passivos" como diagnóstico de alta confiança antes de evidência documental suficiente.

O banco descartável `amigao_audit` foi deixado ativo no container `amigao-audit-db-1`, porta `55433`, para inspeção posterior.

---

*Nota posterior (09/09): P3 e P6 foram corrigidos pela Frente A (PR #149, ADR-063); a matriz foi
reconstruída a partir da spec e commitada como regressão permanente. Ver docs/auditoria/README.md.*
