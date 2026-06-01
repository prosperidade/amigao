export type PortalType = 'sema' | 'ibama' | 'sicar' | 'incra' | 'banco' | 'cooperativa' | 'outro';

export interface Credential {
  id: number;
  client_id: number;
  portal: string;
  label: string | null;
  login: string | null;
  url: string | null;
  notes: string | null;
  has_password: boolean;
  created_at: string | null;
}

export interface CredentialFormValues {
  portal: PortalType;
  label: string;
  login: string;
  password: string;
  url: string;
  notes: string;
}

export interface CredentialPayload {
  client_id?: number;
  portal: string;
  label?: string | null;
  login?: string | null;
  password?: string;
  url?: string | null;
  notes?: string | null;
}
