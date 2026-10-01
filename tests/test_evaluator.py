from backend.evaluator import evaluate, terms


def test_terms_normalize_and_remove_stop_words():
    assert terms("The QUICK brown fox and the fox") == {"quick", "brown", "fox"}


def test_exact_reference_response_has_full_diagnostic_score():
    result = evaluate(
        "A customer can cancel the subscription at any time.",
        "A customer can cancel the subscription at any time.",
    )
    assert result["keyword_coverage"] == 1.0
    assert result["heuristic_score"] == 100.0
    assert result["method"] == "deterministic_reference_overlap_v1"


def test_empty_response_has_zero_score():
    result = evaluate("", "A meaningful reference answer")
    assert result["keyword_coverage"] == 0.0
    assert result["heuristic_score"] == 0.0


def test_evaluator_returns_missing_and_matched_terms():
    result = evaluate("The customer can cancel", "The customer can cancel a subscription")
    assert "customer" in result["matched_terms"]
    assert "subscription" in result["missing_terms"]
