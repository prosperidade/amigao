/**
 * Settings — Configurações do usuário (Regente Camada 4).
 *
 * 6 abas conforme spec da sócia (PDF Camada 4):
 *  1. Perfil
 *  2. Assinatura e Pagamento
 *  3. Notificações
 *  4. Preferências Operacionais
 *  5. Preferências de IA
 *  6. Segurança
 *
 * Princípio: "configuração boa não parece painel de avião".
 */
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import {
  User as UserIcon, CreditCard, Bell, SlidersHorizontal,
  Sparkles, Shield, Save, Loader2, CheckCircle2, AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';

// ─── Types (espelham schemas do backend) ─────────────────────────────────────

interface ProfilePrefs {
  phone: string | null;
  role: string | null;
  company: string | null;
  avatar_url: string | null;
  language: string;
  timezone: string;
}

interface NotificationPrefs {
  email: boolean;
  whatsapp: boolean;
  in_app: boolean;
  push: boolean;
  critical_only: boolean;
  daily_summary: boolean;
  weekly_summary: boolean;
  disabled_alert_kinds: string[];
}

interface OperationalPrefs {
  default_view: 'dashboard' | 'quadro_acoes' | 'cliente_hub';
  default_sort: 'priority' | 'urgency' | 'date' | 'responsible';
  compact_mode: boolean;
  date_format: 'dd/mm/yyyy' | 'yyyy-mm-dd';
  default_state_uf: string | null;
}

interface AiPrefs {
  assistance_level: 'automatic' | 'balanced' | 'manual';
  summary_length: 'short' | 'medium' | 'detailed';
  show_suggestions_in_flow: boolean;
  show_auto_summaries: boolean;
  require_human_validation_before_advance: boolean;
  save_ai_readings_history: boolean;
}

interface UserPreferences {
  profile: ProfilePrefs;
  notifications: NotificationPrefs;
  operational: OperationalPrefs;
  ai: AiPrefs;
}

interface UserMeResponse {
  id: number;
  tenant_id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  preferences: UserPreferences;
}

type TabKey = 'profile' | 'billing' | 'notifications' | 'operational' | 'ai' | 'security';

const TABS: { key: TabKey; label: string; icon: typeof UserIcon }[] = [
  { key: 'profile',       label: 'Perfil',         icon: UserIcon },
  { key: 'billing',       label: 'Pagamento',      icon: CreditCard },
  { key: 'notifications', label: 'Notifica\u00e7\u00f5es',   icon: Bell },
  { key: 'operational',   label: 'Prefer\u00eancias',  icon: SlidersHorizontal },
  { key: 'ai',            label: 'IA',             icon: Sparkles },
  { key: 'security',      label: 'Seguran\u00e7a',      icon: Shield },
];

// ─── Componente principal ────────────────────────────────────────────────────

export default function Settings() {
  const [activeTab, setActiveTab] = useState<TabKey>('profile');
  const queryClient = useQueryClient();

  const { data: me, isLoading } = useQuery({
    queryKey: ['me-full'],
    queryFn: () => api.get<UserMeResponse>('/auth/me/full').then(r => r.data),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['me-full'] });

  if (isLoading || !me) {
    return (
      <div className="max-w-4xl mx-auto space-y-4 animate-pulse">
        <div className="h-10 bg-gray-100 dark:bg-zinc-800/50 rounded w-48" />
        <div className="h-12 bg-gray-100 dark:bg-zinc-800/50 rounded" />
        <div className="h-64 bg-gray-100 dark:bg-zinc-800/50 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Configura\u00e7\u00f5es</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Gerencie seu perfil, assinatura, notifica\u00e7\u00f5es e prefer\u00eancias de IA.
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-zinc-800 flex gap-1 overflow-x-auto">
        {TABS.map(t => {
          const Icon = t.icon;
          const active = activeTab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 text-sm font-medium transition-colors whitespace-nowrap shrink-0 ${
                active
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Conteúdo */}
      <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-6">
        {activeTab === 'profile' && <ProfileTab me={me} onSaved={invalidate} />}
        {activeTab === 'billing' && <BillingTab />}
        {activeTab === 'notifications' && <NotificationsTab me={me} onSaved={invalidate} />}
        {activeTab === 'operational' && <OperationalTab me={me} onSaved={invalidate} />}
        {activeTab === 'ai' && <AiTab me={me} onSaved={invalidate} />}
        {activeTab === 'security' && <SecurityTab />}
      </div>
    </div>
  );
}

// ─── Helpers genéricos ───────────────────────────────────────────────────────

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-gray-900 dark:text-white">{title}</h2>
        {description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-gray-400">{hint}</span>}
    </label>
  );
}

function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <label className="flex items-start justify-between gap-4 py-2.5 cursor-pointer">
      <div className="min-w-0">
        <span className="text-sm font-medium text-gray-900 dark:text-white">{label}</span>
        {hint && <span className="block text-xs text-gray-500 mt-0.5">{hint}</span>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
          checked ? 'bg-emerald-500' : 'bg-gray-200 dark:bg-zinc-700'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-0.5'
          }`}
        />
      </button>
    </label>
  );
}

function SaveButton({ onClick, pending, disabled }: { onClick: () => void; pending: boolean; disabled?: boolean }) {
  return (
    <div className="flex justify-end pt-3 border-t border-gray-100 dark:border-zinc-800">
      <button
        type="button"
        onClick={onClick}
        disabled={pending || disabled}
        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {pending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
        {pending ? 'Salvando...' : 'Salvar altera\u00e7\u00f5es'}
      </button>
    </div>
  );
}

// ─── Tab 1: Perfil ────────────────────────────────────────────────────────────

function ProfileTab({ me, onSaved }: { me: UserMeResponse; onSaved: () => void }) {
  const [fullName, setFullName] = useState(me.full_name ?? '');
  const [email, setEmail] = useState(me.email);
  const [phone, setPhone] = useState(me.preferences.profile.phone ?? '');
  const [role, setRole] = useState(me.preferences.profile.role ?? '');
  const [company, setCompany] = useState(me.preferences.profile.company ?? '');

  const profileMutation = useMutation({
    mutationFn: async () => {
      // 1. Patch identidade (full_name / email) se mudou
      if (fullName !== (me.full_name ?? '') || email !== me.email) {
        await api.patch('/auth/me', { full_name: fullName, email });
      }
      // 2. Patch preferences.profile
      await api.patch('/auth/me/preferences', {
        profile: {
          ...me.preferences.profile,
          phone: phone || null,
          role: role || null,
          company: company || null,
        },
      });
    },
    onSuccess: () => { toast.success('Perfil atualizado'); onSaved(); },
    onError: (err: AxiosError<{ detail?: string }>) =>
      toast.error(err.response?.data?.detail ?? 'Erro ao salvar perfil'),
  });

  return (
    <Section title="Perfil" description="Suas informa\u00e7\u00f5es b\u00e1sicas e identidade dentro do Reg\u00eante.">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Nome completo">
          <input
            type="text"
            value={fullName}
            onChange={e => setFullName(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          />
        </Field>
        <Field label="Email">
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          />
        </Field>
        <Field label="Telefone" hint="Usado para notifica\u00e7\u00f5es por WhatsApp (futuro).">
          <input
            type="tel"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            placeholder="(11) 99999-0000"
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          />
        </Field>
        <Field label="Cargo ou fun\u00e7\u00e3o">
          <input
            type="text"
            value={role}
            onChange={e => setRole(e.target.value)}
            placeholder="Consultor, coordenador..."
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          />
        </Field>
        <Field label="Empresa">
          <input
            type="text"
            value={company}
            onChange={e => setCompany(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          />
        </Field>
      </div>
      <SaveButton onClick={() => profileMutation.mutate()} pending={profileMutation.isPending} />
    </Section>
  );
}

// ─── Tab 2: Assinatura e Pagamento (stub — billing integration future) ──────

function BillingTab() {
  return (
    <Section title="Assinatura e Pagamento" description="Plano atual, forma de pagamento e hist\u00f3rico de cobran\u00e7a.">
      <div className="rounded-xl border border-dashed border-gray-200 dark:border-zinc-700 p-6 text-center">
        <CreditCard className="w-10 h-10 text-gray-300 dark:text-zinc-600 mx-auto mb-3" />
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Integra\u00e7\u00e3o com billing em breve</p>
        <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
          Plano, m\u00e9todo de pagamento (cart\u00e3o / PIX / boleto) e hist\u00f3rico de faturas ficar\u00e3o dispon\u00edveis nesta se\u00e7\u00e3o.
        </p>
      </div>
    </Section>
  );
}

// ─── Tab 3: Notificações ─────────────────────────────────────────────────────

function NotificationsTab({ me, onSaved }: { me: UserMeResponse; onSaved: () => void }) {
  const [prefs, setPrefs] = useState<NotificationPrefs>(me.preferences.notifications);

  const save = useMutation({
    mutationFn: () => api.patch('/auth/me/preferences', { notifications: prefs }),
    onSuccess: () => { toast.success('Notifica\u00e7\u00f5es atualizadas'); onSaved(); },
  });

  return (
    <Section title="Notifica\u00e7\u00f5es" description="Escolha onde e quando receber alertas do Reg\u00eante.">
      <div>
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-500 dark:text-gray-400 mb-1">
          Canais
        </h3>
        <Toggle
          label="Email"
          checked={prefs.email}
          onChange={v => setPrefs({ ...prefs, email: v })}
        />
        <Toggle
          label="WhatsApp"
          checked={prefs.whatsapp}
          onChange={v => setPrefs({ ...prefs, whatsapp: v })}
          hint="Requer telefone cadastrado no Perfil."
        />
        <Toggle
          label="Notifica\u00e7\u00f5es in-app"
          checked={prefs.in_app}
          onChange={v => setPrefs({ ...prefs, in_app: v })}
        />
        <Toggle
          label="Push (browser)"
          checked={prefs.push}
          onChange={v => setPrefs({ ...prefs, push: v })}
        />
      </div>

      <div className="pt-3 border-t border-gray-100 dark:border-zinc-800">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-500 dark:text-gray-400 mb-1">
          Frequ\u00eancia
        </h3>
        <Toggle
          label="Apenas alertas cr\u00edticos"
          checked={prefs.critical_only}
          onChange={v => setPrefs({ ...prefs, critical_only: v })}
          hint="Filtra eventos de baixa prioridade."
        />
        <Toggle
          label="Resumo di\u00e1rio"
          checked={prefs.daily_summary}
          onChange={v => setPrefs({ ...prefs, daily_summary: v })}
        />
        <Toggle
          label="Resumo semanal"
          checked={prefs.weekly_summary}
          onChange={v => setPrefs({ ...prefs, weekly_summary: v })}
        />
      </div>

      <SaveButton onClick={() => save.mutate()} pending={save.isPending} />
    </Section>
  );
}

// ─── Tab 4: Preferências Operacionais ────────────────────────────────────────

function OperationalTab({ me, onSaved }: { me: UserMeResponse; onSaved: () => void }) {
  const [prefs, setPrefs] = useState<OperationalPrefs>(me.preferences.operational);

  const save = useMutation({
    mutationFn: () => api.patch('/auth/me/preferences', { operational: prefs }),
    onSuccess: () => { toast.success('Prefer\u00eancias atualizadas'); onSaved(); },
  });

  return (
    <Section title="Prefer\u00eancias operacionais" description="Como voc\u00ea prefere operar dentro do Reg\u00eante.">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Tela inicial ao entrar">
          <select
            value={prefs.default_view}
            onChange={e => setPrefs({ ...prefs, default_view: e.target.value as OperationalPrefs['default_view'] })}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          >
            <option value="dashboard">Dashboard</option>
            <option value="quadro_acoes">Quadro de A\u00e7\u00f5es</option>
            <option value="cliente_hub">Cliente Hub</option>
          </select>
        </Field>

        <Field label="Ordena\u00e7\u00e3o padr\u00e3o no Quadro">
          <select
            value={prefs.default_sort}
            onChange={e => setPrefs({ ...prefs, default_sort: e.target.value as OperationalPrefs['default_sort'] })}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          >
            <option value="priority">Prioridade</option>
            <option value="urgency">Urg\u00eancia</option>
            <option value="date">Data</option>
            <option value="responsible">Respons\u00e1vel</option>
          </select>
        </Field>

        <Field label="Formato de data">
          <select
            value={prefs.date_format}
            onChange={e => setPrefs({ ...prefs, date_format: e.target.value as OperationalPrefs['date_format'] })}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          >
            <option value="dd/mm/yyyy">DD/MM/AAAA</option>
            <option value="yyyy-mm-dd">AAAA-MM-DD</option>
          </select>
        </Field>

        <Field label="UF padr\u00e3o" hint="Pr\u00e9-seleciona filtro se voc\u00ea s\u00f3 atua em uma UF.">
          <input
            type="text"
            value={prefs.default_state_uf ?? ''}
            maxLength={2}
            onChange={e => setPrefs({ ...prefs, default_state_uf: e.target.value.toUpperCase() || null })}
            placeholder="SP, MG, GO..."
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200 uppercase"
          />
        </Field>
      </div>

      <div className="pt-3 border-t border-gray-100 dark:border-zinc-800">
        <Toggle
          label="Modo compacto"
          checked={prefs.compact_mode}
          onChange={v => setPrefs({ ...prefs, compact_mode: v })}
          hint="Cards e listagens mais densos para ganhar espa\u00e7o vertical."
        />
      </div>

      <SaveButton onClick={() => save.mutate()} pending={save.isPending} />
    </Section>
  );
}

// ─── Tab 5: Preferências de IA ───────────────────────────────────────────────

function AiTab({ me, onSaved }: { me: UserMeResponse; onSaved: () => void }) {
  const [prefs, setPrefs] = useState<AiPrefs>(me.preferences.ai);

  const save = useMutation({
    mutationFn: () => api.patch('/auth/me/preferences', { ai: prefs }),
    onSuccess: () => { toast.success('Prefer\u00eancias de IA atualizadas'); onSaved(); },
  });

  return (
    <Section
      title="Prefer\u00eancias de IA"
      description='Como a IA deve se comportar no apoio ao seu trabalho. "Controle percebido com complexidade escondida".'
    >
      <Field label="N\u00edvel de assist\u00eancia">
        <div className="grid grid-cols-3 gap-2 mt-1">
          {(['automatic', 'balanced', 'manual'] as const).map(level => (
            <button
              key={level}
              type="button"
              onClick={() => setPrefs({ ...prefs, assistance_level: level })}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                prefs.assistance_level === level
                  ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : 'border-gray-200 dark:border-zinc-700 text-gray-600 dark:text-gray-300 hover:border-gray-300'
              }`}
            >
              {level === 'automatic' && 'Autom\u00e1tico'}
              {level === 'balanced' && 'Equilibrado'}
              {level === 'manual' && 'Controlado'}
            </button>
          ))}
        </div>
      </Field>

      <Field label="Tamanho de resumos gerados">
        <select
          value={prefs.summary_length}
          onChange={e => setPrefs({ ...prefs, summary_length: e.target.value as AiPrefs['summary_length'] })}
          className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
        >
          <option value="short">Curtos</option>
          <option value="medium">M\u00e9dios</option>
          <option value="detailed">Detalhados</option>
        </select>
      </Field>

      <div className="pt-3 border-t border-gray-100 dark:border-zinc-800">
        <Toggle
          label="Mostrar sugest\u00f5es da IA no fluxo"
          checked={prefs.show_suggestions_in_flow}
          onChange={v => setPrefs({ ...prefs, show_suggestions_in_flow: v })}
        />
        <Toggle
          label="Exibir resumos autom\u00e1ticos"
          checked={prefs.show_auto_summaries}
          onChange={v => setPrefs({ ...prefs, show_auto_summaries: v })}
        />
        <Toggle
          label="Exigir valida\u00e7\u00e3o humana antes de avan\u00e7ar etapa"
          checked={prefs.require_human_validation_before_advance}
          onChange={v => setPrefs({ ...prefs, require_human_validation_before_advance: v })}
          hint="Recomendado para manter rastreabilidade e governan\u00e7a."
        />
        <Toggle
          label="Salvar hist\u00f3rico das leituras da IA"
          checked={prefs.save_ai_readings_history}
          onChange={v => setPrefs({ ...prefs, save_ai_readings_history: v })}
        />
      </div>

      <SaveButton onClick={() => save.mutate()} pending={save.isPending} />
    </Section>
  );
}

// ─── Tab 6: Segurança ────────────────────────────────────────────────────────

function SecurityTab() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const passwordsMatch = useMemo(
    () => newPassword.length >= 8 && newPassword === confirmPassword,
    [newPassword, confirmPassword],
  );

  const changePassword = useMutation({
    mutationFn: () =>
      api.post('/auth/password-change', {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    onSuccess: () => {
      toast.success('Senha alterada com sucesso');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    },
    onError: (err: AxiosError<{ detail?: string }>) =>
      toast.error(err.response?.data?.detail ?? 'Erro ao trocar senha'),
  });

  return (
    <div className="space-y-6">
      <Section title="Trocar senha" description="Digite a senha atual e escolha uma nova de pelo menos 8 caracteres.">
        <div className="space-y-3 max-w-md">
          <Field label="Senha atual">
            <input
              type="password"
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
            />
          </Field>
          <Field label="Nova senha" hint="M\u00ednimo 8 caracteres.">
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
            />
          </Field>
          <Field label="Confirmar nova senha">
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
            />
          </Field>
          {newPassword && !passwordsMatch && (
            <p className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
              <AlertCircle className="w-3.5 h-3.5" />
              As senhas precisam coincidir e ter pelo menos 8 caracteres.
            </p>
          )}
          {newPassword && passwordsMatch && (
            <p className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" /> Senhas conferem.
            </p>
          )}
        </div>
        <SaveButton
          onClick={() => changePassword.mutate()}
          pending={changePassword.isPending}
          disabled={!currentPassword || !passwordsMatch}
        />
      </Section>

      <Section title="Autentica\u00e7\u00e3o em dois fatores (2FA)" description="Camada extra de seguran\u00e7a ao fazer login.">
        <div className="rounded-xl border border-dashed border-gray-200 dark:border-zinc-700 p-5 text-center">
          <Shield className="w-8 h-8 text-gray-300 dark:text-zinc-600 mx-auto mb-2" />
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">2FA em breve</p>
          <p className="text-xs text-gray-500 mt-1">
            Em breve voc\u00ea poder\u00e1 ativar 2FA por app autenticador ou SMS.
          </p>
        </div>
      </Section>
    </div>
  );
}
