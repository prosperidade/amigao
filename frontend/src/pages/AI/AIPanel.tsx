/**
 * AIPanel — Painel de Agentes IA
 *
 * Aba "IA" no detalhe do processo.
 * Permite rodar agentes individuais, chains, e visualizar historico de execucoes.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  Zap, Clock, CheckCircle2, XCircle, AlertCircle,
  ChevronDown, ChevronRight, Loader2, Link2, Eye,
  Bot, Workflow,
} from 'lucide-react';
import type {
  AgentInfo, AgentRunResponse, AIJob, ChainRunResponse,
} from '@/types/agent';
import { AGENT_LABELS, CHAIN_LABELS, CONFIDENCE_STYLES } from '@/types/agent';
import AgentResultRenderer from '@/components/AgentResultRenderer';

interface AIPanelProps {
  processId: number;
  processDemandType?: string | null;
  processDescription?: string;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending:   <Clock className="w-4 h-4 text-yellow-500 dark:text-yellow-400" />,
  running:   <Loader2 className="w-4 h-4 text-blue-500 dark:text-blue-400 animate-spin" />,
  completed: <CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />,
  failed:    <XCircle className="w-4 h-4 text-red-500 dark:text-red-400" />,
};

const JOB_TYPE_LABEL: Record<string, string> = {
  classify_demand: 'Classificacao de Demanda',
  extract_document: 'Extracao de Documento',
  generate_proposal: 'Geracao de Proposta',
  generate_dossier_summary: 'Resumo de Dossie',
  diagnostico_propriedade: 'Diagnostico Ambiental',
  consulta_regulatoria: 'Consulta Regulatoria',
  gerar_documento: 'Geracao de Documento',
  analise_financeira: 'Analise Financeira',
  acompanhamento_processo: 'Acompanhamento',
  monitoramento_vigia: 'Monitoramento',
  gerar_conteudo_marketing: 'Conteudo Marketing',
};

export default function AIPanel({ processId, processDemandType, processDescription }: AIPanelProps) {
  const queryClient = useQueryClient();
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [selectedChain, setSelectedChain] = useState('');

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
    queryKey: ['ai-jobs', processId],
    queryFn: () =>
      api.get('/ai/jobs', {
        params: { entity_type: 'process', entity_id: processId },
      }).then(r => r.data),
    refetchInterval: (query) => {
      const d = query?.state?.data as AIJob[] | undefined;
      const hasRunning = Array.isArray(d) && d.some(j => j.status === 'running' || j.status === 'pending');
      return hasRunning ? 3000 : false;
    },
  });

  // --- Mutations ---

  const runAgentMutation = useMutation<AgentRunResponse>({
    mutationFn: () =>
      api.post('/agents/run-async', {
        agent_name: selectedAgent,
        process_id: processId,
        metadata: {
          description: processDescription || '',
          demand_type: processDemandType,
        },
      }).then(r => r.data),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['ai-jobs', processId] }), 2000);
    },
  });

  const runChainMutation = useMutation<ChainRunResponse>({
    mutationFn: () =>
      api.post('/agents/chain-async', {
        chain_name: selectedChain,
        process_id: processId,
        metadata: {},
        stop_on_review: true,
      }).then(r => r.data),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['ai-jobs', processId] }), 2000);
    },
  });

  const chainNames = Object.keys(chains);

  return (
    <div className="space-y-5">

      {/* Rodar Agente */}
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <h4 className="text-base font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Bot className="w-4 h-4 text-purple-500 dark:text-purple-400" />
          Rodar Agente Individual
        </h4>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-gray-500 dark:text-slate-400 mb-1 block">Agente</label>
            <select
              value={selectedAgent}
              onChange={e => setSelectedAgent(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-gray-800 dark:text-white"
            >
              <option value="">Selecione um agente...</option>
              {agents.map(a => (
                <option key={a.name} value={a.name}>
                  {AGENT_LABELS[a.name] ?? a.name}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => runAgentMutation.mutate()}
            disabled={!selectedAgent || runAgentMutation.isPending}
            className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors"
          >
            {runAgentMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Zap className="w-4 h-4" />}
            Executar
          </button>
        </div>
        {runAgentMutation.isSuccess && (
          <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">
            Task enfileirada — o resultado aparecera no historico em instantes.
          </p>
        )}
        {runAgentMutation.isError && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" /> Erro ao executar agente.
          </p>
        )}
      </div>

      {/* Rodar Chain */}
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <h4 className="text-base font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Workflow className="w-4 h-4 text-blue-500 dark:text-blue-400" />
          Rodar Chain de Agentes
        </h4>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-gray-500 dark:text-slate-400 mb-1 block">Chain</label>
            <select
              value={selectedChain}
              onChange={e => setSelectedChain(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-gray-800 dark:text-white"
            >
              <option value="">Selecione uma chain...</option>
              {chainNames.map(c => (
                <option key={c} value={c}>
                  {CHAIN_LABELS[c] ?? c} ({(chains[c] ?? []).join(' → ')})
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => runChainMutation.mutate()}
            disabled={!selectedChain || runChainMutation.isPending}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors"
          >
            {runChainMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Link2 className="w-4 h-4" />}
            Executar Chain
          </button>
        </div>
        {runChainMutation.isSuccess && (
          <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">
            Chain enfileirada — os agentes serao executados em sequencia.
          </p>
        )}
        {runChainMutation.isError && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" /> Erro ao executar chain.
          </p>
        )}
      </div>

      {/* Historico de Jobs */}
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <h4 className="text-base font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4 text-gray-400 dark:text-slate-400" />
          Historico de Execucoes IA
          {jobsLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400 ml-1" />}
        </h4>

        {jobs.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-slate-500">Nenhuma execucao de IA registrada para este processo.</p>
        ) : (
          <div className="space-y-2">
            {jobs.map(job => (
              <div key={job.id} className="border border-gray-100 dark:border-white/10 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedJob(expandedJob === job.id ? null : job.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-left"
                >
                  {STATUS_ICON[job.status] ?? <AlertCircle className="w-4 h-4 text-gray-400" />}
                  <span className="text-sm font-medium text-gray-800 dark:text-white flex-1">
                    {job.agent_name
                      ? (AGENT_LABELS[job.agent_name] ?? job.agent_name)
                      : (JOB_TYPE_LABEL[job.job_type] ?? job.job_type)}
                  </span>
                  {typeof job.result?.confidence === 'string' && (
                    <span className={`text-xs px-2 py-0.5 rounded border ${CONFIDENCE_STYLES[job.result.confidence] ?? ''}`}>
                      {job.result.confidence}
                    </span>
                  )}
                  {Boolean(job.result?.requires_review) && (
                    <span className="text-xs px-2 py-0.5 rounded border bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30 flex items-center gap-1">
                      <Eye className="w-3 h-3" /> Revisao
                    </span>
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
                    ? <ChevronDown className="w-4 h-4 text-gray-400" />
                    : <ChevronRight className="w-4 h-4 text-gray-400" />}
                </button>

                {expandedJob === job.id && (
                  <div className="px-4 pb-4 border-t border-gray-100 dark:border-white/10 pt-3 space-y-2 bg-gray-50 dark:bg-black/10">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
                      <span className="text-gray-500 dark:text-slate-400">Status</span>
                      <span className="text-gray-800 dark:text-white capitalize font-medium">{job.status}</span>
                      {job.agent_name && <>
                        <span className="text-gray-500 dark:text-slate-400">Agente</span>
                        <span className="text-gray-800 dark:text-white">{AGENT_LABELS[job.agent_name] ?? job.agent_name}</span>
                      </>}
                      {job.model_used && <>
                        <span className="text-gray-500 dark:text-slate-400">Modelo</span>
                        <span className="text-gray-800 dark:text-white">{job.model_used}</span>
                      </>}
                      {job.tokens_in != null && <>
                        <span className="text-gray-500 dark:text-slate-400">Tokens entrada</span>
                        <span className="text-gray-800 dark:text-white">{job.tokens_in.toLocaleString()}</span>
                      </>}
                      {job.tokens_out != null && <>
                        <span className="text-gray-500 dark:text-slate-400">Tokens saida</span>
                        <span className="text-gray-800 dark:text-white">{job.tokens_out.toLocaleString()}</span>
                      </>}
                      {job.duration_ms != null && <>
                        <span className="text-gray-500 dark:text-slate-400">Duracao</span>
                        <span className="text-gray-800 dark:text-white">{(job.duration_ms / 1000).toFixed(1)}s</span>
                      </>}
                      {job.provider && <>
                        <span className="text-gray-500 dark:text-slate-400">Provider</span>
                        <span className="text-gray-800 dark:text-white">{job.provider}</span>
                      </>}
                    </div>

                    {job.result && (
                      <AgentResultRenderer agentName={job.agent_name} result={job.result} />
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
