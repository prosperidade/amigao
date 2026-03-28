import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Plus, Search, FileText, Clock, AlertCircle, X, CheckCircle2, Circle, Download } from 'lucide-react';
import DocumentUpload from '@/components/DocumentUpload';

interface Process {
  id: number;
  title: string;
  description: string;
  client_id: number;
  status: string;
  step: number;
  created_at: string;
}

const COLUMNS = [
  { id: 'lead', label: 'Lead', color: 'bg-gray-100 border-gray-200 text-gray-700' },
  { id: 'triagem', label: 'Triagem', color: 'bg-blue-50 border-blue-200 text-blue-700' },
  { id: 'diagnostico', label: 'Diagnóstico', color: 'bg-indigo-50 border-indigo-200 text-indigo-700' },
  { id: 'planejamento', label: 'Planejamento', color: 'bg-purple-50 border-purple-200 text-purple-700' },
  { id: 'execucao', label: 'Execução', color: 'bg-teal-50 border-teal-200 text-teal-700' },
  { id: 'protocolo', label: 'Protocolo', color: 'bg-orange-50 border-orange-200 text-orange-700' },
  { id: 'aguardando_orgao', label: 'Aguardando Órgão', color: 'bg-yellow-50 border-yellow-200 text-yellow-700' },
  { id: 'pendencia_orgao', label: 'Pendência Órgão', color: 'bg-red-50 border-red-200 text-red-700' },
  { id: 'concluido', label: 'Concluído', color: 'bg-green-50 border-green-200 text-green-700' },
];

export default function ProcessesPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  const [selectedProcess, setSelectedProcess] = useState<Process | null>(null);
  const [activeTab, setActiveTab] = useState('tasks');
  const [newTaskTitle, setNewTaskTitle] = useState('');
  
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    client_id: '',
    process_type: 'licenciamento'
  });

  const { data: processes, isLoading } = useQuery({
    queryKey: ['processes'],
    queryFn: async () => {
      const res = await api.get('/processes/');
      return res.data as Process[];
    }
  });

  const { data: clients } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => {
      const res = await api.get('/clients/');
      return res.data as any[];
    }
  });

  const createMutation = useMutation({
    mutationFn: (newProcess: any) => api.post('/processes/', {
      ...newProcess,
      client_id: parseInt(newProcess.client_id)
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['processes'] });
      setIsModalOpen(false);
      setFormData({ title: '', description: '', client_id: '', process_type: 'licenciamento' });
    }
  });

  const updateStatusMutation = useMutation({
    mutationFn: (data: { id: number, status: string }) => api.post(`/processes/${data.id}/status`, { status: data.status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['processes'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Erro ao alterar o status do processo. Verifique dependências.');
    }
  });

  const { data: processTasks, refetch: refetchTasks } = useQuery({
    queryKey: ['tasks', selectedProcess?.id],
    queryFn: async () => {
      const res = await api.get(`/tasks/?process_id=${selectedProcess?.id}`);
      return res.data as any[];
    },
    enabled: !!selectedProcess,
  });

  const { data: processTimeline } = useQuery({
    queryKey: ['timeline', selectedProcess?.id],
    queryFn: async () => {
      const res = await api.get(`/processes/${selectedProcess?.id}/timeline`);
      return res.data as any[];
    },
    enabled: !!selectedProcess,
  });

  const { data: processDocuments } = useQuery({
    queryKey: ['documents', selectedProcess?.id],
    queryFn: async () => {
      const res = await api.get(`/documents/?process_id=${selectedProcess?.id}`);
      return res.data as any[];
    },
    enabled: !!selectedProcess,
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
    } catch (err) {
      alert('Erro ao gerar link de download seguro.');
    }
  };

  const createTaskMutation = useMutation({
    mutationFn: (title: string) => api.post('/tasks/', { title, process_id: selectedProcess?.id }),
    onSuccess: () => {
      setNewTaskTitle('');
      refetchTasks();
    }
  });

  const toggleTaskMutation = useMutation({
    mutationFn: (task: any) => api.patch(`/tasks/${task.id}/`, { status: task.status === 'done' ? 'todo' : 'done' }),
    onSuccess: () => {
      refetchTasks();
    }
  });

  const handleDragStart = (e: React.DragEvent, processId: number) => {
    e.dataTransfer.setData('processId', processId.toString());
  };

  const handleDrop = (e: React.DragEvent, newStatus: string) => {
    e.preventDefault();
    const processId = e.dataTransfer.getData('processId');
    if (processId) {
      updateStatusMutation.mutate({ id: parseInt(processId), status: newStatus });
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const filteredProcesses = processes?.filter(p => 
    p.title.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">Processos (Kanban)</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Acompanhe e mova os processos pelo funil operacional.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative w-64 hidden md:block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input 
              type="text"
              placeholder="Buscar processo..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all dark:text-zinc-200"
            />
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="bg-primary text-white px-4 py-2 flex items-center gap-2 rounded-lg hover:bg-primary/90 transition-colors shadow-sm font-medium text-sm"
          >
            <Plus className="w-4 h-4" /> Novo Processo
          </button>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4">
        <div className="flex gap-4 h-full min-w-max items-start">
          {COLUMNS.map(column => (
            <div 
              key={column.id} 
              className="w-80 flex flex-col h-full bg-gray-50/50 dark:bg-zinc-900/30 rounded-xl"
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, column.id)}
            >
              <div className={`p-3 rounded-t-xl border-b font-medium text-sm flex items-center justify-between ${column.color} dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200`}>
                <span>{column.label}</span>
                <span className="bg-white/50 dark:bg-black/20 px-2 py-0.5 rounded-full text-xs">
                  {filteredProcesses.filter(p => p.status === column.id).length}
                </span>
              </div>
              
              <div className="p-3 flex-1 overflow-y-auto space-y-3 custom-scrollbar">
                {isLoading ? (
                  <div className="text-center text-xs text-gray-400 py-4">Carregando...</div>
                ) : (
                  filteredProcesses
                    .filter(p => p.status === column.id)
                    .map(process => (
                      <div
                        key={process.id}
                        draggable
                        onDragStart={(e) => handleDragStart(e, process.id)}
                        onClick={() => setSelectedProcess(process)}
                        className="bg-white dark:bg-zinc-900 p-4 rounded-xl shadow-sm border border-gray-100 dark:border-zinc-800 cursor-pointer hover:border-primary/30 dark:hover:border-primary/30 transition-colors group"
                      >
                        <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1 line-clamp-2">{process.title}</h4>
                        <div className="flex items-center gap-2 text-xs text-gray-500 mb-3">
                          <FileText className="w-3 h-3" />
                         <span className="truncate">{clients?.find(c => c.id === process.client_id)?.full_name || 'Cliente Desconhecido'}</span>
                        </div>
                        <div className="flex items-center justify-between pt-3 border-t border-gray-50 dark:border-zinc-800">
                          <span className="text-xs text-gray-400 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(process.created_at).toLocaleDateString()}
                          </span>
                          <span className="text-xs font-medium text-gray-400">ID: #{process.id}</span>
                        </div>
                      </div>
                    ))
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-gray-100 dark:border-zinc-800">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">Novo Processo</h2>
            </div>
            
            <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate(formData); }} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Título do Processo</label>
                <input required
                  type="text" value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Cliente Vinculado</label>
                <select required
                  value={formData.client_id} onChange={e => setFormData({...formData, client_id: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                >
                  <option value="">Selecione um cliente...</option>
                  {clients?.map((c: any) => (
                    <option key={c.id} value={c.id}>{c.full_name} ({c.cpf_cnpj || 'Sem doc'})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Descrição / Observações (Opcional)</label>
                <textarea 
                  rows={3}
                  value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all resize-none"
                />
              </div>

              <div className="pt-4 flex justify-end gap-3 border-t border-gray-100 dark:border-zinc-800 mt-6">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-5 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 rounded-lg hover:bg-gray-50 dark:hover:bg-zinc-700 transition-colors">
                  Cancelar
                </button>
                <button type="submit" disabled={createMutation.isPending} className="px-5 py-2.5 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-lg transition-colors shadow-sm disabled:opacity-50">
                  Criar Processo
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Side Drawer for Process Details */}
      {selectedProcess && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setSelectedProcess(null)} />
          <div className="relative w-full max-w-md bg-white dark:bg-zinc-900 h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
            <div className="p-6 border-b border-gray-100 dark:border-zinc-800 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-1">{selectedProcess.title}</h2>
                <div className="flex gap-2 text-sm text-gray-500">
                  <span>#{selectedProcess.id}</span>
                  <span>•</span>
                  <span>{clients?.find(c => c.id === selectedProcess.client_id)?.full_name || 'Sem cliente'}</span>
                </div>
              </div>
              <button onClick={() => setSelectedProcess(null)} className="p-2 -mr-2 text-gray-400 hover:text-gray-900 dark:hover:text-white rounded-lg transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-6 border-b border-gray-100 dark:border-zinc-800 flex gap-6 text-sm font-medium text-gray-500 dark:text-gray-400">
              <button onClick={() => setActiveTab('details')} className={`py-4 border-b-2 transition-colors ${activeTab === 'details' ? 'border-primary text-primary' : 'border-transparent hover:text-gray-900 dark:hover:text-white'}`}>Detalhes</button>
              <button onClick={() => setActiveTab('tasks')} className={`py-4 border-b-2 transition-colors ${activeTab === 'tasks' ? 'border-primary text-primary' : 'border-transparent hover:text-gray-900 dark:hover:text-white'}`}>Tarefas</button>
              <button onClick={() => setActiveTab('timeline')} className={`py-4 border-b-2 transition-colors ${activeTab === 'timeline' ? 'border-primary text-primary' : 'border-transparent hover:text-gray-900 dark:hover:text-white'}`}>Timeline</button>
              <button onClick={() => setActiveTab('documents')} className={`py-4 border-b-2 transition-colors ${activeTab === 'documents' ? 'border-primary text-primary' : 'border-transparent hover:text-gray-900 dark:hover:text-white'}`}>Docs</button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {activeTab === 'details' && (
                <div className="space-y-4">
                  <div>
                    <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Descrição</h4>
                    <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{selectedProcess.description || 'Nenhuma descrição fornecida.'}</p>
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Criado em</h4>
                    <p className="text-gray-700 dark:text-gray-300">{new Date(selectedProcess.created_at).toLocaleString()}</p>
                  </div>
                </div>
              )}

              {activeTab === 'tasks' && (
                <div className="space-y-6">
                  <form onSubmit={(e) => { e.preventDefault(); createTaskMutation.mutate(newTaskTitle); }} className="flex gap-2">
                    <input 
                      type="text" required placeholder="Nova tarefa..."
                      value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 outline-none text-sm"
                    />
                    <button type="submit" disabled={createTaskMutation.isPending} className="bg-primary text-white px-3 py-2 rounded-lg font-medium hover:bg-primary/90 text-sm">
                      Adicionar
                    </button>
                  </form>

                  <div className="space-y-2">
                    {processTasks?.length === 0 ? (
                      <p className="text-sm text-gray-500 text-center py-4">Nenhuma tarefa criada.</p>
                    ) : (
                      processTasks?.map(task => (
                        <div key={task.id} className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-zinc-800/50 rounded-lg border border-gray-100 dark:border-zinc-800 group">
                          <button onClick={() => toggleTaskMutation.mutate(task)} className="text-gray-400 hover:text-primary transition-colors">
                            {task.status === 'done' ? <CheckCircle2 className="w-5 h-5 text-green-500" /> : <Circle className="w-5 h-5" />}
                          </button>
                          <span className={`text-sm font-medium ${task.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-800 dark:text-gray-200'}`}>
                            {task.title}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'timeline' && (
                <div className="relative pl-6 border-l-2 border-gray-100 dark:border-zinc-800 space-y-6 py-2">
                  {processTimeline?.length === 0 ? (
                    <p className="text-sm text-gray-500 text-center">Nenhum evento registrado.</p>
                  ) : (
                    processTimeline?.map((log: any) => (
                      <div key={log.id} className="relative">
                        <div className="absolute -left-[31px] bg-white dark:bg-zinc-900 p-1">
                          <div className="w-3 h-3 bg-primary rounded-full ring-4 ring-white dark:ring-zinc-900" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-900 dark:text-white">
                            {log.action === 'status_changed' ? 'Mudança de Status' : log.details}
                          </p>
                          {log.action === 'status_changed' && (
                            <p className="text-sm text-gray-500 mt-0.5">De <span className="font-semibold">{log.old_value}</span> para <span className="font-semibold text-primary">{log.new_value}</span></p>
                          )}
                          <span className="text-xs text-gray-400 mt-1 block">{new Date(log.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
              {activeTab === 'documents' && (
                <div className="space-y-6">
                  <DocumentUpload processId={selectedProcess.id} />
                  
                  <div className="space-y-2 mt-6">
                    <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Arquivos Anexados</h4>
                    {processDocuments?.length === 0 ? (
                      <p className="text-sm text-gray-500 text-center py-4 bg-gray-50 dark:bg-zinc-800/30 rounded-lg">Nenhum documento anexado.</p>
                    ) : (
                      <div className="space-y-2">
                        {processDocuments?.map(doc => (
                          <div key={doc.id} className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between p-3 bg-white dark:bg-zinc-900 border border-gray-100 dark:border-zinc-800 rounded-lg hover:border-primary/30 transition-colors">
                            <div className="flex items-center gap-3 overflow-hidden">
                              <div className="w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 flex items-center justify-center shrink-0">
                                <FileText className="w-5 h-5" />
                              </div>
                              <div className="min-w-0">
                                <p className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate" title={doc.filename}>{doc.filename}</p>
                                <p className="text-xs text-gray-500">
                                  {(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB • {new Date(doc.created_at).toLocaleDateString()}
                                </p>
                              </div>
                            </div>
                            <button 
                              onClick={() => handleDownload(doc.id, doc.filename)}
                              className="w-full sm:w-auto flex items-center justify-center gap-2 px-3 py-1.5 bg-gray-50 dark:bg-zinc-800 hover:bg-gray-100 dark:hover:bg-zinc-700 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-lg transition-colors border border-gray-200 dark:border-zinc-700 hover:border-gray-300 dark:hover:border-zinc-600 focus:ring-2 focus:ring-primary/20 outline-none"
                            >
                              <Download className="w-4 h-4" /> Baixar
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
