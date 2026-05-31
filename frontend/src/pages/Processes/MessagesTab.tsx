/**
 * MessagesTab — Comunicação do caso (PR 2.1)
 *
 * Lista as threads de comunicação do processo (WhatsApp, e-mail, interno) com
 * suas mensagens. Cada thread/mensagem mostra o canal via ícone. Mídia inbound
 * que entrou pelo WhatsApp vira Document do processo (document_category ===
 * 'whatsapp_inbound') e é exibida aqui com link de download acessível.
 *
 * Reutiliza o endpoint /documents/{id}/download-url já existente — não inventa
 * endpoint novo.
 */
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { MessageCircle, Mail, MessageSquare, Paperclip, Download, Clock } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { CommunicationThread, Document } from './ProcessDetailTypes';

interface MessagesTabProps {
  processId: number;
}

// Mapa canal → apresentação (ícone + rótulo + cor). Fallback para canal interno.
const CHANNEL_CONFIG: Record<string, { label: string; icon: LucideIcon; cls: string }> = {
  whatsapp: {
    label: 'WhatsApp',
    icon: MessageCircle,
    cls: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20',
  },
  email: {
    label: 'E-mail',
    icon: Mail,
    cls: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20',
  },
  internal: {
    label: 'Interno',
    icon: MessageSquare,
    cls: 'text-gray-600 dark:text-slate-300 bg-gray-100 dark:bg-white/5 border-gray-200 dark:border-white/10',
  },
};

function channelConfig(channel: string) {
  return CHANNEL_CONFIG[channel] ?? {
    label: channel,
    icon: MessageSquare,
    cls: 'text-gray-600 dark:text-slate-300 bg-gray-100 dark:bg-white/5 border-gray-200 dark:border-white/10',
  };
}

export default function MessagesTab({ processId }: MessagesTabProps) {
  const { data: threads, isLoading } = useQuery({
    queryKey: ['threads', processId],
    queryFn: async () => {
      const res = await api.get(`/threads/?process_id=${processId}`);
      return res.data as CommunicationThread[];
    },
    enabled: !!processId,
  });

  // Mídia inbound do WhatsApp = Document do processo com category 'whatsapp_inbound'.
  const { data: documents } = useQuery({
    queryKey: ['documents', processId],
    queryFn: async () => {
      const res = await api.get(`/documents/?process_id=${processId}`);
      return res.data as Document[];
    },
    enabled: !!processId,
  });

  const inboundMedia = (documents ?? []).filter(
    (d) => d.document_category === 'whatsapp_inbound',
  );

  const handleDownload = async (docId: number, filename: string) => {
    try {
      const res = await api.get(`/documents/${docId}/download-url`);
      const link = document.createElement('a');
      link.href = res.data.download_url;
      link.target = '_blank';
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch {
      toast.error('Erro ao gerar link de download.');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-24 rounded-2xl bg-gray-100 dark:bg-white/5" />
        <div className="h-24 rounded-2xl bg-gray-100 dark:bg-white/5" />
      </div>
    );
  }

  const hasThreads = (threads?.length ?? 0) > 0;

  return (
    <div className="space-y-5">
      {!hasThreads && inboundMedia.length === 0 && (
        <p className="text-sm text-gray-400 dark:text-slate-500">
          Nenhuma comunicação registrada neste caso ainda.
        </p>
      )}

      {threads?.map((thread) => {
        const cfg = channelConfig(thread.channel);
        const ChannelIcon = cfg.icon;
        return (
          <div
            key={thread.id}
            className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 overflow-hidden"
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 dark:border-white/10">
              <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-lg border ${cfg.cls}`}>
                <ChannelIcon className="w-3.5 h-3.5" />
                {cfg.label}
              </span>
              <p className="text-sm font-semibold text-gray-800 dark:text-white truncate">{thread.title}</p>
              {thread.external_id && (
                <span className="ml-auto text-[11px] text-gray-400 dark:text-slate-500 truncate" title={thread.external_id}>
                  {thread.external_id}
                </span>
              )}
            </div>

            <div className="divide-y divide-gray-50 dark:divide-white/5">
              {thread.messages.length === 0 ? (
                <p className="px-4 py-3 text-sm text-gray-400 dark:text-slate-500">Sem mensagens nesta conversa.</p>
              ) : (
                thread.messages.map((msg) => {
                  const isReceived = msg.status === 'received';
                  return (
                    <div key={msg.id} className="px-4 py-3 flex items-start gap-3">
                      <span className={`shrink-0 mt-0.5 inline-flex items-center justify-center w-7 h-7 rounded-full ${cfg.cls}`}>
                        <ChannelIcon className="w-3.5 h-3.5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-gray-800 dark:text-slate-200 whitespace-pre-wrap break-words">{msg.content}</p>
                        <div className="mt-1 flex items-center gap-2 text-[11px] text-gray-400 dark:text-slate-500">
                          <Clock className="w-3 h-3" />
                          <span>{new Date(msg.created_at).toLocaleString('pt-BR')}</span>
                          <span className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-white/5">
                            {isReceived ? 'recebida' : msg.is_internal ? 'interna' : msg.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        );
      })}

      {inboundMedia.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider px-1 flex items-center gap-1.5">
            <Paperclip className="w-3.5 h-3.5" /> Mídia recebida via WhatsApp
          </p>
          {inboundMedia.map((doc) => (
            <div
              key={doc.id}
              className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 flex items-center gap-4 p-4"
            >
              <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-500/20 flex items-center justify-center shrink-0">
                <Paperclip className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 dark:text-white truncate">
                  {doc.filename || doc.original_file_name}
                </p>
                <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                  {(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                  {' · '}{new Date(doc.created_at).toLocaleDateString('pt-BR')}
                </p>
              </div>
              <button
                onClick={() => handleDownload(doc.id, doc.filename || doc.original_file_name || 'download')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 text-sm transition-all shrink-0"
              >
                <Download className="w-3.5 h-3.5" /> Baixar
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
