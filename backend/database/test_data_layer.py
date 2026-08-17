# Purpose:
# End-to-end verification of the BuyQK MVP data layer.
#
# Tests:
# 1. SQLite database and all 11 tables
# 2. SQLite foreign-key relationships
# 3. FAISS vector store
# 4. Vector-store persistence and reload


import json
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------
# Make backend/ available for imports before package modules
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np
from sqlalchemy import inspect, text

from backend.database.init_db import init_db

# ---------------------------------------------------------
# Import database components
# ---------------------------------------------------------

from backend.database.sqlite import engine

from backend.database.vector_store import VectorStore

# Import all models so SQLAlchemy knows about all tables.
from backend import models


# ---------------------------------------------------------
# Expected database tables
# ---------------------------------------------------------

EXPECTED_TABLES = {
    "users",
    "addresses",
    "products",
    "categories",
    "orders",
    "order_items",
    "payments",
    "support_tickets",
    "merchants",
    "riders",
    "conversation_history",
}


# ---------------------------------------------------------
# Test 1: SQLite
# ---------------------------------------------------------

def test_sqlite():
    """
    Verify that SQLite is accessible and all expected
    tables have been created.
    """

    print("\n" + "=" * 60)
    print("TEST 1: SQLite")
    print("=" * 60)

    # -----------------------------------------------------
    # Initialize the database.
    #
    # This creates all SQLAlchemy tables if they do not
    # already exist.
    # -----------------------------------------------------

    init_db()

    # -----------------------------------------------------
    # Test database connection
    # -----------------------------------------------------

    with engine.connect() as connection:

        connection.execute(
            text("SELECT 1")
        )

    print("✓ SQLite connection successful")

    # -----------------------------------------------------
    # Inspect database
    # -----------------------------------------------------

    inspector = inspect(engine)

    actual_tables = set(
        inspector.get_table_names()
    )

    print(
        f"Found {len(actual_tables)} tables:"
    )

    for table in sorted(actual_tables):
        print(f"  ✓ {table}")

    # -----------------------------------------------------
    # Verify expected tables
    # -----------------------------------------------------

    missing_tables = (
        EXPECTED_TABLES - actual_tables
    )

    if missing_tables:
        raise AssertionError(
            "Missing SQLite tables: "
            + ", ".join(
                sorted(missing_tables)
            )
        )

    print(
        f"✓ All {len(EXPECTED_TABLES)} expected "
        "tables exist"
    )

    # -----------------------------------------------------
    # Check foreign keys
    # -----------------------------------------------------

    print("\nChecking foreign-key relationships...")

    total_foreign_keys = 0

    for table in sorted(EXPECTED_TABLES):

        foreign_keys = inspector.get_foreign_keys(
            table
        )

        total_foreign_keys += len(
            foreign_keys
        )

        for fk in foreign_keys:

            constrained_columns = fk.get(
                "constrained_columns",
                [],
            )

            referred_table = fk.get(
                "referred_table"
            )

            referred_columns = fk.get(
                "referred_columns",
                [],
            )

            print(
                f"  ✓ {table}."
                f"{constrained_columns}"
                f" → "
                f"{referred_table}."
                f"{referred_columns}"
            )

    print(
        f"✓ Found {total_foreign_keys} "
        "foreign-key relationship(s)"
    )

    return True


# ---------------------------------------------------------
# Test 2: FAISS / Vector Store
# ---------------------------------------------------------

def test_vector_store():
    """
    Verify:
    - Vector insertion
    - Semantic search
    - Persistence
    - Reload
    - Search after reload
    """

    print("\n" + "=" * 60)
    print("TEST 2: FAISS Vector Store")
    print("=" * 60)

    # -----------------------------------------------------
    # Use a temporary test directory.
    #
    # We do not want to modify the actual production
    # vector store during testing.
    # -----------------------------------------------------

    test_directory = (
        Path("data")
        / "vector_store_test"
    )

    # Remove previous test data.
    if test_directory.exists():
        shutil.rmtree(
            test_directory
        )

    # -----------------------------------------------------
    # Embedding dimension
    # -----------------------------------------------------

    dimension = 4

    vector_store = VectorStore(
        dimension=dimension,
        store_dir=str(
            test_directory
        ),
    )

    print(
        f"✓ VectorStore initialized "
        f"(dimension={dimension})"
    )

    # -----------------------------------------------------
    # Test documents
    # -----------------------------------------------------

    documents = [
        {
            "text": (
                "Customers can cancel an order "
                "before shipment."
            ),
            "source": "order_policy.md",
        },
        {
            "text": (
                "Refunds are processed after "
                "cancellation confirmation."
            ),
            "source": "refund_policy.md",
        },
        {
            "text": (
                "Customers can contact support "
                "for payment issues."
            ),
            "source": "support_policy.md",
        },
    ]

    # -----------------------------------------------------
    # Fake embeddings for testing.
    #
    # In the real application these will come from
    # HuggingFace sentence-transformers.
    # -----------------------------------------------------

    embeddings = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]

    # -----------------------------------------------------
    # Add documents
    # -----------------------------------------------------

    vector_store.add_documents(
        embeddings=embeddings,
        documents=documents,
    )

    if vector_store.count() != 3:
        raise AssertionError(
            "Expected 3 vectors after insertion"
        )

    print(
        "✓ Added 3 vectors and documents"
    )

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    query_embedding = [
        0.95,
        0.05,
        0.0,
        0.0,
    ]

    results = vector_store.search(
        query_embedding=query_embedding,
        top_k=2,
    )

    if not results:
        raise AssertionError(
            "Vector search returned no results"
        )

    print("✓ Vector search successful")

    print("\nTop search result:")

    print(
        f"  Text: "
        f"{results[0]['text']}"
    )

    print(
        f"  Source: "
        f"{results[0]['source']}"
    )

    print(
        f"  Distance: "
        f"{results[0]['distance']}"
    )

    # The query is closest to the first vector.
    if results[0]["source"] != (
        "order_policy.md"
    ):
        raise AssertionError(
            "Unexpected top search result"
        )

    print(
        "✓ Search returned expected document"
    )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    vector_store.save()

    index_file = (
        test_directory / "index.faiss"
    )

    documents_file = (
        test_directory / "documents.json"
    )

    if not index_file.exists():
        raise AssertionError(
            "index.faiss was not created"
        )

    if not documents_file.exists():
        raise AssertionError(
            "documents.json was not created"
        )

    print("✓ FAISS index saved")

    print(
        "✓ Document metadata saved"
    )

    # -----------------------------------------------------
    # Create a completely new VectorStore instance.
    #
    # This proves that persistence works across
    # application restarts.
    # -----------------------------------------------------

    reloaded_store = VectorStore(
        dimension=dimension,
        store_dir=str(
            test_directory
        ),
    )

    reloaded_store.load()

    if reloaded_store.count() != 3:
        raise AssertionError(
            "Reloaded vector count is incorrect"
        )

    print(
        "✓ Vector store loaded successfully"
    )

    # -----------------------------------------------------
    # Search after reload
    # -----------------------------------------------------

    reloaded_results = (
        reloaded_store.search(
            query_embedding=query_embedding,
            top_k=2,
        )
    )

    if not reloaded_results:
        raise AssertionError(
            "Search failed after reload"
        )

    if reloaded_results[0]["source"] != (
        "order_policy.md"
    ):
        raise AssertionError(
            "Unexpected result after reload"
        )

    print(
        "✓ Search works after reload"
    )

    # -----------------------------------------------------
    # Cleanup
    # -----------------------------------------------------

    shutil.rmtree(
        test_directory
    )

    print(
        "✓ Temporary vector-store test data "
        "removed"
    )

    return True


# ---------------------------------------------------------
# Main test runner
# ---------------------------------------------------------

def main():
    """
    Run the complete BuyQK data-layer test suite.
    """

    print("\n")
    print("=" * 60)
    print("BUYQK MVP DATA-LAYER TEST")
    print("=" * 60)

    tests_passed = 0

    try:

        # SQLite
        test_sqlite()
        tests_passed += 1

        # FAISS / Vector Store
        test_vector_store()
        tests_passed += 1

    except Exception as exc:

        print("\n" + "=" * 60)
        print("❌ DATA-LAYER TEST FAILED")
        print("=" * 60)

        print(
            f"\nError:\n{exc}"
        )

        raise SystemExit(1)

    print("\n" + "=" * 60)
    print("✅ ALL DATA-LAYER TESTS PASSED")
    print("=" * 60)

    print(
        f"\nPassed: "
        f"{tests_passed}/2"
    )

    print("\nData layer status:")
    print("  ✓ SQLite")
    print("  ✓ Foreign keys")
    print("  ⏭ Redis (skipped — test later)")
    print("  ✓ FAISS")
    print("  ✓ Vector persistence")
    print("  ✓ Vector reload")
    print()


if __name__ == "__main__":
    main()