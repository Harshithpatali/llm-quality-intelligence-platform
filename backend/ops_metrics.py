from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
from statistics import mean

DIMENSIONS = ("relevance", "correctness", "completeness")
LABELS = {"pass", "minor_issue", "major_issue", "not_applicable"}


def summarize_annotations(rows):
    total = len(rows)
    if not total:
        return {
            "annotation_count": 0,
            "tasks_reviewed": 0,
            "unique_annotators": 0,
            "mean_handling_seconds": None,
            "dimension_pass_rate": {},
            "major_issue_rate": None,
            "escalation_rate": None,
            "label_counts": {},
            "defect_counts": {},
        }

    dims = {}
    for dim in DIMENSIONS:
        eligible = [
            r for r in rows
            if r.get(dim) in LABELS and r.get(dim) != "not_applicable"
        ]
        dims[dim] = (
            round(sum(r[dim] == "pass" for r in eligible) / len(eligible), 4)
            if eligible else None
        )

    durations = [
        float(r["handling_seconds"])
        for r in rows
        if r.get("handling_seconds") is not None
        and float(r["handling_seconds"]) >= 0
    ]

    defects = Counter(
        r.get("defect_category", "none")
        for r in rows
        if r.get("defect_category")
    )

    return {
        "annotation_count": total,
        "tasks_reviewed": len({r.get("task_id") or r.get("trace_id") for r in rows}),
        "unique_annotators": len({r.get("annotator_id") for r in rows}),
        "mean_handling_seconds": round(mean(durations), 1) if durations else None,
        "dimension_pass_rate": dims,
        "major_issue_rate": round(
            sum(any(r.get(d) == "major_issue" for d in DIMENSIONS) for r in rows) / total,
            4,
        ),
        "escalation_rate": round(sum(bool(r.get("escalated")) for r in rows) / total, 4),
        "label_counts": dict(Counter(r.get("overall_label", "unlabelled") for r in rows)),
        "defect_counts": dict(defects),
    }


def _stable_key(row: dict) -> str:
    raw = f'{row.get("trace_id") or row.get("task_id") or row.get("id")}'
    return sha256(raw.encode("utf-8")).hexdigest()


def audit_sample(rows, sample_size=10):
    """Risk-aware deterministic QA sample; not a statistically representative sample."""
    if not rows:
        return []

    eligible = [r for r in rows if not r.get("is_audit")]
    high_risk = [
        r for r in eligible
        if r.get("escalated")
        or r.get("overall_label") in {"reject", "escalate"}
        or any(r.get(d) == "major_issue" for d in DIMENSIONS)
    ]
    baseline = [r for r in eligible if r not in high_risk]

    high_risk = sorted(high_risk, key=_stable_key)
    baseline = sorted(baseline, key=_stable_key)

    limit = max(0, min(int(sample_size), len(eligible)))
    selected = high_risk[:limit]
    if len(selected) < limit:
        selected.extend(baseline[:limit - len(selected)])
    return selected


def _cohen_kappa(labels_a, labels_b):
    n = len(labels_a)
    if n == 0:
        return None

    agree = sum(a == b for a, b in zip(labels_a, labels_b)) / n
    categories = set(labels_a) | set(labels_b)
    expected = sum(
        (labels_a.count(category) / n) * (labels_b.count(category) / n)
        for category in categories
    )
    denominator = 1 - expected
    if denominator == 0:
        return 1.0 if agree == 1 else 0.0
    return round((agree - expected) / denominator, 4)


def summarize_review_agreement(rows):
    """Measure inter-annotator and automated-vs-human agreement."""
    trace_groups = defaultdict(list)
    for row in rows:
        trace_id = row.get("trace_id")
        if trace_id:
            trace_groups[trace_id].append(row)

    pair_overall = []
    pair_dimension = {dimension: [] for dimension in DIMENSIONS}
    auto_matches = 0
    human_rows = 0

    human_to_auto = {
        "accept": "pass",
        "revise": "review",
        "reject": "fail",
        "escalate": "fail",
    }

    for row in rows:
        automated = row.get("automated_evaluation_snapshot")
        human_label = row.get("overall_label")
        if not isinstance(automated, dict) or human_label not in human_to_auto:
            continue
        auto_decision = automated.get("decision")
        if auto_decision not in {"pass", "review", "fail"}:
            continue
        human_rows += 1
        auto_matches += int(auto_decision == human_to_auto[human_label])

    kappa_labels_a = []
    kappa_labels_b = []
    two_annotator_traces = 0

    for group in trace_groups.values():
        annotators = {}
        for row in group:
            annotator = row.get("annotator_id")
            if annotator:
                annotators.setdefault(annotator, row)

        for left_name, right_name in combinations(sorted(annotators), 2):
            left = annotators[left_name]
            right = annotators[right_name]
            pair_overall.append(
                int(left.get("overall_label") == right.get("overall_label"))
            )
            for dimension in DIMENSIONS:
                pair_dimension[dimension].append(
                    int(left.get(dimension) == right.get(dimension))
                )

        if len(annotators) == 2:
            two_annotator_traces += 1
            ordered = [annotators[name] for name in sorted(annotators)]
            kappa_labels_a.append(ordered[0].get("overall_label"))
            kappa_labels_b.append(ordered[1].get("overall_label"))

    return {
        "traces_with_multiple_annotators": sum(
            len({
                r.get("annotator_id")
                for r in group
                if r.get("annotator_id")
            }) >= 2
            for group in trace_groups.values()
        ),
        "two_annotator_traces": two_annotator_traces,
        "pairwise_overall_agreement_pct": (
            round(100 * mean(pair_overall), 1) if pair_overall else None
        ),
        "cohen_kappa_overall": (
            _cohen_kappa(kappa_labels_a, kappa_labels_b)
            if kappa_labels_a else None
        ),
        "dimension_agreement_pct": {
            dimension: round(100 * mean(values), 1) if values else None
            for dimension, values in pair_dimension.items()
        },
        "automated_vs_human_samples": human_rows,
        "automated_vs_human_agreement_pct": (
            round(100 * auto_matches / human_rows, 1)
            if human_rows else None
        ),
    }
