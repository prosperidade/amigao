"""Validação 02/08 (item 1) — checklists da E1/E2 realinhados à Ficha 07.

Os checklists nasciam deslocados uma etapa: a E2 ("Diagnóstico Preliminar")
listava a CONVERSA de entrada — "realizar ligação · aplicar roteiro ·
transcrever áudio · identificar tipo de demanda · classificar urgência" — que
é insumo do intake, não diagnóstico; e a E1 listava só o cadastro que se faz
antes de abrir o caso. A consultora leu isso na tela e disse o óbvio: "isso é
pré-diagnóstico".

A Ficha 07 é a fonte de verdade e diz outra coisa:

  §5  E1 Entrada        — "Documentos: primeiros uploads + checklist;
                           Dados: cadastro básico"
      E2 Diag. Prelim.  — "Conferência: campos do intake (protagonista);
                           Dados: base consolidada; Visão geral: nasce o
                           diagnóstico preliminar; Ações: remediação +
                           divergências + pendências"
  §7  saída da E1       — "mínimo essencial recebido + agentes do intake rodados"
      saída da E2       — "diagnóstico gerado + base consolidada"

Logo: conversa/roteiro/áudio/classificação da demanda são trabalho da E1 (é
deles que o intake se alimenta); conferir, consolidar, ler o diagnóstico e
triar ações são trabalho da E2.

BACKFILL (casos vivos)
──────────────────────
Reescrever a lista sem cuidado zeraria o progresso de quem está no meio do
fluxo. Duas políticas, por posição do caso:

* etapa JÁ PASSADA (índice menor que a macroetapa atual do processo) — a tela
  já a mostra "completed" por índice (`get_macroetapa_status`), então a lista
  nova entra inteira marcada. Não se reabre trabalho que o caso deixou para
  trás.
* etapa ATUAL ou futura — o estado é MIGRADO item a item pelo mapa abaixo.
  Item novo, sem antecessor, nasce desmarcado; item que resultou da fusão de
  dois antigos só é marcado se AMBOS estavam marcados (conservador: não se
  declara feito o que não se sabe feito).

Revision ID: b4c8d1e6a293
Revises: b5c92fa4d7e1
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "b4c8d1e6a293"
down_revision = "b5c92fa4d7e1"
branch_labels = None
depends_on = None


# Ordem canônica das 7 macroetapas (para saber o que é "etapa já passada").
_ORDER = [
    "entrada_demanda",
    "diagnostico_preliminar",
    "coleta_documental",
    "diagnostico_tecnico",
    "caminho_regulatorio",
    "orcamento_negociacao",
    "contrato_formalizacao",
]
_INDEX = {m: i for i, m in enumerate(_ORDER)}

# ── Listas NOVAS (espelham DEFAULT_ACTIONS em app/models/macroetapa.py) ──────
_NEW_E1 = [
    ("ed_01", "Registrar dados básicos do cliente (e verificar duplicidade)"),
    ("ed_02", "Identificar canal de entrada"),
    ("ed_03", "Vincular imóvel ao caso"),
    ("ed_04", "Realizar ligação/reunião aplicando o roteiro de perguntas"),
    ("ed_05", "Subir e transcrever o áudio da conversa"),
    ("ed_06", "Registrar a demanda e a intenção do empreendedor"),
    ("ed_07", "Subir os documentos do mínimo essencial"),
    ("ed_08", "Rodar os agentes do intake (tipo de demanda e urgência)"),
]
_NEW_E2 = [
    ("dp_01", "Conferir os campos lidos dos documentos (Conferência)"),
    ("dp_02", "Resolver as divergências apontadas"),
    ("dp_03", "Gravar na base (Consolidação)"),
    ("dp_04", "Ler o diagnóstico preliminar na Visão geral"),
    ("dp_05", "Validar objetivo real do cliente"),
    ("dp_06", "Triar as ações de remediação propostas"),
    ("dp_07", "Identificar lacunas e documentos essenciais pendentes"),
]

# ── Listas ANTIGAS (para o downgrade) ───────────────────────────────────────
_OLD_E1 = [
    ("ed_01", "Registrar dados básicos do cliente"),
    ("ed_02", "Identificar canal de entrada"),
    ("ed_03", "Vincular imóvel ao caso"),
    ("ed_04", "Registrar demanda inicial"),
    ("ed_05", "Verificar cliente existente (deduplicação)"),
]
_OLD_E2 = [
    ("dp_01", "Realizar ligação/reunião"),
    ("dp_02", "Aplicar roteiro de perguntas"),
    ("dp_03", "Gravar/transcrever áudio"),
    ("dp_04", "Identificar tipo de demanda"),
    ("dp_05", "Classificar urgência"),
    ("dp_06", "Validar objetivo real do cliente"),
    ("dp_07", "Consolidar ficha inicial do caso"),
    ("dp_08", "Identificar lacunas de informação"),
]

# ── Mapa (etapa_antiga, id_antigo) → (etapa_nova, id_novo) ──────────────────
# A conversa migra de etapa: o que era dp_01..dp_05 na E2 vira ed_04..ed_08 na E1.
_MIGRA = {
    ("entrada_demanda", "ed_01"): ("entrada_demanda", "ed_01"),
    ("entrada_demanda", "ed_02"): ("entrada_demanda", "ed_02"),
    ("entrada_demanda", "ed_03"): ("entrada_demanda", "ed_03"),
    ("entrada_demanda", "ed_04"): ("entrada_demanda", "ed_06"),
    ("entrada_demanda", "ed_05"): ("entrada_demanda", "ed_01"),
    ("diagnostico_preliminar", "dp_01"): ("entrada_demanda", "ed_04"),
    ("diagnostico_preliminar", "dp_02"): ("entrada_demanda", "ed_04"),
    ("diagnostico_preliminar", "dp_03"): ("entrada_demanda", "ed_05"),
    ("diagnostico_preliminar", "dp_04"): ("entrada_demanda", "ed_08"),
    ("diagnostico_preliminar", "dp_05"): ("entrada_demanda", "ed_08"),
    ("diagnostico_preliminar", "dp_06"): ("diagnostico_preliminar", "dp_05"),
    ("diagnostico_preliminar", "dp_07"): ("diagnostico_preliminar", "dp_03"),
    ("diagnostico_preliminar", "dp_08"): ("diagnostico_preliminar", "dp_07"),
}

_ETAPAS = ("entrada_demanda", "diagnostico_preliminar")


def _loads(value):
    """A coluna é JSONB no Postgres (vem dict/list) e Text no SQLite (vem str)."""
    if value is None:
        return []
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _pct(actions: list) -> float:
    if not actions:
        return 0.0
    done = sum(1 for a in actions if a.get("completed"))
    return round((done / len(actions)) * 100, 1)


def _reescrever(conn, novas: dict, antigas: dict) -> None:
    """Reescreve os checklists de E1/E2 aplicando `_MIGRA` (ou o inverso).

    ``novas``/``antigas`` mapeiam etapa → lista de (id, label). O mapa de
    migração usado é sempre ``_MIGRA``; no downgrade ele é invertido.
    """
    is_pg = conn.dialect.name == "postgresql"

    # macroetapa atual de cada processo (para separar etapa passada de atual)
    atual = {
        row[0]: row[1]
        for row in conn.execute(sa.text("SELECT id, macroetapa FROM processes")).fetchall()
    }

    rows = conn.execute(
        sa.text(
            "SELECT id, process_id, macroetapa, actions FROM macroetapa_checklists "
            "WHERE macroetapa IN ('entrada_demanda', 'diagnostico_preliminar') "
            "ORDER BY process_id, macroetapa"
        )
    ).fetchall()

    # Estado antigo agrupado por processo — a migração cruza as duas etapas.
    por_processo: dict[int, dict[str, dict[str, bool]]] = {}
    for _cid, pid, etapa, actions in rows:
        feitos = {
            a.get("id"): bool(a.get("completed"))
            for a in _loads(actions)
            if isinstance(a, dict) and a.get("id")
        }
        por_processo.setdefault(pid, {})[etapa] = feitos

    for cid, pid, etapa, _actions in rows:
        idx_etapa = _INDEX.get(etapa, 0)
        idx_atual = _INDEX.get(atual.get(pid) or "", -1)
        etapa_passada = idx_atual > idx_etapa

        destino = novas.get(etapa, [])
        if etapa_passada:
            # Etapa que o caso já deixou para trás: entra inteira marcada.
            novas_actions = [
                {"id": i, "label": lb, "completed": True, "completed_at": None,
                 "agent_suggestion": None}
                for i, lb in destino
            ]
        else:
            # Contribuições vindas de QUALQUER etapa antiga para este id novo.
            contribuicoes: dict[str, list[bool]] = {}
            for (etapa_old, id_old), (etapa_new, id_new) in _MIGRA.items():
                if etapa_new != etapa:
                    continue
                feitos = por_processo.get(pid, {}).get(etapa_old, {})
                if id_old in feitos:
                    contribuicoes.setdefault(id_new, []).append(feitos[id_old])
            novas_actions = [
                {
                    "id": i,
                    "label": lb,
                    # Fusão de dois antigos só conta como feito se AMBOS estavam.
                    "completed": bool(contribuicoes.get(i)) and all(contribuicoes[i]),
                    "completed_at": None,
                    "agent_suggestion": None,
                }
                for i, lb in destino
            ]

        payload = json.dumps(novas_actions, ensure_ascii=False)
        conn.execute(
            sa.text(
                "UPDATE macroetapa_checklists SET actions = "
                + ("CAST(:actions AS jsonb)" if is_pg else ":actions")
                + ", completion_pct = :pct WHERE id = :id"
            ),
            {"actions": payload, "pct": _pct(novas_actions), "id": cid},
        )

    _ = antigas  # simetria da assinatura; o mapa já carrega a direção


def upgrade() -> None:
    conn = op.get_bind()
    _reescrever(
        conn,
        novas={"entrada_demanda": _NEW_E1, "diagnostico_preliminar": _NEW_E2},
        antigas={"entrada_demanda": _OLD_E1, "diagnostico_preliminar": _OLD_E2},
    )


def downgrade() -> None:
    """Volta às listas antigas.

    O estado item-a-item NÃO é reconstruído (a fusão ed_01←ed_05 e ed_04←dp_01+dp_02
    perde informação por natureza): etapa passada volta marcada, etapa atual volta
    desmarcada. É a perda honesta de um downgrade de conteúdo, não de esquema.
    """
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"
    atual = {
        row[0]: row[1]
        for row in conn.execute(sa.text("SELECT id, macroetapa FROM processes")).fetchall()
    }
    rows = conn.execute(
        sa.text(
            "SELECT id, process_id, macroetapa FROM macroetapa_checklists "
            "WHERE macroetapa IN ('entrada_demanda', 'diagnostico_preliminar')"
        )
    ).fetchall()
    velhas = {"entrada_demanda": _OLD_E1, "diagnostico_preliminar": _OLD_E2}
    for cid, pid, etapa in rows:
        passada = _INDEX.get(atual.get(pid) or "", -1) > _INDEX.get(etapa, 0)
        actions = [
            {"id": i, "label": lb, "completed": passada, "completed_at": None,
             "agent_suggestion": None}
            for i, lb in velhas.get(etapa, [])
        ]
        payload = json.dumps(actions, ensure_ascii=False)
        conn.execute(
            sa.text(
                "UPDATE macroetapa_checklists SET actions = "
                + ("CAST(:actions AS jsonb)" if is_pg else ":actions")
                + ", completion_pct = :pct WHERE id = :id"
            ),
            {"actions": payload, "pct": _pct(actions), "id": cid},
        )
