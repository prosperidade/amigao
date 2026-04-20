import { useEffect } from 'react';
import { Outlet, Navigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { isClientPortalToken } from '@/lib/auth';
import {
  Briefcase,
  Users,
  MapPin,
  LayoutDashboard,
  LogOut,
  Leaf,
  FileText,
  Bot,
  Settings as SettingsIcon,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useAgentEvents } from '@/hooks/useAgentEvents';

export default function PrivateLayout() {
  useAgentEvents();
  const { token, user, logout } = useAuthStore();
  const location = useLocation();
  const hasPortalToken = token ? isClientPortalToken(token) : false;

  useEffect(() => {
    if (hasPortalToken) {
      logout();
    }
  }, [hasPortalToken, logout]);

  if (!token || !user || hasPortalToken) {
    return <Navigate to="/login" replace />;
  }

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      console.error(e);
    } finally {
      logout();
    }
  };

  const menu = [
    { name: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
    { name: 'Processos', icon: Briefcase, path: '/processes' },
    { name: 'Clientes', icon: Users, path: '/clients' },
    { name: 'Imóveis', icon: MapPin, path: '/properties' },
    { name: 'Propostas', icon: FileText, path: '/proposals' },
    { name: 'Agentes IA', icon: Bot, path: '/agents' },
    { name: 'Configurações', icon: SettingsIcon, path: '/settings' },
  ];

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-zinc-950 font-sans">
      
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-zinc-900 border-r border-gray-200 dark:border-zinc-800 flex flex-col hidden md:flex">
        
        {/* Brand */}
        <div className="h-16 flex items-center px-6 border-b border-gray-100 dark:border-zinc-800">
          <div className="bg-primary/10 p-1.5 rounded-md mr-3">
            <Leaf className="w-5 h-5 text-primary" />
          </div>
          <span className="font-bold text-gray-900 dark:text-white tracking-tight">Amigão</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {menu.map((item) => {
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive 
                    ? 'bg-primary/10 text-primary dark:bg-primary/20' 
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-zinc-800 dark:hover:text-gray-200'
                }`}
              >
                <item.icon className={`w-5 h-5 mr-3 ${isActive ? 'text-primary' : 'text-gray-400 dark:text-gray-500'}`} />
                {item.name}
              </Link>
            )
          })}
        </nav>

        {/* User profile & Logout */}
        <div className="p-4 border-t border-gray-100 dark:border-zinc-800">
          <div className="flex items-center mb-4">
            <div className="bg-gray-200 dark:bg-zinc-800 w-8 h-8 rounded-full flex items-center justify-center text-gray-600 dark:text-gray-300 font-bold text-sm">
              {user.full_name?.charAt(0).toUpperCase() ?? 'A'}
            </div>
            <div className="ml-3 overflow-hidden">
              <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{user.full_name}</p>
              <p className="text-xs text-gray-500 truncate">{user.email}</p>
            </div>
          </div>
          
          <button 
            onClick={handleLogout}
            className="w-full flex items-center justify-center px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 hover:bg-red-100 dark:hover:bg-red-500/20 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sair do sistema
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header mobile (dummy) */}
        <header className="md:hidden h-16 bg-white dark:bg-zinc-900 border-b border-gray-200 dark:border-zinc-800 flex items-center px-4">
          <div className="bg-primary/10 p-1.5 rounded-md mr-3">
            <Leaf className="w-5 h-5 text-primary" />
          </div>
          <span className="font-bold text-gray-900 dark:text-white">Amigão</span>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-4 md:p-8">
          <Outlet />
        </div>
      </main>

    </div>
  );
}
