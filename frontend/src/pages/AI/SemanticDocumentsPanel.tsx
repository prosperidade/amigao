import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface SourceDocument { id: number; filename: string; tipo: string; classificacao_versao: number; review_required: boolean;
  extraction_status?: string; rejeicoes?: { colecao: string; indice: number; motivo: string }[] }
const species = ['certidao_matricula', 'escritura_publica', 'contrato_particular', 'contrato_servico_documental',
  'documento_pessoal', 'documento_representacao', 'comprovante_situacao_cadastral_cpf', 'car', 'ccir', 'itr', 'sigef', 'rat', 'peca_orgao', 'arquivo_geoespacial', 'indeterminada'];
const label = (value: string) => value.replace(/_/g, ' ');

function Classification({ doc, processId }: { doc: SourceDocument; processId: number }) {
  const cache = useQueryClient();
  const [tipo, setTipo] = useState(doc.tipo);
  const [motivo, setMotivo] = useState('');
  const update = useMutation({
    mutationFn: () => api.post(`/evidence/cases/${processId}/documents/${doc.id}/reclassify`, {
      tipo, motivo, expected_version: doc.classificacao_versao,
    }),
    onSuccess: () => cache.invalidateQueries(),
  });
  return <article className="border rounded p-3 space-y-2" data-document-id={doc.id}>
    <p>{doc.filename} — documento {doc.id}</p>
    <p>Classificação: {label(doc.tipo)}{doc.review_required ? ' — revisão necessária' : ''}</p>
    {doc.extraction_status && <p>{doc.extraction_status}</p>}
    {!!doc.rejeicoes?.length && <details><summary>Observações rejeitadas ({doc.rejeicoes.length})</summary>
      <ul>{doc.rejeicoes.map((r, i) => <li key={i}>{r.colecao} — item {r.indice + 1}: {r.motivo}</li>)}</ul>
    </details>}
    <select aria-label={`Espécie do documento ${doc.id}`} value={tipo} onChange={e => setTipo(e.target.value)}>
      {!species.includes(tipo) && <option value={tipo}>{label(tipo)}</option>}
      {species.map(s => <option key={s} value={s}>{label(s)}</option>)}
    </select>
    <input aria-label={`Motivo da reclassificação ${doc.id}`} value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Motivo da reclassificação" />
    <button disabled={!motivo.trim() || !species.includes(tipo) || update.isPending} onClick={() => update.mutate()}>Reclassificar documento</button>
    {update.isError && <p role="alert">Não foi possível reclassificar. Recarregue a classificação.</p>}
  </article>;
}

export default function SemanticDocumentsPanel({ processId }: { processId: number }) {
  const cache = useQueryClient();
  const [id, setId] = useState('');
  const docs = useQuery<SourceDocument[]>({ queryKey: ['semantic-documents', processId],
    queryFn: async () => (await api.get(`/evidence/cases/${processId}/documents`)).data });
  const associate = useMutation({ mutationFn: () => api.post(`/evidence/cases/${processId}/documents/${Number(id)}/associate`),
    onSuccess: async () => { setId(''); await cache.invalidateQueries(); } });
  return <section className="space-y-3" aria-label="Documentos e classificação">
    <h4>Documentos e classificação</h4>
    <label>Documento já recebido
      <input type="number" min="1" aria-label="Número do documento recebido" value={id} onChange={e => setId(e.target.value)} />
    </label>
    <button disabled={!id || associate.isPending} onClick={() => associate.mutate()}>Associar documento ao caso</button>
    {associate.isError && <p role="alert">Documento indisponível ou associado a outro caso.</p>}
    {docs.data?.map(doc => <Classification key={`${doc.id}:${doc.classificacao_versao}`} doc={doc} processId={processId} />)}
  </section>;
}
