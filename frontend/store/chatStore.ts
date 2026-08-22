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
// - Maintain authoritative frontend cart representation
// - Call the typed chat API
// - Clear/reset conversation
//
// IMPORTANT:
//
// The backend remains authoritative for:
//
// - cart state
// - cart quantities
// - product resolution
// - product price
// - stock
// - product availability
// - checkout status
// - order creation
// - order ID
// - address selection
// - payment method
// - billing
// - prices
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

import {
  getCart as apiGetCart,
  addCartItem as apiAddCartItem,
  updateCartItem as apiUpdateCartItem,
  removeCartItem as apiRemoveCartItem,
  clearCart as apiClearCart,
} from "../services/cart_service";

import type {
  Bill,
  Cart,
  CartItem,
  CartSummary,
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

  /**
   * Current authoritative cart representation.
   *
   * This is populated only from backend responses.
   *
   * The frontend must never calculate or invent cart state.
   */
  cart: Cart | null;

  /**
   * Loading state for direct Cart API operations.
   *
   * Kept separate from chat loading because Cart API mutations
   * are deterministic REST operations, not chat operations.
   */
  isCartLoading: boolean;


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

  /**
   * Load the authoritative cart from the Cart API.
   */
  refreshCart: () => Promise<boolean>;

  /**
   * Add a product to the current Cart through the Cart API.
   */
  addCartItem: (
    productId: number,
    quantity?: number
  ) => Promise<boolean>;

  /**
   * Update an existing Cart item through the Cart API.
   */
  updateCartItem: (
    itemId: number,
    quantity: number
  ) => Promise<boolean>;

  /**
   * Remove an existing Cart item through the Cart API.
   */
  removeCartItem: (
    itemId: number
  ) => Promise<boolean>;

  /**
   * Delete the current backend Cart through the Cart API.
   */
  clearCart: () => Promise<boolean>;

  /**
   * Replace the frontend cart only with an already-authoritative
   * backend cart representation.
   *
   * This does not calculate, mutate, or optimistically modify
   * cart business state.
   */
  setCart: (cart: unknown) => boolean;

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
// It only validates/preserves structured values returned
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
// Cart Item Normalization
// ============================================================
//
// The backend Cart Service serializes each cart item with:
//
// - id
// - product_id
// - product_name
// - quantity
// - unit_price
// - line_total
// - stock
// - is_available
//
// We validate the required fields here.
//
// We do NOT calculate line_total.
// ============================================================

function normalizeCartItem(
  item: unknown,
): CartItem | null {

  if (
    !item ||
    typeof item !== "object" ||
    Array.isArray(item)
  ) {
    return null;
  }

  const value =
    item as Record<string, unknown>;

  if (
    typeof value.id !== "number" ||
    typeof value.product_id !== "number" ||
    typeof value.product_name !== "string" ||
    typeof value.quantity !== "number" ||
    typeof value.unit_price !== "number" ||
    typeof value.line_total !== "number"
  ) {
    return null;
  }

  return value as unknown as CartItem;
}


// ============================================================
// Cart Summary Normalization
// ============================================================
//
// The backend is responsible for calculating these values.
//
// The frontend only validates the shape.
// ============================================================

function normalizeCartSummary(
  summary: unknown,
): CartSummary | null {

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
    typeof value.item_count !== "number" ||
    typeof value.total_quantity !== "number" ||
    typeof value.subtotal !== "number" ||
    typeof value.total !== "number" ||
    typeof value.currency !== "string"
  ) {
    return null;
  }

  if (
    value.delivery_charge !== null &&
    typeof value.delivery_charge !== "number"
  ) {
    return null;
  }

  if (
    value.discount !== null &&
    typeof value.discount !== "number"
  ) {
    return null;
  }

  if (
    value.tax !== null &&
    typeof value.tax !== "number"
  ) {
    return null;
  }

  return value as unknown as CartSummary;
}


// ============================================================
// Cart Normalization
// ============================================================
//
// IMPORTANT:
//
// This function only accepts authoritative backend cart data.
//
// It does NOT:
//
// - calculate totals
// - calculate quantities
// - create cart IDs
// - modify items
// - determine stock
// - determine availability
// ============================================================

function normalizeCart(
  cart: unknown,
): Cart | null {

  if (
    !cart ||
    typeof cart !== "object" ||
    Array.isArray(cart)
  ) {
    return null;
  }

  const value =
    cart as Record<string, unknown>;

  if (
    typeof value.cart_id !== "number" ||
    typeof value.user_id !== "number" ||
    typeof value.status !== "string" ||
    !Array.isArray(value.items)
  ) {
    return null;
  }

  const items: CartItem[] = [];

  for (const item of value.items) {

    const normalizedItem =
      normalizeCartItem(item);

    if (!normalizedItem) {
      return null;
    }

    items.push(normalizedItem);
  }

  const summary =
    normalizeCartSummary(
      value.summary
    );

  if (!summary) {
    return null;
  }

  return {
    ...value,

    cart_id:
      value.cart_id,

    user_id:
      value.user_id,

    status:
      value.status,

    items,

    summary,
  } as Cart;
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

      /**
       * Cart associated with this checkout.
       *
       * Backend remains authoritative.
       */
      cart_id:
        backendCheckout.cart_id ??
        metadata.cart_id ??
        previous?.cart_id ??
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
    metadata.cart_id !== undefined ||
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

    cart_id:
      metadata.cart_id ??
      previous?.cart_id ??
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


  // ----------------------------------------------------------
  // Normalize cart
  // ----------------------------------------------------------
  //
  // Cart metadata is optional.
  //
  // If invalid, we do not replace the existing cart.
  //
  // The actual preservation logic is handled by
  // applyBackendState().
  // ----------------------------------------------------------

  if (metadata.cart !== undefined) {

    const cart =
      normalizeCart(
        metadata.cart,
      );

    if (cart) {
      metadata.cart = cart;
    } else {
      delete metadata.cart;
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

    id:
      createMessageId(),

    role:
      "assistant",

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
// Apply Backend Checkout + Cart State
// ============================================================
//
// Centralized state update.
//
// Every successful backend response passes through this
// function.
//
// No frontend business decision is made here.
//
// The important rule is:
//
//     response contains cart
//         ↓
//     validate cart
//         ↓
//     store cart
//
// If the response does not contain cart:
//
//     keep existing cart
//
// This prevents unrelated chat responses from accidentally
// deleting the user's current cart.
// ============================================================

function applyBackendState(
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

  set((state) => {

    let nextCart =
      state.cart;

    // --------------------------------------------------------
    // Only replace cart when backend actually returned one.
    // --------------------------------------------------------

    if (
      metadata &&
      metadata.cart !== undefined
    ) {

      // normalizeResponseMetadata() has already validated the
      // backend cart. Reuse that normalized representation.
      const normalizedCart =
        normalizeCart(
          metadata.cart,
        );

      if (normalizedCart) {
        nextCart =
          normalizedCart;
      }
    }

    return {

      checkout:
        normalizeCheckoutState(
          metadata,
          state.checkout,
        ),

      cart:
        nextCart,
    };
  });
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

    isCartLoading:
      false,

    /**
     * No cart exists in the frontend until the backend
     * provides authoritative cart state.
     */
    cart:
      null,


    // ========================================================
    // Set User ID
    // ========================================================

    setUserId: (
      userId: number
    ) => {

      if (
        !Number.isInteger(userId) ||
        userId <= 0
      ) {

        set({
          error:
            "Invalid user ID.",
        });

        return;
      }

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

        id:
          createMessageId(),

        role:
          "user",

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

        isLoading:
          true,

        error:
          null,
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

          isLoading:
            false,

          error:
            null,
        }));


        // ----------------------------------------------------
        // Update authoritative backend state
        // ----------------------------------------------------
        //
        // This includes:
        //
        // - checkout
        // - cart
        //
        // The frontend does not calculate either.
        // ----------------------------------------------------

        applyBackendState(
          set,
          response,
        );


      } catch (error) {

        const errorMessage =
          error instanceof Error
            ? error.message
            : "Something went wrong while contacting BuyQK AI.";


        set({

          isLoading:
            false,

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

        id:
          createMessageId(),

        role:
          "user",

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

        isLoading:
          true,

        error:
          null,
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

          isLoading:
            false,

          error:
            null,
        }));


        // ----------------------------------------------------
        // Backend remains authoritative.
        //
        // The selected address is NOT directly written into
        // checkout here.
        //
        // Cart is also updated only if the backend returns
        // authoritative cart metadata.
        // ----------------------------------------------------

        applyBackendState(
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

          isLoading:
            false,

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

        id:
          createMessageId(),

        role:
          "user",

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

        isLoading:
          true,

        error:
          null,
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

          isLoading:
            false,

          error:
            null,
        }));


        // ----------------------------------------------------
        // Do not directly mutate payment state.
        //
        // The backend decides whether the supplied method is
        // valid and what payment method is actually associated
        // with the checkout/order.
        //
        // Cart is likewise updated only from backend metadata.
        // ----------------------------------------------------

        applyBackendState(
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

          isLoading:
            false,

          error:
            errorMessage,
        });


        return false;
      }
    },


    // ========================================================
    // Refresh authoritative Cart
    // ========================================================
    //
    // Direct Cart API operation.
    //
    // The backend remains authoritative. The store only accepts
    // the returned Cart after normalizeCart() validation.
    // ========================================================

    refreshCart: async () => {

      const userId =
        get().userId;

      if (userId === null) {

        set({
          error:
            "User ID is required to load the cart.",
        });

        return false;
      }

      if (get().isCartLoading) {
        return false;
      }

      set({
        isCartLoading:
          true,
        error:
          null,
      });

      try {

        const cart =
          await apiGetCart(userId);

        const normalizedCart =
          normalizeCart(cart);

        if (!normalizedCart) {
          throw new Error(
            "Received invalid cart data from the backend.",
          );
        }

        set({
          cart:
            normalizedCart,
          isCartLoading:
            false,
          error:
            null,
        });

        return true;

      } catch (error) {

        set({
          isCartLoading:
            false,
          error:
            error instanceof Error
              ? error.message
              : "Unable to load the cart.",
        });

        return false;
      }
    },


    // ========================================================
    // Add Cart Item
    // ========================================================

    addCartItem: async (
      productId: number,
      quantity: number = 1,
    ) => {

      const userId = get().userId;

      if (userId === null) {
        set({ error: "User ID is required to add an item to the cart." });
        return false;
      }

      if (!Number.isInteger(productId) || productId <= 0) {
        set({ error: "A valid product ID is required." });
        return false;
      }

      if (!Number.isInteger(quantity) || quantity <= 0) {
        set({ error: "Quantity must be a positive integer." });
        return false;
      }

      if (get().isCartLoading) {
        return false;
      }

      set({ isCartLoading: true, error: null });

      try {
        const cart = await apiAddCartItem({
          user_id: userId,
          product_id: productId,
          quantity,
        });

        const normalizedCart = normalizeCart(cart);

        if (!normalizedCart) {
          throw new Error("Received invalid cart data from the backend.");
        }

        set({
          cart: normalizedCart,
          isCartLoading: false,
          error: null,
        });

        return true;
      } catch (error) {
        set({
          isCartLoading: false,
          error: error instanceof Error
            ? error.message
            : "Unable to add the item to the cart.",
        });
        return false;
      }
    },

    // ========================================================
    // Update Cart Item
    // ========================================================

    updateCartItem: async (
      itemId: number,
      quantity: number,
    ) => {

      const userId =
        get().userId;

      if (userId === null) {

        set({
          error:
            "User ID is required to update the cart.",
        });

        return false;
      }

      if (
        !Number.isInteger(itemId) ||
        itemId <= 0
      ) {

        set({
          error:
            "A valid cart item ID is required.",
        });

        return false;
      }

      if (
        !Number.isInteger(quantity) ||
        quantity <= 0
      ) {

        set({
          error:
            "Quantity must be a positive integer.",
        });

        return false;
      }

      if (get().isCartLoading) {
        return false;
      }

      set({
        isCartLoading:
          true,
        error:
          null,
      });

      try {

        const cart =
          await apiUpdateCartItem(
            itemId,
            {
              user_id:
                userId,
              quantity,
            },
          );

        const normalizedCart =
          normalizeCart(cart);

        if (!normalizedCart) {
          throw new Error(
            "Received invalid cart data from the backend.",
          );
        }

        set({
          cart:
            normalizedCart,
          isCartLoading:
            false,
          error:
            null,
        });

        return true;

      } catch (error) {

        set({
          isCartLoading:
            false,
          error:
            error instanceof Error
              ? error.message
              : "Unable to update the cart.",
        });

        return false;
      }
    },


    // ========================================================
    // Remove Cart Item
    // ========================================================

    removeCartItem: async (
      itemId: number,
    ) => {

      const userId =
        get().userId;

      if (userId === null) {

        set({
          error:
            "User ID is required to remove an item.",
        });

        return false;
      }

      if (
        !Number.isInteger(itemId) ||
        itemId <= 0
      ) {

        set({
          error:
            "A valid cart item ID is required.",
        });

        return false;
      }

      if (get().isCartLoading) {
        return false;
      }

      set({
        isCartLoading:
          true,
        error:
          null,
      });

      try {

        const cart =
          await apiRemoveCartItem(
            itemId,
            userId,
          );

        const normalizedCart =
          normalizeCart(cart);

        if (!normalizedCart) {
          throw new Error(
            "Received invalid cart data from the backend.",
          );
        }

        set({
          cart:
            normalizedCart,
          isCartLoading:
            false,
          error:
            null,
        });

        return true;

      } catch (error) {

        set({
          isCartLoading:
            false,
          error:
            error instanceof Error
              ? error.message
              : "Unable to remove the cart item.",
        });

        return false;
      }
    },


    // ========================================================
    // Clear Cart
    // ========================================================

    clearCart: async () => {

      const userId =
        get().userId;

      if (userId === null) {

        set({
          error:
            "User ID is required to clear the cart.",
        });

        return false;
      }

      if (get().isCartLoading) {
        return false;
      }

      set({
        isCartLoading:
          true,
        error:
          null,
      });

      try {

        const cart =
          await apiClearCart(
            userId,
          );

        const normalizedCart =
          normalizeCart(cart);

        if (!normalizedCart) {
          throw new Error(
            "Received invalid cart data from the backend.",
          );
        }

        set({
          cart:
            normalizedCart,
          isCartLoading:
            false,
          error:
            null,
        });

        return true;

      } catch (error) {

        set({
          isCartLoading:
            false,
          error:
            error instanceof Error
              ? error.message
              : "Unable to clear the cart.",
        });

        return false;
      }
    },


    // ========================================================
    // Set authoritative Cart
    // ========================================================
    //
    // This is the only public store action for replacing cart
    // state. It accepts backend-shaped data and validates it
    // through normalizeCart().
    //
    // IMPORTANT:
    // - no optimistic cart mutation
    // - no quantity calculation
    // - no subtotal/total calculation
    // - no stock/availability decision
    // ========================================================

    setCart: (cart: unknown) => {
      const normalizedCart = normalizeCart(cart);

      if (!normalizedCart) {
        set({
          error: "Received invalid cart data from the backend.",
        });

        return false;
      }

      set({
        cart: normalizedCart,
        error: null,
      });

      return true;
    },

    // ========================================================
    // Clear Chat
    // ========================================================
    //
    // A new session means a new frontend conversation state.
    //
    // Therefore:
    //
    // messages  -> reset
    // sessionId -> regenerate
    // checkout  -> reset
    // cart      -> preserved
    //
    // The backend cart itself is NOT deleted here.
    //
    // This is important:
    //
    // `clearChat()` only clears frontend conversation state.
    //
    // Actual cart deletion must happen through the dedicated
    // Cart API.
    // ========================================================

    clearChat: () => {

      set((state) => ({

        messages:
          [],

        isLoading:
          false,

        isCartLoading:
          false,

        error:
          null,

        sessionId:
          createSessionId(),

        checkout:
          null,

        // IMPORTANT:
        // clearChat() clears conversation state only.
        // The backend cart is still authoritative and must not
        // disappear merely because a new chat session starts.
        cart:
          state.cart,
      }));
    },
  }));