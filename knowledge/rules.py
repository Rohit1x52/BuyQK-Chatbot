"""
BuyQK domain knowledge rules.

This module exposes deterministic knowledge for:
    - electronics comparison
    - medicine safety

These rules describe how the AI should reason about a domain.

They do NOT contain transactional facts.

For example, this module must never determine:
    - whether a medicine is currently in stock
    - the price of a product
    - whether a pharmacy has a particular medicine
    - whether a user's prescription is valid

Those decisions belong to backend services and transaction
workflows.
"""

from __future__ import annotations

from typing import Any

from knowledge.knowledge_base import KnowledgeBase


_KNOWLEDGE_BASE = KnowledgeBase()


def get_electronics_comparison_rules() -> dict[str, Any]:
    """
    Return the structured rules used for electronics comparison.
    """

    return _KNOWLEDGE_BASE.get_electronics_comparison()


def get_medicine_safety_rules() -> dict[str, Any]:
    """
    Return the structured medicine-safety rules.

    These rules are informational guardrails only.
    They must never override backend prescription or
    authorization checks.
    """

    return _KNOWLEDGE_BASE.get_medicine_safety()