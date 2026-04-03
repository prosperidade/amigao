import { useState, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { UploadCloud, CheckCircle2, AlertCircle } from 'lucide-react';

interface DocumentUploadProps {
  processId: number;
}

export default function DocumentUpload({ processId }: DocumentUploadProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<null | 'uploading' | 'success' | 'error'>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [progress, setProgress] = useState(0);

  const handleUploadFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    
    try {
      setUploadStatus('uploading');
      setProgress(10);
      setErrorMessage('');
      
      // 1. Get Presigned URL
      const urlRes = await api.post('/documents/upload-url', {
        process_id: processId,
        filename: file.name,
        content_type: file.type || 'application/octet-stream'
      });
      
      const { upload_url, storage_key } = urlRes.data;
      setProgress(40);
      
      // 2. Upload directly to Storage (S3/MinIO) using Fetch to avoid Axios Auth Headers overriding AWS Signature
      const uploadRes = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type || 'application/octet-stream',
        }
      });
      
      if (!uploadRes.ok) {
        throw new Error('Falha no upload binário para o Storage');
      }
      
      setProgress(80);
      
      // 3. Confirm Metadada with the backend
      await api.post('/documents/confirm-upload', {
        process_id: processId,
        storage_key: storage_key,
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        file_size_bytes: file.size,
        document_category: 'geral'
      });
      
      setProgress(100);
      setUploadStatus('success');
      queryClient.invalidateQueries({ queryKey: ['documents', processId] });
      
      setTimeout(() => setUploadStatus(null), 3000); // clear success msg
      
    } catch (err: unknown) {
      console.error(err);
      setUploadStatus('error');
      setErrorMessage(err instanceof Error ? err.message : 'Erro desconhecido ao enviar arquivo');
    }
    
    // reset input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  
  const onDragLeave = () => setIsDragging(false);
  
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleUploadFiles(e.dataTransfer.files);
  };

  return (
    <div className="w-full">
      <div 
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`w-full border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all ${
          isDragging ? 'border-primary bg-primary/5 dark:bg-primary/10' : 'border-gray-200 dark:border-zinc-700 bg-gray-50 dark:bg-zinc-800/50 hover:bg-gray-100 dark:hover:bg-zinc-800'
        }`}
      >
        <UploadCloud className={`w-10 h-10 mb-3 ${isDragging ? 'text-primary' : 'text-gray-400'}`} />
        <p className="font-medium text-gray-700 dark:text-gray-300">
          Clique ou arraste arquivos aqui
        </p>
        <p className="text-xs text-gray-500 mt-1">PDF, DOCX, JPG, PNG até 50MB</p>
        
        <input 
          ref={fileInputRef}
          type="file" 
          className="hidden" 
          onChange={(e) => handleUploadFiles(e.target.files)}
        />
      </div>
      
      {uploadStatus === 'uploading' && (
        <div className="mt-4 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <div className="flex-1">
            <p className="text-sm font-medium text-blue-700 dark:text-blue-400">Enviando arquivo...</p>
            <div className="w-full bg-blue-200 dark:bg-blue-900/40 rounded-full h-1.5 mt-2">
              <div className="bg-blue-600 h-1.5 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      )}
      
      {uploadStatus === 'success' && (
        <div className="mt-4 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 p-3 rounded-lg flex items-center gap-2 text-sm font-medium">
          <CheckCircle2 className="w-5 h-5" /> Arquivo enviado e sincronizado com sucesso!
        </div>
      )}
      
      {uploadStatus === 'error' && (
        <div className="mt-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 p-3 rounded-lg flex items-center gap-2 text-sm font-medium">
          <AlertCircle className="w-5 h-5" /> {errorMessage}
        </div>
      )}
    </div>
  );
}
