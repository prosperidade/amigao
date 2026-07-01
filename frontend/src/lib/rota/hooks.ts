/**
 * React Query hooks da Rota Regulatória (E5).
 *
 * Endpoints (espelham `app/api/v1/rotas.py`):
 * - `GET   /processes/{pid}/rota`
 * - `POST  /processes/{pid}/rota/gerar`
 * - `PATCH /rotas/{rid}/reordenar`
 * - `POST  /rotas/{rid}/passos`               (manual)
 * - `PATCH /rotas/{rid}/passos/{id}`
 * - `DELETE /rotas/{rid}/passos/{id}`
 * - `POST  /rotas/{rid}/passos/{id}/validar`
 * - `POST  /rotas/{rid}/fechar`
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  PassoCreatePayload,
  PassoUpdatePayload,
  Rota,
  RotaMaterializeResponse,
  RotaPasso,
} from './types';

export const rotaKeys = {
  detail: (processId: number) => ['rota', processId] as const,
};

export function useRota(processId: number, enabled = true): UseQueryResult<Rota | null> {
  return useQuery<Rota | null>({
    queryKey: rotaKeys.detail(processId),
    queryFn: async () => {
      const r = await api.get(`/processes/${processId}/rota`);
      return (r.data ?? null) as Rota | null;
    },
    enabled: !!processId && enabled,
  });
}

export function useGerarRota(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post(`/processes/${processId}/rota/gerar`).then(r => r.data as RotaMaterializeResponse),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    },
  });
}

export function useReordenarRota(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rotaId, passoIds }: { rotaId: number; passoIds: number[] }) =>
      api.patch(`/rotas/${rotaId}/reordenar`, { passo_ids: passoIds }).then(r => r.data as Rota),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    },
  });
}

export function useAddPassoManual(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rotaId, payload }: { rotaId: number; payload: PassoCreatePayload }) =>
      api.post(`/rotas/${rotaId}/passos`, payload).then(r => r.data as RotaPasso),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    },
  });
}

export function useUpdatePasso(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rotaId, passoId, payload }: { rotaId: number; passoId: number; payload: PassoUpdatePayload }) =>
      api.patch(`/rotas/${rotaId}/passos/${passoId}`, payload).then(r => r.data as RotaPasso),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    },
  });
}

export function useRemovePasso(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rotaId, passoId }: { rotaId: number; passoId: number }) =>
      api.delete(`/rotas/${rotaId}/passos/${passoId}`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    },
  });
}

export function useValidarPasso(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rotaId, passoId }: { rotaId: number; passoId: number }) =>
      api.post(`/rotas/${rotaId}/passos/${passoId}/validar`).then(r => r.data as RotaPasso),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    },
  });
}

export function useFecharRota(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rotaId }: { rotaId: number }) =>
      api.post(`/rotas/${rotaId}/fechar`).then(r => r.data as Rota),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rotaKeys.detail(processId) });
    },
  });
}
