from unittest.mock import Mock

import pytest

from backend.providers import ProviderError, _post, configured_models, estimate_cost_usd


def test_default_configuration_exposes_three_distinct_generation_models():
    rows = configured_models(["groq", "openrouter"])
    assert len(rows) == 3
    assert len({(row["provider"], row["model"]) for row in rows}) == 3
    assert {row["model"] for row in rows} == {
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "deepseek/deepseek-v4-flash-0731",
    }


def test_cost_estimate_is_explicit():
    value = estimate_cost_usd(
        "groq",
        "openai/gpt-oss-20b",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    assert value == 0.000375


def test_post_returns_usage_without_placeholder_cost(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {
        "choices": [{"message": {"content": "answer"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
    }
    monkeypatch.setattr("backend.providers.requests.post", lambda *a, **k: response)
    result = _post("https://example.test", "secret", "model", "prompt")
    assert result["response"] == "answer"
    assert result["prompt_tokens"] == 12
    assert "estimated_cost_usd" not in result


def test_post_honors_retry_after_header(monkeypatch):
    responses = [
        Mock(status_code=429, text="rate limited", headers={"Retry-After": "3"}),
        Mock(status_code=200),
    ]
    responses[1].json.return_value = {
        "choices": [{"message": {"content": "recovered"}}],
        "usage": {},
    }
    waits = []
    monkeypatch.setattr("backend.providers.requests.post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr("backend.providers.time.sleep", waits.append)
    result = _post("https://example.test", "secret", "model", "prompt", max_retries=1)
    assert result["response"] == "recovered"
    assert waits == [3.0]


def test_post_does_not_retry_non_retryable_errors(monkeypatch):
    response = Mock(status_code=400, text="bad request", headers={})
    monkeypatch.setattr("backend.providers.requests.post", lambda *a, **k: response)
    with pytest.raises(ProviderError) as error:
        _post("https://example.test", "secret", "model", "prompt", max_retries=3)
    assert error.value.status_code == 400
    assert error.value.retryable is False
