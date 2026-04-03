import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Plus, Search, MapPin, User as UserIcon, AlertTriangle } from 'lucide-react';

interface Property {
  id: number;
  client_id: number;
  name: string;
  car_code: string | null;
  total_area_ha: number | null;
  municipality: string | null;
  state: string | null;
  has_embargo: boolean;
  status: string;
}

export default function PropertiesPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    client_id: '',
    car_code: '',
    total_area_ha: '',
    municipality: '',
    state: '',
    has_embargo: false
  });

  const { data: properties, isLoading } = useQuery({
    queryKey: ['properties'],
    queryFn: async () => {
      const res = await api.get('/properties/');
      return res.data as Property[];
    }
  });

  const { data: clients } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => {
      const res = await api.get('/clients/');
      return res.data as { id: number; full_name: string; cpf_cnpj: string | null }[];
    }
  });

  const createMutation = useMutation({
    mutationFn: (newProp: typeof formData) => api.post('/properties/', {
      ...newProp,
      client_id: parseInt(newProp.client_id),
      total_area_ha: newProp.total_area_ha ? parseFloat(newProp.total_area_ha) : null
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties'] });
      setIsModalOpen(false);
      resetForm();
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      alert(axiosErr.response?.data?.detail || 'Erro ao salvar o Pydantic / Banco de Dados.');
      console.error(axiosErr.response?.data);
    }
  });

  const resetForm = () => {
    setFormData({ name: '', client_id: '', car_code: '', total_area_ha: '', municipality: '', state: '', has_embargo: false });
  };

  const filteredProperties = properties?.filter(p => 
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.car_code?.includes(searchTerm)
  ) || [];

  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">Imóveis Rurais</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Gerencie fazendas e áreas produtivas vinculadas aos clientes.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative w-64 hidden md:block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input 
              type="text"
              placeholder="Buscar imóvel..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all dark:text-zinc-200"
            />
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="bg-primary text-white px-4 py-2 flex items-center gap-2 rounded-lg hover:bg-primary/90 transition-colors shadow-sm font-medium text-sm border-none outline-none focus:ring-2 focus:ring-primary/50"
          >
            <Plus className="w-4 h-4" /> Novo Imóvel
          </button>
        </div>
      </div>

      <div className="flex-1 bg-white dark:bg-zinc-900 rounded-xl shadow-sm border border-gray-200 dark:border-zinc-800 overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-zinc-800/50 border-b border-gray-200 dark:border-zinc-800 text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400 font-semibold">
                <th className="p-4">Propriedade</th>
                <th className="p-4">Cliente / Proprietário</th>
                <th className="p-4">Localização & Área</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-zinc-800">
              {isLoading ? (
                <tr><td colSpan={4} className="p-8 text-center text-gray-400">Carregando imóveis...</td></tr>
              ) : filteredProperties.length === 0 ? (
                <tr><td colSpan={4} className="p-8 text-center text-gray-400">Nenhum imóvel encontrado.</td></tr>
              ) : (
                filteredProperties.map(prop => (
                  <tr key={prop.id} className="hover:bg-gray-50/50 dark:hover:bg-zinc-800/30 transition-colors group">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                          <MapPin className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">{prop.name}</p>
                          <p className="text-xs text-gray-500 font-mono mt-0.5" title="Cadastro Ambiental Rural">CAR: {prop.car_code || 'Não informado'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <UserIcon className="w-4 h-4 text-gray-400" />
                        <span className="truncate max-w-[200px]">{clients?.find(c => c.id === prop.client_id)?.full_name || 'Desconhecido'}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="space-y-1">
                        <div className="text-sm text-gray-600 dark:text-gray-300">
                          {prop.municipality || 'Mun. ND'} - {prop.state || 'UF'}
                        </div>
                        <div className="text-xs text-gray-500 bg-gray-100 dark:bg-zinc-800 inline-flex px-2 py-0.5 rounded">
                          {prop.total_area_ha ? `${prop.total_area_ha} hectares` : 'Área não definida'}
                        </div>
                      </div>
                    </td>
                    <td className="p-4">
                      {prop.has_embargo ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400 border border-red-200 dark:border-red-800">
                          <AlertTriangle className="w-3.5 h-3.5" /> Embargado
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400 border border-green-200 dark:border-green-800">
                          Regular
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-xl w-full max-w-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-gray-100 dark:border-zinc-800 flex justify-between items-center bg-gray-50/50 dark:bg-zinc-800/50">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <MapPin className="w-5 h-5 text-primary" /> Novo Imóvel Rural
              </h2>
            </div>
            
            <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate(formData); }} className="p-6 space-y-6">
              
              {/* Seção 1: General */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nome da Fazenda / Propriedade</label>
                  <input required
                    type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})}
                    placeholder="Ex: Fazenda Boa Esperança"
                    className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                  />
                </div>
                
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Proprietário (Cliente)</label>
                  <select required
                    value={formData.client_id} onChange={e => setFormData({...formData, client_id: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                  >
                    <option value="">Selecione um cliente dono...</option>
                    {clients?.map((c) => (
                      <option key={c.id} value={c.id}>{c.full_name} ({c.cpf_cnpj || 'Sem doc'})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Código do CAR</label>
                  <input
                    type="text" value={formData.car_code} onChange={e => setFormData({...formData, car_code: e.target.value})}
                    placeholder="MT-1234..."
                    className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all font-mono text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Área Total (Equivalente em Hectares)</label>
                  <input
                    type="number" step="0.01" value={formData.total_area_ha} onChange={e => setFormData({...formData, total_area_ha: e.target.value})}
                    placeholder="0.00"
                    className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all font-mono"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Município</label>
                  <input
                    type="text" value={formData.municipality} onChange={e => setFormData({...formData, municipality: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Estado (UF)</label>
                  <select
                    value={formData.state} onChange={e => setFormData({...formData, state: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                  >
                    <option value="">UF</option>
                    {['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'].map(uf => (
                      <option key={uf} value={uf}>{uf}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/30 rounded-lg">
                <input 
                  type="checkbox" 
                  id="embargoCheck"
                  checked={formData.has_embargo} 
                  onChange={e => setFormData({...formData, has_embargo: e.target.checked})}
                  className="w-4 h-4 text-red-600 bg-white border-red-300 rounded focus:ring-red-500 dark:focus:ring-red-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-zinc-700 dark:border-zinc-600 outline-none"
                />
                <label htmlFor="embargoCheck" className="text-sm font-medium text-red-800 dark:text-red-400 cursor-pointer select-none">
                  Marcar Imóvel como Embargado pelo IBAMA/SEMA
                </label>
              </div>

              <div className="pt-4 flex justify-end gap-3 border-t border-gray-100 dark:border-zinc-800">
                <button type="button" onClick={() => { setIsModalOpen(false); resetForm(); }} className="px-5 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 rounded-lg hover:bg-gray-50 dark:hover:bg-zinc-700 transition-colors">
                  Cancelar
                </button>
                <button type="submit" disabled={createMutation.isPending} className="px-5 py-2.5 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-lg transition-colors shadow-sm disabled:opacity-50">
                  Cadastrar Imóvel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
