"""Testes unitários do gate de macroetapa em torno do fix
`fix/diagnostico-propaga-estado`.

Os kwargs `current_macroetapa` e `diagnosis_validated` foram acrescentados em
`can_advance_macroetapa` e `compute_macroetapa_state` para honrar o
Princípio 1 do manifesto — peças formais (o diagnóstico regulatório) só
"fecham" depois da assinatura humana, e a saída da etapa de diagnóstico
exige esse fato.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.models.macroetapa import (
    Macroetapa,
    MacroetapaState,
    can_advance_macroetapa,
    compute_macroetapa_state,
)


def _checklist(*, completion_pct: float = 100.0, actions: list[dict] | None = None):
    """Stub leve do ORM MacroetapaChecklist com só os atributos lidos pelas
    funções pure. `completion_pct` na escala 0–100 (100 = etapa completa)."""
    return SimpleNamespace(
        completion_pct=completion_pct,
        actions=actions or [{"id": "x", "completed": True}],
    )


class TestCanAdvanceMacroetapaDiagnosticGate:
    def test_diagnostico_preliminar_sem_assinatura_bloqueia(self) -> None:
        ok, blockers = can_advance_macroetapa(
            _checklist(),
            current_macroetapa=Macroetapa.diagnostico_preliminar,
            diagnosis_validated=False,
        )
        assert ok is False
        assert any("assinado" in b.lower() for b in blockers)

    def test_diagnostico_preliminar_com_assinatura_libera(self) -> None:
        ok, blockers = can_advance_macroetapa(
            _checklist(),
            current_macroetapa=Macroetapa.diagnostico_preliminar,
            diagnosis_validated=True,
        )
        assert ok is True
        assert blockers == []

    def test_diagnostico_tecnico_sem_assinatura_bloqueia(self) -> None:
        ok, blockers = can_advance_macroetapa(
            _checklist(),
            current_macroetapa=Macroetapa.diagnostico_tecnico,
            diagnosis_validated=False,
        )
        assert ok is False
        assert any("assinado" in b.lower() for b in blockers)

    def test_etapa_nao_diagnostica_nao_e_afetada_pela_assinatura(self) -> None:
        """Etapas fora de diagnóstico ignoram a flag — comportamento legado
        preservado."""
        ok, blockers = can_advance_macroetapa(
            _checklist(),
            current_macroetapa=Macroetapa.coleta_documental,
            diagnosis_validated=False,
        )
        assert ok is True
        assert blockers == []

    def test_sem_current_macroetapa_mantem_comportamento_legado(self) -> None:
        """Callers que ainda não passam o etapa atual não sofrem regressão."""
        ok, blockers = can_advance_macroetapa(_checklist())
        assert ok is True
        assert blockers == []


class TestComputeMacroetapaStateBadge:
    def test_diagnostico_preliminar_100pct_sem_assinatura_e_aguardando_validacao(
        self,
    ) -> None:
        """Badge não vai pra `pronta_para_avancar` enquanto o diagnóstico
        não estiver assinado — card e bloco "diagnóstico assinado" passam a
        concordar."""
        state = compute_macroetapa_state(
            _checklist(completion_pct=100.0),
            is_current=True,
            current_macroetapa=Macroetapa.diagnostico_preliminar,
            diagnosis_validated=False,
        )
        assert state is MacroetapaState.aguardando_validacao

    def test_diagnostico_preliminar_100pct_com_assinatura_e_pronta(self) -> None:
        state = compute_macroetapa_state(
            _checklist(completion_pct=100.0),
            is_current=True,
            current_macroetapa=Macroetapa.diagnostico_preliminar,
            diagnosis_validated=True,
        )
        assert state is MacroetapaState.pronta_para_avancar

    def test_etapa_nao_diagnostica_100pct_e_pronta_sem_assinatura(self) -> None:
        """Para etapas não-diagnósticas, completion_pct=100 (completo) manda."""
        state = compute_macroetapa_state(
            _checklist(completion_pct=100.0),
            is_current=True,
            current_macroetapa=Macroetapa.coleta_documental,
            diagnosis_validated=False,
        )
        assert state is MacroetapaState.pronta_para_avancar


class TestGateEscala0a100:
    """Fecha o furo latente: `completion_pct` é 0–100; o gate/estado comparavam
    contra 1.0, então uma etapa a 20% "passava". Agora só passa a 100."""

    def test_checklist_20pct_nao_passa_o_gate(self) -> None:
        ok, blockers = can_advance_macroetapa(
            _checklist(completion_pct=20.0),
            current_macroetapa=Macroetapa.coleta_documental,
        )
        assert ok is False
        assert any("incompleto" in b.lower() for b in blockers)

    def test_checklist_100pct_passa_o_gate(self) -> None:
        ok, blockers = can_advance_macroetapa(
            _checklist(completion_pct=100.0),
            current_macroetapa=Macroetapa.coleta_documental,
        )
        assert ok is True
        assert blockers == []

    def test_estado_20pct_e_em_andamento_nao_pronta(self) -> None:
        """Badge não mente: a 20% a etapa está em andamento, não pronta."""
        state = compute_macroetapa_state(
            _checklist(completion_pct=20.0),
            is_current=True,
            current_macroetapa=Macroetapa.coleta_documental,
            diagnosis_validated=False,
        )
        assert state is MacroetapaState.em_andamento
