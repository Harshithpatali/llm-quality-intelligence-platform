import re
from collections import Counter

STOP = {"the","a","an","and","or","to","of","in","is","are","for","with","on","by","as","be","this","that","it","you","your","we","our","can","will","from","at","if","not","only","use"}

def terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in STOP}

def evaluate(response: str, reference: str) -> dict:
    ref, out = terms(reference), terms(response)
    coverage = len(ref & out) / len(ref) if ref else 0.0
    length_ratio = min(len((response or "").split()) / max(len((reference or "").split()), 1), 1.0)
    length_score = min(length_ratio / 0.45, 1.0)
    score = round(100 * (0.75 * coverage + 0.25 * length_score), 2)
    return {
        "keyword_coverage": round(coverage, 4),
        "length_sanity": round(length_score, 4),
        "heuristic_score": score,
        "matched_terms": sorted(ref & out),
        "missing_terms": sorted(ref - out),
        "method": "deterministic_reference_overlap_v1"
    }
