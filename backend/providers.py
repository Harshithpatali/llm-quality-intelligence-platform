import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from . import config


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_type: str = "provider_error",
        retryable: bool = False,
        status_code: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after = retry_after


RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def _retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After as delta-seconds or an HTTP date."""
    if not value:
        return None
    try:
        return max(0.0, min(float(value), 30.0))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, min((retry_at - datetime.now(timezone.utc)).total_seconds(), 30.0))
        except (TypeError, ValueError, OverflowError):
            return None


def _request_url(provider: str) -> str:
    if provider == "groq":
        return "https://api.groq.com/openai/v1/chat/completions"
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1/chat/completions"
    raise ProviderError(f"Unsupported provider: {provider}", error_type="unsupported_provider")


def estimate_cost_usd(
    provider: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    if prompt_tokens is None and completion_tokens is None:
        return None
    pricing = config.MODEL_PRICING_USD_PER_MILLION.get(f"{provider}/{model}")
    if not isinstance(pricing, dict):
        return None
    input_cost = float(pricing.get("input", 0)) * float(prompt_tokens or 0) / 1_000_000
    output_cost = float(pricing.get("output", 0)) * float(completion_tokens or 0) / 1_000_000
    return round(input_cost + output_cost, 8)


def _post(
    url: str,
    key: str,
    model: str,
    prompt: str,
    *,
    timeout: int = 60,
    response_format: dict[str, Any] | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    if not key:
        raise ProviderError("API key is not configured.", error_type="missing_api_key")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    start = time.perf_counter()
    last_error: ProviderError | None = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.Timeout:
            last_error = ProviderError(
                f"Provider request timed out after {timeout}s.",
                error_type="timeout",
                retryable=True,
            )
        except requests.ConnectionError as exc:
            last_error = ProviderError(
                f"Provider connection failed: {exc}",
                error_type="connection_error",
                retryable=True,
            )
        except requests.RequestException as exc:
            last_error = ProviderError(
                f"Provider request failed: {exc}",
                error_type="request_error",
            )
        else:
            if response.status_code >= 400:
                last_error = ProviderError(
                    f"Provider returned HTTP {response.status_code}: {response.text[:500]}",
                    error_type="rate_limited" if response.status_code == 429 else "provider_http_error",
                    retryable=response.status_code in RETRYABLE_STATUS_CODES,
                    status_code=response.status_code,
                    retry_after=_retry_after_seconds(response.headers.get("Retry-After")),
                )
            else:
                try:
                    data = response.json()
                    message = data["choices"][0]["message"]
                    text = message.get("content") or ""
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    last_error = ProviderError(
                        f"Unexpected provider response: {exc}",
                        error_type="invalid_provider_response",
                    )
                else:
                    usage = data.get("usage") or {}
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    return {
                        "response": text,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": usage.get("total_tokens"),
                        },
                        "attempts": attempt + 1,
                    }

        if last_error is None or not last_error.retryable or attempt >= max_retries:
            break
        delay = last_error.retry_after
        if delay is None:
            delay = min(2 ** attempt, 8)
        time.sleep(delay)

    assert last_error is not None
    raise last_error


def call_provider(
    provider: str,
    model: str,
    prompt: str,
    *,
    response_format: dict[str, Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    key = config.GROQ_API_KEY if provider == "groq" else config.OPENROUTER_API_KEY
    result = _post(
        _request_url(provider), key, model, prompt,
        response_format=response_format, timeout=timeout,
    )
    result["estimated_cost_usd"] = estimate_cost_usd(
        provider, model, result.get("prompt_tokens"), result.get("completion_tokens")
    )
    return result


def configured_models(providers: list[str]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    if "groq" in providers:
        models.extend({"provider": "groq", "model": model} for model in config.GROQ_MODELS)
    if "openrouter" in providers:
        models.extend({"provider": "openrouter", "model": model} for model in config.OPENROUTER_MODELS)

    seen: set[tuple[str, str]] = set()
    unique = []
    for item in models:
        identity = (item["provider"], item["model"])
        if identity not in seen:
            seen.add(identity)
            unique.append(item)
    return unique
