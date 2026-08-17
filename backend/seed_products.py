"""
BuyQK MVP Product Seeder
=========================

Adds a small local product catalog for chatbot/checkout testing.

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
from decimal import Decimal

from backend.models.merchant import Merchant
from backend.models.category import Category


# ============================================================
# Test Catalog
# ============================================================

TEST_PRODUCTS = [
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
        "name": "Tata Tea Gold",
        "brand": "Tata",
        "price": 190.00,
        "stock": 100,
        "category": "Beverages",
    },
    {
        "name": "Maggi 2-Minute Noodles",
        "brand": "Maggi",
        "price": 14.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Britannia Bread",
        "brand": "Britannia",
        "price": 45.00,
        "stock": 100,
        "category": "Grocery",
    },
    {
        "name": "Parle-G Biscuits",
        "brand": "Parle",
        "price": 10.00,
        "stock": 100,
        "category": "Snacks",
    },
    {
        "name": "Surf Excel Matic",
        "brand": "Surf Excel",
        "price": 220.00,
        "stock": 100,
        "category": "Household",
    },
    {
        "name": "Colgate Strong Teeth",
        "brand": "Colgate",
        "price": 95.00,
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
        return f"BUYQK-{column.name.upper()}"

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
                column
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
        elif "business_name" in merchant_columns:
            merchant_kwargs["business_name"] = "BuyQK Test Shop"
        else:
            raise RuntimeError(
                "Merchant model has neither 'name' nor "
                "'business_name'. Update the test merchant "
                "seed to match backend.models.merchant.Merchant."
            )

        if "is_active" in merchant_columns:
            merchant_kwargs["is_active"] = True

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

        category_name = getattr(
            category,
            "name",
            None,
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

def seed_products() -> None:

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

        # Product requires merchant_id and category_id.
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

                if "savepoint" in locals():
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

        # Commit all successful inserts.
        if inserted > 0:
            db.commit()

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