import { useNavigate } from 'react-router-dom';
import { Stethoscope } from 'lucide-react';
import { Process } from './ProcessDetailTypes';

interface DiagnosisTabProps {
  process: Process;
}

export default function DiagnosisTab({ process }: DiagnosisTabProps) {
  const navigate = useNavigate();

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
