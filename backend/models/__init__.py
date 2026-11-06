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
# Restaurant and Menu
# =========================================================

from .restaurant import Restaurant
from .menu import Menu, MenuItem
from .food_order import FoodOrder, FoodOrderItem


# =========================================================
# Conversation History
# =========================================================

from .conversation import ConversationHistory


# =========================================================
# Service Booking
# =========================================================

from .service import Service
from .professional import Professional
from .professional_service import ProfessionalService
from .availability import Availability
from .booking import Booking


# =========================================================
# Merchant / Rider Onboarding - Phase 12
# =========================================================

from .merchant_document import MerchantDocument
from .rider_document import RiderDocument


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

    # Restaurant / Menu
    "Restaurant",
    "Menu",
    "MenuItem",
    "FoodOrder",
    "FoodOrderItem",

    # Conversation
    "ConversationHistory",

    # Service Booking
    "Service",
    "Professional",
    "ProfessionalService",
    "Availability",
    "Booking",

    # Merchant / Rider Onboarding
    "MerchantDocument",
    "RiderDocument",
]