// Identificação da versão que está na tela: commit do painel (build) + commit
// e ambiente da API. Painel (Netlify) e API (Render) publicam separados, então
// os dois commits podem divergir — e isso tem de ficar visível na prova.

export interface VersaoApi { commit: string | null; ambiente: string }

const AMBIENTES: Record<string, string> = {
  production: 'produção',
  development: 'desenvolvimento',
  test: 'teste',
};

export const curto = (commit: string | null | undefined) => (commit ? commit.slice(0, 7) : 'sem commit');

export function descreverVersao(painel: string | null, api: VersaoApi | undefined, apiFalhou: boolean) {
  const ambiente = api ? AMBIENTES[api.ambiente] ?? api.ambiente : apiFalhou ? 'API indisponível' : '…';
  const divergente = !!(painel && api?.commit && painel !== api.commit);
  return {
    texto: `Painel ${curto(painel)} · API ${api ? curto(api.commit) : apiFalhou ? '—' : '…'} · ${ambiente}`,
    divergente,
    producao: api?.ambiente === 'production',
  };
}
