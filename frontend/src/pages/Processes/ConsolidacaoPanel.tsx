/**
 * ConsolidacaoPanel — Ficha 01 / FASE 4: decisão do consultor + consolidação.
 *
 * Estende a aba "Alertas": lista os campos do staging agrupados por entidade
 * (Cliente / Imóvel / Matrícula), com valor por fonte, status colorido e ações
 * (Aceitar · Escolher fonte · Editar · Rejeitar). Banner de aceite em lote dos
 * consistentes e botão "Consolidar na base". Tudo determinístico — o consultor
 * decide, o sistema grava.
 */

import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2, XCircle, Pencil, ListChecks, Database, Loader2, Layers,
} from 'lucide-react';
import { api } from '@/lib/api';
import { labelFor, humanizeValue } from '@/lib/labels/fieldLabels';

interface StagingField {
  id: number;
  source_doc_type: string | null;
  field_name: string;
  field_value: { value?: unknown; unidade?: string } | null;
  confidence: string | null;
  target_entity: string | null;
  target_field: string | null;
  matricula_hint: string | null;
  status: string;
  decided_value: { value?: unknown } | null;
}

interface ConsolidationResult {
  campos_gravados: number;
  matriculas_criadas: number;
  matriculas_atualizadas: number;
  cliente_atualizado: boolean;
  imovel_atualizado: boolean;
  area_total_matriculas: number | null;
}

const STATUS_CLS: Record<string, string> = {
  pendente: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300 dark:border-white/10',
  consistente: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30',
  divergente_transcricao: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
  divergente_fundo: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-500/10 dark:text-orange-300 dark:border-orange-500/30',
  aceito: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30',
  rejeitado: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
};
const STATUS_LABEL: Record<string, string> = {
  pendente: 'Pendente', consistente: 'Consistente', divergente_transcricao: 'Divergente (transcrição)',
  divergente_fundo: 'Divergente (fundo)', aceito: 'Aceito', rejeitado: 'Rejeitado',
};

function entityLabel(f: StagingField): string {
  if (f.target_entity === 'cliente') return 'Cliente';
  if (f.target_entity === 'imovel') return 'Imóvel';
  if (f.target_entity === 'matricula') return f.matricula_hint ? `Matrícula ${f.matricula_hint}` : 'Matrícula';
  return 'Outros';
}

function fieldValueStr(f: StagingField): string {
  const v = f.decided_value?.value ?? f.field_value?.value;
  const s = humanizeValue(v);
  return f.field_value?.unidade ? `${s} ${f.field_value.unidade}` : s;
}

export default function ConsolidacaoPanel({ processId }: { processId: number }) {
  const qc = useQueryClient();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [consolidated, setConsolidated] = useState<ConsolidationResult | null>(null);

  const { data: fields = [], isLoading } = useQuery<StagingField[]>({
    queryKey: ['staging-fields', processId],
    queryFn: () => api.get(`/processes/${processId}/staging-fields`).then(r => r.data),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['staging-fields', processId] });

  const decide = useMutation({
    mutationFn: (p: { id: number; acao: string; valor?: string }) =>
      api.post(`/processes/${processId}/staging-fields/${p.id}/decidir`, { acao: p.acao, valor: p.valor }).then(r => r.data),
    onSuccess: () => { setEditingId(null); invalidate(); },
  });
  const acceptAll = useMutation({
    mutationFn: () => api.post(`/processes/${processId}/staging-fields/aceitar-consistentes`, {}).then(r => r.data),
    onSuccess: invalidate,
  });
  const consolidate = useMutation<ConsolidationResult>({
    mutationFn: () => api.post(`/processes/${processId}/consolidar`, {}).then(r => r.data),
    onSuccess: (res) => { setConsolidated(res); invalidate(); },
  });

  const consistentesCount = useMemo(() => fields.filter(f => f.status === 'consistente').length, [fields]);
  const pendentesObrig = useMemo(
    () => fields.filter(f => f.status === 'divergente_transcricao').length,
    [fields],
  );
  const grupos = useMemo(() => {
    const by: Record<string, StagingField[]> = {};
    for (const f of fields) {
      const k = entityLabel(f);
      (by[k] ||= []).push(f);
    }
    for (const k of Object.keys(by)) {
      by[k].sort((a, b) => (a.target_field || '').localeCompare(b.target_field || ''));
    }
    return by;
  }, [fields]);

  if (isLoading) {
    return <p className="text-sm text-gray-500 dark:text-slate-400 flex items-center gap-1.5"><Loader2 className="w-4 h-4 animate-spin" /> Carregando campos…</p>;
  }
  if (fields.length === 0) return null;

  return (
    <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Layers className="w-4 h-4 text-purple-500" /> Decisão & Consolidação
        </h3>
        {consistentesCount > 0 && (
          <button
            onClick={() => acceptAll.mutate()}
            disabled={acceptAll.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-medium"
          >
            <ListChecks className="w-3.5 h-3.5" /> Aceitar todos os consistentes ({consistentesCount})
          </button>
        )}
      </div>

      {Object.entries(grupos).map(([grupo, rows]) => (
        <div key={grupo}>
          <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-1.5">{grupo}</p>
          <div className="space-y-1.5">
            {rows.map(f => (
              <div key={f.id} className="flex items-center gap-3 flex-wrap p-2.5 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5">
                <div className="flex-1 min-w-[160px]">
                  <p className="text-sm text-gray-800 dark:text-slate-200">{labelFor(f.target_field || f.field_name)}</p>
                  <p className="text-xs text-gray-400 dark:text-slate-500">
                    {f.source_doc_type ?? '—'} · {fieldValueStr(f)}
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded border whitespace-nowrap ${STATUS_CLS[f.status] ?? ''}`}>
                  {STATUS_LABEL[f.status] ?? f.status}
                </span>
                {editingId === f.id ? (
                  <div className="flex items-center gap-1">
                    <input
                      value={editValue}
                      onChange={e => setEditValue(e.target.value)}
                      placeholder="Novo valor"
                      className="px-2 py-1 text-xs rounded border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-gray-800 dark:text-white w-28"
                    />
                    <button onClick={() => decide.mutate({ id: f.id, acao: 'editar', valor: editValue })}
                      className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white">Salvar</button>
                    <button onClick={() => setEditingId(null)} className="text-xs px-1.5 py-1 text-gray-400">×</button>
                  </div>
                ) : f.status === 'aceito' || f.status === 'rejeitado' ? (
                  <span className="text-xs text-gray-400 dark:text-slate-500">decidido</span>
                ) : (
                  <div className="flex items-center gap-1">
                    {f.status === 'divergente_transcricao' ? (
                      <button onClick={() => decide.mutate({ id: f.id, acao: 'escolher_fonte' })}
                        title="Escolher esta fonte"
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white">
                        <CheckCircle2 className="w-3 h-3" /> Escolher fonte
                      </button>
                    ) : (
                      <button onClick={() => decide.mutate({ id: f.id, acao: 'aceitar' })}
                        title="Aceitar"
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white">
                        <CheckCircle2 className="w-3 h-3" /> Aceitar
                      </button>
                    )}
                    <button onClick={() => { setEditingId(f.id); setEditValue(''); }} title="Editar manual"
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-white/10">
                      <Pencil className="w-3 h-3" /> Editar
                    </button>
                    <button onClick={() => decide.mutate({ id: f.id, acao: 'rejeitar' })} title="Rejeitar"
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-500/10">
                      <XCircle className="w-3 h-3" /> Rejeitar
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className="pt-2 border-t border-gray-100 dark:border-white/10 flex items-center justify-between gap-3 flex-wrap">
        <div className="text-xs text-gray-500 dark:text-slate-400">
          {pendentesObrig > 0
            ? `${pendentesObrig} divergência(s) de transcrição aguardam escolha ativa.`
            : 'Sem divergências pendentes de escolha.'}
        </div>
        <button
          onClick={() => consolidate.mutate()}
          disabled={consolidate.isPending || pendentesObrig > 0}
          title={pendentesObrig > 0 ? 'Resolva as divergências de transcrição antes de consolidar.' : 'Gravar os campos aceitos na base'}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium"
        >
          {consolidate.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
          Consolidar na base
        </button>
      </div>

      {consolidated && (
        <div className="rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 p-3 text-sm text-emerald-800 dark:text-emerald-300">
          Consolidado: {consolidated.campos_gravados} campo(s) gravado(s) · {consolidated.matriculas_criadas} matrícula(s) criada(s)
          {consolidated.matriculas_atualizadas > 0 && ` · ${consolidated.matriculas_atualizadas} atualizada(s)`}
          {consolidated.area_total_matriculas != null && ` · área total (soma das matrículas): ${consolidated.area_total_matriculas} ha`}.
        </div>
      )}
    </div>
  );
}
