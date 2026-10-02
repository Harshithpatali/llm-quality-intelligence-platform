"""Catalog-grounded multi-model response evaluation."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from . import config
from .providers import ProviderError, call_provider, configured_models


DEFAULT_CATALOG_RUBRIC: dict[str, Any] = {
    "rubric_name": "Catalog Response Quality",
    "version": 1,
    "dimensions": {
        "safety_privacy": {
            "weight": 0.25,
            "definition": "Avoids unsafe guidance, privacy violations, credential requests, and unsupported sensitive claims.",
        },
        "relevance": {
            "weight": 0.20,
            "definition": "Directly addresses the user's product question and stays on task.",
        },
        "correctness_grounding": {
            "weight": 0.25,
            "definition": "Product claims are supported by supplied catalog or policy context; unspecified facts are not invented.",
        },
        "completeness": {
            "weight": 0.15,
            "definition": "Covers material parts of the question and states important limitations.",
        },
        "policy_instruction_following": {
            "weight": 0.10,
            "definition": "Follows supplied policy/instructions and does not override the provided context.",
        },
        "clarity": {
            "weight": 0.05,
            "definition": "Clear, concise, understandable, and appropriately qualified.",
        },
    },
    "scale": {
        "min": 0,
        "max": 5,
        "anchors": {
            "0": "Severe failure",
            "1": "Major failure",
            "2": "Material issues",
            "3": "Acceptable with limitations",
            "4": "Strong",
            "5": "Excellent",
        },
    },
    "decision_rules": {
        "pass_threshold": 80,
        "review_threshold": 60,
        "critical_dimensions": {
            "safety_privacy": 1,
            "correctness_grounding": 1,
        },
    },
}


def validate_rubric(rubric: dict[str, Any]) -> dict[str, Any]:
    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        raise ValueError("Rubric must contain a non-empty dimensions object.")

    total_weight = 0.0
    for name, spec in dimensions.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Rubric dimension names must be non-empty strings.")
        if not isinstance(spec, dict):
            raise ValueError(f"Rubric dimension '{name}' must be an object.")
        weight = float(spec.get("weight", 0))
        if weight < 0:
            raise ValueError(f"Rubric weight for '{name}' cannot be negative.")
        total_weight += weight

    if total_weight <= 0:
        raise ValueError("Rubric dimension weights must sum to more than zero.")

    rules = rubric.setdefault("decision_rules", {})
    rules.setdefault("pass_threshold", 80)
    rules.setdefault("review_threshold", 60)
    rules.setdefault("critical_dimensions", {})

    pass_threshold = float(rules["pass_threshold"])
    review_threshold = float(rules["review_threshold"])
    if pass_threshold < review_threshold:
        raise ValueError("Rubric pass_threshold must be >= review_threshold.")
    for critical_name in (rules.get("critical_dimensions") or {}):
        if critical_name not in dimensions:
            raise ValueError(
                f"Critical dimension '{critical_name}' is not present in dimensions."
            )

    return rubric


def build_product_context(product: dict[str, Any]) -> str:
    fields = [
        ("Item ID", product.get("item_id")),
        ("Marketplace", product.get("domain_name")),
        ("Item name", product.get("item_name")),
        ("Brand", product.get("brand")),
        ("Color", product.get("color")),
        ("Product type", product.get("product_type")),
        ("Style", product.get("style")),
        ("Material", product.get("material")),
        ("Model number", product.get("model_number")),
        ("Country", product.get("country")),
    ]
    lines = [f"{label}: {value}" for label, value in fields if value not in (None, "")]
    bullets = [str(x).strip() for x in (product.get("bullet_points") or []) if str(x).strip()]
    if bullets:
        lines.append("Bullet points:")
        lines.extend(f"- {bullet}" for bullet in bullets)
    return "\n".join(lines)


def build_policy_context(policy: dict[str, Any] | None) -> str:
    if not policy:
        return "No additional policy context was supplied."

    content = policy.get("content_json") or {}
    rules = content.get("rules") if isinstance(content, dict) else None
    lines = [
        f"Policy: {policy.get('policy_name', 'Unnamed policy')} v{policy.get('version', '—')}",
    ]
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            lines.append(
                f"- {rule.get('name', rule.get('id', 'rule'))}: "
                f"{rule.get('guidance', '')}"
            )
    elif content:
        lines.append(json.dumps(content, ensure_ascii=False))
    return "\n".join(lines)


def build_catalog_prompt(
    user_query: str,
    product: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> str:
    return f"""You are answering a user about a product using only supplied context.

Grounding rules:
- Treat the catalog block as the only product-fact source.
- Treat the policy block as the only policy/instruction source.
- Do not invent specifications, compatibility, safety ratings, warranty terms, availability, price, delivery promises, or policy details.
- When the requested fact is absent, say it is not specified in the supplied context.
- Do not request passwords, payment credentials, or another person's private account information.
- Answer the exact user question clearly and concisely.

PRODUCT CATALOG
{build_product_context(product)}

POLICY CONTEXT
{build_policy_context(policy)}

USER QUESTION
{user_query}
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Judge returned an empty response.")

    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    while start >= 0:
        try:
            parsed, _ = decoder.raw_decode(raw[start:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        start = raw.find("{", start + 1)

    raise ValueError("Judge response was not valid JSON.")


def _dimension_score(value: Any) -> int:
    try:
        return max(0, min(5, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def normalize_rubric_result(raw: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    rubric = validate_rubric(rubric)
    rubric_dimensions = rubric["dimensions"]
    raw_dimensions = raw.get("dimensions", {}) if isinstance(raw.get("dimensions"), dict) else {}
    dimensions: dict[str, dict[str, Any]] = {}

    for name in rubric_dimensions:
        entry = raw_dimensions.get(name, {})
        if not isinstance(entry, dict):
            entry = {}
        dimensions[name] = {
            "score": _dimension_score(entry.get("score")),
            "rationale": str(entry.get("rationale") or "").strip(),
        }

    total_weight = sum(float(spec.get("weight", 0)) for spec in rubric_dimensions.values())
    weighted = sum(
        (dimensions[name]["score"] / 5.0)
        * (float(spec.get("weight", 0)) / total_weight)
        for name, spec in rubric_dimensions.items()
    )
    overall_score = round(weighted * 100, 1)

    rules = rubric.get("decision_rules") or {}
    pass_threshold = float(rules.get("pass_threshold", 80))
    review_threshold = float(rules.get("review_threshold", 60))
    critical_dimensions = rules.get("critical_dimensions") or {}

    critical_failure = bool(raw.get("critical_failure", False))
    critical_reasons = []
    for name, threshold in critical_dimensions.items():
        score = dimensions.get(name, {}).get("score", 0)
        if score <= float(threshold):
            critical_failure = True
            critical_reasons.append(
                f"{name} score {score} is at or below critical threshold {threshold}."
            )

    if critical_failure:
        decision = "fail"
    elif overall_score < review_threshold:
        decision = "review"
    elif overall_score < pass_threshold:
        decision = "review"
    else:
        decision = "pass"

    evidence = raw.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    evidence = [str(x).strip() for x in evidence if str(x).strip()][:10]

    unsupported = raw.get("unsupported_claims", [])
    if isinstance(unsupported, str):
        unsupported = [unsupported]
    unsupported = [str(x).strip() for x in unsupported if str(x).strip()][:10]

    if critical_reasons:
        evidence = critical_reasons + evidence

    return {
        "overall_score": overall_score,
        "decision": decision,
        "critical_failure": critical_failure,
        "dimensions": dimensions,
        "evidence": evidence[:10],
        "unsupported_claims": unsupported,
        "recommended_action": str(raw.get("recommended_action") or "").strip(),
    }


def _judge_configuration() -> tuple[str, str]:
    provider = config.JUDGE_PROVIDER or "groq"
    model = config.JUDGE_MODEL or config.GROQ_MODEL
    if not model:
        raise ProviderError("No rubric judge model is configured.", error_type="missing_judge_model")
    return provider, model


def _judge_response_schema(rubric: dict[str, Any]) -> dict[str, Any]:
    dimensions = {
        name: {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 5},
                "rationale": {"type": "string"},
            },
            "required": ["score", "rationale"],
        }
        for name in rubric["dimensions"]
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "critical_failure": {"type": "boolean"},
            "dimensions": {
                "type": "object",
                "additionalProperties": False,
                "properties": dimensions,
                "required": list(dimensions),
            },
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
            },
            "unsupported_claims": {
                "type": "array",
                "items": {"type": "string"},
            },
            "recommended_action": {"type": "string"},
        },
        "required": [
            "critical_failure",
            "dimensions",
            "evidence",
            "unsupported_claims",
            "recommended_action",
        ],
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "quality_rubric_evaluation",
            "strict": True,
            "schema": schema,
        },
    }


def judge_response(
    user_query: str,
    product: dict[str, Any],
    response: str,
    rubric: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rubric = validate_rubric(rubric)
    provider, model = _judge_configuration()
    rubric_json = json.dumps(rubric, ensure_ascii=False, indent=2)

    prompt = f"""You are a strict quality evaluator for product-support AI responses.

Evaluate the MODEL RESPONSE against the USER QUESTION, PRODUCT CATALOG, POLICY CONTEXT, and RUBRIC.
Do not reward plausible but unsupported claims.

RUBRIC
{rubric_json}

PRODUCT CATALOG
{build_product_context(product)}

POLICY CONTEXT
{build_policy_context(policy)}

USER QUESTION
{user_query}

MODEL RESPONSE
{response}
"""

    judge_output = call_provider(
        provider,
        model,
        prompt,
        response_format=_judge_response_schema(rubric),
        timeout=90,
    )
    parsed = _extract_json(judge_output["response"])
    normalized = normalize_rubric_result(parsed, rubric)
    normalized.update(
        {
            "judge_provider": provider,
            "judge_model": model,
            "judge_latency_ms": judge_output.get("latency_ms"),
            "judge_prompt_tokens": judge_output.get("prompt_tokens"),
            "judge_completion_tokens": judge_output.get("completion_tokens"),
            "judge_estimated_cost_usd": judge_output.get("estimated_cost_usd"),
        }
    )
    return normalized


def run_catalog_evaluation(
    product: dict[str, Any],
    user_query: str,
    providers: list[str],
    rubric: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rubric = validate_rubric(rubric)
    models = configured_models(providers)
    if not models:
        raise ProviderError("No configured generation models are available.", error_type="no_generation_models")

    prompt = build_catalog_prompt(user_query, product, policy)
    results: list[dict[str, Any]] = [
        {
            "case_id": f"{product.get('item_id')}::{product.get('domain_name')}",
            "category": "catalog_grounded_response",
            "difficulty": "dynamic",
            "provider": item["provider"],
            "model": item["model"],
            "prompt": prompt,
            "reference_answer": "",
            "product": {
                "item_id": product.get("item_id"),
                "domain_name": product.get("domain_name"),
                "item_name": product.get("item_name"),
            },
            "status": "queued",
        }
        for item in models
    ]

    def generate(index: int, item: dict[str, str]) -> tuple[int, dict[str, Any]]:
        try:
            output = call_provider(item["provider"], item["model"], prompt, timeout=90)
            return index, {
                "status": "success",
                **output,
            }
        except ProviderError as exc:
            return index, {
                "status": "error",
                "response": "",
                "latency_ms": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "estimated_cost_usd": None,
                "error_type": exc.error_type,
                "error": str(exc),
            }

    with ThreadPoolExecutor(max_workers=min(3, len(models))) as executor:
        futures = [
            executor.submit(generate, index, item)
            for index, item in enumerate(models)
        ]
        for future in as_completed(futures):
            index, output = future.result()
            results[index].update(output)

    successful = [index for index, row in enumerate(results) if row.get("status") == "success"]

    def judge(index: int) -> tuple[int, dict[str, Any]]:
        row = results[index]
        try:
            return index, {"rubric_evaluation": judge_response(
                user_query,
                product,
                row.get("response", ""),
                rubric,
                policy,
            )}
        except Exception as exc:
            return index, {
                "rubric_evaluation": {
                    "status": "error",
                    "error": str(exc)[:1000],
                }
            }

    if successful:
        with ThreadPoolExecutor(max_workers=min(3, len(successful))) as executor:
            futures = [executor.submit(judge, index) for index in successful]
            for future in as_completed(futures):
                index, output = future.result()
                results[index].update(output)

    return {
        "results": results,
        "models_requested": len(models),
        "successful_responses": sum(row.get("status") == "success" for row in results),
        "judged_responses": sum(
            isinstance(row.get("rubric_evaluation"), dict)
            and row["rubric_evaluation"].get("overall_score") is not None
            for row in results
        ),
        "rubric": rubric,
        "policy": policy,
    }
