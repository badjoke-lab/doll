from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from doll import state, workspace
from doll._confirmation_types import (
    MAX_CONFIRMATION_TTL_SECONDS,
    ConfirmationCorruptError,
    ConfirmationPreview,
    ConfirmationValidationError,
    _validate_preview_text,
    parse_utc,
    safe_now,
    validate_fingerprint,
    validate_preview,
    validate_token,
    validate_ttl,
)


@pytest.mark.parametrize(
    "value",
    [True, 0, MAX_CONFIRMATION_TTL_SECONDS + 1, cast(Any, "120")],
)
def test_confirmation_ttl_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ConfirmationValidationError):
        validate_ttl(cast(Any, value))


def test_confirmation_clock_and_timestamp_fail_closed() -> None:
    def broken_clock() -> datetime:
        raise RuntimeError("synthetic clock failure")

    with pytest.raises(ConfirmationValidationError, match="clock failed"):
        safe_now(broken_clock)
    with pytest.raises(ConfirmationValidationError, match="timezone-aware"):
        safe_now(lambda: datetime(2026, 6, 22))
    with pytest.raises(ConfirmationCorruptError, match="timestamp is invalid"):
        parse_utc("not-a-timestamp")
    with pytest.raises(ConfirmationCorruptError, match="timezone-aware"):
        parse_utc("2026-06-22T00:00:00")

    expected = datetime(2026, 6, 22, tzinfo=UTC)
    assert safe_now(lambda: expected) == expected


def test_confirmation_tokens_fingerprints_and_preview_reject_malformed_input() -> None:
    with pytest.raises(ConfirmationValidationError, match="must be text"):
        validate_token("identifier", 7, 20)
    for value in ("", "bad/value", "x" * 21):
        with pytest.raises(ConfirmationValidationError, match="is invalid"):
            validate_token("identifier", value, 20)
    with pytest.raises(ConfirmationValidationError, match="fingerprint is invalid"):
        validate_fingerprint("fingerprint", "sha256:not-hex")
    with pytest.raises(ConfirmationValidationError, match="preview is invalid"):
        validate_preview(cast(Any, object()))
    with pytest.raises(ConfirmationValidationError, match="irreversible flag"):
        validate_preview(
            ConfirmationPreview(
                effect_summary="Reviewed operation",
                irreversible=cast(Any, "no"),
            )
        )


def test_confirmation_preview_text_validation_covers_required_optional_and_bounds() -> None:
    with pytest.raises(ConfirmationValidationError, match="effect summary is required"):
        _validate_preview_text("effect summary", None, required=True)
    assert _validate_preview_text("recovery", None, required=False) is None
    with pytest.raises(ConfirmationValidationError, match="effect summary is required"):
        _validate_preview_text("effect summary", "   ", required=True)
    assert _validate_preview_text("recovery", "   ", required=False) is None
    with pytest.raises(ConfirmationValidationError, match="exceeds"):
        _validate_preview_text("effect summary", "x" * 501, required=True)
    with pytest.raises(ConfirmationValidationError, match="contains unsafe data"):
        _validate_preview_text(
            "effect summary",
            "Authorization: Bearer synthetic-value-for-redaction",
            required=True,
        )


def test_missing_state_revision_metadata_is_treated_as_corruption(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        repository.connection.execute("DELETE FROM schema_metadata")
        with pytest.raises(state.StateCorruptError, match="state revision metadata is missing"):
            repository._commit_state_revision()
