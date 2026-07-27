/**
 * FonteChip — a fonte de uma afirmação, CLICÁVEL.
 *
 * Regra (Fase 0 do caso 15, 26/07): **acerto sem fonte visível é indistinguível
 * de alucinação**. A Análise Legal citou a Notificação GO-NOT-2024-001985 e a
 * consultora não reconheceu o número — a investigação provou que o dado estava
 * certo (veio do relato dela na entrada do caso), mas a tela não dizia de onde
 * vinha, então "certo" e "inventado" pareciam a mesma coisa. Custou uma auditoria
 * inteira para descobrir algo que um clique deveria responder.
 *
 * Três comportamentos, por tipo de fonte:
 *  - `documento`  → abre o PDF do caso (link assinado do storage);
 *  - `legislacao` → expande o trecho da norma, ao pé da letra (`trecho`);
 *  - `sem_fonte`  → NÃO vira link. Marca âmbar explícita: o sistema declara que
 *                   não sabe de onde tirou. Nunca esconder isso atrás de um chip
 *                   bonito — é a informação mais importante da lista.
 *
 * O `atendimento` (relato do cliente) é um caso à parte e deliberado: aparece
 * como fonte legítima, com aviso de que **não foi conferido em documento**. Era
 * exatamente o rótulo que faltava na GO-NOT.
 */

import { useState } from 'react';
import { BookOpen, ExternalLink, FileText, MessageSquare, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { fonteTipoLabel } from '@/lib/labels/docLabels';

export interface FonteRef {
  tipo: string;
  ref?: string | null;
  descricao?: string | null;
  valor?: string | null;
  confianca?: string | null;
  sem_fonte?: boolean;
  /** Página do documento, quando conhecida. */
  pagina?: number | null;
  /** Texto literal da norma — preenchido na fundamentação (biblioteca). */
  trecho?: string | null;
}

const BASE =
  'inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border max-w-full';

export default function FonteChip({ fonte }: { fonte: FonteRef }) {
  const [aberto, setAberto] = useState(false);
  const semFonte = fonte.sem_fonte === true || fonte.tipo === 'sem_fonte';
  const rotulo = fonte.descricao || fonte.ref || fonte.tipo;

  // ── Sem fonte: aviso, nunca link ─────────────────────────────────────────
  if (semFonte) {
    return (
      <span
        title="O sistema não identificou de onde veio esta afirmação. Trate como hipótese até conferir."
        className={`${BASE} bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/40`}
      >
        <AlertTriangle className="w-3 h-3 shrink-0" />
        sem fonte identificada — confira antes de usar
      </span>
    );
  }

  // ── Documento do caso: abre o arquivo ────────────────────────────────────
  if (fonte.tipo === 'documento' && fonte.ref) {
    const abrir = async () => {
      try {
        const res = await api.get(`/documents/${fonte.ref}/download-url`);
        window.open(res.data.download_url, '_blank', 'noopener');
      } catch {
        toast.error('Não foi possível abrir o documento.');
      }
    };
    return (
      <button
        type="button"
        onClick={abrir}
        title="Abrir o documento de origem"
        className={`${BASE} bg-sky-50 text-sky-700 border-sky-200 hover:bg-sky-100 dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/30`}
      >
        <FileText className="w-3 h-3 shrink-0" />
        <span className="truncate">{rotulo}</span>
        {fonte.pagina != null && <span className="shrink-0">· p. {fonte.pagina}</span>}
        <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-70" />
      </button>
    );
  }

  // ── Relato do cliente: fonte real, com o alcance declarado ───────────────
  if (fonte.tipo === 'atendimento') {
    return (
      <span
        title="Informação relatada pelo cliente na entrada do caso. Não foi conferida em documento."
        className={`${BASE} bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:border-violet-500/30`}
      >
        <MessageSquare className="w-3 h-3 shrink-0" />
        <span className="truncate">relato do cliente — não conferido em documento</span>
      </span>
    );
  }

  // ── Norma: expande o texto literal ───────────────────────────────────────
  if (fonte.tipo === 'legislacao' && fonte.trecho) {
    return (
      <>
        <button
          type="button"
          onClick={() => setAberto(v => !v)}
          title="Ver o texto da norma, ao pé da letra"
          className={`${BASE} bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100 dark:bg-purple-500/10 dark:text-purple-300 dark:border-purple-500/30`}
        >
          <BookOpen className="w-3 h-3 shrink-0" />
          <span className="truncate">{rotulo}</span>
        </button>
        {aberto && (
          <p className="basis-full mt-1 text-xs text-gray-700 dark:text-slate-300 whitespace-pre-wrap bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded p-2 max-h-64 overflow-auto">
            {fonte.trecho}
          </p>
        )}
      </>
    );
  }

  // ── Demais tipos (matriz, rat, auditor): rótulo, sem link ────────────────
  return (
    <span
      className={`${BASE} bg-gray-50 text-gray-600 border-gray-200 dark:bg-white/5 dark:text-slate-300 dark:border-white/10`}
    >
      <span className="truncate">
        {fonteTipoLabel(fonte.tipo)}: {rotulo}
      </span>
    </span>
  );
}
