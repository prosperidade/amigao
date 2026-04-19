import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Detalhes do Processo — Amigão do Meio Ambiente',
  description: 'Detalhes e acompanhamento do processo ambiental',
};

export default function ProcessLayout({ children }: { children: React.ReactNode }) {
  return children;
}
