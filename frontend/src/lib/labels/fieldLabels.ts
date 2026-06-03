/**
 * fieldLabels — fonte ÚNICA de rótulos PT-BR para CAMPOS de documentos/extração.
 *
 * Consolida o que antes vivia fragmentado e incompleto em:
 *   - components/IntakeWizard/PreviewPanel.tsx  (FIELD_LABELS)
 *   - pages/Intake/DraftDocumentUploader.tsx    (FIELD_LABELS)
 *   - components/AgentResultRenderer.tsx         (key.replace(/_/g,' ') cru)
 *   - pages/Processes/DocumentsTab.tsx           (key.replace + JSON.stringify cru)
 *
 * Regra de ouro: NENHUM termo técnico (snake_case, JSON cru, [object Object])
 * pode chegar à tela. Use `labelFor()` para rótulos e `humanizeValue()` para
 * valores. Campos meta/internos (confidence, *_raw, etc.) são ocultados via
 * `isMetaField()`.
 *
 * Para rótulos de DOMÍNIO (tipo de demanda, agentes, severidade, categorias)
 * existem fontes próprias — ver types/agent.ts, lib/regulatory/labels.ts,
 * pages/Processes/quadro-types.ts. Este módulo é só de CAMPO.
 */

export const FIELD_LABELS: Record<string, string> = {
  // ── Identificadores rurais/ambientais ─────────────────────────────────────
  nirf: 'NIRF',
  ccir: 'CCIR',
  ccir_numero: 'CCIR',
  sigef: 'SIGEF',
  sigef_numero: 'SIGEF',
  car: 'CAR',
  car_code: 'Código CAR',
  car_numero: 'Número do CAR',
  kml_sigef: 'KML / SIGEF',

  // ── Imóvel / matrícula ────────────────────────────────────────────────────
  matricula: 'Matrícula',
  numero_matricula: 'Número da matrícula',
  registry_number: 'Matrícula',
  titular_matricula: 'Titular da matrícula',
  denominacao_imovel: 'Denominação do imóvel',
  property_name: 'Nome do imóvel',
  comarca: 'Comarca',
  cartorio: 'Cartório',
  data_registro: 'Data de registro',
  descricao_limites: 'Descrição dos limites',

  // ── Localização ───────────────────────────────────────────────────────────
  municipio: 'Município',
  municipality: 'Município',
  uf: 'UF',
  state: 'UF',
  endereco: 'Endereço',
  naturalidade: 'Naturalidade',
  coordenadas_centroide: 'Coordenadas (centroide)',

  // ── Áreas ─────────────────────────────────────────────────────────────────
  area: 'Área',
  area_ha: 'Área (ha)',
  area_hectares: 'Área (ha)',
  area_total_ha: 'Área total (ha)',
  area_app: 'Área de APP (ha)',
  area_rl: 'Área de RL (ha)',
  area_consolidada: 'Área consolidada (ha)',

  // ── Pessoa / titular ──────────────────────────────────────────────────────
  nome: 'Nome',
  nome_social: 'Nome social',
  razao_social: 'Razão social',
  cpf: 'CPF',
  cpf_cnpj: 'CPF / CNPJ',
  proprietario_nome: 'Proprietário',
  proprietario_cpf_cnpj: 'CPF / CNPJ',
  data_nascimento: 'Data de nascimento',
  sexo: 'Sexo',
  nacionalidade: 'Nacionalidade',
  filiacao: 'Filiação',
  // chave com acento (alguns extratores devolvem assim)
  'filiação': 'Filiação',

  // ── Documento de identidade ───────────────────────────────────────────────
  numero_documento: 'Número do documento',
  orgao_expedidor: 'Órgão expedidor',
  local_emissao: 'Local de emissão',
  data_emissao: 'Data de emissão',
  validade: 'Validade',
};

/**
 * Campos meta/internos que NUNCA devem aparecer como rótulo ao consultor.
 * Cobre chaves exatas + sufixo `_raw` + prefixo `_` (ver isMetaField).
 */
const META_FIELD_KEYS = new Set<string>([
  'confidence',
  'requires_review',
  'geom_present',
  'codigo_alerta',
  'issue_ids',
  'chain_trace_id',
  'findings_raw',
  'method',
  'metadata',
]);

/** True quando a chave é meta/interna e deve ser ocultada da UI. */
export function isMetaField(key: string): boolean {
  if (META_FIELD_KEYS.has(key)) return true;
  if (key.endsWith('_raw')) return true;
  if (key.startsWith('_')) return true; // _parse_error e afins
  return false;
}

/**
 * Humaniza uma chave técnica que NÃO está no dicionário: capitaliza a primeira
 * letra e troca `_` por espaço. NUNCA devolve o termo cru com underscore.
 */
function humanizeKey(field: string): string {
  const spaced = field.replace(/_/g, ' ').trim();
  if (!spaced) return field;
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Rótulo PT-BR do campo, ou fallback humanizado (nunca snake_case cru). */
export function labelFor(field: string): string {
  return FIELD_LABELS[field] ?? humanizeKey(field);
}

/**
 * Renderiza um valor de campo de forma amigável, sem NUNCA produzir JSON cru
 * ou "[object Object]".
 *   - escalar → string
 *   - array de escalares → "a, b, c"
 *   - array de objetos → "N itens"
 *   - objeto → "Rótulo: valor · Rótulo: valor" (só campos escalares, sem meta)
 */
export function humanizeValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '—';
    const allScalar = value.every(
      (v) => v == null || (typeof v !== 'object'),
    );
    if (allScalar) {
      const parts = value.filter((v) => v != null && v !== '').map((v) => String(v));
      return parts.length > 0 ? parts.join(', ') : '—';
    }
    return `${value.length} ${value.length === 1 ? 'item' : 'itens'}`;
  }
  // objeto
  const entries = Object.entries(value as Record<string, unknown>).filter(
    ([k, v]) =>
      v != null && v !== '' && typeof v !== 'object' && !isMetaField(k),
  );
  if (entries.length === 0) return '—';
  return entries.map(([k, v]) => `${labelFor(k)}: ${String(v)}`).join(' · ');
}
