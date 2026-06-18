/**
 * React Query hooks da Ficha 07 — Ações.
 *
 * Endpoints (espelham `app/api/v1/acoes.py`):
 * - `GET   /processes/{pid}/acoes`
 * - `POST  /processes/{pid}/acoes`                (criação manual)
 * - `POST  /processes/{pid}/acoes/generate`       (gera do diagnóstico)
 * - `PATCH /processes/{pid}/acoes/{id}`           (status/prazo/prioridade/...)
 * - `POST  /processes/{pid}/acoes/{id}/triagem`   (tarefa/escopo/dispensar)
 * - `GET   /acoes/kanban`                         (quadro global)
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  Acao,
  AcaoCreatePayload,
  AcaoGenerateResponse,
  AcaoKanbanResponse,
  AcaoUpdatePayload,
  TriagemDecisao,
} from './types';

export const acoesKeys = {
  list: (processId: number) => ['acoes', 'list', processId] as const,
  kanban: () => ['acoes', 'kanban'] as const,
};

export function useAcoes(processId: number): UseQueryResult<Acao[]> {
  return useQuery<Acao[]>({
    queryKey: acoesKeys.list(processId),
    queryFn: async () => {
      const r = await api.get(`/processes/${processId}/acoes`);
      return r.data as Acao[];
    },
    enabled: !!processId,
  });
}

export function useGenerateAcoes(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api
        .post(`/processes/${processId}/acoes/generate`)
        .then(r => r.data as AcaoGenerateResponse),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: acoesKeys.list(processId) });
      queryClient.invalidateQueries({ queryKey: acoesKeys.kanban() });
    },
  });
}

export function useCreateAcao(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AcaoCreatePayload) =>
      api.post(`/processes/${processId}/acoes`, payload).then(r => r.data as Acao),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: acoesKeys.list(processId) });
      queryClient.invalidateQueries({ queryKey: acoesKeys.kanban() });
    },
  });
}

export function useUpdateAcao(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ acaoId, payload }: { acaoId: number; payload: AcaoUpdatePayload }) =>
      api
        .patch(`/processes/${processId}/acoes/${acaoId}`, payload)
        .then(r => r.data as Acao),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: acoesKeys.list(processId) });
      queryClient.invalidateQueries({ queryKey: acoesKeys.kanban() });
    },
  });
}

export function useTriarAcao(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ acaoId, decisao }: { acaoId: number; decisao: TriagemDecisao }) =>
      api
        .post(`/processes/${processId}/acoes/${acaoId}/triagem`, { decisao })
        .then(r => r.data as Acao),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: acoesKeys.list(processId) });
      queryClient.invalidateQueries({ queryKey: acoesKeys.kanban() });
    },
  });
}

// ─── Quadro global ──────────────────────────────────────────────────────────

export function useAcoesKanban(): UseQueryResult<AcaoKanbanResponse> {
  return useQuery<AcaoKanbanResponse>({
    queryKey: acoesKeys.kanban(),
    queryFn: async () => {
      const r = await api.get('/acoes/kanban');
      return r.data as AcaoKanbanResponse;
    },
    staleTime: 15_000,
  });
}

/** PATCH de status usado pelo quadro global (não tem processId no contexto). */
export function useMoveAcaoStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      processId,
      acaoId,
      status,
    }: {
      processId: number;
      acaoId: number;
      status: Acao['status'];
    }) =>
      api
        .patch(`/processes/${processId}/acoes/${acaoId}`, { status })
        .then(r => r.data as Acao),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: acoesKeys.kanban() });
      queryClient.invalidateQueries({ queryKey: acoesKeys.list(variables.processId) });
    },
  });
}
