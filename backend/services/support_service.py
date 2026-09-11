# =========================================================
# BuyQK - Support Service
# =========================================================
#
# Phase 9 - Customer Support
#
# Responsibilities:
#   - Validate support-ticket ownership
#   - Verify support requests against authoritative order/payment state
#   - Create support tickets
#   - Retrieve support tickets
#   - Retrieve a user's support tickets
#
# Database access remains inside this service.
# LangGraph never accesses SQLAlchemy models directly for support business
# logic.
# =========================================================

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.models.payment import Payment
from backend.models.support_ticket import SupportTicket


SUPPORT_ISSUE_TYPES = frozenset(
    {
        "wrong_product",
        "payment_failure",
        "delivery_delay",
        "refund_status",
        "human_escalation",
        "general_support",
    }
)


def _normalize_user_id(user_id: Any) -> int:
    try:
        normalized = int(user_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid user ID.")

    if normalized <= 0:
        raise ValueError("Invalid user ID.")

    return normalized


def _normalize_order_id(order_id: Any) -> int:
    try:
        normalized = int(order_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid order ID.")

    if normalized <= 0:
        raise ValueError("Invalid order ID.")

    return normalized


def _normalize_issue_type(issue_type: Any) -> str:
    normalized = str(issue_type or "").strip().lower()
    if normalized not in SUPPORT_ISSUE_TYPES:
        raise ValueError("Unsupported support issue type.")
    return normalized


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def _get_user_order(
    db: Session,
    user_id: int,
    order_id: int,
) -> Order:
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.user_id == user_id,
        )
        .first()
    )

    if order is None:
        raise ValueError(
            f"Order {order_id} was not found for this user."
        )

    return order


def _get_payment_for_order(
    db: Session,
    order: Order,
) -> Payment | None:
    # Relationship is already defined on Order and Payment.
    payment = getattr(order, "payment", None)
    if payment is not None:
        return payment

    return (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .first()
    )


def _get_payment_by_transaction(
    db: Session,
    user_id: int,
    transaction_id: str,
) -> tuple[Payment, Order]:
    payment = (
        db.query(Payment)
        .filter(Payment.transaction_id == transaction_id)
        .first()
    )

    if payment is None:
        raise ValueError(
            "The specified transaction could not be found."
        )

    order = (
        db.query(Order)
        .filter(
            Order.id == payment.order_id,
            Order.user_id == user_id,
        )
        .first()
    )

    if order is None:
        raise ValueError(
            "The specified transaction does not belong to this user."
        )

    return payment, order


def verify_support_request(
    db: Session,
    user_id: int,
    issue_type: str,
    *,
    order_id: int | None = None,
    transaction_id: str | None = None,
    evidence_url: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """
    Verify a customer-support request against authoritative backend state.

    This function does not create a ticket.

    Returns a structured result with:
        resolved:
            True when the backend can answer/resolve the request without
            human escalation.
        needs_ticket:
            True when a support ticket should be created.
        verification:
            Backend-derived facts safe for the Response Node.
    """
    normalized_user_id = _normalize_user_id(user_id)
    normalized_issue = _normalize_issue_type(issue_type)

    normalized_transaction = _normalize_optional_text(transaction_id)
    normalized_evidence = _normalize_optional_text(evidence_url)
    normalized_description = _normalize_optional_text(description)

    order: Order | None = None
    payment: Payment | None = None

    if order_id is not None:
        normalized_order_id = _normalize_order_id(order_id)
        order = _get_user_order(
            db,
            normalized_user_id,
            normalized_order_id,
        )

    if normalized_transaction:
        payment, transaction_order = _get_payment_by_transaction(
            db,
            normalized_user_id,
            normalized_transaction,
        )

        if order is not None and order.id != transaction_order.id:
            raise ValueError(
                "The supplied order and transaction do not refer to the same order."
            )

        order = transaction_order

    if normalized_issue == "wrong_product":
        if order is None:
            raise ValueError("Order ID is required for a wrong-product issue.")

        if not normalized_evidence:
            return {
                "success": True,
                "type": "support_verification",
                "issue_type": normalized_issue,
                "resolved": False,
                "needs_ticket": True,
                "reason": "evidence_required",
                "order_id": order.id,
                "verification": {
                    "order_verified": True,
                    "evidence_received": False,
                },
            }

        # The MVP backend can verify order ownership and evidence presence,
        # but it does not have a computer-vision/product-image verification
        # service. Therefore it must not claim the image proves the wrong item.
        return {
            "success": True,
            "type": "support_verification",
            "issue_type": normalized_issue,
            "resolved": False,
            "needs_ticket": True,
            "reason": "manual_product_issue_review_required",
            "order_id": order.id,
            "verification": {
                "order_verified": True,
                "evidence_received": True,
            },
        }

    if normalized_issue == "payment_failure":
        if order is None:
            raise ValueError(
                "Transaction ID or Order ID is required for a payment issue."
            )

        if payment is None:
            payment = _get_payment_for_order(db, order)

        if payment is None:
            return {
                "success": True,
                "type": "support_verification",
                "issue_type": normalized_issue,
                "resolved": False,
                "needs_ticket": True,
                "reason": "payment_record_not_found",
                "order_id": order.id,
                "verification": {
                    "payment_found": False,
                },
            }

        payment_status = str(
            getattr(payment, "payment_status", None) or ""
        ).strip().lower()

        if payment_status == "failed":
            return {
                "success": True,
                "type": "support_verification",
                "issue_type": normalized_issue,
                "resolved": True,
                "needs_ticket": False,
                "reason": "payment_failure_confirmed",
                "order_id": order.id,
                "transaction_id": getattr(payment, "transaction_id", None),
                "verification": {
                    "payment_found": True,
                    "payment_status": payment_status,
                },
            }

        # A successful/refunded/pending payment contradicts a simple
        # "payment failed" claim. Do not invent a resolution; escalate.
        return {
            "success": True,
            "type": "support_verification",
            "issue_type": normalized_issue,
            "resolved": False,
            "needs_ticket": True,
            "reason": "payment_status_requires_support_review",
            "order_id": order.id,
            "transaction_id": getattr(payment, "transaction_id", None),
            "verification": {
                "payment_found": True,
                "payment_status": payment_status,
            },
        }

    if normalized_issue == "delivery_delay":
        if order is None:
            # PDF specifies a latest-delivery-status path. Use the most recent
            # order belonging to the authenticated user when no order ID is
            # supplied.
            order = (
                db.query(Order)
                .filter(Order.user_id == normalized_user_id)
                .order_by(Order.id.desc())
                .first()
            )

        if order is None:
            raise ValueError(
                "No order was found for delivery-status verification."
            )

        order_status = str(
            getattr(order, "status", None) or ""
        ).strip().lower()

        return {
            "success": True,
            "type": "support_verification",
            "issue_type": normalized_issue,
            "resolved": True,
            "needs_ticket": False,
            "reason": "delivery_status_verified",
            "order_id": order.id,
            "verification": {
                "order_verified": True,
                "order_status": order_status,
            },
        }

    if normalized_issue == "refund_status":
        if order is None:
            raise ValueError("Order ID is required for refund-status verification.")

        if payment is None:
            payment = _get_payment_for_order(db, order)

        if payment is None:
            return {
                "success": True,
                "type": "support_verification",
                "issue_type": normalized_issue,
                "resolved": True,
                "needs_ticket": False,
                "reason": "refund_payment_record_not_found",
                "order_id": order.id,
                "verification": {
                    "payment_found": False,
                    "refund_status": "not_available",
                },
            }

        payment_status = str(
            getattr(payment, "payment_status", None) or ""
        ).strip().lower()

        refund_status = (
            "refunded"
            if payment_status == "refunded"
            else payment_status or "unknown"
        )

        return {
            "success": True,
            "type": "support_verification",
            "issue_type": normalized_issue,
            "resolved": True,
            "needs_ticket": False,
            "reason": "refund_status_verified",
            "order_id": order.id,
            "transaction_id": getattr(payment, "transaction_id", None),
            "verification": {
                "payment_found": True,
                "payment_status": payment_status,
                "refund_status": refund_status,
            },
        }

    # Human escalation and general support intentionally require a ticket.
    return {
        "success": True,
        "type": "support_verification",
        "issue_type": normalized_issue,
        "resolved": False,
        "needs_ticket": True,
        "reason": (
            "human_escalation_requested"
            if normalized_issue == "human_escalation"
            else "support_review_required"
        ),
        "order_id": order.id if order is not None else None,
        "verification": {
            "order_verified": order is not None,
        },
    }


def create_ticket(
    db: Session,
    user_id: int,
    subject: str,
    description: str,
    order_id: int | None = None,
    *,
    image_url: str | None = None,
    issue_type: str | None = None,
) -> SupportTicket:
    """
    Create a support ticket while preserving the existing function signature.

    ``subject`` remains the backwards-compatible positional issue label.
    Phase 9 can additionally provide ``issue_type`` and ``image_url``.
    """
    normalized_user_id = _normalize_user_id(user_id)

    subject = str(subject or "").strip()
    description = str(description or "").strip()

    if not subject:
        raise ValueError("Ticket subject cannot be empty.")

    if not description:
        raise ValueError("Ticket description cannot be empty.")

    normalized_issue_type = (
        _normalize_issue_type(issue_type)
        if issue_type is not None
        else (
            subject
            if subject in SUPPORT_ISSUE_TYPES
            else "general_support"
        )
    )

    normalized_order_id: int | None = None
    if order_id is not None:
        normalized_order_id = _normalize_order_id(order_id)
        _get_user_order(
            db,
            normalized_user_id,
            normalized_order_id,
        )

    normalized_image_url = _normalize_optional_text(image_url)

    ticket = SupportTicket(
        user_id=normalized_user_id,
        order_id=normalized_order_id,
        issue_type=normalized_issue_type,
        description=description,
        status="open",
        image_url=normalized_image_url,
    )

    db.add(ticket)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(ticket)
    return ticket


def get_ticket(
    db: Session,
    ticket_id: int,
    user_id: int | None = None,
) -> SupportTicket | None:
    query = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
    )

    if user_id is not None:
        query = query.filter(
            SupportTicket.user_id == user_id
        )

    return query.first()


def get_user_tickets(
    db: Session,
    user_id: int,
    limit: int = 20,
) -> list[SupportTicket]:
    normalized_user_id = _normalize_user_id(user_id)

    return (
        db.query(SupportTicket)
        .filter(
            SupportTicket.user_id == normalized_user_id
        )
        .order_by(
            SupportTicket.id.desc()
        )
        .limit(limit)
        .all()
    )
