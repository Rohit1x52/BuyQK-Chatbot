// ============================================================
// BuyQK Chat / Address API Client
// ============================================================
//
// Responsibility:
// - Communicate with the BuyQK FastAPI backend
// - Send typed chat requests
// - Preserve structured chat metadata, including Cart state
// - Retrieve saved addresses
// - Create saved addresses
// - Handle HTTP/network errors
//
// UI state belongs in chatStore.ts.
// UI rendering belongs in React components.
//
// ============================================================

import type {
  Address,
  ChatRequest,
  ChatResponse,
  CreateAddressRequest,
  CreateAddressResponse,
  GetAddressesResponse,
} from "../types/chat";

// ============================================================
// API Configuration
// ============================================================

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

// ============================================================
// Shared HTTP Error Parser
// ============================================================

async function parseError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const contentType =
      response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      const errorData: unknown = await response.json();

      if (
        typeof errorData === "object" &&
        errorData !== null
      ) {
        const detail = (errorData as {
          detail?: unknown;
          message?: unknown;
        }).detail;

        if (typeof detail === "string") {
          return detail;
        }

        if (detail !== undefined) {
          return JSON.stringify(detail);
        }

        const message = (errorData as {
          message?: unknown;
        }).message;

        if (typeof message === "string") {
          return message;
        }
      }
    }
  } catch {
    // Fall through to fallback.
  }

  return fallback;
}

// ============================================================
// Shared Network Error
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
// Chat Response Validation
// ============================================================
//
// Important:
// JSON.parse/json response typing alone does not validate runtime data.
// We only validate the minimum ChatResponse contract here.
//
// Cart validation/normalization remains in chatStore.ts so there is
// exactly one place responsible for turning backend Cart data into
// frontend state.
//
// ============================================================

function validateChatResponse(
  value: unknown,
): ChatResponse {
  if (
    typeof value !== "object" ||
    value === null
  ) {
    throw new Error(
      "BuyQK backend returned an invalid chat response.",
    );
  }

  const data = value as {
    response?: unknown;
    metadata?: unknown;
  };

  if (typeof data.response !== "string") {
    throw new Error(
      "BuyQK backend returned an invalid chat response.",
    );
  }

  // Metadata is intentionally not reshaped here.
  // This preserves Cart / Checkout / Address metadata end-to-end.
  return value as ChatResponse;
}

// ============================================================
// POST /chat
// ============================================================

export async function sendChatMessage(
  request: ChatRequest,
): Promise<ChatResponse> {
  if (
    typeof request.message !== "string" ||
    !request.message.trim()
  ) {
    throw new Error("A chat message is required.");
  }

  if (
    !Number.isInteger(request.user_id) ||
    request.user_id <= 0
  ) {
    throw new Error("A valid user ID is required.");
  }

  if (
    typeof request.session_id !== "string" ||
    !request.session_id.trim()
  ) {
    throw new Error("A valid session ID is required.");
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/chat`,
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
      "Unable to connect to the BuyQK backend.",
    );
  }

  if (!response.ok) {
    const errorMessage = await parseError(
      response,
      "Unable to communicate with BuyQK AI.",
    );

    throw new Error(errorMessage);
  }

  try {
    const data: unknown = await response.json();
    return validateChatResponse(data);
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error(
      "BuyQK backend returned an invalid chat response.",
    );
  }
}

// ============================================================
// GET /addresses
// ============================================================

export async function getSavedAddresses(
  userId: number,
): Promise<Address[]> {
  if (
    !Number.isInteger(userId) ||
    userId <= 0
  ) {
    throw new Error(
      "A valid user ID is required to load saved addresses.",
    );
  }

  const url =
    `${API_BASE_URL}/addresses?user_id=${encodeURIComponent(
      userId,
    )}`;

  let response: Response;

  try {
    response = await fetch(
      url,
      {
        method: "GET",
        // Do not add Content-Type to this GET.
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      },
    );
  } catch (error) {
    throw createNetworkError(
      error,
      "Unable to load your saved addresses.",
    );
  }

  if (!response.ok) {
    const errorMessage = await parseError(
      response,
      `Unable to load your saved addresses. Server returned ${response.status}.`,
    );

    throw new Error(errorMessage);
  }

  let data: GetAddressesResponse;

  try {
    data =
      (await response.json()) as GetAddressesResponse;
  } catch {
    throw new Error(
      "The address server returned an invalid response.",
    );
  }

  if (!data?.success) {
    throw new Error(
      "Unable to load your saved addresses.",
    );
  }

  if (!Array.isArray(data.addresses)) {
    throw new Error(
      "Received an invalid address list from the server.",
    );
  }

  return data.addresses;
}

// ============================================================
// POST /addresses
// ============================================================

export async function createSavedAddress(
  request: CreateAddressRequest,
): Promise<Address> {
  if (
    !Number.isInteger(request.user_id) ||
    request.user_id <= 0
  ) {
    throw new Error("A valid user ID is required.");
  }

  if (
    typeof request.label !== "string" ||
    !request.label.trim()
  ) {
    throw new Error("Address label is required.");
  }

  if (
    typeof request.address !== "string" ||
    !request.address.trim()
  ) {
    throw new Error("Address is required.");
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/addresses`,
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
      "Unable to connect to the BuyQK backend while saving the address.",
    );
  }

  if (!response.ok) {
    const errorMessage = await parseError(
      response,
      `Unable to save this address. Server returned ${response.status}.`,
    );

    throw new Error(errorMessage);
  }

  let data: CreateAddressResponse;

  try {
    data =
      (await response.json()) as CreateAddressResponse;
  } catch {
    throw new Error(
      "The address server returned an invalid response.",
    );
  }

  if (
    !data?.success ||
    !data.address
  ) {
    throw new Error(
      "Unable to save this address. Please check the details and try again.",
    );
  }

  return data.address;
}

// ============================================================
// Backend Health Check
// ============================================================

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/health`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      },
    );

    return response.ok;
  } catch {
    return false;
  }
}