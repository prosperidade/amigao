import { api } from '@/lib/api';
import { getDb } from '@/lib/db';
import { useNetworkStore } from '@/store/network';
import * as SecureStore from 'expo-secure-store';

/** Configurações de retry com exponential backoff */
const MAX_RETRIES = 5;
const BASE_DELAY_MS = 1_000; // 1 segundo
const MAX_DELAY_MS = 60_000; // 1 minuto

function computeBackoffDelay(attempt: number): number {
  const delay = Math.min(BASE_DELAY_MS * Math.pow(2, attempt), MAX_DELAY_MS);
  // Jitter de ±25% para evitar thundering herd
  const jitter = delay * 0.25 * (Math.random() * 2 - 1);
  return Math.round(delay + jitter);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Limpa a sessão local ao detectar 401 — força logout.
 * Retorna true se o erro era 401 (para que o caller saiba que deve abortar).
 */
async function handleUnauthorized(err: unknown): Promise<boolean> {
  const status = (err as any)?.response?.status;
  if (status === 401) {
    console.warn('[SyncService] 401 Unauthorized — limpando sessão.');
    try {
      await SecureStore.deleteItemAsync('token');
      await SecureStore.deleteItemAsync('user');
    } catch (_) {
      // Silencia erros de cleanup
    }
    return true;
  }
  return false;
}

export class SyncService {

  /**
   * PULL DATA: Baixa processos e tarefas do backend e faz UPSERT na tabela local (SQLite).
   * Nunca apaga dados locais antes de confirmar que a resposta do servidor chegou completa.
   */
  static async pullActiveProcesses() {
    console.log('[SyncService] Pulling processes and tasks from server...');
    try {
      const [pRes, tRes] = await Promise.all([
        api.get('/processes/?limit=300'),
        api.get('/tasks/?limit=1000'),
      ]);

      const serverProcesses: any[] = pRes.data;
      const serverTasks: any[] = tRes.data;

      // Só persiste se ambas as respostas chegaram com sucesso
      const db = getDb();

      await db.withTransactionAsync(async () => {
        // UPSERT processos — preserva dados locais caso o servidor envie parcial
        for (const p of serverProcesses) {
          await db.runAsync(
            `INSERT OR REPLACE INTO processes (id, tenant_id, client_id, property_id, name, description, status, priority, urgency, due_date, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
              p.id, p.tenant_id, p.client_id ?? null, p.property_id ?? null,
              p.title || p.name, p.description ?? null, p.status,
              p.priority ?? null, p.urgency ?? null, p.due_date ?? null, p.created_at ?? null,
            ],
          );
        }

        // UPSERT tarefas
        for (const t of serverTasks) {
          await db.runAsync(
            `INSERT OR REPLACE INTO tasks (id, tenant_id, process_id, title, description, status, due_date)
             VALUES (?, ?, ?, ?, ?, ?, ?)`,
            [
              t.id, t.tenant_id, t.process_id ?? null, t.title,
              t.description ?? null, t.status, t.due_date ?? null,
            ],
          );
        }
      });

      console.log(`[SyncService] Upserted ${serverProcesses.length} processes and ${serverTasks.length} tasks.`);
    } catch (err: any) {
      if (await handleUnauthorized(err)) return;
      console.error('[SyncService] Failed to pull:', err.message);
    }
  }

  /**
   * PUSH DATA: Varre a SyncQueue do SQLite e tenta disparar as mutações contra a API.
   * Implementa exponential backoff por item e aborta toda a fila em caso de 401.
   */
  static async pushPendingMutations() {
    const isConnected = useNetworkStore.getState().isConnected;
    if (!isConnected) {
      console.log('[SyncService] Offline — skipping push.');
      return;
    }

    const db = getDb();
    const queues: any[] = await db.getAllAsync(
      `SELECT * FROM sync_queue WHERE status = 'pending' ORDER BY created_at ASC`,
    );

    if (queues.length === 0) {
      console.log('[SyncService] SyncQueue is empty.');
      return;
    }

    console.log(`[SyncService] Pushing ${queues.length} queued mutations...`);

    for (const item of queues) {
      let success = false;

      for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
        try {
          const payload = JSON.parse(item.payload);
          const method = item.method.toUpperCase();

          if (method === 'POST') {
            await api.post(item.endpoint, payload);
          } else if (method === 'PATCH') {
            await api.patch(item.endpoint, payload);
          } else if (method === 'PUT') {
            await api.put(item.endpoint, payload);
          }

          // Sucesso — marca como sincronizado
          await db.runAsync(
            `UPDATE sync_queue SET status = 'synced', retry_count = ? WHERE id = ?`,
            [attempt + 1, item.id],
          );
          console.log(`[SyncService] Job ${item.id} synced (attempt ${attempt + 1}).`);
          success = true;
          break;

        } catch (err: any) {
          // 401 — sessão inválida, aborta toda a fila
          if (await handleUnauthorized(err)) {
            console.warn('[SyncService] 401 durante push — abortando fila.');
            return;
          }

          const status = err?.response?.status;

          // Erro de cliente (400-499 exceto 401) — não adianta retry
          if (status && status >= 400 && status < 500) {
            await db.runAsync(
              `UPDATE sync_queue SET status = 'error', error_message = ?, retry_count = ? WHERE id = ?`,
              [JSON.stringify(err.response.data), attempt + 1, item.id],
            );
            console.error(`[SyncService] Job ${item.id} failed with ${status} — marked as error.`);
            break;
          }

          // Erro de rede ou servidor (5xx) — exponential backoff
          const delay = computeBackoffDelay(attempt);
          console.warn(
            `[SyncService] Job ${item.id} attempt ${attempt + 1}/${MAX_RETRIES} failed. Retrying in ${delay}ms...`,
          );
          await db.runAsync(
            `UPDATE sync_queue SET retry_count = ? WHERE id = ?`,
            [attempt + 1, item.id],
          );
          await sleep(delay);
        }
      }

      if (!success) {
        // Esgotou retries sem sucesso e sem ser erro de cliente — marca como error
        const current = await db.getFirstAsync<{ status: string }>(
          `SELECT status FROM sync_queue WHERE id = ?`,
          [item.id],
        );
        if (current?.status === 'pending') {
          await db.runAsync(
            `UPDATE sync_queue SET status = 'error', error_message = 'Max retries exceeded' WHERE id = ?`,
            [item.id],
          );
          console.error(`[SyncService] Job ${item.id} exhausted ${MAX_RETRIES} retries.`);
        }
      }
    }
  }

  /**
   * Enfileira ação para o Modo Offline.
   * Ex: Marcar tarefa como concluída em campo.
   */
  static async enqueueMutation(endpoint: string, method: 'POST' | 'PUT' | 'PATCH', payload: any) {
    const db = getDb();

    await db.runAsync(
      `INSERT INTO sync_queue (endpoint, method, payload, status, retry_count) VALUES (?, ?, ?, 'pending', 0)`,
      [endpoint, method, JSON.stringify(payload)],
    );

    console.log(`[SyncService] Mutation queued: ${method} ${endpoint}`);

    // Tenta push imediato se online
    if (useNetworkStore.getState().isConnected) {
      this.pushPendingMutations();
    }
  }
}
