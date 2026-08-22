"use client";

import { useEffect, useState } from "react";

import { useChatStore } from "../../store/chatStore";

import type {
  PaymentMethod,
  PaymentSelectionMetadata,
} from "../../types/chat";


// ============================================================
// Props
// ============================================================

interface PaymentSelectorProps {
  metadata: PaymentSelectionMetadata;
}


// ============================================================
// Default MVP Payment Methods
// ============================================================
//
// These are the currently supported BuyQK checkout methods.
//
// The backend should ideally provide these through metadata,
// but the frontend keeps a safe fallback so the checkout UI
// does not disappear when metadata.methods is missing.
// ============================================================

const DEFAULT_PAYMENT_METHODS: PaymentMethod[] = [
  {
    id: "upi",
    label: "UPI",
    description: "Pay securely using UPI.",
  },
  {
    id: "cod",
    label: "Cash on Delivery",
    description: "Pay when your order is delivered.",
  },
];


// ============================================================
// Normalize Payment Method
// ============================================================

function normalizePaymentMethod(
  value: unknown
): PaymentMethod | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const item = value as Record<string, unknown>;

  if (
    typeof item.id !== "string" ||
    !item.id.trim()
  ) {
    return null;
  }

  if (
    typeof item.label !== "string" ||
    !item.label.trim()
  ) {
    return null;
  }

  return {
    id: item.id.trim().toLowerCase(),
    label: item.label.trim(),

    description:
      typeof item.description === "string"
        ? item.description
        : undefined,
  };
}


// ============================================================
// Get Payment Methods
// ============================================================

function getPaymentMethods(
  metadata: PaymentSelectionMetadata
): PaymentMethod[] {
  const rawMetadata =
    metadata as PaymentSelectionMetadata & {
      payment_methods?: unknown;
      methods?: unknown;
    };

  // ----------------------------------------------------------
  // Preferred backend format
  // ----------------------------------------------------------

  if (
    Array.isArray(rawMetadata.methods)
  ) {
    const normalized =
      rawMetadata.methods
        .map(normalizePaymentMethod)
        .filter(
          (
            method
          ): method is PaymentMethod =>
            method !== null
        );

    if (normalized.length > 0) {
      return Array.from(
        new Map(
          normalized.map((method) => [
            method.id,
            method,
          ])
        ).values()
      );
    }
  }

  // ----------------------------------------------------------
  // Compatibility with alternate backend format
  // ----------------------------------------------------------

  if (
    Array.isArray(
      rawMetadata.payment_methods
    )
  ) {
    const normalized =
      rawMetadata.payment_methods
        .map(normalizePaymentMethod)
        .filter(
          (
            method
          ): method is PaymentMethod =>
            method !== null
        );

    if (normalized.length > 0) {
      return Array.from(
        new Map(
          normalized.map((method) => [
            method.id,
            method,
          ])
        ).values()
      );
    }
  }

  // ----------------------------------------------------------
  // MVP fallback
  // ----------------------------------------------------------

  return DEFAULT_PAYMENT_METHODS;
}


// ============================================================
// Component
// ============================================================

export default function PaymentSelector({
  metadata,
}: PaymentSelectorProps) {

  // ==========================================================
  // Chat Store
  // ==========================================================

  const continueWithPaymentMethod =
    useChatStore(
      (state) =>
        state.continueWithPaymentMethod
    );

  const isChatLoading =
    useChatStore(
      (state) =>
        state.isLoading
    );


  // ==========================================================
  // Local State
  // ==========================================================

  const [
    selectedMethod,
    setSelectedMethod,
  ] = useState<string | null>(
    null
  );

  const [
    completed,
    setCompleted,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );

  const [
    submittingMethod,
    setSubmittingMethod,
  ] = useState<string | null>(
    null
  );


  // ==========================================================
  // Reset UI for a new payment-selection step
  // ==========================================================

  useEffect(() => {
    setSelectedMethod(null);
    setCompleted(false);
    setError(null);
    setSubmittingMethod(null);
  }, [
    metadata.methods,
    metadata.payment_methods,
  ]);


  // ==========================================================
  // Payment Methods
  // ==========================================================

  const methods =
    getPaymentMethods(
      metadata
    );


  // ==========================================================
  // Busy State
  // ==========================================================

  const isBusy =
    isChatLoading ||
    submittingMethod !== null;


  // ==========================================================
  // Select Payment Method
  // ==========================================================

  async function handleSelectPayment(
    methodId: string
  ) {

    if (
      isBusy ||
      !methodId
    ) {
      return;
    }

    const normalizedMethod =
      methodId
        .trim()
        .toLowerCase();

    // --------------------------------------------------------
    // Only allow supported MVP methods
    // --------------------------------------------------------

    const selected =
      methods.find(
        (method) =>
          method.id ===
          normalizedMethod
      );

    if (!selected) {
      setError(
        "Invalid payment method selected."
      );

      return;
    }

    // --------------------------------------------------------
    // Update UI
    // --------------------------------------------------------

    setSelectedMethod(
      normalizedMethod
    );

    setSubmittingMethod(
      normalizedMethod
    );

    setError(null);


    try {

      // ======================================================
      // Send selection back to chatStore
      // ======================================================
      //
      // Example:
      //
      // "upi"
      //
      // becomes:
      //
      // Selected payment method: UPI
      //
      // The store then sends this to:
      //
      // POST /chat
      //
      // The backend entity_node resolves:
      //
      // payment_method = "upi"
      //
      // intent = "order_create"
      //
      // and, when all slots are complete:
      //
      // create_order
      // ======================================================

      const success =
        await continueWithPaymentMethod(
          normalizedMethod
        );


      if (success) {

        setCompleted(
          true
        );

      } else {

        setError(
          "Unable to continue with this payment method. Please try again."
        );

        setSelectedMethod(
          null
        );
      }

    } catch (paymentError) {

      const message =
        paymentError instanceof Error
          ? paymentError.message
          : "Unable to select this payment method. Please try again.";

      setError(
        message
      );

      setSelectedMethod(
        null
      );

    } finally {

      setSubmittingMethod(
        null
      );
    }
  }


  // ==========================================================
  // Completed State
  // ==========================================================

  if (completed) {

    const selected =
      methods.find(
        (method) =>
          method.id ===
          selectedMethod
      );


    return (
      <div
        className="payment-selector-complete"
        aria-live="polite"
      >
        {selected
          ? `${selected.label} selected. Continuing checkout...`
          : "Payment method selected. Continuing checkout..."}
      </div>
    );
  }


  // ==========================================================
  // Render
  // ==========================================================

  return (
    <section
      className="payment-selector"
      aria-label="Payment method selection"
    >

      {/* =====================================================
          Header
          ===================================================== */}

      <div
        className="payment-selector-header"
      >

        <h3>
          Choose payment method
        </h3>

      </div>


      {/* =====================================================
          Error
          ===================================================== */}

      {error && (

        <div
          className="payment-selector-error"
          role="alert"
        >
          {error}
        </div>
      )}


      {/* =====================================================
          Payment Methods
          ===================================================== */}

      <div
        className="payment-method-list"
        role="list"
      >

        {methods.map(
          (method) => {

            const isSubmitting =
              submittingMethod ===
              method.id;

            const isSelected =
              selectedMethod ===
              method.id;


            return (
              <button
                key={method.id}
                type="button"

                className={
                  `payment-method-card${
                    isSelected
                      ? " selected"
                      : ""
                  }`
                }

                onClick={() =>
                  void handleSelectPayment(
                    method.id
                  )
                }

                disabled={
                  isBusy
                }

                aria-disabled={
                  isBusy
                }

                aria-pressed={
                  isSelected
                }

                role="listitem"
              >

                {/* =========================================
                    Payment Content
                    ========================================= */}

                <div
                  className="payment-method-content"
                >

                  <div
                    className="payment-method-label"
                  >
                    {method.label}
                  </div>


                  {method.description && (

                    <div
                      className="payment-method-description"
                    >
                      {method.description}
                    </div>
                  )}

                </div>


                {/* =========================================
                    Loading
                    ========================================= */}

                {isSubmitting && (

                  <div
                    className="payment-method-loading"
                    aria-live="polite"
                  >
                    Processing...
                  </div>
                )}

              </button>
            );
          }
        )}

      </div>


      {/* =====================================================
          Small explanatory text
          ===================================================== */}

      <div
        className="payment-selector-note"
        aria-live="polite"
      >
        Select one payment method to continue your order.
      </div>

    </section>
  );
}