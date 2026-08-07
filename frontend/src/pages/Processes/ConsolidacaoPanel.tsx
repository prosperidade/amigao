/**
 * ConsolidacaoPanel — Ficha 01 / FASE 4: decisão do consultor + consolidação.
 *
 * Estende a aba "Alertas": lista os campos do staging agrupados por entidade
 * (Cliente / Imóvel / Matrícula), com valor por fonte, status colorido e ações
 * (Aceitar · Escolher fonte · Editar · Rejeitar). Banner de aceite em lote dos
 * consistentes e botão "Consolidar na base". Tudo determinístico — o consultor
 * decide, o sistema grava.
 */

import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import {
  CheckCircle2, XCircle, Pencil, ListChecks, Database, Loader2, Layers, ArrowRight, RotateCcw, AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { acoesKeys } from '@/lib/acoes/hooks';
import { labelFor, humanizeValue } from '@/lib/labels/fieldLabels';
import { docTypeLabel } from '@/lib/labels/docLabels';

/** Mensagem de erro legível a partir do AxiosError (detail do backend, senão genérica). */
function errDetail(e: unknown, fallback: string): string {
  const ax = e as AxiosError<{ detail?: string }>;
  return ax?.response?.data?.detail ?? ax?.message ?? fallback;
}

interface StagingField {
  id: number;
  source_doc_type: string | null;
  field_name: string;
  field_value: { value?: unknown; unidade?: string } | null;
  confidence: string | null;
  target_entity: string | null;
  target_field: string | null;
  matricula_hint: string | null;
  status: string;
  decided_value: { value?: unknown } | null;
  // Item 6 — aceite que não vai pousar na base (computado no servidor, durável).
  sem_casa?: boolean;
  sem_casa_motivo?: string | null;
  /** Nome do documento de origem — separa os quadros sem número de matrícula. */
  source_doc_nome?: string | null;
  // "Aceito" ≠ "Gravado" (validações 30/07 e 02/08). Aceitar é decidir; gravar
  // é o clique seguinte. Enquanto as duas coisas mostravam a mesma palavra, a
  // consultora não tinha como distinguir o campo que pousou na base do que foi
  // recusado — e leu "gravou apenas três" numa consolidação de dezesseis
  // campos. Vem de `consolidated_at` no servidor.
  gravado?: boolean;
  gravado_em?: string | null;
}

interface ConsolidationResult {
  campos_gravados: number;
  matriculas_criadas: number;
  matriculas_atualizadas: number;
  cliente_atualizado: boolean;
  imovel_atualizado: boolean;
  area_total_matriculas: number | null;
  acoes_criadas: number;
  // Aceites que NÃO viraram dado na base. O backend já os listava; a tela
  // nunca os mostrou — e foi assim que o NIRF e o VTN do caso 15 sumiram em
  // silêncio depois de o consultor ter aceitado os dois.
  ignorados: string[];
  // Validação 02/08 — o TERCEIRO caminho do aceite que não vira dado, e o único
  // que ainda era mudo. Quando dois documentos trazem valores completos e
  // conflitantes para o MESMO destino, a consolidação não desempata: devolve as
  // linhas a `divergente_transcricao`, LIMPA a decisão e cria uma Ação. Correto
  // — mas, da cadeira da consultora, o aceite dela simplesmente evaporava. Era o
  // mesmo furo que o `ignorados` fechou em 26/07, deixado pela metade.
  divergencias_devolvidas: Array<{
    entity: string;
    matricula_hint: string | null;
    field: string;
    valores: unknown[];
    staging_ids: number[];
  }>;
}

const STATUS_CLS: Record<string, string> = {
  pendente: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300 dark:border-white/10',
  consistente: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30',
  divergente_transcricao: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
  divergente_fundo: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-500/10 dark:text-orange-300 dark:border-orange-500/30',
  aceito: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30',
  rejeitado: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
};
const STATUS_LABEL: Record<string, string> = {
  pendente: 'Pendente', consistente: 'Consistente', divergente_transcricao: 'Divergente (transcrição)',
  divergente_fundo: 'Divergente (fundo)', aceito: 'Aceito', rejeitado: 'Rejeitado',
};

function entityLabel(f: StagingField, rotulos: Record<string, string> = {}): string {
  if (f.target_entity === 'cliente') return 'Cliente';
  if (f.target_entity === 'imovel') return 'Imóvel';
  if (f.target_entity === 'matricula') {
    if (!f.matricula_hint) {
      // 26/07 — antes retornava 'Matrícula' seco e TODAS as linhas sem número
      // caíam no mesmo quadro: no caso 15, 15 linhas de 3 documentos distintos
      // (2 ITRs + 1 contrato), com denominação/área repetidas sem dizer de onde
      // vinham. Agrupar pelo DOCUMENTO desfaz a mistura: o ITR não declara nº de
      // matrícula (identifica por NIRF/INCRA), e isso é uma informação útil —
      // não um defeito a esconder.
      const doc = f.source_doc_nome?.trim();
      return doc
        ? `Sem matrícula declarada — ${doc}`
        : 'Sem matrícula declarada';
    }
    // Rótulo de linhagem (item 4): "Matrícula 2923 — ficha anterior da 4698"
    // quando a cadeia já existe, para os itens do CCIR (hint defasado) não
    // parecerem um imóvel à parte.
    const rot = rotulos[f.matricula_hint.replace(/\D/g, '')];
    return rot ? `Matrícula ${f.matricula_hint} — ${rot}` : `Matrícula ${f.matricula_hint}`;
  }
  return 'Outros';
}

function fieldValueStr(f: StagingField): string {
  const v = f.decided_value?.value ?? f.field_value?.value;
  const s = humanizeValue(v);
  return f.field_value?.unidade ? `${s} ${f.field_value.unidade}` : s;
}

export default function ConsolidacaoPanel({ processId }: { processId: number }) {
  const qc = useQueryClient();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [consolidated, setConsolidated] = useState<ConsolidationResult | null>(null);

  const { data: fields = [], isLoading } = useQuery<StagingField[]>({
    queryKey: ['staging-fields', processId],
    queryFn: () => api.get(`/processes/${processId}/staging-fields`).then(r => r.data),
  });
  const { data: rotulos = {} } = useQuery<Record<string, string>>({
    queryKey: ['matriculas-rotulos', processId],
    queryFn: () => api.get(`/processes/${processId}/matriculas-rotulos`).then(r => r.data),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['staging-fields', processId] });
  // Uma decisão de campo pode mudar o confronto de identidade e a cadeia — ao
  // reabrir, os dois têm de voltar a aparecer. Invalida as três leituras juntas.
  const invalidateConferencia = () => {
    invalidate();
    qc.invalidateQueries({ queryKey: ['confronto-identidade', processId] });
    qc.invalidateQueries({ queryKey: ['chain-proposals', processId] });
  };

  const decide = useMutation({
    mutationFn: (p: { id: number; acao: string; valor?: string }) =>
      api.post(`/processes/${processId}/staging-fields/${p.id}/decidir`, { acao: p.acao, valor: p.valor }).then(r => r.data),
    onSuccess: (_data, variables) => {
      setEditingId(null);
      invalidateConferencia();
      if (variables.acao === 'criar_acao') {
        qc.invalidateQueries({ queryKey: acoesKeys.list(processId) });
        toast.success('Ação criada na aba Ações a partir da divergência.');
      }
    },
    onError: (e) => toast.error(errDetail(e, 'Falha ao decidir o campo.')),
  });
  const acceptAll = useMutation({
    mutationFn: () => api.post(`/processes/${processId}/staging-fields/aceitar-consistentes`, {}).then(r => r.data),
    onSuccess: invalidate,
    onError: (e) => toast.error(errDetail(e, 'Falha ao aceitar os consistentes.')),
  });
  const consolidate = useMutation<ConsolidationResult>({
    mutationFn: () => api.post(`/processes/${processId}/consolidar`, {}).then(r => r.data),
    onSuccess: (res) => {
      setConsolidated(res);
      invalidate();
      // O aceite perdido merece o mesmo destaque do sucesso: se o consultor
      // decidiu e o dado não entrou, ele precisa saber AGORA, não descobrir
      // semanas depois com o campo vazio no dossiê.
      //
      // Mas RESSALVA NÃO É ERRO (validação 30/07): isto era um `toast.error`
      // vermelho disparado no caminho de SUCESSO, e a consultora leu "gravar na
      // base deu erro" numa gravação que funcionou. Vermelho é reservado para o
      // que de fato falhou — a ressalva vem em âmbar, junto do número gravado,
      // apontando o detalhe. Sinalizar sem alarmar.
      const ignorados = res.ignorados?.length ?? 0;
      const devolvidas = res.divergencias_devolvidas?.length ?? 0;
      const naoGravados = ignorados + devolvidas;
      const base = `Gravado na base: ${res.campos_gravados} campo(s)${res.acoes_criadas > 0 ? ` · ${res.acoes_criadas} ação(ões)` : ''}.`;
      if (naoGravados > 0) {
        toast(`${base} ${naoGravados} aceite(s) não viraram dado — veja o detalhe abaixo.`, {
          icon: '⚠️',
          style: { background: '#fffbeb', color: '#92400e', border: '1px solid #fcd34d' },
          duration: 6000,
        });
      } else {
        toast.success(base);
      }
    },
    onError: (e) => toast.error(errDetail(e, 'Falha ao consolidar na base.')),
  });

  const consistentesCount = useMemo(() => fields.filter(f => f.status === 'consistente').length, [fields]);
  const pendentesObrig = useMemo(
    () => fields.filter(f => f.status === 'divergente_transcricao').length,
    [fields],
  );
  // Campos que GRAVAM na consolidação (escolhido/editado já viram 'aceito').
  const consolidaveis = useMemo(() => fields.filter(f => f.status === 'aceito').length, [fields]);
  // Já na base (carimbo do servidor). O rodapé conta as duas coisas separadas:
  // o que ainda vai pousar e o que já pousou — antes só existia a primeira, e
  // consolidar de novo parecia não ter feito nada.
  const jaGravados = useMemo(() => fields.filter(f => f.gravado).length, [fields]);
  const grupos = useMemo(() => {
    const by: Record<string, StagingField[]> = {};
    for (const f of fields) {
      const k = entityLabel(f, rotulos);
      (by[k] ||= []).push(f);
    }
    for (const k of Object.keys(by)) {
      by[k].sort((a, b) => (a.target_field || '').localeCompare(b.target_field || ''));
    }
    return by;
  }, [fields, rotulos]);

  if (isLoading) {
    return <p className="text-sm text-gray-500 dark:text-slate-400 flex items-center gap-1.5"><Loader2 className="w-4 h-4 animate-spin" /> Carregando campos…</p>;
  }
  if (fields.length === 0) return null;

  return (
    <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Layers className="w-4 h-4 text-purple-500" /> Decisão & Consolidação
        </h3>
        {consistentesCount > 0 && (
          <button
            onClick={() => acceptAll.mutate()}
            disabled={acceptAll.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-medium"
          >
            <ListChecks className="w-3.5 h-3.5" /> Aceitar todos os consistentes ({consistentesCount})
          </button>
        )}
      </div>

      {Object.entries(grupos).map(([grupo, rows]) => (
        <div key={grupo}>
          <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-1.5">{grupo}</p>
          <div className="space-y-1.5">
            {rows.map(f => (
              <div key={f.id} className="flex items-center gap-3 flex-wrap p-2.5 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5">
                <div className="flex-1 min-w-[160px]">
                  <p className="text-sm text-gray-800 dark:text-slate-200">{labelFor(f.target_field || f.field_name)}</p>
                  {/* Item 14 — `source_doc_type` é chave de banco ("auto_infracao",
                      "rg_cpf"); passa pelo dicionário antes de virar tela. */}
                  <p className="text-xs text-gray-400 dark:text-slate-500">
                    {docTypeLabel(f.source_doc_type)} · {fieldValueStr(f)}
                  </p>
                </div>
                {/* O estado que faltava. "Aceito" é decisão do consultor;
                    "Gravado na base" é consequência do clique em Gravar. Eram a
                    mesma palavra na tela, e é por isso que uma consolidação de
                    16 campos foi lida como "gravou apenas três". */}
                {f.gravado ? (
                  <span
                    title={f.gravado_em ? `Gravado em ${new Date(f.gravado_em).toLocaleString('pt-BR')}` : undefined}
                    className="flex items-center gap-1 text-xs px-2 py-0.5 rounded border whitespace-nowrap bg-emerald-600 text-white border-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40"
                  >
                    <Database className="w-3 h-3" /> Gravado na base
                  </span>
                ) : (
                  <span className={`text-xs px-2 py-0.5 rounded border whitespace-nowrap ${STATUS_CLS[f.status] ?? ''}`}>
                    {STATUS_LABEL[f.status] ?? f.status}
                  </span>
                )}
                {/* Selo legível (26/07): o motivo sai do tooltip e vira texto na
                    linha. Tooltip só é lido por quem já desconfia — e a queixa
                    era exatamente não entender por que o aceite não pousou. */}
                {f.sem_casa && (
                  <span className="basis-full order-last flex items-start gap-1.5 text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded px-2 py-1">
                    <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
                    <span>
                      <strong className="font-semibold">Aceito, mas não entra na base:</strong>{' '}
                      {f.sem_casa_motivo ?? 'este campo não tem destino no cadastro.'}
                    </span>
                  </span>
                )}
                {editingId === f.id ? (
                  <div className="flex items-center gap-1">
                    <input
                      value={editValue}
                      onChange={e => setEditValue(e.target.value)}
                      placeholder="Novo valor"
                      className="px-2 py-1 text-xs rounded border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-gray-800 dark:text-white w-28"
                    />
                    <button onClick={() => decide.mutate({ id: f.id, acao: 'editar', valor: editValue })}
                      className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white">Salvar</button>
                    <button onClick={() => setEditingId(null)} className="text-xs px-1.5 py-1 text-gray-400">×</button>
                  </div>
                ) : f.status === 'aceito' || f.status === 'rejeitado' ? (
                  <div className="flex items-center gap-2">
                    {/* Aceite que ainda não pousou diz o que falta acontecer —
                        e o que falta é um clique, não uma espera. */}
                    <span className="text-xs text-gray-400 dark:text-slate-500">
                      {f.status === 'rejeitado'
                        ? 'rejeitado'
                        : f.gravado ? 'na base' : 'aguardando "Gravar na base"'}
                    </span>
                    {/* Reabrir devolve o campo a PENDENTE — o roteiro da Isis
                        exigia rever uma decisão e não havia botão (o confronto
                        e a cadeia voltam a aparecer com a decisão reaberta). */}
                    <button onClick={() => decide.mutate({ id: f.id, acao: 'reabrir' })}
                      title="Reabrir esta decisão (volta a pendente)"
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-white/10">
                      <RotateCcw className="w-3 h-3" /> Reabrir
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    {f.status === 'divergente_transcricao' ? (
                      <>
                        <button onClick={() => decide.mutate({ id: f.id, acao: 'escolher_fonte' })}
                          title="Escolher esta fonte"
                          className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white">
                          <CheckCircle2 className="w-3 h-3" /> Escolher fonte
                        </button>
                        {/* Item 6 (Ficha 07 §3.3) — 3º caminho explícito: criar ação
                            agora, sem esperar a Consolidação decidir por trás. */}
                        <button onClick={() => decide.mutate({ id: f.id, acao: 'criar_acao' })}
                          title="Criar uma ação na aba Ações a partir desta divergência"
                          className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-purple-200 dark:border-purple-500/30 text-purple-600 dark:text-purple-300 hover:bg-purple-50 dark:hover:bg-purple-500/10">
                          <ArrowRight className="w-3 h-3" /> Criar ação
                        </button>
                      </>
                    ) : (
                      <button onClick={() => decide.mutate({ id: f.id, acao: 'aceitar' })}
                        title="Aceitar"
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white">
                        <CheckCircle2 className="w-3 h-3" /> Aceitar
                      </button>
                    )}
                    <button onClick={() => { setEditingId(f.id); setEditValue(''); }} title="Editar manual"
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-white/10">
                      <Pencil className="w-3 h-3" /> Editar
                    </button>
                    <button onClick={() => decide.mutate({ id: f.id, acao: 'rejeitar' })} title="Rejeitar"
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-500/10">
                      <XCircle className="w-3 h-3" /> Rejeitar
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* P12: aceite que não achou destino aparece — nunca some calado. */}
      {consolidated && consolidated.ignorados?.length > 0 && (
        <div className="rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 p-3 space-y-1">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
            {consolidated.ignorados.length} campo(s) aceito(s) não foram gravados
          </p>
          <ul className="text-xs text-amber-700 dark:text-amber-400 space-y-0.5">
            {consolidated.ignorados.map((motivo, i) => (
              <li key={i}>· {motivo}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Aceite devolvido por conflito — some do valor gravado, mas não da tela. */}
      {consolidated && (consolidated.divergencias_devolvidas?.length ?? 0) > 0 && (
        <div className="rounded-lg bg-orange-50 dark:bg-orange-500/10 border border-orange-200 dark:border-orange-500/30 p-3 space-y-1">
          <p className="text-sm font-medium text-orange-800 dark:text-orange-300">
            {consolidated.divergencias_devolvidas.length} campo(s) aceito(s) voltaram como divergência
          </p>
          <p className="text-xs text-orange-700 dark:text-orange-400">
            Dois documentos trazem valores diferentes para o mesmo campo. A base não
            escolhe por você: o valor não foi gravado e cada caso virou uma Ação.
          </p>
          <ul className="text-xs text-orange-700 dark:text-orange-400 space-y-0.5 pt-1">
            {consolidated.divergencias_devolvidas.map((d, i) => (
              <li key={i}>
                · <strong>{d.field}</strong>
                {d.matricula_hint ? ` (matrícula ${d.matricula_hint})` : ''}
                {': '}
                {d.valores.map(v => String(v)).join('  ×  ')}
              </li>
            ))}
          </ul>
        </div>
      )}

      {consolidated && (
        <div className="rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 p-3 text-sm text-emerald-800 dark:text-emerald-300">
          Consolidado: {consolidated.campos_gravados} campo(s) gravado(s) · {consolidated.matriculas_criadas} matrícula(s) criada(s)
          {consolidated.matriculas_atualizadas > 0 && ` · ${consolidated.matriculas_atualizadas} atualizada(s)`}
          {consolidated.acoes_criadas > 0 && ` · ${consolidated.acoes_criadas} ação(ões) criada(s) para divergências`}
          {consolidated.area_total_matriculas != null && ` · área total (soma das matrículas): ${consolidated.area_total_matriculas} ha`}.
        </div>
      )}

      {/* Ação PRINCIPAL da aba Conferência — barra fixa (sticky) no rodapé do
          card pra ficar sempre à vista, não enterrada no fim do scroll. */}
      <div className="sticky bottom-0 z-10 -mx-5 -mb-5 px-5 py-3 rounded-b-xl border-t border-gray-200 dark:border-white/10 bg-white/95 dark:bg-zinc-900/95 backdrop-blur flex items-center justify-between gap-3 flex-wrap">
        <div className="text-xs text-gray-500 dark:text-slate-400 min-w-0">
          {`${consolidaveis} campo(s) serão gravados`}
          {jaGravados > 0 && ` · ${jaGravados} já na base`}
          {pendentesObrig > 0 && ` · ${pendentesObrig} divergência(s) virarão ações a resolver`}.
          {/* A REGRA, escrita (26/07): a pergunta "por que aceitei e não gravou?"
              é respondida ANTES do clique, na própria tela — não depois, no
              suporte. Espelha exatamente o que a consolidação faz. */}
          <p className="mt-0.5 text-[11px] text-gray-400 dark:text-slate-500">
            Aceitar não grava: grava aqui. Cada campo entra na ficha da matrícula
            indicada — sem matrícula-alvo, vira pendência de vínculo e continua
            nesta lista, marcado.
          </p>
        </div>
        <button
          onClick={() => consolidate.mutate()}
          disabled={consolidate.isPending || consolidaveis === 0}
          title={
            consolidaveis === 0
              ? 'Aceite ao menos um campo para gravar.'
              : 'Grava na base os campos que você aceitou. Campo com matrícula-alvo entra na ficha dela; sem alvo, fica como pendência de vínculo. Divergências não resolvidas viram ações.'
          }
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium"
        >
          {consolidate.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
          Gravar na base
        </button>
      </div>
    </div>
  );
}
