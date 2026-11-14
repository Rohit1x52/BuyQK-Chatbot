from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import decimal
import enum
import json
import logging
import math
import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_engine.graph.state import GraphState


logger = logging.getLogger(__name__)


class ContextBuildError(RuntimeError):
    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.errors = errors or []


class ContextSection(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)


class UserContext(ContextSection):
    user_id: Any = None
    session_id: Any = None
    message: Any = ""


class ConversationContext(ContextSection):
    history: list[Any] = Field(default_factory=list)


class TaskMemoryContext(ContextSection):
    active_task: Any = None
    task_status: Any = None
    missing_fields: list[Any] = Field(default_factory=list)
    selected_product: dict[str, Any] = Field(default_factory=dict)
    execution_result: Any = None


class UnderstandingContext(ContextSection):
    intent: Any = None
    user_goal: Any = None
    detected_language: Any = None
    entities: dict[str, Any] = Field(default_factory=dict)
    references: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[Any] = Field(default_factory=list)
    active_task: Any = None
    task_status: Any = None
    selected_product: dict[str, Any] = Field(default_factory=dict)
    execution_result: Any = None


class CheckoutContext(ContextSection):
    checkout_id: Any = None
    checkout_status: Any = None
    product_id: Any = None
    product_name: Any = None
    quantity: Any = None
    address_id: Any = None
    selected_address_id: Any = None
    selected_payment_method: Any = None
    payment_method: Any = None
    order_created: Any = False
    order_creation_attempted: Any = False
    checkout_completed: Any = False
    order_id: Any = None
    awaiting_order_tracking_confirmation: Any = False


class CartContext(ContextSection):
    cart_id: Any = None
    cart_status: Any = None
    cart_items: list[Any] = Field(default_factory=list)
    cart_summary: dict[str, Any] = Field(default_factory=dict)
    cart_action: Any = None
    cart_result: dict[str, Any] = Field(default_factory=dict)
    cart_checkout_ready: Any = False


class BackendContext(ContextSection):
    tool_name: Any = None
    tool_result: Any = None
    execution_result: Any = None
    transaction_error: dict[str, Any] = Field(default_factory=dict)
    policy_result: dict[str, Any] = Field(default_factory=dict)
    policy_error: dict[str, Any] = Field(default_factory=dict)


class BillingContext(ContextSection):
    billing: dict[str, Any] = Field(default_factory=dict)
    bill: dict[str, Any] = Field(default_factory=dict)
    billing_items: list[Any] = Field(default_factory=list)
    subtotal: Any = None
    delivery_charge: Any = None
    discount: Any = None
    tax: Any = None
    total_amount: Any = None
    currency: Any = None
    billing_payment_method: Any = None


class ContextEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    user: UserContext
    conversation: ConversationContext
    task_memory: TaskMemoryContext
    understanding: UnderstandingContext
    checkout: CheckoutContext
    cart: CartContext
    backend: BackendContext
    billing: BillingContext
    provenance: dict[str, Any] = Field(default_factory=dict)
    context_metadata: dict[str, Any] = Field(default_factory=dict)


_DEFAULT_CONFIG = {
    "schema_version": "1.0.0",
    "max_context_tokens": 12000,
    "max_history_messages": 30,
    "max_serialization_depth": 20,
    "max_collection_items": 2000,
    "max_string_length": 100000,
    "sensitive_keys": (
        "password",
        "passwd",
        "secret",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "private_key",
        "cvv",
        "cvc",
        "security_code",
        "card_number",
        "full_card_number",
        "bank_account_number",
        "account_number",
        "routing_number",
        "ifsc",
        "government_id",
        "national_id",
        "aadhaar",
        "pan_number",
    ),
    "sensitive_key_patterns": (
        r"(^|_)(password|passwd|secret|token|api_key|private_key)(_|$)",
        r"(^|_)(cvv|cvc|security_code)(_|$)",
        r"(^|_)(card_number|bank_account_number|routing_number)(_|$)",
    ),
    "conversation_relevance_filter": False,
    "minimum_relevance_score": 0.0,
    "raise_on_invalid_context": True,
    "include_empty_sections": True,
    "field_sources": {},
    "field_authority": {},
    "field_timestamps": {},
    "section_fields": {},
}


def _config(state: Mapping[str, Any]) -> dict[str, Any]:
    supplied = state.get("context_config")
    supplied = supplied if isinstance(supplied, Mapping) else {}
    config = copy.deepcopy(_DEFAULT_CONFIG)
    for key, value in supplied.items():
        if key in config:
            config[key] = copy.deepcopy(value)
    for key in ("max_context_tokens", "max_history_messages", "max_serialization_depth", "max_collection_items", "max_string_length"):
        try:
            config[key] = max(1, int(config[key]))
        except (TypeError, ValueError):
            config[key] = _DEFAULT_CONFIG[key]
    try:
        config["minimum_relevance_score"] = float(config["minimum_relevance_score"])
    except (TypeError, ValueError):
        config["minimum_relevance_score"] = 0.0
    return config


def _plain_value(value: Any, config: Mapping[str, Any], depth: int = 0, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()
    if depth > config["max_serialization_depth"]:
        raise ContextBuildError("Context value exceeds the configured serialization depth.")
    if value is None or isinstance(value, (str, int, bool)):
        if isinstance(value, str) and len(value) > config["max_string_length"]:
            return value[: config["max_string_length"]]
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, decimal.Decimal):
        return str(value) if value.is_finite() else None
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, enum.Enum)):
        return str(value.value if isinstance(value, enum.Enum) else value)
    if isinstance(value, bytes):
        return None
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    elif hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            value = value.to_dict()
        except Exception as exc:
            raise ContextBuildError("A context object could not be serialized.") from exc
    elif hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump(mode="python")
    elif hasattr(value, "dict") and callable(value.dict):
        value = value.dict()
    identity = id(value)
    if identity in seen:
        raise ContextBuildError("Circular reference detected while building context.")
    if isinstance(value, Mapping):
        seen.add(identity)
        result = {}
        for key, item in value.items():
            if not isinstance(key, (str, int, float, bool)):
                continue
            result[str(key)] = _plain_value(item, config, depth + 1, seen)
        seen.remove(identity)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        seen.add(identity)
        result = [
            _plain_value(item, config, depth + 1, seen)
            for item in value[: config["max_collection_items"]]
        ]
        seen.remove(identity)
        return result
    if isinstance(value, set):
        return [
            _plain_value(item, config, depth + 1, seen)
            for item in sorted(value, key=lambda item: str(item))[: config["max_collection_items"]]
        ]
    raise ContextBuildError(f"Unsupported context value type: {type(value).__name__}.")


def _normalize_mapping(value: Any, config: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContextBuildError(f"Invalid context structure for '{field_name}': expected an object.")
    normalized = _plain_value(value, config)
    if not isinstance(normalized, dict):
        raise ContextBuildError(f"Invalid normalized context structure for '{field_name}'.")
    return normalized


def _normalize_list(value: Any, config: Mapping[str, Any], field_name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ContextBuildError(f"Invalid context structure for '{field_name}': expected a list.")
    normalized = _plain_value(value, config)
    if not isinstance(normalized, list):
        raise ContextBuildError(f"Invalid normalized context structure for '{field_name}'.")
    return normalized


def _normalize_scalar(value: Any, config: Mapping[str, Any]) -> Any:
    return _plain_value(value, config)


def _sensitive_key(key: str, config: Mapping[str, Any]) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    sensitive_keys = {str(item).casefold() for item in config["sensitive_keys"]}
    if normalized in sensitive_keys:
        return True
    for pattern in config["sensitive_key_patterns"]:
        try:
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                return True
        except (TypeError, re.error):
            continue
    return False


def _sanitize(value: Any, config: Mapping[str, Any], path: str = "") -> tuple[Any, list[str]]:
    removed: list[str] = []
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if _sensitive_key(key_text, config):
                removed.append(child_path)
                continue
            child, child_removed = _sanitize(item, config, child_path)
            sanitized[key_text] = child
            removed.extend(child_removed)
        return sanitized, removed
    if isinstance(value, list):
        sanitized = []
        for index, item in enumerate(value):
            child, child_removed = _sanitize(item, config, f"{path}[{index}]")
            sanitized.append(child)
            removed.extend(child_removed)
        return sanitized, removed
    return value, removed


def _message_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        for key in ("content", "message", "text", "user_message"):
            value = item.get(key)
            if isinstance(value, str):
                return value
    return ""


def _relevance_score(item: Any, query: str) -> float:
    message = _message_text(item).casefold()
    query_terms = {term for term in re.findall(r"\w+", query.casefold()) if len(term) > 1}
    if not query_terms or not message:
        return 0.0
    message_terms = set(re.findall(r"\w+", message))
    return len(query_terms & message_terms) / len(query_terms)


def _select_history(history: list[Any], message: str, config: Mapping[str, Any]) -> list[Any]:
    limit = config["max_history_messages"]
    if not history:
        return []
    indexed = list(enumerate(history))
    if config["conversation_relevance_filter"] and message.strip():
        threshold = config["minimum_relevance_score"]
        relevant = [
            (index, item)
            for index, item in indexed
            if _relevance_score(item, message) >= threshold
        ]
        if relevant:
            indexed = relevant
    return [item for _, item in indexed[-limit:]]


def _field_value(state: Mapping[str, Any], name: str, config: Mapping[str, Any], default: Any = None) -> Any:
    overrides = config.get("section_fields")
    if isinstance(overrides, Mapping):
        configured_name = overrides.get(name, name)
        if isinstance(configured_name, str):
            name = configured_name
    return state.get(name, default)


def _build_sections(state: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    def scalar(name: str, default: Any = None) -> Any:
        return _normalize_scalar(_field_value(state, name, config, default), config)

    def mapping(name: str) -> dict[str, Any]:
        return _normalize_mapping(_field_value(state, name, config, {}), config, name)

    def sequence(name: str) -> list[Any]:
        return _normalize_list(_field_value(state, name, config, []), config, name)

    message = scalar("message", "")
    if message is None:
        message = ""
    if not isinstance(message, str):
        message = str(message)

    history = sequence("conversation_history")
    history = _select_history(history, message, config)

    return {
        "user": {
            "user_id": scalar("user_id"),
            "session_id": scalar("session_id"),
            "message": message,
        },
        "conversation": {
            "history": history,
        },
        "task_memory": {
            "active_task": scalar("active_task"),
            "task_status": scalar("task_status"),
            "missing_fields": sequence("missing_fields"),
            "selected_product": mapping("selected_product"),
            "execution_result": scalar("execution_result"),
        },
        "understanding": {
            "intent": scalar("intent"),
            "user_goal": scalar("user_goal"),
            "detected_language": scalar("detected_language"),
            "entities": mapping("entities"),
            "references": mapping("references"),
            "missing_fields": sequence("missing_fields"),
            "active_task": scalar("active_task"),
            "task_status": scalar("task_status"),
            "selected_product": mapping("selected_product"),
            "execution_result": scalar("execution_result"),
        },
        "checkout": {
            "checkout_id": scalar("checkout_id"),
            "checkout_status": scalar("checkout_status"),
            "product_id": scalar("product_id"),
            "product_name": scalar("product_name"),
            "quantity": scalar("quantity"),
            "address_id": scalar("address_id"),
            "selected_address_id": scalar("selected_address_id"),
            "selected_payment_method": scalar("selected_payment_method"),
            "payment_method": scalar("payment_method"),
            "order_created": scalar("order_created", False),
            "order_creation_attempted": scalar("order_creation_attempted", False),
            "checkout_completed": scalar("checkout_completed", False),
            "order_id": scalar("order_id"),
            "awaiting_order_tracking_confirmation": scalar("awaiting_order_tracking_confirmation", False),
        },
        "cart": {
            "cart_id": scalar("cart_id"),
            "cart_status": scalar("cart_status"),
            "cart_items": sequence("cart_items"),
            "cart_summary": mapping("cart_summary"),
            "cart_action": scalar("cart_action"),
            "cart_result": mapping("cart_result"),
            "cart_checkout_ready": scalar("cart_checkout_ready", False),
        },
        "backend": {
            "tool_name": scalar("tool_name"),
            "tool_result": scalar("tool_result"),
            "execution_result": scalar("execution_result"),
            "transaction_error": mapping("transaction_error"),
            "policy_result": mapping("policy_result"),
            "policy_error": mapping("policy_error"),
        },
        "billing": {
            "billing": mapping("billing"),
            "bill": mapping("bill"),
            "billing_items": sequence("billing_items"),
            "subtotal": scalar("subtotal"),
            "delivery_charge": scalar("delivery_charge"),
            "discount": scalar("discount"),
            "tax": scalar("tax"),
            "total_amount": scalar("total_amount"),
            "currency": scalar("currency"),
            "billing_payment_method": scalar("billing_payment_method"),
        },
    }


def _field_metadata(state: Mapping[str, Any], config: Mapping[str, Any], section: str, field: str) -> dict[str, Any]:
    field_path = f"{section}.{field}"
    sources = config.get("field_sources")
    authorities = config.get("field_authority")
    timestamps = config.get("field_timestamps")
    source = sources.get(field_path, sources.get(section, "graph_state")) if isinstance(sources, Mapping) else "graph_state"
    authority = authorities.get(field_path, authorities.get(section, "unspecified")) if isinstance(authorities, Mapping) else "unspecified"
    timestamp = timestamps.get(field_path, timestamps.get(section)) if isinstance(timestamps, Mapping) else None
    freshness = "unknown"
    if timestamp is not None:
        try:
            parsed = dt.datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            age = (dt.datetime.now(dt.timezone.utc) - parsed.astimezone(dt.timezone.utc)).total_seconds()
            freshness = "current" if age >= 0 else "future_timestamp"
        except (TypeError, ValueError):
            freshness = "invalid_timestamp"
    return {
        "source": source,
        "authority": authority,
        "timestamp": timestamp,
        "freshness": freshness,
    }


def _build_provenance(context: Mapping[str, Any], state: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    provenance: dict[str, Any] = {}
    for section, values in context.items():
        if not isinstance(values, Mapping):
            continue
        provenance[section] = {
            field: _field_metadata(state, config, section, field)
            for field in values
        }
    return provenance


def _detect_conflicts(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    conflicts = []
    duplicate_paths = (
        ("task_memory.missing_fields", "understanding.missing_fields"),
        ("task_memory.active_task", "understanding.active_task"),
        ("task_memory.task_status", "understanding.task_status"),
        ("task_memory.selected_product", "understanding.selected_product"),
        ("task_memory.execution_result", "understanding.execution_result"),
        ("checkout.selected_address_id", "checkout.address_id"),
        ("checkout.selected_payment_method", "checkout.payment_method"),
    )
    for left_path, right_path in duplicate_paths:
        left_section, left_key = left_path.split(".", 1)
        right_section, right_key = right_path.split(".", 1)
        left = context.get(left_section, {}).get(left_key)
        right = context.get(right_section, {}).get(right_key)
        if left not in (None, {}, []) and right not in (None, {}, []) and left != right:
            conflicts.append({
                "type": "duplicate_field_mismatch",
                "fields": [left_path, right_path],
            })
    return conflicts


def _estimate_tokens(value: Any) -> int:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return max(1, math.ceil(len(encoded.encode("utf-8")) / 4))


def _apply_token_budget(context: dict[str, Any], config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    limit = config["max_context_tokens"]
    history = context.get("conversation", {}).get("history", [])
    metadata = context.get("context_metadata")
    removed = 0
    if not isinstance(history, list):
        history = []
    if not isinstance(metadata, dict):
        metadata = {}
        context["context_metadata"] = metadata

    while True:
        estimated = _estimate_tokens(context)
        metadata.update(
            {
                "estimated_tokens": estimated,
                "max_tokens": limit,
                "truncated": bool(removed),
                "history_truncated": bool(removed),
                "removed_history_messages": removed,
            }
        )
        estimated_with_metadata = _estimate_tokens(context)
        if estimated_with_metadata <= limit:
            if estimated != estimated_with_metadata:
                metadata["estimated_tokens"] = estimated_with_metadata
                continue
            return context, {
                "estimated_tokens": estimated_with_metadata,
                "max_tokens": limit,
                "truncated": bool(removed),
                "removed_history_messages": removed,
            }
        if not history:
            raise ContextBuildError(
                "Required context exceeds the configured token budget; critical transaction data was not truncated."
            )
        history.pop(0)
        removed += 1


def _validate_context(context: dict[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validated = ContextEnvelope.model_validate(context)
        return validated.model_dump(mode="python")
    except ValidationError as exc:
        errors = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "type": error.get("type"),
                "message": error.get("msg"),
            }
            for error in exc.errors()
        ]
        if config["raise_on_invalid_context"]:
            raise ContextBuildError("Context schema validation failed.", errors) from exc
        logger.warning("Context schema validation failed: %s", errors)
        return context


def build_context(state: GraphState) -> dict[str, Any]:
    if not isinstance(state, Mapping):
        raise ContextBuildError("Graph state must be a mapping.")
    config = _config(state)
    context = _build_sections(state, config)
    sanitized, removed_fields = _sanitize(context, config)
    conflicts = _detect_conflicts(sanitized)
    provenance = _build_provenance(sanitized, state, config)
    context_metadata = {
        "schema_version": str(config["schema_version"]),
        "state_schema_version": _normalize_scalar(state.get("state_schema_version"), config),
        "state_version": _normalize_scalar(state.get("state_version"), config),
        "estimated_tokens": 0,
        "max_tokens": config["max_context_tokens"],
        "history_truncated": False,
        "removed_history_messages": 0,
        "sensitive_fields_removed": removed_fields,
        "conflicts": conflicts,
        "warnings": [],
    }
    if conflicts:
        context_metadata["warnings"].append("Conflicting duplicate context values were detected.")
    context = {
        **sanitized,
        "provenance": provenance,
        "context_metadata": context_metadata,
    }
    context, _ = _apply_token_budget(context, config)
    return _validate_context(context, config)


def context_node(state: GraphState) -> GraphState:
    try:
        context = build_context(state)
        return {"context": context}
    except ContextBuildError as exc:
        logger.error(
            "Context construction failed",
            extra={
                "error_type": type(exc).__name__,
                "validation_errors": exc.errors,
                "session_id": state.get("session_id") if isinstance(state, Mapping) else None,
                "execution_id": state.get("execution_id") if isinstance(state, Mapping) else None,
            },
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unexpected context construction failure",
            extra={
                "session_id": state.get("session_id") if isinstance(state, Mapping) else None,
                "execution_id": state.get("execution_id") if isinstance(state, Mapping) else None,
            },
        )
        raise ContextBuildError("Unexpected context construction failure.") from exc


__all__ = [
    "ContextBuildError",
    "ContextEnvelope",
    "build_context",
    "context_node",
]
