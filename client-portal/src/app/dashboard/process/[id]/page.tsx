'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { ArrowLeft, CheckCircle2, Circle, Clock, Download, FileText, Loader2, PlayCircle, MapPin, Upload } from 'lucide-react';
import axios from 'axios';
import clsx from 'clsx';
import { getProcessStatusClass, getProcessStatusLabel } from '@/lib/process-status';

interface ProcessDetails {
  id: number;
  title: string;
  status: string;
  property_id: number | null;
  created_at: string | null;
}

interface TimelineEntry {
  id: number;
  action: string;
  new_value?: string | null;
  created_at: string;
}

interface DocumentItem {
  id: number;
  filename: string;
  file_size_bytes: number;
}

export default function ProcessDetailsClient() {
  const { id } = useParams();
  const router = useRouter();
  const processId = Number(id);
  const [processInfo, setProcessInfo] = useState<ProcessDetails | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(processId)) {
      setLoading(false);
      setErrorMsg('Processo inválido.');
      return;
    }

    fetchData();
  }, [processId]);

  const fetchData = async () => {
    try {
      const [pRes, tRes, dRes] = await Promise.all([
        api.get(`/processes/${processId}`),
        api.get(`/processes/${processId}/timeline`),
        api.get('/documents', { params: { process_id: processId } }),
      ]);

      setProcessInfo(pRes.data);
      setTimeline(tRes.data);
      setDocuments(dRes.data);
      setErrorMsg(null);
    } catch (error: any) {
      const detail = error.response?.data?.detail || error.message || 'Erro ao carregar processo.';
      setErrorMsg(detail);
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = async (docId: number) => {
    try {
      const res = await api.get(`/documents/${docId}/download-url`);
      window.open(res.data.download_url, '_blank');
    } catch {
      window.alert('Erro ao baixar documento.');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setUploading(true);

    try {
      // 1. Pede URL de Upload (Presigned)
      const resParams = await api.post('/documents/upload-url', {
          filename: file.name,
          process_id: processId,
          content_type: file.type || 'application/octet-stream',
      });
      
      const { upload_url, storage_key } = resParams.data;

      // 2. Faz Upload Direto Pro MinIO
      await axios.put(upload_url, file, {
        headers: {
          'Content-Type': file.type || 'application/octet-stream'
        }
      });

      // 3. Confirma pro Backend
      await api.post('/documents/confirm-upload', {
        process_id: processId,
        storage_key,
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        file_size_bytes: file.size,
      });
      
      // 4. Recarrega Lista
      await fetchData();
    } catch {
      window.alert('Erro ao fazer upload do arquivo.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-600 mb-4" />
      </div>
    );
  }

  if (errorMsg) {
    return <div className="text-red-600">{errorMsg}</div>;
  }

  if (!processInfo) return <div>Processo não encontrado.</div>;

  const publicLogs = timeline.filter((log) => log.action === 'status_changed' || log.action === 'created');

  return (
    <div className="max-w-4xl mx-auto pb-12">
      <button 
        onClick={() => router.back()}
        className="flex items-center text-gray-500 hover:text-gray-900 mb-6 font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-2" /> Voltar para Processos
      </button>

      {/* Header Panel */}
      <div className="bg-white rounded-3xl p-8 border border-gray-200 shadow-sm mb-8 relative overflow-hidden">
        <div className="absolute -right-16 -top-16 w-64 h-64 bg-emerald-50 rounded-full blur-3xl opacity-50 z-0"></div>
        <div className="relative z-10">
          <div className="flex gap-3 mb-3">
            <span className={clsx('px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border', getProcessStatusClass(processInfo.status))}>
              {getProcessStatusLabel(processInfo.status)}
            </span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-4">{processInfo.title}</h1>
          <div className="flex flex-wrap items-center gap-6 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-emerald-600" />
              <span className="font-medium">Imóvel: #{processInfo.property_id || 'N/A'}</span>
            </div>
            <div className="flex items-center gap-2">
              <PlayCircle className="w-4 h-4 text-emerald-600" />
              <span>
                Iniciado em:{' '}
                {processInfo.created_at
                  ? new Date(processInfo.created_at).toLocaleDateString('pt-BR')
                  : 'Data indisponível'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-8">
        
        {/* Coluna Principal: Timeline Pública */}
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
              <Clock className="w-5 h-5 text-emerald-600" />
              Histórico Público
            </h2>

            <div className="space-y-6 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-gray-200 before:to-transparent">
              {publicLogs.map((log) => (
                <div key={log.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                  <div className="flex items-center justify-center w-10 h-10 rounded-full border border-white bg-emerald-100 text-emerald-600 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2">
                    {log.action === 'created' ? <CheckCircle2 className="w-5 h-5" /> : <Circle className="w-5 h-5 fill-current" />}
                  </div>
                  
                  <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] bg-gray-50 p-4 rounded-xl border border-gray-100 shadow-sm">
                    <div className="flex items-center justify-between mb-1">
                      <div className="font-bold text-gray-900">
                        {log.action === 'created'
                          ? 'Abertura do Processo'
                          : `Status alterado para ${getProcessStatusLabel(log.new_value)}`}
                      </div>
                      <time className="text-xs font-medium text-emerald-600">
                        {new Date(log.created_at).toLocaleDateString()}
                      </time>
                    </div>
                  </div>
                </div>
              ))}
              {publicLogs.length === 0 && (
                <div className="text-center text-gray-500 py-4">Nenhuma movimentação registrada.</div>
              )}
            </div>
          </div>
        </div>

        {/* Coluna Lateral: Documentos e Evidências */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-600" />
                Documentos Associados
              </h2>
            </div>
            
            <div className="flex flex-col gap-3 mb-6">
              {documents.length > 0 ? (
                documents.map(doc => (
                  <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 hover:bg-emerald-50 border border-gray-100 hover:border-emerald-100 rounded-xl transition-colors group">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-8 h-8 rounded bg-white flex items-center justify-center shadow-sm text-gray-400 group-hover:text-emerald-600">
                        <FileText className="w-4 h-4" />
                      </div>
                      <div className="truncate">
                        <p className="text-sm font-semibold text-gray-800 truncate">{doc.filename || 'Documento'}</p>
                        <p className="text-xs text-gray-500">
                          {doc.file_size_bytes ? `${(doc.file_size_bytes / 1024).toFixed(0)} KB • ` : ''}Validado
                        </p>
                      </div>
                    </div>
                    <button 
                      onClick={() => downloadFile(doc.id)}
                      className="p-2 text-gray-400 hover:text-emerald-600 bg-white shadow-sm rounded-lg border border-gray-100 transition-colors shrink-0"
                      title="Baixar Documento"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                ))
              ) : (
                <div className="text-sm text-gray-500 text-center py-6 bg-gray-50 rounded-xl border border-dashed border-gray-200">
                  Nenhum documento anexado.
                </div>
              )}
            </div>
            
            {/* Upload Area for Client */}
            <div className="border-t border-gray-100 pt-5">
              <p className="text-sm font-medium text-gray-700 mb-3">Enviar Documentação Pendente</p>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                className="hidden"
                accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
              />
              <button 
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="w-full bg-blue-50 hover:bg-blue-100 text-blue-700 font-medium py-3 px-4 rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
                {uploading ? 'Enviando arquivo...' : 'Fazer Upload'}
              </button>
            </div>
            
          </div>
        </div>
      </div>
    </div>
  );
}
