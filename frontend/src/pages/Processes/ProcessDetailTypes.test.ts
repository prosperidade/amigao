import { describe, it, expect } from 'vitest';
import { TABS } from './ProcessDetailTypes';

describe('TABS (Sprint 0 — contrato de UI)', () => {
  it('a aba de conferência usa label "Conferência" (mantendo a key "alertas")', () => {
    const tab = TABS.find((t) => t.key === 'alertas');
    expect(tab).toBeDefined();
    expect(tab?.label).toBe('Conferência');
  });

  it('não existe mais aba rotulada "Alertas"', () => {
    expect(TABS.some((t) => t.label === 'Alertas')).toBe(false);
  });
});
