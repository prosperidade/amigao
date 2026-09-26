/**
 * MetodosPrecos — métodos e preços do tenant (ADR-074 §4, fecha a #282).
 *
 * O orçamento de cada caso nasce destes métodos: um item por passo da Rota, com o
 * método escolhido pelo consultor, o mapeado à regra do motor ou o padrão do tenant.
 * Nada se edita no lugar: salvar gera a VERSÃO seguinte do método, e os orçamentos já
 * gerados guardam a foto de antes e passam a sair desatualizados com o motivo. É a
 * tabela que substitui os preços de código (#284).
 *
 * Espelha `GET/POST /comercial/metodos` (`app/api/v1/comercial.py`).
 */
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { ChevronDown, ChevronRight, Loader2, Pencil, Plus, Power } from 'lucide-react';
import RodapeVersao from '@/components/RodapeVersao';
import { api } from '@/lib/api';
import { mensagemDeErro } from '@/lib/apiError';
import { comercialKeys, useMetodos } from '@/lib/comercial/hooks';
import { reais, type MetodoOrcamento } from '@/lib/comercial/types';

type Unidade = MetodoOrcamento['unidade'];

const UNIDADE_LABEL: Record<Unidade, string> = { hora: 'por hora', fixo: 'valor fixo', unidade: 'por unidade' };

interface Rascunho {
  codigo: string;
  nome: string;
  unidade: Unidade;
  valor_unitario: string;
  quantidade_padrao: string;
  rule_ids: string[];
  padrao: boolean;
  ativo: boolean;
}

const VAZIO: Rascunho = {
  codigo: '', nome: '', unidade: 'hora', valor_unitario: '', quantidade_padrao: '1',
  rule_ids: [], padrao: false, ativo: true,
};

const INPUT =
  'w-full rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 ' +
  'text-gray-900 dark:text-white px-2.5 py-1.5 text-sm focus:outline-none focus:border-emerald-500 disabled:opacity-60';

function deMetodo(m: MetodoOrcamento, mudar: Partial<Rascunho> = {}): Rascunho {
  return {
    codigo: m.codigo, nome: m.nome, unidade: m.unidade, valor_unitario: m.valor_unitario,
    quantidade_padrao: m.quantidade_padrao, rule_ids: m.rule_ids, padrao: m.padrao, ativo: m.ativo, ...mudar,
  };
}

function useSalvarMetodo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (r: Rascunho) =>
      (await api.post('/comercial/metodos', {
        ...r,
        codigo: r.codigo.trim(),
        nome: r.nome.trim(),
        quantidade_padrao: r.unidade === 'fixo' ? '1' : r.quantidade_padrao,
      })).data as MetodoOrcamento,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: comercialKeys.metodos });
      // Orçamentos abertos leem a atualidade de novo: preço novo desatualiza com o motivo.
      qc.invalidateQueries({ queryKey: ['comercial-orcamento'] });
    },
  });
}

function Formulario({
  inicial,
  novo,
  regras,
  onFechar,
}: {
  inicial: Rascunho;
  novo: boolean;
  regras: string[];
  onFechar: () => void;
}) {
  const [r, setR] = useState<Rascunho>(inicial);
  const salvar = useSalvarMetodo();
  const valido = r.codigo.trim() && r.nome.trim() && Number(r.valor_unitario) >= 0 && r.valor_unitario !== ''
    && (r.unidade === 'fixo' || Number(r.quantidade_padrao) > 0);

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valido) return;
    salvar.mutate(r, {
      onSuccess: m => {
        toast.success(`${m.nome}: versão ${m.versao} salva.`);
        onFechar();
      },
      onError: err => toast.error(mensagemDeErro(err, 'Falha ao salvar o método.')),
    });
  };

  return (
    <form onSubmit={enviar} data-testid="form-metodo" className="rounded-xl border border-emerald-200 dark:border-emerald-500/30 p-4 space-y-3">
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-xs text-gray-600 dark:text-slate-300 space-y-1">
          <span>Código</span>
          <input className={INPUT} value={r.codigo} disabled={!novo} onChange={e => setR({ ...r, codigo: e.target.value })}
            placeholder="ex.: georreferenciamento" />
        </label>
        <label className="text-xs text-gray-600 dark:text-slate-300 space-y-1">
          <span>Nome</span>
          <input className={INPUT} value={r.nome} onChange={e => setR({ ...r, nome: e.target.value })} />
        </label>
        <label className="text-xs text-gray-600 dark:text-slate-300 space-y-1">
          <span>Unidade</span>
          <select className={INPUT} value={r.unidade}
            onChange={e => setR({ ...r, unidade: e.target.value as Unidade, quantidade_padrao: e.target.value === 'fixo' ? '1' : r.quantidade_padrao })}>
            {(Object.keys(UNIDADE_LABEL) as Unidade[]).map(u => <option key={u} value={u}>{UNIDADE_LABEL[u]}</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-600 dark:text-slate-300 space-y-1">
          <span>Valor unitário (R$)</span>
          <input className={INPUT} inputMode="decimal" value={r.valor_unitario}
            onChange={e => setR({ ...r, valor_unitario: e.target.value.replace(',', '.') })} />
        </label>
        <label className="text-xs text-gray-600 dark:text-slate-300 space-y-1">
          <span>Quantidade padrão</span>
          <input className={INPUT} inputMode="decimal" value={r.unidade === 'fixo' ? '1' : r.quantidade_padrao}
            disabled={r.unidade === 'fixo'}
            onChange={e => setR({ ...r, quantidade_padrao: e.target.value.replace(',', '.') })} />
        </label>
        <div className="text-xs text-gray-600 dark:text-slate-300 space-y-1.5 pt-5">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={r.padrao} onChange={e => setR({ ...r, padrao: e.target.checked })} />
            Método padrão do tenant (passo sem método próprio)
          </label>
        </div>
      </div>
      {regras.length > 0 && (
        <fieldset className="text-xs text-gray-600 dark:text-slate-300">
          <legend className="mb-1">Regras do motor que usam este método</legend>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {regras.map(rule => (
              <label key={rule} className="flex items-center gap-1.5 font-mono">
                <input type="checkbox" checked={r.rule_ids.includes(rule)}
                  onChange={e => setR({ ...r, rule_ids: e.target.checked ? [...r.rule_ids, rule] : r.rule_ids.filter(x => x !== rule) })} />
                {rule}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <p className="text-[11px] text-gray-500 dark:text-slate-400">
        {novo ? 'Cria a versão 1 do método.' : 'Salvar cria a versão seguinte; os orçamentos já gerados guardam a de antes e saem desatualizados com o motivo.'}
      </p>
      <div className="flex gap-2">
        <button type="submit" disabled={!valido || salvar.isPending}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white">
          {salvar.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {novo ? 'Criar método' : 'Salvar nova versão'}
        </button>
        <button type="button" onClick={onFechar}
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300">
          Cancelar
        </button>
      </div>
    </form>
  );
}

export default function MetodosPrecos() {
  const { data, isLoading, isError } = useMetodos();
  const salvar = useSalvarMetodo();
  const { data: regrasMotor } = useQuery<{ rule_id: string }[]>({
    queryKey: ['motor-regras'],
    queryFn: async () => (await api.get('/motor-juridico/regras')).data,
    staleTime: 300_000,
  });
  const [editando, setEditando] = useState<string | null>(null); // código, ou '' para novo
  const [historico, setHistorico] = useState<string | null>(null);

  const regras = useMemo(() => [...new Set((regrasMotor ?? []).map(r => r.rule_id))].sort(), [regrasMotor]);
  // A versão mais nova de cada código, ativa ou não (inativo aparece para ser reativado).
  const ultimas = useMemo(() => {
    const por: Record<string, MetodoOrcamento> = {};
    for (const m of data?.versoes ?? []) if (!por[m.codigo] || m.versao > por[m.codigo].versao) por[m.codigo] = m;
    return Object.values(por).sort((a, b) => Number(b.ativo) - Number(a.ativo) || a.codigo.localeCompare(b.codigo));
  }, [data]);

  const alternarAtivo = (m: MetodoOrcamento) =>
    salvar.mutate(deMetodo(m, { ativo: !m.ativo, padrao: m.ativo ? false : m.padrao }), {
      onSuccess: v => toast.success(`${v.nome}: ${v.ativo ? 'reativado' : 'desativado'} (versão ${v.versao}).`),
      onError: err => toast.error(mensagemDeErro(err, 'Falha ao mudar o método.')),
    });

  return (
    <div className="space-y-4" data-testid="metodos-precos">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Métodos e preços</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            O orçamento de cada caso usa estes métodos, um item por passo da Rota. Mudar um preço cria a versão seguinte.
          </p>
        </div>
        {editando === null && (
          <button type="button" onClick={() => setEditando('')}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-gray-800 dark:bg-white/10 hover:bg-gray-700 dark:hover:bg-white/20 text-white">
            <Plus className="w-3.5 h-3.5" /> Novo método
          </button>
        )}
      </div>

      {editando === '' && <Formulario inicial={VAZIO} novo regras={regras} onFechar={() => setEditando(null)} />}

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-gray-500"><Loader2 className="w-4 h-4 animate-spin" /> Carregando…</p>
      ) : isError ? (
        <p className="text-sm text-red-700 dark:text-red-300">Não foi possível ler os métodos.</p>
      ) : ultimas.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-slate-400">
          Nenhum método cadastrado. Sem método padrão, o orçamento recusa passo sem método próprio.
        </p>
      ) : (
        <>
          {!ultimas.some(m => m.ativo && m.padrao) && (
            <p role="alert" className="text-xs text-amber-800 dark:text-amber-300">
              Nenhum método padrão ativo: passo sem método próprio fica sem preço e o orçamento é recusado.
            </p>
          )}
          <ul className="space-y-2">
            {ultimas.map(m => (
              <li key={m.codigo} data-metodo={m.codigo}
                className={`rounded-xl border p-3 ${m.ativo ? 'border-gray-200 dark:border-white/10' : 'border-dashed border-gray-200 dark:border-white/10 opacity-70'}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">{m.nome}</span>
                  <span className="font-mono text-[11px] text-gray-400">{m.codigo} v{m.versao}</span>
                  {m.padrao && m.ativo && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full border bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800">padrão</span>
                  )}
                  {!m.ativo && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full border bg-slate-100 text-slate-600 border-slate-200 dark:bg-zinc-800 dark:text-slate-300 dark:border-zinc-700">inativo</span>
                  )}
                  <span className="ml-auto text-sm font-semibold text-emerald-700 dark:text-emerald-400" data-testid={`preco-${m.codigo}`}>
                    {reais(m.valor_unitario)} <span className="text-xs font-normal text-gray-500">{UNIDADE_LABEL[m.unidade]}</span>
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                  {m.unidade !== 'fixo' && `Quantidade padrão ${m.quantidade_padrao}. `}
                  {m.rule_ids.length ? `Regras: ${m.rule_ids.join(', ')}.` : 'Sem regra mapeada.'}
                </p>
                <div className="flex flex-wrap gap-3 mt-2 text-xs">
                  {m.ativo && editando === null && (
                    <button type="button" onClick={() => setEditando(m.codigo)}
                      className="inline-flex items-center gap-1 text-gray-700 dark:text-slate-200 hover:underline">
                      <Pencil className="w-3.5 h-3.5" /> Editar {m.nome}
                    </button>
                  )}
                  <button type="button" onClick={() => alternarAtivo(m)} disabled={salvar.isPending}
                    className="inline-flex items-center gap-1 text-gray-500 dark:text-slate-400 hover:underline disabled:opacity-40">
                    <Power className="w-3.5 h-3.5" /> {m.ativo ? 'Desativar' : 'Reativar'} {m.nome}
                  </button>
                  <button type="button" onClick={() => setHistorico(historico === m.codigo ? null : m.codigo)}
                    className="inline-flex items-center gap-1 text-gray-500 dark:text-slate-400 hover:underline">
                    {historico === m.codigo ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    Versões
                  </button>
                </div>
                {historico === m.codigo && (
                  <ol className="mt-2 text-[11px] text-gray-500 dark:text-slate-400 space-y-0.5">
                    {(data?.versoes ?? []).filter(v => v.codigo === m.codigo).sort((a, b) => b.versao - a.versao).map(v => (
                      <li key={v.id}>
                        v{v.versao} · {reais(v.valor_unitario)} {UNIDADE_LABEL[v.unidade]}
                        {v.padrao ? ' · padrão' : ''}{v.ativo ? '' : ' · inativo'}
                      </li>
                    ))}
                  </ol>
                )}
                {editando === m.codigo && (
                  <div className="mt-3">
                    <Formulario inicial={deMetodo(m)} novo={false} regras={regras} onFechar={() => setEditando(null)} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      <RodapeVersao />
    </div>
  );
}
