"use client";

import { useEffect, useRef } from "react";

import { useChatStore } from "../../store/chatStore";

import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import AddressSelector from "./AddressSelector";
import PaymentSelector from "./PaymentSelector";
import Cart from "../cart/Cart";

import type {
  AddressSelectionMetadata,
  Bill,
  PaymentSelectionMetadata,
} from "../../types/chat";

/* =========================================================
   Metadata Types
   ========================================================= */

type OrderMetadata = {
  type?: string;

  checkout_id?: string | null;
  checkout_status?: string | null;

  order_created?: boolean;
  order_id?: number | string | null;

  status?: string | null;
  payment_status?: string | null;
  payment_method?: string | null;

  can_track?: boolean;
  can_cancel?: boolean;

  bill?: Bill | null;

  [key: string]: unknown;
};


type TrackingMetadata = {
  type?: string;

  order_id?: number | string | null;
  status?: string | null;

  tracking_status?: string | null;
  can_track?: boolean;

  [key: string]: unknown;
};


type ChatMetadata =
  | AddressSelectionMetadata
  | PaymentSelectionMetadata
  | OrderMetadata
  | TrackingMetadata
  | {
      type?: string;

      checkout_id?: string | null;
      checkout_status?: string | null;

      order_created?: boolean;
      order_id?: number | string | null;

      bill?: Bill | null;

      [key: string]: unknown;
    };


/* =========================================================
   Helpers
   ========================================================= */

function getMessageMetadata(
  message: unknown
): ChatMetadata | null {
  if (
    !message ||
    typeof message !== "object"
  ) {
    return null;
  }

  const item =
    message as Record<string, unknown>;

  const metadata =
    item.metadata;

  if (
    !metadata ||
    typeof metadata !== "object" ||
    Array.isArray(metadata)
  ) {
    return null;
  }

  return metadata as ChatMetadata;
}


/* =========================================================
   Backend Metadata Helpers
   ========================================================= */

/**
 * Extract the checkout identifier returned by the backend.
 *
 * The frontend never generates this value.
 */
function getCheckoutId(
  metadata: ChatMetadata | null
): string | null {
  if (!metadata) {
    return null;
  }

  const checkoutId =
    metadata.checkout_id;

  return typeof checkoutId === "string" &&
    checkoutId.trim()
    ? checkoutId
    : null;
}


/**
 * Extract the backend checkout status.
 *
 * This value is informational only.
 * The frontend does not decide whether a checkout is valid.
 */
function getCheckoutStatus(
  metadata: ChatMetadata | null
): string | null {
  if (!metadata) {
    return null;
  }

  const status =
    metadata.checkout_status;

  return typeof status === "string" &&
    status.trim()
    ? status
    : null;
}


/**
 * Extract backend order creation state.
 */
function getOrderCreated(
  metadata: ChatMetadata | null
): boolean {
  return metadata?.order_created === true;
}


/**
 * Extract backend order ID.
 */
function getOrderId(
  metadata: ChatMetadata | null
): number | string | null {
  if (!metadata) {
    return null;
  }

  const orderId =
    metadata.order_id;

  if (
    typeof orderId === "number" ||
    typeof orderId === "string"
  ) {
    return orderId;
  }

  return null;
}


/* =========================================================
   Billing Validation
   ========================================================= */

/**
 * The backend/order service is authoritative.
 *
 * This helper ONLY verifies that the backend returned
 * enough structured data to safely render the bill.
 *
 * It NEVER calculates:
 *
 * - line totals
 * - subtotal
 * - delivery charge
 * - discount
 * - tax
 * - total
 */
function getValidBill(
  metadata: ChatMetadata | null
): Bill | null {
  if (!metadata) {
    return null;
  }

  const bill =
    metadata.bill;

  if (
    !bill ||
    typeof bill !== "object" ||
    !Array.isArray(bill.items)
  ) {
    return null;
  }

  if (
    typeof bill.subtotal !== "number" ||
    typeof bill.delivery_charge !== "number" ||
    typeof bill.total !== "number"
  ) {
    return null;
  }

  return bill;
}


/* =========================================================
   Currency Formatting
   ========================================================= */

/**
 * Currency comes from the backend.
 *
 * No product-specific currency or price is hardcoded.
 */
function formatMoney(
  amount: number,
  currency?: string | null
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
      }
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
      }
    ).format(amount);
  } catch {
    return `${normalizedCurrency} ${amount.toFixed(2)}`;
  }
}


/* =========================================================
   Bill Display
   ========================================================= */

function BillSummary({
  bill,
}: {
  bill: Bill;
}) {
  const discount =
    typeof bill.discount === "number"
      ? bill.discount
      : 0;

  const tax =
    typeof bill.tax === "number"
      ? bill.tax
      : 0;

  return (
    <section
      className="order-bill"
      aria-label="Order bill"
      style={{
        width: "100%",
        maxWidth: "560px",
        border: "1px solid var(--border-color, #e5e7eb)",
        borderRadius: "12px",
        padding: "18px",
        background: "var(--surface-primary, #ffffff)",
        boxSizing: "border-box",
      }}
    >
      {/* =================================================
          Bill Header
          ================================================= */}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "16px",
          marginBottom: "16px",
        }}
      >
        <div>
          <h3
            style={{
              margin: 0,
              fontSize: "1.05rem",
              fontWeight: 700,
              color: "var(--text-primary)",
            }}
          >
            Order Bill
          </h3>

          {bill.order_id !== null &&
            bill.order_id !== undefined && (
              <p
                style={{
                  margin: "4px 0 0",
                  fontSize: "0.82rem",
                  color: "var(--text-secondary)",
                }}
              >
                Order #{bill.order_id}
              </p>
            )}
        </div>

        {bill.payment_method && (
          <span
            style={{
              fontSize: "0.78rem",
              color: "var(--text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.03em",
            }}
          >
            {bill.payment_method}
          </span>
        )}
      </div>


      {/* =================================================
          Items
          ================================================= */}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {bill.items.map(
          (item, index) => (
            <div
              key={
                item.product_id ??
                `${item.product_name}-${index}`
              }
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: "16px",
                paddingBottom: "12px",
                borderBottom:
                  "1px solid var(--border-color, #eeeeee)",
              }}
            >
              <div
                style={{
                  minWidth: 0,
                  flex: 1,
                }}
              >
                <div
                  style={{
                    fontWeight: 600,
                    color: "var(--text-primary)",
                    overflowWrap: "anywhere",
                  }}
                >
                  {item.product_name}
                </div>

                <div
                  style={{
                    marginTop: "3px",
                    fontSize: "0.82rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  {item.quantity} ×{" "}
                  {formatMoney(
                    item.unit_price,
                    bill.currency
                  )}
                </div>
              </div>

              <div
                style={{
                  flexShrink: 0,
                  fontWeight: 600,
                  color: "var(--text-primary)",
                }}
              >
                {formatMoney(
                  item.line_total,
                  bill.currency
                )}
              </div>
            </div>
          )
        )}
      </div>


      {/* =================================================
          Totals
          ================================================= */}

      <div
        style={{
          marginTop: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          fontSize: "0.9rem",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "16px",
          }}
        >
          <span>Subtotal</span>

          <span>
            {formatMoney(
              bill.subtotal,
              bill.currency
            )}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "16px",
          }}
        >
          <span>Delivery</span>

          <span>
            {formatMoney(
              bill.delivery_charge,
              bill.currency
            )}
          </span>
        </div>

        {discount !== 0 && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "16px",
            }}
          >
            <span>Discount</span>

            <span>
              -{formatMoney(
                discount,
                bill.currency
              )}
            </span>
          </div>
        )}

        {tax !== 0 && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "16px",
            }}
          >
            <span>Tax</span>

            <span>
              {formatMoney(
                tax,
                bill.currency
              )}
            </span>
          </div>
        )}
      </div>


      {/* =================================================
          Grand Total
          ================================================= */}

      <div
        style={{
          marginTop: "14px",
          paddingTop: "14px",
          borderTop:
            "2px solid var(--border-color, #e5e7eb)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "16px",
          fontSize: "1rem",
          fontWeight: 700,
        }}
      >
        <span>
          Total
        </span>

        <span>
          {formatMoney(
            bill.total,
            bill.currency
          )}
        </span>
      </div>
    </section>
  );
}


/* =========================================================
   Order / Checkout Metadata Display
   ========================================================= */

/**
 * This component only displays authoritative metadata.
 *
 * It does not:
 *
 * - create orders
 * - change checkout state
 * - calculate bills
 * - determine whether tracking/cancellation is allowed
 * - select payment methods
 */
function OrderStatusSummary({
  metadata,
}: {
  metadata: ChatMetadata;
}) {
  const checkoutId =
    getCheckoutId(metadata);

  const checkoutStatus =
    getCheckoutStatus(metadata);

  const orderCreated =
    getOrderCreated(metadata);

  const orderId =
    getOrderId(metadata);

  const orderStatus =
    typeof metadata.status === "string"
      ? metadata.status
      : null;

  const paymentStatus =
    typeof metadata.payment_status === "string"
      ? metadata.payment_status
      : null;

  const showOrderInformation =
    checkoutId !== null ||
    checkoutStatus !== null ||
    orderCreated ||
    orderId !== null ||
    orderStatus !== null ||
    paymentStatus !== null;

  if (!showOrderInformation) {
    return null;
  }

  return (
    <section
      aria-label="Order status"
      style={{
        width: "100%",
        maxWidth: "560px",
        border: "1px solid var(--border-color, #e5e7eb)",
        borderRadius: "12px",
        padding: "14px 16px",
        background:
          "var(--surface-secondary, #f9fafb)",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontWeight: 700,
          marginBottom: "10px",
          color: "var(--text-primary)",
        }}
      >
        Order Status
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          fontSize: "0.85rem",
        }}
      >
        {orderId !== null && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
            }}
          >
            <span>Order ID</span>
            <strong>{orderId}</strong>
          </div>
        )}

        {checkoutStatus && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
            }}
          >
            <span>Checkout</span>
            <span>{checkoutStatus}</span>
          </div>
        )}

        {orderStatus && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
            }}
          >
            <span>Order status</span>
            <span>{orderStatus}</span>
          </div>
        )}

        {paymentStatus && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
            }}
          >
            <span>Payment status</span>
            <span>{paymentStatus}</span>
          </div>
        )}

        {orderCreated && (
          <div
            style={{
              marginTop: "4px",
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
            }}
          >
            Order creation has been confirmed by the backend.
          </div>
        )}

        {checkoutId && (
          <div
            style={{
              marginTop: "4px",
              fontSize: "0.72rem",
              color: "var(--text-secondary)",
              overflowWrap: "anywhere",
            }}
          >
            Checkout: {checkoutId}
          </div>
        )}
      </div>
    </section>
  );
}


/* =========================================================
   Tracking Metadata Display
   ========================================================= */

function TrackingSummary({
  metadata,
}: {
  metadata: ChatMetadata;
}) {
  const orderId =
    getOrderId(metadata);

  const status =
    typeof metadata.tracking_status === "string"
      ? metadata.tracking_status
      : typeof metadata.status === "string"
        ? metadata.status
        : null;

  if (
    orderId === null &&
    status === null
  ) {
    return null;
  }

  return (
    <section
      aria-label="Tracking information"
      style={{
        width: "100%",
        maxWidth: "560px",
        border: "1px solid var(--border-color, #e5e7eb)",
        borderRadius: "12px",
        padding: "14px 16px",
        background:
          "var(--surface-secondary, #f9fafb)",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontWeight: 700,
          marginBottom: "8px",
          color: "var(--text-primary)",
        }}
      >
        Tracking
      </div>

      {orderId !== null && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "12px",
            fontSize: "0.85rem",
          }}
        >
          <span>Order ID</span>
          <strong>{orderId}</strong>
        </div>
      )}

      {status && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "12px",
            marginTop: "6px",
            fontSize: "0.85rem",
          }}
        >
          <span>Status</span>
          <span>{status}</span>
        </div>
      )}
    </section>
  );
}


/* =========================================================
   Chat Window
   ========================================================= */

export default function ChatWindow() {
  const {
    messages,
    isLoading,
    error,
  } = useChatStore();

  /* -------------------------------------------------------
     Authoritative Cart

     Cart data is returned by the backend inside assistant
     message metadata. We recover the most recent cart snapshot
     instead of calculating or reconstructing cart state in the
     UI. This keeps ChatWindow compatible with the current
     chatStore while still allowing Cart to update immediately
     after every cart operation.
     ------------------------------------------------------- */

  const cart = (() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const metadata = getMessageMetadata(messages[index]);

      if (!metadata) {
        continue;
      }

      const candidate = metadata.cart;

      if (
        candidate &&
        typeof candidate === "object" &&
        !Array.isArray(candidate)
      ) {
        return candidate as Record<string, unknown>;
      }
    }

    return null;
  })();


  /* -------------------------------------------------------
     Auto Scroll
     ------------------------------------------------------- */

  const messagesEndRef =
    useRef<HTMLDivElement | null>(
      null
    );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [
    messages,
    isLoading,
  ]);


  /* =======================================================
     Render
     ======================================================= */

  return (
    <div className="chat-window">

      {/* =================================================
          Header
          ================================================= */}

      <header className="chat-header">
        <h1>
          BuyQK AI
        </h1>

        <p>
          Your smart shopping assistant
        </p>
      </header>


      {/* =================================================
          Messages
          ================================================= */}

      <main
        className="chat-messages"
        aria-live="polite"
      >

        {/* -----------------------------------------------
            Empty State
            ----------------------------------------------- */}

        {messages.length === 0 &&
          !isLoading && (

            <div className="empty-state">

              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                aria-hidden="true"
              >
                <path
                  d="
                    M21 11.5a8.38 8.38 0 0 1-.9 3.8
                    8.5 8.5 0 0 1-7.6 4.7
                    8.38 8.38 0 0 1-3.8-.9
                    L3 21l1.9-5.7
                    a8.38 8.38 0 0 1-.9-3.8
                    8.5 8.5 0 0 1 4.7-7.6
                    8.38 8.38 0 0 1 3.8-.9
                    h.5a8.48 8.48 0 0 1 8 8v.5z
                  "
                />
              </svg>

              <h2
                style={{
                  fontSize: "1.125rem",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  marginBottom: "8px",
                }}
              >
                How can I help you?
              </h2>

              <p
                style={{
                  maxWidth: "300px",
                  fontSize: "0.875rem",
                }}
              >
                Search for products, check orders,
                track deliveries, or get help with
                your purchase.
              </p>

            </div>
          )}


        {/* -----------------------------------------------
            Conversation
            ----------------------------------------------- */}

        {messages.length > 0 && (

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >

            {messages.map(
              (message) => {

                const metadata =
                  getMessageMetadata(
                    message
                  );

                const bill =
                  getValidBill(
                    metadata
                  );


                const isOrderMetadata =
                  metadata?.type ===
                    "order_success" ||
                  metadata?.type ===
                    "order_created" ||
                  metadata?.order_created === true ||
                  metadata?.order_id !==
                    undefined;

                const isTrackingMetadata =
                  metadata?.type ===
                    "tracking" ||
                  metadata?.type ===
                    "tracking_update" ||
                  metadata?.tracking_status !==
                    undefined;


                return (

                  <div
                    key={message.id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >

                    {/* ---------------------------------
                        Message
                        --------------------------------- */}

                    <MessageBubble
                      message={message}
                    />


                    {/* =================================
                        Address Selection
                        ================================= */}

                    {metadata?.type ===
                      "address_selection" && (

                      <AddressSelector
                        metadata={
                          metadata as AddressSelectionMetadata
                        }
                      />
                    )}


                    {/* =================================
                        Payment Selection
                        ================================= */}

                    {metadata?.type ===
                      "payment_selection" && (

                      <PaymentSelector
                        metadata={
                          metadata as PaymentSelectionMetadata
                        }
                      />
                    )}


                    {/* =================================
                        Order / Checkout Metadata
                        ================================= */}

                    {isOrderMetadata && metadata && (
                      <OrderStatusSummary
                        metadata={metadata}
                      />
                    )}


                    {/* =================================
                        Tracking Metadata
                        ================================= */}

                    {isTrackingMetadata && metadata && (
                      <TrackingSummary
                        metadata={metadata}
                      />
                    )}


                    {/* =================================
                        Order Bill
                        =================================

                        The bill is rendered only when
                        authoritative billing data exists.

                        No calculations happen here.
                        ================================= */}

                    {bill && (
                      <BillSummary
                        bill={bill}
                      />
                    )}

                  </div>
                );
              }
            )}

          </div>
        )}


        {/* =================================================
            Loading / Thinking
            ================================================= */}

        {isLoading && (

          <div className="message-row assistant">

            <div
              className="bubble"
              style={{
                display: "flex",
                gap: "8px",
                alignItems: "center",
              }}
            >

              <span>
                Thinking
              </span>

              <span
                style={{
                  animation:
                    "pulse 1.5s infinite",
                }}
              >
                ...
              </span>

            </div>

          </div>
        )}


        {/* =================================================
            Error
            ================================================= */}

        {error && (

          <div
            role="alert"
            style={{
              backgroundColor: "#fff1f2",
              color: "#be123c",
              padding: "12px 16px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid #fecdd3",
              fontSize: "0.875rem",
              marginTop: "16px",
            }}
          >
            {error}
          </div>
        )}


        {/* =================================================
            Scroll Anchor
            ================================================= */}

        <div
          ref={messagesEndRef}
          aria-hidden="true"
        />

      </main>


      {/* =================================================
          Cart
          ================================================= */}

      {cart && (
        <div
          style={{
            padding: "0 16px 16px",
          }}
        >
          <Cart
            cart={cart}
          />
        </div>
      )}


      {/* =================================================
          Chat Input
          ================================================= */}

      <ChatInput />

    </div>
  );
}