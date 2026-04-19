'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/auth';
import { LogOut, Leaf, LayoutDashboard } from 'lucide-react';

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token, user, logout, hydrated } = useAuthStore();

  useEffect(() => {
    if (hydrated && !token) {
      router.replace('/login');
    }
  }, [hydrated, token, router]);

  if (!hydrated || !token) return null;

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm">
        <div className="h-16 flex items-center px-6 border-b border-gray-100">
          <Leaf className="text-emerald-600 w-6 h-6 mr-2" />
          <span className="font-bold text-gray-800 text-lg tracking-tight">Portal Cliente</span>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-1">
          <Link
            href="/dashboard"
            className="flex items-center px-4 py-3 bg-emerald-50 text-emerald-700 rounded-xl font-medium transition-colors"
          >
            <LayoutDashboard className="w-5 h-5 mr-3" />
            Meus Processos
          </Link>
        </nav>

        <div className="p-4 border-t border-gray-100">
          <div className="mb-4 px-4">
            <p className="text-sm font-medium text-gray-900 truncate">{user?.email}</p>
            <p className="text-xs text-gray-500">Acesso Cliente</p>
          </div>
          <button
            onClick={() => { logout(); router.replace('/login'); }}
            className="flex items-center w-full px-4 py-2 text-red-600 hover:bg-red-50 rounded-xl font-medium transition-colors"
          >
            <LogOut className="w-5 h-5 mr-3" />
            Sair do Portal
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        <header className="h-16 bg-white/80 backdrop-blur-md border-b border-gray-200 flex items-center justify-between px-8 sticky top-0 z-10">
          <h2 className="text-xl font-semibold text-gray-800">Visão Geral</h2>
        </header>
        <div className="flex-1 overflow-y-auto p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
