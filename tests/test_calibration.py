import pytest

from backend.calibration import agreement, analyze_reliability, calibrate_thresholds


def _row(i, split, label, score):
    return {
        "trace_id": f"trace-{i}", "split": split,
        "reviewer_a_decision": label, "reviewer_b_decision": label,
        "adjudicated_decision": label, "judge_decision": label,
        "judge_score": score,
        "dimensions": {
            "correctness": {"reviewer_a": label, "reviewer_b": label,
                            "judge": label, "adjudicated": label},
            "clarity": {"reviewer_a": label, "reviewer_b": ("fail" if label != "fail" else "pass") if i % 2 else label,
                        "judge": label, "adjudicated": label},
        },
    }


def test_agreement_perfect_and_empty():
    assert agreement([("pass", "pass")])["cohen_kappa"] == 1.0
    assert agreement([])["exact_agreement"] is None


def test_calibration_and_holdout_report():
    rows = []
    for i in range(12):
        label = "fail" if i < 4 else "review" if i < 8 else "pass"
        score = 0.1 if label == "fail" else 0.5 if label == "review" else 0.9
        rows.append(_row(i, "validation", label, score))
    for i in range(12, 18):
        label = "fail" if i < 14 else "review" if i < 16 else "pass"
        score = 0.1 if label == "fail" else 0.5 if label == "review" else 0.9
        rows.append(_row(i, "holdout", label, score))
    report = analyze_reliability(rows)
    assert report["split_sizes"] == {"validation": 12, "holdout": 6}
    assert report["frozen_threshold_holdout_evaluation"]["calibrated_score_vs_adjudicated"]["accuracy"] == 1.0
    assert report["dimension_disagreement"]["validation"]["clarity"]["human_disagreement_rate"] == pytest.approx(0.5)


def test_threshold_calibration_rejects_too_small_validation():
    with pytest.raises(ValueError, match="12 validation"):
        calibrate_thresholds([_row(i, "validation", "pass", 0.9) for i in range(5)])


def test_requires_unique_ids_and_both_splits():
    with pytest.raises(ValueError, match="unique"):
        analyze_reliability([_row(1, "validation", "pass", .9),
                             _row(1, "holdout", "pass", .9)])
    with pytest.raises(ValueError, match="Both validation"):
        analyze_reliability([_row(i, "validation", "pass", .9) for i in range(12)])


def test_group_id_cannot_cross_validation_and_holdout():
    a = _row(1, "validation", "pass", .9)
    b = _row(2, "holdout", "pass", .9)
    a["group_id"] = b["group_id"] = "same-prompt"
    rows = [a] + [_row(i, "validation", "pass", .9) for i in range(3, 14)] + [b]
    with pytest.raises(ValueError, match="both validation and holdout"):
        analyze_reliability(rows)


def test_invalid_scores_rejected():
    rows = [_row(i, "validation", "pass", .9) for i in range(12)]
    rows += [_row(20, "holdout", "pass", 1.2)]
    with pytest.raises(ValueError, match="judge_score"):
        analyze_reliability(rows)
