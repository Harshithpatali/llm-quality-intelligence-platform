from backend.catalog_eval import (
    DEFAULT_CATALOG_RUBRIC,
    build_catalog_prompt,
    build_product_context,
    normalize_rubric_result,
)


def test_catalog_context_contains_product_metadata_and_bullets():
    product = {
        "item_id": "X1",
        "domain_name": "amazon.in",
        "item_name": "Demo Phone Case",
        "brand": "Demo",
        "color": "Black",
        "bullet_points": ["Shock resistant", "Slim fit"],
    }
    context = build_product_context(product)
    assert "Demo Phone Case" in context
    assert "Color: Black" in context
    assert "- Shock resistant" in context


def test_catalog_prompt_enforces_grounding():
    product = {
        "item_id": "X1",
        "domain_name": "amazon.in",
        "item_name": "Demo",
        "bullet_points": [],
    }
    prompt = build_catalog_prompt("Is it waterproof?", product)
    assert "Do not invent specifications" in prompt
    assert "Is it waterproof?" in prompt


def test_rubric_score_is_weighted_and_deterministic():
    raw = {
        "critical_failure": False,
        "dimensions": {
            name: {"score": 5, "rationale": "supported"}
            for name in DEFAULT_CATALOG_RUBRIC["dimensions"]
        },
        "evidence": ["All claims were grounded."],
        "unsupported_claims": [],
        "recommended_action": "No correction required.",
    }
    result = normalize_rubric_result(raw, DEFAULT_CATALOG_RUBRIC)
    assert result["overall_score"] == 100.0
    assert result["decision"] == "pass"
