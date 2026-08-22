// ============================================================
// BuyQK Product Result Card
// ============================================================
//
// Responsibility:
// - Display one product returned by the backend
// - Allow the user to add that backend-resolved product to Cart
// - Keep product rendering separate from chat messages
//
// This component does NOT:
// - call the Cart API directly
// - calculate prices or totals
// - determine stock
// - resolve product IDs
// - perform checkout logic
//
// Cart mutation flow:
// ProductCard -> Zustand -> cart_service -> FastAPI -> Cart
// ============================================================

"use client";

import { useState } from "react";

import type { Product } from "../../types/chat";
import { useChatStore } from "../../store/chatStore";

interface ProductCardProps {
  product: Product;
}

export default function ProductCard({ product }: ProductCardProps) {
  const addCartItem = useChatStore((state) => state.addCartItem);
  const isCartLoading = useChatStore((state) => state.isCartLoading);

  const [isAdding, setIsAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const productId = product.id;
  const hasValidProductId = Number.isInteger(productId) && productId > 0;

  // These are UI hints only. Backend CartService remains authoritative.
  const isOutOfStock =
    product.stock !== null &&
    product.stock !== undefined &&
    product.stock <= 0;

  const isUnavailable = product.is_available === false;

  const canAddToCart =
    hasValidProductId &&
    !isOutOfStock &&
    !isUnavailable &&
    !isCartLoading &&
    !isAdding;

  async function handleAddToCart() {
    if (!hasValidProductId) {
      setAddError("This product cannot be added because its ID is invalid.");
      return;
    }

    if (isOutOfStock) {
      setAddError("This product is currently out of stock.");
      return;
    }

    if (isUnavailable) {
      setAddError("This product is currently unavailable.");
      return;
    }

    if (isCartLoading || isAdding) {
      return;
    }

    setAddError(null);
    setIsAdding(true);

    try {
      const success = await addCartItem(productId, 1);

      if (!success) {
        setAddError(
          useChatStore.getState().error ||
            "Unable to add this product to your cart.",
        );
      }
    } finally {
      setIsAdding(false);
    }
  }

  return (
    <article className="w-full max-w-sm overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div className="p-4">
        {product.brand && (
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
            {product.brand}
          </p>
        )}

        <h3 className="text-base font-semibold text-gray-900">
          {product.name}
        </h3>

        {product.description && (
          <p className="mt-2 line-clamp-2 text-sm text-gray-500">
            {product.description}
          </p>
        )}

        <div className="mt-4 flex items-center justify-between">
          <p className="text-lg font-semibold text-gray-900">
            {formatPrice(product.price)}
          </p>

          {product.stock !== null && product.stock !== undefined && (
            <span
              className={`text-xs font-medium ${
                product.stock > 0 ? "text-green-600" : "text-red-600"
              }`}
            >
              {product.stock > 0
                ? `${product.stock} available`
                : "Out of stock"}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={handleAddToCart}
          disabled={!canAddToCart}
          className="mt-4 w-full rounded-xl bg-black px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
          aria-busy={isAdding}
        >
          {isAdding
            ? "Adding..."
            : isOutOfStock
              ? "Out of stock"
              : isUnavailable
                ? "Unavailable"
                : "Add to cart"}
        </button>

        {addError && (
          <p className="mt-2 text-xs text-red-600" role="alert">
            {addError}
          </p>
        )}
      </div>
    </article>
  );
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(price);
}