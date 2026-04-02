export interface AccessTokenPayload {
  sub?: string;
  tenant_id?: number | null;
  client_id?: number | null;
  profile?: 'internal' | 'client_portal';
}

function decodeBase64Url(value: string): string | null {
  try {
    const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + ((4 - normalized.length % 4) % 4), '=');
    return atob(padded);
  } catch {
    return null;
  }
}

export function parseAccessToken(token: string): AccessTokenPayload | null {
  const segments = token.split('.');
  if (segments.length !== 3) {
    return null;
  }

  const decoded = decodeBase64Url(segments[1]);
  if (!decoded) {
    return null;
  }

  try {
    return JSON.parse(decoded) as AccessTokenPayload;
  } catch {
    return null;
  }
}

export function isClientPortalToken(token: string): boolean {
  const payload = parseAccessToken(token);
  return payload?.profile === 'client_portal' || payload?.client_id != null;
}
