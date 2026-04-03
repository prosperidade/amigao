"""
Testes de contrato para as máquinas de estados de Task e Process.

Validam:
- Todas as transições válidas são aceitas
- Todas as transições inválidas são rejeitadas
- Terminais não possuem saída (exceto auto-transição em Task)
- Cada status aparece nas transições (sem órfãos)
- Consistência entre enum e mapa de transições
"""

import pytest

from app.models.process import (
    TERMINAL_PROCESS_STATUSES,
    ProcessStatus,
)
from app.models.process import (
    VALID_TRANSITIONS as VALID_PROCESS_TRANSITIONS,
)
from app.models.process import (
    is_valid_transition as is_valid_process_transition,
)
from app.models.task import (
    TERMINAL_TASK_STATUSES,
    VALID_TASK_TRANSITIONS,
    TaskStatus,
    is_valid_task_transition,
)

# ============================================================
# Task State Machine
# ============================================================

class TestTaskStateMachine:
    """Testes de contrato para a máquina de estados de Task."""

    def test_all_statuses_have_transitions_defined(self):
        """Todo status do enum deve ter uma entrada no mapa de transições."""
        for status in TaskStatus:
            assert status in VALID_TASK_TRANSITIONS, (
                f"TaskStatus.{status.name} não tem transições definidas"
            )

    def test_no_extra_keys_in_transitions(self):
        """Mapa de transições não deve ter chaves fora do enum."""
        for key in VALID_TASK_TRANSITIONS:
            assert key in TaskStatus, f"Chave {key} não pertence ao TaskStatus enum"

    def test_transition_targets_are_valid_statuses(self):
        """Todo target de transição deve ser um status válido."""
        for from_status, targets in VALID_TASK_TRANSITIONS.items():
            for target in targets:
                assert target in TaskStatus, (
                    f"Transição {from_status} -> {target}: target inválido"
                )

    def test_terminal_statuses_have_no_outgoing(self):
        """cancelada não deve ter transições de saída."""
        assert VALID_TASK_TRANSITIONS[TaskStatus.cancelada] == []

    def test_concluida_only_goes_to_cancelada(self):
        """concluida só transiciona para cancelada."""
        assert VALID_TASK_TRANSITIONS[TaskStatus.concluida] == [TaskStatus.cancelada]

    def test_terminal_set_matches_definition(self):
        """TERMINAL_TASK_STATUSES deve conter exatamente concluida e cancelada."""
        assert {TaskStatus.concluida, TaskStatus.cancelada} == TERMINAL_TASK_STATUSES

    def test_self_transition_is_allowed(self):
        """Auto-transição (mesmo status) deve ser aceita."""
        for status in TaskStatus:
            assert is_valid_task_transition(status, status) is True

    @pytest.mark.parametrize("from_s,to_s", [
        (TaskStatus.backlog, TaskStatus.a_fazer),
        (TaskStatus.backlog, TaskStatus.cancelada),
        (TaskStatus.a_fazer, TaskStatus.em_progresso),
        (TaskStatus.a_fazer, TaskStatus.cancelada),
        (TaskStatus.em_progresso, TaskStatus.aguardando),
        (TaskStatus.em_progresso, TaskStatus.revisao),
        (TaskStatus.em_progresso, TaskStatus.cancelada),
        (TaskStatus.aguardando, TaskStatus.em_progresso),
        (TaskStatus.aguardando, TaskStatus.cancelada),
        (TaskStatus.revisao, TaskStatus.concluida),
        (TaskStatus.revisao, TaskStatus.cancelada),
        (TaskStatus.concluida, TaskStatus.cancelada),
    ])
    def test_valid_transitions_accepted(self, from_s, to_s):
        assert is_valid_task_transition(from_s, to_s) is True

    @pytest.mark.parametrize("from_s,to_s", [
        (TaskStatus.backlog, TaskStatus.concluida),
        (TaskStatus.backlog, TaskStatus.revisao),
        (TaskStatus.a_fazer, TaskStatus.concluida),
        (TaskStatus.a_fazer, TaskStatus.revisao),
        (TaskStatus.em_progresso, TaskStatus.concluida),
        (TaskStatus.em_progresso, TaskStatus.backlog),
        (TaskStatus.aguardando, TaskStatus.concluida),
        (TaskStatus.revisao, TaskStatus.backlog),
        (TaskStatus.revisao, TaskStatus.em_progresso),
        (TaskStatus.cancelada, TaskStatus.backlog),
        (TaskStatus.cancelada, TaskStatus.a_fazer),
        (TaskStatus.cancelada, TaskStatus.concluida),
    ])
    def test_invalid_transitions_rejected(self, from_s, to_s):
        assert is_valid_task_transition(from_s, to_s) is False

    def test_every_non_terminal_status_is_reachable(self):
        """Todo status não-terminal deve ser target de pelo menos uma transição."""
        all_targets = set()
        for targets in VALID_TASK_TRANSITIONS.values():
            all_targets.update(targets)
        # backlog é o status inicial, então pode não ser target
        non_initial = {s for s in TaskStatus if s != TaskStatus.backlog}
        unreachable = non_initial - all_targets
        assert unreachable == set(), f"Status inalcançáveis: {unreachable}"


# ============================================================
# Process State Machine
# ============================================================

class TestProcessStateMachine:
    """Testes de contrato para a máquina de estados de Process."""

    def test_all_statuses_have_transitions_defined(self):
        for status in ProcessStatus:
            assert status in VALID_PROCESS_TRANSITIONS, (
                f"ProcessStatus.{status.name} não tem transições definidas"
            )

    def test_no_extra_keys_in_transitions(self):
        for key in VALID_PROCESS_TRANSITIONS:
            assert key in ProcessStatus, f"Chave {key} não pertence ao ProcessStatus enum"

    def test_transition_targets_are_valid_statuses(self):
        for from_status, targets in VALID_PROCESS_TRANSITIONS.items():
            for target in targets:
                assert target in ProcessStatus, (
                    f"Transição {from_status} -> {target}: target inválido"
                )

    def test_terminal_status_has_no_outgoing(self):
        """arquivado não deve ter transições de saída."""
        assert VALID_PROCESS_TRANSITIONS[ProcessStatus.arquivado] == []

    def test_terminal_set(self):
        assert {ProcessStatus.arquivado} == TERMINAL_PROCESS_STATUSES

    def test_self_transition_not_allowed(self):
        """Process não permite auto-transição (diferente de Task)."""
        for status in ProcessStatus:
            assert is_valid_process_transition(status, status) is False

    @pytest.mark.parametrize("from_s,to_s", [
        (ProcessStatus.lead, ProcessStatus.triagem),
        (ProcessStatus.triagem, ProcessStatus.diagnostico),
        (ProcessStatus.triagem, ProcessStatus.cancelado),
        (ProcessStatus.diagnostico, ProcessStatus.planejamento),
        (ProcessStatus.diagnostico, ProcessStatus.cancelado),
        (ProcessStatus.planejamento, ProcessStatus.execucao),
        (ProcessStatus.execucao, ProcessStatus.protocolo),
        (ProcessStatus.execucao, ProcessStatus.cancelado),
        (ProcessStatus.protocolo, ProcessStatus.aguardando_orgao),
        (ProcessStatus.aguardando_orgao, ProcessStatus.pendencia_orgao),
        (ProcessStatus.aguardando_orgao, ProcessStatus.concluido),
        (ProcessStatus.pendencia_orgao, ProcessStatus.execucao),
        (ProcessStatus.concluido, ProcessStatus.arquivado),
        (ProcessStatus.cancelado, ProcessStatus.arquivado),
    ])
    def test_valid_transitions_accepted(self, from_s, to_s):
        assert is_valid_process_transition(from_s, to_s) is True

    @pytest.mark.parametrize("from_s,to_s", [
        (ProcessStatus.lead, ProcessStatus.diagnostico),
        (ProcessStatus.lead, ProcessStatus.cancelado),
        (ProcessStatus.triagem, ProcessStatus.lead),
        (ProcessStatus.planejamento, ProcessStatus.cancelado),
        (ProcessStatus.protocolo, ProcessStatus.cancelado),
        (ProcessStatus.concluido, ProcessStatus.lead),
        (ProcessStatus.concluido, ProcessStatus.cancelado),
        (ProcessStatus.arquivado, ProcessStatus.lead),
        (ProcessStatus.arquivado, ProcessStatus.concluido),
        (ProcessStatus.cancelado, ProcessStatus.lead),
    ])
    def test_invalid_transitions_rejected(self, from_s, to_s):
        assert is_valid_process_transition(from_s, to_s) is False

    def test_happy_path_reaches_arquivado(self):
        """Caminho feliz: lead -> triagem -> ... -> concluido -> arquivado."""
        happy_path = [
            ProcessStatus.lead,
            ProcessStatus.triagem,
            ProcessStatus.diagnostico,
            ProcessStatus.planejamento,
            ProcessStatus.execucao,
            ProcessStatus.protocolo,
            ProcessStatus.aguardando_orgao,
            ProcessStatus.concluido,
            ProcessStatus.arquivado,
        ]
        for i in range(len(happy_path) - 1):
            assert is_valid_process_transition(happy_path[i], happy_path[i + 1]) is True, (
                f"Transição {happy_path[i]} -> {happy_path[i + 1]} deveria ser válida"
            )

    def test_pendencia_loop(self):
        """pendencia_orgao volta para execucao (loop de correção)."""
        assert is_valid_process_transition(ProcessStatus.pendencia_orgao, ProcessStatus.execucao) is True
        assert is_valid_process_transition(ProcessStatus.execucao, ProcessStatus.protocolo) is True
