# =========================================================
# BuyQK AI - Tool Node
# =========================================================
#
# Purpose:
#   Execute the backend operation selected by decision_node.
#
# Important:
#   - Backend services remain authoritative for business rules.
#   - The LLM never supplies authoritative product/order IDs.
#   - Product search is resilient to exact-name mismatches.
#   - Checkout uses product_id -> quantity -> address -> payment.
#
# =========================================================

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ai_engine.graph.state import GraphState

from backend.models.product import Product

from backend.services.product_service import (
    search_products,
    get_product,
    check_product_availability,
)

from backend.services.order_service import (
    create_order,
    get_order,
    get_user_orders,
    cancel_order,
)

from backend.services.support_service import (
    create_ticket,
    get_ticket,
    get_user_tickets,
)

from backend.services.address_service import (
    get_user_addresses,
)


SUPPORTED_PAYMENT_METHODS = {
    "upi",
    "cod",
}


# =========================================================
# Generic Helpers
# =========================================================

def _has_value(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _normalize_text(value: Any) -> str:
    """
    Normalize user/product text for matching.

    Example:
        "Amul   Milk" -> "amul milk"
    """
    if value is None:
        return ""

    text = str(value).strip().lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _tokenize(value: Any) -> list[str]:
    normalized = _normalize_text(value)

    if not normalized:
        return []

    return normalized.split()


def _product_value(
    product: Any,
    field: str,
) -> Any:
    """
    Safely read a field from either:
      - SQLAlchemy ORM object
      - dict
    """
    if isinstance(product, dict):
        return product.get(field)

    return getattr(
        product,
        field,
        None,
    )


def _product_id(product: Any) -> Any:
    return _product_value(
        product,
        "id",
    )


def _product_name(product: Any) -> str:
    return str(
        _product_value(
            product,
            "name",
        )
        or ""
    ).strip()


def _serialize_product(
    product: Any,
) -> dict[str, Any]:
    """
    Convert Product ORM/dict into JSON-safe data.
    """
    return {
        "id": _product_value(product, "id"),
        "name": _product_value(product, "name"),
        "description": _product_value(product, "description"),
        "brand": _product_value(product, "brand"),
        "price": _product_value(product, "price"),
        "stock": _product_value(product, "stock"),
        "image_url": _product_value(product, "image_url"),
        "is_available": _product_value(product, "is_available"),
        "merchant_id": _product_value(product, "merchant_id"),
        "category_id": _product_value(product, "category_id"),
    }


def _serialize_address(address: Any) -> dict[str, Any]:
    """
    Serialize an address without assuming one exact address schema.
    """
    if isinstance(address, dict):
        return {
            "id": address.get("id"),
            "label": address.get("label"),
            "address": address.get("address"),
            "address_line1": address.get("address_line1"),
            "address_line2": address.get("address_line2"),
            "city": address.get("city"),
            "state": address.get("state"),
            "postal_code": address.get("postal_code"),
            "pincode": address.get("pincode"),
        }

    return {
        "id": getattr(address, "id", None),
        "label": getattr(address, "label", None),
        "address": getattr(address, "address", None),
        "address_line1": getattr(address, "address_line1", None),
        "address_line2": getattr(address, "address_line2", None),
        "city": getattr(address, "city", None),
        "state": getattr(address, "state", None),
        "postal_code": getattr(address, "postal_code", None),
        "pincode": getattr(address, "pincode", None),
    }


def _serialize_order(order: Any) -> dict[str, Any]:
    """
    JSON-safe order representation.
    """
    if order is None:
        return {}

    result: dict[str, Any] = {
        "id": getattr(order, "id", None),
        "user_id": getattr(order, "user_id", None),
        "address_id": getattr(order, "address_id", None),
        "status": getattr(order, "status", None),
        "payment_status": getattr(order, "payment_status", None),
        "total_amount": getattr(order, "total_amount", None),
    }

    payment_method = getattr(
        order,
        "_buyqk_payment_method",
        None,
    )

    if payment_method:
        result["payment_method"] = payment_method

    items = getattr(order, "items", None)

    if items:
        serialized_items: list[dict[str, Any]] = []

        for item in items:
            serialized_items.append(
                {
                    "id": getattr(item, "id", None),
                    "product_id": getattr(
                        item,
                        "product_id",
                        None,
                    ),
                    "quantity": getattr(
                        item,
                        "quantity",
                        None,
                    ),
                    "unit_price": getattr(
                        item,
                        "unit_price",
                        None,
                    ),
                    "total_price": getattr(
                        item,
                        "total_price",
                        None,
                    ),
                }
            )

        result["items"] = serialized_items

    return result


def _serialize_ticket(ticket: Any) -> dict[str, Any]:
    if ticket is None:
        return {}

    return {
        "id": getattr(ticket, "id", None),
        "user_id": getattr(ticket, "user_id", None),
        "order_id": getattr(ticket, "order_id", None),
        "subject": getattr(ticket, "subject", None),
        "description": getattr(ticket, "description", None),
        "status": getattr(ticket, "status", None),
    }


def _safe_error(exc: Exception) -> str:
    """
    Keep backend errors user-readable while avoiding traceback leakage.
    """
    message = str(exc).strip()

    if message:
        return message

    return (
        "The requested operation could not be completed."
    )


def _result(
    success: bool,
    **data: Any,
) -> dict[str, Any]:
    """
    Consistent tool_result shape.
    """
    return {
        "success": success,
        **data,
    }


# =========================================================
# Product Deduplication
# =========================================================

def _deduplicate_products(
    products: list[Any],
) -> list[Any]:
    result: list[Any] = []

    seen_ids: set[Any] = set()
    seen_names: set[str] = set()

    for product in products:
        product_id = _product_id(product)

        if product_id is not None:
            if product_id in seen_ids:
                continue

            seen_ids.add(product_id)

        else:
            name_key = _normalize_text(
                _product_name(product)
            )

            if name_key and name_key in seen_names:
                continue

            if name_key:
                seen_names.add(name_key)

        result.append(product)

    return result


# =========================================================
# Product Matching
# =========================================================

def _score_product(
    product: Any,
    query: str,
) -> int:
    """
    Higher score = stronger product match.

    Exact product name wins over variants.

    Example:
        Query: "Amul milk"

        "Amul Milk"       -> exact, strongest
        "Amul Taaza Milk" -> strong partial
        "Amul Full Cream Milk" -> strong partial
    """
    name = _normalize_text(
        _product_name(product)
    )

    normalized_query = _normalize_text(
        query
    )

    if not name or not normalized_query:
        return 0

    query_tokens = _tokenize(
        normalized_query
    )

    name_tokens = set(
        _tokenize(name)
    )

    if not query_tokens:
        return 0

    score = 0
    matched_tokens = 0

    # Exact name.
    if name == normalized_query:
        score += 10_000

    # Exact phrase inside product name.
    if normalized_query in name:
        score += 2_000

    for token in query_tokens:
        if token in name_tokens:
            matched_tokens += 1
            score += 500

        elif token in name:
            matched_tokens += 1
            score += 100

    # All query tokens matched.
    if matched_tokens == len(query_tokens):
        score += 1_000

    # Penalize extra unmatched tokens slightly.
    extra_tokens = max(
        0,
        len(name_tokens) - len(query_tokens),
    )

    score -= extra_tokens * 5

    return max(score, 0)


def _collect_search_results(
    db: Session,
    query: str,
) -> list[Any]:
    """
    Collect candidates from the existing product service.

    The service is treated as a first source, not the only source.
    """
    candidates: list[Any] = []

    queries = [query]

    for token in _tokenize(query):
        if len(token) >= 2 and token not in queries:
            queries.append(token)

    for search_query in queries:
        try:
            results = search_products(
                db=db,
                query=search_query,
            )

            if not results:
                continue

            if isinstance(results, (list, tuple)):
                candidates.extend(results)
            else:
                candidates.append(results)

        except Exception as exc:
            print(
                "[PRODUCT SEARCH FALLBACK] "
                f"{type(exc).__name__}: {exc}"
            )

    return candidates


def _collect_db_candidates(
    db: Session,
    query: str,
) -> list[Any]:
    """
    Direct DB fallback.

    This is specifically what protects checkout from:
        search_products("Amul milk") -> []
    when a real Product row exists.
    """
    candidates: list[Any] = []

    normalized_query = _normalize_text(
        query
    )

    if not normalized_query:
        return candidates

    try:
        # -----------------------------------------------------
        # Exact normalized name
        # -----------------------------------------------------
        exact = (
            db.query(Product)
            .filter(
                func.lower(Product.name)
                == normalized_query
            )
            .first()
        )

        if exact is not None:
            candidates.append(exact)

        # -----------------------------------------------------
        # Phrase match
        # -----------------------------------------------------
        partial = (
            db.query(Product)
            .filter(
                func.lower(Product.name).like(
                    f"%{normalized_query}%"
                )
            )
            .all()
        )

        candidates.extend(partial)

        # -----------------------------------------------------
        # Token-level fallback
        # -----------------------------------------------------
        query_tokens = [
            token
            for token in _tokenize(query)
            if len(token) >= 2
        ]

        if query_tokens:
            all_products = (
                db.query(Product)
                .all()
            )

            for product in all_products:
                product_name = _normalize_text(
                    _product_name(product)
                )

                if not product_name:
                    continue

                if all(
                    token in product_name
                    for token in query_tokens
                ):
                    candidates.append(product)

    except Exception as exc:
        print(
            "[PRODUCT DB FALLBACK] "
            f"{type(exc).__name__}: {exc}"
        )

    return candidates


def _resolve_product(
    db: Session,
    product_name: str,
) -> tuple[Any | None, list[Any]]:
    """
    Resolve a natural-language product name.

    Resolution order:
        1. Product service search
        2. Direct DB exact/partial/token search
        3. Deduplicate
        4. Score
        5. Exact match wins
        6. Otherwise unique strongest match wins
        7. Otherwise return ambiguity
    """
    if not product_name:
        return None, []

    query = str(product_name).strip()

    if not query:
        return None, []

    candidates = []

    candidates.extend(
        _collect_search_results(
            db=db,
            query=query,
        )
    )

    candidates.extend(
        _collect_db_candidates(
            db=db,
            query=query,
        )
    )

    candidates = _deduplicate_products(
        candidates
    )

    if not candidates:
        return None, []

    scored: list[tuple[int, Any]] = []

    for product in candidates:
        score = _score_product(
            product,
            query,
        )

        if score > 0:
            scored.append(
                (
                    score,
                    product,
                )
            )

    if not scored:
        return None, candidates

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score = scored[0][0]

    best_products = [
        product
        for score, product in scored
        if score == best_score
    ]

    best_product = best_products[0]

    normalized_query = _normalize_text(
        query
    )

    best_name = _normalize_text(
        _product_name(best_product)
    )

    # Exact name always wins.
    if best_name == normalized_query:
        return (
            best_product,
            candidates,
        )

    # Unique strongest result.
    if len(best_products) == 1:
        return (
            best_product,
            candidates,
        )

    # Ambiguous.
    return (
        None,
        best_products,
    )


def _resolve_product_by_id(
    db: Session,
    product_id: Any,
) -> Any | None:
    """
    Product ID is authoritative when already resolved.

    Never use the LLM to fabricate an ID.
    """
    try:
        normalized_id = int(product_id)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if normalized_id <= 0:
        return None

    try:
        # Prefer the service if available.
        product = get_product(
            db=db,
            product_id=normalized_id,
        )

        if product is not None:
            return product

    except Exception as exc:
        print(
            "[PRODUCT BY ID] "
            f"{type(exc).__name__}: {exc}"
        )

    # Direct DB fallback.
    try:
        return (
            db.query(Product)
            .filter(
                Product.id == normalized_id
            )
            .first()
        )

    except Exception as exc:
        print(
            "[PRODUCT ID DB FALLBACK] "
            f"{type(exc).__name__}: {exc}"
        )

    return None


# =========================================================
# Graph State Helpers
# =========================================================

def _get_entities(
    state: GraphState,
) -> dict[str, Any]:
    return dict(
        state.get(
            "entities",
            {},
        )
        or {}
    )


def _get_selected_address_id(
    state: GraphState,
    entities: dict[str, Any],
) -> Any:
    """
    Frontend selection is authoritative.
    """
    selected_address_id = state.get(
        "selected_address_id"
    )

    if _has_value(
        selected_address_id
    ):
        return selected_address_id

    return entities.get(
        "address_id"
    )


def _get_payment_method(
    state: GraphState,
    entities: dict[str, Any],
) -> str | None:
    """
    Frontend payment selection is authoritative.
    """
    payment_method = state.get(
        "payment_method"
    )

    if payment_method is None:
        payment_method = entities.get(
            "payment_method"
        )

    if payment_method is None:
        return None

    normalized = (
        str(payment_method)
        .strip()
        .lower()
    )

    if normalized not in SUPPORTED_PAYMENT_METHODS:
        return None

    return normalized


def _normalize_positive_int(
    value: Any,
    field_name: str,
) -> tuple[int | None, str | None]:
    try:
        normalized = int(value)

    except (
        TypeError,
        ValueError,
    ):
        return (
            None,
            f"{field_name} must be a valid number.",
        )

    if normalized <= 0:
        return (
            None,
            f"{field_name} must be greater than zero.",
        )

    return (
        normalized,
        None,
    )


# =========================================================
# Tool Node
# =========================================================

def tool_node(
    state: GraphState,
    db: Session,
) -> GraphState:
    """
    Execute the backend operation selected by decision_node.

    The function always returns a GraphState update.
    Backend failures are converted into tool_result instead
    of crashing the LangGraph execution.
    """

    tool_name = state.get(
        "tool_name"
    )

    entities = _get_entities(
        state
    )

    user_id = state.get(
        "user_id"
    )

    if not tool_name:
        return {
            "tool_result": None,
        }

    print(
        "\n[TOOL NODE]"
        f"\n  tool_name = {tool_name!r}"
        f"\n  user_id   = {user_id!r}"
        f"\n  entities  = {entities}"
    )

    # =====================================================
    # SEARCH PRODUCTS
    # =====================================================

    if tool_name == "search_products":

        product_name = entities.get(
            "product_name"
        )

        if not _has_value(
            product_name
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Product name is required.",
                )
            }

        query = str(
            product_name
        ).strip()

        # IMPORTANT:
        # Do not rely only on search_products().
        # Resolve against the actual Product table too.
        try:
            matched_product, candidates = (
                _resolve_product(
                    db=db,
                    product_name=query,
                )
            )

            serialized = [
                _serialize_product(product)
                for product in candidates
            ]

            updated_entities = dict(
                entities
            )

            # If resolution found one authoritative match,
            # carry product_id forward for checkout.
            if matched_product is not None:
                resolved_id = _product_id(
                    matched_product
                )

                if resolved_id is not None:
                    updated_entities[
                        "product_id"
                    ] = int(resolved_id)

                    updated_entities[
                        "product_name"
                    ] = _product_name(
                        matched_product
                    )

            if not serialized:
                return {
                    "tool_result": _result(
                        False,
                        type="product_not_found",
                        error=(
                            f"No product found for "
                            f"'{query}'."
                        ),
                    ),
                    "entities": updated_entities,
                }

            return {
                "tool_result": _result(
                    True,
                    type="product_results",
                    products=serialized,
                    selected_product=(
                        _serialize_product(
                            matched_product
                        )
                        if matched_product is not None
                        else None
                    ),
                ),
                "entities": updated_entities,
            }

        except Exception as exc:
            print(
                "[TOOL search_products ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # GET PRODUCT
    # =====================================================

    if tool_name == "get_product":

        product_id = entities.get(
            "product_id"
        )

        if not _has_value(
            product_id
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Product ID is required.",
                )
            }

        try:
            product = _resolve_product_by_id(
                db=db,
                product_id=product_id,
            )

            if product is None:
                return {
                    "tool_result": _result(
                        False,
                        type="product_not_found",
                        error=(
                            f"Product {product_id} "
                            "does not exist."
                        ),
                    )
                }

            return {
                "tool_result": _result(
                    True,
                    type="product",
                    product=_serialize_product(
                        product
                    ),
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # CHECK PRODUCT AVAILABILITY
    # =====================================================

    if tool_name == "check_product_availability":

        product_id = entities.get(
            "product_id"
        )

        quantity = entities.get(
            "quantity"
        )

        if not _has_value(
            product_id
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Product ID is required.",
                )
            }

        normalized_quantity, quantity_error = (
            _normalize_positive_int(
                quantity,
                "Quantity",
            )
        )

        if quantity_error:
            return {
                "tool_result": _result(
                    False,
                    error=quantity_error,
                )
            }

        try:
            available = (
                check_product_availability(
                    db=db,
                    product_id=int(product_id),
                    quantity=normalized_quantity,
                )
            )

            product = _resolve_product_by_id(
                db=db,
                product_id=product_id,
            )

            return {
                "tool_result": _result(
                    True,
                    type="product_availability",
                    product=(
                        _serialize_product(product)
                        if product is not None
                        else None
                    ),
                    quantity=normalized_quantity,
                    available=bool(available),
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # LIST SAVED ADDRESSES
    # =====================================================

    if tool_name == "list_saved_addresses":

        if user_id is None:
            return {
                "tool_result": _result(
                    False,
                    type="address_selection",
                    error=(
                        "User ID is required "
                        "to load saved addresses."
                    ),
                )
            }

        try:
            addresses = get_user_addresses(
                db=db,
                user_id=int(user_id),
            )

            serialized_addresses = [
                _serialize_address(address)
                for address in (
                    addresses or []
                )
            ]

            return {
                "tool_result": _result(
                    True,
                    type="address_selection",
                    addresses=serialized_addresses,
                    allow_new=True,
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    type="address_selection",
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # LIST PAYMENT METHODS
    # =====================================================

    if tool_name == "list_payment_methods":

        return {
            "tool_result": _result(
                True,
                type="payment_selection",
                methods=[
                    {
                        "id": "upi",
                        "label": "UPI",
                        "description": (
                            "Pay instantly using UPI"
                        ),
                    },
                    {
                        "id": "cod",
                        "label": "Cash on Delivery",
                        "description": (
                            "Pay when your order arrives"
                        ),
                    },
                ],
            )
        }

    # =====================================================
    # CREATE ORDER
    # =====================================================

    if tool_name == "create_order":

        if user_id is None:
            return {
                "tool_result": _result(
                    False,
                    error="User ID is required.",
                )
            }

        # -------------------------------------------------
        # Product
        # -------------------------------------------------

        product_id = entities.get(
            "product_id"
        )

        product_name = entities.get(
            "product_name"
        )

        product = None

        # Product ID is authoritative if available.
        if _has_value(product_id):

            product = _resolve_product_by_id(
                db=db,
                product_id=product_id,
            )

            if product is None:
                return {
                    "tool_result": _result(
                        False,
                        type="product_not_found",
                        error=(
                            f"Product {product_id} "
                            "does not exist."
                        ),
                    )
                }

            # Normalize state to actual DB product.
            product_id = _product_id(
                product
            )

            product_name = _product_name(
                product
            )

        # Otherwise resolve the natural-language name.
        elif _has_value(product_name):

            product, candidates = (
                _resolve_product(
                    db=db,
                    product_name=str(
                        product_name
                    ),
                )
            )

            if product is None:

                if candidates:
                    return {
                        "tool_result": _result(
                            False,
                            type="product_selection",
                            error=(
                                "I found multiple "
                                "products matching "
                                "your request. "
                                "Please choose one."
                            ),
                            products=[
                                _serialize_product(
                                    candidate
                                )
                                for candidate in candidates
                            ],
                        )
                    }

                return {
                    "tool_result": _result(
                        False,
                        type="product_not_found",
                        error=(
                            f"No product found for "
                            f"'{product_name}'."
                        ),
                    )
                }

            product_id = _product_id(
                product
            )

            product_name = _product_name(
                product
            )

        else:
            return {
                "tool_result": _result(
                    False,
                    error="Product is required.",
                )
            }

        if product_id is None:
            return {
                "tool_result": _result(
                    False,
                    error=(
                        "The selected product "
                        "does not have a valid ID."
                    ),
                )
            }

        # -------------------------------------------------
        # Quantity
        # -------------------------------------------------

        quantity, quantity_error = (
            _normalize_positive_int(
                entities.get("quantity"),
                "Quantity",
            )
        )

        if quantity_error:
            return {
                "tool_result": _result(
                    False,
                    error=quantity_error,
                )
            }

        # -------------------------------------------------
        # Address
        # -------------------------------------------------

        address_id = _get_selected_address_id(
            state,
            entities,
        )

        if not _has_value(
            address_id
        ):
            return {
                "tool_result": _result(
                    False,
                    type="address_selection",
                    error=(
                        "Please select a saved "
                        "delivery address before "
                        "placing the order."
                    ),
                )
            }

        try:
            address_id = int(
                address_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "tool_result": _result(
                    False,
                    type="address_selection",
                    error="Invalid delivery address.",
                )
            }

        if address_id <= 0:
            return {
                "tool_result": _result(
                    False,
                    type="address_selection",
                    error="Invalid delivery address.",
                )
            }

        # -------------------------------------------------
        # Payment
        # -------------------------------------------------

        payment_method = _get_payment_method(
            state,
            entities,
        )

        if payment_method is None:
            return {
                "tool_result": _result(
                    False,
                    type="payment_selection",
                    error=(
                        "Please select a payment "
                        "method before placing "
                        "the order."
                    ),
                )
            }

        # -------------------------------------------------
        # Availability
        # -------------------------------------------------

        try:
            available = (
                check_product_availability(
                    db=db,
                    product_id=int(product_id),
                    quantity=quantity,
                )
            )

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

        if not available:
            return {
                "tool_result": _result(
                    False,
                    type="product_unavailable",
                    error=(
                        f"'{product_name}' "
                        "is not available in the "
                        "requested quantity."
                    ),
                    product=_serialize_product(
                        product
                    ),
                    quantity=quantity,
                )
            }

        # -------------------------------------------------
        # Create Order
        # -------------------------------------------------

        try:
            order = create_order(
                db=db,
                user_id=int(user_id),
                address_id=address_id,
                items=[
                    {
                        "product_id": int(
                            product_id
                        ),
                        "quantity": quantity,
                    }
                ],
                payment_method=payment_method,
            )

        except ValueError as exc:
            return {
                "tool_result": _result(
                    False,
                    error=str(exc),
                )
            }

        except Exception as exc:
            print(
                "[TOOL create_order ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

        # Backend is authoritative.
        created_order_id = getattr(
            order,
            "id",
            None,
        )

        if created_order_id is None:
            return {
                "tool_result": _result(
                    False,
                    error=(
                        "Order creation returned "
                        "no order ID."
                    ),
                )
            }

        updated_entities = dict(
            entities
        )

        updated_entities[
            "product_id"
        ] = int(product_id)

        updated_entities[
            "product_name"
        ] = product_name

        updated_entities[
            "quantity"
        ] = quantity

        updated_entities[
            "address_id"
        ] = address_id

        updated_entities[
            "payment_method"
        ] = payment_method

        return {
            "tool_result": _result(
                True,
                type="order_success",
                order_id=created_order_id,
                total_amount=getattr(
                    order,
                    "total_amount",
                    None,
                ),
                status=getattr(
                    order,
                    "status",
                    None,
                ),
                product_id=int(
                    product_id
                ),
                product_name=product_name,
                quantity=quantity,
                address_id=address_id,
                payment_method=payment_method,
            ),
            "order_id": created_order_id,
            "entities": updated_entities,
            "awaiting_order_tracking_confirmation": True,
        }

    # =====================================================
    # GET ORDER
    # =====================================================

    if tool_name == "get_order":

        order_id = entities.get(
            "order_id"
        )

        if not _has_value(
            order_id
        ):
            order_id = state.get(
                "order_id"
            )

        if not _has_value(
            order_id
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Order ID is required.",
                )
            }

        try:
            order_id = int(
                order_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Invalid order ID.",
                )
            }

        try:
            order = get_order(
                db=db,
                order_id=order_id,
            )

            if order is None:
                return {
                    "tool_result": _result(
                        False,
                        error=(
                            f"Order {order_id} "
                            "does not exist."
                        ),
                    )
                }

            if (
                user_id is not None
                and getattr(
                    order,
                    "user_id",
                    None,
                ) != int(user_id)
            ):
                return {
                    "tool_result": _result(
                        False,
                        error=(
                            "You are not authorized "
                            "to view this order."
                        ),
                    )
                }

            return {
                "tool_result": _result(
                    True,
                    type="order",
                    order=_serialize_order(
                        order
                    ),
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # TRACK ORDER
    # =====================================================

    if tool_name == "track_order":

        order_id = entities.get(
            "order_id"
        )

        if not _has_value(
            order_id
        ):
            order_id = state.get(
                "order_id"
            )

        if not _has_value(
            order_id
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Order ID is required.",
                )
            }

        try:
            order_id = int(
                order_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Invalid order ID.",
                )
            }

        try:
            order = get_order(
                db=db,
                order_id=order_id,
            )

            if order is None:
                return {
                    "tool_result": _result(
                        False,
                        error=(
                            f"Order {order_id} "
                            "does not exist."
                        ),
                    )
                }

            if (
                user_id is not None
                and getattr(
                    order,
                    "user_id",
                    None,
                ) != int(user_id)
            ):
                return {
                    "tool_result": _result(
                        False,
                        error=(
                            "You are not authorized "
                            "to view this order."
                        ),
                    )
                }

            return {
                "tool_result": _result(
                    True,
                    type="tracking",
                    order_id=order.id,
                    status=getattr(
                        order,
                        "status",
                        None,
                    ),
                    payment_status=getattr(
                        order,
                        "payment_status",
                        None,
                    ),
                    total_amount=getattr(
                        order,
                        "total_amount",
                        None,
                    ),
                ),
                "awaiting_order_tracking_confirmation": False,
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # GET USER ORDERS
    # =====================================================

    if tool_name == "get_user_orders":

        if user_id is None:
            return {
                "tool_result": _result(
                    False,
                    error="User ID is required.",
                )
            }

        try:
            orders = get_user_orders(
                db=db,
                user_id=int(user_id),
            )

            return {
                "tool_result": _result(
                    True,
                    type="order_list",
                    orders=[
                        _serialize_order(order)
                        for order in (
                            orders or []
                        )
                    ],
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # CANCEL ORDER
    # =====================================================

    if tool_name == "cancel_order":

        if user_id is None:
            return {
                "tool_result": _result(
                    False,
                    error="User ID is required.",
                )
            }

        order_id = entities.get(
            "order_id"
        )

        if not _has_value(
            order_id
        ):
            order_id = state.get(
                "order_id"
            )

        if not _has_value(
            order_id
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Order ID is required.",
                )
            }

        try:
            order_id = int(
                order_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Invalid order ID.",
                )
            }

        try:
            order = cancel_order(
                db=db,
                order_id=order_id,
                user_id=int(user_id),
            )

            return {
                "tool_result": _result(
                    True,
                    type="order_cancelled",
                    order_id=order.id,
                    status=getattr(
                        order,
                        "status",
                        None,
                    ),
                ),
                "awaiting_order_tracking_confirmation": False,
            }

        except ValueError as exc:
            return {
                "tool_result": _result(
                    False,
                    error=str(exc),
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # CREATE SUPPORT TICKET
    # =====================================================

    if tool_name == "create_support_ticket":

        if user_id is None:
            return {
                "tool_result": _result(
                    False,
                    error="User ID is required.",
                )
            }

        order_id = entities.get(
            "order_id"
        )

        message = (
            state.get(
                "message",
                "",
            )
            or ""
        ).strip()

        if not message:
            return {
                "tool_result": _result(
                    False,
                    error=(
                        "Please describe the issue "
                        "you need help with."
                    ),
                )
            }

        try:
            ticket = create_ticket(
                db=db,
                user_id=int(user_id),
                subject="BuyQK Customer Support",
                description=message,
                order_id=order_id,
            )

            return {
                "tool_result": _result(
                    True,
                    type="support_ticket",
                    ticket_id=ticket.id,
                    status=getattr(
                        ticket,
                        "status",
                        None,
                    ),
                )
            }

        except ValueError as exc:
            return {
                "tool_result": _result(
                    False,
                    error=str(exc),
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # GET TICKET
    # =====================================================

    if tool_name == "get_ticket":

        ticket_id = entities.get(
            "ticket_id"
        )

        if not _has_value(
            ticket_id
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Ticket ID is required.",
                )
            }

        try:
            ticket_id = int(
                ticket_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "tool_result": _result(
                    False,
                    error="Invalid ticket ID.",
                )
            }

        try:
            ticket = get_ticket(
                db=db,
                ticket_id=ticket_id,
            )

            if ticket is None:
                return {
                    "tool_result": _result(
                        False,
                        error=(
                            f"Ticket {ticket_id} "
                            "does not exist."
                        ),
                    )
                }

            if (
                user_id is not None
                and getattr(
                    ticket,
                    "user_id",
                    None,
                ) != int(user_id)
            ):
                return {
                    "tool_result": _result(
                        False,
                        error=(
                            "You are not authorized "
                            "to view this ticket."
                        ),
                    )
                }

            return {
                "tool_result": _result(
                    True,
                    type="support_ticket",
                    ticket=_serialize_ticket(
                        ticket
                    ),
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # GET USER TICKETS
    # =====================================================

    if tool_name == "get_user_tickets":

        if user_id is None:
            return {
                "tool_result": _result(
                    False,
                    error="User ID is required.",
                )
            }

        try:
            tickets = get_user_tickets(
                db=db,
                user_id=int(user_id),
            )

            return {
                "tool_result": _result(
                    True,
                    type="support_ticket_list",
                    tickets=[
                        _serialize_ticket(ticket)
                        for ticket in (
                            tickets or []
                        )
                    ],
                )
            }

        except Exception as exc:
            return {
                "tool_result": _result(
                    False,
                    error=_safe_error(exc),
                )
            }

    # =====================================================
    # UNKNOWN TOOL
    # =====================================================

    return {
        "tool_result": _result(
            False,
            error=(
                f"Unsupported tool: {tool_name}"
            ),
        )
    }