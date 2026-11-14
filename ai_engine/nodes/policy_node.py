from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
import re
from ai_engine.graph.state import GraphState
SUPPORTED_TOOLS = {'search_products', 'add_to_cart', 'remove_from_cart', 'update_cart_item', 'clear_cart', 'show_cart', 'checkout_cart', 'create_order', 'track_order', 'cancel_order', 'create_support_ticket', 'list_saved_addresses', 'list_payment_methods', 'add_new_address', 'search_services', 'check_availability', 'get_available_professionals', 'create_booking', 'get_booking', 'cancel_booking', 'process_booking_payment', 'register_merchant', 'get_merchant_status', 'submit_merchant_document', 'verify_merchant', 'approve_merchant', 'reject_merchant', 'register_rider', 'get_rider_status', 'submit_rider_document', 'verify_rider', 'approve_rider', 'reject_rider'}
NON_TOOL_ACTIONS = {'ANSWER', 'ASK_CLARIFICATION', 'CONFIRM', 'END_CONVERSATION', 'START_CHECKOUT', 'MODIFY_CHECKOUT'}
CART_ACTIONS = {'ADD_CART_ITEM', 'REMOVE_CART_ITEM', 'UPDATE_CART_ITEM', 'CLEAR_CART', 'SHOW_CART', 'CHECKOUT_CART'}
CART_TOOL_MAPPING = {'ADD_CART_ITEM': 'add_to_cart', 'REMOVE_CART_ITEM': 'remove_from_cart', 'UPDATE_CART_ITEM': 'update_cart_item', 'CLEAR_CART': 'clear_cart', 'SHOW_CART': 'show_cart', 'CHECKOUT_CART': 'checkout_cart'}

def _normalize_action(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper().replace('-', '_').replace(' ', '_')
    return ACTION_ALIASES.get(normalized, normalized) or None

def _normalize_tool(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized or None

def _normalize_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold().replace('-', '_').replace(' ', '_')
    return normalized or None

def _trusted_auth_context(state: GraphState) -> dict[str, Any]:
    auth = state.get('auth_context')
    if isinstance(auth, dict):
        return auth
    principal = state.get('authenticated_principal')
    return principal if isinstance(principal, dict) else {}

def _auth_subject(auth: dict[str, Any]) -> Any:
    return auth.get('subject_id') or auth.get('user_id') or auth.get('principal_id')



def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _record_is_fresh(record: dict[str, Any]) -> bool:
    expires_at = _parse_timestamp(record.get('expires_at'))
    return expires_at is not None and expires_at > datetime.now(timezone.utc)


def _trusted_backend_record(record: Any) -> bool:
    return isinstance(record, dict) and (record.get('verified') is True or record.get('authoritative') is True) and record.get('signature_verified') is True and record.get('issuer') in {'backend', 'trusted_backend'}


def _same_value(left: Any, right: Any) -> bool:
    return _has_value(left) and _has_value(right) and str(left) == str(right)


def _confirmation_for_action(state: GraphState, action: str) -> dict[str, Any] | None:
    auth = _trusted_auth_context(state)
    candidates = (state.get('confirmation'), state.get('confirmation_result'))
    entity_id = _get_argument(state, 'cart_id') if action == 'CLEAR_CART' else _get_argument(state, 'booking_id')
    request_id = state.get('request_id') or state.get('execution_id')
    subject_id = _auth_subject(auth)
    if not all((_has_value(entity_id), _has_value(request_id), _has_value(subject_id))):
        return None
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if candidate.get('confirmed') is not True or candidate.get('signature_verified') is not True:
            continue
        if candidate.get('issuer') not in {'backend', 'trusted_confirmation_handler'}:
            continue
        if not _record_is_fresh(candidate) or candidate.get('consumed') is not False:
            continue
        if _normalize_action(candidate.get('action')) != action:
            continue
        if not _has_value(candidate.get('confirmation_id')):
            continue
        if not _same_value(candidate.get('subject_id'), subject_id):
            continue
        candidate_entity = candidate.get('entity_id') or candidate.get('cart_id') or candidate.get('booking_id')
        if not _same_value(candidate_entity, entity_id):
            continue
        candidate_request = candidate.get('request_id') or candidate.get('execution_id')
        if not _same_value(candidate_request, request_id):
            continue
        return candidate
    return None

def _cart_snapshot_status(state: GraphState) -> str | None:
    snapshot = state.get('cart_snapshot')
    if not isinstance(snapshot, dict):
        return _normalize_token(state.get('cart_snapshot_status'))
    return _normalize_token(snapshot.get('status'))

def _registry_is_valid() -> bool:
    mapped_tools = set(ACTION_TOOL_MAPPING.values())
    return mapped_tools == SUPPORTED_TOOLS and (not set(ACTION_TOOL_MAPPING) & NON_TOOL_ACTIONS) and all((isinstance(action, str) and action for action in ACTION_TOOL_MAPPING)) and all((isinstance(tool, str) and tool for tool in ACTION_TOOL_MAPPING.values()))

def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True

def _failure(reason: str, *, action: str | None=None, tool: str | None=None, retryable: bool=False) -> GraphState:
    result = {'allowed': False, 'action': action, 'tool': tool, 'reason': reason, 'retryable': retryable}
    return {'policy_result': result, 'policy_error': result, 'policy_decision': 'deny', 'policy_allowed': False, 'policy_reason': reason, 'tool_name': None, 'planner_action': action, 'planner_tool': tool, 'planner_status': 'rejected'}

def _success(action: str, tool: str | None) -> GraphState:
    result = {'allowed': True, 'action': action, 'tool': tool}
    return {'policy_result': result, 'policy_error': None, 'policy_decision': 'allow', 'policy_allowed': True, 'policy_reason': None, 'tool_name': tool, 'planner_action': action, 'planner_tool': tool, 'planner_status': 'approved'}

def _get_planned_arguments(state: GraphState) -> dict[str, Any]:
    planned_arguments = state.get('planned_arguments')
    if isinstance(planned_arguments, dict):
        return planned_arguments
    planner_args = state.get('planner_args')
    if isinstance(planner_args, dict):
        return planner_args
    arguments = state.get('arguments')
    if isinstance(arguments, dict):
        return arguments
    return {}

def _get_argument(state: GraphState, *keys: str) -> Any:
    arguments = _get_planned_arguments(state)
    for key in keys:
        if key in arguments:
            value = arguments.get(key)
            if _has_value(value):
                return value
    for key in keys:
        value = state.get(key)
        if _has_value(value):
            return value
    return None

def _get_product_reference(state: GraphState) -> Any:
    return _get_argument(state, 'product_name', 'product', 'product_reference', 'product_id')

def _validate_product_reference(state: GraphState, action: str, tool: str) -> GraphState | None:
    product_reference = _get_product_reference(state)
    if not _has_value(product_reference):
        return _failure('missing_product_reference', action=action, tool=tool, retryable=True)
    return None

def _get_quantity(state: GraphState) -> Any:
    return _get_argument(state, 'quantity')

def _validate_positive_quantity(state: GraphState, action: str, tool: str) -> GraphState | None:
    quantity = _get_quantity(state)
    if quantity is None:
        return _failure('missing_quantity', action=action, tool=tool, retryable=True)
    if isinstance(quantity, bool):
        return _failure('invalid_quantity', action=action, tool=tool, retryable=True)
    if not isinstance(quantity, int):
        return _failure('invalid_quantity', action=action, tool=tool, retryable=True)
    if quantity <= 0:
        return _failure('invalid_quantity', action=action, tool=tool, retryable=True)
    return None

def _get_cart_items(state: GraphState) -> list[Any]:
    snapshot = state.get('cart_snapshot')
    if isinstance(snapshot, dict):
        items = snapshot.get('items')
        return items if isinstance(items, list) else []
    items = state.get('cart_items')
    return items if isinstance(items, list) else []

def _cart_has_items(state: GraphState) -> bool:
    items = _get_cart_items(state)
    return bool(items)

def _transaction_already_completed(state: GraphState) -> bool:
    checkout_id = state.get('checkout_id')
    if not _has_value(checkout_id):
        return False
    records = (state.get('backend_checkout_status'), state.get('backend_transaction'), state.get('checkout_validation'))
    terminal_statuses = CHECKOUT_COMPLETED_STATUSES
    for record in records:
        if not isinstance(record, dict):
            continue
        record_checkout_id = record.get('checkout_id')
        if not _has_value(record_checkout_id) or str(record_checkout_id) != str(checkout_id):
            continue
        if record.get('verified') is not True and record.get('authoritative') is not True:
            continue
        status = record.get('status') or record.get('checkout_status') or record.get('transaction_status')
        if _normalize_token(status) in terminal_statuses:
            return True
        if record.get('order_created') is True or record.get('checkout_completed') is True:
            return True
    return False

def _checkout_has_required_state(state: GraphState) -> tuple[bool, list[str]]:
    missing: list[str] = []
    entities = _get_entities(state)
    vertical = _normalize_token(state.get('commerce_vertical') or entities.get('commerce_vertical'))
    if not _has_value(state.get('checkout_id')):
        missing.append('checkout_id')
    snapshot = state.get('cart_snapshot')
    snapshot_status = snapshot.get('status') if isinstance(snapshot, dict) else state.get('cart_snapshot_status')
    cart_items = snapshot.get('items') if isinstance(snapshot, dict) else state.get('cart_items')
    cart_ready = snapshot.get('checkout_ready') if isinstance(snapshot, dict) else state.get('cart_checkout_ready')
    direct_items = state.get('order_items') or entities.get('items')
    direct_item = None
    if not isinstance(direct_items, list) or not direct_items:
        product_reference = _get_argument(state, 'product_name', 'product_id')
        quantity = _get_argument(state, 'quantity')
        if _has_value(product_reference):
            direct_item = {'product_name': product_reference, 'quantity': quantity}
            direct_items = [direct_item]
        else:
            direct_items = []
    use_cart = isinstance(cart_items, list) and bool(cart_items)
    if use_cart:
        normalized_status = _normalize_token(snapshot_status)
        if not isinstance(snapshot, dict):
            missing.append('cart_snapshot_unavailable')
        elif normalized_status not in CART_SNAPSHOT_READY_STATUSES:
            missing.append('cart_snapshot_not_verified')
        if not _trusted_backend_record(snapshot):
            missing.append('cart_snapshot_not_authoritative')
        elif not _record_is_fresh(snapshot):
            missing.append('cart_snapshot_stale')
        auth = _trusted_auth_context(state)
        snapshot_subject = snapshot.get('subject_id') if isinstance(snapshot, dict) else None
        if not _same_value(snapshot_subject, _auth_subject(auth)):
            missing.append('cart_snapshot_identity_mismatch')
        snapshot_cart_id = snapshot.get('cart_id') if isinstance(snapshot, dict) else None
        current_cart_id = state.get('cart_id') or entities.get('cart_id')
        if _has_value(current_cart_id) and not _same_value(snapshot_cart_id, current_cart_id):
            missing.append('cart_snapshot_context_mismatch')
        if cart_ready is not True:
            missing.append('cart_checkout_ready')
        items = cart_items
    else:
        items = direct_items
        if not items:
            if snapshot_status is None and (not isinstance(cart_items, list)):
                missing.append('cart_snapshot_unavailable')
            else:
                missing.append('order_items')
    for item in items:
        if not isinstance(item, dict):
            missing.append('order_items')
            break
        quantity = item.get('quantity')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            missing.append('quantity')
            break
        reference_fields = FOOD_ITEM_REFERENCE_FIELDS if vertical in FOOD_VERTICALS else PRODUCT_ITEM_REFERENCE_FIELDS
        if not any((_has_value(item.get(key)) for key in reference_fields)):
            missing.append('order_items')
            break
    address_id = state.get('selected_address_id') or state.get('address_id') or entities.get('address_id')
    if not _has_value(address_id):
        missing.append('address_id')
    payment_method = state.get('selected_payment_method') or state.get('payment_method') or state.get('selected_payment_method_normalized') or entities.get('payment_method')
    if not _has_value(payment_method):
        missing.append('payment_method')
    return (not missing, list(dict.fromkeys(missing)))

def _validate_tool(tool: Any) -> tuple[bool, str | None]:
    if tool is None:
        return (True, None)
    if not isinstance(tool, str):
        return (False, 'invalid_tool')
    tool = tool.strip()
    if not tool:
        return (True, None)
    if tool not in SUPPORTED_TOOLS:
        return (False, 'unsupported_tool')
    return (True, tool)

def _validate_cart_action(state: GraphState, action: str, tool: str | None) -> GraphState:
    if action == 'ADD_CART_ITEM':
        product_error = _validate_product_reference(state, action, tool)
        if product_error is not None:
            return product_error
        quantity_error = _validate_positive_quantity(state, action, tool)
        return quantity_error or _success(action, tool)
    if action == 'REMOVE_CART_ITEM':
        product_error = _validate_product_reference(state, action, tool)
        return product_error or _success(action, tool)
    if action == 'UPDATE_CART_ITEM':
        product_error = _validate_product_reference(state, action, tool)
        if product_error is not None:
            return product_error
        quantity_error = _validate_positive_quantity(state, action, tool)
        return quantity_error or _success(action, tool)
    if action == 'CLEAR_CART':
        confirmation = _confirmation_for_action(state, action)
        if confirmation is None:
            return _failure('explicit_cart_clear_confirmation_required', action=action, tool=tool, retryable=True)
        return _success(action, tool)
    if action == 'SHOW_CART':
        return _success(action, tool)
    if action == 'CHECKOUT_CART':
        snapshot = state.get('cart_snapshot')
        snapshot_status = _cart_snapshot_status(state)
        if not isinstance(snapshot, dict) or snapshot_status not in CART_SNAPSHOT_READY_STATUSES:
            return _failure('cart_snapshot_unavailable_or_unverified', action=action, tool=tool, retryable=True)
        if not _trusted_backend_record(snapshot):
            return _failure('cart_snapshot_not_authoritative', action=action, tool=tool, retryable=True)
        if not _record_is_fresh(snapshot):
            return _failure('cart_snapshot_stale', action=action, tool=tool, retryable=True)
        auth = _trusted_auth_context(state)
        if not _same_value(snapshot.get('subject_id'), _auth_subject(auth)):
            return _failure('cart_snapshot_identity_mismatch', action=action, tool=tool, retryable=False)
        current_cart_id = _get_argument(state, 'cart_id')
        if _has_value(current_cart_id) and not _same_value(snapshot.get('cart_id'), current_cart_id):
            return _failure('cart_snapshot_context_mismatch', action=action, tool=tool, retryable=False)
        if snapshot.get('checkout_ready') is not True:
            return _failure('cart_not_checkout_ready', action=action, tool=tool, retryable=True)
        if not _cart_has_items(state):
            return _failure('empty_cart', action=action, tool=tool, retryable=True)
        if _transaction_already_completed(state):
            return _failure('checkout_already_completed', action=action, tool=tool, retryable=False)
        return _success(action, tool)
    return _failure('unsupported_cart_action', action=action, tool=tool, retryable=False)

def _get_entities(state: GraphState) -> dict[str, Any]:
    entities = state.get('entities', {})
    return dict(entities) if isinstance(entities, dict) else {}

def _validate_add_new_address(state: GraphState, action: str, tool: str | None) -> GraphState:
    if tool != 'add_new_address':
        return _failure('add_new_address_requires_add_new_address_tool', action=action, tool=tool, retryable=False)
    arguments = _get_planned_arguments(state)
    required = ('address_label', 'address_text', 'address_city', 'address_state', 'address_postal_code')
    missing = [field for field in required if not _has_value(arguments.get(field)) and (not _has_value(state.get(field))) and (not _has_value(_get_entities(state).get(field)))]
    if missing:
        result = {'allowed': False, 'action': action, 'tool': tool, 'reason': 'new_address_incomplete', 'missing_fields': missing, 'retryable': True}
        return {'policy_result': result, 'policy_error': result, 'policy_decision': 'deny', 'policy_allowed': False, 'policy_reason': 'new_address_incomplete', 'tool_name': None, 'missing_fields': missing, 'planner_action': action, 'planner_tool': tool, 'planner_status': 'rejected'}
    return _success(action, tool)

def _validate_create_order(state: GraphState, action: str, tool: str | None) -> GraphState:
    checkout_id = _get_argument(state, 'checkout_id')
    if not _has_value(checkout_id):
        return _failure('missing_checkout_id', action=action, tool=tool, retryable=True)
    if _transaction_already_completed(state):
        return _failure('checkout_already_completed', action=action, tool=tool, retryable=False)
    idempotency_key = _get_argument(state, 'idempotency_key')
    if not _has_value(idempotency_key):
        return _failure('missing_idempotency_key', action=action, tool=tool, retryable=True)
    validation = state.get('checkout_validation')
    if not _trusted_backend_record(validation):
        return _failure('checkout_validation_not_authoritative', action=action, tool=tool, retryable=True)
    if not _record_is_fresh(validation):
        return _failure('checkout_validation_expired', action=action, tool=tool, retryable=True)
    if not _same_value(validation.get('checkout_id'), checkout_id):
        return _failure('checkout_validation_context_mismatch', action=action, tool=tool, retryable=False)
    auth = _trusted_auth_context(state)
    subject_id = _auth_subject(auth)
    validation_subject = validation.get('subject_id') or validation.get('customer_id')
    if not _same_value(validation_subject, subject_id):
        return _failure('checkout_validation_identity_mismatch', action=action, tool=tool, retryable=False)
    request_id = state.get('request_id') or state.get('execution_id')
    validation_request = validation.get('request_id') or validation.get('execution_id')
    if not _same_value(validation_request, request_id):
        return _failure('checkout_validation_request_mismatch', action=action, tool=tool, retryable=False)
    if validation.get('ready') is not True or validation.get('allowed') is False:
        missing = validation.get('missing_fields')
        return _failure('checkout_incomplete', action=action, tool=tool, retryable=True) | {'missing_fields': missing if isinstance(missing, list) else []}
    ready, missing = _checkout_has_required_state(state)
    if not ready:
        return _failure('checkout_incomplete', action=action, tool=tool, retryable=True) | {'missing_fields': missing}
    return _success(action, tool)

def _validate_track_order(state: GraphState, action: str, tool: str | None) -> GraphState:
    order_id = _get_argument(state, 'order_id')
    order_reference = _get_argument(state, 'order_reference')
    reference_type = _normalize_token(_get_argument(state, 'order_reference_type'))
    if not (_has_value(order_id) or _has_value(order_reference) or reference_type in ORDER_REFERENCE_TYPES):
        return _failure('missing_order_reference', action=action, tool=tool, retryable=True)
    return _success(action, tool)

def _validate_cancel_order(state: GraphState, action: str, tool: str | None) -> GraphState:
    arguments = _get_planned_arguments(state)
    order_reference = _get_argument(state, 'order_id', 'order_reference')
    reference_type = _normalize_token(_get_argument(state, 'order_reference_type'))
    if not _has_value(order_reference) and reference_type not in ORDER_REFERENCE_TYPES:
        return _failure('missing_order_reference', action=action, tool=tool, retryable=True)
    eligibility = state.get('cancellation_eligibility')
    if not _trusted_backend_record(eligibility):
        return _failure('authoritative_cancellation_eligibility_required', action=action, tool=tool, retryable=True)
    if not _record_is_fresh(eligibility):
        return _failure('cancellation_eligibility_expired', action=action, tool=tool, retryable=True)
    resolved_order_id = eligibility.get('order_id')
    if not _has_value(resolved_order_id):
        return _failure('cancellation_preflight_missing_resolved_order_id', action=action, tool=tool, retryable=True)
    planned_arguments = _get_planned_arguments(state)
    requested_order_id = planned_arguments.get('order_id') if _has_value(planned_arguments.get('order_id')) else state.get('order_id')
    requested_reference = _get_argument(state, 'order_reference')
    requested_reference_type = _normalize_token(_get_argument(state, 'order_reference_type'))
    if requested_reference_type in ORDER_REFERENCE_TYPES and requested_reference_type != 'specific':
        requested_order_id = planned_arguments.get('order_id') if _has_value(planned_arguments.get('order_id')) else None
    if _has_value(requested_order_id) and str(requested_order_id) != str(resolved_order_id):
        return _failure('cancellation_eligibility_order_mismatch', action=action, tool=tool, retryable=False)
    if not _has_value(requested_order_id):
        eligibility_reference = eligibility.get('order_reference')
        eligibility_reference_type = _normalize_token(eligibility.get('order_reference_type'))
        if requested_reference_type not in ORDER_REFERENCE_TYPES:
            requested_reference_type = _normalize_token(requested_reference)
        if requested_reference_type not in ORDER_REFERENCE_TYPES:
            return _failure('cancellation_reference_not_resolved', action=action, tool=tool, retryable=True)
        if eligibility_reference_type != requested_reference_type:
            return _failure('cancellation_eligibility_reference_mismatch', action=action, tool=tool, retryable=False)
        if _has_value(requested_reference) and requested_reference_type not in ORDER_REFERENCE_TYPES:
            if str(eligibility_reference) != str(requested_reference):
                return _failure('cancellation_eligibility_reference_mismatch', action=action, tool=tool, retryable=False)
    if eligibility.get('verified') is not True and eligibility.get('authoritative') is not True:
        return _failure('unverified_cancellation_eligibility', action=action, tool=tool, retryable=True)
    auth = _trusted_auth_context(state)
    eligibility_subject = eligibility.get('customer_id') or eligibility.get('user_id')
    if not _has_value(_auth_subject(auth)) or not _has_value(eligibility_subject):
        return _failure('cancellation_eligibility_identity_missing', action=action, tool=tool, retryable=False)
    if str(_auth_subject(auth)) != str(eligibility_subject):
        return _failure('cancellation_eligibility_identity_mismatch', action=action, tool=tool, retryable=False)
    request_id = state.get('request_id') or state.get('execution_id')
    eligibility_request_id = eligibility.get('request_id') or eligibility.get('execution_id')
    if not _has_value(request_id) or not _has_value(eligibility_request_id) or str(request_id) != str(eligibility_request_id):
        return _failure('cancellation_eligibility_context_mismatch', action=action, tool=tool, retryable=False)
    if eligibility.get('eligible') is False:
        return _failure('cancellation_not_eligible', action=action, tool=tool, retryable=False)
    if eligibility.get('eligible') is not True:
        return _failure('invalid_cancellation_eligibility', action=action, tool=tool, retryable=True)
    reason = _get_argument(state, 'cancellation_reason')
    if not _has_value(reason):
        return _failure('missing_cancellation_reason', action=action, tool=tool, retryable=True)
    return _success(action, tool)

def _validate_booking_tool(state: GraphState, action: str, tool: str | None) -> GraphState:
    if action == 'SEARCH_SERVICES':
        if not any((_has_value(_get_argument(state, key)) for key in SERVICE_SEARCH_FIELDS)):
            return _failure('missing_service_search_criteria', action=action, tool=tool, retryable=True)
    elif action in {'CHECK_AVAILABILITY', 'GET_AVAILABLE_PROFESSIONALS'}:
        required_groups = (SERVICE_REFERENCE_FIELDS, BOOKING_DATE_FIELDS, BOOKING_TIME_FIELDS)
        if action == 'CHECK_AVAILABILITY':
            required_groups += (BOOKING_DURATION_FIELDS,)
        for fields in required_groups:
            if not any((_has_value(_get_argument(state, key)) for key in fields)):
                return _failure(f'missing_{fields[0]}', action=action, tool=tool, retryable=True)
        if not _has_value(_get_argument(state, 'timezone')):
            return _failure('missing_timezone', action=action, tool=tool, retryable=True)
    elif action == 'CREATE_BOOKING':
        for fields in (SERVICE_REFERENCE_FIELDS, BOOKING_DATE_FIELDS, BOOKING_TIME_FIELDS, BOOKING_ADDRESS_FIELDS, PROFESSIONAL_REFERENCE_FIELDS):
            if not any((_has_value(_get_argument(state, key)) for key in fields)):
                return _failure(f'missing_{fields[0]}', action=action, tool=tool, retryable=True)
        availability = state.get('backend_availability_result')
        if not _trusted_backend_record(availability):
            return _failure('unverified_availability_result', action=action, tool=tool, retryable=True)
        if not _record_is_fresh(availability):
            return _failure('availability_result_expired', action=action, tool=tool, retryable=True)
        if availability.get('consumed') is not False:
            return _failure('availability_token_unavailable', action=action, tool=tool, retryable=False)
        availability_token = availability.get('availability_token')
        proposed_token = _get_argument(state, 'availability_token')
        if not _has_value(availability_token) or str(proposed_token) != str(availability_token):
            return _failure('availability_token_mismatch', action=action, tool=tool, retryable=False)
        auth = _trusted_auth_context(state)
        if not _has_value(_auth_subject(auth)) or not _has_value(availability.get('subject_id')):
            return _failure('availability_subject_missing', action=action, tool=tool, retryable=False)
        if str(availability.get('subject_id')) != str(_auth_subject(auth)):
            return _failure('availability_subject_mismatch', action=action, tool=tool, retryable=False)
        context_pairs = (
            (_get_argument(state, 'service_id'), availability.get('service_id')),
            (_get_argument(state, 'booking_date', 'date'), availability.get('booking_date')),
            (_get_argument(state, 'booking_start_time', 'start_time', 'time'), availability.get('booking_start_time')),
            (_get_argument(state, 'professional_id', 'professional_reference'), availability.get('professional_id')),
            (_get_argument(state, 'duration_minutes', 'duration'), availability.get('duration_minutes')),
            (_get_argument(state, 'address_id', 'address_selection', 'address_reference'), availability.get('address_id')),
        )
        for proposed, verified in context_pairs:
            if not _same_value(proposed, verified):
                return _failure('availability_context_mismatch', action=action, tool=tool, retryable=False)
        if not _has_value(_get_argument(state, 'idempotency_key')):
            return _failure('missing_idempotency_key', action=action, tool=tool, retryable=True)
    elif action == 'GET_BOOKING':
        if not _has_value(_get_argument(state, 'booking_id', 'booking_reference')):
            return _failure('missing_booking_reference', action=action, tool=tool, retryable=True)
    elif action == 'CANCEL_BOOKING':
        if not _has_value(_get_argument(state, 'booking_id', 'booking_reference')):
            return _failure('missing_booking_reference', action=action, tool=tool, retryable=True)
        if _confirmation_for_action(state, action) is None:
            return _failure('booking_cancellation_confirmation_required', action=action, tool=tool, retryable=True)
    elif action == 'PROCESS_BOOKING_PAYMENT':
        requirements = (('booking_id', 'booking_reference'), ('payment_intent_id', 'payment_session_id'), ('idempotency_key',))
        for fields in requirements:
            if not any((_has_value(_get_argument(state, key)) for key in fields)):
                return _failure(f'missing_{fields[0]}', action=action, tool=tool, retryable=True)
        payment_context = state.get('backend_payment_intent')
        booking_context = state.get('backend_booking_status')
        if not isinstance(payment_context, dict) or payment_context.get('verified') is not True:
            return _failure('unverified_booking_payment_intent', action=action, tool=tool, retryable=True)
        if not isinstance(booking_context, dict) or booking_context.get('verified') is not True:
            return _failure('unverified_booking_status', action=action, tool=tool, retryable=True)
        proposed_booking_id = _get_argument(state, 'booking_id', 'booking_reference')
        proposed_intent_id = _get_argument(state, 'payment_intent_id', 'payment_session_id')
        if str(payment_context.get('booking_id')) != str(proposed_booking_id):
            return _failure('payment_intent_booking_mismatch', action=action, tool=tool, retryable=False)
        if str(payment_context.get('payment_intent_id') or payment_context.get('payment_session_id')) != str(proposed_intent_id):
            return _failure('payment_intent_reference_mismatch', action=action, tool=tool, retryable=False)
        if _normalize_token(payment_context.get('status')) not in PAYMENT_INTENT_READY_STATUSES:
            return _failure('booking_payment_intent_not_ready', action=action, tool=tool, retryable=False)
        if str(booking_context.get('booking_id')) != str(proposed_booking_id):
            return _failure('booking_status_reference_mismatch', action=action, tool=tool, retryable=False)
        if _normalize_token(booking_context.get('status')) not in BOOKING_PAYMENT_ELIGIBLE_STATUSES:
            return _failure('booking_not_payable', action=action, tool=tool, retryable=False)
        if _has_value(_get_argument(state, 'amount')):
            return _failure('client_supplied_payment_amount_not_allowed', action=action, tool=tool, retryable=False)
    return _success(action, tool)
MERCHANT_ONBOARDING_TOOLS = {'REGISTER_MERCHANT': 'register_merchant', 'GET_MERCHANT_STATUS': 'get_merchant_status', 'SUBMIT_MERCHANT_DOCUMENT': 'submit_merchant_document', 'VERIFY_MERCHANT': 'verify_merchant', 'APPROVE_MERCHANT': 'approve_merchant', 'REJECT_MERCHANT': 'reject_merchant'}
RIDER_ONBOARDING_TOOLS = {'REGISTER_RIDER': 'register_rider', 'GET_RIDER_STATUS': 'get_rider_status', 'SUBMIT_RIDER_DOCUMENT': 'submit_rider_document', 'VERIFY_RIDER': 'verify_rider', 'APPROVE_RIDER': 'approve_rider', 'REJECT_RIDER': 'reject_rider'}
ACTION_TOOL_MAPPING = {**CART_TOOL_MAPPING, 'SEARCH_PRODUCTS': 'search_products', 'CREATE_ORDER': 'create_order', 'TRACK_ORDER': 'track_order', 'CANCEL_ORDER': 'cancel_order', 'ADD_NEW_ADDRESS': 'add_new_address', 'REQUEST_SUPPORT': 'create_support_ticket', 'LIST_SAVED_ADDRESSES': 'list_saved_addresses', 'LIST_PAYMENT_METHODS': 'list_payment_methods', 'SEARCH_SERVICES': 'search_services', 'CHECK_AVAILABILITY': 'check_availability', 'GET_AVAILABLE_PROFESSIONALS': 'get_available_professionals', 'CREATE_BOOKING': 'create_booking', 'GET_BOOKING': 'get_booking', 'CANCEL_BOOKING': 'cancel_booking', 'PROCESS_BOOKING_PAYMENT': 'process_booking_payment', **MERCHANT_ONBOARDING_TOOLS, **RIDER_ONBOARDING_TOOLS}
ACTION_ALIASES = {'ADD_TO_CART': 'ADD_CART_ITEM', 'REMOVE_FROM_CART': 'REMOVE_CART_ITEM', 'UPDATE_CART': 'UPDATE_CART_ITEM', 'UPDATE_CART_QUANTITY': 'UPDATE_CART_ITEM', 'CHECKOUT': 'CHECKOUT_CART', 'MERCHANT_ONBOARDING': 'REGISTER_MERCHANT', 'RIDER_ONBOARDING': 'REGISTER_RIDER'}
CHECKOUT_COMPLETED_STATUSES = frozenset({'completed', 'complete', 'success', 'successful'})
CART_SNAPSHOT_READY_STATUSES = frozenset({'ready', 'loaded', 'verified'})
CART_SNAPSHOT_FAILURE_STATUSES = frozenset({'failed', 'error', 'unavailable'})
CART_SNAPSHOT_STALE_STATUSES = frozenset({'stale', 'expired'})
FOOD_VERTICALS = frozenset({'food', 'restaurant', 'grocery_food'})
FOOD_ITEM_REFERENCE_FIELDS = ('menu_item_id', 'product_id', 'product_name', 'item_id')
PRODUCT_ITEM_REFERENCE_FIELDS = ('product_id', 'product_name', 'sku', 'item_id')
ORDER_REFERENCE_TYPES = frozenset({'specific', 'latest', 'previous'})
SERVICE_SEARCH_FIELDS = ('query', 'search_query', 'service_name', 'service_category')
SERVICE_REFERENCE_FIELDS = ('service_id', 'service_name')
BOOKING_DATE_FIELDS = ('booking_date', 'date')
BOOKING_TIME_FIELDS = ('booking_start_time', 'start_time', 'time')
BOOKING_DURATION_FIELDS = ('duration_minutes', 'duration')
BOOKING_ADDRESS_FIELDS = ('address_id', 'address_selection', 'address_reference')
PROFESSIONAL_REFERENCE_FIELDS = ('professional_id', 'professional_reference')
PAYMENT_INTENT_READY_STATUSES = frozenset({'requires_confirmation', 'requires_action', 'authorized', 'ready'})
BOOKING_PAYMENT_ELIGIBLE_STATUSES = frozenset({'confirmed', 'pending_payment', 'awaiting_payment'})
SUPPORT_ISSUE_TYPES = frozenset({'wrong_product', 'payment_failure', 'delivery_delay', 'refund_status', 'human_escalation', 'general_support'})
MERCHANT_REGISTRATION_FIELDS = {'business_name': ('business_name',), 'category': ('category', 'business_category'), 'phone': ('phone', 'merchant_phone'), 'email': ('email', 'merchant_email')}
RIDER_REGISTRATION_FIELDS = {'name': ('name', 'rider_name'), 'phone': ('phone', 'rider_phone'), 'vehicle_type': ('vehicle_type',)}
ONBOARDING_ACTION_PERMISSIONS = {'APPROVE_MERCHANT': 'merchant:approve', 'REJECT_MERCHANT': 'merchant:reject', 'VERIFY_MERCHANT': 'merchant:verify', 'APPROVE_RIDER': 'rider:approve', 'REJECT_RIDER': 'rider:reject', 'VERIFY_RIDER': 'rider:verify'}
SENSITIVE_DOCUMENT_PATH_FIELDS = ('document_url', 'document_path', 'file_path', 'filesystem_path')
SENSITIVE_ONBOARDING_FIELDS = ('government_id', 'license_number', 'bank_account', 'bank_details', 'bank_account_number')
PRODUCT_SEARCH_FIELDS = ('query', 'search_query', 'product_name', 'category', 'brand')
BOOKING_ACTIONS = frozenset({'SEARCH_SERVICES', 'CHECK_AVAILABILITY', 'GET_AVAILABLE_PROFESSIONALS', 'CREATE_BOOKING', 'GET_BOOKING', 'CANCEL_BOOKING', 'PROCESS_BOOKING_PAYMENT'})
ONBOARDING_ACTIONS = frozenset(set(MERCHANT_ONBOARDING_TOOLS) | set(RIDER_ONBOARDING_TOOLS))

def _onboarding_field_present(state: GraphState, *keys: str) -> bool:
    entities = _get_entities(state)
    return any((_has_value(_get_argument(state, key)) or _has_value(entities.get(key)) for key in keys))

def _onboarding_failure(action: str, tool: str | None, reason: str, *, missing_fields: list[str] | None=None, retryable: bool=True) -> GraphState:
    result: dict[str, Any] = {'allowed': False, 'action': action, 'tool': tool, 'reason': reason, 'retryable': retryable}
    if missing_fields:
        result['missing_fields'] = missing_fields
    response: GraphState = {'policy_result': result, 'policy_error': result, 'policy_decision': 'deny', 'policy_allowed': False, 'policy_reason': reason, 'tool_name': None, 'planner_action': action, 'planner_tool': tool, 'planner_status': 'rejected'}
    if missing_fields:
        response['missing_fields'] = missing_fields
    return response

def _validate_onboarding_action(state: GraphState, action: str, tool: str | None) -> GraphState:
    if action in MERCHANT_ONBOARDING_TOOLS:
        entity_id_key = 'merchant_id'
        entity_name = 'merchant'
        registration_fields = MERCHANT_REGISTRATION_FIELDS
        document_action = 'SUBMIT_MERCHANT_DOCUMENT'
    elif action in RIDER_ONBOARDING_TOOLS:
        entity_id_key = 'rider_id'
        entity_name = 'rider'
        registration_fields = RIDER_REGISTRATION_FIELDS
        document_action = 'SUBMIT_RIDER_DOCUMENT'
    else:
        return _failure('unsupported_onboarding_action', action=action, tool=tool, retryable=False)
    if action in {f'APPROVE_{entity_name.upper()}', f'REJECT_{entity_name.upper()}', f'VERIFY_{entity_name.upper()}'}:
        auth = _trusted_auth_context(state)
        required_permission = ONBOARDING_ACTION_PERMISSIONS.get(action)
        permissions = auth.get('permissions')
        roles = auth.get('roles')
        if not _has_value(_auth_subject(auth)) or not _has_value(auth.get('audit_id')):
            return _failure('trusted_actor_and_audit_context_required', action=action, tool=tool, retryable=False)
        if not isinstance(permissions, (list, tuple, set)) or required_permission not in permissions:
            return _failure('onboarding_permission_denied', action=action, tool=tool, retryable=False)
        if not isinstance(roles, (list, tuple, set)) or not roles:
            return _failure('onboarding_role_context_missing', action=action, tool=tool, retryable=False)
    if action in {f'REGISTER_{entity_name.upper()}'}:
        if any((_has_value(_get_argument(state, key)) for key in SENSITIVE_ONBOARDING_FIELDS)):
            return _failure('sensitive_onboarding_data_must_use_secure_profile', action=action, tool=tool, retryable=False)
        missing = [field for field, aliases in registration_fields.items() if not any((_has_value(_get_argument(state, key)) for key in aliases))]
        secure_reference = _get_argument(state, 'onboarding_profile_token', 'application_reference')
        if not _has_value(secure_reference):
            missing.append('onboarding_profile_token')
        if missing:
            return _onboarding_failure(action, tool, f'{entity_name}_registration_incomplete', missing_fields=missing, retryable=True)
        email_value = _get_argument(state, 'email', 'merchant_email')
        phone_value = _get_argument(state, 'phone', 'merchant_phone', 'rider_phone')
        if email_value is not None and (not isinstance(email_value, str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email_value.strip())):
            return _failure('invalid_registration_email', action=action, tool=tool, retryable=True)
        if phone_value is not None:
            digits = re.sub(r'\D', '', str(phone_value))
            if len(digits) < 7 or len(digits) > 15:
                return _failure('invalid_registration_phone', action=action, tool=tool, retryable=True)
        category = _get_argument(state, 'category', 'business_category')
        if action == 'REGISTER_MERCHANT' and (not isinstance(category, str) or not category.strip()):
            return _failure('invalid_merchant_category', action=action, tool=tool, retryable=True)
        vehicle_type = _get_argument(state, 'vehicle_type')
        if action == 'REGISTER_RIDER' and (not isinstance(vehicle_type, str) or not vehicle_type.strip()):
            return _failure('invalid_rider_vehicle_type', action=action, tool=tool, retryable=True)
        return _success(action, tool)
    if not _onboarding_field_present(state, entity_id_key):
        return _onboarding_failure(action, tool, f'missing_{entity_id_key}', missing_fields=[entity_id_key], retryable=True)
    if action == document_action:
        missing = []
        if not _onboarding_field_present(state, 'document_type'):
            missing.append('document_type')
        if not _onboarding_field_present(state, 'document_upload_id', 'document_reference_token'):
            missing.append('document_upload_id')
        if any((_has_value(_get_argument(state, key)) for key in SENSITIVE_DOCUMENT_PATH_FIELDS)):
            return _failure('raw_document_location_not_allowed', action=action, tool=tool, retryable=False)
        if missing:
            return _onboarding_failure(action, tool, 'onboarding_document_details_incomplete', missing_fields=missing, retryable=True)
    return _success(action, tool)

def _validate_generic_tool(state: GraphState, action: str, tool: str | None) -> GraphState:
    return _success(action, tool)

def _validate_request_support(state: GraphState, action: str, tool: str | None) -> GraphState:
    issue_type = _normalize_token(_get_argument(state, 'support_issue_type', 'issue_type'))
    if issue_type not in SUPPORT_ISSUE_TYPES:
        return _failure('invalid_support_issue_type', action=action, tool=tool, retryable=True)
    auth = _trusted_auth_context(state)
    if not _has_value(_auth_subject(auth)):
        return _failure('missing_authenticated_subject', action=action, tool=tool, retryable=False)
    return _success(action, tool)

def _policy_node_for_state(state: GraphState) -> GraphState:
    if not _registry_is_valid():
        return _failure('invalid_action_tool_registry', retryable=False)
    planner_decision = state.get('planner_decision')
    if not isinstance(planner_decision, dict):
        planner = state.get('planner')
        if isinstance(planner, dict):
            planner_decision = planner
        elif _has_value(state.get('planner_action')):
            planner_decision = {'action': state.get('planner_action'), 'tool': state.get('planner_tool'), 'arguments': state.get('planner_args', {})}
        elif _has_value(state.get('action')):
            planner_decision = {'action': state.get('action'), 'tool': state.get('tool') or state.get('tool_name'), 'arguments': state.get('arguments', {})}
        else:
            return _failure('missing_planner_decision')
    action = _normalize_action(planner_decision.get('action'))
    if action is None:
        return _failure('invalid_planner_action')
    tool = _normalize_tool(planner_decision.get('tool') or planner_decision.get('tool_name'))
    if action in NON_TOOL_ACTIONS:
        if tool is not None:
            return _failure('tool_not_allowed_for_non_tool_action', action=action, tool=tool)
    else:
        expected_tool = ACTION_TOOL_MAPPING.get(action)
        if expected_tool is None:
            return _failure('unregistered_executable_action', action=action, tool=tool)
        if tool is None:
            return _failure('tool_required_for_action', action=action, tool=None)
        if tool != expected_tool:
            return _failure('action_tool_mismatch', action=action, tool=tool)
        if tool not in SUPPORTED_TOOLS:
            return _failure('unsupported_tool', action=action, tool=tool)
    planned_arguments = planner_decision.get('arguments', {})
    if planned_arguments is None:
        planned_arguments = {}
    if not isinstance(planned_arguments, dict):
        return _failure('invalid_planner_arguments', action=action, tool=tool, retryable=True)
    scoped_state = dict(state)
    scoped_state['planned_arguments'] = dict(planned_arguments)
    scoped_state['planner_decision'] = planner_decision
    if action in NON_TOOL_ACTIONS:
        return _success(action, None)
    if action in CART_ACTIONS:
        return _validate_cart_action(scoped_state, action, tool)
    if action == 'SEARCH_PRODUCTS':
        if not any((_has_value(_get_argument(scoped_state, key)) for key in PRODUCT_SEARCH_FIELDS)):
            return _failure('missing_product_search_criteria', action=action, tool=tool, retryable=True)
        return _validate_generic_tool(scoped_state, action, tool)
    if action == 'ADD_NEW_ADDRESS':
        return _validate_add_new_address(scoped_state, action, tool)
    if action == 'REQUEST_SUPPORT':
        return _validate_request_support(scoped_state, action, tool)
    if action == 'CREATE_ORDER':
        return _validate_create_order(scoped_state, action, tool)
    if action == 'TRACK_ORDER':
        return _validate_track_order(scoped_state, action, tool)
    if action == 'CANCEL_ORDER':
        return _validate_cancel_order(scoped_state, action, tool)
    if action in BOOKING_ACTIONS:
        return _validate_booking_tool(scoped_state, action, tool)
    if action in ONBOARDING_ACTIONS:
        return _validate_onboarding_action(scoped_state, action, tool)
    if action == 'LIST_SAVED_ADDRESSES':
        auth = _trusted_auth_context(scoped_state)
        if not _has_value(_auth_subject(auth)):
            return _failure('missing_authenticated_subject', action=action, tool=tool, retryable=False)
        return _success(action, tool)
    if action == 'LIST_PAYMENT_METHODS':
        auth = _trusted_auth_context(scoped_state)
        if not _has_value(_auth_subject(auth)):
            return _failure('missing_authenticated_subject', action=action, tool=tool, retryable=False)
        if not _has_value(_get_argument(scoped_state, 'checkout_id')):
            return _failure('missing_checkout_id', action=action, tool=tool, retryable=True)
        return _success(action, tool)
    if action == 'GET_MERCHANT_STATUS' or action == 'GET_RIDER_STATUS':
        entity_key = 'merchant_id' if action == 'GET_MERCHANT_STATUS' else 'rider_id'
        if not _onboarding_field_present(scoped_state, entity_key):
            return _failure(f'missing_{entity_key}', action=action, tool=tool, retryable=True)
        return _success(action, tool)
    return _failure('registered_action_has_no_policy_validator', action=action, tool=tool, retryable=False)

def _active_intent_from_state(state: GraphState) -> Any:
    multi_intent = state.get('multi_intent')
    if isinstance(multi_intent, dict) and _has_value(multi_intent.get('active_intent')):
        return multi_intent.get('active_intent')
    for key in ('active_intent', 'current_intent'):
        value = state.get(key)
        if _has_value(value):
            return value
    return None

def _intent_identity(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip().casefold() or None
    if isinstance(value, dict):
        for key in ('active_intent_id', 'intent_id', 'id', 'name', 'intent', 'type'):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip().casefold()
    return None

def _multi_intent_is_present(state: GraphState) -> bool:
    multi_intent = state.get('multi_intent')
    if isinstance(multi_intent, dict) and multi_intent:
        return True
    for key in ('detected_intents', 'pending_intents'):
        value = state.get(key)
        if isinstance(value, (list, tuple)) and len(value) > 1:
            return True
    intent_entities = state.get('intent_entities')
    if isinstance(intent_entities, dict) and len(intent_entities) > 1:
        return True
    return False

def _decision_intent(planner_decision: Any, state: GraphState) -> Any:
    if isinstance(planner_decision, dict):
        for key in ('active_intent_id', 'active_intent', 'intent_id', 'intent', 'source_intent'):
            value = planner_decision.get(key)
            if _has_value(value):
                return value
    return None

def _phase13_rejection(reason: str, *, active_intent: Any=None, proposed_intent: Any=None, action: str | None=None, tool: str | None=None) -> GraphState:
    result = {'allowed': False, 'action': action, 'tool': tool, 'reason': reason, 'retryable': False}
    if _has_value(active_intent):
        result['active_intent'] = active_intent
        result['active_intent_id'] = _intent_identity(active_intent)
    if _has_value(proposed_intent):
        result['proposed_intent'] = proposed_intent
    return {'policy_result': result, 'policy_error': result, 'policy_decision': 'deny', 'policy_allowed': False, 'policy_reason': reason, 'tool_name': None, 'planner_status': 'rejected', 'policy_active_intent': active_intent}

def policy_node(state: GraphState) -> GraphState:
    multi_intent = _multi_intent_is_present(state)
    active_intent = _active_intent_from_state(state)
    if multi_intent and active_intent is None:
        return _phase13_rejection('missing_active_intent')
    planner_decision = state.get('planner_decision')
    if not isinstance(planner_decision, dict):
        planner = state.get('planner')
        if isinstance(planner, dict):
            planner_decision = planner
        elif _has_value(state.get('planner_action')):
            planner_decision = {'action': state.get('planner_action'), 'tool': state.get('planner_tool'), 'arguments': state.get('planner_args', {}), 'active_intent_id': state.get('active_intent_id'), 'task_id': state.get('task_id'), 'execution_id': state.get('execution_id'), 'planner_decision_id': state.get('planner_decision_id')}
        elif _has_value(state.get('action')):
            planner_decision = {'action': state.get('action'), 'tool': state.get('tool') or state.get('tool_name'), 'arguments': state.get('arguments', {}), 'active_intent_id': state.get('active_intent_id'), 'task_id': state.get('task_id'), 'execution_id': state.get('execution_id'), 'planner_decision_id': state.get('planner_decision_id')}
        else:
            planner_decision = None
    if multi_intent:
        active_identity = _intent_identity(active_intent)
        if active_identity is None:
            return _phase13_rejection('missing_active_intent_id', active_intent=active_intent)
        multi = state.get('multi_intent')
        multi = multi if isinstance(multi, dict) else {}
        trusted_context = {'active_intent_id': state.get('active_intent_id') or multi.get('active_intent_id') or active_identity, 'task_id': state.get('task_id') or multi.get('task_id'), 'execution_id': state.get('execution_id') or multi.get('execution_id'), 'planner_decision_id': state.get('planner_decision_id') or multi.get('planner_decision_id')}
        if not isinstance(planner_decision, dict):
            return _phase13_rejection('missing_planner_decision', active_intent=active_intent)
        proposal_context = {'active_intent_id': planner_decision.get('active_intent_id'), 'task_id': planner_decision.get('task_id'), 'execution_id': planner_decision.get('execution_id'), 'planner_decision_id': planner_decision.get('planner_decision_id') or planner_decision.get('decision_id')}
        for key, trusted_value in trusted_context.items():
            proposed_value = proposal_context.get(key)
            if not _has_value(trusted_value):
                return _phase13_rejection(f'missing_coordinator_{key}', active_intent=active_intent)
            if not _has_value(proposed_value):
                return _phase13_rejection(f'missing_planner_{key}', active_intent=active_intent)
            if str(proposed_value) != str(trusted_value):
                return _phase13_rejection(f'planner_{key}_mismatch', active_intent=active_intent)
        proposed_intent = _decision_intent(planner_decision, state)
        if _intent_identity(proposed_intent) != active_identity:
            return _phase13_rejection('planner_intent_mismatch', active_intent=active_intent, proposed_intent=proposed_intent)
    scoped_state = dict(state)
    if active_intent is not None:
        active_identity = _intent_identity(active_intent)
        scoped_state['active_intent'] = active_intent
        scoped_state['active_intent_metadata'] = active_intent if isinstance(active_intent, dict) else {}
        scoped_state['intent'] = active_identity
        intent_entities = state.get('intent_entities')
        if isinstance(intent_entities, dict) and active_identity is not None:
            matching_bucket = next((bucket for key, bucket in intent_entities.items() if _intent_identity(key) == active_identity), None)
            if isinstance(matching_bucket, dict):
                scoped_state['entities'] = dict(matching_bucket)
    result = dict(_policy_node_for_state(scoped_state))
    if active_intent is not None:
        active_identity = _intent_identity(active_intent)
        result['policy_active_intent'] = active_intent
        policy_result = result.get('policy_result')
        if isinstance(policy_result, dict):
            policy_result = dict(policy_result)
            policy_result['active_intent'] = active_intent
            policy_result['active_intent_id'] = active_identity
            if multi_intent:
                multi = state.get('multi_intent')
                multi = multi if isinstance(multi, dict) else {}
                policy_result.update({'task_id': state.get('task_id') or multi.get('task_id'), 'execution_id': state.get('execution_id') or multi.get('execution_id'), 'planner_decision_id': state.get('planner_decision_id') or multi.get('planner_decision_id')})
            result['policy_result'] = policy_result
            if isinstance(result.get('policy_error'), dict):
                result['policy_error'] = dict(policy_result)
    return result
__all__ = ['policy_node', 'SUPPORTED_TOOLS', 'NON_TOOL_ACTIONS', 'CART_TOOL_MAPPING', 'MERCHANT_ONBOARDING_TOOLS', 'RIDER_ONBOARDING_TOOLS', 'ACTION_TOOL_MAPPING', 'ACTION_ALIASES', '_normalize_action', '_normalize_tool']
