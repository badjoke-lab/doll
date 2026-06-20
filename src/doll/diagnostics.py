"""Secret-safe rendering for user-visible errors and structured diagnostics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from doll.secret_detection import DEFAULT_MAX_SCAN_CHARS, redact_text
from doll.sensitive_fields import field_redaction_marker

type DiagnosticScalar = str | int | float | bool | None
type DiagnosticValue = DiagnosticScalar | list[DiagnosticValue] | dict[str, DiagnosticValue]

DEFAULT_MAX_DIAGNOSTIC_DEPTH = 6
DEFAULT_MAX_DIAGNOSTIC_ITEMS = 256
_DEPTH_LIMIT_MARKER = "[DIAGNOSTIC_DEPTH_LIMIT]"
_ITEM_LIMIT_MARKER = "[DIAGNOSTIC_ITEM_LIMIT]"
_BINARY_MARKER = "[BINARY_CONTENT_OMITTED]"
_CYCLE_MARKER = "[DIAGNOSTIC_CYCLE_OMITTED]"
_NON_FINITE_MARKER = "[NON_FINITE_NUMBER_OMITTED]"


@dataclass(frozen=True, slots=True)
class DiagnosticRedactionResult:
    """Bounded diagnostic payload and aggregate non-secret metadata."""

    value: DiagnosticValue
    finding_count: int
    field_redaction_count: int
    text_truncated: bool
    depth_limit_reached: bool
    item_limit_reached: bool
    cycle_detected: bool


@dataclass(slots=True)
class _DiagnosticState:
    finding_count: int = 0
    field_redaction_count: int = 0
    text_truncated: bool = False
    depth_limit_reached: bool = False
    item_limit_reached: bool = False
    cycle_detected: bool = False
    items_seen: int = 0


def redact_exception_text(exc: BaseException) -> str:
    """Return only a redacted exception message, preserving no matched value."""

    error_class = type(exc).__name__
    try:
        raw_message = str(exc)
    except BaseException:
        return error_class
    result = redact_text(raw_message)
    return result.redacted_text.strip() or error_class


def safe_exception_message(prefix: str, exc: BaseException) -> str:
    """Render an exception for CLI output without returning detected secret values."""

    error_class = type(exc).__name__
    message = redact_exception_text(exc)
    if message == error_class:
        return f"{prefix}: {error_class}"
    return f"{prefix}: {error_class}: {message}"


def redact_diagnostic(
    value: object,
    *,
    max_depth: int = DEFAULT_MAX_DIAGNOSTIC_DEPTH,
    max_items: int = DEFAULT_MAX_DIAGNOSTIC_ITEMS,
    max_string_chars: int = DEFAULT_MAX_SCAN_CHARS,
) -> DiagnosticRedactionResult:
    """Recursively redact an explicitly supplied diagnostic object within bounds."""

    if max_depth < 0:
        raise ValueError("max_depth must be at least 0")
    if max_items < 1:
        raise ValueError("max_items must be at least 1")
    state = _DiagnosticState()
    redacted = _redact_value(
        value,
        depth=0,
        max_depth=max_depth,
        max_items=max_items,
        max_string_chars=max_string_chars,
        state=state,
        active_container_ids=set(),
    )
    return DiagnosticRedactionResult(
        value=redacted,
        finding_count=state.finding_count,
        field_redaction_count=state.field_redaction_count,
        text_truncated=state.text_truncated,
        depth_limit_reached=state.depth_limit_reached,
        item_limit_reached=state.item_limit_reached,
        cycle_detected=state.cycle_detected,
    )


def _redact_value(
    value: object,
    *,
    depth: int,
    max_depth: int,
    max_items: int,
    max_string_chars: int,
    state: _DiagnosticState,
    active_container_ids: set[int],
) -> DiagnosticValue:
    if depth > max_depth:
        state.depth_limit_reached = True
        return _DEPTH_LIMIT_MARKER
    if isinstance(value, str):
        return _redact_string(value, max_string_chars=max_string_chars, state=state)
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _NON_FINITE_MARKER
    if isinstance(value, bytes | bytearray | memoryview):
        return _BINARY_MARKER
    if isinstance(value, Mapping):
        return _redact_mapping(
            value,
            depth=depth,
            max_depth=max_depth,
            max_items=max_items,
            max_string_chars=max_string_chars,
            state=state,
            active_container_ids=active_container_ids,
        )
    if isinstance(value, Sequence):
        return _redact_sequence(
            value,
            depth=depth,
            max_depth=max_depth,
            max_items=max_items,
            max_string_chars=max_string_chars,
            state=state,
            active_container_ids=active_container_ids,
        )
    return f"[OBJECT:{type(value).__name__}]"


def _redact_mapping(
    value: Mapping[object, object],
    *,
    depth: int,
    max_depth: int,
    max_items: int,
    max_string_chars: int,
    state: _DiagnosticState,
    active_container_ids: set[int],
) -> dict[str, DiagnosticValue]:
    identity = id(value)
    if identity in active_container_ids:
        state.cycle_detected = True
        return {_CYCLE_MARKER: True}
    active_container_ids.add(identity)
    result: dict[str, DiagnosticValue] = {}
    try:
        for raw_key, raw_value in value.items():
            if not _consume_item(state, max_items=max_items):
                result[_ITEM_LIMIT_MARKER] = True
                break
            key = _redact_mapping_key(
                raw_key,
                max_string_chars=max_string_chars,
                state=state,
            )
            key = _unique_key(result, key)
            marker = field_redaction_marker(raw_key) if isinstance(raw_key, str) else None
            if marker is not None:
                state.field_redaction_count += 1
                result[key] = marker
                continue
            result[key] = _redact_value(
                raw_value,
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
                max_string_chars=max_string_chars,
                state=state,
                active_container_ids=active_container_ids,
            )
    finally:
        active_container_ids.remove(identity)
    return result


def _redact_sequence(
    value: Sequence[object],
    *,
    depth: int,
    max_depth: int,
    max_items: int,
    max_string_chars: int,
    state: _DiagnosticState,
    active_container_ids: set[int],
) -> list[DiagnosticValue]:
    identity = id(value)
    if identity in active_container_ids:
        state.cycle_detected = True
        return [_CYCLE_MARKER]
    active_container_ids.add(identity)
    result: list[DiagnosticValue] = []
    try:
        for item in value:
            if not _consume_item(state, max_items=max_items):
                result.append(_ITEM_LIMIT_MARKER)
                break
            result.append(
                _redact_value(
                    item,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                    max_string_chars=max_string_chars,
                    state=state,
                    active_container_ids=active_container_ids,
                )
            )
    finally:
        active_container_ids.remove(identity)
    return result


def _redact_mapping_key(
    value: object,
    *,
    max_string_chars: int,
    state: _DiagnosticState,
) -> str:
    if isinstance(value, str):
        return _redact_string(value, max_string_chars=max_string_chars, state=state)
    if value is None or isinstance(value, bool | int):
        return str(value)
    if isinstance(value, float):
        return str(value) if math.isfinite(value) else _NON_FINITE_MARKER
    return f"[OBJECT_KEY:{type(value).__name__}]"


def _unique_key(result: dict[str, DiagnosticValue], key: str) -> str:
    if key not in result:
        return key
    index = 2
    while f"{key}#{index}" in result:
        index += 1
    return f"{key}#{index}"


def _redact_string(
    value: str,
    *,
    max_string_chars: int,
    state: _DiagnosticState,
) -> str:
    result = redact_text(value, max_scan_chars=max_string_chars)
    state.finding_count += len(result.findings)
    state.text_truncated = state.text_truncated or result.input_truncated
    return result.redacted_text


def _consume_item(state: _DiagnosticState, *, max_items: int) -> bool:
    if state.items_seen >= max_items:
        state.item_limit_reached = True
        return False
    state.items_seen += 1
    return True


__all__ = [
    "DEFAULT_MAX_DIAGNOSTIC_DEPTH",
    "DEFAULT_MAX_DIAGNOSTIC_ITEMS",
    "DiagnosticRedactionResult",
    "DiagnosticValue",
    "redact_diagnostic",
    "redact_exception_text",
    "safe_exception_message",
]
