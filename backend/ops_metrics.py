from collections import Counter
from statistics import mean

DIMENSIONS = ("relevance", "correctness", "completeness")
LABELS = {"pass", "minor_issue", "major_issue", "not_applicable"}

def summarize_annotations(rows):
    """Compute transparent operational metrics from submitted human annotations."""
    total = len(rows)
    if not total:
        return {"annotation_count": 0, "tasks_reviewed": 0, "unique_annotators": 0,
                "mean_handling_seconds": None, "dimension_pass_rate": {},
                "major_issue_rate": None, "escalation_rate": None, "label_counts": {}}
    dims = {}
    for dim in DIMENSIONS:
        eligible = [r for r in rows if r.get(dim) in LABELS and r.get(dim) != "not_applicable"]
        dims[dim] = round(sum(r[dim] == "pass" for r in eligible) / len(eligible), 4) if eligible else None
    durations = [float(r["handling_seconds"]) for r in rows if r.get("handling_seconds") is not None and float(r["handling_seconds"]) >= 0]
    return {
        "annotation_count": total,
        "tasks_reviewed": len({r.get("task_id") for r in rows}),
        "unique_annotators": len({r.get("annotator_id") for r in rows}),
        "mean_handling_seconds": round(mean(durations), 1) if durations else None,
        "dimension_pass_rate": dims,
        "major_issue_rate": round(sum(any(r.get(d) == "major_issue" for d in DIMENSIONS) for r in rows) / total, 4),
        "escalation_rate": round(sum(bool(r.get("escalated")) for r in rows) / total, 4),
        "label_counts": dict(Counter(r.get("overall_label", "unlabelled") for r in rows)),
    }

def audit_sample(rows, sample_size=5):
    """Deterministic audit selection, stable for a fixed input ordering."""
    eligible = [r for r in rows if not r.get("is_audit")]
    return eligible[:max(0, min(int(sample_size), len(eligible)))]
