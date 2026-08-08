/**
 * RotaTab — a Rota Regulatória na etapa E5 (Ficha 07 §8.1).
 *
 * Renderizada DENTRO da aba "Ações" quando o processo está em
 * `caminho_regulatorio` (não é 7ª aba — é view etapa-sensível). A IA propõe a
 * rota; o consultor reordena (drag), classifica (faturável vs direção), valida
 * passo a passo e FECHA (assina). Materializa o Princípio 1.
 *
 * Regras: validar exige classificação; "Fechar rota" só habilita com TODOS os
 * passos validados; rota 'desatualizada' trava o fechamento até aceitar o diff.
 */
import { useState } from 'react';
import { AxiosError } from 'axios';
import { Reorder, useDragControls } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  GripVertical,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
} from 'lucide-react';
import {
  useAddPassoManual,
  useFecharRota,
  useGerarRota,
  useRemovePasso,
  useReordenarRota,
  useRota,
  useUpdatePasso,
  useValidarPasso,
} from '@/lib/rota/hooks';
import {
  CLASSIFICACAO_CLS,
  CLASSIFICACAO_LABEL,
  ROTA_STATUS_CLS,
  ROTA_STATUS_LABEL,
  type RotaPasso,
  type RotaPassoClassificacao,
} from '@/lib/rota/types';

interface RotaTabProps {
  processId: number;
}

function detalheErro(err: unknown, fallback: string): string {
  if (err instanceof AxiosError) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
    if (detail) return detail;
  }
  return fallback;
}

/** Chip honesto de fonte: com norma (verde) ou estimativa sem fonte (âmbar). */
function FonteChip({ passo }: { passo: RotaPasso }) {
  const comNorma =
    passo.prazo_fonte === 'norma' ||
    !!passo.norma_ref ||
    passo.sources.some(s => s.tipo === 'legislacao' && !s.sem_fonte);
  if (comNorma) {
    return (
      <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
        {passo.norma_ref ? `📖 ${passo.norma_ref}` : '📖 com fonte normativa'}
      </span>
    );
  }
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
      {`⚠ estimativa profissional (sem fonte)`}
    </span>
  );
}

interface PassoCardProps {
  passo: RotaPasso;
  processId: number;
  rotaId: number;
  fechada: boolean;
  onCommitOrder: () => void;
  /** Posição visível (1-based). Vem do índice, não de `passo.ordem`: entre o
   *  gesto e a resposta do servidor a `ordem` gravada ainda é a antiga, e o
   *  consultor veria dois passos com o mesmo número. */
  posicao: number;
  total: number;
  /** Move o passo N casas (−1 sobe, +1 desce). Mesma ação do arrastar, mesmo
   *  endpoint — só a entrada é outra (teclado). */
  onMover: (delta: -1 | 1) => void;
}

function PassoCard({
  passo,
  processId,
  rotaId,
  fechada,
  onCommitOrder,
  posicao,
  total,
  onMover,
}: PassoCardProps) {
  const controls = useDragControls();
  const updateMut = useUpdatePasso(processId);
  const removeMut = useRemovePasso(processId);
  const validarMut = useValidarPasso(processId);

  const validado = passo.status === 'validado';

  const setClassificacao = (classificacao: RotaPassoClassificacao) => {
    updateMut.mutate(
      { rotaId, passoId: passo.id, payload: { classificacao } },
      { onError: () => toast.error('Falha ao classificar o passo.') },
    );
  };

  const validar = () => {
    if (passo.classificacao === null) {
      toast('Classifique o passo (item de proposta ou direção) antes de validar.', { icon: 'ℹ️' });
      return;
    }
    validarMut.mutate(
      { rotaId, passoId: passo.id },
      {
        onSuccess: () => toast.success('Passo validado.'),
        onError: err => toast.error(detalheErro(err, 'Falha ao validar o passo.')),
      },
    );
  };

  const remover = () => {
    removeMut.mutate(
      { rotaId, passoId: passo.id },
      { onError: () => toast.error('Falha ao remover o passo.') },
    );
  };

  return (
    <Reorder.Item
      value={passo}
      dragListener={false}
      dragControls={controls}
      onPointerUp={onCommitOrder}
      className={`rounded-xl border p-4 bg-white dark:bg-white/5 ${
        validado
          ? 'border-emerald-200 dark:border-emerald-800/60'
          : 'border-gray-200 dark:border-white/10'
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Reordenar: arrastar (mouse) e ↑/↓ (teclado) — duas entradas para a
            mesma ação, ambas terminando no mesmo PATCH /reordenar. O arrastar
            sozinho deixava de fora quem opera no teclado, e esta é tela de
            trabalho diário. */}
        <div className="mt-0.5 shrink-0 flex flex-col items-center">
          <button
            type="button"
            onClick={() => onMover(-1)}
            disabled={fechada || posicao === 1}
            className="text-gray-300 dark:text-slate-600 enabled:hover:text-gray-600 dark:enabled:hover:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            aria-label={`Subir passo ${posicao} de ${total}`}
            title="Subir"
          >
            <ChevronUp className="w-4 h-4" />
          </button>

          <span
            onPointerDown={e => !fechada && controls.start(e)}
            className={`text-gray-300 dark:text-slate-600 ${
              fechada ? 'cursor-not-allowed' : 'cursor-grab hover:text-gray-500 dark:hover:text-slate-400'
            }`}
            aria-hidden="true"
          >
            <GripVertical className="w-4 h-4" />
          </span>

          <button
            type="button"
            onClick={() => onMover(1)}
            disabled={fechada || posicao === total}
            className="text-gray-300 dark:text-slate-600 enabled:hover:text-gray-600 dark:enabled:hover:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            aria-label={`Descer passo ${posicao} de ${total}`}
            title="Descer"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>

        <span className="mt-0.5 shrink-0 w-6 h-6 rounded-full bg-gray-100 dark:bg-white/10 text-gray-700 dark:text-slate-200 text-xs font-semibold flex items-center justify-center">
          {posicao}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center flex-wrap gap-2">
            <p className="text-sm font-medium text-gray-900 dark:text-white">{passo.titulo}</p>
            {passo.origem === 'manual' && (
              <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-slate-300 border border-slate-200 dark:border-zinc-700">
                manual
              </span>
            )}
            <FonteChip passo={passo} />
            {validado && (
              <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 inline-flex items-center gap-1">
                <Check className="w-3 h-3" /> validado
              </span>
            )}
          </div>

          {passo.descricao && (
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">{passo.descricao}</p>
          )}
          <div className="text-xs text-gray-400 dark:text-slate-500 mt-1 flex flex-wrap gap-x-3">
            {passo.orgao && <span>Órgão: {passo.orgao}</span>}
            {passo.prazo_estimado_dias !== null && <span>Prazo: ~{passo.prazo_estimado_dias} dias</span>}
            {passo.origem_manual_nota && <span>Origem: {passo.origem_manual_nota}</span>}
          </div>

          {/* Classificação (Ficha §8.1) — obrigatória para validar */}
          <div className="flex items-center gap-1.5 mt-3">
            {(Object.keys(CLASSIFICACAO_LABEL) as RotaPassoClassificacao[]).map(c => {
              const ativo = passo.classificacao === c;
              return (
                <button
                  key={c}
                  type="button"
                  disabled={fechada || updateMut.isPending}
                  onClick={() => setClassificacao(c)}
                  className={`text-[11px] px-2.5 py-1 rounded-full font-medium border transition-colors disabled:opacity-50 ${
                    ativo
                      ? CLASSIFICACAO_CLS[c]
                      : 'bg-transparent text-gray-400 dark:text-slate-500 border-gray-200 dark:border-white/10 hover:border-gray-300'
                  }`}
                >
                  {CLASSIFICACAO_LABEL[c]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Ações do passo */}
        {!fechada && (
          <div className="flex items-center gap-1 shrink-0">
            {!validado && (
              <button
                type="button"
                onClick={validar}
                disabled={validarMut.isPending}
                title="Validar passo"
                className="p-1.5 rounded-lg text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 disabled:opacity-50"
              >
                <Check className="w-4 h-4" />
              </button>
            )}
            <button
              type="button"
              onClick={remover}
              disabled={removeMut.isPending}
              title="Remover passo"
              // Nome acessível com o título: com vários cards na tela, "Remover
              // passo" sozinho não diz QUAL — nem para o leitor de tela, nem
              // para o teste que exerce o gesto.
              aria-label={`Remover passo ${posicao}: ${passo.titulo}`}
              className="p-1.5 rounded-lg text-gray-400 dark:text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </Reorder.Item>
  );
}

export default function RotaTab({ processId }: RotaTabProps) {
  const { data: rota, isLoading } = useRota(processId);
  const gerarMut = useGerarRota(processId);
  const reordenarMut = useReordenarRota(processId);
  const addManualMut = useAddPassoManual(processId);
  const fecharMut = useFecharRota(processId);

  const [order, setOrder] = useState<RotaPasso[]>([]);
  const [novoTitulo, setNovoTitulo] = useState('');
  const [novaNota, setNovaNota] = useState('');

  // Sincroniza a ordem local quando o servidor manda passos novos — padrão
  // "adjusting state during render" do React (setState em effect é barrado
  // pelo react-hooks/set-state-in-effect e re-renderiza dobrado).
  const [passosSincronizados, setPassosSincronizados] = useState(rota?.passos);
  if (rota?.passos !== passosSincronizados) {
    setPassosSincronizados(rota?.passos);
    setOrder(rota?.passos ?? []);
  }

  const gerar = () => {
    gerarMut.mutate(undefined, {
      onSuccess: data => {
        // Passo que o consultor removeu e a IA repropôs não volta — mas também
        // não some do relato. Sem esta frase, ele leria "nenhum passo novo" e
        // concluiria que a atualização não rodou (foi a leitura do 02/08).
        const suprimidos = data.suprimidos
          ? ` ${data.suprimidos} passo(s) que você removeu continuam fora.`
          : '';
        if (data.rota.status === 'desatualizada') {
          toast(`Rota atualizada: há passos novos para validar.${suprimidos}`, { icon: '⚠️' });
        } else if (data.created === 0 && data.matched > 0) {
          toast(`Rota já estava em dia — nenhum passo novo.${suprimidos}`, { icon: '✓' });
        } else {
          toast.success(`Rota gerada: ${data.created} passo(s).${suprimidos}`);
        }
      },
      onError: err => toast.error(detalheErro(err, 'Falha ao gerar a rota.')),
    });
  };

  /** Porta única da reordenação — arrastar e ↑/↓ passam por aqui.
   *
   *  O sucesso FALA. Antes só o erro tinha voz: o consultor arrastava, o card
   *  assentava e nada dizia se aquilo tinha ficado gravado — mesma lição do
   *  #141 (o sistema gravava certo e a tela não mostrava). Ordem que some no
   *  recarregar e ordem que salvou em silêncio são indistinguíveis na tela. */
  const salvarOrdem = (novos: RotaPasso[]) => {
    if (!rota) return;
    const ids = novos.map(p => p.id);
    const atuais = rota.passos.map(p => p.id);
    if (ids.length === atuais.length && ids.every((v, i) => v === atuais[i])) return; // sem mudança
    reordenarMut.mutate(
      { rotaId: rota.id, passoIds: ids },
      {
        onSuccess: () => toast.success('Ordem salva.'),
        onError: () => {
          // Devolve a lista ao que o servidor tem: manter na tela uma ordem que
          // não foi gravada é a mentira que o #141 ensinou a não contar.
          setOrder(rota.passos);
          toast.error('Falha ao reordenar — a ordem anterior foi restaurada.');
        },
      },
    );
  };

  const commitOrder = () => salvarOrdem(order);

  const moverPasso = (index: number, delta: -1 | 1) => {
    const destino = index + delta;
    if (destino < 0 || destino >= order.length) return;
    const novos = [...order];
    [novos[index], novos[destino]] = [novos[destino], novos[index]];
    setOrder(novos);
    salvarOrdem(novos);
  };

  const addManual = (e: React.FormEvent) => {
    e.preventDefault();
    if (!rota || !novoTitulo.trim()) return;
    addManualMut.mutate(
      { rotaId: rota.id, payload: { titulo: novoTitulo.trim(), origem_manual_nota: novaNota.trim() || null } },
      {
        onSuccess: () => { setNovoTitulo(''); setNovaNota(''); toast.success('Passo manual adicionado.'); },
        onError: () => toast.error('Falha ao adicionar passo.'),
      },
    );
  };

  const fechar = () => {
    if (!rota) return;
    fecharMut.mutate(
      { rotaId: rota.id },
      {
        onSuccess: () => toast.success('Rota fechada e assinada.'),
        onError: err => toast.error(detalheErro(err, 'Falha ao fechar a rota.')),
      },
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400 p-4">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando rota…
      </div>
    );
  }

  // Estado vazio — rota ainda não materializada.
  if (!rota) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-1">
          {`A Rota Regulatória ainda não foi gerada.`}
        </p>
        <p className="text-xs text-gray-400 dark:text-slate-500 mb-5">
          {`A IA propõe os passos do caminho regulatório; você reordena, classifica e assina.`}
        </p>
        <button
          type="button"
          onClick={gerar}
          disabled={gerarMut.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
        >
          {gerarMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Gerar rota
        </button>
      </div>
    );
  }

  const fechada = rota.status === 'validada';
  const desatualizada = rota.status === 'desatualizada';
  const pendentes = rota.passos.filter(p => p.status !== 'validado').length;
  // Validação 02/08 — `desatualizada` NÃO pode travar sozinha. Ela também é
  // marcada quando a IA REMOVE um passo: aí não nasce passo novo, não há o que
  // validar, e a rota nunca saía desse estado. O botão ficava desabilitado para
  // sempre com o rodapé dizendo "todos os passos validados" — a E5 virava beco
  // sem saída. O que trava é ter passo PENDENTE, não o rótulo do estado.
  const podeFechar = !fechada && rota.passos.length > 0 && pendentes === 0;

  return (
    <div className="space-y-5">
      {/* Cabeçalho */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 uppercase tracking-wider">
              Rota Regulatória
            </h2>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${ROTA_STATUS_CLS[rota.status]}`}>
              {ROTA_STATUS_LABEL[rota.status]}
            </span>
            {/* Sinal de gravação em curso — o toast confirma depois, este diz
                que a ordem está a caminho do servidor e não só na tela. */}
            {reordenarMut.isPending && (
              <span className="inline-flex items-center gap-1 text-[10px] text-gray-500 dark:text-slate-400">
                <Loader2 className="w-3 h-3 animate-spin" /> salvando ordem…
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
            {`A IA propõe a rota; você reordena, classifica e assina. Nenhum passo sem decisão.`}
          </p>
        </div>
        {!fechada && (
          <button
            type="button"
            onClick={gerar}
            disabled={gerarMut.isPending}
            className="shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-800 dark:bg-white/10 hover:bg-gray-700 dark:hover:bg-white/20 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {gerarMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Atualizar da IA
          </button>
        )}
      </div>

      {/* Banner desatualizada */}
      {desatualizada && (
        <div className="rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-800 dark:text-amber-300">
            {`A IA trouxe passos novos após o fechamento. Valide os passos pendentes para liberar o fechamento novamente.`}
          </p>
        </div>
      )}

      {/* Lista ordenável (framer Reorder) */}
      {rota.passos.length === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400 dark:text-slate-500">
          {`Rota sem passos. Gere da IA ou adicione um passo manual.`}
        </div>
      ) : (
        <Reorder.Group axis="y" values={order} onReorder={setOrder} className="space-y-3">
          {order.map((passo, index) => (
            <PassoCard
              key={passo.id}
              passo={passo}
              processId={processId}
              rotaId={rota.id}
              fechada={fechada}
              onCommitOrder={commitOrder}
              posicao={index + 1}
              total={order.length}
              onMover={delta => moverPasso(index, delta)}
            />
          ))}
        </Reorder.Group>
      )}

      {/* Adicionar passo manual (Ficha §9) */}
      {!fechada && (
        <form onSubmit={addManual} className="space-y-2 rounded-xl border border-dashed border-gray-200 dark:border-white/10 p-3">
          <input
            type="text"
            placeholder="Adicionar passo manual (ex.: protocolar ofício na secretaria)…"
            value={novoTitulo}
            onChange={e => setNovoTitulo(e.target.value)}
            className="w-full rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
          />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Fundamento/origem (ex.: orientação verbal da secretaria)"
              value={novaNota}
              onChange={e => setNovaNota(e.target.value)}
              className="flex-1 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 px-3 py-2 text-xs focus:outline-none focus:border-emerald-500"
            />
            <button
              type="submit"
              disabled={addManualMut.isPending || !novoTitulo.trim()}
              className="px-3 py-2 rounded-lg bg-gray-800 dark:bg-white/10 hover:bg-gray-700 dark:hover:bg-white/20 disabled:opacity-40 text-white text-sm font-medium flex items-center gap-1.5 shrink-0"
            >
              <Plus className="w-4 h-4" /> Passo
            </button>
          </div>
        </form>
      )}

      {/* Rodapé — fechar rota (assinar) */}
      <div className="flex items-center justify-between gap-3 pt-2 border-t border-gray-100 dark:border-white/10">
        <p className="text-xs text-gray-500 dark:text-slate-400">
          {fechada ? (
            <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="w-4 h-4" /> Rota assinada — registrada na trilha de auditoria.
            </span>
          ) : pendentes > 0 ? (
            desatualizada
              ? `A IA trouxe mudanças: ${pendentes} passo(s) esperam sua validação.`
              : `${pendentes} passo(s) pendente(s) de validação.`
          ) : desatualizada ? (
            // Diff sem passo novo (remoção): não há o que validar — o aceite é o
            // próprio fechamento. Dizer "todos validados" aqui seria verdadeiro e
            // inútil: não explicaria por que a rota ainda não está fechada.
            `A rota mudou desde a última assinatura — feche de novo para reassinar.`
          ) : (
            `Todos os passos validados.`
          )}
        </p>
        {!fechada && (
          <button
            type="button"
            onClick={fechar}
            disabled={!podeFechar || fecharMut.isPending}
            title={podeFechar ? 'Fechar e assinar a rota' : `${pendentes} passo(s) ainda não validado(s)`}
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            {fecharMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
            Fechar rota
          </button>
        )}
      </div>
    </div>
  );
}
