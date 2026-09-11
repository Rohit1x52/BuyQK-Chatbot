"""
BuyQK knowledge retriever.

Connects:
    query
        ↓
    embedding provider
        ↓
    VectorStore
        ↓
    FAISS results

This module does not access transactional data.
"""

from __future__ import annotations

from typing import Any

from backend.database.vector_store import VectorStore
from knowledge.embeddings import EmbeddingProvider


class KnowledgeRetriever:
    """
    Semantic knowledge retriever backed by FAISS.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        store_dir: str = "data/vector_store",
    ) -> None:
        self.embedding_provider = (
            embedding_provider
            or EmbeddingProvider()
        )

        self.vector_store = VectorStore(
            dimension=self.embedding_provider.dimension,
            store_dir=store_dir,
        )

    # ---------------------------------------------------------
    # Index Documents
    # ---------------------------------------------------------

    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """
        Embed and store knowledge documents.

        Each document must contain a `text` field.
        """

        if not documents:
            return

        texts = []

        for document in documents:
            text = document.get("text")

            if not isinstance(text, str):
                raise ValueError(
                    "Every knowledge document must contain "
                    "a string 'text' field."
                )

            text = text.strip()

            if not text:
                raise ValueError(
                    "Knowledge document text cannot be empty."
                )

            texts.append(text)

        embeddings = (
            self.embedding_provider.embed_documents(
                texts
            )
        )

        self.vector_store.add_documents(
            embeddings=embeddings,
            documents=documents,
        )

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the most relevant knowledge documents.
        """

        query = str(query).strip()

        if not query:
            return []

        query_embedding = (
            self.embedding_provider.embed_query(
                query
            )
        )

        if not query_embedding:
            return []

        return self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
        )

    # ---------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------

    def save(self) -> None:
        """
        Persist the FAISS index and document metadata.
        """

        self.vector_store.save()

    def load(self) -> None:
        """
        Load the persisted FAISS knowledge store.
        """

        self.vector_store.load()

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------

    def count(self) -> int:
        """
        Return the number of indexed knowledge documents.
        """

        return self.vector_store.count()

    def clear(self) -> None:
        """
        Clear the complete knowledge index.
        """

        self.vector_store.clear()