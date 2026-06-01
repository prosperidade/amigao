import { useEffect, useState } from 'react';
import { X } from 'lucide-react';

import type { Credential, CredentialFormValues, PortalType } from './types';

const PORTAL_OPTIONS: Array<{ value: PortalType; label: string }> = [
  { value: 'sema', label: 'SEMA' },
  { value: 'ibama', label: 'IBAMA' },
  { value: 'sicar', label: 'SICAR' },
  { value: 'incra', label: 'INCRA' },
  { value: 'banco', label: 'Banco' },
  { value: 'cooperativa', label: 'Cooperativa' },
  { value: 'outro', label: 'Outro' },
];

interface CredentialModalProps {
  credential?: Credential | null;
  error?: string;
  isSaving: boolean;
  mode: 'create' | 'edit';
  onClose: () => void;
  onSubmit: (values: CredentialFormValues) => void;
}

const INITIAL_FORM: CredentialFormValues = {
  portal: 'sema',
  label: '',
  login: '',
  password: '',
  url: '',
  notes: '',
};

export function CredentialModal({
  credential,
  error,
  isSaving,
  mode,
  onClose,
  onSubmit,
}: CredentialModalProps) {
  const [form, setForm] = useState<CredentialFormValues>(INITIAL_FORM);
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    if (mode === 'edit' && credential) {
      setForm({
        portal: credential.portal as PortalType,
        label: credential.label ?? '',
        login: credential.login ?? '',
        password: '',
        url: credential.url ?? '',
        notes: credential.notes ?? '',
      });
      return;
    }

    setForm(INITIAL_FORM);
  }, [credential, mode]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setValidationError('');

    if (!form.portal.trim()) {
      setValidationError('Selecione o portal.');
      return;
    }

    if (mode === 'create' && !form.password.trim()) {
      setValidationError('Informe a senha para criar a credencial.');
      return;
    }

    onSubmit({
      ...form,
      portal: form.portal.trim().toLowerCase() as PortalType,
      label: form.label.trim(),
      login: form.login.trim(),
      password: form.password,
      url: form.url.trim(),
      notes: form.notes.trim(),
    });
  };

  const title = mode === 'create' ? 'Adicionar credencial' : 'Editar credencial';
  const submitLabel = mode === 'create' ? 'Adicionar' : 'Salvar';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              A senha e criptografada no servidor e nunca volta em plaintext pela API.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 p-6">
          {(validationError || error) && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
              {validationError || error}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-1.5 text-sm font-medium text-foreground">
              <span>Portal</span>
              <select
                required
                value={form.portal}
                onChange={(event) => setForm((current) => ({ ...current, portal: event.target.value as PortalType }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              >
                {PORTAL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5 text-sm font-medium text-foreground">
              <span>Nome amigavel</span>
              <input
                type="text"
                value={form.label}
                onChange={(event) => setForm((current) => ({ ...current, label: event.target.value }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                placeholder="SEMA-GO do cliente"
              />
            </label>

            <label className="space-y-1.5 text-sm font-medium text-foreground">
              <span>Login</span>
              <input
                type="text"
                value={form.login}
                onChange={(event) => setForm((current) => ({ ...current, login: event.target.value }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                autoComplete="username"
              />
            </label>

            <label className="space-y-1.5 text-sm font-medium text-foreground">
              <span>Senha</span>
              <input
                required={mode === 'create'}
                type="password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                autoComplete="new-password"
                placeholder={mode === 'edit' ? 'Deixe em branco para manter senha atual.' : ''}
              />
            </label>

            <label className="space-y-1.5 text-sm font-medium text-foreground md:col-span-2">
              <span>URL</span>
              <input
                type="url"
                value={form.url}
                onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                placeholder="https://"
              />
            </label>

            <label className="space-y-1.5 text-sm font-medium text-foreground md:col-span-2">
              <span>Observacoes</span>
              <textarea
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                className="min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>
          </div>

          <div className="flex justify-end gap-3 border-t border-border pt-5">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:bg-muted disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
            >
              {isSaving ? 'Salvando...' : submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
