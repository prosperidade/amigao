/**
 * Mensagem legível a partir de um erro da API.
 *
 * O `detail` do FastAPI tem três formas e a UI recebia as três como se fossem
 * string: texto simples (HTTPException comum), OBJETO (os erros acionáveis, como
 * o 409 de documento duplicado, que carregam `message` + o registro a reutilizar)
 * e LISTA (422 de validação do Pydantic). Jogar um objeto direto no estado de
 * erro quebra a renderização — React não aceita objeto como filho.
 */

type DetalhePydantic = { msg?: string; loc?: (string | number)[] };
type DetalheObjeto = { message?: string; detail?: string };

export interface ErroApi {
  response?: { data?: { detail?: unknown }; status?: number };
}

export function mensagemDeErro(erro: unknown, padrao: string): string {
  const detail = (erro as ErroApi)?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) return detail;

  // 422 do Pydantic: lista de problemas por campo.
  if (Array.isArray(detail)) {
    const partes = (detail as DetalhePydantic[])
      .map((d) => {
        const campo = (d.loc ?? []).filter((p) => p !== 'body').join('.');
        return campo ? `${campo}: ${d.msg ?? ''}`.trim() : (d.msg ?? '');
      })
      .filter(Boolean);
    if (partes.length) return partes.join(' · ');
  }

  if (detail && typeof detail === 'object') {
    const d = detail as DetalheObjeto;
    if (typeof d.message === 'string' && d.message.trim()) return d.message;
    if (typeof d.detail === 'string' && d.detail.trim()) return d.detail;
  }

  return padrao;
}

/** Payload do 409 de documento já cadastrado (ENT-002), quando for esse o caso. */
export function clienteDuplicado(
  erro: unknown,
): { client_id: number; full_name?: string; legal_name?: string | null } | null {
  const detail = (erro as ErroApi)?.response?.data?.detail;
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const d = detail as { code?: string; client_id?: number; full_name?: string; legal_name?: string | null };
  if (d.code !== 'documento_ja_cadastrado' || typeof d.client_id !== 'number') return null;
  return { client_id: d.client_id, full_name: d.full_name, legal_name: d.legal_name };
}
