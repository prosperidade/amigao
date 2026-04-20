import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import DiagnosisPanel from './DiagnosisPanel';
import DraftDocumentUploader from './DraftDocumentUploader';

// ─── Tipos ────────────────────────────────────────────────────────────────────

// Regente Cam1: Step 0 = tipo de entrada, Step 4 = documentos (opcional), Step 5 = confirmar
type Step = 0 | 1 | 2 | 3 | 4 | 5;

type EntryType =
  | 'novo_cliente_novo_imovel'
  | 'cliente_existente_novo_imovel'
  | 'cliente_existente_imovel_existente'
  | 'complementar_base_existente'
  | 'importar_documentos';

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
  // Etapa 0 — Tipo de entrada (Regente Cam1)
  entry_type: EntryType;

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
  initial_summary: string;
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

const ENTRY_TYPE_OPTIONS: { value: EntryType; label: string; description: string; icon: string; available: boolean }[] = [
  {
    value: 'novo_cliente_novo_imovel',
    label: 'Novo cliente + novo imóvel',
    description: 'Cadastrar do zero',
    icon: '✨',
    available: true,
  },
  {
    value: 'cliente_existente_novo_imovel',
    label: 'Cliente existente + novo imóvel',
    description: 'Adicionar imóvel a um cliente já cadastrado',
    icon: '➕',
    available: true,
  },
  {
    value: 'cliente_existente_imovel_existente',
    label: 'Cliente existente + imóvel existente',
    description: 'Abrir nova demanda sobre base já criada',
    icon: '🔄',
    available: true,
  },
  {
    value: 'complementar_base_existente',
    label: 'Complementar base já iniciada',
    description: 'Adicionar dados/docs faltantes a um caso existente',
    icon: '📝',
    available: true,
  },
  {
    value: 'importar_documentos',
    label: 'Importar documentos',
    description: 'Subir arquivos e deixar a IA preencher',
    icon: '📄',
    available: true,
  },
];

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
  const [step, setStep] = useState<Step>(0);
  const [classifyResult, setClassifyResult] = useState<ClassifyResult | null>(null);
  const [classifying, setClassifying] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [draftExpiresAt, setDraftExpiresAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>({
    entry_type: 'novo_cliente_novo_imovel',
    client_mode: 'new', client_id: '', client_name: '', client_phone: '',
    client_email: '', client_cpf_cnpj: '', client_type: 'pf', source_channel: 'whatsapp',
    description: '', initial_summary: '', urgency: 'media',
    property_mode: 'none', property_id: '', property_name: '',
    property_municipality: '', property_state: '', property_car: '',
    intake_notes: '',
  });

  const set = (field: keyof FormState, value: string) =>
    setForm(prev => ({ ...prev, [field]: value }));

  // Regente Cam1: entry_type força certos modes no Step 1 e 3
  const selectEntryType = (t: EntryType) => {
    const forceExistingClient =
      t === 'cliente_existente_novo_imovel' ||
      t === 'cliente_existente_imovel_existente' ||
      t === 'complementar_base_existente';
    const forceExistingProperty =
      t === 'cliente_existente_imovel_existente' ||
      t === 'complementar_base_existente';
    setForm(prev => ({
      ...prev,
      entry_type: t,
      client_mode: forceExistingClient ? 'existing' : prev.client_mode,
      property_mode: forceExistingProperty
        ? 'existing'
        : t === 'cliente_existente_novo_imovel'
        ? 'new'
        : prev.property_mode,
    }));
  };

  const isEnrichFlow = form.entry_type === 'complementar_base_existente';

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

  // ── Monta payload compartilhado entre submit e salvar-rascunho ───────────
  const buildPayload = (): Record<string, unknown> => {
    const payload: Record<string, unknown> = {
      entry_type: form.entry_type,
      description: form.description.trim() || null,
      initial_summary: form.initial_summary.trim() || null,
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

    return payload;
  };

  // ── Etapa 4: criar caso OU complementar base ─────────────────────────────
  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      if (isEnrichFlow) {
        // CAM1-004: complementar base existente
        const clientId = parseInt(form.client_id);
        if (!clientId) {
          setError('Informe o ID do cliente existente.');
          setSubmitting(false);
          return;
        }
        const propertyId = form.property_id ? parseInt(form.property_id) : null;
        const enrichPayload = {
          client_id: clientId,
          property_id: propertyId,
          note: form.intake_notes || null,
        };
        const { data } = await api.post('/intake/enrich', enrichPayload);
        navigate('/processes', { state: { baseEnriched: true, enrichData: data } });
        return;
      }
      const { data } = await api.post('/intake/create-case', buildPayload());
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

  // ── Salvar rascunho (CAM1-008/009) ────────────────────────────────────────
  const handleSaveDraft = async () => {
    setSavingDraft(true);
    setError(null);
    try {
      const id = await persistDraft();
      if (!id) throw new Error('Falha ao salvar rascunho');
      navigate('/processes', { state: { draftSaved: true } });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (err as { message?: string })?.message;
      setError(msg || 'Erro ao salvar rascunho.');
    } finally {
      setSavingDraft(false);
    }
  };

  // Persiste o rascunho sem navegar — útil pra obter draftId antes de upload.
  const persistDraft = async (): Promise<number | null> => {
    try {
      const body = {
        entry_type: form.entry_type,
        form_data: buildPayload(),
      };
      if (draftId) {
        const { data } = await api.patch(`/intake/drafts/${draftId}`, body);
        setDraftExpiresAt(data?.expires_at ?? null);
        return draftId;
      }
      const { data } = await api.post('/intake/drafts', body);
      setDraftId(data.id);
      setDraftExpiresAt(data.expires_at ?? null);
      return data.id as number;
    } catch {
      return null;
    }
  };

  // Auto-cria rascunho ao entrar no Step 4 (Documentos) se ainda não existe.
  const ensureDraftBeforeStep4 = async () => {
    if (!draftId) {
      setError(null);
      const id = await persistDraft();
      if (!id) setError('Não consegui salvar o rascunho para anexar documentos.');
    }
  };

  const canGoNext = () => {
    if (step === 0) {
      const opt = ENTRY_TYPE_OPTIONS.find(o => o.value === form.entry_type);
      return !!opt?.available;
    }
    if (step === 1) {
      if (form.client_mode === 'existing') return form.client_id.trim().length > 0;
      // Regente Cam1: dados mínimos = nome + telefone + email + tipo
      return (
        form.client_name.trim().length >= 2 &&
        !!form.client_phone.trim() &&
        !!form.client_email.trim() &&
        !!form.client_type
      );
    }
    // Steps 2, 3 e 4 sempre permitem avançar (todos opcionais agora)
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
          {/* Sprint F Bloco 3: rascunho expira em 15 dias */}
          {draftExpiresAt && <DraftExpirationBadge expiresAt={draftExpiresAt} />}
        </div>

        {/* Stepper */}
        <div className="flex items-center justify-between mb-8 px-4">
          {([0, 1, 2, 3, 4, 5] as const).map((num, i) => {
            const labels = ['Entrada', 'Cliente', 'Demanda', 'Imóvel', 'Documentos', 'Confirmar'];
            const active = step === num;
            const done = step > num;
            return (
              <div key={num} className="flex-1 flex flex-col items-center gap-1">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-all ${
                  done ? 'bg-emerald-500 border-emerald-500 text-white' :
                  active ? 'bg-white border-white text-slate-900' :
                  'bg-transparent border-slate-600 text-slate-500'
                }`}>
                  {done ? '✓' : num}
                </div>
                <span className={`text-[10px] ${active ? 'text-white font-semibold' : 'text-slate-500'}`}>
                  {labels[i]}
                </span>
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

          {/* ── Etapa 0: Tipo de entrada (Regente Cam1) ────────────────────── */}
          {step === 0 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-white mb-1">O que você está cadastrando agora?</h2>
                <p className="text-slate-400 text-sm">Escolha o cenário para o sistema adaptar o fluxo.</p>
              </div>

              <div className="grid gap-3">
                {ENTRY_TYPE_OPTIONS.map(opt => {
                  const active = form.entry_type === opt.value;
                  return (
                    <button
                      key={opt.value}
                      onClick={() => opt.available && selectEntryType(opt.value)}
                      disabled={!opt.available}
                      className={`text-left p-4 rounded-xl border transition-all flex items-start gap-3 ${
                        !opt.available
                          ? 'bg-white/5 border-white/5 text-slate-500 cursor-not-allowed opacity-50'
                          : active
                          ? 'bg-emerald-500/10 border-emerald-500 text-white'
                          : 'bg-white/5 border-white/10 text-slate-300 hover:border-white/30'
                      }`}
                    >
                      <span className="text-2xl">{opt.icon}</span>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{opt.label}</span>
                          {!opt.available && (
                            <span className="text-[10px] uppercase tracking-wide bg-white/10 px-1.5 py-0.5 rounded">
                              Em breve
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-slate-400 mt-0.5 block">{opt.description}</span>
                      </div>
                      {active && <span className="text-emerald-400">✓</span>}
                    </button>
                  );
                })}
              </div>
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
                <p className="text-slate-400 text-sm">
                  Regra Regente: o card pode nascer <strong>sem</strong> descrição completa. Você complementa depois.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Resumo inicial <span className="text-slate-500 font-normal">(opcional — voz do cliente no primeiro contato)</span>
                </label>
                <textarea
                  rows={2}
                  value={form.initial_summary}
                  onChange={e => set('initial_summary', e.target.value)}
                  placeholder="Ex: Cliente ligou querendo regularizar CAR para pegar PRONAF"
                  className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Descrição técnica <span className="text-slate-500 font-normal">(opcional — habilita classificação automática)</span>
                </label>
                <textarea
                  rows={4}
                  value={form.description}
                  onChange={e => set('description', e.target.value)}
                  placeholder="Descrição mais detalhada — se tiver 10+ caracteres, o sistema pode pré-classificar a demanda."
                  className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 resize-none"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {form.description.length} caracteres {form.description.length < 10 && form.description.length > 0 ? '(mín. 10 para classificar)' : ''}
                </p>
              </div>

              <Select label="Urgência" value={form.urgency} onChange={v => set('urgency', v)} options={URGENCY_OPTIONS} />

              {form.description.trim().length >= 10 && !classifyResult && (
                <button
                  onClick={handleClassify}
                  disabled={classifying}
                  className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold transition-all flex items-center justify-center gap-2"
                >
                  {classifying ? (
                    <><span className="animate-spin">⟳</span> Classificando...</>
                  ) : (
                    '🔍 Classificar demanda (opcional)'
                  )}
                </button>
              )}
              {classifyResult && (
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

          {/* ── Etapa 4: Documentos (Regente Cam1 Bloco 3 — opcional) ───────── */}
          {step === 4 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-white mb-1">📎 Documentos (opcional)</h2>
                <p className="text-slate-400 text-sm">
                  Upload opcional dos documentos iniciais. Regra Regente: o card nasce mesmo sem docs completos — isso aqui só pré-alimenta a base.
                </p>
              </div>
              {draftId ? (
                <DraftDocumentUploader draftId={draftId} />
              ) : (
                <div className="p-4 rounded-xl bg-slate-800/50 border border-white/10 text-sm text-slate-300">
                  Preparando rascunho... <button
                    onClick={ensureDraftBeforeStep4}
                    className="underline hover:text-white"
                  >
                    Reintentar
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Etapa 5: Confirmar ────────────────────────────────────────── */}
          {step === 5 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-white mb-1">Confirmar e abrir caso</h2>
                <p className="text-slate-400 text-sm">
                  Revise o resumo. Você pode criar o card agora ou salvar como rascunho pra continuar depois.
                </p>
              </div>

              {/* Resumo */}
              <div className="space-y-3">
                <SummaryRow icon="🎯" label="Cenário">
                  {ENTRY_TYPE_OPTIONS.find(o => o.value === form.entry_type)?.label ?? form.entry_type}
                </SummaryRow>
                <SummaryRow icon="👤" label="Cliente">
                  {form.client_mode === 'existing'
                    ? `Cliente ID #${form.client_id}`
                    : form.client_name}
                </SummaryRow>
                <SummaryRow icon="🏷️" label="Tipo de demanda">
                  {classifyResult ? (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                      classifyResult.urgency_flag === 'critica' ? 'bg-red-500/20 text-red-300' :
                      classifyResult.urgency_flag === 'alta' ? 'bg-orange-500/20 text-orange-300' :
                      'bg-emerald-500/20 text-emerald-300'
                    }`}>
                      {classifyResult.demand_label}
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-500/20 text-slate-300">
                      Não identificado — a IA classifica depois
                    </span>
                  )}
                </SummaryRow>
                <SummaryRow icon="🚨" label="Urgência">
                  {URGENCY_OPTIONS.find(o => o.value === form.urgency)?.label ?? form.urgency}
                </SummaryRow>
                {classifyResult && (
                  <SummaryRow icon="📋" label="Documentos esperados">
                    {classifyResult.required_documents.filter(d => d.required).length} obrigatórios, {classifyResult.required_documents.length} no total
                  </SummaryRow>
                )}
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

              <div className="space-y-3">
                <button
                  onClick={handleSubmit}
                  disabled={submitting || savingDraft}
                  className="w-full py-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white font-bold text-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/25"
                >
                  {submitting ? (
                    <><span className="animate-spin">⟳</span> {isEnrichFlow ? 'Complementando...' : 'Criando caso...'}</>
                  ) : isEnrichFlow ? (
                    '📝 Complementar base agora'
                  ) : (
                    '✅ Abrir caso agora'
                  )}
                </button>

                {!isEnrichFlow && (
                  <button
                    onClick={handleSaveDraft}
                    disabled={submitting || savingDraft}
                    className="w-full py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-sm font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-40"
                  >
                    {savingDraft ? (
                      <><span className="animate-spin">⟳</span> Salvando...</>
                    ) : (
                      '💾 Salvar e continuar depois'
                    )}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Navegação */}
          <div className="flex justify-between mt-8 pt-6 border-t border-white/10">
            <button
              onClick={() => setStep(prev => Math.max(0, prev - 1) as Step)}
              disabled={step === 0}
              className="px-6 py-2.5 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 disabled:opacity-30 transition-all text-sm font-medium"
            >
              ← Voltar
            </button>
            {step < 5 && (
              <button
                onClick={async () => {
                  setError(null);
                  // Auto-salva rascunho ao entrar no Step 4 (Documentos) pra habilitar upload
                  if (step === 3) {
                    await ensureDraftBeforeStep4();
                  }
                  setStep(prev => Math.min(5, prev + 1) as Step);
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

/**
 * Sprint F Bloco 3 — Regente Cam1: rascunho expira em 15 dias (sócia 2026-04-19).
 * Mostra um badge com dias restantes. Amarelo se <= 3 dias.
 */
function DraftExpirationBadge({ expiresAt }: { expiresAt: string }) {
  const diffMs = new Date(expiresAt).getTime() - Date.now();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return null;

  const urgent = diffDays <= 3;
  const cls = urgent
    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
    : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';

  return (
    <span
      className={`inline-flex items-center gap-1.5 mt-3 text-xs px-3 py-1 rounded-full border ${cls}`}
      title="Rascunho \u00e9 mantido por at\u00e9 15 dias sem atividade."
    >
      \ud83d\udcbe Rascunho salvo \u00b7 expira em {diffDays === 0 ? 'hoje' : `${diffDays} dia${diffDays > 1 ? 's' : ''}`}
    </span>
  );
}
