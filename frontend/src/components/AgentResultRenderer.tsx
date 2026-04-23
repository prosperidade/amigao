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
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {typeof r.confidence === 'string' && <ConfidenceBadge confidence={r.confidence} />}
        {typeof r.risco_estimado === 'string' && (
          <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
            r.risco_estimado === 'alto' ? 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30'
            : r.risco_estimado === 'medio' ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30'
            : 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30'
          }`}>
            Risco: {str(r.risco_estimado)}
          </span>
        )}
        {r.requires_review === true && <ReviewBadge />}
      </div>

      {str(r.situacao_geral) && (
        <p className="text-sm text-gray-700 dark:text-slate-200 leading-relaxed bg-gray-50 dark:bg-white/5 p-3 rounded-lg">
          {str(r.situacao_geral)}
        </p>
      )}

      {arr(r.passivos_identificados).length > 0 && (
        <Section icon={AlertTriangle} title="Passivos Identificados" color="text-red-600 dark:text-red-400">
          <BulletList items={arr(r.passivos_identificados)} color="text-red-400" />
        </Section>
      )}

      {arr(r.acoes_remediacao).length > 0 && (
        <Section icon={CheckCircle2} title="Ações de Remediação" color="text-emerald-600 dark:text-emerald-400">
          <BulletList items={arr(r.acoes_remediacao)} color="text-emerald-400" />
        </Section>
      )}

      {str(r.observacoes) && (
        <p className="text-xs text-gray-500 dark:text-slate-400 italic mt-2">{str(r.observacoes)}</p>
      )}
    </div>
  );
}

function LegislaçãoResult({ r }: { r: Record<string, unknown> }) {
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
                  {str(etapa.prazo_estimado_dias) && <p className="text-xs text-blue-500 mt-0.5">Prazo: ~{str(etapa.prazo_estimado_dias)} dias</p>}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {arr(r.legislacao_aplicavel).length > 0 && (
        <Section icon={BookOpen} title="Legislação Aplicável" color="text-purple-600 dark:text-purple-400">
          <BulletList items={arr(r.legislacao_aplicavel)} color="text-purple-400" />
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
          {Object.entries(fields).map(([key, value]) => (
            <KeyValue key={key} label={key.replace(/_/g, ' ')} value={value != null ? String(value) : null} />
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
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {typeof r.document_type === 'string' && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-500/30 font-medium uppercase">
            {str(r.document_type)}
          </span>
        )}
        {r.requires_review === true && <ReviewBadge />}
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
  return (
    <div className="bg-gray-50 dark:bg-white/5 rounded-lg p-3">
      {Object.entries(r).filter(([_, v]) => v != null && v !== '').map(([key, value]) => (
        <KeyValue key={key} label={key.replace(/_/g, ' ')} value={
          typeof value === 'object' ? JSON.stringify(value) : String(value)
        } />
      ))}
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
