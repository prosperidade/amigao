import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Login — Portal do Cliente',
  description: 'Acesse o portal do cliente Amigão do Meio Ambiente',
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
