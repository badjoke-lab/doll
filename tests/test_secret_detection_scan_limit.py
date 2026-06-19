from __future__ import annotations

from doll.secret_detection import redact_text


def test_scan_limit_omits_the_entire_original_input() -> None:
    text = "prefix contact=user@example.invalid"
    result = redact_text(text, max_scan_chars=20)
    assert result.input_truncated is True
    assert result.scanned_characters == 20
    assert result.redacted_text == "[UNSCANNED_CONTENT_OMITTED]"
    assert "prefix" not in result.redacted_text
    assert "user@" not in result.redacted_text
