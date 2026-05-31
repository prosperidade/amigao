/**
 * PreviewPanel — coluna lateral que mostra, em tempo real, o que a IA está
 * extraindo dos documentos anexados ao draft (proposta REGENTE_1, validada Isis).
 *
 * Faz polling de GET /intake/drafts/{id}/extracted-fields (a cada 5s) e exibe,
 * por campo: valor, confiança (badge verde/amarelo/vermelho), documento de
 * origem. Quando há divergência com o valor digitado, abre o ReconcileModal.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import ReconcileModal from './ReconcileModal';

interface ExtractedFieldView {
  field: string;
  value: unknown;
  confidence: number | null;
  source_document_id: number | null;
  source_document_name: string | null;
  diverges_from_manual: boolean;
}

interface ExtractedFieldsResponse {
  draft_id: number;
  fields: ExtractedFieldView[];
  has_divergence: boolean;
}

interface Props {
  draftId: number;
  /** Valores digitados pelo consultor, por nome de campo extraído (p/ o modal). */
  manualValues?: Record<string, unknown>;
}

const FIELD_LABELS: Record<string, string> = {
  nirf: 'NIRF',
  ccir_numero: 'CCIR',
  ccir: 'CCIR',
  sigef_numero: 'SIGEF',
  car_numero: 'Número do CAR',
  car_code: 'Número do CAR',
  municipio: 'Município',
  uf: 'UF',
  coordenadas_centroide: 'Coordenadas (centroide)',
  area_total_ha: 'Área total (ha)',
  titular_matricula: 'Titular da matrícula',
  area_app: 'Área de APP (ha)',
  area_rl: 'Área de RL (ha)',
  area_consolidada: 'Área consolidada (ha)',
  cpf_cnpj: 'CPF / CNPJ',
};

function labelFor(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

// Semântica de confiança preservada (verde >0.9, amarelo 0.7–0.9, vermelho <0.7),
// adaptada para fundo claro — não há tokens semânticos success/warning no design system.
function confidenceBadge(confidence: number | null): { cls: string; text: string } {
  if (confidence === null || confidence === undefined) {
    return { cls: 'bg-muted text-muted-foreground border-border', text: 's/ score' };
  }
  const pct = `${Math.round(confidence * 100)}%`;
  if (confidence > 0.9) return { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', text: pct };
  if (confidence >= 0.7) return { cls: 'bg-yellow-50 text-yellow-700 border-yellow-200', text: pct };
  return { cls: 'bg-red-50 text-red-700 border-red-200', text: pct };
}

function display(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  return String(v);
}

export default function PreviewPanel({ draftId, manualValues = {} }: Props) {
  const [fields, setFields] = useState<ExtractedFieldView[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [reconciling, setReconciling] = useState<ExtractedFieldView | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get<ExtractedFieldsResponse>(
        `/intake/drafts/${draftId}/extracted-fields`,
      );
      setFields(data.fields);
    } catch {
      /* silencioso — preview é best-effort, não bloqueia o wizard */
    } finally {
      setLoaded(true);
    }
  }, [draftId]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return (
    <div className="rounded-2xl bg-card border border-border p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">🤖</span>
        <h3 className="text-sm font-semibold text-foreground">Extração da IA</h3>
        <span className="ml-auto text-[10px] text-muted-foreground animate-pulse">● ao vivo</span>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Campos lidos dos documentos anexados. Atualiza sozinho enquanto a IA processa.
      </p>

      {!loaded ? (
        <div className="text-sm text-muted-foreground py-6 text-center">Carregando…</div>
      ) : fields.length === 0 ? (
        <div className="text-sm text-muted-foreground py-6 text-center">
          Nenhum campo extraído ainda. Anexe documentos para a IA preencher automaticamente.
        </div>
      ) : (
        <div className="space-y-2">
          {fields.map(f => {
            const badge = confidenceBadge(f.confidence);
            return (
              <div
                key={f.field}
                className={`p-3 rounded-xl border ${
                  f.diverges_from_manual
                    ? 'border-amber-300 bg-amber-50'
                    : 'border-border bg-muted/30'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground flex-1">{labelFor(f.field)}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${badge.cls}`}>
                    {badge.text}
                  </span>
                </div>
                <div className="text-sm text-foreground font-medium mt-0.5 break-words">{display(f.value)}</div>
                {f.source_document_name && (
                  <div className="text-[10px] text-muted-foreground mt-1">📄 {f.source_document_name}</div>
                )}
                {f.diverges_from_manual && (
                  <button
                    onClick={() => setReconciling(f)}
                    className="mt-2 text-xs text-amber-700 hover:text-amber-800 underline flex items-center gap-1"
                  >
                    ⚠️ Diverge do que você digitou — reconciliar
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {reconciling && (
        <ReconcileModal
          draftId={draftId}
          field={reconciling.field}
          fieldLabel={labelFor(reconciling.field)}
          manualValue={manualValues[reconciling.field]}
          extractedValue={reconciling.value}
          onClose={() => setReconciling(null)}
          onReconciled={refresh}
        />
      )}
    </div>
  );
}
