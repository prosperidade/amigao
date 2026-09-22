import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { descreverVersao, type VersaoApi } from './versao';

const COMMIT_PAINEL = (import.meta.env.VITE_BUILD_COMMIT as string | undefined) || null;

// Rodapé da tela de conferência: print de prova diz de qual versão e ambiente veio.
export default function RodapeVersao() {
  const versao = useQuery({
    queryKey: ['versao-api'],
    queryFn: async () => (await api.get<VersaoApi>('/versao')).data,
    staleTime: Infinity,
    retry: 1,
  });
  const { texto, divergente, producao } = descreverVersao(COMMIT_PAINEL, versao.data, versao.isError);

  return <footer data-testid="rodape-versao"
    className="mt-6 border-t pt-2 font-mono text-xs text-gray-500 dark:border-white/10 dark:text-slate-400">
    <span className={producao ? 'font-semibold text-emerald-700 dark:text-emerald-400' : ''}>{texto}</span>
    {divergente && <span className="ml-2 text-amber-700 dark:text-amber-400">· painel e API em commits diferentes</span>}
  </footer>;
}
