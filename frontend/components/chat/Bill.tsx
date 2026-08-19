"use client";

import type { Bill as BillType } from "../../types/chat";


/* =========================================================
   Props
   ========================================================= */

interface BillProps {
  bill: BillType;
}


/* =========================================================
   Currency Formatter
   ========================================================= */

/**
 * Format a backend-provided monetary value.
 *
 * IMPORTANT:
 * The frontend does not decide the currency.
 * Currency comes from the backend bill.
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
    /*
     * Unknown backend currency must not
     * crash the checkout UI.
     */
    return `${normalizedCurrency} ${amount.toFixed(2)}`;
  }
}


/* =========================================================
   Bill Validation
   ========================================================= */

/**
 * Validate the minimum structure required to render
 * an authoritative backend bill.
 *
 * This function does NOT calculate anything.
 *
 * Backend remains responsible for:
 *
 * - item prices
 * - line totals
 * - subtotal
 * - delivery charge
 * - discount
 * - tax
 * - total
 */
function isValidBill(
  bill: BillType | null | undefined
): bill is BillType {
  if (!bill) {
    return false;
  }

  if (!Array.isArray(bill.items)) {
    return false;
  }

  if (
    typeof bill.subtotal !== "number" ||
    !Number.isFinite(bill.subtotal)
  ) {
    return false;
  }

  if (
    typeof bill.delivery_charge !== "number" ||
    !Number.isFinite(bill.delivery_charge)
  ) {
    return false;
  }

  if (
    typeof bill.total !== "number" ||
    !Number.isFinite(bill.total)
  ) {
    return false;
  }

  return true;
}


/**
 * Validate an individual bill item before rendering it.
 *
 * No monetary calculation is performed here.
 */
function isValidBillItem(
  item: unknown
): item is BillType["items"][number] {
  if (
    !item ||
    typeof item !== "object"
  ) {
    return false;
  }

  const value =
    item as Record<string, unknown>;

  return (
    typeof value.product_name === "string" &&
    typeof value.quantity === "number" &&
    Number.isFinite(value.quantity) &&
    typeof value.unit_price === "number" &&
    Number.isFinite(value.unit_price) &&
    typeof value.line_total === "number" &&
    Number.isFinite(value.line_total)
  );
}


/* =========================================================
   Bill Component
   ========================================================= */

export default function Bill({
  bill,
}: BillProps) {

  /*
   * The backend is the source of truth.
   *
   * The frontend does NOT:
   *
   * - create an order
   * - modify checkout state
   * - calculate quantity × price
   * - calculate subtotal
   * - calculate delivery
   * - calculate discount
   * - calculate tax
   * - calculate total
   * - determine payment validity
   */

  if (!isValidBill(bill)) {
    return null;
  }


  /*
   * Optional values are display-only.
   *
   * Missing discount/tax means that the backend did not
   * provide those optional components.
   */
  const discount =
    typeof bill.discount === "number" &&
    Number.isFinite(bill.discount)
      ? bill.discount
      : null;

  const tax =
    typeof bill.tax === "number" &&
    Number.isFinite(bill.tax)
      ? bill.tax
      : null;


  /*
   * Filter invalid items instead of allowing malformed
   * backend metadata to break the complete bill UI.
   */
  const validItems =
    bill.items.filter(
      isValidBillItem
    );


  /* =======================================================
     Render
     ======================================================= */

  return (
    <section
      className="order-bill"
      aria-label="Order bill"
      style={{
        width: "100%",
        maxWidth: "560px",
        boxSizing: "border-box",
        padding: "18px",
        border:
          "1px solid var(--border-color, #e5e7eb)",
        borderRadius: "12px",
        background:
          "var(--surface-primary, #ffffff)",
      }}
    >

      {/* =================================================
          Header
          ================================================= */}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "16px",
          marginBottom: "18px",
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


          {/* -----------------------------------------------
              Order ID
              ----------------------------------------------- */}

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


        {/* -----------------------------------------------
            Payment Method
            ----------------------------------------------- */}

        {bill.payment_method && (

          <span
            style={{
              fontSize: "0.78rem",
              color: "var(--text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
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

        {validItems.map(
          (item, index) => (

            <div
              key={
                item.product_id ??
                `${item.product_name}-${index}`
              }
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: "16px",
                paddingBottom: "12px",
                borderBottom:
                  "1px solid var(--border-color, #eeeeee)",
              }}
            >

              {/* -----------------------------------------
                  Product Information
                  ----------------------------------------- */}

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
                    marginTop: "4px",
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


              {/* -----------------------------------------
                  Backend-provided Line Total
                  ----------------------------------------- */}

              <div
                style={{
                  flexShrink: 0,
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
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
          Bill Breakdown
          ================================================= */}

      <div
        style={{
          marginTop: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          fontSize: "0.9rem",
          color: "var(--text-secondary)",
        }}
      >

        {/* -----------------------------------------------
            Subtotal
            ----------------------------------------------- */}

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "16px",
          }}
        >

          <span>
            Subtotal
          </span>

          <span>
            {formatMoney(
              bill.subtotal,
              bill.currency
            )}
          </span>

        </div>


        {/* -----------------------------------------------
            Delivery
            ----------------------------------------------- */}

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "16px",
          }}
        >

          <span>
            Delivery
          </span>

          <span>
            {formatMoney(
              bill.delivery_charge,
              bill.currency
            )}
          </span>

        </div>


        {/* -----------------------------------------------
            Discount
            ----------------------------------------------- */}

        {discount !== null &&
          discount !== 0 && (

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: "16px",
              }}
            >

              <span>
                Discount
              </span>

              <span>
                -{formatMoney(
                  discount,
                  bill.currency
                )}
              </span>

            </div>

          )}


        {/* -----------------------------------------------
            Tax
            ----------------------------------------------- */}

        {tax !== null &&
          tax !== 0 && (

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: "16px",
              }}
            >

              <span>
                Tax
              </span>

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
          Total
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
          color: "var(--text-primary)",
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