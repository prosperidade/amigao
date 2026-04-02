/**
 * AIPanel — Sprint 5 (Wave 2)
 *
 * Painel de IA exibido na aba "IA" do detalhe do processo.
 * Funcionalidades:
 *  - Status da IA (habilitada/configurada)
 *  - Classificação LLM da demanda (síncrona e assíncrona)
 *  - Histórico de jobs de IA vinculados ao processo
 *  - Extração de campos de documentos (trigger manual)
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
  pending:   <Clock className="w-4 h-4 text-yellow-400" />,
  running:   <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
  completed: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
  failed:    <XCircle className="w-4 h-4 text-red-400" />,
};

const CONFIDENCE_CLS: Record<string, string> = {
  high:   'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  medium: 'bg-yellow-500/10 text-yellow-300 border-yellow-500/30',
  low:    'bg-red-500/10 text-red-300 border-red-500/30',
};

export default function AIPanel({ processId, processDemandType, processDescription }: AIPanelProps) {
  const queryClient = useQueryClient();
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  const [classifyResult, setClassifyResult] = useState<ClassifyResult | null>(null);

  // Status da IA
  const { data: aiStatus } = useQuery<AIStatus>({
    queryKey: ['ai-status'],
    queryFn: () => api.get('/ai/status').then(r => r.data),
    staleTime: 60_000,
  });

  // Jobs do processo
  const { data: jobs = [], isLoading: jobsLoading } = useQuery<AIJob[]>({
    queryKey: ['ai-jobs', processId],
    queryFn: () =>
      api.get('/ai/jobs', {
        params: { entity_type: 'process', entity_id: processId },
      }).then(r => r.data),
    refetchInterval: (data) => {
      const hasRunning = (data as AIJob[] | undefined)?.some(j => j.status === 'running' || j.status === 'pending');
      return hasRunning ? 3000 : false;
    },
  });

  // Classificação síncrona
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

  // Classificação assíncrona (Celery)
  const classifyAsyncMutation = useMutation({
    mutationFn: () =>
      api.post('/ai/jobs/classify-async', { process_id: processId }).then(r => r.data),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['ai-jobs', processId] }), 2000);
    },
  });

  const isConfigured = aiStatus?.ai_configured ?? false;

  return (
    <div className="space-y-6">

      {/* Status da IA */}
      <div className="bg-white/5 rounded-xl p-5 border border-white/10">
        <div className="flex items-center gap-3 mb-4">
          <Brain className="w-5 h-5 text-purple-400" />
          <h3 className="text-white font-semibold">Inteligência Artificial</h3>
          <span className={`ml-auto text-xs px-2 py-1 rounded-full border ${
            isConfigured
              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
              : 'bg-slate-500/10 text-slate-400 border-slate-500/30'
          }`}>
            {isConfigured ? '● Configurada' : '○ Não configurada'}
          </span>
        </div>

        {isConfigured ? (
          <div className="text-sm text-slate-400 space-y-1">
            <p>Modelo padrão: <span className="text-white">{aiStatus?.default_model}</span></p>
            <p>Providers: <span className="text-white">{aiStatus?.providers_available.join(', ')}</span></p>
          </div>
        ) : (
          <p className="text-sm text-slate-400">
            Configure <code className="text-purple-300">AI_ENABLED=true</code> e ao menos uma chave de API
            (<code className="text-purple-300">OPENAI_API_KEY</code>, <code className="text-purple-300">GEMINI_API_KEY</code>
            ou <code className="text-purple-300">ANTHROPIC_API_KEY</code>) para habilitar.
          </p>
        )}
      </div>

      {/* Ações de IA */}
      <div className="bg-white/5 rounded-xl p-5 border border-white/10">
        <h4 className="text-white font-medium mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4 text-yellow-400" />
          Ações
        </h4>

        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => classifyMutation.mutate()}
            disabled={!isConfigured || classifyMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm rounded-lg transition-colors"
          >
            {classifyMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Brain className="w-4 h-4" />}
            Classificar Demanda (IA)
          </button>

          <button
            onClick={() => classifyAsyncMutation.mutate()}
            disabled={!isConfigured || classifyAsyncMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm rounded-lg transition-colors"
          >
            {classifyAsyncMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <RefreshCw className="w-4 h-4" />}
            Reclassificar (background)
          </button>
        </div>

        {classifyMutation.isError && (
          <div className="mt-3 flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            Erro na classificação. Verifique se a IA está configurada.
          </div>
        )}

        {classifyAsyncMutation.isSuccess && (
          <p className="mt-3 text-sm text-emerald-400">
            Task enfileirada — o resultado aparecerá no histórico em instantes.
          </p>
        )}
      </div>

      {/* Resultado da classificação */}
      {classifyResult && (
        <div className="bg-purple-500/10 rounded-xl p-5 border border-purple-500/20">
          <div className="flex items-start justify-between mb-3">
            <h4 className="text-white font-medium">Resultado da Classificação</h4>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded border ${CONFIDENCE_CLS[classifyResult.confidence] ?? ''}`}>
                Confiança {classifyResult.confidence}
              </span>
              {classifyResult.llm_used && (
                <span className="text-xs px-2 py-0.5 rounded border bg-purple-500/10 text-purple-300 border-purple-500/30">
                  via LLM
                </span>
              )}
            </div>
          </div>

          <p className="text-sm font-semibold text-purple-200 mb-2">
            {classifyResult.demand_label}
          </p>
          <p className="text-sm text-slate-300 mb-4 leading-relaxed">
            {classifyResult.initial_diagnosis}
          </p>

          {classifyResult.suggested_next_steps.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Próximos Passos</p>
              <ul className="space-y-1">
                {classifyResult.suggested_next_steps.map((step, i) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <span className="text-purple-400 mt-0.5">›</span>
                    {step}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {classifyResult.relevant_agencies.length > 0 && (
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-slate-400 mr-1">Órgãos:</span>
              {classifyResult.relevant_agencies.map(agency => (
                <span key={agency} className="text-xs px-2 py-0.5 bg-white/5 text-slate-300 rounded border border-white/10">
                  {agency}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Histórico de Jobs */}
      <div className="bg-white/5 rounded-xl p-5 border border-white/10">
        <h4 className="text-white font-medium mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4 text-slate-400" />
          Histórico de Jobs IA
          {jobsLoading && <Loader2 className="w-3 h-3 animate-spin text-slate-400 ml-1" />}
        </h4>

        {jobs.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhum job de IA registrado para este processo.</p>
        ) : (
          <div className="space-y-2">
            {jobs.map(job => (
              <div key={job.id} className="border border-white/10 rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedJob(expandedJob === job.id ? null : job.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors text-left"
                >
                  {STATUS_ICON[job.status] ?? <AlertCircle className="w-4 h-4 text-slate-400" />}
                  <span className="text-sm text-white flex-1">
                    {JOB_TYPE_LABEL[job.job_type] ?? job.job_type}
                  </span>
                  {job.model_used && (
                    <span className="text-xs text-slate-500 hidden sm:block">{job.model_used}</span>
                  )}
                  {job.cost_usd != null && (
                    <span className="text-xs text-slate-400">
                      ${job.cost_usd.toFixed(5)}
                    </span>
                  )}
                  <span className="text-xs text-slate-500">
                    {new Date(job.created_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                  {expandedJob === job.id
                    ? <ChevronDown className="w-4 h-4 text-slate-400" />
                    : <ChevronRight className="w-4 h-4 text-slate-400" />}
                </button>

                {expandedJob === job.id && (
                  <div className="px-4 pb-4 border-t border-white/10 pt-3 space-y-2 bg-black/10">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
                      <span className="text-slate-400">Status</span>
                      <span className="text-white capitalize">{job.status}</span>
                      {job.tokens_in != null && <>
                        <span className="text-slate-400">Tokens entrada</span>
                        <span className="text-white">{job.tokens_in}</span>
                      </>}
                      {job.tokens_out != null && <>
                        <span className="text-slate-400">Tokens saída</span>
                        <span className="text-white">{job.tokens_out}</span>
                      </>}
                      {job.duration_ms != null && <>
                        <span className="text-slate-400">Duração</span>
                        <span className="text-white">{job.duration_ms}ms</span>
                      </>}
                      {job.provider && <>
                        <span className="text-slate-400">Provider</span>
                        <span className="text-white">{job.provider}</span>
                      </>}
                    </div>

                    {job.result && (
                      <div className="mt-2">
                        <p className="text-xs text-slate-400 mb-1">Resultado</p>
                        <pre className="text-xs text-slate-300 bg-black/20 rounded p-2 overflow-x-auto max-h-40">
                          {JSON.stringify(job.result, null, 2)}
                        </pre>
                      </div>
                    )}

                    {job.error && (
                      <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">
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
