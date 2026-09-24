"""Request-local attempt recorder. Credentials and provider exception bodies are excluded."""

from contextlib import contextmanager
from contextvars import ContextVar

attempt_sink: ContextVar[list | None] = ContextVar("ai_attempt_sink", default=None)

# Dívida #272: teto de custo ACUMULADO por job. O gateway soma aqui o custo de cada
# chamada paga ao provedor — inclusive a truncada que é refeita, que não aparece na
# resposta final — e recusa a próxima chamada quando o gasto já alcançou o limite.
job_budget: ContextVar[dict | None] = ContextVar("ai_job_budget", default=None)


@contextmanager
def orcamento_do_job(limite_usd: float, *, job_id=None, agente=None):
    """Abre o orçamento de um job; ``limite_usd <= 0`` desliga o teto (só conta)."""
    estado = {"limite_usd": limite_usd, "gasto_usd": 0.0, "chamadas_pagas": 0,
              "sem_custo": 0, "job_id": job_id, "agente": agente}
    token = job_budget.set(estado)
    try:
        yield estado
    finally:
        job_budget.reset(token)


def tracked_completion(completion, *, model, messages, max_tokens, temperature, timeout, api_key, stream=False,
                       token_param="max_tokens"):
    """Uma chamada ao provedor, registrada.

    ``stream=True`` (ADR-077): a resposta chega em pedaços e é remontada aqui. O
    ``timeout`` passa a valer para o provedor TRAVADO — sem nenhum byte por
    ``timeout`` segundos —, não para a geração inteira; uma resposta longa que
    continua chegando não é cortada. O uso de tokens vem no último pedaço
    (``include_usage``), então o custo segue sendo o calculado.
    """
    attempts = attempt_sink.get()
    entry = {"model": model, "provider": model.split("/")[0] if "/" in model else "openai",
             "parameters": {token_param: max_tokens, "temperature": temperature, "timeout": timeout,
                            **({"stream": True} if stream else {})},
             "status": "running"}
    if attempts is not None:
        attempts.append(entry)
    try:
        kwargs = dict(model=model, messages=messages, temperature=temperature, timeout=timeout, api_key=api_key)
        kwargs[token_param] = max_tokens
        if stream:
            kwargs.update(stream=True, stream_options={"include_usage": True})
        response = completion(**kwargs)
        if stream:
            import litellm
            response = litellm.stream_chunk_builder(list(response), messages=messages)
        if attempts is not None:
            import litellm
            entry.update(status="returned", raw=response.choices[0].message.content,
                         finish_reason=response.choices[0].finish_reason)
            try:
                entry["cost_usd"] = litellm.completion_cost(completion_response=response)
            except Exception:
                entry["cost_usd"] = None  # unknown is not zero
        return response
    except Exception as exc:
        entry.update(status="failed", error_type=type(exc).__name__)
        raise
