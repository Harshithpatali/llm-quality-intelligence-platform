from backend.ops_metrics import (
    audit_sample,
    summarize_annotations,
    summarize_review_agreement,
)


def test_empty_metrics_are_explicit():
    result = summarize_annotations([])
    assert result["annotation_count"] == 0
    assert result["mean_handling_seconds"] is None
    assert result["dimension_pass_rate"] == {}


def test_metrics_use_eligible_dimension_denominator():
    rows = [
        {
            "task_id": "T1",
            "annotator_id": "a",
            "relevance": "pass",
            "correctness": "major_issue",
            "completeness": "not_applicable",
            "overall_label": "reject",
            "handling_seconds": 30,
            "escalated": True,
        },
        {
            "task_id": "T1",
            "annotator_id": "b",
            "relevance": "minor_issue",
            "correctness": "pass",
            "completeness": "pass",
            "overall_label": "revise",
            "handling_seconds": 60,
            "escalated": False,
        },
    ]
    result = summarize_annotations(rows)
    assert result["annotation_count"] == 2
    assert result["tasks_reviewed"] == 1
    assert result["unique_annotators"] == 2
    assert result["dimension_pass_rate"] == {
        "relevance": 0.5,
        "correctness": 0.5,
        "completeness": 1.0,
    }
    assert result["major_issue_rate"] == 0.5
    assert result["escalation_rate"] == 0.5
    assert result["mean_handling_seconds"] == 45


def test_audit_sample_is_stable_and_excludes_existing_audits():
    rows = [
        {"id": 1},
        {"id": 2, "is_audit": True},
        {"id": 3},
        {"id": 4},
    ]
    first = audit_sample(rows, 2)
    second = audit_sample(rows, 2)
    assert first == second
    assert {row["id"] for row in first}.issubset({1, 3, 4})
    assert 2 not in {row["id"] for row in first}
    assert len(first) == 2


def test_audit_sample_prioritizes_risk():
    rows = [
        {"id": "safe-1", "overall_label": "accept"},
        {"id": "high-risk", "overall_label": "reject"},
        {"id": "safe-2", "overall_label": "accept"},
    ]
    sample = audit_sample(rows, 1)
    assert sample == [{"id": "high-risk", "overall_label": "reject"}]


def test_review_agreement_reports_human_and_automated_alignment():
    automated = {
        "decision": "pass",
        "overall_score": 90,
    }
    rows = [
        {
            "trace_id": "T1",
            "annotator_id": "a",
            "overall_label": "accept",
            "relevance": "pass",
            "correctness": "pass",
            "completeness": "pass",
            "automated_evaluation_snapshot": automated,
        },
        {
            "trace_id": "T1",
            "annotator_id": "b",
            "overall_label": "accept",
            "relevance": "pass",
            "correctness": "minor_issue",
            "completeness": "pass",
            "automated_evaluation_snapshot": automated,
        },
    ]
    result = summarize_review_agreement(rows)
    assert result["pairwise_overall_agreement_pct"] == 100.0
    assert result["automated_vs_human_agreement_pct"] == 100.0
