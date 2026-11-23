from backend.evaluator import evaluate, terms


def test_terms_normalize_and_remove_stop_words():
    assert terms("The QUICK brown fox and the fox") == {"quick", "brown", "fox"}


def test_exact_reference_response_has_full_diagnostic_score():
    result = evaluate(
        "A customer can cancel the subscription at any time.",
        "A customer can cancel the subscription at any time.",
    )
    assert result["keyword_coverage"] == 1.0
    assert result["keyword_precision"] == 1.0
    assert result["keyword_f1"] == 1.0
    assert result["heuristic_score"] == 100.0
    assert result["method"] == "deterministic_reference_overlap_v2"


def test_empty_response_has_zero_score():
    result = evaluate("", "A meaningful reference answer")
    assert result["keyword_coverage"] == 0.0
    assert result["keyword_precision"] == 0.0
    assert result["heuristic_score"] == 0.0


def test_evaluator_returns_missing_matched_and_extra_terms():
    result = evaluate(
        "The customer can cancel a warranty",
        "The customer can cancel a subscription",
    )
    assert "customer" in result["matched_terms"]
    assert "subscription" in result["missing_terms"]
    assert "warranty" in result["extra_terms"]


def test_lexical_metric_explicitly_disclaims_semantic_validity():
    result = evaluate("A plausible but unsupported claim", "A reference answer")
    assert "not semantic correctness" in result["interpretation"]
