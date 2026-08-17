# =========================================================
# BuyQK - Order Service
# =========================================================
#
# Responsibilities:
#
# - Validate order data
# - Validate address ownership
# - Validate payment method
# - Resolve products from the database
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
# The AI only understands the user's request and extracts:
#
# - Product
# - Quantity
# - Address
# - Payment method
#
# Then this service validates everything against the database.
#
# Checkout flow:
#
# Product
#    ↓
# Quantity
#    ↓
# Address
#    ↓
# Payment
#    ↓
# Validate everything
#    ↓
# Resolve product from DB
#    ↓
# Read DB price
#    ↓
# Calculate line total
#    ↓
# Calculate subtotal
#    ↓
# Delivery charge = 0 for MVP
#    ↓
# Calculate final total
#    ↓
# Reserve inventory
#    ↓
# Create Order
#    ↓
# Create Order Items
#    ↓
# Create Payment
#    ↓
# Commit transaction
#    ↓
# Generate Bill
#    ↓
# Return Order
#
# =========================================================


from __future__ import annotations


from decimal import Decimal, InvalidOperation
from typing import Any


from sqlalchemy import func
from sqlalchemy.orm import Session


from backend.models.address import Address
from backend.models.order import Order
from backend.models.order_item import OrderItem
from backend.models.product import Product
from backend.models.payment import Payment


# =========================================================
# Supported Payment Methods
# =========================================================

SUPPORTED_PAYMENT_METHODS = {
    "upi",
    "cod",
}


# =========================================================
# MVP Delivery Charge
# =========================================================
#
# Delivery is intentionally free for the MVP.
#
# Later this can be replaced by:
#
# - merchant distance
# - location
# - cart value
# - delivery partner
# - time slot
# - express delivery
#
# IMPORTANT:
# The AI must NOT invent this value.
#
# =========================================================

MVP_DELIVERY_CHARGE = Decimal("0.00")


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

    This is critical because the frontend sends an
    address_id selected by the user.
    """

    if user_id is None:
        raise ValueError(
            "User ID is required."
        )

    if address_id is None:
        raise ValueError(
            "Address ID is required."
        )

    try:
        address_id = int(address_id)

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid address ID."
        )

    if address_id <= 0:
        raise ValueError(
            "Invalid address ID."
        )

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
    payment_method: str,
) -> str:
    """
    Validate and normalize payment method.

    Supported MVP methods:

        upi
        cod

    Common frontend/user representations are accepted.
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
            "Invalid payment method. "
            "Supported methods are UPI "
            "and Cash on Delivery."
        )

    return normalized


# =========================================================
# Normalize Quantity
# =========================================================


def _normalize_quantity(
    quantity: Any,
) -> int:
    """
    Convert quantity into a positive integer.

    Natural-language extraction such as:

        "3 packets"
        "three"
        "I need 3"

    should normally happen in the AI/entity layer.

    This service receives the extracted numeric value.
    """

    if isinstance(
        quantity,
        bool,
    ):
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
# Normalize Product Name
# =========================================================


def _normalize_product_name(
    product_name: Any,
) -> str:
    """
    Normalize a product name for database lookup.

    Examples:

        "Amul Milk"
        "amul milk"
        "  Amul Milk  "

    all become:

        "amul milk"
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
    Resolve a product from the database.

    Resolution priority:

        1. product_id
        2. exact product_name
        3. unique partial product_name

    The database is ALWAYS authoritative.

    The AI may provide:

        product_id
        OR
        product_name

    but never the price.

    Example:

        product_name = "amul milk"

    can resolve to:

        Product(id=1, name="Amul Milk")
    """

    # =====================================================
    # Product ID
    # =====================================================

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
                "Product ID must be a positive integer."
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

    # =====================================================
    # Product Name
    # =====================================================

    normalized_name = (
        _normalize_product_name(
            product_name
        )
    )

    # -----------------------------------------------------
    # Exact case-insensitive match
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Partial match
    #
    # Only accept a partial match when it is unique.
    #
    # Example:
    #
    # "maggi"
    #
    # can resolve to "Maggi 2-Minute Noodles"
    #
    # But if multiple products match "milk", do not guess.
    # -----------------------------------------------------

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

        formatted = ", ".join(
            names
        )

        raise ValueError(
            f"Multiple products matched "
            f"'{product_name}': {formatted}. "
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
    Safely convert a numeric database value into Decimal.

    Decimal is used for money calculations to avoid
    floating-point rounding problems.
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
# Money Formatting
# =========================================================


def _money(
    value: Decimal | float | int,
) -> float:
    """
    Convert Decimal into a JSON-friendly float.

    Database/model fields in the current MVP use numeric
    values compatible with float serialization.
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
    Validate items, resolve products, calculate prices,
    reserve inventory, and create OrderItem objects.

    Returns:

        (
            order_items,
            subtotal,
            bill_items
        )

    IMPORTANT:

    Prices ALWAYS come from Product.price.

    The AI/client cannot provide the authoritative price.
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

    order_items: list[OrderItem] = []

    bill_items: list[
        dict[str, Any]
    ] = []

    subtotal = Decimal("0.00")

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
            entry.get(
                "quantity"
            )
        )

        # -------------------------------------------------
        # Product identifier
        # -------------------------------------------------

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
    # Resolve and validate products
    # =====================================================

    for (
        key,
        quantity,
    ) in aggregated_items.items():

        identifier_type, identifier = key

        if identifier_type == "id":

            product = _resolve_product(
                db=db,
                product_id=identifier,
            )

        else:

            product = _resolve_product(
                db=db,
                product_name=identifier,
            )

        # -------------------------------------------------
        # Availability
        # -------------------------------------------------

        if not product.is_available:
            raise ValueError(
                f"'{product.name}' is currently unavailable."
            )

        # -------------------------------------------------
        # Stock
        # -------------------------------------------------

        if product.stock is None:
            raise ValueError(
                f"Stock information for "
                f"'{product.name}' is unavailable."
            )

        try:
            current_stock = int(
                product.stock
            )

        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                f"Invalid stock information for "
                f"'{product.name}'."
            )

        if current_stock < quantity:
            raise ValueError(
                f"Insufficient stock for "
                f"'{product.name}'. "
                f"Available: {current_stock}, "
                f"requested: {quantity}."
            )

        # -------------------------------------------------
        # Database Price
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
        # Calculate Line Total
        # -------------------------------------------------

        line_total = (
            unit_price
            * Decimal(quantity)
        )

        line_total = line_total.quantize(
            Decimal("0.01")
        )

        # -------------------------------------------------
        # Create Order Item
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
        # Reserve Inventory
        # -------------------------------------------------

        product.stock = (
            current_stock
            - quantity
        )

        # -------------------------------------------------
        # Add To Subtotal
        # -------------------------------------------------

        subtotal += line_total

        # -------------------------------------------------
        # Bill Item
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

    # =====================================================
    # Safety
    # =====================================================

    if not order_items:
        raise ValueError(
            "No valid order items were found."
        )

    if subtotal < 0:
        raise ValueError(
            "Invalid order subtotal."
        )

    return (
        order_items,
        subtotal,
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
    Generate the authoritative order bill.

    Current MVP:

        delivery_charge = 0

    Future versions can replace the delivery calculation
    without changing product/price logic.
    """

    delivery_charge = (
        MVP_DELIVERY_CHARGE
    )

    final_total = (
        subtotal
        + delivery_charge
    )

    final_total = final_total.quantize(
        Decimal("0.01")
    )

    subtotal = subtotal.quantize(
        Decimal("0.01")
    )

    delivery_charge = (
        delivery_charge.quantize(
            Decimal("0.01")
        )
    )

    return {
        "items": bill_items,

        "subtotal": _money(
            subtotal
        ),

        "delivery_charge": _money(
            delivery_charge
        ),

        "total": _money(
            final_total
        ),

        "payment_method": payment_method,
    }


# =========================================================
# Create Payment
# =========================================================


def _create_payment_record(
    db: Session,
    order: Order,
    payment_method: str,
    amount: float,
) -> Payment:
    """
    Create the payment record associated with an order.

    This is NOT a real payment gateway transaction.

    MVP:

        UPI
            -> pending

        COD
            -> pending

    A future payment gateway can update this to:

        success
        failed
        refunded
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
# Create Order
# =========================================================


def create_order(
    db: Session,
    user_id: int,
    address_id: int,
    items: list[dict[str, Any]],
    payment_method: str | None = None,
) -> Order:
    """
    Create a BuyQK order.

    Required:

        user_id
        address_id
        items
        payment_method

    Product item can contain:

        {
            "product_id": 9,
            "quantity": 3
        }

    OR:

        {
            "product_name": "Maggi 2-Minute Noodles",
            "quantity": 3
        }

    The product name is resolved against the database.

    The price is ALWAYS taken from the database.

    The returned Order contains a transient:

        order._buyqk_bill

    object for the response/tool layer.

    Example bill:

        {
            "order_id": 1,
            "items": [...],
            "subtotal": 45.0,
            "delivery_charge": 0.0,
            "total": 45.0,
            "payment_method": "cod"
        }
    """

    # =====================================================
    # Basic User Validation
    # =====================================================

    if user_id is None:
        raise ValueError(
            "User ID is required."
        )

    try:
        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid user ID."
        )

    if user_id <= 0:
        raise ValueError(
            "Invalid user ID."
        )

    # =====================================================
    # Address Validation
    # =====================================================

    if address_id is None:
        raise ValueError(
            "Address ID is required."
        )

    try:
        address_id = int(
            address_id
        )

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid address ID."
        )

    if address_id <= 0:
        raise ValueError(
            "Invalid address ID."
        )

    _validate_user_address(
        db=db,
        user_id=user_id,
        address_id=address_id,
    )

    # =====================================================
    # Payment Validation
    # =====================================================

    normalized_payment_method = (
        _validate_payment_method(
            payment_method
        )
    )

    # =====================================================
    # Build Order Items
    # =====================================================

    (
        order_items,
        subtotal,
        bill_items,
    ) = _build_order_items(
        db=db,
        items=items,
    )

    # =====================================================
    # Calculate Bill
    # =====================================================

    bill = _calculate_bill(
        bill_items=bill_items,
        subtotal=subtotal,
        payment_method=(
            normalized_payment_method
        ),
    )

    # =====================================================
    # Create Order
    # =====================================================

    order = Order(
        user_id=user_id,
        address_id=address_id,
        status="pending",
        payment_status="pending",
        total_amount=bill["total"],
    )

    # =====================================================
    # Attach Items
    # =====================================================

    order.items.extend(
        order_items
    )

    # =====================================================
    # Add Order
    # =====================================================

    db.add(
        order
    )

    # =====================================================
    # Flush
    #
    # We need order.id before creating Payment.
    # =====================================================

    try:

        db.flush()

    except Exception:

        db.rollback()

        raise

    # =====================================================
    # Order ID
    # =====================================================

    bill["order_id"] = (
        order.id
    )

    # =====================================================
    # Create Payment
    # =====================================================

    try:

        payment = _create_payment_record(
            db=db,
            order=order,
            payment_method=(
                normalized_payment_method
            ),
            amount=bill["total"],
        )

        db.add(
            payment
        )

    except Exception:

        db.rollback()

        raise

    # =====================================================
    # Final Commit
    # =====================================================

    try:

        db.commit()

    except Exception:

        db.rollback()

        raise

    # =====================================================
    # Refresh Order
    # =====================================================

    db.refresh(
        order
    )

    # =====================================================
    # Attach Payment Method
    # =====================================================

    order._buyqk_payment_method = (
        normalized_payment_method
    )

    # =====================================================
    # Attach Structured Bill
    # =====================================================
    #
    # This is intentionally a transient Python attribute.
    #
    # We do NOT add a new database column just for the MVP.
    #
    # The tool/response layer can read:
    #
    #     order._buyqk_bill
    #
    # =====================================================

    order._buyqk_bill = {
        "order_id": order.id,

        "items": bill["items"],

        "subtotal": bill["subtotal"],

        "delivery_charge": (
            bill["delivery_charge"]
        ),

        "total": bill["total"],

        "payment_method": (
            bill["payment_method"]
        ),
    }

    # =====================================================
    # Useful Compatibility Attributes
    # =====================================================

    order._buyqk_subtotal = (
        bill["subtotal"]
    )

    order._buyqk_delivery_charge = (
        bill["delivery_charge"]
    )

    order._buyqk_total = (
        bill["total"]
    )

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

    if user_id is None:
        raise ValueError(
            "User ID is required."
        )

    try:
        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid user ID."
        )

    if user_id <= 0:
        raise ValueError(
            "Invalid user ID."
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
    Build a bill for an existing order.

    This is useful when:

    - the order is retrieved later
    - the response node needs the bill
    - the tracking flow wants to display order details

    IMPORTANT:

    Prices are taken from OrderItem.unit_price, which is the
    historical price stored at order creation time.

    We DO NOT re-read the current Product.price here because
    product prices may change after the order was placed.
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

        product_name = None
        brand = None

        product = (
            db.query(Product)
            .filter(
                Product.id
                == item.product_id
            )
            .first()
        )

        if product is not None:

            product_name = (
                product.name
            )

            brand = (
                product.brand
            )

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

    delivery_charge = (
        MVP_DELIVERY_CHARGE
    )

    total = (
        subtotal
        + delivery_charge
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

        "total": _money(
            total
        ),

        "payment_method": (
            payment_method
        ),
    }


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

        Validate order
            ↓
        Validate ownership
            ↓
        Validate cancellable state
            ↓
        Restore stock
            ↓
        Update order status
            ↓
        Update payment
            ↓
        Commit
    """

    # =====================================================
    # Validate Order ID
    # =====================================================

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

    # =====================================================
    # Validate User
    # =====================================================

    if user_id is None:
        raise ValueError(
            "User ID is required."
        )

    try:
        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid user ID."
        )

    if user_id <= 0:
        raise ValueError(
            "Invalid user ID."
        )

    # =====================================================
    # Get Order
    # =====================================================

    order = get_order(
        db=db,
        order_id=order_id,
    )

    if order is None:
        raise ValueError(
            f"Order {order_id} does not exist."
        )

    # =====================================================
    # Ownership
    # =====================================================

    if order.user_id != user_id:
        raise ValueError(
            "You are not authorized to cancel "
            "this order."
        )

    # =====================================================
    # Already Cancelled
    # =====================================================

    if order.status == "cancelled":
        return order

    # =====================================================
    # Prevent Cancellation of Completed Orders
    # =====================================================

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

    # =====================================================
    # Restore Inventory
    # =====================================================

    try:

        for item in order.items:

            product = (
                db.query(Product)
                .filter(
                    Product.id
                    == item.product_id
                )
                .first()
            )

            if product is not None:

                current_stock = (
                    int(
                        product.stock
                        or 0
                    )
                )

                product.stock = (
                    current_stock
                    + item.quantity
                )

        # =================================================
        # Update Order
        # =================================================

        order.status = "cancelled"

        # =================================================
        # Update Order Payment Status
        # =================================================

        if hasattr(
            order,
            "payment_status",
        ):

            order.payment_status = (
                "cancelled"
            )

        # =================================================
        # Update Payment Record
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
                    "failed"
                )

        # =================================================
        # Commit
        # =================================================

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

    return order