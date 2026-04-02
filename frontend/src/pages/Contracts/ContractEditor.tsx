/**
 * ContractEditor — Criar / visualizar contrato (Sprint 4)
 */
import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ArrowLeft, FileText, Download, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  draft:     { label: 'Rascunho',  cls: 'text-slate-400 bg-slate-500/10 border-slate-500/20' },
  sent:      { label: 'Enviado',   cls: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  signed:    { label: 'Assinado', cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  cancelled: { label: 'Cancelado', cls: 'text-red-400 bg-red-500/10 border-red-500/20' },
};

export default function ContractEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState('');

  const { data: contract, isLoading } = useQuery({
    queryKey: ['contract', id],
    queryFn: async () => {
      const res = await api.get(`/contracts/${id}`);
      return res.data;
    },
    enabled: !!id,
  });

  const { data: templates = [] } = useQuery({
    queryKey: ['contract-templates'],
    queryFn: async () => {
      // Listar templates via endpoint de workflows reutilizando lógica interna
      // Por ora retorna lista vazia; pode ser expandido
      return [];
    },
  });

  const generatePdfMutation = useMutation({
    mutationFn: () => api.post(`/contracts/${id}/generate-pdf`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] });
      setPdfError('');
    },
    onError: (err: any) => {
      setPdfError(err?.response?.data?.detail ?? 'Erro ao gerar PDF.');
    },
  });

  const downloadMutation = useMutation({
    mutationFn: async () => {
      const res = await api.get(`/contracts/${id}/download`);
      return res.data.download_url as string;
    },
    onSuccess: (url) => {
      setPdfUrl(url);
      window.open(url, '_blank');
    },
    onError: () => setPdfError('Erro ao obter link de download.'),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin text-3xl text-slate-500">⟳</div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-slate-400">Contrato não encontrado.</p>
        <button onClick={() => navigate('/proposals')} className="text-sm text-emerald-400 underline">
          Voltar para propostas
        </button>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[contract.status] ?? STATUS_CONFIG.draft;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-white">{contract.title}</h1>
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${statusCfg.cls}`}>
              {statusCfg.label}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-0.5">Contrato #{contract.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => generatePdfMutation.mutate()}
            disabled={generatePdfMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 text-sm font-medium transition-all disabled:opacity-50"
          >
            {generatePdfMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <FileText className="w-4 h-4" />
            }
            {contract.has_pdf ? 'Regenerar PDF' : 'Gerar PDF'}
          </button>
          {contract.has_pdf && (
            <button
              onClick={() => downloadMutation.mutate()}
              disabled={downloadMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium transition-all disabled:opacity-50"
            >
              {downloadMutation.isPending
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Download className="w-4 h-4" />
              }
              Baixar PDF
            </button>
          )}
        </div>
      </div>

      {/* Feedback */}
      {generatePdfMutation.isSuccess && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
          <CheckCircle2 className="w-4 h-4" /> PDF gerado com sucesso! Clique em "Baixar PDF" para fazer o download.
        </div>
      )}
      {pdfError && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4" /> {pdfError}
        </div>
      )}

      {/* Metadados */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Contrato', value: `#${contract.id}` },
          { label: 'Proposta', value: contract.proposal_id ? `#${contract.proposal_id}` : '—' },
          { label: 'Processo', value: contract.process_id ? `#${contract.process_id}` : '—' },
          { label: 'PDF', value: contract.has_pdf ? '✓ Gerado' : 'Pendente' },
        ].map(m => (
          <div key={m.label} className="rounded-xl bg-white/5 border border-white/5 p-4">
            <p className="text-xs text-slate-500 mb-0.5">{m.label}</p>
            <p className="text-sm font-medium text-white">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Preview do conteúdo */}
      {contract.content ? (
        <div className="rounded-2xl bg-white/5 border border-white/10 p-6">
          <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4 text-indigo-400" />
            Conteúdo do Contrato
          </h2>
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed max-h-[600px] overflow-y-auto">
            {contract.content}
          </pre>
        </div>
      ) : (
        <div className="rounded-2xl bg-white/5 border border-dashed border-white/10 p-12 text-center">
          <FileText className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Conteúdo ainda não gerado.</p>
          <p className="text-slate-500 text-xs mt-1">Clique em "Gerar PDF" para preencher o template e gerar o documento.</p>
          <button
            onClick={() => generatePdfMutation.mutate()}
            disabled={generatePdfMutation.isPending}
            className="mt-4 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium transition-all disabled:opacity-50 flex items-center gap-2 mx-auto"
          >
            {generatePdfMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            Gerar PDF Agora
          </button>
        </div>
      )}
    </div>
  );
}
