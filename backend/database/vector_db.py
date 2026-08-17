# Purpose:
# Provides a minimal FAISS-based vector database for
# BuyQK knowledge-base semantic search.
#
# IMPORTANT:
# This database is ONLY for unstructured knowledge/RAG data.
#
# Transactional data such as:
# users
# products
# orders
# payments
# support tickets
#
# remains in SQLite.


from pathlib import Path
from typing import Any

import faiss
import numpy as np


class VectorDB:
    """
    Minimal FAISS vector database for the BuyQK MVP.

    Responsibilities:
    - Store document embeddings
    - Store associated document text/metadata
    - Perform semantic similarity search
    - Save the FAISS index locally
    - Load the FAISS index when the application starts
    """

    def __init__(
        self,
        dimension: int,
        index_path: str = "data/vector_store/index.faiss",
    ):
        """
        Initialize the vector database.

        Args:
            dimension:
                Size of the embedding vector.

            index_path:
                Location where the FAISS index will be stored.
        """

        self.dimension = dimension

        self.index_path = Path(index_path)

        # Metadata/text associated with each vector.
        #
        # Example:
        #
        # [
        #     {
        #         "text": "Orders can be cancelled...",
        #         "source": "order_policy.txt"
        #     }
        # ]
        #
        self.documents: list[dict[str, Any]] = []

        # Create FAISS index.
        #
        # IndexFlatL2 performs exact Euclidean-distance search.
        #
        self.index = faiss.IndexFlatL2(
            self.dimension
        )

    # ---------------------------------------------------------
    # Add documents
    # ---------------------------------------------------------

    def add_documents(
        self,
        embeddings: list[list[float]],
        documents: list[dict[str, Any]],
    ) -> None:
        """
        Add document embeddings and metadata to the index.

        Args:
            embeddings:
                List of embedding vectors.

            documents:
                Metadata/text associated with each embedding.
        """

        if len(embeddings) != len(documents):
            raise ValueError(
                "Number of embeddings must match "
                "number of documents."
            )

        if not embeddings:
            return

        vectors = np.asarray(
            embeddings,
            dtype="float32",
        )

        # Validate embedding dimensions.
        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Expected embedding dimension "
                f"{self.dimension}, "
                f"but received {vectors.shape[1]}."
            )

        # Add vectors to FAISS.
        self.index.add(vectors)

        # Store corresponding document metadata.
        self.documents.extend(documents)

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for the most semantically similar documents.

        Args:
            query_embedding:
                Embedding vector for the user's query.

            top_k:
                Number of results to return.

        Returns:
            List of matching documents with similarity distance.
        """

        if self.index.ntotal == 0:
            return []

        query_vector = np.asarray(
            [query_embedding],
            dtype="float32",
        )

        if query_vector.shape[1] != self.dimension:
            raise ValueError(
                f"Expected query embedding dimension "
                f"{self.dimension}, "
                f"but received {query_vector.shape[1]}."
            )

        # Don't request more results than available.
        top_k = min(
            top_k,
            self.index.ntotal,
        )

        distances, indices = self.index.search(
            query_vector,
            top_k,
        )

        results = []

        for distance, index in zip(
            distances[0],
            indices[0],
        ):
            if index == -1:
                continue

            document = self.documents[index].copy()

            document["distance"] = float(distance)

            results.append(document)

        return results

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    def save(self) -> None:
        """
        Save the FAISS index to disk.

        The document metadata is stored separately.
        """

        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        faiss.write_index(
            self.index,
            str(self.index_path),
        )

    # ---------------------------------------------------------
    # Load
    # ---------------------------------------------------------

    def load(self) -> None:
        """
        Load an existing FAISS index from disk.

        Raises:
            FileNotFoundError:
                If the FAISS index does not exist.
        """

        if not self.index_path.exists():
            raise FileNotFoundError(
                f"Vector index not found: "
                f"{self.index_path}"
            )

        self.index = faiss.read_index(
            str(self.index_path)
        )

    # ---------------------------------------------------------
    # Clear
    # ---------------------------------------------------------

    def clear(self) -> None:
        """
        Remove all vectors and document metadata.
        """

        self.index = faiss.IndexFlatL2(
            self.dimension
        )

        self.documents.clear()

    # ---------------------------------------------------------
    # Count
    # ---------------------------------------------------------

    def count(self) -> int:
        """
        Return the number of vectors stored.
        """

        return self.index.ntotal