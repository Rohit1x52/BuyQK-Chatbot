// ============================================================
// BuyQK AI - Shared Chat / Cart Types
// ============================================================
//
// Backend:
//
//     FastAPI
//         ↓
//     /chat
//     /cart
//
// Frontend:
//
//     chat.ts
//         ↓
//     chatStore.ts
//         ↓
//     Cart / Checkout / Chat UI
//
// Keep these types aligned with:
//
//     backend/schemas/chat_schema.py
//     backend/api/chat.py
//     backend/api/cart.py
//     backend/services/cart_service.py
//
// IMPORTANT:
//
// Backend/database/service results are authoritative for:
//
//     - product price
//     - stock
//     - product availability
//     - cart quantities
//     - cart subtotal
//     - delivery charge
//     - discount
//     - tax
//     - final total
//     - checkout ID
//     - order ID
//     - order status
//     - payment status
//     - billing
//
// The frontend only displays and stores these values.
//
// The frontend must NOT independently calculate transactional
// values or invent transaction state.
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
// CART - PHASE 3
// ============================================================
//
// The cart is now a first-class backend entity.
//
// Product
//     ↓
// CartItem
//     ↓
// Cart
//     ↓
// Checkout
//     ↓
// Order
//
// IMPORTANT:
//
// These values originate from backend/cart_service.py.
//
// The frontend must not:
//
//     - calculate line totals
//     - calculate subtotal
//     - change stock
//     - determine availability
//     - invent cart IDs
//     - silently mutate cart state
//
// ============================================================


// ============================================================
// Cart Status
// ============================================================

export type CartStatus =
  | string;


// ============================================================
// Cart Item
// ============================================================

export interface CartItem {
  /**
   * Unique database ID of this cart item.
   */
  id: number;

  /**
   * Product database ID.
   */
  product_id: number;

  /**
   * Product name returned by the backend.
   */
  product_name: string;

  /**
   * Product brand.
   */
  brand?: string | null;

  /**
   * Product description.
   */
  description?: string | null;

  /**
   * Product image URL.
   */
  image_url?: string | null;

  /**
   * Current cart quantity.
   *
   * This is authoritative backend state.
   */
  quantity: number;

  /**
   * Current backend-authoritative product price.
   */
  unit_price: number;

  /**
   * Backend-calculated quantity × unit price.
   */
  line_total: number;

  /**
   * Current backend-reported available stock.
   */
  stock?: number | null;

  /**
   * Current backend-reported product availability.
   */
  is_available?: boolean | null;

  /**
   * Allows future cart-item metadata without breaking
   * the frontend type.
   */
  [key: string]: unknown;
}


// ============================================================
// Cart Summary
// ============================================================

export interface CartSummary {
  /**
   * Number of distinct cart items.
   */
  item_count: number;

  /**
   * Total number of physical units.
   */
  total_quantity: number;

  /**
   * Backend-calculated subtotal.
   */
  subtotal: number;

  /**
   * Backend-provided currency.
   */
  currency: string;

  /**
   * Delivery charge.
   *
   * May be null until checkout/billing determines it.
   */
  delivery_charge: number | null;

  /**
   * Discount.
   *
   * May be null when no discount has been calculated.
   */
  discount: number | null;

  /**
   * Tax.
   *
   * May be null until checkout/billing determines it.
   */
  tax: number | null;

  /**
   * Current backend-calculated total.
   */
  total: number;

  /**
   * Future backend summary fields.
   */
  [key: string]: unknown;
}


// ============================================================
// Cart
// ============================================================

export interface Cart {
  /**
   * Authoritative database cart ID.
   */
  cart_id: number;

  /**
   * User who owns this cart.
   */
  user_id: number;

  /**
   * Current backend cart status.
   */
  status: CartStatus;

  /**
   * Current authoritative cart items.
   */
  items: CartItem[];

  /**
   * Backend-calculated cart summary.
   */
  summary: CartSummary;

  /**
   * Backend timestamp.
   */
  created_at?: string | null;

  /**
   * Backend timestamp.
   */
  updated_at?: string | null;

  /**
   * Future cart metadata.
   */
  [key: string]: unknown;
}


// ============================================================
// Cart API Requests
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


export interface UpdateCartProductRequest {
  user_id: number;

  quantity: number;
}


// ============================================================
// Cart API Responses
// ============================================================

export interface CartResponse {
  success: boolean;

  cart: Cart;
}


// ============================================================
// Checkout State
// ============================================================
//
// This mirrors the authoritative transaction state introduced
// during Phase 1 / Phase 2.
//
// Phase 3 adds cart_id so the frontend can associate the current
// checkout with the cart that produced it.
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
   * Cart associated with this checkout.
   */
  cart_id: number | null;

  /**
   * Resolved authoritative product ID.
   *
   * Kept for backwards compatibility with the Phase 1/2
   * single-product checkout flow.
   */
  product_id: number | null;

  /**
   * Natural-language/product name associated with checkout.
   */
  product_name: string | null;

  /**
   * Requested/purchased quantity.
   *
   * Kept for backwards compatibility with the Phase 1/2
   * single-product checkout flow.
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
   *     cart
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
  // Cart - Phase 3
  // ----------------------------------------------------------

  /**
   * Current backend-authoritative cart.
   *
   * This may be returned by the AI/tool layer after:
   *
   *     add_item
   *     remove_item
   *     update_quantity
   *     clear_cart
   *     show_cart
   *     checkout_cart
   */
  cart?: Cart | null;

  /**
   * Current cart database ID.
   */
  cart_id?: number | null;

  /**
   * Cart operation performed by the backend/tool layer.
   *
   * Examples:
   *
   *     add_item
   *     remove_item
   *     update_quantity
   *     clear_cart
   *     show_cart
   *     checkout
   */
  cart_action?: string | null;

  /**
   * True when the backend/tool layer changed cart state.
   */
  cart_updated?: boolean;


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

  /**
   * Explicit order status when returned by backend.
   *
   * `status` remains supported for backwards compatibility.
   */
  order_status?: string | null;

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

  can_track?: boolean;


  // ----------------------------------------------------------
  // Cancellation
  // ----------------------------------------------------------

  can_cancel?: boolean;


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
// Cart Metadata - Phase 3
// ============================================================

export interface CartMetadata
  extends ChatMetadata {

  type: "cart";

  /**
   * Backend-authoritative cart.
   */
  cart: Cart;

  /**
   * Operation that produced this cart response.
   */
  cart_action?: string | null;

  /**
   * Indicates that cart state changed.
   */
  cart_updated?: boolean;
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
   * Cart used for this checkout.
   */
  cart_id?: number | null;

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
//
// The store keeps a frontend representation of backend state.
//
// Backend remains authoritative.
//
// Phase 3 adds:
//
//     cart
//
// so cart state survives across conversational turns.
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

  /**
   * Current authoritative cart.
   *
   * This should be updated only from backend/API responses.
   */
  cart: Cart | null;
}