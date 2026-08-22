# =========================================================
# BuyQK AI - Tool Node
# =========================================================
#
# Purpose:
#   Execute the backend operation selected by decision_node.
#
# Responsibilities:
#
#   - Read tool_name from GraphState
#   - Read AI-extracted entities
#   - Resolve products against database
#   - Validate quantity
#   - Validate address ownership
#   - Validate payment method
#   - Check product availability
#   - Create orders
#   - Generate / forward bill
#   - Track orders
#   - Cancel orders
#   - Create support tickets
#   - Execute CartService operations
#   - Prepare / validate Cart checkout
#   - Return structured tool_result
#
# IMPORTANT:
#
#   AI understands the user's natural language.
#
#   DATABASE is authoritative for:
#
#       product_id
#       product_name
#       price
#       stock
#       availability
#       address ownership
#       order_id
#       order status
#       payment
#
#   The AI NEVER invents these values.
#
# =========================================================


from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ai_engine.graph.state import GraphState

from backend.models.product import Product

from backend.services.product_service import (
    search_products,
    check_product_availability,
)

from backend.services.order_service import (
    create_order,
    get_order,
    cancel_order,
    build_order_bill,
    get_available_payment_methods,
)

from backend.services.support_service import (
    create_ticket,
)

from backend.services.address_service import (
    get_user_addresses,
)

from backend.services.cart_service import (
    add_item as cart_add_item,
    remove_item as cart_remove_item,
    remove_product as cart_remove_product,
    update_quantity as cart_update_quantity,
    update_item_quantity as cart_update_item_quantity,
    clear_cart as cart_clear_cart,
    get_cart as cart_get_cart,
    calculate_cart as cart_calculate_cart,
    commit_cart,
    CartServiceError,
    ProductNotFoundError,
    ProductUnavailableError,
    InsufficientStockError,
    CartItemNotFoundError,
    InvalidQuantityError,
)


# =========================================================
# Constants
# =========================================================

# =========================================================
# Generic Helpers
# =========================================================


def _has_value(
    value: Any,
) -> bool:
    """
    Return True when a value is actually present.
    """

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _normalize_text(
    value: Any,
) -> str:
    """
    Normalize text for reliable product matching.

    Examples:

        "Amul   Milk"
            ->
        "amul milk"

        "AMUL-MILK"
            ->
        "amul milk"
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


def _tokenize(
    value: Any,
) -> list[str]:
    """
    Convert text into normalized tokens.
    """

    normalized = _normalize_text(
        value
    )

    if not normalized:
        return []

    return normalized.split()


# =========================================================
# Product Helpers
# =========================================================


def _product_value(
    product: Any,
    field: str,
) -> Any:
    """
    Safely read a field from:

        - SQLAlchemy Product
        - dictionary
    """

    if isinstance(
        product,
        dict,
    ):
        return product.get(
            field
        )

    return getattr(
        product,
        field,
        None,
    )


def _product_id(
    product: Any,
) -> Any:
    return _product_value(
        product,
        "id",
    )


def _product_name(
    product: Any,
) -> str:
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
    Convert product into JSON-safe data.
    """

    return {
        "id": _product_value(
            product,
            "id",
        ),
        "name": _product_value(
            product,
            "name",
        ),
        "description": _product_value(
            product,
            "description",
        ),
        "brand": _product_value(
            product,
            "brand",
        ),
        "price": _product_value(
            product,
            "price",
        ),
        "stock": _product_value(
            product,
            "stock",
        ),
        "image_url": _product_value(
            product,
            "image_url",
        ),
        "is_available": _product_value(
            product,
            "is_available",
        ),
        "merchant_id": _product_value(
            product,
            "merchant_id",
        ),
        "category_id": _product_value(
            product,
            "category_id",
        ),
    }


def _deduplicate_products(
    products: list[Any],
) -> list[Any]:
    """
    Remove duplicate products.
    """

    result = []

    seen_ids = set()
    seen_names = set()

    for product in products:

        product_id = _product_id(
            product
        )

        if product_id is not None:

            if product_id in seen_ids:
                continue

            seen_ids.add(
                product_id
            )

        else:

            name = _normalize_text(
                _product_name(
                    product
                )
            )

            if name and name in seen_names:
                continue

            if name:
                seen_names.add(
                    name
                )

        result.append(
            product
        )

    return result


# =========================================================
# Product Scoring
# =========================================================


def _score_product(
    product: Any,
    query: str,
) -> int:
    """
    Score product against user/AI extracted query.

    Priority:

        Exact name
            ↓
        Full phrase
            ↓
        All tokens
            ↓
        Partial tokens
    """

    product_name = _normalize_text(
        _product_name(
            product
        )
    )

    normalized_query = _normalize_text(
        query
    )

    if not product_name:
        return 0

    if not normalized_query:
        return 0

    query_tokens = _tokenize(
        normalized_query
    )

    product_tokens = set(
        _tokenize(
            product_name
        )
    )

    if not query_tokens:
        return 0

    # Exact match
    if product_name == normalized_query:
        return 10000

    score = 0

    # Full phrase
    if normalized_query in product_name:
        score += 5000

    matched_tokens = 0

    for token in query_tokens:

        if token in product_tokens:

            matched_tokens += 1
            score += 1000

        elif token in product_name:

            matched_tokens += 1
            score += 300

    # All tokens matched
    if matched_tokens == len(
        query_tokens
    ):
        score += 2000

    return score


# =========================================================
# Resolve Product
# =========================================================


def _resolve_product(
    db: Session,
    product_name: str,
) -> tuple[Any | None, list[Any]]:
    """
    Resolve a product using the actual Product table.

    The AI may say:

        "amul milk"
        "Amul Milk"
        "amul"
        "milk"

    This function resolves the request against the
    database.

    IMPORTANT:

    The LLM does NOT decide the product ID.

    The database decides the authoritative product.
    """

    if db is None:
        return None, []

    if not _has_value(
        product_name
    ):
        return None, []

    query = str(
        product_name
    ).strip()

    normalized_query = _normalize_text(
        query
    )

    if not normalized_query:
        return None, []

    # =====================================================
    # Load authoritative catalog
    # =====================================================

    try:

        all_products = (
            db.query(Product)
            .all()
        )

    except Exception as exc:

        print(
            "[PRODUCT DB ERROR]",
            type(exc).__name__,
            str(exc),
        )

        return None, []

    if not all_products:

        print(
            "[PRODUCT RESOLVER] "
            "Product table is empty."
        )

        return None, []

    # =====================================================
    # Exact match
    # =====================================================

    exact_matches = []

    for product in all_products:

        database_name = _normalize_text(
            _product_name(
                product
            )
        )

        if database_name == normalized_query:

            exact_matches.append(
                product
            )

    if exact_matches:

        product = exact_matches[0]

        print(
            "[PRODUCT RESOLVED - EXACT]",
            f"'{query}' ->",
            f"id={_product_id(product)}",
            f"name='{_product_name(product)}'",
        )

        return (
            product,
            exact_matches,
        )

    # =====================================================
    # Phrase match
    # =====================================================

    phrase_matches = []

    for product in all_products:

        database_name = _normalize_text(
            _product_name(
                product
            )
        )

        if (
            normalized_query in database_name
            or database_name in normalized_query
        ):

            phrase_matches.append(
                product
            )

    phrase_matches = _deduplicate_products(
        phrase_matches
    )

    # =====================================================
    # Token match
    # =====================================================

    query_tokens = set(
        _tokenize(
            normalized_query
        )
    )

    token_matches = []

    if query_tokens:

        for product in all_products:

            database_name = _normalize_text(
                _product_name(
                    product
                )
            )

            product_tokens = set(
                _tokenize(
                    database_name
                )
            )

            if query_tokens.issubset(
                product_tokens
            ):

                token_matches.append(
                    product
                )

    token_matches = _deduplicate_products(
        token_matches
    )

    # =====================================================
    # Supplementary service search
    # =====================================================

    service_candidates = []

    try:

        results = search_products(
            db=db,
            query=query,
        )

        if results:

            if isinstance(
                results,
                list,
            ):

                service_candidates.extend(
                    results
                )

            else:

                service_candidates.append(
                    results
                )

    except Exception as exc:

        print(
            "[PRODUCT SERVICE SEARCH ERROR]",
            type(exc).__name__,
            str(exc),
        )

    # Search meaningful tokens too
    for token in _tokenize(
        query
    ):

        if len(token) < 2:
            continue

        try:

            results = search_products(
                db=db,
                query=token,
            )

            if not results:
                continue

            if isinstance(
                results,
                list,
            ):

                service_candidates.extend(
                    results
                )

            else:

                service_candidates.append(
                    results
                )

        except Exception:
            continue

    # =====================================================
    # Combine candidates
    # =====================================================

    candidates = _deduplicate_products(
        exact_matches
        + phrase_matches
        + token_matches
        + service_candidates
    )

    if not candidates:

        print(
            "[PRODUCT NOT FOUND]",
            f"'{query}'",
        )

        return None, []

    # =====================================================
    # Score
    # =====================================================

    scored = []

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

    # =====================================================
    # Unique best match
    # =====================================================

    if len(best_products) == 1:

        product = best_products[0]

        print(
            "[PRODUCT RESOLVED]",
            f"'{query}' ->",
            f"id={_product_id(product)}",
            f"name='{_product_name(product)}'",
            f"score={best_score}",
        )

        return (
            product,
            candidates,
        )

    # =====================================================
    # Ambiguous
    # =====================================================

    print(
        "[PRODUCT AMBIGUOUS]",
        f"'{query}'",
    )

    return (
        None,
        best_products,
    )


# =========================================================
# Address Helpers
# =========================================================


def _get_address_id(
    state: GraphState,
    entities: dict[str, Any],
) -> Any:
    """
    Address priority:

        1. selected_address_id from GraphState
        2. address_id from AI entities
    """

    address_id = state.get(
        "selected_address_id"
    )

    if address_id is not None:
        return address_id

    return entities.get(
        "address_id"
    )


def _validate_address(
    db: Session,
    user_id: int,
    address_id: Any,
) -> tuple[bool, str | None]:
    """
    Validate address ownership.
    """

    if address_id is None:

        return (
            False,
            "Please select a saved delivery address before placing the order.",
        )

    try:

        address_id = int(
            address_id
        )

    except (
        TypeError,
        ValueError,
    ):

        return (
            False,
            "Invalid delivery address.",
        )

    if address_id <= 0:

        return (
            False,
            "Invalid delivery address.",
        )

    try:

        addresses = get_user_addresses(
            db=db,
            user_id=user_id,
        )

    except Exception as exc:

        print(
            "[ADDRESS VALIDATION ERROR]",
            type(exc).__name__,
            str(exc),
        )

        return (
            False,
            "Unable to validate the selected delivery address.",
        )

    for address in addresses:

        current_id = getattr(
            address,
            "id",
            None,
        )

        if current_id is None:
            continue

        try:

            if int(
                current_id
            ) == address_id:

                return (
                    True,
                    None,
                )

        except (
            TypeError,
            ValueError,
        ):

            continue

    return (
        False,
        "The selected delivery address does not belong to this user.",
    )


# =========================================================
# Payment Helper
# =========================================================


def _get_payment_method(
    state: GraphState,
    entities: dict[str, Any],
) -> str | None:
    """
    Read the payment method understood by the AI/frontend.

    The tool node does not maintain a business-method allowlist
    or alias table. The backend payment service is authoritative.
    """

    payment_method = state.get(
        "payment_method"
    )

    if payment_method is None:
        payment_method = state.get(
            "selected_payment_method"
        )

    if payment_method is None:
        payment_method = entities.get(
            "payment_method"
        )

    if payment_method is None:
        return None

    normalized = str(
        payment_method
    ).strip().casefold()

    return normalized or None


# =========================================================
# Address Serialization
# =========================================================


def _serialize_address(
    address: Any,
) -> dict[str, Any]:

    return {
        "id": getattr(
            address,
            "id",
            None,
        ),
        "label": getattr(
            address,
            "label",
            None,
        ),
        "address": getattr(
            address,
            "address",
            None,
        ),
        "address_line1": getattr(
            address,
            "address_line1",
            None,
        ),
        "address_line2": getattr(
            address,
            "address_line2",
            None,
        ),
        "city": getattr(
            address,
            "city",
            None,
        ),
        "state": getattr(
            address,
            "state",
            None,
        ),
        "postal_code": getattr(
            address,
            "postal_code",
            None,
        ),
        "pincode": getattr(
            address,
            "pincode",
            None,
        ),
    }


# =========================================================
# Quantity Helper
# =========================================================


def _normalize_quantity(
    quantity: Any,
) -> int | None:
    """
    Convert AI-extracted quantity into integer.
    """

    if quantity is None:
        return None

    if isinstance(
        quantity,
        bool,
    ):
        return None

    try:

        quantity = int(
            quantity
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    if quantity <= 0:
        return None

    return quantity


# =========================================================
# Order Items From AI Entities
# =========================================================


def _extract_order_items(
    entities: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert AI-extracted shopping information into the
    backend order_items format.

    Supported AI structures:

    Single product:

        {
            "product_name": "Maggi",
            "quantity": 3
        }

    Multiple products:

        {
            "items": [
                {
                    "product_name": "Maggi",
                    "quantity": 3
                },
                {
                    "product_name": "Amul Milk",
                    "quantity": 2
                }
            ]
        }

    Also accepts:

        cart_items

    The AI is responsible for understanding the user's
    natural-language request.

    This function only normalizes the extracted structure.
    """

    raw_items = entities.get(
        "items"
    )

    if raw_items is None:

        raw_items = entities.get(
            "cart_items"
        )

    # =====================================================
    # Multi-item request
    # =====================================================

    if isinstance(
        raw_items,
        list,
    ):

        normalized_items = []

        for item in raw_items:

            if not isinstance(
                item,
                dict,
            ):
                continue

            product_id = item.get(
                "product_id"
            )

            product_name = item.get(
                "product_name"
            )

            quantity = _normalize_quantity(
                item.get(
                    "quantity"
                )
            )

            if quantity is None:
                continue

            if (
                product_id is None
                and not _has_value(
                    product_name
                )
            ):
                continue

            order_item = {
                "quantity": quantity,
            }

            if product_id is not None:
                order_item[
                    "product_id"
                ] = product_id

            else:
                order_item[
                    "product_name"
                ] = str(
                    product_name
                ).strip()

            normalized_items.append(
                order_item
            )

        return normalized_items

    # =====================================================
    # Single-item request
    # =====================================================

    product_id = entities.get(
        "product_id"
    )

    product_name = entities.get(
        "product_name"
    )

    quantity = _normalize_quantity(
        entities.get(
            "quantity"
        )
    )

    if quantity is None:
        return []

    if (
        product_id is None
        and not _has_value(
            product_name
        )
    ):
        return []

    item = {
        "quantity": quantity,
    }

    if product_id is not None:

        item[
            "product_id"
        ] = product_id

    else:

        item[
            "product_name"
        ] = str(
            product_name
        ).strip()

    return [
        item
    ]


# =========================================================
# Bill Serialization
# =========================================================


def _serialize_bill(
    bill: Any,
) -> dict[str, Any] | None:
    """
    Serialize the authoritative bill generated by order_service.py.

    This function NEVER calculates prices. Billing remains the
    responsibility of the backend order service.
    """

    if not isinstance(bill, dict):
        return None

    return {
        "order_id": bill.get("order_id"),
        "items": bill.get("items", []),
        "subtotal": bill.get("subtotal", 0),
        "delivery_charge": bill.get("delivery_charge", 0),
        "discount": bill.get("discount", 0),
        "tax": bill.get("tax", 0),
        "total": bill.get("total", 0),
        "currency": bill.get("currency", "INR"),
        "payment_method": bill.get("payment_method"),
    }


# =========================================================
# Cart Helpers
# =========================================================


def _resolve_cart_product(
    db: Session,
    entities: dict[str, Any],
) -> tuple[int | None, str | None, list[Any]]:
    """
    Resolve the product required by a Cart operation.

    Priority:
        1. A backend-resolved product_id already present in entities.
        2. A natural-language product_name resolved against Product.

    The CartService remains authoritative for availability and stock.
    This helper only resolves the product identity required by the
    CartService API.
    """

    product_id = entities.get("product_id")

    # -----------------------------------------------------
    # Existing authoritative product ID
    # -----------------------------------------------------

    if product_id is not None:
        try:
            normalized_id = int(product_id)
        except (TypeError, ValueError):
            return None, "Invalid product ID.", []

        if normalized_id <= 0:
            return None, "Invalid product ID.", []

        product = (
            db.query(Product)
            .filter(Product.id == normalized_id)
            .first()
        )

        if product is None:
            return (
                None,
                f"Product {normalized_id} does not exist.",
                [],
            )

        return (
            normalized_id,
            _product_name(product),
            [],
        )

    # -----------------------------------------------------
    # Natural-language product name
    # -----------------------------------------------------

    product_name = entities.get("product_name")

    if not _has_value(product_name):
        return (
            None,
            "Please tell me which product you want to modify.",
            [],
        )

    product, candidates = _resolve_product(
        db=db,
        product_name=str(product_name).strip(),
    )

    if product is None:
        if candidates:
            return (
                None,
                (
                    f"I found multiple products matching "
                    f"'{product_name}'. Please choose one."
                ),
                candidates,
            )

        return (
            None,
            f"No product found for '{product_name}'.",
            [],
        )

    resolved_product_id = _product_id(product)

    try:
        resolved_product_id = int(resolved_product_id)
    except (TypeError, ValueError):
        return (
            None,
            "The selected product has an invalid product ID.",
            [],
        )

    if resolved_product_id <= 0:
        return (
            None,
            "The selected product has an invalid product ID.",
            [],
        )

    return (
        resolved_product_id,
        _product_name(product),
        [],
    )


def _cart_state_from_result(
    cart: Any,
    *,
    checkout_ready: bool | None = None,
) -> dict[str, Any]:
    """
    Convert the authoritative CartService response into the GraphState
    fields consumed by Planner/Response/frontend integration.

    No cart calculations are performed here.
    """

    if not isinstance(cart, dict):
        return {}

    summary = cart.get("summary")
    items = cart.get("items")

    result: dict[str, Any] = {
        "cart_id": cart.get("cart_id"),
        "cart_status": cart.get("status"),
        "cart_items": items if isinstance(items, list) else [],
        "cart_summary": summary,
    }

    if checkout_ready is not None:
        result["cart_checkout_ready"] = checkout_ready

    return result


def _cart_tool_error(
    *,
    action: str,
    error: str,
    candidates: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Build a consistent Cart tool error response.
    """

    result: dict[str, Any] = {
        "success": False,
        "type": action,
        "error": error,
    }

    if candidates:
        result["products"] = [
            _serialize_product(candidate)
            for candidate in candidates
        ]

    return result


def _execute_cart_mutation(
    db: Session,
    user_id: int,
    tool_name: str,
    entities: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Execute one Cart mutation through CartService.

    IMPORTANT:
        No Cart business rules are implemented here.
        Product identity is resolved here because CartService accepts
        product_id, while the AI may provide product_name.

    Returns:
        (tool_result, GraphState updates)
    """

    # -----------------------------------------------------
    # Validate user
    # -----------------------------------------------------

    if user_id is None:
        return (
            _cart_tool_error(
                action=tool_name,
                error="User ID is required.",
            ),
            {},
        )

    try:
        normalized_user_id = int(user_id)
    except (TypeError, ValueError):
        return (
            _cart_tool_error(
                action=tool_name,
                error="Invalid user ID.",
            ),
            {},
        )

    if normalized_user_id <= 0:
        return (
            _cart_tool_error(
                action=tool_name,
                error="Invalid user ID.",
            ),
            {},
        )

    # -----------------------------------------------------
    # Resolve product for product-based operations
    # -----------------------------------------------------

    if tool_name in {
        "add_to_cart",
        "remove_from_cart",
        "update_cart_item",
    }:
        (
            product_id,
            resolved_product_name,
            candidates,
        ) = _resolve_cart_product(
            db=db,
            entities=entities,
        )

        if product_id is None:
            return (
                _cart_tool_error(
                    action=tool_name,
                    error=(
                        "Unable to resolve the requested product."
                    )
                    if not candidates
                    else (
                        f"I found multiple products matching "
                        f"'{entities.get('product_name')}'. "
                        "Please choose one."
                    ),
                    candidates=candidates,
                ),
                {},
            )

    else:
        product_id = None
        resolved_product_name = None

    # -----------------------------------------------------
    # ADD
    # -----------------------------------------------------

    if tool_name == "add_to_cart":

        quantity = _normalize_quantity(
            entities.get("quantity")
        )

        if quantity is None:
            return (
                _cart_tool_error(
                    action="add_to_cart",
                    error="Quantity must be a positive number.",
                ),
                {},
            )

        try:
            cart = cart_add_item(
                db=db,
                user_id=normalized_user_id,
                product_id=product_id,
                quantity=quantity,
            )

            # CartService intentionally leaves transaction ownership
            # to its caller. Commit only after the service succeeds.
            commit_cart(db)

        except (
            ProductNotFoundError,
            ProductUnavailableError,
            InsufficientStockError,
            InvalidQuantityError,
            CartServiceError,
            ValueError,
        ) as exc:
            return (
                _cart_tool_error(
                    action="add_to_cart",
                    error=str(exc),
                ),
                {},
            )
        except Exception as exc:
            print(
                "[TOOL add_to_cart ERROR]",
                type(exc).__name__,
                str(exc),
            )
            return (
                _cart_tool_error(
                    action="add_to_cart",
                    error=(
                        "I could not add the product to your cart "
                        "because of a backend error."
                    ),
                ),
                {},
            )

        updates = _cart_state_from_result(
            cart,
            checkout_ready=bool(cart.get("items")),
        )

        updates["entities"] = {
            **entities,
            "cart_action": None,
        }
        
        # Clear the added product so next cart action starts fresh
        updates["entities"].pop("product_id", None)
        updates["entities"].pop("product_name", None)
        updates["entities"].pop("quantity", None)

        return (
            {
                "success": True,
                "type": "cart_add",
                "action": "add_to_cart",
                "cart": cart,
                "cart_id": cart.get("cart_id"),
                "items": cart.get("items", []),
                "summary": cart.get("summary"),
            },
            updates,
        )

    # -----------------------------------------------------
    # REMOVE BY PRODUCT
    # -----------------------------------------------------

    if tool_name == "remove_from_cart":

        try:
            cart = cart_remove_product(
                db=db,
                user_id=normalized_user_id,
                product_id=product_id,
            )
            commit_cart(db)

        except (
            CartItemNotFoundError,
            ProductNotFoundError,
            ProductUnavailableError,
            CartServiceError,
            ValueError,
        ) as exc:
            return (
                _cart_tool_error(
                    action="remove_from_cart",
                    error=str(exc),
                ),
                {},
            )
        except Exception as exc:
            print(
                "[TOOL remove_from_cart ERROR]",
                type(exc).__name__,
                str(exc),
            )
            return (
                _cart_tool_error(
                    action="remove_from_cart",
                    error=(
                        "I could not remove the product from your "
                        "cart because of a backend error."
                    ),
                ),
                {},
            )

        updates = _cart_state_from_result(
            cart,
            checkout_ready=bool(cart.get("items")),
        )

        updates["entities"] = {
            **entities,
            "cart_action": None,
        }
        updates["entities"].pop("product_id", None)
        updates["entities"].pop("product_name", None)

        return (
            {
                "success": True,
                "type": "cart_remove",
                "action": "remove_from_cart",
                "cart": cart,
                "cart_id": cart.get("cart_id"),
                "items": cart.get("items", []),
                "summary": cart.get("summary"),
            },
            updates,
        )

    # -----------------------------------------------------
    # UPDATE QUANTITY BY PRODUCT
    # -----------------------------------------------------

    if tool_name == "update_cart_item":

        quantity = _normalize_quantity(
            entities.get("quantity")
        )

        if quantity is None:
            return (
                _cart_tool_error(
                    action="update_cart_item",
                    error="Quantity must be a positive number.",
                ),
                {},
            )

        try:
            cart = cart_update_item_quantity(
                db=db,
                user_id=normalized_user_id,
                product_id=product_id,
                quantity=quantity,
            )
            commit_cart(db)

        except (
            CartItemNotFoundError,
            ProductNotFoundError,
            ProductUnavailableError,
            InsufficientStockError,
            InvalidQuantityError,
            CartServiceError,
            ValueError,
        ) as exc:
            return (
                _cart_tool_error(
                    action="update_cart_item",
                    error=str(exc),
                ),
                {},
            )
        except Exception as exc:
            print(
                "[TOOL update_cart_item ERROR]",
                type(exc).__name__,
                str(exc),
            )
            return (
                _cart_tool_error(
                    action="update_cart_item",
                    error=(
                        "I could not update the cart item because "
                        "of a backend error."
                    ),
                ),
                {},
            )

        updates = _cart_state_from_result(
            cart,
            checkout_ready=bool(cart.get("items")),
        )

        updates["entities"] = {
            **entities,
            "cart_action": None,
        }
        updates["entities"].pop("product_id", None)
        updates["entities"].pop("product_name", None)
        updates["entities"].pop("quantity", None)

        return (
            {
                "success": True,
                "type": "cart_update",
                "action": "update_cart_item",
                "cart": cart,
                "cart_id": cart.get("cart_id"),
                "items": cart.get("items", []),
                "summary": cart.get("summary"),
            },
            updates,
        )

    # -----------------------------------------------------
    # CLEAR
    # -----------------------------------------------------

    if tool_name == "clear_cart":

        try:
            cart = cart_clear_cart(
                db=db,
                user_id=normalized_user_id,
            )
            commit_cart(db)

        except (
            CartServiceError,
            ValueError,
        ) as exc:
            return (
                _cart_tool_error(
                    action="clear_cart",
                    error=str(exc),
                ),
                {},
            )
        except Exception as exc:
            print(
                "[TOOL clear_cart ERROR]",
                type(exc).__name__,
                str(exc),
            )
            return (
                _cart_tool_error(
                    action="clear_cart",
                    error=(
                        "I could not clear your cart because "
                        "of a backend error."
                    ),
                ),
                {},
            )

        updates = _cart_state_from_result(
            cart,
            checkout_ready=False,
        )

        return (
            {
                "success": True,
                "type": "cart_clear",
                "action": "clear_cart",
                "cart": cart,
                "cart_id": cart.get("cart_id"),
                "items": cart.get("items", []),
                "summary": cart.get("summary"),
            },
            updates,
        )

    return (
        _cart_tool_error(
            action=tool_name,
            error=f"Unsupported Cart mutation: {tool_name}.",
        ),
        {},
    )


# =========================================================
# Tool Node
# =========================================================


def tool_node(
    state: GraphState,
    db: Session,
) -> GraphState:
    """
    Execute the tool selected by decision_node.

    The AI determines WHAT the user wants.

    The tool node performs the authoritative backend
    operation.

    The response AI receives the complete structured
    result through tool_result.
    """

    # =====================================================
    # Read State
    # =====================================================

    tool_name = state.get(
        "tool_name"
    )

    entities = (
        state.get(
            "entities",
            {},
        )
        or {}
    )

    updated_entities = dict(
        entities
    )

    user_id = state.get(
        "user_id"
    )

    checkout_id = state.get(
        "checkout_id"
    )
    if not checkout_id:
        planner_args = state.get("planner_args")
        if isinstance(planner_args, dict):
            checkout_id = planner_args.get("checkout_id")

    print(
        "\n=================================================="
    )

    print(
        "[TOOL NODE]"
    )

    print(
        f"tool_name = {tool_name}"
    )

    print(
        f"user_id = {user_id}"
    )

    print(
        f"checkout_id = {checkout_id!r}"
    )

    print(
        f"entities = {updated_entities}"
    )

    print(
        "=================================================="
    )

    # =====================================================
    # No Tool
    # =====================================================

    if not tool_name:

        return {
            "tool_result": None,
        }

    # =====================================================
    # SEARCH PRODUCTS
    # =====================================================

    if tool_name == "search_products":

        product_name = (
            updated_entities.get(
                "product_name"
            )
        )

        if not _has_value(
            product_name
        ):

            return {
                "tool_result": {
                    "success": False,
                    "type": "product_search",
                    "error": "Product name is required.",
                }
            }

        try:

            products = search_products(
                db=db,
                query=str(
                    product_name
                ).strip(),
            )

            if products is None:
                products = []

            if not isinstance(
                products,
                list,
            ):

                products = [
                    products
                ]

            return {
                "tool_result": {
                    "success": True,
                    "type": "product_search",
                    "products": [
                        _serialize_product(
                            product
                        )
                        for product in products
                    ],
                }
            }

        except Exception as exc:

            print(
                "[TOOL search_products ERROR]",
                type(exc).__name__,
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "type": "product_search",
                    "error": str(exc),
                }
            }

    # =====================================================
    # LIST SAVED ADDRESSES
    # =====================================================

    if tool_name == "list_saved_addresses":

        if user_id is None:

            return {
                "tool_result": {
                    "success": False,
                    "type": "address_selection",
                    "error": (
                        "User ID is required to load "
                        "saved addresses."
                    ),
                }
            }

        try:

            addresses = get_user_addresses(
                db=db,
                user_id=int(
                    user_id
                ),
            )

            return {
                "tool_result": {
                    "success": True,
                    "type": "address_selection",
                    "addresses": [
                        _serialize_address(
                            address
                        )
                        for address in addresses
                    ],
                    "allow_new": True,
                }
            }

        except Exception as exc:

            print(
                "[TOOL list_saved_addresses ERROR]",
                type(exc).__name__,
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "type": "address_selection",
                    "error": str(exc),
                }
            }

    # =====================================================
    # LIST PAYMENT METHODS
    # =====================================================

    if tool_name == "list_payment_methods":

        try:
            methods = get_available_payment_methods()

            return {
                "tool_result": {
                    "success": True,
                    "type": "payment_selection",
                    "methods": methods,
                }
            }

        except Exception as exc:
            print(
                "[TOOL list_payment_methods ERROR]",
                type(exc).__name__,
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "type": "payment_selection",
                    "error": (
                        "Payment methods are currently unavailable."
                    ),
                }
            }

    # =====================================================
    # CART: ADD / REMOVE / UPDATE / CLEAR
    # =====================================================

    if tool_name in {
        "add_to_cart",
        "remove_from_cart",
        "update_cart_item",
        "clear_cart",
    }:

        cart_result, cart_updates = _execute_cart_mutation(
            db=db,
            user_id=user_id,
            tool_name=tool_name,
            entities=updated_entities,
        )

        result: GraphState = {
            "tool_result": cart_result,
        }

        result.update(cart_updates)

        return result

    # =====================================================
    # CART: SHOW
    # =====================================================

    if tool_name == "show_cart":

        if user_id is None:
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_view",
                    "error": "User ID is required.",
                },
            }

        try:
            normalized_user_id = int(user_id)
        except (TypeError, ValueError):
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_view",
                    "error": "Invalid user ID.",
                },
            }

        if normalized_user_id <= 0:
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_view",
                    "error": "Invalid user ID.",
                },
            }

        try:
            cart = cart_get_cart(
                db=db,
                user_id=normalized_user_id,
            )
        except (
            CartServiceError,
            ValueError,
        ) as exc:
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_view",
                    "error": str(exc),
                },
            }
        except Exception as exc:
            print(
                "[TOOL show_cart ERROR]",
                type(exc).__name__,
                str(exc),
            )
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_view",
                    "error": (
                        "I could not load your cart because "
                        "of a backend error."
                    ),
                },
            }

        has_items = bool(cart.get("items"))

        return {
            "tool_result": {
                "success": True,
                "type": "cart_view",
                "action": "show_cart",
                "cart": cart,
                "cart_id": cart.get("cart_id"),
                "items": cart.get("items", []),
                "summary": cart.get("summary"),
            },
            **_cart_state_from_result(
                cart,
                checkout_ready=has_items,
            ),
        }

    # =====================================================
    # CART: CHECKOUT PREPARATION / VALIDATION
    # =====================================================

    if tool_name == "checkout_cart":

        if user_id is None:
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_checkout",
                    "error": "User ID is required.",
                },
            }

        try:
            normalized_user_id = int(user_id)
        except (TypeError, ValueError):
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_checkout",
                    "error": "Invalid user ID.",
                },
            }

        if normalized_user_id <= 0:
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_checkout",
                    "error": "Invalid user ID.",
                },
            }

        try:
            cart = cart_get_cart(
                db=db,
                user_id=normalized_user_id,
            )
        except (
            CartServiceError,
            ValueError,
        ) as exc:
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_checkout",
                    "error": str(exc),
                },
            }
        except Exception as exc:
            print(
                "[TOOL checkout_cart ERROR]",
                type(exc).__name__,
                str(exc),
            )
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_checkout",
                    "error": (
                        "I could not prepare your cart for checkout "
                        "because of a backend error."
                    ),
                },
            }

        items = cart.get("items", [])
        has_items = bool(items)

        # CartService has already calculated the authoritative
        # summary. This node does not calculate totals.
        if not has_items:
            return {
                "tool_result": {
                    "success": False,
                    "type": "cart_checkout",
                    "action": "checkout_cart",
                    "checkout_ready": False,
                    "error": "Your cart is empty.",
                    "cart": cart,
                    "cart_id": cart.get("cart_id"),
                    "items": [],
                    "summary": cart.get("summary"),
                },
                **_cart_state_from_result(
                    cart,
                    checkout_ready=False,
                ),
            }

        # IMPORTANT:
        # checkout_cart prepares/validates the cart only.
        #
        # It does NOT:
        #   - create an order
        #   - create a payment
        #   - reserve stock
        #   - calculate a new bill
        #
        # Address and payment selection remain part of the
        # existing checkout flow and are validated by the
        # authoritative order path before order creation.
        return {
            "tool_result": {
                "success": True,
                "type": "cart_checkout",
                "action": "checkout_cart",
                "checkout_ready": True,
                "cart": cart,
                "cart_id": cart.get("cart_id"),
                "items": items,
                "summary": cart.get("summary"),
                "next_step": "address_selection",
            },
            **_cart_state_from_result(
                cart,
                checkout_ready=True,
            ),
        }

    # =====================================================
    # CREATE ORDER
    # =====================================================

    if tool_name == "create_order":

        # =================================================
        # USER
        # =================================================

        if user_id is None:

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_error",
                    "error": "User ID is required.",
                }
            }

        try:

            user_id = int(
                user_id
            )

        except (
            TypeError,
            ValueError,
        ):

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_error",
                    "error": "Invalid user ID.",
                }
            }

        # =================================================
        # ORDER ITEMS
        # =================================================
        #
        # Let the AI provide either:
        #
        #   product_name + quantity
        #
        # OR:
        #
        #   product_id + quantity
        #
        # OR:
        #
        #   items = [...]
        #
        # =================================================

        order_items = _extract_order_items(
            updated_entities
        )

        if not order_items:

            return {
                "tool_result": {
                    "success": False,
                    "type": "product_required",
                    "error": (
                        "Please tell me which product "
                        "you want and the quantity."
                    ),
                }
            }

        # =================================================
        # ADDRESS
        # =================================================

        address_id = _get_address_id(
            state,
            updated_entities,
        )

        if address_id is None:

            return {
                "tool_result": {
                    "success": False,
                    "type": "address_selection",
                    "error": (
                        "Please select a saved delivery "
                        "address before placing the order."
                    ),
                },
                "entities": updated_entities,
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
                "tool_result": {
                    "success": False,
                    "type": "address_selection",
                    "error": "Invalid delivery address.",
                },
                "entities": updated_entities,
            }

        # =================================================
        # ADDRESS OWNERSHIP
        # =================================================

        address_valid, address_error = (
            _validate_address(
                db=db,
                user_id=user_id,
                address_id=address_id,
            )
        )

        if not address_valid:

            return {
                "tool_result": {
                    "success": False,
                    "type": "address_selection",
                    "error": (
                        address_error
                        or "Invalid delivery address."
                    ),
                },
                "entities": updated_entities,
            }

        # =================================================
        # PAYMENT
        # =================================================

        payment_method = _get_payment_method(
            state,
            updated_entities,
        )

        if payment_method is None:

            return {
                "tool_result": {
                    "success": False,
                    "type": "payment_selection",
                    "error": (
                        "Please select a valid payment "
                        "method before placing the order."
                    ),
                },
                "entities": updated_entities,
            }

        # =================================================
        # RESOLVE ALL PRODUCTS
        # =================================================

        resolved_items = []

        for item in order_items:

            product_id = item.get(
                "product_id"
            )

            product_name = item.get(
                "product_name"
            )

            quantity = item.get(
                "quantity"
            )

            print(
                "[CREATE ORDER] "
                "Resolving product:",
                product_name
                if product_name
                else product_id,
            )

            # ---------------------------------------------
            # If AI already has authoritative product ID,
            # verify it against DB.
            # ---------------------------------------------

            if product_id is not None:

                try:

                    product_id = int(
                        product_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    return {
                        "tool_result": {
                            "success": False,
                            "type": "product_invalid",
                            "error": (
                                "The selected product "
                                "has an invalid product ID."
                            ),
                        },
                        "entities": updated_entities,
                    }

                product = (
                    db.query(Product)
                    .filter(
                        Product.id
                        == product_id
                    )
                    .first()
                )

                if product is None:

                    return {
                        "tool_result": {
                            "success": False,
                            "type": "product_not_found",
                            "error": (
                                f"Product {product_id} "
                                "does not exist."
                            ),
                        },
                        "entities": updated_entities,
                    }

                candidates = []

            # ---------------------------------------------
            # Otherwise resolve natural-language name.
            # ---------------------------------------------

            else:

                product, candidates = (
                    _resolve_product(
                        db=db,
                        product_name=product_name,
                    )
                )

                # -----------------------------------------
                # Ambiguous product
                # -----------------------------------------

                if product is None:

                    if candidates:

                        return {
                            "tool_result": {
                                "success": False,
                                "type": "product_selection",
                                "error": (
                                    "I found multiple "
                                    "products matching "
                                    f"'{product_name}'. "
                                    "Please choose one."
                                ),
                                "products": [
                                    _serialize_product(
                                        candidate
                                    )
                                    for candidate in candidates
                                ],
                            },
                            "entities": updated_entities,
                        }

                    # -------------------------------------
                    # Not found
                    # -------------------------------------

                    return {
                        "tool_result": {
                            "success": False,
                            "type": "product_not_found",
                            "error": (
                                f"No product found for "
                                f"'{product_name}'."
                            ),
                        },
                        "entities": updated_entities,
                    }

                product_id = _product_id(
                    product
                )

            # =================================================
            # VALID PRODUCT ID
            # =================================================

            if product_id is None:

                return {
                    "tool_result": {
                        "success": False,
                        "type": "product_invalid",
                        "error": (
                            "The selected product does not "
                            "have a valid product ID."
                        ),
                    },
                    "entities": updated_entities,
                }

            try:

                product_id = int(
                    product_id
                )

            except (
                TypeError,
                ValueError,
            ):

                return {
                    "tool_result": {
                        "success": False,
                        "type": "product_invalid",
                        "error": (
                            "The selected product has "
                            "an invalid product ID."
                        ),
                    },
                    "entities": updated_entities,
                }

            # =================================================
            # QUANTITY
            # =================================================

            quantity = _normalize_quantity(
                quantity
            )

            if quantity is None:

                return {
                    "tool_result": {
                        "success": False,
                        "type": "quantity_required",
                        "error": (
                            "Quantity must be a "
                            "positive number."
                        ),
                    },
                    "entities": updated_entities,
                }

            # =================================================
            # AUTHORITATIVE PRODUCT
            # =================================================

            authoritative_product = (
                db.query(Product)
                .filter(
                    Product.id
                    == product_id
                )
                .first()
            )

            if authoritative_product is None:

                return {
                    "tool_result": {
                        "success": False,
                        "type": "product_not_found",
                        "error": (
                            f"Product {product_id} "
                            "does not exist."
                        ),
                    },
                    "entities": updated_entities,
                }

            # =================================================
            # AVAILABILITY
            # =================================================

            try:

                available = (
                    check_product_availability(
                        db=db,
                        product_id=product_id,
                        quantity=quantity,
                    )
                )

            except Exception as exc:

                print(
                    "[AVAILABILITY ERROR]",
                    type(exc).__name__,
                    str(exc),
                )

                return {
                    "tool_result": {
                        "success": False,
                        "type": "availability_error",
                        "error": str(exc),
                    },
                    "entities": updated_entities,
                }

            if not available:

                display_name = (
                    _product_name(
                        authoritative_product
                    )
                    or str(
                        product_name
                        or product_id
                    )
                )

                return {
                    "tool_result": {
                        "success": False,
                        "type": "product_unavailable",
                        "error": (
                            f"'{display_name}' is not "
                            "available in the requested "
                            "quantity."
                        ),
                        "product": _serialize_product(
                            authoritative_product
                        ),
                        "quantity": quantity,
                    },
                    "entities": updated_entities,
                }

            # =================================================
            # Store authoritative information
            # =================================================

            resolved_items.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                }
            )

            print(
                "[PRODUCT RESOLVED]",
                f"id={product_id}",
                f"name='{_product_name(authoritative_product)}'",
                f"quantity={quantity}",
            )

        # =================================================
        # SAVE AUTHORITATIVE CHECKOUT ENTITIES
        # =================================================

        updated_entities[
            "address_id"
        ] = address_id

        updated_entities[
            "payment_method"
        ] = payment_method

        # Keep single-product compatibility.
        if len(resolved_items) == 1:

            updated_entities[
                "product_id"
            ] = resolved_items[0][
                "product_id"
            ]

            updated_entities[
                "quantity"
            ] = resolved_items[0][
                "quantity"
            ]

            authoritative_product = (
                db.query(Product)
                .filter(
                    Product.id
                    == resolved_items[0][
                        "product_id"
                    ]
                )
                .first()
            )

            if authoritative_product:

                updated_entities[
                    "product_name"
                ] = _product_name(
                    authoritative_product
                )

        # =================================================
        # CREATE ORDER
        # =================================================

        print(
            "[CREATE ORDER]"
        )

        print(
            f"    user_id  = {user_id}"
        )

        print(
            f"    items    = {resolved_items}"
        )

        print(
            f"    address  = {address_id}"
        )

        print(
            f"    payment  = {payment_method}"
        )

        print(
            f"    checkout = {checkout_id!r}"
        )

        if not checkout_id:
            return {
                "tool_result": {
                    "success": False,
                    "type": "checkout_error",
                    "error": (
                        "The active checkout could not be identified. "
                        "Please restart the checkout."
                    ),
                },
                "entities": updated_entities,
            }

        try:

            order = create_order(
                db=db,
                user_id=user_id,
                address_id=address_id,
                items=resolved_items,
                payment_method=payment_method,
                checkout_id=checkout_id,
            )

        except ValueError as exc:

            print(
                "[CREATE ORDER VALUE ERROR]",
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_error",
                    "error": str(exc),
                },
                "entities": updated_entities,
            }

        except Exception as exc:

            print(
                "[CREATE ORDER ERROR]",
                type(exc).__name__,
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_error",
                    "error": (
                        "I could not place the order "
                        "because of a backend error."
                    ),
                },
                "entities": updated_entities,
            }

        # =================================================
        # VERIFY ORDER
        # =================================================

        order_id = getattr(
            order,
            "id",
            None,
        )

        if order_id is None:

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_error",
                    "error": (
                        "Order creation completed but "
                        "no order ID was returned."
                    ),
                },
                "entities": updated_entities,
            }

        # =================================================
        # GET BILL
        # =================================================
        #
        # order_service.py now creates:
        #
        #     order._buyqk_bill
        #
        # Use that first.
        #
        # If it is unavailable, rebuild the bill from the
        # persisted order.
        #
        # =================================================

        bill = getattr(
            order,
            "_buyqk_bill",
            None,
        )

        if bill is None:

            try:

                bill = build_order_bill(
                    db=db,
                    order=order,
                )

            except Exception as exc:

                print(
                    "[BILL GENERATION ERROR]",
                    type(exc).__name__,
                    str(exc),
                )

                return {
                    "tool_result": {
                        "success": False,
                        "type": "bill_error",
                        "error": (
                            "Order was created, but "
                            "the bill could not be generated."
                        ),
                        "order_id": order_id,
                    },
                    "entities": updated_entities,
                    "order_id": order_id,
                }

        bill = _serialize_bill(
            bill
        )

        if bill is None:

            return {
                "tool_result": {
                    "success": False,
                    "type": "bill_error",
                    "error": (
                        "Order was created, but "
                        "the bill data is invalid."
                    ),
                    "order_id": order_id,
                },
                "entities": updated_entities,
                "order_id": order_id,
            }

        # Make absolutely sure the authoritative order ID
        # is used in the bill.

        bill[
            "order_id"
        ] = order_id

        # =================================================
        # AUTHORITATIVE BILLING
        # =================================================
        #
        # order_service.py has already calculated the bill.
        # This node only transfers those authoritative values.
        # =================================================

        billing_items = bill.get("items", [])
        subtotal = bill.get("subtotal", 0)
        delivery_charge = bill.get("delivery_charge", 0)
        discount = bill.get("discount", 0)
        tax = bill.get("tax", 0)
        total_amount = bill.get("total", 0)
        currency = bill.get("currency", "INR")

        billing_payment_method = (
            bill.get("payment_method")
            or payment_method
        )

        # Keep authoritative identifiers inside the bill.
        bill["order_id"] = order_id
        bill["payment_method"] = billing_payment_method

        print("[ORDER CREATED SUCCESSFULLY]")
        print(f"    order_id = {order_id}")
        print(f"    subtotal = {currency} {subtotal}")
        print(f"    delivery = {currency} {delivery_charge}")
        print(f"    discount = {currency} {discount}")
        print(f"    tax      = {currency} {tax}")
        print(f"    total    = {currency} {total_amount}")

        return {
            "tool_result": {
                "success": True,
                "type": "order_success",
                "order_id": order_id,
                "status": getattr(order, "status", None),
                "payment_status": getattr(
                    order,
                    "payment_status",
                    None,
                ),
                "payment_method": billing_payment_method,
                "total_amount": total_amount,
                "bill": bill,
                "purchase_summary": {
                    "items": billing_items,
                    "subtotal": subtotal,
                    "delivery_charge": delivery_charge,
                    "discount": discount,
                    "tax": tax,
                    "total": total_amount,
                    "currency": currency,
                    "payment_method": billing_payment_method,
                },
            },

            "entities": updated_entities,
            "checkout_id": checkout_id,
            "checkout_status": "completed",
            "checkout_completed": True,
            "order_created": True,
            "order_creation_attempted": True,
            "order_id": order_id,

            # Authoritative billing copied from order_service.
            "billing": bill,
            "bill": bill,
            "billing_items": billing_items,
            "subtotal": subtotal,
            "delivery_charge": delivery_charge,
            "discount": discount,
            "tax": tax,
            "total_amount": total_amount,
            "currency": currency,
            "billing_payment_method": billing_payment_method,

            "awaiting_order_tracking_confirmation": True,
        }

    # =====================================================
    # TRACK ORDER
    # =====================================================

    if tool_name == "track_order":

        order_id = updated_entities.get(
            "order_id"
        )

        if not order_id:

            order_id = state.get(
                "order_id"
            )

        if not order_id:

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_tracking",
                    "error": "Order ID is required.",
                }
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
                "tool_result": {
                    "success": False,
                    "type": "order_tracking",
                    "error": "Invalid order ID.",
                }
            }

        try:

            order = get_order(
                db=db,
                order_id=order_id,
            )

        except Exception as exc:

            print(
                "[TRACK ORDER ERROR]",
                type(exc).__name__,
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_tracking",
                    "error": str(exc),
                }
            }

        if order is None:

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_tracking",
                    "error": (
                        f"Order {order_id} "
                        "does not exist."
                    ),
                }
            }

        # =================================================
        # Ownership
        # =================================================

        order_user_id = getattr(
            order,
            "user_id",
            None,
        )

        if (
            user_id is not None
            and order_user_id != user_id
        ):

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_tracking",
                    "error": (
                        "You are not authorized to "
                        "view this order."
                    ),
                }
            }

        # =================================================
        # Generate bill for tracking too
        # =================================================

        try:

            bill = build_order_bill(
                db=db,
                order=order,
            )

        except Exception:

            bill = None

        serialized_bill = (
            _serialize_bill(bill)
            if bill
            else None
        )

        tracking_state = {
            "tool_result": {
                "success": True,
                "type": "tracking",
                "order_id": getattr(
                    order,
                    "id",
                    order_id,
                ),
                "status": getattr(
                    order,
                    "status",
                    None,
                ),
                "payment_status": getattr(
                    order,
                    "payment_status",
                    None,
                ),
                "total_amount": getattr(
                    order,
                    "total_amount",
                    None,
                ),
                "bill": serialized_bill,
            },

            "order_id": getattr(
                order,
                "id",
                order_id,
            ),

            "awaiting_order_tracking_confirmation": False,
        }

        if serialized_bill is not None:
            tracking_state.update(
                {
                    "billing": serialized_bill,
                    "bill": serialized_bill,
                    "billing_items": serialized_bill.get(
                        "items",
                        [],
                    ),
                    "subtotal": serialized_bill.get(
                        "subtotal",
                        0,
                    ),
                    "delivery_charge": serialized_bill.get(
                        "delivery_charge",
                        0,
                    ),
                    "discount": serialized_bill.get(
                        "discount",
                        0,
                    ),
                    "tax": serialized_bill.get(
                        "tax",
                        0,
                    ),
                    "total_amount": serialized_bill.get(
                        "total",
                        0,
                    ),
                    "currency": serialized_bill.get(
                        "currency",
                        "INR",
                    ),
                    "billing_payment_method": serialized_bill.get(
                        "payment_method"
                    ),
                }
            )

        return tracking_state
    # =====================================================
    # CANCEL ORDER
    # =====================================================

    if tool_name == "cancel_order":

        if user_id is None:

            return {
                "tool_result": {
                    "success": False,
                    "error": "User ID is required.",
                }
            }

        order_id = updated_entities.get(
            "order_id"
        )

        if not order_id:

            order_id = state.get(
                "order_id"
            )

        if not order_id:

            return {
                "tool_result": {
                    "success": False,
                    "error": "Order ID is required.",
                }
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
                "tool_result": {
                    "success": False,
                    "error": "Invalid order ID.",
                }
            }

        try:

            order = cancel_order(
                db=db,
                order_id=order_id,
                user_id=int(
                    user_id
                ),
            )

            return {
                "tool_result": {
                    "success": True,
                    "type": "order_cancelled",
                    "order_id": getattr(
                        order,
                        "id",
                        order_id,
                    ),
                    "status": getattr(
                        order,
                        "status",
                        None,
                    ),
                },

                "entities": updated_entities,

                "order_id": order_id,
            }

        except ValueError as exc:

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_cancelled",
                    "error": str(exc),
                }
            }

        except Exception as exc:

            print(
                "[CANCEL ORDER ERROR]",
                type(exc).__name__,
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "type": "order_cancelled",
                    "error": str(exc),
                }
            }

    # =====================================================
    # CREATE SUPPORT TICKET
    # =====================================================

    if tool_name == "create_support_ticket":

        if user_id is None:

            return {
                "tool_result": {
                    "success": False,
                    "error": "User ID is required.",
                }
            }

        order_id = updated_entities.get(
            "order_id"
        )

        message = state.get(
            "message",
            "",
        )

        if not _has_value(
            message
        ):

            return {
                "tool_result": {
                    "success": False,
                    "error": (
                        "Support message is required."
                    ),
                }
            }

        try:

            ticket = create_ticket(
                db=db,
                user_id=int(
                    user_id
                ),
                subject="BuyQK Customer Support",
                description=str(
                    message
                ),
                order_id=order_id,
            )

            return {
                "tool_result": {
                    "success": True,
                    "type": "support_ticket",
                    "ticket_id": getattr(
                        ticket,
                        "id",
                        None,
                    ),
                    "status": getattr(
                        ticket,
                        "status",
                        None,
                    ),
                }
            }

        except ValueError as exc:

            return {
                "tool_result": {
                    "success": False,
                    "error": str(exc),
                }
            }

        except Exception as exc:

            print(
                "[SUPPORT TICKET ERROR]",
                type(exc).__name__,
                str(exc),
            )

            return {
                "tool_result": {
                    "success": False,
                    "error": str(exc),
                }
            }

    # =====================================================
    # UNKNOWN TOOL
    # =====================================================

    print(
        f"[TOOL ERROR] Unsupported tool: {tool_name}"
    )

    return {
        "tool_result": {
            "success": False,
            "error": (
                f"Unsupported tool: {tool_name}"
            ),
        }
    }