// ============================================================
// BuyQK - Chat Store
// ============================================================
//
// Responsibilities:
//
// - Store chat messages
// - Track loading state
// - Track API errors
// - Maintain session ID
// - Maintain user ID
// - Maintain authoritative frontend checkout representation
// - Call the typed chat API
// - Clear/reset conversation
//
// IMPORTANT:
//
// The backend remains authoritative for:
//
// - checkout status
// - order creation
// - order ID
// - product resolution
// - quantity accepted by backend
// - address selection
// - payment method
// - billing
// - prices
// - stock
// - totals
//
// Zustand is only a frontend representation of backend state.
//
// UI components should use this store instead of calling the
// FastAPI API directly.
// ============================================================


import { create } from "zustand";

import {
  sendChatMessage,
} from "../services/chat";

import type {
  Bill,
  ChatMessage,
  ChatMetadata,
  ChatResponse,
  CheckoutState,
  PurchaseSummary,
} from "../types/chat";


// ============================================================
// Store Interface
// ============================================================

interface ChatStore {

  // ----------------------------------------------------------
  // State
  // ----------------------------------------------------------

  messages: ChatMessage[];

  isLoading: boolean;

  error: string | null;

  sessionId: string;

  userId: number | null;

  /**
   * Current authoritative checkout representation.
   *
   * This is populated only from backend metadata.
   */
  checkout: CheckoutState | null;


  // ----------------------------------------------------------
  // Actions
  // ----------------------------------------------------------

  sendMessage: (
    message: string
  ) => Promise<void>;

  continueWithSelectedAddress: (
    addressId: number
  ) => Promise<boolean>;

  continueWithPaymentMethod: (
    methodId: string
  ) => Promise<boolean>;

  clearChat: () => void;

  setUserId: (
    userId: number
  ) => void;
}


// ============================================================
// Session ID
// ============================================================

function createSessionId(): string {

  return (
    `session-${Date.now()}-` +
    `${Math.random()
      .toString(36)
      .substring(2, 10)}`
  );
}


// ============================================================
// Message ID
// ============================================================

function createMessageId(): string {

  return (
    `message-${Date.now()}-` +
    `${Math.random()
      .toString(36)
      .substring(2, 10)}`
  );
}


// ============================================================
// Initial User ID
// ============================================================
//
// Authentication is not part of the current MVP yet.
// Keep nullable until the authentication layer supplies it.
// ============================================================

const INITIAL_USER_ID: number | null = null;


// ============================================================
// Billing Normalization
// ============================================================
//
// The backend is authoritative.
//
// The store does NOT calculate:
//
// - item totals
// - subtotal
// - delivery charge
// - discount
// - tax
// - grand total
//
// It only validates/preserves the structured values returned
// by the backend.
// ============================================================

function normalizeBill(
  bill: unknown,
): Bill | null {

  if (
    !bill ||
    typeof bill !== "object" ||
    Array.isArray(bill)
  ) {
    return null;
  }

  const value =
    bill as Record<string, unknown>;

  if (
    !Array.isArray(value.items) ||
    typeof value.subtotal !== "number" ||
    typeof value.delivery_charge !== "number" ||
    typeof value.total !== "number"
  ) {
    return null;
  }

  return value as unknown as Bill;
}


// ============================================================
// Purchase Summary Normalization
// ============================================================

function normalizePurchaseSummary(
  summary: unknown,
): PurchaseSummary | null {

  if (
    !summary ||
    typeof summary !== "object" ||
    Array.isArray(summary)
  ) {
    return null;
  }

  const value =
    summary as Record<string, unknown>;

  if (
    !Array.isArray(value.items) ||
    typeof value.subtotal !== "number" ||
    typeof value.delivery_charge !== "number" ||
    typeof value.total !== "number"
  ) {
    return null;
  }

  return value as unknown as PurchaseSummary;
}


// ============================================================
// Checkout State Normalization
// ============================================================
//
// IMPORTANT:
//
// This function does NOT decide anything.
//
// It only extracts authoritative checkout fields returned by
// the backend.
//
// Missing fields are preserved as null or existing state.
// ============================================================

function normalizeCheckoutState(
  metadata: ChatMetadata | null,
  previous: CheckoutState | null,
): CheckoutState | null {

  if (!metadata) {
    return previous;
  }

  const backendCheckout =
    metadata.checkout;

  // ----------------------------------------------------------
  // If the backend explicitly returned a complete checkout
  // object, use it as the primary source.
  // ----------------------------------------------------------

  if (
    backendCheckout &&
    typeof backendCheckout === "object"
  ) {

    const normalizedBill =
      normalizeBill(
        backendCheckout.bill,
      );

    return {
      checkout_id:
        backendCheckout.checkout_id ??
        metadata.checkout_id ??
        previous?.checkout_id ??
        null,

      checkout_status:
        backendCheckout.checkout_status ??
        metadata.checkout_status ??
        previous?.checkout_status ??
        null,

      order_created:
        typeof backendCheckout.order_created === "boolean"
          ? backendCheckout.order_created
          : typeof metadata.order_created === "boolean"
            ? metadata.order_created
            : previous?.order_created ?? false,

      order_id:
        backendCheckout.order_id ??
        metadata.order_id ??
        previous?.order_id ??
        null,

      product_id:
        backendCheckout.product_id ??
        previous?.product_id ??
        null,

      product_name:
        backendCheckout.product_name ??
        previous?.product_name ??
        null,

      quantity:
        backendCheckout.quantity ??
        previous?.quantity ??
        null,

      address_id:
        backendCheckout.address_id ??
        previous?.address_id ??
        null,

      selected_payment_method:
        backendCheckout.selected_payment_method ??
        metadata.payment_method ??
        previous?.selected_payment_method ??
        null,

      bill:
        normalizedBill ??
        normalizeBill(metadata.bill) ??
        previous?.bill ??
        null,
    };
  }


  // ----------------------------------------------------------
  // No explicit checkout object.
  //
  // Build the frontend representation from individual
  // backend metadata fields without inventing values.
  // ----------------------------------------------------------

  const hasCheckoutInformation =
    metadata.checkout_id !== undefined ||
    metadata.checkout_status !== undefined ||
    metadata.order_created !== undefined ||
    metadata.order_id !== undefined ||
    metadata.bill !== undefined ||
    metadata.payment_method !== undefined;

  if (!hasCheckoutInformation) {
    return previous;
  }


  return {
    checkout_id:
      metadata.checkout_id ??
      previous?.checkout_id ??
      null,

    checkout_status:
      metadata.checkout_status ??
      previous?.checkout_status ??
      null,

    order_created:
      typeof metadata.order_created === "boolean"
        ? metadata.order_created
        : previous?.order_created ?? false,

    order_id:
      metadata.order_id ??
      previous?.order_id ??
      null,

    product_id:
      previous?.product_id ??
      null,

    product_name:
      previous?.product_name ??
      null,

    quantity:
      previous?.quantity ??
      null,

    address_id:
      previous?.address_id ??
      null,

    selected_payment_method:
      metadata.payment_method ??
      previous?.selected_payment_method ??
      null,

    bill:
      normalizeBill(metadata.bill) ??
      previous?.bill ??
      null,
  };
}


// ============================================================
// Response Metadata Normalization
// ============================================================

function normalizeResponseMetadata(
  response: ChatResponse,
): ChatMetadata | null {

  if (!response.metadata) {
    return null;
  }

  const metadata: ChatMetadata = {
    ...response.metadata,
  };


  // ----------------------------------------------------------
  // Preserve authoritative bill
  // ----------------------------------------------------------

  const bill =
    normalizeBill(
      metadata.bill,
    );

  if (bill) {
    metadata.bill = bill;
  }


  // ----------------------------------------------------------
  // Preserve purchase summary
  // ----------------------------------------------------------

  const purchaseSummary =
    normalizePurchaseSummary(
      metadata.purchase_summary,
    );

  if (purchaseSummary) {
    metadata.purchase_summary =
      purchaseSummary;
  }


  // ----------------------------------------------------------
  // Normalize nested checkout
  // ----------------------------------------------------------

  if (
    metadata.checkout &&
    typeof metadata.checkout === "object"
  ) {

    const checkoutBill =
      normalizeBill(
        metadata.checkout.bill,
      );

    if (checkoutBill) {
      metadata.checkout = {
        ...metadata.checkout,
        bill: checkoutBill,
      };
    }
  }


  return metadata;
}


// ============================================================
// Assistant Message
// ============================================================

function createAssistantMessage(
  response: ChatResponse,
): ChatMessage {

  return {
    id: createMessageId(),

    role: "assistant",

    content:
      response.response,

    metadata:
      normalizeResponseMetadata(
        response,
      ),

    created_at:
      new Date().toISOString(),
  };
}


// ============================================================
// Apply Backend Checkout State
// ============================================================
//
// Centralized state update.
//
// Every successful backend response passes through this
// function.
//
// No frontend business decision is made here.
// ============================================================

function applyBackendCheckoutState(
  set: (
    updater:
      | Partial<ChatStore>
      | ((state: ChatStore) => Partial<ChatStore>)
  ) => void,
  response: ChatResponse,
): void {

  const metadata =
    normalizeResponseMetadata(
      response,
    );

  set((state) => ({
    checkout:
      normalizeCheckoutState(
        metadata,
        state.checkout,
      ),
  }));
}


// ============================================================
// Zustand Store
// ============================================================

export const useChatStore =
  create<ChatStore>((set, get) => ({

    // ========================================================
    // Initial State
    // ========================================================

    messages: [],

    isLoading: false,

    error: null,

    sessionId:
      createSessionId(),

    userId:
      INITIAL_USER_ID,

    checkout:
      null,


    // ========================================================
    // Set User ID
    // ========================================================

    setUserId: (
      userId: number
    ) => {

      set({
        userId,
      });
    },


    // ========================================================
    // Send Message
    // ========================================================

    sendMessage: async (
      message: string
    ) => {

      if (get().isLoading) {
        return;
      }

      const trimmedMessage =
        message.trim();

      if (!trimmedMessage) {
        return;
      }

      const {
        sessionId,
        userId,
      } = get();

      if (userId === null) {

        set({
          error:
            "User ID is required to start a chat.",
        });

        return;
      }


      // ------------------------------------------------------
      // Add user message immediately
      // ------------------------------------------------------

      const userMessage: ChatMessage = {
        id: createMessageId(),

        role: "user",

        content:
          trimmedMessage,

        created_at:
          new Date().toISOString(),
      };

      set((state) => ({
        messages: [
          ...state.messages,
          userMessage,
        ],

        isLoading: true,

        error: null,
      }));


      try {

        // ----------------------------------------------------
        // Send to backend
        // ----------------------------------------------------

        const response =
          await sendChatMessage({
            message:
              trimmedMessage,

            session_id:
              sessionId,

            user_id:
              userId,
          });


        // ----------------------------------------------------
        // Create assistant message
        // ----------------------------------------------------

        const assistantMessage =
          createAssistantMessage(
            response,
          );


        // ----------------------------------------------------
        // Update messages
        // ----------------------------------------------------

        set((state) => ({
          messages: [
            ...state.messages,
            assistantMessage,
          ],

          isLoading: false,

          error: null,
        }));


        // ----------------------------------------------------
        // Update authoritative checkout state
        // ----------------------------------------------------

        applyBackendCheckoutState(
          set,
          response,
        );


      } catch (error) {

        const errorMessage =
          error instanceof Error
            ? error.message
            : "Something went wrong while contacting BuyQK AI.";

        set({
          isLoading: false,

          error:
            errorMessage,
        });
      }
    },


    // ========================================================
    // Continue with Selected Address
    // ========================================================

    continueWithSelectedAddress: async (
      addressId: number
    ) => {

      if (get().isLoading) {
        return false;
      }

      if (
        !Number.isInteger(addressId) ||
        addressId <= 0
      ) {

        set({
          error:
            "Please select a valid saved address.",
        });

        return false;
      }


      const {
        sessionId,
        userId,
      } = get();

      if (userId === null) {

        set({
          error:
            "User ID is required to continue checkout.",
        });

        return false;
      }


      const userMessage: ChatMessage = {
        id: createMessageId(),

        role: "user",

        content:
          "Use the selected delivery address.",

        created_at:
          new Date().toISOString(),
      };


      set((state) => ({
        messages: [
          ...state.messages,
          userMessage,
        ],

        isLoading: true,

        error: null,
      }));


      try {

        const response =
          await sendChatMessage({
            message:
              "Use the selected delivery address.",

            session_id:
              sessionId,

            user_id:
              userId,

            selected_address_id:
              addressId,
          });


        const assistantMessage =
          createAssistantMessage(
            response,
          );


        set((state) => ({
          messages: [
            ...state.messages,
            assistantMessage,
          ],

          isLoading: false,

          error: null,
        }));


        // ----------------------------------------------------
        // Backend remains authoritative.
        //
        // The selected address is NOT directly written into
        // checkout here. It is accepted only through the
        // backend response.
        // ----------------------------------------------------

        applyBackendCheckoutState(
          set,
          response,
        );


        return true;


      } catch (error) {

        const errorMessage =
          error instanceof Error
            ? error.message
            : "Something went wrong while contacting BuyQK AI.";

        set({
          isLoading: false,

          error:
            errorMessage,
        });

        return false;
      }
    },


    // ========================================================
    // Continue with Payment Method
    // ========================================================

    continueWithPaymentMethod: async (
      methodId: string
    ) => {

      if (get().isLoading) {
        return false;
      }


      const normalizedMethod =
        methodId.trim();

      if (!normalizedMethod) {

        set({
          error:
            "Please select a valid payment method.",
        });

        return false;
      }


      const {
        sessionId,
        userId,
      } = get();

      if (userId === null) {

        set({
          error:
            "User ID is required to continue checkout.",
        });

        return false;
      }


      const userMessage: ChatMessage = {
        id: createMessageId(),

        role: "user",

        // Do not expose assumptions about the method.
        // The selected ID comes from backend-provided UI
        // metadata.
        content:
          "Use the selected payment method.",

        created_at:
          new Date().toISOString(),
      };


      set((state) => ({
        messages: [
          ...state.messages,
          userMessage,
        ],

        isLoading: true,

        error: null,
      }));


      try {

        const response =
          await sendChatMessage({
            message:
              "Use the selected payment method.",

            session_id:
              sessionId,

            user_id:
              userId,

            payment_method:
              normalizedMethod,
          });


        const assistantMessage =
          createAssistantMessage(
            response,
          );


        set((state) => ({
          messages: [
            ...state.messages,
            assistantMessage,
          ],

          isLoading: false,

          error: null,
        }));


        // ----------------------------------------------------
        // Do not directly mutate payment state.
        //
        // The backend decides whether the supplied method is
        // valid and what payment method is actually associated
        // with the checkout/order.
        // ----------------------------------------------------

        applyBackendCheckoutState(
          set,
          response,
        );


        return true;


      } catch (error) {

        const errorMessage =
          error instanceof Error
            ? error.message
            : "Something went wrong while contacting BuyQK AI.";

        set({
          isLoading: false,

          error:
            errorMessage,
        });

        return false;
      }
    },


    // ========================================================
    // Clear Chat
    // ========================================================

    clearChat: () => {

      set({

        messages: [],

        isLoading: false,

        error: null,

        sessionId:
          createSessionId(),

        checkout:
          null,
      });
    },
  }));