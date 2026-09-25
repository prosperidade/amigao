import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import RodapeVersao from '@/components/RodapeVersao';
import { apoioNaRodada, camposLegiveis, segmentar, type ObservacaoConferencia } from './documentObservations';

interface DocumentoDoCaso { id: number; filename: string; tipo: string }
interface CampoSemSuporte { colecao: string; indice: number; campo: string; motivo: string }
interface Conferencia {
  documento: { id: number; nome: string; especie: string; versao: number | null; extraction_status: string | null };
  texto: string;
  observacoes: ObservacaoConferencia[];
  rejeicoes: { colecao: string; indice: number | null; motivo: string }[];
  campos_sem_suporte: CampoSemSuporte[];
  reparos: { colecao?: string; resultado?: string }[];
}

const rotulo = (valor: string | null) => (valor || 'indeterminado').replace(/_/g, ' ');

// Documento de um lado, observações do outro, com o trecho de origem visível (sessão com a Isis).
export default function DocumentObservationsPage() {
  const processId = Number(useParams<{ id: string }>().id);
  const [params, setParams] = useSearchParams();
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [mostrarSuperadas, setMostrarSuperadas] = useState(false);
  const [justificativaLote, setJustificativaLote] = useState('');
  const queryClient = useQueryClient();

  const documentos = useQuery({
    queryKey: ['semantic-documents', processId],
    queryFn: async () => (await api.get<DocumentoDoCaso[]>(`/evidence/cases/${processId}/documents`)).data,
  });
  const documentoId = Number(params.get('documento')) || documentos.data?.[0]?.id;
  const conferencia = useQuery({
    queryKey: ['document-conference', processId, documentoId],
    enabled: !!documentoId,
    queryFn: async () =>
      (await api.get<Conferencia>(`/evidence/cases/${processId}/documents/${documentoId}/conferencia`)).data,
  });

  const observacoes = useMemo(() => (conferencia.data?.observacoes || [])
    .filter(o => mostrarSuperadas || !o.superada), [conferencia.data, mostrarSuperadas]);
  const segmentos = useMemo(() => segmentar(conferencia.data?.texto || '', observacoes),
    [conferencia.data, observacoes]);
  const lote = useMemo(() => (conferencia.data?.observacoes || []).filter(o => o.no_lote),
    [conferencia.data]);
  // Dívida #286: uma decisão para as não reencontradas que uma leitura só viu; cada uma recebe a sua revisão.
  const decidirLote = useMutation({
    mutationFn: async (acao: 'aprovar' | 'rejeitar') => (await api.post<{ decididas: number }>(
      `/evidence/cases/${processId}/documents/${documentoId}/nao-reencontradas/lote`,
      { acao, justificativa: justificativaLote, observacoes: lote.map(o => ({ id: o.id, version: o.version })) })).data,
    onSuccess: () => {
      setJustificativaLote('');
      queryClient.invalidateQueries({ queryKey: ['document-conference', processId, documentoId] });
    },
  });
  const semSuporte = (o: ObservacaoConferencia) =>
    (o.conteudo?.campos_sem_suporte as CampoSemSuporte[] | undefined) || [];

  useEffect(() => {
    if (!selecionada) return;
    for (const lado of ['texto', 'lista']) {
      document.querySelector(`[data-lado="${lado}"][data-selecionada="true"]`)
        ?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }, [selecionada]);

  if (documentos.isPending) return <p className="p-6">Carregando documentos…</p>;
  if (documentos.isError) return <p role="alert" className="p-6">Não foi possível carregar os documentos do caso.</p>;

  return <div className="space-y-4">
    <header className="flex flex-wrap items-center gap-3">
      <Link to={`/processes/${processId}?tab=ai`} className="text-sm text-emerald-700 hover:underline">← Voltar ao caso</Link>
      <h1 className="text-lg font-semibold">Documento e observações</h1>
      <select aria-label="Documento" className="rounded border px-2 py-1 text-sm" value={documentoId || ''}
        onChange={e => { setSelecionada(null); setParams({ documento: e.target.value }); }}>
        {documentos.data?.map(d => <option key={d.id} value={d.id}>{d.filename} — {rotulo(d.tipo)}</option>)}
      </select>
      <label className="text-sm"><input type="checkbox" checked={mostrarSuperadas}
        onChange={e => setMostrarSuperadas(e.target.checked)} /> Mostrar observações superadas</label>
    </header>

    {conferencia.isPending && <p>Carregando documento…</p>}
    {conferencia.isError && <p role="alert">Não foi possível carregar o documento.</p>}
    {conferencia.data && <>
      <p className="text-sm text-gray-600">
        {rotulo(conferencia.data.documento.especie)} · versão do texto {conferencia.data.documento.versao ?? '—'} ·{' '}
        {observacoes.length} observações · {conferencia.data.rejeicoes.length} rejeitadas ·{' '}
        {conferencia.data.campos_sem_suporte.length} campos sem suporte no trecho
        {lote.length ? ` · ${lote.length} não reencontradas para decidir` : ''}
        {conferencia.data.documento.extraction_status ? ` · ${conferencia.data.documento.extraction_status}` : ''}
      </p>
      {lote.length > 0 && <section aria-label="Decisão em lote" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm">
        <p className="font-medium">
          {lote.length} não reencontrada(s) na última leitura, vista(s) por uma leitura só — decisão em lote
        </p>
        <p className="mt-1 text-xs text-gray-600">
          As vistas por duas ou mais leituras permanecem correntes, só com a marca informativa.
          A justificativa vai para a revisão de cada observação.
        </p>
        <textarea aria-label="Justificativa do lote" className="mt-2 w-full rounded border p-2" rows={2}
          value={justificativaLote} onChange={e => setJustificativaLote(e.target.value)} />
        <div className="mt-2 flex gap-2">
          <button type="button" disabled={!justificativaLote.trim() || decidirLote.isPending}
            onClick={() => decidirLote.mutate('aprovar')}
            className="rounded bg-emerald-600 px-3 py-1 text-white disabled:opacity-50">Manter todas (aprovar)</button>
          <button type="button" disabled={!justificativaLote.trim() || decidirLote.isPending}
            onClick={() => decidirLote.mutate('rejeitar')}
            className="rounded bg-gray-600 px-3 py-1 text-white disabled:opacity-50">Descartar todas (rejeitar)</button>
        </div>
        {decidirLote.isError && <p role="alert" className="mt-1 text-red-700">
          Não foi possível decidir o lote; recarregue a conferência.</p>}
      </section>}
      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-label="Texto do documento" className="rounded-xl border bg-white p-4 dark:bg-white/5">
          <pre className="max-h-[75vh] overflow-auto whitespace-pre-wrap break-words font-mono text-sm leading-6">
            {segmentos.map(s => {
              if (!s.observacoes.length) return <span key={s.inicio}>{s.texto}</span>;
              const ativo = selecionada !== null && s.observacoes.includes(selecionada);
              return <mark key={s.inicio} data-lado="texto" data-selecionada={ativo}
                title={`${s.observacoes.length} observação(ões) — clique para ver`}
                onClick={() => setSelecionada(s.observacoes.find(id => id !== selecionada) || s.observacoes[0])}
                className={`cursor-pointer rounded-sm ${ativo ? 'bg-amber-300 ring-2 ring-amber-500' : 'bg-emerald-100 hover:bg-emerald-200'}`}>
                {s.texto}
              </mark>;
            })}
          </pre>
        </section>
        <section aria-label="Observações" className="max-h-[80vh] space-y-2 overflow-auto">
          {observacoes.map(o => {
            const ativa = o.id === selecionada;
            return <article key={`${o.id}:${o.version}`} data-lado="lista" data-selecionada={ativa}
              data-observacao-id={o.id} onClick={() => setSelecionada(o.id)}
              className={`cursor-pointer rounded-lg border p-3 text-sm ${ativa ? 'border-amber-500 bg-amber-50' : 'bg-white dark:bg-white/5'}`}>
              <p className="font-medium">
                {rotulo(o.tipo)}{o.predicado && o.predicado !== o.tipo ? ` · ${rotulo(o.predicado)}` : ''}
                {o.superada && <span className="ml-2 text-xs text-gray-500">superada por nova extração</span>}
                {!o.superada && o.desatualizada && <span className="ml-2 text-xs text-gray-500">desatualizada</span>}
                {o.no_lote && <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs text-amber-800">
                  não reencontrada, vista por uma leitura — no lote</span>}
                {o.nao_reencontrada && !o.no_lote && <span className="ml-2 text-xs text-gray-500">
                  não reencontrada na última rodada</span>}
              </p>
              <dl className="mt-1 grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5">
                {camposLegiveis(o.conteudo).map(([chave, valor]) =>
                  <div key={chave} className="contents"><dt className="text-gray-500">{chave}</dt><dd>{valor}</dd></div>)}
              </dl>
              {semSuporte(o).map(c => <p key={c.campo} className="mt-1 text-xs text-amber-700">
                {rotulo(c.campo)} vazio: {c.motivo} (conhecimento não determinado)</p>)}
              <blockquote className="mt-2 border-l-4 border-emerald-400 pl-2 font-mono text-xs whitespace-pre-wrap">
                {o.trecho}
              </blockquote>
              <p className="mt-1 text-xs text-gray-500">
                {o.inicio !== null ? `Trecho de origem: caracteres ${o.inicio}–${o.fim}` : 'Trecho fora da versão atual do texto'}
                {' · '}conhecimento: {rotulo(o.conhecimento)}
                {apoioNaRodada(o.conteudo) && ` · ${apoioNaRodada(o.conteudo)}`}
              </p>
            </article>;
          })}
          {!!conferencia.data.rejeicoes.length && <details className="rounded-lg border p-3 text-sm">
            <summary>Observações rejeitadas ({conferencia.data.rejeicoes.length})</summary>
            <ul>{conferencia.data.rejeicoes.map((r, i) =>
              <li key={i}>{r.colecao}{r.indice !== null ? ` — item ${r.indice + 1}` : ''}: {r.motivo}</li>)}</ul>
          </details>}
        </section>
      </div>
    </>}
    <RodapeVersao />
  </div>;
}
