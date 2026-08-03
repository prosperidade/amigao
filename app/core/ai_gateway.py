"""
AI Gateway — Sprint 5 (Wave 2)

Gateway multi-provider via litellm com:
- Fallback automático entre providers (OpenAI → Gemini → Claude)
- Registro de custo e tokens por chamada
- Timeout e proteção de custo máximo por job
- Modo degradado quando IA não está configurada (retorna None)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    content: str
    model_used: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    provider: str
    # fix/llm-consistencia (2026-06-07): motivo de parada do provider, normalizado.
    # "stop" = resposta completa; "length" = TRUNCADA (estourou max_tokens de saída).
    # Sempre preenchido quando o provider informa; "" quando desconhecido.
    finish_reason: str = ""


@dataclass
class AIGatewayError(Exception):
    message: str
    last_error: Optional[str] = None
    # Sprint -1 B — preserva métricas para auditoria quando o job é bloqueado por cost_exceeded
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    model_used: str = ""


@dataclass
class AITruncationError(AIGatewayError):
    """Resposta do LLM truncada por estouro de max_tokens de saída.

    fix/llm-consistencia (2026-06-07): erro ESPECÍFICO e legível, distinto do
    erro genérico de parse de JSON. O gateway já tentou 1× com max_tokens maior
    antes de levantar isto. Subclasse de AIGatewayError para fail-fast: trocar de
    provider não ajuda (o teto é o mesmo), então não cascateia pra próximo modelo.
    """


def _normalize_finish_reason(raw: object) -> str:
    """Normaliza o finish_reason do provider para vocabulário comum.

    OpenAI/LiteLLM: "stop" | "length" | "content_filter" | "tool_calls".
    Anthropic (via claude_client): "end_turn" | "max_tokens" | "stop_sequence".
    Mapeia qualquer variante de "estourou tokens" para "length".
    """
    s = str(raw or "").strip().lower()
    if s in ("length", "max_tokens", "max_output_tokens", "model_length"):
        return "length"
    return s


@dataclass
class AITranscriptionResponse:
    """Resultado de uma transcrição de áudio (dívida #103 · ADR-060).

    Espelha ``AIResponse`` no que faz sentido para áudio. ``tokens_in/out`` não
    existem em transcrição — o que se cobra é DURAÇÃO —, então o campo que sustenta
    custo e auditoria é ``audio_seconds``.
    """

    text: str
    model_used: str
    provider: str
    cost_usd: float
    duration_ms: int
    audio_seconds: float
    # "provedor" quando a duração veio do próprio retorno da API (custo exato);
    # "estimada" quando foi inferida do tamanho do arquivo (custo aproximado).
    # Nunca colapsar os dois: custo estimado apresentado como medido é auditoria
    # mentindo (Princípio 2).
    duracao_fonte: str = "provedor"


AI_HOURLY_COST_LIMIT_USD = 5.0  # limite padrão por tenant por hora


def check_tenant_cost_limit(
    tenant_id: int,
    db: Session,
    limit_usd: float = AI_HOURLY_COST_LIMIT_USD,
) -> float:
    """Retorna custo acumulado na última hora. Levanta HTTPException se exceder limite."""
    from datetime import UTC, datetime, timedelta

    from fastapi import HTTPException
    from sqlalchemy import func

    from app.models.ai_job import AIJob

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    total_cost = (
        db.query(func.coalesce(func.sum(AIJob.cost_usd), 0.0))
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.created_at >= one_hour_ago,
        )
        .scalar()
    )
    if total_cost >= limit_usd:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de custo de IA excedido: ${total_cost:.2f}/${limit_usd:.2f} na última hora",
        )
    return float(total_cost)


def _month_window_utc() -> tuple[datetime, datetime]:
    """Retorna (início do mês UTC, início do próximo mês UTC)."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_start = start.replace(year=start.year + 1, month=1)
    else:
        next_start = start.replace(month=start.month + 1)
    return start, next_start


def get_tenant_monthly_budget(tenant_id: int, db: Session) -> float:
    """Retorna o teto mensal vigente para o tenant (override > default global)."""
    from app.core.config import settings
    from app.models.tenant import Tenant

    tenant_budget = (
        db.query(Tenant.ai_monthly_budget_usd).filter(Tenant.id == tenant_id).scalar()
    )
    if tenant_budget is not None:
        return float(tenant_budget)
    return float(settings.AI_BUDGET_USD_MONTHLY_PER_TENANT_DEFAULT)


def get_tenant_monthly_spend(tenant_id: int, db: Session) -> float:
    """Retorna custo acumulado de IA do tenant no mês corrente (UTC)."""
    from sqlalchemy import func

    from app.models.ai_job import AIJob

    start, next_start = _month_window_utc()
    total = (
        db.query(func.coalesce(func.sum(AIJob.cost_usd), 0.0))
        .filter(
            AIJob.tenant_id == tenant_id,
            AIJob.created_at >= start,
            AIJob.created_at < next_start,
        )
        .scalar()
    )
    return float(total or 0.0)


def check_tenant_monthly_budget(tenant_id: int, db: Session) -> float:
    """
    Valida o teto mensal de IA do tenant. Retorna o custo acumulado no mês.
    Levanta HTTPException 429 se estourou. limit=0 ⇒ ilimitado.
    """
    from fastapi import HTTPException

    limit = get_tenant_monthly_budget(tenant_id, db)
    if limit <= 0:
        return get_tenant_monthly_spend(tenant_id, db)

    spent = get_tenant_monthly_spend(tenant_id, db)
    if spent >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Orçamento mensal de IA excedido: ${spent:.2f}/${limit:.2f} no mês corrente",
        )
    return spent


def _build_model_list(settings) -> list[tuple[str, str]]:
    """Monta lista de (modelo, api_key) em ordem de preferência baseado nas chaves disponíveis."""
    candidates: list[tuple[str, str, str]] = [
        (settings.OPENAI_API_KEY, settings.AI_DEFAULT_MODEL, settings.OPENAI_API_KEY),
        (settings.GEMINI_API_KEY, settings.AI_FALLBACK_MODEL, settings.GEMINI_API_KEY),
        (settings.ANTHROPIC_API_KEY, "claude-haiku-4-5-20251001", settings.ANTHROPIC_API_KEY),
    ]
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, model, api_key in candidates:
        if key and model not in seen:
            seen.add(model)
            result.append((model, api_key))
    return result or [(settings.AI_DEFAULT_MODEL, "")]


# White label (André 2026-05-28): provider escolhido pelo consultor → prefixo
# LiteLLM correspondente. Os 4 providers suportados (DeepSeek = provider chinês default).
_PROVIDER_LITELLM_PREFIX = {
    "anthropic": "anthropic/",
    "google": "gemini/",
    "openai": "openai/",
    "deepseek": "deepseek/",
}


def _is_auth_error(exc: Exception) -> bool:
    """Heurística para erro de autenticação do provider (chave inválida)."""
    try:
        import litellm  # noqa: PLC0415
        if isinstance(exc, getattr(litellm, "AuthenticationError", ())):
            return True
    except Exception:
        pass
    msg = str(exc).lower()
    return (
        "401" in msg
        or "authentication" in msg
        or "invalid api key" in msg
        or "incorrect api key" in msg
        or "unauthorized" in msg
    )


def _resolve_user_model(user_preferences: Optional[dict]) -> Optional[tuple[str, str]]:
    """Se as prefs do usuário têm provider+model+api_key completos, devolve
    (modelo_litellm, api_key). Caso contrário None (cai no global)."""
    if not user_preferences:
        return None
    provider = (user_preferences.get("provider") or "").strip()
    model = (user_preferences.get("model") or "").strip()
    api_key = (user_preferences.get("api_key") or "").strip()
    if not (provider and model and api_key):
        return None
    prefix = _PROVIDER_LITELLM_PREFIX.get(provider)
    if not prefix:
        return None
    litellm_model = model if model.startswith(prefix) else f"{prefix}{model}"
    return (litellm_model, api_key)


def complete(
    prompt: str,
    *,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    max_cost_override_usd: Optional[float] = None,
    user_preferences: Optional[dict] = None,
    agent_name: Optional[str] = None,
) -> AIResponse:
    """
    Envia um prompt para o LLM e retorna AIResponse.

    Tenta os modelos em ordem de fallback. Lança AIGatewayError se todos falharem.
    Deve ser chamado somente quando settings.ai_configured == True.

    Sprint 0 (2026-04-23): `max_cost_override_usd` permite que agentes com casos
    especiais (ex: legislacao consultando coletâneas grandes via Gemini 1.5 Pro)
    passem um teto maior que `AI_MAX_COST_PER_JOB_USD` global. O override é
    enforcado do mesmo jeito — job acima dele levanta AIGatewayError.
    """
    # Import tardio para evitar erro de import quando IA desabilitada
    import litellm  # noqa: PLC0415

    from app.core.config import settings

    # Erros TRANSITÓRIOS que justificam retry (vs. erro permanente que cai pro
    # próximo provider). Coletados via getattr para tolerar variação de versão
    # do litellm — só entram os que são classes de exceção de fato.
    _transient: tuple[type[BaseException], ...] = tuple(
        e
        for e in (
            getattr(litellm, "Timeout", None),
            getattr(litellm, "APIConnectionError", None),
            getattr(litellm, "ServiceUnavailableError", None),
            getattr(litellm, "InternalServerError", None),
            getattr(litellm, "RateLimitError", None),
        )
        if isinstance(e, type) and issubclass(e, BaseException)
    )

    # White label: se o consultor configurou provider+model+chave, usa SÓ a
    # combinação dele (sem fallback global — não gastar crédito do sistema na
    # conta do consultor). Senão, comportamento atual (override por `model` ou
    # cadeia global de fallback).
    user_resolved = _resolve_user_model(user_preferences)
    if user_resolved:
        models = [user_resolved]
    elif agent_name:
        # fix/llm-consistencia: matriz de equivalência agente×provider. O
        # primário (model=) é preservado em 1º; equivalentes em OUTROS providers
        # DISPONÍVEIS entram como fallback de resiliência (503/timeout). Resolve
        # "legislação refém do Gemini" e o BYOK de provider único.
        from app.core.model_matrix import resolve_agent_models  # noqa: PLC0415
        models = resolve_agent_models(agent_name, settings, primary_model=model)
    elif model:
        models = [(model, "")]
    else:
        models = _build_model_list(settings)
    user_scoped = user_resolved is not None
    _max_tokens = max_tokens or settings.AI_MAX_TOKENS
    # Teto absoluto para o retry de truncamento (nunca abaixo do pedido).
    _ceiling = max(_max_tokens, getattr(settings, "AI_MAX_TOKENS_CEILING", 32_768))
    _temperature = temperature if temperature is not None else settings.AI_TEMPERATURE
    # `or 30.0`: blindagem contra timeout None/0 chegando ao litellm — a
    # mensagem "Connection timed out after None seconds" prova que sem timeout
    # explícito o provider pendura indefinidamente.
    _timeout = settings.AI_TIMEOUT_SECONDS or 30.0
    _max_retries = max(0, settings.AI_MAX_RETRIES)
    _backoff_base = settings.AI_RETRY_BACKOFF_SECONDS

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Optional[str] = None
    for attempt_model, api_key in models:
        try:
            t0 = time.monotonic()

            def _attempt_completion(mt: int, _model: str, _api_key: str):
                """1 chamada ao provider com retry SÓ para erros transitórios.

                Crítico para a legislação/diagnóstico (model= explícito): sem isto
                um único Timeout/503 derruba a consulta. Erro permanente (auth,
                schema) propaga na hora pro fallback de provider.
                """
                resp = None
                for _attempt in range(_max_retries + 1):
                    try:
                        resp = litellm.completion(
                            model=_model,
                            messages=messages,
                            max_tokens=mt,
                            temperature=_temperature,
                            timeout=_timeout,
                            api_key=_api_key or None,
                        )
                        break
                    except _transient as transient_exc:
                        if _attempt >= _max_retries:
                            raise
                        backoff = _backoff_base * (2 ** _attempt)
                        logger.warning(
                            "ai_gateway.complete transient error model=%s attempt=%d/%d "
                            "err=%s; retry em %.1fs",
                            _model, _attempt + 1, _max_retries + 1,
                            transient_exc, backoff,
                        )
                        time.sleep(backoff)
                assert resp is not None  # loop sai por break (sucesso) ou raise
                return resp

            # fix/llm-consistencia: trata TRUNCAMENTO (finish_reason=length).
            # 1 retry automático com max_tokens dobrado (até o teto). Se ainda
            # truncar, levanta erro ESPECÍFICO e legível — NÃO tenta parse parcial
            # nem cascateia pra outro provider (o teto seria o mesmo).
            _mt = _max_tokens
            response = None
            finish_reason = ""
            while True:
                response = _attempt_completion(_mt, attempt_model, api_key)
                finish_reason = _normalize_finish_reason(
                    getattr(response.choices[0], "finish_reason", None)
                )
                if finish_reason != "length":
                    break
                _u = response.usage or {}
                bumped = min(_mt * 2, _ceiling)
                if bumped > _mt:
                    logger.warning(
                        "ai_gateway.complete TRUNCADO model=%s max_tokens=%d "
                        "tokens_out=%s; retry com max_tokens=%d",
                        attempt_model, _mt,
                        getattr(_u, "completion_tokens", "?"), bumped,
                    )
                    _mt = bumped
                    continue
                _t_in = getattr(_u, "prompt_tokens", 0) or 0
                _t_out = getattr(_u, "completion_tokens", 0) or 0
                logger.error(
                    "ai_gateway.complete resposta truncada (limite de tokens) "
                    "model=%s max_tokens=%d tokens_in=%d tokens_out=%d",
                    attempt_model, _mt, _t_in, _t_out,
                )
                raise AITruncationError(
                    message=(
                        "resposta truncada (limite de tokens): o modelo atingiu "
                        f"max_tokens={_mt} sem fechar a resposta. Aumente o teto "
                        "de saída do agente."
                    ),
                    last_error=f"finish_reason=length model={attempt_model}",
                    tokens_in=_t_in,
                    tokens_out=_t_out,
                    model_used=attempt_model,
                )

            elapsed_ms = int((time.monotonic() - t0) * 1000)

            content = response.choices[0].message.content or ""
            usage = response.usage or {}
            tokens_in = getattr(usage, "prompt_tokens", 0) or 0
            tokens_out = getattr(usage, "completion_tokens", 0) or 0

            # litellm calcula custo automaticamente quando disponível
            try:
                cost = litellm.completion_cost(completion_response=response) or 0.0
            except Exception:
                cost = 0.0

            provider = attempt_model.split("/")[0] if "/" in attempt_model else attempt_model.split("-")[0]

            # Sprint -1 B — teto de custo por job.
            # Só enforcado quando o provider informa custo (>0). Provider sem tabela de preço
            # retorna 0.0 e o guardrail não dispara — custo real é monitorado pelos limites
            # horário e mensal por tenant.
            # Sprint 0 — override por chamada permite budgets maiores para casos específicos
            # (ex: legislacao com Gemini 1.5 Pro em coletâneas grandes).
            max_per_job = (
                max_cost_override_usd
                if max_cost_override_usd is not None
                else settings.AI_MAX_COST_PER_JOB_USD
            )
            if cost > 0 and max_per_job > 0 and cost > max_per_job:
                logger.error(
                    "ai_gateway.complete cost exceeded max per job: "
                    "cost=%.4f max=%.4f model=%s tokens_in=%d tokens_out=%d",
                    cost, max_per_job, attempt_model, tokens_in, tokens_out,
                )
                raise AIGatewayError(
                    message=f"Job cost ${cost:.4f} exceeded max ${max_per_job:.4f}",
                    last_error=f"cost_exceeded model={attempt_model}",
                    cost_usd=cost,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    model_used=attempt_model,
                )

            logger.info(
                "ai_gateway.complete model=%s tokens_in=%d tokens_out=%d cost_usd=%.6f ms=%d",
                attempt_model, tokens_in, tokens_out, cost, elapsed_ms,
            )

            return AIResponse(
                content=content,
                model_used=attempt_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                duration_ms=elapsed_ms,
                provider=provider,
                finish_reason=finish_reason,
            )

        except AIGatewayError:
            # Sprint -1 B — cost_exceeded deve fail-fast; não cair pra próximo provider
            # porque o próximo pode custar o mesmo e o risco financeiro se acumula.
            raise
        except Exception as exc:
            last_error = str(exc)
            # White label: falha de AUTH com a chave do consultor NÃO cai no
            # fallback global (proibido gastar crédito do sistema). Erro claro.
            if user_scoped and _is_auth_error(exc):
                logger.warning("ai_gateway.complete user-scoped auth error model=%s", attempt_model)
                raise AIGatewayError(
                    message="Credenciais de IA do consultor inválidas; revise em Configurações > IA",
                    last_error=last_error,
                )
            logger.warning("ai_gateway.complete fallback model=%s error=%s", attempt_model, exc)
            continue

    raise AIGatewayError(
        message=f"Todos os providers falharam. Último erro: {last_error}",
        last_error=last_error,
    )


# ----------------------------------------------------------------------
# Transcrição de áudio (dívida #103 · ADR-060)
# ----------------------------------------------------------------------

# Bitrate assumido quando o provedor não devolve a duração do áudio. 64 kbps mono
# é o perfil típico de gravador de celular / nota de voz — a estimativa erra para
# mais em WAV (não comprimido) e para menos em áudio de alta qualidade. Só serve
# para NÃO registrar custo 0.0 num job que gastou; quem consome a estimativa é
# avisado por `duracao_fonte="estimada"`.
_BITRATE_ASSUMIDO_BPS = 64_000


def _resolve_transcription_key(settings, user_preferences: Optional[dict]) -> tuple[str, bool]:
    """Devolve (api_key, é_chave_do_consultor) para a transcrição.

    BYOK: se o consultor configurou OpenAI com chave própria, transcrever na conta
    dele. Providers que não fazem transcrição (Gemini/Anthropic/DeepSeek) NÃO caem
    silenciosamente na chave do sistema — devolvem a chave global só se ela existir,
    e o chamador recebe erro explícito quando não existe.
    """
    prefs = user_preferences or {}
    if (prefs.get("provider") or "").strip() == "openai" and (prefs.get("api_key") or "").strip():
        return prefs["api_key"].strip(), True
    return (settings.OPENAI_API_KEY or ""), False


def transcribe(
    audio_bytes: bytes,
    *,
    filename: str,
    model: Optional[str] = None,
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    max_cost_override_usd: Optional[float] = None,
    user_preferences: Optional[dict] = None,
) -> AITranscriptionResponse:
    """Transcreve áudio via litellm (Whisper por default), na MESMA camada dos
    demais modelos — nenhum serviço fala com provedor direto e nenhuma chave nova
    entra em código (tudo vem de settings/BYOK).

    Diferente de ``complete()``, aqui **não há cadeia de fallback entre providers**:
    dos quatro providers suportados só a OpenAI expõe endpoint de transcrição. Sem
    chave OpenAI a função levanta ``AIGatewayError`` com mensagem acionável, em vez
    de tentar um Gemini que recusaria o formato da requisição.

    Custo é calculado por DURAÇÃO (o litellm não precifica transcrição): duração
    real quando o provedor devolve ``duration`` no ``verbose_json``, estimada pelo
    tamanho do arquivo quando não devolve — e a diferença viaja em ``duracao_fonte``.
    """
    import io  # noqa: PLC0415

    import litellm  # noqa: PLC0415

    from app.core.config import settings  # noqa: PLC0415

    if not audio_bytes:
        raise AIGatewayError(message="Áudio vazio — nada a transcrever.")

    api_key, user_scoped = _resolve_transcription_key(settings, user_preferences)
    if not api_key:
        raise AIGatewayError(
            message=(
                "Transcrição de áudio exige chave OpenAI (é o único provedor "
                "suportado hoje). Configure OPENAI_API_KEY ou a chave OpenAI do "
                "consultor em Configurações > IA."
            ),
            last_error="sem_chave_openai",
        )

    _model = model or settings.AUDIO_TRANSCRIPTION_MODEL
    _language = language if language is not None else (settings.AUDIO_TRANSCRIPTION_LANGUAGE or None)
    _timeout = settings.AUDIO_TRANSCRIPTION_TIMEOUT_SECONDS or 300.0

    # O SDK identifica o formato pelo NOME do arquivo — um BytesIO sem `.name`
    # chega como `application/octet-stream` e é recusado. Daí o buffer nomeado.
    buffer = io.BytesIO(audio_bytes)
    buffer.name = filename or "audio.mp3"

    t0 = time.monotonic()
    try:
        kwargs: dict = {
            "model": _model,
            "file": buffer,
            "api_key": api_key,
            "timeout": _timeout,
            # verbose_json traz `duration` — é o que torna o custo MEDIDO em vez
            # de estimado. Provedor que ignore o formato cai na estimativa.
            "response_format": "verbose_json",
        }
        if _language:
            kwargs["language"] = _language
        if prompt:
            kwargs["prompt"] = prompt
        response = litellm.transcription(**kwargs)
    except Exception as exc:
        if user_scoped and _is_auth_error(exc):
            raise AIGatewayError(
                message="Credenciais de IA do consultor inválidas; revise em Configurações > IA",
                last_error=str(exc),
            ) from exc
        logger.warning("ai_gateway.transcribe falhou model=%s error=%s", _model, exc)
        raise AIGatewayError(
            message=f"Falha na transcrição de áudio: {exc}",
            last_error=str(exc),
            model_used=_model,
        ) from exc

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    text = (getattr(response, "text", None) or "").strip()
    raw_duration = getattr(response, "duration", None)
    if raw_duration is None and isinstance(response, dict):
        raw_duration = response.get("duration")
    try:
        audio_seconds = float(raw_duration) if raw_duration is not None else 0.0
    except (TypeError, ValueError):
        audio_seconds = 0.0

    duracao_fonte = "provedor"
    if audio_seconds <= 0:
        audio_seconds = (len(audio_bytes) * 8) / _BITRATE_ASSUMIDO_BPS
        duracao_fonte = "estimada"
        logger.info(
            "ai_gateway.transcribe provedor não devolveu duração — estimando "
            "%.1fs a partir de %d bytes", audio_seconds, len(audio_bytes),
        )

    cost = (audio_seconds / 60.0) * float(settings.AUDIO_TRANSCRIPTION_USD_PER_MINUTE)

    max_per_job = (
        max_cost_override_usd
        if max_cost_override_usd is not None
        else settings.AI_MAX_COST_PER_JOB_USD_TRANSCRICAO
    )
    if max_per_job > 0 and cost > max_per_job:
        logger.error(
            "ai_gateway.transcribe cost exceeded max per job: cost=%.4f max=%.4f "
            "audio_s=%.1f model=%s",
            cost, max_per_job, audio_seconds, _model,
        )
        raise AIGatewayError(
            message=(
                f"Áudio longo demais para o teto de custo: ${cost:.4f} passa de "
                f"${max_per_job:.4f}. Divida a gravação ou aumente o teto."
            ),
            last_error=f"cost_exceeded model={_model}",
            cost_usd=cost,
            model_used=_model,
        )

    provider = _model.split("/")[0] if "/" in _model else "openai"

    logger.info(
        "ai_gateway.transcribe model=%s chars=%d audio_s=%.1f (%s) cost_usd=%.6f ms=%d",
        _model, len(text), audio_seconds, duracao_fonte, cost, elapsed_ms,
    )

    return AITranscriptionResponse(
        text=text,
        model_used=_model,
        provider=provider,
        cost_usd=cost,
        duration_ms=elapsed_ms,
        audio_seconds=audio_seconds,
        duracao_fonte=duracao_fonte,
    )
