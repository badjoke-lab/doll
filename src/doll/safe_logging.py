"""Bounded secret-safe logging for doll-owned standard-library loggers."""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import UTC, datetime
from typing import TextIO

from doll.diagnostics import redact_diagnostic, redact_exception_text
from doll.secret_detection import redact_text

MAX_LOG_TEXT_CHARS = 4096
MAX_LOG_CONTEXT_DEPTH = 6
MAX_LOG_CONTEXT_ITEMS = 128
MAX_LOG_LINE_BYTES = 16_384
_LOG_RECORD_OMITTED = '{"level":"ERROR","logger":"doll.safe_logging","message":"[LOG_RECORD_OMITTED]"}'
_LOG_RECORD_SIZE_LIMIT = "[LOG_RECORD_SIZE_LIMIT]"
_STACK_INFO_OMITTED = "[STACK_INFO_OMITTED]"


def render_log_record(record: logging.LogRecord) -> str:
    """Render one LogRecord without interpolating or stringifying unsafe objects."""

    try:
        payload: dict[str, object] = {
            "timestamp": _timestamp(record.created),
            "level": _sanitize_text(record.levelname, maximum=32) or "UNKNOWN",
            "logger": _sanitize_text(record.name, maximum=200) or "doll",
            "message": _sanitize_message(record.msg),
        }
        if record.args:
            payload["arguments"] = redact_diagnostic(
                record.args,
                max_depth=MAX_LOG_CONTEXT_DEPTH,
                max_items=MAX_LOG_CONTEXT_ITEMS,
                max_string_chars=MAX_LOG_TEXT_CHARS,
            ).value
        context = getattr(record, "context", None)
        if context is not None:
            payload["context"] = redact_diagnostic(
                context,
                max_depth=MAX_LOG_CONTEXT_DEPTH,
                max_items=MAX_LOG_CONTEXT_ITEMS,
                max_string_chars=MAX_LOG_TEXT_CHARS,
            ).value
        _copy_safe_correlation_fields(record, payload)
        if record.exc_info is not None:
            exception = record.exc_info[1]
            if exception is not None:
                payload["exception"] = {
                    "class": _sanitize_text(type(exception).__name__, maximum=120) or "Error",
                    "message": redact_exception_text(exception),
                }
        if record.stack_info:
            payload["stack"] = _STACK_INFO_OMITTED
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        if len(rendered.encode("utf-8")) <= MAX_LOG_LINE_BYTES:
            return rendered
        reduced = {
            "timestamp": payload["timestamp"],
            "level": payload["level"],
            "logger": payload["logger"],
            "message": _LOG_RECORD_SIZE_LIMIT,
        }
        return json.dumps(reduced, sort_keys=True, separators=(",", ":"))
    except BaseException:
        return _LOG_RECORD_OMITTED


class SecretSafeLogHandler(logging.Handler):
    """Write only rendered secret-safe JSON lines to the configured stream."""

    terminator = "\n"

    def __init__(self, stream: TextIO | None = None, level: int = logging.NOTSET) -> None:
        super().__init__(level=level)
        self.stream = stream if stream is not None else sys.stderr

    def emit(self, record: logging.LogRecord) -> None:
        """Sanitize before persistence and avoid logging's unsafe fallback renderer."""

        try:
            self.stream.write(render_log_record(record) + self.terminator)
            self.flush()
        except BaseException:
            try:
                self.stream.write(_LOG_RECORD_OMITTED + self.terminator)
                self.flush()
            except BaseException:
                return

    def flush(self) -> None:
        """Flush without exposing a failed record through logging.handleError."""

        try:
            self.stream.flush()
        except BaseException:
            return


def configure_secret_safe_logger(
    name: str,
    *,
    stream: TextIO | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure one doll-owned logger with only the secret-safe handler."""

    logger = logging.getLogger(name)
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.addHandler(SecretSafeLogHandler(stream=stream))
    logger.setLevel(level)
    logger.propagate = False
    return logger


def _timestamp(created: float) -> str:
    try:
        value = created if math.isfinite(created) else 0.0
        return datetime.fromtimestamp(value, UTC).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
    except (OverflowError, OSError, ValueError):
        return "1970-01-01T00:00:00.000Z"


def _sanitize_message(value: object) -> str:
    if isinstance(value, str):
        return _sanitize_text(value, maximum=MAX_LOG_TEXT_CHARS)
    if value is None or isinstance(value, bool | int):
        return str(value)
    if isinstance(value, float):
        return str(value) if math.isfinite(value) else "[NON_FINITE_NUMBER_OMITTED]"
    return f"[OBJECT:{type(value).__name__}]"


def _sanitize_text(value: str, *, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        return ""
    return redact_text(normalized, max_scan_chars=maximum).redacted_text


def _copy_safe_correlation_fields(
    record: logging.LogRecord,
    payload: dict[str, object],
) -> None:
    for field in ("operation_id", "event_id", "action"):
        value = getattr(record, field, None)
        if isinstance(value, str):
            sanitized = _sanitize_text(value, maximum=200)
            if sanitized:
                payload[field] = sanitized


__all__ = [
    "MAX_LOG_CONTEXT_DEPTH",
    "MAX_LOG_CONTEXT_ITEMS",
    "MAX_LOG_LINE_BYTES",
    "MAX_LOG_TEXT_CHARS",
    "SecretSafeLogHandler",
    "configure_secret_safe_logger",
    "render_log_record",
]
