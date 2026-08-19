"""
BuyQK SQLAlchemy Models

This module imports and exposes all database models.

Importing the models here ensures that SQLAlchemy registers
their tables with Base.metadata before database initialization
or migrations create the schema.
"""

# =========================================================
# User and Address
# =========================================================

from .user import User
from .address import Address


# =========================================================
# Product Organization
# =========================================================

from .category import Category
from .merchant import Merchant
from .product import Product


# =========================================================
# Cart
# =========================================================

from .cart import Cart
from .cart_item import CartItem


# =========================================================
# Delivery and Order
# =========================================================

from .rider import Rider
from .order import Order
from .order_item import OrderItem


# =========================================================
# Payment and Support
# =========================================================

from .payment import Payment
from .support_ticket import SupportTicket


# =========================================================
# Conversation History
# =========================================================

from .conversation import ConversationHistory


# =========================================================
# Public Models
# =========================================================

__all__ = [
    # User / Address
    "User",
    "Address",

    # Product
    "Category",
    "Merchant",
    "Product",

    # Cart
    "Cart",
    "CartItem",

    # Delivery / Order
    "Rider",
    "Order",
    "OrderItem",

    # Payment / Support
    "Payment",
    "SupportTicket",

    # Conversation
    "ConversationHistory",
]