from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState
from ai_engine.nodes.policy_node import ACTION_TOOL_MAPPING, NON_TOOL_ACTIONS, SUPPORTED_TOOLS

ROUTE_TOOL = "tool"
ROUTE_RESPONSE = "response"


def _normalize_action(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
    return normalized or None


def _normalize_tool(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _intent_identity(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip().casefold() or None
    if isinstance(value, dict):
        for key in ("intent_id", "id", "name", "intent", "type"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip().casefold()
    return None


def _active_intent_from_state(state: GraphState) -> Any:
    multi_intent = _as_mapping(state.get("multi_intent"))
    for candidate in (
        state.get("active_intent"),
        state.get("current_intent"),
        multi_intent.get("active_intent"),
    ):
        if _has_value(candidate):
            return candidate
    return None


def _is_multi_intent_state(state: GraphState) -> bool:
    multi_intent = state.get("multi_intent")
    if isinstance(multi_intent, dict) and multi_intent:
        return True

    for key in ("detected_intents", "pending_intents"):
        value = state.get(key)
        if isinstance(value, (list, tuple)) and len(value) > 1:
            return True

    intent_entities = state.get("intent_entities")
    if isinstance(intent_entities, dict) and len(intent_entities) > 1:
        return True

    return False


def _state_for_active_intent(state: GraphState, active_intent: Any) -> GraphState:
    scoped = dict(state)
    active_identity = _intent_identity(active_intent)
    scoped["intent"] = active_identity
    scoped["active_intent_metadata"] = active_intent if isinstance(active_intent, dict) else None
    intent_entities = state.get("intent_entities")

    if isinstance(intent_entities, dict) and active_identity is not None:
        matching_bucket = None
        matching_key_found = False

        for key, bucket in intent_entities.items():
            if _intent_identity(key) == active_identity:
                matching_key_found = True
                matching_bucket = bucket
                break

        if matching_key_found:
            scoped["entities"] = dict(matching_bucket) if isinstance(matching_bucket, dict) else {}

    return scoped


def _decision_result(
    *,
    route: str,
    allowed: bool,
    action: str | None,
    tool: str | None,
    reason: Any = None,
    **extra: Any,
) -> GraphState:
    policy_error = None
    if not allowed:
        policy_error = {
            "allowed": False,
            "action": action,
            "tool": tool,
            "reason": reason,
        }

    decision = {
        "route": route,
        "allowed": allowed,
        "action": action,
        "tool": tool,
        "reason": reason,
    }
    decision.update(extra.pop("decision_metadata", {}))

    result: dict[str, Any] = {
        "decision": decision,
        "decision_route": route,
        "decision_action": action,
        "tool_name": tool,
        "policy_error": policy_error,
    }
    result.update(extra)
    return result


def _reject(
    reason: str,
    *,
    action: str | None = None,
    tool: str | None = None,
    active_intent: Any = None,
    **extra: Any,
) -> GraphState:
    result = _decision_result(
        route=ROUTE_RESPONSE,
        allowed=False,
        action=action,
        tool=None,
        reason=reason,
        active_intent=active_intent,
        orchestrator_action="stop_on_policy_rejection",
        advance_intent_queue=False,
        **extra,
    )
    return result


def _policy_contract(state: GraphState) -> tuple[dict[str, Any] | None, str | None]:
    policy = state.get("policy_result")
    if not isinstance(policy, dict):
        policy = state.get("policy")

    if not isinstance(policy, dict):
        return None, "missing_policy_result"

    allowed = policy.get("allowed")
    if not isinstance(allowed, bool):
        return None, "invalid_policy_authorization"

    policy_decision = state.get("policy_decision")
    if isinstance(policy_decision, str):
        normalized_decision = policy_decision.strip().casefold()
        expected_decision = "allow" if allowed else "deny"
        if normalized_decision and normalized_decision != expected_decision:
            return None, "policy_contract_mismatch"

    policy_allowed = state.get("policy_allowed")
    if policy_allowed is not None:
        if not isinstance(policy_allowed, bool) or policy_allowed is not allowed:
            return None, "policy_contract_mismatch"

    return policy, None


def _transaction_already_completed(state: GraphState) -> bool:
    checkout_id = state.get("checkout_id")
    if not _has_value(checkout_id):
        return False

    records = (
        state.get("backend_checkout_status"),
        state.get("backend_transaction"),
    )
    for record in records:
        if not isinstance(record, dict):
            continue
        record_checkout_id = record.get("checkout_id")
        if not _has_value(record_checkout_id) or str(record_checkout_id) != str(checkout_id):
            continue
        status = record.get("status") or record.get("checkout_status") or record.get("transaction_status")
        if isinstance(status, str) and status.strip().casefold() in {"completed", "complete", "success", "successful"}:
            return True
        if record.get("order_created") is True or record.get("checkout_completed") is True:
            return True
    return False


def _validate_policy_provenance(
    state: GraphState,
    policy: dict[str, Any],
    active_intent: Any,
    multi_intent: bool,
) -> str | None:
    if not multi_intent:
        return None

    active_identity = _intent_identity(active_intent)
    if active_identity is None:
        return "missing_active_intent"

    policy_intent = (
        policy.get("active_intent")
        or state.get("policy_active_intent")
    )
    policy_identity = _intent_identity(policy_intent)

    if policy_identity is None:
        return "missing_policy_intent_provenance"

    if policy_identity != active_identity:
        return "active_intent_policy_mismatch"

    for key in ("task_id", "execution_id"):
        policy_value = policy.get(key)
        state_value = state.get(key)
        if _has_value(policy_value) and _has_value(state_value):
            if str(policy_value) != str(state_value):
                return f"policy_{key}_mismatch"

    planner = _as_mapping(state.get("planner_decision"))
    planner_intent = None
    for key in ("active_intent", "intent", "intent_id", "source_intent"):
        if _has_value(planner.get(key)):
            planner_intent = planner.get(key)
            break

    planner_identity = _intent_identity(planner_intent)
    if planner_identity is not None and planner_identity != active_identity:
        return "planner_intent_mismatch"

    return None


def _orchestrator_directive(
    state: GraphState,
    result: GraphState,
    active_intent: Any,
) -> dict[str, Any]:
    decision = _as_mapping(result.get("decision"))
    action = _normalize_action(decision.get("action"))
    route = decision.get("route")
    allowed = decision.get("allowed") is True
    reason = decision.get("reason")

    retryable = False
    policy = state.get("policy_result")
    if not isinstance(policy, dict):
        policy = state.get("policy")
    if isinstance(policy, dict):
        retryable = policy.get("retryable") is True

    if action == "ASK_CLARIFICATION" or retryable:
        directive = "wait_for_input"
    elif route == ROUTE_TOOL and allowed:
        directive = "execute_active_intent"
    elif not allowed:
        directive = "stop_on_policy_rejection"
    elif action == "END_CONVERSATION":
        directive = "finish_conversation"
    else:
        directive = "continue_current_intent"

    statuses = state.get("intent_statuses")
    if not isinstance(statuses, dict):
        statuses = _as_mapping(state.get("multi_intent")).get("intent_statuses")
    statuses = dict(statuses) if isinstance(statuses, dict) else {}

    pending = state.get("pending_intents")
    if not isinstance(pending, list):
        pending = _as_mapping(state.get("multi_intent")).get("pending_intents")
    pending = [
        item for item in pending
        if isinstance(item, str) and item.strip()
    ] if isinstance(pending, list) else []

    metadata: dict[str, Any] = {
        "orchestrator_action": directive,
        "active_intent": active_intent,
        "pending_intents": pending,
        "intent_statuses": statuses,
        "advance_intent_queue": False,
    }

    if statuses:
        terminal_values = {"completed", "complete", "done", "failed", "skipped", "cancelled"}
        all_terminal = all(
            (
                isinstance(status, str)
                and status.strip().casefold() in terminal_values
            )
            or (
                isinstance(status, dict)
                and str(status.get("status", "")).strip().casefold() in terminal_values
            )
            for status in statuses.values()
        )
        if all_terminal and not pending and directive not in {"wait_for_input", "execute_active_intent"}:
            metadata["orchestrator_action"] = "finish_multi_intent"

    return metadata


def _checkout_discovery_decision(
    state: GraphState,
    policy: dict[str, Any],
    action: str | None,
) -> GraphState | None:
    entities = _as_mapping(state.get("entities"))
    address_action = entities.get("address_action")
    if not isinstance(address_action, str):
        address_action = state.get("address_action")
    address_action = address_action.strip().casefold() if isinstance(address_action, str) else ""

    if action in {"START_CHECKOUT", "MODIFY_CHECKOUT"} and policy.get("allowed") is True:
        selected_address = (
            state.get("selected_address_id")
            or state.get("address_id")
            or entities.get("address_id")
        )
        if not _has_value(selected_address) and address_action != "add":
            if "list_saved_addresses" not in SUPPORTED_TOOLS or ACTION_TOOL_MAPPING.get("LIST_SAVED_ADDRESSES") != "list_saved_addresses":
                return _reject(
                    "address_discovery_tool_not_supported",
                    action=action,
                )
            return _decision_result(
                route=ROUTE_TOOL,
                allowed=True,
                action="LIST_SAVED_ADDRESSES",
                tool="list_saved_addresses",
                reason="load_saved_addresses_for_checkout",
                checkout_discovery="address",
                source_action=action,
            )

    if action == "CREATE_ORDER" and policy.get("allowed") is False:
        missing_fields = policy.get("missing_fields")
        if not isinstance(missing_fields, (list, tuple, set)):
            missing_fields = state.get("missing_fields")
        missing = {
            str(value).strip().casefold()
            for value in missing_fields
            if isinstance(value, str) and value.strip()
        } if isinstance(missing_fields, (list, tuple, set)) else set()
        reason = str(policy.get("reason") or "").strip().casefold()
        checkout_id = state.get("checkout_id")
        selected_address = (
            state.get("selected_address_id")
            or state.get("address_id")
            or entities.get("address_id")
        )
        if (
            reason == "checkout_incomplete"
            and missing == {"payment_method"}
            and _has_value(checkout_id)
            and _has_value(selected_address)
            and "list_payment_methods" in SUPPORTED_TOOLS
            and ACTION_TOOL_MAPPING.get("LIST_PAYMENT_METHODS") == "list_payment_methods"
        ):
            return _decision_result(
                route=ROUTE_TOOL,
                allowed=True,
                action="LIST_PAYMENT_METHODS",
                tool="list_payment_methods",
                reason="load_payment_methods_for_checkout",
                checkout_discovery="payment",
                source_action=action,
            )

    return None


def _decision_node_for_current_task(state: GraphState) -> GraphState:
    policy, contract_error = _policy_contract(state)
    if contract_error is not None or policy is None:
        return _reject(contract_error or "invalid_policy_result")

    action = _normalize_action(policy.get("action"))
    tool = _normalize_tool(policy.get("tool") or policy.get("tool_name"))
    reason = policy.get("reason")

    discovery = _checkout_discovery_decision(state, policy, action)
    if discovery is not None:
        return discovery

    if policy.get("allowed") is not True:
        return _decision_result(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=action,
            tool=None,
            reason=reason or "policy_rejected",
        )

    if action is None:
        return _reject("missing_policy_action")

    if action in NON_TOOL_ACTIONS:
        if tool is not None:
            return _reject(
                "tool_not_allowed_for_toolless_action",
                action=action,
                tool=tool,
            )
        return _decision_result(
            route=ROUTE_RESPONSE,
            allowed=True,
            action=action,
            tool=None,
            reason=reason,
        )

    if tool is None:
        return _reject(
            "tool_required_for_action",
            action=action,
        )

    if tool not in SUPPORTED_TOOLS:
        return _reject(
            "unsupported_tool",
            action=action,
            tool=tool,
        )

    expected_tool = ACTION_TOOL_MAPPING.get(action)
    if expected_tool is None:
        return _reject(
            "action_has_no_canonical_tool_mapping",
            action=action,
            tool=tool,
        )

    if tool != _normalize_tool(expected_tool):
        return _reject(
            "action_tool_mapping_mismatch",
            action=action,
            tool=tool,
            expected_tool=expected_tool,
        )

    if action == "CREATE_ORDER" and _transaction_already_completed(state):
        return _reject(
            "checkout_already_completed",
            action=action,
            tool=tool,
        )

    return _decision_result(
        route=ROUTE_TOOL,
        allowed=True,
        action=action,
        tool=tool,
        reason=reason,
    )


def decision_node(state: GraphState) -> GraphState:
    multi_intent = _is_multi_intent_state(state)
    active_intent = _active_intent_from_state(state)

    if multi_intent and active_intent is None:
        return _reject("missing_active_intent")

    scoped_state = (
        _state_for_active_intent(state, active_intent)
        if active_intent is not None
        else dict(state)
    )

    policy, contract_error = _policy_contract(scoped_state)
    if contract_error is not None or policy is None:
        result = _reject(
            contract_error or "invalid_policy_result",
            active_intent=active_intent,
        )
        result.update(
            _orchestrator_directive(scoped_state, result, active_intent)
        )
        return result

    provenance_error = _validate_policy_provenance(
        scoped_state,
        policy,
        active_intent,
        multi_intent,
    )
    if provenance_error is not None:
        result = _reject(
            provenance_error,
            action=_normalize_action(policy.get("action")),
            active_intent=active_intent,
        )
        result.update(
            _orchestrator_directive(scoped_state, result, active_intent)
        )
        return result

    result = _decision_node_for_current_task(scoped_state)
    result.update(
        _orchestrator_directive(scoped_state, result, active_intent)
    )
    return result


__all__ = [
    "decision_node",
    "SUPPORTED_TOOLS",
    "ROUTE_TOOL",
    "ROUTE_RESPONSE",
]
