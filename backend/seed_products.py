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
# Expanded MVP Catalog
# ============================================================
# Product-centric catalogue. Shop/merchant modelling is deferred.
# Additional products use the existing Product fields only.

ADDITIONAL_PRODUCTS = [
    {'name': 'Aashirvaad Multigrain Atta', 'brand': 'Aashirvaad', 'price': 320.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Pillsbury Chakki Atta', 'brand': 'Pillsbury', 'price': 310.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Fortune Chakki Atta', 'brand': 'Fortune', 'price': 300.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Tata Sampann Toor Dal', 'brand': 'Tata Sampann', 'price': 190.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Tata Sampann Moong Dal', 'brand': 'Tata Sampann', 'price': 175.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Tata Sampann Masoor Dal', 'brand': 'Tata Sampann', 'price': 150.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Rajdhani Rajma', 'brand': 'Rajdhani', 'price': 145.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'India Gate Dubar Rice', 'brand': 'India Gate', 'price': 260.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Daawat Brown Rice', 'brand': 'Daawat', 'price': 190.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Fortune Groundnut Oil', 'brand': 'Fortune', 'price': 185.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Fortune Rice Bran Oil', 'brand': 'Fortune', 'price': 170.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Saffola Active Oil', 'brand': 'Saffola', 'price': 180.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Tata Rock Salt', 'brand': 'Tata', 'price': 45.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Catch Black Pepper', 'brand': 'Catch', 'price': 95.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Everest Coriander Powder', 'brand': 'Everest', 'price': 55.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'MDH Chana Masala', 'brand': 'MDH', 'price': 60.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Kissan Tomato Ketchup', 'brand': 'Kissan', 'price': 120.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Veeba Mayonnaise', 'brand': 'Veeba', 'price': 145.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Dabur Honey', 'brand': 'Dabur', 'price': 190.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Saffola Oats 1kg', 'brand': 'Saffola', 'price': 180.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Quaker Oats 1kg', 'brand': 'Quaker', 'price': 190.0, 'stock': 100, 'category': 'Grocery'},
    {'name': "Kellogg's Corn Flakes", 'brand': "Kellogg's", 'price': 210.0, 'stock': 100, 'category': 'Grocery'},
    {'name': "Bagrry's Muesli", 'brand': "Bagrry's", 'price': 290.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Pintola Peanut Butter', 'brand': 'Pintola', 'price': 350.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Weikfield Baking Powder', 'brand': 'Weikfield', 'price': 55.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Weikfield Custard Powder', 'brand': 'Weikfield', 'price': 75.0, 'stock': 100, 'category': 'Grocery'},
    {'name': 'Apple Royal Gala 1kg', 'brand': 'BuyQK Fresh', 'price': 220.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Apple Fuji 1kg', 'brand': 'BuyQK Fresh', 'price': 240.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Banana Robusta 1 dozen', 'brand': 'BuyQK Fresh', 'price': 55.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Mango Kesar 1kg', 'brand': 'BuyQK Fresh', 'price': 180.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Mango Dasheri 1kg', 'brand': 'BuyQK Fresh', 'price': 140.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Mosambi 1kg', 'brand': 'BuyQK Fresh', 'price': 100.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Lemon 250g', 'brand': 'BuyQK Fresh', 'price': 35.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Kiwi 3pc', 'brand': 'BuyQK Fresh', 'price': 140.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Dragon Fruit 1pc', 'brand': 'BuyQK Fresh', 'price': 110.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Strawberry 200g', 'brand': 'BuyQK Fresh', 'price': 140.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Blueberry 125g', 'brand': 'BuyQK Fresh', 'price': 180.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Pear 1kg', 'brand': 'BuyQK Fresh', 'price': 150.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Chikoo 1kg', 'brand': 'BuyQK Fresh', 'price': 80.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Muskmelon 1pc', 'brand': 'BuyQK Fresh', 'price': 65.0, 'stock': 100, 'category': 'Fruits'},
    {'name': 'Broccoli 500g', 'brand': 'BuyQK Fresh', 'price': 70.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Beetroot 500g', 'brand': 'BuyQK Fresh', 'price': 35.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Radish 500g', 'brand': 'BuyQK Fresh', 'price': 30.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Bottle Gourd 1pc', 'brand': 'BuyQK Fresh', 'price': 45.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Bitter Gourd 500g', 'brand': 'BuyQK Fresh', 'price': 40.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Ridge Gourd 500g', 'brand': 'BuyQK Fresh', 'price': 45.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Pumpkin 1kg', 'brand': 'BuyQK Fresh', 'price': 45.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'French Beans 500g', 'brand': 'BuyQK Fresh', 'price': 55.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Sweet Corn 2pc', 'brand': 'BuyQK Fresh', 'price': 50.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Red Capsicum 500g', 'brand': 'BuyQK Fresh', 'price': 90.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Mushroom 200g', 'brand': 'BuyQK Fresh', 'price': 80.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Coriander 100g', 'brand': 'BuyQK Fresh', 'price': 20.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Mint 100g', 'brand': 'BuyQK Fresh', 'price': 20.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Spring Onion 250g', 'brand': 'BuyQK Fresh', 'price': 30.0, 'stock': 100, 'category': 'Vegetables'},
    {'name': 'Paneer Butter Masala', 'brand': 'BuyQK Food', 'price': 199.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Kadai Paneer', 'brand': 'BuyQK Food', 'price': 189.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Shahi Paneer', 'brand': 'BuyQK Food', 'price': 199.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Dal Makhani', 'brand': 'BuyQK Food', 'price': 159.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Dal Tadka', 'brand': 'BuyQK Food', 'price': 139.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Chole Bhature', 'brand': 'BuyQK Food', 'price': 149.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Rajma Rice', 'brand': 'BuyQK Food', 'price': 149.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Veg Biryani', 'brand': 'BuyQK Food', 'price': 179.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Chicken Biryani', 'brand': 'BuyQK Food', 'price': 249.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Mutton Biryani', 'brand': 'BuyQK Food', 'price': 299.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Butter Chicken', 'brand': 'BuyQK Food', 'price': 279.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Chicken Tikka', 'brand': 'BuyQK Food', 'price': 249.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Paneer Tikka', 'brand': 'BuyQK Food', 'price': 219.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Tandoori Chicken Half', 'brand': 'BuyQK Food', 'price': 299.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Veg Manchurian', 'brand': 'BuyQK Food', 'price': 169.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Chilli Paneer', 'brand': 'BuyQK Food', 'price': 189.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Hakka Noodles', 'brand': 'BuyQK Food', 'price': 159.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Chicken Fried Rice', 'brand': 'BuyQK Food', 'price': 199.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Garlic Naan', 'brand': 'BuyQK Food', 'price': 65.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Gulab Jamun 2pc', 'brand': 'BuyQK Food', 'price': 79.0, 'stock': 50, 'category': 'Restaurant'},
    {'name': 'Cold Coffee', 'brand': 'BuyQK Food', 'price': 129.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Cappuccino', 'brand': 'BuyQK Food', 'price': 139.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Cafe Latte', 'brand': 'BuyQK Food', 'price': 149.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Americano', 'brand': 'BuyQK Food', 'price': 119.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Masala Chai', 'brand': 'BuyQK Food', 'price': 79.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Green Tea', 'brand': 'BuyQK Food', 'price': 89.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Mango Smoothie', 'brand': 'BuyQK Food', 'price': 169.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Chocolate Milkshake', 'brand': 'BuyQK Food', 'price': 179.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Chicken Sandwich', 'brand': 'BuyQK Food', 'price': 189.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Veg Grilled Sandwich', 'brand': 'BuyQK Food', 'price': 159.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Paneer Wrap', 'brand': 'BuyQK Food', 'price': 179.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Chicken Wrap', 'brand': 'BuyQK Food', 'price': 199.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Veg Pasta', 'brand': 'BuyQK Food', 'price': 179.0, 'stock': 50, 'category': 'Cafe'},
    {'name': 'Chocolate Cake Slice', 'brand': 'BuyQK Food', 'price': 119.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Red Velvet Cake Slice', 'brand': 'BuyQK Food', 'price': 139.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Black Forest Cake Slice', 'brand': 'BuyQK Food', 'price': 129.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Chocolate Truffle Cake 500g', 'brand': 'BuyQK Food', 'price': 499.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Chocolate Croissant', 'brand': 'BuyQK Food', 'price': 99.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Chocolate Muffin', 'brand': 'BuyQK Food', 'price': 79.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Chocolate Donut', 'brand': 'BuyQK Food', 'price': 69.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Garlic Bread', 'brand': 'BuyQK Food', 'price': 99.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Veg Puff', 'brand': 'BuyQK Food', 'price': 49.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Paneer Puff', 'brand': 'BuyQK Food', 'price': 59.0, 'stock': 50, 'category': 'Bakery'},
    {'name': 'Veg Burger', 'brand': 'BuyQK Food', 'price': 129.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Chicken Burger', 'brand': 'BuyQK Food', 'price': 179.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Cheese Burger', 'brand': 'BuyQK Food', 'price': 159.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Margherita Pizza', 'brand': 'BuyQK Food', 'price': 199.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Farmhouse Pizza', 'brand': 'BuyQK Food', 'price': 249.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Chicken Pepperoni Pizza', 'brand': 'BuyQK Food', 'price': 299.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Chicken Nuggets 6pc', 'brand': 'BuyQK Food', 'price': 179.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Chicken Wings 6pc', 'brand': 'BuyQK Food', 'price': 229.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Veg Momos 8pc', 'brand': 'BuyQK Food', 'price': 129.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Chicken Momos 8pc', 'brand': 'BuyQK Food', 'price': 169.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Chicken Kathi Roll', 'brand': 'BuyQK Food', 'price': 189.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Paneer Kathi Roll', 'brand': 'BuyQK Food', 'price': 169.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Chicken Shawarma', 'brand': 'BuyQK Food', 'price': 179.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'White Sauce Pasta', 'brand': 'BuyQK Food', 'price': 199.0, 'stock': 50, 'category': 'Fast Food'},
    {'name': 'Paracetamol 650mg Tablets 10s', 'brand': 'Generic', 'price': 25.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Ibuprofen 400mg Tablets 10s', 'brand': 'Generic', 'price': 35.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Aspirin 75mg Tablets 14s', 'brand': 'Generic', 'price': 30.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'ORS Electrolyte Sachet', 'brand': 'Electral', 'price': 22.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Vitamin C 500mg Tablets 20s', 'brand': 'Generic', 'price': 90.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Multivitamin Tablets 30s', 'brand': 'Generic', 'price': 180.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Calcium Vitamin D Tablets 30s', 'brand': 'Generic', 'price': 220.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Antiseptic Cream 20g', 'brand': 'Generic', 'price': 55.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Calamine Lotion 100ml', 'brand': 'Generic', 'price': 95.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Cough Syrup 100ml', 'brand': 'Generic', 'price': 110.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Saline Nasal Spray', 'brand': 'Generic', 'price': 120.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': False},
    {'name': 'Digital Thermometer', 'brand': 'Dr Trust', 'price': 180.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Pulse Oximeter', 'brand': 'Dr Trust', 'price': 799.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Blood Pressure Monitor', 'brand': 'Dr Trust', 'price': 1899.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Glucometer Kit', 'brand': 'Accu-Chek', 'price': 999.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Glucometer Test Strips 50s', 'brand': 'Accu-Chek', 'price': 999.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Heating Pad', 'brand': 'Dr Trust', 'price': 899.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Nebulizer Machine', 'brand': 'Dr Trust', 'price': 1499.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Digital Weighing Scale', 'brand': 'Dr Trust', 'price': 999.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Knee Support', 'brand': 'Tynor', 'price': 699.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Wrist Support', 'brand': 'Tynor', 'price': 399.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Ankle Support', 'brand': 'Tynor', 'price': 499.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Lumbar Back Support', 'brand': 'Tynor', 'price': 999.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Elastic Crepe Bandage', 'brand': 'Tynor', 'price': 199.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Sterile Gauze Pads Pack', 'brand': 'Generic', 'price': 120.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Nitrile Examination Gloves 100s', 'brand': 'Generic', 'price': 450.0, 'stock': 50, 'category': 'Healthcare', 'prescription_required': False},
    {'name': 'Vitamin D3 60000 IU Capsules 4s', 'brand': 'Generic', 'price': 120.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Amoxicillin 500mg Capsules 10s', 'brand': 'Generic', 'price': 90.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Azithromycin 500mg Tablets 5s', 'brand': 'Generic', 'price': 110.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Cefixime 200mg Tablets 10s', 'brand': 'Generic', 'price': 140.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Metformin 500mg Tablets 20s', 'brand': 'Generic', 'price': 55.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Amlodipine 5mg Tablets 20s', 'brand': 'Generic', 'price': 45.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Telmisartan 40mg Tablets 15s', 'brand': 'Generic', 'price': 85.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Atorvastatin 10mg Tablets 15s', 'brand': 'Generic', 'price': 65.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Pantoprazole 40mg Tablets 15s', 'brand': 'Generic', 'price': 80.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Levocetirizine 5mg Tablets 10s', 'brand': 'Generic', 'price': 35.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Montelukast 10mg Tablets 10s', 'brand': 'Generic', 'price': 90.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Diclofenac 50mg Tablets 10s', 'brand': 'Generic', 'price': 40.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Aceclofenac 100mg Tablets 10s', 'brand': 'Generic', 'price': 55.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'Mupirocin Ointment 5g', 'brand': 'Generic', 'price': 95.0, 'stock': 50, 'category': 'Pharmacy', 'prescription_required': True},
    {'name': 'iPhone 16 128GB', 'brand': 'Apple', 'price': 69900.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '128GB', 'network': '5G'}},
    {'name': 'iPhone 16 256GB', 'brand': 'Apple', 'price': 79900.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'iPhone 16 Plus 128GB', 'brand': 'Apple', 'price': 79900.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '128GB', 'network': '5G'}},
    {'name': 'iPhone 16 Pro 256GB', 'brand': 'Apple', 'price': 109900.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'iPhone 16 Pro Max 256GB', 'brand': 'Apple', 'price': 119900.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Galaxy S25 256GB', 'brand': 'Samsung', 'price': 80999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Galaxy S25 Ultra 256GB', 'brand': 'Samsung', 'price': 129999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Galaxy A56 128GB', 'brand': 'Samsung', 'price': 41999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '128GB', 'network': '5G'}},
    {'name': 'Pixel 9 256GB', 'brand': 'Google', 'price': 84999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'OnePlus 13 256GB', 'brand': 'OnePlus', 'price': 69999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'OnePlus 13R 256GB', 'brand': 'OnePlus', 'price': 42999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Xiaomi 15 256GB', 'brand': 'Xiaomi', 'price': 64999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Nothing Phone 3a 128GB', 'brand': 'Nothing', 'price': 24999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '128GB', 'network': '5G'}},
    {'name': 'Motorola Edge 60 Pro 256GB', 'brand': 'Motorola', 'price': 29999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Vivo V50 256GB', 'brand': 'Vivo', 'price': 34999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Oppo Reno 13 256GB', 'brand': 'Oppo', 'price': 37999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'Realme GT 7 256GB', 'brand': 'Realme', 'price': 39999.0, 'stock': 20, 'category': 'Mobile', 'specifications': {'storage': '256GB', 'network': '5G'}},
    {'name': 'MacBook Air M4 13-inch 16GB 256GB', 'brand': 'Apple', 'price': 99900.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'MacBook Air M4 15-inch 16GB 256GB', 'brand': 'Apple', 'price': 119900.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'MacBook Pro M4 14-inch 16GB 512GB', 'brand': 'Apple', 'price': 169900.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'Dell Inspiron 15 Core i5 16GB 512GB', 'brand': 'Dell', 'price': 65990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'Dell XPS 14 Core Ultra 7 32GB 1TB', 'brand': 'Dell', 'price': 189990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'HP Pavilion 14 Core i5 16GB 512GB', 'brand': 'HP', 'price': 67990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'HP Envy x360 14 Core Ultra 5 16GB 512GB', 'brand': 'HP', 'price': 99990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'Lenovo IdeaPad Slim 5 Core Ultra 5 16GB 512GB', 'brand': 'Lenovo', 'price': 69990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'Lenovo LOQ 15 Core i5 16GB 512GB', 'brand': 'Lenovo', 'price': 94990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'ASUS Zenbook 14 OLED Core Ultra 7 16GB 1TB', 'brand': 'ASUS', 'price': 109990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'ASUS ROG Zephyrus G14 Ryzen 9 32GB 1TB', 'brand': 'ASUS', 'price': 179990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'Acer Aspire 5 Core i5 16GB 512GB', 'brand': 'Acer', 'price': 54990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'MSI Katana 15 Core i7 16GB 1TB', 'brand': 'MSI', 'price': 119990.0, 'stock': 15, 'category': 'Laptop'},
    {'name': 'Samsung 43-inch Crystal 4K Smart TV', 'brand': 'Samsung', 'price': 34990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'Samsung 55-inch Crystal 4K Smart TV', 'brand': 'Samsung', 'price': 49990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'Samsung 65-inch QLED 4K Smart TV', 'brand': 'Samsung', 'price': 99990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'LG 43-inch UHD 4K Smart TV', 'brand': 'LG', 'price': 36990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'LG 55-inch OLED 4K Smart TV', 'brand': 'LG', 'price': 119990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'LG 65-inch OLED 4K Smart TV', 'brand': 'LG', 'price': 169990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'Sony 43-inch Bravia 3 4K Smart TV', 'brand': 'Sony', 'price': 49990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'Sony 55-inch Bravia 5 Mini LED 4K', 'brand': 'Sony', 'price': 109990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'OnePlus 55-inch QLED 4K Smart TV', 'brand': 'OnePlus', 'price': 39999.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'Xiaomi 55-inch X Pro 4K Smart TV', 'brand': 'Xiaomi', 'price': 44999.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'TCL 65-inch C6K QLED 4K Smart TV', 'brand': 'TCL', 'price': 59990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'Hisense 55-inch Mini LED 4K Smart TV', 'brand': 'Hisense', 'price': 54990.0, 'stock': 15, 'category': 'TV', 'specifications': {'resolution': '4K'}},
    {'name': 'Apple 20W USB-C Power Adapter', 'brand': 'Apple', 'price': 1900.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Apple 35W Dual USB-C Power Adapter', 'brand': 'Apple', 'price': 5800.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Samsung 25W USB-C Fast Charger', 'brand': 'Samsung', 'price': 1299.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Samsung 45W USB-C Fast Charger', 'brand': 'Samsung', 'price': 2999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'OnePlus 100W SuperVOOC Charger', 'brand': 'OnePlus', 'price': 4999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Anker 65W GaN Charger', 'brand': 'Anker', 'price': 4499.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Apple USB-C Charge Cable 1m', 'brand': 'Apple', 'price': 1900.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Anker USB-C to USB-C Cable 1.8m', 'brand': 'Anker', 'price': 999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Belkin USB-C to Lightning Cable 1m', 'brand': 'Belkin', 'price': 1799.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Apple MagSafe Charger', 'brand': 'Apple', 'price': 4500.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Anker 10000mAh Power Bank 20W', 'brand': 'Anker', 'price': 2499.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Anker 20000mAh Power Bank 30W', 'brand': 'Anker', 'price': 3999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Mi 10000mAh Power Bank 22.5W', 'brand': 'Xiaomi', 'price': 1499.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'AirPods 4', 'brand': 'Apple', 'price': 12900.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'AirPods Pro 2 USB-C', 'brand': 'Apple', 'price': 24900.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Galaxy Buds3 Pro', 'brand': 'Samsung', 'price': 18999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'OnePlus Buds 4', 'brand': 'OnePlus', 'price': 5999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Sony WF-1000XM5', 'brand': 'Sony', 'price': 24990.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Sony WH-1000XM5', 'brand': 'Sony', 'price': 29990.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Bose QuietComfort Headphones', 'brand': 'Bose', 'price': 29900.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'JBL Flip 7', 'brand': 'JBL', 'price': 14999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Apple Magic Keyboard USB-C', 'brand': 'Apple', 'price': 9990.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Apple Magic Mouse USB-C', 'brand': 'Apple', 'price': 7490.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Logitech MX Keys S', 'brand': 'Logitech', 'price': 10995.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Logitech MX Master 3S', 'brand': 'Logitech', 'price': 8995.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Samsung T7 1TB Portable SSD', 'brand': 'Samsung', 'price': 8999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Samsung T7 2TB Portable SSD', 'brand': 'Samsung', 'price': 15999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'SanDisk Extreme Portable SSD 1TB', 'brand': 'SanDisk', 'price': 9499.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'WD My Passport 2TB', 'brand': 'WD', 'price': 7499.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'SanDisk Ultra 256GB microSDXC', 'brand': 'SanDisk', 'price': 1799.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Belkin 8-in-1 USB-C Hub', 'brand': 'Belkin', 'price': 5999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Anker 7-in-1 USB-C Hub', 'brand': 'Anker', 'price': 4999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'DJI Osmo Mobile 6', 'brand': 'DJI', 'price': 14999.0, 'stock': 30, 'category': 'Electronics Accessories'},
    {'name': 'Kindle Paperwhite 16GB', 'brand': 'Amazon', 'price': 16999.0, 'stock': 30, 'category': 'Electronics Accessories'},
]

TEST_PRODUCTS.extend(ADDITIONAL_PRODUCTS)


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