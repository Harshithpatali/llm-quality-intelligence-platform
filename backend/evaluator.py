"""Deterministic reference-overlap diagnostics.

These metrics are useful for triage, not semantic correctness or factuality.
Use the rubric judge and human review workflow for response-quality decisions.
"""
from __future__ import annotations

import re
from collections import Counter

STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "is", "are", "for",
    "with", "on", "by", "as", "be", "this", "that", "it", "you", "your",
    "we", "our", "can", "will", "from", "at", "if", "not", "only", "use",
}


def terms(text: str) -> list[str]:
    """Return normalized content tokens, retaining repetitions for precision."""
    return [
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").casefold())
        if len(token) > 2 and token not in STOP
    ]


def evaluate(response: str, reference: str) -> dict:
    """Calculate transparent lexical diagnostics against a reference answer.

    The composite is deliberately named heuristic_score. It must not be
    presented as a probability, factuality score, or validated quality score.
    """
    ref_tokens = terms(reference)
    out_tokens = terms(response)
    ref_counts, out_counts = Counter(ref_tokens), Counter(out_tokens)
    overlap = ref_counts & out_counts
    matched = sum(overlap.values())
    precision = matched / len(out_tokens) if out_tokens else 0.0
    recall = matched / len(ref_tokens) if ref_tokens else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )
    coverage = recall
    length_ratio = (
        min(len((response or "").split()) / max(len((reference or "").split()), 1), 1.0)
    )
    length_score = min(length_ratio / 0.45, 1.0)
    score = round(100 * (0.8 * f1 + 0.2 * length_score), 2)

    return {
        "keyword_precision": round(precision, 4),
        "keyword_recall": round(recall, 4),
        "keyword_f1": round(f1, 4),
        "keyword_coverage": round(coverage, 4),
        "length_sanity": round(length_score, 4),
        "heuristic_score": score,
        "matched_terms": sorted(overlap.elements()),
        "missing_terms": sorted((ref_counts - out_counts).elements()),
        "extra_terms": sorted((out_counts - ref_counts).elements()),
        "method": "deterministic_multiset_reference_overlap_v2",
        "interpretation": (
            "Lexical overlap diagnostic only; not semantic correctness, "
            "factuality, relevance, or safety."
        ),
    }
