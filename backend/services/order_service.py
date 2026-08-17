# =========================================================
# BuyQK - Order Service
# =========================================================
#
# Responsibilities:
#
# - Validate order data
# - Validate address ownership
# - Validate payment method
# - Resolve products from database
# - Validate product availability
# - Validate stock
# - Calculate item totals
# - Calculate subtotal
# - Calculate delivery charge
# - Calculate final order total
# - Reserve/decrease inventory
# - Create order
# - Create order items
# - Create payment record
# - Generate structured bill
# - Retrieve orders
# - Cancel orders
# - Restore inventory
# - Guarantee checkout-level idempotency
#
# IMPORTANT:
#
# The database is authoritative for:
#
# - Product
# - Product name
# - Product price
# - Product stock
# - Product availability
# - Address ownership
# - Order ID
# - Order status
# - Payment record
#
# The AI NEVER invents:
#
# - Product price
# - Product ID
# - Stock
# - Order ID
# - Subtotal
# - Total
#
# The AI understands the user's request.
#
# This service validates and executes the transaction.
#
# =========================================================


from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from backend.models.address import Address
from backend.models.order import Order
from backend.models.order_item import OrderItem
from backend.models.product import Product
from backend.models.payment import Payment


# =========================================================
# Supported Payment Methods
# =========================================================
#
# These are backend-supported payment identifiers.
#
# The AI may understand different natural-language forms,
# but the backend decides whether a normalized method is
# actually supported.
#
# =========================================================

SUPPORTED_PAYMENT_METHODS = {
    "upi",
    "cod",
}


# =========================================================
# MVP Delivery Charge
# =========================================================
#
# Delivery is free in the current MVP.
#
# This value belongs to backend business logic.
#
# The AI must never calculate or invent delivery charges.
#
# Future implementation can replace this with a dynamic
# delivery/pricing service.
#
# =========================================================

MVP_DELIVERY_CHARGE = Decimal("0.00")


# =========================================================
# Utility - Checkout ID
# =========================================================


def _normalize_checkout_id(
    checkout_id: Any,
) -> str:
    """
    Validate and normalize checkout_id.

    checkout_id identifies one checkout transaction.

    It is NOT the order ID.

    The same checkout_id must never create two orders.
    """

    if checkout_id is None:
        raise ValueError(
            "Checkout ID is required for order creation."
        )

    normalized = str(checkout_id).strip()

    if not normalized:
        raise ValueError(
            "Checkout ID is required for order creation."
        )

    if len(normalized) > 255:
        raise ValueError(
            "Checkout ID is too long."
        )

    return normalized


# =========================================================
# Utility - User ID
# =========================================================


def _normalize_user_id(
    user_id: Any,
) -> int:
    """
    Validate user ID.
    """

    if user_id is None:
        raise ValueError(
            "User ID is required."
        )

    try:
        normalized = int(user_id)

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid user ID."
        )

    if normalized <= 0:
        raise ValueError(
            "Invalid user ID."
        )

    return normalized


# =========================================================
# Utility - Address ID
# =========================================================


def _normalize_address_id(
    address_id: Any,
) -> int:
    """
    Validate address ID.
    """

    if address_id is None:
        raise ValueError(
            "Address ID is required."
        )

    try:
        normalized = int(address_id)

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid address ID."
        )

    if normalized <= 0:
        raise ValueError(
            "Invalid address ID."
        )

    return normalized


# =========================================================
# Address Validation
# =========================================================


def _validate_user_address(
    db: Session,
    user_id: int,
    address_id: int,
) -> Address:
    """
    Ensure the selected address exists and belongs
    to the current user.

    Frontend selection is never trusted without
    backend ownership validation.
    """

    user_id = _normalize_user_id(user_id)

    address_id = _normalize_address_id(address_id)

    address = (
        db.query(Address)
        .filter(
            Address.id == address_id,
            Address.user_id == user_id,
        )
        .first()
    )

    if address is None:
        raise ValueError(
            "The selected address does not belong "
            "to this user."
        )

    return address


# =========================================================
# Payment Validation
# =========================================================


def _validate_payment_method(
    payment_method: Any,
) -> str:
    """
    Normalize and validate payment method.

    Natural-language representations are normalized here.

    Examples:

        cash on delivery
        cash_on_delivery
        cash
        COD

    become:

        cod

    The backend still decides whether the normalized method
    is supported.
    """

    if payment_method is None:
        raise ValueError(
            "Payment method is required."
        )

    normalized = (
        str(payment_method)
        .strip()
        .lower()
    )

    if not normalized:
        raise ValueError(
            "Payment method is required."
        )

    aliases = {
        "cash on delivery": "cod",
        "cash_on_delivery": "cod",
        "cashondelivery": "cod",
        "cash": "cod",
        "cod": "cod",
        "upi": "upi",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    if normalized not in SUPPORTED_PAYMENT_METHODS:
        raise ValueError(
            "Unsupported payment method."
        )

    return normalized


# =========================================================
# Available Payment Methods
# =========================================================


def get_available_payment_methods() -> list[dict[str, str]]:
    """
    Return backend-supported payment methods.

    Frontend should use this rather than hardcoding payment
    methods independently.
    """

    return [
        {
            "id": method,
            "label": (
                "Cash on Delivery"
                if method == "cod"
                else "UPI"
            ),
            "description": (
                "Pay when your order is delivered."
                if method == "cod"
                else "Pay using UPI."
            ),
        }
        for method in sorted(
            SUPPORTED_PAYMENT_METHODS
        )
    ]


# =========================================================
# Quantity Normalization
# =========================================================


def _normalize_quantity(
    quantity: Any,
) -> int:
    """
    Convert extracted quantity into a positive integer.

    Natural-language understanding belongs to the AI layer.

    This service only validates the resulting value.
    """

    if isinstance(quantity, bool):
        raise ValueError(
            "Quantity must be a positive integer."
        )

    try:
        normalized = int(quantity)

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Quantity must be a positive integer."
        )

    if normalized <= 0:
        raise ValueError(
            "Quantity must be a positive integer."
        )

    return normalized


# =========================================================
# Product Name Normalization
# =========================================================


def _normalize_product_name(
    product_name: Any,
) -> str:
    """
    Normalize product name for database lookup.
    """

    if product_name is None:
        raise ValueError(
            "Product name is required."
        )

    normalized = (
        str(product_name)
        .strip()
        .lower()
    )

    if not normalized:
        raise ValueError(
            "Product name is required."
        )

    return normalized


# =========================================================
# Resolve Product
# =========================================================


def _resolve_product(
    db: Session,
    product_id: Any = None,
    product_name: Any = None,
) -> Product:
    """
    Resolve product from the database.

    Priority:

        1. product_id
        2. exact product name
        3. unique partial product name

    Price is ALWAYS read from Product.price.
    """

    # -----------------------------------------------------
    # Product ID
    # -----------------------------------------------------

    if product_id is not None:

        try:
            normalized_id = int(
                product_id
            )

        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                "Product ID must be a valid integer."
            )

        if normalized_id <= 0:
            raise ValueError(
                "Product ID must be positive."
            )

        product = (
            db.query(Product)
            .filter(
                Product.id == normalized_id
            )
            .first()
        )

        if product is None:
            raise ValueError(
                f"Product {normalized_id} does not exist."
            )

        return product

    # -----------------------------------------------------
    # Product Name
    # -----------------------------------------------------

    normalized_name = (
        _normalize_product_name(
            product_name
        )
    )

    # Exact case-insensitive match
    product = (
        db.query(Product)
        .filter(
            func.lower(Product.name)
            == normalized_name
        )
        .first()
    )

    if product is not None:
        return product

    # Unique partial match
    partial_matches = (
        db.query(Product)
        .filter(
            func.lower(Product.name).contains(
                normalized_name
            )
        )
        .all()
    )

    if len(partial_matches) == 1:
        return partial_matches[0]

    if len(partial_matches) > 1:

        names = [
            product.name
            for product in partial_matches[:5]
        ]

        raise ValueError(
            f"Multiple products matched "
            f"'{product_name}': "
            f"{', '.join(names)}. "
            "Please specify the exact product."
        )

    raise ValueError(
        f"No product found for "
        f"'{product_name}'."
    )


# =========================================================
# Decimal Conversion
# =========================================================


def _to_decimal(
    value: Any,
) -> Decimal:
    """
    Convert monetary value to Decimal.
    """

    if value is None:
        raise ValueError(
            "Monetary value is missing."
        )

    try:
        return Decimal(
            str(value)
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):
        raise ValueError(
            "Invalid monetary value."
        )


# =========================================================
# Money Conversion
# =========================================================


def _money(
    value: Decimal | float | int,
) -> float:
    """
    Convert Decimal into JSON-friendly float.
    """

    decimal_value = _to_decimal(
        value
    )

    return float(
        decimal_value.quantize(
            Decimal("0.01")
        )
    )


# =========================================================
# Existing Checkout Lookup
# =========================================================


def _get_existing_checkout_order(
    db: Session,
    user_id: int,
    checkout_id: str,
) -> Order | None:
    """
    Find an order already created for this checkout.

    This is the core idempotency lookup.

    IMPORTANT:

    The Order model must contain:

        checkout_id

    and that field should have a database index/unique
    constraint where possible.
    """

    # Explicitly require the model field so that a missing
    # migration cannot silently disable idempotency.
    if not hasattr(
        Order,
        "checkout_id",
    ):
        raise RuntimeError(
            "Order model is missing the "
            "'checkout_id' field. "
            "Add checkout_id to backend.models.order.Order "
            "before using idempotent order creation."
        )

    return (
        db.query(Order)
        .filter(
            Order.checkout_id == checkout_id,
            Order.user_id == user_id,
        )
        .first()
    )


# =========================================================
# Build Order Items
# =========================================================


def _build_order_items(
    db: Session,
    items: list[dict[str, Any]],
) -> tuple[
    list[OrderItem],
    Decimal,
    list[dict[str, Any]],
]:
    """
    Resolve products, validate stock, calculate line totals,
    and reserve inventory.

    Prices come exclusively from the database.

    Returns:

        order_items
        subtotal
        bill_items
    """

    if not items:
        raise ValueError(
            "At least one order item is required."
        )

    if not isinstance(
        items,
        list,
    ):
        raise ValueError(
            "Order items must be provided as a list."
        )

    # =====================================================
    # Aggregate duplicate products
    # =====================================================

    aggregated_items: dict[
        tuple[str, Any],
        int,
    ] = {}

    for entry in items:

        if not isinstance(
            entry,
            dict,
        ):
            raise ValueError(
                "Each order item must be an object."
            )

        product_id = entry.get(
            "product_id"
        )

        product_name = entry.get(
            "product_name"
        )

        quantity = _normalize_quantity(
            entry.get("quantity")
        )

        if product_id is not None:

            key = (
                "id",
                product_id,
            )

        elif product_name is not None:

            key = (
                "name",
                _normalize_product_name(
                    product_name
                ),
            )

        else:
            raise ValueError(
                "Each order item must include "
                "product_id or product_name."
            )

        aggregated_items[key] = (
            aggregated_items.get(
                key,
                0,
            )
            + quantity
        )

    # =====================================================
    # Resolve / validate products
    # =====================================================

    order_items: list[OrderItem] = []

    bill_items: list[
        dict[str, Any]
    ] = []

    subtotal = Decimal("0.00")

    for (
        identifier,
        quantity,
    ) in aggregated_items.items():

        identifier_type, value = identifier

        if identifier_type == "id":

            product = _resolve_product(
                db=db,
                product_id=value,
            )

        else:

            product = _resolve_product(
                db=db,
                product_name=value,
            )

        # -------------------------------------------------
        # Availability
        # -------------------------------------------------

        if not product.is_available:
            raise ValueError(
                f"'{product.name}' is currently unavailable."
            )

        # -------------------------------------------------
        # Price
        # -------------------------------------------------

        if product.price is None:
            raise ValueError(
                f"Price for '{product.name}' "
                "is unavailable."
            )

        unit_price = _to_decimal(
            product.price
        )

        if unit_price < 0:
            raise ValueError(
                f"Invalid price for "
                f"'{product.name}'."
            )

        # -------------------------------------------------
        # Atomic stock reservation
        # -------------------------------------------------
        #
        # Instead of:
        #
        #     read stock
        #     calculate
        #     write stock
        #
        # we perform:
        #
        #     stock = stock - quantity
        #
        # only when enough stock exists.
        #
        # This reduces race-condition risk when multiple
        # orders are being created concurrently.
        #
        # -------------------------------------------------

        stock_update = (
            update(Product)
            .where(
                Product.id == product.id,
                Product.is_available.is_(True),
                Product.stock >= quantity,
            )
            .values(
                stock=Product.stock - quantity
            )
        )

        result = db.execute(
            stock_update
        )

        if result.rowcount != 1:

            # Refresh product state for an accurate error.
            db.refresh(product)

            current_stock = (
                product.stock
                if product.stock is not None
                else 0
            )

            if current_stock < quantity:

                raise ValueError(
                    f"Insufficient stock for "
                    f"'{product.name}'. "
                    f"Available: {current_stock}, "
                    f"requested: {quantity}."
                )

            raise ValueError(
                f"Unable to reserve "
                f"'{product.name}'."
            )

        # -------------------------------------------------
        # Line total
        # -------------------------------------------------

        line_total = (
            unit_price
            * Decimal(quantity)
        ).quantize(
            Decimal("0.01")
        )

        # -------------------------------------------------
        # Order item
        # -------------------------------------------------

        order_item = OrderItem(
            product_id=product.id,
            quantity=quantity,
            unit_price=_money(
                unit_price
            ),
            total_price=_money(
                line_total
            ),
        )

        order_items.append(
            order_item
        )

        # -------------------------------------------------
        # Bill item
        # -------------------------------------------------

        bill_items.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "brand": product.brand,
                "quantity": quantity,
                "unit_price": _money(
                    unit_price
                ),
                "line_total": _money(
                    line_total
                ),
            }
        )

        subtotal += line_total

    if not order_items:
        raise ValueError(
            "No valid order items were found."
        )

    return (
        order_items,
        subtotal.quantize(
            Decimal("0.01")
        ),
        bill_items,
    )


# =========================================================
# Calculate Bill
# =========================================================


def _calculate_bill(
    bill_items: list[dict[str, Any]],
    subtotal: Decimal,
    payment_method: str,
) -> dict[str, Any]:
    """
    Calculate authoritative backend billing.

    MVP delivery policy is currently free.

    All values returned here are backend-generated.
    """

    delivery_charge = (
        MVP_DELIVERY_CHARGE
    )

    discount = Decimal("0.00")

    tax = Decimal("0.00")

    total = (
        subtotal
        + delivery_charge
        + tax
        - discount
    ).quantize(
        Decimal("0.01")
    )

    return {
        "items": bill_items,
        "subtotal": _money(subtotal),
        "delivery_charge": _money(
            delivery_charge
        ),
        "discount": _money(
            discount
        ),
        "tax": _money(
            tax
        ),
        "total": _money(
            total
        ),
        "currency": "INR",
        "payment_method": payment_method,
    }


# =========================================================
# Create Payment Record
# =========================================================


def _create_payment_record(
    db: Session,
    order: Order,
    payment_method: str,
    amount: float,
) -> Payment:
    """
    Create the MVP payment record.

    This does not process an external payment gateway.
    """

    payment = Payment(
        order_id=order.id,
        transaction_id=None,
        payment_method=payment_method,
        payment_status="pending",
        amount=amount,
    )

    db.add(
        payment
    )

    return payment


# =========================================================
# Attach Bill To Order
# =========================================================


def _attach_bill(
    order: Order,
    bill: dict[str, Any],
) -> None:
    """
    Attach transient billing information for the tool layer.

    Billing remains authoritative in the backend result.
    """

    order._buyqk_bill = {
        **bill,
        "order_id": order.id,
    }

    order._buyqk_payment_method = (
        bill.get("payment_method")
    )

    order._buyqk_subtotal = (
        bill.get("subtotal")
    )

    order._buyqk_delivery_charge = (
        bill.get("delivery_charge")
    )

    order._buyqk_discount = (
        bill.get("discount")
    )

    order._buyqk_tax = (
        bill.get("tax")
    )

    order._buyqk_total = (
        bill.get("total")
    )

    order._buyqk_currency = (
        bill.get("currency")
    )


# =========================================================
# Create Order
# =========================================================


def create_order(
    db: Session,
    user_id: int,
    address_id: int,
    items: list[dict[str, Any]],
    payment_method: str | None = None,
    checkout_id: str | None = None,
) -> Order:
    """
    Create exactly one order for a checkout.

    Idempotency contract:

        Same user_id + same checkout_id
        --------------------------------
                 ↓
        return existing order

    instead of creating another order.

    This is what prevents:

        user:
            "Thank you"

    from accidentally generating another order when the
    graph incorrectly reaches create_order again.

    The service is intentionally defensive:

        - checkout_id is required
        - existing checkout is checked
        - order creation is transactional
        - inventory is reserved inside the transaction
        - payment is created inside the transaction
        - rollback restores the transaction state
    """

    # =====================================================
    # Normalize inputs
    # =====================================================

    user_id = _normalize_user_id(
        user_id
    )

    address_id = _normalize_address_id(
        address_id
    )

    checkout_id = _normalize_checkout_id(
        checkout_id
    )

    # =====================================================
    # Verify model support
    # =====================================================

    if not hasattr(
        Order,
        "checkout_id",
    ):
        raise RuntimeError(
            "Order model is missing checkout_id. "
            "Add checkout_id to Order and create/apply "
            "the corresponding database migration."
        )

    # =====================================================
    # Idempotency check
    # =====================================================

    existing_order = (
        _get_existing_checkout_order(
            db=db,
            user_id=user_id,
            checkout_id=checkout_id,
        )
    )

    if existing_order is not None:

        existing_bill = (
            build_order_bill(
                db=db,
                order=existing_order,
            )
        )

        _attach_bill(
            order=existing_order,
            bill=existing_bill,
        )

        existing_order._buyqk_idempotent = True

        return existing_order

    # =====================================================
    # Validate address
    # =====================================================

    _validate_user_address(
        db=db,
        user_id=user_id,
        address_id=address_id,
    )

    # =====================================================
    # Validate payment
    # =====================================================

    normalized_payment_method = (
        _validate_payment_method(
            payment_method
        )
    )

    # =====================================================
    # Transaction
    # =====================================================
    #
    # Everything below must succeed together.
    #
    # If anything fails:
    #
    #     stock update
    #     order
    #     order items
    #     payment
    #
    # are rolled back together.
    #
    # =====================================================

    try:

        # -------------------------------------------------
        # Build items / reserve inventory
        # -------------------------------------------------

        (
            order_items,
            subtotal,
            bill_items,
        ) = _build_order_items(
            db=db,
            items=items,
        )

        # -------------------------------------------------
        # Calculate authoritative bill
        # -------------------------------------------------

        bill = _calculate_bill(
            bill_items=bill_items,
            subtotal=subtotal,
            payment_method=(
                normalized_payment_method
            ),
        )

        # -------------------------------------------------
        # Create order
        # -------------------------------------------------

        order = Order(
            user_id=user_id,
            address_id=address_id,
            status="pending",
            payment_status="pending",
            total_amount=bill["total"],
            checkout_id=checkout_id,
        )

        # -------------------------------------------------
        # Add order items
        # -------------------------------------------------

        order.items.extend(
            order_items
        )

        db.add(
            order
        )

        # -------------------------------------------------
        # Get generated order ID
        # -------------------------------------------------

        db.flush()

        # -------------------------------------------------
        # Create payment
        # -------------------------------------------------

        _create_payment_record(
            db=db,
            order=order,
            payment_method=(
                normalized_payment_method
            ),
            amount=bill["total"],
        )

        # -------------------------------------------------
        # Commit entire transaction
        # -------------------------------------------------

        db.commit()

    except Exception:
        db.rollback()
        raise

    # =====================================================
    # Refresh
    # =====================================================

    db.refresh(
        order
    )

    # =====================================================
    # Attach authoritative bill
    # =====================================================

    bill["order_id"] = order.id

    _attach_bill(
        order=order,
        bill=bill,
    )

    order._buyqk_idempotent = False

    return order


# =========================================================
# Get Order
# =========================================================


def get_order(
    db: Session,
    order_id: int,
) -> Order | None:
    """
    Return a single order by ID.
    """

    if order_id is None:
        return None

    try:
        order_id = int(
            order_id
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if order_id <= 0:
        return None

    return (
        db.query(Order)
        .filter(
            Order.id == order_id
        )
        .first()
    )


# =========================================================
# Get User Orders
# =========================================================


def get_user_orders(
    db: Session,
    user_id: int,
    limit: int = 20,
) -> list[Order]:
    """
    Return recent orders belonging to a user.
    """

    user_id = _normalize_user_id(
        user_id
    )

    try:
        limit = int(
            limit
        )

    except (
        TypeError,
        ValueError,
    ):
        limit = 20

    limit = max(
        1,
        min(
            limit,
            100,
        ),
    )

    return (
        db.query(Order)
        .filter(
            Order.user_id == user_id
        )
        .order_by(
            Order.id.desc()
        )
        .limit(limit)
        .all()
    )


# =========================================================
# Build Bill From Existing Order
# =========================================================


def build_order_bill(
    db: Session,
    order: Order,
) -> dict[str, Any]:
    """
    Build authoritative bill from an existing order.

    IMPORTANT:

    Historical OrderItem.unit_price is used.

    We do NOT read current Product.price because the product
    price may have changed after the order was created.
    """

    if order is None:
        raise ValueError(
            "Order is required."
        )

    bill_items: list[
        dict[str, Any]
    ] = []

    subtotal = Decimal("0.00")

    for item in order.items:

        unit_price = _to_decimal(
            item.unit_price
        )

        quantity = _normalize_quantity(
            item.quantity
        )

        line_total = _to_decimal(
            item.total_price
        )

        subtotal += line_total

        product = (
            db.query(Product)
            .filter(
                Product.id
                == item.product_id
            )
            .first()
        )

        product_name = None
        brand = None

        if product is not None:
            product_name = product.name
            brand = product.brand

        bill_items.append(
            {
                "product_id": item.product_id,
                "product_name": (
                    product_name
                    or f"Product #{item.product_id}"
                ),
                "brand": brand,
                "quantity": quantity,
                "unit_price": _money(
                    unit_price
                ),
                "line_total": _money(
                    line_total
                ),
            }
        )

    subtotal = subtotal.quantize(
        Decimal("0.01")
    )

    delivery_charge = (
        MVP_DELIVERY_CHARGE
    )

    discount = Decimal("0.00")

    tax = Decimal("0.00")

    total = (
        subtotal
        + delivery_charge
        + tax
        - discount
    ).quantize(
        Decimal("0.01")
    )

    payment = (
        db.query(Payment)
        .filter(
            Payment.order_id
            == order.id
        )
        .first()
    )

    payment_method = None

    if payment is not None:
        payment_method = (
            payment.payment_method
        )

    return {
        "order_id": order.id,
        "items": bill_items,
        "subtotal": _money(
            subtotal
        ),
        "delivery_charge": _money(
            delivery_charge
        ),
        "discount": _money(
            discount
        ),
        "tax": _money(
            tax
        ),
        "total": _money(
            total
        ),
        "currency": "INR",
        "payment_method": payment_method,
    }


# =========================================================
# Get Order Bill
# =========================================================


def get_order_bill(
    db: Session,
    order_id: int,
    user_id: int,
) -> dict[str, Any]:
    """
    Safely retrieve an order bill for the authenticated user.
    """

    user_id = _normalize_user_id(
        user_id
    )

    order = get_order(
        db=db,
        order_id=order_id,
    )

    if order is None:
        raise ValueError(
            "Order does not exist."
        )

    if order.user_id != user_id:
        raise ValueError(
            "You are not authorized to access "
            "this order."
        )

    return build_order_bill(
        db=db,
        order=order,
    )


# =========================================================
# Cancel Order
# =========================================================


def cancel_order(
    db: Session,
    order_id: int,
    user_id: int,
) -> Order:
    """
    Cancel an existing user order.

    Flow:

        validate order
            ↓
        validate ownership
            ↓
        validate status
            ↓
        restore inventory
            ↓
        update order
            ↓
        update payment
            ↓
        commit
    """

    user_id = _normalize_user_id(
        user_id
    )

    if order_id is None:
        raise ValueError(
            "Order ID is required."
        )

    try:
        order_id = int(
            order_id
        )

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid order ID."
        )

    if order_id <= 0:
        raise ValueError(
            "Invalid order ID."
        )

    order = get_order(
        db=db,
        order_id=order_id,
    )

    if order is None:
        raise ValueError(
            f"Order {order_id} does not exist."
        )

    if order.user_id != user_id:
        raise ValueError(
            "You are not authorized to cancel "
            "this order."
        )

    if order.status == "cancelled":
        return order

    non_cancellable_statuses = {
        "delivered",
        "completed",
    }

    if (
        order.status
        in non_cancellable_statuses
    ):
        raise ValueError(
            "This order can no longer be cancelled."
        )

    try:

        # =================================================
        # Restore inventory
        # =================================================

        for item in order.items:

            product = (
                db.query(Product)
                .filter(
                    Product.id
                    == item.product_id
                )
                .first()
            )

            if product is None:
                raise ValueError(
                    f"Product {item.product_id} "
                    "no longer exists."
                )

            current_stock = int(
                product.stock or 0
            )

            product.stock = (
                current_stock
                + int(item.quantity)
            )

        # =================================================
        # Update order
        # =================================================

        order.status = "cancelled"

        if hasattr(
            order,
            "payment_status",
        ):
            order.payment_status = (
                "cancelled"
            )

        # =================================================
        # Update payment
        # =================================================

        payment = (
            db.query(Payment)
            .filter(
                Payment.order_id
                == order.id
            )
            .first()
        )

        if payment is not None:

            if (
                payment.payment_status
                == "success"
            ):
                payment.payment_status = (
                    "refunded"
                )

            else:
                payment.payment_status = (
                    "cancelled"
                )

        # =================================================
        # Commit
        # =================================================

        db.commit()

    except Exception:

        db.rollback()
        raise

    db.refresh(
        order
    )

    return order