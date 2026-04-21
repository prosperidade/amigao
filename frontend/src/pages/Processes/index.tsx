import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { Plus, Search, FileText, Clock, LayoutGrid, Columns3 } from 'lucide-react';
import { AxiosError } from 'axios';
import QuadroAcoes from './QuadroAcoes';

// CAM3PR-001 (Sprint N) — "Cadastro cria, Workspace executa, Fluxo coordena".
// O Kanban legado aqui é somente coordenação (mover/listar). Clicar num card
// redireciona para o Workspace (/processes/:id) — não abre mais modal profunda.

interface Process {
  id: number;
  title: string;
  description: string;
  client_id: number;
  status: string;
  step: number;
  created_at: string;
}

interface Client {
  id: number;
  full_name: string;
  cpf_cnpj?: string;
}

interface CreateProcessPayload {
  title: string;
  description: string;
  client_id: string;
  process_type: string;
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

type ViewMode = 'quadro' | 'kanban';

export default function ProcessesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  // CAM3PR-001 — Quadro de Ações (7 etapas Regente) é o modo default.
  // Kanban legado (9 colunas status) fica como fallback opcional. localStorage
  // respeita a preferência anterior do usuário para não empurrar mudança forçada.
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    try {
      const stored = localStorage.getItem('processes-view');
      return stored === 'kanban' ? 'kanban' : 'quadro';
    } catch {
      return 'quadro';
    }
  });

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
      return res.data as Client[];
    }
  });

  const createMutation = useMutation({
    mutationFn: (newProcess: CreateProcessPayload) => api.post('/processes/', {
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
    onError: (err: AxiosError<{ detail?: string }>) => {
      toast.error(err.response?.data?.detail || 'Erro ao alterar o status do processo. Verifique dependências.');
    }
  });

  // CAM3PR-001 — tasks/timeline/documents/upload vivem no Workspace agora.
  // Aqui mantemos só o que o Kanban legado precisa: listar, mover por drag e criar processo.

  // Quadro de Ações (macroetapas) — early return APÓS todos os hooks
  if (viewMode === 'quadro') {
    return (
      <div className="h-full flex flex-col">
        <div className="flex justify-end mb-2 shrink-0">
          <button
            onClick={() => setViewMode('kanban')}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 dark:hover:text-white transition-colors px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-zinc-800 border border-gray-200 dark:border-zinc-700"
          >
            <Columns3 className="w-3.5 h-3.5" /> Voltar ao Kanban
          </button>
        </div>
        <div className="flex-1 min-h-0">
          <QuadroAcoes />
        </div>
      </div>
    );
  }

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
          <button
            onClick={() => { setViewMode('quadro'); try { localStorage.setItem('processes-view', 'quadro'); } catch { /* */ } }}
            className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors px-3 py-2 rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800"
          >
            <LayoutGrid className="w-3.5 h-3.5" /> Quadro de Ações (7 Etapas)
          </button>
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
                        onClick={() => navigate(`/processes/${process.id}`)}
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
                  {clients?.map((c) => (
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

    </div>
  );
}
