"""
eval/metrics.py

Standard information-retrieval metrics, applied to scheme retrieval. All
functions are pure (no DB, no I/O) so they're trivially unit-testable on
their own with synthetic inputs.
"""
from __future__ import annotations


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Of the top-k retrieved, what fraction are actually relevant?"""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Of all relevant items, what fraction appeared in the top-k?"""
    if not relevant_ids:
        return 1.0  # nothing relevant expected -- vacuously satisfied
    top_k = set(retrieved_ids[:k])
    hits = len(top_k & relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """1/rank of the FIRST relevant item found; 0 if none appear at all."""
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def hit_rate(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """1.0 if at least one relevant item is in the top-k, else 0.0."""
    if not relevant_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    return 1.0 if (top_k & relevant_ids) else 0.0


def aggregate(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0