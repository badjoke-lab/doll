"""Secret-safe rendering for user-visible errors and structured diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from doll.secret_detection import DEFAULT_MAX_SCAN_CHARS, redact_text

type DiagnosticScalar = str | int | float | bool | None
type DiagnosticValue = DiagnosticScalar | list[DiagnosticValue] | dict[str, DiagnosticValue]

DEFAULT_MAX_DIAGNOSTIC_DEPTH = 6
DEFAULT_MAX_DIAGNOSTIC_ITEMS = 256
_DEPTH_LIMIT_MARKER = "[DIAGNOSTIC_DEPTH_LIMIT]"
_ITEM_LIMIT_MARKER = "[DIAGNOSTIC_ITEM_LIMIT]"
_BINARY_MARKER = "[BINARY_CONTENT_OMITTED]"


@dataclass(frozen=True, slots=True)
class DiagnosticRedactionResult:
    """Bounded diagnostic payload and aggregate non-secret metadata."""

    value: DiagnosticValue
    finding_count: int
    text_truncated: bool
    depth_limit_reached: bool
    item_limit_reached: bool


@dataclass(slots=True)
class _DiagnosticState:
    finding_count: int = 0
    text_truncated: bool = False
    depth_limit_reached: bool = False
    item_limit_reached: bool = False
    items_seen: int = 0


def redact_exception_text(exc: BaseException) -> str:
    """Return only a redacted exception message, preserving no matched value."""

    result = redact_text(str(exc))
    return result.redacted_text.strip() or type(exc).__name__


def safe_exception_message(prefix: str, exc: BaseException) -> str:
    """Render an exception for CLI output without returning detected secret values."""

    message = redact_exception_text(exc)
    if message == type(exc).__name__ and not str(exc):
        return f"{prefix}: {type(exc).__name__}"
    return f"{prefix}: {type(exc).__name__}: {message}"


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
    )
    return DiagnosticRedactionResult(
        value=redacted,
        finding_count=state.finding_count,
        text_truncated=state.text_truncated,
        depth_limit_reached=state.depth_limit_reached,
        item_limit_reached=state.item_limit_reached,
    )


def _redact_value(
    value: object,
    *,
    depth: int,
    max_depth: int,
    max_items: int,
    max_string_chars: int,
    state: _DiagnosticState,
) -> DiagnosticValue:
    if depth > max_depth:
        state.depth_limit_reached = True
        return _DEPTH_LIMIT_MARKER
    if isinstance(value, str):
        return _redact_string(value, max_string_chars=max_string_chars, state=state)
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, bytes | bytearray | memoryview):
        return _BINARY_MARKER
    if isinstance(value, Mapping):
        result: dict[str, DiagnosticValue] = {}
        for raw_key, raw_value in value.items():
            if not _consume_item(state, max_items=max_items):
                result[_ITEM_LIMIT_MARKER] = True
                break
            key = _redact_string(
                str(raw_key),
                max_string_chars=max_string_chars,
                state=state,
            )
            result[key] = _redact_value(
                raw_value,
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
                max_string_chars=max_string_chars,
                state=state,
            )
        return result
    if isinstance(value, Sequence):
        result_list: list[DiagnosticValue] = []
        for item in value:
            if not _consume_item(state, max_items=max_items):
                result_list.append(_ITEM_LIMIT_MARKER)
                break
            result_list.append(
                _redact_value(
                    item,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                    max_string_chars=max_string_chars,
                    state=state,
                )
            )
        return result_list
    return f"[OBJECT:{type(value).__name__}]"


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
