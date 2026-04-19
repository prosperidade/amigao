import { useState } from 'react';
import { useAuthStore } from '@/store/auth';
import { api } from '@/lib/api';
import { isClientPortalToken } from '@/lib/auth';
import { useNavigate } from 'react-router-dom';
import { Leaf } from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const setAuth = useAuthStore((state) => state.setAuth);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      // Chamada OAuth2 para o Token
      const tokenRes = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-Auth-Profile': 'internal',
        },
      });

      const token = tokenRes.data.access_token;

      if (isClientPortalToken(token)) {
        const portalUrl = import.meta.env.VITE_CLIENT_PORTAL_URL || '/';
        throw new Error(`Este usuário pertence ao portal do cliente. Use o portal em ${portalUrl}`);
      }
      
      // Chamada para pegar dados do User com o novo token
      const userRes = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const user = userRes.data;

      // Salva no State Zustand
      setAuth(token, user);
      
      // Redireciona pro App
      navigate('/dashboard');
      
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(axiosErr.response?.data?.detail || axiosErr.message || 'Erro ao realizar login.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-zinc-900 p-4">
      <div className="w-full max-w-md bg-white dark:bg-zinc-950 rounded-2xl shadow-xl border border-gray-100 dark:border-zinc-800 p-8">
        
        <div className="flex flex-col items-center mb-8">
          <div className="bg-primary/10 p-4 rounded-full mb-4">
            <Leaf className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Amigão do Meio Ambiente</h1>
          <p className="text-sm text-gray-500 text-center">Software de Gestão Ambiental e Fundiária</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100 flex items-center justify-center">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">E-mail corporativo</label>
            <input 
              type="email" 
              className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-primary focus:border-transparent dark:bg-zinc-900 dark:border-zinc-800 dark:text-white transition-all"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="seu@email.com"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Senha de acesso</label>
            <input 
              type="password" 
              className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-primary focus:border-transparent dark:bg-zinc-900 dark:border-zinc-800 dark:text-white transition-all"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-3 rounded-lg flex items-center justify-center transition-colors shadow-sm disabled:opacity-70"
          >
            {loading ? 'Autenticando...' : 'Acessar Plataforma'}
          </button>
        </form>
        
        <div className="mt-8 text-center text-xs text-gray-400">
          <p>Uso exclusivo e monitorado.</p>
        </div>
      </div>
    </div>
  );
}
