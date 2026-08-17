# Purpose:
# Contains business logic for BuyQK support-ticket operations.
#
# Responsibilities:
# - Create support tickets
# - Retrieve a support ticket
# - Retrieve a user's support tickets
# - Validate user/order relationships
#
# This service is used by:
# - FastAPI
# - LangGraph tools
#
# Database access remains inside this service rather than
# inside LangGraph nodes.


from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.models.support_ticket import SupportTicket


# ---------------------------------------------------------
# Create Support Ticket
# ---------------------------------------------------------

def create_ticket(
    db: Session,
    user_id: int,
    subject: str,
    description: str,
    order_id: int | None = None,
) -> SupportTicket:
    """
    Create a new support ticket.

    Args:
        db:
            Active SQLAlchemy database session.

        user_id:
            ID of the customer creating the ticket.

        subject:
            Short description/title of the issue.

        description:
            Detailed description of the issue.

        order_id:
            Optional order associated with the issue.

    Returns:
        Newly created SupportTicket object.

    Raises:
        ValueError:
            If required information is invalid or the
            referenced order does not belong to the user.
    """

    # -----------------------------------------------------
    # Basic validation
    # -----------------------------------------------------

    if user_id <= 0:
        raise ValueError(
            "Invalid user ID."
        )

    subject = subject.strip()
    description = description.strip()

    if not subject:
        raise ValueError(
            "Ticket subject cannot be empty."
        )

    if not description:
        raise ValueError(
            "Ticket description cannot be empty."
        )

    # -----------------------------------------------------
    # Validate order if supplied
    # -----------------------------------------------------

    if order_id is not None:

        if order_id <= 0:
            raise ValueError(
                "Invalid order ID."
            )

        order = (
            db.query(Order)
            .filter(
                Order.id == order_id
            )
            .first()
        )

        if order is None:
            raise ValueError(
                f"Order {order_id} does not exist."
            )

        # Important authorization check.
        #
        # A user must not be able to create a ticket
        # against another user's order.
        if order.user_id != user_id:
            raise ValueError(
                "The specified order does not "
                "belong to this user."
            )

    # -----------------------------------------------------
    # Create ticket
    # -----------------------------------------------------

    ticket = SupportTicket(
        user_id=user_id,
        order_id=order_id,
        issue_type=subject,
        description=description,
        status="open",
    )

    db.add(ticket)

    # -----------------------------------------------------
    # Commit transaction
    # -----------------------------------------------------

    try:

        db.commit()

    except Exception:

        db.rollback()

        raise

    # -----------------------------------------------------
    # Refresh object
    # -----------------------------------------------------

    db.refresh(ticket)

    return ticket


# ---------------------------------------------------------
# Get Ticket
# ---------------------------------------------------------

def get_ticket(
    db: Session,
    ticket_id: int,
    user_id: int | None = None,
) -> SupportTicket | None:
    """
    Retrieve a support ticket.

    Args:
        db:
            Active SQLAlchemy database session.

        ticket_id:
            Support ticket ID.

        user_id:
            Optional user ID.

            If supplied, the ticket must belong to
            that user.

    Returns:
        SupportTicket object if found and authorized,
        otherwise None.
    """

    query = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.id == ticket_id
        )
    )

    # -----------------------------------------------------
    # Optional ownership check
    # -----------------------------------------------------

    if user_id is not None:

        query = query.filter(
            SupportTicket.user_id == user_id
        )

    return query.first()


# ---------------------------------------------------------
# Get User Tickets
# ---------------------------------------------------------

def get_user_tickets(
    db: Session,
    user_id: int,
    limit: int = 20,
) -> list[SupportTicket]:
    """
    Retrieve recent support tickets belonging to a user.

    Args:
        db:
            Active SQLAlchemy database session.

        user_id:
            Customer ID.

        limit:
            Maximum number of tickets to return.

    Returns:
        List of SupportTicket objects.
    """

    if user_id <= 0:
        raise ValueError(
            "Invalid user ID."
        )

    return (
        db.query(SupportTicket)
        .filter(
            SupportTicket.user_id == user_id
        )
        .order_by(
            SupportTicket.id.desc()
        )
        .limit(limit)
        .all()
    )