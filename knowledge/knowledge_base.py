"""
BuyQK Knowledge Base.

Provides access to structured, non-transactional knowledge
stored under data/knowledge/.

This module must not be used as a source of transactional facts.

Transactional facts such as:
    - product price
    - stock
    - product availability
    - orders
    - cart contents
    - payment status

must always come from backend services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class KnowledgeBase:
    """
    Lightweight structured knowledge-base loader.

    Knowledge files are JSON documents stored under:

        data/knowledge/

    The class loads them lazily and caches them in memory.
    """

    def __init__(
        self,
        data_dir: str | Path = "data/knowledge",
    ) -> None:
        self.data_dir = Path(data_dir)
        self._cache: dict[str, Any] = {}

    # ---------------------------------------------------------
    # Internal loader
    # ---------------------------------------------------------

    def _load_json(
        self,
        filename: str,
    ) -> Any:
        """
        Load a JSON knowledge file.

        Raises:
            FileNotFoundError:
                If the requested knowledge file does not exist.

            ValueError:
                If the JSON content is invalid.
        """

        if filename in self._cache:
            return self._cache[filename]

        path = self.data_dir / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Knowledge file not found: {path}"
            )

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in knowledge file: {path}"
            ) from exc

        self._cache[filename] = data

        return data

    # ---------------------------------------------------------
    # Product Categories
    # ---------------------------------------------------------

    def get_product_categories(
        self,
    ) -> dict[str, Any]:
        """
        Return product-category knowledge.
        """

        return self._load_json(
            "product_categories.json"
        )

    # ---------------------------------------------------------
    # Merchant Categories
    # ---------------------------------------------------------

    def get_merchant_categories(
        self,
    ) -> dict[str, Any]:
        """
        Return merchant-category knowledge.
        """

        return self._load_json(
            "merchant_categories.json"
        )

    # ---------------------------------------------------------
    # Electronics
    # ---------------------------------------------------------

    def get_electronics_comparison(
        self,
    ) -> dict[str, Any]:
        """
        Return electronics comparison knowledge.
        """

        return self._load_json(
            "electronics_comparison.json"
        )

    # ---------------------------------------------------------
    # Medicine
    # ---------------------------------------------------------

    def get_medicine_safety(
        self,
    ) -> dict[str, Any]:
        """
        Return medicine safety knowledge.

        This knowledge is informational and must not be treated
        as a substitute for prescription verification,
        pharmacist review, or backend authorization.
        """

        return self._load_json(
            "medicine_safety.json"
        )

    # ---------------------------------------------------------
    # Generic Access
    # ---------------------------------------------------------

    def get(
        self,
        filename: str,
    ) -> Any:
        """
        Load an arbitrary JSON knowledge file.

        The filename must refer to a JSON file under the
        configured knowledge directory.
        """

        if not filename.endswith(".json"):
            raise ValueError(
                "Knowledge files must use the .json extension."
            )

        return self._load_json(filename)

    # ---------------------------------------------------------
    # Cache
    # ---------------------------------------------------------

    def clear_cache(self) -> None:
        """
        Clear cached knowledge.

        Useful when knowledge files are updated during
        development.
        """

        self._cache.clear()