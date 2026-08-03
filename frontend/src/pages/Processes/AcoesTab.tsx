/**
 * AcoesTab — aba "Ações" do workspace do caso (Ficha 07).
 *
 * Onde o diagnóstico vira trabalho. Lista as ações DESTE caso, filtráveis por
 * status e triagem. Botão "Gerar do diagnóstico" cria ações pendentes (com
 * fonte #70) a partir dos passivos. Criação manual também. Concluir uma ação
 * NÃO resolve o passivo (ADR-016) — é só "trabalho interno feito".
 */
import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { Eye, EyeOff, ListChecks, Plus, Sparkles, Loader2 } from 'lucide-react';
import { useAcoes, useCreateAcao, useGenerateAcoes } from '@/lib/acoes/hooks';
import {
  ACAO_STATUS_LABELS,
  ACAO_TRIAGEM_LABELS,
  type AcaoStatus,
  type AcaoTipoTriagem,
} from '@/lib/acoes/types';
import { MACROETAPA_LABELS } from './quadro-types';
import AcaoCard from './AcaoCard';
import RotaTab from './RotaTab';

interface AcoesTabProps {
  processId: number;
  /** Macroetapa que o consultor está visualizando. Na E5 (`caminho_regulatorio`)
   *  a aba Ações vira a Rota Regulatória (Ficha §8.1 — não é 7ª aba). */
  currentStage?: string;
}

type StatusFilter = AcaoStatus | 'all';
type TriagemFilter = AcaoTipoTriagem | 'all';

export default function AcoesTab({ processId, currentStage }: AcoesTabProps) {
  // Ficha §8.1: na etapa E5, a aba Ações renderiza a Rota. Fora da E5, segue normal.
  if (currentStage === 'caminho_regulatorio') {
    return <RotaTab processId={processId} />;
  }
  return <AcoesList processId={processId} />;
}

function AcoesList({ processId }: { processId: number }) {
  const { data: acoes, isLoading } = useAcoes(processId);
  const generateMut = useGenerateAcoes(processId);
  const createMut = useCreateAcao(processId);

  const [newTitle, setNewTitle] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [triagemFilter, setTriagemFilter] = useState<TriagemFilter>('all');
  // Item 3 — dispensadas somem da visão default (nada é excluído; auditável via toggle).
  const [showDispensadas, setShowDispensadas] = useState(false);

  const filtered = useMemo(() => {
    const list = acoes ?? [];
    return list.filter(a => {
      const isDispensada = a.tipo_triagem === 'dispensada';
      // Dispensada fica oculta por padrão. Exceção: o consultor pediu explicitamente
      // (toggle ligado, ou filtro de triagem apontando para "dispensada").
      if (isDispensada && !showDispensadas && triagemFilter !== 'dispensada') return false;
      if (statusFilter !== 'all' && a.status !== statusFilter) return false;
      if (triagemFilter !== 'all' && a.tipo_triagem !== triagemFilter) return false;
      return true;
    });
  }, [acoes, statusFilter, triagemFilter, showDispensadas]);

  // Validação 02/08 — as Fichas descrevem as ações de cada etapa registradas e
  // visíveis conforme o caso avança. A lista era plana: dava para filtrar, não
  // para LER o caso como sequência de trabalho. Agrupa na ordem do fluxo; as
  // ações sem carimbo (anteriores à coluna) vão para o fim, nomeadas — não se
  // inventa a etapa de quem nasceu antes do registro existir.
  const grupos = useMemo(() => {
    const porEtapa = new Map<string, typeof filtered>();
    for (const acao of filtered) {
      const chave = acao.macroetapa ?? '__sem_etapa__';
      const atual = porEtapa.get(chave) ?? [];
      atual.push(acao);
      porEtapa.set(chave, atual);
    }
    const ordem = Object.keys(MACROETAPA_LABELS);
    return [...porEtapa.entries()]
      .sort(([a], [b]) => {
        const ia = a === '__sem_etapa__' ? ordem.length : ordem.indexOf(a);
        const ib = b === '__sem_etapa__' ? ordem.length : ordem.indexOf(b);
        return ia - ib;
      })
      .map(([chave, itens]) => ({
        chave,
        label: chave === '__sem_etapa__'
          ? 'Etapa não registrada'
          : MACROETAPA_LABELS[chave] ?? chave,
        itens,
        concluidas: itens.filter(a => a.status === 'concluida').length,
      }));
  }, [filtered]);

  const pendentesCount = (acoes ?? []).filter(a => a.tipo_triagem === 'pendente').length;
  const dispensadasCount = (acoes ?? []).filter(a => a.tipo_triagem === 'dispensada').length;

  const handleGenerate = () => {
    generateMut.mutate(undefined, {
      onSuccess: data => {
        if (data.diagnosis_version === null) {
          toast('Sem diagnóstico ainda — gere o diagnóstico primeiro.', { icon: 'ℹ️' });
        } else if (data.created === 0) {
          toast('Nenhuma ação nova — todas já foram geradas.', { icon: '✓' });
        } else {
          toast.success(`${data.created} ação(ões) gerada(s) do diagnóstico v${data.diagnosis_version}.`);
        }
      },
      onError: () => toast.error('Falha ao gerar ações do diagnóstico.'),
    });
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    createMut.mutate(
      { titulo: newTitle.trim() },
      {
        onSuccess: () => { setNewTitle(''); toast.success('Ação criada.'); },
        onError: () => toast.error('Falha ao criar ação.'),
      },
    );
  };

  return (
    <div className="space-y-5">
      {/* Cabeçalho + gerar do diagnóstico */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 uppercase tracking-wider">
            Ações do caso
          </h2>
          <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
            {`Cada pendência do diagnóstico vira uma ação a triar. A IA propõe; você decide.`}
            {pendentesCount > 0 && (
              <span className="ml-1 text-amber-600 dark:text-amber-400 font-medium">
                {pendentesCount} pendente(s) de triagem.
              </span>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={generateMut.isPending}
          className="shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
        >
          {generateMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Gerar do diagnóstico
        </button>
      </div>

      {/* Criação manual */}
      <form onSubmit={handleCreate} className="flex gap-2">
        <input
          type="text"
          placeholder="Criar ação manualmente (tarefa do zero)…"
          value={newTitle}
          onChange={e => setNewTitle(e.target.value)}
          className="flex-1 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <button
          type="submit"
          disabled={createMut.isPending || !newTitle.trim()}
          className="px-4 py-2.5 rounded-xl bg-gray-800 dark:bg-white/10 hover:bg-gray-700 dark:hover:bg-white/20 disabled:opacity-40 text-white font-medium text-sm transition-colors flex items-center gap-1.5 shrink-0"
        >
          <Plus className="w-4 h-4" /> Adicionar
        </button>
      </form>

      {/* Filtros */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as StatusFilter)}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 dark:text-slate-200"
        >
          <option value="all">Status (todos)</option>
          {(Object.keys(ACAO_STATUS_LABELS) as AcaoStatus[]).map(s => (
            <option key={s} value={s}>{ACAO_STATUS_LABELS[s]}</option>
          ))}
        </select>
        <select
          value={triagemFilter}
          onChange={e => setTriagemFilter(e.target.value as TriagemFilter)}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 dark:text-slate-200"
        >
          <option value="all">Triagem (todas)</option>
          {(Object.keys(ACAO_TRIAGEM_LABELS) as AcaoTipoTriagem[]).map(t => (
            <option key={t} value={t}>{ACAO_TRIAGEM_LABELS[t]}</option>
          ))}
        </select>
        {/* Item 3 — mostrar/ocultar dispensadas (auditoria; nada é excluído) */}
        {dispensadasCount > 0 && triagemFilter !== 'dispensada' && (
          <button
            type="button"
            onClick={() => setShowDispensadas(v => !v)}
            aria-pressed={showDispensadas}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-colors ${
              showDispensadas
                ? 'border-gray-300 dark:border-white/20 bg-gray-100 dark:bg-white/10 text-gray-700 dark:text-slate-200'
                : 'border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-200'
            }`}
          >
            {showDispensadas ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            {showDispensadas ? 'Ocultar dispensadas' : 'Mostrar dispensadas'} ({dispensadasCount})
          </button>
        )}
      </div>

      {/* Lista */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400 p-4">
          <Loader2 className="w-4 h-4 animate-spin" /> Carregando ações…
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400 dark:text-slate-500 text-sm">
          <ListChecks className="w-8 h-8 mx-auto mb-2 text-gray-300 dark:text-slate-600" />
          {(acoes ?? []).length === 0
            ? 'Nenhuma ação ainda. Gere a partir do diagnóstico ou crie manualmente.'
            : 'Nenhuma ação para os filtros selecionados.'}
        </div>
      ) : (
        <div className="space-y-6">
          {grupos.map(grupo => (
            <section key={grupo.chave}>
              <div className="flex items-baseline gap-2 mb-2 px-1">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-400">
                  {grupo.label}
                </h4>
                <span className="text-[11px] text-gray-400 dark:text-slate-500">
                  {grupo.itens.length} ação(ões)
                  {grupo.concluidas > 0 && ` · ${grupo.concluidas} concluída(s)`}
                </span>
              </div>
              <div className="space-y-3">
                {grupo.itens.map(acao => (
                  <AcaoCard key={acao.id} acao={acao} processId={processId} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
