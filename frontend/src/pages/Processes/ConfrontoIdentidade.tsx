/**
 * ConfrontoIdentidade — a primeira coisa da Conferência quando dois documentos
 * declaram números de matrícula diferentes.
 *
 * É o painel que teria evitado o erro do caso 15: o CCIR do Lote 1B declarava
 * 2923 (número registral defasado), a certidão declarava 4698 (atual), e a tela
 * nunca colocou os dois lado a lado. O consultor aceitou o CCIR e rejeitou a
 * certidão sem saber que estava escolhendo a identidade jurídica do imóvel.
 *
 * A frase da regra vem PRONTA do backend (mesmo padrão do guard-rail do avanço):
 * a tela não reimplementa a hierarquia da Ficha 08 §5.1. Foi a redação duplicada
 * em cada superfície que produziu as divergências do ADR-031.
 *
 * Este painel não decide nada — mostra, nomeia a fonte de cada número e deixa a
 * escolha com o consultor.
 */

import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, GitBranch, FileText } from 'lucide-react';
import { api } from '@/lib/api';

interface FonteNumero {
  numero: string;
  document_id: number | null;
  fonte: string;
  status: string;
  staging_id: number;
}

interface CadeiaProposta {
  vigente: string;
  historica: string;
  texto: string;
  evidencia_document_id: number | null;
}

interface ConfrontoResponse {
  ha_confronto: boolean;
  regra: string;
  prevalente: { numero: string; fonte: string } | null;
  fontes: FonteNumero[];
  cadeia_proposta: CadeiaProposta | null;
}

const STATUS_LABEL: Record<string, string> = {
  pendente: 'a decidir',
  aceito: 'aceito',
  rejeitado: 'rejeitado',
  consistente: 'consistente',
  divergente_transcricao: 'divergente',
  divergente_fundo: 'divergente',
};

export default function ConfrontoIdentidade({ processId }: { processId: number }) {
  const { data, isLoading } = useQuery<ConfrontoResponse>({
    queryKey: ['confronto-identidade', processId],
    queryFn: () => api.get(`/processes/${processId}/confronto-identidade`).then(r => r.data),
  });

  // Sem confronto não há o que mostrar — o painel só aparece quando há de fato
  // números concorrentes. Radar-não-cancela: falha ao carregar não derruba a aba.
  if (isLoading || !data?.ha_confronto) return null;

  return (
    <div className="rounded-2xl border-2 border-amber-300 dark:border-amber-500/40 bg-amber-50/70 dark:bg-amber-500/5 overflow-hidden">
      <div className="px-5 py-4 border-b border-amber-200 dark:border-amber-500/20">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
              Qual é o número da matrícula deste imóvel?
            </h3>
            <p className="text-xs text-amber-800 dark:text-amber-300/90 mt-1">
              Documentos deste caso declaram números diferentes. Decida isto antes
              de conferir os campos — é a identidade jurídica do imóvel.
            </p>
          </div>
        </div>
      </div>

      {/* Números lado a lado, com a fonte de cada um. */}
      <div className="px-5 py-4 grid gap-2 sm:grid-cols-2">
        {data.fontes.map(f => {
          const prevalece = data.prevalente?.numero === f.numero;
          return (
            <div
              key={f.staging_id}
              className={`rounded-xl border p-3 ${
                prevalece
                  ? 'border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10'
                  : 'border-gray-200 dark:border-white/10 bg-white/70 dark:bg-white/5'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-lg font-semibold text-gray-900 dark:text-white">
                  {f.numero}
                </span>
                {prevalece && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30">
                    fonte jurídica
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-600 dark:text-slate-400 mt-1 flex items-center gap-1">
                <FileText className="w-3 h-3 shrink-0" />
                {f.fonte}
                {f.document_id != null && ` · doc ${f.document_id}`}
                {' · '}
                {STATUS_LABEL[f.status] ?? f.status}
              </p>
            </div>
          );
        })}
      </div>

      {/* A regra vem pronta do backend — a tela não reimplementa a hierarquia. */}
      <div className="px-5 pb-4">
        <p className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
          {data.regra}
        </p>
      </div>

      {/* Cadeia proposta ANTES da decisão: os dois números podem ser a mesma
          terra em momentos diferentes, e não um erro a corrigir. */}
      {data.cadeia_proposta && (
        <div className="px-5 py-4 border-t border-amber-200 dark:border-amber-500/20 bg-white/50 dark:bg-white/5">
          <div className="flex items-start gap-3">
            <GitBranch className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-medium text-gray-900 dark:text-white">
                Possível linhagem detectada
              </p>
              <p className="text-xs text-gray-600 dark:text-slate-400 mt-1 leading-relaxed">
                {data.cadeia_proposta.texto}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
