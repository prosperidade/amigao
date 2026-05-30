"""Regras de coerência entre os status do alerta regulatório.

Fecha a dívida #17 do `docs/REGISTRO_DIVIDAS.md` (PROMPT_8). A reconciliação
(Opção A, ver `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md`) deu três
dimensões ortogonais (`status_achado` + `status_saneamento` no
`RegulatoryIssue`, `decisao` em `ProcessIssueDecision`). Os enums são soltos
no DB — em tese o sistema aceita combinações que o negócio considera
incoerentes. Aqui barramos os absurdos óbvios.

Escopo fechado em 2 helpers — não é máquina de estados completa (over-eng
para dívida P2; o consultor não é adversário). Só barra o que constrange:

- Regra A — `assert_status_coerente(status_achado, status_saneamento)`:
  saneamento ATIVO (`em_validacao`) ou CONCLUÍDO (`saneado`) exige que o
  achado esteja `confirmada` ou `resolvida`. Saneamento só faz sentido
  depois que o consultor confirmou que a divergência é real.

- Regra B — `assert_decisao_permitida(status_achado)`: não dá pra registrar
  decisão (`PUT /processes/.../issues/.../decision`) se o achado ainda é só
  `suspeita`. Decide-se o que fazer com a divergência depois de confirmar
  que ela é real.

Pontos de chamada:
- `@model_validator` de `RegulatoryIssueUpdate` (fast-fail quando os 2 status
  vêm juntos no corpo, sem ler o DB);
- endpoint `PATCH /properties/{prop}/issues/{id}` sobre o estado **resultante**
  (corpo aplicado sobre o estado já carregado — fonte da verdade);
- endpoint `PUT /processes/{pid}/issues/{iid}/decision` (carrega a issue e
  rejeita se `status_achado == suspeita`).

Por que `resolvida` também habilita saneamento? Decisão de UX validada com
o Andre em 26/05: `StatusAchado.resolvida` é a evolução terminal de
`confirmada` (a divergência foi sanada no mundo) — bloquear a transição
simultânea `confirmada → resolvida` + `em_validacao → saneado` em um único
PATCH forçaria salvar em duas etapas, sem ganho de invariante.
"""

from __future__ import annotations

from app.models.regulatory import StatusAchado, StatusSaneamento

# Saneamento que pressupõe achado validado: ativo no fluxo ou concluído.
# Os demais (`pendente`, `descartado`, `nao_aplicavel`) não constrangem a
# natureza do achado.
_SANEAMENTO_EXIGE_ACHADO_VALIDADO: frozenset[StatusSaneamento] = frozenset(
    {StatusSaneamento.em_validacao, StatusSaneamento.saneado}
)

# Achados que habilitam saneamento ativo/concluído. `resolvida` entra porque
# é o terminal natural de `confirmada` (saneou no mundo) — bloquear a
# transição simultânea seria UX ruim sem ganho.
_ACHADOS_QUE_HABILITAM_SANEAMENTO: frozenset[StatusAchado] = frozenset(
    {StatusAchado.confirmada, StatusAchado.resolvida}
)


class StatusCoherenceError(ValueError):
    """Combinação incoerente entre os status do `RegulatoryIssue`, ou
    tentativa de decidir sobre um achado ainda em `suspeita`.

    Subclasse de `ValueError` para que `@model_validator` do Pydantic
    converta automaticamente em `ValidationError` (e o FastAPI traduza
    em HTTP 422 com payload padrão). Nos endpoints, capturamos
    explicitamente para devolver mensagem acionável.
    """


def assert_status_coerente(
    status_achado: StatusAchado,
    status_saneamento: StatusSaneamento,
) -> None:
    """Regra A — saneamento ATIVO/CONCLUÍDO exige achado validado.

    Args:
        status_achado: estado resultante do achado (após aplicar PATCH).
        status_saneamento: estado resultante do saneamento (após aplicar PATCH).

    Raises:
        StatusCoherenceError: quando a combinação for proibida.
    """
    if (
        status_saneamento in _SANEAMENTO_EXIGE_ACHADO_VALIDADO
        and status_achado not in _ACHADOS_QUE_HABILITAM_SANEAMENTO
    ):
        raise StatusCoherenceError(
            f"Combinação inválida: saneamento '{status_saneamento.value}' "
            f"exige que o achado esteja 'confirmada' ou 'resolvida' "
            f"(atual: '{status_achado.value}')."
        )


def assert_decisao_permitida(status_achado: StatusAchado) -> None:
    """Regra B — bloqueia registro de decisão quando o achado é só suspeita.

    Args:
        status_achado: estado atual do achado na `RegulatoryIssue`.

    Raises:
        StatusCoherenceError: quando `status_achado == suspeita`.
    """
    if status_achado == StatusAchado.suspeita:
        raise StatusCoherenceError(
            "Não é possível registrar decisão: o achado ainda está como "
            "'suspeita'. Confirme ou descarte o achado antes de decidir."
        )
