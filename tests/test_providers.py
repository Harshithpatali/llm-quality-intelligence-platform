from backend.providers import configured_models, estimate_cost_usd


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
