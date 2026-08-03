"""Os checklists por macroetapa não podem escorregar de etapa (validação 02/08).

O bug que este arquivo tranca: a E2 ("Diagnóstico Preliminar") listava a
CONVERSA de entrada — "realizar ligação · aplicar roteiro · transcrever áudio ·
identificar tipo de demanda · classificar urgência" — e a E1 listava só o
cadastro pré-abertura. A consultora abriu a E2 e disse: "isso é pré-diagnóstico".

A Ficha 07 §5/§7 é a fonte de verdade:
  E1 Entrada  → uploads + cadastro básico; sai com "mínimo essencial recebido +
                agentes do intake rodados"  ⇒ a conversa que ALIMENTA o intake
                é trabalho da E1.
  E2 Diag.    → Conferência (campos do intake) + base consolidada + nasce o
                diagnóstico preliminar; sai com "diagnóstico gerado + base
                consolidada".

Estes testes falham se alguém devolver o vocabulário de uma etapa para a outra.
"""

from __future__ import annotations

import pytest

from app.models.macroetapa import DEFAULT_ACTIONS, MACROETAPA_ORDER, Macroetapa


def _labels(etapa: Macroetapa) -> str:
    """Todos os rótulos da etapa em uma string minúscula, para busca por termo."""
    return " · ".join(a["label"] for a in DEFAULT_ACTIONS[etapa]).lower()


# ---------------------------------------------------------------------------
# O deslocamento em si
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "termo",
    ["ligação", "roteiro", "áudio", "tipo de demanda", "urgência", "mínimo essencial"],
)
def test_conversa_do_intake_pertence_a_e1_e_nao_a_e2(termo: str) -> None:
    """Conversa, áudio e classificação da demanda alimentam o intake ⇒ E1."""
    assert termo in _labels(Macroetapa.entrada_demanda), (
        f"'{termo}' sumiu da E1 — a Ficha 07 §7 põe a conversa do intake na Entrada"
    )
    assert termo not in _labels(Macroetapa.diagnostico_preliminar), (
        f"'{termo}' voltou para a E2 — é pré-diagnóstico, não diagnóstico "
        "(foi exatamente esta a queixa da validação de 02/08)"
    )


@pytest.mark.parametrize(
    "termo",
    ["conferir", "divergências", "consolidação", "diagnóstico preliminar", "lacunas"],
)
def test_trabalho_de_diagnostico_pertence_a_e2_e_nao_a_e1(termo: str) -> None:
    """Conferir, consolidar, ler o diagnóstico e triar ações ⇒ E2 (Ficha 07 §5)."""
    assert termo in _labels(Macroetapa.diagnostico_preliminar), (
        f"'{termo}' sumiu da E2 — é o conteúdo que a Ficha 07 §5 dá ao Diagnóstico Preliminar"
    )
    assert termo not in _labels(Macroetapa.entrada_demanda), (
        f"'{termo}' escorregou para a E1 — a Entrada ainda não tem base consolidada"
    )


def test_e2_nao_repete_o_checklist_da_e1() -> None:
    """As duas listas não podem convergir para o mesmo texto."""
    e1 = {a["label"] for a in DEFAULT_ACTIONS[Macroetapa.entrada_demanda]}
    e2 = {a["label"] for a in DEFAULT_ACTIONS[Macroetapa.diagnostico_preliminar]}
    assert not (e1 & e2), f"rótulos duplicados entre E1 e E2: {sorted(e1 & e2)}"


# ---------------------------------------------------------------------------
# Integridade estrutural (vale para as 7 etapas)
# ---------------------------------------------------------------------------

def test_todas_as_macroetapas_tem_checklist() -> None:
    for etapa in MACROETAPA_ORDER:
        assert DEFAULT_ACTIONS.get(etapa), f"macroetapa sem checklist: {etapa.value}"


def test_ids_sao_unicos_e_ordenados_por_etapa() -> None:
    """`id` é a chave que a migration usa para migrar estado — tem de ser estável.

    O sufixo numérico precisa acompanhar a POSIÇÃO na lista: é isso que faz o
    checklist ser lido como uma sequência de trabalho, e não um saco de tarefas.
    """
    for etapa in MACROETAPA_ORDER:
        ids = [a["id"] for a in DEFAULT_ACTIONS[etapa]]
        assert len(ids) == len(set(ids)), f"ids repetidos em {etapa.value}: {ids}"

        prefixo = ids[0].split("_")[0]
        assert all(i.startswith(f"{prefixo}_") for i in ids), (
            f"{etapa.value} mistura prefixos de id: {ids}"
        )
        assert ids == [f"{prefixo}_{n:02d}" for n in range(1, len(ids) + 1)], (
            f"{etapa.value} tem ids fora de ordem/sequência: {ids}"
        )


def test_todo_item_tem_id_e_label_nao_vazios() -> None:
    for etapa in MACROETAPA_ORDER:
        for item in DEFAULT_ACTIONS[etapa]:
            assert item.get("id", "").strip(), f"item sem id em {etapa.value}: {item}"
            assert item.get("label", "").strip(), f"item sem label em {etapa.value}: {item}"


def test_migration_do_item_1_cobre_todos_os_ids_novos_de_e1_e_e2() -> None:
    """A migration precisa saber o destino de cada id novo — senão o backfill mente.

    Importa o mapa da própria migration: se alguém acrescentar um item na E1/E2
    sem ensinar a migration, este teste acusa (o item nasceria desmarcado em
    silêncio para todo caso vivo).
    """
    import importlib.util
    from pathlib import Path

    caminho = (
        Path(__file__).resolve().parents[2]
        / "alembic" / "versions" / "b4c8d1e6a293_validacao_0208_checklists_ficha07.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_b4c8d1e6a293", caminho)
    assert spec and spec.loader
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    for etapa, esperado in (
        (Macroetapa.entrada_demanda, mig._NEW_E1),
        (Macroetapa.diagnostico_preliminar, mig._NEW_E2),
    ):
        atual = [(a["id"], a["label"]) for a in DEFAULT_ACTIONS[etapa]]
        assert atual == list(esperado), (
            f"a migration e o DEFAULT_ACTIONS divergiram em {etapa.value} — "
            "o backfill gravaria uma lista diferente da que o código serve"
        )
