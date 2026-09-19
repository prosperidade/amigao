import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import SemanticDocumentsPanel from './SemanticDocumentsPanel';

interface EvidenceObject {
  id: string;
  version: number;
  kind: string;
  statement: string | null;
  attributes: { predicate?: string; literal?: unknown; role?: string; document_id?: number };
  knowledge: { state: string; justification?: string };
  premises: { id: string; version: number }[];
}
interface EvidenceRow {
  object: EvidenceObject;
  revision: number;
  stale: boolean;
  review: { action: string; author: number; justification: string; at: string } | null;
  history?: { action: string; author: number; justification: string; at: string; revision: number }[];
}
interface Execution {
  id: string;
  revision: number;
  status: string;
  waiting_reason: string | null;
  steps: { agent: string; status: string; error?: string }[];
}
interface EvidenceData {
  objects: EvidenceRow[];
  executions: Execution[];
}

const labels: Record<string, string> = {
  completed: 'Passo concluído', awaiting_review: 'Aguardando revisão', pending: 'Pendente',
  capacidade_insuficiente: 'CAPACIDADE INSUFICIENTE', agente_desativado: 'Agente desativado',
  failed: 'Falha', aprovar: 'Aprovada', rejeitar: 'Rejeitada', corrigir: 'Substituída por correção',
  nao_aplicavel: 'Não aplicável',
};

function ReviewCard({ row, latest, processId }: { row: EvidenceRow; latest: boolean; processId: number }) {
  const cache = useQueryClient();
  const [justification, setJustification] = useState('');
  const [correction, setCorrection] = useState(row.object.statement || '');
  const mutation = useMutation({
    mutationFn: async (action: string) => api.post(
      `/evidence/cases/${processId}/objects/${encodeURIComponent(row.object.id)}/review`, {
        expected_version: row.object.version, expected_revision: row.revision, action, justification,
        ...(action === 'corrigir' ? { correction: { ...row.object, statement: correction } } : {}),
      }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['case-evidence', processId] }),
  });
  return <article className="rounded-lg border p-3 space-y-2">
    <p>{row.object.statement || row.object.attributes.predicate} <span className="text-xs">— versão {row.object.version}</span></p>
    {row.object.kind === 'observacao' && <>
      <p>Documento {row.object.attributes.document_id} — declaração extraída{row.object.attributes.role ? ` — ${row.object.attributes.role}` : ''}</p>
      <p className="text-sm whitespace-pre-wrap">{String(row.object.attributes.literal ?? '')}</p>
    </>}
    <p className="text-sm">{row.stale ? 'Desatualizada — pendência de coleta dependente' : labels[row.review?.action || 'pending']}</p>
    {row.review && <p className="text-xs">Decisão de {new Date(row.review.at).toLocaleString('pt-BR')} — {row.review.justification}</p>}
    {!!row.history?.length && <details><summary className="text-sm">Histórico de decisões</summary>
      {row.history.map(r => <p key={r.revision} className="text-xs">{labels[r.action] || r.action} — consultor {r.author} — {new Date(r.at).toLocaleString('pt-BR')} — {r.justification}</p>)}
    </details>}
    <details><summary className="text-sm">Evidência e premissas</summary>
      <p className="text-xs">Conhecimento: {row.object.knowledge.state}</p>
      <p className="text-xs">{row.object.premises.length} premissa(s) versionada(s). Consulte a linhagem preservada:</p>
      <SourceButton processId={processId} reference={row.object} />
      {row.object.premises.map(ref => <SourceButton key={`${ref.id}:${ref.version}`} processId={processId} reference={ref} />)}
    </details>
    {latest && row.object.kind === 'conclusao' && <>
      <label className="block text-sm">Justificativa
        <textarea aria-label="Justificativa da revisão" value={justification} onChange={e => setJustification(e.target.value)} className="block w-full rounded border p-2 text-gray-900" />
      </label>
      <label className="block text-sm">Texto corrigido (cria versão pendente de aprovação)
        <textarea aria-label="Texto corrigido" value={correction} onChange={e => setCorrection(e.target.value)} className="block w-full rounded border p-2 text-gray-900" />
      </label>
      <div className="flex flex-wrap gap-2">
        {(['aprovar', 'corrigir', 'rejeitar', 'nao_aplicavel'] as const).map(action =>
          <button key={action} disabled={!justification.trim() || mutation.isPending || (row.stale && action !== 'corrigir')}
            onClick={() => mutation.mutate(action)} className="rounded border px-3 py-1 disabled:opacity-40">
            {{ aprovar: 'Aprovar', corrigir: 'Criar correção', rejeitar: 'Rejeitar', nao_aplicavel: 'Não aplicável' }[action]}
          </button>)}
      </div>
      {mutation.isError && <p role="alert">Não foi possível registrar a revisão. Recarregue para conferir versões e premissas.</p>}
    </>}
  </article>;
}

function SourceButton({ processId, reference }: { processId: number; reference: { id: string; version: number } }) {
  const [open, setOpen] = useState(false);
  const source = useQuery<{ object: EvidenceObject; source: { text?: string } | null }>({
    queryKey: ['evidence-source', processId, reference.id, reference.version], enabled: open,
    queryFn: async () => (await api.get(`/evidence/cases/${processId}/sources/${encodeURIComponent(reference.id)}/versions/${reference.version}`)).data,
  });
  return <div className="text-xs">
    <button className="underline" onClick={() => setOpen(!open)}>{reference.id} — versão {reference.version}</button>
    {open && source.data && <div className="border-l pl-2 whitespace-pre-wrap">
      <p>{source.data.source?.text || source.data.object.statement || JSON.stringify(source.data.object.attributes.literal ?? source.data.object.attributes)}</p>
      {source.data.object.premises.map(ref => <SourceButton key={`${ref.id}:${ref.version}`} processId={processId} reference={ref} />)}
    </div>}
    {open && source.isError && <p role="alert">Fonte não recuperada.</p>}
  </div>;
}

export default function EvidencePanel({ processId }: { processId: number }) {
  const cache = useQueryClient();
  const [history, setHistory] = useState(false);
  const query = useQuery<EvidenceData>({
    queryKey: ['case-evidence', processId],
    queryFn: async () => (await api.get(`/evidence/cases/${processId}`)).data,
    refetchInterval: 5000,
  });
  const resume = useMutation({
    mutationFn: async ({ execution, recompute = false }: { execution: Execution; recompute?: boolean }) => api.post(`/evidence/executions/${execution.id}/resume`, { expected_revision: execution.revision, recompute_stale: recompute }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['case-evidence', processId] }),
  });
  const collect = useMutation({
    mutationFn: async () => api.post(`/evidence/cases/${processId}/return-to-collection`),
    onSuccess: async () => { await cache.invalidateQueries(); },
  });
  if (query.isPending) return <p>Carregando revisão e execuções…</p>;
  if (query.isError) return <p role="alert">Não foi possível consultar as decisões. Tente recarregar.</p>;
  const latest = new Map<string, number>();
  for (const row of query.data.objects) latest.set(row.object.id, Math.max(latest.get(row.object.id) || 0, row.object.version));
  const conclusions = query.data.objects.filter(r => r.object.kind === 'conclusao');
  return <section className="rounded-xl border p-5 space-y-3">
    <SemanticDocumentsPanel processId={processId} />
    <h4 className="font-semibold">Revisão das conclusões e retomada</h4>
    <p className="text-sm">A correção cria nova versão pendente. Só conclusões aprovadas e vigentes entram na análise seguinte.</p>
    <label className="text-sm"><input type="checkbox" checked={history} onChange={e => setHistory(e.target.checked)} /> Mostrar versões anteriores</label>
    <details><summary>Observações documentais</summary>
      {query.data.objects.filter(r => r.object.kind === 'observacao' && (history || latest.get(r.object.id) === r.object.version)).map(row =>
        <ReviewCard key={`${row.object.id}:${row.object.version}`} row={row} latest={latest.get(row.object.id) === row.object.version} processId={processId} />)}
    </details>
    {conclusions.filter(r => history || latest.get(r.object.id) === r.object.version).map(row =>
      <ReviewCard key={`${row.object.id}:${row.object.version}`} row={row} latest={latest.get(row.object.id) === row.object.version} processId={processId} />)}
    {conclusions.some(r => r.stale) && <button className="rounded border px-3 py-2" disabled={collect.isPending} onClick={() => collect.mutate()}>
      Voltar à coleta por pendência dependente
    </button>}
    {query.data.executions.map(execution => <div key={execution.id} className="rounded border p-3">
      <p>{labels[execution.status] || execution.status}</p>
      {execution.steps.map(step => <p key={step.agent} className="text-sm">{step.agent}: {labels[step.status] || step.status}{step.error ? ` — ${step.error}` : ''}</p>)}
      {execution.waiting_reason && <p className="text-sm">{execution.waiting_reason}</p>}
      {execution.status !== 'completed' && <button disabled={resume.isPending} onClick={() => resume.mutate({ execution })} className="rounded border px-3 py-1">Retomar execução</button>}
      {conclusions.some(r => r.stale) && <button disabled={resume.isPending} onClick={() => resume.mutate({ execution, recompute: true })} className="rounded border px-3 py-1">Reavaliar premissas alteradas</button>}
    </div>)}
    {(resume.isError || collect.isError) && <p role="alert">Conflito ou falha na operação. Recarregue o estado antes de tentar novamente.</p>}
  </section>;
}
