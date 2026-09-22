/**
 * GeometriaPanel — geometria e confronto de áreas (ADR-072, Incremento 3).
 *
 * Auto-oculta quando o caso não tem arquivo geoespacial — mesmo padrão de
 * ConfrontoIdentidade e CadeiaFichasPanel. Para o KMZ de Jobson: mostra a
 * leitura (ou a falha, com código), as feições calculadas, as medições
 * declaradas encontradas nos documentos, e o confronto — sempre com
 * denominador e tolerância declarados, nunca "sem sobreposição" quando não
 * houver camada carregada.
 *
 * Não decide nada por conta própria: ler o arquivo e rodar o confronto são
 * gestos do consultor; escolher qual feição projeta em Property.geom também
 * — exceto quando há exatamente uma feição poligonal válida, caso em que o
 * próprio backend já projeta (regra `feicao_poligonal_unica`).
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import { MapPin, Loader2, AlertTriangle, CheckCircle2, XCircle, HelpCircle, Ruler } from 'lucide-react';
import { api } from '@/lib/api';

function errDetail(e: unknown, fallback: string): string {
  const ax = e as AxiosError<{ detail?: string }>;
  return ax?.response?.data?.detail ?? ax?.message ?? fallback;
}

interface Feicao {
  id: number;
  ordem: number;
  identificador: string;
  nome: string | null;
  tipo: string;
  valida: boolean;
  motivo_invalidade: string | null;
  aneis_internos: number;
  medicao_id: number | null;
  area_ha: string | null;
  area_estado: string | null;
  area_motivo: string | null;
}

interface Leitura {
  id: number;
  numero: number;
  sha256: string | null;
  membro: string | null;
  crs_origem: string | null;
  metodo_versao: string;
  falha_codigo: string | null;
  falha_detalhe: string | null;
  lido_em: string;
}

interface ArquivoGeo {
  documento_id: number;
  nome: string;
  formato: string;
  estado: string;
  leituras: number;
  leitura: Leitura | null;
  feicoes: Feicao[];
}

interface Medicao {
  id: number;
  origem_tipo: string;
  estado: string;
  valor_ha: string | null;
  motivo: string | null;
  metodo: string;
  fonte: string | null;
  predicado: string | null;
  literal: string | null;
}

interface Projecao {
  feicao_id: number;
  regra: string | null;
  autor_id: number | null;
  motivo: string;
  criada_em: string;
  property_geom_gravada: boolean;
}

interface ConfrontoLinha {
  id: number;
  calculada_ha: string | null;
  referencia_ha: string | null;
  referencia_fonte: string | null;
  referencia_origem: string | null;
  delta_ha: string | null;
  denominador_regra: string;
  denominador_ha: string | null;
  percentual: string | null;
  percentual_sobre_maior: string | null;
  tolerancia_pct: number;
  tolerancia_origem: string;
  resultado: string;
  grau: string;
}

interface GeometriaData {
  process_id: number;
  arquivos: ArquivoGeo[];
  medicoes: Medicao[];
  projecao: Projecao | null;
  confronto: {
    estado: string;
    execucao: string | null;
    executado_em: string | null;
    execucoes: number;
    linhas: ConfrontoLinha[];
  };
  parametros: {
    tolerancia_pct: number;
    tolerancia_origem: string;
    denominador: string;
    metodo_area: string;
    crs_calculo: string;
  };
  sobreposicao: { estado: string; motivo: string };
}

const GRAU_STYLE: Record<string, string> = {
  informativo: 'bg-gray-100 dark:bg-white/10 text-gray-700 dark:text-slate-300',
  atencao: 'bg-amber-100 dark:bg-amber-500/15 text-amber-800 dark:text-amber-300',
  alto: 'bg-orange-100 dark:bg-orange-500/15 text-orange-800 dark:text-orange-300',
  critico: 'bg-red-100 dark:bg-red-500/15 text-red-800 dark:text-red-300',
};

const RESULTADO_LABEL: Record<string, string> = {
  dentro_da_tolerancia: 'dentro da tolerância',
  divergente: 'divergente',
  nao_calculavel: 'não calculável',
};

function fmtHa(v: string | null): string {
  if (v == null) return '—';
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toLocaleString('pt-BR', { maximumFractionDigits: 4 })} ha` : v;
}

function fmtPct(v: string | null): string {
  if (v == null) return '—';
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%` : v;
}

function EstadoArquivo({ arquivo }: { arquivo: ArquivoGeo }) {
  if (arquivo.estado === 'nao_lido') {
    return <span className="text-xs text-gray-500 dark:text-slate-400">Ainda não lido</span>;
  }
  if (arquivo.estado === 'falha') {
    return (
      <span className="text-xs text-red-700 dark:text-red-300 flex items-center gap-1">
        <XCircle className="w-3.5 h-3.5 shrink-0" />
        Falha na leitura [{arquivo.leitura?.falha_codigo}]: {arquivo.leitura?.falha_detalhe}
      </span>
    );
  }
  return (
    <span className="text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-1">
      <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
      Lido — {arquivo.feicoes.length} feição(ões)
    </span>
  );
}

export default function GeometriaPanel({ processId }: { processId: number }) {
  const qc = useQueryClient();
  const [projetando, setProjetando] = useState<{ feicaoId: number; motivo: string } | null>(null);

  const { data, isLoading } = useQuery<GeometriaData>({
    queryKey: ['geometria', processId],
    queryFn: () => api.get(`/processes/${processId}/geometria`).then(r => r.data),
  });

  const ler = useMutation({
    mutationFn: (documentoId: number) =>
      api.post(`/processes/${processId}/geometria/documentos/${documentoId}/ler`).then(r => r.data),
    onSuccess: (result: GeometriaData) => {
      qc.setQueryData(['geometria', processId], result);
      toast.success('Geometria lida.');
    },
    onError: (e) => toast.error(errDetail(e, 'Falha ao ler a geometria.')),
  });

  const confrontar = useMutation({
    mutationFn: () => api.post(`/processes/${processId}/geometria/confronto`).then(r => r.data),
    onSuccess: (result: GeometriaData) => {
      qc.setQueryData(['geometria', processId], result);
      toast.success('Confronto de áreas executado.');
    },
    onError: (e) => toast.error(errDetail(e, 'Falha ao rodar o confronto.')),
  });

  const projetar = useMutation({
    mutationFn: (p: { feicaoId: number; motivo: string }) =>
      api.post(`/processes/${processId}/geometria/projecao`, { feicao_id: p.feicaoId, motivo: p.motivo }).then(r => r.data),
    onSuccess: (result: GeometriaData) => {
      qc.setQueryData(['geometria', processId], result);
      setProjetando(null);
      toast.success('Geometria do imóvel escolhida.');
    },
    onError: (e) => toast.error(errDetail(e, 'Falha ao escolher a geometria.')),
  });

  if (isLoading) return null;
  // Sem arquivo geoespacial neste caso, nada a mostrar (mesmo padrão de
  // ConfrontoIdentidade: painel só existe quando há o que confrontar).
  if (!data || data.arquivos.length === 0) return null;

  const podeConfrontar = data.medicoes.some(m => m.origem_tipo === 'feicao_calculada' && m.estado === 'determinado');

  return (
    <div className="rounded-2xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 dark:border-white/10 flex items-start gap-3">
        <MapPin className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Geometria e confronto de áreas</h3>
          <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
            Denominador: {data.parametros.denominador === 'referencia_documental' ? 'área documental' : data.parametros.denominador}
            {' · '}Tolerância: {data.parametros.tolerancia_pct}% ({data.parametros.tolerancia_origem === 'provisoria_regua_onda_c_pendente_q_isis_04'
              ? 'provisória, pendente da Ísis' : data.parametros.tolerancia_origem})
          </p>
        </div>
      </div>

      {/* Arquivos geoespaciais do caso. */}
      <div className="px-5 py-4 space-y-3">
        {data.arquivos.map(arquivo => (
          <div key={arquivo.documento_id} className="rounded-xl border border-gray-200 dark:border-white/10 p-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">{arquivo.nome}</p>
                <EstadoArquivo arquivo={arquivo} />
              </div>
              <button
                onClick={() => ler.mutate(arquivo.documento_id)}
                disabled={ler.isPending}
                className="text-xs px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 flex items-center gap-1.5 disabled:opacity-50"
              >
                {ler.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {arquivo.estado === 'lido' ? 'Reler geometria' : 'Ler geometria'}
              </button>
            </div>

            {arquivo.feicoes.length > 0 && (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {arquivo.feicoes.map(f => (
                  <div key={f.id} className="rounded-lg border border-gray-100 dark:border-white/10 bg-gray-50 dark:bg-white/5 p-2.5 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-gray-800 dark:text-slate-200 truncate">
                        {f.nome || f.identificador} <span className="text-gray-400">({f.tipo})</span>
                      </span>
                      {!f.valida && (
                        <span title={f.motivo_invalidade ?? ''}>
                          <AlertTriangle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-gray-600 dark:text-slate-400">
                      {f.area_estado === 'determinado' ? (
                        <span className="flex items-center gap-1"><Ruler className="w-3 h-3" /> {fmtHa(f.area_ha)}</span>
                      ) : f.area_motivo ? (
                        <span className="text-amber-700 dark:text-amber-400">Não determinado: {f.area_motivo}</span>
                      ) : (
                        <span className="text-gray-400">sem medição</span>
                      )}
                    </p>
                    {!f.valida && (
                      <button
                        onClick={() => setProjetando({ feicaoId: f.id, motivo: '' })}
                        className="mt-1.5 text-[11px] text-gray-400 cursor-not-allowed"
                        disabled
                        title="Só feição poligonal válida pode ser a geometria do imóvel"
                      >
                        geometria inválida — não pode ser projetada
                      </button>
                    )}
                    {f.valida && (f.tipo === 'poligono' || f.tipo === 'multipoligono') && (
                      <button
                        onClick={() => setProjetando({ feicaoId: f.id, motivo: '' })}
                        className="mt-1.5 text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        {data.projecao?.feicao_id === f.id ? 'geometria do imóvel ✓' : 'usar como geometria do imóvel'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Escolha de projeção — motivo obrigatório (ADR-072 §6). */}
      {projetando && (
        <div className="mx-5 mb-4 rounded-xl border border-blue-200 dark:border-blue-500/30 bg-blue-50/60 dark:bg-blue-500/5 p-3">
          <p className="text-xs font-medium text-gray-800 dark:text-slate-200 mb-1.5">
            Por que esta feição é a geometria do imóvel?
          </p>
          <textarea
            value={projetando.motivo}
            onChange={e => setProjetando({ ...projetando, motivo: e.target.value })}
            placeholder="Ex.: única feição que corresponde ao perímetro do CAR nº..."
            className="w-full text-xs rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-2 min-h-[60px]"
          />
          <div className="mt-2 flex gap-2 justify-end">
            <button onClick={() => setProjetando(null)} className="text-xs px-3 py-1.5 rounded-lg text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-white/10">
              Cancelar
            </button>
            <button
              onClick={() => projetando.motivo.trim() && projetar.mutate({ feicaoId: projetando.feicaoId, motivo: projetando.motivo })}
              disabled={!projetando.motivo.trim() || projetar.isPending}
              className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white disabled:opacity-50"
            >
              Confirmar
            </button>
          </div>
        </div>
      )}

      {/* Medições declaradas — o que os documentos dizem sobre a área. */}
      {data.medicoes.filter(m => m.origem_tipo !== 'feicao_calculada').length > 0 && (
        <div className="px-5 pb-4">
          <p className="text-xs font-medium text-gray-700 dark:text-slate-300 mb-2">Áreas declaradas nos documentos</p>
          <div className="space-y-1.5">
            {data.medicoes.filter(m => m.origem_tipo !== 'feicao_calculada').map(m => (
              <div key={m.id} className="text-xs flex items-center gap-2 flex-wrap">
                <span className="text-gray-500 dark:text-slate-400 shrink-0">{m.fonte ?? `doc ${m.id}`}:</span>
                {m.estado === 'determinado' ? (
                  <span className="font-medium text-gray-800 dark:text-slate-200">{fmtHa(m.valor_ha)}</span>
                ) : (
                  <span className="text-amber-700 dark:text-amber-400 flex items-center gap-1">
                    <HelpCircle className="w-3 h-3" /> não determinado — {m.motivo}
                  </span>
                )}
                {m.literal && <span className="text-gray-400 truncate">"{m.literal}"</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Confronto. */}
      <div className="px-5 py-4 border-t border-gray-100 dark:border-white/10">
        <div className="flex items-center justify-between gap-3 mb-2">
          <p className="text-xs font-medium text-gray-700 dark:text-slate-300">Confronto de áreas</p>
          {podeConfrontar && (
            <button
              onClick={() => confrontar.mutate()}
              disabled={confrontar.isPending}
              className="text-xs px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 flex items-center gap-1.5 disabled:opacity-50"
            >
              {confrontar.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {data.confronto.execucoes > 0 ? 'Rodar novo confronto' : 'Rodar confronto'}
            </button>
          )}
        </div>

        {!podeConfrontar && (
          <p className="text-xs text-gray-500 dark:text-slate-400">
            Nenhuma feição poligonal calculada ainda — leia um arquivo geoespacial acima.
          </p>
        )}

        {data.confronto.linhas.length === 0 && podeConfrontar && data.confronto.execucoes === 0 && (
          <p className="text-xs text-gray-500 dark:text-slate-400">
            Geometria lida, mas nenhuma área declarada nos documentos para confrontar ainda.
          </p>
        )}

        {data.confronto.linhas.map(linha => (
          <div key={linha.id} className="rounded-lg border border-gray-200 dark:border-white/10 p-3 mb-2 text-xs">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="text-gray-700 dark:text-slate-300">
                {fmtHa(linha.calculada_ha)} (calculada) × {fmtHa(linha.referencia_ha)} ({linha.referencia_fonte ?? linha.referencia_origem})
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${GRAU_STYLE[linha.grau] ?? GRAU_STYLE.informativo}`}>
                {linha.grau}
              </span>
            </div>
            <p className="mt-1 text-gray-500 dark:text-slate-400">
              Δ {fmtHa(linha.delta_ha)} · {fmtPct(linha.percentual)} sobre a área documental
              {linha.percentual_sobre_maior != null && ` (${fmtPct(linha.percentual_sobre_maior)} sobre o maior valor)`}
              {' · '}tolerância {linha.tolerancia_pct}% · {RESULTADO_LABEL[linha.resultado] ?? linha.resultado}
            </p>
          </div>
        ))}

        {data.confronto.executado_em && (
          <p className="text-[11px] text-gray-400 dark:text-slate-500 mt-1">
            Última execução: {new Date(data.confronto.executado_em).toLocaleString('pt-BR')}
            {data.confronto.execucoes > 1 && ` (${data.confronto.execucoes} execuções — reexecutar não substitui as anteriores)`}
          </p>
        )}
      </div>

      {/* Sobreposição — sempre "não verificado" enquanto não houver camada. */}
      <div className="px-5 py-3 border-t border-gray-100 dark:border-white/10 bg-gray-50/50 dark:bg-white/5">
        <p className="text-[11px] text-gray-500 dark:text-slate-400 flex items-center gap-1.5">
          <HelpCircle className="w-3.5 h-3.5 shrink-0" />
          Sobreposição espacial: {data.sobreposicao.motivo}
        </p>
      </div>
    </div>
  );
}
