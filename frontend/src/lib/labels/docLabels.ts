/**
 * docLabels — fonte ÚNICA de rótulos PT-BR para TIPO DE DOCUMENTO.
 *
 * Regra permanente da casa (26/07): **termo interno de sistema nunca renderiza
 * cru na tela do consultor**. `document_type` é uma chave de banco
 * (`auto_infracao`, `certidao_embargo`, `rg_cpf`) e vinha aparecendo assim na
 * aba Documentos — snake_case direto na cara de quem opera.
 *
 * Complementa os dicionários já existentes, sem duplicá-los:
 *   - `fieldLabels.ts`     → CAMPOS extraídos de documento
 *   - `activityLabels.ts`  → EVENTOS de auditoria (+ `AGENT_LABELS` de `@/types/agent`)
 *   - `regulatory/labels`  → severidade / família de alerta
 *   - `quadro-types.ts`    → tipo de demanda / macroetapa
 *
 * `null`/desconhecido tem tradução PRÓPRIA e honesta: o documento existe, foi
 * lido, e só não se encaixou numa das fichas conhecidas — isso não é erro nem
 * bloqueia nada, e a tela precisa dizer exatamente isso.
 */

export const DOC_TYPE_LABELS: Record<string, string> = {
  // ── Fundiários / cadastrais ───────────────────────────────────────────────
  matricula: 'Certidão de matrícula',
  car: 'Recibo do CAR',
  // RAT = parecer do órgão SOBRE o CAR, numa data. Nunca é o CAR (Ficha 08 §2).
  // O rótulo diz isso na própria tela, para não induzir a consultora a tratá-lo
  // como o documento oficial do cadastro.
  rat: 'Análise histórica do CAR (RAT)',
  ccir: 'CCIR',
  itr: 'Declaração do ITR',
  sigef: 'Certificação SIGEF',
  memorial_descritivo: 'Memorial descritivo',
  planta_topografica: 'Planta topográfica',

  // ── Fiscalização / passivo ────────────────────────────────────────────────
  auto_infracao: 'Auto de infração',
  certidao_embargo: 'Certidão de embargo',

  // ── Pessoais ──────────────────────────────────────────────────────────────
  rg_cpf: 'Documento de identidade',
  cpf_cnpj: 'CPF / CNPJ',
  endereco: 'Comprovante de endereço',
  contrato: 'Contrato',

  // ── Sem ficha própria ─────────────────────────────────────────────────────
  outro: 'Peça do processo (sem ficha própria)',
};

/** Rótulo do tipo não classificado — nomeado, não escondido. */
export const DOC_TYPE_NAO_CLASSIFICADO = 'Não classificado — peça do processo';

/**
 * Explicação de apoio para o tipo não classificado. Aparece como tooltip: a
 * consultora precisa saber que isto **não trava nada** (o documento foi lido e
 * está no caso), e o que ela ganha se classificar.
 */
export const DOC_TYPE_NAO_CLASSIFICADO_AJUDA =
  'O documento foi lido e está anexado ao caso. Ele só não corresponde a uma ' +
  'das fichas conhecidas (matrícula, CAR, CCIR, ITR…), então não alimenta ' +
  'campos automaticamente. Não impede nenhuma etapa.';

/**
 * Tipo de FONTE (`SourceRef.tipo`) em linguagem de consultora.
 *
 * Os valores crus vêm de `app/schemas/stage_output.py:SourceRefTipo` e vinham
 * sendo renderizados como estão ("matriz: …", "auditor: …").
 */
export const FONTE_TIPO_LABELS: Record<string, string> = {
  documento: 'Documento',
  matriz: 'Conferência de documentos',
  rat: 'Análise histórica do CAR (RAT)',
  legislacao: 'Norma',
  atendimento: 'Relato do cliente',
  auditor: 'Verificação automática',
  sem_fonte: 'Sem fonte identificada',
};

export function fonteTipoLabel(tipo: string | null | undefined): string {
  const key = (tipo ?? '').trim().toLowerCase();
  return FONTE_TIPO_LABELS[key] ?? 'Fonte';
}

/**
 * Origem de um dado gravado na base (`field_sources` / eventos da linha do tempo).
 * Termos internos que descreviam COMO o dado entrou, não o que isso significa.
 */
export const ORIGEM_DADO_LABELS: Record<string, string> = {
  human_validated: 'conferido por você',
  pendente_oficializacao: 'aguardando oficialização',
  derived_matricula: 'derivado da matrícula',
  consolidacao: 'gravado na Conferência',
  manual: 'informado à mão',
  intake: 'entrada do caso',
  agente: 'leitura automática',
};

export function origemDadoLabel(origem: string | null | undefined): string {
  const key = (origem ?? '').trim().toLowerCase();
  return ORIGEM_DADO_LABELS[key] ?? (key ? key.replace(/_/g, ' ') : '—');
}

/** Rótulo PT-BR do tipo de documento. `null`/vazio/desconhecido nunca vaza cru. */
export function docTypeLabel(docType: string | null | undefined): string {
  const key = (docType ?? '').trim().toLowerCase();
  if (!key) return DOC_TYPE_NAO_CLASSIFICADO;
  return DOC_TYPE_LABELS[key] ?? DOC_TYPE_NAO_CLASSIFICADO;
}

/** True quando o tipo não tem ficha conhecida — para a UI oferecer o tooltip. */
export function isDocTypeNaoClassificado(docType: string | null | undefined): boolean {
  const key = (docType ?? '').trim().toLowerCase();
  return !key || !(key in DOC_TYPE_LABELS);
}
