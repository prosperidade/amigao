/**
 * React Query hooks para o domínio regulatório.
 *
 * Endpoints consumidos (sem inventar nada — espelham `app/api/v1/regulatory.py`):
 * - `GET   /properties/{prop}/issues?status=...`
 * - `PATCH /properties/{prop}/issues/{id}`              (Regra A — coerência)
 * - `GET   /processes/{pid}/issues/{iid}/decision`      (404 = sem decisão)
 * - `PUT   /processes/{pid}/issues/{iid}/decision`      (Regra B — rejeita suspeita)
 * - `GET   /processes/{pid}/diagnoses`
 * - `PATCH /processes/{pid}/diagnoses/{version}/validate` (gate camada 2)
 *
 * Query keys centralizadas em `regulatoryKeys` para invalidate consistente.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import { api } from '@/lib/api';
import type {
  DiagnosisNote,
  ProcessIssueDecision,
  ProcessIssueDecisionUpsertPayload,
  RegulatoryDiagnosis,
  RegulatoryIssue,
  RegulatoryIssueUpdatePayload,
} from './types';

export const regulatoryKeys = {
  issues: (propertyId: number) => ['regulatory', 'issues', propertyId] as const,
  notes: (propertyId: number) => ['regulatory', 'notes', propertyId] as const,
  decision: (processId: number, issueId: number) =>
    ['regulatory', 'decision', processId, issueId] as const,
  diagnoses: (processId: number) => ['regulatory', 'diagnoses', processId] as const,
};

// ─── Issues ─────────────────────────────────────────────────────────────────

export function useIssues(
  propertyId: number | null,
  statusFilter: 'open' | 'resolved' | 'all' = 'open',
): UseQueryResult<RegulatoryIssue[]> {
  return useQuery<RegulatoryIssue[]>({
    queryKey: propertyId ? regulatoryKeys.issues(propertyId) : ['regulatory', 'issues', 'noop'],
    queryFn: async () => {
      const r = await api.get(`/properties/${propertyId}/issues`, {
        params: { status: statusFilter },
      });
      return r.data as RegulatoryIssue[];
    },
    enabled: !!propertyId,
  });
}

// ─── Notas derivadas (ADR-020) — não-acionáveis, calculadas na leitura ───────

export function useDiagnosisNotes(
  propertyId: number | null,
): UseQueryResult<DiagnosisNote[]> {
  return useQuery<DiagnosisNote[]>({
    queryKey: propertyId ? regulatoryKeys.notes(propertyId) : ['regulatory', 'notes', 'noop'],
    queryFn: async () => {
      const r = await api.get(`/properties/${propertyId}/diagnosis-notes`);
      return r.data as DiagnosisNote[];
    },
    enabled: !!propertyId,
  });
}

export function useUpdateIssue(propertyId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      issueId,
      payload,
    }: {
      issueId: number;
      payload: RegulatoryIssueUpdatePayload;
    }) => api.patch(`/properties/${propertyId}/issues/${issueId}`, payload).then(r => r.data as RegulatoryIssue),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: regulatoryKeys.issues(propertyId) });
    },
  });
}

// ─── Decision ───────────────────────────────────────────────────────────────

/**
 * GET da decisão por (processId, issueId). Trata 404 como `null` (sem decisão
 * ainda — cada processo recomeça do zero, ADR-012). Outros erros propagam.
 */
export function useDecision(
  processId: number,
  issueId: number,
  enabled = true,
): UseQueryResult<ProcessIssueDecision | null> {
  return useQuery<ProcessIssueDecision | null>({
    queryKey: regulatoryKeys.decision(processId, issueId),
    queryFn: async () => {
      try {
        const r = await api.get(`/processes/${processId}/issues/${issueId}/decision`);
        return r.data as ProcessIssueDecision;
      } catch (err) {
        const ax = err as AxiosError;
        if (ax.response?.status === 404) return null;
        throw err;
      }
    },
    enabled: enabled && !!processId && !!issueId,
    staleTime: 30_000,
  });
}

export function useUpsertDecision(processId: number, issueId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProcessIssueDecisionUpsertPayload) =>
      api
        .put(`/processes/${processId}/issues/${issueId}/decision`, payload)
        .then(r => r.data as ProcessIssueDecision),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: regulatoryKeys.decision(processId, issueId) });
      // Gate camada 2 lê decisões → invalida o cache do diagnóstico também.
      queryClient.invalidateQueries({ queryKey: regulatoryKeys.diagnoses(processId) });
    },
  });
}

// ─── Diagnoses + gate camada 2 ──────────────────────────────────────────────

export function useDiagnoses(processId: number): UseQueryResult<RegulatoryDiagnosis[]> {
  return useQuery<RegulatoryDiagnosis[]>({
    queryKey: regulatoryKeys.diagnoses(processId),
    queryFn: async () => {
      const r = await api.get(`/processes/${processId}/diagnoses`);
      return r.data as RegulatoryDiagnosis[];
    },
    enabled: !!processId,
  });
}

export function useValidateDiagnosis(processId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ version }: { version: number }) =>
      api
        .patch(`/processes/${processId}/diagnoses/${version}/validate`)
        .then(r => r.data as RegulatoryDiagnosis),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: regulatoryKeys.diagnoses(processId) });
    },
  });
}
