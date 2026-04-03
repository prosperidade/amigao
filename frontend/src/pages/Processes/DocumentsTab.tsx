import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { FileText, Download } from 'lucide-react';
import { Document } from './ProcessDetailTypes';
import ProcessChecklist from './ProcessChecklist';
import DocumentUploadZone from '@/components/DocumentUploadZone';

interface DocumentsTabProps {
  processId: number;
}

export default function DocumentsTab({ processId }: DocumentsTabProps) {
  const { data: documents, refetch: refetchDocuments } = useQuery({
    queryKey: ['documents', processId],
    queryFn: async () => {
      const res = await api.get(`/documents/?process_id=${processId}`);
      return res.data as Document[];
    },
    enabled: !!processId,
  });

  const handleDownload = async (docId: number, filename: string) => {
    try {
      const res = await api.get(`/documents/${docId}/download-url`);
      const link = document.createElement('a');
      link.href = res.data.download_url;
      link.target = '_blank';
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch {
      alert('Erro ao gerar link de download.');
    }
  };

  return (
    <div className="space-y-5">
      <ProcessChecklist processId={processId} />

      <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3">Enviar Documento</h3>
        <DocumentUploadZone
          processId={processId}
          onUploadSuccess={() => refetchDocuments()}
        />
      </div>

      {(documents?.length ?? 0) > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider px-1">
            Documentos Enviados
          </p>
          {documents?.map(doc => (
            <div key={doc.id} className="flex items-center gap-4 p-4 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-200 dark:hover:border-white/10 transition-colors">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-500/20 flex items-center justify-center shrink-0">
                <FileText className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 dark:text-white truncate">{doc.filename || doc.original_file_name}</p>
                <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                  {(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                  {doc.document_type && ` \u00b7 ${doc.document_type}`}
                  {' \u00b7 '}{new Date(doc.created_at).toLocaleDateString('pt-BR')}
                </p>
              </div>
              <button
                onClick={() => handleDownload(doc.id, doc.filename || doc.original_file_name || 'download')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 text-sm transition-all"
              >
                <Download className="w-3.5 h-3.5" /> Baixar
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
