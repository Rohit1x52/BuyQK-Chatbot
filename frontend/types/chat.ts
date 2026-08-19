// ============================================================
// BuyQK AI - Shared Chat Types
// ============================================================
//
// Backend:
//     FastAPI -> POST /chat
//
// Frontend:
//     chat.ts -> chatStore.ts -> Chat UI
//
// Keep these types aligned with:
//
//     backend/schemas/chat_schema.py
//     backend/api/chat.py
//
// IMPORTANT:
//
// The backend/database is authoritative for:
//
//     - product price
//     - stock
//     - delivery charge
//     - discount
//     - tax
//     - final total
//     - order ID
//     - order status
//     - payment status
//     - billing
//
// The frontend only displays authoritative values.
// It must NOT calculate transactional values.
// ============================================================


// ============================================================
// Chat Request
// ============================================================

export interface ChatRequest {
  message: string;

  session_id: string;

  user_id: number;

  /**
   * Address selected explicitly by the user in the UI.
   */
  selected_address_id?: number;

  /**
   * Payment method selected explicitly by the user.
   *
   * The frontend must not hardcode available methods.
   */
  payment_method?: string;
}


// ============================================================
// Address
// ============================================================

export interface Address {
  id: number;

  label: string;

  address: string;

  city?: string | null;

  state?: string | null;

  postal_code?: string | null;
}


export interface CreateAddressRequest {
  user_id: number;

  label: string;

  address: string;

  city?: string;

  state?: string;

  postal_code?: string;
}


export interface GetAddressesResponse {
  success: boolean;

  addresses: Address[];
}


export interface CreateAddressResponse {
  success: boolean;

  address: Address;
}


// ============================================================
// Product
// ============================================================

export interface Product {
  id: number;

  name: string;

  brand?: string | null;

  description?: string | null;

  /**
   * Backend-authoritative product price.
   */
  price: number;

  stock?: number | null;

  merchant_id?: number | null;

  category_id?: number | null;

  image_url?: string | null;

  is_available?: boolean | null;
}


// ============================================================
// Checkout State
// ============================================================
//
// This mirrors the authoritative transaction state introduced
// during Phase 1 / Phase 2.
//
// IMPORTANT:
//
// The frontend may DISPLAY this state and use it to render UI,
// but it must not independently change transactional facts.
//
// The backend remains authoritative.
// ============================================================

export type CheckoutStatus =
  | string;


export interface CheckoutState {
  /**
   * Unique identity of the current checkout attempt.
   */
  checkout_id: string | null;

  /**
   * Current backend-authoritative checkout status.
   *
   * Kept as string because the backend may introduce
   * additional states without requiring a frontend release.
   */
  checkout_status: CheckoutStatus | null;

  /**
   * True only after the backend successfully creates
   * an order.
   */
  order_created: boolean;

  /**
   * Authoritative database order ID.
   */
  order_id: number | null;

  /**
   * Resolved authoritative product ID.
   */
  product_id: number | null;

  /**
   * Natural-language/product name associated with checkout.
   */
  product_name: string | null;

  /**
   * Requested/purchased quantity.
   */
  quantity: number | null;

  /**
   * Selected delivery address database ID.
   */
  address_id: number | null;

  /**
   * Payment method selected/normalized by the backend.
   */
  selected_payment_method: string | null;

  /**
   * Complete backend-generated bill.
   */
  bill: Bill | null;
}


// ============================================================
// BILLING
// ============================================================
//
// Billing values come from the backend/order service.
//
// The frontend displays these values.
// It must NOT calculate them.
// ============================================================


export interface BillItem {
  /**
   * Authoritative product database ID.
   */
  product_id?: number | null;

  /**
   * Product name returned by backend.
   */
  product_name: string;

  /**
   * Quantity purchased.
   */
  quantity: number;

  /**
   * Backend-authoritative unit price.
   */
  unit_price: number;

  /**
   * Backend-calculated line total.
   */
  line_total: number;

  /**
   * Optional product metadata.
   */
  brand?: string | null;

  description?: string | null;

  image_url?: string | null;

  /**
   * Allows future backend billing fields without
   * breaking the frontend.
   */
  [key: string]: unknown;
}


// ============================================================
// Bill
// ============================================================

export interface Bill {
  /**
   * Order associated with this bill.
   */
  order_id?: number | null;

  /**
   * Purchased items.
   */
  items: BillItem[];

  /**
   * Backend-calculated subtotal.
   */
  subtotal: number;

  /**
   * Backend-calculated delivery charge.
   */
  delivery_charge: number;

  /**
   * Backend-calculated discount.
   */
  discount?: number;

  /**
   * Backend-calculated tax.
   */
  tax?: number;

  /**
   * Backend-calculated final payable amount.
   */
  total: number;

  /**
   * Currency returned by backend.
   */
  currency?: string | null;

  /**
   * Payment method associated with the order.
   */
  payment_method?: string | null;

  /**
   * Future backend billing fields.
   */
  [key: string]: unknown;
}


// ============================================================
// Purchase Summary
// ============================================================
//
// Optional simplified representation returned by tools.
// ============================================================

export interface PurchaseSummary {
  items: BillItem[];

  subtotal: number;

  delivery_charge: number;

  discount?: number;

  tax?: number;

  total: number;

  currency?: string | null;

  payment_method?: string | null;

  [key: string]: unknown;
}


// ============================================================
// Payment
// ============================================================

export interface PaymentMethod {
  /**
   * Backend-defined payment method ID.
   */
  id: string;

  /**
   * Backend/frontend display label.
   */
  label: string;

  /**
   * Optional explanation supplied by backend.
   */
  description?: string;
}


// ============================================================
// Tool Result Metadata
// ============================================================

export interface ChatMetadata {
  /**
   * Metadata type generated by backend.
   *
   * Examples:
   *
   *     address_selection
   *     payment_selection
   *     order_success
   *     tracking
   *     cancellation
   *     product_search
   */
  type?: string;


  // ----------------------------------------------------------
  // Checkout
  // ----------------------------------------------------------

  /**
   * Current authoritative checkout state.
   */
  checkout?: CheckoutState | null;

  /**
   * Unique checkout identifier.
   */
  checkout_id?: string | null;

  /**
   * Current checkout status.
   */
  checkout_status?: string | null;

  /**
   * True only when backend confirms order creation.
   */
  order_created?: boolean;


  // ----------------------------------------------------------
  // Product
  // ----------------------------------------------------------

  products?: Product[];


  // ----------------------------------------------------------
  // Missing Information
  // ----------------------------------------------------------

  missing_fields?: string[];


  // ----------------------------------------------------------
  // Order
  // ----------------------------------------------------------

  order_id?: number | null;

  status?: string | null;

  payment_status?: string | null;

  total_amount?: number | null;

  payment_method?: string | null;


  // ----------------------------------------------------------
  // Billing
  // ----------------------------------------------------------

  /**
   * Complete backend-generated bill.
   */
  bill?: Bill | null;

  /**
   * Optional simplified purchase summary.
   */
  purchase_summary?: PurchaseSummary | null;


  // ----------------------------------------------------------
  // Address
  // ----------------------------------------------------------

  addresses?: Address[];

  allow_new?: boolean;

  prefill?: string | null;


  // ----------------------------------------------------------
  // Payment
  // ----------------------------------------------------------

  /**
   * Payment methods supplied by backend.
   *
   * Never hardcode the available methods here.
   */
  methods?: PaymentMethod[];


  // ----------------------------------------------------------
  // Tracking
  // ----------------------------------------------------------

  tracking?: TrackingMetadata | null;


  // ----------------------------------------------------------
  // Support
  // ----------------------------------------------------------

  ticket_id?: number | null;


  // ----------------------------------------------------------
  // Dynamic Metadata
  // ----------------------------------------------------------

  /**
   * Allows future backend metadata without breaking
   * the frontend type system.
   */
  [key: string]: unknown;
}


// ============================================================
// Address Selection Metadata
// ============================================================

export interface AddressSelectionMetadata
  extends ChatMetadata {

  type: "address_selection";

  addresses: Address[];

  allow_new: boolean;

  prefill?: string | null;
}


// ============================================================
// Payment Selection Metadata
// ============================================================

export interface PaymentSelectionMetadata
  extends ChatMetadata {

  type: "payment_selection";

  methods: PaymentMethod[];
}


// ============================================================
// Order Success Metadata
// ============================================================

export interface OrderSuccessMetadata
  extends ChatMetadata {

  type: "order_success";

  /**
   * Checkout that produced this order.
   */
  checkout_id?: string | null;

  /**
   * Final checkout state.
   */
  checkout_status?: string | null;

  /**
   * Backend confirmation that the order exists.
   */
  order_created: true;

  /**
   * Authoritative order ID.
   */
  order_id: number;

  /**
   * Current order status.
   */
  status?: string | null;

  /**
   * Current payment status.
   */
  payment_status?: string | null;

  /**
   * Payment method associated with order.
   */
  payment_method?: string | null;

  /**
   * Backend-authoritative final amount.
   */
  total_amount?: number | null;

  /**
   * Complete backend-generated bill.
   */
  bill?: Bill | null;

  /**
   * Optional simplified summary.
   */
  purchase_summary?: PurchaseSummary | null;
}


// ============================================================
// Tracking Metadata
// ============================================================

export interface TrackingMetadata
  extends ChatMetadata {

  type: "tracking";

  /**
   * Authoritative order being tracked.
   */
  order_id: number;

  /**
   * Current backend order status.
   */
  status?: string | null;

  /**
   * Optional tracking information.
   *
   * Backend may provide:
   *
   *     rider
   *     estimated_delivery
   *     location
   *     tracking_url
   *
   * without requiring frontend schema changes.
   */
  [key: string]: unknown;
}


// ============================================================
// Cancellation Metadata
// ============================================================

export interface CancellationMetadata
  extends ChatMetadata {

  type: "cancellation";

  /**
   * Order involved in the cancellation request.
   */
  order_id: number;

  /**
   * Backend-authoritative cancellation result.
   */
  status?: string | null;

  /**
   * Optional explanation returned by backend.
   */
  reason?: string | null;
}


// ============================================================
// Chat Response
// ============================================================

export interface ChatResponse {
  /**
   * Natural-language response generated by BuyQK AI.
   */
  response: string;

  /**
   * Structured backend metadata.
   */
  metadata?: ChatMetadata | null;
}


// ============================================================
// Chat Message
// ============================================================

export type ChatRole =
  | "user"
  | "assistant";


export interface ChatMessage {
  id: string;

  role: ChatRole;

  content: string;

  /**
   * Structured backend metadata.
   */
  metadata?: ChatMetadata | null;

  created_at: string;
}


// ============================================================
// Chat State
// ============================================================

export interface ChatState {
  /**
   * Conversation messages.
   */
  messages: ChatMessage[];

  /**
   * Whether the frontend is waiting for the backend.
   */
  isLoading: boolean;

  /**
   * Frontend-visible error.
   */
  error: string | null;

  /**
   * Current conversation/session identifier.
   */
  sessionId: string;

  /**
   * Current user ID.
   */
  userId: number | null;

  /**
   * Current authoritative checkout state.
   *
   * This should be updated from backend metadata,
   * not calculated by the frontend.
   */
  checkout: CheckoutState | null;
}