import type { Metadata } from 'next';
import DashboardShell from './DashboardShell';

export const metadata: Metadata = {
  title: 'Dashboard — Amigão do Meio Ambiente',
  description: 'Portal do cliente — acompanhe seus processos ambientais',
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <DashboardShell>{children}</DashboardShell>;
}
