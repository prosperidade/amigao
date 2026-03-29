import { api } from '@/lib/api';
import { getDb } from '@/lib/db';
import { useNetworkStore } from '@/store/network';

export class SyncService {

  /**
   * PULL DATA: Baixa processos e tarefas do backend e sobrescreve/atualiza a tabela local (SQLite)
   * Só é acionado quando usuário faz SignIn, Refresh Manual, ou Background App Startup com Rede.
   */
  static async pullActiveProcesses() {
    console.log('[SyncService] Pulling processes and tasks from server...');
    try {
      const pRes = await api.get('/processes/?limit=300'); // No futuro, usar paginação pesada no background sync
      const serverProcesses = pRes.data;
      
      const tRes = await api.get('/tasks/?limit=1000');
      const serverTasks = tRes.data;
      
      const db = getDb();
      
      await db.withTransactionAsync(async () => {
        // Limpar tabela pra demonstração segura (no real: usar upsert / data_atualizacao)
        await db.runAsync(`DELETE FROM tasks;`);
        await db.runAsync(`DELETE FROM processes;`);
        
        for (const p of serverProcesses) {
          await db.runAsync(
            `INSERT INTO processes (id, tenant_id, client_id, property_id, name, description, status, priority, urgency, due_date, created_at) 
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
             [
               p.id, p.tenant_id, p.client_id ?? null, p.property_id ?? null, p.title || p.name, p.description ?? null, 
               p.status, p.priority ?? null, p.urgency ?? null, p.due_date ?? null, p.created_at ?? null
             ]
          );
        }

        for (const t of serverTasks) {
          await db.runAsync(
            `INSERT INTO tasks (id, tenant_id, process_id, title, description, status, due_date) 
             VALUES (?, ?, ?, ?, ?, ?, ?)`,
             [
               t.id, t.tenant_id, t.process_id ?? null, t.title, t.description ?? null, t.status, t.due_date ?? null
             ]
          );
        }
      });
      console.log(`[SyncService] ${serverProcesses.length} processes and ${serverTasks.length} tasks written to SQLite.`);
    } catch (err: any) {
      console.error('[SyncService] Failed to pull processes or tasks: ', err.message);
      import('react-native').then(({ Alert }) => {
        Alert.alert('Erro no Sincronismo', err.message);
      });
    }
  }

  /**
   * PUSH DATA: Varre a SyncQueue do SQLite e tenta disparar as mutações contra a API.
   * Acionado quando o Zustand de Rede acusa "Offline -> Online".
   */
  static async pushPendingMutations() {
    const isConnected = useNetworkStore.getState().isConnected;
    if (!isConnected) {
      console.log('[SyncService] App is Offline. Skipping Push.');
      return;
    }

    const db = getDb();
    const queues: any[] = await db.getAllAsync(`SELECT * FROM sync_queue WHERE status = 'pending' ORDER BY created_at ASC`);

    if (queues.length === 0) {
      console.log('[SyncService] SyncQueue is empty. Nothing to push.');
      return;
    }

    console.log(`[SyncService] Starting push of ${queues.length} queued mutations...`);

    for (const item of queues) {
      try {
        const payload = JSON.parse(item.payload);
        
        if (item.method.toUpperCase() === 'POST') {
          await api.post(item.endpoint, payload);
        } else if (item.method.toUpperCase() === 'PATCH') {
          await api.patch(item.endpoint, payload);
        } else if (item.method.toUpperCase() === 'PUT') {
          await api.put(item.endpoint, payload);
        }

        // Marcar como sucesso
        await db.runAsync(`UPDATE sync_queue SET status = 'synced' WHERE id = ?`, [item.id]);
        console.log(`[SyncService] Job ${item.id} (${item.method} ${item.endpoint}) executed successfully.`);

      } catch (err: any) {
        console.error(`[SyncService] Error pushing Job ${item.id}:`, err?.response?.data || err.message);
        // Atualiza mensagem de erro mas mantém pending se for erro de rede. Se for 400 Bad Request que não pode passar, quebra.
        if (err.response && err.response.status >= 400 && err.response.status < 500) {
          await db.runAsync(`UPDATE sync_queue SET status = 'error', error_message = ? WHERE id = ?`, [JSON.stringify(err.response.data), item.id]);
        }
      }
    }
  }

  /**
   * Enfileira ação pro Modo Offline
   * Ex: Marcar tarefa como concluída em campo. 
   */
  static async enqueueMutation(endpoint: string, method: 'POST' | 'PUT' | 'PATCH', payload: any) {
    const db = getDb();
    
    await db.runAsync(
      `INSERT INTO sync_queue (endpoint, method, payload) VALUES (?, ?, ?)`,
      [endpoint, method, JSON.stringify(payload)]
    );
    
    console.log(`[SyncService] Mutation queued: ${method} ${endpoint}`);
    
    // Tenta push imediato caso o app ache que tem internet.
    if (useNetworkStore.getState().isConnected) {
      this.pushPendingMutations();
    }
  }
}
