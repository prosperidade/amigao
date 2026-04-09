import { Check } from 'lucide-react';
import type { MacroetapaStep } from './quadro-types';

interface Props {
  steps: MacroetapaStep[];
  compact?: boolean;
}

export default function MacroetapaStepper({ steps, compact }: Props) {
  return (
    <div className="space-y-0">
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        return (
          <div key={step.macroetapa} className="flex gap-3">
            {/* Dot + line */}
            <div className="flex flex-col items-center">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                  step.status === 'completed'
                    ? 'bg-emerald-500 text-white'
                    : step.status === 'active'
                      ? 'bg-emerald-100 border-2 border-emerald-500 text-emerald-600 dark:bg-emerald-900/30'
                      : 'bg-gray-100 border border-gray-300 text-gray-400 dark:bg-zinc-800 dark:border-zinc-600'
                }`}
              >
                {step.status === 'completed' ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  <span className="text-xs font-bold">{i + 1}</span>
                )}
              </div>
              {!isLast && (
                <div
                  className={`w-0.5 flex-1 min-h-[16px] ${
                    step.status === 'completed'
                      ? 'bg-emerald-300'
                      : 'bg-gray-200 dark:bg-zinc-700'
                  }`}
                />
              )}
            </div>

            {/* Label */}
            <div className={`pb-3 ${compact ? 'pt-0.5' : 'pt-0'}`}>
              <p
                className={`text-sm font-medium leading-tight ${
                  step.status === 'active'
                    ? 'text-emerald-700 dark:text-emerald-400'
                    : step.status === 'completed'
                      ? 'text-gray-500 dark:text-gray-400'
                      : 'text-gray-400 dark:text-gray-500'
                }`}
              >
                {step.label}
              </p>
              {!compact && step.status === 'active' && step.completion_pct > 0 && (
                <p className="text-xs text-gray-500 mt-0.5">{step.completion_pct.toFixed(0)}% concluído</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
