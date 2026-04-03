/**
 * DocumentUploadZone — Sprint 2
 * Upload com drag-and-drop, categorização por tipo e vinculação automática
 * ao item de checklist correspondente.
 */
import { useState, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { UploadCloud, CheckCircle2, AlertCircle, Tag } from 'lucide-react';

// ─── Tipos de documento disponíveis para categorização rápida ─────────────────

const DOC_TYPES = [
  { value: '',            label: 'Selecionar tipo...' },
  { value: 'car',         label: '🌿 CAR' },
  { value: 'matricula',   label: '📄 Matrícula' },
  { value: 'ccir',        label: '📋 CCIR' },
  { value: 'caf',         label: '🌾 CAF/DAP' },
  { value: 'doc_pessoal', label: '👤 Doc. Pessoal' },
  { value: 'mapa',        label: '🗺️ Mapa/Shapefile' },
  { value: 'laudo',       label: '🔬 Laudo' },
  { value: 'notificacao', label: '⚠️ Notificação/Auto' },
  { value: 'licenca',     label: '📜 Licença' },
  { value: 'planta',      label: '🏗️ Planta/Croqui' },
  { value: 'foto',        label: '📷 Fotos' },
  { value: 'contrato',    label: '📝 Contrato' },
  { value: 'declaracao',  label: '📃 Declaração' },
  { value: 'carta_banco', label: '🏦 Carta Bancária' },
  { value: 'outorga',     label: '💧 Outorga' },
  { value: 'auto_infracao', label: '⚖️ Auto de Infração' },
  { value: 'outro',       label: '📁 Outro' },
];

interface DocumentUploadZoneProps {
  processId: number;
  /** Se informado, vincula o upload diretamente a este item de checklist */
  checklistItemId?: string;
  /** doc_type pré-selecionado (ao clicar "Upload" direto de um item) */
  defaultDocType?: string;
  onUploadSuccess?: () => void;
}

export default function DocumentUploadZone({
  processId,
  checklistItemId,
  defaultDocType = '',
  onUploadSuccess,
}: DocumentUploadZoneProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [selectedDocType, setSelectedDocType] = useState(defaultDocType);
  const [uploadState, setUploadState] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [progress, setProgress] = useState(0);
  const [lastFileName, setLastFileName] = useState('');

  const doUpload = async (file: File) => {
    try {
      setUploadState('uploading');
      setProgress(10);
      setErrorMessage('');
      setLastFileName(file.name);

      // 1. Presigned URL
      const urlRes = await api.post('/documents/upload-url', {
        process_id: processId,
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      });
      const { upload_url, storage_key } = urlRes.data;
      setProgress(40);

      // 2. Upload binário direto para MinIO/S3
      const uploadRes = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
      });
      if (!uploadRes.ok) throw new Error('Falha no upload para o storage.');
      setProgress(80);

      // 3. Confirmar metadados
      await api.post('/documents/confirm-upload', {
        process_id: processId,
        storage_key,
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        file_size_bytes: file.size,
        document_type: selectedDocType || undefined,
        document_category: _inferCategory(selectedDocType),
        checklist_item_id: checklistItemId || undefined,
      });

      setProgress(100);
      setUploadState('success');

      queryClient.invalidateQueries({ queryKey: ['documents', processId] });
      queryClient.invalidateQueries({ queryKey: ['checklist', processId] });
      onUploadSuccess?.();

      setTimeout(() => setUploadState('idle'), 3500);
    } catch (err: unknown) {
      console.error(err);
      setUploadState('error');
      setErrorMessage(err instanceof Error ? err.message : 'Erro desconhecido.');
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    doUpload(files[0]);
  };

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const onDragLeave = () => setIsDragging(false);
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="space-y-3">
      {/* Seletor de tipo */}
      <div className="flex items-center gap-2">
        <Tag className="w-4 h-4 text-gray-400 dark:text-slate-500 shrink-0" />
        <select
          value={selectedDocType}
          onChange={e => setSelectedDocType(e.target.value)}
          className="flex-1 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-300 text-sm px-3 py-2 focus:outline-none focus:border-emerald-500 dark:focus:border-emerald-400 transition-colors"
        >
          {DOC_TYPES.map(dt => (
            <option key={dt.value} value={dt.value} className="bg-white dark:bg-slate-900">
              {dt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => uploadState === 'idle' && fileInputRef.current?.click()}
        className={`w-full border-2 border-dashed rounded-xl p-7 flex flex-col items-center justify-center transition-all cursor-pointer ${
          isDragging
            ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-500/10'
            : uploadState === 'success'
            ? 'border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/5 cursor-default'
            : uploadState === 'error'
            ? 'border-red-300 dark:border-red-500/40 bg-red-50 dark:bg-red-500/5 cursor-default'
            : 'border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/3 hover:border-gray-300 dark:hover:border-white/20 hover:bg-gray-100 dark:hover:bg-white/5'
        }`}
      >
        {uploadState === 'success' ? (
          <>
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mb-2" />
            <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">Enviado com sucesso!</p>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5 truncate max-w-xs">{lastFileName}</p>
          </>
        ) : uploadState === 'error' ? (
          <>
            <AlertCircle className="w-8 h-8 text-red-500 mb-2" />
            <p className="text-sm font-medium text-red-700 dark:text-red-300">Falha no envio</p>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">{errorMessage}</p>
            <button
              onClick={e => { e.stopPropagation(); setUploadState('idle'); }}
              className="mt-3 text-xs text-gray-500 dark:text-slate-400 underline hover:text-gray-800 dark:hover:text-white"
            >
              Tentar novamente
            </button>
          </>
        ) : uploadState === 'uploading' ? (
          <>
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3" />
            <p className="text-sm text-gray-700 dark:text-slate-300 font-medium">Enviando {lastFileName}...</p>
            <div className="w-48 bg-gray-200 dark:bg-white/10 rounded-full h-1.5 mt-3">
              <div
                className="bg-emerald-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </>
        ) : (
          <>
            <UploadCloud className={`w-8 h-8 mb-2 ${isDragging ? 'text-emerald-500' : 'text-gray-400 dark:text-slate-500'}`} />
            <p className="text-sm font-medium text-gray-600 dark:text-slate-300">
              {isDragging ? 'Solte o arquivo aqui' : 'Clique ou arraste um arquivo'}
            </p>
            <p className="text-xs text-gray-400 dark:text-slate-600 mt-0.5">PDF, DOCX, JPG, PNG — até 50 MB</p>
          </>
        )}

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
        />
      </div>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function _inferCategory(docType: string): string {
  const map: Record<string, string> = {
    car: 'ambiental', laudo: 'ambiental', licenca: 'ambiental',
    matricula: 'fundiario', ccir: 'fundiario', contrato: 'fundiario', declaracao: 'fundiario', outorga: 'fundiario',
    doc_pessoal: 'pessoal',
    mapa: 'geoespacial',
    planta: 'tecnico', foto: 'tecnico',
    notificacao: 'administrativo', auto_infracao: 'administrativo',
    carta_banco: 'bancario', caf: 'fundiario',
  };
  return map[docType] || 'geral';
}
