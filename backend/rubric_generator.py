"""LLM-assisted rubric drafting with a human approval gate."""

from __future__ import annotations

import json
from typing import Any

from . import config
from .catalog_eval import validate_rubric
from .providers import ProviderError, call_provider

RUBRIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rubric_name": {"type": "string"},
        "objective": {"type": "string"},
        "dimensions": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "weight": {"type": "number", "minimum": 0, "maximum": 1},
                    "definition": {"type": "string"},
                    "pass_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "failure_examples": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "weight",
                    "definition",
                    "pass_criteria",
                    "failure_examples",
                ],
            },
        },
        "decision_rules": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "pass_threshold": {"type": "number", "minimum": 0, "maximum": 100},
                "review_threshold": {"type": "number", "minimum": 0, "maximum": 100},
                "critical_dimensions": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 5,
                    },
                },
            },
            "required": [
                "pass_threshold",
                "review_threshold",
                "critical_dimensions",
            ],
        },
    },
    "required": [
        "rubric_name",
        "objective",
        "dimensions",
        "decision_rules",
    ],
}


def generate_rubric(
    rubric_name: str,
    objective: str,
    policy_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = config.RUBRIC_PROVIDER
    model = config.RUBRIC_MODEL
    if not provider or not model:
        raise ProviderError(
            "Rubric generator provider/model is not configured.",
            error_type="missing_rubric_generator",
        )

    policy_text = (
        json.dumps(policy_context, ensure_ascii=False, indent=2)
        if policy_context
        else "No additional policy context was supplied."
    )

    prompt = f"""Create a rigorous quality-evaluation rubric for an AI response quality operation.

The rubric must be usable by both an automated judge and a human reviewer.
Include the dimensions needed to assess safety/privacy, relevance, correctness/grounding,
completeness, instruction/policy following, and clarity whenever they are relevant to the objective.
Do not invent external policy. Use only the supplied objective and policy context.
Each dimension needs a definition, pass criteria, and concrete failure examples.
Weights must sum to approximately 1.0.
Critical dimensions must include dimensions where a severe failure should block acceptance.

RUBRIC NAME
{rubric_name}

OBJECTIVE
{objective}

POLICY CONTEXT
{policy_text}
"""

    result = call_provider(
        provider,
        model,
        prompt,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "quality_rubric",
                "strict": True,
                "schema": RUBRIC_SCHEMA,
            },
        },
        timeout=90,
    )

    try:
        rubric = json.loads(result["response"])
    except json.JSONDecodeError as exc:
        raise ProviderError(
            f"Rubric generator returned invalid JSON: {exc}",
            error_type="invalid_rubric_json",
        ) from exc

    rubric = validate_rubric(rubric)
    rubric["generator_provider"] = provider
    rubric["generator_model"] = model
    rubric["generator_latency_ms"] = result.get("latency_ms")
    rubric["generator_estimated_cost_usd"] = result.get("estimated_cost_usd")
    return rubric
