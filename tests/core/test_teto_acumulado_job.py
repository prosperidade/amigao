"""Dívida #272 — teto de custo ACUMULADO por job.

Até 23/09/2026 o teto era conferido por chamada, e três jobs do extrator passaram
de US$ 0,10 em produção sem nenhuma checagem reprovar. Estes testes travam: o job
soma todas as chamadas pagas (inclusive a truncada que é refeita), recusa a
próxima quando alcança o limite, e sem orçamento aberto nada muda.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.ai_gateway import AIGatewayError, complete
from app.core.ai_trace import orcamento_do_job
from app.core.config import settings as settings_reais


def _settings(**over):
    s = SimpleNamespace(OPENAI_API_KEY="sk-proj-abc", GEMINI_API_KEY="", ANTHROPIC_API_KEY="",
                        AI_DEFAULT_MODEL="gpt-4o-mini", AI_FALLBACK_MODEL="gemini/gemini-1.5-flash")
    s.AI_MAX_TOKENS = over.get("AI_MAX_TOKENS", 2048)
    s.AI_TEMPERATURE = 0.2
    s.AI_TIMEOUT_SECONDS = 30.0
    s.AI_MAX_RETRIES = 0
    s.AI_RETRY_BACKOFF_SECONDS = 0.0
    s.AI_MAX_COST_PER_JOB_USD = 0.10  # guarda por chamada, inalterada
    s.AI_MAX_TOKENS_CEILING = over.get("AI_MAX_TOKENS_CEILING", 32_768)
    return s


def _resposta(conteudo="ok", fr="stop"):
    choice = SimpleNamespace(message=SimpleNamespace(content=conteudo), finish_reason=fr)
    return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50))


@pytest.fixture
def fake_litellm():
    mock = MagicMock()
    salvo = sys.modules.get("litellm")
    sys.modules["litellm"] = mock
    try:
        yield mock
    finally:
        if salvo is not None:
            sys.modules["litellm"] = salvo
        else:
            sys.modules.pop("litellm", None)


def test_job_soma_chamadas_e_recusa_a_proxima_quando_alcanca_o_teto(fake_litellm):
    fake_litellm.completion.return_value = _resposta()
    fake_litellm.completion_cost.return_value = 0.04  # cada chamada, sozinha, passa na guarda por chamada
    with patch("app.core.config.settings", _settings()), orcamento_do_job(0.10, job_id=7, agente="extrator") as orc:
        for _ in range(3):
            complete("fatia", model="gpt-4o-mini")  # 0,04 → 0,08 → 0,12
        with pytest.raises(AIGatewayError) as exc:
            complete("fatia", model="gpt-4o-mini")
    assert fake_litellm.completion.call_count == 3  # a quarta NÃO saiu
    assert orc["gasto_usd"] == pytest.approx(0.12)
    assert orc["chamadas_pagas"] == 3
    assert "Teto de custo do job atingido" in exc.value.message
    assert exc.value.cost_usd == pytest.approx(0.12)
    assert "job=7" in exc.value.last_error


def test_chamada_truncada_refeita_entra_na_conta(fake_litellm):
    fake_litellm.completion.side_effect = [_resposta("{trunc", fr="length"), _resposta('{"ok": 1}')]
    fake_litellm.completion_cost.return_value = 0.03
    with patch("app.core.config.settings", _settings(AI_MAX_TOKENS_CEILING=8192)), \
            orcamento_do_job(1.0, agente="extrator") as orc:
        r = complete("fatia", model="gpt-4o-mini")
    # A resposta final diz 0,03; o job pagou duas chamadas.
    assert r.cost_usd == pytest.approx(0.03)
    assert orc["chamadas_pagas"] == 2
    assert orc["gasto_usd"] == pytest.approx(0.06)


def test_sem_orcamento_aberto_nada_muda(fake_litellm):
    fake_litellm.completion.return_value = _resposta()
    fake_litellm.completion_cost.return_value = 0.09
    with patch("app.core.config.settings", _settings()):
        for _ in range(3):  # 0,27 no total, sem job: só a guarda por chamada vale
            complete("x", model="gpt-4o-mini")
    assert fake_litellm.completion.call_count == 3


def test_limite_zero_so_conta(fake_litellm):
    fake_litellm.completion.return_value = _resposta()
    fake_litellm.completion_cost.return_value = 0.05
    with patch("app.core.config.settings", _settings()), orcamento_do_job(0, agente="x") as orc:
        for _ in range(4):
            complete("x", model="gpt-4o-mini")
    assert orc["chamadas_pagas"] == 4
    assert orc["gasto_usd"] == pytest.approx(0.20)


def test_custo_desconhecido_e_contado_e_dito(fake_litellm):
    fake_litellm.completion.return_value = _resposta()
    # 1º cálculo: o do orçamento (falha); 2º: o da resposta, pelo gateway.
    fake_litellm.completion_cost.side_effect = [Exception("sem preço"), 0.01]
    with patch("app.core.config.settings", _settings()), orcamento_do_job(1.0, agente="x") as orc:
        complete("x", model="gpt-4o-mini")
    assert orc["chamadas_pagas"] == 1  # desconhecido não é zero: a chamada fica contada
    assert orc["sem_custo"] == 1       # e a falta de preço, dita
    assert orc["gasto_usd"] == 0


@pytest.mark.parametrize("agente,campo", [
    ("extrator", "AI_MAX_COST_PER_JOB_USD_EXTRATOR"),
    ("diagnostico", "AI_MAX_COST_PER_JOB_USD_DIAGNOSTICO"),
    ("legislacao", "AI_MAX_COST_PER_JOB_USD_LEGISLACAO"),
    ("auditor_imovel", "AI_MAX_COST_PER_JOB_USD"),
    (None, "AI_MAX_COST_PER_JOB_USD"),
])
def test_teto_por_agente(agente, campo):
    assert settings_reais.teto_de_custo_por_job(agente) == getattr(settings_reais, campo)


# ---------------------------------------------------------------------------
# ADR-077 — streaming: o timeout mede provedor travado, não geração longa
# ---------------------------------------------------------------------------


def test_stream_pede_usage_e_remonta_a_resposta(fake_litellm):
    pedacos = [object(), object(), object()]
    fake_litellm.completion.return_value = iter(pedacos)
    fake_litellm.stream_chunk_builder.return_value = _resposta('{"ok": 1}')
    fake_litellm.completion_cost.return_value = 0.007
    with patch("app.core.config.settings", _settings()):
        r = complete("ato inteiro", model="gpt-4o-mini", stream=True)
    kwargs = fake_litellm.completion.call_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}  # o custo vem do uso real, não de estimativa
    assert kwargs["timeout"] == 30.0  # o VALOR do timeout não muda
    fake_litellm.stream_chunk_builder.assert_called_once()
    assert list(fake_litellm.stream_chunk_builder.call_args.args[0]) == pedacos  # consumiu o stream inteiro
    assert r.content == '{"ok": 1}'
    assert r.cost_usd == pytest.approx(0.007)


def test_sem_stream_a_chamada_nao_muda(fake_litellm):
    fake_litellm.completion.return_value = _resposta()
    fake_litellm.completion_cost.return_value = 0.001
    with patch("app.core.config.settings", _settings()):
        complete("x", model="gpt-4o-mini")
    assert "stream" not in fake_litellm.completion.call_args.kwargs
    fake_litellm.stream_chunk_builder.assert_not_called()


def test_stream_entra_no_orcamento_do_job(fake_litellm):
    fake_litellm.completion.return_value = iter([object()])
    fake_litellm.stream_chunk_builder.return_value = _resposta()
    fake_litellm.completion_cost.return_value = 0.02
    with patch("app.core.config.settings", _settings()), orcamento_do_job(1.0, agente="extrator") as orc:
        complete("ato", model="gpt-4o-mini", stream=True)
    assert orc["chamadas_pagas"] == 1
    assert orc["gasto_usd"] == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# gpt-6-luna (23/09): recusa max_tokens e exige max_completion_tokens
# ---------------------------------------------------------------------------


class _Recusa(Exception):
    pass


def test_recusa_de_max_tokens_troca_o_parametro_e_o_processo_lembra(fake_litellm):
    from app.core import ai_gateway

    fake_litellm.BadRequestError = _Recusa
    ai_gateway._SO_MAX_COMPLETION_TOKENS.discard("gpt-novo")
    recusa = _Recusa("Unsupported parameter: 'max_tokens' is not supported with this model. "
                     "Use 'max_completion_tokens' instead.")
    fake_litellm.completion.side_effect = [recusa, _resposta(), _resposta()]
    fake_litellm.completion_cost.return_value = 0.001
    with patch("app.core.config.settings", _settings()):
        complete("x", model="gpt-novo")
        complete("y", model="gpt-novo")
    chamadas = [c.kwargs for c in fake_litellm.completion.call_args_list]
    assert "max_tokens" in chamadas[0] and "max_completion_tokens" not in chamadas[0]
    assert "max_completion_tokens" in chamadas[1] and "max_tokens" not in chamadas[1]
    assert "max_completion_tokens" in chamadas[2]  # a segunda chamada já sai certa: sem nova recusa
    ai_gateway._SO_MAX_COMPLETION_TOKENS.discard("gpt-novo")


def test_recusa_que_nao_e_de_parametro_propaga(fake_litellm):
    fake_litellm.BadRequestError = _Recusa
    fake_litellm.completion.side_effect = _Recusa("context length exceeded")
    with patch("app.core.config.settings", _settings()), pytest.raises(AIGatewayError):
        complete("x", model="gpt-outro")
    # Chegou ao provedor uma vez só: recusa que não é de parâmetro não ganha "ajuste".
    assert fake_litellm.completion.call_count == 1
