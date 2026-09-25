/**
 * React Query hooks do fechamento comercial (ADR-074) e do motor jurídico (ADR-073).
 *
 * Endpoints (espelham `app/api/v1/comercial.py` e `app/api/v1/motor_juridico.py`):
 * - `GET/POST /processes/{pid}/comercial/redacao`, `POST .../redacao/{id}/revisar`
 * - `GET/POST /processes/{pid}/comercial/orcamento`, `PATCH .../orcamento/passos/{passo}`,
 *   `POST .../orcamento/{id}/revisar`
 * - `GET /comercial/metodos`
 * - `GET /processes/{pid}/evidencias/{tipo}/{id}`
 * - `GET /processes/{pid}/motor/execucoes/ultima`, `POST /processes/{pid}/rota/gerar-motor`,
 *   `POST /processes/{pid}/motor/alertas/{avaliacao}/ciencia`
 *
 * Toda mutação invalida o conjunto do caso: redação, orçamento, Rota e execução
 * andam juntos (a atualidade de um lê a base dos outros).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { rotaKeys } from '@/lib/rota/hooks';
import type { RotaMaterializeResponse } from '@/lib/rota/types';
import type {
  EvidenciaDetalhe,
  EvidenciaTipo,
  ExecucaoRelatorio,
  MetodoOrcamento,
  Orcamento,
  OrcamentoOut,
  Redacao,
  RedacoesOut,
} from './types';

export const comercialKeys = {
  redacao: (pid: number) => ['comercial-redacao', pid] as const,
  orcamento: (pid: number) => ['comercial-orcamento', pid] as const,
  metodos: ['comercial-metodos'] as const,
  execucao: (pid: number) => ['motor-execucao', pid] as const,
  evidencia: (pid: number, tipo: string, id: number) => ['evidencia', pid, tipo, id] as const,
};

function useInvalidarCaso(processId: number) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: comercialKeys.redacao(processId) });
    qc.invalidateQueries({ queryKey: comercialKeys.orcamento(processId) });
    qc.invalidateQueries({ queryKey: comercialKeys.execucao(processId) });
    qc.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    qc.invalidateQueries({ queryKey: ['proposals', processId] });
  };
}

export function useRedacoes(processId: number) {
  return useQuery<RedacoesOut>({
    queryKey: comercialKeys.redacao(processId),
    queryFn: async () => (await api.get(`/processes/${processId}/comercial/redacao`)).data,
    enabled: !!processId,
  });
}

export function useGerarRedacao(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async () =>
      (await api.post(`/processes/${processId}/comercial/redacao`)).data as {
        relatorio_preliminar: Redacao;
        especificacao_escopo: Redacao;
      },
    onSuccess: invalidar,
  });
}

export interface RevisaoPayload {
  acao: 'aprovar' | 'rejeitar';
  justificativa: string;
}

export function useRevisarRedacao(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async ({ redacaoId, ...body }: RevisaoPayload & { redacaoId: number }) =>
      (await api.post(`/processes/${processId}/comercial/redacao/${redacaoId}/revisar`, body)).data as Redacao,
    onSuccess: invalidar,
  });
}

export function useOrcamento(processId: number) {
  return useQuery<OrcamentoOut>({
    queryKey: comercialKeys.orcamento(processId),
    queryFn: async () => (await api.get(`/processes/${processId}/comercial/orcamento`)).data,
    enabled: !!processId,
  });
}

export function useGerarOrcamento(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async () => (await api.post(`/processes/${processId}/comercial/orcamento`)).data as Orcamento,
    onSuccess: invalidar,
  });
}

export function useEscolherNoPasso(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async ({
      passoId,
      metodo_codigo,
      quantidade,
    }: {
      passoId: number;
      metodo_codigo?: string | null;
      quantidade?: string | null;
    }) =>
      (await api.patch(`/processes/${processId}/comercial/orcamento/passos/${passoId}`, {
        metodo_codigo: metodo_codigo ?? null,
        quantidade: quantidade ?? null,
      })).data as Orcamento,
    onSuccess: invalidar,
  });
}

export function useRevisarOrcamento(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async ({ orcamentoId, ...body }: RevisaoPayload & { orcamentoId: number }) =>
      (await api.post(`/processes/${processId}/comercial/orcamento/${orcamentoId}/revisar`, body)).data as Orcamento,
    onSuccess: invalidar,
  });
}

export function useMetodos() {
  return useQuery<{ correntes: MetodoOrcamento[]; versoes: MetodoOrcamento[] }>({
    queryKey: comercialKeys.metodos,
    queryFn: async () => (await api.get('/comercial/metodos')).data,
    staleTime: 60_000,
  });
}

/** Proposta nasce do orçamento aprovado e atual (ADR-074 §7): o servidor copia itens e total dele. */
export function useCriarPropostaDoOrcamento(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async ({ orcamentoId, clientId, titulo }: { orcamentoId: number; clientId: number; titulo: string }) =>
      (await api.post('/proposals/', {
        client_id: clientId,
        process_id: processId,
        orcamento_id: orcamentoId,
        title: titulo,
      })).data as { id: number },
    onSuccess: invalidar,
  });
}

export function useEvidencia(processId: number, tipo: EvidenciaTipo, id: number, enabled: boolean) {
  return useQuery<EvidenciaDetalhe>({
    queryKey: comercialKeys.evidencia(processId, tipo, id),
    queryFn: async () => (await api.get(`/processes/${processId}/evidencias/${tipo}/${id}`)).data,
    enabled: enabled && !!processId,
    staleTime: 60_000,
    retry: false,
  });
}

// ─── Motor jurídico ─────────────────────────────────────────────────────────

/** Última execução do motor; `null` quando o motor ainda não avaliou o caso (404). */
export function useExecucaoMotor(processId: number) {
  return useQuery<ExecucaoRelatorio | null>({
    queryKey: comercialKeys.execucao(processId),
    queryFn: async () => {
      try {
        return (await api.get(`/processes/${processId}/motor/execucoes/ultima`)).data;
      } catch (err) {
        if ((err as { response?: { status?: number } })?.response?.status === 404) return null;
        throw err;
      }
    },
    enabled: !!processId,
  });
}

export function useGerarRotaMotor(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async () =>
      (await api.post(`/processes/${processId}/rota/gerar-motor`)).data as {
        rota: RotaMaterializeResponse;
        execucao: ExecucaoRelatorio;
      },
    onSuccess: invalidar,
  });
}

export function useCienciaAlerta(processId: number) {
  const invalidar = useInvalidarCaso(processId);
  return useMutation({
    mutationFn: async ({ avaliacaoId, justificativa }: { avaliacaoId: number; justificativa: string }) =>
      (await api.post(`/processes/${processId}/motor/alertas/${avaliacaoId}/ciencia`, { justificativa })).data,
    onSuccess: invalidar,
  });
}
