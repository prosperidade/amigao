/**
 * AIPanel — Sprint 5 (Wave 2)
 *
 * Painel de IA exibido na aba "IA" do detalhe do processo.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  Brain, Zap, RefreshCw, Clock, CheckCircle2, XCircle,
  AlertCircle, ChevronDown, ChevronRight, Loader2,
} from 'lucide-react';

interface AIPanelProps {
  processId: number;
  processDemandType?: string | null;
  processDescription?: string;
}

interface AIJob {
  id: number;
  entity_type: string;
  entity_id: number;
  job_type: string;
  status: string;
  model_used: string | null;
  provider: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  duration_ms: number | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

interface AIStatus {
  ai_enabled: boolean;
  ai_configured: boolean;
  default_model: string | null;
  providers_available: string[];
}

interface ClassifyResult {
  demand_type: string;
  demand_label: string;
  confidence: string;
  initial_diagnosis: string;
  urgency_flag: string | null;
  relevant_agencies: string[];
  suggested_next_steps: string[];
  llm_used: boolean;
  ai_job_id: number | null;
}

const JOB_TYPE_LABEL: Record<string, string> = {
  classify_demand: 'Classificação de Demanda',
  extract_document: 'Extração de Documento',
  generate_proposal: 'Geração de Proposta',
  generate_dossier_summary: 'Resumo de Dossiê',
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending:   <Clock className="w-4 h-4 text-yellow-500 dark:text-yellow-400" />,
  running:   <Loader2 className="w-4 h-4 text-blue-500 dark:text-blue-400 animate-spin" />,
  completed: <CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />,
  failed:    <XCircle className="w-4 h-4 text-red-500 dark:text-red-400" />,
};

const CONFIDENCE_CLS: Record<string, string> = {
  high:   'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30',
  medium: 'bg-yellow-50 dark:bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 border-yellow-200 dark:border-yellow-500/30',
  low:    'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300 border-red-200 dark:border-red-500/30',
};

export default function AIPanel({ processId, processDemandType, processDescription }: AIPanelProps) {
  const queryClient = useQueryClient();
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  const [classifyResult, setClassifyResult] = useState<ClassifyResult | null>(null);

  const { data: aiStatus } = useQuery<AIStatus>({
    queryKey: ['ai-status'],
    queryFn: () => api.get('/ai/status').then(r => r.data),
    staleTime: 60_000,
  });

  const { data: jobs = [], isLoading: jobsLoading } = useQuery<AIJob[]>({
    queryKey: ['ai-jobs', processId],
    queryFn: () =>
      api.get('/ai/jobs', {
        params: { entity_type: 'process', entity_id: processId },
      }).then(r => r.data),
    refetchInterval: (query: any) => {
      const d = query?.state?.data as AIJob[] | undefined;
      const hasRunning = Array.isArray(d) && d.some(j => j.status === 'running' || j.status === 'pending');
      return hasRunning ? 3000 : false;
    },
  });

  const classifyMutation = useMutation({
    mutationFn: () =>
      api.post('/ai/classify', {
        description: processDescription || '',
        process_type: processDemandType,
        save_job: true,
      }).then(r => r.data as ClassifyResult),
    onSuccess: (data) => {
      setClassifyResult(data);
      queryClient.invalidateQueries({ queryKey: ['ai-jobs', processId] });
    },
  });

  const classifyAsyncMutation = useMutation({
    mutationFn: () =>
      api.post('/ai/jobs/classify-async', { process_id: processId }).then(r => r.data),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['ai-jobs', processId] }), 2000);
    },
  });

  const isConfigured = aiStatus?.ai_configured ?? false;

  return (
    <div className="space-y-5">

      {/* Status da IA */}
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-xl bg-purple-50 dark:bg-purple-500/15 flex items-center justify-center">
            <Brain className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">Inteligência Artificial</h3>
            <p className="text-xs text-gray-400 dark:text-slate-500">Classificação e extração via LLM</p>
          </div>
          <span className={`ml-auto text-xs px-2.5 py-1 rounded-full border font-medium ${
            isConfigured
              ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30'
              : 'bg-gray-100 dark:bg-slate-500/10 text-gray-500 dark:text-slate-400 border-gray-200 dark:border-slate-500/30'
          }`}>
            {isConfigured ? '● Configurada' : '○ Não configurada'}
          </span>
        </div>

        {isConfigured ? (
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-3">
              <p className="text-xs text-gray-400 dark:text-slate-500 mb-0.5">Modelo padrão</p>
              <p className="text-sm font-semibold text-gray-800 dark:text-white">{aiStatus?.default_model}</p>
            </div>
            <div className="rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-3">
              <p className="text-xs text-gray-400 dark:text-slate-500 mb-0.5">Providers ativos</p>
              <p className="text-sm font-semibold text-gray-800 dark:text-white">{aiStatus?.providers_available.join(', ')}</p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-amber-50 dark:bg-amber-500/5 border border-amber-100 dark:border-amber-500/20 p-4">
            <p className="text-sm text-gray-700 dark:text-slate-300 leading-relaxed">
              Configure no <code className="text-xs bg-gray-100 dark:bg-white/10 px-1.5 py-0.5 rounded font-mono">.env</code>:
            </p>
            <ul className="mt-2 space-y-1">
              {[
                'AI_ENABLED=true',
                'OPENAI_API_KEY=sk-...',
              ].map(line => (
                <li key={line}>
                  <code className="text-xs bg-gray-100 dark:bg-white/10 text-purple-700 dark:text-purple-300 px-2 py-0.5 rounded font-mono">{line}</code>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Ações */}
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <h4 className="text-base font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4 text-yellow-500 dark:text-yellow-400" />
          Ações de IA
        </h4>

        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => classifyMutation.mutate()}
            disabled={!isConfigured || classifyMutation.isPending}
            className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors"
          >
            {classifyMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Brain className="w-4 h-4" />}
            Classificar Demanda (IA)
          </button>

          <button
            onClick={() => classifyAsyncMutation.mutate()}
            disabled={!isConfigured || classifyAsyncMutation.isPending}
            className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 dark:bg-white/10 hover:bg-gray-200 dark:hover:bg-white/15 disabled:opacity-40 disabled:cursor-not-allowed text-gray-700 dark:text-slate-300 text-sm font-medium rounded-xl border border-gray-200 dark:border-white/10 transition-colors"
          >
            {classifyAsyncMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <RefreshCw className="w-4 h-4" />}
            Reclassificar (background)
          </button>
        </div>

        {classifyMutation.isError && (
          <div className="mt-3 flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            Erro na classificação. Verifique se a IA está configurada.
          </div>
        )}

        {classifyAsyncMutation.isSuccess && (
          <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">
            ✓ Task enfileirada — o resultado aparecerá no histórico em instantes.
          </p>
        )}
      </div>

      {/* Resultado da classificação */}
      {classifyResult && (
        <div className="rounded-xl bg-purple-50 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/20 p-5">
          <div className="flex items-start justify-between mb-3">
            <h4 className="text-base font-semibold text-gray-900 dark:text-white">Resultado da Classificação</h4>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded border ${CONFIDENCE_CLS[classifyResult.confidence] ?? ''}`}>
                Confiança {classifyResult.confidence}
              </span>
              {classifyResult.llm_used && (
                <span className="text-xs px-2 py-0.5 rounded border bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-500/30">
                  via LLM
                </span>
              )}
            </div>
          </div>

          <p className="text-sm font-bold text-purple-700 dark:text-purple-200 mb-2">
            {classifyResult.demand_label}
          </p>
          <p className="text-sm text-gray-700 dark:text-slate-300 mb-4 leading-relaxed">
            {classifyResult.initial_diagnosis}
          </p>

          {classifyResult.suggested_next_steps.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider mb-2">Próximos Passos</p>
              <ul className="space-y-1.5">
                {classifyResult.suggested_next_steps.map((step, i) => (
                  <li key={i} className="text-sm text-gray-700 dark:text-slate-300 flex items-start gap-2">
                    <span className="text-purple-500 dark:text-purple-400 mt-0.5 font-bold">›</span>
                    {step}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {classifyResult.relevant_agencies.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              <span className="text-xs text-gray-500 dark:text-slate-400 mr-1 self-center">Órgãos:</span>
              {classifyResult.relevant_agencies.map(agency => (
                <span key={agency} className="text-xs px-2 py-0.5 bg-white dark:bg-white/5 text-gray-600 dark:text-slate-300 rounded border border-gray-200 dark:border-white/10">
                  {agency}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Histórico de Jobs */}
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <h4 className="text-base font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4 text-gray-400 dark:text-slate-400" />
          Histórico de Jobs IA
          {jobsLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400 dark:text-slate-400 ml-1" />}
        </h4>

        {jobs.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-slate-500">Nenhum job de IA registrado para este processo.</p>
        ) : (
          <div className="space-y-2">
            {jobs.map(job => (
              <div key={job.id} className="border border-gray-100 dark:border-white/10 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedJob(expandedJob === job.id ? null : job.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-left"
                >
                  {STATUS_ICON[job.status] ?? <AlertCircle className="w-4 h-4 text-gray-400 dark:text-slate-400" />}
                  <span className="text-sm font-medium text-gray-800 dark:text-white flex-1">
                    {JOB_TYPE_LABEL[job.job_type] ?? job.job_type}
                  </span>
                  {job.model_used && (
                    <span className="text-xs text-gray-400 dark:text-slate-500 hidden sm:block">{job.model_used}</span>
                  )}
                  {job.cost_usd != null && (
                    <span className="text-xs text-gray-500 dark:text-slate-400">
                      ${job.cost_usd.toFixed(5)}
                    </span>
                  )}
                  <span className="text-xs text-gray-400 dark:text-slate-500">
                    {new Date(job.created_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                  {expandedJob === job.id
                    ? <ChevronDown className="w-4 h-4 text-gray-400 dark:text-slate-400" />
                    : <ChevronRight className="w-4 h-4 text-gray-400 dark:text-slate-400" />}
                </button>

                {expandedJob === job.id && (
                  <div className="px-4 pb-4 border-t border-gray-100 dark:border-white/10 pt-3 space-y-2 bg-gray-50 dark:bg-black/10">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
                      <span className="text-gray-500 dark:text-slate-400">Status</span>
                      <span className="text-gray-800 dark:text-white capitalize font-medium">{job.status}</span>
                      {job.tokens_in != null && <>
                        <span className="text-gray-500 dark:text-slate-400">Tokens entrada</span>
                        <span className="text-gray-800 dark:text-white">{job.tokens_in}</span>
                      </>}
                      {job.tokens_out != null && <>
                        <span className="text-gray-500 dark:text-slate-400">Tokens saída</span>
                        <span className="text-gray-800 dark:text-white">{job.tokens_out}</span>
                      </>}
                      {job.duration_ms != null && <>
                        <span className="text-gray-500 dark:text-slate-400">Duração</span>
                        <span className="text-gray-800 dark:text-white">{job.duration_ms}ms</span>
                      </>}
                      {job.provider && <>
                        <span className="text-gray-500 dark:text-slate-400">Provider</span>
                        <span className="text-gray-800 dark:text-white">{job.provider}</span>
                      </>}
                    </div>

                    {job.result && (
                      <div className="mt-2">
                        <p className="text-xs text-gray-400 dark:text-slate-400 mb-1 font-semibold uppercase tracking-wider">Resultado</p>
                        <pre className="text-xs text-gray-700 dark:text-slate-300 bg-white dark:bg-black/20 rounded-lg p-3 overflow-x-auto max-h-40 border border-gray-100 dark:border-white/5">
                          {JSON.stringify(job.result, null, 2)}
                        </pre>
                      </div>
                    )}

                    {job.error && (
                      <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 rounded-lg p-3 border border-red-100 dark:border-red-500/20">
                        {job.error}
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
