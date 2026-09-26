/**
 * ComercialRotaPanel — relatório preliminar, especificação de escopo e orçamento (ADR-074, dívida #282).
 *
 * A cadeia comercial nasce da Rota validada: o Redator escreve o relatório e o
 * escopo como afirmações com evidência por ID; o orçamento tem um item por passo
 * cobrado; a proposta nasce do orçamento aprovado e atual. Nada aqui regenera
 * sozinho — a atualidade chega na leitura, com os motivos, e quem decide gerar
 * a versão nova é o consultor.
 *
 * Toda afirmação mostra a evidência clicável (EvidenciaChip). Aprovar e rejeitar
 * exigem justificativa, como na API.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { AlertTriangle, Check, FilePlus2, FileText, Loader2, RefreshCw, X } from 'lucide-react';
import EvidenciaChip from '@/components/EvidenciaChip';
import { api } from '@/lib/api';
import { mensagemDeErro } from '@/lib/apiError';
import {
  useCriarPropostaDoOrcamento,
  useEscolherNoPasso,
  useGerarOrcamento,
  useGerarRedacao,
  useMetodos,
  useOrcamento,
  useRedacoes,
  useRevisarOrcamento,
  useRevisarRedacao,
  type RevisaoPayload,
} from '@/lib/comercial/hooks';
import {
  ATUALIDADE_LABEL,
  REVISAO_LABEL,
  reais,
  type Atualidade,
  type EstadoRevisao,
  type Orcamento,
  type OrcamentoItem,
  type Redacao,
  type VersaoResumo,
} from '@/lib/comercial/types';

const CARD = 'rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5 space-y-4';

const REVISAO_CLS: Record<EstadoRevisao, string> = {
  proposta: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-zinc-800 dark:text-slate-300 dark:border-zinc-700',
  aprovada: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800',
  rejeitada: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800',
};

function Selos({ estado, atualidade, testid }: { estado: EstadoRevisao; atualidade: Atualidade; testid: string }) {
  return (
    <span className="inline-flex flex-wrap gap-1.5" data-testid={testid}>
      <span className={`text-[10px] px-2 py-0.5 rounded-full border ${REVISAO_CLS[estado]}`}>{REVISAO_LABEL[estado]}</span>
      <span
        className={`text-[10px] px-2 py-0.5 rounded-full border ${
          atualidade.estado === 'vigente'
            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30'
            : 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800'
        }`}
      >
        {ATUALIDADE_LABEL[atualidade.estado]}
      </span>
    </span>
  );
}

function Motivos({ atualidade }: { atualidade: Atualidade }) {
  if (atualidade.estado === 'vigente' || atualidade.motivos.length === 0) return null;
  return (
    <div role="alert" className="rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 p-3">
      <p className="text-xs font-medium text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
        <AlertTriangle className="w-4 h-4" /> {ATUALIDADE_LABEL[atualidade.estado]} — motivos:
      </p>
      <ul className="mt-1 list-disc pl-6 text-xs text-amber-800 dark:text-amber-300 space-y-0.5">
        {atualidade.motivos.map(m => <li key={m}>{m}</li>)}
      </ul>
    </div>
  );
}

/** Aprovar/rejeitar com justificativa obrigatória (mesma regra da API). */
function RevisaoForm({
  rotulo,
  pendente,
  onRevisar,
}: {
  rotulo: string;
  pendente: boolean;
  onRevisar: (p: RevisaoPayload, limpar: () => void) => void;
}) {
  const [justificativa, setJustificativa] = useState('');
  const enviar = (acao: RevisaoPayload['acao']) => {
    if (!justificativa.trim()) {
      toast('Escreva a justificativa da revisão.', { icon: 'ℹ️' });
      return;
    }
    onRevisar({ acao, justificativa: justificativa.trim() }, () => setJustificativa(''));
  };
  return (
    <div className="space-y-1.5 border-t border-gray-100 dark:border-white/10 pt-3">
      <label className="block text-[11px] text-gray-500 dark:text-slate-400" htmlFor={`rev-${rotulo}`}>
        Revisão do {rotulo} — justificativa
      </label>
      <textarea
        id={`rev-${rotulo}`}
        value={justificativa}
        onChange={e => setJustificativa(e.target.value)}
        rows={2}
        className="w-full rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-900 dark:text-white px-2 py-1.5 text-xs focus:outline-none focus:border-emerald-500"
      />
      <div className="flex gap-2">
        <button
          type="button"
          disabled={pendente}
          onClick={() => enviar('aprovar')}
          className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white"
        >
          <Check className="w-3.5 h-3.5" /> Aprovar {rotulo}
        </button>
        <button
          type="button"
          disabled={pendente}
          onClick={() => enviar('rejeitar')}
          className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-500/10 disabled:opacity-40"
        >
          <X className="w-3.5 h-3.5" /> Rejeitar {rotulo}
        </button>
      </div>
    </div>
  );
}

function Versoes({ versoes }: { versoes: VersaoResumo[] }) {
  if (versoes.length <= 1) return null;
  return (
    <p className="text-[11px] text-gray-400 dark:text-slate-500">
      Versões:{' '}
      {versoes.map(v => `v${v.versao} ${REVISAO_LABEL[v.estado_revisao].toLowerCase()}${v.superada_em ? ' (superada)' : ''}`).join(' · ')}
    </p>
  );
}

function RedacaoCard({
  processId,
  titulo,
  rotulo,
  redacao,
  versoes,
}: {
  processId: number;
  titulo: string;
  rotulo: string;
  redacao: Redacao;
  versoes: VersaoResumo[];
}) {
  const revisar = useRevisarRedacao(processId);
  return (
    <section className={CARD} data-testid={`redacao-${redacao.tipo}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-800 dark:text-white">
          {titulo} <span className="font-normal text-gray-400">v{redacao.versao} · #{redacao.id}</span>
        </h3>
        <Selos estado={redacao.estado_revisao} atualidade={redacao.atualidade} testid={`selos-${redacao.tipo}`} />
      </div>
      <Motivos atualidade={redacao.atualidade} />
      {redacao.justificativa && (
        <p className="text-xs text-gray-500 dark:text-slate-400">Última revisão: “{redacao.justificativa}”</p>
      )}
      {redacao.conteudo.secoes.map(secao => (
        <div key={secao.chave}>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-400 mb-2">
            {secao.titulo}
          </h4>
          {secao.afirmacoes.length === 0 ? (
            <p className="text-xs text-gray-400 dark:text-slate-500">Nada nesta seção.</p>
          ) : (
            <ul className="space-y-2">
              {secao.afirmacoes.map(a => (
                <li key={a.id} data-afirmacao={a.id} className="text-sm text-gray-800 dark:text-slate-200">
                  <p>{a.texto}</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {a.evidencias.map(e => (
                      <EvidenciaChip key={`${e.tipo}:${e.id}`} processId={processId} evidencia={e} />
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
      {redacao.conteudo.limites && redacao.conteudo.limites.length > 0 && (
        <div className="text-[11px] text-gray-500 dark:text-slate-400">
          <p className="font-semibold">Limites deste documento</p>
          <ul className="list-disc pl-5">
            {redacao.conteudo.limites.map(l => <li key={l}>{l}</li>)}
          </ul>
        </div>
      )}
      <Versoes versoes={versoes} />
      {redacao.estado_revisao === 'proposta' && redacao.atualidade.estado !== 'superada' && (
        <RevisaoForm
          rotulo={rotulo}
          pendente={revisar.isPending}
          onRevisar={(p, limpar) =>
            revisar.mutate(
              { redacaoId: redacao.id, ...p },
              {
                onSuccess: () => {
                  limpar();
                  toast.success(p.acao === 'aprovar' ? `${titulo} aprovado.` : `${titulo} rejeitado.`);
                },
                onError: err => toast.error(mensagemDeErro(err, 'Falha ao revisar.')),
              },
            )
          }
        />
      )}
    </section>
  );
}

function ItemLinha({
  processId,
  item,
  editavel,
}: {
  processId: number;
  item: OrcamentoItem;
  editavel: boolean;
}) {
  const { data: metodos } = useMetodos();
  const escolher = useEscolherNoPasso(processId);
  const [quantidade, setQuantidade] = useState(item.quantidade);
  const correntes = metodos?.correntes.filter(m => m.ativo) ?? [];

  const aplicar = (payload: { metodo_codigo?: string | null; quantidade?: string | null }) =>
    escolher.mutate(
      { passoId: item.rota_passo_id, ...payload },
      {
        onSuccess: o => toast.success(`Orçamento v${o.versao} gerado com a sua escolha — revise e aprove.`),
        onError: err => toast.error(mensagemDeErro(err, 'Falha ao aplicar a escolha.')),
      },
    );

  return (
    <tr className="border-t border-gray-100 dark:border-white/10 align-top" data-testid={`item-passo-${item.rota_passo_id}`}>
      <td className="py-2 pr-2 text-gray-400">{item.ordem}</td>
      <td className="py-2 pr-2">
        <p className="text-gray-800 dark:text-slate-200">{item.descricao}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          <EvidenciaChip processId={processId} evidencia={{ tipo: 'rota_passo', id: item.rota_passo_id, rotulo: `passo #${item.rota_passo_id}` }} />
          {item.fundamento?.dispositivo_id && (
            <EvidenciaChip
              processId={processId}
              evidencia={{ tipo: 'dispositivo', id: item.fundamento.dispositivo_id, rotulo: item.fundamento.caminho ?? 'fundamento' }}
            />
          )}
        </div>
      </td>
      <td className="py-2 pr-2">
        {editavel ? (
          <select
            aria-label={`Método do passo ${item.rota_passo_id}`}
            value={item.metodo.codigo}
            disabled={escolher.isPending}
            onChange={e => aplicar({ metodo_codigo: e.target.value })}
            className="rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-xs px-1.5 py-1"
          >
            {!correntes.some(m => m.codigo === item.metodo.codigo) && (
              <option value={item.metodo.codigo}>{item.metodo.nome}</option>
            )}
            {correntes.map(m => (
              <option key={m.codigo} value={m.codigo}>{m.nome}</option>
            ))}
          </select>
        ) : (
          <span>{item.metodo.nome}</span>
        )}
        <p className="text-[10px] text-gray-400 mt-0.5">
          {item.metodo.codigo} v{item.metodo.versao} · por {item.escolha}
        </p>
      </td>
      <td className="py-2 pr-2 whitespace-nowrap">
        {editavel ? (
          <input
            aria-label={`Quantidade do passo ${item.rota_passo_id}`}
            value={quantidade}
            onChange={e => setQuantidade(e.target.value)}
            onBlur={() => {
              if (quantidade !== item.quantidade && Number(quantidade) > 0) aplicar({ quantidade });
            }}
            className="w-16 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-xs px-1.5 py-1"
          />
        ) : (
          item.quantidade
        )}{' '}
        <span className="text-gray-400">{item.unidade}</span>
      </td>
      <td className="py-2 pr-2 whitespace-nowrap">{reais(item.valor_unitario)}</td>
      <td className="py-2 font-semibold whitespace-nowrap">
        {reais(item.total)}
        {item.calculo && <p className="text-[10px] font-normal text-gray-400">{item.calculo}</p>}
      </td>
    </tr>
  );
}

function OrcamentoCard({
  processId,
  orcamento,
  versoes,
}: {
  processId: number;
  orcamento: Orcamento;
  versoes: VersaoResumo[];
}) {
  const navigate = useNavigate();
  const revisar = useRevisarOrcamento(processId);
  const criarProposta = useCriarPropostaDoOrcamento(processId);
  const { data: processo } = useQuery<{ id: number; client_id: number | null; title: string }>({
    queryKey: ['process-for-proposal', String(processId)],
    queryFn: async () => (await api.get(`/processes/${processId}`)).data,
    staleTime: 60_000,
  });
  const atual = orcamento.atualidade.estado === 'vigente';
  const aprovado = orcamento.estado_revisao === 'aprovada';
  const podeProposta = atual && aprovado && !!processo?.client_id;

  const gerarProposta = () => {
    if (!processo?.client_id) return;
    criarProposta.mutate(
      { orcamentoId: orcamento.id, clientId: processo.client_id, titulo: `${processo.title} — orçamento v${orcamento.versao}` },
      {
        onSuccess: p => {
          toast.success('Proposta criada do orçamento aprovado.');
          navigate(`/proposals/${p.id}`);
        },
        onError: err => toast.error(mensagemDeErro(err, 'Falha ao criar a proposta.')),
      },
    );
  };

  return (
    <section className={CARD} data-testid="orcamento">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-800 dark:text-white">
          Orçamento <span className="font-normal text-gray-400">v{orcamento.versao} · #{orcamento.id}</span>
        </h3>
        <Selos estado={orcamento.estado_revisao} atualidade={orcamento.atualidade} testid="selos-orcamento" />
      </div>
      <Motivos atualidade={orcamento.atualidade} />
      {orcamento.justificativa && (
        <p className="text-xs text-gray-500 dark:text-slate-400">Última revisão: “{orcamento.justificativa}”</p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-gray-400">
              <th className="pb-1 pr-2">#</th>
              <th className="pb-1 pr-2">Passo da Rota</th>
              <th className="pb-1 pr-2">Método</th>
              <th className="pb-1 pr-2">Qtd.</th>
              <th className="pb-1 pr-2">Unitário</th>
              <th className="pb-1">Total</th>
            </tr>
          </thead>
          <tbody>
            {orcamento.itens.map(i => (
              <ItemLinha key={i.id} processId={processId} item={i} editavel={orcamento.atualidade.estado !== 'superada'} />
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-gray-200 dark:border-white/20">
              <td colSpan={5} className="pt-2 text-right font-semibold text-gray-600 dark:text-slate-300">Total</td>
              <td className="pt-2 font-bold text-emerald-700 dark:text-emerald-400" data-testid="orcamento-total">
                {reais(orcamento.total)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="text-[10px] text-gray-400">
        Mudar método ou quantidade gera a versão seguinte, que volta para revisão.{' '}
        <Link to="/settings?tab=metodos" className="underline text-gray-500 dark:text-slate-300">
          Métodos e preços do escritório →
        </Link>
      </p>

      {orcamento.fora.length > 0 && (
        <div data-testid="orcamento-fora">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-400 mb-1">Fora do orçamento</h4>
          <ul className="space-y-1.5">
            {orcamento.fora.map(f => (
              <li key={f.rota_passo_id} className="text-xs text-gray-700 dark:text-slate-300">
                <span className="font-medium">{f.titulo}</span> — <span className="italic">{f.motivo}</span>{' '}
                <EvidenciaChip processId={processId} evidencia={{ tipo: 'rota_passo', id: f.rota_passo_id, rotulo: `passo #${f.rota_passo_id}` }} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {orcamento.ressalvas.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-400 mb-1">Ressalvas</h4>
          {orcamento.ressalvas.map(r => (
            <div key={r.tipo} className="text-xs text-gray-700 dark:text-slate-300">
              <p>{r.texto}</p>
              {r.conclusoes && r.conclusoes.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {r.conclusoes.map(c => (
                    <EvidenciaChip key={c} processId={processId} evidencia={{ tipo: 'conclusao', id: c, rotulo: `conclusão #${c}` }} />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <Versoes versoes={versoes} />

      {orcamento.estado_revisao === 'proposta' && orcamento.atualidade.estado !== 'superada' && (
        <RevisaoForm
          rotulo="orçamento"
          pendente={revisar.isPending}
          onRevisar={(p, limpar) =>
            revisar.mutate(
              { orcamentoId: orcamento.id, ...p },
              {
                onSuccess: () => {
                  limpar();
                  toast.success(p.acao === 'aprovar' ? 'Orçamento aprovado.' : 'Orçamento rejeitado.');
                },
                onError: err => toast.error(mensagemDeErro(err, 'Falha ao revisar o orçamento.')),
              },
            )
          }
        />
      )}

      <div className="border-t border-gray-100 dark:border-white/10 pt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={gerarProposta}
          disabled={!podeProposta || criarProposta.isPending}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white"
        >
          {criarProposta.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FilePlus2 className="w-3.5 h-3.5" />}
          Criar proposta deste orçamento
        </button>
        {!podeProposta && (
          <span className="text-[11px] text-gray-500 dark:text-slate-400">
            {!aprovado
              ? 'A proposta nasce do orçamento aprovado.'
              : !atual
                ? 'Orçamento desatualizado: gere a versão nova antes da proposta.'
                : 'O processo não tem cliente vinculado.'}
          </span>
        )}
      </div>
    </section>
  );
}

export default function ComercialRotaPanel({ processId }: { processId: number }) {
  const redacoes = useRedacoes(processId);
  const orcamento = useOrcamento(processId);
  const gerarRedacao = useGerarRedacao(processId);
  const gerarOrcamento = useGerarOrcamento(processId);

  const rel = redacoes.data?.relatorio_preliminar ?? null;
  const esc = redacoes.data?.especificacao_escopo ?? null;
  const orc = orcamento.data?.orcamento ?? null;
  const versoesRed = redacoes.data?.versoes ?? [];

  const gerarDocs = () =>
    gerarRedacao.mutate(undefined, {
      onSuccess: d =>
        toast.success(`Relatório v${d.relatorio_preliminar.versao} e escopo v${d.especificacao_escopo.versao} gerados.`),
      onError: err => toast.error(mensagemDeErro(err, 'Falha ao gerar o relatório e o escopo.')),
    });
  const gerarOrc = () =>
    gerarOrcamento.mutate(undefined, {
      onSuccess: o => toast.success(`Orçamento v${o.versao} gerado: ${reais(o.total)}.`),
      onError: err => toast.error(mensagemDeErro(err, 'Falha ao gerar o orçamento.')),
    });

  if (redacoes.isLoading || orcamento.isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando o fechamento comercial…
      </p>
    );
  }

  return (
    <div className="space-y-4" data-testid="comercial-rota">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200">Relatório, escopo e orçamento</h2>
          <p className="text-xs text-gray-500 dark:text-slate-400">
            Nascem da Rota validada. Cada afirmação cita a evidência por ID — clique para ver.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={gerarDocs}
            disabled={gerarRedacao.isPending}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-gray-800 dark:bg-white/10 hover:bg-gray-700 dark:hover:bg-white/20 disabled:opacity-40 text-white"
          >
            {gerarRedacao.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : rel ? <RefreshCw className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
            {rel ? 'Gerar nova versão do relatório e escopo' : 'Gerar relatório e escopo'}
          </button>
          <button
            type="button"
            onClick={gerarOrc}
            disabled={gerarOrcamento.isPending || !esc}
            title={esc ? undefined : 'O orçamento nasce do escopo aprovado'}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white"
          >
            {gerarOrcamento.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {orc ? 'Gerar nova versão do orçamento' : 'Gerar orçamento'}
          </button>
        </div>
      </div>

      {!rel && !esc && (
        <p className="text-xs text-gray-400 dark:text-slate-500">
          Nenhum relatório gerado. Feche a Rota e gere o relatório preliminar e a especificação de escopo.
        </p>
      )}
      {rel && (
        <RedacaoCard
          processId={processId}
          titulo="Relatório preliminar"
          rotulo="relatório"
          redacao={rel}
          versoes={versoesRed.filter(v => v.tipo === 'relatorio_preliminar')}
        />
      )}
      {esc && (
        <RedacaoCard
          processId={processId}
          titulo="Especificação de escopo"
          rotulo="escopo"
          redacao={esc}
          versoes={versoesRed.filter(v => v.tipo === 'especificacao_escopo')}
        />
      )}
      {orc ? (
        <OrcamentoCard processId={processId} orcamento={orc} versoes={orcamento.data?.versoes ?? []} />
      ) : (
        esc && <p className="text-xs text-gray-400 dark:text-slate-500">Nenhum orçamento gerado. Aprove o escopo e gere o orçamento.</p>
      )}
    </div>
  );
}
