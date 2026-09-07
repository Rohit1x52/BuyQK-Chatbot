"""
BuyQK MVP Product Seeder
=========================

Adds a local product catalog for chatbot/checkout testing.

This consolidated version keeps the larger MVP catalog while making
merchant/category handling, required Product fields, SKU defaults,
and per-product transaction handling safer.

Run from the project root:

    python -m backend.seed_products

The script is intentionally idempotent:
- Existing products with the same name are not duplicated.
- New products are inserted with stock for testing.

It uses the existing SQLAlchemy Product model and database
dependency instead of hard-coding a database URL.
"""

from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect

# Database initialization
from backend.database.init_db import init_db

# Import all models before creating tables
import backend.models

from backend.database.dependencies import get_db
from backend.models.product import Product

from typing import Any
import re
from decimal import Decimal

from backend.models.merchant import Merchant
from backend.models.category import Category


# ============================================================
# Test Catalog
# ============================================================

TEST_PRODUCTS = [

    # -------------------------------------------------------
    # Dairy
    # -------------------------------------------------------
    {
        "name": "Amul Milk",
        "brand": "Amul",
        "price": 32.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Amul Taaza Milk",
        "brand": "Amul",
        "price": 30.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Amul Full Cream Milk",
        "brand": "Amul",
        "price": 36.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Amul Butter",
        "brand": "Amul",
        "price": 55.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Amul Ghee",
        "brand": "Amul",
        "price": 560.00,
        "stock": 60,
        "category": "Dairy",
    },
    {
        "name": "Amul Cheese Slices",
        "brand": "Amul",
        "price": 120.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Amul Paneer",
        "brand": "Amul",
        "price": 90.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Mother Dairy Curd",
        "brand": "Mother Dairy",
        "price": 40.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Nestle a+ Milk",
        "brand": "Nestle",
        "price": 34.00,
        "stock": 100,
        "category": "Dairy",
    },
    {
        "name": "Britannia Cheese Cubes",
        "brand": "Britannia",
        "price": 140.00,
        "stock": 100,
        "category": "Dairy",
    },

    # -------------------------------------------------------
    # Grocery / Staples
    # -------------------------------------------------------
    {
        "name": "Tata Salt",
        "brand": "Tata",
        "price": 28.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Sugar",
        "brand": "Madhur",
        "price": 48.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Aashirvaad Atta",
        "brand": "Aashirvaad",
        "price": 280.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Fortune Sunflower Oil",
        "brand": "Fortune",
        "price": 145.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Saffola Gold Oil",
        "brand": "Saffola",
        "price": 165.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "India Gate Basmati Rice",
        "brand": "India Gate",
        "price": 220.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Sona Masoori Rice",
        "brand": "BuyQK",
        "price": 180.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Toor Dal",
        "brand": "BuyQK",
        "price": 160.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Chana Dal",
        "brand": "BuyQK",
        "price": 110.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Moong Dal",
        "brand": "BuyQK",
        "price": 140.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Rajma",
        "brand": "BuyQK",
        "price": 130.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Chana (Chickpeas)",
        "brand": "BuyQK",
        "price": 95.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Besan (Gram Flour)",
        "brand": "BuyQK",
        "price": 70.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Maida (All Purpose Flour)",
        "brand": "BuyQK",
        "price": 55.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Everest Turmeric Powder",
        "brand": "Everest",
        "price": 45.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Everest Red Chilli Powder",
        "brand": "Everest",
        "price": 55.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "MDH Garam Masala",
        "brand": "MDH",
        "price": 60.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Patanjali Honey",
        "brand": "Patanjali",
        "price": 120.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Kissan Mixed Fruit Jam",
        "brand": "Kissan",
        "price": 130.00,
        "stock": 100,
        "category": "Grocery",
    },

    # -------------------------------------------------------
    # Beverages
    # -------------------------------------------------------
    {
        "name": "Tata Tea Gold",
        "brand": "Tata",
        "price": 190.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Red Label Tea",
        "brand": "Brooke Bond",
        "price": 210.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Nescafe Classic Coffee",
        "brand": "Nescafe",
        "price": 260.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Bru Instant Coffee",
        "brand": "Bru",
        "price": 130.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Horlicks Health Drink",
        "brand": "Horlicks",
        "price": 245.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Bournvita",
        "brand": "Cadbury",
        "price": 230.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Real Fruit Juice - Mixed Fruit",
        "brand": "Real",
        "price": 110.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Frooti Mango Drink",
        "brand": "Frooti",
        "price": 20.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Coca-Cola 750ml",
        "brand": "Coca-Cola",
        "price": 40.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Sprite 750ml",
        "brand": "Sprite",
        "price": 40.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Bisleri Water 1L",
        "brand": "Bisleri",
        "price": 20.00,
        "stock": 100,
        "category": "Beverages",
    },

    # -------------------------------------------------------
    # Snacks
    # -------------------------------------------------------
    {
        "name": "Maggi 2-Minute Noodles",
        "brand": "Maggi",
        "price": 14.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Parle-G Biscuits",
        "brand": "Parle",
        "price": 10.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Britannia Good Day Biscuits",
        "brand": "Britannia",
        "price": 30.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Oreo Biscuits",
        "brand": "Cadbury",
        "price": 30.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Sunfeast Marie Light",
        "brand": "Sunfeast",
        "price": 35.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Lay's Classic Chips",
        "brand": "Lay's",
        "price": 20.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Kurkure Masala Munch",
        "brand": "Kurkure",
        "price": 20.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Haldiram's Bhujia",
        "brand": "Haldiram's",
        "price": 55.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Bikaji Aloo Bhujia",
        "brand": "Bikaji",
        "price": 50.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Act II Popcorn",
        "brand": "Act II",
        "price": 25.00,
        "stock": 100,
        "category": "Snacks",
    },

    # -------------------------------------------------------
    # Household
    # -------------------------------------------------------
    {
        "name": "Surf Excel Matic",
        "brand": "Surf Excel",
        "price": 220.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Ariel Detergent Powder",
        "brand": "Ariel",
        "price": 210.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Rin Detergent Bar",
        "brand": "Rin",
        "price": 20.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Vim Dishwash Bar",
        "brand": "Vim",
        "price": 10.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Vim Dishwash Gel",
        "brand": "Vim",
        "price": 99.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Harpic Toilet Cleaner",
        "brand": "Harpic",
        "price": 95.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Lizol Disinfectant Floor Cleaner",
        "brand": "Lizol",
        "price": 190.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Good Knight Mosquito Repellent",
        "brand": "Good Knight",
        "price": 65.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "All Out Mosquito Repellent Refill",
        "brand": "All Out",
        "price": 75.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Odonil Air Freshener",
        "brand": "Odonil",
        "price": 75.00,
        "stock": 100,
        "category": "Household",
    },

    # -------------------------------------------------------
    # Personal Care
    # -------------------------------------------------------
    {
        "name": "Colgate Strong Teeth",
        "brand": "Colgate",
        "price": 95.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Colgate MaxFresh",
        "brand": "Colgate",
        "price": 90.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Sensodyne Toothpaste",
        "brand": "Sensodyne",
        "price": 110.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Dettol Handwash",
        "brand": "Dettol",
        "price": 85.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Dove Soap",
        "brand": "Dove",
        "price": 65.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Lifebuoy Soap",
        "brand": "Lifebuoy",
        "price": 30.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Pears Soap",
        "brand": "Pears",
        "price": 55.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Head & Shoulders Shampoo",
        "brand": "Head & Shoulders",
        "price": 180.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Pantene Shampoo",
        "brand": "Pantene",
        "price": 170.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Nivea Body Lotion",
        "brand": "Nivea",
        "price": 220.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Vaseline Petroleum Jelly",
        "brand": "Vaseline",
        "price": 95.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Gillette Shaving Razor",
        "brand": "Gillette",
        "price": 99.00,
        "stock": 100,
        "category": "Personal Care",
    },
    {
        "name": "Whisper Sanitary Pads",
        "brand": "Whisper",
        "price": 150.00,
        "stock": 100,
        "category": "Personal Care",
    },

    # -------------------------------------------------------
    # Fruits
    # -------------------------------------------------------
    {
        "name": "Banana (1 dozen)",
        "brand": "BuyQK Fresh",
        "price": 60.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Apple Shimla (1kg)",
        "brand": "BuyQK Fresh",
        "price": 180.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Mango Alphonso (1kg)",
        "brand": "BuyQK Fresh",
        "price": 250.00,
        "stock": 80,
        "category": "Fruits",
    },
    {
        "name": "Orange (1kg)",
        "brand": "BuyQK Fresh",
        "price": 90.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Papaya (1pc)",
        "brand": "BuyQK Fresh",
        "price": 45.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Watermelon (1pc)",
        "brand": "BuyQK Fresh",
        "price": 60.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Pomegranate (1kg)",
        "brand": "BuyQK Fresh",
        "price": 160.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Grapes Green Seedless (1kg)",
        "brand": "BuyQK Fresh",
        "price": 90.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Pineapple (1pc)",
        "brand": "BuyQK Fresh",
        "price": 55.00,
        "stock": 100,
        "category": "Fruits",
    },
    {
        "name": "Guava (1kg)",
        "brand": "BuyQK Fresh",
        "price": 70.00,
        "stock": 100,
        "category": "Fruits",
    },

    # -------------------------------------------------------
    # Vegetables
    # -------------------------------------------------------
    {
        "name": "Onion (1kg)",
        "brand": "BuyQK Fresh",
        "price": 35.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Potato (1kg)",
        "brand": "BuyQK Fresh",
        "price": 28.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Tomato (1kg)",
        "brand": "BuyQK Fresh",
        "price": 40.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Green Chilli (250g)",
        "brand": "BuyQK Fresh",
        "price": 15.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Ginger (250g)",
        "brand": "BuyQK Fresh",
        "price": 25.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Garlic (250g)",
        "brand": "BuyQK Fresh",
        "price": 45.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Carrot (500g)",
        "brand": "BuyQK Fresh",
        "price": 30.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Cauliflower (1pc)",
        "brand": "BuyQK Fresh",
        "price": 35.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Cabbage (1pc)",
        "brand": "BuyQK Fresh",
        "price": 25.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Capsicum (500g)",
        "brand": "BuyQK Fresh",
        "price": 40.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Cucumber (500g)",
        "brand": "BuyQK Fresh",
        "price": 20.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Spinach (250g)",
        "brand": "BuyQK Fresh",
        "price": 20.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Brinjal (500g)",
        "brand": "BuyQK Fresh",
        "price": 30.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Lady Finger (500g)",
        "brand": "BuyQK Fresh",
        "price": 35.00,
        "stock": 100,
        "category": "Vegetables",
    },
    {
        "name": "Green Peas (500g)",
        "brand": "BuyQK Fresh",
        "price": 60.00,
        "stock": 100,
        "category": "Vegetables",
    },

    # -------------------------------------------------------
    # Pharmacy / Medicines
    # -------------------------------------------------------
    {
        "name": "Paracetamol 500mg (strip of 10)",
        "brand": "Generic",
        "price": 20.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Crocin Advance (strip of 15)",
        "brand": "GSK",
        "price": 30.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Dolo 650 (strip of 15)",
        "brand": "Micro Labs",
        "price": 30.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Combiflam Tablets (strip of 20)",
        "brand": "Sanofi",
        "price": 35.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Cetirizine Tablets (strip of 10)",
        "brand": "Generic",
        "price": 25.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Vicks Vaporub",
        "brand": "Vicks",
        "price": 95.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Digene Antacid Tablets",
        "brand": "Abbott",
        "price": 45.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Electral ORS Powder",
        "brand": "FDC",
        "price": 20.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Betadine Antiseptic Liquid",
        "brand": "Betadine",
        "price": 85.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Band-Aid Strips (pack)",
        "brand": "Band-Aid",
        "price": 40.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Volini Pain Relief Spray",
        "brand": "Volini",
        "price": 190.00,
        "stock": 100,
        "category": "Pharmacy",
    },
    {
        "name": "Revital H Multivitamin",
        "brand": "Sun Pharma",
        "price": 450.00,
        "stock": 100,
        "category": "Pharmacy",
    },

    # -------------------------------------------------------
    # Bakery
    # -------------------------------------------------------
    {
        "name": "Britannia Bread",
        "brand": "Britannia",
        "price": 45.00,
        "stock": 100,
        "category": "Bakery",
    },
    {
        "name": "Britannia Whole Wheat Bread",
        "brand": "Britannia",
        "price": 45.00,
        "stock": 100,
        "category": "Bakery",
    },
    {
        "name": "Harvest Gold Bread",
        "brand": "Harvest Gold",
        "price": 45.00,
        "stock": 100,
        "category": "Bakery",
    },
    {
        "name": "Britannia Cake Rusk",
        "brand": "Britannia",
        "price": 55.00,
        "stock": 100,
        "category": "Bakery",
    },
    {
        "name": "Britannia Milk Bikis",
        "brand": "Britannia",
        "price": 25.00,
        "stock": 100,
        "category": "Bakery",
    },
    {
        "name": "Cream Bun (pack of 6)",
        "brand": "BuyQK Fresh",
        "price": 40.00,
        "stock": 100,
        "category": "Bakery",
    },

    # -------------------------------------------------------
    # Baby Care
    # -------------------------------------------------------
    {
        "name": "Pampers Baby Diapers (M)",
        "brand": "Pampers",
        "price": 450.00,
        "stock": 100,
        "category": "Baby Care",
    },
    {
        "name": "Johnson's Baby Powder",
        "brand": "Johnson's",
        "price": 180.00,
        "stock": 100,
        "category": "Baby Care",
    },
    {
        "name": "Johnson's Baby Oil",
        "brand": "Johnson's",
        "price": 150.00,
        "stock": 100,
        "category": "Baby Care",
    },
    {
        "name": "Cerelac Baby Cereal",
        "brand": "Nestle",
        "price": 220.00,
        "stock": 100,
        "category": "Baby Care",
    },

    # -------------------------------------------------------
    # Pet Care
    # -------------------------------------------------------
    {
        "name": "Pedigree Adult Dog Food",
        "brand": "Pedigree",
        "price": 350.00,
        "stock": 100,
        "category": "Pet Care",
    },
    {
        "name": "Whiskas Cat Food",
        "brand": "Whiskas",
        "price": 320.00,
        "stock": 100,
        "category": "Pet Care",
    },
    {
        "name": "Pedigree Dog Treats",
        "brand": "Pedigree",
        "price": 150.00,
        "stock": 100,
        "category": "Pet Care",
    },

    # -------------------------------------------------------
    # Frozen Foods
    # -------------------------------------------------------
    {
        "name": "McCain French Fries",
        "brand": "McCain",
        "price": 120.00,
        "stock": 100,
        "category": "Frozen Foods",
    },
    {
        "name": "Amul Ice Cream Vanilla",
        "brand": "Amul",
        "price": 150.00,
        "stock": 100,
        "category": "Frozen Foods",
    },
    {
        "name": "Godrej Yummiez Chicken Nuggets",
        "brand": "Godrej",
        "price": 180.00,
        "stock": 100,
        "category": "Frozen Foods",
    },
]


# ============================================================
# Helpers
# ============================================================

def _existing_product(
    db: Any,
    name: str,
):
    """Find an existing product by case-insensitive name."""

    return (
        db.query(Product)
        .filter(
            Product.name.ilike(name)
        )
        .first()
    )


def _first_fk_value(
    db: Any,
    column: Any,
):
    """
    Return an existing ID for a required foreign-key column.

    This lets the seed work with projects where Product requires
    merchant_id/category_id/etc. and those parent tables already
    contain at least one row.
    """

    foreign_keys = list(column.foreign_keys)

    if not foreign_keys:
        return None

    target = foreign_keys[0].column

    try:
        return db.execute(
            select(target)
        ).scalars().first()
    except Exception:
        return None


def _default_for_column(
    column: Any,
    product_name: str | None = None,
):
    """
    Provide a safe MVP value for common required Product fields.

    Unknown fields are left as None so the script can clearly report
    the actual database constraint rather than silently inventing
    business data.
    """

    name = column.name.lower()

    if name in {"name", "product_name", "title"}:
        return "Test Product"

    if name in {"brand"}:
        return "BuyQK"

    if name in {
        "price",
        "unit_price",
        "selling_price",
        "mrp",
    }:
        return 1.0

    if name in {
        "stock",
        "quantity",
        "inventory",
        "available_stock",
    }:
        return 100

    if name in {
        "description",
        "short_description",
    }:
        return "BuyQK MVP test product"

    if name in {
        "sku",
        "product_code",
    }:
        base = product_name or "TEST-PRODUCT"
        slug = re.sub(
            r"[^A-Z0-9]+",
            "-",
            str(base).upper(),
        ).strip("-")
        return f"BUYQK-{slug or 'TEST-PRODUCT'}"

    if name in {
        "is_available",
        "available",
        "active",
        "is_active",
    }:
        return True

    if name in {
        "image_url",
        "image",
        "thumbnail",
    }:
        return None

    return None


def _build_product_kwargs(
    db: Any,
    product_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Build Product constructor kwargs from the actual model columns.

    This prevents the seed script from assuming columns that may not
    exist in the current MVP schema.
    """

    mapper = sa_inspect(Product)

    kwargs: dict[str, Any] = {}

    supplied_name = product_data["name"]

    for column in mapper.columns:

        # Never set primary key manually.
        if column.primary_key:
            continue

        column_name = column.name

        # Explicit catalog value.
        if column_name in product_data:
            kwargs[column_name] = product_data[column_name]
            continue

        # Required foreign key.
        if column.nullable is False and column.foreign_keys:

            fk_value = _first_fk_value(
                db=db,
                column=column,
            )

            if fk_value is not None:
                kwargs[column_name] = fk_value
                continue

        # Common defaults.
        if column.nullable is False and column.default is None:

            value = _default_for_column(
                column,
                product_name=supplied_name,
            )

            if value is not None:
                kwargs[column_name] = value

    # Make sure the real product name wins.
    if hasattr(Product, "name"):
        kwargs["name"] = supplied_name

    # Convert Decimal-friendly prices if the model expects them.
    if "price" in kwargs:
        try:
            kwargs["price"] = float(
                Decimal(str(kwargs["price"]))
            )
        except Exception:
            pass

    return kwargs

def _get_or_create_test_parents(db: Any):
    """
    Create the minimum merchant/category records required by
    Product for the local MVP test catalog.

    This function adapts to the current Merchant/Category model
    column names instead of assuming a particular schema.
    """

    # =========================================================
    # Test Merchant
    # =========================================================

    merchant = db.query(Merchant).first()

    if merchant is None:

        merchant_columns = {
            column.name
            for column in Merchant.__table__.columns
        }

        merchant_kwargs: dict[str, Any] = {}

        if "name" in merchant_columns:
            merchant_kwargs["name"] = "BuyQK Test Shop"

        if "business_name" in merchant_columns:
            merchant_kwargs["business_name"] = "BuyQK Test Shop"

        if "category" in merchant_columns:
            merchant_kwargs["category"] = "Grocery"

        if "phone" in merchant_columns:
            merchant_kwargs["phone"] = "9999999999"

        if "email" in merchant_columns:
            merchant_kwargs["email"] = "merchant@buyqk.test"

        if "address" in merchant_columns:
            merchant_kwargs["address"] = "BuyQK Test Address"

        if "is_active" in merchant_columns:
            merchant_kwargs["is_active"] = True

        if not merchant_kwargs:
            raise RuntimeError(
                "Could not determine usable fields for "
                "backend.models.merchant.Merchant."
            )

        merchant = Merchant(**merchant_kwargs)
        db.add(merchant)
        db.flush()

        print(
            f"[ADD] Test merchant "
            f"(id={merchant.id})"
        )

    else:
        print(
            f"[OK] Existing merchant "
            f"(id={merchant.id})"
        )

    # =========================================================
    # Test Categories
    # =========================================================

    category_names = [
        "Dairy",
        "Grocery",
        "Beverages",
        "Snacks",
        "Personal Care",
        "Household",
        "Fruits",
        "Vegetables",
        "Pharmacy",
        "Bakery",
        "Baby Care",
        "Pet Care",
        "Frozen Foods",
    ]

    categories: dict[str, Category] = {}

    existing_categories = (
        db.query(Category)
        .all()
    )

    category_columns = {
        column.name
        for column in Category.__table__.columns
    }

    for category in existing_categories:

        category_name = (
            getattr(category, "name", None)
            or getattr(category, "category_name", None)
        )

        if category_name:
            categories[
                str(category_name).strip().lower()
            ] = category

    for category_name in category_names:

        key = category_name.lower()

        if key in categories:
            continue

        category_kwargs: dict[str, Any] = {}

        if "name" in category_columns:
            category_kwargs["name"] = category_name

        elif "category_name" in category_columns:
            category_kwargs["category_name"] = category_name

        else:
            raise RuntimeError(
                "Category model has neither 'name' nor "
                "'category_name'. Update the test category "
                "seed to match backend.models.category.Category."
            )

        category = Category(**category_kwargs)

        db.add(category)
        db.flush()

        categories[key] = category

        print(
            f"[ADD] Category: {category_name} "
            f"(id={category.id})"
        )

    return merchant, categories



# ============================================================
# Seed
# ============================================================

def seed_products(*, auto_init: bool = True) -> None:

    if auto_init:
        print("[DB] Initializing BuyQK database schema...")
        init_db()
        print("[DB] Database schema ready.")

    db_generator = get_db()
    db = next(db_generator)

    inserted = 0
    skipped = 0
    failed = 0

    try:

        print("=" * 60)
        print("BuyQK MVP Product Seeder")
        print("=" * 60)

        # Product requires these foreign keys in the BuyQK MVP.
        product_columns = {
            column.name
            for column in Product.__table__.columns
        }

        missing_required_fks = [
            field
            for field in ("merchant_id", "category_id")
            if field not in product_columns
        ]

        if missing_required_fks:
            raise RuntimeError(
                "Product model is missing required seeder fields: "
                + ", ".join(missing_required_fks)
            )

        merchant, categories = _get_or_create_test_parents(
            db
        )

        # Parent records are now staged in the transaction.
        # Product inserts below can safely reference them.
        for product_data in TEST_PRODUCTS:

            name = product_data["name"]

            existing = _existing_product(
                db=db,
                name=name,
            )

            if existing is not None:

                print(
                    f"[SKIP] {name} "
                    f"(already exists: id={existing.id})"
                )

                skipped += 1
                continue

            savepoint = None

            try:

                category_name = product_data.get(
                    "category",
                    "Grocery",
                )

                savepoint = db.begin_nested()

                category = categories.get(
                    category_name.strip().lower()
                )

                if category is None:
                    raise ValueError(
                        f"Category '{category_name}' "
                        "was not created."
                    )

                kwargs = _build_product_kwargs(
                    db=db,
                    product_data=product_data,
                )

                # These are required by the Product schema.
                kwargs["merchant_id"] = merchant.id
                kwargs["category_id"] = category.id

                # "category" is only used by this seeder.
                kwargs.pop("category", None)

                product = Product(
                    **kwargs
                )

                db.add(product)
                db.flush()

                print(
                    f"[ADD]  {name} "
                    f"(id={product.id}) "
                    f"[merchant={merchant.id}, "
                    f"category={category.id}]"
                )

                savepoint.commit()
                inserted += 1

            except Exception as exc:

                if savepoint is not None:
                    try:
                        savepoint.rollback()
                    except Exception:
                        pass

                # The parent records remain intact; only this
                # product's savepoint is rolled back.
                print(
                    f"[FAIL] {name}: "
                    f"{type(exc).__name__}: {exc}"
                )

                failed += 1

        # Commit only when at least one product was inserted.
        # If nothing was inserted, closing the session rolls back any
        # newly-created parent records as well.
        if inserted > 0:
            db.commit()
        else:
            db.rollback()

        print()
        print("=" * 60)
        print("SEED SUMMARY")
        print("=" * 60)
        print(f"Inserted : {inserted}")
        print(f"Skipped  : {skipped}")
        print(f"Failed   : {failed}")
        print("=" * 60)

        if inserted == 0 and failed > 0:
            print()
            print(
                "No products were inserted."
            )
            print(
                "If Product requires merchant/category "
                "foreign keys, create at least one "
                "merchant/category first and rerun."
            )

    finally:

        try:
            db.close()
        except Exception:
            pass

        try:
            db_generator.close()
        except Exception:
            pass


if __name__ == "__main__":
    seed_products()