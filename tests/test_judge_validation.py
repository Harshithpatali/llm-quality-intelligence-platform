import pytest

from backend.judge_validation import validate_judge


def test_judge_validation_maps_human_labels_and_builds_confusion_matrix():
    rows = [
        {"human_decision": "accept", "judge_decision": "pass", "category": "grounding"},
        {"human_decision": "revise", "judge_decision": "review", "category": "grounding"},
        {"human_decision": "reject", "judge_decision": "fail", "category": "safety"},
        {"human_decision": "escalate", "judge_decision": "fail", "category": "safety"},
    ]
    result = validate_judge(rows, bootstrap_iterations=200, seed=7)
    assert result["n"] == 4
    assert result["accuracy"] == 1.0
    assert result["cohen_kappa"] == 1.0
    assert result["confusion_matrix"]["fail"]["fail"] == 2
    assert set(result["by_category"]) == {"grounding", "safety"}
    assert result["accuracy_ci_95"] == [1.0, 1.0]


def test_judge_validation_reports_disagreement():
    rows = [
        {"human_decision": "accept", "judge_decision": "fail"},
        {"human_decision": "reject", "judge_decision": "pass"},
    ]
    result = validate_judge(rows, bootstrap_iterations=200)
    assert result["accuracy"] == 0.0
    assert result["cohen_kappa"] <= 0.0


def test_judge_validation_rejects_unknown_labels_and_missing_fields():
    with pytest.raises(ValueError, match="Unsupported"):
        validate_judge([{"human_decision": "maybe", "judge_decision": "pass"}])
    with pytest.raises(ValueError, match="must contain"):
        validate_judge([{"judge_decision": "pass"}])


def test_judge_validation_requires_reasonable_bootstrap_count():
    with pytest.raises(ValueError, match="at least 100"):
        validate_judge([], bootstrap_iterations=10)
