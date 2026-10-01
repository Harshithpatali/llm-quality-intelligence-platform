from backend.ops_metrics import summarize_annotations, audit_sample

def test_empty_metrics_are_explicit():
    result = summarize_annotations([])
    assert result["annotation_count"] == 0
    assert result["mean_handling_seconds"] is None
    assert result["dimension_pass_rate"] == {}

def test_metrics_use_eligible_dimension_denominator():
    rows = [
        {"task_id":"T1","annotator_id":"a","relevance":"pass","correctness":"major_issue","completeness":"not_applicable","overall_label":"reject","handling_seconds":30,"escalated":True},
        {"task_id":"T1","annotator_id":"b","relevance":"minor_issue","correctness":"pass","completeness":"pass","overall_label":"revise","handling_seconds":60,"escalated":False},
    ]
    result = summarize_annotations(rows)
    assert result["annotation_count"] == 2
    assert result["tasks_reviewed"] == 1
    assert result["unique_annotators"] == 2
    assert result["dimension_pass_rate"] == {"relevance":0.5,"correctness":0.5,"completeness":1.0}
    assert result["major_issue_rate"] == 0.5
    assert result["escalation_rate"] == 0.5
    assert result["mean_handling_seconds"] == 45

def test_audit_sample_is_stable_and_excludes_existing_audits():
    rows = [{"id":1},{"id":2,"is_audit":True},{"id":3},{"id":4}]
    assert audit_sample(rows, 2) == [{"id":1},{"id":3}]
