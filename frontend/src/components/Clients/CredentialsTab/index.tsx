import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ExternalLink,
  KeyRound,
  Loader2,
  LockKeyhole,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react';

import { api } from '@/lib/api';
import { CredentialModal } from './CredentialModal';
import type { Credential, CredentialFormValues, CredentialPayload } from './types';

const PORTAL_LABELS: Record<string, string> = {
  sema: 'SEMA',
  ibama: 'IBAMA',
  sicar: 'SICAR',
  incra: 'INCRA',
  banco: 'Banco',
  cooperativa: 'Cooperativa',
  outro: 'Outro',
};

interface CredentialsTabProps {
  clientId: number;
}

type ModalState =
  | { mode: 'create'; credential: null }
  | { mode: 'edit'; credential: Credential };

export default function CredentialsTab({ clientId }: CredentialsTabProps) {
  const queryClient = useQueryClient();
  const [modal, setModal] = useState<ModalState | null>(null);
  const [formError, setFormError] = useState('');
  const [pendingDelete, setPendingDelete] = useState<Credential | null>(null);

  const queryKey = useMemo(() => ['client-hub-credentials', clientId], [clientId]);

  const {
    data: credentials = [],
    isError,
    isLoading,
    refetch,
  } = useQuery({
    queryKey,
    queryFn: () => api.get<Credential[]>(`/credentials?client_id=${clientId}`).then((response) => response.data),
    enabled: !!clientId,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CredentialPayload) => api.post('/credentials', payload),
    onSuccess: () => {
      toast.success('Credencial adicionada.');
      closeModal();
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (error: unknown) => {
      setFormError(extractErrorMessage(error, 'Nao foi possivel adicionar a credencial.'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CredentialPayload }) => api.patch(`/credentials/${id}`, payload),
    onSuccess: () => {
      toast.success('Credencial atualizada.');
      closeModal();
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (error: unknown) => {
      setFormError(extractErrorMessage(error, 'Nao foi possivel atualizar a credencial.'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/credentials/${id}`),
    onSuccess: () => {
      toast.success('Credencial excluida.');
      setPendingDelete(null);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (error: unknown) => {
      toast.error(extractErrorMessage(error, 'Nao foi possivel excluir a credencial.'));
    },
  });

  const openCreateModal = () => {
    setFormError('');
    setModal({ mode: 'create', credential: null });
  };

  const openEditModal = (credential: Credential) => {
    setFormError('');
    setModal({ mode: 'edit', credential });
  };

  const closeModal = () => {
    setFormError('');
    setModal(null);
  };

  const handleSubmit = (values: CredentialFormValues) => {
    const basePayload: CredentialPayload = {
      portal: values.portal,
      label: emptyToNull(values.label),
      login: emptyToNull(values.login),
      url: emptyToNull(values.url),
      notes: emptyToNull(values.notes),
    };

    if (modal?.mode === 'create') {
      createMutation.mutate({
        client_id: clientId,
        ...basePayload,
        password: values.password,
      });
      return;
    }

    if (modal?.mode === 'edit') {
      const payload = values.password.trim()
        ? { ...basePayload, password: values.password }
        : basePayload;
      updateMutation.mutate({ id: modal.credential.id, payload });
    }
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-foreground">Credenciais de Portal</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Logins externos vinculados a este cliente, sem exibicao de senha.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreateModal}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Adicionar
        </button>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map((item) => (
            <div key={item} className="h-24 animate-pulse rounded-xl border border-border bg-muted/50" />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
          <div className="font-medium">Nao foi possivel carregar as credenciais.</div>
          <button type="button" onClick={() => refetch()} className="mt-2 text-sm font-semibold underline">
            Tentar novamente
          </button>
        </div>
      )}

      {!isLoading && !isError && credentials.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-muted/30 p-8 text-center">
          <KeyRound className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            Nenhuma credencial cadastrada. Adicione a primeira clicando em "Adicionar".
          </p>
        </div>
      )}

      {!isLoading && !isError && credentials.length > 0 && (
        <div className="divide-y divide-border overflow-hidden rounded-xl border border-border">
          {credentials.map((credential) => (
            <CredentialRow
              key={credential.id}
              credential={credential}
              onDelete={() => setPendingDelete(credential)}
              onEdit={() => openEditModal(credential)}
            />
          ))}
        </div>
      )}

      {modal && (
        <CredentialModal
          key={modal.mode === 'edit' ? `edit-${modal.credential?.id}` : 'create'}
          credential={modal.credential}
          error={formError}
          isSaving={isSaving}
          mode={modal.mode}
          onClose={closeModal}
          onSubmit={handleSubmit}
        />
      )}

      {pendingDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md overflow-hidden rounded-2xl border border-border bg-card shadow-xl">
            <div className="border-b border-border p-5">
              <h2 className="text-lg font-semibold text-foreground">Excluir credencial?</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Excluir credencial "{credentialTitle(pendingDelete)}"? Esta acao nao pode ser desfeita.
              </p>
            </div>
            <div className="flex justify-end gap-3 p-5">
              <button
                type="button"
                onClick={() => setPendingDelete(null)}
                disabled={deleteMutation.isPending}
                className="rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:bg-muted disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => deleteMutation.mutate(pendingDelete.id)}
                disabled={deleteMutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CredentialRow({
  credential,
  onDelete,
  onEdit,
}: {
  credential: Credential;
  onDelete: () => void;
  onEdit: () => void;
}) {
  return (
    <div className="bg-card p-4 transition hover:bg-muted/40">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-medium text-foreground">{credentialTitle(credential)}</h4>
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-primary">
              {PORTAL_LABELS[credential.portal] ?? credential.portal}
            </span>
            {credential.has_password && (
              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700 dark:bg-white/10 dark:text-gray-200">
                <LockKeyhole className="h-3 w-3" />
                Senha protegida
              </span>
            )}
          </div>

          <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
            <div>
              <span className="font-medium text-foreground">Login:</span>{' '}
              <span>{credential.login || '-'}</span>
            </div>
            <div>
              <span className="font-medium text-foreground">Criada:</span>{' '}
              <span>{credential.created_at ? new Date(credential.created_at).toLocaleDateString('pt-BR') : '-'}</span>
            </div>
          </div>

          {credential.url && (
            <a
              href={credential.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex max-w-full items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              <ExternalLink className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{credential.url}</span>
            </a>
          )}

          {credential.notes && (
            <p className="text-sm text-muted-foreground">{credential.notes}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onEdit}
            className="rounded-lg p-2 text-muted-foreground transition hover:bg-primary/10 hover:text-primary"
            aria-label="Editar credencial"
            title="Editar"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded-lg p-2 text-muted-foreground transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"
            aria-label="Excluir credencial"
            title="Excluir"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function credentialTitle(credential: Credential): string {
  return credential.label || PORTAL_LABELS[credential.portal] || credential.portal || `Credencial #${credential.id}`;
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function extractErrorMessage(error: unknown, fallback: string): string {
  const axiosError = error as { response?: { data?: { detail?: unknown } } };
  const detail = axiosError.response?.data?.detail;

  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item?.msg === 'string') return item.msg;
        return null;
      })
      .filter(Boolean)
      .join(' ');
  }

  return fallback;
}
