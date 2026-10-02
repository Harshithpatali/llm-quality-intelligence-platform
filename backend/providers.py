import time
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
    ):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.status_code = status_code


RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def _request_url(provider: str) -> str:
    if provider == "groq":
        return "https://api.groq.com/openai/v1/chat/completions"
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1/chat/completions"
    raise ProviderError(
        f"Unsupported provider: {provider}",
        error_type="unsupported_provider",
    )


def estimate_cost_usd(
    provider: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    if prompt_tokens is None and completion_tokens is None:
        return None
    key = f"{provider}/{model}"
    pricing = config.MODEL_PRICING_USD_PER_MILLION.get(key)
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
        raise ProviderError(
            "API key is not configured.",
            error_type="missing_api_key",
        )

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    start = time.perf_counter()

    last_error: ProviderError | None = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.Timeout as exc:
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
            status_code = response.status_code
            if status_code >= 400:
                body = response.text[:500]
                retryable = status_code in RETRYABLE_STATUS_CODES
                last_error = ProviderError(
                    f"Provider returned HTTP {status_code}: {body}",
                    error_type="rate_limited" if status_code == 429 else "provider_http_error",
                    retryable=retryable,
                    status_code=status_code,
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
                        "estimated_cost_usd": estimate_cost_usd(
                            "",
                            "",
                            None,
                            None,
                        ),
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": usage.get("total_tokens"),
                        },
                        "attempts": attempt + 1,
                    }

        if last_error is None or not last_error.retryable or attempt >= max_retries:
            break
        time.sleep(min(2 ** attempt, 8))

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
        _request_url(provider),
        key,
        model,
        prompt,
        timeout=timeout,
        response_format=response_format,
    )
    result["estimated_cost_usd"] = estimate_cost_usd(
        provider,
        model,
        result.get("prompt_tokens"),
        result.get("completion_tokens"),
    )
    return result


def configured_models(providers: list[str]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []

    if "groq" in providers:
        for model in config.GROQ_MODELS:
            models.append({"provider": "groq", "model": model})

    if "openrouter" in providers:
        for model in config.OPENROUTER_MODELS:
            models.append({"provider": "openrouter", "model": model})

    # Keep configuration deterministic and avoid duplicate provider/model pairs.
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in models:
        key = (item["provider"], item["model"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
