"""Local sentence-transformer embedding service.

Loads the model named by EMBEDDING_MODEL (default:
sentence-transformers/all-MiniLM-L6-v2, 384 dims) once per process and reuses
it for both single-text and batched embedding. Runs fully locally -- no
external API call, so sensitive free-text profile input never leaves the
server, matching the README's stated design.

The model is loaded lazily (on first ``embed``/``generate_embeddings_batch``
call, not at import time) because loading it is too heavy to do on every
FastAPI worker boot when many requests never touch retrieval.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingService:
    """Wraps a local sentence-transformers model behind a small, stable
    interface (``embed``, ``generate_embeddings_batch``, ``dimension``,
    ``model_name``) so callers (retrieval_service.py, the embedding-generation
    scripts) never need to know which model is actually loaded.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME)
        self._model = None  # lazy-loaded on first use
        self._dimension: Optional[int] = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - environment issue, not a code bug
            raise RuntimeError(
                "sentence-transformers is not installed. Run "
                "`pip install -r requirements.txt` (it's already listed there) "
                "before generating or querying embeddings."
            ) from exc

        self._model = SentenceTransformer(self.model_name)
        if hasattr(self._model, "get_embedding_dimension"):
            self._dimension = self._model.get_embedding_dimension()
        else:  # older sentence-transformers versions    
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load()
        return self._dimension

    def embed(self, text: str) -> list[float]:
        model = self._load()
        vector = model.encode(text or "", normalize_embeddings=True)
        return vector.tolist()

    def generate_embeddings_batch(self, texts: Iterable[str]) -> list[list[float]]:
        model = self._load()
        texts = list(texts)
        if not texts:
            return []
        vectors = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return [v.tolist() for v in vectors]


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service