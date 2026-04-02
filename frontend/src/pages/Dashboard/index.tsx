import { Users, Briefcase, Frame, AlertCircle, FileText, Activity, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';

export default function Dashboard() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  
  // Buscaríamos da API os totais reais (Placeholder Data para visualização inicial)
  const stats = [
    { title: 'Processos Ativos', value: '24', icon: Briefcase, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30' },
    { title: 'Tarefas em Atraso', value: '3', icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30' },
    { title: 'Clientes Totais', value: '142', icon: Users, color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30' },
    { title: 'Imóveis Cadastrados', value: '89', icon: Frame, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Olá, {user?.full_name?.split(' ')[0] ?? 'Administrador'} 👋</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Bem-vindo(a) ao painel de gestão ambiental.</p>
        </div>
        <button
          onClick={() => navigate('/intake')}
          className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-emerald-500/20 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nova Demanda
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {stats.map((item, index) => (
          <div key={index} className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm transform transition-all hover:scale-[1.02]">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{item.title}</p>
                <h3 className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{item.value}</h3>
              </div>
              <div className={`p-3 rounded-lg ${item.bg}`}>
                <item.icon className={`w-6 h-6 ${item.color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        
        {/* Componente Atividades Recentes */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm col-span-1 lg:col-span-2 p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-primary" />
            Atividades Recentes
          </h2>
          <div className="space-y-4">
            {[1, 2, 3].map((_, i) => (
              <div key={i} className="flex gap-4 items-start p-3 hover:bg-gray-50 dark:hover:bg-zinc-800/50 rounded-lg transition-colors border border-transparent hover:border-gray-100 dark:hover:border-zinc-800">
                <div className="bg-gray-100 dark:bg-zinc-800 p-2 rounded-full mt-0.5">
                  <FileText className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">Documento CAR importado para o Processo P-2026/00{i}</p>
                  <p className="text-xs text-gray-500 mt-1">Há {i + 2} horas • Por Agente Extrator Automático</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Componente Tarefas Pendentes */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm col-span-1 p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Minhas Tarefas Hoje</h2>
          <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
            Nenhuma tarefa urgente pra você hoje. Aproveite o café! ☕
          </div>
        </div>

      </div>
    </div>
  );
}
