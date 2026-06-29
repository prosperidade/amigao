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
    list_macroetapa_blockers,
    resolve_next_macroetapa,
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


class TestResolveNextMacroetapaRamoE2:
    """Sprint 1 (Ficha 07) — ramo condicional na saída da E2.

    `resolve_next_macroetapa` decide o DESTINO recomendado do avanço:
    coleta (E3) quando há documento essencial pendente, diagnóstico técnico
    (E4) quando não há. Demais etapas seguem o sucessor linear.
    """

    def test_e2_com_doc_essencial_pendente_vai_para_coleta(self) -> None:
        assert resolve_next_macroetapa(
            Macroetapa.diagnostico_preliminar, has_essential_pending=True
        ) is Macroetapa.coleta_documental

    def test_e2_sem_doc_essencial_pendente_pula_para_diagnostico_tecnico(self) -> None:
        assert resolve_next_macroetapa(
            Macroetapa.diagnostico_preliminar, has_essential_pending=False
        ) is Macroetapa.diagnostico_tecnico

    def test_e1_segue_linear_para_e2(self) -> None:
        assert resolve_next_macroetapa(
            Macroetapa.entrada_demanda, has_essential_pending=True
        ) is Macroetapa.diagnostico_preliminar

    def test_coleta_segue_linear_para_diagnostico_tecnico(self) -> None:
        """E3 (quando percorrida) sempre vai para E4 — pendência não a afeta."""
        assert resolve_next_macroetapa(
            Macroetapa.coleta_documental, has_essential_pending=True
        ) is Macroetapa.diagnostico_tecnico

    def test_etapa_terminal_retorna_none(self) -> None:
        assert resolve_next_macroetapa(Macroetapa.contrato_formalizacao) is None

    def test_current_none_retorna_none(self) -> None:
        assert resolve_next_macroetapa(None) is None

    def test_ambas_transicoes_da_e2_sao_validas(self) -> None:
        """E4 alcançável direto da E2 (não exige passar por E3)."""
        from app.models.macroetapa import is_valid_macroetapa_transition

        assert is_valid_macroetapa_transition(
            Macroetapa.diagnostico_preliminar, Macroetapa.coleta_documental
        )
        assert is_valid_macroetapa_transition(
            Macroetapa.diagnostico_preliminar, Macroetapa.diagnostico_tecnico
        )


class TestRamoE2DocPendenteRoteiaNaoTrava:
    """Sprint 1 — doc essencial pendente ROTEIA (não trava) ao sair da E2.

    Travar a E2 por documento pendente impediria justamente o caminho que
    existe para coletá-lo (E3). Nas demais etapas o doc pendente segue blocker.
    """

    def test_e2_com_doc_pendente_nao_gera_blocker(self) -> None:
        blockers = list_macroetapa_blockers(
            _checklist(),
            documents_pending_required=3,
            current_macroetapa=Macroetapa.diagnostico_preliminar,
        )
        assert blockers == []

    def test_coleta_com_doc_pendente_gera_blocker(self) -> None:
        blockers = list_macroetapa_blockers(
            _checklist(),
            documents_pending_required=2,
            current_macroetapa=Macroetapa.coleta_documental,
        )
        assert any("pendente" in b.lower() for b in blockers)

    def test_e2_avanca_com_doc_pendente_se_assinado(self) -> None:
        """Com diagnóstico assinado + checklist 100%, a E2 avança mesmo com
        documento essencial pendente (vai rotear para a coleta)."""
        ok, blockers = can_advance_macroetapa(
            _checklist(completion_pct=100.0),
            documents_pending_required=3,
            current_macroetapa=Macroetapa.diagnostico_preliminar,
            diagnosis_validated=True,
        )
        assert ok is True
        assert blockers == []

    def test_coleta_nao_avanca_com_doc_pendente(self) -> None:
        ok, blockers = can_advance_macroetapa(
            _checklist(completion_pct=100.0),
            documents_pending_required=1,
            current_macroetapa=Macroetapa.coleta_documental,
        )
        assert ok is False
        assert any("pendente" in b.lower() for b in blockers)
