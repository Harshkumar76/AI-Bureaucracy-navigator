"""
eval/retrieval_eval.py

Runs your REAL RetrievalService against each case's free-text note and
scores the results using eval/metrics.py.
"""
from __future__ import annotations
from backend.retrieval_service import RetrievalService
from eval.metrics import precision_at_k, recall_at_k, reciprocal_rank, hit_rate


def evaluate_retrieval_case(conn, extra_info: str, expected_ids: list[str], top_k: int = 5) -> dict:
    relevant = set(expected_ids)

    if not extra_info:
        return {
            "extra_info": extra_info,
            "retrieved_ids": [],
            "relevant_ids": list(relevant),
            "precision_at_k": 1.0,
            "recall_at_k": 1.0,
            "reciprocal_rank": 1.0,
            "hit_rate": 1.0,
            "skipped": True,
        }

    retrieval_service = RetrievalService(conn, top_k=top_k)
    results = retrieval_service.retrieve(extra_info)
    retrieved_ids = [r["id"] for r in results]

    return {
        "extra_info": extra_info,
        "retrieved_ids": retrieved_ids,
        "relevant_ids": list(relevant),
        "precision_at_k": precision_at_k(retrieved_ids, relevant, top_k),
        "recall_at_k": recall_at_k(retrieved_ids, relevant, top_k),
        "reciprocal_rank": reciprocal_rank(retrieved_ids, relevant),
        "hit_rate": hit_rate(retrieved_ids, relevant, top_k),
        "skipped": False,
    }