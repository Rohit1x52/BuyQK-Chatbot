"use client";

// ============================================================
// BuyQK - Cart UI
// ============================================================
//
// Responsibilities:
//
// - Display the authoritative backend cart.
// - Display backend-provided prices.
// - Display backend-provided quantities.
// - Allow quantity modification.
// - Allow item removal.
// - Allow cart clearing.
// - Start cart checkout.
//
// IMPORTANT:
//
// This component does NOT:
//
// - calculate prices
// - calculate line totals
// - calculate subtotal
// - calculate delivery charges
// - calculate discounts
// - calculate tax
// - calculate final total
// - validate stock
// - decide product availability
// - create orders
//
// All transactional truth comes from the backend.
//
// ============================================================

import {
  useState,
} from "react";

import {
  useChatStore,
} from "../../store/chatStore";

import {
  removeCartItem,
  updateCartItem,
  clearCart,
} from "../../services/cart_service";

import type {
  CartItem,
} from "../../types/chat";


// ============================================================
// Helpers
// ============================================================

function formatMoney(
  amount: number,
  currency?: string | null,
): string {

  if (!Number.isFinite(amount)) {
    return "—";
  }

  const normalizedCurrency =
    typeof currency === "string" &&
    currency.trim()
      ? currency.trim().toUpperCase()
      : null;

  if (!normalizedCurrency) {
    return amount.toLocaleString(
      undefined,
      {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      },
    );
  }

  try {
    return new Intl.NumberFormat(
      undefined,
      {
        style: "currency",
        currency: normalizedCurrency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      },
    ).format(amount);
  } catch {
    return (
      `${normalizedCurrency} ` +
      `${amount.toFixed(2)}`
    );
  }
}


// ============================================================
// Cart Item
// ============================================================

function CartItemRow({
  item,
  currency,
  busy,
  onUpdateQuantity,
  onRemove,
}: {
  item: CartItem;
  currency: string | null;
  busy: boolean;
  onUpdateQuantity: (
    item: CartItem,
    quantity: number,
  ) => Promise<void>;
  onRemove: (
    item: CartItem,
  ) => Promise<void>;
}) {

  const [
    updating,
    setUpdating,
  ] = useState(false);

  const [
    removing,
    setRemoving,
  ] = useState(false);


  const itemBusy =
    busy ||
    updating ||
    removing;


  async function decreaseQuantity() {

    if (
      itemBusy ||
      item.quantity <= 1
    ) {
      return;
    }

    setUpdating(true);

    try {
      await onUpdateQuantity(
        item,
        item.quantity - 1,
      );
    } finally {
      setUpdating(false);
    }
  }


  async function increaseQuantity() {

    if (itemBusy) {
      return;
    }

    setUpdating(true);

    try {
      await onUpdateQuantity(
        item,
        item.quantity + 1,
      );
    } finally {
      setUpdating(false);
    }
  }


  async function remove() {

    if (itemBusy) {
      return;
    }

    setRemoving(true);

    try {
      await onRemove(item);
    } finally {
      setRemoving(false);
    }
  }


  return (
    <article
      style={{
        display: "flex",
        gap: "14px",
        padding: "14px 0",
        borderBottom:
          "1px solid var(--border-color, #e5e7eb)",
      }}
    >

      {/* ====================================================
          Product Image
          ==================================================== */}

      <div
        style={{
          width: "64px",
          height: "64px",
          flexShrink: 0,
          borderRadius: "10px",
          overflow: "hidden",
          background:
            "var(--surface-secondary, #f3f4f6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >

        {item.image_url ? (
          <img
            src={item.image_url}
            alt={item.product_name}
            width={64}
            height={64}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          <span
            aria-hidden="true"
            style={{
              fontSize: "1.4rem",
            }}
          >
            🛒
          </span>
        )}

      </div>


      {/* ====================================================
          Product Information
          ==================================================== */}

      <div
        style={{
          minWidth: 0,
          flex: 1,
        }}
      >

        <div
          style={{
            fontWeight: 600,
            color:
              "var(--text-primary, #111827)",
            overflowWrap: "anywhere",
          }}
        >
          {item.product_name}
        </div>


        {item.brand && (
          <div
            style={{
              marginTop: "2px",
              fontSize: "0.8rem",
              color:
                "var(--text-secondary, #6b7280)",
            }}
          >
            {item.brand}
          </div>
        )}


        <div
          style={{
            marginTop: "4px",
            fontSize: "0.85rem",
            color:
              "var(--text-secondary, #6b7280)",
          }}
        >
          {formatMoney(
            item.unit_price,
            currency,
          )}{" "}
          each
        </div>


        {!item.is_available && (
          <div
            style={{
              marginTop: "5px",
              fontSize: "0.78rem",
              color: "#b91c1c",
            }}
          >
            Currently unavailable
          </div>
        )}


        {/* ==================================================
            Quantity Controls
            ================================================== */}

        <div
          style={{
            marginTop: "10px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >

          <button
            type="button"
            onClick={decreaseQuantity}
            disabled={
              itemBusy ||
              item.quantity <= 1
            }
            aria-label={
              `Decrease ${item.product_name} quantity`
            }
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              border:
                "1px solid var(--border-color, #d1d5db)",
              background:
                "var(--surface-primary, #ffffff)",
              cursor:
                itemBusy ||
                item.quantity <= 1
                  ? "not-allowed"
                  : "pointer",
              opacity:
                itemBusy ||
                item.quantity <= 1
                  ? 0.5
                  : 1,
            }}
          >
            −
          </button>


          <span
            style={{
              minWidth: "28px",
              textAlign: "center",
              fontWeight: 600,
            }}
          >
            {item.quantity}
          </span>


          <button
            type="button"
            onClick={increaseQuantity}
            disabled={itemBusy}
            aria-label={
              `Increase ${item.product_name} quantity`
            }
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              border:
                "1px solid var(--border-color, #d1d5db)",
              background:
                "var(--surface-primary, #ffffff)",
              cursor:
                itemBusy
                  ? "not-allowed"
                  : "pointer",
              opacity:
                itemBusy
                  ? 0.5
                  : 1,
            }}
          >
            +
          </button>


          <button
            type="button"
            onClick={remove}
            disabled={itemBusy}
            style={{
              marginLeft: "6px",
              border: "none",
              background: "transparent",
              color: "#b91c1c",
              cursor:
                itemBusy
                  ? "not-allowed"
                  : "pointer",
              fontSize: "0.82rem",
            }}
          >
            {removing
              ? "Removing..."
              : "Remove"}
          </button>

        </div>

      </div>


      {/* ====================================================
          Line Total
          ==================================================== */}

      <div
        style={{
          flexShrink: 0,
          textAlign: "right",
          fontWeight: 700,
          color:
            "var(--text-primary, #111827)",
        }}
      >
        {formatMoney(
          item.line_total,
          currency,
        )}
      </div>

    </article>
  );
}


// ============================================================
// Cart Component
// ============================================================

export default function Cart() {

  const cart =
    useChatStore(
      (state) => state.cart,
    );

  const isLoading =
    useChatStore(
      (state) => state.isLoading,
    );

  const sendMessage =
    useChatStore(
      (state) => state.sendMessage,
    );

  const userId =
    useChatStore(
      (state) => state.userId,
    );

  const setCart =
    useChatStore(
      (state) => state.setCart,
    );

  const globalError =
    useChatStore(
      (state) => state.error,
    );


  const [
    actionError,
    setActionError,
  ] = useState<string | null>(null);

  const [
    actionBusy,
    setActionBusy,
  ] = useState(false);


  // ==========================================================
  // No Cart
  // ==========================================================

  if (!cart) {
    return null;
  }


  const items =
    Array.isArray(cart.items)
      ? cart.items
      : [];


  const summary =
    cart.summary;


  const currency =
    summary?.currency ??
    null;


  // ==========================================================
  // Update Quantity
  // ==========================================================

  async function handleUpdateQuantity(
    item: CartItem,
    quantity: number,
  ): Promise<void> {

    if (
      !Number.isInteger(quantity) ||
      quantity <= 0 ||
      actionBusy ||
      userId === null
    ) {
      return;
    }

    setActionError(null);
    setActionBusy(true);

    try {
      // Direct Cart API operation.
      //
      // CartService remains authoritative for:
      // - product ownership
      // - stock
      // - quantity validation
      // - price
      // - totals
      const updatedCart =
        await updateCartItem(
          item.id,
          {
            user_id: userId,
            quantity,
          },
        );

      // Replace Zustand only with the successful backend result.
      const accepted =
        setCart(updatedCart);

      if (!accepted) {
        throw new Error(
          "Received invalid cart data from the backend.",
        );
      }
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to update the cart.",
      );
    } finally {
      setActionBusy(false);
    }
  }


  // ==========================================================
  // Remove Item
  // ==========================================================

  async function handleRemove(
    item: CartItem,
  ): Promise<void> {

    if (
      actionBusy ||
      userId === null
    ) {
      return;
    }

    setActionError(null);
    setActionBusy(true);

    try {
      // Direct Cart API operation.
      const updatedCart =
        await removeCartItem(
          item.id,
          userId,
        );

      const accepted =
        setCart(updatedCart);

      if (!accepted) {
        throw new Error(
          "Received invalid cart data from the backend.",
        );
      }
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to remove the item.",
      );
    } finally {
      setActionBusy(false);
    }
  }


  // ==========================================================
  // Clear Cart
  // ==========================================================

  async function handleClearCart(): Promise<void> {

    if (
      isLoading ||
      actionBusy ||
      items.length === 0 ||
      userId === null
    ) {
      return;
    }

    const confirmed =
      window.confirm(
        "Are you sure you want to clear your cart?",
      );

    if (!confirmed) {
      return;
    }

    setActionError(null);
    setActionBusy(true);

    try {
      // Direct Cart API operation.
      const updatedCart =
        await clearCart(userId);

      const accepted =
        setCart(updatedCart);

      if (!accepted) {
        throw new Error(
          "Received invalid cart data from the backend.",
        );
      }
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to clear the cart.",
      );
    } finally {
      setActionBusy(false);
    }
  }


  // ==========================================================
  // Cart → Checkout
  // ==========================================================
  //
  // This is deliberately NOT a frontend order creation call.
  //
  // It tells the AI/backend:
  //
  //     "checkout my cart"
  //
  // The backend then:
  //
  //     cart
  //       ↓
  //     checkout
  //       ↓
  //     address
  //       ↓
  //     payment
  //       ↓
  //     order
  //
  // Existing AddressSelector and PaymentSelector remain
  // responsible for the subsequent selections.
  // ==========================================================

  async function handleCheckout(): Promise<void> {

    if (
      isLoading ||
      actionBusy ||
      items.length === 0 ||
      userId === null
    ) {
      return;
    }


    setActionError(null);

    try {

      await sendMessage(
        "checkout my cart",
      );

    } catch (error) {

      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to start checkout.",
      );
    }
  }


  // ==========================================================
  // Render
  // ==========================================================

  return (
    <section
      aria-label="Shopping cart"
      style={{
        width: "100%",
        maxWidth: "720px",
        margin: "0 auto",
        padding: "18px",
        borderRadius: "14px",
        border:
          "1px solid var(--border-color, #e5e7eb)",
        background:
          "var(--surface-primary, #ffffff)",
        boxSizing: "border-box",
      }}
    >

      {/* ====================================================
          Header
          ==================================================== */}

      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
        }}
      >

        <div>

          <h2
            style={{
              margin: 0,
              fontSize: "1.2rem",
              fontWeight: 700,
              color:
                "var(--text-primary, #111827)",
            }}
          >
            Your Cart
          </h2>

          <p
            style={{
              margin:
                "4px 0 0",
              fontSize: "0.82rem",
              color:
                "var(--text-secondary, #6b7280)",
            }}
          >
            {summary.total_quantity}{" "}
            item
            {summary.total_quantity === 1
              ? ""
              : "s"}
          </p>

        </div>


        {items.length > 0 && (
          <button
            type="button"
            onClick={handleClearCart}
            disabled={isLoading || actionBusy}
            style={{
              border: "none",
              background: "transparent",
              color: "#b91c1c",
              cursor:
                isLoading
                  ? "not-allowed"
                  : "pointer",
              fontSize: "0.82rem",
              opacity:
                isLoading
                  ? 0.5
                  : 1,
            }}
          >
            Clear cart
          </button>
        )}

      </header>


      {/* ====================================================
          Errors
          ==================================================== */}

      {(actionError || globalError) && (
        <div
          role="alert"
          style={{
            marginTop: "14px",
            padding: "10px 12px",
            borderRadius: "8px",
            background: "#fef2f2",
            color: "#991b1b",
            fontSize: "0.85rem",
          }}
        >
          {actionError || globalError}
        </div>
      )}


      {/* ====================================================
          Empty Cart
          ==================================================== */}

      {items.length === 0 ? (

        <div
          style={{
            padding:
              "42px 16px",
            textAlign: "center",
            color:
              "var(--text-secondary, #6b7280)",
          }}
        >

          <div
            style={{
              fontSize: "2rem",
              marginBottom: "8px",
            }}
          >
            🛒
          </div>

          <div
            style={{
              fontWeight: 600,
              color:
                "var(--text-primary, #111827)",
            }}
          >
            Your cart is empty
          </div>

          <p
            style={{
              margin:
                "6px 0 0",
              fontSize: "0.85rem",
            }}
          >
            Add products to continue shopping.
          </p>

        </div>

      ) : (

        <>

          {/* ==================================================
              Items
              ================================================== */}

          <div
            style={{
              marginTop: "10px",
            }}
          >

            {items.map(
              (item) => (
                <CartItemRow
                  key={item.id}
                  item={item}
                  currency={currency}
                  busy={isLoading || actionBusy}
                  onUpdateQuantity={
                    handleUpdateQuantity
                  }
                  onRemove={
                    handleRemove
                  }
                />
              ),
            )}

          </div>


          {/* ==================================================
              Backend Summary
              ================================================== */}

          <div
            style={{
              marginTop: "18px",
              paddingTop: "16px",
              borderTop:
                "1px solid var(--border-color, #e5e7eb)",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}
          >

            <SummaryRow
              label="Items"
              value={
                String(
                  summary.total_quantity,
                )
              }
            />

            <SummaryRow
              label="Subtotal"
              value={formatMoney(
                summary.subtotal,
                currency,
              )}
            />


            {typeof summary.delivery_charge ===
              "number" && (
              <SummaryRow
                label="Delivery"
                value={formatMoney(
                  summary.delivery_charge,
                  currency,
                )}
              />
            )}


            {typeof summary.discount ===
              "number" &&
              summary.discount !== 0 && (
              <SummaryRow
                label="Discount"
                value={`-${formatMoney(
                  summary.discount,
                  currency,
                )}`}
              />
            )}


            {typeof summary.tax ===
              "number" &&
              summary.tax !== 0 && (
              <SummaryRow
                label="Tax"
                value={formatMoney(
                  summary.tax,
                  currency,
                )}
              />
            )}


            <div
              style={{
                marginTop: "8px",
                paddingTop: "12px",
                borderTop:
                  "2px solid var(--border-color, #e5e7eb)",
              }}
            >

              <SummaryRow
                label="Total"
                value={formatMoney(
                  summary.total,
                  currency,
                )}
                strong
              />

            </div>

          </div>


          {/* ==================================================
              Checkout
              ================================================== */}

          <button
            type="button"
            onClick={handleCheckout}
            disabled={
              isLoading ||
              actionBusy
            }
            style={{
              width: "100%",
              marginTop: "18px",
              padding:
                "12px 16px",
              border: "none",
              borderRadius: "10px",
              background:
                "var(--accent-color, #111827)",
              color: "#ffffff",
              fontWeight: 700,
              cursor:
                isLoading
                  ? "not-allowed"
                  : "pointer",
              opacity:
                isLoading
                  ? 0.6
                  : 1,
            }}
          >
            {isLoading || actionBusy
              ? "Processing..."
              : "Checkout"}
          </button>

        </>
      )}

    </section>
  );
}


// ============================================================
// Summary Row
// ============================================================

function SummaryRow({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "16px",
        fontSize:
          strong
            ? "1rem"
            : "0.88rem",
        fontWeight:
          strong
            ? 700
            : 400,
        color:
          "var(--text-primary, #111827)",
      }}
    >

      <span>
        {label}
      </span>

      <span>
        {value}
      </span>

    </div>
  );
}