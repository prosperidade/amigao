/**
 * ContiguidadeDeclararLink — item 4 do pack UX das Ações.
 *
 * O alerta "Contiguidade das matrículas não declarada" (dossiê do caso) e o
 * controle tri-state onde se DECLARA a contiguidade (Hub do Imóvel) vivem em
 * rotas diferentes. Este link faz a ponte de um clique: leva direto ao Hub do
 * Imóvel, na âncora `#contiguidade`, onde o PropertyHub rola até o controle.
 */
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { contiguidadeHref } from '@/lib/deeplinks';

export default function ContiguidadeDeclararLink({ propertyId }: { propertyId: number }) {
  return (
    <Link
      to={contiguidadeHref(propertyId)}
      className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 dark:text-emerald-400 hover:underline"
    >
      Declarar contiguidade <ArrowRight className="w-3 h-3" />
    </Link>
  );
}
