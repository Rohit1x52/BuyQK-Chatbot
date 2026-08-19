"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { useChatStore } from "../../store/chatStore";

import type {
  PaymentMethod,
  PaymentSelectionMetadata,
} from "../../types/chat";


/* =========================================================
   Props
   ========================================================= */

interface PaymentSelectorProps {
  metadata: PaymentSelectionMetadata;
}


/* =========================================================
   Payment Method Validation
   ========================================================= */

function normalizePaymentMethod(
  value: unknown
): PaymentMethod | null {

  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value)
  ) {
    return null;
  }

  const item =
    value as Record<string, unknown>;

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

  const id =
    item.id.trim();

  const label =
    item.label.trim();

  return {
    id,
    label,

    description:
      typeof item.description === "string" &&
      item.description.trim()
        ? item.description.trim()
        : undefined,
  };
}


/* =========================================================
   Get Backend Payment Methods
   ========================================================= */

function getPaymentMethods(
  metadata: PaymentSelectionMetadata
): PaymentMethod[] {

  const rawMetadata =
    metadata as PaymentSelectionMetadata & {
      payment_methods?: unknown;
      methods?: unknown;
    };


  /*
   * Preferred backend format.
   */
  const rawMethods =
    Array.isArray(rawMetadata.methods)
      ? rawMetadata.methods
      : Array.isArray(
          rawMetadata.payment_methods
        )
        ? rawMetadata.payment_methods
        : [];


  /*
   * Normalize only backend-provided values.
   */
  const normalized =
    rawMethods
      .map(
        normalizePaymentMethod
      )
      .filter(
        (
          method
        ): method is PaymentMethod =>
          method !== null
      );


  /*
   * Remove duplicate IDs.
   *
   * This is UI sanitation only.
   * It does not create or modify payment methods.
   */
  const seen =
    new Set<string>();

  return normalized.filter(
    (method) => {

      const key =
        method.id.trim();

      if (seen.has(key)) {
        return false;
      }

      seen.add(key);

      return true;
    }
  );
}


/* =========================================================
   Component
   ========================================================= */

export default function PaymentSelector({
  metadata,
}: PaymentSelectorProps) {

  /* =======================================================
     Chat Store
     ======================================================= */

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


  /* =======================================================
     Backend Payment Methods
     ======================================================= */

  const methods =
    useMemo(
      () =>
        getPaymentMethods(
          metadata
        ),
      [metadata]
    );


  /* =======================================================
     Local UI State
     ======================================================= */

  const [
    selectedMethod,
    setSelectedMethod,
  ] = useState<string | null>(
    null
  );

  const [
    submittingMethod,
    setSubmittingMethod,
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


  /* =======================================================
     Reset State When Backend Sends New Selection Request
     ======================================================= */

  useEffect(() => {

    /*
     * Payment-selection metadata represents a new backend
     * request for the user to select a method.
     *
     * Do not carry the previous UI selection into a new
     * backend decision.
     */
    setSelectedMethod(null);
    setSubmittingMethod(null);
    setCompleted(false);
    setError(null);

  }, [metadata]);


  /* =======================================================
     Busy State
     ======================================================= */

  const isBusy =
    isChatLoading ||
    submittingMethod !== null;


  /* =======================================================
     Select Payment Method
     ======================================================= */

  async function handleSelectPayment(
    methodId: string
  ) {

    if (
      isBusy ||
      typeof methodId !== "string" ||
      !methodId.trim()
    ) {
      return;
    }


    const normalizedMethod =
      methodId.trim();


    /*
     * IMPORTANT:
     *
     * Only allow a payment method that was supplied by
     * the backend in the current metadata.
     *
     * This prevents:
     *
     * frontend input
     *       ↓
     * arbitrary payment method
     *       ↓
     * backend request
     *
     * The frontend can select.
     * It cannot invent.
     */

    const selected =
      methods.find(
        (method) =>
          method.id ===
          normalizedMethod
      );


    if (!selected) {

      setError(
        "This payment method is no longer available. "
        + "Please choose an available method."
      );

      return;
    }


    /*
     * Record the selection for UI feedback only.
     *
     * This does NOT mean payment succeeded.
     */
    setSelectedMethod(
      selected.id
    );

    setSubmittingMethod(
      selected.id
    );

    setError(null);


    try {

      /*
       * Send only the backend-provided payment-method ID.
       *
       * The backend / AI workflow remains responsible for:
       *
       * - interpreting the request
       * - validating the payment method
       * - validating checkout state
       * - validating the user
       * - calculating the bill
       * - creating the order
       * - determining payment status
       * - returning authoritative checkout state
       */
      const success =
        await continueWithPaymentMethod(
          selected.id
        );


      /*
       * IMPORTANT:
       *
       * A successful frontend request does not itself mean
       * payment succeeded or an order was created.
       *
       * The store should return true only when the backend
       * workflow successfully accepted the selection and
       * progressed the conversation.
       */
      if (success) {

        setCompleted(true);

      } else {

        setError(
          "Unable to continue with this payment method. "
          + "Please try again."
        );

        setSelectedMethod(null);
      }

    } catch (paymentError) {

      const message =
        paymentError instanceof Error
          ? paymentError.message
          : (
              "Unable to select this payment method. "
              + "Please try again."
            );

      setError(message);
      setSelectedMethod(null);

    } finally {

      setSubmittingMethod(null);
    }
  }


  /* =======================================================
     Completed UI
     ======================================================= */

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


  /* =======================================================
     Render
     ======================================================= */

  return (

    <section
      className="payment-selector"
      aria-label="Payment method selection"
    >

      {/* =================================================
          Header
          ================================================= */}

      <div
        className="payment-selector-header"
      >

        <h3>
          Choose payment method
        </h3>

      </div>


      {/* =================================================
          Error
          ================================================= */}

      {error && (

        <div
          className="payment-selector-error"
          role="alert"
        >
          {error}
        </div>

      )}


      {/* =================================================
          Payment Methods
          ================================================= */}

      {methods.length > 0 ? (

        <div
          className="payment-method-list"
          role="list"
          aria-label="Available payment methods"
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

                <div
                  key={method.id}
                  role="listitem"
                >

                  <button
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

                    style={{
                      width: "100%",
                    }}
                  >

                    {/* =================================
                        Payment Content
                        ================================= */}

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


                    {/* =================================
                        Loading
                        ================================= */}

                    {isSubmitting && (

                      <div
                        className="payment-method-loading"
                        aria-live="polite"
                      >
                        Continuing...
                      </div>

                    )}

                  </button>

                </div>

              );
            }
          )}

        </div>

      ) : (

        <div
          className="payment-empty-state"
          role="status"
        >
          No payment methods are currently available.
          Please try again.
        </div>

      )}


      {/* =================================================
          Explanation
          ================================================= */}

      {methods.length > 0 && (

        <div
          className="payment-selector-note"
          aria-live="polite"
        >
          Select one payment method to continue checkout.
        </div>

      )}

    </section>
  );
}