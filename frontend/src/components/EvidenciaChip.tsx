/**
 * EvidenciaChip — a evidência por ID de uma afirmação, CLICÁVEL (dívidas #278/#282).
 *
 * O relatório preliminar, o escopo, o orçamento e a Rota do motor citam evidência
 * como `{tipo, id}` (ADR-074 §2). O chip mostra o rótulo; o clique abre o painel
 * com o que está gravado por trás daquele ID — o texto do dispositivo, a
 * observação com a âncora, a avaliação da regra com os fatos que faltaram — lido
 * de `GET /processes/{pid}/evidencias/{tipo}/{id}`, com as mesmas travas de tenant
 * e caso da verificação. Um ID que não resolve aparece como tal, nunca some.
 *
 * Dentro do painel, as evidências que o próprio detalhe cita (o passo cita o
 * dispositivo; a observação cita o documento) são clicáveis e empilham: "voltar"
 * refaz o caminho.
 */
import { useState } from 'react';
import { ArrowLeft, ExternalLink, Link2, Loader2, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { useEvidencia } from '@/lib/comercial/hooks';
import { EVIDENCIA_TIPO_LABEL, type EvidenciaRef } from '@/lib/comercial/types';

const CHIP =
  'inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border max-w-full ' +
  'bg-sky-50 text-sky-700 border-sky-200 hover:bg-sky-100 ' +
  'dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/30 dark:hover:bg-sky-500/20';

async function abrirDocumento(documentoId: number) {
  try {
    const res = await api.get(`/documents/${documentoId}/download-url`);
    window.open(res.data.download_url, '_blank', 'noopener');
  } catch {
    toast.error('Não foi possível abrir o documento.');
  }
}

function Detalhe({
  processId,
  evidencia,
  onSeguir,
}: {
  processId: number;
  evidencia: EvidenciaRef;
  onSeguir: (ref: EvidenciaRef) => void;
}) {
  const { data, isLoading, isError } = useEvidencia(processId, evidencia.tipo, evidencia.id, true);

  if (isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando…
      </p>
    );
  }
  if (isError || !data) {
    return (
      <p role="alert" className="text-sm text-red-700 dark:text-red-300">
        {`${EVIDENCIA_TIPO_LABEL[evidencia.tipo]} #${evidencia.id} não resolve neste caso.`}
      </p>
    );
  }
  return (
    <div className="space-y-3" data-testid="evidencia-detalhe">
      <div>
        <p className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-slate-500">
          {EVIDENCIA_TIPO_LABEL[data.tipo]} #{data.id}
        </p>
        <p className="text-sm font-semibold text-gray-900 dark:text-white">{data.titulo}</p>
      </div>
      {data.texto && (
        <div>
          <p className="text-xs text-gray-800 dark:text-slate-200 whitespace-pre-wrap bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded p-2 max-h-72 overflow-auto">
            {data.texto}
          </p>
          {data.texto_cortado && (
            <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-1">Texto cortado na tela; o registro é integral.</p>
          )}
        </div>
      )}
      {data.campos.length > 0 && (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
          {data.campos.map(c => (
            <div key={c.rotulo} className="contents">
              <dt className="text-gray-500 dark:text-slate-400">{c.rotulo}</dt>
              <dd className="text-gray-800 dark:text-slate-200 break-all">{c.valor}</dd>
            </div>
          ))}
        </dl>
      )}
      {data.documento_id !== null && (
        <button
          type="button"
          onClick={() => abrirDocumento(data.documento_id!)}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white"
        >
          <ExternalLink className="w-3.5 h-3.5" /> Abrir o documento
        </button>
      )}
      {data.refs.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-slate-500 mb-1">Cita</p>
          <div className="flex flex-wrap gap-1.5">
            {data.refs.map(r => (
              <button key={`${r.tipo}:${r.id}`} type="button" onClick={() => onSeguir(r)} className={CHIP}>
                <Link2 className="w-3 h-3 shrink-0" />
                <span className="truncate">{r.rotulo}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function EvidenciaPainel({
  processId,
  inicial,
  onFechar,
}: {
  processId: number;
  inicial: EvidenciaRef;
  onFechar: () => void;
}) {
  const [pilha, setPilha] = useState<EvidenciaRef[]>([inicial]);
  const atual = pilha[pilha.length - 1];
  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/30"
      onClick={onFechar}
      role="presentation"
    >
      <aside
        role="dialog"
        aria-label="Evidência"
        className="h-full w-full max-w-lg overflow-y-auto bg-white dark:bg-zinc-900 border-l border-gray-200 dark:border-white/10 p-5 space-y-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2">
          {pilha.length > 1 ? (
            <button
              type="button"
              onClick={() => setPilha(p => p.slice(0, -1))}
              className="inline-flex items-center gap-1 text-xs text-gray-600 dark:text-slate-300 hover:underline"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> voltar
            </button>
          ) : (
            <span className="text-xs text-gray-500 dark:text-slate-400">Evidência por ID</span>
          )}
          <button type="button" onClick={onFechar} aria-label="Fechar evidência" className="p-1 rounded hover:bg-gray-100 dark:hover:bg-white/10">
            <X className="w-4 h-4" />
          </button>
        </div>
        <Detalhe
          key={`${atual.tipo}:${atual.id}`}
          processId={processId}
          evidencia={atual}
          onSeguir={r => setPilha(p => [...p, r])}
        />
      </aside>
    </div>
  );
}

export default function EvidenciaChip({ processId, evidencia }: { processId: number; evidencia: EvidenciaRef }) {
  const [aberto, setAberto] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setAberto(true)}
        title={`Abrir ${EVIDENCIA_TIPO_LABEL[evidencia.tipo] ?? evidencia.tipo} #${evidencia.id}`}
        data-evidencia={`${evidencia.tipo}:${evidencia.id}`}
        className={CHIP}
      >
        <Link2 className="w-3 h-3 shrink-0" />
        <span className="truncate">{evidencia.rotulo}</span>
      </button>
      {aberto && <EvidenciaPainel processId={processId} inicial={evidencia} onFechar={() => setAberto(false)} />}
    </>
  );
}
