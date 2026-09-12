"""
eval/recommendation_eval.py

Mirrors the REAL discovery.py behavior: semantic search only RANKS the
structural candidate set, it never narrows it. Every structurally-eligible
scheme is still evaluated by the rule engine -- similarity score only
affects order, never whether a scheme is evaluated at all.
"""
from __future__ import annotations
from backend.rules import evaluate
from backend.retrieval_service import RetrievalService
from eval.metrics import precision_at_k, recall_at_k


def _get_structural_candidates(conn, state: str | None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT data FROM schemes WHERE state = 'ALL' OR state = %s", (state,))
        return [row["data"] for row in cur.fetchall()]


def get_ranked_recommended_scheme_ids(conn, profile, top_k: int = 5) -> list[str]:
    structural_candidates = _get_structural_candidates(conn, getattr(profile, "state", None))

    similarity_by_id: dict[str, float] = {}
    extra_info = getattr(profile, "extra_info", None)
    if extra_info:
        semantic_hits = RetrievalService(conn, top_k=top_k).retrieve(extra_info)
        similarity_by_id = {hit["id"]: hit["similarity"] for hit in semantic_hits}

    structural_candidates.sort(
        key=lambda s: similarity_by_id.get(s["id"], -1.0),
        reverse=True,
    )

    recommended = []
    for scheme in structural_candidates:
        status, _, _ = evaluate(profile, scheme.get("rules", {}))
        if status in ("eligible", "possible"):
            recommended.append(scheme["id"])
    return recommended


def evaluate_recommendation_case(conn, profile, expected_ids: list[str], min_relevant_in_top_k: int, top_k: int = 5) -> dict:
    relevant = set(expected_ids)
    recommended_ids = get_ranked_recommended_scheme_ids(conn, profile, top_k=top_k)

    relevant_found = len(set(recommended_ids) & relevant)
    meets_minimum = relevant_found >= min_relevant_in_top_k

    return {
        "recommended_ids": recommended_ids,
        "relevant_ids": list(relevant),
        "relevant_found": relevant_found,
        "min_relevant_required": min_relevant_in_top_k,
        "meets_minimum": meets_minimum,
        "precision": precision_at_k(recommended_ids, relevant, top_k),
        "recall": recall_at_k(recommended_ids, relevant, top_k),
    }