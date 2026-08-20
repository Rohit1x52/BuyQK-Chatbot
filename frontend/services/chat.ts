// ============================================================
// BuyQK Chat / Address API Client
// ============================================================
//
// Responsibility:
// - Communicate with the BuyQK FastAPI backend
// - Send typed chat requests
// - Retrieve saved addresses
// - Create saved addresses
// - Handle HTTP/network errors
//
// UI state belongs in chatStore.ts.
// UI rendering belongs in React components.
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

    if (
      contentType.includes("application/json")
    ) {

      const errorData = await response.json();

      if (
        typeof errorData?.detail === "string"
      ) {
        return errorData.detail;
      }

      if (errorData?.detail) {

        return JSON.stringify(
          errorData.detail
        );
      }

      if (
        typeof errorData?.message === "string"
      ) {

        return errorData.message;
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
      `${fallback} Make sure the BuyQK backend is running and the API URL is correct.`
    );
  }

  if (error instanceof Error) {

    return error;
  }

  return new Error(
    fallback
  );
}


// ============================================================
// POST /chat
// ============================================================

export async function sendChatMessage(
  request: ChatRequest,
): Promise<ChatResponse> {

  let response: Response;

  try {

    response = await fetch(
      `${API_BASE_URL}/chat`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify(request),

        cache: "no-store",
      }
    );

  } catch (error) {

    throw createNetworkError(
      error,
      "Unable to connect to the BuyQK backend.",
    );
  }


  // ----------------------------------------------------------
  // HTTP Error
  // ----------------------------------------------------------

  if (!response.ok) {

    const errorMessage =
      await parseError(
        response,
        "Unable to communicate with BuyQK AI.",
      );

    throw new Error(
      errorMessage
    );
  }


  // ----------------------------------------------------------
  // Parse Response
  // ----------------------------------------------------------

  try {

    const data =
      await response.json();

    return data as ChatResponse;

  } catch {

    throw new Error(
      "BuyQK backend returned an invalid chat response."
    );
  }
}


// ============================================================
// GET /addresses
// ============================================================
//
// IMPORTANT:
//
// Do NOT send:
//     Content-Type: application/json
//
// on this GET request.
//
// Doing so can trigger a CORS preflight in the browser.
// That is unnecessary for GET and can result in:
//
//     TypeError: Failed to fetch
//
// ============================================================

export async function getSavedAddresses(
  userId: number,
): Promise<Address[]> {

  if (
    !Number.isInteger(userId) ||
    userId <= 0
  ) {

    throw new Error(
      "A valid user ID is required to load saved addresses."
    );
  }


  const url =
    `${API_BASE_URL}/addresses?user_id=${encodeURIComponent(
      userId
    )}`;


  let response: Response;

  try {

    response = await fetch(
      url,
      {
        method: "GET",

        // IMPORTANT:
        // No Content-Type header here.
        headers: {
          Accept: "application/json",
        },

        cache: "no-store",
      }
    );

  } catch (error) {

    throw createNetworkError(
      error,
      "Unable to load your saved addresses.",
    );
  }


  // ----------------------------------------------------------
  // HTTP Error
  // ----------------------------------------------------------

  if (!response.ok) {

    const errorMessage =
      await parseError(
        response,
        `Unable to load your saved addresses. Server returned ${response.status}.`,
      );

    throw new Error(
      errorMessage
    );
  }


  // ----------------------------------------------------------
  // Parse Response
  // ----------------------------------------------------------

  let data: GetAddressesResponse;

  try {

    data =
      await response.json() as GetAddressesResponse;

  } catch {

    throw new Error(
      "The address server returned an invalid response."
    );
  }


  // ----------------------------------------------------------
  // Validate Response
  // ----------------------------------------------------------

  if (!data?.success) {

    throw new Error(
      "Unable to load your saved addresses."
    );
  }


  if (!Array.isArray(data.addresses)) {

    throw new Error(
      "Received an invalid address list from the server."
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
      }
    );

  } catch (error) {

    throw createNetworkError(
      error,
      "Unable to connect to the BuyQK backend while saving the address.",
    );
  }


  // ----------------------------------------------------------
  // HTTP Error
  // ----------------------------------------------------------

  if (!response.ok) {

    const errorMessage =
      await parseError(
        response,
        `Unable to save this address. Server returned ${response.status}.`,
      );

    throw new Error(
      errorMessage
    );
  }


  // ----------------------------------------------------------
  // Parse Response
  // ----------------------------------------------------------

  let data: CreateAddressResponse;

  try {

    data =
      await response.json() as CreateAddressResponse;

  } catch {

    throw new Error(
      "The address server returned an invalid response."
    );
  }


  // ----------------------------------------------------------
  // Validate Response
  // ----------------------------------------------------------

  if (
    !data?.success ||
    !data.address
  ) {

    throw new Error(
      "Unable to save this address. Please check the details and try again."
    );
  }


  return data.address;
}


// ============================================================
// Backend Health Check
// ============================================================

export async function checkBackendHealth(): Promise<boolean> {

  try {

    const response =
      await fetch(
        `${API_BASE_URL}/health`,
        {
          method: "GET",

          headers: {
            Accept: "application/json",
          },

          cache: "no-store",
        }
      );

    return response.ok;

  } catch {

    return false;
  }
}