# ADR-029 — O contrato nasce da proposta ACEITA; template Mirante como padrão do tenant

- **Status:** Aceita
- **Data:** 2026-07-19
- **Espec de origem:** Ficha 07 §8 (E6 Orçamento → E7 Contrato); Sprint 5-B.
  Documentos reais da Mirante (proposta de 6 seções, contrato de 8 cláusulas).
- **Relacionada a:** ADR-028 (a proposta nasce da Rota — S5-A), ADR-027 (vigência
  de matrícula), dívida #67 (multi-bloco/multi-titular), dívida #34 (duas trilhas
  de orçamento), dívida #49 (RedatorAgent sem template de peça), Princípios 1 (IA
  propõe, humano decide), 2 (tudo auditável) e 6 (schema antes de escala).

## Contexto

O S5-A fez a proposta (entidade) NASCER da Rota validada, com escopo rastreável
(`scope_items[].rota_passo_id`) e precificação. Faltava a **peça** — o documento
que o cliente lê e assina — nos moldes REAIS da Mirante, e o **contrato** que
espelha o escopo aceito.

O gerador legado de contrato (`contract_generator.fill_contract_template`) fazia
substituição textual `{{...}}` sobre um template no banco, **hardcodava** os dados
do emissor (`"Regente Ambiental"`, `"00.000.000/0001-00"`), **não** consumia a
rastreabilidade `rota_passo_id`, e **não tinha validação de consistência** — a
classe de erro real dos contratos manuais da Mirante (soma de parcelas que não
fecha, valor da cláusula de pagamento diferente da tabela de serviços, matrícula
superada citada como vigente). O `RedatorAgent` (templates `proposta`/`contrato`)
era um caminho paralelo que já só logava aviso.

## Decisão

**1. Uma fonte determinística para a peça (`app/services/mirante_documents.py`).**
A geração de proposta e contrato passa por um serviço DETERMINÍSTICO (sem LLM):
`build_proposta` (6 seções) e `build_contrato` (8 cláusulas). Determinismo é
requisito, não escolha — as validações de consistência precisam BLOQUEAR com
certeza, e um LLM não garante que "a soma das parcelas fecha". O `RedatorAgent`
não é a fonte da proposta/contrato (o log de aviso já media isso).

**2. O contrato nasce da proposta ACEITA.** `build_contrato` exige
`status == accepted` (senão 422 honesto). A cláusula 1ª espelha o escopo aceito
(serviços = `scope_items`, cada um rastreável ao `rota_passo_id`); a cláusula 2ª
espelha os valores. **Bloco único do processo corrente** — multi-bloco /
multi-titular permanece a **dívida #67** (já registrada no S5-A).

**3. Template Mirante como padrão versionado (`docs/templates/*.md`).** A estrutura
destilada dos documentos reais vive versionada no repo com placeholders e exemplos
FICTÍCIOS (zero PII — os originais com CPF/RG/conta NUNCA entram no git). É a
referência humana; a geração monta o documento programaticamente espelhando-a.

**4. Perfil emissor do tenant (`tenant.settings["issuer"]`).** O `Tenant` mínimo
ganhou `settings` (JSON aditivo). Razão social, CNPJ, endereço, responsável
técnico (nome/título/CREA), dados bancários e foro vivem ali. **Nunca inventamos**
CNPJ/conta como o legado fazia: perfil incompleto = geração **bloqueada** nomeando
o que falta (`app/services/tenant_profile.py`).

**5. Três validações de consistência — violação BLOQUEIA (422):**
   1. soma dos valores dos serviços == total declarado da proposta;
   2. soma das parcelas == total do bloco (cláusula 2ª == cláusula 1ª);
   3. matrículas citadas existem e são **VIGENTES** (`Matricula.is_vigente`,
      ADR-027) — uma ficha histórica/superada não fundamenta o objeto.
As parcelas viraram estruturadas (`proposals.payment_installments`) para a
validação (2) poder falhar de verdade; vazio = uma parcela única à vista.

**6. Guard de placeholder.** Nenhum `{{...}}` ou `[12]` sai no documento final
(`assert_resolved` → `PlaceholderUnresolvedError`), como acontecia no real.

**7. IA propõe; humano decide.** O gerado é RASCUNHO (`needs_human_validation=True`
na Saída/StageOutput). O consultor revisa/edita antes de enviar; a **assinatura**
segue o fluxo do S5-C (fora deste PR).

**8. Saída em PDF + registro em Saídas.** Reaproveita a infra de artefatos (fpdf2 +
StorageService/MinIO). Proposta → `StageOutput(output_type="proposta")` (E6);
contrato → `StageOutput(output_type="minuta")` (E7) + `Contract` (draft). Falha de
storage/PDF é não-fatal (degrada com elegância): a peça textual é registrada e um
`warning` sobe ao retorno.

## Consequências

**Positivas**
- A peça reflete o trabalho real (Rota → proposta → contrato), rastreável
  item→passo, com os erros de consistência barrados na origem.
- O emissor deixa de ser hardcoded; a peça só sai com dados institucionais reais.
- Bloco único fecha o caminho E6→E7 no nível de código; multi-bloco é #67.

**Custos / riscos residuais (dívida #68)**
- O `contract_generator.fill_contract_template` (template-fill genérico) e o
  `scope_base` residual do `PRICE_TABLE` seguem no código para o caminho AVULSO
  (contrato sem proposta); aposentá-los de vez é follow-on.
- A seção 4 (entregáveis) reusa a descrição do passo — falta `entregavel`
  explícito por `RotaPasso`.
- Sem UI neste PR para editar o perfil emissor e as parcelas estruturadas.
- A migration `f1a7c2d9e4b6` precisa rodar em prod (aditiva).

## Validação

- `tests/api/test_mirante_documents_s5b.py` (15 testes): 6 seções, 8 cláusulas,
  rastreabilidade passo→etapa, as 3 validações (passam e bloqueiam), vigência de
  matrícula, perfil incompleto, proposta não-aceita, guard de placeholder,
  endpoints (rascunho + registro em Saídas).
- Exemplos fictícios: `docs/templates/exemplos/EXEMPLO_{PROPOSTA,CONTRATO}.txt`
  (via `scripts/gerar_exemplo_s5b.py`). Suíte completa verde; migration
  `f1a7c2d9e4b6` aditiva (up/down triviais).
