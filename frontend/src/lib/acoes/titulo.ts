/**
 * Humanização de títulos de Ação (Ficha 07) — camada de LEITURA no frontend.
 *
 * Alguns geradores do backend (`app/services/acao_generator.py`) escrevem o
 * título no formato-máquina, descrevendo o ACHADO técnico em vez de dizer ao
 * consultor O QUE FAZER. Exemplo do caso 13:
 *   "Resolver divergência de total_area_ha (matrícula 4698)"  ← achado cru
 *
 * Esta camada reescreve esses títulos reconhecíveis para linguagem de consultor,
 * usando os rótulos de campo (`labelFor`) e os valores divergentes que já vêm
 * nas fontes da própria ação (#70):
 *   "Padronizar Área total (ha) (matrícula 4698): CCIR: \"349,90\" vs SIGEF: \"350,00\""
 *
 * Regras:
 *  - Só reescreve títulos que casam com um padrão de máquina conhecido.
 *  - Título manual, de diagnóstico (LLM) ou JÁ editado pelo consultor passa
 *    intacto — não casa nenhum padrão, então volta verbatim.
 *  - É pura leitura: não muda o dado gravado. Quando o consultor confirma a
 *    edição inline (item 1), o texto humanizado vira o `titulo` persistido.
 */
import { labelFor } from '@/lib/labels/fieldLabels';
import type { Acao } from './types';

// "Resolver divergência de <field>" ou "... de <field> (matrícula <hint>)"
const DIVERGENCIA_RE = /^Resolver divergência de (.+?)(?: \(matrícula ([^)]+)\))?$/;

// "Atualização de arquivos oficiais — <rótulo>"
const OFICIALIZACAO_RE = /^Atualização de arquivos oficiais — (.+)$/;

/** Extrai pares {documento, valor} das fontes da ação, ignorando "sem fonte". */
function valoresDivergentes(acao: Acao): { doc: string; valor: string }[] {
  return (acao.origem_fontes ?? [])
    .filter((f) => !f.sem_fonte && f.valor != null && String(f.valor).trim() !== '')
    .map((f) => ({
      doc: (f.descricao || f.tipo || 'documento').toString(),
      valor: String(f.valor),
    }));
}

/**
 * Título da ação em linguagem de consultor. Idempotente: aplicar duas vezes
 * devolve o mesmo texto (a saída não casa os padrões de máquina de entrada).
 */
export function humanizeAcaoTitulo(acao: Acao): string {
  const titulo = (acao.titulo ?? '').trim();
  if (!titulo) return titulo;

  const mDiv = DIVERGENCIA_RE.exec(titulo);
  if (mDiv) {
    const field = mDiv[1];
    const hint = mDiv[2];
    const label = labelFor(field);
    const matricula = hint ? ` (matrícula ${hint})` : '';
    const valores = valoresDivergentes(acao);
    const base = `Padronizar ${label}${matricula}`;
    if (valores.length >= 2) {
      const comparacao = valores.map((v) => `${v.doc}: "${v.valor}"`).join(' vs ');
      return `${base}: ${comparacao}`;
    }
    return base;
  }

  const mOfi = OFICIALIZACAO_RE.exec(titulo);
  if (mOfi) {
    return `Atualizar nos arquivos oficiais — ${mOfi[1]}`;
  }

  return titulo;
}
