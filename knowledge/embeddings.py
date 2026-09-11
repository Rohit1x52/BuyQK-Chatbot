"""
BuyQK embedding provider.

This module is responsible only for converting text into
embedding vectors.

It does not:
    - access SQLite
    - access products
    - access orders
    - perform FAISS search
    - contain commerce business logic
"""

from __future__ import annotations

from typing import Sequence


DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)


class EmbeddingProvider:
    """
    Local sentence-transformers embedding provider.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        try:
            from sentence_transformers import (
                SentenceTransformer,
            )
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for "
                "BuyQK knowledge-base embeddings."
            ) from exc

        self.model_name = model_name
        self.model = SentenceTransformer(
            model_name
        )

    # ---------------------------------------------------------
    # Document Embeddings
    # ---------------------------------------------------------

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple documents.
        """

        if not texts:
            return []

        embeddings = self.model.encode(
            list(texts),
            normalize_embeddings=True,
        )

        return embeddings.tolist()

    # ---------------------------------------------------------
    # Query Embedding
    # ---------------------------------------------------------

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """
        Generate an embedding for a single query.
        """

        text = str(text).strip()

        if not text:
            return []

        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
        )

        return embedding.tolist()

    # ---------------------------------------------------------
    # Dimension
    # ---------------------------------------------------------

    @property
    def dimension(self) -> int:
        """
        Return the embedding dimension.
        """

        return int(
            self.model.get_sentence_embedding_dimension()
        )