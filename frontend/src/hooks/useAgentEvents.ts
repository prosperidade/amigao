/**
 * useAgentEvents — Hook para receber notificacoes de agentes IA em tempo real.
 *
 * Escuta o WebSocket existente por eventos agent.*.completed / agent.*.failed
 * e dispara toast notifications + invalidacao de queries.
 */

import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useAuthStore } from '@/store/auth';
import { AGENT_LABELS } from '@/types/agent';

const WS_BASE = (import.meta.env.VITE_WS_URL as string | undefined)
  || (import.meta.env.VITE_API_URL as string || '').replace(/^http/, 'ws')
  || 'ws://localhost:8000';

export function useAgentEvents() {
  const queryClient = useQueryClient();
  const token = useAuthStore(s => s.token);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;

    const url = `${WS_BASE}/ws?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const eventType = data?.event_type as string | undefined;
        if (!eventType?.startsWith('agent.')) return;

        const agentName = data?.payload?.agent_name as string | undefined;
        const status = data?.payload?.status as string | undefined;
        const processId = data?.payload?.process_id as number | undefined;
        const confidence = data?.payload?.confidence as string | undefined;
        const label = agentName ? (AGENT_LABELS[agentName] ?? agentName) : 'Agente';

        if (status === 'completed') {
          toast.success(`${label} concluido${confidence ? ` (confianca ${confidence})` : ''}`, {
            duration: 4000,
            icon: '\u2705',
          });
        } else if (status === 'failed') {
          const error = (data?.payload?.error as string)?.slice(0, 100) || 'Erro desconhecido';
          toast.error(`${label} falhou: ${error}`, {
            duration: 6000,
            icon: '\u274c',
          });
        }

        // Invalidar queries relevantes
        if (processId) {
          queryClient.invalidateQueries({ queryKey: ['ai-jobs', processId] });
          queryClient.invalidateQueries({ queryKey: ['process', processId] });
        }
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onerror = () => {
      // Silent — WS pode nao estar disponivel em dev
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [token, queryClient]);
}
