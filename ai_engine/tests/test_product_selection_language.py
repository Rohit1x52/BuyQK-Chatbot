"""
BuyQK AI - Phase 6C Product Selection Language Tests

Candidate selection is catalog-agnostic. These tests verify that the same
backend-derived candidate position can be selected in:
- English
- Hinglish
- Hindi

The tests never ask the LLM to choose a product and never invent a product ID.
"""

from __future__ import annotations

import pytest

from ai_engine.nodes import entity_node as entity_node_module
from ai_engine.nodes.entity_node import _selection_index_from_message


@pytest.mark.parametrize(
    "message,expected_index",
    [
        ("second one", 2),
        ("second option", 2),
        ("option 2", 2),
        ("dusra wala", 2),
        ("doosra wala", 2),
        ("दूसरा वाला", 2),
        ("दूसरा ऑप्शन", 2),
    ],
)
def test_selection_position_supports_english_hinglish_and_hindi(
    message: str,
    expected_index: int,
) -> None:
    assert _selection_index_from_message(message) == expected_index


@pytest.mark.parametrize(
    "message",
    [
        "pehla wala",
        "teesra wala",
        "chautha wala",
        "पहला वाला",
        "तीसरा वाला",
        "चौथा वाला",
    ],
)
def test_other_common_multilingual_ordinals_are_supported(
    message: str,
) -> None:
    assert _selection_index_from_message(message) is not None


@pytest.mark.parametrize(
    "message",
    [
        "option 2",
        "dusra wala",
        "दूसरा वाला",
    ],
)
def test_multilingual_selection_resolves_only_against_backend_candidates(
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        {
            "id": 501,
            "name": "Synthetic Candidate A",
        },
        {
            "id": 502,
            "name": "Synthetic Candidate B",
        },
        {
            "id": 503,
            "name": "Synthetic Candidate C",
        },
    ]

    # Keep this test focused on candidate selection rather than the LLM.
    # The entity node must obtain product identity from the candidate list.
    monkeypatch.setattr(
        entity_node_module,
        "extract_entities",
        lambda *args, **kwargs: entity_node_module.LLMEntityOutput(),
    )

    result = entity_node_module.entity_node(
        {
            "message": message,
            "intent": "cart",
            "entities": {
                "cart_action": "add_item",
                "quantity": 1,
            },
            "product_search_results": candidates,
            "conversation_history": [],
        }
    )

    assert result["entities"]["product_id"] == 502
    assert (
        result["entities"]["product_name"]
        == "Synthetic Candidate B"
    )


@pytest.mark.parametrize(
    "message",
    [
        "option 0",
        "option 9",
        "dusra",  # No explicit candidate marker.
        "यह वाला",  # No ordinal/position.
    ],
)
def test_ambiguous_or_invalid_selection_is_not_resolved(
    message: str,
) -> None:
    candidates = [
        {
            "id": 601,
            "name": "Synthetic Candidate A",
        },
        {
            "id": 602,
            "name": "Synthetic Candidate B",
        },
    ]

    assert entity_node_module._select_product_search_result(
        message,
        candidates,
    ) is None
