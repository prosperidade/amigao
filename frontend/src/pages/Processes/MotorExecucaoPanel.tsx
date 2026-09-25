/**
 * MotorExecucaoPanel — relatório da última execução do motor jurídico (ADR-073, dívida #278).
 *
 * O que a tela precisa dizer, sem resumir por cima: quantas regras foram avaliadas
 * e em que estado ficaram; as indeterminadas com os fatos que faltaram; o
 * fundamento de cada regra por ID (clicável) ou a razão de não ter; e os alertas
 * críticos, cada um com a ciência registrada ou o formulário para registrá-la —
 * a Rota não fecha com alerta crítico sem ciência.
 *
 * "Zero regras disparadas" não é regularidade: sai escrito como é.
 */
import { useState } from 'react';
import toast from 'react-hot-toast';
import { AlertOctagon, ChevronDown, ChevronRight, Loader2, ShieldAlert } from 'lucide-react';
import EvidenciaChip from '@/components/EvidenciaChip';
import { mensagemDeErro } from '@/lib/apiError';
import { useCienciaAlerta, useExecucaoMotor } from '@/lib/comercial/hooks';
import {
  ESTADO_AVALIACAO_LABEL,
  type AvaliacaoLinha,
  type EstadoAvaliacao,
  type ExecucaoRelatorio,
} from '@/lib/comercial/types';

const ORDEM: EstadoAvaliacao[] = [
  'aplicavel_disparou',
  'indeterminado',
  'conflito',
  'erro_execucao',
  'aplicavel_nao_disparou',
  'nao_aplicavel',
];

const ESTADO_CLS: Record<EstadoAvaliacao, string> = {
  aplicavel_disparou: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800',
  indeterminado: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800',
  conflito: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800',
  erro_execucao: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800',
  aplicavel_nao_disparou: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-zinc-800 dark:text-slate-300 dark:border-zinc-700',
  nao_aplicavel: 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-zinc-800 dark:text-slate-400 dark:border-zinc-700',
};

const RAZAO_LABEL: Record<string, string> = {
  fonte_ausente: 'norma fora do catálogo normativo',
  versao_nao_elegivel: 'norma sem versão elegível para citação',
  dispositivo_ausente: 'artigo não encontrado na norma do catálogo',
  sem_fundamento_declarado: 'regra sem fundamento declarado',
};

function emiteAlertaCritico(a: AvaliacaoLinha) {
  return a.estado === 'aplicavel_disparou' && a.efeitos.some(e => e.tipo === 'alerta_critico');
}

function CienciaForm({ processId, avaliacao }: { processId: number; avaliacao: AvaliacaoLinha }) {
  const [justificativa, setJustificativa] = useState('');
  const mut = useCienciaAlerta(processId);
  const registrar = (e: React.FormEvent) => {
    e.preventDefault();
    if (!justificativa.trim()) return;
    mut.mutate(
      { avaliacaoId: avaliacao.avaliacao_id, justificativa: justificativa.trim() },
      {
        onSuccess: () => toast.success(`Ciência do alerta ${avaliacao.rule_id} registrada.`),
        onError: err => toast.error(mensagemDeErro(err, 'Falha ao registrar a ciência.')),
      },
    );
  };
  return (
    <form onSubmit={registrar} className="mt-2 space-y-1.5">
      <label className="block text-[11px] text-red-800 dark:text-red-300" htmlFor={`ciencia-${avaliacao.avaliacao_id}`}>
        Ciência do alerta crítico — justificativa (obrigatória)
      </label>
      <textarea
        id={`ciencia-${avaliacao.avaliacao_id}`}
        value={justificativa}
        onChange={e => setJustificativa(e.target.value)}
        rows={2}
        placeholder="Ex.: cliente informado em reunião; a sucessão será tratada antes do protocolo."
        className="w-full rounded-lg bg-white dark:bg-white/5 border border-red-200 dark:border-red-500/30 text-gray-900 dark:text-white px-2 py-1.5 text-xs focus:outline-none focus:border-red-500"
      />
      <button
        type="submit"
        disabled={!justificativa.trim() || mut.isPending}
        className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white"
      >
        {mut.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Registrar ciência
      </button>
    </form>
  );
}

function LinhaAvaliacao({ processId, a }: { processId: number; a: AvaliacaoLinha }) {
  const alerta = emiteAlertaCritico(a);
  return (
    <li
      data-testid={`avaliacao-${a.rule_id}`}
      className={`rounded-lg border p-3 ${
        a.alerta_critico_sem_ciencia
          ? 'border-red-300 bg-red-50 dark:border-red-500/40 dark:bg-red-500/10'
          : 'border-gray-200 dark:border-white/10'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-mono font-semibold text-gray-800 dark:text-slate-100">{a.rule_id}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${ESTADO_CLS[a.estado]}`}>
          {ESTADO_AVALIACAO_LABEL[a.estado] ?? a.estado}
        </span>
        {alerta && (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800">
            <AlertOctagon className="w-3 h-3" />
            {a.alerta_critico_sem_ciencia ? 'alerta crítico sem ciência' : 'alerta crítico — ciência registrada'}
          </span>
        )}
        <EvidenciaChip processId={processId} evidencia={{ tipo: 'avaliacao_regra', id: a.avaliacao_id, rotulo: `avaliação #${a.avaliacao_id}` }} />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-gray-600 dark:text-slate-400">
        <span>Fundamento:</span>
        {a.fundamento.dispositivo_id ? (
          <EvidenciaChip
            processId={processId}
            evidencia={{ tipo: 'dispositivo', id: a.fundamento.dispositivo_id, rotulo: a.fundamento.caminho ?? `dispositivo #${a.fundamento.dispositivo_id}` }}
          />
        ) : (
          <span className="text-amber-700 dark:text-amber-300">
            não resolvido — {RAZAO_LABEL[a.fundamento.razao ?? ''] ?? a.fundamento.razao ?? 'sem razão registrada'}
            {a.fundamento.caminho ? ` (${a.fundamento.caminho})` : ''}
          </span>
        )}
      </div>
      {a.faltantes.length > 0 && (
        <p className="mt-1 text-[11px] text-amber-800 dark:text-amber-300">
          Fatos que faltaram: {a.faltantes.join(', ')}
        </p>
      )}
      {a.efeitos.length > 0 && (
        <p className="mt-1 text-[11px] text-gray-500 dark:text-slate-400">
          Efeitos: {a.efeitos.map(e => e.tipo).join(', ')}
        </p>
      )}
      {a.detalhe_erro && <p className="mt-1 text-[11px] text-red-700 dark:text-red-300">{a.detalhe_erro}</p>}
      {a.alerta_critico_sem_ciencia && <CienciaForm processId={processId} avaliacao={a} />}
    </li>
  );
}

function Relatorio({ processId, ex }: { processId: number; ex: ExecucaoRelatorio }) {
  const [verTodas, setVerTodas] = useState(false);
  const [verFatos, setVerFatos] = useState(false);
  const ordenadas = [...ex.avaliacoes].sort((x, y) => ORDEM.indexOf(x.estado) - ORDEM.indexOf(y.estado));
  const principais = ordenadas.filter(a => a.estado !== 'nao_aplicavel' && a.estado !== 'aplicavel_nao_disparou');
  const demais = ordenadas.filter(a => !principais.includes(a));
  const semCiencia = ex.alertas_sem_ciencia.length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600 dark:text-slate-300">
        <EvidenciaChip processId={processId} evidencia={{ tipo: 'execucao_motor', id: ex.execucao_id, rotulo: `execução #${ex.execucao_id}` }} />
        <span>referência {new Date(ex.data_referencia + 'T00:00:00').toLocaleDateString('pt-BR')}</span>
        <span data-testid="motor-avaliadas">{ex.avaliacoes.length} regra(s) avaliada(s)</span>
        {ORDEM.filter(e => ex.contagem[e]).map(e => (
          <span key={e} className={`text-[10px] px-2 py-0.5 rounded-full border ${ESTADO_CLS[e]}`}>
            {ESTADO_AVALIACAO_LABEL[e]}: {ex.contagem[e]}
          </span>
        ))}
      </div>
      {ex.disparadas === 0 && (
        <p className="text-xs text-amber-800 dark:text-amber-300">
          Nenhuma regra disparou. Isso não é regularidade: confira as indeterminadas e os fatos que faltaram.
        </p>
      )}
      {semCiencia > 0 && (
        <p role="alert" className="text-xs font-medium text-red-700 dark:text-red-300 inline-flex items-center gap-1.5">
          <ShieldAlert className="w-4 h-4" />
          {semCiencia} alerta(s) crítico(s) sem ciência — a Rota não fecha até registrar.
        </p>
      )}
      <ul className="space-y-2">
        {principais.map(a => <LinhaAvaliacao key={a.avaliacao_id} processId={processId} a={a} />)}
      </ul>
      {demais.length > 0 && (
        <div>
          <button type="button" onClick={() => setVerTodas(v => !v)} className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-slate-400 hover:underline">
            {verTodas ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            {demais.length} regra(s) não aplicável(is) ou sem disparo
          </button>
          {verTodas && (
            <ul className="space-y-2 mt-2">
              {demais.map(a => <LinhaAvaliacao key={a.avaliacao_id} processId={processId} a={a} />)}
            </ul>
          )}
        </div>
      )}
      <div>
        <button type="button" onClick={() => setVerFatos(v => !v)} className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-slate-400 hover:underline">
          {verFatos ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          Fatos lidos dos autos ({Object.keys(ex.fatos).length})
        </button>
        {verFatos && (
          <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-[11px]">
            {Object.entries(ex.fatos).sort(([a], [b]) => a.localeCompare(b)).map(([chave, f]) => (
              <div key={chave} className="contents">
                <dt className="font-mono text-gray-500 dark:text-slate-400">{chave}</dt>
                <dd className={f.estado === 'determinado' ? 'text-gray-800 dark:text-slate-200' : 'text-amber-700 dark:text-amber-300'}>
                  {f.estado === 'determinado' ? JSON.stringify(f.valor) : 'não determinado'}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </div>
  );
}

export default function MotorExecucaoPanel({ processId }: { processId: number }) {
  const { data: ex, isLoading, isError } = useExecucaoMotor(processId);
  if (isLoading) return null;
  return (
    <section
      data-testid="motor-relatorio"
      className="rounded-xl border border-gray-200 dark:border-white/10 p-4 space-y-3 bg-white dark:bg-white/5"
    >
      <h3 className="text-xs font-semibold text-gray-700 dark:text-slate-200 uppercase tracking-wider">
        Motor jurídico — última execução
      </h3>
      {isError ? (
        <p className="text-xs text-red-700 dark:text-red-300">Não foi possível ler a execução do motor.</p>
      ) : !ex ? (
        <p className="text-xs text-gray-500 dark:text-slate-400">O motor ainda não avaliou este caso.</p>
      ) : (
        <Relatorio processId={processId} ex={ex} />
      )}
    </section>
  );
}
