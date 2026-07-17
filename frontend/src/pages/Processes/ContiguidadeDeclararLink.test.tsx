// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import ContiguidadeDeclararLink from './ContiguidadeDeclararLink';
import { contiguidadeHref } from '@/lib/deeplinks';

describe('ContiguidadeDeclararLink (item 4 — contiguidade com caminho)', () => {
  it('aponta para o Hub do Imóvel na âncora do controle tri-state', () => {
    expect(contiguidadeHref(42)).toBe('/properties/42#contiguidade');
  });

  it('renderiza um link clicável para o destino de declaração', () => {
    render(
      <MemoryRouter>
        <ContiguidadeDeclararLink propertyId={7} />
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: /declarar contiguidade/i });
    expect(link).toHaveAttribute('href', '/properties/7#contiguidade');
  });
});
