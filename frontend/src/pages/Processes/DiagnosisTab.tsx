import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Stethoscope, Brain, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { Process } from './ProcessDetailTypes';
import type { AIJob } from '@/types/agent';
import { CONFIDENCE_STYLES } from '@/types/agent';

interface DiagnosisTabProps {
  process: Process;
}

export default function DiagnosisTab({ process }: DiagnosisTabProps) {
  const navigate = useNavigate();

  // Buscar ultimo job do agente diagnostico para este processo
  const { data: jobs = [] } = useQuery<AIJob[]>({
    queryKey: ['ai-jobs', process.id],
    queryFn: () =>
      api.get('/ai/jobs', {
        params: { entity_type: 'process', entity_id: process.id },
      }).then(r => r.data),
  });

  const diagJob = jobs.find(j => j.agent_name === 'diagnostico' && j.status === 'completed');
  const diagResult = diagJob?.result as Record<string, unknown> | undefined;
  const diagRunning = jobs.some(j => j.agent_name === 'diagnostico' && (j.status === 'running' || j.status === 'pending'));

  return (
    <div className="space-y-4">

      {process.initial_diagnosis ? (
        <div className="rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-500/5 dark:to-teal-500/5 border border-emerald-100 dark:border-emerald-500/20 p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center">
              <Stethoscope className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h2 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider">
              {`Diagn\u00f3stico Inicial \u2014 autom\u00e1tico`}
            </h2>
          </div>
          <p className="text-gray-700 dark:text-slate-200 leading-relaxed whitespace-pre-wrap text-sm">
            {process.initial_diagnosis}
          </p>
        </div>
      ) : (
        <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-8 text-center">
          <Stethoscope className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
          <p className="text-gray-500 dark:text-slate-400 text-sm">{`Nenhum diagn\u00f3stico gerado ainda.`}</p>
          <p className="text-gray-400 dark:text-slate-500 text-xs mt-1">
            Use o{' '}
            <button onClick={() => navigate('/intake')} className="text-emerald-600 dark:text-emerald-400 underline">
              Intake Wizard
            </button>{' '}
            {`para gerar um diagn\u00f3stico autom\u00e1tico.`}
          </p>
        </div>
      )}

      {/* Resultado do Agente Diagnostico (IA) */}
      {diagRunning && (
        <div className="rounded-xl bg-blue-50 dark:bg-blue-500/5 border border-blue-200 dark:border-blue-500/20 p-5 flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
          <p className="text-sm text-blue-700 dark:text-blue-300">Agente de diagnostico em execucao...</p>
        </div>
      )}

      {diagResult && (
        <div className="rounded-xl bg-purple-50 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/20 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-600 dark:text-purple-400" />
              <h2 className="text-sm font-semibold text-purple-800 dark:text-purple-300 uppercase tracking-wider">
                Diagnostico IA
              </h2>
            </div>
            {typeof diagResult.confidence === 'string' && (
              <span className={`text-xs px-2 py-0.5 rounded border ${CONFIDENCE_STYLES[diagResult.confidence] ?? ''}`}>
                Confianca {diagResult.confidence}
              </span>
            )}
          </div>

          {typeof diagResult.situacao_geral === 'string' && (
            <p className="text-sm text-gray-700 dark:text-slate-200 mb-3 leading-relaxed">
              {diagResult.situacao_geral}
            </p>
          )}

          {Array.isArray(diagResult.passivos_identificados) && (diagResult.passivos_identificados as string[]).length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Passivos Identificados
              </p>
              <ul className="space-y-1">
                {(diagResult.passivos_identificados as string[]).map((p, i) => (
                  <li key={i} className="text-sm text-gray-700 dark:text-slate-300 flex items-start gap-2">
                    <span className="text-red-400 mt-0.5">&#x2022;</span> {String(p)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(diagResult.acoes_remediacao) && (diagResult.acoes_remediacao as string[]).length > 0 && (
            <div>
              <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Acoes de Remediacao
              </p>
              <ul className="space-y-1">
                {(diagResult.acoes_remediacao as string[]).map((a, i) => (
                  <li key={i} className="text-sm text-gray-700 dark:text-slate-300 flex items-start gap-2">
                    <span className="text-emerald-400 mt-0.5">&#x203A;</span> {String(a)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {process.description && (
        <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
          <h2 className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider mb-3">{`Descri\u00e7\u00e3o da Demanda`}</h2>
          <p className="text-gray-700 dark:text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{process.description}</p>
        </div>
      )}

      {process.intake_notes && (
        <div className="rounded-xl bg-amber-50 dark:bg-amber-500/5 border border-amber-200 dark:border-amber-500/20 p-5">
          <h2 className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider mb-3">{`\ud83d\udcdd Notas do Intake`}</h2>
          <p className="text-gray-700 dark:text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{process.intake_notes}</p>
        </div>
      )}

      {/* Metadata grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[
          { label: 'ID do Processo',       value: `#${process.id}` },
          { label: 'Tipo do Processo',     value: process.process_type ?? '\u2014' },
          { label: 'Tipo de Demanda',      value: process.demand_type ?? '\u2014' },
          { label: 'Canal de Entrada',     value: process.intake_source ?? '\u2014' },
          { label: 'Prioridade',           value: process.priority ?? '\u2014' },
          { label: 'Template Checklist',   value: process.suggested_checklist_template ?? '\u2014' },
        ].map(m => (
          <div key={m.label} className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-4">
            <p className="text-xs text-gray-400 dark:text-slate-500 mb-1">{m.label}</p>
            <p className="text-sm font-semibold text-gray-800 dark:text-white">{m.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
