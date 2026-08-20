// BuyQK product result card.
//
// Responsibility:
// - Display one product returned by the backend
// - Keep product rendering separate from chat messages
//
// This component does NOT:
// - call the API
// - modify products
// - manage Zustand state
// - perform purchasing logic


"use client";

import type {
  Product,
} from "../../types/chat";


// ============================================================
// Props
// ============================================================

interface ProductCardProps {
  product: Product;
}


// ============================================================
// Component
// ============================================================

export default function ProductCard({
  product,
}: ProductCardProps) {

  return (
    <article className="w-full max-w-sm overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">

      {/* ====================================================
          Product Information
      ==================================================== */}

      <div className="p-4">

        {/* --------------------------------------------------
            Brand
        -------------------------------------------------- */}

        {product.brand && (

          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
            {product.brand}
          </p>

        )}


        {/* --------------------------------------------------
            Product Name
        -------------------------------------------------- */}

        <h3 className="text-base font-semibold text-gray-900">
          {product.name}
        </h3>


        {/* --------------------------------------------------
            Description
        -------------------------------------------------- */}

        {product.description && (

          <p className="mt-2 line-clamp-2 text-sm text-gray-500">
            {product.description}
          </p>

        )}


        {/* ==================================================
            Price + Stock
        ================================================== */}

        <div className="mt-4 flex items-center justify-between">

          <div>

            <p className="text-lg font-semibold text-gray-900">
              {formatPrice(product.price)}
            </p>

          </div>


          {/* ------------------------------------------------
              Stock
          ------------------------------------------------ */}

          {product.stock !== null &&
            product.stock !== undefined && (

            <span
              className={`text-xs font-medium ${
                product.stock > 0
                  ? "text-green-600"
                  : "text-red-600"
              }`}
            >
              {product.stock > 0
                ? `${product.stock} available`
                : "Out of stock"}
            </span>

          )}

        </div>

      </div>

    </article>
  );
}


// ============================================================
// Price Formatter
// ============================================================

function formatPrice(
  price: number
): string {

  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }
  ).format(price);
}