// ============================================================
// BuyQK Cart API Client
// ============================================================
//
// Responsibility:
// - Communicate with the BuyQK FastAPI Cart endpoints
// - Validate request arguments before making HTTP calls
// - Parse and validate Cart responses
// - Return backend-authoritative Cart state
//
// UI state belongs in chatStore.ts.
// Cart business logic belongs in the backend CartService.
//
// Supported endpoints:
//
// GET    /cart
// POST   /cart/items
// PATCH  /cart/items/{id}
// DELETE /cart/items/{id}
// DELETE /cart
//
// IMPORTANT:
// The frontend never calculates prices, totals, stock, discounts,
// or cart business rules. The backend is authoritative.
// ============================================================

import type {
  Cart,
  CartResponse,
} from "../types/chat";

// ============================================================
// API Configuration
// ============================================================

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

// ============================================================
// Types
// ============================================================

export interface AddCartItemRequest {
  user_id: number;
  product_id: number;
  quantity: number;
}

export interface UpdateCartItemRequest {
  user_id: number;
  quantity: number;
}

// ============================================================
// Error Parser
// ============================================================

async function parseError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const contentType =
      response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
      return fallback;
    }

    const data: unknown = await response.json();

    if (
      typeof data === "object" &&
      data !== null
    ) {
      const errorData = data as {
        detail?: unknown;
        message?: unknown;
      };

      if (typeof errorData.detail === "string") {
        return errorData.detail;
      }

      if (errorData.detail !== undefined) {
        return JSON.stringify(errorData.detail);
      }

      if (typeof errorData.message === "string") {
        return errorData.message;
      }
    }
  } catch {
    // Fall through to fallback.
  }

  return fallback;
}

// ============================================================
// Network Error
// ============================================================

function createNetworkError(
  error: unknown,
  fallback: string,
): Error {
  if (error instanceof TypeError) {
    return new Error(
      `${fallback} Make sure the BuyQK backend is running and the API URL is correct.`,
    );
  }

  if (error instanceof Error) {
    return error;
  }

  return new Error(fallback);
}

// ============================================================
// Request Validation
// ============================================================

function validateUserId(
  userId: number,
): void {
  if (
    !Number.isInteger(userId) ||
    userId <= 0
  ) {
    throw new Error(
      "A valid user ID is required.",
    );
  }
}

function validateProductId(
  productId: number,
): void {
  if (
    !Number.isInteger(productId) ||
    productId <= 0
  ) {
    throw new Error(
      "A valid product ID is required.",
    );
  }
}

function validateQuantity(
  quantity: number,
): void {
  if (
    !Number.isInteger(quantity) ||
    quantity <= 0
  ) {
    throw new Error(
      "Quantity must be a positive integer.",
    );
  }
}

// ============================================================
// Cart Response Validation
// ============================================================
//
// Runtime validation is intentionally minimal.
//
// The Cart object is returned by the backend and normalized by
// chatStore.ts before entering UI state. This client verifies
// the response envelope without duplicating Cart normalization.
// ============================================================

function parseCartResponse(
  value: unknown,
): Cart {
  if (
    typeof value !== "object" ||
    value === null
  ) {
    throw new Error(
      "BuyQK backend returned an invalid cart response.",
    );
  }

  const data = value as Partial<CartResponse>;

  if (!data.success) {
    throw new Error(
      "BuyQK backend returned an unsuccessful cart response.",
    );
  }

  if (
    !data.cart ||
    typeof data.cart !== "object"
  ) {
    throw new Error(
      "BuyQK backend returned an invalid cart.",
    );
  }

  return data.cart;
}

// ============================================================
// GET /cart
// ============================================================

export async function getCart(
  userId: number,
): Promise<Cart> {
  validateUserId(userId);

  const url =
    `${API_BASE_URL}/cart?user_id=${encodeURIComponent(
      userId,
    )}`;

  let response: Response;

  try {
    response = await fetch(
      url,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      },
    );
  } catch (error) {
    throw createNetworkError(
      error,
      "Unable to load your cart.",
    );
  }

  if (!response.ok) {
    throw new Error(
      await parseError(
        response,
        `Unable to load your cart. Server returned ${response.status}.`,
      ),
    );
  }

  try {
    return parseCartResponse(
      await response.json(),
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error(
      "The cart server returned an invalid response.",
    );
  }
}

// ============================================================
// POST /cart/items
// ============================================================

export async function addCartItem(
  request: AddCartItemRequest,
): Promise<Cart> {
  validateUserId(request.user_id);
  validateProductId(request.product_id);
  validateQuantity(request.quantity);

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/cart/items`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(request),
        cache: "no-store",
      },
    );
  } catch (error) {
    throw createNetworkError(
      error,
      "Unable to add this product to your cart.",
    );
  }

  if (!response.ok) {
    throw new Error(
      await parseError(
        response,
        `Unable to add this product to your cart. Server returned ${response.status}.`,
      ),
    );
  }

  try {
    return parseCartResponse(
      await response.json(),
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error(
      "The cart server returned an invalid response.",
    );
  }
}

// ============================================================
// PATCH /cart/items/{id}
// ============================================================

export async function updateCartItem(
  itemId: number,
  request: UpdateCartItemRequest,
): Promise<Cart> {
  validateUserId(request.user_id);

  if (
    !Number.isInteger(itemId) ||
    itemId <= 0
  ) {
    throw new Error(
      "A valid cart item ID is required.",
    );
  }

  validateQuantity(request.quantity);

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/cart/items/${encodeURIComponent(
        itemId,
      )}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(request),
        cache: "no-store",
      },
    );
  } catch (error) {
    throw createNetworkError(
      error,
      "Unable to update this cart item.",
    );
  }

  if (!response.ok) {
    throw new Error(
      await parseError(
        response,
        `Unable to update this cart item. Server returned ${response.status}.`,
      ),
    );
  }

  try {
    return parseCartResponse(
      await response.json(),
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error(
      "The cart server returned an invalid response.",
    );
  }
}

// ============================================================
// DELETE /cart/items/{id}
// ============================================================

export async function removeCartItem(
  itemId: number,
  userId: number,
): Promise<Cart> {
  validateUserId(userId);

  if (
    !Number.isInteger(itemId) ||
    itemId <= 0
  ) {
    throw new Error(
      "A valid cart item ID is required.",
    );
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/cart/items/${encodeURIComponent(
        itemId,
      )}?user_id=${encodeURIComponent(userId)}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      },
    );
  } catch (error) {
    throw createNetworkError(
      error,
      "Unable to remove this item from your cart.",
    );
  }

  if (!response.ok) {
    throw new Error(
      await parseError(
        response,
        `Unable to remove this cart item. Server returned ${response.status}.`,
      ),
    );
  }

  try {
    return parseCartResponse(
      await response.json(),
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error(
      "The cart server returned an invalid response.",
    );
  }
}

// ============================================================
// DELETE /cart
// ============================================================

export async function clearCart(
  userId: number,
): Promise<Cart> {
  validateUserId(userId);

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/cart?user_id=${encodeURIComponent(
        userId,
      )}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      },
    );
  } catch (error) {
    throw createNetworkError(
      error,
      "Unable to clear your cart.",
    );
  }

  if (!response.ok) {
    throw new Error(
      await parseError(
        response,
        `Unable to clear your cart. Server returned ${response.status}.`,
      ),
    );
  }

  try {
    return parseCartResponse(
      await response.json(),
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error(
      "The cart server returned an invalid response.",
    );
  }
}