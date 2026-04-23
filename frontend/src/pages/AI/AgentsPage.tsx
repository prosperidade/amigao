/**
 * AgentsPage — Painel dedicado de Agentes IA
 *
 * Rota: /agents
 * Funcionalidades:
 *  - Lista dos 10 agentes com status e descricao
 *  - Disparo manual de agente ou chain (com seletor de processo)
 *  - Historico global de execucoes (ultimas 50)
 *  - Metricas consolidadas (hoje): execucoes, taxa sucesso, custo, review
 *  - Resultado expandido de cada job
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import {
  Bot, Zap, Clock, CheckCircle2, XCircle, AlertCircle,
  ChevronDown, ChevronRight, Loader2, Link2, Eye,
  Workflow, BarChart3, DollarSign, Target, AlertTriangle,
  Search,
} from 'lucide-react';
import type { AgentInfo, AIJob } from '@/types/agent';
import { AGENT_LABELS, CHAIN_LABELS, CONFIDENCE_STYLES, STATUS_LABELS, CONFIDENCE_LABELS } from '@/types/agent';
import AgentResultRenderer from '@/components/AgentResultRenderer';

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending:   <Clock className="w-4 h-4 text-yellow-500" />,
  running:   <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
  failed:    <XCircle className="w-4 h-4 text-red-500" />,
};

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-500/10 dark:text-yellow-300 dark:border-yellow-500/30',
  running: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30',
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30',
  failed: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
};

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [selectedChain, setSelectedChain] = useState('');
  const [processIdInput, setProcessIdInput] = useState('');
  const [filterAgent, setFilterAgent] = useState('');

  // --- Queries ---

  const { data: agents = [] } = useQuery<AgentInfo[]>({
    queryKey: ['agents-registry'],
    queryFn: () => api.get('/agents/registry').then(r => r.data),
    staleTime: 300_000,
  });

  const { data: chains = {} } = useQuery<Record<string, string[]>>({
    queryKey: ['agents-chains'],
    queryFn: () => api.get('/agents/chains').then(r => r.data),
    staleTime: 300_000,
  });

  const { data: jobs = [], isLoading: jobsLoading } = useQuery<AIJob[]>({
    queryKey: ['ai-jobs-global'],
    queryFn: () => api.get('/ai/jobs', { params: { limit: 50 } }).then(r => r.data),
    refetchInterval: (query) => {
      const d = query?.state?.data as AIJob[] | undefined;
      const hasRunning = Array.isArray(d) && d.some(j => j.status === 'running' || j.status === 'pending');
      return hasRunning ? 4000 : 30000;
    },
  });

  // Sprint R — Budget mensal do tenant
  interface Budget {
    used_usd: number;
    limit_usd: number;
    pct: number;
    unlimited: boolean;
    alert: boolean;
    period_end: string;
  }
  const { data: budget } = useQuery<Budget>({
    queryKey: ['agents-budget'],
    queryFn: () => api.get('/agents/budget').then(r => r.data),
    refetchInterval: 60_000,
  });

  // --- Mutations ---

  const runAgentMutation = useMutation({
    mutationFn: () =>
      api.post('/agents/run-async', {
        agent_name: selectedAgent,
        process_id: processIdInput ? parseInt(processIdInput) : null,
        metadata: {},
      }).then(r => r.data),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['ai-jobs-global'] }), 2000);
    },
  });

  const runChainMutation = useMutation({
    mutationFn: () =>
      api.post('/agents/chain-async', {
        chain_name: selectedChain,
        process_id: processIdInput ? parseInt(processIdInput) : null,
        metadata: {},
        stop_on_review: true,
      }).then(r => r.data),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['ai-jobs-global'] }), 2000);
    },
  });

  // --- Metricas ---

  const today = new Date().toDateString();
  const todayJobs = jobs.filter(j => new Date(j.created_at).toDateString() === today);
  const completed = todayJobs.filter(j => j.status === 'completed').length;
  const running = todayJobs.filter(j => j.status === 'running' || j.status === 'pending').length;
  const totalCost = todayJobs.reduce((s, j) => s + (j.cost_usd ?? 0), 0);
  const needsReview = todayJobs.filter(j => j.result?.requires_review === true).length;
  const successRate = todayJobs.length > 0 ? Math.round((completed / todayJobs.length) * 100) : 0;

  // --- Filtro ---

  const filteredJobs = filterAgent
    ? jobs.filter(j => j.agent_name === filterAgent)
    : jobs;

  const chainNames = Object.keys(chains);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-500/20">
            <Bot className="w-6 h-6 text-purple-600 dark:text-purple-400" />
          </div>
          Agentes IA
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1 ml-14">
          10 agentes e 9 cadeias trabalhando em conjunto — execução automática e manual
        </p>
      </div>

      {/* Guia rápido */}
      <div className="rounded-xl bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-500/5 dark:to-blue-500/5 border border-purple-200 dark:border-purple-500/20 p-5">
        <h3 className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">Como usar os agentes?</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-700 dark:text-slate-300">
          <div>
            <p className="font-medium text-purple-700 dark:text-purple-300 mb-1">1. Automático</p>
            <p className="text-xs text-gray-500 dark:text-slate-400">
              Os agentes rodam sozinhos: ao criar um caso, ao enviar um documento e ao avançar etapas do processo.
            </p>
          </div>
          <div>
            <p className="font-medium text-purple-700 dark:text-purple-300 mb-1">2. Agente individual</p>
            <p className="text-xs text-gray-500 dark:text-slate-400">
              Escolha um agente e clique em Executar. Ideal para ações pontuais como gerar um orçamento ou classificar uma demanda.
            </p>
          </div>
          <div>
            <p className="font-medium text-blue-700 dark:text-blue-300 mb-1">3. Cadeia (sequência de agentes)</p>
            <p className="text-xs text-gray-500 dark:text-slate-400">
              Roda vários agentes em ordem. Ex.: "Diagnóstico Completo" executa Extrator, depois Legislação e depois Diagnóstico.
            </p>
          </div>
        </div>
      </div>

      {/* Métricas (hoje) */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Execuções hoje', value: String(todayJobs.length), icon: BarChart3, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-500/10' },
          { label: 'Taxa de sucesso', value: `${successRate}%`, icon: Target, color: successRate >= 80 ? 'text-emerald-600' : 'text-amber-600', bg: 'bg-emerald-50 dark:bg-emerald-500/10' },
          { label: 'Custo total (hoje)', value: `$${totalCost.toFixed(4)}`, icon: DollarSign, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-500/10' },
          { label: 'Aguardando revisão', value: String(needsReview), icon: Eye, color: needsReview > 0 ? 'text-amber-600' : 'text-gray-500', bg: 'bg-amber-50 dark:bg-amber-500/10' },
          { label: 'Em execução', value: String(running), icon: Loader2, color: running > 0 ? 'text-blue-600' : 'text-gray-500', bg: 'bg-blue-50 dark:bg-blue-500/10' },
        ].map(m => (
          <div key={m.label} className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-gray-500 dark:text-slate-400">{m.label}</p>
              <div className={`p-1.5 rounded-lg ${m.bg}`}>
                <m.icon className={`w-3.5 h-3.5 ${m.color}`} />
              </div>
            </div>
            <p className={`text-2xl font-bold ${m.color}`}>{m.value}</p>
          </div>
        ))}
      </div>

      {/* Sprint R — Orçamento mensal do tenant */}
      {budget && (
        <div
          className={`rounded-xl border p-5 ${
            budget.alert
              ? 'bg-amber-50 dark:bg-amber-500/5 border-amber-300 dark:border-amber-500/40'
              : 'bg-white dark:bg-white/5 border-gray-100 dark:border-white/10'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`p-1.5 rounded-lg ${budget.alert ? 'bg-amber-100 dark:bg-amber-500/20' : 'bg-emerald-50 dark:bg-emerald-500/10'}`}>
                <DollarSign className={`w-4 h-4 ${budget.alert ? 'text-amber-600 dark:text-amber-300' : 'text-emerald-600 dark:text-emerald-400'}`} />
              </div>
              <h3 className="text-sm font-semibold text-gray-800 dark:text-white">
                Orçamento mensal de IA
              </h3>
              {budget.alert && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 font-medium">
                  ATENÇÃO
                </span>
              )}
            </div>
            {budget.unlimited ? (
              <span className="text-xs text-gray-500 dark:text-slate-400">Ilimitado</span>
            ) : (
              <span className="text-xs text-gray-500 dark:text-slate-400">
                ${budget.used_usd.toFixed(4)} / ${budget.limit_usd.toFixed(2)}
              </span>
            )}
          </div>

          {!budget.unlimited && (
            <>
              <div className="h-2.5 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    budget.pct >= 100
                      ? 'bg-red-500'
                      : budget.alert
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, budget.pct)}%` }}
                />
              </div>
              <div className="mt-2 flex items-center justify-between text-xs text-gray-500 dark:text-slate-400">
                <span>{budget.pct.toFixed(1)}% usado</span>
                <span>Renova em {new Date(budget.period_end).toLocaleDateString('pt-BR')}</span>
              </div>
              {budget.alert && (
                <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                  Uso acima de 80% do orçamento mensal. Execuções são bloqueadas ao atingir 100%.
                </p>
              )}
            </>
          )}
          {budget.unlimited && (
            <p className="text-xs text-gray-500 dark:text-slate-400">
              Sem teto mensal definido para este tenant. Gasto no mês: ${budget.used_usd.toFixed(4)}.
            </p>
          )}
        </div>
      )}

      {/* Grid: Agentes + Disparo */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Lista de Agentes */}
        <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Bot className="w-4 h-4 text-purple-500" />
            Agentes Registrados ({agents.length})
          </h2>
          <div className="space-y-2">
            {agents.map(a => {
              const agentJobs = todayJobs.filter(j => j.agent_name === a.name);
              const agentCompleted = agentJobs.filter(j => j.status === 'completed').length;
              const agentFailed = agentJobs.filter(j => j.status === 'failed').length;
              return (
                <div
                  key={a.name}
                  className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-purple-200 dark:hover:border-purple-500/30 transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-purple-50 dark:bg-purple-500/10 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-purple-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 dark:text-white">
                      {AGENT_LABELS[a.name] ?? a.name}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-slate-500 truncate">{a.description}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {agentJobs.length > 0 && (
                      <span className="text-xs text-gray-400">
                        {agentCompleted > 0 && <span className="text-emerald-500">{agentCompleted} ok</span>}
                        {agentFailed > 0 && <span className="text-red-500 ml-1">{agentFailed} falhas</span>}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Painel de Disparo */}
        <div className="space-y-5">
          {/* Processo ID */}
          <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Search className="w-4 h-4 text-gray-400" />
              Contexto do Processo
            </h2>
            <div>
              <label className="text-xs text-gray-500 dark:text-slate-400 mb-1 block">ID do Processo (opcional)</label>
              <input
                type="number"
                value={processIdInput}
                onChange={e => setProcessIdInput(e.target.value)}
                placeholder="Ex: 42"
                className="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-gray-800 dark:text-white placeholder:text-gray-400"
              />
            </div>
          </div>

          {/* Executar agente individual */}
          <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-purple-500" />
              Executar agente
            </h2>
            <div className="flex gap-3">
              <select
                value={selectedAgent}
                onChange={e => setSelectedAgent(e.target.value)}
                className="flex-1 px-3 py-2.5 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-gray-800 dark:text-white"
              >
                <option value="">Selecione um agente...</option>
                {agents.map(a => (
                  <option key={a.name} value={a.name}>{AGENT_LABELS[a.name] ?? a.name}</option>
                ))}
              </select>
              <button
                onClick={() => runAgentMutation.mutate()}
                disabled={!selectedAgent || runAgentMutation.isPending}
                className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-sm font-medium rounded-xl transition-colors"
              >
                {runAgentMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                Executar
              </button>
            </div>
            {runAgentMutation.isSuccess && (
              <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-400">Execução agendada com sucesso.</p>
            )}
            {runAgentMutation.isError && (
              <p className="mt-2 text-xs text-red-600 dark:text-red-400">Erro ao executar agente.</p>
            )}
          </div>

          {/* Executar cadeia (sequência de agentes) */}
          <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Workflow className="w-4 h-4 text-blue-500" />
              Executar cadeia
            </h2>
            <div className="flex gap-3">
              <select
                value={selectedChain}
                onChange={e => setSelectedChain(e.target.value)}
                className="flex-1 px-3 py-2.5 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-gray-800 dark:text-white"
              >
                <option value="">Selecione uma cadeia...</option>
                {chainNames.map(c => (
                  <option key={c} value={c}>
                    {CHAIN_LABELS[c] ?? c} ({(chains[c] ?? []).join(' → ')})
                  </option>
                ))}
              </select>
              <button
                onClick={() => runChainMutation.mutate()}
                disabled={!selectedChain || runChainMutation.isPending}
                className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-medium rounded-xl transition-colors"
              >
                {runChainMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
                Executar
              </button>
            </div>
            {runChainMutation.isSuccess && (
              <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-400">Cadeia agendada com sucesso.</p>
            )}
            {runChainMutation.isError && (
              <p className="mt-2 text-xs text-red-600 dark:text-red-400">Erro ao executar cadeia.</p>
            )}
          </div>
        </div>
      </div>

      {/* Histórico global */}
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            Histórico de execuções
            {jobsLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400 ml-1" />}
          </h2>
          <select
            value={filterAgent}
            onChange={e => setFilterAgent(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-xs text-gray-700 dark:text-slate-300"
          >
            <option value="">Todos os agentes</option>
            {agents.map(a => (
              <option key={a.name} value={a.name}>{AGENT_LABELS[a.name] ?? a.name}</option>
            ))}
          </select>
        </div>

        {filteredJobs.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-slate-500 text-center py-8">Nenhuma execução registrada.</p>
        ) : (
          <div className="space-y-2">
            {filteredJobs.map(job => (
              <div key={job.id} className="border border-gray-100 dark:border-white/10 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedJob(expandedJob === job.id ? null : job.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-left"
                >
                  {STATUS_ICON[job.status] ?? <AlertCircle className="w-4 h-4 text-gray-400" />}
                  <span className="text-sm font-medium text-gray-800 dark:text-white">
                    {job.agent_name ? (AGENT_LABELS[job.agent_name] ?? job.agent_name) : job.job_type}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_BADGE[job.status] ?? ''}`}>
                    {STATUS_LABELS[job.status] ?? job.status}
                  </span>
                  {typeof job.result?.confidence === 'string' && (
                    <span className={`text-xs px-2 py-0.5 rounded border ${CONFIDENCE_STYLES[job.result.confidence] ?? ''}`}>
                      Confiança: {CONFIDENCE_LABELS[job.result.confidence] ?? job.result.confidence}
                    </span>
                  )}
                  {Boolean(job.result?.requires_review) && (
                    <span className="text-xs px-2 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30 flex items-center gap-1">
                      <Eye className="w-3 h-3" /> Aguardando revisão
                    </span>
                  )}
                  {job.entity_id && (
                    <button
                      onClick={e => { e.stopPropagation(); navigate(`/processes/${job.entity_id}`); }}
                      className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline"
                    >
                      #{job.entity_id}
                    </button>
                  )}
                  <span className="ml-auto text-xs text-gray-400 dark:text-slate-500">
                    {new Date(job.created_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                  {expandedJob === job.id
                    ? <ChevronDown className="w-4 h-4 text-gray-400" />
                    : <ChevronRight className="w-4 h-4 text-gray-400" />}
                </button>

                {expandedJob === job.id && (
                  <div className="px-4 pb-4 border-t border-gray-100 dark:border-white/10 pt-3 space-y-3 bg-gray-50 dark:bg-black/10">
                    {/* Metadata grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {[
                        { label: 'Agente', value: job.agent_name ? (AGENT_LABELS[job.agent_name] ?? job.agent_name) : '—' },
                        { label: 'Modelo', value: job.model_used ?? '—' },
                        { label: 'Provedor', value: job.provider ?? '—' },
                        { label: 'Duração', value: job.duration_ms != null ? `${(job.duration_ms / 1000).toFixed(1)}s` : '—' },
                        { label: 'Tokens enviados', value: job.tokens_in?.toLocaleString() ?? '—' },
                        { label: 'Tokens recebidos', value: job.tokens_out?.toLocaleString() ?? '—' },
                        { label: 'Custo (US$)', value: job.cost_usd != null ? `$${job.cost_usd.toFixed(5)}` : '—' },
                        { label: 'Caso', value: job.entity_id ? `#${job.entity_id}` : '—' },
                      ].map(m => (
                        <div key={m.label} className="p-2 rounded-lg bg-white dark:bg-white/5">
                          <p className="text-xs text-gray-400 dark:text-slate-500">{m.label}</p>
                          <p className="text-sm font-medium text-gray-800 dark:text-white">{m.value}</p>
                        </div>
                      ))}
                    </div>

                    {/* Resultado humanizado */}
                    {job.result && (
                      <AgentResultRenderer agentName={job.agent_name} result={job.result} />
                    )}

                    {/* Erro */}
                    {job.error && (
                      <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 rounded-lg p-3 border border-red-100 dark:border-red-500/20 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                        <span>{job.error}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
