"""Retrieval service used by the discovery agent and test scripts.

This keeps the existing public interfaces intact while providing a simple
fallback implementation when pgvector-backed embeddings are not yet available.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from backend.embeddings import get_embedding_service
from backend.scheme_document import build_scheme_document

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[\'’][A-Za-z0-9]+)?")


class RetrievalService:
    def __init__(self, conn: Any, top_k: int = 5, min_similarity: float = 0.1):
        self.conn = conn
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.embedding_service = get_embedding_service()

    def retrieve(self, query: str, top_k: int | None = None, min_similarity: float | None = None):
        query = (query or "").strip()
        if not query:
            return []

        top_k = self.top_k if top_k is None else top_k
        min_similarity = self.min_similarity if min_similarity is None else min_similarity

        results = self._retrieve_by_embedding(query, min_similarity=min_similarity, top_k=top_k)
        if results:
            return results

        return self._retrieve_by_keyword(query, min_similarity=min_similarity, top_k=top_k)

    def _retrieve_by_embedding(self, query: str, min_similarity: float, top_k: int):
        # register_vector(conn) (in database.py) lets psycopg encode this list
        # straight into a Postgres `vector` literal via the %s::vector cast --
        # no manual serialization needed on this side.
        query_vector = self.embedding_service.embed(query)

        # Cosine similarity computed IN POSTGRES via the <=> operator, not in
        # a Python loop -- returns a plain float per row, no Vector/text
        # decoding involved, and only pulls back top_k rows instead of every
        # embedding in the table.
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT data, 1 - (embedding <=> %s::vector) AS similarity
                FROM schemes
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vector, query_vector, top_k),
            )
            rows = cur.fetchall()

        return [
            dict(row["data"], similarity=row["similarity"])
            for row in rows
            if row["similarity"] >= min_similarity
        ]

    def _retrieve_by_keyword(self, query: str, min_similarity: float, top_k: int):
        query_tokens = Counter(token.lower() for token in _TOKEN_RE.findall(query))
        if not query_tokens:
            return []

        with self.conn.cursor() as cur:
            cur.execute("SELECT id, name, category, data FROM schemes")
            rows = cur.fetchall()

        scored: list[dict[str, Any]] = []
        for row in rows:
            document = build_scheme_document(row.get("data", {}))
            doc_tokens = Counter(token.lower() for token in _TOKEN_RE.findall(document))
            overlap = sum(min(query_tokens[token], doc_tokens.get(token, 0)) for token in query_tokens)
            if overlap == 0:
                continue

            score = overlap / (len(query_tokens) + 0.01)
            if score >= min_similarity:
                scored.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "category": row["category"],
                        "similarity": score,
                    }
                )

        scored.sort(key=lambda item: item["similarity"], reverse=True)
        return scored[:top_k]