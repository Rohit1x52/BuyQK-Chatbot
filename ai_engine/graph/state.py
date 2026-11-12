from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict

from ai_engine.tools.results import ToolResult

class GraphState(TypedDict, total=False):
    message: str
    session_id: str
    user_id: int
    context: dict[str, Any]

    conversation_history: list[dict[str, Any]]
    active_task: str | None
    task_status: str | None
    execution_result: Any
    selected_product: dict[str, Any] | None
    product_search_results: list[dict[str, Any]]
    commerce_vertical: str | None
    comparison_product_ids: list[int]
    restaurant_id: int | None
    restaurant_name: str | None
    menu_id: int | None
    menu_items: list[dict[str, Any]]
    pharmacy_id: int | None
    pharmacy_name: str | None
    prescription_required: bool | None
    prescription_status: str | None
    product_specifications: dict[str, Any] | None
    product_variants: list[dict[str, Any]]
    comparison_results: list[dict[str, Any]]
    service_id: int | None
    service_name: str | None
    booking_date: str | None
    booking_start_time: str | None
    booking_end_time: str | None
    available_slots: list[dict[str, Any]]
    available_professionals: list[dict[str, Any]]
    professional_id: int | None
    professional_name: str | None
    booking_id: int | None
    booking_status: str | None
    payment_status: str | None

    merchant_id: int | None
    merchant_business_name: str | None
    merchant_category: str | None
    merchant_phone: str | None
    merchant_email: str | None
    merchant_address: str | None
    merchant_documents: list[dict[str, Any]]
    merchant_verification_status: str | None
    merchant_approval_status: str | None

    rider_id: int | None
    rider_name: str | None
    rider_phone: str | None
    rider_vehicle_type: str | None
    rider_documents: list[dict[str, Any]]
    rider_bank_details: dict[str, Any] | None
    rider_verification_status: str | None
    rider_approval_status: str | None
    intent: str
    user_goal: str | None
    detected_language: str | None
    references: dict[str, Any]
    entities: dict[str, Any]
    order_items: list[dict[str, Any]]
    missing_fields: list[str]
    current_missing_field: str | None
    follow_up_question: str | None
    awaiting_user_input: bool
    next_missing: str | None
    planner_decision: dict[str, Any]
    planner: dict[str, Any]
    planner_args: dict[str, Any]
    planned_action: str | None
    planned_tool: str | None
    planned_arguments: dict[str, Any]
    planner_confidence: float | None
    policy_result: dict[str, Any]
    decision_route: str | None
    policy_error: dict[str, Any] | None
    cart_id: int | None
    cart_status: str | None
    cart_items: list[dict[str, Any]]
    cart_summary: dict[str, Any] | None
    cart_action: str | None
    cart_result: dict[str, Any] | None
    cart_checkout_ready: bool
    checkout_id: str | None
    checkout_status: str | None
    selected_address_id: int | None
    selected_payment_method: str | None
    payment_method: str | None
    db: Any
    product_name: str | None
    product_id: int | None
    quantity: int | None
    size: str | None
    variant: str | None
    delivery_preference: str | None
    address_id: int | None
    address_action: str | None
    address_label: str | None
    address_line_2: str | None
    address_city: str | None
    address_state: str | None
    address_postal_code: str | None
    selected_payment_method_normalized: str | None
    tool_name: str | None
    tool_result: ToolResult | dict[str, Any] | None
    order_id: int | None
    order_created: bool
    order_creation_attempted: bool
    checkout_completed: bool
    awaiting_order_tracking_confirmation: bool
    cancellation_reason: str | None
    cancellation_eligibility: dict[str, Any] | None
    refund_eligibility: dict[str, Any] | None
    awaiting_cancellation_reason: bool
    transaction_error: dict[str, Any] | None
    support_issue_type: str | None
    support_description: str | None
    support_transaction_id: str | None
    support_evidence_url: str | None
    support_verification: dict[str, Any] | None
    support_resolved: bool
    support_ticket_id: int | None
    support_ticket_reference: str | None
    support_status: str | None
    support_escalation_required: bool
    billing: dict[str, Any]
    bill: dict[str, Any]
    billing_items: list[dict[str, Any]]
    subtotal: float | None
    delivery_charge: float | None
    discount: float | None
    tax: float | None
    total_amount: float | None
    currency: str | None
    billing_payment_method: str | None
    response: str
    metadata: dict[str, Any]
    detected_intents: list[str | dict[str, Any]]
    intent_entities: dict[str, dict[str, Any]]
    intent_statuses: dict[str, str]
    pending_intents: list[str]
    multi_intent: dict[str, Any]
    orchestration_directive: str | None
    task_outcome: dict[str, Any] | None
    multi_intent_queue: list[dict[str, Any]]
    active_intent: str | None
    active_intent_index: int | None
    multi_intent_status: str | None
    multi_intent_initialized: bool
    multi_intent_results: list[dict[str, Any]]
    active_intent_message: str | None
    multi_intent_error: str | None

    current_intent: str | None
    action: str | None
    decision_action: str | None
    decision: dict[str, Any] | None
    tool_args: dict[str, Any]
    task_completed: bool
    task_failed: bool
    followup_required: bool
    requires_confirmation: bool
    user_confirmed: bool

    state_version: int
    state_schema_version: int
    state_validation_errors: list[dict[str, Any]]
    state_warnings: list[dict[str, Any]]
    state_updated_at: str | None

    task_id: str | None
    task_ids: list[str]
    task_graph: list[dict[str, Any]]
    task_dependencies: dict[str, list[str]]
    task_outputs: dict[str, Any]
    task_errors: dict[str, Any]
    task_attempts: dict[str, int]
    ready_tasks: list[str]
    running_tasks: list[str]
    blocked_tasks: list[str]
    cancelled_tasks: list[str]
    task_execution_order: list[str]
    task_execution_mode: Literal["sequential", "parallel"] | None
    task_scheduler_status: str | None
    task_deadlock_detected: bool
    task_cycle_detected: bool

    execution_id: str | None
    parent_execution_id: str | None
    idempotency_key: str | None
    execution_started_at: str | None
    execution_completed_at: str | None
    execution_status: str | None
    execution_attempt: int
    execution_timeout_seconds: float | None
    execution_metadata: dict[str, Any]

    error_class: str | None
    error_code: str | None
    error_message: str | None
    error_details: dict[str, Any]
    error_retryable: bool
    recovery_action: str | None
    recovery_status: str | None
    retry_count: int
    max_retries: int
    retry_after_seconds: float | None
    fallback_used: bool
    escalation_required: bool

    interrupt_id: str | None
    interrupt_type: str | None
    interrupt_reason: str | None
    interrupt_payload: dict[str, Any]
    interrupt_status: str | None
    resume_value: Any
    resume_from_node: str | None
    checkpoint_namespace: str | None
    confirmation_type: str | None
    confirmation_payload: dict[str, Any]
    confirmation_expires_at: str | None

    tool_registry_version: str | None
    tool_execution_id: str | None
    tool_timeout_seconds: float | None
    tool_retry_count: int
    tool_idempotency_key: str | None
    tool_authorization: dict[str, Any]
    tool_validation_errors: list[dict[str, Any]]
    tool_audit: list[dict[str, Any]]

    conversation_id: str | None
    correlation_id: str | None
    trace_id: str | None
    span_id: str | None
    current_node: str | None
    node_execution_history: list[dict[str, Any]]
    graph_started_at: str | None
    graph_completed_at: str | None
    graph_error: dict[str, Any] | None
    metrics: dict[str, Any]
