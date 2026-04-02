import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import DiagnosisPanel from './DiagnosisPanel';

// ─── Tipos ────────────────────────────────────────────────────────────────────

type Step = 1 | 2 | 3 | 4;

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
  checklist_template_demand_type: string;
}

interface FormState {
  // Etapa 1 — Cliente
  client_mode: 'existing' | 'new';
  client_id: string;
  client_name: string;
  client_phone: string;
  client_email: string;
  client_cpf_cnpj: string;
  client_type: 'pf' | 'pj';
  source_channel: string;

  // Etapa 2 — Demanda
  description: string;
  urgency: string;

  // Etapa 3 — Imóvel
  property_mode: 'none' | 'existing' | 'new';
  property_id: string;
  property_name: string;
  property_municipality: string;
  property_state: string;
  property_car: string;

  // Etapa 4 — Notas finais
  intake_notes: string;
}

const SOURCE_CHANNEL_OPTIONS = [
  { value: 'whatsapp', label: '💬 WhatsApp' },
  { value: 'email', label: '📧 E-mail' },
  { value: 'presencial', label: '🤝 Presencial' },
  { value: 'indicacao', label: '👥 Indicação' },
  { value: 'banco', label: '🏦 Banco / Financeira' },
  { value: 'cooperativa', label: '🌾 Cooperativa' },
  { value: 'parceiro', label: '🤝 Parceiro' },
  { value: 'site', label: '🌐 Site' },
];

const URGENCY_OPTIONS = [
  { value: 'baixa', label: '🟢 Baixa — pode aguardar' },
  { value: 'media', label: '🟡 Média — nas próximas semanas' },
  { value: 'alta', label: '🟠 Alta — urgente (banco, prazo, crédito)' },
  { value: 'critica', label: '🔴 Crítica — auto de infração, embargo, prazo vencendo' },
];

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function IntakeWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [classifyResult, setClassifyResult] = useState<ClassifyResult | null>(null);
  const [classifying, setClassifying] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>({
    client_mode: 'new', client_id: '', client_name: '', client_phone: '',
    client_email: '', client_cpf_cnpj: '', client_type: 'pf', source_channel: 'whatsapp',
    description: '', urgency: 'media',
    property_mode: 'none', property_id: '', property_name: '',
    property_municipality: '', property_state: '', property_car: '',
    intake_notes: '',
  });

  const set = (field: keyof FormState, value: string) =>
    setForm(prev => ({ ...prev, [field]: value }));

  // ── Etapa 2: classificar demanda ──────────────────────────────────────────
  const handleClassify = async () => {
    if (!form.description.trim() || form.description.trim().length < 10) {
      setError('Descreva a demanda com pelo menos 10 caracteres.');
      return;
    }
    setClassifying(true);
    setError(null);
    try {
      const { data } = await api.post('/intake/classify', {
        description: form.description,
        urgency: form.urgency,
        source_channel: form.source_channel,
      });
      setClassifyResult(data);
    } catch {
      setError('Erro ao classificar a demanda. Verifique sua conexão.');
    } finally {
      setClassifying(false);
    }
  };

  // ── Etapa 4: criar caso ───────────────────────────────────────────────────
  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        description: form.description,
        urgency: form.urgency,
        source_channel: form.source_channel,
        intake_notes: form.intake_notes || null,
        demand_type: classifyResult?.demand_type,
      };

      if (form.client_mode === 'existing') {
        payload.client_id = parseInt(form.client_id);
      } else {
        payload.new_client = {
          full_name: form.client_name,
          phone: form.client_phone || null,
          email: form.client_email || null,
          cpf_cnpj: form.client_cpf_cnpj || null,
          client_type: form.client_type,
          source_channel: form.source_channel,
        };
      }

      if (form.property_mode === 'existing') {
        payload.property_id = parseInt(form.property_id);
      } else if (form.property_mode === 'new' && form.property_name.trim()) {
        payload.new_property = {
          name: form.property_name,
          municipality: form.property_municipality || null,
          state: form.property_state || null,
          car_number: form.property_car || null,
        };
      }

      const { data } = await api.post('/intake/create-case', payload);
      navigate(`/processes/${data.process_id}`, {
        state: { fromIntake: true, caseData: data },
      });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Erro ao criar o caso. Tente novamente.');
    } finally {
      setSubmitting(false);
    }
  };

  const canGoNext = () => {
    if (step === 1) {
      if (form.client_mode === 'existing') return form.client_id.trim().length > 0;
      return form.client_name.trim().length >= 2;
    }
    if (step === 2) return form.description.trim().length >= 10 && !!classifyResult;
    return true;
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-emerald-950 flex items-start justify-center py-10 px-4">
      <div className="w-full max-w-3xl">

        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-white tracking-tight">
            🌿 Nova Demanda
          </h1>
          <p className="text-slate-400 mt-1">Cadastro guiado de caso ambiental</p>
        </div>

        {/* Stepper */}
        <div className="flex items-center justify-between mb-8 px-4">
          {(['1', '2', '3', '4'] as const).map((s, i) => {
            const labels = ['Cliente', 'Demanda', 'Imóvel', 'Confirmar'];
            const num = i + 1;
            const active = step === num;
            const done = step > num;
            return (
              <div key={s} className="flex-1 flex flex-col items-center gap-1">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-all ${
                  done ? 'bg-emerald-500 border-emerald-500 text-white' :
                  active ? 'bg-white border-white text-slate-900' :
                  'bg-transparent border-slate-600 text-slate-500'
                }`}>
                  {done ? '✓' : num}
                </div>
                <span className={`text-xs ${active ? 'text-white font-semibold' : 'text-slate-500'}`}>
                  {labels[i]}
                </span>
                {i < 3 && (
                  <div className={`absolute hidden`} />
                )}
              </div>
            );
          })}
        </div>

        {/* Card */}
        <div className="bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-8 shadow-2xl">

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-sm">
              {error}
            </div>
          )}

          {/* ── Etapa 1: Cliente ─────────────────────────────────────────── */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-white mb-1">Quem é o cliente?</h2>
                <p className="text-slate-400 text-sm">Vincule a um cliente existente ou cadastre um novo.</p>
              </div>

              <div className="flex gap-3">
                {(['new', 'existing'] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => set('client_mode', mode)}
                    className={`flex-1 py-2.5 rounded-xl text-sm font-medium border transition-all ${
                      form.client_mode === mode
                        ? 'bg-emerald-500 border-emerald-500 text-white'
                        : 'bg-white/5 border-white/10 text-slate-400 hover:border-white/30'
                    }`}
                  >
                    {mode === 'new' ? '+ Novo cliente' : '🔍 Cliente existente'}
                  </button>
                ))}
              </div>

              {form.client_mode === 'existing' ? (
                <Input label="ID do cliente" value={form.client_id} onChange={v => set('client_id', v)} placeholder="ex: 42" />
              ) : (
                <div className="space-y-4">
                  <Input label="Nome completo *" value={form.client_name} onChange={v => set('client_name', v)} placeholder="João da Silva" />
                  <div className="grid grid-cols-2 gap-4">
                    <Input label="CPF / CNPJ" value={form.client_cpf_cnpj} onChange={v => set('client_cpf_cnpj', v)} placeholder="000.000.000-00" />
                    <Select label="Tipo" value={form.client_type} onChange={v => set('client_type', v)}
                      options={[{ value: 'pf', label: 'Pessoa Física' }, { value: 'pj', label: 'Pessoa Jurídica' }]} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Input label="Telefone / WhatsApp" value={form.client_phone} onChange={v => set('client_phone', v)} placeholder="(65) 99999-0000" />
                    <Input label="E-mail" value={form.client_email} onChange={v => set('client_email', v)} placeholder="joao@email.com" type="email" />
                  </div>
                </div>
              )}

              <Select label="Como chegou até você? *" value={form.source_channel} onChange={v => set('source_channel', v)} options={SOURCE_CHANNEL_OPTIONS} />
            </div>
          )}

          {/* ── Etapa 2: Demanda ─────────────────────────────────────────── */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-white mb-1">Qual é a demanda?</h2>
                <p className="text-slate-400 text-sm">Descreva com suas palavras o problema do cliente. O sistema classifica automaticamente.</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Descrição da demanda *</label>
                <textarea
                  rows={5}
                  value={form.description}
                  onChange={e => set('description', e.target.value)}
                  placeholder="Ex: Cliente chegou pelo WhatsApp dizendo que o banco solicitou o CAR regularizado para liberar o PRONAF. Ele tem o imóvel há 10 anos mas nunca regularizou. Precisa resolver rápido pois a proposta vence em 30 dias."
                  className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 resize-none"
                />
                <p className="text-xs text-slate-500 mt-1">{form.description.length} caracteres (mín. 10)</p>
              </div>

              <Select label="Urgência" value={form.urgency} onChange={v => set('urgency', v)} options={URGENCY_OPTIONS} />

              {!classifyResult ? (
                <button
                  onClick={handleClassify}
                  disabled={classifying || form.description.trim().length < 10}
                  className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold transition-all flex items-center justify-center gap-2"
                >
                  {classifying ? (
                    <><span className="animate-spin">⟳</span> Classificando...</>
                  ) : (
                    '🔍 Classificar demanda'
                  )}
                </button>
              ) : (
                <div className="space-y-3">
                  <DiagnosisPanel result={classifyResult} />
                  <button
                    onClick={() => setClassifyResult(null)}
                    className="text-xs text-slate-400 hover:text-white underline"
                  >
                    Reclassificar com outra descrição
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Etapa 3: Imóvel ─────────────────────────────────────────── */}
          {step === 3 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-white mb-1">O imóvel</h2>
                <p className="text-slate-400 text-sm">Vincule um imóvel existente, cadastre um novo ou pule por enquanto.</p>
              </div>

              <div className="flex gap-3 flex-wrap">
                {(['none', 'existing', 'new'] as const).map(mode => {
                  const labels = { none: 'Pular por enquanto', existing: '🔍 Imóvel existente', new: '+ Novo imóvel' };
                  return (
                    <button
                      key={mode}
                      onClick={() => set('property_mode', mode)}
                      className={`flex-1 py-2.5 rounded-xl text-sm font-medium border transition-all min-w-[140px] ${
                        form.property_mode === mode
                          ? 'bg-emerald-500 border-emerald-500 text-white'
                          : 'bg-white/5 border-white/10 text-slate-400 hover:border-white/30'
                      }`}
                    >
                      {labels[mode]}
                    </button>
                  );
                })}
              </div>

              {form.property_mode === 'existing' && (
                <Input label="ID do imóvel" value={form.property_id} onChange={v => set('property_id', v)} placeholder="ex: 7" />
              )}

              {form.property_mode === 'new' && (
                <div className="space-y-4">
                  <Input label="Nome / denominação do imóvel *" value={form.property_name} onChange={v => set('property_name', v)} placeholder="Fazenda São João" />
                  <div className="grid grid-cols-2 gap-4">
                    <Input label="Município" value={form.property_municipality} onChange={v => set('property_municipality', v)} placeholder="Sorriso" />
                    <Input label="UF" value={form.property_state} onChange={v => set('property_state', v)} placeholder="MT" maxLength={2} />
                  </div>
                  <Input label="Número do CAR (se houver)" value={form.property_car} onChange={v => set('property_car', v)} placeholder="MT-5107925-XXXXXXXX..." />
                </div>
              )}
            </div>
          )}

          {/* ── Etapa 4: Confirmar ────────────────────────────────────────── */}
          {step === 4 && classifyResult && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-white mb-1">Confirmar e abrir caso</h2>
                <p className="text-slate-400 text-sm">Revise o resumo e confirme a abertura do caso.</p>
              </div>

              {/* Resumo */}
              <div className="space-y-3">
                <SummaryRow icon="👤" label="Cliente">
                  {form.client_mode === 'existing'
                    ? `Cliente ID #${form.client_id}`
                    : form.client_name}
                </SummaryRow>
                <SummaryRow icon="🏷️" label="Tipo de demanda">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                    classifyResult.urgency_flag === 'critica' ? 'bg-red-500/20 text-red-300' :
                    classifyResult.urgency_flag === 'alta' ? 'bg-orange-500/20 text-orange-300' :
                    'bg-emerald-500/20 text-emerald-300'
                  }`}>
                    {classifyResult.demand_label}
                  </span>
                </SummaryRow>
                <SummaryRow icon="🚨" label="Urgência">
                  {URGENCY_OPTIONS.find(o => o.value === form.urgency)?.label ?? form.urgency}
                </SummaryRow>
                <SummaryRow icon="📋" label="Documentos esperados">
                  {classifyResult.required_documents.filter(d => d.required).length} obrigatórios, {classifyResult.required_documents.length} no total
                </SummaryRow>
                {form.property_mode !== 'none' && (
                  <SummaryRow icon="🌾" label="Imóvel">
                    {form.property_mode === 'existing' ? `Imóvel ID #${form.property_id}` : form.property_name}
                  </SummaryRow>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Observações internas (opcional)</label>
                <textarea
                  rows={3}
                  value={form.intake_notes}
                  onChange={e => set('intake_notes', e.target.value)}
                  placeholder="Notas para o consultor responsável..."
                  className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 resize-none"
                />
              </div>

              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="w-full py-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white font-bold text-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/25"
              >
                {submitting ? (
                  <><span className="animate-spin">⟳</span> Criando caso...</>
                ) : (
                  '✅ Abrir caso agora'
                )}
              </button>
            </div>
          )}

          {/* Navegação */}
          <div className="flex justify-between mt-8 pt-6 border-t border-white/10">
            <button
              onClick={() => setStep(prev => Math.max(1, prev - 1) as Step)}
              disabled={step === 1}
              className="px-6 py-2.5 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 disabled:opacity-30 transition-all text-sm font-medium"
            >
              ← Voltar
            </button>
            {step < 4 && (
              <button
                onClick={() => {
                  setError(null);
                  setStep(prev => Math.min(4, prev + 1) as Step);
                }}
                disabled={!canGoNext()}
                className="px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white font-semibold transition-all text-sm"
              >
                Próximo →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-componentes reutilizáveis ─────────────────────────────────────────────

function Input({
  label, value, onChange, placeholder, type = 'text', maxLength,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; maxLength?: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-2">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 transition-colors"
      />
    </div>
  );
}

function Select({
  label, value, onChange, options,
}: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-2">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full rounded-xl bg-slate-800 border border-white/10 text-white px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 transition-colors"
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

function SummaryRow({ icon, label, children }: { icon: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-xl bg-white/5 border border-white/5">
      <span className="text-lg">{icon}</span>
      <div className="flex-1">
        <span className="text-xs text-slate-400 block mb-0.5">{label}</span>
        <span className="text-sm text-white font-medium">{children}</span>
      </div>
    </div>
  );
}
