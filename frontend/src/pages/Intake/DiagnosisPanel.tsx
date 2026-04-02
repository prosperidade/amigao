/**
 * DiagnosisPanel — Exibe o resultado da classificação automática da demanda
 * Sprint 1 — Intake / Diagnóstico Inicial
 */

interface DocumentRequirement {
  id: string;
  label: string;
  doc_type: string;
  category: string;
  required: boolean;
}

interface ClassifyResult {
  demand_type: string;
  demand_label: string;
  confidence: string;
  initial_diagnosis: string;
  required_documents: DocumentRequirement[];
  suggested_next_steps: string[];
  urgency_flag: string | null;
  relevant_agencies: string[];
}

const CONFIDENCE_CONFIG = {
  high: { label: 'Alta confiança', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30' },
  medium: { label: 'Confiança média', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30' },
  low: { label: 'Baixa confiança', color: 'text-slate-400', bg: 'bg-slate-500/10 border-slate-500/30' },
};

const URGENCY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  critica: { label: '🔴 URGÊNCIA CRÍTICA', color: 'text-red-300', bg: 'bg-red-500/20 border-red-500/40' },
  alta: { label: '🟠 Urgência alta', color: 'text-orange-300', bg: 'bg-orange-500/20 border-orange-500/30' },
};

const CATEGORY_COLORS: Record<string, string> = {
  ambiental: 'bg-emerald-500/20 text-emerald-300',
  fundiario: 'bg-blue-500/20 text-blue-300',
  pessoal: 'bg-purple-500/20 text-purple-300',
  bancario: 'bg-yellow-500/20 text-yellow-300',
  administrativo: 'bg-orange-500/20 text-orange-300',
  geoespacial: 'bg-cyan-500/20 text-cyan-300',
  tecnico: 'bg-rose-500/20 text-rose-300',
  geral: 'bg-slate-500/20 text-slate-300',
};

export default function DiagnosisPanel({ result }: { result: ClassifyResult }) {
  const confidence = CONFIDENCE_CONFIG[result.confidence as keyof typeof CONFIDENCE_CONFIG] ?? CONFIDENCE_CONFIG.low;
  const urgencyConfig = result.urgency_flag ? URGENCY_CONFIG[result.urgency_flag] : null;

  const requiredDocs = result.required_documents.filter(d => d.required);
  const optionalDocs = result.required_documents.filter(d => !d.required);

  return (
    <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 overflow-hidden">

      {/* Header */}
      <div className="px-5 py-4 border-b border-white/10 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">🔍</span>
            <span className="text-sm text-slate-400">Tipo identificado</span>
          </div>
          <h3 className="text-lg font-bold text-white">{result.demand_label}</h3>
          {result.relevant_agencies.length > 0 && (
            <p className="text-xs text-slate-400 mt-0.5">
              Órgãos: {result.relevant_agencies.join(' · ')}
            </p>
          )}
        </div>
        <span className={`text-xs font-medium px-3 py-1 rounded-full border ${confidence.bg} ${confidence.color} shrink-0`}>
          {confidence.label}
        </span>
      </div>

      {/* Urgência */}
      {urgencyConfig && (
        <div className={`mx-5 mt-4 p-3 rounded-xl border ${urgencyConfig.bg}`}>
          <span className={`text-sm font-bold ${urgencyConfig.color}`}>{urgencyConfig.label}</span>
        </div>
      )}

      {/* Diagnóstico */}
      <div className="px-5 pt-4 pb-2">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Diagnóstico inicial</h4>
        <p className="text-sm text-slate-200 leading-relaxed">{result.initial_diagnosis}</p>
      </div>

      {/* Próximos passos */}
      <div className="px-5 py-4">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Próximos passos sugeridos</h4>
        <ol className="space-y-2">
          {result.suggested_next_steps.map((step, i) => (
            <li key={i} className="flex gap-3 text-sm text-slate-300">
              <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs flex items-center justify-center shrink-0 font-bold mt-0.5">
                {i + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Documentos */}
      <div className="px-5 pb-5 border-t border-white/5 pt-4">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Documentos necessários
          <span className="ml-2 text-emerald-400 font-bold">{requiredDocs.length} obrigatórios</span>
          {optionalDocs.length > 0 && (
            <span className="ml-1 text-slate-500">+ {optionalDocs.length} opcionais</span>
          )}
        </h4>

        <div className="space-y-2">
          {requiredDocs.map(doc => (
            <DocItem key={doc.id} doc={doc} required />
          ))}
          {optionalDocs.map(doc => (
            <DocItem key={doc.id} doc={doc} required={false} />
          ))}
        </div>
      </div>
    </div>
  );
}

function DocItem({ doc, required }: { doc: DocumentRequirement; required: boolean }) {
  const catColor = CATEGORY_COLORS[doc.category] ?? CATEGORY_COLORS.geral;
  return (
    <div className={`flex items-center gap-3 p-2.5 rounded-lg ${required ? 'bg-white/5' : 'bg-white/2 opacity-70'}`}>
      <span className={`w-2 h-2 rounded-full shrink-0 ${required ? 'bg-emerald-400' : 'bg-slate-500'}`} />
      <span className="text-sm text-slate-200 flex-1">{doc.label}</span>
      <span className={`text-xs px-2 py-0.5 rounded-full ${catColor}`}>{doc.category}</span>
      {required && (
        <span className="text-xs text-emerald-400 font-medium">obrig.</span>
      )}
    </div>
  );
}
