/**
 * ContractEditor — Criar / visualizar contrato (Sprint 4)
 */
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ArrowLeft, FileText, Download, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  draft:     { label: 'Rascunho',  cls: 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-500/10 border-slate-300 dark:border-slate-500/20' },
  sent:      { label: 'Enviado',   cls: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20' },
  signed:    { label: 'Assinado', cls: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20' },
  cancelled: { label: 'Cancelado', cls: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20' },
};

export default function ContractEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [pdfError, setPdfError] = useState('');
  const [pdfWarning, setPdfWarning] = useState('');

  const { data: contract, isLoading } = useQuery({
    queryKey: ['contract', id],
    queryFn: async () => {
      const res = await api.get(`/contracts/${id}`);
      return res.data;
    },
    enabled: !!id,
  });

  const generatePdfMutation = useMutation({
    mutationFn: () => api.post(`/contracts/${id}/generate-pdf`),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] });
      setPdfError('');
      setPdfWarning(res?.data?.warning ?? '');
    },
    onError: (err: any) => {
      setPdfWarning('');
      setPdfError(err?.response?.data?.detail ?? 'Erro ao gerar PDF.');
    },
  });

  const downloadMutation = useMutation({
    mutationFn: async () => {
      const res = await api.get(`/contracts/${id}/download`);
      return res.data.download_url as string;
    },
    onSuccess: (url) => {
      window.open(url, '_blank');
    },
    onError: () => setPdfError('Erro ao obter link de download.'),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-gray-500 dark:text-slate-400">Contrato não encontrado.</p>
        <button onClick={() => navigate('/proposals')} className="text-sm text-emerald-600 dark:text-emerald-400 underline">
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
          className="p-2 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">{contract.title}</h1>
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${statusCfg.cls}`}>
              {statusCfg.label}
            </span>
          </div>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">Contrato #{contract.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => generatePdfMutation.mutate()}
            disabled={generatePdfMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-white/10 text-sm font-medium transition-all disabled:opacity-50"
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
        <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-400 text-sm">
          <CheckCircle2 className="w-4 h-4" />
          {pdfWarning ? 'Conteúdo gerado e salvo. Clique para visualizar abaixo.' : 'PDF gerado com sucesso! Clique em "Baixar PDF" para fazer o download.'}
        </div>
      )}
      {pdfWarning && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-yellow-50 dark:bg-yellow-500/10 border border-yellow-200 dark:border-yellow-500/20 text-yellow-700 dark:text-yellow-400 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Storage indisponível — conteúdo salvo no banco</p>
            <p className="text-xs mt-1 text-gray-500 dark:text-slate-400">O texto do contrato foi gerado e está visível abaixo. O download do PDF ficará disponível quando o MinIO estiver acessível.</p>
          </div>
        </div>
      )}
      {pdfError && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <p>{pdfError}</p>
            {pdfError.includes('template') && (
              <p className="text-xs mt-1 text-gray-500 dark:text-slate-400">
                Nenhum template de contrato foi encontrado para este tipo de demanda. Verifique se os templates foram criados no banco de dados.
              </p>
            )}
          </div>
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
          <div key={m.label} className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 p-4">
            <p className="text-xs text-gray-400 dark:text-slate-500 mb-0.5">{m.label}</p>
            <p className="text-sm font-medium text-gray-900 dark:text-white">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Preview do conteúdo */}
      {contract.content ? (
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-6">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
            Conteúdo do Contrato
          </h2>
          <pre className="text-xs text-gray-700 dark:text-slate-300 whitespace-pre-wrap font-mono leading-relaxed max-h-[600px] overflow-y-auto">
            {contract.content}
          </pre>
        </div>
      ) : (
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-12 text-center">
          <FileText className="w-10 h-10 text-gray-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-slate-400 text-sm">Conteúdo ainda não gerado.</p>
          <p className="text-gray-400 dark:text-slate-500 text-xs mt-1">Clique em "Gerar PDF" para preencher o template e gerar o documento.</p>
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
