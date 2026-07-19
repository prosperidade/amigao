# ADR-030 — Assinatura manual do contrato conclui o caso; Comercial oculta (S5-C)

- **Status:** Aceita
- **Data:** 2026-07-19
- **Espec de origem:** Ficha 07 §8 (E7 Contrato/Formalização) — fechamento da Ficha.
  Sprint 5-C.
- **Relacionada a:** ADR-029 (contrato nasce da proposta aceita — S5-B), ADR-028
  (proposta nasce da Rota — S5-A), ADR-024 (isTabVisible do Sprint 6), gate E7
  `has_contract_signed` (Fase 0, item 9), Princípios 1 (IA propõe, humano decide)
  e 2 (tudo auditável).

## Contexto

O S5-B fez o contrato NASCER da proposta aceita (minuta Mirante determinística).
Faltava o **último elo da Ficha 07**: assinar. O gate E7 (`has_contract_signed`)
já lia `Contract.signed_at`, mas **nenhum fluxo o escrevia** — a E7 nunca ficava
"concluída" (honesto, mas o caso nunca fechava). Além disso, a aba **Comercial**
(atalho de E6/E7 no workspace) seguia visível "até o Sprint 5 convergir tudo".

## Decisão

**1. Assinatura MANUAL (MVP, sem integração externa).** Ciclo explícito do
contrato: `rascunho → ENVIADO → ASSINADO`.
- `POST /contracts/{id}/aprovar-enviar` (draft→sent): o consultor aprova a minuta
  e a marca como enviada ao cliente. Auditado (AuditLog + hash chain).
- `POST /contracts/{id}/assinar` (sent→signed): registra a assinatura — `signed_at`
  (data informada), quem REGISTROU (`signed_registered_by_user_id`) e, OPCIONAL, o
  upload do PDF já assinado (`signed_pdf_storage_key`). Multipart; sem arquivo é
  válido. Auditado. Exige contrato ENVIADO (bloqueio honesto: assinar um rascunho
  ou reenviar um enviado = 422).
- Preencher `signed_at` satisfaz o gate E7 — a E7 passa a fechar de verdade.

**2. Contrato assinado CONCLUI o caso.** A E7 é a etapa TERMINAL (não há "avançar").
`compute_macroetapa_state` passa a devolver `concluida` (não `pronta_para_avancar`)
quando a E7 está 100% E o contrato está assinado — mesmo sendo a etapa corrente. O
endpoint de assinatura também marca `Process.closed_at` (fecho tangível do caso). O
`ProcessStatus` operacional (lead→…→concluido) NÃO é tocado: é o eixo pós-contrato
(MVP2), desacoplado da macroetapa por design — a conclusão da Ficha 07 vive no eixo
da macroetapa, honestamente.

**3. Assinatura eletrônica externa = dívida pós-MVP.** gov.br / Clicksign /
DocuSign ficam para depois (dívida #69). O MVP registra a assinatura que aconteceu
fora do sistema — coerente com "IA propõe, humano decide": o gerado é rascunho, o
consultor aprova, envia e assina.

**4. Saídas converge.** A aba **Saídas** (que já listava StageOutputs) passa a
oferecer **download** do PDF do artefato (novo `GET /processes/{id}/artifacts/{id}/
download`, lendo `content_data.pdf_storage_key`) e **atalho para o contrato**
(quando o artefato é a minuta, via `content_data.contract_id`). Proposta, minuta e
contrato convergem num só lugar, com estado, data e download.

**5. Comercial OCULTA (isTabVisible=false).** Com a convergência, a aba Comercial
sai da superfície (segue viva por baixo, mesmo padrão do S6/ADR-024). Varredura
feita: **nada fica acessível só por ela** —
- ações de estado da proposta (enviar/aceitar/recusar) já viviam no `ProposalEditor`
  (rota `/proposals/:id`, no menu lateral);
- a `nova-versao` (renegociação), que só existia na Comercial, foi **migrada** para o
  `ProposalEditor`;
- "Gerar Contrato" no `ProposalEditor` passou a chamar o gerador Mirante
  (`POST /contracts/gerar`, S5-B) — antes usava o legado `POST /contracts/` (que não
  registrava minuta em Saídas);
- a assinatura vive no `ContractEditor` (`/contracts/:id`), alcançável pela Saídas.

## Consequências

**Positivas**
- A Ficha 07 fecha ponta a ponta: E1→E7, contrato assinado → caso concluído.
- O gate E7 deixa de ser sempre-falso; a E7 mostra "concluída" com honestidade.
- Uma superfície a menos (Comercial) sem perder capacidade — Saídas é o hub.

**Custos / riscos residuais (dívida #69)**
- Assinatura eletrônica externa (gov.br/Clicksign) não implementada.
- `closed_at` marca o fecho, mas o `ProcessStatus.concluido` (eixo operacional
  pós-contrato) não é setado automaticamente — decisão consciente (eixos separados).
- A migration `c3e9b1d7f4a2` (2 colunas em `contracts`) é aditiva e precisa rodar
  em prod no deploy.

## Validação

- `tests/api/test_signature_e2e_s5c.py` (9 testes): assinatura com/sem upload,
  bloqueios (assinar exige enviado; aprovar exige rascunho; data inválida), card E7
  (aguardando sem assinatura / concluída com), Saídas lista proposta+minuta +
  download de artefato, e o **teste de integração E1→E7 completo** (a Ficha inteira
  dirigida pela API — o gate real barra em cada etapa, o caso conclui com
  `closed_at` + `has_contract_signed`).
- `frontend/src/lib/tabFlags.test.ts` — Comercial agora oculta (12 abas cobertas).
- Suíte completa verde + tsc + vitest (124). Migration aditiva.
