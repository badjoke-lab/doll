from __future__ import annotations

import pytest

from doll.secret_detection import redact_text, scan_secrets


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Authorization: Bearer syntheticBearerToken_123456", "authorization_header"),
        ('api_key="sk-syntheticTokenValue1234567890"', "credential_assignment"),
        ("password=synthetic-password-value", "credential_assignment"),
        ("Cookie: session=synthetic-cookie-value", "session_cookie"),
        (
            "recovery phrase: alpha bravo charlie delta echo foxtrot golf hotel "
            "india juliet kilo lima",
            "recovery_phrase",
        ),
        (
            "-----BEGIN PRIVATE KEY-----\nsynthetic-material\n-----END PRIVATE KEY-----",
            "private_key",
        ),
        ("token sk-syntheticTokenValue1234567890", "known_token"),
        ("contact=user@example.invalid", "personal_email"),
        ("phone: +81 90-1234-5678", "personal_phone"),
        ("failed at /Users/example/private/workspace", "private_path"),
        (r"failed at C:\Users\example\private\workspace", "private_path"),
    ],
)
def test_common_synthetic_patterns_are_detected_and_redacted(
    text: str,
    kind: str,
) -> None:
    result = redact_text(text)
    assert result.changed is True
    assert any(finding.kind == kind for finding in result.findings)
    assert "synthetic" not in result.redacted_text.lower()
    assert "example/private" not in result.redacted_text


def test_plain_text_remains_unchanged() -> None:
    text = "The local continuity check completed successfully."
    result = redact_text(text)
    assert result.redacted_text == text
    assert result.findings == ()
    assert result.changed is False


def test_findings_never_retain_matched_secret_values() -> None:
    secret = "synthetic-password-value"
    result = scan_secrets(f"password={secret}")
    assert result.detected is True
    assert secret not in repr(result)
    assert secret not in repr(result.findings)
    finding = result.findings[0]
    assert finding.end > finding.start
    assert finding.detector_id


def test_overlapping_findings_are_normalized_deterministically() -> None:
    text = 'access_token="sk-syntheticTokenValue1234567890"'
    first = scan_secrets(text)
    second = scan_secrets(text)
    assert first == second
    assert len(first.findings) == 1
    result = redact_text(text)
    assert result.redacted_text.count("[REDACTED:") == 1
    assert "syntheticTokenValue" not in result.redacted_text


def test_scan_limit_is_explicit_and_unscanned_suffix_is_not_returned() -> None:
    secret = "password=synthetic-password-value"
    text = "safe-prefix " + ("x" * 30) + secret
    result = redact_text(text, max_scan_chars=20)
    assert result.input_truncated is True
    assert result.scanned_characters == 20
    assert result.input_characters == len(text)
    assert result.redacted_text.endswith("[UNSCANNED_CONTENT_OMITTED]")
    assert secret not in result.redacted_text


def test_finding_limit_is_enforced() -> None:
    text = " ".join(f"password=synthetic-value-{index:02d}" for index in range(20))
    result = scan_secrets(text, max_findings=3)
    assert len(result.findings) == 3
    assert result.finding_limit_reached is True


@pytest.mark.parametrize(
    ("max_scan_chars", "max_findings"),
    [(0, 1), (1_048_577, 1), (1, 0), (1, 1_025)],
)
def test_invalid_resource_limits_are_rejected(
    max_scan_chars: int,
    max_findings: int,
) -> None:
    with pytest.raises(ValueError):
        scan_secrets(
            "safe",
            max_scan_chars=max_scan_chars,
            max_findings=max_findings,
        )


def test_jwt_detection_is_medium_confidence() -> None:
    token = "eyJheader12345.payload12345.signature12345"
    result = scan_secrets(token)
    assert len(result.findings) == 1
    assert result.findings[0].kind == "known_token"
    assert result.findings[0].confidence == "medium"
