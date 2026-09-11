"""
BuyQK knowledge layer.

This package contains non-transactional knowledge used by
the AI orchestration layer.

Transactional facts such as:
    products
    prices
    stock
    orders
    payments
    carts

remain authoritative in the backend/database layer.
"""

from knowledge.embeddings import (
    EmbeddingProvider,
)

from knowledge.retriever import (
    KnowledgeRetriever,
)

from knowledge.knowledge_base import (
    KnowledgeBase,
)

__all__ = [
    "KnowledgeBase",
    "get_electronics_comparison_rules",
    "get_medicine_safety_rules",
]