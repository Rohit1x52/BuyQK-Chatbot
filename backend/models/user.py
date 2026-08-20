"""
The User model represents a BuyQK customer. It will store the basic information needed to:
Identify the customer.
Authenticate them later.
Associate addresses with them.
Associate orders with them.
Associate support tickets with them.
Associate conversation history with them.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class User(Base):
    """
    Represents a BuyQK customer.
    """

    __tablename__ = "users"

    # Unique identifier for the user
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Customer's full name
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # Customer's email address
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    # Customer's phone number
    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True
    )

    # Hashed password
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    # Preferred conversation language
    # Supported by the BuyQK conversation design:
    # English, Hindi, and Hinglish.
    language: Mapped[str] = mapped_column(
        String(20),
        default="English",
        nullable=False
    )

    # Account creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Last account update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Store address
    addresses = relationship(
        "Address",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Orders placed by the user
    orders = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Support tickets created by the user
    support_tickets = relationship(
        "SupportTicket",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Conversation history connected to the user
    conversation_history = relationship(
        "ConversationHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    carts = relationship(
        "Cart",
        back_populates="user",
        cascade="all, delete-orphan",
    )