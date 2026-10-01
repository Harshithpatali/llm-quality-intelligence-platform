from backend.evaluator import evaluate

def test_exact_reference_scores_high():
    result=evaluate("Returns are accepted within 30 days with receipt.","Returns are accepted within 30 days with receipt.")
    assert result["heuristic_score"] >= 90
    assert result["keyword_coverage"] == 1

def test_empty_response_scores_zero():
    result=evaluate("","A clear answer with useful details.")
    assert result["heuristic_score"] == 0

def test_missing_terms_are_reported():
    result=evaluate("Contact support.","Contact support within 14 days for a refund.")
    assert "refund" in result["missing_terms"]
