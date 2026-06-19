from __future__ import annotations

from dataclasses import dataclass

import pytest

from doll.diagnostics import redact_diagnostic, safe_exception_message


def test_safe_exception_message_redacts_secret_and_private_path() -> None:
    exc = RuntimeError(
        "request failed api_key=synthetic-secret-value at /Users/example/private/workspace"
    )
    message = safe_exception_message("operation failed", exc)
    assert message.startswith("operation failed: RuntimeError:")
    assert "synthetic-secret-value" not in message
    assert "/Users/example" not in message
    assert "[REDACTED:credential_assignment]" in message
    assert "[REDACTED:private_path]" in message


def test_safe_exception_message_handles_empty_message() -> None:
    assert safe_exception_message("operation failed", RuntimeError()) == (
        "operation failed: RuntimeError"
    )


def test_structured_diagnostic_redacts_nested_values_and_keys() -> None:
    payload = {
        "request": {
            "api_key=synthetic-key-in-key": "Authorization: Bearer syntheticBearer123456",
            "contact": ["user@example.invalid", {"phone": "phone: +81 90-1234-5678"}],
        }
    }
    result = redact_diagnostic(payload)
    rendered = repr(result.value)
    assert "synthetic-key-in-key" not in rendered
    assert "syntheticBearer" not in rendered
    assert "user@example.invalid" not in rendered
    assert "90-1234-5678" not in rendered
    assert result.finding_count == 4
    assert result.text_truncated is False
    assert result.depth_limit_reached is False
    assert result.item_limit_reached is False


def test_structured_diagnostic_omits_binary_and_unknown_object_representation() -> None:
    @dataclass
    class SecretObject:
        value: str

    secret = "synthetic-object-secret"
    result = redact_diagnostic(
        {
            "binary": b"synthetic-binary-secret",
            "object": SecretObject(secret),
        }
    )
    assert result.value == {
        "binary": "[BINARY_CONTENT_OMITTED]",
        "object": "[OBJECT:SecretObject]",
    }
    assert secret not in repr(result.value)


def test_structured_diagnostic_depth_and_item_limits_are_explicit() -> None:
    depth_result = redact_diagnostic({"a": {"b": {"c": "value"}}}, max_depth=1)
    assert depth_result.depth_limit_reached is True
    assert "[DIAGNOSTIC_DEPTH_LIMIT]" in repr(depth_result.value)

    item_result = redact_diagnostic(["a", "b", "c"], max_items=2)
    assert item_result.item_limit_reached is True
    assert item_result.value == ["a", "b", "[DIAGNOSTIC_ITEM_LIMIT]"]


def test_structured_diagnostic_string_limit_omits_unscanned_suffix() -> None:
    secret = "password=synthetic-secret-value"
    result = redact_diagnostic("safe-prefix-" + ("x" * 20) + secret, max_string_chars=12)
    assert result.text_truncated is True
    assert secret not in repr(result.value)
    assert "[UNSCANNED_CONTENT_OMITTED]" in repr(result.value)


@pytest.mark.parametrize(
    ("max_depth", "max_items"),
    [(-1, 1), (1, 0)],
)
def test_invalid_diagnostic_limits_are_rejected(max_depth: int, max_items: int) -> None:
    with pytest.raises(ValueError):
        redact_diagnostic("safe", max_depth=max_depth, max_items=max_items)


def test_scalar_diagnostic_values_are_preserved() -> None:
    result = redact_diagnostic([None, True, 3, 4.5])
    assert result.value == [None, True, 3, 4.5]
