'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { MapPin, Calendar, Clock, ArrowRight, Loader2, Search, FileText } from 'lucide-react';
import clsx from 'clsx';
import { useAuthStore } from '@/store/auth';
import { getProcessStatusClass, getProcessStatusLabel } from '@/lib/process-status';

interface ProcessSummary {
  id: number;
  title: string;
  status: string;
  property_id: number | null;
  due_date: string | null;
}

export default function DashboardPage() {
  const [processes, setProcesses] = useState<ProcessSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const token = useAuthStore((state) => state.token);

  useEffect(() => {
    if (token) {
      fetchProcesses();
    }
  }, [token]);

  const fetchProcesses = async () => {
    try {
      const res = await api.get('/processes/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      setProcesses(res.data);
      setErrorMsg(null);
    } catch (error: any) {
      // Evitando o console.error que aciona a Tela Vermelha do Next.js
      const detail = error.response?.data?.detail || error.message || 'Erro Desconhecido';
      setErrorMsg(`Falha ao buscar: ${detail} (${error.response?.status || 'Sem HTTP Status'})`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Seus Processos de Licenciamento</h1>
          <p className="text-gray-500 mt-1">Acompanhe o andamento das suas solicitações ambientais.</p>
        </div>
        
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input 
            type="text" 
            placeholder="Buscar pelo número CAR..." 
            className="pl-10 pr-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 outline-none transition-all w-full md:w-64"
          />
        </div>
      </div>

      {errorMsg ? (
        <div className="bg-red-50 border border-red-200 text-red-700 p-6 rounded-2xl mb-6">
          <h3 className="font-bold">Aviso do Sistema:</h3>
          <p>{errorMsg}</p>
        </div>
      ) : null}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-600 mb-4" />
          <p className="text-gray-500">Buscando informações ativadas...</p>
        </div>
      ) : processes.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center shadow-sm">
          <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900">Nenhum processo encontrado</h3>
          <p className="text-gray-500 mt-2">Você ainda não possui processos de licenciamento ativos neste portal.</p>
        </div>
      ) : (
        <div className="grid gap-6">
          {processes.map((proc) => (
            <div key={proc.id} className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow group flex flex-col md:flex-row gap-6 items-start md:items-center">
              
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={clsx("px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border", getProcessStatusClass(proc.status))}>
                    {getProcessStatusLabel(proc.status)}
                  </span>
                  <span className="text-sm text-gray-500 flex items-center gap-1">
                    <Clock className="w-4 h-4" /> Atualizado recentemente
                  </span>
                </div>
                
                <h3 className="text-xl font-bold text-gray-900 group-hover:text-emerald-700 transition-colors">
                  {proc.title}
                </h3>
                
                <div className="flex items-center gap-4 mt-4 text-sm text-gray-600">
                  <div className="flex items-center gap-1.5 flex-1 min-w-[200px]">
                    <MapPin className="w-4 h-4 text-gray-400" />
                    <span className="truncate">Imóvel Associado: #{proc.property_id || 'Não Vinculado'}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span>Prazo: {proc.due_date ? new Date(proc.due_date).toLocaleDateString('pt-BR') : 'Indefinido'}</span>
                  </div>
                </div>
              </div>

              <div className="w-full md:w-auto flex-shrink-0 pt-4 md:pt-0 md:border-l border-gray-100 md:pl-6">
                <Link
                  href={`/dashboard/process/${proc.id}`}
                  className="w-full md:w-auto bg-gray-50 hover:bg-emerald-50 text-gray-700 hover:text-emerald-700 font-medium py-2.5 px-6 rounded-xl border border-gray-200 hover:border-emerald-200 transition-colors flex items-center justify-center gap-2"
                >
                  Ver Detalhes
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
