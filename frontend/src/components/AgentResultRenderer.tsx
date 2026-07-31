/**
 * AgentResultRenderer — Renderiza resultados de agentes IA de forma humanizada.
 *
 * Cada agente tem seu proprio layout visual com linguagem natural,
 * transformando JSON tecnico em cards compreensiveis por usuario leigo.
 */

import React from 'react';
import {
  Stethoscope, Scale, FileText, DollarSign, AlertTriangle,
  CheckCircle2, Clock, Shield, Megaphone, Search,
  Building2, BookOpen, ListChecks, TrendingUp,
  Mail, Eye, Sparkles,
} from 'lucide-react';
import { CONFIDENCE_STYLES } from '@/types/agent';
import { labelFor, isMetaField, humanizeValue } from '@/lib/labels/fieldLabels';
import FonteChip, { type FonteRef } from '@/components/FonteChip';

// Safe accessors for Record<string, unknown>
function str(v: unknown): string { return v != null ? String(v) : ''; }
function arr(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map(item => typeof item === 'object' && item !== null && 'label' in item ? String((item as Record<string, unknown>).label) : String(item));
}
function objArr(v: unknown): Record<string, unknown>[] {
  if (!Array.isArray(v)) return [];
  return v.filter(item => typeof item === 'object' && item !== null) as Record<string, unknown>[];
}
function rawArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

/**
 * Formata um item de `legislacao_aplicavel` — que chega como string OU objeto
 * (`{identificador|norma|lei, numero, titulo, artigo, descricao, ...}`) — em
 * texto legível tipo "Lei nº 12.651/2012 — Código Florestal, art. 17".
 * NUNCA produz "[object Object]". Espelha a prioridade de
 * `legislacao._citation_ref_from_raw` no backend e cai em `humanizeValue` como
 * último recurso.
 */
function formatLegislacao(item: unknown): string {
  if (item == null) return '';
  if (typeof item !== 'object') return String(item);
  const o = item as Record<string, unknown>;
  const ident = str(o.identificador) || str(o.norma) || str(o.lei) || str(o.raw);
  const numero = str(o.numero);
  const titulo = str(o.titulo) || str(o.descricao);
  const artigo = str(o.artigo);

  let head = ident;
  if (ident && numero && !ident.includes(numero)) head = `${ident} nº ${numero}`;

  const parts: string[] = [];
  if (head) parts.push(head);
  if (titulo && titulo !== head) parts.push(titulo);
  let label = parts.join(' — ');
  if (artigo) label = label ? `${label}, art. ${artigo}` : `art. ${artigo}`;

  return label || humanizeValue(o);
}

interface Props {
  agentName: string | null;
  result: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const labels: Record<string, string> = {
    high: 'Alta',
    medium: 'Média',
    low: 'Baixa',
    alta: 'Alta',
    media: 'Média',
    baixa: 'Baixa',
  };
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${CONFIDENCE_STYLES[confidence] ?? CONFIDENCE_STYLES.medium ?? ''}`}>
      Confiança: {labels[confidence] ?? confidence}
    </span>
  );
}

function ReviewBadge() {
  return (
    <span className="text-xs px-2.5 py-1 rounded-full border font-medium bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30 flex items-center gap-1">
      <Eye className="w-3 h-3" /> Requer revisão humana
    </span>
  );
}

function Section({ icon: Icon, title, color, children }: {
  icon: React.ElementType;
  title: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-3">
      <p className={`text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5 ${color}`}>
        <Icon className="w-3.5 h-3.5" /> {title}
      </p>
      {children}
    </div>
  );
}

function BulletList({ items, color = 'text-gray-400' }: { items: string[]; color?: string }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="text-sm text-gray-700 dark:text-slate-300 flex items-start gap-2">
          <span className={`mt-1 ${color}`}>&#x2022;</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function KeyValue({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value == null || value === '') return null;
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-gray-100 dark:border-white/5 last:border-0">
      <span className="text-xs text-gray-500 dark:text-slate-400">{label}</span>
      <span className="text-sm font-medium text-gray-800 dark:text-white">{String(value)}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Renderers por agente
// ---------------------------------------------------------------------------

function AtendimentoResult({ r }: { r: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {str(r.demand_label) && (
          <span className="text-sm font-bold text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-500/10 px-3 py-1 rounded-full">
            {str(r.demand_label)}
          </span>
        )}
        {typeof r.confidence === 'string' && <ConfidenceBadge confidence={r.confidence} />}
        {str(r.urgency_flag) && (
          <span className="text-xs px-2 py-1 rounded-full bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-300 border border-red-200 dark:border-red-500/30">
            Urgência: {str(r.urgency_flag)}
          </span>
        )}
      </div>

      {str(r.initial_diagnosis) && (
        <p className="text-sm text-gray-700 dark:text-slate-200 leading-relaxed bg-gray-50 dark:bg-white/5 p-3 rounded-lg">
          {str(r.initial_diagnosis)}
        </p>
      )}

      {arr(r.suggested_next_steps).length > 0 && (
        <Section icon={ListChecks} title="Próximos Passos" color="text-emerald-600 dark:text-emerald-400">
          <BulletList items={arr(r.suggested_next_steps)} color="text-emerald-400" />
        </Section>
      )}

      {arr(r.required_documents).length > 0 && (
        <Section icon={FileText} title="Documentos Necessários" color="text-blue-600 dark:text-blue-400">
          <BulletList items={arr(r.required_documents)} color="text-blue-400" />
        </Section>
      )}

      {arr(r.relevant_agencies).length > 0 && (
        <Section icon={Building2} title="Órgãos Relevantes" color="text-indigo-600 dark:text-indigo-400">
          <div className="flex flex-wrap gap-2">
            {arr(r.relevant_agencies).map((a, i) => (
              <span key={i} className="text-xs px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30">
                {a}
              </span>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function DiagnósticoResult({ r }: { r: Record<string, unknown> }) {
  // Sprint A2-diagnostico-B: leitura aditiva, dual-emit-aware.
  // - Chaves NOVAS (DiagnosticoPreliminarContent): content, hipoteses, lacunas,
  //   riscos (objetos), checklist_documental, sources, metadata.
  // - Chaves ANTIGAS (dual-emit): situacao_geral, passivos_identificados,
  //   acoes_remediacao, prioridade_acoes, risco_estimado, observacoes.
  // Para AIJobs históricos (pré-A2-diagnostico) sem chaves novas, lê apenas
  // chaves antigas — defesa em profundidade.
  const situacaoText =
    (typeof r.content === 'string' && r.content) ||
    (typeof r.situacao_geral === 'string' && r.situacao_geral) ||
    null;
  const hipoteses = arr(r.hipoteses ?? r.passivos_identificados);
  const checklist = arr(r.checklist_documental ?? r.acoes_remediacao);
  const lacunas = arr(r.lacunas);
  const riscosArr = objArr(r.riscos);
  // risco_estimado (string única, dual-emit) tem precedência visual no badge
  // de header; se ausente, deriva da maior severidade entre riscos[*].severidade.
  const riscoEstimado =
    (typeof r.risco_estimado === 'string' && r.risco_estimado) ||
    (riscosArr.length > 0 && typeof riscosArr[0].severidade === 'string'
      ? (riscosArr[0].severidade as string)
      : null);
  const observacoesText =
    (typeof r.observacoes === 'string' && r.observacoes) ||
    (typeof (r.metadata as Record<string, unknown> | undefined)?.observacoes === 'string'
      ? ((r.metadata as Record<string, unknown>).observacoes as string)
      : null);
  const prioridades = arr(
    r.prioridade_acoes ?? (r.metadata as Record<string, unknown> | undefined)?.prioridade_acoes,
  );
  const divergencias = objArr(r.divergencias);
  // Rastreabilidade (06/06): afirmações com fonte por item.
  const afirmacoes = objArr(r.afirmacoes);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {typeof r.confidence === 'string' && <ConfidenceBadge confidence={r.confidence} />}
        {riscoEstimado && (
          <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
            riscoEstimado === 'alto' ? 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30'
            : riscoEstimado === 'medio' ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30'
            : 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30'
          }`}>
            Risco: {riscoEstimado}
          </span>
        )}
        {r.requires_review === true && <ReviewBadge />}
      </div>

      {situacaoText && (
        <p className="text-sm text-gray-700 dark:text-slate-200 leading-relaxed bg-gray-50 dark:bg-white/5 p-3 rounded-lg">
          {situacaoText}
        </p>
      )}

      {/* Passivos sem fonte (regra de ouro, Ficha 04): quando há afirmações com
          fonte, elas cobrem 100% dos passivos (com fonte ou "sem fonte
          identificada"). A lista crua só aparece em payloads antigos sem
          afirmações — senão um passivo apareceria como fato sem fonte. */}
      {hipoteses.length > 0 && afirmacoes.length === 0 && (
        <Section icon={AlertTriangle} title="Hipóteses / Pendências" color="text-red-600 dark:text-red-400">
          <BulletList items={hipoteses} color="text-red-400" />
        </Section>
      )}

      {afirmacoes.length > 0 && (
        <Section icon={Search} title="Afirmações com fonte" color="text-sky-600 dark:text-sky-400">
          <div className="space-y-2">
            {afirmacoes.map((a, i) => {
              const fontes = Array.isArray(a.fontes) ? (a.fontes as Record<string, unknown>[]) : [];
              return (
                <div key={i} className="p-2.5 bg-sky-50/50 dark:bg-sky-500/5 rounded-lg border border-sky-100 dark:border-sky-500/20">
                  <p className="text-sm text-gray-800 dark:text-slate-200">{str(a.texto)}</p>
                  {/* Fonte CLICÁVEL (26/07): o chip abre o documento de origem
                      ou o texto da norma. Fonte que não se pode conferir com um
                      clique é indistinguível de invenção — foi a lição da
                      GO-NOT-2024-001985. */}
                  <div className="mt-1 flex flex-wrap items-start gap-1">
                    {fontes.map((f, fi) => (
                      <FonteChip key={fi} fonte={f as unknown as FonteRef} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {lacunas.length > 0 && (
        <Section icon={AlertTriangle} title="Lacunas Documentais" color="text-amber-600 dark:text-amber-400">
          <BulletList items={lacunas} color="text-amber-400" />
        </Section>
      )}

      {checklist.length > 0 && (
        <Section icon={CheckCircle2} title="Ações / Checklist" color="text-emerald-600 dark:text-emerald-400">
          <BulletList items={checklist} color="text-emerald-400" />
        </Section>
      )}

      {prioridades.length > 0 && (
        <Section icon={CheckCircle2} title="Prioridades" color="text-blue-600 dark:text-blue-400">
          <BulletList items={prioridades} color="text-blue-400" />
        </Section>
      )}

      {divergencias.length > 0 && (
        <Section icon={Search} title="Divergências Documentais" color="text-amber-600 dark:text-amber-400">
          <div className="space-y-2">
            {divergencias.map((d, i) => (
              <div key={i} className="p-2.5 bg-amber-50 dark:bg-amber-500/5 rounded-lg border border-amber-200 dark:border-amber-500/20">
                {str(d.tema) && (
                  <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider mb-1">{str(d.tema)}</p>
                )}
                {str(d.divergencia) && <p className="text-sm text-gray-800 dark:text-slate-200">{str(d.divergencia)}</p>}
                {str(d.impacto) && <p className="text-xs text-gray-500 dark:text-slate-400 mt-1 italic">Impacto: {str(d.impacto)}</p>}
              </div>
            ))}
          </div>
        </Section>
      )}

      {observacoesText && (
        <p className="text-xs text-gray-500 dark:text-slate-400 italic mt-2">{observacoesText}</p>
      )}
    </div>
  );
}

// Ficha 02 / FASE 3 — cores/rótulos por situação da matriz (taxonomia §4).
const MATRIZ_SIT_CLS: Record<string, string> = {
  critico: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
  inconsistente: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-500/10 dark:text-orange-300 dark:border-orange-500/30',
  divergente: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
  atencao: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30',
  consistente: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30',
};
const MATRIZ_SIT_LABEL: Record<string, string> = {
  critico: 'Crítico', inconsistente: 'Inconsistente', divergente: 'Divergente',
  atencao: 'Atenção', consistente: 'Consistente',
};

function AuditorResult({ r }: { r: Record<string, unknown> }) {
  // auditor_imovel cruza documentos extraídos (matrícula × CAR × CCIR/etc.) e
  // produz `divergencias` ({tema, divergencia, impacto}). findings_raw, issue_ids,
  // method e geom_present são meta internos — não exibir ao consultor.
  const divergencias = objArr(r.divergencias);
  const matriz = (r.matriz_inconsistencias && typeof r.matriz_inconsistencias === 'object')
    ? (r.matriz_inconsistencias as Record<string, unknown>)
    : null;
  const linhas = matriz ? objArr(matriz.linhas) : [];
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {r.requires_review === true && <ReviewBadge />}
      </div>

      {str(r.content) && (
        <p className="text-sm text-gray-700 dark:text-slate-200 leading-relaxed bg-gray-50 dark:bg-white/5 p-3 rounded-lg">
          {str(r.content)}
        </p>
      )}

      {divergencias.length > 0 ? (
        <Section icon={AlertTriangle} title="Divergências Encontradas" color="text-amber-600 dark:text-amber-400">
          <div className="space-y-2">
            {divergencias.map((d, i) => (
              <div key={i} className="p-3 bg-amber-50 dark:bg-amber-500/5 rounded-lg border border-amber-200 dark:border-amber-500/20">
                {str(d.tema) && (
                  <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider mb-1">
                    {str(d.tema)}
                  </p>
                )}
                {str(d.divergencia) && (
                  <p className="text-sm text-gray-800 dark:text-slate-200">{str(d.divergencia)}</p>
                )}
                {str(d.impacto) && (
                  <p className="text-xs text-gray-500 dark:text-slate-400 mt-1 italic">Impacto: {str(d.impacto)}</p>
                )}
              </div>
            ))}
          </div>
        </Section>
      ) : (
        <p className="text-sm text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
          <CheckCircle2 className="w-4 h-4" /> Nenhuma divergência documental encontrada.
        </p>
      )}

      {linhas.length > 0 && (
        <Section icon={AlertTriangle} title="Matriz de Inconsistências" color="text-purple-600 dark:text-purple-400">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-xs text-gray-400 dark:text-slate-500 uppercase tracking-wider">
                  <th className="py-2 pr-3 font-medium">Item</th>
                  <th className="py-2 pr-3 font-medium">Situação</th>
                  <th className="py-2 font-medium">Ação recomendada</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l, i) => {
                  const sit = str(l.situacao);
                  return (
                    <tr key={i} className="border-t border-gray-100 dark:border-white/10 align-top">
                      <td className="py-2 pr-3 text-gray-800 dark:text-slate-200">
                        {str(l.label) || str(l.item)}
                        {str(l.profundidade) === 'tecnica' && (
                          <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-white/10 text-gray-500 dark:text-slate-400">
                            técnica — aguarda geo
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-3">
                        <span className={`text-xs px-2 py-0.5 rounded border whitespace-nowrap ${MATRIZ_SIT_CLS[sit] ?? ''}`}>
                          {MATRIZ_SIT_LABEL[sit] ?? sit}
                          {str(l.subtipo) && ` · ${str(l.subtipo)}`}
                        </span>
                      </td>
                      <td className="py-2 text-gray-600 dark:text-slate-300">
                        {str(l.acao_recomendada)}
                        {Array.isArray(l.fontes_detalhe) && (l.fontes_detalhe as unknown[]).length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {(l.fontes_detalhe as Record<string, unknown>[]).map((f, fi) => (
                              <span
                                key={fi}
                                title="fonte do confronto"
                                className="text-[10px] px-1.5 py-0.5 rounded bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-500/20"
                              >
                                {str(f.protocolo) || str(f.source_doc_type) || str(f.fonte)}
                                {str(f.valor) ? `: ${str(f.valor)}` : ''}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  );
}

/**
 * Biblioteca qualificada (ADR-033) — as normas localizadas, ao pé da letra.
 *
 * É o que a Análise Legal mostra no modo sombra: fundamentação achada, com fonte
 * clicável, alcance declarado e a data em que a vigência foi conferida. Não
 * sequencia etapas nem estima prazo — a rota é decisão da consultora.
 */
function BibliotecaQualificada({ r }: { r: Record<string, unknown> }) {
  const normas = objArr(r.fundamentacao);
  const rotulo = str(r.rota_shadow_rotulo) || 'fundamentação localizada — a rota é decisão do consultor';

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-purple-200 dark:border-purple-500/30 bg-purple-50/60 dark:bg-purple-500/5 p-3">
        <p className="text-xs font-semibold text-purple-700 dark:text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5" /> {rotulo}
        </p>
        <p className="text-[11px] text-purple-700/80 dark:text-purple-300/80 mt-1">
          O sistema localiza as normas aplicáveis e as apresenta como estão escritas.
          Ele não define etapas, prazos nem ordem de protocolo.
        </p>
      </div>

      {normas.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-slate-400">
          Nenhum trecho normativo foi localizado para este caso. Sem fundamentação
          encontrada, o sistema não sugere norma de memória.
        </p>
      ) : (
        <div className="space-y-2">
          {normas.map((n, i) => {
            const fonte = (n.fonte && typeof n.fonte === 'object'
              ? { ...(n.fonte as Record<string, unknown>), trecho: n.trecho }
              : null) as FonteRef | null;
            const alcance = [str(n.esfera), str(n.uf)].filter(Boolean).join(' · ');
            return (
              <div
                key={i}
                className="p-3 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10"
              >
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <p className="text-sm font-medium text-gray-800 dark:text-white min-w-0">
                    {str(n.identificador) || str(n.titulo) || 'Norma'}
                    {str(n.secao) && (
                      <span className="text-gray-500 dark:text-slate-400"> — {str(n.secao)}</span>
                    )}
                  </p>
                  {alcance && (
                    <span className="shrink-0 text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full border bg-gray-50 text-gray-600 border-gray-200 dark:bg-white/5 dark:text-slate-300 dark:border-white/10">
                      {alcance}
                    </span>
                  )}
                </div>
                {str(n.titulo) && str(n.titulo) !== str(n.identificador) && (
                  <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{str(n.titulo)}</p>
                )}
                {str(n.trecho) && (
                  <p className="mt-2 text-sm text-gray-700 dark:text-slate-300 whitespace-pre-wrap border-l-2 border-purple-300 dark:border-purple-500/40 pl-3 max-h-56 overflow-auto">
                    {str(n.trecho)}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {fonte && <FonteChip fonte={fonte} />}
                  {/* Item 12 — honestidade estrutural: o sistema não afirma "está
                      vigente", afirma quando conferiu. A diferença é a que separa
                      informar de garantir. */}
                  <span className="text-[10px] text-gray-400 dark:text-slate-500">
                    {str(n.vigencia_conferida_em)
                      ? `vigência conferida em ${new Date(str(n.vigencia_conferida_em)).toLocaleDateString('pt-BR')}`
                      : 'vigência ainda não conferida'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {str(r.orgao_competente) && (
        <KeyValue label="Órgão indicado nos autos" value={str(r.orgao_competente)} />
      )}

      {str(r.justificativa) && (
        <p className="text-xs text-gray-500 dark:text-slate-400 italic mt-2 bg-gray-50 dark:bg-white/5 p-2 rounded">
          {str(r.justificativa)}
        </p>
      )}
    </div>
  );
}

function LegislaçãoResult({ r }: { r: Record<string, unknown> }) {
  // ADR-033 — no modo sombra o backend nem serve os campos prescritivos; este
  // guard é a segunda barreira, para o caso de um payload antigo em cache.
  if (r.rota_shadow === true) {
    return <BibliotecaQualificada r={r} />;
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {typeof r.confidence === 'string' && <ConfidenceBadge confidence={r.confidence} />}
        {r.requires_review === true && <ReviewBadge />}
      </div>

      {typeof r.caminho_regulatorio === 'string' && (
        <div className="bg-blue-50 dark:bg-blue-500/5 p-3 rounded-lg border border-blue-200 dark:border-blue-500/20">
          <p className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-1">Caminho Regulatório</p>
          <p className="text-sm text-gray-800 dark:text-slate-200 font-medium">{str(r.caminho_regulatorio)}</p>
        </div>
      )}

      {typeof r.orgao_competente === 'string' && (
        <KeyValue label="Órgão Competente" value={str(r.orgao_competente)} />
      )}

      {objArr(r.etapas).length > 0 && (
        <Section icon={ListChecks} title="Etapas Regulatórias" color="text-blue-600 dark:text-blue-400">
          <div className="space-y-2">
            {objArr(r.etapas).map((etapa, i) => (
              <div key={i} className="flex items-start gap-3 p-2 bg-gray-50 dark:bg-white/5 rounded-lg">
                <span className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-300 text-xs font-bold flex items-center justify-center shrink-0">
                  {typeof etapa.ordem === 'number' ? etapa.ordem : i + 1}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-800 dark:text-white">{String(etapa.titulo ?? etapa.title ?? '')}</p>
                  {str(etapa.descricao) && <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{str(etapa.descricao)}</p>}
                  {str(etapa.prazo_estimado_dias) && (
                    <p className="text-xs text-blue-500 mt-0.5">
                      Prazo: ~{str(etapa.prazo_estimado_dias)} dias
                      {etapa.prazo_fonte === 'estimativa_profissional' && (
                        <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30">
                          ⚠️ estimativa profissional — sem fonte normativa
                        </span>
                      )}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {rawArr(r.legislacao_aplicavel).length > 0 && (
        <Section icon={BookOpen} title="Legislação Aplicável" color="text-purple-600 dark:text-purple-400">
          <BulletList
            items={rawArr(r.legislacao_aplicavel).map(formatLegislacao).filter(Boolean)}
            color="text-purple-400"
          />
        </Section>
      )}

      {arr(r.documentos_necessarios).length > 0 && (
        <Section icon={FileText} title="Documentos Necessários" color="text-indigo-600 dark:text-indigo-400">
          <BulletList items={arr(r.documentos_necessarios)} color="text-indigo-400" />
        </Section>
      )}

      {str(r.justificativa) && (
        <p className="text-xs text-gray-500 dark:text-slate-400 italic mt-2 bg-gray-50 dark:bg-white/5 p-2 rounded">
          {str(r.justificativa)}
        </p>
      )}
    </div>
  );
}

/**
 * Renderiza o valor de um campo extraído sem NUNCA produzir "[object Object]".
 * Cobre dois shapes do extrator:
 *   - flat:    `{ area: "412 ha" }`                  → "412 ha"
 *   - aninhado:`{ area: { value: "412 ha", confidence: "high" } }` → "412 ha"
 * Qualquer outro objeto cai em `humanizeValue` ("Rótulo: valor · ...").
 */
function extratorFieldValue(value: unknown): string | null {
  if (value == null || value === '') return null;
  if (typeof value === 'object' && !Array.isArray(value)) {
    const o = value as Record<string, unknown>;
    if ('value' in o) return humanizeValue(o.value);
  }
  return humanizeValue(value);
}

function ExtratorResult({ r }: { r: Record<string, unknown> }) {
  const fields = r.extracted_fields as Record<string, unknown> | undefined;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30 font-medium">
          Tipo: {str(r.doc_type ?? '—')}
        </span>
        <span className="text-xs text-gray-500">{str(r.fields_count ?? 0)} campos extraídos</span>
      </div>

      {fields && Object.keys(fields).length > 0 && (
        <div className="bg-gray-50 dark:bg-white/5 rounded-lg p-3 space-y-0.5">
          {Object.entries(fields)
            .filter(([key]) => !isMetaField(key))
            .map(([key, value]) => (
              <KeyValue key={key} label={labelFor(key)} value={extratorFieldValue(value)} />
            ))}
        </div>
      )}
    </div>
  );
}

function OrçamentoResult({ r }: { r: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {typeof r.confidence === 'string' && <ConfidenceBadge confidence={r.confidence} />}
        {typeof r.complexity === 'string' && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 dark:bg-white/10 text-gray-700 dark:text-slate-300 border border-gray-200 dark:border-white/10">
            Complexidade: {str(r.complexity)}
          </span>
        )}
        {r.requires_review === true && <ReviewBadge />}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {r.suggested_value_min != null && (
          <div className="bg-emerald-50 dark:bg-emerald-500/5 p-3 rounded-lg border border-emerald-200 dark:border-emerald-500/20">
            <p className="text-xs text-emerald-600 dark:text-emerald-400">Valor Mínimo</p>
            <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">
              R$ {Number(r.suggested_value_min).toLocaleString('pt-BR')}
            </p>
          </div>
        )}
        {r.suggested_value_max != null && (
          <div className="bg-emerald-50 dark:bg-emerald-500/5 p-3 rounded-lg border border-emerald-200 dark:border-emerald-500/20">
            <p className="text-xs text-emerald-600 dark:text-emerald-400">Valor Máximo</p>
            <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">
              R$ {Number(r.suggested_value_max).toLocaleString('pt-BR')}
            </p>
          </div>
        )}
      </div>

      {r.estimated_days != null && (
        <KeyValue label="Prazo Estimado" value={`${str(r.estimated_days)} dias`} />
      )}

      {objArr(r.scope_items).length > 0 && (
        <Section icon={ListChecks} title="Escopo do Serviço" color="text-emerald-600 dark:text-emerald-400">
          <div className="space-y-1.5">
            {objArr(r.scope_items).map((item, i) => (
              <div key={i} className="flex justify-between items-center text-sm py-1 border-b border-gray-100 dark:border-white/5 last:border-0">
                <span className="text-gray-700 dark:text-slate-300">{String(item.description ?? '')}</span>
                {str(item.estimated_hours) && (
                  <span className="text-xs text-gray-400">{str(item.estimated_hours)}h</span>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function RedatorResult({ r }: { r: Record<string, unknown> }) {
  // Sprint A2-redator-B: lê r.template (PecaJuridicaContent.template) com
  // fallback para r.document_type (formato dict legado de AIJobs antigos +
  // alias computed_field na schema). Frontend cobre os dois shapes.
  const templateValue =
    (typeof r.template === 'string' && r.template) ||
    (typeof r.document_type === 'string' && r.document_type) ||
    null;
  const addressee = typeof r.addressee === 'string' ? r.addressee : null;
  const citationTotal = typeof r.citation_total === 'number' ? r.citation_total : null;
  const citationValid = typeof r.citation_valid === 'boolean' ? r.citation_valid : null;
  const citationCoverage =
    typeof r.citation_coverage_ratio === 'number' ? r.citation_coverage_ratio : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {templateValue && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-500/30 font-medium uppercase">
            {templateValue}
          </span>
        )}
        {addressee && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-gray-50 dark:bg-white/5 text-gray-700 dark:text-slate-300 border border-gray-200 dark:border-white/10">
            Para: {addressee}
          </span>
        )}
        {r.requires_review === true && <ReviewBadge />}
        {citationValid === false && citationTotal !== null && (
          <span
            className="text-xs px-2.5 py-1 rounded-full bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 font-medium"
            title={
              citationCoverage !== null
                ? `Cobertura: ${(citationCoverage * 100).toFixed(0)}%`
                : undefined
            }
          >
            Citações suspeitas
          </span>
        )}
      </div>

      {typeof r.content === 'string' && (
        <div className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg p-4 max-h-96 overflow-y-auto">
          <pre className="text-sm text-gray-800 dark:text-slate-200 whitespace-pre-wrap font-sans leading-relaxed">
            {str(r.content)}
          </pre>
        </div>
      )}
    </div>
  );
}

function FinanceiroResult({ r }: { r: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-white/5">
          <p className="text-xs text-gray-500">Custo IA</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">
            ${Number(r.ai_cost_usd ?? 0).toFixed(4)}
          </p>
        </div>
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-white/5">
          <p className="text-xs text-gray-500">Jobs IA</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">{str(r.ai_job_count ?? 0)}</p>
        </div>
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-500/5">
          <p className="text-xs text-emerald-600">Valor Proposto</p>
          <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">
            R$ {Number(r.total_proposed_value ?? 0).toLocaleString('pt-BR')}
          </p>
        </div>
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-500/5">
          <p className="text-xs text-emerald-600">Valor Aceito</p>
          <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">
            R$ {Number(r.accepted_value ?? 0).toLocaleString('pt-BR')}
          </p>
        </div>
      </div>

      {arr(r.insights).length > 0 && (
        <Section icon={TrendingUp} title="Insights" color="text-blue-600 dark:text-blue-400">
          <BulletList items={arr(r.insights)} color="text-blue-400" />
        </Section>
      )}

      {arr(r.recommendations).length > 0 && (
        <Section icon={CheckCircle2} title="Recomendações" color="text-emerald-600 dark:text-emerald-400">
          <BulletList items={arr(r.recommendations)} color="text-emerald-400" />
        </Section>
      )}
    </div>
  );
}

function AcompanhamentoResult({ r }: { r: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {r.is_agency_response === true && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30 font-medium">
            Resposta de Órgão
          </span>
        )}
        {typeof r.response_type === 'string' && (
          <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
            r.response_type === 'aprovacao' ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300'
            : r.response_type === 'exigencia' ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300'
            : r.response_type === 'indeferimento' ? 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300'
            : 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300'
          }`}>
            {str(r.response_type)}
          </span>
        )}
        {r.action_required === true && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-red-50 text-red-700 border border-red-200 dark:bg-red-500/10 dark:text-red-300 font-medium flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Ação necessária
          </span>
        )}
      </div>

      {str(r.summary) && (
        <p className="text-sm text-gray-700 dark:text-slate-200 leading-relaxed bg-gray-50 dark:bg-white/5 p-3 rounded-lg">
          {str(r.summary)}
        </p>
      )}

      {arr(r.deadlines_detected).length > 0 && (
        <Section icon={Clock} title="Prazos Detectados" color="text-red-600 dark:text-red-400">
          <BulletList items={arr(r.deadlines_detected)} color="text-red-400" />
        </Section>
      )}
    </div>
  );
}

function VigiaResult({ r }: { r: Record<string, unknown> }) {
  const alerts = objArr(r.alerts);
  const severityIcon: Record<string, string> = {
    error: 'text-red-500',
    warning: 'text-amber-500',
  };
  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-700 dark:text-slate-300">
        {alerts.length} alerta(s) encontrado(s)
      </p>
      {alerts.map((alert, i) => (
        <div key={i} className={`p-3 rounded-lg border text-sm flex items-start gap-2 ${
          alert.severity === 'error'
            ? 'bg-red-50 border-red-200 dark:bg-red-500/10 dark:border-red-500/20'
            : 'bg-amber-50 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/20'
        }`}>
          <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${severityIcon[String(alert.severity)] ?? 'text-gray-400'}`} />
          <span className="text-gray-800 dark:text-slate-200">{String(alert.message ?? '')}</span>
        </div>
      ))}
    </div>
  );
}

function MarketingResult({ r }: { r: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {typeof r.content_type === 'string' && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-pink-50 dark:bg-pink-500/10 text-pink-700 dark:text-pink-300 border border-pink-200 dark:border-pink-500/30 font-medium uppercase">
            {str(r.content_type)}
          </span>
        )}
        {typeof r.topic === 'string' && (
          <span className="text-xs text-gray-500">Tema: {str(r.topic)}</span>
        )}
      </div>

      {typeof r.generated_content === 'string' && (
        <div className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg p-4 max-h-64 overflow-y-auto">
          <pre className="text-sm text-gray-800 dark:text-slate-200 whitespace-pre-wrap font-sans leading-relaxed">
            {str(r.generated_content)}
          </pre>
        </div>
      )}
    </div>
  );
}

function GenericResult({ r }: { r: Record<string, unknown> }) {
  // Rede de segurança para agentes sem renderer dedicado. NUNCA faz
  // JSON.stringify nem deixa vazar "[object Object]": escalares viram linha
  // label/valor, arrays de string viram bullets, arrays/objetos com campos
  // escalares viram cards rotulados, e qualquer aninhamento mais profundo é
  // omitido em vez de despejado. Campos meta/internos ocultados via isMetaField.
  const entries = Object.entries(r).filter(
    ([k, v]) => v != null && v !== '' && !isMetaField(k),
  );
  if (entries.length === 0) {
    return <p className="text-sm text-gray-400 italic">Sem detalhes para exibir.</p>;
  }
  const scalarFields = (obj: Record<string, unknown>) =>
    Object.entries(obj).filter(
      ([k, v]) => v != null && v !== '' && typeof v !== 'object' && !isMetaField(k),
    );
  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => {
        const label = labelFor(key);
        if (typeof value !== 'object') {
          return <KeyValue key={key} label={label} value={String(value)} />;
        }
        if (Array.isArray(value)) {
          if (value.length === 0) return null;
          const allScalar = value.every((v) => v == null || typeof v !== 'object');
          return (
            <Section key={key} icon={ListChecks} title={label} color="text-gray-500 dark:text-slate-400">
              {allScalar ? (
                <BulletList items={value.filter((v) => v != null).map((v) => String(v))} />
              ) : (
                <div className="space-y-2">
                  {objArr(value).map((obj, i) => (
                    <div key={i} className="p-2 bg-white dark:bg-white/5 rounded border border-gray-100 dark:border-white/10">
                      {scalarFields(obj).map(([k, v]) => (
                        <KeyValue key={k} label={labelFor(k)} value={String(v)} />
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </Section>
          );
        }
        return (
          <Section key={key} icon={ListChecks} title={label} color="text-gray-500 dark:text-slate-400">
            <div className="bg-white dark:bg-white/5 rounded p-2">
              {scalarFields(value as Record<string, unknown>).map(([k, v]) => (
                <KeyValue key={k} label={labelFor(k)} value={String(v)} />
              ))}
            </div>
          </Section>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Icones por agente
// ---------------------------------------------------------------------------

const AGENT_ICON: Record<string, React.ElementType> = {
  atendimento: Sparkles,
  extrator: Search,
  diagnostico: Stethoscope,
  auditor_imovel: Building2,
  legislacao: Scale,
  redator: FileText,
  orcamento: DollarSign,
  financeiro: TrendingUp,
  acompanhamento: Mail,
  vigia: Shield,
  marketing: Megaphone,
};

const AGENT_TITLE: Record<string, string> = {
  atendimento: 'Classificação da Demanda',
  extrator: 'Campos Extraídos do Documento',
  diagnostico: 'Diagnóstico Ambiental',
  auditor_imovel: 'Auditoria do Imóvel',
  legislacao: 'Enquadramento Regulatório',
  redator: 'Documento Gerado',
  orcamento: 'Proposta de Orçamento',
  financeiro: 'Análise Financeira',
  acompanhamento: 'Análise de Acompanhamento',
  vigia: 'Alertas de Monitoramento',
  marketing: 'Conteúdo de Marketing',
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AgentResultRenderer({ agentName, result }: Props) {
  if (!result || Object.keys(result).length === 0) {
    return <p className="text-sm text-gray-400 italic">Sem resultado disponível.</p>;
  }

  const Icon = AGENT_ICON[agentName ?? ''] ?? Sparkles;
  const title = AGENT_TITLE[agentName ?? ''] ?? 'Resultado do Agente';

  const renderers: Record<string, (r: Record<string, unknown>) => React.ReactNode> = {
    atendimento: (r) => <AtendimentoResult r={r} />,
    extrator: (r) => <ExtratorResult r={r} />,
    diagnostico: (r) => <DiagnósticoResult r={r} />,
    auditor_imovel: (r) => <AuditorResult r={r} />,
    legislacao: (r) => <LegislaçãoResult r={r} />,
    redator: (r) => <RedatorResult r={r} />,
    orcamento: (r) => <OrçamentoResult r={r} />,
    financeiro: (r) => <FinanceiroResult r={r} />,
    acompanhamento: (r) => <AcompanhamentoResult r={r} />,
    vigia: (r) => <VigiaResult r={r} />,
    marketing: (r) => <MarketingResult r={r} />,
  };

  const Renderer = agentName && renderers[agentName] ? renderers[agentName] : null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-purple-500" />
        <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">{title}</p>
      </div>
      {Renderer ? Renderer(result) : <GenericResult r={result} />}
    </div>
  );
}
