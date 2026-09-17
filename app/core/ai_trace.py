"""Request-local attempt recorder. Credentials and provider exception bodies are excluded."""

from contextvars import ContextVar

attempt_sink: ContextVar[list | None] = ContextVar("ai_attempt_sink", default=None)


def tracked_completion(completion, *, model, messages, max_tokens, temperature, timeout, api_key):
    attempts = attempt_sink.get()
    entry = {"model": model, "provider": model.split("/")[0] if "/" in model else "openai",
             "parameters": {"max_tokens": max_tokens, "temperature": temperature, "timeout": timeout},
             "status": "running"}
    if attempts is not None:
        attempts.append(entry)
    try:
        response = completion(model=model, messages=messages, max_tokens=max_tokens,
                              temperature=temperature, timeout=timeout, api_key=api_key)
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
