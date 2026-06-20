from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from doll.safe_logging import (
    MAX_LOG_LINE_BYTES,
    SecretSafeLogHandler,
    configure_secret_safe_logger,
    render_log_record,
)


def test_secret_safe_logger_sanitizes_before_stream_persistence() -> None:
    stream = StringIO()
    logger = configure_secret_safe_logger("doll.test.secret-safe", stream=stream)

    try:
        raise RuntimeError("api_key=synthetic-exception-secret at /Users/example/private/workspace")
    except RuntimeError:
        logger.exception(
            "operation failed for %s\nfor retry",
            "user@example.invalid",
            extra={
                "operation_id": "operation-1",
                "context": {
                    "password": "synthetic-unlabeled-password",
                    "hostname": "private-machine",
                    "path": "/Users/example/private/input.txt",
                },
            },
        )

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    rendered = repr(payload)

    assert payload["message"] == "operation failed for %s for retry"
    assert payload["operation_id"] == "operation-1"
    assert payload["arguments"] == ["[REDACTED:personal_email]"]
    assert payload["context"]["password"] == "[REDACTED:secret_field]"
    assert payload["context"]["hostname"] == "[REDACTED:private_environment]"
    assert payload["exception"]["class"] == "RuntimeError"
    assert "synthetic-exception-secret" not in rendered
    assert "synthetic-unlabeled-password" not in rendered
    assert "private-machine" not in rendered
    assert "/Users/example" not in rendered
    assert "user@example.invalid" not in rendered
    assert "pathname" not in payload
    assert "traceback" not in payload


def test_secret_safe_handler_never_stringifies_unknown_objects() -> None:
    class DangerousObject:
        def __str__(self) -> str:
            raise AssertionError("must not be called")

    stream = StringIO()
    logger = configure_secret_safe_logger("doll.test.object", stream=stream)
    logger.info(
        DangerousObject(),
        DangerousObject(),
        extra={"context": {"value": DangerousObject()}},
    )

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "[OBJECT:DangerousObject]"
    assert payload["arguments"] == ["[OBJECT:DangerousObject]"]
    assert payload["context"] == {"value": "[OBJECT:DangerousObject]"}


def test_configure_secret_safe_logger_removes_existing_unsafe_handlers() -> None:
    unsafe_stream = StringIO()
    safe_stream = StringIO()
    logger = logging.getLogger("doll.test.replace-handler")
    logger.handlers.clear()
    logger.addHandler(logging.StreamHandler(unsafe_stream))
    logger.setLevel(logging.INFO)

    configured = configure_secret_safe_logger(logger.name, stream=safe_stream)
    configured.info("password=synthetic-handler-secret")

    assert unsafe_stream.getvalue() == ""
    assert "synthetic-handler-secret" not in safe_stream.getvalue()
    assert all(isinstance(handler, SecretSafeLogHandler) for handler in configured.handlers)


def test_log_record_size_limit_returns_only_bounded_safe_payload() -> None:
    record = logging.LogRecord(
        name="doll.test.size",
        level=logging.INFO,
        pathname="/Users/example/private/source.py",
        lineno=10,
        msg="safe message",
        args=(),
        exc_info=None,
    )
    record.created = 0.0
    record.context = {f"field_{index}": "x" * 1000 for index in range(20)}

    rendered = render_log_record(record)
    payload = json.loads(rendered)

    assert payload["message"] == "[LOG_RECORD_SIZE_LIMIT]"
    assert len(rendered.encode("utf-8")) <= MAX_LOG_LINE_BYTES
    assert "/Users/example" not in rendered


def test_preformatted_exception_and_stack_text_are_not_reused() -> None:
    record = logging.LogRecord(
        name="doll.test.preformatted",
        level=logging.ERROR,
        pathname="/Users/example/private/source.py",
        lineno=20,
        msg="failed",
        args=(),
        exc_info=None,
    )
    record.exc_text = "password=synthetic-preformatted-secret"
    record.stack_info = "/Users/example/private/stack.py"

    payload = json.loads(render_log_record(record))
    rendered = repr(payload)
    assert "synthetic-preformatted-secret" not in rendered
    assert "/Users/example" not in rendered
    assert payload["stack"] == "[STACK_INFO_OMITTED]"


def test_renderer_returns_static_omission_event_when_encoding_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = logging.LogRecord(
        name="doll.test.render-failure",
        level=logging.ERROR,
        pathname="ignored.py",
        lineno=1,
        msg="password=synthetic-render-secret",
        args=(),
        exc_info=None,
    )

    def fail_encoding(*args: object, **kwargs: object) -> str:
        raise RuntimeError("synthetic encoder failure")

    monkeypatch.setattr(json, "dumps", fail_encoding)
    rendered = render_log_record(record)

    assert rendered == (
        '{"level":"ERROR","logger":"doll.safe_logging","message":"[LOG_RECORD_OMITTED]"}'
    )
    assert "synthetic-render-secret" not in rendered


def test_handler_writes_static_omission_event_after_first_stream_failure() -> None:
    class FailOnceStream(StringIO):
        failed = False

        def write(self, value: str) -> int:
            if not self.failed:
                self.failed = True
                raise OSError("synthetic first write failure")
            return super().write(value)

    stream = FailOnceStream()
    handler = SecretSafeLogHandler(stream=stream)
    record = logging.LogRecord(
        name="doll.test.stream-failure",
        level=logging.ERROR,
        pathname="ignored.py",
        lineno=1,
        msg="password=synthetic-stream-secret",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert "[LOG_RECORD_OMITTED]" in stream.getvalue()
    assert "synthetic-stream-secret" not in stream.getvalue()


def test_handler_suppresses_second_stream_failure() -> None:
    class AlwaysFailStream(StringIO):
        def write(self, value: str) -> int:
            raise OSError("synthetic persistent write failure")

    handler = SecretSafeLogHandler(stream=AlwaysFailStream())
    record = logging.LogRecord(
        name="doll.test.double-stream-failure",
        level=logging.ERROR,
        pathname="ignored.py",
        lineno=1,
        msg="password=synthetic-double-failure-secret",
        args=(),
        exc_info=None,
    )

    handler.emit(record)


def test_renderer_handles_invalid_timestamp_and_scalar_messages() -> None:
    invalid_time_record = logging.LogRecord(
        name="doll.test.invalid-time",
        level=logging.INFO,
        pathname="ignored.py",
        lineno=1,
        msg=None,
        args=(),
        exc_info=None,
    )
    invalid_time_record.created = 1e300
    invalid_time_record.operation_id = ""
    invalid_time_record.event_id = 7
    invalid_time = json.loads(render_log_record(invalid_time_record))
    assert invalid_time["timestamp"] == "1970-01-01T00:00:00.000Z"
    assert invalid_time["message"] == "None"
    assert "operation_id" not in invalid_time
    assert "event_id" not in invalid_time

    non_finite_record = logging.LogRecord(
        name="doll.test.non-finite",
        level=logging.INFO,
        pathname="ignored.py",
        lineno=1,
        msg=float("nan"),
        args=(),
        exc_info=None,
    )
    non_finite = json.loads(render_log_record(non_finite_record))
    assert non_finite["message"] == "[NON_FINITE_NUMBER_OMITTED]"

    blank_record = logging.LogRecord(
        name="doll.test.blank",
        level=logging.INFO,
        pathname="ignored.py",
        lineno=1,
        msg="   ",
        args=(),
        exc_info=None,
    )
    blank = json.loads(render_log_record(blank_record))
    assert blank["message"] == ""


def test_handler_suppresses_flush_failure() -> None:
    class FlushFailureStream(StringIO):
        def flush(self) -> None:
            raise OSError("synthetic flush failure")

    handler = SecretSafeLogHandler(stream=FlushFailureStream())
    handler.flush()
