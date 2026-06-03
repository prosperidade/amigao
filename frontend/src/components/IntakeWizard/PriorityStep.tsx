/**
 * PriorityStep — dois eixos INDEPENDENTES de prioridade (decisão Isis 2026-05-28).
 *
 * Urgência (4 níveis) e Valor Estratégico (3 níveis) são eixos separados —
 * NÃO se combinam num único índice. As opções vivem em ./priorityOptions
 * (constantes fora do arquivo de componente — exigência do Fast Refresh).
 */

import { URGENCIA_OPTIONS, VALOR_ESTRATEGICO_OPTIONS } from './priorityOptions';

interface Props {
  urgencia: string;
  valorEstrategico: string;
  observacoes: string;
  onChangeUrgencia: (v: string) => void;
  onChangeValorEstrategico: (v: string) => void;
  onChangeObservacoes: (v: string) => void;
}

export default function PriorityStep({
  urgencia,
  valorEstrategico,
  observacoes,
  onChangeUrgencia,
  onChangeValorEstrategico,
  onChangeObservacoes,
}: Props) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Urgência</label>
          <select
            value={urgencia}
            onChange={e => onChangeUrgencia(e.target.value)}
            className="w-full rounded-xl bg-background border border-input text-foreground px-4 py-3 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-ring transition-colors"
          >
            {URGENCIA_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Valor Estratégico
          </label>
          <select
            value={valorEstrategico}
            onChange={e => onChangeValorEstrategico(e.target.value)}
            className="w-full rounded-xl bg-background border border-input text-foreground px-4 py-3 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-ring transition-colors"
          >
            {VALOR_ESTRATEGICO_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Os dois eixos são independentes — um caso pode ser urgentíssimo e de baixo valor estratégico,
        ou o inverso.
      </p>

      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Observações da triagem <span className="text-muted-foreground font-normal">(opcional)</span>
        </label>
        <textarea
          rows={2}
          value={observacoes}
          onChange={e => onChangeObservacoes(e.target.value)}
          placeholder="Contexto da priorização (prazo específico, relação com o cliente, etc.)"
          className="w-full rounded-xl bg-background border border-input text-foreground placeholder:text-muted-foreground px-4 py-3 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-ring resize-none"
        />
      </div>
    </div>
  );
}
