"""Deterministic lightweight embedding helpers for the project scripts.

The application already relies on a set of scripts that expect an
``EmbeddingService`` interface. This file supplies that interface without
requiring external ML packages, so the existing terminal workflows can run
and existing code paths remain unchanged.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[\'’][A-Za-z0-9]+)?")


class EmbeddingService:
    """A deterministic, dependency-free embedding service.

    The implementation uses a stable bag-of-tokens approach: each token is
    hashed into a fixed-size vector. This is enough for the repository's
    retrieval scripts and keeps the interfaces compatible with the rest of the
    codebase.
    """

    def __init__(self, dimension: int = 256, model_name: str = "deterministic-bow"):
        self.dimension = dimension
        self.model_name = model_name

    def embed(self, text: str) -> list[float]:
        tokens = [token.lower() for token in _TOKEN_RE.findall(text or "")]
        if not tokens:
            return [0.0] * self.dimension

        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1

        vector = [0.0] * self.dimension
        for token, count in counts.items():
            idx = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % self.dimension
            vector[idx] += count

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def generate_embeddings_batch(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


_embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    return _embedding_service
