"""Catalog-grounded multi-model response evaluation.

This module keeps catalog retrieval separate from judging. The supplied Amazon item-list
metadata is treated as grounding context, not as a source of internal Amazon policies.
"""

from __future__ import annotations

import json
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
            "definition": "Product claims are supported by the supplied catalog metadata; unspecified facts are not invented.",
        },
        "completeness": {
            "weight": 0.15,
            "definition": "Covers the material parts of the question and clearly states important limitations or missing information.",
        },
        "policy_instruction_following": {
            "weight": 0.10,
            "definition": "Follows the evaluation instructions and does not override the supplied product context.",
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
}


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


def build_catalog_prompt(user_query: str, product: dict[str, Any]) -> str:
    return f"""You are answering a user about a product using only the supplied catalog metadata.

Grounding rules:
- Treat the catalog block as the only product-fact source.
- Do not invent specifications, compatibility, safety ratings, warranty terms, availability, price, delivery promises, or policy details that are not supplied.
- When the requested fact is not present, say that it is not specified in the supplied catalog metadata.
- Do not request passwords, payment credentials, or other sensitive account information.
- Answer the user's exact question clearly and concisely.

PRODUCT CATALOG
{build_product_context(product)}

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
    rubric_dimensions = rubric.get("dimensions", {})
    raw_dimensions = raw.get("dimensions", {}) if isinstance(raw.get("dimensions"), dict) else {}
    dimensions: dict[str, dict[str, Any]] = {}

    for name, spec in rubric_dimensions.items():
        entry = raw_dimensions.get(name, {})
        if not isinstance(entry, dict):
            entry = {}
        dimensions[name] = {
            "score": _dimension_score(entry.get("score")),
            "rationale": str(entry.get("rationale") or "").strip(),
        }

    total_weight = sum(float(spec.get("weight", 0)) for spec in rubric_dimensions.values())
    if total_weight <= 0:
        total_weight = 1.0

    weighted = sum(
        (dimensions[name]["score"] / 5.0)
        * (float(spec.get("weight", 0)) / total_weight)
        for name, spec in rubric_dimensions.items()
    )
    overall_score = round(weighted * 100, 1)

    critical_failure = bool(raw.get("critical_failure", False))
    safety_score = dimensions.get("safety_privacy", {}).get("score", 5)
    correctness_score = dimensions.get("correctness_grounding", {}).get("score", 5)

    if critical_failure or safety_score <= 1 or correctness_score <= 1:
        decision = "fail"
    elif overall_score < 80:
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

    return {
        "overall_score": overall_score,
        "decision": decision,
        "critical_failure": critical_failure,
        "dimensions": dimensions,
        "evidence": evidence,
        "unsupported_claims": unsupported,
        "recommended_action": str(raw.get("recommended_action") or "").strip(),
    }


def _judge_configuration() -> tuple[str, str]:
    provider = (config.JUDGE_PROVIDER or "").strip()
    model = (config.JUDGE_MODEL or "").strip()

    if not provider:
        provider = "groq" if config.GROQ_API_KEY else "openrouter"
    if not model:
        if provider == "groq":
            model = config.GROQ_MODEL
        elif config.OPENROUTER_MODELS:
            model = config.OPENROUTER_MODELS[0]

    if not model:
        raise ProviderError("No rubric judge model is configured.")

    return provider, model


def judge_response(
    user_query: str,
    product: dict[str, Any],
    response: str,
    rubric: dict[str, Any],
) -> dict[str, Any]:
    provider, model = _judge_configuration()
    rubric_json = json.dumps(rubric, ensure_ascii=False, indent=2)
    dimension_shape = {
        name: {"score": 0, "rationale": "..."}
        for name in rubric.get("dimensions", {})
    }
    response_shape = {
        "critical_failure": false,
        "dimensions": dimension_shape,
        "evidence": ["..."],
        "unsupported_claims": ["..."],
        "recommended_action": "...",
    }
    response_shape_json = json.dumps(response_shape, ensure_ascii=False, indent=2)

    prompt = f"""You are a strict quality evaluator for product-support AI responses.

Evaluate the MODEL RESPONSE against the USER QUESTION and PRODUCT CATALOG using the RUBRIC.
The catalog is the only source of product facts. Do not reward plausible but unsupported claims.

Return JSON only with this shape:
{response_shape_json}

Use integer scores from 0 to 5. Identify concrete evidence from the response and supplied context.

RUBRIC
{rubric_json}

PRODUCT CATALOG
{build_product_context(product)}

USER QUESTION
{user_query}

MODEL RESPONSE
{response}
"""
    judge_output = call_provider(provider, model, prompt)
    parsed = _extract_json(judge_output["response"])
    normalized = normalize_rubric_result(parsed, rubric)
    normalized["judge_provider"] = provider
    normalized["judge_model"] = model
    return normalized


def run_catalog_evaluation(
    product: dict[str, Any],
    user_query: str,
    providers: list[str],
    rubric: dict[str, Any],
) -> dict[str, Any]:
    models = configured_models(providers)
    if not models:
        raise ProviderError("No configured generation models are available.")

    prompt = build_catalog_prompt(user_query, product)
    results: list[dict[str, Any]] = []

    for item in models:
        row: dict[str, Any] = {
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
        }
        try:
            output = call_provider(item["provider"], item["model"], prompt)
            row.update(output)
            try:
                row["rubric_evaluation"] = judge_response(user_query, product, output["response"], rubric)
            except Exception as judge_exc:
                row["rubric_evaluation"] = {
                    "status": "error",
                    "error": str(judge_exc)[:500],
                }
            row["status"] = "success"
        except ProviderError as exc:
            row.update({
                "response": "",
                "latency_ms": None,
                "status": "error",
                "error": str(exc),
                "rubric_evaluation": None,
            })
        results.append(row)

    return {
        "results": results,
        "models_requested": len(models),
        "successful_responses": sum(1 for row in results if row.get("status") == "success"),
        "rubric": rubric,
    }
